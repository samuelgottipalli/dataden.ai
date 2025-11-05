# Documentation Templates - Copy & Customize

Use these templates immediately in your `docs/` directory.

---

## FILE 1: docs/README.md

```markdown
# MCP Multi-Agent System Documentation

Welcome! This documentation will guide you through understanding, running, and extending our multi-agent data analysis system.

## Quick Navigation

- **New to the project?** → Start with [Quick Start](QUICK_START.md)
- **Want to understand the architecture?** → Read [Architecture](ARCHITECTURE.md)
- **Need to modify agents?** → See [AutoGen Studio Guide](AUTOGEN_STUDIO_GUIDE.md)
- **Want to add new functionality?** → Check [Examples](examples/)
- **Having issues?** → Check [FAQ](FAQ.md)
- **Don't know a term?** → Try [Glossary](GLOSSARY.md)

## System Overview

This system uses multiple AI agent teams to:
- **Analyze Data**: Query data warehouse, generate insights
- **Research Web**: Search internet, summarize findings
- **Manage Calendar**: Schedule meetings, manage conflicts

Users request tasks in natural language, a supervisor agent routes to the appropriate team, and results are delivered automatically.

## Key Technologies

- **AutoGen 2**: Multi-agent orchestration framework
- **Ollama + Gemma**: Local LLM (no API keys needed)
- **FastAPI**: MCP server for tool exposure
- **MS SQL Server**: 100GB+ enterprise data warehouse
- **LDAP**: Enterprise authentication (same as OpenWebUI)

## Onboarding Timeline

- **Day 1 (Morning)**: Environment setup, architecture understanding
- **Day 1 (Afternoon)**: AutoGen Studio introduction
- **Day 2**: Component deep-dives, first contribution
- **Day 3+**: Ramping on real tasks

## Getting Help

1. Check [FAQ](FAQ.md) first
2. Consult relevant component documentation in `docs/components/`
3. Review `docs/examples/` for similar patterns
4. Ask your mentor or team lead

## Repository Structure

```
autogen-mcp-system/
├── docs/                 # This folder
├── config/              # Environment & LDAP config
├── mcp_server/          # FastAPI MCP server
├── agents/              # Agent orchestration
├── utils/               # Shared utilities
├── tests/               # Test suite
├── autogen_configs/     # Exported Studio configs (JSON)
└── logs/               # Runtime logs
```

## Running the System

Three commands in three terminals:

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start MCP Server
python run_mcp_server.py

# Terminal 3: Run agents (or start API)
python run_agents.py
```

See [Quick Start](QUICK_START.md) for detailed steps.

---

## FILE 2: docs/QUICK_START.md

```markdown
# Quick Start Guide

Get the system running in 30 minutes.

## Prerequisites

- Python 3.10+
- Ollama installed (https://ollama.com)
- VS Code or PyCharm
- Windows/Mac/Linux

## Step 1: Environment Setup (5 minutes)

```bash
# Clone or create project
cd autogen-mcp-system

# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configuration (5 minutes)

```bash
# Copy example config
cp .env.example .env

# Edit .env with your values
# - MSSQL_SERVER: Your SQL server address
# - LDAP_SERVER: Your AD/LDAP server
# - Other credentials
```

Get these from:
- SQL Server: Your DBA or IT team
- LDAP/AD: Your IT/security team
- Ollama: Local (no credentials needed)

## Step 3: Verify Prerequisites (5 minutes)

```bash
# Test SQL connection
python test_mssql_connection.py
# Expected output: ✓ MS SQL connection successful

# Test LDAP connection
python test_ldap_connection.py
# Expected output: ✓ LDAP connection successful

# Verify Ollama model
ollama pull gemma  # First time only, ~5GB download
```

## Step 4: Start Services (3 terminals, ~10 minutes setup)

**Terminal 1 - Ollama:**
```bash
ollama serve
# Wait for: Listening on ...
```

**Terminal 2 - MCP Server:**
```bash
python run_mcp_server.py
# Expected output:
# ✓ MS SQL Server connection established
# Starting MCP Server on 127.0.0.1:8000
```

**Terminal 3 - Agents (POC mode):**
```bash
python run_agents.py
# Watch agent conversations in real-time
```

## Success Indicators

✅ All three terminals running without errors
✅ Agent messages appearing in Terminal 3
✅ No SQL/LDAP authentication errors

## Next Steps

