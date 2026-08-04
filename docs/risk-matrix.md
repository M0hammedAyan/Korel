# KORAL Formal Risk Matrix

## 1. Comprehensive Risk Register

| ID | Risk | Category | Probability | Impact | Severity | Affected Services | Mitigation Strategy | Priority | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | Internal microservices listening without API auth headers | Security | High | Critical | High | `sandbox-executor`, `remediation-planner`, `approval-engine`, `verification-engine`, `notifier`, `ai-engine` | Mount shared FastAPI dependency enforcing `X-API-Key` validation mapped against backend secret. | P0 | Open | `sandbox-executor/main.py:284` |
| R-02 | `backend/models.py` SQLAlchemy schema diverges from `backend/database.py` actual tables | Architecture | High | High | High | `backend` | Migrate full route layer to single ORM/Alembic-controlled schema. | P1 | Open | `backend/models.py:1-105` vs `backend/database.py:120-242` |
| R-03 | Single-node Redis configuration creates SPOF for rate-limiting | Reliability | Medium | Medium | Medium | `backend` | Enable Redis Sentinel or Cluster inside `docker-compose.yml`. | P1 | Open | `docker-compose.yml:144-157` |
| R-04 | Default passwords hardcoded in `docker-compose.yml` | Security | High | High | High | All services (via Postgres) | Generate ephemeral secrets on initial cluster bootstrap. | P1 | Open | `docker-compose.yml:169` |
| R-05 | Backend startup doesn't validate required `JWT_SECRET` or DB connect loss | Reliability | Medium | High | Medium | `backend` | Implement a Pydantic `BaseSettings` readiness gate on `lifespan` startup. | P2 | Open | `backend/main.py:128` |
| R-06 | Synchronous database calls in async context (dev mode) | Performance | High | Low | Low | `backend` (dev) | Switch dev mode to PostgreSQL container. | P2 | Open | `backend/database.py:251-272` |
| R-07 | `in-memory execution_store` in `sandbox-executor` | Reliability | Medium | High | Medium | `sandbox-executor` | Persist executions to `execution_log` table. | P1 | Open | `sandbox-executor/main.py:119` |
| R-08 | LLM cost / rate-limit exposure to OpenAI / Anthropic | Operations | High | High | High | `ai-engine` | Implement internal prompt caching layer, configurable budget limits. | P2 | Open | `ai_engine/main.py:135-169` |
| R-09 | Isolation Forest re-fits model on every call | Performance | High | Medium | High | `correlation-engine` | Implement incremental `partial_fit()` style wrapper or cache scoring matrix. | P2 | Open | `correlation-engine/ai_core/anomaly.py:101-148` |
| R-10 | Legacy endpoints in `approval-engine` complicate authentication boundaries | Security | Low | Medium | Low | `approval-engine` | Force deprecation dates on legacy routes, restrict access to admin scopes. | P3 | Open | `approval-engine/main.py:174-181` |
