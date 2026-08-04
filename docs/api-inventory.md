# KORAL API Inventory & Service Interaction Matrix

## 1. Service Interaction Matrix

| Source Service | Target Service | Path | Protocol | Authentication | Timeout |
|---|---|---|---|---|---|
| Backend | Correlation Engine | `GET /health` | HTTP/HTTPS | None | 2.0s |
| Backend | AI Engine | `GET /health` | HTTP/HTTPS | None | 2.0s |
| Backend | AI Engine | `POST /analyze` | HTTP/HTTPS | None | 30.0s |
| Backend | Remediation Planner | `POST /create-plan`| HTTP/HTTPS | None | 30.0s |
| Backend | Approval Engine | `POST /request-approval`| HTTP/HTTPS | None | 30.0s |
| Backend | Approval Engine | `GET /status/{id}` | HTTP/HTTPS | None | 600.0s |
| Backend | Approval Engine | `PATCH /approvals/{id}/approve` | HTTP/HTTPS | None | 10.0s |
| Backend | Approval Engine | `PATCH /approvals/{id}/reject` | HTTP/HTTPS | None | 10.0s |
| Backend | Sandbox Executor | `POST /execute` | HTTP/HTTPS | None | 600.0s |
| Backend | Verification Engine | `GET /pre-metrics` | HTTP/HTTPS | None | 10.0s |
| Backend | Verification Engine | `POST /verify` | HTTP/HTTPS | None | 600.0s |
| Backend | Notifier | `POST /notify` | HTTP/HTTPS | None | 30.0s |
| Remediation Planner| AI Engine | `POST /analyze` | HTTP/HTTPS | None | 15.0s |
| Sandbox Executor| Kubernetes API | Subprocess | kubectl binary | Node SA | 300.0s |
| Verification Engine| Prometheus API | `GET /api/v1/query`| HTTP/HTTPS | None | 10.0s |
| Agent | Prometheus API | `GET /api/v1/query`| HTTP/HTTPS | None | 5.0s |
| Agent | Backend | `POST /anomalies` | HTTP/HTTPS | None | 5.0s |
| Verification Engine| Backend | `POST /remediation/verifications` | HTTP/HTTPS | `X-API-Key` | 10.0s |
| Remediation Planner| Backend | `POST /remediation/plans` | HTTP/HTTPS | None* (bug) | 300.0s |

**Evidence**: 
- `backend/routes/remediation.py` HTTP calls to all services
- `remediation-planner/main.py:297` AI engine call, `main.py:340` Backend plan post
- `sandbox-executor/main.py:201` subprocess execution
- `verification-engine/main.py:100` Prometheus query, `main.py:218` Backend post

---

## 2. Public API Inventory (Backend Core)

**Base URL**: `http://<host>:8000`
**Authentication**: `X-API-Key: <token>` or `Authorization: Bearer <jwt>` (unless noted)
**Rate Limiting**: IP (100/min), API Key (500/min)

### Health & Metrics
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/` | None | Service info | `200 OK: {"service": "KORAL Backend", ...}` |
| GET | `/health/live` | None | Liveness probe | `200 OK: {"status": "ok", ...}` |
| GET | `/health/ready` | None | Readiness probe & downstream check | `200 OK` (Healthy) or `503` (Degraded) |
| GET | `/health` | None | Detailed health checks | `200 OK` or `503` |
| GET | `/metrics` | None | Prometheus metrics expose | `200 OK (text/plain)` |

### Real-Time Communications
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| WS | `/ws/live` | Key | Real-time event streaming | WebSocket Upgrade (role-filtered) |

### Anomalies
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| POST | `/anomalies` | Operator | Ingest telemetry/anomaly. Proxies to `/correlate` if `is_anomaly=True`. | `200 OK` or `201 Created` |
| GET | `/anomalies` | Viewer | Search historical anomalies (hours/pod/limit parameters) | `200 OK: [...]` |
| GET | `/anomalies/{pod_name}` | Viewer | Search anomalies specific to a pod | `200 OK: [...]` |

### Incidents
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/incidents` | Viewer | List incidents (limit param) | `200 OK: [...]` |
| GET | `/incidents/{id}` | Viewer | Get specific incident details | `200 OK: {...}` |

### Correlations
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/correlations` | Viewer | List correlated incidents | `200 OK: [...]` |

### SLO Metrics
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/slo/` | Viewer | Aggregate SLO data | `200 OK: {availability_percent, mttr_seconds, ...}` |
| GET | `/slo/availability`| Viewer | Raw availability metrics | `200 OK: {...}` |
| GET | `/slo/mttr` | Viewer | Raw Mean Time To Repair metrics | `200 OK: {...}` |
| GET | `/slo/detection-latency`| Viewer | Detection latency metrics | `200 OK: {...}` |
| GET | `/slo/remediation-success`| Viewer | Auto-remediation success rate | `200 OK: {...}` |
| GET | `/slo/error-budget`| Viewer | Error budget remaining | `200 OK: {...}` |