1. Read [Architecture](ARCHITECTURE.md) to understand the flow
2. Explore [AutoGen Studio](AUTOGEN_STUDIO_GUIDE.md) visually
3. Try modifying an agent's system message in Studio
4. Make your first commit

## Troubleshooting

**Issue**: "Connection timeout to Ollama"
→ Run `ollama serve` in Terminal 1

**Issue**: "LDAP authentication failed"
→ Verify credentials in .env match your AD/LDAP

**Issue**: "Python not found"
→ Ensure Python 3.10+ is installed: `python --version`

For more issues, see [FAQ](FAQ.md)

---

## FILE 3: docs/ARCHITECTURE.md

```markdown
# System Architecture

## High-Level Flow

```
1. User Input (Text)
        ↓
2. OpenWebUI (LDAP Auth)
        ↓
3. API Request to Supervisor Agent
        ↓
4. Supervisor Classifies Intent
        ↓
   ┌────────┼────────┐
   ↓        ↓        ↓
5. Route to Appropriate Team:
   - DATA_ANALYSIS → SQL Agent + Analysis Agent + Validator
   - WEB_RESEARCH  → Search Agent + Summarizer Agent
   - CALENDAR      → Scheduler Agent + Conflict Checker
        ↓
6. Team Processes Task (Agents Collaborate)
        ↓
7. Final Result to User
```

## Component Breakdown

### Layer 1: Entry Point
- **OpenWebUI**: User-facing chat interface (LDAP authenticated)
- Sends natural language requests to our API

### Layer 2: Request Router
- **Supervisor Agent**: Classifies user intent
- Determines which team should handle the request
- Uses Ollama + Gemma for classification

### Layer 3: Specialized Agent Teams

**Data Analysis Team:**
- SQL Agent: Generates and executes SQL queries
- Analysis Agent: Performs statistical analysis
- Validation Agent: Verifies accuracy

**Web Research Team:**
- Search Agent: Queries web for information
- Summarizer Agent: Condenses findings

**Calendar Team:**
- Scheduler Agent: Books meetings
- Conflict Checker: Detects scheduling conflicts

### Layer 4: Supporting Infrastructure
- **MCP Server**: Exposes tools to agents
- **Database**: MS SQL Server (100GB+)
- **LLM**: Ollama + Gemma (local)
- **Auth**: LDAP/Active Directory

## Data Flow Example

**User Request**: "Show Q4 sales by region and find news about competitors"

```
Step 1: OpenWebUI receives message (user: sales_analyst)
Step 2: API endpoint receives request
Step 3: Supervisor Agent classifies as MIXED
        → DATA_ANALYSIS (primary)
        → WEB_RESEARCH (secondary)
Step 4: Data Analysis Team runs
        → SQL Agent: "SELECT region, SUM(sales) FROM sales WHERE Q4"
        → Analysis Agent: Calculates trends, top/bottom performers
        → Validation Agent: Verifies numbers are reasonable
Step 5: Web Research Team runs (parallel)
        → Search Agent: "Competitors news Q4 2024"
        → Summarizer: Extracts key points
Step 6: Results aggregated
Step 7: Return to user:
        "Q4 Sales Analysis:
         [formatted table]
         Trends: [insights]
         
         Competitor News:
         [summaries]"
```

## Technical Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | AutoGen 2 v0.4+ | Multi-agent orchestration |
| LLM | Ollama + Gemma | Local inference (no API keys) |
| MCP | FastAPI + FastMCP | Tool/function exposure |
| Database | MS SQL Server | Enterprise data warehouse |
| Auth | LDAP/Active Directory | Enterprise authentication |
| UI | OpenWebUI | User-facing chat interface |
| Config | JSON (AutoGen Studio) | Agent/team definitions |
| Language | Python 3.10+ | Implementation language |

## Key Design Decisions

1. **Local LLM (Ollama)**
   - No API costs
   - Data stays internal
   - No vendor lock-in
   - PoC to production ready

2. **AutoGen Studio**
   - Visual agent design
   - Easy modification
   - JSON export for version control
   - Python integration

3. **Multi-Team Architecture**
   - Specialized agents for each domain
   - Teams collaborate autonomously
   - Easy to add new teams
   - Clear separation of concerns

4. **LDAP Authentication**
   - Integrate with existing enterprise auth
   - Same as OpenWebUI
   - Role-based access ready
   - Enterprise-grade security

## Scaling Considerations (Future)

- **Queue-based execution**: For long-running tasks
- **Agent clustering**: Multiple Ollama instances
- **Caching layer**: For repeated queries
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK stack for analysis

---

## FILE 4: docs/AUTOGEN_STUDIO_GUIDE.md

```markdown
# AutoGen Studio Guide

