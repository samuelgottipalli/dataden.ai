# OpenWebUI Integration - Complete Setup Guide
# File 4 of 5: Step-by-Step Instructions

## 🎯 Goal
Connect your existing OpenWebUI to the MCP Agent System so users can chat with agents and see the full thought process.

---

## 📋 Prerequisites Checklist

Before configuring OpenWebUI, verify:

- [x] MCP server running: `python mcp_server/main.py`
- [x] Test endpoint: `curl http://localhost:8000/api/v1/health`
- [x] Returns: `{"status":"healthy",...}`
- [x] Ollama running: `ollama ps`
- [x] Model available: `ollama list | grep 120b-cloud`
- [x] Database accessible
- [x] OpenWebUI accessible: http://localhost:3000

**If all checked ✅, proceed to configuration!**

---

## 🔧 Configuration Steps

### Step 1: Find Your Server IP

**If OpenWebUI on SAME computer as MCP server:**
```bash
# Use localhost
SERVER_URL="http://localhost:8000"
```

**If OpenWebUI on DIFFERENT computer:**
```bash
# Find server IP
# Windows:
ipconfig
# Look for: IPv4 Address

# Linux/Mac:
hostname -I
# or
ip addr show

# Example result: 192.168.1.50
SERVER_URL="http://192.168.1.50:8000"
```

**Test from OpenWebUI computer:**
```bash
curl http://YOUR_SERVER_IP:8000/api/v1/health
```

✅ If this works, you're ready to configure!

---

### Step 2: Log Into OpenWebUI

1. Open browser
2. Go to: `http://localhost:3000` (or your OpenWebUI URL)
3. Log in with your LDAP credentials
4. You should see the chat interface

---

### Step 3: Access Settings

