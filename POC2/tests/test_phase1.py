"""
tests/test_phase1.py
AI Data Assistant — POC2

Phase 1 integration tests.
These tests validate the full pipeline: Supervisor → SQL Agent → Validation Agent.

Run with:
    pytest tests/test_phase1.py -v
    pytest tests/test_phase1.py -v -k "test_intent"   # run only intent tests

Requirements:
    - Ollama must be running with the configured model loaded
    - MS SQL connection must be active and accessible
    - PostgreSQL / pgvector (Phase 0) must be set up

Tests are grouped:
    1. Unit tests (no model/DB needed) — response normaliser, SQL validator
    2. Integration tests (model + DB needed) — intent classification, full pipeline
"""

import asyncio
import json
import re
import pytest
from unittest.mock import patch, MagicMock

# ── 1. Unit tests — no external services ─────────────────────────────────────

class TestResponseNormaliser:
    """utils/response_normaliser.py"""

    def setup_method(self):
        from utils.response_normaliser import normalise, normalise_sql
        self.normalise = normalise
        self.normalise_sql = normalise_sql

    def test_strips_think_block(self):
        raw = "<think>Let me work through this...</think>\nThe answer is 42."
        result = self.normalise(raw)
        assert "<think>" not in result
        assert "The answer is 42." in result

    def test_strips_code_fence(self):
        raw = "Here is the SQL:\n```sql\nSELECT * FROM dbo.students\n```"
        result = self.normalise(raw)
        assert "```" not in result
        assert "SELECT * FROM dbo.students" in result

    def test_strips_preamble(self):
        raw = "Sure, I'd be happy to help. The result is 100 students."
        result = self.normalise(raw)
        assert "Sure" not in result
        assert "100 students" in result

    def test_empty_input_returns_fallback(self):
        result = self.normalise("")
        assert len(result) > 0
        assert "unable" in result.lower()

    def test_normalise_sql_uppercases_keywords(self):
        sql = "select top 10 * from dbo.students where year = 2024 order by name"
        result = self.normalise_sql(sql)
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result
        assert "ORDER BY" in result

    def test_passthrough_clean_text(self):
        clean = "There are 1,234 students enrolled this semester."
        result = self.normalise(clean)
        assert "1,234 students" in result


class TestSQLValidator:
    """db/connection.py — validate_readonly_sql"""

    def setup_method(self):
        from db.connection import validate_readonly_sql
        self.validate = validate_readonly_sql

    def test_select_passes(self):
        ok, _ = self.validate("SELECT COUNT(*) FROM dbo.students WHERE year = 2024")
        assert ok is True

    def test_select_with_subquery_passes(self):
        ok, _ = self.validate(
            "SELECT dept, COUNT(*) FROM dbo.enrollments "
            "WHERE year IN (SELECT year FROM dbo.academic_years WHERE active = 1) "
            "GROUP BY dept"
        )
        assert ok is True

    def test_insert_blocked(self):
        ok, reason = self.validate("INSERT INTO dbo.students (name) VALUES ('test')")
        assert ok is False
        assert reason

    def test_update_blocked(self):
        ok, reason = self.validate("UPDATE dbo.students SET name = 'x' WHERE id = 1")
        assert ok is False
        assert reason

    def test_delete_blocked(self):
        ok, reason = self.validate("DELETE FROM dbo.students WHERE id = 1")
        assert ok is False
        assert reason

    def test_drop_blocked(self):
        ok, reason = self.validate("DROP TABLE dbo.students")
        assert ok is False
        assert reason

    def test_truncate_blocked(self):
        ok, reason = self.validate("TRUNCATE TABLE dbo.students")
        assert ok is False
        assert reason

    def test_exec_blocked(self):
        ok, reason = self.validate("EXEC sp_dangerous_proc")
        assert ok is False
        assert reason

    def test_inline_insert_blocked(self):
        # Attempts to embed a write after a SELECT
        ok, reason = self.validate("SELECT 1; INSERT INTO dbo.audit (msg) VALUES ('x')")
        assert ok is False
        assert reason


# ── 2. Integration tests — require Ollama + MS SQL ───────────────────────────

@pytest.mark.asyncio
class TestIntentClassification:
    """orchestration/supervisor.py — classify_intent"""

    async def test_data_query_intent(self):
        from orchestration.supervisor import classify_intent, Intent
        intent = await classify_intent("How many students enrolled in 2024?")
        assert intent == Intent.DATA_QUERY

    async def test_retention_query_intent(self):
        from orchestration.supervisor import classify_intent, Intent
        intent = await classify_intent("Show me retention rates by department for last year")
        assert intent == Intent.DATA_QUERY

    async def test_unknown_intent(self):
        from orchestration.supervisor import classify_intent, Intent
        intent = await classify_intent("What is the weather in Paris?")
        assert intent == Intent.UNKNOWN

    async def test_greeting_intent(self):
        from orchestration.supervisor import classify_intent, Intent
        intent = await classify_intent("Hi there, how are you?")
        assert intent == Intent.UNKNOWN


@pytest.mark.asyncio
class TestSchemaDiscovery:
    """tools/sql_tools.py — get_schema_summary"""

    async def test_schema_returns_tables(self):
        from tools.sql_tools import get_schema_summary
        result_json = get_schema_summary()
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["table_count"] > 0
        assert isinstance(result["tables"], list)
        # Each table should have schema, table, and columns keys
        for table in result["tables"][:3]:
            assert "schema" in table
            assert "table" in table
            assert "columns" in table


@pytest.mark.asyncio
class TestFullPipeline:
    """End-to-end: process_query() → SQL Agent → Validation Agent"""

    async def test_unknown_query_returns_graceful_message(self):
        from orchestration.supervisor import process_query
        result = await process_query("What is the capital of France?")
        assert result.intent == "UNKNOWN"
        assert result.success is False
        assert len(result.final_response) > 20

    async def test_data_query_runs_pipeline(self):
        """
        Runs a simple count query end-to-end.
        Asserts the pipeline completes and returns a structured result.
        Does NOT assert specific numbers (depends on your data).
        """
        from orchestration.supervisor import process_query
        result = await process_query(
            "How many tables are visible in the data warehouse schema?"
        )
        # Pipeline must complete
        assert result.intent == "DATA_QUERY"
        assert result.final_response
        assert len(result.message_trace) > 0
        # SQL should have been generated
        # (may fail if DB is empty, but pipeline itself should not crash)

    async def test_result_has_required_fields(self):
        from orchestration.supervisor import process_query, QueryResult
        result = await process_query("How many students enrolled in the last academic year?")
        assert isinstance(result, QueryResult)
        assert hasattr(result, "success")
        assert hasattr(result, "intent")
        assert hasattr(result, "final_response")
        assert hasattr(result, "validation_status")
        assert hasattr(result, "message_trace")
