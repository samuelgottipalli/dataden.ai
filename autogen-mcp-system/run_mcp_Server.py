"""
Run the MCP server with Ollama + AutoGen 2 agents

Usage:
    python run_mcp_server.py

The server will:
1. Initialize Ollama connection
2. Connect to MS SQL Server
3. Verify LDAP authentication
4. Start FastAPI server on http://127.0.0.1:8000
5. Expose MCP tools for agents
"""

from mcp_server.main import app
from utils.logging_config import setup_logging
from config.settings import settings
from loguru import logger
import uvicorn

setup_logging()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("STARTING MCP SERVER")
    logger.info("=" * 60)
    logger.info(f"Host: {settings.mcp_server_host}:{settings.mcp_server_port}")
    logger.info(f"Ollama: {settings.ollama_host} ({settings.ollama_model})")
    logger.info(
        f"Database: {settings.mssql_server}:{settings.mssql_port}/{settings.mssql_database}"
    )
    logger.info("=" * 60)

    uvicorn.run(
        "mcp_server.main:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=False,
        log_config=None,
    )
