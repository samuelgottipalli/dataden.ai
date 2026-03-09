"""
agents/sql_agent.py
AI Data Assistant — POC2

SQL Agent: given a user intent and a target database key, generates and
executes a SQL query against the appropriate MS SQL database.

The database routing decision (which database_key to use) is made by the
Supervisor BEFORE this agent is invoked. The resolved database_key is
injected into this agent's task context by the supervisor pipeline.

Tools available to this agent:
  - get_schema_summary(database_key)
  - get_table_sample(database_key, table_name, sample_rows)
  - execute_sql_query(database_key, sql)
"""

from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily
from config.settings import settings
from tools.sql_tools import execute_sql_query, get_schema_summary, get_table_sample

_SYSTEM_MESSAGE = """
You are a SQL Data Agent for a university data warehouse (MS SQL Server).
Your job is to answer the user's data question by writing and executing a SELECT query,
or to ask a single focused clarifying question when the question is genuinely ambiguous.

The Supervisor has already chosen which database to query.
The task will start with a line: TARGET DATABASE: <database_key>
Use that exact key in every tool call.

━━━ MANDATORY STEPS — follow in this exact order, every time ━━━

STEP 1  Read the TARGET DATABASE line. Note the database_key.

STEP 2  Call get_schema_summary(database_key=<key>).
        This returns a list of tables as: SCHEMA.TABLE: col (type), col (type), ...
        Read it carefully to find which tables are relevant.

STEP 3  Decide: can you write a reasonable query from the available schema?

        ► If YES — proceed to STEP 4. This is the default path.

        ► If the question is genuinely ambiguous in a way that would change the
          query significantly (e.g. which academic year, headcount vs FTE,
          active students only vs all), ask ONE short clarifying question and
          respond in this format:

          CLARIFICATION_NEEDED
          Question: <your single focused question, offering 2-3 options where possible>

          Do NOT ask for clarification just because you are uncertain which
          table to use — that is what get_table_sample() is for.
          Do NOT ask multiple questions at once.

STEP 4  Pick the best table(s). Key conventions in this EDW:
        - Dimension tables have a prefix "D_" or suffix "_TBL" — join them
          to get human-readable labels (ethnicity names, dept names, etc.)
        - CENSUS_ or _SNAPSHOT tables are point-in-time snapshots — prefer
          these for term/semester-specific questions.
        - If unsure how a value is stored (code vs label, date format, etc.),
          call get_table_sample() on that table before writing the query.

STEP 5  Write a SELECT query:
        - SELECT only. NEVER write INSERT, UPDATE, DELETE, DROP, ALTER,
          CREATE, TRUNCATE, EXEC, or EXECUTE.
        - Always qualify table names with their schema: SCHEMA.TABLE
          (e.g. STDNT.Enrollment — never just Enrollment).
        - Use TOP 1000 for detail queries, GROUP BY + aggregates for summaries.
          Never return an unbounded result set.
        - Only use column names that appear in the schema — do NOT invent names.
        - Filter by semester/term using the exact values stored in the table.
          If unsure of the format, call get_table_sample() first.

STEP 6  Call execute_sql_query(database_key=<key>, sql=<your SELECT>).

STEP 7  When results are returned, respond EXACTLY in this format:

QUERY_COMPLETE
SQL: <the exact SELECT statement you executed>
RESULT: <2-4 sentence plain-English summary of what the data shows>
DATA: <the full JSON rows array from the result>

━━━ RULES ━━━

- Do NOT ask about things you can find out yourself using get_table_sample().
- Do NOT ask multiple clarifying questions — one at a time only.
- Do NOT fabricate data. If the query returns zero rows, say so in RESULT.
- Do NOT skip execute_sql_query(). Always run the query.
- Do NOT generate CREATE TABLE or DDL statements.
- Do NOT use a database_key other than the one in the task.

If execute_sql_query() returns an error, fix the SQL and retry once.
If it fails a second time, respond:
QUERY_FAILED
Reason: <exact error>
""".strip()


def build_sql_agent() -> AssistantAgent:
    """Build and return the SQL Agent instance."""
    model_client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family=ModelFamily.R1,
            structured_output=False,
        ),
        options={
            "temperature": 0.0,
            "num_ctx": 16384,   # large enough for schema dump + query + results
        },
    )

    tools = [
        FunctionTool(get_schema_summary, description=(
            "Retrieve a compact schema summary (all tables and columns) for a "
            "specific database. ALWAYS call this first before writing any SQL."
        )),
        FunctionTool(get_table_sample, description=(
            "Retrieve a small sample of rows from a specific table. Use this to "
            "understand how values are stored (formats, codes vs labels, date "
            "formats, etc.) before writing a query."
        )),
        FunctionTool(execute_sql_query, description=(
            "Execute a read-only SELECT query against a specific database and "
            "return the results as JSON. Always call this — never skip execution."
        )),
    ]

    return AssistantAgent(
        name="SQLAgent",
        model_client=model_client,
        tools=tools,
        system_message=_SYSTEM_MESSAGE,
        reflect_on_tool_use=True,
    )
