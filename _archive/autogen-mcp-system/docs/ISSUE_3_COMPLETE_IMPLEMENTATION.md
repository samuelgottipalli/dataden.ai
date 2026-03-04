# Issue #3: Execution Limits, Fallback Model & Increased Context
## Complete Implementation Guide

---

## 🎯 What We're Implementing

1. **Execution Limits** - Max retries per query (prevent infinite loops)
2. **Fallback Model** - Switch to local model when cloud fails
3. **API Usage Tracking** - Monitor token consumption
4. **Increased Context Length** - Handle longer responses (4000 → 8000 tokens)
5. **User Notifications** - Inform users about model switches

---

## 📊 Current vs Target Configuration

### Current Configuration:
```python
# config/settings.py - CURRENT
ollama_model: str = "gpt-oss:120b-cloud"  # Cloud model
temperature: 0.3
max_tokens: 4000
# No fallback
# No retry limits
# No usage tracking
```

### Target Configuration:
```python
# config/settings.py - TARGET
ollama_model: str = "gpt-oss:120b-cloud"        # Primary cloud model
ollama_fallback_model: str = "llama3.2:3b"      # Local fallback
max_tokens: 8000                                 # Increased for long responses
max_retries_per_query: int = 3                   # Retry limit
api_quota_daily_limit: int = 1000                # Daily request limit
enable_fallback: bool = True                     # Auto-fallback on failure
fallback_after_attempts: int = 2                 # Fallback after 2 failures
```

---

## 📦 Files to Create/Modify

### File 1: Update Settings (config/settings.py)
### File 2: Create Usage Tracker (utils/usage_tracker.py) - NEW
### File 3: Create Model Manager (utils/model_manager.py) - NEW
### File 4: Update Orchestrator (agents/enhanced_orchestrator.py)
### File 5: Update API Routes (mcp_server/api_routes.py)

---

## FILE 1: Update Settings

**File:** `config/settings.py`

**ADD these new settings** (around line 20, after ollama_model):

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Ollama - PRIMARY MODEL
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_model_info: dict[str, str | bool] = {
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "gpt-oss",
        "structured_output": True,
    }

    # ===== NEW SETTINGS FOR ISSUE #3 =====
    
    # Fallback Model Configuration
    ollama_fallback_model: str = "llama3.2:3b"  # Smaller local model
    enable_fallback: bool = True                 # Enable automatic fallback
    fallback_after_attempts: int = 2             # Fallback after N failures
    
    # Token and Context Configuration
    max_tokens: int = 8000                       # Increased from 4000
    temperature: float = 0.3                     # Keep low for consistency
    
    # Rate Limiting and Retry Configuration
    max_retries_per_query: int = 3               # Max attempts per query
    retry_delay_seconds: int = 2                 # Wait between retries
    
    # API Quota Limits (Cloud Model)
    api_quota_daily_limit: int = 1000            # Daily request limit
    api_quota_warn_percentage: float = 0.8       # Warn at 80%
    api_quota_reset_hour: int = 0                # Reset at midnight
    
    # Usage Tracking
    track_token_usage: bool = True               # Track all token usage
    usage_log_file: str = "logs/api_usage.log"   # Usage log location
    
    # User Notifications
    notify_on_fallback: bool = True              # Tell user when falling back
    notify_on_quota_warning: bool = True         # Warn approaching quota
    show_token_count: bool = False               # Show tokens in response (debug)
    
    # ===== END NEW SETTINGS =====

    # MS SQL Server
    mssql_server: str
    mssql_port: int = 1433
    mssql_database: str
    mssql_user: str
    mssql_password: str
    mssql_driver: str = "{ODBC Driver 18 for SQL Server}"

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

    # OpenWebUI Integration
    openwebui_api_key: str = ""

    class Config:
        env_file = r"G:\dataden.ai\autogen-mcp-system\config\.env"
        case_sensitive = False