**Option A: Admin Settings (if you're admin)**
```
Profile Icon (top right) → Admin Settings → Connections
```

**Option B: User Settings**
```
Profile Icon (top right) → Settings → Connections
```

**Option C: Direct URL**
```
http://localhost:3000/settings/connections
```

---

### Step 4: Add External Connection

Look for one of these buttons:
- **"+ Add Connection"**
- **"Add External API"**
- **"Add Custom Model"**
- **"Add OpenAI Compatible API"**

Click it!

---

### Step 5: Fill In Connection Form

```
┌────────────────────────────────────────────────────────┐
│  Add External Connection                               │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Name/Title: *                                         │
│  ┌────────────────────────────────────────────────┐   │
│  │ Autogen MCP Agents                            │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  API Type: *                                           │
│  ⦿ OpenAI Compatible                                   │
│  ○ Custom                                              │
│                                                         │
│  Base URL: *                                           │
│  ┌────────────────────────────────────────────────┐   │
│  │ http://YOUR_IP:8000/api/v1                    │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  API Key: *                                            │
│  ┌────────────────────────────────────────────────┐   │
│  │ your-api-key-from-env-file                    │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  Options:                                              │
│  ☑ Enable Streaming                                   │
│  ☑ Show in Model Selector                             │
│  ☐ Set as Default Model                               │
│                                                         │
│  Model Identifier:                                     │
│  ┌────────────────────────────────────────────────┐   │
│  │ autogen-agents                                │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
│  [Test Connection]  [Cancel]  [Save]                  │
└────────────────────────────────────────────────────────┘
```

**CRITICAL VALUES:**
- **Base URL:** `http://YOUR_SERVER_IP:8000/api/v1` (no trailing slash!)
- **API Key:** Copy from your `.env` file (`OPENWEBUI_API_KEY=...`)
- **Enable Streaming:** ✅ MUST be checked (for agent visibility)
- **Model Identifier:** `autogen-agents` (exact match)

---

### Step 6: Test Connection

1. Click **"Test Connection"** button
2. Wait 2-5 seconds

**Expected Results:**

✅ **Success:**
```
✓ Connection successful
✓ Model detected: autogen-agents
```

❌ **Failure:**
```
✗ Connection failed: [error message]
```

**If failed, see Troubleshooting section below**

---

### Step 7: Save Configuration

1. Click **"Save"** button
2. You should see success message
3. Connection appears in your list

---

### Step 8: Select Model in Chat

1. Go back to main chat interface
2. Look for **model selector** (usually top of page or sidebar)
3. Click model selector dropdown
4. Look for **"Autogen MCP Agents"** or **"autogen-agents"**
5. Click to select it

**Should see:** ✓ Selected: Autogen MCP Agents

---

### Step 9: Test Chat!

**Test 1: Simple Math**
```
You: What is 15% of 850?
```

**Expected:**
```
🎯 SupervisorAgent
Routing to: GENERAL_ASSISTANT_TEAM

🤖 GeneralAssistant [Thinking]
I'll calculate 15% of 850

⚡ GeneralAssistant [Action]
calculate_math("15% of 850")

📦 Tool Result
{"result": 127.5}

✅ Final Answer
15% of 850 is 127.5
```

✅ **If you see this formatted output with agent names and steps, IT WORKS!**

**Test 2: Database Query**
```
You: List the first 3 tables in the database
```

**Expected:**
```
🎯 SupervisorAgent
Routing to: DATA_ANALYSIS_TEAM

🤖 SQLAgent [Thinking]
I'll query the database schema

⚡ SQLAgent [Action]
list_all_tables()

📦 Tool Result
[Shows table names]

✅ Final Answer
Here are the first 3 tables:
1. [Table 1]
2. [Table 2]
3. [Table 3]
```

---

## 🎉 Success Criteria

You've successfully integrated when:

1. ✅ Model appears in OpenWebUI selector
2. ✅ Can send messages
3. ✅ See agent names (SupervisorAgent, SQLAgent, etc.)
4. ✅ See agent types ([Thinking], [Action], etc.)
5. ✅ See tool calls and results
6. ✅ Messages stream in real-time (not all at once)
7. ✅ Database queries work
8. ✅ Math calculations work
9. ✅ No errors in browser console (F12)

**If all ✅, you're done! Multiple users can now use the system!** 🎊

---

## ⚠️ Troubleshooting

### Issue 1: "Test Connection" Fails

**Error:** "Connection failed" or "Network error"

**Fixes:**
```bash
# Check 1: Is MCP server running?
curl http://localhost:8000/api/v1/health

# Check 2: Can OpenWebUI reach it?
# From OpenWebUI machine:
curl http://YOUR_SERVER_IP:8000/api/v1/health

# Check 3: Firewall blocking?
# Windows:
netsh advfirewall firewall add rule name="MCP" dir=in action=allow protocol=TCP localport=8000

# Linux:
sudo ufw allow 8000/tcp

# Check 4: URL format correct?
# Good: http://192.168.1.50:8000/api/v1
# Bad:  http://192.168.1.50:8000/api/v1/
# Bad:  http://192.168.1.50:8000/
```

---

### Issue 2: "Invalid API Key"

**Error:** "401 Unauthorized" or "Invalid API key"

**Fixes:**
```bash
# Check 1: API key matches?
cat .env | grep OPENWEBUI_API_KEY

# Check 2: Copy exact value (no quotes, no spaces)
# Good: OPENWEBUI_API_KEY=abc123xyz789
# Bad:  OPENWEBUI_API_KEY="abc123xyz789"
# Bad:  OPENWEBUI_API_KEY= abc123xyz789

# Check 3: Restart MCP server after .env changes
# Kill server (Ctrl+C)
python mcp_server/main.py
```

---

### Issue 3: Model Doesn't Appear in Selector

**Symptoms:** Connection saves but no model visible

**Fixes:**
```
1. Refresh OpenWebUI page (F5)
2. Log out and log back in
3. Clear browser cache
4. Check "Show in Model Selector" is enabled
5. Try different browser
6. Check OpenWebUI logs for errors
```

---

### Issue 4: No Streaming / All At Once

**Symptoms:** Entire response appears at once, no agent steps

**Fixes:**
```
1. Verify "Enable Streaming" is checked ✅
2. Check browser console (F12) for errors
3. Test streaming with curl:
   curl -X POST http://localhost:8000/api/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-key" \
     -d '{"model":"autogen-agents","messages":[{"role":"user","content":"Hi"}],"stream":true}'

4. Try different OpenWebUI version
5. Check network (streaming needs stable connection)
```

---

### Issue 5: CORS Errors

**Symptoms:** Browser console shows "CORS policy" errors

**Fixes:**
```python
# In mcp_server/main.py, update CORS:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://YOUR_OPENWEBUI_URL",  # ← Add this
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Then restart MCP server
```

---

### Issue 6: Responses Timeout

**Symptoms:** "Request timeout" or loading forever

**Fixes:**
```bash
# Check 1: Ollama responding?
ollama ps

# Check 2: Model loaded?
ollama list | grep 120b-cloud

# Check 3: Database accessible?
curl http://localhost:8000/api/v1/health

# Check 4: MCP server logs
tail -f logs/app.log

# Look for errors or warnings
```

---

## 📊 Testing Matrix

| Test | Command | Expected Result |
|------|---------|----------------|
| Health | `curl .../health` | `{"status":"healthy"}` |
| Models | `curl .../models` | `{"data":[{"id":"autogen-agents"}]}` |
| Simple Math | "What is 10+5?" | Shows agent steps, returns 15 |
| Database | "List tables" | Shows SQL query, returns tables |
| Error Handling | "DROP TABLE" | ValidationAgent blocks it |
| Streaming | Any query | See steps in real-time |
| Multi-user | 2+ users chat | Both work simultaneously |

---

## 🔒 Security Notes

**For Testing/Development:**
- ✅ Current setup is fine on trusted network
- ✅ API key provides basic authentication
- ✅ LDAP handles user authentication in OpenWebUI

**For Production:**
- [ ] Enable HTTPS (use reverse proxy)
- [ ] Restrict CORS to specific OpenWebUI domain
- [ ] Add rate limiting
- [ ] Use firewall rules
- [ ] Set up monitoring/alerting
- [ ] Regular security audits

---

## 📁 File Locations Reference

```
autogen-mcp-system/
├── .env                          ← API key here
├── mcp_server/
│   ├── main.py                   ← CORS config here
│   └── api_routes.py             ← Endpoints here
├── agents/
│   └── enhanced_orchestrator.py  ← Streaming here
└── config/
    └── openwebui_config.py       ← Settings (optional)
```

---

## ✅ Final Checklist

Before marking as complete:

- [ ] MCP server running on network (0.0.0.0)
- [ ] Health endpoint accessible from OpenWebUI machine
- [ ] API key set in .env
- [ ] Connection configured in OpenWebUI
- [ ] Test connection passes ✅
- [ ] Model appears in selector
- [ ] Simple math test works
- [ ] Database query test works
- [ ] Agent steps visible
- [ ] Streaming works
- [ ] No CORS errors
- [ ] Multiple users tested (if applicable)

**All checked? You're DONE! 🎉**

---

## 🎯 What's Next

Now that OpenWebUI is connected:

1. ✅ Train users on how to use it
2. ✅ Share documentation (File 5)
3. ✅ Monitor usage and performance
4. ✅ Gather feedback
5. ✅ Add more teams (Web Research, Calendar) as needed
6. ✅ Consider production deployment (Docker, HTTPS, etc.)

---

**Progress: 80% complete** 📊

**One more file to go: File 5 - Complete Setup Documentation!**
