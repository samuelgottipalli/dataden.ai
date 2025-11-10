# ISSUE #4 STREAMING FIX - Complete Implementation
# This fixes the streaming to show real-time agent messages

## Problem Identified:
1. OpenWebUI v0.6.36 has no streaming toggle - streaming controlled by API
2. Current code uses fake chunking (execute_with_streaming_fallback)
3. Need TRUE agent-level streaming where messages yield as they happen

## Solution:
Implement proper streaming by capturing agent messages in real-time and yielding them immediately

---

## FILE 1: Enhanced Orchestrator Streaming Fix

**File:** `agents/enhanced_orchestrator.py`

**What to change:** Replace the `execute_with_streaming()` method with this improved version

```python
async def execute_with_streaming(self, task_description: str, username: str = "system"):
    """
    Execute task with TRUE real-time streaming
    
    This yields agent messages AS THEY HAPPEN, not after completion
    """
    from datetime import datetime
    import asyncio
    
    try:
        logger.info(f"{'='*60}")
        logger.info(f"STREAMING TASK from {username}")
        logger.info(f"Task: {task_description}")
        logger.info(f"{'='*60}")
        
        # Step 1: Classify task and select team
        yield {
            "agent": "SupervisorAgent",
            "type": "routing",
            "content": "🎯 Analyzing your request...",
            "timestamp": datetime.now().isoformat()
        }
        
        # Classify the task
        classification = await self._classify_task(task_description)
        task_type = classification.get("type", "general").upper()
        confidence = classification.get("confidence", 0.0)
        
        # Create appropriate team
        if "SQL" in task_type or "DATABASE" in task_type or "DATA" in task_type:
            team_name = "DATA_ANALYSIS_TEAM"
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": f"🎯 **Routing Decision**\n**Team:** Data Analysis Team\n**Reason:** Database query detected\n**Confidence:** {confidence:.0%}",
                "timestamp": datetime.now().isoformat()
            }
            team = await self.create_data_analysis_team()
        else:
            team_name = "GENERAL_ASSISTANT_TEAM"
            yield {
                "agent": "SupervisorAgent",
                "type": "routing",
                "content": f"🎯 **Routing Decision**\n**Team:** General Assistant Team\n**Reason:** General task\n**Confidence:** {confidence:.0%}",
                "timestamp": datetime.now().isoformat()
            }
            team = await self.create_general_assistant_team()
        
        logger.info(f"Selected team: {team_name}")
        
        # Step 2: Stream team execution
        try:
            # Try to use run_stream if available
            if hasattr(team, 'run_stream'):
                logger.info("Using team.run_stream() for real-time streaming")
                
                async for message in team.run_stream(task=task_description):
                    # Extract message details safely
                    source = getattr(message, 'source', 'Unknown')
                    raw_content = getattr(message, 'content', None)
                    
                    # Handle content - might be string, list, or dict
                    if raw_content is None:
                        content = str(message)
                    elif isinstance(raw_content, str):
                        content = raw_content
                    elif isinstance(raw_content, (list, dict)):
                        content = str(raw_content)
                    else:
                        content = str(raw_content)
                    
                    # Classify message type based on content
                    msg_type = self._classify_message_type(source, content)
                    
                    # Yield immediately
                    yield {
                        "agent": source,
                        "type": msg_type,
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Small delay to prevent overwhelming client
                    await asyncio.sleep(0.05)
                
                # Success message
                yield {
                    "agent": "System",
                    "type": "final",
                    "content": "✅ Task completed successfully",
                    "timestamp": datetime.now().isoformat()
                }
            
            else:
                # Fallback: run_stream not available
                logger.warning("run_stream not available, using incremental execution")
                
                # Show processing message
                yield {
                    "agent": team_name,
                    "type": "thinking",
                    "content": "🤔 Processing your request...",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Execute task
                result = await self.execute_task_with_routing(
                    task_description=task_description,
                    username=username
                )
                
                # Stream the result incrementally
                if result["success"]:
                    response = result.get("response", "Task completed")
                    
                    # Send in smaller chunks for perceived streaming
                    words = response.split()
                    chunk_size = 20  # words per chunk
                    
                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i:i+chunk_size])
                        
                        yield {
                            "agent": team_name,
                            "type": "message",
                            "content": chunk,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await asyncio.sleep(0.1)
                    
                    # Final message
                    yield {
                        "agent": "System",
                        "type": "final",
                        "content": "✅ Task completed",
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    # Error message
                    yield {
                        "agent": "System",
                        "type": "error",
                        "content": f"❌ Error: {result.get('error', 'Unknown error')}",
                        "timestamp": datetime.now().isoformat()
                    }
        
        except AttributeError as ae:
            # run_stream doesn't exist - use fallback
            logger.warning(f"AttributeError with run_stream: {ae}, using fallback")
            
            # Execute normally and stream result
            result = await self.execute_task_with_routing(
                task_description=task_description,
                username=username
            )
            
            if result["success"]:
                response = result.get("response", "Task completed")
                
                # Stream response word by word for better UX
                words = response.split()
                chunk_size = 15
                
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i+chunk_size])
                    
                    yield {
                        "agent": team_name,
                        "type": "message",
                        "content": chunk + " ",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await asyncio.sleep(0.08)
            
            yield {
                "agent": "System",
                "type": "final",
                "content": "✅ Complete",
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Streaming execution failed: {e}")
        logger.exception("Full traceback:")
        
        yield {
            "agent": "System",
            "type": "error",
            "content": f"❌ Error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


def _classify_message_type(self, source: str, content: str) -> str:
    """
    Classify message type based on source and content
    
    Returns: 'routing', 'thinking', 'action', 'tool_result', 'validation', 'analysis', 'final', or 'message'
    """
    content_lower = content.lower() if isinstance(content, str) else ""
    source_lower = source.lower()
    
    # Routing messages
    if "supervisor" in source_lower or "routing" in content_lower:
        return "routing"
    
    # Thinking/planning
    if any(word in content_lower for word in ["thinking", "analyzing", "planning", "considering", "let me", "i need to", "i'll"]):
        return "thinking"
    
    # Actions/tool calls
    if any(word in content_lower for word in ["executing", "calling", "running", "query:", "select ", "function call"]):
        return "action"
    
    # Tool results
    if any(word in content_lower for word in ["result:", "output:", "returned", "rows returned"]):
        return "tool_result"
    
    # Validation
    if "validation" in source_lower or any(word in content_lower for word in ["validating", "checking", "approved", "blocked", "safe"]):
        return "validation"
    
    # Analysis
    if "analysis" in source_lower or any(word in content_lower for word in ["analyzing", "shows that", "indicates", "trend"]):
        return "analysis"
    
    # Final answer indicators
    if any(word in content_lower for word in ["final answer", "in conclusion", "to summarize", "✅"]):
        return "final"
    
    # Default
    return "message"
```