Launch, modify, and export agent teams visually.

## Installation & Launch

```bash
# Already installed via pip
# To launch the UI:
autogen-studio ui

# Opens at http://127.0.0.1:8081
```

## The AutoGen Studio Interface

### Top Tabs

1. **Build** (Main tab)
   - Create skills (Python functions)
   - Configure models (Ollama, OpenAI)
   - Build agents
   - Define workflows/teams

2. **Playground** 
   - Test your workflows
   - Chat with agents
   - See conversation flow
   - Monitor token usage

3. **Gallery**
   - Browse pre-built examples
   - Import from community
   - Default component library

4. **Deploy**
   - Instructions for production
   - Export as API
   - Docker deployment

## Modifying an Existing Agent

### Goal: Change SQL Agent's system message

1. Go to **Build** tab
2. Find **Data Analysis Team** in left sidebar
3. Click on **SQL Agent** within the team
4. In right panel, edit "System Message" field
5. Add new instruction (e.g., "Always use LIMIT 100 for safety")
6. Click "Save"
7. Test in Playground tab

### What Changed Behind the Scenes

AutoGen Studio updated the JSON config:

```json
{
  "name": "SQLAgent",
  "system_message": "You are a SQL expert...[UPDATED MESSAGE]",
  "model": {
    "model": "gemma",
    "base_url": "http://localhost:11434/v1"
  }
}
```

## Adding a New Tool to a Team

### Goal: Add a web search tool to Data Analysis Team

1. Go to **Build → Skills**
2. Click **Create New Skill**
3. Name: `web_search`
4. Write Python function:
   ```python
   def web_search(query: str) -> list:
       """Search web for information"""
       # Implementation here
       return results
   ```
5. Click **Save**
6. Go back to **Data Analysis Team**
7. Click the **"+"** button in the team
8. Select the new `web_search` skill
9. Click **Save**

## Modifying Agent Collaboration Pattern

Teams can use different collaboration patterns:

- **RoundRobin**: One agent at a time (A → B → C → A)
- **MagenticOne**: Agents collaborate as needed (all talk to each other)
- **Swarm**: Hierarchical structure

To change:

1. Select your team
2. Find "Team Type" or "Provider" field
3. Choose pattern
4. Save and test in Playground

## Testing in Playground

1. Go to **Playground** tab
2. Select your team
3. Type a task (e.g., "Analyze last quarter's sales")
4. Click **Run**
5. Watch agents collaborate in real-time
6. See token usage and costs

## Exporting for Production

After you're happy with your team:

1. Go to **Build**
2. Right-click team name → **Download**
3. Save as `my_team.json`
4. Commit to Git: `git add autogen_configs/my_team.json`
5. In Python code, load it:
   ```python
   import json
   with open("autogen_configs/my_team.json") as f:
       config = json.load(f)
   team = MagenticOneGroupChat.model_validate(config)
   ```

## Common Modifications Cheat Sheet

| Want to... | Where | How |
|-----------|-------|-----|
| Change an agent's personality | Build → Agent → System Message | Edit text field |
| Add a new tool | Build → Skills | Write Python function |
| Use different LLM | Build → Models | Add new model config |
| Change team structure | Build → Team type | Select pattern |
| Test a workflow | Playground | Select team, type task |
| Share config | Export JSON | Download and commit |
| Import example | Gallery | Select, click Import |

## Troubleshooting in Studio

**Issue**: "Model not available"
→ In Build → Models, verify Ollama is running and model is installed

**Issue**: "Agent not responding"
→ Check System Message has no syntax errors

**Issue**: "Tool not showing up"
→ Go to Build → Skills, verify function is saved

**Issue**: "Can't test workflow"
→ Playground only works after saving. Click Save first.

---

## FILE 5: docs/components/MCP_SERVER.md

