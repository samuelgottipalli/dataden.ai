# ============================================================
# OpenWebUI Integration - Streaming API Routes
# File 1 of 5: API endpoints for OpenWebUI connection
# ============================================================

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio
from datetime import datetime
from loguru import logger

# Import our orchestrator
from agents.enhanced_orchestrator import EnhancedAgentOrchestrator
from config.settings import settings

# Create router
router = APIRouter(prefix="/api/v1", tags=["openwebui"])


# ============================================================
# Request/Response Models (OpenAI-Compatible)
# ============================================================


class Message(BaseModel):
    """Single message in conversation"""

    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    """OpenAI-compatible chat request"""

    model: str = "autogen-agents"  # Model name (not used, but required by OpenAI spec)
    messages: List[Message]  # Conversation history
    stream: bool = True  # Always stream for agent visibility
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 4000


class ChatResponse(BaseModel):
    """OpenAI-compatible chat response (non-streaming)"""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]


# ============================================================
# Authentication Helper
# ============================================================


def verify_api_key(api_key: Optional[str] = None) -> bool:
    """
    Verify API key from OpenWebUI

    Returns True if valid, raises HTTPException if invalid
    """
    if not settings.openwebui_api_key:
        # No API key configured - allow all (for testing)
        logger.warning("No API key configured - allowing all requests")
        return True

    if api_key != settings.openwebui_api_key:
        logger.error(f"Invalid API key received: {api_key[:10]}...")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


