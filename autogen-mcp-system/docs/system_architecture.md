┌─────────────────────────────────────────────────────────────-──┐
│                     LAYER 1: USER INTERFACE                    │
│                                                                │
│  ┌───────────────────────────────────────────────────────-─┐   │
│  │          OpenWebUI (Web-based Chat Interface)           │   │
│  │              • LDAP Authentication                      │   │
│  │              • Natural Language Input                   │   │
│  │              • Real-time Agent Responses                │   │
│  └────────────────────┬───────────────────────────────────-┘   │
└─────────────────────┬─┘                                        │
                      │                                          │
                      ▼                                          │
┌────────────────────────────────────────────────────────────────┐
│                 LAYER 2: ORCHESTRATION LAYER                   │
│                                                                │
│  ┌───────────────────────────────────────────────────────-─┐   │
│  │           SUPERVISOR / ROUTER AGENT                     │   │
│  │           (Powered by Ollama + Gemma)                   │   │
│  │                                                         │   │
│  │  Analyzes user intent and classifies as:                │   │
│  │    • DATA_ANALYSIS    → Data Team                       │   │
│  │    • WEB_RESEARCH     → Research Team                   │   │
│  │    • CALENDAR         → Calendar Team                   │   │
│  │    • MIXED            → Multiple Teams                  │   │
│  └───────────────────────────────────────────────────────-─┘   │
│                      │                                         │
│         ┌────────────┼────────────┐                            │
│         ▼            ▼            ▼                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │   DATA   │  │   WEB    │  │ CALENDAR │                      │
│  │ ANALYSIS │  │ RESEARCH │  │   MGMT   │                      │
│  │   TEAM   │  │   TEAM   │  │   TEAM   │                      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
└───────┼─────────────┼─────────────┼───────────────────────-─--─┘
        │             │             │
        ▼             ▼             ▼
┌────────────────────────────────────────────────────────────────┐
│                   LAYER 3: AGENT TEAMS                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              DATA ANALYSIS TEAM (Magentic)              │   │
│  │  ┌─────────────┐  ┌────────────────┐  ┌──────────────┐  │   │
│  │  │  SQL Agent  │  │ Analysis Agent │  │  Validation  │  │   │
│  │  │             │  │                │  │    Agent     │  │   │
│  │  │ Generates   │  │ Performs data  │  │ Reviews and  │  │   │
│  │  │ SQL queries │→ │ analysis with  │→ │ validates    │  │   │
│  │  │ Executes    │  │ pandas/stats   │  │ all findings │  │   │
│  │  │ via tools   │  │                │  │              │  │   │
│  │  └─────────────┘  └────────────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              WEB RESEARCH TEAM (Magentic)               │   │
│  │  ┌─────────────┐  ┌────────────────┐                    │   │
│  │  │Search Agent │  │  Summarizer    │                    │   │
│  │  │             │  │     Agent      │                    │   │
│  │  │ Queries web │→ │  Condenses     │                    │   │
│  │  │ APIs for    │  │  findings &    │                    │   │
│  │  │ information │  │  creates       │                    │   │
│  │  │             │  │  summaries     │                    │   │
│  │  └─────────────┘  └────────────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            CALENDAR MANAGEMENT TEAM (Magentic)          │   │
│  │  ┌─────────────┐  ┌────────────────┐                    │   │
│  │  │ Scheduler   │  │ Conflict       │                    │   │
│  │  │   Agent     │  │  Checker       │                    │   │
│  │  │             │  │   Agent        │                    │   │
│  │  │ Books mtgs  │→ │ Detects        │                    │   │
│  │  │ Manages     │  │ scheduling     │                    │   │
│  │  │ calendar    │  │ conflicts      │                    │   │
│  │  └─────────────┘  └────────────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────-──┐
│                    LAYER 4: MCP SERVER                         │
│                    (FastAPI Application)                       │
│                                                                │
│  ┌───────────────────────────────────────────────────────-─┐   │
│  │                    EXPOSED TOOLS                        │   │
│  │                                                         │   │
│  │  1. sql_tool(query_description, sql_script)             │   │
│  │     → Executes SQL with retry logic                     │   │
│  │                                                         │   │
│  │  2. data_analysis_tool(data_json, analysis_type)        │   │
│  │     → Performs pandas analysis                          │   │
│  │                                                         │   │
│  │  3. get_table_schema(table_name)                        │   │
│  │     → Returns table structure                           │   │
│  │                                                         │   │
│  │  Future:                                                │   │
│  │  4. web_search_tool(query, max_results)                 │   │
│  │  5. calendar_tool(action, params)                       │   │
│  └───────────────────────────────────────────────────────-─┘   │
│                                                                │
│  ┌───────────────────────────────────────────────────────-─┐   │
│  │              SUPPORTING COMPONENTS                      │   │
│  │                                                         │   │
│  │  • LDAP Authentication (verify_credentials)             │   │
│  │  • Query Retry Handler (3 attempts, exponential)        │   │
│  │  • SQL Query Validation (blocks dangerous ops)          │   │
│  │  • Structured Logging (Loguru)                          │   │
│  │  • Health Checks (/health, /health/db)                  │   │
│  └───────────────────────────────────────────────────────-─┘   │
└───────────────────────────┬───────────────────────────────-────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌────────────────────────────────────────────────────────────────┐
│                  LAYER 5: DATA & SERVICES                      │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  MS SQL      │  │   Ollama     │  │    LDAP      │          │
│  │  Server      │  │   + Gemma    │  │   / AD       │          │
│  │              │  │              │  │              │          │
│  │ • 100GB+     │  │ • Local LLM  │  │ • Enterprise │          │
│  │ • 50-60      │  │ • No API     │  │   Auth       │          │
│  │   tables     │  │   keys       │  │ • User       │          │
│  │ • Millions   │  │ • Private    │  │   groups     │          │
│  │   of rows    │  │   data       │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────────────────────────────────────────┘