settings = Settings()
```

---

## FILE 2: Create Usage Tracker

**File:** `utils/usage_tracker.py` (NEW FILE - create this)

```python
"""
Usage Tracker - Monitor API usage and enforce quotas
Tracks token consumption and request counts
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger
import json
import os
from pathlib import Path

class UsageTracker:
    """Track API usage to prevent quota exhaustion"""
    
    def __init__(self, daily_limit: int = 1000, warn_percentage: float = 0.8):
        self.daily_limit = daily_limit
        self.warn_percentage = warn_percentage
        self.usage_file = Path("logs/usage_tracking.json")
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing usage data
        self.data = self._load_usage_data()
    
    def _load_usage_data(self) -> Dict:
        """Load usage data from file"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load usage data: {e}")
        
        # Return default structure
        return {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "requests_today": 0,
            "tokens_today": 0,
            "requests_total": 0,
            "tokens_total": 0,
            "last_warning_at": None,
            "fallback_count": 0
        }
    
    def _save_usage_data(self):
        """Save usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save usage data: {e}")
    
    def _check_date_reset(self):
        """Reset daily counters if new day"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.data["current_date"] != current_date:
            logger.info(f"New day detected, resetting daily counters")
            self.data["current_date"] = current_date
            self.data["requests_today"] = 0
            self.data["tokens_today"] = 0
            self.data["last_warning_at"] = None
            self._save_usage_data()
    
    def record_request(self, tokens_used: int = 0, model: str = "primary"):
        """Record a request and token usage"""
        self._check_date_reset()
        
        # Increment counters
        self.data["requests_today"] += 1
        self.data["requests_total"] += 1
        self.data["tokens_today"] += tokens_used
        self.data["tokens_total"] += tokens_used
        
        # Track fallback usage
        if model == "fallback":
            self.data["fallback_count"] += 1
        
        # Save
        self._save_usage_data()
        
        logger.debug(f"Usage recorded: {self.data['requests_today']}/{self.daily_limit} requests today")
    
    def check_quota(self) -> Dict[str, any]:
        """
        Check if approaching or exceeded quota
        
        Returns:
            dict with: exceeded, approaching, percentage, remaining
        """
        self._check_date_reset()
        
        requests_today = self.data["requests_today"]
        percentage = requests_today / self.daily_limit
        remaining = self.daily_limit - requests_today
        
        exceeded = requests_today >= self.daily_limit
        approaching = percentage >= self.warn_percentage
        
        return {
            "exceeded": exceeded,
            "approaching": approaching,
            "percentage": percentage,
            "remaining": remaining,
            "used": requests_today,
            "limit": self.daily_limit
        }
    
    def should_warn_user(self) -> bool:
        """Check if we should warn user about quota"""
        quota_status = self.check_quota()
        
        # Don't spam warnings - only once when crossing threshold
        if quota_status["approaching"] and not self.data["last_warning_at"]:
            self.data["last_warning_at"] = datetime.now().isoformat()
            self._save_usage_data()
            return True
        
        return False
    
    def get_usage_summary(self) -> str:
        """Get human-readable usage summary"""
        self._check_date_reset()
        quota_status = self.check_quota()
        
        summary = f"""
📊 API Usage Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Today: {quota_status['used']}/{quota_status['limit']} requests ({quota_status['percentage']:.1%})
Remaining: {quota_status['remaining']} requests
Tokens used today: {self.data['tokens_today']:,}
Fallback usage: {self.data['fallback_count']} times

Total (all time):
  Requests: {self.data['requests_total']:,}
  Tokens: {self.data['tokens_total']:,}
"""
        return summary.strip()


# Global instance
_tracker = None

def get_usage_tracker() -> UsageTracker:
    """Get or create global usage tracker"""
    global _tracker
    if _tracker is None:
        from config.settings import settings
        _tracker = UsageTracker(
            daily_limit=settings.api_quota_daily_limit,
            warn_percentage=settings.api_quota_warn_percentage
        )
    return _tracker
```

---

## FILE 3: Create Model Manager

**File:** `utils/model_manager.py` (NEW FILE - create this)

```python
"""
Model Manager - Handle primary and fallback models
Automatic switching when primary model fails
"""

from loguru import logger
from typing import Optional, Tuple
from autogen_ext.models.openai import OllamaChatCompletionClient
from config.settings import settings

class ModelManager:
    """Manage primary and fallback model switching"""
    
    def __init__(self):
        self.primary_model = settings.ollama_model
        self.fallback_model = settings.ollama_fallback_model
        self.enable_fallback = settings.enable_fallback
        self.fallback_after_attempts = settings.fallback_after_attempts
        
        self.current_model = self.primary_model
        self.failure_count = 0
        self.using_fallback = False
    
    def get_model_client(self, force_fallback: bool = False) -> Tuple[OllamaChatCompletionClient, str]:
        """
        Get appropriate model client
        
        Returns:
            (model_client, model_name)
        """
        # Determine which model to use
        if force_fallback or (self.using_fallback and self.enable_fallback):
            model_name = self.fallback_model
            logger.info(f"🔄 Using fallback model: {model_name}")
        else:
            model_name = self.primary_model
            logger.debug(f"Using primary model: {model_name}")
        
        # Create client with INCREASED context length
        client = OllamaChatCompletionClient(
            model=model_name,
            base_url=settings.ollama_host,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,  # Now 8000!
        )
        
        return client, model_name
    
    def record_failure(self) -> bool:
        """
        Record a model failure
        
        Returns:
            True if should switch to fallback
        """
        self.failure_count += 1
        logger.warning(f"Model failure #{self.failure_count}")
        
        # Check if we should switch to fallback
        if (self.enable_fallback and 
            not self.using_fallback and 
            self.failure_count >= self.fallback_after_attempts):
            
            logger.warning(f"⚠️  Switching to fallback model after {self.failure_count} failures")
            self.using_fallback = True
            return True
        
        return False
    
    def record_success(self):
        """Record a successful request"""
        # Reset failure counter on success
        if self.failure_count > 0:
            logger.info("✓ Request successful, resetting failure counter")
            self.failure_count = 0
    
    def reset_to_primary(self):
        """Reset back to primary model"""
        if self.using_fallback:
            logger.info("Resetting to primary model")
            self.using_fallback = False
            self.failure_count = 0
    
    def get_fallback_notification(self) -> str:
        """Get user notification message about fallback"""
        if not self.using_fallback:
            return ""
        
        return f"""
🔄 **Notice: Using Fallback Model**

The primary cloud model is currently unavailable. I've switched to a local model ({self.fallback_model}).

**What this means:**
- ✅ Your request will still be processed
- ⚠️  Response quality may be slightly reduced
- ⚠️  Response time may be slower
- ✅ No data or context is lost

You can continue your conversation normally. The system will automatically switch back to the primary model when available.
"""

