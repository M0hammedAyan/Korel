# Project State

## Meta
- Generated: 2026-07-17
- Source: Graphify (commit a696d68e) + manual verification
- Freshness: Stale if HEAD differs from `a696d68e`

## Overview

KORAL is an AI-powered Kubernetes AIOps and Observability Platform.
Detect -> Correlate -> Plan -> Approve -> Execute -> Verify -> Audit -> Alert

## Completion Estimate

**Overall: ~78%**

| Module | Completion | Status |
|---|---|---|
| Backend API (FastAPI) | 90% | Feature Complete |
| Frontend (React/TypeScript/Vite) | 80% | Functional |
| Correlation Engine | 85% | Feature Complete |
| AI Engine (GPT/Claude) | 85% | Feature Complete |
| Remediation Planner | 80% | Functional |
| Approval Engine | 85% | Feature Complete |
| Sandbox Executor | 80% | Functional |
| Verification Engine | 80% | Functional |
| Notifier (Slack/Email/Telegram) | 85% | Feature Complete |
| Agents (CPU/Memory/Log/Storage) | 75% | Functional |
| ML/Isolation Forest | 90% | Feature Complete |
| Database Layer | 85% | Feature Complete |
| Alembic Migrations | 80% | Functional |
| Authentication/RBAC | 90% | Feature Complete |
| Multi-tenancy | 85% | Feature Complete |
| Multi-cluster Federation | 80% | Functional |
| Helm Charts | 85% | Feature Complete |
| mTLS | 85% | Feature Complete |
| SLO/SLA Platform | 80% | Functional |
| Audit Logging | 90% | Feature Complete |
| Grafana Dashboards | 85% | Feature Complete |
| Prometheus/AlertManager | 85% | Feature Complete |
| Load Tests (Locust) | 80% | Functional |
| Integration Tests | 75% | Functional |
| SBOM/Supply Chain | 80% | Functional |
| CI/CD (GitHub Actions) | 85% | Feature Complete |
| User Management API | 80% | Functional |
| WebSocket RBAC | 85% | Feature Complete |
| Rate Limiting (Redis) | 80% | Functional |

## Completed Services

- backend (port 8000)
- correlation-engine (port 8005)
- ai-engine (port 8006)
- remediation-planner (port 8007)
- approval-engine (port 8008)
- sandbox-executor (port 8009)
- verification-engine (port 8010)
- notifier (port 8011)
- prometheus (port 9090)
- grafana (port 3001)
- alertmanager (port 9093)
- postgres (port 5432)
- pgbouncer (port 6432)

## Implemented APIs

- /anomalies - Ingest and list anomalies
- /incidents - List incidents
- /correlations - List correlations
- /graph - Graph data
- /fixes - Fix history, stats, recording
- /feedback - Feedback loop
- /ai - AI engine proxy
- /audit - Audit log query
- /remediation - Full remediation workflow
- /slo - SLO metrics
- /health - Liveness/readiness probes
- /metrics - Prometheus metrics
- /ws/live - WebSocket real-time events

## Known Gaps

- Frontend test coverage is minimal
- Some services lack comprehensive unit tests
- E2E testing pipeline not fully automated
- Performance benchmarks not integrated into CI
- Some API routes lack OpenAPI response models
- Error handling in some edge services is inconsistent
