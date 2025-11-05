# ============================================================
# AGENT ORCHESTRATION - AUTOGEN 2 WITH OLLAMA
# ============================================================

# FILE 1: agents/orchestrator.py
# ============================================================
import asyncio
from typing import Optional
from loguru import logger
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams
from config.settings import settings

class AgentOrchestrator:
    """
    Orchestrates AutoGen 2 agents with Ollama LLM
    Manages SQL generation, data analysis, and validation
    """
    
    def __init__(self, mcp_server_url: str = None):
        self.mcp_server_url = mcp_server_url or f"http://{settings.mcp_server_host}:{settings.mcp_server_port}/mcp"
        
        self.model_client = OllamaChatCompletionClient(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.7,
            max_tokens=2000
        )
        logger.info(f"Initialized Ollama client with model: {settings.ollama_model}")
    
    async def setup_agents(self) -> tuple:
        """
        Create and configure the agent team
        
        Agents:
        1. SQL Agent - Generates and executes SQL queries
        2. Analysis Agent - Analyzes retrieved data
        3. Validation Agent - Reviews and validates responses
        """
        
        # Connect to MCP server
        server_params = SseServerParams(url=self.mcp_server_url)
        workbench = McpWorkbench(server_params)
        
        logger.info("Connecting to MCP server...")
        await workbench.connect()
        
        # SQL Generation & Execution Agent
        sql_agent = AssistantAgent(
            name="SQLAgent",
            model_client=self.model_client,
            workbench=workbench,
            system_message="""You are an expert SQL developer for Microsoft SQL Server.

Your responsibilities:
1. Understand natural language requests for data
2. Generate accurate, optimized SQL queries
3. Use the sql_tool to execute queries against the data warehouse
4. Handle errors gracefully and provide clear feedback
5. Never execute DROP, DELETE, TRUNCATE, or ALTER commands
6. Always retrieve table schemas before writing queries
7. Explain your SQL logic to the team

When retrieving data:
- Use SELECT TOP for initial data exploration
- Request table schema via get_table_schema tool if needed
- Report row counts and data types
- Pass results to AnalysisAgent for further processing""",
        )
        
        # Data Analysis Agent
        analysis_agent = AssistantAgent(
            name="AnalysisAgent",
            model_client=self.model_client,
            workbench=workbench,
            system_message="""You are a data analyst and data scientist.

Your responsibilities:
1. Receive data retrieved by SQLAgent
2. Perform statistical analysis using the data_analysis_tool
3. Identify trends, patterns, and anomalies
4. Calculate key metrics and aggregations
5. Create meaningful insights from raw data
6. Provide clear, actionable recommendations
7. Highlight any data quality issues

Analysis types you can perform:
- Summary: Basic statistics, null values, duplicates
- Correlation: Correlation matrices for numeric data
- Trend: Time-series analysis if dates are present
- Outliers: Detection of anomalous values

Always validate your findings and explain methodology to ValidationAgent.""",
        )
        
        # Validation & Quality Assurance Agent
        validation_agent = AssistantAgent(
            name="ValidationAgent",
            model_client=self.model_client,
            system_message="""You are a quality assurance specialist and data validator.

Your responsibilities:
1. Review SQL queries for accuracy and safety
2. Validate data analysis results
3. Check for logical inconsistencies
4. Verify data meets business requirements
5. Ensure all steps were executed correctly
6. Approve or request corrections

Validation checklist:
□ SQL query syntax is correct for MS SQL Server
□ No dangerous operations (DROP, DELETE, etc)
□ Data retrieved matches the request
□ Analysis methodology is sound
□ Results are logically consistent
□ Findings support the conclusions
□ All assumptions are documented

Approval process:
- If everything checks out: Approve and summarize findings
- If issues found: Request specific corrections
- Escalate complex issues to human team lead""",
        )
        
        # Create Magentic Team for group chat
        team = MagenticOneGroupChat(
            participants=[sql_agent, analysis_agent, validation_agent],
            model_client=self.model_client,
            max_turns=15,  # Limit conversation turns to prevent infinite loops
        )
        
        logger.info("Agent team successfully configured")
        return team, workbench
    
    async def execute_task(self, task_description: str, username: str = "system") -> dict:
        """
        Execute a data analysis task using the agent team
        
        Args:
            task_description: Natural language description of the task
            username: User requesting the analysis (for audit logging)
        
        Returns:
            Dictionary with task results and agent communications
        """
        team = None
        workbench = None
        
        try:
            logger.info(f"Starting task execution for user: {username}")
            logger.info(f"Task: {task_description}")
            
            team, workbench = await self.setup_agents()
            
            # Execute the team
            result = await team.run(task_description)
            
            logger.info(f"Task completed successfully for user: {username}")
            
            return {
                "success": True,
                "user": username,
                "task": task_description,
                "result": result,
                "status": "completed"
            }
            
        except asyncio.TimeoutError:
            logger.error("Task execution timed out")
            return {
                "success": False,
                "user": username,
                "task": task_description,
                "error": "Task execution timed out",
                "status": "timeout"
            }
        
        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "user": username,
                "task": task_description,
                "error": str(e),
                "status": "failed"
            }
        
        finally:
            # Cleanup
            if workbench:
                try:
                    await workbench.disconnect()
                    logger.info("MCP workbench disconnected")
                except Exception as e:
                    logger.warning(f"Error disconnecting workbench: {e}")


