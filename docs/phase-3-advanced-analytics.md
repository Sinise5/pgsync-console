# Phase 3: Advanced Analytics & Alerting

**Version:** v2.0.0
**Duration:** 4 weeks
**Status:** In Progress
**Previous:** Phase 2 (Advanced Features) ✅ Complete

---

## Overview

Add enterprise analytics, alerting, RBAC, and compliance features to complete PGSync Admin platform.

---

## Goals

1. **Advanced Reporting** — Custom dashboards + scheduled reports
2. **Alerting System** — Threshold-based rules + anomaly detection
3. **Access Control** — Role-based permissions + audit trail
4. **Data Lineage** — Visual graph of data relationships
5. **Cost Analysis** — Resource usage estimation
6. **Compliance** — Audit logs + data governance

---

## Sub-Phases

### **Phase 3a: Advanced Analytics & Custom Dashboards (1 week)**

**Deliverables:**
- Custom dashboard builder (drag-drop widgets)
- 8+ pre-built widgets (metrics, charts, tables)
- Dashboard persistence (save/load)
- Widget configuration UI
- Real-time data updates (WebSocket)
- Export dashboards (PNG, PDF)
- Dashboard sharing (link-based)

**Backend (3 files, 300 lines):**
- `Dashboard` model (SQLite)
- `DashboardWidget` model
- `dashboards_routes.py` (CRUD + widget config)

**Frontend (4 files, 250 lines):**
- `dashboards.tsx` page
- `dashboard-builder.tsx` component
- `widgets/` directory (8 widget components)
- Widget library + config UI

**API Endpoints (7 total):**
```
POST   /api/dashboards              # Create dashboard
GET    /api/dashboards              # List dashboards
GET    /api/dashboards/{id}         # Get dashboard
PUT    /api/dashboards/{id}         # Update dashboard
DELETE /api/dashboards/{id}         # Delete dashboard
POST   /api/dashboards/{id}/widgets # Add widget
PUT    /api/dashboards/{id}/widgets/{widget_id} # Update widget
```

---

### **Phase 3b: Alerting Rules & Anomaly Detection (1 week)**

**Deliverables:**
- Alert rule engine (threshold + anomaly detection)
- 10+ pre-built alert templates
- Rule evaluation scheduler
- Alert history + audit trail
- Alert suppression (during maintenance)
- Dynamic thresholds (ML-based)
- Alert correlation (group related alerts)

**Backend (4 files, 400 lines):**
- `AlertRule` model
- `AlertEvaluation` model
- `anomaly_detector.py` service
- `alerts_routes.py`

**Frontend (3 files, 200 lines):**
- `alerts.tsx` page
- `alert-rule-builder.tsx`
- Alert history table + visualization

**API Endpoints (9 total):**
```
POST   /api/alerts/rules             # Create rule
GET    /api/alerts/rules             # List rules
PUT    /api/alerts/rules/{id}        # Update rule
DELETE /api/alerts/rules/{id}        # Delete rule
POST   /api/alerts/rules/{id}/test   # Test rule
GET    /api/alerts/history           # Alert history
POST   /api/alerts/{id}/suppress     # Suppress alert
GET    /api/alerts/templates         # Pre-built templates
```

---

### **Phase 3c: RBAC & Audit Logging (1 week)**

**Deliverables:**
- Role-based access control (3 roles: admin, operator, viewer)
- Permission matrix (40+ permissions)
- Audit log (all user actions + system events)
- User management API
- Permission validator middleware
- Audit log export (compliance)
- Session audit (login, logout, IP, device)

**Backend (5 files, 350 lines):**
- `User` model
- `Role` model
- `AuditLog` model
- `rbac_service.py`
- `audit_routes.py`

**Frontend (2 files, 150 lines):**
- `audit-logs.tsx` page
- `user-management.tsx`

