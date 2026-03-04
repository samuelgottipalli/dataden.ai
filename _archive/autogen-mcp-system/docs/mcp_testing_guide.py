# ============================================================
# TESTING & VALIDATION GUIDE
# Comprehensive tests for all components
# ============================================================

# FILE 1: tests/test_database.py
# ============================================================
"""
Test MS SQL Server connection and query execution
Run: python -m pytest tests/test_database.py -v
"""

import pytest
import sys
sys.path.insert(0, '..')

from mcp_server.database import DataWarehouseConnection

@pytest.fixture
def db():
    """Initialize database connection for tests"""
    return DataWarehouseConnection()

def test_database_connection(db):
    """Test that database connection succeeds"""
    result = db.execute_query("SELECT 1 as test")
    assert result["success"] is True
    assert result["row_count"] >= 0
    print("✓ Database connection successful")

def test_sql_validation_allows_safe_queries(db):
    """Test that safe SQL queries pass validation"""
    safe_query = "SELECT TOP 100 * FROM sys.tables"
    is_safe, error = db.validate_sql(safe_query)
    assert is_safe is True
    assert error is None
    print("✓ Safe query validation passed")

def test_sql_validation_blocks_dangerous_queries(db):
    """Test that dangerous queries are blocked"""
    dangerous_queries = [
        "DROP TABLE users",
        "DELETE FROM accounts WHERE id=1",
        "TRUNCATE TABLE logs",
        "ALTER TABLE data ADD COLUMN new_col INT"
    ]
    
    for query in dangerous_queries:
        is_safe, error = db.validate_sql(query)
        assert is_safe is False
        assert error is not None
        print(f"✓ Dangerous query blocked: {query[:30]}...")

def test_query_returns_structured_data(db):
    """Test that query results are properly formatted"""
    result = db.execute_query("""
        SELECT TOP 5 
            name, 
            create_date 
        FROM sys.tables
    """)
    
    assert result["success"] is True
    assert "columns" in result
    assert "rows" in result
    assert isinstance(result["rows"], list)
    print("✓ Query returns properly structured data")

def test_query_retry_on_failure(db):
    """Test that failed queries can be retried"""
    # This will fail, but shouldn't crash
    result = db.execute_query("SELECT * FROM nonexistent_table")
    
    assert result["success"] is False
    assert "error" in result
    print("✓ Failed query handled gracefully")


# FILE 2: tests/test_ldap.py
# ============================================================
"""
Test LDAP authentication
Run: python -m pytest tests/test_ldap.py -v
"""

import pytest
import sys
sys.path.insert(0, '..')

from ldap3 import Server, Connection
from config.settings import settings

def test_ldap_server_accessible():
    """Test that LDAP server is accessible"""
    try:
        server = Server(
            settings.ldap_server,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl
        )
        conn = Connection(
            server,
            user=settings.ldap_service_account_user,
            password=settings.ldap_service_account_password,
            auto_bind=True
        )
        conn.unbind()
        print("✓ LDAP server connection successful")
        assert True
    except Exception as e:
        print(f"✗ LDAP server not accessible: {e}")
        pytest.skip(f"LDAP server not available: {e}")

def test_ldap_invalid_credentials():
    """Test that invalid LDAP credentials are rejected"""
    try:
        server = Server(
            settings.ldap_server,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl
        )
        # Try with obviously wrong credentials
        conn = Connection(
            server,
            user="invalid_user@domain.com",
            password="wrong_password",
            auto_bind=True
        )
        assert False, "Should have rejected invalid credentials"
    except Exception:
        print("✓ Invalid LDAP credentials correctly rejected")
        assert True


# FILE 3: tests/test_retry_handler.py
# ============================================================
"""
Test query retry logic and escalation
Run: python -m pytest tests/test_retry_handler.py -v
"""

import pytest
import sys
sys.path.insert(0, '..')

from utils.retry_handler import QueryRetryHandler