# FILE 2: run_agents.py (Entry Point for Agent Execution)
# ============================================================
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
        "Generate a summary report of inventory levels. Identify items below minimum threshold and calculate procurement needs."
    ]
    
    orchestrator = AgentOrchestrator()
    
    for i, task in enumerate(example_tasks, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"TASK {i}/{len(example_tasks)}")
        logger.info(f"{'='*60}")
        
        result = await orchestrator.execute_task(
            task_description=task,
            username="test_user"
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


# FILE 3: run_mcp_server.py (Entry Point for MCP Server)
# ============================================================
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
    logger.info("="*60)
    logger.info("STARTING MCP SERVER")
    logger.info("="*60)
    logger.info(f"Host: {settings.mcp_server_host}:{settings.mcp_server_port}")
    logger.info(f"Ollama: {settings.ollama_host} ({settings.ollama_model})")
    logger.info(f"Database: {settings.mssql_server}:{settings.mssql_port}/{settings.mssql_database}")
    logger.info("="*60)
    
    uvicorn.run(
        "mcp_server.main:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=False,
        log_config=None,
    )


# FILE 4: run_agents_api.py (FastAPI Endpoint for Agent Execution)
# ============================================================
"""
Optional: Wrap agent execution in a FastAPI endpoint
This allows HTTP requests to trigger agent tasks
"""

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from agents.orchestrator import AgentOrchestrator
from mcp_server.auth import verify_credentials
from utils.logging_config import setup_logging
from loguru import logger
import uvicorn
import asyncio

setup_logging()

app = FastAPI(
    title="Agent Execution API",
    description="Trigger data analysis tasks via HTTP"
)

class TaskRequest(BaseModel):
    """Schema for agent task requests"""
    task_description: str
    timeout_seconds: int = 300

class TaskResponse(BaseModel):
    """Schema for task responses"""
    success: bool
    task: str
    result: str
    status: str
    error: str = None

orchestrator = AgentOrchestrator()

@app.post("/execute-task", response_model=TaskResponse)
async def execute_agent_task(
    request: TaskRequest,
    user_info: dict = Depends(verify_credentials)
):
    """
    Execute an agent task
    
    Requires LDAP authentication
    Returns agent conversation and final result
    """
    try:
        logger.info(f"Task request from {user_info['username']}: {request.task_description}")
        
        result = await asyncio.wait_for(
            orchestrator.execute_task(
                task_description=request.task_description,
                username=user_info['username']
            ),
            timeout=request.timeout_seconds
        )
        
        return TaskResponse(
            success=result["success"],
            task=result["task"],
            result=str(result.get("result", "")),
            status=result["status"],
            error=result.get("error")
        )
        
    except asyncio.TimeoutError:
        logger.error("Task execution timed out")
        raise HTTPException(
            status_code=504,
            detail="Task execution timed out"
        )
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "service": "Agent Execution API"}

if __name__ == "__main__":
    logger.info("Starting Agent Execution API on http://127.0.0.1:8001")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        reload=False,
        log_config=None,
    )
