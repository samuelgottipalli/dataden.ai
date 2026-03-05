"""
tests/verify_mssql.py
AI Data Assistant — POC2

Phase 0 verification: MS SQL Server connection.

Run from the project root with venv activated:
    python tests\verify_mssql.py
"""

import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from db.connection import test_mssql_connection, validate_readonly_sql

logger.remove()
logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")


def run():
    print("\n" + "=" * 55)
    print("  MS SQL Server — Connection Verification")
    print("=" * 55)

    # ── 1. Connection test ──────────────────────────────────
    print("\n[1/2] Testing connection...")
    result = test_mssql_connection()

    if result["success"]:
        print(f"  ✓ Connected")
        print(f"  ✓ Server  : {result['server_version']}")
        print(f"  ✓ Tables visible in schema: {result['visible_tables']}")
    else:
        print(f"  ✗ Connection FAILED")
        print(f"  ✗ Error: {result['error']}")
        print("\nTroubleshooting:")
        print("  - Check MSSQL_SERVER, MSSQL_USER, MSSQL_PASSWORD in .env")
        print("  - Confirm ODBC Driver 18 is installed:")
        print("    https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
        print("  - Confirm the SQL Server service is running and reachable")
        sys.exit(1)

    # ── 2. Read-only guard test ─────────────────────────────
    print("\n[2/2] Testing read-only SQL guard...")

    safe_cases = [
        "SELECT TOP 10 * FROM students",
        "SELECT COUNT(*) FROM enrollment WHERE year = 2024",
    ]
    blocked_cases = [
        "DELETE FROM students WHERE id = 1",
        "DROP TABLE enrollment",
        "INSERT INTO logs VALUES (1, 'test')",
        "UPDATE students SET name = 'test'",
    ]

    all_passed = True
    for sql in safe_cases:
        ok, reason = validate_readonly_sql(sql)
        status = "✓ ALLOWED (correct)" if ok else f"✗ BLOCKED unexpectedly: {reason}"
        print(f"  {status} | {sql[:50]}")
        if not ok:
            all_passed = False

    for sql in blocked_cases:
        ok, reason = validate_readonly_sql(sql)
        status = "✓ BLOCKED (correct)" if not ok else "✗ ALLOWED unexpectedly — SECURITY ISSUE"
        print(f"  {status} | {sql[:50]}")
        if ok:
            all_passed = False

    print("\n" + "=" * 55)
    if all_passed:
        print("  ✓ MS SQL Server: ALL CHECKS PASSED")
    else:
        print("  ✗ MS SQL Server: SOME CHECKS FAILED — review output above")
        sys.exit(1)
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run()