```

---

## 🔄 DATA FLOW - How a User Request Works

### Example: "Show Q4 2024 sales by region and calculate growth trends"
```

STEP 1: USER INPUT
├─ User types in OpenWebUI: "Show Q4 2024 sales by region and calculate growth trends"
├─ OpenWebUI authenticates via LDAP (username: john.doe)
└─ Request sent to MCP Server API

STEP 2: SUPERVISOR ROUTING
├─ Supervisor Agent receives request
├─ Analyzes intent using Ollama + Gemma
├─ Classification: "DATA_ANALYSIS" (SQL + statistics needed)
├─ Context prepared for Data Analysis Team
└─ Routes to Data Analysis Team

STEP 3: DATA ANALYSIS TEAM COLLABORATES (Magentic Pattern)
│
├─ SQL Agent (Turn 1):
│   ├─ "I need to understand the sales table structure"
│   ├─ Calls: get_table_schema("sales")
│   ├─ Receives: columns [region, date, amount, product_id]
│   └─ Generates SQL:
│       "SELECT region,
│               SUM(amount) as total_sales,
│               COUNT(*) as transaction_count
│        FROM sales
│        WHERE date >= '2024-10-01' AND date <= '2024-12-31'
│        GROUP BY region
│        ORDER BY total_sales DESC"
│
├─ SQL Agent (Turn 2):
│   ├─ Calls: sql_tool("Q4 sales by region", [SQL above])
│   ├─ MCP Server validates SQL (passes - no dangerous keywords)
│   ├─ Retry Handler: Attempt 1
│   ├─ SQL executes successfully
│   └─ Returns:
│       {
│         "success": true,
│         "columns": ["region", "total_sales", "transaction_count"],
│         "rows": [
│           {"region": "North", "total_sales": 1500000, "transaction_count": 3200},
│           {"region": "South", "total_sales": 1200000, "transaction_count": 2800},
│           {"region": "East", "total_sales": 980000, "transaction_count": 2100},
│           {"region": "West", "total_sales": 750000, "transaction_count": 1600}
│         ],
│         "row_count": 4
│       }
│
├─ Analysis Agent (Turn 3):
│   ├─ Receives SQL results from SQL Agent
│   ├─ "I'll calculate growth trends by comparing to Q3"
│   ├─ Requests Q3 data (asks SQL Agent)
│   └─ SQL Agent fetches Q3 data
│
├─ SQL Agent (Turn 4):
│   ├─ Generates Q3 query
│   ├─ Executes via sql_tool
│   └─ Returns Q3 data
│
├─ Analysis Agent (Turn 5):
│   ├─ Now has Q4 and Q3 data
│   ├─ Calls: data_analysis_tool(combined_json, "trend")
│   ├─ Calculates:
│   │   • North: +12.5% growth
│   │   • South: +8.3% growth
│   │   • East: -3.2% decline
│   │   • West: +15.7% growth
│   ├─ Identifies insights:
│   │   • Overall growth: +9.8%
│   │   • West region shows strongest growth
│   │   • East region declining, needs attention
│   └─ Prepares summary
│
└─ Validation Agent (Turn 6):
    ├─ Reviews SQL queries: ✓ Syntactically correct
    ├─ Reviews calculations: ✓ Math checks out
    ├─ Reviews logic: ✓ Q3 vs Q4 comparison makes sense
    ├─ Reviews insights: ✓ Conclusions supported by data
    ├─ Checks for data quality issues: ✓ No nulls, no anomalies
    └─ APPROVES final response

STEP 4: RESPONSE AGGREGATION
├─ Team conversation complete (6 turns, under max 15)
├─ Final result compiled
└─ Formatted for user

