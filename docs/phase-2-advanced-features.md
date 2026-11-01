# Phase 2: Advanced Features (Production-Ready)

**Version:** v0.7.0
**Duration:** 2 weeks
**Status:** In Progress
**Previous:** Phase 1 (MVP) ✅ Complete

---

## Overview

Transform PGSync Admin from MVP to production-grade platform with scheduling, alerting, health monitoring, and operational features.

---

## Goals

1. **Automated Scheduling** — Recurring syncs via cron expressions
2. **Alert System** — Multi-channel notifications (Telegram, email, webhook)
3. **Health Monitoring** — Auto-restart, failure detection, resource tracking
4. **Configuration Templates** — Pre-built configs for common patterns
5. **Audit Logging** — Track all user actions and system events
6. **Performance Optimization** — Query caching, connection pooling

---

## Sub-Phases

### **Phase 2a: Scheduler & Jobs (3 days)**

**Scope:**
- Cron-based recurring execution scheduler
- Job queue with priority levels
- Retry logic with exponential backoff
- Concurrent execution limits
- Job cancellation and pause

**Deliverables:**
- `SchedulerService` (APScheduler-based)
- `jobs` table (SQLite)
- Job CRUD API endpoints (5 routes)
- Frontend job management page
- Cron expression builder UI

**Backend Routes:**
```
POST   /api/jobs              — Create scheduled job
GET    /api/jobs              — List all jobs
GET    /api/jobs/{id}         — Get job details
PATCH  /api/jobs/{id}         — Update job (pause/resume)
DELETE /api/jobs/{id}         — Delete job
POST   /api/jobs/{id}/run     — Trigger immediate run
```

