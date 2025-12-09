# ============================================================
# COMPLETE API Routes - Matches Working Orchestrator
# ============================================================

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.enhanced_orchestrator import EnhancedAgentOrchestrator
from config.settings import settings
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["openwebui"])


# ============================================================
# Models
# ============================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "autogen-agents"
    messages: List[Message]
    stream: bool = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2000


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]


# ============================================================
# Authentication - Handles both formats
# ============================================================

def verify_api_key(
    x_api_key: Optional[str] = None,
    authorization: Optional[str] = None
) -> bool:
    """Verify API key from X-API-Key or Authorization Bearer"""

    if not settings.openwebui_api_key:
        logger.warning("⚠️ No API key configured")
        return True

    received_key = None
    if authorization:
        received_key = authorization.replace("Bearer ", "").strip()
    elif x_api_key:
        received_key = x_api_key.strip()

    if not received_key:
        logger.error("❌ No API key")
        raise HTTPException(401, "API key required")

    if received_key != settings.openwebui_api_key:
        logger.error("❌ Invalid API key")
        raise HTTPException(401, "Invalid API key")

    return True


# ============================================================
# Main Chat Endpoint
# ============================================================


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
):
    """Chat completions with streaming and conversation context"""

    verify_api_key(x_api_key=x_api_key, authorization=authorization)

    user_id = x_user_id or "anonymous"
    user_email = x_user_email or "unknown@example.com"

    # Extract ALL messages (for context)
    all_messages = request.messages

    # Get user messages
    user_messages = [msg for msg in all_messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message")

    # Current message is the last user message
    last_message = user_messages[-1].content

    # Build conversation history (everything BEFORE the last message)
    # This includes previous user messages AND assistant responses
    conversation_history = []
    for msg in all_messages[:-1]:  # All except the last one
        conversation_history.append({"role": msg.role, "content": msg.content})

    logger.info(f"💬 Chat from {user_id}: {last_message[:100]}...")
    if conversation_history:
        logger.info(f"📚 With {len(conversation_history)} previous messages in context")

    if request.stream:
        return StreamingResponse(
            stream_response(last_message, user_id, conversation_history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await non_streaming_response(last_message, user_id, conversation_history)


# ============================================================
# Streaming Implementation
# ============================================================


async def stream_response(
    message: str, user_id: str, conversation_history: List[Dict] = None
):
    """Stream agent responses with conversation context"""

    try:
        orchestrator = EnhancedAgentOrchestrator()
        conversation_id = f"chatcmpl-{datetime.now().timestamp()}"

        logger.info(f"🎬 Streaming for {user_id}")
        if conversation_history:
            logger.info(f"📚 Context: {len(conversation_history)} previous messages")

        # Pass conversation history to orchestrator
        async for event in orchestrator.execute_with_streaming(
            task_description=message,
            username=user_id,
            conversation_history=conversation_history,  # NEW: Pass context
        ):
            # Format as OpenAI chunk
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
                            "content": format_message(event),
                        },
                        "finish_reason": None,
                    }
                ],
            }

            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.01)

        # Final chunk
        final_chunk = {
            "id": conversation_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

        logger.info(f"✅ Streaming complete for {user_id}")

    except Exception as e:
        logger.error(f"❌ Streaming error: {e}")
        logger.exception("Full traceback:")

        error_chunk = {
            "id": conversation_id if "conversation_id" in locals() else "error",
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"\n\n❌ Error: {str(e)}\n",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


def format_message(event: dict) -> str:
    """Format event for display"""

    agent = event.get("agent", "System")
    msg_type = event.get("type", "message")
    content = event.get("content", "")

    if msg_type == "routing":
        return f"\n{content}\n"
    elif msg_type == "thinking":
        return f"\n🤔 **{agent}** [Thinking]\n{content}\n"
    elif msg_type == "action":
        return f"\n⚡ **{agent}** [Action]\n```sql\n{content}\n```\n"
    elif msg_type == "validation":
        return f"\n🛡️ **{agent}**\n{content}\n"
    elif msg_type == "analysis":
        return f"\n📊 **{agent}**\n{content}\n"
    elif msg_type == "final":
        return f"\n✅ **Result**\n{content}\n"
    elif msg_type == "error":
        return f"\n❌ **Error**\n{content}\n"
    else:
        return f"\n💬 **{agent}**\n{content}\n"


# ============================================================
# Non-Streaming Fallback
# ============================================================


async def non_streaming_response(
    message: str, user_id: str, conversation_history: List[Dict] = None
) -> ChatResponse:
    """Non-streaming fallback with conversation context"""

    logger.warning(f"⚠️ Non-streaming from {user_id}")
    if conversation_history:
        logger.info(f"📚 Context: {len(conversation_history)} previous messages")

    try:
        orchestrator = EnhancedAgentOrchestrator()

        # Pass conversation history to orchestrator
        result = await orchestrator.execute_task_with_routing(
            task_description=message,
            username=user_id,
            conversation_history=conversation_history,  # NEW: Pass context
        )

        if result["success"]:
            content = result.get("response", "Completed")
        else:
            content = f"Error: {result.get('error', 'Unknown')}"

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

    except Exception as e:
        logger.error(f"❌ Non-streaming error: {e}")
        raise HTTPException(500, f"Execution failed: {str(e)}")


# ============================================================
# Info Endpoints
# ============================================================

@router.get("/models")
async def list_models():
    """List models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "autogen-agents",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "autogen-mcp-system",
            }
        ],
    }


@router.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "autogen-mcp-system",
        "version": "2.0-complete",
        "timestamp": datetime.now().isoformat(),
    }
