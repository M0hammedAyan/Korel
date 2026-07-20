# Component Inventory

## Services (Docker Compose / K8s)

| Component | Language | Port | Status | Directory |
|---|---|---|---|---|
| backend | Python/FastAPI | 8000 | Feature Complete | backend/ |
| correlation-engine | Python/FastAPI | 8005 | Feature Complete | correlation-engine/ |
| ai-engine | Python/FastAPI | 8006 | Feature Complete | ai_engine/ |
| remediation-planner | Python/FastAPI | 8007 | Feature Complete | remediation-planner/ |
| approval-engine | Python/FastAPI | 8008 | Feature Complete | approval-engine/ |
| sandbox-executor | Python/FastAPI | 8009 | Feature Complete | sandbox-executor/ |
| verification-engine | Python/FastAPI | 8010 | Feature Complete | verification-engine/ |
| notifier | Python | 8011 | Feature Complete | notifier/ |
| frontend | React/TypeScript | 5173 | Functional | frontend/ |

## Agents

| Agent | Language | Directory |
|---|---|---|
| CPU Agent | Python | agents/cpu-agent/ |
| Memory Agent | Python | agents/memory-agent/ |
| Log Agent | Python | agents/log-agent/ |
| Storage Agent | Python | agents/storage-agent/ |

## ML/AI Modules

| Module | Location | Status |
|---|---|---|
| RollingZScoreDetector | AIML/Member1_work/ai_core/anomaly.py | Functional |
| IsolationForestDetector | shared/isolation_forest.py | Production Ready |
| RRCFStreamDetector | shared/rrcf_detector.py | Functional |
| STLDecomposer | shared/stl_detector.py | Functional |
| DetectorFactory | shared/detector_factory.py | Functional |
| Correlation Engine | correlation-engine/ | Feature Complete |
| Feedback Loop | feedback/ | Functional |

## Infrastructure

| Component | Directory | Status |
|---|---|---|
| Helm Charts | charts/, helm/ | Feature Complete |
| Docker Compose | docker/ | Feature Complete |
| K8s Manifests | k8s/ | Functional |
| Grafana Dashboards | docs/grafana/ | Feature Complete |
| Alembic Migrations | alembic/ | Functional |
| CI/CD (GitHub Actions) | .github/ | Feature Complete |

## Database

| Component | Location | Status |
|---|---|---|
| Connection Pool | backend/pool.py | Feature Complete |
| Database Module | backend/database.py | Feature Complete |
| Models | backend/models.py | Feature Complete |
| Remediation DB | backend/remediation.py | Feature Complete |

## Security

| Component | Location | Status |
|---|---|---|
| RBAC | backend/rbac.py | Feature Complete |
| Authentication | backend/auth.py | Feature Complete |
| mTLS | shared/mtls.py | Feature Complete |
| Rate Limiter | backend/rate_limit_redis.py | Feature Complete |
| Multi-tenancy | backend/tenancy.py | Feature Complete |

## Testing

| Component | Location | Status |
|---|---|---|
| Integration Tests | tests/test_backend_integration.py | Functional |
| Load Tests | load_tests/ | Functional |
| User Management Tests | tests/test_user_management.py | Functional |
| Multi-tenancy Tests | tests/test_multi_tenancy.py | Functional |
| WebSocket Auth Tests | tests/ | Functional |