**Database Schema:**
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    config_id INTEGER NOT NULL,
    cron_expression TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    next_run TIMESTAMP,
    last_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    retry_on_failure BOOLEAN DEFAULT TRUE,
    max_retries INTEGER DEFAULT 3,
    notification_channels TEXT, -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES configurations(id)
);
```

---

### **Phase 2b: Alert System (2 days)**

**Scope:**
- Multi-channel notification service
- Alert rules and thresholds
- Telegram bot integration
- Email via SMTP
- Webhook delivery
- Alert history and deduplication

**Deliverables:**
- `AlertService` with channel adapters
- `alerts` table (SQLite)
- Alert configuration UI
- Test alert functionality
- Alert templates (success, failure, warning)

**Backend Routes:**
```
POST   /api/alerts/test       — Send test alert
GET    /api/alerts/history    — Alert history
POST   /api/alerts/config     — Configure alert channels
```

**Notification Channels:**
- Telegram (via bot token)
- Email (SMTP)
- Webhook (POST JSON)
- Log file (fallback)

---

### **Phase 2c: Health Monitoring & Auto-Recovery (2 days)**

**Scope:**
- Process health checks (CPU, memory, status)
- Auto-restart on failure
- Resource usage thresholds
- Dead process detection
- Execution timeout enforcement
- System metrics dashboard

**Deliverables:**
- `HealthMonitor` service (background thread)
- `/api/health` endpoint
- Auto-restart logic in ExecutionOrchestrator
- Frontend health dashboard
- Resource usage charts

**Backend Routes:**
```
GET    /api/health            — System health status
GET    /api/health/processes  — All running processes
POST   /api/health/restart    — Manual restart
```

**Health Checks:**
- Process alive check (every 30s)
- CPU usage < 80%
- Memory usage < 2GB per process
- Execution timeout (configurable per config)
- ClickHouse connection status

---

### **Phase 2d: Configuration Templates (1 day)**

**Scope:**
- Pre-built config templates
- Template marketplace
- Template variables (e.g., {{DB_HOST}})
- One-click deployment
- Template versioning

**Deliverables:**
- `templates` table (SQLite)
- Template CRUD API
- Frontend template selector
- 5 built-in templates (e-commerce, analytics, logs, events, full-db)

**Backend Routes:**
```
GET    /api/templates         — List templates
GET    /api/templates/{id}    — Get template
POST   /api/templates         — Create custom template
POST   /api/configs/from-template — Create config from template
```

**Built-in Templates:**
1. **E-commerce CDC** — orders, products, customers, inventory
2. **Analytics Events** — user_events, page_views, conversions
3. **Application Logs** — logs, errors, audit_trail
4. **Full Database Sync** — All tables (batch only)
5. **Custom Starter** — Blank template with best practices

---

### **Phase 2e: Audit Logging & Security (2 days)**

**Scope:**
- Audit trail for all operations
- User action logging
- Configuration change history (enhanced)
- Security event tracking
- Export audit logs

**Deliverables:**
- `audit_logs` table (SQLite)
- Audit logging middleware
- Frontend audit log viewer
- Filter by user, action, resource
- CSV export

**Backend Routes:**
```
GET    /api/audit             — Query audit logs
GET    /api/audit/export      — Export as CSV
```

**Tracked Events:**
- Configuration created/updated/deleted
- Execution started/stopped
- Job created/paused/deleted
- Alert sent
- System settings changed
- Health check failures

---

### **Phase 2f: Performance Optimization (2 days)**

**Scope:**
- Query result caching (Redis optional)
- Connection pooling (PostgreSQL, ClickHouse)
- Batch query optimization
- Frontend lazy loading
- API response compression
- Database indexing

**Deliverables:**
- Connection pool configuration
- Query cache decorator
- Frontend pagination for large lists
- Gzip compression middleware
- Performance benchmarks

**Optimizations:**
- Cache config list (5min TTL)
- Cache discovery results (10min TTL)
- Lazy load execution logs (pagination)
- Compress API responses >1KB
- Add indexes on frequently queried columns

---

## Technology Stack Updates

**Backend Dependencies (add to pyproject.toml):**
```toml
apscheduler = "^3.10.0"        # Job scheduling
python-telegram-bot = "^20.0"  # Telegram alerts
aiosmtplib = "^3.0.0"          # Async email
redis = { version = "^5.0.0", optional = true }  # Caching (optional)
```

**Frontend Dependencies (add to package.json):**
```json
"cron-parser": "^4.9.0",       // Cron expression validation
"react-cron-generator": "^2.0.0"  // Cron UI builder (adapt for Solid)
```

---

## Database Migrations

**New Tables:**
1. `jobs` — Scheduled job definitions
2. `alerts` — Alert configuration and history
3. `templates` — Configuration templates
4. `audit_logs` — Audit trail
5. `health_checks` — Health check history

**Schema Evolution:**
- Add `alert_channels` column to `configurations`
- Add `timeout_seconds` column to `configurations`
- Add `auto_restart` column to `configurations`

---

## Success Criteria

✅ **Scheduler:**
- Jobs run on schedule (cron accuracy ±10s)
- Retry logic handles transient failures
- Concurrent execution limits enforced

✅ **Alerts:**
- Notifications delivered <5s after event
- Multi-channel delivery working
- Alert deduplication prevents spam

✅ **Health Monitoring:**
- Auto-restart recovers failed processes
- Resource thresholds prevent OOM
- Health dashboard shows real-time status

✅ **Templates:**
- 5 built-in templates available
- Template deployment <30s
- Variables properly substituted

✅ **Audit Logs:**
- All critical actions logged
- Logs queryable and exportable
- No PII in logs (passwords masked)

✅ **Performance:**
- API response time <200ms (p95)
- Frontend initial load <2s
- Support 50+ concurrent executions

---

## Implementation Order

1. **Phase 2a** — Scheduler (foundation for automation)
2. **Phase 2b** — Alerts (operational visibility)
3. **Phase 2c** — Health Monitoring (reliability)
4. **Phase 2d** — Templates (ease of use)
5. **Phase 2e** — Audit Logging (compliance)
6. **Phase 2f** — Performance (scale)

---

## Files to Create/Modify

**Backend (estimated 2,500 lines):**
- `backend/services/scheduler_service.py` (250 lines)
- `backend/services/alert_service.py` (200 lines)
- `backend/services/health_monitor.py` (180 lines)
- `backend/routes/jobs.py` (300 lines)
- `backend/routes/alerts.py` (150 lines)
- `backend/routes/health.py` (120 lines)
- `backend/routes/templates.py` (200 lines)
- `backend/routes/audit.py` (150 lines)
- `backend/models/job.py` (80 lines)
- `backend/models/alert.py` (70 lines)
- `backend/models/template.py` (60 lines)
- `backend/models/audit_log.py` (60 lines)

**Frontend (estimated 1,800 lines):**
- `src/pages/jobs.tsx` (280 lines)
- `src/pages/job-form.tsx` (250 lines)
- `src/pages/alerts.tsx` (220 lines)
- `src/pages/health.tsx` (240 lines)
- `src/pages/templates.tsx` (200 lines)
- `src/pages/audit.tsx` (200 lines)
- `src/components/cron-builder.tsx` (180 lines)
- `src/components/health-chart.tsx` (150 lines)

**ALL FILES WILL FOLLOW CHUNKED WRITE PROTOCOL ≤300 LINES**

---

## Risk Mitigation

**Risk:** APScheduler conflicts with Robyn async runtime
**Mitigation:** Run scheduler in separate thread, use thread-safe job queue

**Risk:** Alert spam on cascade failures
**Mitigation:** Alert deduplication window (5min), rate limiting

**Risk:** Auto-restart loops (restart → fail → restart)
**Mitigation:** Max 3 restarts per hour, exponential backoff

**Risk:** Performance degradation with many jobs
**Mitigation:** Job queue with priority, max concurrent limit

---

## Timeline

- **Phase 2a:** Days 1-3 (Scheduler)
- **Phase 2b:** Days 4-5 (Alerts)
- **Phase 2c:** Days 6-7 (Health)
- **Phase 2d:** Day 8 (Templates)
- **Phase 2e:** Days 9-10 (Audit)
- **Phase 2f:** Days 11-12 (Performance)
- **Testing:** Days 13-14 (End-to-end)

**Total:** 14 days (2 weeks)

---

## Next: Phase 3 (Enterprise Features)

- Multi-user authentication (JWT)
- Role-based access control (RBAC)
- API rate limiting
- Data encryption at rest
- Compliance reporting (GDPR, SOC2)
- White-label branding

---

**Ready to start Phase 2a (Scheduler)?** 🚀