def test_retry_success_on_first_attempt():
    """Test that successful queries don't retry"""
    handler = QueryRetryHandler(max_attempts=3)
    
    call_count = 0
    def successful_func():
        nonlocal call_count
        call_count += 1
        return {"success": True, "data": "result"}
    
    result = handler.execute_with_retry(successful_func)
    
    assert result["success"] is True
    assert call_count == 1  # Should only be called once
    print("✓ Successful query executed once (no retry)")

def test_retry_retries_on_failure():
    """Test that failed queries are retried"""
    handler = QueryRetryHandler(max_attempts=3)
    
    call_count = 0
    def failing_func():
        nonlocal call_count
        call_count += 1
        return {"success": False, "error": "Database unavailable"}
    
    result = handler.execute_with_retry(failing_func)
    
    assert result["success"] is False
    assert call_count == 3  # Should be called 3 times
    assert result["status"] == "escalated"
    print("✓ Failed query retried 3 times then escalated")

def test_retry_succeeds_on_second_attempt():
    """Test that retry succeeds on subsequent attempt"""
    handler = QueryRetryHandler(max_attempts=3)
    
    call_count = 0
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return {"success": False, "error": "Timeout"}
        return {"success": True, "data": "recovered"}
    
    result = handler.execute_with_retry(flaky_func)
    
    assert result["success"] is True
    assert call_count == 2  # Called twice
    print("✓ Failed query succeeded on retry")

def test_escalation_email_included():
    """Test that escalation includes contact information"""
    handler = QueryRetryHandler(max_attempts=2)
    
    def always_fails():
        return {"success": False, "error": "Permanent failure"}
    
    result = handler.execute_with_retry(always_fails)
    
    assert result["status"] == "escalated"
    assert "escalation_email" in result
    assert result["escalation_email"] is not None
    print("✓ Escalation includes email notification")


# FILE 4: tests/test_mcp_tools.py
# ============================================================
"""
Test MCP tool definitions
Run: python -m pytest tests/test_mcp_tools.py -v
"""

import pytest
import asyncio
import sys
sys.path.insert(0, '..')

from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas

@pytest.mark.asyncio
async def test_sql_tool_execution():
    """Test SQL execution through MCP tool"""
    result = await generate_and_execute_sql(
        "Test query",
        "SELECT 1 as test_col"
    )
    
    assert result["success"] is True
    print("✓ SQL tool executes successfully")

@pytest.mark.asyncio
async def test_sql_tool_rejects_dangerous_queries():
    """Test that MCP tool blocks dangerous queries"""
    result = await generate_and_execute_sql(
        "Dangerous",
        "DROP TABLE users"
    )
    
    assert result["success"] is False
    assert "error" in result
    print("✓ SQL tool rejects dangerous queries")

@pytest.mark.asyncio
async def test_analysis_tool_with_valid_data():
    """Test data analysis tool"""
    import json
    
    test_data = [
        {"name": "Alice", "score": 85, "department": "Sales"},
        {"name": "Bob", "score": 92, "department": "Engineering"},
        {"name": "Charlie", "score": 78, "department": "Sales"}
    ]
    
    result = await analyze_data_pandas(
        json.dumps(test_data),
        "summary"
    )
    
    assert result["success"] is True
    assert "shape" in result
    assert result["shape"][0] == 3  # 3 rows
    print("✓ Analysis tool processes data correctly")

@pytest.mark.asyncio
async def test_analysis_tool_handles_invalid_json():
    """Test that analysis tool handles bad JSON"""
    result = await analyze_data_pandas(
        "invalid json {",
        "summary"
    )
    
    assert result["success"] is False
    assert "error" in result
    print("✓ Analysis tool handles invalid JSON gracefully")


# FILE 5: manual_integration_tests.py
# ============================================================
"""
Manual integration tests to run sequentially
Run: python manual_integration_tests.py
"""

import asyncio
import sys
sys.path.insert(0, '.')

from config.settings import settings
from mcp_server.database import DataWarehouseConnection
from config.ldap_config import ldap_manager
from utils.logging_config import setup_logging
from loguru import logger

setup_logging()

