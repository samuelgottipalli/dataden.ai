"""
db/connection.py
AI Data Assistant — POC2

Manages connections to:
  - MS SQL Server (data warehouse — read-only)
  - PostgreSQL (operational database — audit logs, RAG store, sessions)

Usage:
    from db.connection import get_mssql_connection, get_postgres_connection
"""

import pyodbc
import psycopg2
from loguru import logger
from typing import Optional
from config.settings import settings


# ─────────────────────────────────────────────────────────────
# MS SQL Server
# ─────────────────────────────────────────────────────────────

# Keywords that must never appear in a query going to the data warehouse.
# This is a defence-in-depth check on top of the read-only DB account.
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
        # Check as a whole word to avoid false positives (e.g. "CREATED_AT")
        import re
        if re.search(rf"\b{keyword}\b", normalised):
            reason = f"Query contains disallowed operation: {keyword}"
            logger.warning(f"[SQL BLOCK] {reason} | Query preview: {sql[:120]}")
            return False, reason
    return True, None


def get_mssql_connection() -> pyodbc.Connection:
    """
    Opens and returns a new pyodbc connection to the MS SQL data warehouse.

    The connection is intentionally not pooled at this layer — each caller
    is responsible for closing it. Use as a context manager:

        with get_mssql_connection() as conn:
            cursor = conn.cursor()
            ...

    Raises:
        pyodbc.Error — if the connection cannot be established.
    """
    try:
        conn = pyodbc.connect(settings.mssql_connection_string, timeout=10)
        logger.debug("MSSQL connection opened")
        return conn
    except pyodbc.Error as e:
        logger.error(f"Failed to connect to MS SQL Server: {e}")
        raise


def test_mssql_connection() -> dict:
    """
    Verifies the MS SQL Server connection and returns status info.
    Used by the Phase 0 verification script and health checks.

    Returns a dict with keys: success (bool), server_version (str), error (str)
    """
    try:
        with get_mssql_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version_row = cursor.fetchone()
            version = version_row[0].split("\n")[0].strip() if version_row else "Unknown"

            # Confirm we can query INFORMATION_SCHEMA (proves read access)
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE'"
            )
            table_count = cursor.fetchone()[0]

        logger.info(f"MSSQL connection OK | Tables visible: {table_count}")
        return {
            "success": True,
            "server_version": version,
            "visible_tables": table_count,
            "error": None,
        }
    except Exception as e:
        logger.error(f"MSSQL connection test failed: {e}")
        return {"success": False, "server_version": None, "visible_tables": None, "error": str(e)}


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

    Call this once during Phase 0 setup:
        python tests/verify_postgres.py --setup
    """
    results = []

    ddl_statements = [
        # Enable pgvector
        ("pgvector extension", "CREATE EXTENSION IF NOT EXISTS vector;"),

        # RAG document store
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

        # HNSW index for fast similarity search
        ("rag_documents embedding index", """
            CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
            ON rag_documents
            USING hnsw (embedding vector_cosine_ops);
        """),

        # Audit log
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

        # Query store (Tier 1 self-learning cache)
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

        # RAG enrichment review queue (Tier 2 self-learning)
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

        # LoRA version tracker (Tier 3 self-learning)
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
