"""
orchestration/supervisor.py
AI Data Assistant — POC2

Supervisor: the entry point for all user queries.

Phase 1 flow:
  1. classify_intent()      — DATA_QUERY or UNKNOWN
  2. route_to_database()    — identify which database to query (new in multi-DB)
  3. run_data_query_pipeline(user_query, database_key)
                            — SQL Agent → Validation Agent

The database routing uses the catalog in config/databases.json.
The resolved database_key is injected into the SQL Agent's task context.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily, UserMessage, SystemMessage

from config.settings import settings
from db.catalog import build_catalog_context, get_all_database_keys, get_database_entry, get_available_database_entry
from agents.sql_agent import build_sql_agent
from agents.validation_agent import build_validation_agent
from utils.response_normaliser import normalise


# ── Data structures ───────────────────────────────────────────────────────────

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
    database_key: str | None = None          # which DB was queried


@dataclass
class ConversationTurn:
    """A single turn in a multi-turn conversation."""
    user_query: str
    assistant_response: str
    database_key: Optional[str] = None
    sql_executed: Optional[str] = None


# ── Intent extraction ─────────────────────────────────────────────────────────

_DATA_QUERY_PATTERNS = re.compile(
    r"\b(DATA_QUERY|data.query|how many|how much|count|total|sum|average|"
    r"show me|show all|list|report|enrollment|enrol|student|faculty|course|"
    r"retention|graduation|completion|headcount|fte|credit|semester|"
    r"academic|department|college|program|degree|financial|"
    r"trend|compare|breakdown|group.?by|statistics|stats|data|tables?|"
    r"warehouse|database|query|queries|schema|records?|employee|staff|"
    r"payroll|salary|schedule|section|curriculum|tuition|aid|billing)\b",
    re.IGNORECASE,
)


def _extract_intent_from_text(text: str, original_query: str) -> str:
    if not text:
        return _fallback_intent(original_query)

    cleaned = re.sub(
        r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE
    ).strip()

    upper = cleaned.upper().strip().strip(".,!?;:\n ")
    if upper == "DATA_QUERY":
        return Intent.DATA_QUERY
    if upper == "UNKNOWN":
        return Intent.UNKNOWN

    if "DATA_QUERY" in cleaned.upper():
        return Intent.DATA_QUERY
    if "UNKNOWN" in cleaned.upper():
        return Intent.UNKNOWN

    logger.warning(
        f"[SUPERVISOR] Model gave verbose intent response. "
        f"Raw (first 120 chars): {text[:120]!r}. Falling back to pattern match."
    )
    return _fallback_intent(original_query)


def _fallback_intent(user_query: str) -> str:
    if _DATA_QUERY_PATTERNS.search(user_query):
        logger.info("[SUPERVISOR] Pattern-match fallback → DATA_QUERY")
        return Intent.DATA_QUERY
    logger.info("[SUPERVISOR] Pattern-match fallback → UNKNOWN")
    return Intent.UNKNOWN


# ── Intent classifier ─────────────────────────────────────────────────────────

_SUPERVISOR_SYSTEM = (
    "You are an intent classifier. "
    "Respond with ONLY one of these two words: DATA_QUERY or UNKNOWN. "
    "DATA_QUERY: the user wants to retrieve, count, list, compare, or analyse "
    "data from the university database (students, enrollment, courses, "
    "retention, grades, financials, departments, employees, payroll, "
    "schedules, tables, etc.). "
    "UNKNOWN: anything else — greetings, general knowledge, weather, jokes, etc. "
    "Your ENTIRE response must be exactly one word: DATA_QUERY or UNKNOWN. "
    "Do NOT include any explanation, punctuation, or other text."
)


async def classify_intent(user_query: str) -> str:
    """
    Classify the user's intent as DATA_QUERY or UNKNOWN.
    Uses Qwen3 with R1 family (strips <think> blocks) and falls back to
    keyword pattern matching if the model returns a verbose response.
    """
    client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        model_info=ModelInfo(
            vision=False,
            function_calling=False,
            json_output=False,
            family=ModelFamily.R1,
            structured_output=False,
        ),
        options={
            "temperature": 0.0,
            # No num_predict cap: Qwen3 thinking mode emits a <think> block
            # before the answer token — capping tokens cuts off mid-think and
            # returns an empty string. The R1 family strips <think> blocks
            # automatically; the fallback pattern matcher handles empty output.
            "num_ctx": 2048,
        },
    )
    try:
        result = await client.create(
            messages=[
                SystemMessage(content=_SUPERVISOR_SYSTEM, source="system"),
                UserMessage(content=f"Classify: {user_query}", source="user"),
            ]
        )
        raw = result.content if isinstance(result.content, str) else str(result.content)
        intent = _extract_intent_from_text(raw, user_query)
        logger.info(f"[SUPERVISOR] Intent: {intent} | raw: {raw[:80]!r}")
        return intent
    except Exception as e:
        logger.error(f"[SUPERVISOR] Classification error: {e}")
        return _fallback_intent(user_query)
    finally:
        await client.close()


# ── Database router ───────────────────────────────────────────────────────────

def _build_db_router_system(catalog_context: str) -> str:
    return (
        "You are a database router for a university analytics system. "
        "Your job is to read the user's question and decide which database "
        "contains the data needed to answer it. "
        "You must respond with ONLY the database key — nothing else. "
        "No explanation, no punctuation, no extra text.\n\n"
        "Available databases:\n\n"
        f"{catalog_context}\n\n"
        "Rules:\n"
        "- Respond with ONLY the database key exactly as shown above "
        "(e.g. StudentDB, CourseDB, FinanceDB, HRDatabase).\n"
        "- If the question clearly belongs to one database, return that key.\n"
        "- If uncertain, prefer StudentDB for anything about students or enrollment.\n"
        "- Never return more than one word."
    )


def _fallback_db_route(user_query: str) -> str:
    """
    Keyword-based fallback for database routing when the LLM gives a bad response.
    Returns a database key from the catalog, defaulting to the first available.

    Routing logic for the EDW:
    - Both edw_landing and edw_staging hold similar domains (STDNT, EMP, FIN, etc.)
    - Prefer edw_staging for reporting/analytical queries (already transformed)
    - Prefer edw_landing for raw/snapshot/census queries or when staging may not
      have the specific table (e.g. SURVY schema only exists in edw_landing)
    """
    q = user_query.lower()
    all_keys = get_all_database_keys()

    # Signals that the user wants raw/snapshot data — route to edw_landing
    landing_keywords = [
        "snapshot", "census", "raw", "source", "landing",
        "landing_tables", "update schedule", "last updated",
        "survy", "survey response",
    ]

    # Signals that the user wants reporting/aggregated data — route to edw_staging
    staging_keywords = [
        "retention", "graduation", "completion rate", "headcount",
        "fte", "trend", "report", "dashboard", "staging",
        "staging_tables", "year over year", "cohort",
    ]

    if any(kw in q for kw in landing_keywords):
        key = "edw_landing"
    elif any(kw in q for kw in staging_keywords):
        key = "edw_staging"
    else:
        # Default: prefer edw_staging for general analytical queries
        key = "edw_staging"

    # Confirm key exists and is available; fall back to first available key
    if get_available_database_entry(key) is None and all_keys:
        key = all_keys[0]

    logger.info(f"[DB ROUTER] Keyword fallback → {key}")
    return key


async def route_to_database(user_query: str) -> str:
    """
    Determines which database in the catalog should be queried for the given
    user question. Returns a database key (e.g. "StudentDB").

    Two-stage approach:
    1. Ask the LLM (Qwen3 in classification mode)
    2. If the LLM response is not a valid catalog key, fall back to keyword matching
    """
    catalog_context = build_catalog_context()
    all_keys = get_all_database_keys()

    client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        model_info=ModelInfo(
            vision=False,
            function_calling=False,
            json_output=False,
            family=ModelFamily.R1,
            structured_output=False,
        ),
        options={
            "temperature": 0.0,
            # No num_predict cap — same reason as classify_intent above.
            "num_ctx": 4096,
        },
    )

    try:
        result = await client.create(
            messages=[
                SystemMessage(
                    content=_build_db_router_system(catalog_context),
                    source="system",
                ),
                UserMessage(
                    content=f"Which database should I query for: {user_query}",
                    source="user",
                ),
            ]
        )
        raw = result.content if isinstance(result.content, str) else str(result.content)

        # Strip think blocks, whitespace, punctuation
        cleaned = re.sub(
            r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE
        ).strip().strip(".,!?;:\n ")

        # Check if the cleaned response matches a known key (case-insensitive)
        cleaned_lower = cleaned.lower()
        for key in all_keys:
            if key.lower() == cleaned_lower:
                logger.info(f"[DB ROUTER] LLM chose: {key}")
                return key

        # The LLM returned something that doesn't match a key — log and fall back
        logger.warning(
            f"[DB ROUTER] LLM returned unrecognised key: {cleaned!r}. "
            "Falling back to keyword routing."
        )
        return _fallback_db_route(user_query)

    except Exception as e:
        logger.error(f"[DB ROUTER] Routing error: {e}. Falling back to keyword routing.")
        return _fallback_db_route(user_query)
    finally:
        await client.close()


# ── Phase 1 pipeline ──────────────────────────────────────────────────────────

async def run_data_query_pipeline(
    user_query: str,
    database_key: str,
    history: Optional[list[ConversationTurn]] = None,
) -> QueryResult:
    """
    Runs the SQL Agent → Validation Agent pipeline for a DATA_QUERY intent.
    The resolved database_key is injected into the task so the SQL Agent
    knows which database to connect to. If history is provided, a concise
    context summary is prepended to help the agent resolve references to
    previous questions (e.g. "same semester", "that table", "now by gender").
    """
    sql_agent = build_sql_agent()
    validation_agent = build_validation_agent()

    termination = TextMentionTermination("QUERY_COMPLETE") | \
                  TextMentionTermination("QUERY_FAILED") | \
                  TextMentionTermination("VALIDATION_PASSED") | \
                  TextMentionTermination("VALIDATION_FAILED") | \
                  TextMentionTermination("VALIDATION_WARNING") | \
                  TextMentionTermination("CLARIFICATION_NEEDED") | \
                  MaxMessageTermination(12)

    team = RoundRobinGroupChat(
        participants=[sql_agent, validation_agent],
        termination_condition=termination,
    )

    # Build conversation context summary from history (last 3 turns max)
    history_context = ""
    if history:
        recent = history[-3:]
        lines = ["Previous conversation context (for resolving references):"]
        for i, turn in enumerate(recent, 1):
            lines.append(f"  Turn {i} — User asked: {turn.user_query}")
            if turn.sql_executed:
                lines.append(f"           SQL used: {turn.sql_executed}")
            lines.append(f"           Assistant answered: {turn.assistant_response[:200]}")
        history_context = "\n".join(lines) + "\n\n"

    # Inject database key, optional history, and the current question
    task_with_db = (
        f"TARGET DATABASE: {database_key}\n\n"
        + history_context
        + f"Current question: {user_query}"
    )

    message_trace: list[str] = []
    final_response: str = ""
    validation_status: str = "UNKNOWN"
    sql_executed: str | None = None
    raw_data: list | None = None

    try:
        async for event in team.run_stream(task=task_with_db):
            if not (hasattr(event, "source") and hasattr(event, "content")):
                continue

            # event.content can be a list (FunctionCall/FunctionExecutionResult)
            # or a string (text message). Only process string content for parsing.
            content_str = event.content if isinstance(event.content, str) else None

            # Always trace — repr for non-string content so it's readable
            trace_text = content_str if content_str is not None else repr(event.content)
            entry = f"[{event.source}] {trace_text}"
            message_trace.append(entry)
            logger.debug(entry[:300])

            if content_str is None:
                # Tool call or tool result — nothing to parse as text
                continue

            content_upper = content_str.upper()

            # Capture clarification request from SQL Agent
            if "CLARIFICATION_NEEDED" in content_upper and event.source == "SQLAgent":
                # Extract the question text after "Question:"
                question_text = content_str
                if "Question:" in content_str:
                    question_text = content_str.split("Question:", 1)[-1].strip()
                validation_status = "CLARIFICATION_NEEDED"
                final_response = question_text
                logger.info(f"[PIPELINE] SQL Agent requested clarification: {question_text[:100]}")

            # Capture validation status
            for status in ("VALIDATION_PASSED", "VALIDATION_FAILED", "VALIDATION_WARNING"):
                if status in content_upper:
                    validation_status = status
                    if not final_response:
                        after = content_str.split(status, 1)[-1].strip()
                        final_response = normalise(after) if after else ""

            # Capture SQL and DATA from SQL agent text output
            if event.source == "SQLAgent":
                if "SQL:" in content_str:
                    lines = content_str.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip().startswith("SQL:"):
                            sql_executed = line.replace("SQL:", "").strip()
                            j = i + 1
                            while j < len(lines) and not lines[j].startswith(
                                ("RESULT:", "DATA:", "QUERY_COMPLETE", "QUERY_FAILED")
                            ):
                                sql_executed += " " + lines[j].strip()
                                j += 1
                            sql_executed = sql_executed.strip()

                if "DATA:" in content_str:
                    data_part = content_str.split("DATA:")[-1].strip()
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
            database_key=database_key,
        )

    if not final_response:
        final_response = normalise(
            message_trace[-1].split("]", 1)[-1].strip() if message_trace else ""
        )

    # CLARIFICATION_NEEDED is not a failure — it's an intentional agent response
    success = validation_status in ("VALIDATION_PASSED", "VALIDATION_WARNING", "CLARIFICATION_NEEDED")

    return QueryResult(
        success=success,
        intent=Intent.DATA_QUERY,
        user_query=user_query,
        final_response=final_response,
        validation_status=validation_status,
        sql_executed=sql_executed,
        raw_data=raw_data,
        error=None if success else "Query could not be validated — see final_response.",
        message_trace=message_trace,
        database_key=database_key,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_query(
    user_query: str,
    history: Optional[list[ConversationTurn]] = None,
) -> QueryResult:
    """
    Main entry point. Classifies intent, routes to a database, then runs
    the appropriate pipeline.

    Pass `history` (a list of ConversationTurn) to give the SQL Agent
    context from previous turns in the same session. The history is
    summarised and prepended to the task so the agent understands
    references like "same semester", "that table", "now show by gender", etc.
    """
    # Step 1 — intent classification
    intent = await classify_intent(user_query)

    if intent != Intent.DATA_QUERY:
        return QueryResult(
            success=False,
            intent=intent,
            user_query=user_query,
            final_response=(
                "I'm not sure I can help with that. "
                "I'm currently set up to answer questions about university data — "
                "things like enrollment, retention, course completions, employee records, "
                "financial aid, and similar reports. "
                "Could you rephrase your question in those terms?"
            ),
            validation_status="N/A",
            sql_executed=None,
            raw_data=None,
            error="Intent not supported in Phase 1",
            message_trace=[],
            database_key=None,
        )

    # Step 2 — database routing (new in multi-DB)
    database_key = await route_to_database(user_query)
    logger.info(f"[SUPERVISOR] Routing DATA_QUERY to database: {database_key}")

    # Step 3 — run pipeline
    return await run_data_query_pipeline(user_query, database_key, history=history)
