import asyncio
import sys
from agents.orchestrator import AgentOrchestrator
from config.settings import settings
from utils.logging_config import setup_logging
from loguru import logger

# Setup logging
setup_logging()


async def main():
    """
    Main entry point for running agents
    Example usage for proof of concept
    """

    logger.info("=" * 60)
    logger.info("MCP AGENT SYSTEM - POC EXECUTION")
    logger.info("=" * 60)

    # Example tasks to execute
    example_tasks = [
        "Query the sales table for the last quarter. Calculate total revenue by region and identify top 5 products. Provide trend analysis.",
        "Analyze customer data from the past 6 months. Show customer count, average purchase value, and segment by geographic region.",
        "Generate a summary report of inventory levels. Identify items below minimum threshold and calculate procurement needs.",
    ]

    orchestrator = AgentOrchestrator()

    for i, task in enumerate(example_tasks, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"TASK {i}/{len(example_tasks)}")
        logger.info(f"{'='*60}")

        result = await orchestrator.execute_task(
            task_description=task, username="test_user"
        )

        # Pretty print results
        if result["success"]:
            logger.info(f"✓ Task completed successfully")
            print("\nAgent Conversation:")
            print(result["result"])
        else:
            logger.error(f"✗ Task failed: {result['error']}")

        # Small delay between tasks
        await asyncio.sleep(2)

    logger.info(f"\n{'='*60}")
    logger.info("ALL TASKS COMPLETED")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