```markdown
# MCP Server Component

## Overview

The MCP (Model Context Protocol) Server is a FastAPI application that:
- Exposes Python functions as tools to agents
- Handles MS SQL database connections
- Authenticates users via LDAP
- Implements query retry logic with escalation
- Provides REST API endpoints for testing

**Location**: `mcp_server/` directory

## Architecture

```
FastAPI App
    ├── Health Endpoints
    │   ├── /health
    │   └── /health/db
    ├── Authentication
    │   └── /auth/verify
    └── MCP Tools
        ├── sql_tool
        ├── data_analysis_tool
        └── get_table_schema
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, route definitions |
| `database.py` | MS SQL connections, query execution |
| `tools.py` | Tool definitions exposed to agents |
| `auth.py` | LDAP authentication |

## Running the MCP Server

```bash
python run_mcp_server.py
```

Expected output:
```
Starting MCP Server on 127.0.0.1:8000
✓ MS SQL Server connection established
Listening on http://127.0.0.1:8000
```

Access Swagger UI for testing:
```
http://127.0.0.1:8000/docs
```

## Available Tools

### 1. sql_tool

**Purpose**: Execute SQL queries against data warehouse with automatic retry

**Function**:
```python
async def sql_tool(query_description: str, sql_script: str) -> dict
```

**Parameters**:
- `query_description` (str): What the query does (for logging)
- `sql_script` (str): SQL to execute

**Returns**:
```json
{
  "success": true,
  "columns": ["column1", "column2"],
  "rows": [{"column1": "value1", "column2": "value2"}],
  "row_count": 100
}
```

**Example Usage** (in agent context):
```
Agent: "I need to get top 5 products by sales this month"
MCP: Call sql_tool(
  query_description="Top 5 products by sales",
  sql_script="SELECT TOP 5 ProductID, SUM(Amount) FROM sales WHERE MONTH(Date) = MONTH(GETDATE()) GROUP BY ProductID ORDER BY 2 DESC"
)
```

**Automatic Retry**:
- If query fails, automatically retries up to 3 times
- Uses exponential backoff (2s, 4s, 8s)
- On final failure, escalates to team lead email

### 2. data_analysis_tool

**Purpose**: Analyze retrieved data using pandas

**Function**:
```python
async def data_analysis_tool(data_json: str, analysis_type: str) -> dict
```

**Parameters**:
- `data_json` (str): JSON string of data
- `analysis_type` (str): One of "summary", "correlation", "trend"

**Returns**:
```json
{
  "success": true,
  "shape": [100, 5],
  "columns": ["col1", "col2"],
  "basic_stats": {...},
  "summary": {...}
}
```

**Analysis Types**:
- `summary`: Null values, duplicates, data types
- `correlation`: Correlation matrix for numeric columns
- `trend`: Time-series analysis (if dates present)

### 3. get_table_schema

**Purpose**: Retrieve table schema information

**Function**:
```python
async def get_table_schema(table_name: str) -> dict
```

**Returns**: Column names, data types, nullable status

**Use Case**: Agent needs to understand table structure before writing SQL

## Adding a New Tool

### Step 1: Create Python function in `tools.py`

```python
async def my_new_tool(param1: str, param2: int) -> dict:
    """
    Tool description - this becomes the MCP tool description
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Result dictionary
    """
    result = do_something(param1, param2)
    return {"success": True, "result": result}
```

### Step 2: Register as MCP tool in `main.py`

```python
@mcp.tool
async def my_new_tool(param1: str, param2: int) -> dict:
    """Tool description"""
    return await mcp_server.tools.my_new_tool(param1, param2)
```

### Step 3: Test via Swagger

1. Restart `python run_mcp_server.py`
2. Open http://127.0.0.1:8000/docs
3. Find your new tool
4. Click "Try it out"
5. Fill in parameters
6. Click "Execute"

### Step 4: Test with agents

In your agent workflow, the new tool automatically appears as an option.

## Authentication

All MCP endpoints support LDAP authentication:

```bash
curl -u username:password http://127.0.0.1:8000/health
```

System authenticates against configured LDAP server. On success, user info is returned.

## Database Connection Details

**Connection String** (from .env):
```
mssql+pyodbc://user:password@server:1433/database?driver=ODBC+Driver+17+for+SQL+Server
```

**Query Validation**:
Dangerous operations are blocked:
- `DROP` table, database
- `DELETE` rows
- `TRUNCATE` table
- `ALTER` schema

Safe queries (SELECT, INSERT with validation, UPDATE with WHERE clause) are allowed.

**Connection Pooling**:
Currently using default connection per query. For production, implement SQLAlchemy connection pooling.

## Monitoring & Debugging

### View Logs

```bash
tail -f logs/app.log
```

