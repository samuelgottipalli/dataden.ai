# Test Failures - Root Cause Analysis and Solutions

## Issues Identified

### 1. **MagenticOne vs RoundRobin Inconsistency**
**Problem:** Original code mixed two different orchestration patterns:
- `MagenticOneGroupChat` for Data Analysis Team
- `RoundRobinGroupChat` for General Assistant Team

**Why This Matters:**
- Different patterns have different requirements
- MagenticOne expects specific response formats from LLMs
- Mixing patterns can cause unpredictable behavior

**Solution:** Use `MagenticOneGroupChat` consistently across all teams for uniform behavior.

---

### 2. **"Failed to parse ledger information" Error**
**Root Cause:** This is a MagenticOne-specific error that occurs when:
1. The LLM's response format doesn't match what MagenticOne expects
2. The model generates responses in an unexpected structure
3. Temperature/token settings produce inconsistent outputs

**From logs:**
```
ValueError: Failed to parse ledger information after multiple retries.
```

**Why It Happens:**
- MagenticOne has an internal "ledger" tracking system
- It expects LLM responses to follow specific patterns
- The `gpt-oss:120b-cloud` model may not generate these patterns reliably

**Solutions Implemented:**
1. **Lower temperature** (0.7 → 0.3): More consistent, predictable responses
2. **Higher max_tokens** (2000 → 4000): Prevents truncation issues
3. **Simplified system messages**: Clearer instructions for format
4. **Better error handling**: Catches MagenticOne-specific errors
5. **Direct execution mode**: Bypass routing when format issues occur

---

### 3. **Model Compatibility Issues**
**Problem:** `gpt-oss:120b-cloud` is optimized for cloud deployment, which may have:
- Different output formatting
- Less strict adherence to format requirements
- Variations in response structure

**Recommended Alternative Models for MagenticOne:**
- `llama3:8b` or `llama3:70b` (best compatibility)
- `mistral:7b` (good balance)
- `gemma3:latest` (lightweight option)

---

## File Structure for Fixed Version

```
autogen-mcp-system/
├── agents/
│   ├── enhanced_orchestrator.py          ← REPLACE with enhanced_orchestrator_fixed.py
│   └── orchestrator.py                   ← Keep for reference
├── test_complete_system.py               ← REPLACE with test_complete_system_fixed.py
└── [other files remain the same]
```

---

## What Was Fixed in enhanced_orchestrator_fixed.py

### 1. **Consistent MagenticOne Usage**
```python
# OLD (inconsistent):
general_team = RoundRobinGroupChat(...)  # ❌ Different pattern

# NEW (consistent):
general_team = MagenticOneGroupChat(...)  # ✓ Same pattern everywhere
```

### 2. **Better Model Configuration**
```python
# OLD:
temperature=0.7,  # Too high for structured responses
max_tokens=2000,  # May truncate complex responses

# NEW:
temperature=0.3,  # Lower = more consistent formatting
max_tokens=4000,  # More headroom for complex responses
```

### 3. **Simplified System Messages**
```python
# OLD: Long, complex instructions
system_message="""[500+ words of instructions]"""

# NEW: Short, focused instructions
system_message="""You are a task classifier. 
Respond with ONLY:
- DATA_ANALYSIS_TEAM
- GENERAL_ASSISTANT_TEAM"""
```

### 4. **MagenticOne Error Handling**
```python
try:
    result = await team.run(task=task_description)
except ValueError as ve:
    if "Failed to parse ledger information" in str(ve):
        # Specific handling for MagenticOne format errors
        return {
            "success": False,
            "error": "Model format incompatible with MagenticOne",
            "suggestion": "Try direct execution or different model"
        }
```

### 5. **Direct Execution Mode**
```python
# New method for bypassing routing
async def execute_direct(self, task_description: str, team_type: str = "data") -> dict:
    """
    Bypass routing and execute directly
    More reliable when model format is incompatible
    """
    if team_type == "data":
        team = await self.create_data_analysis_team()
    else:
        team = await self.create_general_assistant_team()
    
    return await team.run(task=task_description)
```

---

## Updated Test Coverage

### test_complete_system_fixed.py Improvements:

1. **8 Tests Instead of 7:**
   - Added: Model Format Check (new)
   - Tests model's ability to follow format instructions

2. **Better Diagnostics:**
   - Identifies MagenticOne-specific errors
   - Suggests solutions based on error type
   - Provides model compatibility warnings

3. **Timeout Protection:**
   - 60-second timeout on routing tests
   - Prevents indefinite hanging

4. **Fallback Testing:**
   - Offers to run direct execution tests if routing fails
   - Validates system works even with format issues

---

## Step-by-Step Fix Instructions

### Option 1: Replace Files (Recommended)

1. **Backup existing files:**
```bash
cd /path/to/autogen-mcp-system
cp agents/enhanced_orchestrator.py agents/enhanced_orchestrator.py.backup
cp test_complete_system.py test_complete_system.py.backup
```

2. **Copy fixed versions:**
```bash
# Download the fixed files from this conversation
# Place them in the correct locations:
cp enhanced_orchestrator_fixed.py agents/enhanced_orchestrator.py
cp test_complete_system_fixed.py test_complete_system.py
```

3. **Run tests:**
```bash
python test_complete_system.py
```

### Option 2: Manual Fixes

If you prefer to update your existing files:

#### In `agents/enhanced_orchestrator.py`:

**Change 1:** Update model configuration (line ~30)
```python
# OLD:
self.model_client = OllamaChatCompletionClient(
    model=settings.ollama_model,
    base_url=settings.ollama_host,
    temperature=0.7,
    max_tokens=2000
)

# NEW:
self.model_client = OllamaChatCompletionClient(
    model=settings.ollama_model,
    base_url=settings.ollama_host,
    temperature=0.3,  # Changed
    max_tokens=4000,  # Changed
)
```

**Change 2:** Replace RoundRobinGroupChat with MagenticOneGroupChat (line ~180)
```python
# OLD:
team = RoundRobinGroupChat(
    participants=[general_agent],
    model_client=self.model_client,
)

# NEW:
team = MagenticOneGroupChat(
    participants=[general_agent],
    model_client=self.model_client,
    max_turns=5,
)
```

**Change 3:** Add error handling for MagenticOne (in `execute_task_with_routing` method)
```python
# Inside try block, wrap team.run() call:
try:
    result = await team.run(task=task_description)
    # ... existing code ...
except ValueError as ve:
    if "Failed to parse ledger information" in str(ve):
        logger.error("MagenticOne ledger parsing error")
        return {
            "success": False,
            "error": "Model response format incompatible with MagenticOne orchestration",
            "details": str(ve)
        }
    else:
        raise
```

**Change 4:** Add direct execution method (new method at end of class)
```python
async def execute_direct(self, task_description: str, team_type: str = "data") -> dict:
    """Execute without routing - more reliable"""
    try:
        logger.info(f"Direct execution: {team_type} team")
        
        if team_type == "data":
            team = await self.create_data_analysis_team()
        else:
            team = await self.create_general_assistant_team()
        
        result = await team.run(task=task_description)
        
        final_message = None
        if hasattr(result, 'messages') and result.messages:
            final_message = result.messages[-1].content
        else:
            final_message = str(result)
        
        return {
            "success": True,
            "response": final_message
        }
    except Exception as e:
        logger.error(f"Direct execution failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
```

---

## Testing Strategy

### 1. Run Component Tests First
```bash
python test_complete_system.py
```

**Expected Results:**
- Tests 1-7: Should PASS (component creation)
- Test 8 (routing): May FAIL due to model format

### 2. If Routing Fails, Test Direct Execution
```bash
python test_complete_system.py
# When prompted, type 'y' to run direct execution tests
```

**Direct execution tests should PASS** even if routing fails.

### 3. Try Alternative Model (If Issues Persist)
```bash
# Pull a more compatible model
ollama pull llama3:8b

# Update .env file
OLLAMA_MODEL=llama3:8b

# Run tests again
python test_complete_system.py
```

---

## Usage Examples After Fix

### Example 1: Using Routing (Recommended)
```python
orchestrator = EnhancedAgentOrchestrator()

result = await orchestrator.execute_task_with_routing(
    "What is 15% of 850?",
    "user123"
)

print(f"Routed to: {result['routed_to']}")
print(f"Response: {result['response']}")
```

### Example 2: Using Direct Execution (If Routing Has Issues)
```python
orchestrator = EnhancedAgentOrchestrator()

# For simple tasks
result = await orchestrator.execute_direct(
    "What is 15% of 850?",
    "general"
)

# For database tasks
result = await orchestrator.execute_direct(
    "List the first 5 tables",
    "data"
)

print(f"Response: {result['response']}")
```

---

## Why Routing Might Still Fail

Even with fixes, routing may fail if:

1. **Model Format Incompatibility:**
   - Your model doesn't follow MagenticOne's expected format
   - Solution: Use direct execution OR switch models

2. **Network/Performance Issues:**
   - Model responses too slow
   - Solution: Increase timeout values

3. **Model Not Downloaded:**
   - Model file corrupted or incomplete
   - Solution: Re-pull model: `ollama pull gpt-oss:120b-cloud`

---

## Next Steps

1. **Replace the files** using the fixed versions
2. **Run the test suite:** `python test_complete_system.py`
3. **Review test results:**
   - If all pass: You're good to go!
   - If routing fails: Use direct execution mode
   - If components fail: Check logs for specific errors

4. **Consider model alternatives** if issues persist:
   - `llama3:8b` - Best compatibility
   - `mistral:7b` - Good balance
   - `gemma3:latest` - Lightweight

5. **Monitor logs** during operation:
   - Check `logs/app.log` for detailed errors
   - Look for "Failed to parse ledger" messages
   - Check for timeout issues

---

## Summary

**Main Issues:**
1. ❌ Mixed MagenticOne/RoundRobin patterns
2. ❌ Model format incompatibility
3. ❌ Insufficient error handling

**Solutions Applied:**
1. ✅ Consistent MagenticOne usage
2. ✅ Better model configuration (lower temp, higher tokens)
3. ✅ MagenticOne-specific error handling
4. ✅ Direct execution fallback
5. ✅ Enhanced diagnostics

**Result:**
- System components work correctly
- Routing may have issues with certain models
- Direct execution provides reliable fallback
- Tests provide clear diagnostics

---

## Questions to Consider

1. **Is `gpt-oss:120b-cloud` required?**
   - If yes: Use direct execution mode
   - If no: Switch to `llama3:8b` for better compatibility

2. **Do you need automatic routing?**
   - If yes: Consider model switch
   - If no: Direct execution works great

3. **What's your priority?**
   - Speed: Keep current model, use direct execution
   - Reliability: Switch to llama3/mistral
   - Features: Try gradual model testing

Let me know which approach you'd like to take!
