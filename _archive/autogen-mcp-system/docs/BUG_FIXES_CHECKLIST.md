# Bug Fixes & Enhancements Checklist
**Project:** autogen-mcp-system OpenWebUI Integration  
**Date Created:** 2025-11-07  
**Status:** Active Development

---

## ✅ Confirmed Working

- ✅ OpenWebUI successfully integrated with MCP server
- ✅ LDAP authentication working (multiple users tested)
- ✅ Query capability functional (agents can execute SQL)
- ✅ All servers, services, and endpoints running without major issues

---

## 🐛 Bug Fixes & Enhancements To-Do

### **Issue #1: Agent Response Too Verbose** 🔴 HIGH PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 2-3 hours  
**Category:** User Experience

**Problem:**
- Agent responses show too much technical detail
- Function calls are visible to end users
- Users don't need to see internal implementation details
- Makes responses harder to read and understand

**Desired Behavior:**
- Hide function call details from users
- Replace technical messages with simple, user-friendly text
- Show only relevant information
- Keep responses clean and concise

**Implementation Plan:**
1. [ ] Identify all message types currently shown to users
2. [ ] Categorize messages (user-facing vs internal)
3. [ ] Create message filtering logic in `api_routes.py`
4. [ ] Replace verbose technical messages with simple summaries
5. [ ] Add configuration option for verbose mode (admin/debug)
6. [ ] Test with real users to validate readability

**Files to Modify:**
- `mcp_server/api_routes.py` - Message formatting function
- `agents/enhanced_orchestrator.py` - Message emission logic
- `config/openwebui_config.py` - Add verbosity settings

**Acceptance Criteria:**
- [ ] Function calls not visible to regular users
- [ ] Messages are simple and clear
- [ ] Technical details available in debug/admin mode
- [ ] Users report responses are easier to read

---

### **Issue #2: SQL Results Not Formatted as Tables** 🔴 HIGH PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Category:** Data Presentation

**Problem:**
- Function execution results (especially SQL) appear as plain text
- Data is difficult to read and understand
- No visual structure to results
- Hard to compare values or see patterns

**Desired Behavior:**
- SQL results displayed as formatted tables
- Proper column headers
- Aligned columns for easy reading
- Ideally: HTML/Markdown tables that render nicely in OpenWebUI

**Implementation Plan:**
1. [ ] Research OpenWebUI's markdown/HTML rendering capabilities
2. [ ] Create table formatting utility function
3. [ ] Detect SQL result format (list of dicts, tuple, etc.)
4. [ ] Convert results to markdown table format
5. [ ] Add column alignment and header formatting
6. [ ] Handle edge cases (empty results, large datasets, special characters)
7. [ ] Add pagination for large result sets (>50 rows)
8. [ ] Test rendering in OpenWebUI

**Files to Modify:**
- `mcp_server/api_routes.py` - Add table formatting function
- `agents/enhanced_orchestrator.py` - Format results before returning
- Create new utility: `utils/table_formatter.py`

**Example Output:**
```markdown
| Customer Name    | Revenue    | Region   |
|------------------|------------|----------|
| Acme Corp        | $1,245,000 | West     |
| Tech Solutions   | $987,500   | East     |
| Global Industries| $856,200   | Central  |
```

**Acceptance Criteria:**
- [ ] SQL results render as tables in OpenWebUI
- [ ] Tables are properly formatted and aligned
- [ ] Column headers are clear
- [ ] Large datasets handled gracefully (pagination/truncation)
- [ ] Numbers formatted with proper separators
- [ ] Empty results show friendly message

---

### **Issue #3: No Execution Limit or Fallback Model** 🟡 MEDIUM PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 4-5 hours  
**Category:** Cost Control & Reliability

**Problem:**
- Cloud model has limited API calls/tokens
- No execution limit when agent retries fail repeatedly
- Could exhaust API quota quickly
- No fallback mechanism when cloud model unavailable
- Users not informed about quality/speed trade-offs

**Desired Behavior:**
- Set maximum retry attempts per query
- Implement fallback to local model when cloud model fails/exhausted
- Notify users when switching to fallback model
- Clear messaging about quality/speed expectations
- Track and log API usage for monitoring