---

## FILE 2: API Routes Streaming Enhancement

**File:** `mcp_server/api_routes.py`

**What to change:** Update the `stream_agent_response()` function to flush chunks immediately

```python
async def stream_agent_response(message: str, user_id: str, user_email: str):
    """
    Stream agent messages back to OpenWebUI in real-time
    
    CRITICAL: Each chunk must be yielded and flushed immediately
    """
    try:
        # Create orchestrator
        orchestrator = EnhancedAgentOrchestrator()
        
        # Generate unique ID
        conversation_id = f"chatcmpl-{int(datetime.now().timestamp())}"
        
        logger.info(f"🎬 Starting streaming response for {user_id}")
        
        message_count = 0
        
        # Stream agent execution - THIS IS THE KEY PART
        async for event in orchestrator.execute_with_streaming(
            task_description=message,
            username=user_id
        ):
            message_count += 1
            
            # Format agent message
            formatted_content = format_agent_message(event)
            
            # Create OpenAI-compatible streaming chunk
            chunk = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": formatted_content
                    },
                    "finish_reason": None
                }]
            }
            
            # Yield immediately - NO BUFFERING
            chunk_json = json.dumps(chunk)
            yield f"data: {chunk_json}\n\n"
            
            # CRITICAL: Very small delay helps prevent overwhelming
            # But don't make it too long or it defeats real-time
            await asyncio.sleep(0.01)
        
        logger.info(f"✅ Streamed {message_count} messages for {user_id}")
        
        # Send final completion chunk
        final_chunk = {
            "id": conversation_id,
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
        
        # Send [DONE] marker
        yield "data: [DONE]\n\n"
    
    except Exception as e:
        logger.error(f"❌ Error streaming response: {e}")
        logger.exception("Full traceback:")
        
        # Send error message
        error_chunk = {
            "id": conversation_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": "autogen-agents",
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": f"\n\n❌ **Error**\n{str(e)}\n\nPlease try again."
                },
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
```