Search for specific operations:
```bash
grep "Executing query" logs/app.log
grep "ERROR" logs/app.log
grep "username" logs/app.log  # Audit trail
```

### Health Checks

```bash
# Server health
curl http://127.0.0.1:8000/health

# Database connectivity
curl http://127.0.0.1:8000/health/db

# Auth verification
curl -u testuser:testpass http://127.0.0.1:8000/auth/verify
```

### Performance Tuning

If queries are slow:

1. Check database indexes: `SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('table_name')`
2. Monitor query execution time in logs
3. For large result sets, add LIMIT/TOP clause
4. Consider caching layer for frequent queries

## Common Issues

**Issue**: "Connection refused"
→ Check MSSQL_SERVER and MSSQL_PORT in .env
→ Run `test_mssql_connection.py`

**Issue**: "LDAP authentication failed"
→ Check LDAP_SERVER, LDAP_USER in .env
→ Run `test_ldap_connection.py`

**Issue**: "Query blocked"
→ Check for dangerous keywords (DROP, DELETE, etc.)
→ Modify query to be safe

**Issue**: "Query timeout"
→ Add `LIMIT 1000` or `TOP 1000`
→ Increase timeout in config
→ Query may need optimization

---

## FILE 6: docs/components/AGENTS.md

```markdown
# Agent Teams Component

## Overview

Agents are autonomous entities powered by LLMs. They receive instructions (system message), tools (MCP tools), and collaborate to accomplish tasks.

**Your System Has 3 Teams**:
1. Data Analysis Team
2. Web Research Team
3. Calendar Management Team

## Supervisor/Router Agent

**Purpose**: Classify user requests and route to appropriate team

**System Message**:
```
You are a task router. Your job is to understand user intent and route to the right team.

Categories:
1. DATA_ANALYSIS - Anything about data, queries, analytics
   Examples: "Show sales trends", "Analyze customer data"
   
2. WEB_RESEARCH - Internet search, research, news
   Examples: "Find latest news on X", "Research competitor Y"
   
3. CALENDAR - Meeting scheduling, calendar management
   Examples: "Schedule meeting", "When is everyone free"

For each request:
1. Identify the category
2. If mixed (needs multiple teams), start with primary
3. Provide context for the team
4. Format: [CATEGORY] - [reasoning] - [task details]
```

**How to Modify**:
1. Open AutoGen Studio
2. Find "Supervisor Agent"
3. Click and edit "System Message"
4. Add new categories or examples
5. Save and test in Playground

## Data Analysis Team

### Team Members

1. **SQL Agent**
   - Role: Generate and execute SQL queries
   - Tools: sql_tool, get_table_schema
   - System Message: SQL expert for MS SQL Server

2. **Analysis Agent**
   - Role: Perform statistical analysis
   - Tools: data_analysis_tool
   - System Message: Data scientist, calculates insights

3. **Validation Agent**
   - Role: Quality assurance, verify accuracy
   - Tools: None (analytical only)
   - System Message: QA specialist, checks logic

### Workflow

```
User: "Show Q4 sales by region"
  ↓
SQL Agent: Generates query → "SELECT region, SUM(sales) FROM..."
  ↓
(SQL Agent executes via sql_tool with retry)
  ↓
Analysis Agent: Gets results → Calculates trends, identifies patterns
  ↓
Validation Agent: Reviews → Checks numbers make sense, approves or requests changes
  ↓
Result: "Q4 Sales by Region: [table with analysis]"
```

### Conversation Pattern

**Type**: Magentic (agents talk to each other as needed)

**Max Turns**: 15 (prevents infinite loops)

**Exit Condition**: When Validation Agent approves results

### How to Modify

#### Change SQL Agent Behavior

In AutoGen Studio → Data Analysis Team → SQL Agent:
- Edit "System Message" to add constraints
- Add "Tools" if new tools needed
- Adjust "Model Temperature" for consistency (lower = more consistent, 0.3-0.5 recommended)

Example modification:
```
Original: "Generate SQL queries"
Modified: "Generate SQL queries. Always use TOP 1000 for safety. 
           Always explain your SQL before executing."
