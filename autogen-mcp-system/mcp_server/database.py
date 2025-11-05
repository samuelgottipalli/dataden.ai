import pyodbc
from config.settings import settings
from loguru import logger
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential


class DataWarehouseConnection:
    """Manages MS SQL Server connections and query execution"""

    def __init__(self):
        self.conn_str = (
            f"Driver={settings.mssql_driver};"
            f"Server={settings.mssql_server};"
            f"Database={settings.mssql_database};"
            f"UID={settings.mssql_user};"
            f"PWD={settings.mssql_password};"
            f"TrustServerCertificate=yes;"
        )
        self._verify_connection()

    def _verify_connection(self):
        """Test connection on initialization"""
        try:
            conn = pyodbc.connect(self.conn_str)
            conn.close()
            logger.info("✓ MS SQL Server connection established")
        except Exception as e:
            logger.error(f"✗ Failed to connect to MS SQL Server: {e}")
            raise

    def validate_sql(self, sql_query: str) -> tuple[bool, Optional[str]]:
        """
        Validate SQL query for dangerous operations
        Returns: (is_safe: bool, error_message: str or None)
        """
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]

        for keyword in dangerous_keywords:
            if keyword in sql_query.upper():
                error = f"Query contains dangerous operation: {keyword}"
                logger.warning(error)
                return False, error

        return True, None

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def execute_query(self, sql_query: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute SQL query with automatic retry on failure

        Args:
            sql_query: SQL command to execute
            timeout: Query timeout in seconds

        Returns:
            Dict with success status and results/error
        """
        # Validate before execution
        is_safe, error_msg = self.validate_sql(sql_query)
        if not is_safe:
            return {"success": False, "error": error_msg}

        try:
            conn = pyodbc.connect(self.conn_str, timeout=timeout)
            cursor = conn.cursor()

            logger.debug(f"Executing query: {sql_query[:100]}...")
            cursor.execute(sql_query)

            # Handle SELECT vs INSERT/UPDATE/DELETE
            if sql_query.strip().upper().startswith("SELECT"):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                result = {
                    "success": True,
                    "columns": columns,
                    "rows": [dict(zip(columns, row)) for row in rows],
                    "row_count": len(rows),
                }
            else:
                conn.commit()
                result = {
                    "success": True,
                    "rows_affected": cursor.rowcount,
                    "message": "Query executed successfully",
                }

            cursor.close()
            conn.close()
            return result

        except pyodbc.Error as e:
            logger.error(f"MS SQL Error: {e}")
            return {"success": False, "error": str(e), "error_type": "database"}
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            return {"success": False, "error": str(e), "error_type": "unknown"}

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Retrieve table schema for reference"""
        query = f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        return self.execute_query(query)


db = DataWarehouseConnection()
