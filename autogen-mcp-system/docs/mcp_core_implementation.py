# ============================================================
# MCP AGENT SYSTEM - CORE IMPLEMENTATION
# MS SQL Server + Ollama + AutoGen 2 + LDAP + Retry Logic
# ============================================================

# FILE 1: config/settings.py
# ============================================================
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma"
    
    # MS SQL Server
    mssql_server: str
    mssql_port: int = 1433
    mssql_database: str
    mssql_user: str
    mssql_password: str
    mssql_driver: str = "{ODBC Driver 17 for SQL Server}"
    
    # LDAP
    ldap_server: str
    ldap_port: int = 389
    ldap_domain: str
    ldap_base_dn: str
    ldap_user_dn_pattern: str
    ldap_service_account_user: str
    ldap_service_account_password: str
    ldap_use_ssl: bool = False
    
    # MCP Server
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8000
    mcp_api_prefix: str = "/mcp"
    
    # Agents
    agent_retry_attempts: int = 3
    agent_escalation_email: str
    log_level: str = "INFO"
    
    # Security
    secret_key: str
    jwt_expiration_hours: int = 24
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()


# FILE 2: config/ldap_config.py
# ============================================================
from ldap3 import Server, Connection, ALL
from config.settings import settings
from loguru import logger
from typing import Tuple, Optional, List

class LDAPManager:
    """Manages LDAP connections and authentication"""
    
    def __init__(self):
        self.server = Server(
            settings.ldap_server,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl,
            get_info=ALL
        )
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[dict]]:
        """
        Authenticate user against LDAP
        Returns: (success: bool, user_info: dict or None)
        """
        try:
            user_dn = settings.ldap_user_dn_pattern.format(
                username=username,
                base_dn=settings.ldap_base_dn
            )
            
            conn = Connection(
                self.server,
                user=user_dn,
                password=password,
                auto_bind=True
            )
            
            logger.info(f"User {username} authenticated successfully")
            
            # Retrieve user groups/attributes
            user_info = self._get_user_info(conn, username)
            conn.unbind()
            
            return True, user_info
            
        except Exception as e:
            logger.warning(f"Authentication failed for user {username}: {str(e)}")
            return False, None
    
    def _get_user_info(self, conn: Connection, username: str) -> dict:
        """Get user information including groups"""
        try:
            search_filter = f"(sAMAccountName={username})"
            conn.search(
                search_base=settings.ldap_base_dn,
                search_filter=search_filter,
                attributes=['mail', 'displayName', 'memberOf']
            )
            
            if conn.entries:
                entry = conn.entries[0]
                return {
                    'username': username,
                    'email': str(entry.mail.value) if entry.mail else None,
                    'display_name': str(entry.displayName.value) if entry.displayName else username,
                    'groups': [str(g) for g in entry.memberOf.values] if entry.memberOf else []
                }
            return {'username': username}
        except Exception as e:
            logger.error(f"Error retrieving user info: {e}")
            return {'username': username}

ldap_manager = LDAPManager()