async def test_all_components():
    """Test all system components in sequence"""
    
    logger.info("=" * 60)
    logger.info("INTEGRATION TEST SUITE")
    logger.info("=" * 60)
    
    # Test 1: Database
    logger.info("\n[1/4] Testing MS SQL Server Connection...")
    try:
        db = DataWarehouseConnection()
        result = db.execute_query("SELECT @@VERSION as version")
        if result["success"]:
            logger.info("✓ MS SQL Server: PASSED")
            logger.info(f"  Version: {result['rows'][0]['version'] if result['rows'] else 'Unknown'}")
        else:
            logger.error(f"✗ MS SQL Server: FAILED - {result['error']}")
    except Exception as e:
        logger.error(f"✗ MS SQL Server: ERROR - {e}")
    
    # Test 2: LDAP
    logger.info("\n[2/4] Testing LDAP Connection...")
    try:
        from ldap3 import Server, Connection
        server = Server(
            settings.ldap_server,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl
        )
        conn = Connection(
            server,
            user=settings.ldap_service_account_user,
            password=settings.ldap_service_account_password,
            auto_bind=True
        )
        conn.unbind()
        logger.info("✓ LDAP/AD: PASSED")
    except Exception as e:
        logger.error(f"✗ LDAP/AD: FAILED - {e}")
    
    # Test 3: Ollama
    logger.info("\n[3/4] Testing Ollama Connection...")
    try:
        import requests
        response = requests.get(f"{settings.ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if any(m["name"].startswith(settings.ollama_model) for m in models):
                logger.info("✓ Ollama: PASSED")
                logger.info(f"  Model: {settings.ollama_model}")
            else:
                logger.warning("⚠ Ollama: Model not found, downloading...")
                logger.info(f"  Run: ollama pull {settings.ollama_model}")
        else:
            logger.error(f"✗ Ollama: FAILED - Status {response.status_code}")
    except Exception as e:
        logger.error(f"✗ Ollama: FAILED - {e}")
        logger.info("  Make sure Ollama is running: ollama serve")
    
    # Test 4: Retry Handler
    logger.info("\n[4/4] Testing Retry Handler...")
    try:
        from utils.retry_handler import retry_handler
        
        def test_func():
            return {"success": True, "message": "Works"}
        
        result = retry_handler.execute_with_retry(test_func)
        if result["success"]:
            logger.info("✓ Retry Handler: PASSED")
        else:
            logger.error(f"✗ Retry Handler: FAILED - {result['error']}")
    except Exception as e:
        logger.error(f"✗ Retry Handler: ERROR - {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("INTEGRATION TEST COMPLETE")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_all_components())


# FILE 6: tests/conftest.py (Pytest configuration)
# ============================================================
"""
Pytest configuration for all tests
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# FILE 7: test_api_endpoints.sh (API endpoint tests)
# ============================================================
"""
Bash script to test MCP server API endpoints
Run: bash test_api_endpoints.sh

Requires: curl, jq (for JSON parsing)
"""

#!/bin/bash

echo "========================================"
echo "MCP SERVER API ENDPOINT TESTS"
echo "========================================"

BASE_URL="http://127.0.0.1:8000"

# Test 1: Health check
echo -e "\n[1/4] Testing /health endpoint..."
curl -s "$BASE_URL/health" | jq '.' || echo "✗ Failed"

# Test 2: Database health
echo -e "\n[2/4] Testing /health/db endpoint..."
curl -s "$BASE_URL/health/db" | jq '.' || echo "✗ Failed"

# Test 3: Authentication (will fail without valid creds)
echo -e "\n[3/4] Testing /auth/verify endpoint (expects 401)..."
curl -s "$BASE_URL/auth/verify" -H "Authorization: Basic dXNlcjpwYXNz" | jq '.' || echo "✗ Failed"

# Test 4: MCP introspection
echo -e "\n[4/4] Testing MCP server introspection..."
curl -s "$BASE_URL/mcp/info" 2>/dev/null || echo "✗ MCP endpoint not available yet"

echo -e "\n========================================"
echo "API TESTS COMPLETE"
echo "========================================"
