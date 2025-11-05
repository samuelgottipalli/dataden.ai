# MCP Agent System - Quick Start Implementation Guide

## Overview
A production-ready proof-of-concept system that uses:
- **MCP Server**: FastAPI-based Model Context Protocol server
- **AutoGen 2**: Multi-agent orchestration with Ollama
- **MS SQL Server**: Enterprise data warehouse (100GB+)
- **Ollama**: Local LLM (Gemma, Llama, Mistral, etc.)
- **LDAP**: Enterprise authentication
- **Retry Logic**: Automatic fault tolerance with human escalation

---

## IMPLEMENTATION CHECKLIST

### ✅ Phase 1: Environment Setup (15 minutes)

- [ ] Create project directory: `mkdir autogen-mcp-system && cd autogen-mcp-system`
- [ ] Create venv: `python -m venv venv`
- [ ] Activate venv (see setup guide artifact)
- [ ] Create `requirements.txt` (from setup guide artifact)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create `.env` file from `.env.example` (see setup guide)
- [ ] Install MS SQL ODBC driver (see setup guide for OS-specific instructions)

### ✅ Phase 2: File Structure (5 minutes)

Create these directories:
```
autogen-mcp-system/
├── config/
├── mcp_server/
├── agents/
├── utils/
├── logs/
└── tests/
```

Create `__init__.py` in each directory:
```bash
touch config/__init__.py mcp_server/__init__.py agents/__init__.py utils/__init__.py
```

### ✅ Phase 3: Configuration Files (10 minutes)

1. Create `config/settings.py` (from core implementation artifact)
2. Create `config/ldap_config.py` (from core implementation artifact)
3. Create `.env` with your values:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

### ✅ Phase 4: Core Implementation (20 minutes)

Copy these files from the core implementation artifact:

1. `mcp_server/database.py` - MS SQL connections
2. `mcp_server/auth.py` - LDAP authentication
3. `mcp_server/tools.py` - MCP tool definitions
4. `mcp_server/main.py` - FastAPI server
5. `utils/logging_config.py` - Logging setup
6. `utils/retry_handler.py` - Retry logic
7. `agents/orchestrator.py` - Agent setup (from orchestration artifact)
8. `run_mcp_server.py` - MCP server entry point
9. `run_agents.py` - Agent execution entry point

### ✅ Phase 5: Testing & Validation (15 minutes)

```bash
# Test MS SQL connection
python test_mssql_connection.py

# Test LDAP connection
python test_ldap_connection.py

# Test Ollama
ollama run gemma "Say hello in one sentence"
```

### ✅ Phase 6: Start Services (10 minutes)

**Terminal 1 - Start Ollama:**
```bash
ollama serve
```

**Terminal 2 - Pull your model:**
```bash
ollama pull gemma
```

**Terminal 3 - Start MCP Server:**
```bash
python run_mcp_server.py
```

You should see:
```
2024-10-18 14:30:45 | INFO     | Starting MCP Server on 127.0.0.1:8000
✓ MS SQL Server connection established
```

**Terminal 4 - Run agents (POC):**
```bash
python run_agents.py
```

---

## ARCHITECTURE FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                              │
│         (LDAP authenticated via OpenWebUI or API)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              AGENT ORCHESTRATOR (AutoGen 2)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Magentic Team: SQLAgent + AnalysisAgent + Validation   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────┬──────────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌─────────┐ ┌──────────┐ ┌────────────┐
    │  SQL    │ │ Analysis │ │ Validation │
    │ Tool    │ │   Tool   │ │   Agent    │
    └────┬────┘ └────┬─────┘ └────────────┘
         │           │
         │           └─────────────────┐
         ▼                             ▼
    ┌─────────────────────────────────────┐
    │    MCP SERVER (FastAPI)             │
    │  - Retry Handler                    │
    │  - LDAP Auth                        │
    │  - Query Validation                 │
    └────────┬────────────────────────────┘
              │
         ┌────┴─────────────────┐
         ▼                      ▼
    ┌─────────────┐     ┌──────────────┐
    │  MS SQL DB  │     │ Ollama LLM   │
    │  (100GB+)   │     │  (Gemma)     │
    └─────────────┘     └──────────────┘
```

---

## KEY WORKFLOWS

### Workflow 1: Data Query & Analysis

```
1. User: "Show Q4 sales by region"
   ↓
2. SQLAgent: Generates → "SELECT region, SUM(amount)... WHERE date >= 2024-10-01"
   ↓
3. Retry Handler: Executes query (max 3 attempts)
   ↓
4. AnalysisAgent: Processes results → Calculates trends, identifies top regions
   ↓
5. ValidationAgent: Reviews findings → Checks logic, approves
   ↓
6. Result: "Sales by Region: North $X, South $Y..." with analysis
```

### Workflow 2: Query Failure & Escalation

```
1. SQLAgent: Creates query
   ↓
2. Attempt 1: FAILS (connection timeout)
   ↓
3. Attempt 2: FAILS (syntax error in generated SQL)
   ↓
4. Attempt 3: FAILS (timeout again)
   ↓
5. Escalation: Alert sent to team_lead@company.com
   Status: "Query failed after 3 attempts. Manual review required."
```

### Workflow 3: Data Security

```
1. User submits: "DROP TABLE sales"
   ↓
2. SQL Validation: Detects dangerous keyword
   ↓
3. Result: "Query contains dangerous operation: DROP"
   ✗ Query blocked, not attempted
