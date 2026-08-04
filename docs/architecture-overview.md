# KORAL Enterprise Architecture Overview

## 1. System Mission & Scope
KORAL is an autonomous, Kubernetes-native AI observability platform. It ingests high-frequency metrics from distributed workloads, detects anomalous behavior via Isolation Forest, correlates multi-pod incidents using metric-priority rules, plans AI-driven remediations (GPT-4o / Claude), enforces role-based approvals, executes allowlisted commands in sandboxed environments, and validates fix effectiveness against Prometheus metric baselines.

---

## 2. Executive Summary & Quality Scoring

| Category | Score / 100 | Key Driver |
|---|---|---|
| **Architecture Maturity** | 82 | Clean 10+ microservice decomposition, clear single-responsibility boundaries |
| **Security Maturity** | 76 | End-to-end RBAC (VIEWER/OPERATOR/ADMIN), mTLS support, argv-only execution sandbox; gap: internal microservices default to HTTP without auth token verification |
| **Reliability Maturity** | 80 | Resilience fallback to synthetic modes, PostgreSQL PgBouncer pooling, Redis rate limiting |
| **Operational Maturity** | 78 | Full Prometheus metrics, auto-provisioned Grafana dashboards, Helm charts |
| **Overall Weighted Score** | **79.0** | **Production-Ready Core with Internal Hardening Gaps** |

---

## 3. Top Architectural Strengths
1. **Sandboxed & Constrained Execution**: Commands executed via `sandbox-executor` never use shell strings (`shell=False`). Parameters are strictly validated against standard Kubernetes naming patterns (`_SAFE_NAME_RE`) and replica count limits.
2. **Layered AI Logic**: Primary GPT-4o integration falls back to Claude-3.5-Sonnet, which falls back to a deterministic time-aware rule engine (suppressing known weekly/seasonal/batch spikes).
3. **Database Flexibility**: Native abstraction supporting SQLite for lightweight dev/testing and PostgreSQL via PgBouncer transaction pooling with read replicas for production.
4. **WebSocket RBAC & Role Filtering**: Live event streaming authenticates connections via header or query string and enforces minimum role-level routing (`WSRole.VIEWER`, `OPERATOR`, `ADMIN`).

---

## 4. Top Architectural Weaknesses & Risks
1. **Unauthenticated Internal Service Endpoints**: Microservices (e.g. `remediation-planner`, `approval-engine`, `sandbox-executor`) expose port-level HTTP endpoints without enforcing API keys or JWT tokens internally when accessed directly outside the backend proxy.
2. **Database Layer Dual-Mapping**: Legacy SQLAlchemy ORM definitions (`backend/models.py`) coexist with raw parameterised SQL queries (`backend/database.py`), creating schema divergence risks if migrations are not aligned across both paradigms.
3. **State Ephemerality in Auxiliary Engines**: `sandbox-executor` and `verification-engine` maintain internal in-memory Python dictionaries (`execution_store`, `verification_store`) alongside backend DB persistence; service restarts lose local cache state.

---

## 5. Architectural Subsystem Inventory

```
+-----------------------------------------------------------------------------------+
|                                 FRONTEND (3000)                                   |
|                          React + TypeScript + Vite + Nginx                        |
+------------------------------------------+----------------------------------------+
                                           | HTTP / WebSocket
                                           v
+-----------------------------------------------------------------------------------+
|                                 BACKEND (8000)                                    |
|              FastAPI Core API - Auth / RBAC / Audit / Rate Limit / SLO              |
+--------+------------------+------------------+------------------+-----------------+
         |                  |                  |                  |
         v                  v                  v                  v
+------------------+ +--------------+ +------------------+ +------------------+
| CORRELATION-ENG  | |  AI-ENGINE   | | REMEDIATION-PLAN | | APPROVAL-ENGINE  |
|      (8005)      | |    (8006)    | |      (8007)      | |      (8008)      |
| Isolation Forest | | GPT-4o/Claude| | Plan Generator | | Approval State |
+------------------+ +--------------+ +--------+---------+ +--------+---------+
                                               |                  |
                                               +--------+---------+
                                                        |
                                                        v
                                              +-------------------+
                                              | SANDBOX-EXECUTOR  |
                                              |      (8009)       |
                                              |  kubectl Argv-Exec|
                                              +---------+---------+
                                                        |
                                                        v
                                              +-------------------+
                                              | VERIFICATION-ENG  |
                                              |      (8010)       |
                                              | Prometheus Baseline|
                                              +-------------------+
```

### 1. Backend Core (`backend/`)
- **Port**: 8000
- **Tech Stack**: Python 3.11, FastAPI, Uvicorn, PostgreSQL / PgBouncer, Redis, OpenTelemetry, Prometheus Client.
- **Responsibilities**: Entry point for frontend & external clients. Handles X-API-Key auth, JWT validation, Redis rate-limiting (IP & API Key), Audit Logging, SLO calculations (`/slo`), User & Tenant management, WebSocket management (`/ws/live`).

### 2. Correlation Engine (`correlation-engine/`)
- **Port**: 8005
- **Tech Stack**: Python 3.11, FastAPI, scikit-learn (`IsolationForest`), NumPy.
- **Responsibilities**: Ingests raw anomalies, maintains rolling metric windows (300s default), runs Isolation Forest anomaly detection, converts decision scores to pseudo Z-scores, correlates cross-pod incidents via rule-based RCA.