**Implementation Plan:**
1. [ ] Add retry limit configuration (default: 3 attempts)
2. [ ] Implement retry counter in orchestrator
3. [ ] Configure fallback local model (smaller Ollama model)
4. [ ] Create model switching logic
5. [ ] Add user notification when fallback activated
6. [ ] Implement token/cost tracking
7. [ ] Add API quota monitoring
8. [ ] Create admin dashboard for usage stats
9. [ ] Add graceful degradation messaging

**Files to Modify:**
- `config/settings.py` - Add retry limits, fallback model config
- `agents/enhanced_orchestrator.py` - Add retry logic and model switching
- `mcp_server/api_routes.py` - Add usage tracking
- Create new: `utils/usage_tracker.py`
- Create new: `utils/model_manager.py`

**Configuration Options:**
```python
# Add to settings.py
max_retries_per_query: int = 3
fallback_model: str = "llama3.2:3b"  # Smaller local model
enable_fallback: bool = True
api_quota_limit: int = 1000  # requests per day
warn_at_percentage: float = 0.8  # 80% quota usage
```

**User Messages:**
```
🔄 Switching to local model (cloud model unavailable)
⚠️ Response quality may be reduced, but faster processing
💡 Would you like to continue or retry later?

📊 Current API Usage: 847/1000 requests (84.7%)
```

**Acceptance Criteria:**
- [ ] Queries stop after max retries reached
- [ ] Fallback model activates when needed
- [ ] Users informed about model switches
- [ ] API usage tracked and logged
- [ ] Admins can monitor quota usage
- [ ] System doesn't exhaust API limits
- [ ] Graceful degradation messages shown

---

### **Issue #4: Streaming Not Working in OpenWebUI** 🔴 HIGH PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Category:** Real-time Response

**Problem:**
- OpenWebUI not showing streaming checkbox/option
- Responses arrive as single chunks per agent
- No real-time message streaming
- Users can't see agents working in real-time
- Poor user experience for long-running queries

**Desired Behavior:**
- Messages stream in real-time as agents work
- Users see progress incrementally
- Better feedback during long operations
- Smooth, responsive chat experience

**Root Cause Analysis Needed:**
1. Is OpenWebUI configured to support streaming?
2. Is the API endpoint returning proper SSE format?
3. Are there CORS/networking issues blocking streaming?
4. Is OpenWebUI version compatible with streaming?

**Implementation Plan:**
1. [ ] **Diagnose OpenWebUI streaming capability**
   - Check OpenWebUI version and streaming support
   - Review OpenWebUI connection settings
   - Test with simple streaming endpoint
   - Check browser network tab for SSE connections

2. [ ] **Verify API Implementation**
   - Confirm `/api/v1/chat/completions` returns SSE format
   - Test endpoint directly with curl/Postman
   - Validate chunk format matches OpenAI spec
   - Check for proper `data:` prefix and newlines

3. [ ] **Fix Streaming Format Issues**
   - Ensure proper Server-Sent Events (SSE) format
   - Add proper headers: `Content-Type: text/event-stream`
   - Implement proper chunk buffering
   - Add heartbeat messages to keep connection alive

4. [ ] **Test Streaming End-to-End**
   - Test with browser developer tools
   - Verify messages arrive incrementally
   - Check for connection drops
   - Test with long-running queries

5. [ ] **Alternative: Implement Polling if SSE Fails**
   - Fallback to short polling if streaming not supported
   - Implement status endpoint for query progress
   - Client polls every 500ms for updates

**Files to Modify:**
- `mcp_server/api_routes.py` - Fix streaming response format
- `mcp_server/main.py` - Verify CORS and SSE headers
- Test endpoint: `test_streaming.py` (create new)

**Testing Script:**
```bash
# Test streaming directly
curl -N -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "autogen-agents",
    "messages": [{"role": "user", "content": "test"}],
    "stream": true
  }' \
  http://localhost:8000/api/v1/chat/completions
```