**API Endpoints (10 total):**
```
POST   /api/users                    # Create user
GET    /api/users                    # List users
PUT    /api/users/{id}               # Update user
DELETE /api/users/{id}               # Delete user
GET    /api/roles                    # List roles
POST   /api/audit/logs               # Get audit logs
POST   /api/audit/export             # Export audit trail
GET    /api/permissions              # List permissions
```

---

### **Phase 3d: Data Lineage & Cost Analysis (1 week)**

**Deliverables:**
- Data lineage graph (D3.js visualization)
- Lineage tracing (source → target path)
- Column-level lineage (data sensitivity marking)
- Cost calculator (storage + compute)
- Cost dashboard (monthly trends)
- Resource usage tracking
- ROI calculation

**Backend (3 files, 280 lines):**
- `lineage_service.py`
- `cost_calculator.py`
- `lineage_routes.py`

**Frontend (3 files, 220 lines):**
- `lineage.tsx` page (D3.js visualization)
- `cost-analysis.tsx`
- `cost-calculator.tsx` (interactive tool)

**API Endpoints (8 total):**
```
GET    /api/lineage/{config_id}      # Get data lineage
GET    /api/lineage/trace            # Trace lineage path
GET    /api/cost/estimate            # Estimate costs
GET    /api/cost/actual              # Actual costs
GET    /api/cost/projections         # Cost projections
POST   /api/cost/export              # Export cost report
```

---

## Database Schema Additions

### Phase 3a: Dashboards

```sql
CREATE TABLE dashboards (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  created_by INTEGER,
  created_at DATETIME,
  updated_at DATETIME,
  is_shared BOOLEAN DEFAULT 0,
  share_token TEXT
);

CREATE TABLE dashboard_widgets (
  id INTEGER PRIMARY KEY,
  dashboard_id INTEGER,
  widget_type TEXT,  -- metric, chart, table, gauge
  title TEXT,
  config JSON,  -- widget-specific config
  position INTEGER,
  FOREIGN KEY (dashboard_id) REFERENCES dashboards(id)
);
```

### Phase 3c: RBAC & Audit

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE,
  email TEXT,
  password_hash TEXT,
  role_id INTEGER,
  created_at DATETIME,
  FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE roles (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE,  -- admin, operator, viewer
  permissions JSON  -- list of permission strings
);

CREATE TABLE audit_logs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  action TEXT,  -- CREATE, UPDATE, DELETE, READ
  resource_type TEXT,  -- config, job, dashboard
  resource_id INTEGER,
  changes JSON,  -- before/after values
  timestamp DATETIME,
  ip_address TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Phase 3d: Lineage & Cost

```sql
CREATE TABLE lineage_metadata (
  id INTEGER PRIMARY KEY,
  config_id INTEGER,
  source_table TEXT,
  target_index TEXT,
  column_mappings JSON,
  sensitivity_level TEXT,  -- public, internal, confidential
  FOREIGN KEY (config_id) REFERENCES configurations(id)
);

CREATE TABLE cost_estimates (
  id INTEGER PRIMARY KEY,
  config_id INTEGER,
  storage_gb FLOAT,
  compute_cost FLOAT,
  monthly_projection FLOAT,
  calculated_at DATETIME,
  FOREIGN KEY (config_id) REFERENCES configurations(id)
);
```

---

## Implementation Order

1. **Phase 3a** (Days 1-7): Dashboards + widgets
2. **Phase 3b** (Days 8-14): Alerting rules + anomaly detection
3. **Phase 3c** (Days 15-21): RBAC + audit logging
4. **Phase 3d** (Days 22-28): Lineage + cost analysis

---

## Success Criteria

✅ All 30+ API endpoints functional
✅ Custom dashboards persist + load
✅ Alert rules evaluate on schedule
✅ All actions audited + queryable
✅ Lineage graph renders without lag
✅ Cost estimates within 10% accuracy
✅ Frontend build <150KB (gzip)
✅ E2E tests pass (all workflows)
✅ Documentation complete

---

**Maintainer:** QTI Research
**Created:** 2026-06-19