### Remediation Orchestration
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| POST | `/remediation/plans` | Operator | Create remediation plan via AI analysis | `200 OK: {...plan...}` |
| GET | `/remediation/plans` | Viewer | List remediation plans | `200 OK: {count, plans}` |
| GET | `/remediation/plans/{id}`| Viewer | Get specific plan | `200 OK: {...}` |
| POST | `/remediation/approve/{id}`| Operator| Trigger Approval Engine for a plan | `200 OK: {approval_id...}`|
| PATCH | `/remediation/approvals/{id}/approve`| Operator| Approve a pending plan | `200 OK: {...}` |
| PATCH | `/remediation/approvals/{id}/reject`| Operator| Reject a pending plan | `200 OK: {...}` |
| POST | `/remediation/execute/{id}` | **Admin** | Execute an approved plan | `200 OK: {execution_id...}` |
| POST | `/remediation/verify/{id}` | Operator | Trigger verification of a completed execution | `200 OK: {verification_id...}` |
| POST | `/remediation/notify/{id}` | Operator | Send notification via Notifier service | `200 OK: {...}` |
| GET | `/remediation/status` | Viewer | Global remediation enabled status | `200 OK: {...}` |

### Fix History & Manual Fixes
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/fixes/history`| Viewer | Get applied fix history | `200 OK: [...]` |
| GET | `/fixes/stats` | Viewer | Get fix statistics (AI vs Dev successful) | `200 OK: {...}` |
| GET | `/fixes/by-incident/{id}`| Viewer | List fixes applied to an incident | `200 OK: [...]` |
| POST | `/fixes/record` | Operator | Record a manual or AI fix | `200 OK: {...}` |

### Graph & Viz
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/graph/nodes` | Viewer | Get cluster node topology | `200 OK: [...]` |
| GET | `/graph/edges` | Viewer | Get service relationship edges | `200 OK: [...]` |

### Audit
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/audit` | **Admin** | Extract security and operational audit logs | `200 OK: [...]` |

### Users & Tenants (SaaS Features)
| Method | Path | Auth | Purpose | Response |
|---|---|---|---|---|
| GET | `/users` | Viewer | List system users | `200 OK: [...]` |
| POST | `/users` | **Admin** | Create user | `201 Created` |
| POST | `/users/invite`| **Admin** | Invite a new user (with generated token)| `200 OK` |
| GET | `/tenants` | Viewer | List tenants | `200 OK: [...]` |
| GET | `/federation` | Viewer | Cluster federation status | `200 OK: [...]` |
| GET | `/sla` | Viewer | Enterprise SLA guarantees | `200 OK: [...]` |

---

## 3. Internal Microservice APIs 
*(No authentication required by default. Bindings are inter-pod within the Kubernetes namespace.)*

### Correlation Engine (`:8005`)
- `POST /correlate` - Single anomaly correlation.
- `POST /correlate-batch` - Batch cross-pod cross-service correlation using Isolation Forest.

### AI Engine (`:8006`)
- `POST /analyze` - Determines anomaly type, generates reasoning, evaluates auto-fix mapping.
- `POST /chat` - Conversational K8s/RCA chatbot.
- `GET /activity` - Returns the last 1000 AI interactions inside a deque.

### Remediation Planner (`:8007`)
- `POST /create-plan` - Queries K8s, looks up internal allowlist, calls AI Engine, builds remediation step.
- `POST /validate-execution` - Validates payload against allowlisted schemas (blast radius limits, parameters).
- `GET /approved-commands` - Dump available remediation commands schema.

### Approval Engine (`:8008`)
- `POST /request-approval` - Sends email via SMTP and stores pending request with 30-min TTL.
- `PATCH /approvals/{id}/approve` - Modifies DB state to approved.
- `PATCH /approvals/{id}/reject` - Modifies DB state to rejected.
- `GET /status/{id}` - Verification endpoint used by Sandbox Executor.

### Sandbox Executor (`:8009`)
- `POST /execute` - Subprocess wrapper executing `kubectl ...` against the internal k8s context. Limits length of stdio buffering. Generates `execution_id`.

### Verification Engine (`:8010`)
- `GET /pre-metrics` - Synchronously extracts a pre-fix baseline from Prometheus query output.
- `POST /verify` - Asynchronously waits up to 60 seconds (configurable), scrapes Prometheus, calculates `z_score_delta`, returns `resolved` or `improving`.

### Notifier (`:8011`)
- `POST /notify` - Dispatches messages sequentially to SMTP, Telegram, Slack.
- `POST /test/telegram` - Debugging route to trace connection path to Telegram APIs.
