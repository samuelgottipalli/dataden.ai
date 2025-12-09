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
    title="Agent Execution API", description="Trigger data analysis tasks via HTTP"
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
    request: TaskRequest, user_info: dict = Depends(verify_credentials)
):
    """
    Execute an agent task

    Requires LDAP authentication
    Returns agent conversation and final result
    """
    try:
        logger.info(
            f"Task request from {user_info['username']}: {request.task_description}"
        )

        result = await asyncio.wait_for(
            orchestrator.execute_task(
                task_description=request.task_description,
                username=user_info["username"],
            ),
            timeout=request.timeout_seconds,
        )

        return TaskResponse(
            success=result["success"],
            task=result["task"],
            result=str(result.get("result", "")),
            status=result["status"],
            error=result.get("error"),
        )

    except asyncio.TimeoutError:
        logger.error("Task execution timed out")
        raise HTTPException(status_code=504, detail="Task execution timed out")
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
