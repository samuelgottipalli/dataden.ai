"""
agents/validation_agent.py
AI Data Assistant — POC2

Validation Agent: reviews the SQL Agent's output and checks for:
  - Completeness (did the query actually run?)
  - Sanity (are the numbers plausible?)
  - Safety (does the result contain obvious PII or FERPA-sensitive data?)
  - Format (is the response clean and user-ready?)

The Validation Agent does NOT re-execute queries.
In Phase 1, PII/FERPA checks are basic pattern matching.
Full FERPA enforcement is added in Phase 4.
"""

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily
from config.settings import settings

_SYSTEM_MESSAGE = """
You are a Data Validation Agent for a higher education analytics system.

Your job is to review the output produced by the SQL Agent and confirm it is:
1. COMPLETE — a query was actually executed and results were returned.
2. SENSIBLE — the numbers and values are plausible for a university dataset.
3. SAFE — the response does not expose FERPA-protected individual student data
   (e.g. individual student names combined with grades, SSNs, student IDs linked
   to personal details). Aggregated statistics (counts, averages, percentages) are safe.
4. CLEAR — the response is readable and would make sense to a non-technical staff member.

Validation rules:
- If the SQL Agent returned an error, flag it as VALIDATION_FAILED with the reason.
- If results contain raw individual student records with identifiable information,
  flag as VALIDATION_FAILED with reason: FERPA_RISK.
- If counts/totals are wildly implausible (e.g. enrollment of 0 or 10 million), flag
  as VALIDATION_WARNING with your concern, but still pass the result.
- If everything looks correct, respond with VALIDATION_PASSED followed by a clean,
  plain-English summary of the results suitable for the end user.
- Do not reproduce the full raw data in your response — summarise it.

Response format:
VALIDATION_PASSED
<Clean summary for the end user>

— OR —

VALIDATION_FAILED
Reason: <specific reason>
Suggestion: <what the user or system should do next>

— OR —

VALIDATION_WARNING
Concern: <what seems unusual>
<Clean summary for the end user despite the concern>
""".strip()


def build_validation_agent() -> AssistantAgent:
    """Build and return the Validation Agent instance."""

    model_client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        # Use R1 family so AutoGen cleanly separates <think> content from
        # the actual response text — Qwen3 uses the same format as DeepSeek R1
        model_info=ModelInfo(
            vision=False,
            function_calling=False,
            json_output=False,
            family=ModelFamily.R1,
            structured_output=False,
        ),
        options={
            "temperature": 0.2,
            "num_ctx": 8192,
        },
    )

    return AssistantAgent(
        name="ValidationAgent",
        description="Reviews SQL Agent output for completeness, sanity, and FERPA safety.",
        model_client=model_client,
        system_message=_SYSTEM_MESSAGE,
        reflect_on_tool_use=False,
    )
