"""
tools/sql_tools.py
AI Data Assistant — POC2

Tool functions registered with the SQL Agent.
These are the actual functions that touch the database.
AutoGen calls these as FunctionTools when the agent decides to use them.

All tools are:
  - Read-only (enforced by validate_readonly_sql before every execution)
  - Row-limited (MAX_ROWS cap)
  - Logged (every execution appears in audit log)
"""

import json
from typing import Annotated
from loguru import logger
from db.connection import get_mssql_connection, validate_readonly_sql

# Hard cap on rows returned
MAX_ROWS = 500
# Hard cap on query execution time (seconds)
QUERY_TIMEOUT_SECONDS = 30
# Max tables to return in a full schema summary before switching to compact mode
_SCHEMA_COMPACT_THRESHOLD = 30


def execute_sql_query(
    sql: Annotated[str, "The SELECT SQL query to execute against the data warehouse"],
) -> str:
    """
    Execute a read-only SQL SELECT query against the MS SQL data warehouse.

    Returns a JSON string with keys:
      - success (bool)
      - rows (list of dicts, up to MAX_ROWS)
      - row_count (int)
      - columns (list of str)
      - truncated (bool) — True if results were capped at MAX_ROWS
      - error (str or None)

    Only SELECT statements are permitted. Do not pass INSERT, UPDATE, DELETE,
    DROP, TRUNCATE, ALTER, or any DDL/DML statement.
    """
    is_safe, reason = validate_readonly_sql(sql)
    if not is_safe:
        logger.warning(f"[SQL BLOCKED] {reason}")
        return json.dumps({
            "success": False,
            "rows": [],
            "row_count": 0,
            "columns": [],
            "truncated": False,
            "error": f"Query blocked by safety check: {reason}",
        })

    logger.info(f"[SQL EXECUTE] {sql[:200]}")

    try:
        with get_mssql_connection() as conn:
            conn.timeout = QUERY_TIMEOUT_SECONDS
            cursor = conn.cursor()
            cursor.execute(sql)

            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows_raw = cursor.fetchmany(MAX_ROWS + 1)

            truncated = len(rows_raw) > MAX_ROWS
            rows_raw = rows_raw[:MAX_ROWS]

            rows = []
            for row in rows_raw:
                row_dict = {}
                for col, val in zip(columns, row):
                    if hasattr(val, "isoformat"):
                        row_dict[col] = val.isoformat()
                    elif val is None:
                        row_dict[col] = None
                    else:
                        row_dict[col] = str(val) if not isinstance(val, (int, float, bool)) else val
                rows.append(row_dict)

        logger.info(f"[SQL OK] {len(rows)} rows returned (truncated={truncated})")
        return json.dumps({
            "success": True,
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
            "truncated": truncated,
            "error": None,
        })

    except Exception as e:
        logger.error(f"[SQL ERROR] {e}")
        return json.dumps({
            "success": False,
            "rows": [],
            "row_count": 0,
            "columns": [],
            "truncated": False,
            "error": str(e),
        })


def get_schema_summary() -> str:
    """
    Return the list of tables and their columns available in the data warehouse.

    To keep the output manageable, this returns a COMPACT format:
    each table is shown as one line:
        SCHEMA.TABLE_NAME: col1 (type), col2 (type), ...

    This is the format you should read to decide which tables and columns
    are relevant to the user's question before writing a SQL query.
    Use get_table_sample() if you need to see actual data values in a table.
    """
    logger.info("[SCHEMA] Fetching schema summary")

    schema_sql = """
        SELECT
            t.TABLE_SCHEMA,
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
            ON t.TABLE_NAME = c.TABLE_NAME
            AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """

    try:
        with get_mssql_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(schema_sql)
            rows = cursor.fetchall()

        # Build compact one-line-per-table representation
        tables: dict = {}
        for schema_name, table_name, col_name, data_type, nullable in rows:
            key = f"{schema_name}.{table_name}"
            if key not in tables:
                tables[key] = []
            null_marker = "" if nullable == "YES" else " NOT NULL"
            tables[key].append(f"{col_name} ({data_type}{null_marker})")

        compact_lines = []
        for table_key, columns in sorted(tables.items()):
            col_str = ", ".join(columns)
            compact_lines.append(f"{table_key}: {col_str}")

        table_count = len(tables)
        compact_text = "\n".join(compact_lines)

        logger.info(f"[SCHEMA] {table_count} tables found")
        return json.dumps({
            "success": True,
            "table_count": table_count,
            "format": "compact",
            "schema": compact_text,
            "instructions": (
                "Each line is: SCHEMA.TABLE: col (type), col (type), ... "
                "Use these table and column names directly in your SELECT query. "
                "Do NOT generate CREATE TABLE statements. "
                "Your task is to write a SELECT query to answer the user's question."
            ),
        })

    except Exception as e:
        logger.error(f"[SCHEMA ERROR] {e}")
        return json.dumps({"success": False, "table_count": 0, "schema": "", "error": str(e)})


def get_table_sample(
    table_name: Annotated[str, "The table name (schema-qualified, e.g. dbo.students)"],
    sample_rows: Annotated[int, "Number of sample rows to return (max 10)"] = 5,
) -> str:
    """
    Return a small sample of rows from a specific table.
    Use this to understand the actual data format and values in a table
    before writing a query — e.g. to check date formats, enum values,
    or how a field like 'semester' or 'sex' is stored.

    Returns JSON with sample rows and column names.
    """
    sample_rows = min(sample_rows, 10)

    import re
    if not re.match(r"^[a-zA-Z0-9_\.\[\]]+$", table_name):
        return json.dumps({
            "success": False,
            "error": f"Invalid table name: {table_name}",
        })

    sql = f"SELECT TOP {sample_rows} * FROM {table_name}"
    logger.info(f"[SAMPLE] {sql}")
    return execute_sql_query(sql)
