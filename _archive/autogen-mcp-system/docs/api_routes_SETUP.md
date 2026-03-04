# File 1 Setup Instructions

## 📁 File Location
**Save as:** `mcp_server/api_routes.py`

## ⚙️ Configuration Needed

### Step 1: Add to .env
```bash
# Add this line to your .env file:
OPENWEBUI_API_KEY=your-secret-key-here-change-this-to-something-random
```

**Generate a secure key:**
```bash
# On Linux/Mac:
openssl rand -hex 32

# On Windows (PowerShell):
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})

# Or just use a random string like:
# OPENWEBUI_API_KEY=autogen-mcp-2024-secure-key-abc123xyz789
```

### Step 2: Update config/settings.py
```python
# Add this line to the Settings class (around line 30):

class Settings(BaseSettings):
    # ... existing settings ...
    
    # OpenWebUI Integration (NEW)
    openwebui_api_key: str = ""  # Add this line
    
    # ... rest of settings ...
```

## 🧪 Testing

### Test 1: Check file is in correct location
```bash
ls mcp_server/api_routes.py
# Should show: mcp_server/api_routes.py
```

### Test 2: Check Python syntax
```bash
python -m py_compile mcp_server/api_routes.py
# No output = success
```

### Test 3: Check imports work
```bash
python -c "from mcp_server.api_routes import router; print('✓ Imports work!')"
# Should print: ✓ Imports work!
```

## ⚠️ Expected Status After This File

**What works:**
- ✅ File created
- ✅ API key configured
- ✅ Settings updated

**What doesn't work yet:**
- ❌ Can't start server (need File 2 next)
- ❌ Streaming not implemented (need File 2 next)
- ❌ OpenWebUI can't connect (need all 5 files)

## 🎯 When Ready

After you've:
1. ✅ Saved the file to `mcp_server/api_routes.py`
2. ✅ Added `OPENWEBUI_API_KEY` to `.env`
3. ✅ Updated `config/settings.py`
4. ✅ Run the 3 tests above

**Tell me:** "Ready for File 2"

And I'll give you the orchestrator streaming update!

## 🆘 Troubleshooting

**Error: ModuleNotFoundError: No module named 'mcp_server.api_routes'**
- Check file is at: `mcp_server/api_routes.py` (not in wrong folder)
- Check `mcp_server/__init__.py` exists

**Error: ImportError: cannot import name 'router'**
- Check the file saved correctly
- Check no syntax errors in file

**Error: 'Settings' object has no attribute 'openwebui_api_key'**
- You forgot Step 2 - update `config/settings.py`

## 📝 What This File Does

This file creates:
1. **`/api/v1/chat/completions`** - Main endpoint OpenWebUI calls
2. **`/api/v1/models`** - Lists available models
3. **`/api/v1/health`** - Health check

Features:
- ✅ OpenAI-compatible API format
- ✅ Streaming support (for agent visibility)
- ✅ API key authentication
- ✅ User context extraction from headers
- ✅ Formatted agent messages (emojis for readability)

## 🎨 What Users Will See (Preview)

```
User: Show me top 5 sales

🎯 SupervisorAgent
Routing to: DATA_ANALYSIS_TEAM

🤔 SQLAgent [Thinking]
I need to query the sales table

⚡ SQLAgent [Action]
SELECT TOP 5 * FROM sales ORDER BY amount DESC

🛡️ ValidationAgent [Validation]
✓ Query is safe
Approved for execution

📦 Tool Result
5 rows returned

📊 AnalysisAgent [Analysis]
Top sale: $45,230 from Customer A

✅ Final Answer
Here are the top 5 sales...
```

---

**Current Progress: 1 of 5 files complete (20%)**