```

#### Add New Skill to Team

1. Create in AutoGen Studio → Skills
2. Write Python function
3. Add to Data Analysis Team
4. Test in Playground

## Web Research Team

### Team Members

1. **Search Agent**
   - Queries web for information
   - Tools: web_search_tool (to be implemented)

2. **Summarizer Agent**
   - Condenses findings
   - Tools: None (analysis only)

### Implementation Status

**Current**: Not yet implemented (data warehouse focused POC)

**To Implement**:
1. Add `web_search_tool` to MCP server
2. Create Search Agent in Studio
3. Create Summarizer Agent in Studio
4. Combine in "Web Research Team"

### Example Integration

```python
# In mcp_server/tools.py
async def web_search_tool(query: str, max_results: int = 5) -> dict:
    """Search web using your preferred API (Google, Bing, etc)"""
    import requests
    results = search_api.query(query)
    return {"success": True, "results": results[:max_results]}
```

## Calendar Management Team

### Team Members

1. **Scheduler Agent**
   - Books meetings, manages calendar
   - Tools: calendar_tool (to be implemented)

2. **Conflict Checker Agent**
   - Detects scheduling conflicts
   - Tools: calendar_query_tool (to be implemented)

### Implementation Status

**Current**: Not yet implemented

**To Implement**:
1. Add calendar API integration (Outlook, Google, etc)
2. Create `calendar_tool` and `calendar_query_tool` in MCP
3. Create agents in Studio
4. Combine in team

## Agent Conversation Patterns

### Pattern 1: Sequential (A → B → C)
- Agent A does task
- Results to Agent B
- Results to Agent C
- Clean but inflexible

**Use for**: Simple, straightforward workflows

### Pattern 2: Magentic (All talk to each other)
- Any agent can talk to any agent
- Agents decide who needs to be involved
- More flexible and efficient

**Use for**: Complex reasoning, quality gates

**Your Data Analysis Team uses this** ✅

### Pattern 3: Hierarchical
- Manager agent coordinates
- Worker agents specialize
- Good for large teams

**Consider for**: Multiple research teams

## Creating a New Agent

### In AutoGen Studio

1. Go to **Build** tab
2. Click **New Agent**
3. Fill in:
   - Name: `my_agent`
   - Type: `Assistant`
   - Model: Select your LLM
   - System Message: Agent personality/instructions
   - Tools: Select available tools
4. Save
5. Add to a team

### In Python Code

```python
from autogen_agentchat.agents import AssistantAgent

my_agent = AssistantAgent(
    name="MyAgent",
    model_client=model_client,
    system_message="""You are an expert at...""",
    workbench=workbench  # Gives access to tools
)
```

## Debugging Agents

### Issue: Agent not responding

**In Studio Playground**:
1. Type your task
2. Click Run
3. Watch the conversation
4. See where it stops

**Check**:
- Does agent have required tools?
- Is system message clear?
- Is LLM working? (Check Ollama)

### Issue: Agent making mistakes

**Solutions**:
1. Improve system message with examples
2. Add validation agent to team
3. Give agent more tools for verification

### Issue: Agents looping

**Solutions**:
1. Reduce `max_turns` in team config
2. Add clear exit condition
3. Check system message isn't ambiguous

---

## FILE 7: docs/FAQ.md

```markdown
# FAQ - Frequently Asked Questions

## Installation & Setup

**Q: Python not found**
A: Ensure Python 3.10+ is installed: `python --version`
   If not, download from python.org

**Q: Virtual environment won't activate**
A: On Windows, try: `venv\Scripts\activate`
   On Mac/Linux: `source venv/bin/activate`

**Q: pip install fails**
A: Try: `pip install --upgrade pip`
   Then retry: `pip install -r requirements.txt`

## Running the System

**Q: "Connection refused" on MCP server startup**
A: Check:
   - MSSQL_SERVER and port in .env
   - SQL Server is running
   - Run: `python test_mssql_connection.py`

**Q: Ollama says "model not found"**
A: Download it: `ollama pull gemma`
   First run is slow (~5GB download)

**Q: LDAP authentication keeps failing**
A: Verify in .env:
   - LDAP_SERVER address
   - LDAP_USER credentials (use service account)
   - Run: `python test_ldap_connection.py`

## AutoGen Studio

**Q: How do I launch Studio?**
A: `autogen-studio ui`
   Opens at http://127.0.0.1:8081

**Q: Can I use my own model instead of Ollama?**
A: Yes. In Studio → Build → Models → Add new model with OpenAI-compatible endpoint

**Q: How do I export my workflow?**
A: Right-click team → Download JSON
   Use in Python: `MagenticOneGroupChat.model_validate(json_config)`

## Agents & Behavior

