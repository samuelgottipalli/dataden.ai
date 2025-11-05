# quick_test.py
# Quick test to verify MCP server connection and agent setup

import asyncio
from agents.orchestrator import AgentOrchestrator
from config.settings import settings
from utils.logging_config import setup_logging
from loguru import logger

setup_logging()


async def test_simple_task():
    """Test a very simple task to verify the setup works"""

    logger.info("=" * 60)
    logger.info("QUICK CONNECTION TEST")
    logger.info("=" * 60)

    orchestrator = AgentOrchestrator()

    # Simple test task
    simple_task = "List the first 5 tables in the database"

    logger.info(f"\nTesting with simple task: {simple_task}")

    result = await orchestrator.execute_task(
        task_description=simple_task, username="sqlapi"
    )

    if result["success"]:
        logger.info("✓ TEST PASSED")
        logger.info(f"Result: {result['result']}")
    else:
        logger.error("✗ TEST FAILED")
        logger.error(f"Error: {result.get('error', 'Unknown error')}")

    logger.info("=" * 60)
    return result


if __name__ == "__main__":
    asyncio.run(test_simple_task())
