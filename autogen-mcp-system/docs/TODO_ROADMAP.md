# autogen-mcp-system - Feature Roadmap & To-Do List

**Last Updated:** December 9, 2024

---

## ✅ Completed Features

- [x] Multi-agent orchestration (MagenticOne)
- [x] Database connectivity (MS SQL Server with retry logic)
- [x] SQL agent with database awareness (directive, no credential asking)
- [x] Two-tier routing (complex vs simple tasks)
- [x] Message filtering (mostly clean responses)
- [x] OpenWebUI integration with streaming
- [x] LDAP authentication (Bearer + X-API-Key)
- [x] Conversation context (multi-turn conversations)
- [x] Max turns = 10 (prevents loops, especially qwen3-vl)
- [x] General Assistant Team (math, conversions, knowledge)
- [x] Data Analysis Team (SQL + Analysis + Validation)

---

## 🚧 Ready to Deploy (Created but Not Deployed)

- [ ] **Model fallback on rate limits** - Auto-switch to qwen3-vl when gpt-oss:120b-cloud hits limit
  - Files ready: `utils_model_manager.py`, integration guide
  - Estimated deployment: 10 minutes
  - Priority: HIGH

- [ ] **Usage tracking** - Integrated with model manager
  - Tracks model usage, switches, failures
  - Logs to `logs/model_usage.json`
  - Priority: HIGH

---

## 🎯 High Priority (Do First)

### 1. Fix Remaining TextMessage Wrappers
- **Status:** IN PROGRESS
- **Estimated Time:** 30 minutes
- **Priority:** HIGH
- **Description:** Data Analysis Team still shows some TextMessage wrappers in responses
- **Impact:** Clean, professional responses
- **Tasks:**
  - [ ] Improve message filtering regex
  - [ ] Add better content extraction for complex responses
  - [ ] Test with database queries
  - [ ] Verify no wrappers appear

### 2. Query Result Pagination
- **Status:** NOT STARTED
- **Estimated Time:** 1-2 hours
- **Priority:** HIGH
- **Description:** Large result sets (100+ rows) overwhelm UI
- **Impact:** Prevents browser crashes, better UX for big data
- **Tasks:**
  - [ ] Add result chunking to SQL tool
  - [ ] Implement pagination controls (Next/Previous/Jump)
  - [ ] Add row count display
  - [ ] Test with large datasets (1000+ rows)
  - [ ] Add user preference for page size

### 3. Better Error Messages
- **Status:** NOT STARTED
- **Estimated Time:** 1 hour
- **Priority:** HIGH
- **Description:** Users see technical stack traces
- **Impact:** Professional error handling
- **Tasks:**
  - [ ] Create error message mapping
  - [ ] Wrap technical errors with friendly messages
  - [ ] Add suggestions for common errors
  - [ ] Add "try again" / "contact support" guidance
  - [ ] Log technical details but show friendly message to user

### 4. Session Persistence
- **Status:** NOT STARTED
- **Estimated Time:** 2-3 hours
- **Priority:** HIGH
- **Description:** Conversations lost on server restart
- **Impact:** Users can continue conversations after restart
- **Tasks:**
  - [ ] Add conversation storage (SQLite or Redis)
  - [ ] Store conversation history per user
  - [ ] Restore context on server restart
  - [ ] Add conversation expiry (7 days?)
  - [ ] Add conversation list/search endpoint

---

## 🔄 Medium Priority (Do Second)

### 5. Export Query Results
- **Status:** NOT STARTED
- **Estimated Time:** 2 hours
- **Priority:** MEDIUM
- **Description:** Download results as CSV, Excel, JSON
- **Impact:** Users can work with data in Excel, other tools
- **Tasks:**
  - [ ] Add export button to SQL results
  - [ ] Implement CSV export
  - [ ] Implement Excel export (openpyxl)
  - [ ] Implement JSON export
  - [ ] Add metadata (query, timestamp, user)
  - [ ] Add filename with timestamp