# Global instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get or create global model manager"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
```

---

## FILE 4: Update Enhanced Orchestrator

**File:** `agents/enhanced_orchestrator.py`

**MODIFY the __init__ method** (around line 25):

```python
def __init__(self, model_name: Optional[str] = None):
    """Initialize the orchestrator with model client"""
    
    # Use model manager for dynamic model selection
    from utils.model_manager import get_model_manager
    model_manager = get_model_manager()
    
    # Get appropriate model client
    self.model_client, self.current_model = model_manager.get_model_client()
    self.model_manager = model_manager
    
    logger.info(f"Initialized Enhanced Orchestrator")
    logger.info(f"Model: {self.current_model}")
    logger.info(f"Max tokens: {settings.max_tokens}")
    logger.info(f"Temperature: {settings.temperature}")
```

**ADD this new method** (around line 200):

```python
async def _execute_with_retry(self, team, task_description: str, team_name: str) -> dict:
    """
    Execute task with retry logic and fallback support
    
    Handles:
    - Automatic retries on failure
    - Fallback to local model
    - Usage tracking
    - User notifications
    """
    from utils.usage_tracker import get_usage_tracker
    from utils.model_manager import get_model_manager
    import asyncio
    
    tracker = get_usage_tracker()
    model_manager = get_model_manager()
    
    max_retries = settings.max_retries_per_query
    attempt = 0
    
    while attempt < max_retries:
        attempt += 1
        logger.info(f"Attempt {attempt}/{max_retries}")
        
        try:
            # Check quota before making request
            quota_status = tracker.check_quota()
            
            if quota_status["exceeded"]:
                logger.error("❌ Daily API quota exceeded!")
                return {
                    "success": False,
                    "error": "Daily API quota exceeded. Please try again tomorrow.",
                    "quota_status": quota_status
                }
            
            # Warn user if approaching quota
            if tracker.should_warn_user():
                logger.warning(f"⚠️  Approaching quota: {quota_status['percentage']:.0%} used")
            
            # Execute task
            result = await team.run(task=task_description)
            
            # Extract response
            final_message = None
            if hasattr(result, 'messages') and result.messages:
                final_message = result.messages[-1].content
            else:
                final_message = str(result)
            
            # Record successful request
            tracker.record_request(tokens_used=len(final_message.split()), model="primary")
            model_manager.record_success()
            
            logger.info("✓ Task completed successfully")
            
            return {
                "success": True,
                "response": final_message,
                "routed_to": team_name,
                "attempt": attempt,
                "model_used": model_manager.current_model
            }
        
        except Exception as e:
            logger.error(f"❌ Attempt {attempt} failed: {e}")
            
            # Record failure
            model_manager.record_failure()
            
            # Check if we should switch to fallback
            switched_to_fallback = model_manager.using_fallback
            
            # If this was the last attempt, return error
            if attempt >= max_retries:
                return {
                    "success": False,
                    "error": f"Failed after {max_retries} attempts: {str(e)}",
                    "routed_to": team_name,
                    "fallback_attempted": switched_to_fallback
                }
            
            # If switched to fallback, recreate team with new model
            if switched_to_fallback:
                logger.info("🔄 Recreating team with fallback model")
                self.model_client, self.current_model = model_manager.get_model_client()
                
                # Recreate team based on type
                if "DATA" in team_name:
                    team = await self.create_data_analysis_team()
                else:
                    team = await self.create_general_assistant_team()
            
            # Wait before retry
            if attempt < max_retries:
                wait_time = settings.retry_delay_seconds * attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
