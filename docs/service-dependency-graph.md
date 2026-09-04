# KORAL Service Dependency Graph

## 1. Overview
This document maps out the static and runtime dependencies across all microservices, frontend applications, databases, external APIs, and infrastructure components in the KORAL platform.

---

## 2. Complete Dependency Map (ASCII)

```
[ Frontend (React/Vite) ]
       │
       │ HTTP / WebSocket (X-API-Key / JWT)
       ▼
[ Backend Core (FastAPI:8000) ]
       │
       ├──► [ PostgreSQL / PgBouncer:6432 ] (State Persistence)
       ├──► [ Redis:6379 ] (Rate Limiting & Caching)
       │
       ├──► [ Correlation Engine (8005) ] ──► [ Isolation Forest Engine ]
       │
       ├──► [ AI Engine (8006) ] ───────────► [ OpenAI API / Anthropic API ]
       │
       ├──► [ Remediation Planner (8007) ] ─► [ Kubernetes API (in-cluster) ]
       │
       ├──► [ Approval Engine (8008) ] ─────► [ SMTP Mail Server ]
       │
       ├──► [ Sandbox Executor (8009) ] ────► [ Kubectl CLI / K8s Cluster ]
       │
       ├──► [ Verification Engine (8010) ] ─► [ Prometheus (9090) ]
       │
       └──► [ Notifier (8011) ] ────────────► [ Telegram API / SMTP ]

[ Metric Agents (CPU:8001, Mem:8002, Storage:8003, Log:8004) ]
       │
       ├──► [ Prometheus (9090) ] (Metric Scrape Target)
       └──► [ Backend Core (8000) ] (POST /anomalies)

[ Monitoring Infrastructure ]
       ├── [ Prometheus (9090) ] ──► Scrapes all service /metrics endpoints
       ├── [ Grafana (3001) ] ────► Queries Prometheus (9090)
       └── [ AlertManager (9093) ]► Routes Prometheus Alerts ──► [ Notifier (8011) ]
```

---

## 3. Directional Service Interconnection Table

| Source Service | Target Service / Component | Protocol / Port | Purpose | Evidence |
|---|---|---|---|---|
| Frontend | Backend | HTTP/WS :8000 | Core API calls & real-time WS streaming | `frontend/src/api/client.ts` |
| Metric Agents | Backend | HTTP :8000 | Ingest telemetry & anomalies (`POST /anomalies`) | `agents/base_agent.py` |
| Metric Agents | Prometheus | HTTP :8001-8004 | Expose `/metrics` endpoint for scraping | `agents/base_agent.py` |
| Backend | PostgreSQL / PgBouncer | TCP :5432 / :6432 | Primary data store | `backend/database.py` |
| Backend | Redis | TCP :6379 | Rate limiting & token buckets | `backend/rate_limit_redis.py` |
| Backend | Correlation Engine | HTTP/HTTPS :8005 | Forward raw anomaly for correlation | `backend/main.py`, `backend/routes/correlations.py` |
| Backend | AI Engine | HTTP/HTTPS :8006 | Incident root-cause analysis proxy | `backend/main.py`, `backend/routes/ai.py` |
| Backend | Remediation Planner | HTTP/HTTPS :8007 | Plan creation & validation | `backend/routes/remediation.py` |
| Backend | Approval Engine | HTTP/HTTPS :8008 | Request/query approval state | `backend/routes/remediation.py` |
| Backend | Sandbox Executor | HTTP/HTTPS :8009 | Execute validated remediation commands | `backend/routes/remediation.py` |
| Backend | Verification Engine | HTTP/HTTPS :8010 | Baseline & post-fix metric validation | `backend/routes/remediation.py` |
| Backend | Notifier | HTTP/HTTPS :8011 | Trigger incident & remediation notifications | `backend/routes/remediation.py` |
| AI Engine | OpenAI API | HTTPS :443 | GPT-4o LLM analysis | `ai_engine/main.py` |
| AI Engine | Anthropic API | HTTPS :443 | Claude-3.5-Sonnet fallback LLM | `ai_engine/main.py` |
| AI Engine | Backend | HTTP/HTTPS :8000 | Store AI-recommended fixes (`POST /fixes/record`) | `ai_engine/main.py` |
| Remediation Planner | Kubernetes API | HTTPS :6443 | Discover pods, deployments, nodes | `remediation-planner/main.py` |
| Remediation Planner | AI Engine | HTTP/HTTPS :8006 | Enrich reasoning with LLM output | `remediation-planner/main.py` |
| Approval Engine | SMTP Server | TCP :25 / :587 / :1025 | Dispatch approval email requests | `approval-engine/main.py` |
| Sandbox Executor | Kubernetes Cluster | Subprocess / CLI | Execute allowlisted `kubectl` commands | `sandbox-executor/main.py` |
| Verification Engine | Prometheus | HTTP :9090 | Query metric baselines & pre/post values | `verification-engine/main.py` |
| Notifier | Telegram Bot API | HTTPS :443 | Send Telegram alerts | `notifier/notification/telegram.py` |
| Notifier | Telegram / SMTP | HTTPS / SMTP | Send incident alerts | `notifier/main.py` |

