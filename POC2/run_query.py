"""
run_query.py
AI Data Assistant — POC2 Phase 1 CLI

Usage:
    python run_query.py "How many students enrolled in 2024?"
    python run_query.py --trace "Show retention rates by department"
    python run_query.py --interactive

Flags:
    --trace     Print the full agent message trace after the result
    --json      Output the full QueryResult as JSON instead of human-readable
    --interactive / -i   Start an interactive prompt loop
"""

import asyncio
import json
import sys
import argparse
from loguru import logger

from utils.logging_config import setup_logging
from orchestration.supervisor import process_query


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Data Assistant — Phase 1 query runner"
    )
    parser.add_argument("query", nargs="?", help="The question to ask")
    parser.add_argument(
        "--trace", action="store_true", help="Print full agent message trace"
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Output full QueryResult as JSON"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Start an interactive prompt loop"
    )
    return parser.parse_args()


def print_result(result, show_trace: bool = False, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({
            "success": result.success,
            "intent": result.intent,
            "database": result.database_key,
            "query": result.user_query,
            "response": result.final_response,
            "validation": result.validation_status,
            "sql": result.sql_executed,
            "row_count": len(result.raw_data) if result.raw_data else 0,
            "error": result.error,
            "trace": result.message_trace if show_trace else [],
        }, indent=2))
        return

    print("\n" + "=" * 60)
    status_icon = "✓" if result.success else "✗"
    print(f"{status_icon}  Intent: {result.intent}")

    if result.database_key:
        print(f"   Database: {result.database_key}")

    if result.sql_executed:
        print(f"\n   SQL executed:\n   {result.sql_executed}")

    print(f"\n   {result.final_response}")

    if result.validation_status not in ("N/A", "UNKNOWN"):
        print(f"\n   Validation: {result.validation_status}")

    if result.error and not result.success:
        print(f"\n   Error: {result.error}")

    if show_trace and result.message_trace:
        print("\n--- Agent trace ---")
        for line in result.message_trace:
            print(f"  {line[:200]}")

    print("=" * 60)


async def run_single(
    query: str,
    show_trace: bool = False,
    as_json: bool = False,
) -> bool:
    result = await process_query(query)
    print_result(result, show_trace=show_trace, as_json=as_json)
    return result.success


async def interactive_loop(show_trace: bool) -> None:
    print("\nAI Data Assistant — Phase 1 Interactive Mode")
    print("Type your question and press Enter. Type 'exit' to quit.\n")
    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break
        await run_single(query, show_trace=show_trace, as_json=False)


async def main() -> None:
    setup_logging()
    args = parse_args()

    if args.interactive:
        await interactive_loop(show_trace=args.trace)
        return

    if not args.query:
        print("Error: Provide a query or use --interactive")
        print('Usage: python run_query.py "Your question here"')
        sys.exit(1)

    success = await run_single(args.query, show_trace=args.trace, as_json=args.as_json)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (SystemExit, KeyboardInterrupt):
        # SystemExit is raised by sys.exit() inside main().
        # Re-raising it here after asyncio.run() has finished avoids the
        # "task_done() called too many times" noise from AutoGen's runtime
        # shutdown on Windows (Python 3.11 asyncio teardown race condition).
        raise