STEP 5: DELIVERY TO USER
├─ Response returned to OpenWebUI
└─ User sees:

    "Q4 2024 Sales Analysis by Region:
    
    Regional Performance:
    • North: $1,500,000 (3,200 transactions) - ↑ 12.5% vs Q3
    • South: $1,200,000 (2,800 transactions) - ↑ 8.3% vs Q3
    • East: $980,000 (2,100 transactions) - ↓ 3.2% vs Q3
    • West: $750,000 (1,600 transactions) - ↑ 15.7% vs Q3
    
    Key Insights:
    1. Overall Q4 growth: +9.8% compared to Q3
    2. West region shows strongest growth momentum
    3. East region experiencing decline - recommend investigation
    4. North region maintains largest market share
    
    Total Q4 Sales: $4,430,000 across 9,700 transactions"

```

---

## 🛠️ TECHNICAL COMPONENTS BREAKDOWN

### 1. **MCP Server** (FastAPI)
**Location**: `mcp_server/` directory
**Purpose**: Exposes Python functions as tools to AI agents

**Key Files**:
- `main.py` - FastAPI app, routes, MCP tool registration
- `database.py` - MS SQL connection, query execution, retry logic
- `tools.py` - Tool definitions (sql_tool, data_analysis_tool, etc.)
- `auth.py` - LDAP authentication middleware

**What it does**:
- Authenticates users via LDAP
- Validates SQL queries (blocks DROP, DELETE, etc.)
- Executes queries with automatic retry (3 attempts, exponential backoff)
- Provides health check endpoints
- Logs all operations with structured logging

### 2. **Agent Orchestrator** (AutoGen 2)
**Location**: `agents/` directory
**Purpose**: Coordinates multiple AI agent teams

**Key Components**:
- **Supervisor/Router Agent**: Classifies user intent, routes to appropriate team
- **Team Manager**: Loads team configurations from JSON
- **Conversation Manager**: Handles multi-turn agent conversations
- **Result Aggregator**: Combines outputs from multiple teams

**Agent Collaboration Pattern**: Magentic
- Agents talk to each other as needed
- Not strictly sequential
- Validation agent can request corrections
- Max 15 turns to prevent infinite loops

### 3. **Data Analysis Team**
**Members**: 3 agents
- **SQL Agent**: Generates and executes SQL queries
- **Analysis Agent**: Performs statistical analysis with pandas
- **Validation Agent**: Reviews and validates findings

**Tools Available**:
- `sql_tool` - Execute SQL with retry
- `data_analysis_tool` - Pandas analysis
- `get_table_schema` - Understand table structure

### 4. **Web Research Team** (Future)
**Members**: 2 agents
- **Search Agent**: Queries web APIs
- **Summarizer Agent**: Condenses findings

**Tools Needed** (to be implemented):
- `web_search_tool` - Internet search
- `content_scraper_tool` - Extract content

### 5. **Calendar Management Team** (Future)
**Members**: 2 agents
- **Scheduler Agent**: Books meetings
- **Conflict Checker Agent**: Detects conflicts

**Tools Needed** (to be implemented):
- `calendar_tool` - Create/update events
- `availability_tool` - Check free/busy

### 6. **Configuration Layer**
**Location**: `config/` directory

**Key Files**:
- `settings.py` - Environment variables, Pydantic models
- `ldap_config.py` - LDAP authentication logic

**Environment Variables** (`.env`):
```

# Ollama

OLLAMA_HOST=<http://localhost:11434>
OLLAMA_MODEL=gemma

# MS SQL Server

MSSQL_SERVER=your_server
MSSQL_DATABASE=your_database
MSSQL_USER=your_user
MSSQL_PASSWORD=your_password

# LDAP

LDAP_SERVER=ldap://your_ad_server
LDAP_BASE_DN=dc=company,dc=com
LDAP_SERVICE_ACCOUNT_USER=<service@company.com>
LDAP_SERVICE_ACCOUNT_PASSWORD=password

# Agent Config

AGENT_RETRY_ATTEMPTS=3
AGENT_ESCALATION_EMAIL=<team-lead@company.com>

```

### 7. **Utilities**
**Location**: `utils/` directory

**Key Components**:
- `logging_config.py` - Structured logging setup (Loguru)
- `retry_handler.py` - Query retry logic with exponential backoff

**Retry Logic**:
```

Attempt 1: Execute immediately
  ↓ (fails)
Wait 2 seconds
  ↓
Attempt 2: Execute again
  ↓ (fails)
Wait 4 seconds
  ↓
Attempt 3: Execute final time
  ↓ (fails)
Escalate to human (send email to AGENT_ESCALATION_EMAIL)

