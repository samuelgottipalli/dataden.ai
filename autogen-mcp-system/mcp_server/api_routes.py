# ============================================================
# PHASE 1: INTERACTIVE API ROUTES
# Updated streaming API with user question/answer support
# ============================================================

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio
from datetime import datetime
from loguru import logger

# Import Phase 1 orchestrator
from agents.enhanced_orchestrator import EnhancedAgentOrchestrator
from config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["openwebui"])


# ============================================================
# Request/Response Models
# ============================================================


class Message(BaseModel):
    """Single message in conversation"""
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    """OpenAI-compatible chat request"""
    model: str = "autogen-agents"
    messages: List[Message]
    stream: bool = True
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 4000


class ChatResponse(BaseModel):
    """OpenAI-compatible chat response"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]


# ============================================================
# PHASE 1: Conversation ID Management
# ============================================================

# Store conversation IDs per user session
# In production, this should be Redis or database
conversation_tracking = {}


def get_or_create_conversation_id(user_id: str, session_hint: Optional[str] = None) -> str:
    """
    Get existing conversation ID or create new one
    
    Args:
        user_id: User identifier
        session_hint: Optional hint from client (e.g. OpenWebUI session)
    
    Returns:
        conversation_id to use
    """
    
    if session_hint and session_hint in conversation_tracking:
        return conversation_tracking[session_hint]["conversation_id"]
    
    # Create new conversation
    import uuid
    conversation_id = f"conv-{uuid.uuid4()}"
    
    if session_hint:
        conversation_tracking[session_hint] = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "created": datetime.now().isoformat()
        }
    
    return conversation_id


# ============================================================
# Authentication
# ============================================================


def verify_api_key(api_key: Optional[str] = None) -> bool:
    """Verify API key from OpenWebUI"""
    
    if not settings.openwebui_api_key:
        logger.warning("No API key configured - allowing all requests")
        return True

    if api_key != settings.openwebui_api_key:
        logger.error(f"Invalid API key received")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


# ============================================================
# PHASE 1: MAIN CHAT ENDPOINT (with interactive support)
# ============================================================


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Phase 1: Interactive Chat Completions
    
    Now supports:
    - Agents asking clarifying questions
    - Conversation pause/resume
    - Multi-turn interactions
    
    Headers:
        X-API-Key: API key for authentication
        X-User-ID: User identifier (from LDAP)
        X-User-Email: User email
        X-Session-ID: Optional session identifier for tracking conversations
    """

    verify_api_key(x_api_key)

    user_id = x_user_id or "anonymous"
    user_email = x_user_email or "unknown@example.com"

    # Get user messages
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message found")

    last_message = user_messages[-1].content

    logger.info(f"💬 Chat request from {user_id}: {last_message[:100]}...")

    # Stream response
    if request.stream:
        return StreamingResponse(
            stream_interactive_response(
                message=last_message,
                user_id=user_id,
                user_email=user_email,
                session_id=x_session_id
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming fallback
        return await non_streaming_response(last_message, user_id, user_email)


# ============================================================
# PHASE 1: INTERACTIVE STREAMING
# ============================================================


async def stream_interactive_response(
    message: str,
    user_id: str,
    user_email: str,
    session_id: Optional[str] = None
):
    """
    Phase 1: Stream agent responses with interactive Q&A support
    
    This function handles:
    1. Normal streaming execution
    2. Pausing when agent asks a question
    3. Resuming when user provides an answer
    
    Yields:
        Server-Sent Events in OpenAI format
    """

    try:
        orchestrator = EnhancedAgentOrchestrator()
        
        # Get or create conversation ID
        conversation_id = get_or_create_conversation_id(user_id, session_id)
        
        # Generate response ID
        response_id = f"chatcmpl-{int(datetime.now().timestamp())}"
        
        logger.info(f"🎬 Starting interactive streaming for {user_id}")
        logger.info(f"Conversation: {conversation_id}")
        
        # Check if this is a response to a pending question
        user_response = None
        if conversation_id in orchestrator.pending_questions:
            logger.info(f"▶️ Detected response to pending question")
            user_response = message
        
        # Execute with interactive capability
        message_count = 0
        async for event in orchestrator.execute_with_interactive_streaming(
            task_description=message,
            username=user_id,
            conversation_id=conversation_id,
            user_response=user_response
        ):
            message_count += 1
            
            event_type = event.get("type", "message")
            agent_name = event.get("agent", "Agent")
            content = event.get("content", "")
            
            # Special handling for user_question events
            if event_type == "user_question":
                logger.info(f"❓ Agent asked question - pausing execution")
                
                # Format as complete message (not streaming)
                # This tells OpenWebUI the response is complete and waiting for user
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": int(datetime.now().timestamp()),
                    "model": "autogen-agents",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": content
                        },
                        "finish_reason": "stop"  # Important: mark as complete
                    }]
                }
                
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
                
                logger.info("⏸️ Streaming paused - waiting for user response")
                return  # Stop streaming, wait for next user message
            
            # Format regular message for streaming
            formatted_content = format_agent_message(agent_name, event_type, content)
            
            # Create streaming chunk
            chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": formatted_content + "\n"
                    },
                    "finish_reason": None  # Still streaming
                }]
            }
            
            yield f"data: {json.dumps(chunk)}\n\n"
            
            # Small delay for readability
            await asyncio.sleep(0.05)
        
        # Final chunk
        final_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
        
        logger.info(f"✅ Streaming complete: {message_count} events")

    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        logger.exception("Full traceback:")
        
        error_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": f"\n❌ **Error:** {str(e)}\n\nPlease try again.\n"
                },
                "finish_reason": "stop"
            }]
        }
        
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


