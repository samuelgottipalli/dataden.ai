"""
orchestration/supervisor.py
AI Data Assistant — POC2

Supervisor: the entry point for all user queries in Phase 1.

In Phase 1, the Supervisor handles exactly one intent type:
  DATA_QUERY — route to SQL Agent → Validation Agent

In Phase 2+, additional intent types will be added:
  GENERAL    → General Assistant
  ANALYSIS   → Analysis Agent
  EXPORT     → Export Agent
"""

import asyncio
import json
import re
from dataclasses import dataclass
from loguru import logger

from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily, UserMessage, SystemMessage

from config.settings import settings
from agents.sql_agent import build_sql_agent
from agents.validation_agent import build_validation_agent
from utils.response_normaliser import normalise


# ── Intent types ─────────────────────────────────────────────────────────────

class Intent:
    DATA_QUERY = "DATA_QUERY"
    UNKNOWN = "UNKNOWN"


@dataclass
class QueryResult:
    """Structured result returned by the supervisor to the caller."""
    success: bool
    intent: str
    user_query: str
    final_response: str
    validation_status: str
    sql_executed: str | None
    raw_data: list | None
    error: str | None
    message_trace: list[str]


# ── Intent extraction (robust, handles verbose Qwen3 output) ──────────────────

# Broad patterns that signal a data retrieval intent
_DATA_QUERY_PATTERNS = re.compile(
    r"\b(DATA_QUERY|data.query|how many|how much|count|total|sum|average|"
    r"show me|show all|list|report|enrollment|enrol|student|faculty|course|"
    r"retention|graduation|completion|headcount|fte|credit|semester|"
    r"academic|department|college|program|degree|financial|"
    r"trend|compare|breakdown|group.?by|statistics|stats|data|tables?|"
    r"warehouse|database|query|queries|schema|records?)\b",
    re.IGNORECASE,
)


def _extract_intent_from_text(text: str, original_query: str) -> str:
    """
    Robustly extract intent from model output.

    Strategy:
    1. Strip <think>...</think> blocks (Qwen3 / R1 reasoning tokens)
    2. Exact keyword match on cleaned text
    3. Substring match for the keyword anywhere in the response
    4. Pattern-match the ORIGINAL user query as a fallback
       (if the model gave garbage output, we decide based on the question itself)
    5. Default to UNKNOWN
    """
    if not text:
        return _fallback_intent(original_query)

    # Step 1: Strip think blocks
    cleaned = re.sub(
        r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    # Step 2: Exact match (ideal case — model obeyed the prompt)
    upper = cleaned.upper().strip().strip(".,!?;:\n ")
    if upper == "DATA_QUERY":
        return Intent.DATA_QUERY
    if upper == "UNKNOWN":
        return Intent.UNKNOWN

    # Step 3: Keyword appears anywhere in the cleaned response
    if "DATA_QUERY" in cleaned.upper():
        return Intent.DATA_QUERY
    if "UNKNOWN" in cleaned.upper():
        return Intent.UNKNOWN

    # Step 4: Model gave a verbose/irrelevant answer — classify from the original query
    logger.warning(
        f"[SUPERVISOR] Model response did not contain a valid intent keyword. "
        f"Raw (first 120 chars): {text[:120]!r}. "
        f"Falling back to query pattern matching."
    )
    return _fallback_intent(original_query)


def _fallback_intent(user_query: str) -> str:
    """Classify intent directly from the user's query text using keyword patterns."""
    if _DATA_QUERY_PATTERNS.search(user_query):
        logger.info("[SUPERVISOR] Pattern-match fallback → DATA_QUERY")
        return Intent.DATA_QUERY
    logger.info("[SUPERVISOR] Pattern-match fallback → UNKNOWN")
    return Intent.UNKNOWN


# ── Supervisor client and classifier ─────────────────────────────────────────

_SUPERVISOR_SYSTEM = (
    "You are an intent classifier. "
    "Respond with ONLY one of these two words: DATA_QUERY or UNKNOWN. "
    "DATA_QUERY: the user wants to retrieve, count, list, compare, or analyse "
    "data from the university database (students, enrollment, courses, "
    "retention, grades, financials, departments, tables, etc.). "
    "UNKNOWN: anything else — greetings, general knowledge, weather, jokes, etc. "
    "Your ENTIRE response must be exactly one word: DATA_QUERY or UNKNOWN. "
    "Do NOT include any explanation, punctuation, or other text."
)


async def classify_intent(user_query: str) -> str:
    """
    Use the Supervisor LLM to classify the user's intent.

    Uses ModelFamily.R1 so AutoGen's OllamaChatCompletionClient calls
    parse_r1_content() to strip <think>...</think> tokens before returning
    result.content — this is the correct family for Qwen3's thinking mode.

    Falls back to direct query pattern matching if the model still returns
    a verbose answer despite the strict system prompt.
    """
    client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        model_info=ModelInfo(
            vision=False,
            function_calling=False,
            json_output=False,
            family=ModelFamily.R1,   # strips <think> blocks from content
            structured_output=False,
        ),
        options={
            "temperature": 0.0,      # fully deterministic
            "num_ctx": 2048,
            "num_predict": 10,       # very short response — just one word needed
        },
    )
    try:
        result = await client.create(
            messages=[
                SystemMessage(content=_SUPERVISOR_SYSTEM, source="system"),
                UserMessage(
                    content=f"Classify: {user_query}",
                    source="user",
                ),
            ]
        )
        raw = result.content if isinstance(result.content, str) else str(result.content)
        intent = _extract_intent_from_text(raw, user_query)
        logger.info(f"[SUPERVISOR] Intent: {intent} | raw response: {raw[:80]!r}")
        return intent
    except Exception as e:
        logger.error(f"[SUPERVISOR] Classification error: {e}")
        # Don't silently fail — try pattern matching on the query itself
        return _fallback_intent(user_query)
    finally:
        await client.close()