**Proper SSE Format:**
```
data: {"id":"1","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}

data: {"id":"1","object":"chat.completion.chunk","choices":[{"delta":{"content":" World"}}]}

data: [DONE]
```

**Acceptance Criteria:**
- [ ] OpenWebUI shows streaming option (if version supports)
- [ ] Messages arrive incrementally in real-time
- [ ] No full-page waits for responses
- [ ] Long queries show progressive updates
- [ ] Browser dev tools show SSE connection
- [ ] No connection timeouts or drops
- [ ] Fallback mechanism works if streaming unsupported

### **Issue #5: Multi-Turn Conversation Support** 🔴 HIGH PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Category:** Conversation Flow

**Problem:**
- System currently operates as one-shot Q&A
- No conversation context maintained between messages
- Users can't ask follow-up questions
- Can't refine queries based on previous results
- Each query starts fresh with no memory

**Desired Behavior:**
- Support multi-turn conversations
- Maintain conversation history and context
- Allow follow-up questions like:
  - "Now show me the same for Q3"
  - "What about the top 10 instead?"
  - "Can you break that down by region?"
- Remember table names, column names mentioned earlier
- Reference previous query results
- Build on previous analysis

**Example Conversation Flow:**
```
User: Show me top 5 customers by revenue
Agent: [Returns table with top 5 customers]

User: Now show me their purchase history
Agent: [Uses customer IDs from previous query, shows purchase history]

User: What's the average order value for the top customer?
Agent: [Remembers "top customer" = Acme Corp from first query]
```

**Implementation Plan:**
1. [ ] **Update Message Handling**
   - Store full conversation history per user session
   - Pass conversation context to orchestrator
   - Include previous queries and results in agent context

2. [ ] **Modify Orchestrator for Context Awareness**
   - Update `execute_with_streaming()` to accept conversation history
   - Pass history to agents so they can reference it
   - Add context summarization for long conversations

3. [ ] **Update Agent System Prompts**
   - Modify agent instructions to use conversation context
   - Teach agents to recognize references like "the same", "those customers", "that table"
   - Enable agents to reference previous results

4. [ ] **Implement Context Management**
   - Track what tables/columns were mentioned
   - Remember entity names (customers, products, etc.)
   - Store previous query results (last N results)
   - Implement context pruning (keep last 10 turns)

5. [ ] **Add Session Management**
   - Create session store (Redis or in-memory)
   - Associate sessions with user IDs
   - Implement session timeout (30 minutes idle)
   - Clear session on explicit user request

**Files to Modify:**
- `mcp_server/api_routes.py` - Store and pass conversation history
- `agents/enhanced_orchestrator.py` - Accept and use conversation context
- `agents/sql_agent.py` - Update to use context
- `agents/general_assistant.py` - Update to use context
- Create new: `utils/session_manager.py`
- Create new: `utils/context_extractor.py`

**Configuration Options:**
```python
# Add to settings.py
enable_conversation_context: bool = True
max_context_turns: int = 10  # Keep last 10 messages
session_timeout_minutes: int = 30
store_query_results: bool = True  # Store for reference
max_stored_results: int = 5  # Keep last 5 query results
```

**System Instruction Updates:**
```python
# Update agent prompts to include:
"""
You have access to the conversation history. When the user says:
- "the same" or "those" - refer to entities from previous messages
- "now show me X" - build upon previous query
- "what about Y" - modify the previous query for Y

Previous conversation context will be provided to help you understand references.
"""
```

**Acceptance Criteria:**
- [ ] Users can ask follow-up questions
- [ ] Agents understand references to previous messages
- [ ] Context maintained across multiple turns
- [ ] No need to repeat information from earlier
- [ ] Sessions timeout appropriately
- [ ] Memory usage stays reasonable (context pruning works)

---

### **Issue #6: SQL Execution Confirmation Required** 🔴 HIGH PRIORITY
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 4-5 hours  
**Category:** Safety & User Control

**Problem:**
- SQL queries execute automatically without user confirmation
- Users have no chance to review queries before execution
- Risk of running unintended or expensive queries
- No control over what data is accessed
- Safety concern for production databases