# ============================================================
# Message Formatting
# ============================================================


def format_agent_message(agent: str, msg_type: str, content: str) -> str:
    """
    Format agent message for display in OpenWebUI
    
    Phase 1: Adds visual indicators for different message types
    """
    
    # Skip certain verbose message types
    if msg_type in ["tool_result"] and len(content) > 500:
        return ""  # Don't show very verbose tool results
    
    # Add emoji prefixes based on type
    emoji_map = {
        "routing": "🎯",
        "thinking": "🤔",
        "action": "⚡",
        "validation": "🛡️",
        "analysis": "📊",
        "tool_result": "📦",
        "error": "❌",
        "user_response": "✅",
        "user_question": "🤔",
        "final": "✨"
    }
    
    emoji = emoji_map.get(msg_type, "💬")
    
    # Format based on type
    if msg_type == "routing":
        return f"{emoji} **{agent}:** {content}"
    elif msg_type == "thinking":
        return f"{emoji} *{agent} is thinking...*"
    elif msg_type == "action":
        return f"{emoji} **{agent}** executing..."
    elif msg_type == "user_question":
        # Questions are already formatted by orchestrator
        return content
    elif msg_type == "final":
        return f"\n{emoji} **Final Result:**\n{content}"
    else:
        return f"{emoji} {content}"


# ============================================================
# Non-Streaming Fallback
# ============================================================


async def non_streaming_response(message: str, user_id: str, user_email: str):
    """
    Non-streaming fallback (not recommended for Phase 1)
    """
    
    logger.warning("Non-streaming mode requested - interactive features limited")
    
    try:
        orchestrator = EnhancedAgentOrchestrator()
        
        # Execute without streaming
        events = []
        async for event in orchestrator.execute_with_interactive_streaming(
            task_description=message,
            username=user_id
        ):
            events.append(event)
            
            # If agent asks question, return immediately
            if event.get("type") == "user_question":
                content = event.get("content", "I need more information")
                return ChatResponse(
                    id=f"chatcmpl-{int(datetime.now().timestamp())}",
                    created=int(datetime.now().timestamp()),
                    model="autogen-agents",
                    choices=[{
                        "message": {
                            "role": "assistant",
                            "content": content
                        },
                        "finish_reason": "stop"
                    }]
                )
        
        # Combine all content
        final_content = "\n".join(
            format_agent_message(e.get("agent", ""), e.get("type", ""), e.get("content", ""))
            for e in events
            if e.get("content")
        )
        
        return ChatResponse(
            id=f"chatcmpl-{int(datetime.now().timestamp())}",
            created=int(datetime.now().timestamp()),
            model="autogen-agents",
            choices=[{
                "message": {
                    "role": "assistant",
                    "content": final_content
                },
                "finish_reason": "stop"
            }]
        )
        
    except Exception as e:
        logger.error(f"Non-streaming failed: {e}")
        raise HTTPException(500, f"Execution failed: {str(e)}")


# ============================================================
# Health & Models Endpoints
# ============================================================


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "autogen-mcp-interactive",
        "phase": "1",
        "features": ["streaming", "interactive_qa", "multi_turn"],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [{
            "id": "autogen-agents",
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "autogen-mcp-system",
            "permission": [],
            "root": "autogen-agents",
            "parent": None,
            "features": ["interactive", "streaming", "clarification"],
            "phase": "1"
        }]
    }


# ============================================================
# PHASE 1: Conversation Management Endpoints
# ============================================================


@router.get("/conversations/{conversation_id}/status")
async def get_conversation_status(
    conversation_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Get status of a conversation
    
    Useful for checking if conversation is waiting for user input
    """
    
    verify_api_key(x_api_key)
    
    orchestrator = EnhancedAgentOrchestrator()
    
    has_pending_question = conversation_id in orchestrator.pending_questions
    state = orchestrator._get_conversation_state(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "has_pending_question": has_pending_question,
        "status": state.get("status") if state else "not_found",
        "pending_question": orchestrator.pending_questions.get(conversation_id),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Clear a conversation's state
    
    Useful for starting fresh or cleaning up stale conversations
    """
    
    verify_api_key(x_api_key)
    
    orchestrator = EnhancedAgentOrchestrator()
    orchestrator._clear_conversation_state(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "status": "cleared",
        "timestamp": datetime.now().isoformat()
    }
