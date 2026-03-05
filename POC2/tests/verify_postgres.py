"""
tests/verify_postgres.py
AI Data Assistant — POC2

Phase 0 verification: PostgreSQL + pgvector connection and schema setup.

Usage:
    # Connection check only:
    python tests\verify_postgres.py

    # Connection check + create all tables (run once on first setup):
    python tests\verify_postgres.py --setup
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from db.connection import test_postgres_connection, setup_postgres_schema

logger.remove()
logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")

RUN_SETUP = "--setup" in sys.argv


def run():
    print("\n" + "=" * 55)
    print("  PostgreSQL + pgvector — Connection Verification")
    print("=" * 55)

    # ── 1. Connection test ──────────────────────────────────
    print("\n[1/2] Testing connection...")
    result = test_postgres_connection()

    if result["success"]:
        print(f"  ✓ Connected")
        print(f"  ✓ Server  : {result['server_version']}")
        print(f"  ✓ Public tables currently: {result['public_tables']}")
    else:
        print(f"  ✗ Connection FAILED")
        print(f"  ✗ Error: {result['error']}")
        print("\nTroubleshooting:")
        print("  - Confirm PostgreSQL service is running:")
        print("    Get-Service -Name 'postgresql*'")
        print("  - Check POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD in .env")
        print("  - Default PostgreSQL port is 5432")
        sys.exit(1)

    # ── 2. Schema setup (optional) ──────────────────────────
    if RUN_SETUP:
        print("\n[2/2] Running schema setup (--setup flag detected)...")
        schema_result = setup_postgres_schema()

        for step in schema_result["steps"]:
            if step["status"] == "ok":
                print(f"  ✓ {step['name']}")
            else:
                print(f"  ✗ {step['name']} — {step.get('error', 'unknown error')}")

        if schema_result["success"]:
            print("\n  ✓ All schema objects created successfully")
        else:
            print("\n  ✗ Schema setup had errors — review output above")
            sys.exit(1)
    else:
        print("\n[2/2] Schema setup skipped (run with --setup to create tables)")

    print("\n" + "=" * 55)
    print("  ✓ PostgreSQL: ALL CHECKS PASSED")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run()
