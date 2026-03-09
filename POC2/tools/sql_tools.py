"""
tools/sql_tools.py
AI Data Assistant — POC2

SQL tools available to the SQL Agent. All tools now accept a `database_key`
parameter that identifies which database in the catalog to connect to.

Tools:
  get_schema_summary(database_key)          — compact schema for a specific DB
  get_table_sample(database_key, table)     — sample rows from a specific table
  execute_sql_query(database_key, sql)      — execute a validated SELECT query
"""

import json
from typing import Annotated
from loguru import logger

from db.connection import get_mssql_connection, validate_readonly_sql
from db.catalog import get_available_database_entry, get_schemas_for_database, build_schema_filter_sql


# ── get_schema_summary ────────────────────────────────────────────────────────

def get_schema_summary(
    database_key: Annotated[
        str,
        "The database key to query (e.g. 'StudentDB', 'CourseDB'). "
        "Must be one of the keys from the database catalog provided to you.",
    ],
) -> str:
    """
    Returns a compact one-line-per-table schema summary for the specified
    database. Only tables in the allowed schemas (as defined in the catalog)
    are included.

    Format per line:
        SCHEMA.TABLE_NAME: col1 (type), col2 (type), ...

    Use this before writing a query to discover available tables and columns.
    """
    logger.info(f"[SCHEMA] Fetching schema summary for database: {database_key}")

    entry = get_available_database_entry(database_key)
    if entry is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown database key: '{database_key}'. "
                     "Use a key from the database catalog.",
        })

    schemas = get_schemas_for_database(database_key)
    schema_filter = build_schema_filter_sql(schemas)

    schema_sql = f"""
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
          AND t.TABLE_SCHEMA IN {schema_filter}
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
    """

    try:
        with get_mssql_connection(entry["database_name"]) as conn:
            cursor = conn.cursor()
            cursor.execute(schema_sql)
            rows = cursor.fetchall()

        tables: dict = {}
        for schema_name, table_name, col_name, data_type, nullable in rows:
            key = f"{schema_name}.{table_name}"
            if key not in tables:
                tables[key] = []
            null_marker = "" if nullable == "YES" else " NOT NULL"
            tables[key].append(f"{col_name} ({data_type}{null_marker})")

        compact_lines = [
            f"{tbl}: {', '.join(cols)}"
            for tbl, cols in sorted(tables.items())
        ]

        table_count = len(tables)
        logger.info(f"[SCHEMA] {database_key} — {table_count} tables found")

        return json.dumps({
            "success": True,
            "database": database_key,
            "table_count": table_count,
            "format": "compact",
            "schema": "\n".join(compact_lines),
            "instructions": (
                f"Each line is: SCHEMA.TABLE: col (type), col (type), ... "
                f"These are tables in the '{database_key}' database. "
                "Use SCHEMA.TABLE notation in your SELECT query (e.g. dbo.students). "
                "Do NOT generate CREATE TABLE statements. "
                "Your task is to write a SELECT query to answer the user's question."
            ),
        })

    except Exception as e:
        logger.error(f"[SCHEMA ERROR] {database_key}: {e}")
        return json.dumps({"success": False, "database": database_key, "error": str(e)})


# ── get_table_sample ──────────────────────────────────────────────────────────

