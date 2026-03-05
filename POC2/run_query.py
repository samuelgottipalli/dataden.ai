"""
run_query.py
AI Data Assistant — POC2 Phase 1 CLI

Usage:
    python run_query.py "How many students enrolled in 2024?"
    python run_query.py --trace "Show retention rates by department"

Flags:
    --trace     Print the full agent message trace after the result
    --json      Output the full QueryResult as JSON instead of human-readable

This script is the Phase 1 integration test harness.
No UI — purely a console runner to confirm the end-to-end pipeline works.
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
    parser.add_argument("query", nargs="?", help="The natural language query to run")
    parser.add_argument(
        "--trace", action="store_true",
        help="Print the full agent message trace",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output the full result as JSON",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Run in interactive mode (loop until 'exit')",
    )
    return parser.parse_args()


def print_result(result, show_trace: bool = False, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({
            "success": result.success,
            "intent": result.intent,
            "user_query": result.user_query,
            "final_response": result.final_response,
            "validation_status": result.validation_status,
            "sql_executed": result.sql_executed,
            "raw_data": result.raw_data,
            "error": result.error,
        }, indent=2))
        return

    width = 72
    print("\n" + "=" * width)
    print(f"  Query : {result.user_query}")
    print(f"  Intent: {result.intent}")
    print(f"  Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
    print("=" * width)

    print("\n📋 Response:\n")
    print(result.final_response)

    if result.sql_executed:
        print("\n🔍 SQL Executed:\n")
        print(f"  {result.sql_executed}")

    if result.raw_data:
        print(f"\n📊 Data Rows Returned: {len(result.raw_data)}")
        if len(result.raw_data) <= 5:
            for row in result.raw_data:
                print(f"  {row}")
        else:
            for row in result.raw_data[:3]:
                print(f"  {row}")
            print(f"  ... and {len(result.raw_data) - 3} more rows")

    if result.error and not result.success:
        print(f"\n⚠️  Error: {result.error}")

    if show_trace and result.message_trace:
        print("\n" + "-" * width)
        print("  Agent Message Trace")
        print("-" * width)
        for msg in result.message_trace:
            print(f"\n{msg}")

    print("\n" + "=" * width + "\n")


async def run_single(query: str, show_trace: bool, as_json: bool) -> bool:
    """Run one query and return True if it succeeded."""
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
    asyncio.run(main())
