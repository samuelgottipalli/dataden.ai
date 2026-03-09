"""
run_query.py
AI Data Assistant — POC2 Phase 1 CLI

Usage:
    python run_query.py "How many students enrolled in 2024?"
    python run_query.py --trace "Show retention rates by department"
    python run_query.py --interactive

Flags:
    --trace         Print the full agent message trace after the result
    --json          Output the full QueryResult as JSON
    --interactive   Start an interactive prompt loop (maintains session history)
"""

import asyncio
import json
import sys
import argparse
from loguru import logger

from utils.logging_config import setup_logging
from orchestration.supervisor import process_query, ConversationTurn


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
        help="Start an interactive prompt loop (maintains conversation history)"
    )
    return parser.parse_args()


def _format_rows(rows: list, max_display: int = 20) -> str:
    """Format result rows as a readable table."""
    if not rows:
        return "  (no rows returned)"

    # Collect all keys
    keys = list(rows[0].keys()) if rows else []
    if not keys:
        return str(rows)

    # Calculate column widths
    col_widths = {k: max(len(str(k)), max(len(str(r.get(k, ""))) for r in rows[:max_display]))
                  for k in keys}
    # Cap column width at 40 chars
    col_widths = {k: min(v, 40) for k, v in col_widths.items()}

    sep = "  " + "-+-".join("-" * col_widths[k] for k in keys)
    header = "  " + " | ".join(str(k).ljust(col_widths[k])[:col_widths[k]] for k in keys)

    lines = [sep, header, sep]
    for row in rows[:max_display]:
        line = "  " + " | ".join(
            str(row.get(k, "")).ljust(col_widths[k])[:col_widths[k]] for k in keys
        )
        lines.append(line)

    if len(rows) > max_display:
        lines.append(f"  ... and {len(rows) - max_display} more rows")
    lines.append(sep)
    return "\n".join(lines)


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
            "rows": result.raw_data or [],
            "error": result.error,
        }, indent=2))
        return

    print("\n" + "=" * 70)

    # Clarification request — show as a question, not a status/error
    if result.validation_status == "CLARIFICATION_NEEDED":
        print(f"  ❓  Database: {result.database_key or 'N/A'}")
        print(f"\n  {result.final_response}")
        print("=" * 70)
        return

    status_icon = "✓" if result.success else "✗"
    print(f"{status_icon}  Intent: {result.intent}  |  Database: {result.database_key or 'N/A'}")

    if result.sql_executed:
        print(f"\n  SQL:\n  {result.sql_executed}")

    print(f"\n  Summary:\n  {result.final_response}")

    if result.raw_data:
        row_count = len(result.raw_data)
        print(f"\n  Data ({row_count} row{'s' if row_count != 1 else ''}):\n")
        print(_format_rows(result.raw_data))
    elif result.success:
        print("\n  (Query succeeded but returned no rows)")

    if result.validation_status not in ("N/A", "UNKNOWN", "CLARIFICATION_NEEDED"):
        print(f"\n  Validation: {result.validation_status}")

    if result.error and not result.success:
        print(f"\n  Error: {result.error}")

    if show_trace and result.message_trace:
        print("\n" + "-" * 70)
        print("  Agent Trace")
        print("-" * 70)
        for line in result.message_trace:
            print(f"  {line[:250]}")

    print("=" * 70)


async def run_single(
    query: str,
    show_trace: bool = False,
    as_json: bool = False,
    history: list | None = None,
) -> tuple[bool, ConversationTurn | None]:
    """Run one query. Returns (success, ConversationTurn) for history tracking."""
    result = await process_query(query, history=history)
    print_result(result, show_trace=show_trace, as_json=as_json)

    turn = ConversationTurn(
        user_query=query,
        assistant_response=result.final_response,
        database_key=result.database_key,
        sql_executed=result.sql_executed,
    ) if result.final_response else None

    return result.success, turn


async def interactive_loop(show_trace: bool) -> None:
    print("\nAI Data Assistant — Interactive Mode")
    print("Conversation history is maintained within this session.")
    print("Type 'history' to review past turns. Type 'clear' to reset. Type 'exit' to quit.\n")

    history: list[ConversationTurn] = []

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

        if query.lower() == "clear":
            history.clear()
            print("  Conversation history cleared.\n")
            continue

        if query.lower() == "history":
            if not history:
                print("  No history yet.\n")
            else:
                print(f"\n  {len(history)} turn(s) in this session:")
                for i, t in enumerate(history, 1):
                    print(f"  [{i}] You: {t.user_query}")
                    print(f"       DB: {t.database_key}  |  {t.assistant_response[:120]}")
                print()
            continue

        success, turn = await run_single(query, show_trace=show_trace, history=history)
        if turn:
            history.append(turn)


async def main() -> None:
    setup_logging()
    args = parse_args()

    if args.interactive:
        await interactive_loop(show_trace=args.trace)
        return

    if not args.query:
        print("Error: Provide a query or use --interactive / -i")
        print('Usage: python run_query.py "Your question here"')
        sys.exit(1)

    success, _ = await run_single(args.query, show_trace=args.trace, as_json=args.as_json)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (SystemExit, KeyboardInterrupt):
        raise