### 3. AI Engine (`ai_engine/`)
- **Port**: 8006
- **Tech Stack**: Python 3.11, FastAPI, httpx, OpenAI API (GPT-4o), Anthropic API (Claude 3.5 Sonnet).
- **Responsibilities**: Evaluates incident context against time-aware patterns (e.g. Monday morning traffic surge, weekend batch jobs). Suppresses false positives, generates human-readable incident summaries.

### 4. Remediation Planner (`remediation-planner/`)
- **Port**: 8007
- **Tech Stack**: Python 3.11, FastAPI, Kubernetes Client / in-cluster Service Account.
- **Responsibilities**: Generates candidate remediation plans (e.g., `restart_pod`, `scale_deployment`, `restart_deployment`) based on incident root causes and Kubernetes cluster inspection.

### 5. Approval Engine (`approval-engine/`)
- **Port**: 8008
- **Tech Stack**: Python 3.11, FastAPI, SQLite / PostgreSQL.
- **Responsibilities**: Manages human-in-the-loop approval workflows. Sends email notifications (SMTP), tracks approval status (`pending`, `approved`, `rejected`, `expired`), enforces 30-minute approval windows.

### 6. Sandbox Executor (`sandbox-executor/`)
- **Port**: 8009
- **Tech Stack**: Python 3.11, FastAPI, `subprocess` (argv-only).
- **Responsibilities**: Safely executes allowed kubectl commands (`shell=False`). Enforces maximum blast radius (default 5 pods) and timeout limits (default 300s). Supports `DRY_RUN` mode.

### 7. Verification Engine (`verification-engine/`)
- **Port**: 8010
- **Tech Stack**: Python 3.11, FastAPI, Prometheus API Client.
- **Responsibilities**: Measures pre- and post-remediation metric baselines from Prometheus. Calculates improvement percentage and Z-score deltas to verify fix resolution.

### 8. Notifier (`notifier/`)
- **Port**: 8011
- **Tech Stack**: Python 3.11, FastAPI, httpx, SMTP, Telegram Bot API, Slack Webhook.
- **Responsibilities**: Dispatcher for multi-channel notifications (Telegram, Slack, Email) when anomalies or remediation events occur.

### 9. Edge Metrics Agents (`agents/`)
- **Ports**: 8001 (CPU), 8002 (Memory), 8003 (Storage), 8004 (Log)
- **Tech Stack**: Python 3.11, FastAPI, Prometheus Client, httpx.
- **Responsibilities**: Collect high-frequency telemetry from container metrics/Prometheus; automatically fall back to synthetic metric generation if cluster metrics are unavailable.

---

## 6. Top 20 Architectural Improvement Roadmap

1. **Internal Service Authentication (mTLS / Service Tokens)**: Enforce token header validation on all inter-service communications (`remediation-planner`, `sandbox-executor`, `approval-engine`).
2. **SQLAlchemy ORM Data Layer Standardization**: Unify raw SQL calls in `backend/database.py` with SQLAlchemy ORM models in `backend/models.py`.
3. **Database Persistence for Sandbox Executor**: Persist execution state to PostgreSQL rather than relying solely on in-memory `execution_store`.
4. **Database Persistence for Verification Engine**: Persist verification state to PostgreSQL rather than relying solely on in-memory `verification_store`.
5. **Circuit Breaker Coverage Expansion**: Wrap all microservice HTTP calls with `pybreaker` circuit breakers to prevent cascading failures.
6. **Explicit PostgreSQL Database Indexes**: Add B-tree indexes for `pod`, `namespace`, `timestamp`, and `created_at` across `anomalies` and `incidents` tables.
7. **Removal of Legacy Approval Endpoints**: Deprecate legacy synchronous endpoints in `approval-engine` in favor of RESTful `PATCH` routes.
8. **Configurable Detection Windowing**: Expose Isolation Forest parameters (`window_size`, `n_estimators`, `z_threshold`) in Helm values / environment variables.
9. **Strict OpenAPI Schema Validation**: Define explicit response models for all FastAPI routes to eliminate untyped JSON responses.
10. **Redis Cluster Integration**: Upgrade single-node Redis configuration to Redis Sentinel or Cluster mode for high availability.
11. **Dead Code Cleanup**: Audit unused modules in `system-intelligence-evaluation` and root-level scripts.
12. **Prometheus Alert Rule Standardization**: Synchronize rules in `infra/monitoring/alert-rules.yaml` with backend SLO thresholds.
13. **Graceful Degradation Metrics**: Expose Prometheus gauges for degraded state when dependency services (e.g. `ai-engine`) fail health checks.
14. **Asynchronous Database Driver Adoption**: Migrate `psycopg2` driver to `asyncpg` or `async-sqlalchemy` to eliminate thread-offloading.
15. **Helm Chart Integration Validation**: Reconcile root `helm/` charts with `charts/` sub-charts for single-command enterprise deployment.
16. **Dynamic Log Level Reconfiguration**: Implement endpoint to toggle FastAPI log levels dynamically without pod restarts.
17. **Strict Cross-Namespace Control Policies**: Enforce namespace isolation checks across all sandbox commands regardless of `ALLOW_CROSS_NAMESPACE` settings.
18. **Automated Secret Rotation**: Implement automated token rotation handlers for user API keys and JWT signing secrets.
19. **Load Test Realism Expansion**: Expand Locust scenarios to test 10,000 concurrent WebSocket connections under heavy anomaly loads.
20. **Distributed Tracing Coverage**: Instrument all downstream microservices (`correlation-engine`, `remediation-planner`) with OpenTelemetry spans.