### 6. Query Templates
- **Status:** NOT STARTED
- **Estimated Time:** 2 hours
- **Priority:** MEDIUM
- **Description:** Pre-built queries users can select
- **Impact:** Faster access to common queries
- **Tasks:**
  - [ ] Design template structure (JSON)
  - [ ] Create common templates (sales, customers, inventory)
  - [ ] Add parameter support (date ranges, filters)
  - [ ] UI for selecting templates
  - [ ] Allow users to save custom templates

### 7. User Preferences
- **Status:** NOT STARTED
- **Estimated Time:** 2 hours
- **Priority:** MEDIUM
- **Description:** Remember user's preferred settings
- **Impact:** Personalized experience
- **Tasks:**
  - [ ] Add preferences storage (per user)
  - [ ] Output format preference (detailed vs summary)
  - [ ] Page size preference
  - [ ] Theme preference (if applicable)
  - [ ] Default database preference (for multi-DB)

### 8. Scheduled Queries
- **Status:** NOT STARTED
- **Estimated Time:** 3-4 hours
- **Priority:** MEDIUM
- **Description:** Run queries on schedule, email results
- **Impact:** Automated reporting
- **Tasks:**
  - [ ] Add scheduler (APScheduler or Celery)
  - [ ] Create scheduled query configuration
  - [ ] Add email integration (SMTP)
  - [ ] Format results for email
  - [ ] Add schedule management UI
  - [ ] Add error notifications

### 9. Multi-Database Support
- **Status:** NOT STARTED
- **Estimated Time:** 3-4 hours
- **Priority:** MEDIUM
- **Description:** Connect to multiple databases
- **Impact:** Query across different data sources
- **Tasks:**
  - [ ] Add database configuration management
  - [ ] Update SQL agent to handle multiple connections
  - [ ] Add database selection in queries
  - [ ] Test with different DB types (PostgreSQL, MySQL)
  - [ ] Add connection pooling

---

## 🎨 Low Priority / Nice to Have (Do Later)

### 10. Web Research Team
- **Status:** NOT STARTED
- **Estimated Time:** 4-6 hours
- **Priority:** LOW
- **Description:** Add internet search capability
- **Impact:** Answer questions requiring web data
- **Tasks:**
  - [ ] Choose search API (Google, Bing, DuckDuckGo)
  - [ ] Create web_search_tool
  - [ ] Create WebSearchAgent
  - [ ] Create SummarizerAgent
  - [ ] Add to routing logic
  - [ ] Test with various queries

### 11. Calendar Integration
- **Status:** NOT STARTED
- **Estimated Time:** 4-6 hours
- **Priority:** LOW
- **Description:** Connect to Outlook/Google Calendar
- **Impact:** Schedule meetings, check availability
- **Tasks:**
  - [ ] Choose API (Microsoft Graph or Google Calendar)
  - [ ] Implement authentication flow
  - [ ] Create calendar tools
  - [ ] Create SchedulerAgent
  - [ ] Create ConflictCheckerAgent
  - [ ] Add to routing logic

### 12. Query Result Visualization
- **Status:** NOT STARTED
- **Estimated Time:** 4-6 hours
- **Priority:** LOW
- **Description:** Charts and graphs from query results
- **Impact:** Visual data analysis
- **Tasks:**
  - [ ] Choose charting library (Chart.js, Plotly)
  - [ ] Detect chartable data (time series, categories)
  - [ ] Auto-generate appropriate chart types
  - [ ] Add chart customization options
  - [ ] Integrate with OpenWebUI

### 13. Query Optimization Suggestions
- **Status:** NOT STARTED
- **Estimated Time:** 3-4 hours
- **Priority:** LOW
- **Description:** SQL agent suggests performance improvements
- **Impact:** Faster queries, better database performance
- **Tasks:**
  - [ ] Analyze query execution plans
  - [ ] Detect missing indexes
  - [ ] Suggest query rewrites
  - [ ] Estimate performance impact
  - [ ] Add optimization agent

### 14. Audit Logging
- **Status:** NOT STARTED
- **Estimated Time:** 2 hours
- **Priority:** LOW
- **Description:** Track who queried what, when
- **Impact:** Security, compliance, debugging
- **Tasks:**
  - [ ] Create audit log table
  - [ ] Log all queries with user, timestamp
  - [ ] Log authentication attempts
  - [ ] Log system errors
  - [ ] Add audit report generation
  - [ ] Add audit log retention policy

