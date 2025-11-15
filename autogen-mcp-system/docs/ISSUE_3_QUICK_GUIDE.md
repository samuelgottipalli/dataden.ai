# Issue #3: Quick Implementation Guide
## Execution Limits, Fallback & Increased Context

---

## 📦 What You Have

1. **[Complete Guide](computer:///mnt/user-data/outputs/ISSUE_3_COMPLETE_IMPLEMENTATION.md)** - Full details
2. **[usage_tracker.py](computer:///mnt/user-data/outputs/usage_tracker.py)** - Ready to use
3. **[model_manager.py](computer:///mnt/user-data/outputs/model_manager.py)** - Ready to use

---

## 🚀 Implementation Steps (30 minutes)

### Step 1: Install Fallback Model (5 min)

```bash
# Pull the lightweight fallback model
ollama pull llama3.2:3b

# Verify it works
ollama run llama3.2:3b "test"
```

---

### Step 2: Create Utils Directory & Add Files (2 min)

```bash
# Create utils directory if it doesn't exist
mkdir -p utils

# Create __init__.py
touch utils/__init__.py

# Copy the two utility files
# Place usage_tracker.py in utils/
# Place model_manager.py in utils/
```

**Folder structure:**
```
your-project/
└── utils/
    ├── __init__.py
    ├── usage_tracker.py  ← NEW
    └── model_manager.py  ← NEW
```

---

### Step 3: Update Settings (10 min)

**File:** `config/settings.py`

**ADD these new settings** after the existing `ollama_model` line (around line 20):

```python
    # Ollama - PRIMARY MODEL
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:120b-cloud"
    
    # ===== ADD THESE NEW SETTINGS =====
    
    # Fallback Model Configuration
    ollama_fallback_model: str = "llama3.2:3b"
    enable_fallback: bool = True
    fallback_after_attempts: int = 2
    
    # Token and Context Configuration  
    max_tokens: int = 8000  # INCREASED from 4000
    temperature: float = 0.3
    
    # Rate Limiting
    max_retries_per_query: int = 3
    retry_delay_seconds: int = 2
    
    # API Quota Limits
    api_quota_daily_limit: int = 1000
    api_quota_warn_percentage: float = 0.8
    api_quota_reset_hour: int = 0
    
    # Usage Tracking
    track_token_usage: bool = True
    usage_log_file: str = "logs/api_usage.log"
    
    # User Notifications
    notify_on_fallback: bool = True
    notify_on_quota_warning: bool = True
    show_token_count: bool = False
    
    # ===== END NEW SETTINGS =====
```

---

### Step 4: Update Orchestrator __init__ (5 min)

**File:** `agents/enhanced_orchestrator.py`

**FIND the __init__ method** (around line 25) and **REPLACE** with:

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

---

### Step 5: Add Retry Logic to Orchestrator (8 min)

**File:** `agents/enhanced_orchestrator.py`

**ADD this new method** (around line 200, before `execute_task_with_routing`):

```python
async def _execute_with_retry(self, team, task_description: str, team_name: str) -> dict:
    """Execute task with retry logic and fallback support"""
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
            # Check quota
            quota_status = tracker.check_quota()
            if quota_status["exceeded"]:
                return {
                    "success": False,
                    "error": "Daily API quota exceeded. Please try again tomorrow."
                }
            
            # Execute
            result = await team.run(task=task_description)
            
            # Extract response
            final_message = None
            if hasattr(result, 'messages') and result.messages:
                final_message = result.messages[-1].content
            else:
                final_message = str(result)
            
            # Record success
            tracker.record_request(tokens_used=len(final_message.split()))
            model_manager.record_success()
            
            return {
                "success": True,
                "response": final_message,
                "routed_to": team_name
            }
        
        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {e}")
            model_manager.record_failure()
            
            if attempt >= max_retries:
                return {
                    "success": False,
                    "error": f"Failed after {max_retries} attempts: {str(e)}"
                }
            
            # If switched to fallback, recreate team
            if model_manager.using_fallback:
                self.model_client, self.current_model = model_manager.get_model_client()
                if "DATA" in team_name:
                    team = await self.create_data_analysis_team()
                else:
                    team = await self.create_general_assistant_team()
            
            # Wait before retry
            await asyncio.sleep(settings.retry_delay_seconds * attempt)
```

**Then UPDATE execute_task_with_routing** to use this new method.

**FIND** this line (around line 450):
```python
result = await team.run(task=task_description)
```

**REPLACE** with:
```python
result = await self._execute_with_retry(team, task_description, team_name)
return result
```

---

### Step 6: Restart & Test (5 min)

```bash
# Stop server
# Start again
python mcp_server/main.py

# Check logs - should see:
# "Initialized Enhanced Orchestrator"
# "Model: gpt-oss:120b-cloud"
# "Max tokens: 8000"  ← Should be 8000 now!
```

---

## ✅ Testing

### Test 1: Check increased context

Look at logs when starting server:
```
✓ Should see: "Max tokens: 8000"
✗ If you see: "Max tokens: 4000" - settings not loaded
```

### Test 2: Check usage tracking

```bash
# After a few queries, check usage file:
cat logs/usage_tracking.json

# Should show:
# "requests_today": 5
# "tokens_today": 2500
```

### Test 3: Force fallback

In Python console:
```python
from utils.model_manager import get_model_manager

manager = get_model_manager()
manager.record_failure()
manager.record_failure()

print(f"Using fallback: {manager.using_fallback}")
# Should print: Using fallback: True
```

### Test 4: Check quota

```python
from utils.usage_tracker import get_usage_tracker

tracker = get_usage_tracker()
print(tracker.get_usage_summary())

# Should show usage stats
```

---

## 🎯 What Changed

| Feature | Before | After |
|---------|--------|-------|
| Max tokens | 4000 | 8000 ✅ |
| Fallback model | None | llama3.2:3b ✅ |
| Max retries | Unlimited | 3 ✅ |
| Usage tracking | None | Full tracking ✅ |
| Quota limits | None | 1000/day ✅ |
| Auto-fallback | No | Yes ✅ |
| User notifications | No | Yes ✅ |

---

## 📁 Files Changed

1. `config/settings.py` - Added ~20 new settings
2. `utils/usage_tracker.py` - NEW file (~200 lines)
3. `utils/model_manager.py` - NEW file (~100 lines)
4. `agents/enhanced_orchestrator.py` - Modified __init__ + added _execute_with_retry (~80 lines)

**Total:** 3 files modified, 2 files created

---

## 🐛 Troubleshooting

### Issue: "No module named 'utils'"

**Fix:**
```bash
# Make sure utils/__init__.py exists
touch utils/__init__.py
```

### Issue: "AttributeError: 'Settings' object has no attribute 'max_tokens'"

**Fix:** Settings not loaded properly. Check:
1. Did you add ALL new settings to settings.py?
2. Restart server after changing settings.py

### Issue: Fallback not triggering

**Check logs** for:
```
"Model failure #1"
"Model failure #2"
"⚠️  Switching to fallback model"
```

If not seeing these, failures aren't being recorded.

---

## ✅ Success Criteria

After implementing, verify:

- [ ] Server starts without errors
- [ ] Logs show "Max tokens: 8000"
- [ ] usage_tracking.json file created in logs/
- [ ] Can query normally
- [ ] Usage is being tracked
- [ ] Fallback model installed (`ollama list` shows llama3.2:3b)

---

**Time needed:** ~30 minutes

**Difficulty:** Medium (involves multiple files)

**Impact:** HIGH - prevents quota exhaustion, adds reliability

---

Ready to implement? Start with Step 1!
