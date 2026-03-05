"""
agents/sql_agent.py
AI Data Assistant — POC2

SQL Agent: given a user intent (natural language), generates and executes
a SQL query against the MS SQL data warehouse.

Tools available to this agent:
  - get_schema_summary()  — discover available tables/columns (compact format)
  - get_table_sample()    — inspect sample data values in a specific table
  - execute_sql_query()   — run a validated SELECT query and get results
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

## Step-by-step instructions — follow in this exact order:

STEP 1 — Call get_schema_summary() to see the available tables and columns.
STEP 2 — Identify which table(s) and column(s) are relevant to the user's question.
          If you are unsure what values a column contains, call get_table_sample() on that table.
STEP 3 — Write a SELECT query. Rules:
          - Use only SELECT. NEVER write CREATE, INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE.
          - Qualify all table names with their schema (e.g. dbo.enrollments, not just enrollments).
          - Use TOP 1000 or GROUP BY as appropriate. Do not return unbounded result sets.
          - Do not invent column names. Use only names from the schema.
STEP 4 — Call execute_sql_query() with your SELECT statement.
STEP 5 — When you receive the results, respond with this exact format:

QUERY_COMPLETE
SQL: <the SELECT statement you executed>
RESULT: <plain English summary of what the results show>
DATA: <the JSON rows from the result>

## What NOT to do:
- Do NOT generate CREATE TABLE statements.
- Do NOT describe how to convert schema to DDL.
- Do NOT explain what you would do. Just do it.
- Do NOT skip the execute_sql_query() step. Always run the query.
- Do NOT make up data. If execute_sql_query() returns zero rows, say so honestly.

## Error handling:
If execute_sql_query() returns an error, check the SQL for mistakes and try once more
with a corrected query. If it fails again, report QUERY_FAILED with the error.
""".strip()


def build_sql_agent() -> AssistantAgent:
    """Build and return the SQL Agent instance."""

    model_client = OllamaChatCompletionClient(
        model=settings.ollama_model,
        host=settings.ollama_host,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=ModelFamily.R1,  # strips <think> blocks from content
            structured_output=True,
        ),
        options={
            "temperature": 0.1,
            "num_ctx": 8192,
        },
    )

    tools = [
        FunctionTool(get_schema_summary, description=(
            "Returns the list of all tables and their columns in the data warehouse "
            "in a compact text format. Always call this first before writing any SQL."
        )),
        FunctionTool(get_table_sample, description=(
            "Returns a small sample of rows from a specific table. "
            "Call this when you need to see actual data values — for example, "
            "to check how a semester, sex, or ethnicity column stores its values."
        )),
        FunctionTool(execute_sql_query, description=(
            "Executes a SELECT SQL query against the MS SQL data warehouse and returns "
            "the results as JSON. This is the ONLY way to get data — always call this "
            "after writing your SELECT statement. Only SELECT queries are permitted."
        )),
    ]

    return AssistantAgent(
        name="SQLAgent",
        description="Generates and executes SQL SELECT queries against the data warehouse.",
        model_client=model_client,
        tools=tools,
        system_message=_SYSTEM_MESSAGE,
        reflect_on_tool_use=True,
        max_tool_iterations=8,  # schema + 1-2 samples + execute + 1 retry
    )