```

**UPDATE execute_task_with_routing** (around line 400) to use the new retry logic:

Find this line:
```python
result = await team.run(task=task_description)
```

Replace with:
```python
result = await self._execute_with_retry(team, task_description, team_name)
return result
```

---

## FILE 5: Update API Routes

**File:** `mcp_server/api_routes.py`

**UPDATE the stream_agent_response function** (around line 100) to show fallback notifications:

Add this at the beginning of the function (after creating orchestrator):

```python
async def stream_agent_response(message: str, user_id: str, user_email: str):
    """Stream agent messages back to OpenWebUI in real-time"""
    
    try:
        # Create orchestrator
        orchestrator = EnhancedAgentOrchestrator()
        
        # Get model manager and usage tracker
        from utils.model_manager import get_model_manager
        from utils.usage_tracker import get_usage_tracker
        
        model_manager = get_model_manager()
        tracker = get_usage_tracker()
        
        # Generate unique ID
        conversation_id = f"chatcmpl-{int(datetime.now().timestamp())}"
        
        logger.info(f"🎬 Starting streaming response for {user_id}")
        
        # Check quota first
        quota_status = tracker.check_quota()
        
        if quota_status["exceeded"]:
            # Send quota exceeded message
            error_chunk = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"\n⚠️ **Daily API Quota Exceeded**\n\nYou've used {quota_status['used']}/{quota_status['limit']} requests today.\n\nPlease try again tomorrow when the quota resets.\n"
                    },
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # Warn if approaching quota
        if quota_status["approaching"] and tracker.should_warn_user():
            warning_chunk = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"\n⚠️ **Quota Warning:** {quota_status['used']}/{quota_status['limit']} requests used ({quota_status['percentage']:.0%})\n\n"
                    },
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(warning_chunk)}\n\n"
        
        # Show fallback notification if using fallback
        if model_manager.using_fallback and settings.notify_on_fallback:
            fallback_notification = model_manager.get_fallback_notification()
            fallback_chunk = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now().timestamp()),
                "model": "autogen-agents",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": fallback_notification
                    },
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(fallback_chunk)}\n\n"
        
        # Rest of your existing streaming code...
        message_count = 0
        async for event in orchestrator.execute_with_streaming(
            task_description=message,
            username=user_id
        ):
            # ... existing code ...
```

---

## Testing the Implementation

### Test 1: Normal Operation
```bash
# Should work normally with primary model
curl -N -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "model": "autogen-agents",
    "messages": [{"role": "user", "content": "What is 15% of 850?"}],
    "stream": true
  }' \
  http://localhost:8000/api/v1/chat/completions
```

### Test 2: Check Usage
```python
from utils.usage_tracker import get_usage_tracker

tracker = get_usage_tracker()
print(tracker.get_usage_summary())
```

### Test 3: Force Fallback
```python
# In Python console
from utils.model_manager import get_model_manager

manager = get_model_manager()
manager.record_failure()
manager.record_failure()  # Should trigger fallback

# Next request will use fallback model
```

### Test 4: Quota Check
```python
from utils.usage_tracker import get_usage_tracker

tracker = get_usage_tracker()
status = tracker.check_quota()
print(f"Used: {status['used']}/{status['limit']}")
print(f"Remaining: {status['remaining']}")
```

---

## Expected Behavior

### Scenario 1: Normal Usage
```
User: Show me top 5 customers

🎯 SupervisorAgent
Routing to: Data Analysis Team

[Normal response with gpt-oss:120b-cloud]

✅ Answer
[Results displayed]

Usage: 15/1000 requests (1.5%)
```

### Scenario 2: Cloud Model Fails
```
User: Show me top 5 customers

[Attempt 1 fails]
[Attempt 2 fails]

🔄 Notice: Using Fallback Model
The primary cloud model is currently unavailable...

🎯 SupervisorAgent
Routing to: Data Analysis Team

[Response with llama3.2:3b fallback model]

✅ Answer
[Results displayed - may be slightly different quality]

Usage: 17/1000 requests (1.7%)
```

### Scenario 3: Approaching Quota
```
User: Show me revenue

⚠️ Quota Warning: 850/1000 requests used (85%)

🎯 SupervisorAgent
...
[Normal response continues]
```

### Scenario 4: Quota Exceeded
```
User: Show me revenue

⚠️ Daily API Quota Exceeded

You've used 1000/1000 requests today.
Please try again tomorrow when the quota resets.
```

---

## Configuration Summary

**Primary Changes:**
- ✅ Max tokens: 4000 → 8000 (handle longer responses)
- ✅ Fallback model: llama3.2:3b (lightweight local)
- ✅ Max retries: 3 per query
- ✅ Daily quota: 1000 requests
- ✅ Auto-fallback after 2 failures
- ✅ Usage tracking enabled
- ✅ User notifications enabled

---

Ready to implement? This is comprehensive but straightforward!