**Desired Behavior:**
- Show generated SQL to user before execution
- Request explicit confirmation for data queries (SELECT)
- Block and request confirmation for ANY write operations (INSERT, UPDATE, DELETE)
- Auto-approve safe operations:
  - Schema queries (DESCRIBE, SHOW TABLES, INFORMATION_SCHEMA)
  - Column definition queries
  - Requirement gathering queries
- Clear distinction between exploration and data access

**Example Flow:**
```
User: Show me top 5 customers by revenue

Agent: I need to query the database. Here's the SQL I'll run:

┌─────────────────────────────────────────────┐
│ SELECT TOP 5                                │
│   customer_name,                            │
│   SUM(order_total) as total_revenue        │
│ FROM customers c                            │
│ JOIN orders o ON c.customer_id = o.customer_id │
│ GROUP BY customer_name                      │
│ ORDER BY total_revenue DESC                 │
└─────────────────────────────────────────────┘

This query will:
✓ Read from: customers, orders tables
✓ Return: 5 rows maximum
✓ Operation: SELECT (read-only)

Do you want me to execute this query?
[✓ Approve] [✗ Deny] [✏️ Modify]
```

**Auto-Approved Queries (No Confirmation Needed):**
```sql
-- Schema exploration
SHOW TABLES;
DESCRIBE customers;
SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'customers';

-- These run automatically to help agent understand schema
```

**Requires Confirmation:**
```sql
-- Any actual data query
SELECT * FROM customers;
SELECT TOP 100 * FROM orders WHERE date > '2024-01-01';

-- Definitely requires confirmation (write operations)
UPDATE customers SET status = 'inactive';
DELETE FROM orders WHERE order_id = 123;
INSERT INTO customers VALUES (...);
```

**Implementation Plan:**
1. [ ] **Create Query Classification System**
   - Classify queries: SAFE_SCHEMA, DATA_READ, DATA_WRITE
   - Auto-approve SAFE_SCHEMA queries
   - Require confirmation for DATA_READ
   - Block and warn for DATA_WRITE

2. [ ] **Implement Confirmation Workflow**
   - Pause execution when confirmation needed
   - Send formatted query + explanation to user
   - Wait for user response (approve/deny/modify)
   - Resume or cancel based on response

3. [ ] **Update OpenWebUI Integration**
   - Add interactive buttons/response mechanism
   - Handle user confirmation responses
   - Implement timeout (2 minutes for response)
   - Auto-cancel if timeout exceeded

4. [ ] **Add Query Explanation**
   - Explain what query will do in plain English
   - Show which tables accessed
   - Estimate rows affected/returned
   - Show operation type (read/write)

5. [ ] **Implement Query Modification Flow**
   - Allow user to edit query before execution
   - Validate edited query
   - Re-classify modified query
   - Request new confirmation if needed

**Files to Modify:**
- `agents/sql_agent.py` - Add query classification
- `agents/validation_agent.py` - Enhanced validation with confirmation
- `mcp_server/api_routes.py` - Handle confirmation workflow
- Create new: `utils/query_classifier.py`
- Create new: `utils/confirmation_handler.py`
- Create new: `utils/query_explainer.py`

**Configuration Options:**
```python
# Add to settings.py
require_sql_confirmation: bool = True
auto_approve_schema_queries: bool = True
confirmation_timeout_seconds: int = 120  # 2 minutes
allow_query_modification: bool = True
block_write_operations: bool = True  # Always block INSERT/UPDATE/DELETE
show_query_explanation: bool = True
show_table_access_list: bool = True
show_estimated_rows: bool = True
```

