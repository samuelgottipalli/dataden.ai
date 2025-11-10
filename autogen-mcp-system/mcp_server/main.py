import uvicorn
from config.settings import settings
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from mcp_server.api_routes import router as openwebui_router
from mcp_server.auth import verify_credentials
from mcp_server.database import db
from mcp_server.tools import analyze_data_pandas, generate_and_execute_sql
from utils.logging_config import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="MCP Agent System", description="MS SQL Server + Ollama + AutoGen 2", version="1.0.0"
)


@app.middleware("http")
async def disable_buffering_middleware(request: Request, call_next):
    """
    Disable response buffering for streaming endpoints

    This ensures nginx and other proxies don't buffer our SSE responses
    """
    response = await call_next(request)

    # Disable buffering for streaming endpoints
    if request.url.path.endswith("/chat/completions"):
        response.headers["X-Accel-Buffering"] = "no"  # Nginx
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Connection"] = "keep-alive"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # OpenWebUI default
        "http://localhost:8080",  # OpenWebUI alternative
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        # Add your OpenWebUI URL here:
        # "https://your-openwebui-domain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS configured for OpenWebUI integration")

# Register OpenWebUI API routes
app.include_router(openwebui_router)
logger.info("OpenWebUI API routes registered at /api/v1")


# ============ DIRECT TOOL ENDPOINTS (for testing) ============


@app.post("/tools/sql_tool")
async def sql_tool_endpoint(query_description: str, sql_script: str):
    """Execute SQL query (for testing)"""
    return await generate_and_execute_sql(query_description, sql_script)


@app.post("/tools/data_analysis_tool")
async def data_analysis_endpoint(data_json: str, analysis_type: str):
    """Analyze data with pandas (for testing)"""
    return await analyze_data_pandas(data_json, analysis_type)


@app.get("/tools/get_table_schema")
async def schema_endpoint(table_name: str):
    """Get table schema (for testing)"""
    logger.info(f"Schema tool called for table: {table_name}")
    return db.get_table_schema(table_name)


# ============ HEALTH & AUTH ENDPOINTS ============


@app.get("/")
async def root():
    return {"message": "MCP Agent System is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "MCP Agent System"}


@app.get("/health/db")
async def health_check_db():
    """Database connectivity check"""
    try:
        result = db.execute_query("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return {"status": "error", "database": "disconnected", "error": str(e)}


@app.post("/auth/verify")
async def verify_user(user_info: dict = Depends(verify_credentials)):
    """Verify user credentials via LDAP"""
    return {"authenticated": True, "user": user_info}


# ============ MCP SSE ENDPOINTS ============
# These are required for AutoGen MCP integration


@app.get("/mcp/sse")
async def mcp_sse():
    """MCP Server-Sent Events endpoint"""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    async def event_stream():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"

        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/mcp/messages")
async def mcp_messages(request: dict):
    """MCP messages endpoint for tool calls"""
    logger.info(f"MCP message received: {request}")

    # Handle tool calls
    if request.get("method") == "tools/call":
        tool_name = request.get("params", {}).get("name")
        tool_args = request.get("params", {}).get("arguments", {})

        logger.info(f"Tool call: {tool_name} with args: {tool_args}")

        if tool_name == "sql_tool":
            result = await generate_and_execute_sql(
                tool_args.get("query_description"), tool_args.get("sql_script")
            )
            return {"result": result}

        elif tool_name == "data_analysis_tool":
            result = await analyze_data_pandas(
                tool_args.get("data_json"), tool_args.get("analysis_type")
            )
            return {"result": result}

        elif tool_name == "get_table_schema":
            result = db.get_table_schema(tool_args.get("table_name"))
            return {"result": result}

    # Handle tool list request
    elif request.get("method") == "tools/list":
        return {
            "tools": [
                {
                    "name": "sql_tool",
                    "description": "Execute SQL query against data warehouse with retry logic",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query_description": {"type": "string"},
                            "sql_script": {"type": "string"},
                        },
                        "required": ["query_description", "sql_script"],
                    },
                },
                {
                    "name": "data_analysis_tool",
                    "description": "Analyze retrieved data using pandas",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "data_json": {"type": "string"},
                            "analysis_type": {"type": "string"},
                        },
                        "required": ["data_json", "analysis_type"],
                    },
                },
                {
                    "name": "get_table_schema",
                    "description": "Get schema information for a specific table",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"table_name": {"type": "string"}},
                        "required": ["table_name"],
                    },
                },
            ]
        }

    return {"error": "Unknown method"}


# ============ START SERVER ============

if __name__ == "__main__":
    logger.info(
        f"Starting MCP Server on {settings.mcp_server_host}:{settings.mcp_server_port}"
    )
    uvicorn.run(
        app,
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        log_config=None,  # Use our loguru config
    )