# ── Phase 1 pipeline: DATA_QUERY ─────────────────────────────────────────────

async def run_data_query_pipeline(user_query: str) -> QueryResult:
    """
    Run the Phase 1 pipeline:  SQL Agent → Validation Agent
    """
    logger.info(f"[PIPELINE] Starting DATA_QUERY pipeline for: {user_query[:100]}")

    sql_agent = build_sql_agent()
    validation_agent = build_validation_agent()

    termination = (
        TextMentionTermination("VALIDATION_PASSED")
        | TextMentionTermination("VALIDATION_FAILED")
        | MaxMessageTermination(12)
    )

    team = RoundRobinGroupChat(
        [sql_agent, validation_agent],
        termination_condition=termination,
    )

    message_trace: list[str] = []
    final_response = ""
    validation_status = "UNKNOWN"
    sql_executed: str | None = None
    raw_data: list | None = None

    try:
        async for event in team.run_stream(task=user_query):
            if hasattr(event, "content") and isinstance(event.content, str):
                agent_name = getattr(event, "source", "agent")
                msg = f"[{agent_name}] {event.content}"
                message_trace.append(msg)
                logger.debug(msg)

                if hasattr(event, "source") and event.source == "ValidationAgent":
                    final_response = normalise(event.content)
                    if "VALIDATION_PASSED" in event.content:
                        validation_status = "VALIDATION_PASSED"
                    elif "VALIDATION_FAILED" in event.content:
                        validation_status = "VALIDATION_FAILED"
                    elif "VALIDATION_WARNING" in event.content:
                        validation_status = "VALIDATION_WARNING"

                if hasattr(event, "source") and event.source == "SQLAgent":
                    if "SQL:" in event.content:
                        lines = event.content.split("\n")
                        for i, line in enumerate(lines):
                            if line.strip().startswith("SQL:"):
                                sql_executed = line.replace("SQL:", "").strip()
                                j = i + 1
                                while j < len(lines) and not lines[j].startswith(
                                    ("RESULT:", "DATA:", "QUERY_COMPLETE")
                                ):
                                    sql_executed += " " + lines[j].strip()
                                    j += 1
                                sql_executed = sql_executed.strip()

                    if "DATA:" in event.content:
                        data_part = event.content.split("DATA:")[-1].strip()
                        try:
                            parsed = json.loads(data_part)
                            if isinstance(parsed, list):
                                raw_data = parsed
                            elif isinstance(parsed, dict) and "rows" in parsed:
                                raw_data = parsed["rows"]
                        except json.JSONDecodeError:
                            pass

    except Exception as e:
        logger.error(f"[PIPELINE] Pipeline error: {e}")
        return QueryResult(
            success=False,
            intent=Intent.DATA_QUERY,
            user_query=user_query,
            final_response="An internal error occurred while processing your request.",
            validation_status="ERROR",
            sql_executed=None,
            raw_data=None,
            error=str(e),
            message_trace=message_trace,
        )

    if not final_response:
        final_response = normalise(
            message_trace[-1].split("]", 1)[-1].strip() if message_trace else ""
        )

    success = validation_status in ("VALIDATION_PASSED", "VALIDATION_WARNING")

    return QueryResult(
        success=success,
        intent=Intent.DATA_QUERY,
        user_query=user_query,
        final_response=final_response,
        validation_status=validation_status,
        sql_executed=sql_executed,
        raw_data=raw_data,
        error=None if success else "Query could not be validated — see final_response for details.",
        message_trace=message_trace,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_query(user_query: str) -> QueryResult:
    """
    Main entry point. Classifies intent and routes to the appropriate pipeline.
    """
    intent = await classify_intent(user_query)

    if intent == Intent.DATA_QUERY:
        return await run_data_query_pipeline(user_query)

    return QueryResult(
        success=False,
        intent=intent,
        user_query=user_query,
        final_response=(
            "I'm not sure I can help with that. "
            "I'm currently set up to answer questions about university data — "
            "things like enrollment, retention, course completions, and similar reports. "
            "Could you rephrase your question in those terms?"
        ),
        validation_status="N/A",
        sql_executed=None,
        raw_data=None,
        error="Intent not supported in Phase 1",
        message_trace=[],
    )
