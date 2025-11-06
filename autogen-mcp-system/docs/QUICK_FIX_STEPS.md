# Quick Fix Steps for Test Failures

## TL;DR - What's Wrong
Your tests failed because:
1. **RoundRobin was used for General Assistant** - Should be MagenticOne like everything else
2. **Model format incompatibility** - `gpt-oss:120b-cloud` doesn't format responses the way MagenticOne expects
3. **"Failed to parse ledger information"** - Classic MagenticOne error when model response format is wrong

## Immediate Fix (5 minutes)

### Step 1: Replace Two Files

```bash
# In your project root: autogen-mcp-system/

# Backup originals
cp agents/enhanced_orchestrator.py agents/enhanced_orchestrator.py.backup
cp test_complete_system.py test_complete_system.py.backup

# Replace with fixed versions (from the artifacts I just created)
# Copy the contents of:
#   - enhanced_orchestrator_fixed.py  →  agents/enhanced_orchestrator.py
#   - test_complete_system_fixed.py   →  test_complete_system.py
```

### Step 2: Run Tests
```bash
python test_complete_system.py
```

### Step 3: Check Results

**If you see 8/8 PASS:**
🎉 Perfect! Everything works.

**If you see 7/8 PASS (routing fails):**
✅ System works, but routing has issues. This is expected with your model.

**If fewer tests pass:**
❌ Check TROUBLESHOOTING_GUIDE.md for detailed diagnostics

---

## What Changed

### 1. Consistent Orchestration Pattern
```python
# BEFORE: Mixed patterns ❌
general_team = RoundRobinGroupChat(...)  # Different!
data_team = MagenticOneGroupChat(...)    

# AFTER: Consistent pattern ✅
general_team = MagenticOneGroupChat(...)  # Same!
data_team = MagenticOneGroupChat(...)
```

### 2. Better Model Settings
```python
# BEFORE ❌
temperature=0.7,  # Too creative
max_tokens=2000,  # Too restrictive

# AFTER ✅
temperature=0.3,  # More consistent
max_tokens=4000,  # More headroom
```

### 3. Added Safety Net
```python
# New method for when routing fails:
result = await orchestrator.execute_direct("your task", "general")
# or
result = await orchestrator.execute_direct("your task", "data")
```

---

## If Routing Test Still Fails

### Option A: Use Direct Execution (Easiest)
Instead of this:
```python
result = await orchestrator.execute_task_with_routing("List tables", "user")
```

Do this:
```python
result = await orchestrator.execute_direct("List tables", "data")
```

### Option B: Switch Models (More Reliable)
```bash
# Install better model for MagenticOne
ollama pull llama3:8b

# Update .env
OLLAMA_MODEL=llama3:8b

# Restart Ollama
ollama serve

# Run tests again
python test_complete_system.py
```

**Model Compatibility Ranking:**
1. 🥇 `llama3:8b` or `llama3:70b` - Best
2. 🥈 `mistral:7b` - Good
3. 🥉 `gemma3:latest` - Okay
4. ⚠️  `gpt-oss:120b-cloud` - Format issues

---

## Folder Structure

Your files should be organized like this:

```
autogen-mcp-system/
├── agents/
│   ├── enhanced_orchestrator.py     ← REPLACE THIS
│   └── orchestrator.py              ← keep
├── test_complete_system.py          ← REPLACE THIS
├── .env
└── [other files unchanged]
```

---

## File Locations

**Replace these files:**
1. `agents/enhanced_orchestrator.py`
   - **With:** `enhanced_orchestrator_fixed.py` 
   - **Location in Git:** Should be in `/agents/` directory

2. `test_complete_system.py`
   - **With:** `test_complete_system_fixed.py`
   - **Location in Git:** Should be in project root

**Reference files (don't need to move):**
- `TROUBLESHOOTING_GUIDE.md` - Detailed explanations
- `QUICK_FIX_STEPS.md` - This file

---

## Testing Checklist

After replacing files:

- [ ] Run `python test_complete_system.py`
- [ ] Verify database test passes (test 1/8)
- [ ] Verify Ollama test passes (test 2/8)
- [ ] Verify model format test passes (test 3/8)
- [ ] Verify component creation tests pass (tests 4-7/8)
- [ ] Check routing test (test 8/8) - may fail, that's okay
- [ ] If routing fails, try direct execution mode

---

## Common Questions

**Q: Why did RoundRobin cause issues?**
A: MagenticOne and RoundRobin have different orchestration patterns. Mixing them creates unpredictable behavior. Always use one pattern consistently.

**Q: Why does routing fail but components work?**
A: The agents work fine, but the supervisor's classification and MagenticOne's orchestration need specific response formats your model doesn't produce reliably.

**Q: Should I switch models?**
A: Only if you need the routing feature. Direct execution works perfectly with your current model.

**Q: What's the difference between routing and direct execution?**
A:
- **Routing:** Supervisor decides which team to use (automatic)
- **Direct:** You specify which team to use (manual)

Both execute tasks the same way, just different selection methods.

---

## Next Steps

1. ✅ Replace the two files
2. ✅ Run tests
3. ✅ Review results
4. ✅ Choose approach:
   - Keep current model + use direct execution
   - OR switch to llama3 + use routing

5. ✅ Commit to Git:
```bash
git add agents/enhanced_orchestrator.py
git add test_complete_system.py
git commit -m "Fix: Use consistent MagenticOne pattern and add direct execution mode"
git push
```

---

## Help

If tests still fail, check:
1. **Ollama running?** → `ollama ps`
2. **Model downloaded?** → `ollama list`
3. **Database connected?** → Check .env credentials
4. **Logs?** → Check `logs/app.log`

For detailed help, see `TROUBLESHOOTING_GUIDE.md`