---

## 4. Shared Utilities & Internal Python Package Dependencies

```
                          [ shared/mtls.py ]
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      │                            │                            │
      v                            v                            v
[ backend/main.py ]      [ ai_engine/main.py ]      [ verification-engine/main.py ]
(Provides mTLS SSLContext & AsyncClient for all HTTP/HTTPS microservice calls)
```

- **`shared/mtls.py`**: Inter-service mutual TLS validation module. Imported by `backend`, `ai_engine`, `correlation-engine`, `remediation-planner`, `approval-engine`, `sandbox-executor`, `verification-engine`, `notifier`.
- **`database/pool.py`**: Thread-safe PostgreSQL connection pooling module using `psycopg2.pool.ThreadedConnectionPool`. Imported by `backend/database.py`.

---

## 5. Third-Party Python Package Inventory

```
+-----------------------------------------------------------------------------------+
| Core Web & Network Stack:                                                         |
| - fastapi==0.111.0          (Web framework across all microservices)              |
| - uvicorn[standard]==0.29.0 (ASGI Web Server)                                     |
| - httpx==0.27.0             (Async HTTP Client for internal microservice calls)   |
| - pydantic==2.7.1           (Data validation & settings management)               |
+-----------------------------------------------------------------------------------+
| Database & ORM Stack:                                                             |
| - psycopg2-binary==2.9.12   (PostgreSQL database driver)                            |
| - SQLAlchemy==2.0.49        (ORM framework)                                       |
| - alembic==1.13.1           (Database migration tool)                             |
| - redis==5.0.4              (Redis client for rate-limiting)                      |
+-----------------------------------------------------------------------------------+
| Observability & Resilience Stack:                                                 |
| - prometheus-client==0.17.0 (Prometheus metrics exporter)                         |
| - opentelemetry-api==1.25.0 (Tracing API)                                         |
| - opentelemetry-sdk==1.25.0 (Tracing SDK)                                         |
| - pybreaker==1.2.0          (Circuit breaker pattern implementation)              |
| - tenacity==9.0.0           (Retry logic utility)                                 |
+-----------------------------------------------------------------------------------+
| Machine Learning & Math Stack:                                                    |
| - scikit-learn==1.4.2       (Isolation Forest anomaly detection)                  |
| - numpy==1.26.4             (Array mathematics & numerical transformations)        |
+-----------------------------------------------------------------------------------+
```

---

## 6. External Dependency Risks & Resilience Policies

1. **LLM API Availability (OpenAI / Anthropic)**:
   - *Risk*: Third-party API rate limits, downtime, or network latency.
   - *Mitigation*: Multi-tier fallback pattern in `ai_engine/main.py`: GPT-4o -> Claude 3.5 Sonnet -> Deterministic Rule Engine.
2. **Prometheus Scraping Interruption**:
   - *Risk*: Prometheus service outage affects `verification-engine` pre/post fix validation.
   - *Mitigation*: `verification-engine` defaults to `inconclusive` status rather than throwing uncaught exceptions.
3. **Kubernetes API Unavailability**:
   - *Risk*: In-cluster service account token failure or API server downtime.
   - *Mitigation*: `remediation-planner` falls back to default namespaces and generic pod name extraction rules when K8s API queries fail.