```

### 8. **Testing Suite**
**Location**: `tests/` directory

**Test Coverage**:
- Database connection tests
- LDAP authentication tests
- Query validation tests
- Retry handler tests
- MCP tool tests
- Integration tests
- API endpoint tests

**Run with**: `pytest tests/ -v`

### 9. **AutoGen Studio** (Visual Design Tool)
**Purpose**: Drag-and-drop agent design without code

**Workflow**:
1. Design agent teams visually
2. Configure system messages, tools, models
3. Test in Playground
4. Export as JSON
5. Commit JSON to Git
6. Load JSON in production Python code

**Installation**: `pip install autogen-studio`
**Launch**: `autogen-studio ui`
**Access**: http://127.0.0.1:8081

### 10. **Documentation**
**Location**: `docs/` directory

**9 Professional Templates**:
- README.md - Navigation
- QUICK_START.md - 30-minute setup
- ARCHITECTURE.md - System design (this document!)
- AUTOGEN_STUDIO_GUIDE.md - Visual editing guide
- MCP_SERVER.md - Tool documentation
- AGENTS.md - Team structure
- FAQ.md - Troubleshooting
- GLOSSARY.md - Domain terms
- TESTING.md - Test strategies

---

## 📊 TECHNOLOGY STACK

### Programming & Frameworks
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.10+ | Primary development |
| API Framework | FastAPI | 0.104+ | MCP server |
| Agent Framework | AutoGen 2 | 0.4.8+ | Multi-agent orchestration |
| MCP Protocol | FastMCP | 0.1.0+ | Tool exposure |
| Testing | pytest | Latest | Unit & integration tests |

### AI & LLM
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| LLM Runtime | Ollama | Latest | Local inference |
| Model | Gemma | 2B/7B | Language model |
| Studio | AutoGen Studio | Latest | Visual agent design |

### Database & Data
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Database | MS SQL Server | 2016+ | Data warehouse |
| ODBC Driver | Microsoft ODBC 17+ | Latest | Database connectivity |
| ORM | SQLAlchemy | 2.0+ | Query building |
| Data Analysis | pandas | 2.1+ | Statistical analysis |
| Database Client | pyodbc | 5.1+ | SQL Server connection |

### Authentication & Security
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Auth Protocol | LDAP | - | User authentication |
| LDAP Client | ldap3 | 1.4+ | Python LDAP interface |
| Secrets | python-dotenv | 1.0+ | Environment variables |

### Utilities
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Logging | Loguru | 0.7+ | Structured logging |
| Retry Logic | tenacity | 8.2+ | Exponential backoff |
| Config | Pydantic | 2.5+ | Settings validation |

---

## 📁 PROJECT STRUCTURE
```

autogen-mcp-system/
│
├── config/                      # Configuration layer
│   ├── settings.py             # Environment settings (Pydantic)
│   └── ldap_config.py          # LDAP authentication
│
├── mcp_server/                  # MCP Server (FastAPI)
│   ├── main.py                 # FastAPI app + routes
│   ├── database.py             # MS SQL connections
│   ├── auth.py                 # LDAP middleware
│   └── tools.py                # MCP tool definitions
│
├── agents/                      # Agent orchestration
│   └── orchestrator.py         # Supervisor + team management
│
├── utils/                       # Shared utilities
│   ├── logging_config.py       # Loguru setup
│   └── retry_handler.py        # Query retry logic
│
├── tests/                       # Test suite
│   ├── test_database.py        # DB tests
│   ├── test_ldap.py            # Auth tests
│   ├── test_retry_handler.py   # Retry tests
│   └── test_mcp_tools.py       # Tool tests
│
├── autogen_configs/             # Studio JSON exports
│   ├── data_analysis_team.json
│   ├── web_research_team.json
│   └── calendar_team.json
│
├── docs/                        # Documentation
│   ├── README.md               # Start here
│   ├── QUICK_START.md          # Setup guide
│   ├── ARCHITECTURE.md         # This document
│   ├── AUTOGEN_STUDIO_GUIDE.md # Visual editing
│   ├── components/
│   │   ├── MCP_SERVER.md       # Tool docs
│   │   └── AGENTS.md           # Team docs
│   ├── FAQ.md                  # Troubleshooting
│   ├── GLOSSARY.md             # Terms
│   └── TESTING.md              # Test guide
│
├── logs/                        # Runtime logs
│   └── app.log                 # (auto-created)
│
├── .env                         # Credentials (NOT in Git)
├── .env.example                 # Template
├── .gitignore                   # Git exclusions
├── requirements.txt             # Python dependencies
│
├── run_mcp_server.py            # Start MCP server
├── run_agents.py                # Start agents (POC)
├── run_agents_api.py            # Start agents (HTTP API)
│
├── test_mssql_connection.py     # Manual DB test
├── test_ldap_connection.py      # Manual LDAP test
└── manual_integration_tests.py  # Full system test
