# ============================================================
# OPENWEBUI CONFIGURATION
# File 4 of 5: Configuration settings for OpenWebUI integration
# ============================================================

"""
This file contains the settings needed to configure OpenWebUI
to connect to your MCP Agent System.
"""

# ============================================================
# FILE: config/openwebui_config.py (NEW FILE)
# ============================================================

from pydantic_settings import BaseSettings
from typing import List

class OpenWebUISettings(BaseSettings):
    """
    Configuration for OpenWebUI integration
    """
    
    # MCP Server Connection
    mcp_server_url: str = "http://localhost:8000"  # Change to your server IP
    mcp_api_key: str = ""  # Same as OPENWEBUI_API_KEY in .env
    
    # OpenWebUI Details
    openwebui_url: str = "http://localhost:3000"  # Your OpenWebUI URL
    
    # Display Settings
    show_agent_names: bool = True  # Show which agent is responding
    show_tool_calls: bool = True   # Show when tools are called
    show_thinking: bool = True     # Show agent thinking process
    
    # Performance Settings
    stream_chunk_size: int = 100   # Characters per chunk
    stream_delay_ms: int = 10      # Delay between chunks (milliseconds)
    max_retries: int = 3           # Retry failed requests
    timeout_seconds: int = 300     # 5 minute timeout
    
    class Config:
        env_file = ".env"
        env_prefix = "OPENWEBUI_"


# ============================================================
# OPENWEBUI CONNECTION DETAILS (For Manual Configuration)
# ============================================================

"""
USE THESE SETTINGS IN OPENWEBUI:

1. Log into your OpenWebUI instance
2. Go to: Settings → Admin Settings → Connections
3. Click: "Add External Connection" or "Add Custom API"
4. Fill in these details:

CONNECTION SETTINGS:
--------------------
Name: Autogen MCP Agents
Type: OpenAI API (or Custom API)
Base URL: http://YOUR_SERVER_IP:8000/api/v1
API Key: [Your OPENWEBUI_API_KEY from .env]

ADVANCED SETTINGS:
------------------
☑ Enable Streaming
☑ Show in Model Selector
Model Name: autogen-agents
Temperature: 0.3
Max Tokens: 4000

HEADERS (if available):
-----------------------
X-API-Key: [Your OPENWEBUI_API_KEY]

IMPORTANT:
- Replace YOUR_SERVER_IP with your actual server IP address
- If OpenWebUI is on same machine: use localhost or 127.0.0.1
- If OpenWebUI is on different machine: use server's network IP
"""


# ============================================================
# STEP-BY-STEP OPENWEBUI CONFIGURATION
# ============================================================

CONFIGURATION_STEPS = """
STEP 1: ACCESS OPENWEBUI SETTINGS
==================================
1. Open OpenWebUI in browser: http://localhost:3000
2. Log in with your LDAP credentials
3. Click your profile icon (top right)
4. Select "Settings"

STEP 2: NAVIGATE TO CONNECTIONS
================================
1. In Settings menu, look for:
   - "Admin Settings" (if admin)
   - "Connections" 
   - "External APIs"
   - "Models" → "Add Model"
   
2. Click "Add Connection" or "Add External API"

STEP 3: CONFIGURE CONNECTION
=============================
Fill in the form:

┌─────────────────────────────────────────┐
│ Add External Connection                 │
├─────────────────────────────────────────┤
│ Name: Autogen MCP Agents               │
│                                         │
│ Type: ⦿ OpenAI API                     │
│       ○ Custom API                      │
│                                         │
│ Base URL:                               │
│ http://YOUR_IP:8000/api/v1            │
│                                         │
│ API Key:                                │
│ your-api-key-here                      │
│                                         │
│ ☑ Enable Streaming                     │
│ ☑ Show in Model Selector               │
│                                         │
│ Model ID: autogen-agents               │
│                                         │
│ [Test Connection]  [Save]              │
└─────────────────────────────────────────┘

STEP 4: TEST CONNECTION
========================
1. Click "Test Connection" button
2. Should see: ✅ "Connection successful"
3. Click "Save"

STEP 5: SELECT MODEL IN CHAT
=============================
1. Go back to main chat interface
2. Click model selector (usually top of page)
3. Look for "Autogen MCP Agents" or "autogen-agents"
4. Select it
5. Start chatting!

STEP 6: VERIFY STREAMING
=========================
Send a test message: "What is 15% of 850?"

You should see:
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
"""


# ============================================================
# TROUBLESHOOTING GUIDE
# ============================================================

TROUBLESHOOTING = """
ISSUE 1: "Connection failed" error
===================================
Symptoms: Red error message, can't save connection

Fixes:
□ Check MCP server is running: curl http://YOUR_IP:8000/api/v1/health
□ Check firewall allows port 8000
□ Try from server: curl http://localhost:8000/api/v1/health
□ Check API key matches .env file
□ Check Base URL format: http://IP:8000/api/v1 (no trailing slash)

ISSUE 2: Connection saves but model doesn't appear
===================================================
Symptoms: Connection works, but no model in selector

Fixes:
□ Check "Show in Model Selector" is enabled
□ Refresh OpenWebUI page
□ Log out and log back in
□ Check OpenWebUI logs for errors
□ Verify model ID: curl http://YOUR_IP:8000/api/v1/models

ISSUE 3: Model selected but responses don't stream
===================================================
Symptoms: Messages appear all at once, no agent visibility

Fixes:
□ Check "Enable Streaming" is checked
□ Check browser console for errors (F12)
□ Verify streaming works: curl test from FILE_3_SETUP.md
□ Try different browser
□ Check OpenWebUI version (needs streaming support)

ISSUE 4: CORS errors in browser console
========================================
Symptoms: Red CORS errors, requests blocked

Fixes:
□ Add OpenWebUI URL to CORS in mcp_server/main.py:
  allow_origins=["http://YOUR_OPENWEBUI_URL"]
□ Restart MCP server
□ Clear browser cache
□ Check OpenWebUI and MCP on same domain/protocol

ISSUE 5: Responses timeout
===========================
Symptoms: Loading forever, then timeout error

Fixes:
□ Increase timeout in OpenWebUI settings (if available)
□ Check Ollama is responding: ollama ps
□ Check MCP server logs: tail -f logs/app.log
□ Try simpler query first
□ Check database connection

ISSUE 6: Authentication fails
==============================
Symptoms: 401 Unauthorized errors

Fixes:
□ Verify API key in OpenWebUI matches .env
□ Check API key in request headers
□ Verify OPENWEBUI_API_KEY in .env is set
□ Restart MCP server after changing .env
"""