# ============================================================
# Streaming Endpoint (Main Integration Point)
# ============================================================


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
):
    """
    OpenAI-compatible chat completions endpoint with streaming

    This is what OpenWebUI will call when users send messages.

    Features:
    - Streams agent conversations in real-time
    - Shows full thought process
    - OpenAI-compatible format
    - User context from headers

    Example request from OpenWebUI:
    POST /api/v1/chat/completions
    Headers:
        X-API-Key: your-secret-key
        X-User-ID: sgottipalli
        X-User-Email: sgottipalli@company.com
    Body:
        {
            "model": "autogen-agents",
            "messages": [
                {"role": "user", "content": "Show top 5 sales"}
            ],
            "stream": true
        }
    """

    # Verify API key
    verify_api_key(x_api_key)

    # Extract user info
    user_id = x_user_id or "anonymous"
    user_email = x_user_email or "unknown@example.com"

    # Get the last user message (most recent)
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message found")

    last_message = user_messages[-1].content

    logger.info(f"Chat request from {user_id}: {last_message[:100]}...")

    # If streaming requested (always true for agent visibility)
    if request.stream:
        return StreamingResponse(
            stream_agent_response(last_message, user_id, user_email),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    else:
        # Non-streaming response (fallback, not recommended)
        return await non_streaming_response(last_message, user_id, user_email)


# ============================================================
# Streaming Implementation
# ============================================================


async def stream_agent_response(message: str, user_id: str, user_email: str):
    """
    Stream agent messages back to OpenWebUI in real-time

    Yields Server-Sent Events (SSE) in OpenAI format
    """

    try:
        # Create orchestrator
        orchestrator = EnhancedAgentOrchestrator()

        # Generate unique ID for this conversation
        conversation_id = f"chatcmpl-{datetime.now().timestamp()}"

        logger.info(f"Starting streaming response for {user_id}")

        # Stream agent execution
        message_count = 0
        async for event in orchestrator.execute_with_streaming(
            task_description=message, username=user_id
        ):
            message_count += 1

            # Format as OpenAI streaming chunk
            chunk = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": format_agent_message(event),
                        },
                        "finish_reason": None,
                    }
                ],
            }

            # Yield as SSE
            yield f"data: {json.dumps(chunk)}\n\n"

            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)

        logger.info(f"Streamed {message_count} messages for {user_id}")

        # Send final chunk with finish_reason
        final_chunk = {
            "id": conversation_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"

        # Send [DONE] marker
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        logger.exception("Full traceback:")

        # Send error as final message
        error_chunk = {
            "id": conversation_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"\n\n❌ Error: {str(e)}\n\nPlease try again or contact support.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


def format_agent_message(event: dict) -> str:
    """
    Format agent event for display in OpenWebUI

    Makes agent conversations readable and visually appealing
    """

    agent_name = event.get("agent", "System")
    message_type = event.get("type", "message")
    content = event.get("content", "")

    # Format based on message type
    if message_type == "routing":
        # Supervisor routing decision
        return f"\n🎯 **{agent_name}**\n{content}\n"

    elif message_type == "thinking":
        # Agent thinking/planning
        return f"\n🤔 **{agent_name}** [Thinking]\n{content}\n"

    elif message_type == "action":
        # Agent taking action (tool call)
        return f"\n⚡ **{agent_name}** [Action]\n```\n{content}\n```\n"

    elif message_type == "tool_result":
        # Tool execution result
        return f"\n📦 **Tool Result**\n```\n{content}\n```\n"

    elif message_type == "validation":
        # Validation checks
        return f"\n🛡️ **{agent_name}** [Validation]\n{content}\n"

    elif message_type == "analysis":
        # Data analysis
        return f"\n📊 **{agent_name}** [Analysis]\n{content}\n"

    elif message_type == "final":
        # Final answer
        return f"\n✅ **Final Answer**\n{content}\n"

    elif message_type == "error":
        # Error message
        return f"\n❌ **Error**\n{content}\n"

    else:
        # Generic message
        return f"\n💬 **{agent_name}**\n{content}\n"


# ============================================================
# Non-Streaming Fallback (Not Recommended)
# ============================================================


async def non_streaming_response(
    message: str, user_id: str, user_email: str
) -> ChatResponse:
    """
    Non-streaming response (fallback)

    Not recommended because it hides agent process
    Only use if streaming is not supported
    """

    logger.warning(
        f"Non-streaming request from {user_id} - agent visibility will be hidden"
    )

    # Create orchestrator
    orchestrator = EnhancedAgentOrchestrator()

    # Execute task (no streaming)
    result = await orchestrator.execute_task_with_routing(
        task_description=message, username=user_id
    )

    # Format response
    if result["success"]:
        content = result.get("response", "Task completed successfully")
    else:
        content = f"Error: {result.get('error', 'Unknown error')}"

    # Return OpenAI-compatible response
    return ChatResponse(
        id=f"chatcmpl-{datetime.now().timestamp()}",
        created=int(datetime.now().timestamp()),
        model="autogen-agents",
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    )


# ============================================================
# Health Check & Info Endpoints
# ============================================================


@router.get("/models")
async def list_models():
    """
    List available models (OpenAI-compatible)

    OpenWebUI uses this to discover available models
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "autogen-agents",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "autogen-mcp-system",
                "permission": [],
                "root": "autogen-agents",
                "parent": None,
            }
        ],
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint

    OpenWebUI can use this to verify connection
    """
    return {
        "status": "healthy",
        "service": "autogen-mcp-system",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# Usage Instructions
# ============================================================

"""
USAGE INSTRUCTIONS:

1. Add to your mcp_server/main.py:
   
   from mcp_server.api_routes import router as openwebui_router
   app.include_router(openwebui_router)

2. Set environment variable in .env:
   
   OPENWEBUI_API_KEY=your-secret-key-here

3. Configure OpenWebUI:
   
   - Go to Settings → Connections
   - Add External API
   - URL: http://your-server:8000/api/v1/chat/completions
   - API Key: your-secret-key-here
   - Enable streaming: Yes

4. Test the connection:
   
   curl -X POST http://localhost:8000/api/v1/health
   
   Should return: {"status": "healthy", ...}

5. Test streaming:
   
   curl -X POST http://localhost:8000/api/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-secret-key-here" \
     -H "X-User-ID: test_user" \
     -d '{
       "model": "autogen-agents",
       "messages": [{"role": "user", "content": "What is 15% of 850?"}],
       "stream": true
     }'

WHAT YOU'LL SEE IN OPENWEBUI:

User: "Show me top 5 sales"

🎯 SupervisorAgent
Routing to: DATA_ANALYSIS_TEAM

🤔 SQLAgent [Thinking]
I need to find the sales table and check its schema

⚡ SQLAgent [Action]
get_table_schema("sales")

📦 Tool Result
Schema: id, customer, amount, date...

⚡ SQLAgent [Action]
SELECT TOP 5 customer, amount 
FROM sales 
ORDER BY amount DESC

🛡️ ValidationAgent [Validation]
✓ Query is safe
✓ No dangerous operations
Approved for execution

📦 Tool Result
5 rows returned

📊 AnalysisAgent [Analysis]
Top 5 customers with highest sales...

✅ Final Answer
[Shows results and analysis]
"""