---

## 🏗️ Infrastructure (Do When Ready for Production)

### 15. Docker Deployment
- **Status:** NOT STARTED
- **Estimated Time:** 3-4 hours
- **Priority:** MEDIUM (for production)
- **Description:** Containerize the entire system
- **Impact:** Easy deployment, scalability
- **Tasks:**
  - [ ] Create Dockerfile for MCP server
  - [ ] Create Dockerfile for Ollama (or use official)
  - [ ] Create docker-compose.yml
  - [ ] Add environment variable management
  - [ ] Test full stack deployment
  - [ ] Add volume mounts for persistence
  - [ ] Document deployment process

### 16. Production Hardening
- **Status:** NOT STARTED
- **Estimated Time:** 4-6 hours
- **Priority:** MEDIUM (for production)
- **Description:** Security, secrets management, rate limiting
- **Impact:** Production-ready security
- **Tasks:**
  - [ ] Move secrets to environment variables / vault
  - [ ] Add rate limiting (per user, per endpoint)
  - [ ] Add HTTPS/SSL support
  - [ ] Add request validation
  - [ ] Add SQL injection protection (enhanced)
  - [ ] Add CORS configuration
  - [ ] Add health check endpoints
  - [ ] Add graceful shutdown

### 17. Monitoring Dashboard
- **Status:** NOT STARTED
- **Estimated Time:** 6-8 hours
- **Priority:** LOW (for production)
- **Description:** Grafana/Prometheus integration
- **Impact:** System observability
- **Tasks:**
  - [ ] Add Prometheus metrics endpoint
  - [ ] Track request counts, latencies
  - [ ] Track model usage, failures
  - [ ] Track database query performance
  - [ ] Create Grafana dashboards
  - [ ] Add alerting rules
  - [ ] Document dashboard usage

### 18. Load Balancing
- **Status:** NOT STARTED
- **Estimated Time:** 4-6 hours
- **Priority:** LOW (for production)
- **Description:** Multiple instances for high availability
- **Impact:** Scalability, reliability
- **Tasks:**
  - [ ] Add nginx/HAProxy load balancer
  - [ ] Make application stateless
  - [ ] Add session storage (Redis)
  - [ ] Test with multiple instances
  - [ ] Add health checks
  - [ ] Document scaling process

---

## 📊 Summary

**Total Features:** 18 (9 completed, 9 to implement)

**Estimated Total Time:** 60-80 hours

**Priority Breakdown:**
- High Priority: 4 features (~5-7 hours)
- Medium Priority: 5 features (~14-17 hours)
- Low Priority: 5 features (~17-26 hours)
- Infrastructure: 4 features (~17-24 hours)

---

## 🎯 Recommended Implementation Order

### Phase 1: Core Improvements (Week 1)
1. Fix TextMessage wrappers (30 min)
2. Deploy model fallback (10 min)
3. Query pagination (2 hours)
4. Better error messages (1 hour)
5. Session persistence (3 hours)

**Total: ~7 hours → Production-ready improvements**

### Phase 2: User Features (Week 2)
6. Export results (2 hours)
7. Query templates (2 hours)
8. User preferences (2 hours)

**Total: ~6 hours → Enhanced user experience**

### Phase 3: Advanced Features (Week 3-4)
9. Scheduled queries (4 hours)
10. Multi-database support (4 hours)
11. Audit logging (2 hours)

**Total: ~10 hours → Enterprise features**

### Phase 4: Optional Enhancements (As Needed)
12-14. Web research, calendar, visualization, etc.

### Phase 5: Production Infrastructure (Before Going Live)
15-18. Docker, hardening, monitoring, load balancing

---

## 📝 Notes

- All time estimates are for implementation only (not including testing)
- Testing should add ~30% to each estimate
- Documentation should add ~20% to each estimate
- Some features may be combined for efficiency

---

**Next Up:** Fix TextMessage Wrappers (IN PROGRESS)
