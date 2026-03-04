from typing import Dict, Any, Callable
from loguru import logger
from config.settings import settings


class QueryRetryHandler:
    """Handles query retry logic with escalation"""

    def __init__(self, max_attempts: int = None):
        self.max_attempts = max_attempts or settings.agent_retry_attempts

    def execute_with_retry(
        self, query_func: Callable, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a function with retry logic
        Escalates to human after max attempts
        """
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.info(f"Attempt {attempt}/{self.max_attempts}")
                result = query_func(*args, **kwargs)

                if result.get("success"):
                    logger.info(f"Query succeeded on attempt {attempt}")
                    return result

                last_error = result.get("error", "Unknown error")
                logger.warning(f"Attempt {attempt} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} exception: {last_error}")

        # All attempts exhausted
        logger.error(f"All {self.max_attempts} attempts failed. Escalating to human.")
        return {
            "success": False,
            "error": last_error,
            "status": "escalated",
            "escalation_email": settings.agent_escalation_email,
            "message": f"Query failed after {self.max_attempts} attempts. Manual intervention required.",
        }


retry_handler = QueryRetryHandler()
