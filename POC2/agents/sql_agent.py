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
Your ONLY job is to answer the user's data question by executing a SELECT query.

The Supervisor has already identified which database you should query.
The target database key will be provided to you in the task — look for a line like:
    TARGET DATABASE: <database_key>

## Step-by-step instructions — follow in this exact order:

STEP 1 — Identify the database_key from the task context (e.g. "StudentDB").
          You will use this key in EVERY tool call below.

STEP 2 — Call get_schema_summary(database_key=<key>) to see the available
          tables and columns in that database.

STEP 3 — Identify which table(s) and column(s) are relevant to the question.
          If you are unsure what values a column contains, call
          get_table_sample(database_key=<key>, table_name="schema.table").

STEP 4 — Write a SELECT query. Rules:
          - Use only SELECT. NEVER write CREATE, INSERT, UPDATE, DELETE, DROP,
            ALTER, TRUNCATE, EXEC, or EXECUTE.
          - Qualify all table names with their schema (e.g. dbo.enrollments,
            Academic.grades — never just the table name alone).
          - Use TOP 1000 or GROUP BY as appropriate. Do not return unbounded
            result sets.
          - Do not invent column names. Only use names from the schema.

STEP 5 — Call execute_sql_query(database_key=<key>, sql=<your SELECT>).

STEP 6 — When you receive the results, respond with this exact format:

QUERY_COMPLETE
SQL: <the SELECT statement you executed>
RESULT: <plain English summary of what the results show>
DATA: <the JSON rows from the result>

## What NOT to do:
- Do NOT generate CREATE TABLE statements.
- Do NOT skip the execute_sql_query() step. Always run the query.
- Do NOT make up data. If execute_sql_query() returns zero rows, say so honestly.
- Do NOT use a different database_key than the one provided in the task.

## Error handling:
If execute_sql_query() returns an error, check the SQL for mistakes and try
once more with a corrected query. If it fails a second time, report:
QUERY_FAILED
Reason: <error>
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
            "num_ctx": 8192,
            "num_predict": 2048,
        },
    )

    tools = [
        FunctionTool(get_schema_summary, description=(
            "Retrieve a compact schema summary (tables and columns) for a specific "
            "database. Call this first before writing any SQL query."
        )),
        FunctionTool(get_table_sample, description=(
            "Retrieve a small sample of rows from a specific table to understand "
            "data formats and values."
        )),
        FunctionTool(execute_sql_query, description=(
            "Execute a read-only SELECT query against a specific database and "
            "return the results."
        )),
    ]

    return AssistantAgent(
        name="SQLAgent",
        model_client=model_client,
        tools=tools,
        system_message=_SYSTEM_MESSAGE,
        reflect_on_tool_use=True,
    )