# FILE 3: mcp_server/database.py
# ============================================================
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
    
    def validate_sql(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL query for dangerous operations
        Returns: (is_safe: bool, error_message: str or None)
        """
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE']
        
        for keyword in dangerous_keywords:
            if keyword in sql_query.upper():
                error = f"Query contains dangerous operation: {keyword}"
                logger.warning(error)
                return False, error
        
        return True, None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
            if sql_query.strip().upper().startswith('SELECT'):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                result = {
                    "success": True,
                    "columns": columns,
                    "rows": [dict(zip(columns, row)) for row in rows],
                    "row_count": len(rows)
                }
            else:
                conn.commit()
                result = {
                    "success": True,
                    "rows_affected": cursor.rowcount,
                    "message": "Query executed successfully"
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


# FILE 4: mcp_server/auth.py
# ============================================================
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config.ldap_config import ldap_manager
from loguru import logger
import jwt
from datetime import datetime, timedelta
from config.settings import settings

security = HTTPBasic()

async def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> dict:
    """
    Verify user credentials via LDAP
    Used as a dependency for protected endpoints
    """
    success, user_info = ldap_manager.authenticate_user(
        credentials.username,
        credentials.password
    )
    
    if not success:
        logger.warning(f"Failed login attempt for user: {credentials.username}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    logger.info(f"Successful login for user: {credentials.username}")
    return user_info or {"username": credentials.username}


# FILE 5: utils/logging_config.py
# ============================================================
import sys
from loguru import logger
from config.settings import settings

def setup_logging():
    """Configure loguru logging"""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    logger.add(
        "logs/app.log",
        rotation="500 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=settings.log_level
    )


# FILE 6: utils/retry_handler.py
# ============================================================
from typing import Dict, Any, Callable
from loguru import logger
from config.settings import settings

class QueryRetryHandler:
    """Handles query retry logic with escalation"""
    
    def __init__(self, max_attempts: int = None):
        self.max_attempts = max_attempts or settings.agent_retry_attempts
    
    def execute_with_retry(self, 
                          query_func: Callable,
                          *args, 
                          **kwargs) -> Dict[str, Any]:
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
            "message": f"Query failed after {self.max_attempts} attempts. Manual intervention required."
        }

retry_handler = QueryRetryHandler()


# FILE 7: mcp_server/tools.py
# ============================================================
from mcp_server.database import db
from utils.retry_handler import retry_handler
from typing import Dict, Any
from loguru import logger

async def generate_and_execute_sql(query_description: str, sql_script: str) -> Dict[str, Any]:
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
    result = retry_handler.execute_with_retry(
        db.execute_query,
        sql_script
    )
    
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
            "basic_stats": df.describe().to_dict() if df.shape[0] > 0 else {}
        }
        
        # Add specific analysis
        if analysis_type == "summary":
            analysis_result["summary"] = {
                "null_values": df.isnull().sum().to_dict(),
                "duplicate_rows": df.duplicated().sum()
            }
        
        elif analysis_type == "correlation":
            numeric_df = df.select_dtypes(include=['number'])
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


# FILE 8: mcp_server/main.py (FastAPI MCP Server)
# ============================================================
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from mcp_server.auth import verify_credentials
from mcp_server.tools import generate_and_execute_sql, analyze_data_pandas
from mcp_server.database import db
from config.settings import settings
from utils.logging_config import setup_logging
from loguru import logger
import uvicorn
import json

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="MCP Agent System",
    description="MS SQL + Ollama + AutoGen 2",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create FastMCP instance
mcp = FastMCP("agent-mcp-server")

# ============ MCP TOOLS ============

@mcp.tool
async def sql_tool(query_description: str, sql_script: str) -> dict:
    """Execute SQL against data warehouse with retry logic"""
    return await generate_and_execute_sql(query_description, sql_script)

@mcp.tool
async def data_analysis_tool(data_json: str, analysis_type: str) -> dict:
    """Analyze retrieved data using pandas"""
    return await analyze_data_pandas(data_json, analysis_type)

@mcp.tool
async def get_table_schema(table_name: str) -> dict:
    """Get schema information for a specific table"""
    logger.info(f"Schema tool called for table: {table_name}")
    return db.get_table_schema(table_name)

# ============ HEALTH & AUTH ENDPOINTS ============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "MCP Agent System"}

@app.get("/health/db")
async def health_check_db():
    """Database connectivity check"""
    try:
        db.execute_query("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return {"status": "error", "database": "disconnected", "error": str(e)}

@app.post("/auth/verify")
async def verify_user(user_info: dict = Depends(verify_credentials)):
    """Verify user credentials via LDAP"""
    return {"authenticated": True, "user": user_info}

# ============ START SERVER ============

if __name__ == "__main__":
    logger.info(f"Starting MCP Server on {settings.mcp_server_host}:{settings.mcp_server_port}")
    uvicorn.run(
        app,
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        log_config=None  # Use our loguru config
    )
