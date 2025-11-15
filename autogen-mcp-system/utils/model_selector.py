"""
Smart Model Selector - Route tasks to appropriate model
File: utils/model_selector.py (NEW FILE)

Uses local model for simple tasks, cloud for complex ones
"""

from pyexpat import model
from loguru import logger
from typing import Any, Tuple
from config.settings import settings

class TaskComplexity:
    """Classify task complexity"""
    
    # Keywords that indicate simple tasks (use local model)
    SIMPLE_KEYWORDS = [
        "calculate", "convert", "what is", "how much",
        "percentage", "multiply", "divide", "add", "subtract",
        "temperature", "currency", "units", "time", "date",
        "capital", "definition", "meaning", "explain simply",
        "fahrenheit", "celsius", "kilometers", "miles",
        "plus", "minus", "times", "equals"
    ]
    
    # Keywords that indicate complex tasks (use cloud model)
    COMPLEX_KEYWORDS = [
        "database", "sql", "query", "analyze", "data",
        "report", "trend", "forecast", "predict",
        "compare", "correlation", "statistics",
        "revenue", "sales", "customers", "orders",
        "table", "column", "rows", "from the database",
        "show", "list", "find", "fetch", "retrieve",
        "top", "bottom", "best", "worst", "highest", "lowest",
        "count", "total", "sum", "average", "median",
        "q1", "q2", "q3", "q4", "quarter", "monthly", "yearly",
        "employee", "transaction", "inventory", "product",
        "region", "department", "location", "category"
    ]
    
    @classmethod
    def classify(cls, task: str) -> str:
        """
        Classify task as 'simple' or 'complex'
        
        Returns:
            'simple' - Use local model (qwen3-vl)
            'complex' - Use cloud model (gpt-oss:120b-cloud)
        """
        task_lower = task.lower()
        
        # Check for complex indicators first (higher priority)
        complex_count = 0
        for keyword in cls.COMPLEX_KEYWORDS:
            if keyword in task_lower:
                complex_count += 1
        
        if complex_count >= 1:
            logger.info(f"Task classified as COMPLEX ({complex_count} indicators)")
            return "complex"
        
        # Check for simple indicators
        simple_count = 0
        for keyword in cls.SIMPLE_KEYWORDS:
            if keyword in task_lower:
                simple_count += 1
        
        if simple_count >= 1:
            logger.info(f"Task classified as SIMPLE ({simple_count} indicators)")
            return "simple"
        
        # Default based on length
        word_count = len(task.split())
        
        if word_count <= 10:
            logger.info(f"Task classified as SIMPLE (short: {word_count} words)")
            return "simple"
        else:
            logger.info(f"Task classified as COMPLEX (default: {word_count} words)")
            return "complex"


def select_model_for_task(task: str, force_model: str | None = None) -> Tuple[str, dict[str, bool | str], bool]:
    """
    Select appropriate model for task
    
    Args:
        task: The user's query/task
        force_model: Optional model to force use
    
    Returns:
        (model_name, show_notice)
        - model_name: Which model to use
        - show_notice: Whether to show "using local model" message
    """
    if force_model:
        logger.info(f"Using forced model: {force_model}")
        model_info = (
            settings.ollama_model_info
            if force_model == settings.ollama_model
            else (
                settings.ollama_fallback_model_info
                if force_model == settings.ollama_fallback_model
                else (
                    {
                        "vision": True,
                        "function_calling": True,
                        "json_output": True,
                        "family": force_model.split(":")[0],
                        "structured_output": True,
                    }
                    if "vision" in force_model or "vl" in force_model
                    else {
                        "vision": False,
                        "function_calling": True,
                        "json_output": True,
                        "family": force_model.split(":")[0],
                        "structured_output": True,
                    }
                )
            )
        )
        return force_model, model_info, False

    complexity = TaskComplexity.classify(task)

    if complexity == "simple":
        # Use local model for simple tasks
        logger.info(f"📱 Using LOCAL model: {settings.ollama_fallback_model}")
        return settings.ollama_fallback_model, settings.ollama_fallback_model_info, True
    else:
        # Use cloud model for complex tasks
        logger.info(f"☁️  Using CLOUD model: {settings.ollama_model}")
        return settings.ollama_model, settings.ollama_model_info, False