```

---

## CONFIGURATION DETAILS

### Ollama Model Selection

Choose based on your needs:

| Model | Size | Speed | Quality | VRAM |
|-------|------|-------|---------|------|
| gemma | 2.5GB | Fast | Good | 4GB |
| mistral | 4GB | Fast | Good | 8GB |
| llama2 | 7GB | Medium | Excellent | 16GB |
| neural-chat | 6GB | Fast | Good | 12GB |

Install: `ollama pull gemma` (replace with your choice)

### LDAP Configuration Examples

**Active Directory (Windows):**
```
LDAP_SERVER=ldap://ad.yourcompany.local
LDAP_PORT=389
LDAP_BASE_DN=dc=yourcompany,dc=local
LDAP_DOMAIN=yourcompany.local
```

**OpenLDAP (Linux):**
```
LDAP_SERVER=ldap://ldap.company.com
LDAP_PORT=389
LDAP_BASE_DN=ou=people,dc=company,dc=com
LDAP_DOMAIN=company.com
```

**LDAP with SSL:**
```
LDAP_SERVER=ldaps://ldap.company.com
LDAP_PORT=636
LDAP_USE_SSL=true
```

---

## RUNNING IN DIFFERENT SCENARIOS

### Scenario 1: Proof of Concept (Local Development)
```bash
# Terminal 1
ollama serve

# Terminal 2
python run_mcp_server.py

# Terminal 3
python run_agents.py
```

### Scenario 2: API Server (Continuous)
```bash
# Terminal 1
ollama serve

# Terminal 2
python run_mcp_server.py

# Terminal 3
python run_agents_api.py
```

Then make HTTP requests:
```bash
curl -X POST http://localhost:8001/execute-task \
  -H "Content-Type: application/json" \
  -u username:password \
  -d '{"task_description": "Show total sales this month"}'
```

### Scenario 3: Integration with OpenWebUI

OpenWebUI can call the Agent Execution API:
1. Set MCP Server URL: `http://localhost:8000`
2. Configure tools in OpenWebUI
3. Users interact via OpenWebUI chat interface

---

## TROUBLESHOOTING

### Issue: "Connection timeout to Ollama"
**Solution:**
```bash
# Check Ollama is running
ollama serve

# Check connectivity
curl http://localhost:11434/api/tags

# Verify model is installed
ollama pull gemma
```

### Issue: "MS SQL connection failed"
**Solution:**
```bash
# Run connection test
python test_mssql_connection.py

# Check ODBC driver
# Windows: ODBC Data Source Administrator
# Linux/Mac: 
isql -v <DSN>

# Verify credentials in .env
```

### Issue: "LDAP authentication failed"
**Solution:**
```bash
# Run LDAP test
python test_ldap_connection.py

# Verify LDAP_SERVER is accessible
ping ad.yourcompany.com

# Check credentials
ldapsearch -x -H ldap://server -D "user@domain" -W
```

### Issue: "Agent hangs or times out"
**Solution:**
```python
# In run_agents.py, increase timeout:
result = await asyncio.wait_for(
    orchestrator.execute_task(...),
    timeout=600  # Increase from 300
)
```

### Issue: "Query retry exhausted too quickly"
**Solution:**
```
# Increase retry attempts in .env
AGENT_RETRY_ATTEMPTS=5

# Or increase timeouts on individual queries
cursor = conn.cursor()
cursor.timeout = 60  # seconds
```

---

## MONITORING & LOGGING

### View Logs
```bash
# Real-time logs
tail -f logs/app.log

# Search for errors
grep ERROR logs/app.log

# Search by user
grep "username" logs/app.log

# Count query executions
grep "Executing query" logs/app.log | wc -l
```

### Health Checks
```bash
# MCP Server health
curl http://localhost:8000/health

# Database connection
curl http://localhost:8000/health/db

# Verify authentication
curl -u testuser:testpass http://localhost:8000/auth/verify
```

---

## NEXT STEPS FOR PRODUCTION

1. **Database**: Use connection pooling (SQLAlchemy connection pools)
2. **Performance**: Add query caching for frequently accessed data
3. **Scaling**: Deploy MCP server in Docker container
4. **Security**: 
   - Use SSL/TLS for all connections
   - Implement role-based access control (RBAC)
   - Audit logging for all queries
5. **Monitoring**: Add Prometheus metrics and alerting
6. **Error Handling**: Implement dead-letter queue for failed tasks
7. **Testing**: Add unit tests for SQL generation and validation

---

## FILE SUMMARY

| File | Purpose | Status |
|------|---------|--------|
| config/settings.py | Environment config | ✓ Artifact 2 |
| config/ldap_config.py | LDAP auth | ✓ Artifact 2 |
| mcp_server/database.py | MS SQL operations | ✓ Artifact 2 |
| mcp_server/auth.py | LDAP integration | ✓ Artifact 2 |
| mcp_server/tools.py | MCP tool defs | ✓ Artifact 2 |
| mcp_server/main.py | FastAPI server | ✓ Artifact 2 |
| utils/logging_config.py | Logging setup | ✓ Artifact 2 |
| utils/retry_handler.py | Retry logic | ✓ Artifact 2 |
| agents/orchestrator.py | Agent setup | ✓ Artifact 3 |
| run_mcp_server.py | Server entry | ✓ Artifact 3 |
| run_agents.py | Agent execution | ✓ Artifact 3 |
| run_agents_api.py | Agent HTTP API | ✓ Artifact 3 |

---

## QUESTIONS TO VERIFY BEFORE STARTING

Before implementing, confirm:

1. ✓ Do you have MS SQL Server 2016+ running? (with ODBC driver installed)
2. ✓ Is Ollama installed and accessible at `http://localhost:11434`?
3. ✓ Do you have LDAP/AD credentials and server address?
4. ✓ Do you have Python 3.10+ with pip available?
5. ✓ Can your data warehouse be queried with your SQL user account?

If all ✓, you're ready to implement!
