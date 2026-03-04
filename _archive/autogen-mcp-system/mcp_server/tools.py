from mcp_server.database import db
from utils.retry_handler import retry_handler
from typing import Dict, Any
from loguru import logger


async def generate_and_execute_sql(
    query_description: str, sql_script: str
) -> Dict[str, Any]:
    """
    MCP Tool: Generate and execute SQL query

    Args:
        query_description: What the query does (for logging)
        sql_script: SQL to execute

    Returns:
        Query results or error
    """
    logger.info(f"SQL Tool called: {query_description}")

    # Use retry handler for fault tolerance
    result = retry_handler.execute_with_retry(db.execute_query, sql_script)

    return result


async def analyze_data_pandas(data_json: str, analysis_type: str) -> Dict[str, Any]:
    """
    MCP Tool: Perform data analysis on retrieved data

    Args:
        data_json: JSON string of data
        analysis_type: Type of analysis (summary, correlation, trend, etc)

    Returns:
        Analysis results
    """
    import pandas as pd
    import json

    try:
        logger.info(f"Analysis tool called: {analysis_type}")

        # Parse data
        data = json.loads(data_json)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])

        # Basic analysis
        analysis_result = {
            "success": True,
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "basic_stats": df.describe().to_dict() if df.shape[0] > 0 else {},
        }

        # Add specific analysis
        if analysis_type == "summary":
            analysis_result["summary"] = {
                "null_values": df.isnull().sum().to_dict(),
                "duplicate_rows": df.duplicated().sum(),
            }

        elif analysis_type == "correlation":
            numeric_df = df.select_dtypes(include=["number"])
            if numeric_df.shape[1] > 1:
                analysis_result["correlation_matrix"] = numeric_df.corr().to_dict()

        logger.info("Analysis completed successfully")
        return analysis_result

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON data: {e}")
        return {"success": False, "error": f"Invalid JSON: {str(e)}"}
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {"success": False, "error": str(e)}