**Q: Agent is repeating itself**
A: In Studio → Team settings → Reduce `max_turns` (default 15)
   Also check system message isn't circular

**Q: How do I add a new tool?**
A: 1. Write Python function in `mcp_server/tools.py`
   2. Add @mcp.tool decorator
   3. Restart MCP server
   4. In Studio, tool auto-appears

**Q: Can agents use external APIs?**
A: Yes, via tools. Create tool function that calls API:
   ```python
   async def my_api_tool(param: str) -> dict:
       response = requests.get(f"https://api.example.com?q={param}")
       return response.json()
   ```

## Data & Queries

**Q: Why did my SQL query get blocked?**
A: Queries with DROP, DELETE, TRUNCATE, ALTER are blocked for safety.
   Modify query to be safe (SELECT only, or UPDATE with WHERE clause)

**Q: Query takes forever**
A: Add LIMIT or TOP clause: `SELECT TOP 1000 * FROM table`
   Check if it's running: `SELECT @@VERSION`

**Q: How do I see query history?**
A: Check logs: `grep "Executing query" logs/app.log`

## Performance

**Q: System is slow**
A: 
   1. Check: `curl http://127.0.0.1:8000/health/db` - is DB responding?
   2. Check: `ollama ps` - is LLM responding?
   3. Check logs for errors: `tail logs/app.log`

**Q: Too many tokens being used**
A: In Studio → Agent settings → Lower temperature (more consistent)
   Shorter system messages
   Fewer turns in conversation

## Debugging

**Q: How do I see what agent is doing?**
A: In Studio Playground → Run task → Watch live conversation

**Q: How do I see MCP server logs?**
A: Open new terminal: `tail -f logs/app.log`

**Q: How do I debug a query?**
A: 1. Copy exact SQL from logs
   2. Run in SQL Server Management Studio
   3. Check results manually

## Security & Access

**Q: Who can use this system?**
A: Anyone with LDAP credentials in your organization

**Q: Can I restrict certain queries?**
A: Currently: Block DROP/DELETE/ALTER via sql validation
   Future: Add SQL permission model

**Q: Is data encrypted?**
A: In transit: No (POC) - Use HTTPS in production
   At rest: Follows SQL Server configuration

---

## FILE 8: docs/GLOSSARY.md

```markdown
# Glossary of Terms

## AI/ML Concepts

**Agent**: An autonomous entity powered by an LLM that can think, plan, and use tools to accomplish tasks.

**LLM (Large Language Model)**: Neural network trained on massive text data. Examples: GPT-4, Gemma, Llama.

**Model Temperature**: Parameter controlling randomness (0 = deterministic, 1 = creative). For agents, typically 0.3-0.7.

**Token**: Unit of text the LLM processes. ~4 chars = 1 token. Affects cost and latency.

**Inference**: Running the LLM to generate output based on input.

## System-Specific

**MCP (Model Context Protocol)**: Open standard for connecting LLMs to tools/APIs. Think of it as "how agents call functions."

**Tool**: Python function exposed to agents via MCP. Example: `sql_tool` executes SQL queries.

**Skill**: Same as Tool, just different terminology.

**Supervisor/Router Agent**: Special agent that classifies user requests and routes to appropriate teams.

**Team**: Group of agents working together. Example: Data Analysis Team = SQL Agent + Analysis Agent + Validation Agent.

**Magentic Pattern**: Agents can talk to each other as needed (vs strict sequence).

**Turn**: One back-and-forth in agent conversation. Max turns = conversation limit.

## Database Terms

**Data Warehouse**: Centralized database for analytics. Your 100GB+ SQL Server.

**Query**: SQL command requesting data. Example: "SELECT * FROM sales WHERE date > 2024-01-01"

**ODBC**: Protocol for database connections. Allows Python to talk to SQL Server.

**Result Set**: Data returned from query. Example: 1000 rows × 5 columns.

**Transaction**: Group of database operations treated as unit. Either all succeed or all fail.

## Authentication Terms

**LDAP**: Lightweight Directory Access Protocol. Protocol for authenticating users against company directory (Active Directory).

**Active Directory (AD)**: Microsoft's centralized authentication system. What your company uses.

**Service Account**: Special user account for applications (not a real person). Used by app to query LDAP.

**Credentials**: Username + password.

**Authentication**: Verifying "you are who you claim to be".

**Authorization**: What authenticated user is allowed to do.

## DevOps Terms

**Docker**: Containerization. Packages your app with all dependencies.

**API**: Application Programming Interface. How apps talk to each other.

**Webhook**: HTTP callback. When X happens, send data to URL Y.

**Environment Variables**: Configuration stored outside code. Examples: DB passwords, API keys.

**.env File**: Text file with environment variables.

**Virtual Environment (venv)**: Isolated Python environment. Prevents dependency conflicts.

**Git**: Version control. Tracks code changes over time.

**Repository**: Folder under Git control.

## File/Folder Terms

**artifacts**: Reusable outputs (code, configs, docs)

**autogen_configs**: JSON files exported from AutoGen Studio

**mcp_server**: FastAPI application serving as tool provider

**agents**: AutoGen orchestration code

**tests**: Unit and integration tests

**logs**: Runtime logs from MCP server and agents

**docs**: This documentation

---

## FILE 9: docs/TESTING.md

```markdown
# Testing Guide