**Query Classification Logic:**
```python
class QueryType(Enum):
    SAFE_SCHEMA = "safe_schema"      # Auto-approve
    DATA_READ = "data_read"          # Require confirmation
    DATA_WRITE = "data_write"        # Block + warn + require confirmation
    DANGEROUS = "dangerous"          # Block completely

def classify_query(sql: str) -> QueryType:
    sql_upper = sql.upper().strip()
    
    # Safe schema queries
    if any(sql_upper.startswith(x) for x in [
        "SHOW TABLES", "DESCRIBE", "SHOW COLUMNS",
        "SELECT * FROM INFORMATION_SCHEMA"
    ]):
        return QueryType.SAFE_SCHEMA
    
    # Write operations
    if any(sql_upper.startswith(x) for x in [
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER"
    ]):
        return QueryType.DATA_WRITE
    
    # Dangerous operations
    if any(x in sql_upper for x in [
        "DROP DATABASE", "DROP TABLE", "TRUNCATE"
    ]):
        return QueryType.DANGEROUS
    
    # Regular SELECT
    if sql_upper.startswith("SELECT"):
        return QueryType.DATA_READ
    
    return QueryType.DATA_READ  # Default to requiring confirmation
```

**User Response Handling:**
```python
# In OpenWebUI chat
User sees:
"""
🔍 SQL Query Ready for Execution

[SQL query displayed in formatted box]

📊 Query Summary:
• Type: SELECT (read-only)
• Tables: customers, orders
• Estimated rows: ~5
• Risk level: LOW

Reply with:
• "approve" or "yes" or "✓" to execute
• "deny" or "no" or "✗" to cancel
• "modify" to edit the query
"""

# System waits for user response before proceeding
```

**Acceptance Criteria:**
- [ ] Schema queries execute automatically (no confirmation)
- [ ] Data queries show SQL and wait for confirmation
- [ ] Write operations blocked by default with strong warnings
- [ ] Clear explanation of what query will do
- [ ] User can approve, deny, or modify
- [ ] Timeout after 2 minutes cancels query
- [ ] Modified queries re-validated and re-confirmed
- [ ] All confirmations logged for audit

---

## 📋 Work Priority Order

### **Sprint 1: Core User Experience (Week 1)**
1. 🔴 Issue #4 - Fix Streaming (Day 1-2)
2. 🔴 Issue #2 - Format SQL Results as Tables (Day 2-3)
3. 🔴 Issue #1 - Reduce Response Verbosity (Day 4-5)

### **Sprint 2: Conversation & Safety (Week 2)**
4. 🔴 Issue #5 - Multi-Turn Conversation Support (Day 1-2)
5. 🔴 Issue #6 - SQL Execution Confirmation (Day 3-4)
6. 🟢 Testing & User Validation (Day 5)

### **Sprint 3: Reliability & Cost Control (Week 3)**
7. 🟡 Issue #3 - Add Execution Limits & Fallback Model (Day 1-3)
8. 🟢 Integration Testing (Day 4)
9. 🟢 Documentation Updates (Day 5)

---

## 🧪 Testing Checklist

After each fix, verify:
- [ ] Original issue is resolved
- [ ] No regressions in other features
- [ ] Multiple users can still access system
- [ ] LDAP authentication still works
- [ ] SQL queries still execute correctly
- [ ] Performance is acceptable
- [ ] Error handling works properly
- [ ] Logs show useful information

---

## 📝 Notes & Dependencies

### Dependencies Between Issues:
- Issue #4 (Streaming) should be fixed first - affects how other fixes are perceived
- Issue #2 (Table Formatting) can be done in parallel with Issue #4
- Issue #1 (Verbosity) easier after Issue #4 is fixed
- Issue #3 (Limits) is independent and can be done anytime

### Configuration Changes Needed:
```python
# config/settings.py - ADD THESE
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Response Formatting (Issue #1, #2)
    verbose_mode: bool = False  # Show technical details
    max_table_rows: int = 50    # Pagination threshold
    table_format: str = "markdown"  # or "html"
    
    # Execution Control (Issue #3)
    max_retries_per_query: int = 3
    fallback_model: str = "llama3.2:3b"
    enable_fallback: bool = True
    api_quota_limit: int = 1000
    
    # Streaming (Issue #4)
    enable_streaming: bool = True
    stream_heartbeat_interval: int = 30  # seconds
```

---

## 🚀 Ready to Start?

When ready to begin, tell me:
**"Let's fix Issue #[number]"**

And I'll create the detailed implementation with code files!

---

**Current Status:** All issues documented, ready to start fixing
**Next Action:** Choose which issue to fix first (recommend #4)
**Estimated Total Time:** 12-16 hours across all issues
