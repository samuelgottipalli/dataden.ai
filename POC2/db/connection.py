"""
db/connection.py
AI Data Assistant — POC2

Manages connections to:
  - MS SQL Server (data warehouse — read-only, multi-database)
  - PostgreSQL (operational database — audit logs, RAG store, sessions)

Usage:
    from db.connection import get_mssql_connection, get_postgres_connection

    # Connect to a specific database (key from databases.json)
    with get_mssql_connection("StudentDB") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.students")
        ...
"""

import pyodbc
import psycopg2
import re
from loguru import logger
from typing import Optional
from config.settings import settings


# ─────────────────────────────────────────────────────────────
# MS SQL Server
# ─────────────────────────────────────────────────────────────

# Keywords that must never appear in a query going to the data warehouse.
# Defence-in-depth on top of the read-only DB account.
_DISALLOWED_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
    "ALTER", "CREATE", "EXEC", "EXECUTE", "MERGE",
    "GRANT", "REVOKE", "DENY",
}


def validate_readonly_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    Checks that a SQL string contains no write or DDL operations.

    Returns:
        (True, None)          — safe to execute
        (False, reason_str)   — blocked, reason explains why
    """
    normalised = sql.upper()
    for keyword in _DISALLOWED_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalised):
            reason = f"Query contains disallowed operation: {keyword}"
            logger.warning(f"[SQL BLOCK] {reason} | Query preview: {sql[:120]}")
            return False, reason
    return True, None


def get_mssql_connection(database: str) -> pyodbc.Connection:
    """
    Opens and returns a new pyodbc connection to the specified MS SQL database.

    The `database` parameter must be one of the keys defined in
    config/databases.json (e.g. "StudentDB", "CourseDB").

    The connection is intentionally not pooled — each caller is responsible
    for closing it. Use as a context manager:

        with get_mssql_connection("StudentDB") as conn:
            cursor = conn.cursor()
            ...

    Raises:
        ValueError  — if `database` is empty or None
        pyodbc.Error — if the connection cannot be established
    """
    if not database:
        raise ValueError("database parameter is required for get_mssql_connection()")

    conn_str = settings.mssql_connection_string(database)
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        logger.debug(f"MSSQL connection opened → {database}")
        return conn
    except pyodbc.Error as e:
        logger.error(f"Failed to connect to MS SQL Server [{database}]: {e}")
        raise


def test_mssql_connection(database: str) -> dict:
    """
    Verifies the MS SQL Server connection for a specific database.
    Returns a status dict with keys: success, server_version, visible_tables, error.
    """
    try:
        with get_mssql_connection(database) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version_row = cursor.fetchone()
            version = version_row[0].split("\n")[0].strip() if version_row else "Unknown"

            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE'"
            )
            table_count = cursor.fetchone()[0]

        logger.info(f"MSSQL [{database}] OK | Tables visible: {table_count}")
        return {
            "success": True,
            "database": database,
            "server_version": version,
            "visible_tables": table_count,
            "error": None,
        }
    except Exception as e:
        logger.error(f"MSSQL [{database}] connection test failed: {e}")
        return {
            "success": False,
            "database": database,
            "server_version": None,
            "visible_tables": None,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────────────────

def get_postgres_connection() -> psycopg2.extensions.connection:
    """
    Opens and returns a new psycopg2 connection to the operational PostgreSQL DB.

    Use as a context manager:

        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()

    Raises:
        psycopg2.Error — if the connection cannot be established.
    """
    try:
        conn = psycopg2.connect(settings.postgres_connection_string)
        logger.debug("PostgreSQL connection opened")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


def test_postgres_connection() -> dict:
    """
    Verifies the PostgreSQL connection and returns status info.
    Used by the Phase 0 verification script and health checks.
    """
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0].split(",")[0].strip()

                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                table_count = cur.fetchone()[0]

        logger.info(f"PostgreSQL connection OK | Public tables: {table_count}")
        return {
            "success": True,
            "server_version": version,
            "public_tables": table_count,
            "error": None,
        }
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}")
        return {"success": False, "server_version": None, "public_tables": None, "error": str(e)}


def setup_postgres_schema() -> dict:
    """
    Creates the pgvector extension and all required tables if they do not
    already exist. Safe to run multiple times (uses IF NOT EXISTS throughout).
    """
    results = []

    ddl_statements = [
        ("pgvector extension", "CREATE EXTENSION IF NOT EXISTS vector;"),

        ("rag_documents table", """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id          BIGSERIAL PRIMARY KEY,
                source      TEXT NOT NULL,
                content     TEXT NOT NULL,
                embedding   vector(768),
                metadata    JSONB DEFAULT '{}',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """),

        ("rag_documents embedding index", """
            CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
            ON rag_documents
            USING hnsw (embedding vector_cosine_ops);
        """),

        ("audit_log table", """
            CREATE TABLE IF NOT EXISTS audit_log (
                id              BIGSERIAL PRIMARY KEY,
                session_id      TEXT,
                username        TEXT,
                user_role       TEXT,
                timestamp       TIMESTAMPTZ DEFAULT NOW(),
                intent_type     TEXT,
                user_message    TEXT,
                generated_sql   TEXT,
                result_summary  TEXT,
                confidence      NUMERIC(4,3),
                flagged         BOOLEAN DEFAULT FALSE,
                flag_reason     TEXT
            );
        """),

        ("query_store table", """
            CREATE TABLE IF NOT EXISTS query_store (
                id              BIGSERIAL PRIMARY KEY,
                query_hash      TEXT UNIQUE NOT NULL,
                normalised_sql  TEXT NOT NULL,
                original_intent TEXT,
                user_role       TEXT,
                result_summary  TEXT,
                result_cache    JSONB,
                cache_expires_at TIMESTAMPTZ,
                execution_count INTEGER DEFAULT 1,
                first_seen      TIMESTAMPTZ DEFAULT NOW(),
                last_seen       TIMESTAMPTZ DEFAULT NOW()
            );
        """),

        ("rag_review_queue table", """
            CREATE TABLE IF NOT EXISTS rag_review_queue (
                id              BIGSERIAL PRIMARY KEY,
                item_type       TEXT NOT NULL,
                content         TEXT NOT NULL,
                source_context  TEXT,
                frequency       INTEGER DEFAULT 1,
                status          TEXT DEFAULT 'pending',
                reviewed_by     TEXT,
                reviewed_at     TIMESTAMPTZ,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );
        """),

        ("lora_versions table", """
            CREATE TABLE IF NOT EXISTS lora_versions (
                id                  BIGSERIAL PRIMARY KEY,
                version             TEXT NOT NULL,
                quarter             TEXT NOT NULL,
                adapter_path        TEXT NOT NULL,
                training_data_from  TIMESTAMPTZ,
                training_data_to    TIMESTAMPTZ,
                training_examples   INTEGER,
                final_loss          NUMERIC(6,4),
                notes               TEXT,
                is_active           BOOLEAN DEFAULT FALSE,
                created_at          TIMESTAMPTZ DEFAULT NOW()
            );
        """),
    ]

    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                for name, ddl in ddl_statements:
                    try:
                        cur.execute(ddl)
                        results.append({"name": name, "status": "ok"})
                        logger.info(f"Schema: {name} — OK")
                    except Exception as e:
                        results.append({"name": name, "status": "error", "error": str(e)})
                        logger.error(f"Schema: {name} — FAILED: {e}")
            conn.commit()

        all_ok = all(r["status"] == "ok" for r in results)
        return {"success": all_ok, "steps": results}

    except Exception as e:
        logger.error(f"Schema setup failed: {e}")
        return {"success": False, "steps": results, "error": str(e)}