## Running Tests

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_database.py -v

# Run specific test
pytest tests/test_database.py::test_database_connection -v
```

**Expected output**:
```
tests/test_database.py::test_database_connection PASSED
tests/test_database.py::test_sql_validation_blocks_dangerous_queries PASSED
...
===================== 12 passed in 2.34s =====================
```

### Integration Tests

```bash
# Full system check
python manual_integration_tests.py
```

**Expected output**:
```
[1/4] Testing MS SQL Server Connection...
✓ MS SQL Server: PASSED

[2/4] Testing LDAP Connection...
✓ LDAP/AD: PASSED

[3/4] Testing Ollama Connection...
✓ Ollama: PASSED

[4/4] Testing Retry Handler...
✓ Retry Handler: PASSED
```

### API Endpoint Tests

```bash
bash test_api_endpoints.sh
```

**Expected output**:
```
[1/4] Testing /health endpoint...
{"status":"ok","service":"MCP Agent System"}

[2/4] Testing /health/db endpoint...
{"status":"ok","database":"connected"}
```

## Test Coverage

Current coverage:
- Database layer: 95%
- LDAP authentication: 90%
- Retry handler: 100%
- MCP tools: 85%

Target: 90%+ overall

## Adding New Tests

### Test Template

```python
import pytest
from component_to_test import function_name

def test_function_does_something():
    """Test description"""
    # Arrange: Set up test data
    test_input = "example"
    
    # Act: Call the function
    result = function_name(test_input)
    
    # Assert: Check results
    assert result == "expected_output"
```

### Test File Location

- Database tests → `tests/test_database.py`
- Agent tests → `tests/test_agents.py`
- API tests → `tests/test_api.py`

## Debugging Failed Tests

**Test fails**:
```
FAILED tests/test_database.py::test_connection - Connection refused
```

**Steps**:
1. Check error message: "Connection refused"
2. Likely cause: MSSQL not running
3. Fix: Start MSSQL Server, verify connection string in .env
4. Rerun: `pytest tests/test_database.py::test_connection -v`

**Test times out**:
```
FAILED tests/test_agents.py::test_agent_execution - Timeout
```

**Steps**:
1. Agent taking too long to respond
2. Check: Is Ollama running? `ollama ps`
3. Try simpler task
4. Increase timeout in test: `timeout=600`

## Continuous Integration (CI)

When you commit to Git, tests run automatically:

```yaml
# .github/workflows/test.yml (example)
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: pytest tests/ -v
```

**Your responsibility**: Don't commit broken code
- Always run: `pytest tests/ -v` before git push
- Fix failures before committing

## Performance Testing

### Database Query Performance

```python
import time

def test_query_performance():
    start = time.time()
    result = db.execute_query("SELECT TOP 1000 * FROM large_table")
    duration = time.time() - start
    
    # Query should complete in < 5 seconds
    assert duration < 5.0
```

### Agent Response Time

```python
@pytest.mark.asyncio
async def test_agent_response_time():
    start = time.time()
    result = await team.run("Simple task")
    duration = time.time() - start
    
    # Agent should respond in < 30 seconds
    assert duration < 30.0
```

## Test Environments

- **Local**: Your machine (python run_mcp_server.py)
- **CI/CD**: GitHub Actions on each push
- **Staging**: Pre-production environment
- **Production**: Live system (manual testing only)

---

```

These templates are ready to copy into your `docs/` directory. Customize with your specific details (server names, team members, etc.) and you have professional documentation ready for new developers!