def get_table_sample(
    database_key: Annotated[
        str,
        "The database key (e.g. 'StudentDB'). Must match a key in the catalog.",
    ],
    table_name: Annotated[
        str,
        "Schema-qualified table name (e.g. 'dbo.students', 'Academic.grades').",
    ],
    sample_rows: Annotated[
        int,
        "Number of sample rows to return (max 10).",
    ] = 5,
) -> str:
    """
    Returns a small sample of rows from a specific table in the specified
    database. Use this to understand actual data values before writing a query
    (e.g. to check date formats, enum values, how a field is stored).
    """
    logger.info(f"[SAMPLE] {database_key} → {table_name} ({sample_rows} rows)")

    entry = get_available_database_entry(database_key)
    if entry is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown database key: '{database_key}'.",
        })

    # Clamp sample rows
    sample_rows = max(1, min(sample_rows, 10))

    # Validate table_name format (schema.table) to prevent injection
    import re
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$", table_name):
        return json.dumps({
            "success": False,
            "error": (
                f"Invalid table_name format: '{table_name}'. "
                "Use schema-qualified format, e.g. 'dbo.students'."
            ),
        })

    # Confirm the schema is in the allowed list for this database
    schema_part = table_name.split(".")[0]
    allowed_schemas = get_schemas_for_database(database_key)
    if schema_part not in allowed_schemas:
        return json.dumps({
            "success": False,
            "error": (
                f"Schema '{schema_part}' is not in the allowed schemas for "
                f"'{database_key}'. Allowed schemas: {allowed_schemas}"
            ),
        })

    sample_sql = f"SELECT TOP {sample_rows} * FROM {table_name}"

    try:
        with get_mssql_connection(entry["database_name"]) as conn:
            cursor = conn.cursor()
            cursor.execute(sample_sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            row_dicts = [dict(zip(columns, row)) for row in rows]

        logger.info(f"[SAMPLE] {database_key}.{table_name} — {len(row_dicts)} rows returned")
        return json.dumps({
            "success": True,
            "database": database_key,
            "table": table_name,
            "columns": columns,
            "rows": row_dicts,
            "row_count": len(row_dicts),
        }, default=str)

    except Exception as e:
        logger.error(f"[SAMPLE ERROR] {database_key}.{table_name}: {e}")
        return json.dumps({"success": False, "database": database_key, "table": table_name, "error": str(e)})


# ── execute_sql_query ─────────────────────────────────────────────────────────

def execute_sql_query(
    database_key: Annotated[
        str,
        "The database key to run the query against (e.g. 'StudentDB'). "
        "Must match a key in the database catalog.",
    ],
    sql: Annotated[
        str,
        "The SELECT query to execute. Must be read-only — no INSERT, UPDATE, "
        "DELETE, DROP, ALTER, EXEC, or TRUNCATE.",
    ],
) -> str:
    """
    Executes a validated read-only SELECT query against the specified database
    and returns the results as JSON.

    Results are capped at 1000 rows. If the query returns more, the caller
    is advised to refine with GROUP BY or TOP.
    """
    logger.info(f"[SQL] execute_sql_query on '{database_key}' | SQL: {sql[:100]}...")

    entry = get_available_database_entry(database_key)
    if entry is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown database key: '{database_key}'.",
        })

    # Validate read-only
    is_safe, reason = validate_readonly_sql(sql)
    if not is_safe:
        return json.dumps({"success": False, "error": reason})

    try:
        with get_mssql_connection(entry["database_name"]) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)

            if cursor.description is None:
                # Non-SELECT statement slipped through — return empty result
                logger.warning(f"[SQL] Query returned no cursor description: {sql[:80]}")
                return json.dumps({
                    "success": False,
                    "error": "Query did not return a result set. Only SELECT queries are allowed.",
                })

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchmany(1000)
            row_dicts = [dict(zip(columns, row)) for row in rows]

        truncated = len(row_dicts) == 1000
        logger.info(
            f"[SQL] {database_key} — {len(row_dicts)} rows returned"
            + (" (truncated at 1000)" if truncated else "")
        )

        result = {
            "success": True,
            "database": database_key,
            "columns": columns,
            "rows": row_dicts,
            "row_count": len(row_dicts),
        }
        if truncated:
            result["warning"] = (
                "Results truncated at 1000 rows. Consider adding TOP, "
                "WHERE filters, or GROUP BY to your query."
            )

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error(f"[SQL ERROR] {database_key}: {e} | SQL: {sql[:120]}")
        return json.dumps({"success": False, "database": database_key, "error": str(e)})