---

## FILE 3: Main Server - Ensure No Buffering

**File:** `mcp_server/main.py`

**What to add:** Ensure nginx/proxy buffering is disabled

```python
# In your CORS configuration or main.py startup

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MCP Agent System")

# CRITICAL: Disable response buffering for streaming
@app.middleware("http")
async def disable_buffering(request, call_next):
    response = await call_next(request)
    
    # Disable buffering for streaming endpoints
    if request.url.path.endswith("/chat/completions"):
        response.headers["X-Accel-Buffering"] = "no"  # Nginx
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
    
    return response

# ... rest of your app configuration
```

---

## TESTING THE FIX

### Test 1: Direct endpoint test
```bash
curl -N -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -H "X-User-ID: test" \
  -d '{
    "model": "autogen-agents",
    "messages": [{"role": "user", "content": "What is 15% of 850?"}],
    "stream": true
  }' \
  http://localhost:8000/api/v1/chat/completions

# You should see chunks arriving incrementally:
# data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"🎯 SupervisorAgent\n..."}...
# data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"🤔 Thinking\n..."}...
# data: [DONE]
```

### Test 2: Check in OpenWebUI
1. Open OpenWebUI
2. Send message: "What is 15% of 850?"
3. Watch the response area
4. You should see messages appearing incrementally, not all at once

### Test 3: Browser Developer Tools
1. Open OpenWebUI
2. Press F12
3. Go to Network tab
4. Filter by "chat"
5. Send a message
6. Look at the response - should show "text/event-stream"
7. Preview tab should show data arriving in chunks

---

## EXPECTED BEHAVIOR AFTER FIX

**Before (Current):**
```
[User sends message]
[Wait... wait... wait...]
[All response appears at once]
```

**After (Fixed):**
```
[User sends message]
🎯 SupervisorAgent - Analyzing... [appears immediately]
🎯 Routing to Data Analysis Team [appears 0.5s later]
🤔 SQLAgent - Thinking... [appears 1s later]
⚡ SQLAgent - Executing query [appears 2s later]
📦 Tool Result - 5 rows returned [appears 3s later]
✅ Final Answer - Here are results [appears 4s later]
```

Each message appears AS IT HAPPENS, not all at once!

---

## CHECKLIST

Apply these changes in order:

- [ ] Update `agents/enhanced_orchestrator.py` - Replace `execute_with_streaming()` method
- [ ] Update `agents/enhanced_orchestrator.py` - Add `_classify_message_type()` method
- [ ] Update `mcp_server/api_routes.py` - Replace `stream_agent_response()` function
- [ ] Update `mcp_server/main.py` - Add buffering disable middleware
- [ ] Restart your MCP server
- [ ] Test with curl (Test 1)
- [ ] Test in OpenWebUI (Test 2)
- [ ] Check browser network tab (Test 3)
- [ ] Verify messages arrive incrementally

---

## TROUBLESHOOTING

**If still not streaming:**

1. **Check logs** - Look for "Using team.run_stream()" or "run_stream not available"
2. **Verify no proxy buffering** - Check if you have nginx/reverse proxy
3. **Try different browser** - Some browsers cache aggressively
4. **Clear browser cache** - Force refresh (Ctrl+Shift+R)
5. **Check OpenWebUI version** - Ensure v0.6.36 supports external streaming

**Common issues:**

- **Nginx buffering**: Add `proxy_buffering off;` to nginx config
- **Browser caching**: Clear cache and hard reload
- **Firewall/proxy**: May buffer responses
- **OpenWebUI config**: Connection must point to correct endpoint

---

Ready to apply these fixes?