# ============================================================
# NETWORK CONFIGURATION EXAMPLES
# ============================================================

NETWORK_EXAMPLES = """
SCENARIO 1: Everything on Same Machine
=======================================
OpenWebUI: http://localhost:3000
MCP Server: http://localhost:8000

OpenWebUI Configuration:
Base URL: http://localhost:8000/api/v1
✓ Works immediately
✓ No firewall needed
✓ Fastest performance

SCENARIO 2: OpenWebUI on Different Machine (Same Network)
==========================================================
OpenWebUI: Computer A (192.168.1.100)
MCP Server: Computer B (192.168.1.50)

OpenWebUI Configuration:
Base URL: http://192.168.1.50:8000/api/v1

Requirements:
□ Firewall on Computer B allows port 8000
□ Both on same network
□ MCP server using host="0.0.0.0"

Test: From Computer A, run:
curl http://192.168.1.50:8000/api/v1/health

SCENARIO 3: OpenWebUI Publicly Accessible
==========================================
OpenWebUI: https://openwebui.yourcompany.com
MCP Server: Internal server (10.0.0.50)

Option A - VPN:
- Users connect via VPN
- Access internal MCP server
- OpenWebUI uses: http://10.0.0.50:8000/api/v1

Option B - Reverse Proxy:
- Expose MCP through same domain
- OpenWebUI uses: https://openwebui.yourcompany.com/api/mcp/v1
- Nginx/Caddy proxies to internal MCP server

SCENARIO 4: Docker Containers
==============================
OpenWebUI: Docker container
MCP Server: Docker container or host

If both in Docker:
- Use Docker network
- MCP URL: http://mcp-server:8000/api/v1

If MCP on host:
- MCP URL: http://host.docker.internal:8000/api/v1 (Mac/Windows)
- MCP URL: http://172.17.0.1:8000/api/v1 (Linux)
"""


# ============================================================
# TESTING CHECKLIST
# ============================================================

TESTING_CHECKLIST = """
PRE-CONFIGURATION TESTS
=======================
□ MCP server running: python mcp_server/main.py
□ Health endpoint works: curl http://localhost:8000/api/v1/health
□ Models endpoint works: curl http://localhost:8000/api/v1/models
□ Streaming test works (from FILE_3_SETUP.md)
□ Ollama running: ollama ps
□ Database accessible

POST-CONFIGURATION TESTS
========================
□ Connection test passes in OpenWebUI
□ Model appears in selector
□ Can send simple message: "Hello"
□ Can see agent responses streaming
□ Math works: "What is 25% of 400?"
□ Database works: "List first 3 tables"
□ Tool calls visible in chat
□ No CORS errors in browser console
□ Multiple users can connect simultaneously

EDGE CASE TESTS
===============
□ Long queries (>500 characters)
□ Complex SQL queries
□ Queries that take >30 seconds
□ Error handling (invalid queries)
□ Concurrent requests (multiple users)
□ Network interruption recovery
"""


# ============================================================
# EXAMPLE .ENV CONFIGURATION
# ============================================================

EXAMPLE_ENV = """
# Add these to your .env file if not already present:

# OpenWebUI Integration
OPENWEBUI_API_KEY=your-secret-key-change-this-abc123
OPENWEBUI_URL=http://localhost:3000

# MCP Server (make sure these are set)
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_HOST=http://localhost:11434

# Database (make sure these are set)
DB_SERVER=your-server.com
DB_PORT=1433
DB_NAME=AdventureWorksDW2022
DB_USER=your-username
DB_PASSWORD=your-password

# LDAP (make sure these are set)
LDAP_SERVER=ldap.yourcompany.com
LDAP_PORT=389
LDAP_USE_SSL=false
LDAP_BASE_DN=DC=yourcompany,DC=com
LDAP_SERVICE_ACCOUNT_USER=service_account@yourcompany.com
LDAP_SERVICE_ACCOUNT_PASSWORD=service-password
"""


# ============================================================
# USAGE INSTRUCTIONS
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("OPENWEBUI CONFIGURATION GUIDE")
    print("="*60)
    print()
    print("Follow these steps to configure OpenWebUI:")
    print()
    print(CONFIGURATION_STEPS)
    print()
    print("="*60)
    print("NETWORK CONFIGURATION EXAMPLES")
    print("="*60)
    print()
    print(NETWORK_EXAMPLES)
    print()
    print("="*60)
    print("TROUBLESHOOTING")
    print("="*60)
    print()
    print(TROUBLESHOOTING)
    print()
    print("="*60)
    print("TESTING CHECKLIST")
    print("="*60)
    print()
    print(TESTING_CHECKLIST)
