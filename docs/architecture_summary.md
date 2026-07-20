# Architecture Summary

## High-Level Architecture

```
[Agents] -> [Backend API] -> [Correlation Engine] -> [AI Engine]
                                          |                    |
                                          v                    v
                                    [Remediation Planner]  [Incident Analysis]
                                          |
                                          v
                                    [Approval Engine]
                                          |
                                          v
                                    [Sandbox Executor]
                                          |
                                          v
                                    [Verification Engine]
                                          |
                                          v
                                    [Notifier] -> Slack/Email/Telegram
```

## Data Flow

1. Agents (CPU/Memory/Log/Storage) collect K8s metrics
2. Events ingested via backend `/anomalies` endpoint
3. Correlation engine groups anomalous events into incidents
4. AI Engine analyzes incidents (GPT-4o primary, Claude fallback)
5. Remediation Planner generates fix plans from K8s discovery
6. Approval Engine manages human approval workflow
7. Sandbox Executor runs approved fix commands safely
8. Verification Engine checks Prometheus metrics pre/post fix
9. Notifier sends results via Slack/Email/Telegram
10. All actions logged to audit table

## Service Communication

- REST between services (internal Docker network)
- WebSocket for real-time dashboard updates
- mTLS in production (cert-manager)
- Redis for rate limiting and caching

## Database Architecture

- PostgreSQL (production) / SQLite (dev)
- PgBouncer for connection pooling
- Partitioned tables for anomalies and audit logs
- Read replicas for reporting queries

## Frontend Architecture

- React 18 + TypeScript + Vite
- Recharts for dashboard charts
- D3 for dependency graph visualization
- WebSocket for real-time updates

## Security Architecture

- API Key authentication on all routes
- JWT support available
- RBAC (VIEWER/OPERATOR/ADMIN)
- mTLS between internal services
- Rate limiting via Redis
- Multi-tenancy namespace isolation
