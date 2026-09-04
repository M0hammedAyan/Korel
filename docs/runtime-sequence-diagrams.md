# KORAL Runtime Sequence Diagrams

---

## Sequence 1 — Anomaly Detection & Incident Creation

```
Agent              Backend            Correlation-Engine      Database        Notifier
  │                   │                       │                   │              │
  │  POST /anomalies  │                       │                   │              │
  │  {pod,metric,     │                       │                   │              │
  │   value,z_score}  │                       │                   │              │
  │──────────────────>│                       │                   │              │
  │                   │  INSERT anomalies     │                   │              │
  │                   │───────────────────────────────────────────>│              │
  │                   │                       │                   │<─ (ack) ──── │
  │                   │                       │                   │              │
  │                   │ POST /correlate       │                   │              │
  │                   │ {timestamp,pod,metric,│                   │              │
  │                   │  value,z_score,       │                   │              │
  │                   │  is_anomaly,namespace}│                   │              │
  │                   │──────────────────────>│                   │              │
  │                   │                       │                   │              │
  │                   │                       │ IsolationForest   │              │
  │                   │                       │ detect(raw_event) │              │
  │                   │                       │   ┌──────────┐    │              │
  │                   │                       │   │ Fit model │    │              │
  │                   │                       │   │ on window │    │              │
  │                   │                       │   │ Predict   │    │              │
  │                   │                       │   └──────────┘    │              │
  │                   │                       │                   │              │
  │                   │                       │ build_incident()  │              │
  │                   │                       │ determine_root_   │              │
  │                   │                       │ cause()           │              │
  │                   │                       │ determine_        │              │
  │                   │                       │ severity()        │              │
  │                   │                       │                   │              │
  │                   │<──────────────────────│                   │              │
  │                   │ {incident_id,severity,│                   │              │
  │                   │  root_cause,summary,  │                   │              │
  │                   │  affected_pods,       │                   │              │
  │                   │  confidence}          │                   │              │
  │                   │                       │                   │              │
  │                   │  INSERT incidents     │                   │              │
  │                   │───────────────────────────────────────────>│              │
  │                   │                       │                   │              │
  │                   │  ws.broadcast(        │                   │              │
  │                   │   {type:"anomaly"})   │                   │              │
  │                   │──────> [Frontend WS]  │                   │              │
  │                   │                       │                   │              │
```

**Evidence**:
- Agent posts to backend: `agents/base_agent.py:130-133`
- Backend routes anomalies: `backend/routes/anomalies.py`
- Correlation engine detection: `correlation-engine/main.py:86-138`
- Isolation Forest scoring: `correlation-engine/ai_core/anomaly.py:79-99`
- Root cause analysis: `correlation-engine/ai_core/rca.py:10-32`
- Incident building: `correlation-engine/ai_core/incident.py`

---

## Sequence 2 — Full Remediation Workflow (Incident Response)

```
Backend         AI-Engine     Rem-Planner    Approval-Eng  Sandbox-Exec   Verif-Engine   Notifier
  │                │               │               │              │              │           │
  │ POST /remediation/plans        │               │              │              │           │
  │ {incident_id, severity,        │               │              │              │           │
  │  root_cause, affected_pods,    │               │              │              │           │
  │  primary_metric, z_score}      │               │              │              │           │
  │───────────────────────────────>│               │              │              │           │
  │                │               │               │              │              │           │
  │                │ POST /create-plan              │              │              │           │
  │                │──────────────>│               │              │              │           │
  │                │               │               │              │              │           │
  │                │               │ POST /analyze │              │              │           │
  │                │               │──────────────>│              │              │           │
  │                │               │               │              │              │           │
  │                │               │ GPT-4o / Claude / Rule-Engine│              │           │
  │                │               │<──────────────│              │              │           │
  │                │               │               │              │              │           │
  │                │               │ K8s API: resolve namespace   │              │           │
  │                │               │ & deployment                 │              │           │
  │                │               │               │              │              │           │
  │                │<──────────────│               │              │              │           │
  │                │ {plan_id,     │               │              │              │           │
  │                │  recommended_ │               │              │              │           │
  │                │  action,      │               │              │              │           │
  │                │  parameters}  │               │              │              │           │
  │<───────────────│               │               │              │              │           │
  │                │               │               │              │              │           │
  │ DB: INSERT remediation_plans   │               │              │              │           │
  │────────> [PostgreSQL]          │               │              │              │           │
  │                │               │               │              │              │           │
  │ POST /remediation/approve/{plan_id}            │              │              │           │
  │───────────────────────────────────────────────>│              │              │           │
  │                │               │               │              │              │           │
  │                │               │  POST /request-approval      │              │           │
  │                │               │──────────────>│              │              │           │
  │                │               │               │ Send email   │              │           │
  │                │               │               │──> [SMTP]    │              │           │
  │                │               │               │              │              │           │
  │                │               │               │ DB: INSERT   │              │           │
  │                │               │               │ approval     │              │           │
  │                │               │<──────────────│              │              │           │
  │<───────────────────────────────│               │              │              │           │
  │                │               │               │              │              │           │
  │ PATCH /remediation/approvals/{id}/approve      │              │              │           │
  │───────────────────────────────────────────────>│              │              │           │
  │                │               │               │ DB: UPDATE   │              │           │
  │                │               │               │ status=      │              │           │
  │                │               │               │ "approved"   │              │           │
  │<───────────────────────────────────────────────│              │              │           │
  │                │               │               │              │              │           │
  │ POST /remediation/execute/{plan_id}            │              │              │           │
  │                │               │               │              │              │           │
  │  1. GET /status/{approval_id}                  │              │              │           │
  │───────────────────────────────────────────────>│              │              │           │
  │<───────────────────────────────────────────────│              │              │           │
  │  (verify status == "approved" & not expired)   │              │              │           │
  │                │               │               │              │              │           │
  │  2. GET /pre-metrics                           │              │              │           │
  │───────────────────────────────────────────────────────────────>│              │           │
  │<───────────────────────────────────────────────────────────────│              │           │
  │  (Prometheus baseline metrics snapshot)        │              │              │           │
  │                │               │               │              │              │           │
  │  3. POST /execute                              │              │              │           │
  │──────────────────────────────────────────────────────────────>│              │           │
  │                │               │               │              │              │           │
  │                │               │               │  Validate    │              │           │
  │                │               │               │  params      │              │           │
  │                │               │               │  Build argv  │              │           │
  │                │               │               │  Execute or  │              │           │
  │                │               │               │  DRY_RUN     │              │           │
  │<──────────────────────────────────────────────────────────────│              │           │
  │  {execution_id, status, exit_code, stdout}     │              │              │           │
  │                │               │               │              │              │           │
  │  DB: INSERT execution_log      │               │              │              │           │
  │────────> [PostgreSQL]          │               │              │              │           │
  │                │               │               │              │              │           │
  │ POST /remediation/verify/{execution_id}        │              │              │           │
  │───────────────────────────────────────────────────────────────────────────── >│           │
  │                │               │               │              │              │           │
  │                │               │               │              │  sleep(60s)  │           │
  │                │               │               │              │  Query       │           │
  │                │               │               │              │  Prometheus  │           │
  │                │               │               │              │  post-metrics│           │
  │                │               │               │              │  Compare     │           │
  │                │               │               │              │  pre vs post │           │
  │<─────────────────────────────────────────────────────────────────────────────│           │
  │  {verification_id, improvement_percent, anomaly_resolved}    │              │           │
  │                │               │               │              │              │           │
  │  DB: INSERT verification_results               │              │              │           │
  │────────> [PostgreSQL]          │               │              │              │           │
  │                │               │               │              │              │           │
  │ POST /remediation/notify/{incident_id}         │              │              │           │
  │──────────────────────────────────────────────────────────────────────────────────────── >│
  │                │               │               │              │              │           │
  │                │               │               │              │              │  Telegram │
  │                │               │               │              │              │  Email    │
  │<────────────────────────────────────────────────────────────────────────────────────────│
  │                │               │               │              │              │           │
```

**Evidence**:
- Plan creation: `backend/routes/remediation.py:103-140`
- Approval request: `backend/routes/remediation.py:153-189`
- Approval approval: `backend/routes/remediation.py:448-470`
- Execution flow: `backend/routes/remediation.py:192-277`
- Pre-metrics fetch: `backend/routes/remediation.py:41-54`
- Verification: `backend/routes/remediation.py:280-335`
- Notification dispatch: `backend/routes/remediation.py:338-370`
- Sandbox command execution: `sandbox-executor/main.py:201-281`
- Prometheus metric query: `verification-engine/main.py:90-121`

---

## Sequence 3 — User Dashboard Request Flow

```
Browser          Nginx/Frontend      Backend (8000)          PostgreSQL       Prometheus
  │                   │                    │                      │               │
  │  GET /dashboard   │                    │                      │               │
  │──────────────────>│                    │                      │               │
  │                   │ Serve React SPA    │                      │               │
  │<──────────────────│                    │                      │               │
  │                   │                    │                      │               │
  │  XHR GET /incidents?limit=50          │                      │               │
  │  Header: X-API-Key: <key>             │                      │               │
  │──────────────────────────────────────>│                      │               │
  │                   │                    │                      │               │
  │                   │                    │ Rate limit check     │               │
  │                   │                    │ (Redis / in-memory)  │               │
  │                   │                    │                      │               │
  │                   │                    │ Auth: validate X-API │               │
  │                   │                    │ -Key via RBAC layer  │               │
  │                   │                    │                      │               │
  │                   │                    │ RBAC: require_viewer │               │
  │                   │                    │                      │               │
  │                   │                    │ SELECT * FROM        │               │
  │                   │                    │ incidents ORDER BY   │               │
  │                   │                    │ timestamp DESC       │               │
  │                   │                    │ LIMIT 50             │               │
  │                   │                    │─────────────────────>│               │
  │                   │                    │<─────────────────────│               │
  │                   │                    │                      │               │
  │<──────────────────────────────────────│                      │               │
  │  200 OK [{incident_id, ...}]          │                      │               │
  │                   │                    │                      │               │
  │  WS /ws/live?api_key=<key>            │                      │               │
  │──────────────────────────────────────>│                      │               │
  │                   │                    │                      │               │
  │                   │                    │ authenticate_        │               │
  │                   │                    │ websocket(api_key)   │               │
  │                   │                    │ ─> Resolve WSRole    │               │
  │                   │                    │                      │               │
  │<─────────── (WS connection accepted) ─│                      │               │
  │                   │                    │                      │               │
  │  {"type":"subscribe","channel":"all"} │                      │               │
  │──────────────────────────────────────>│                      │               │
  │                   │                    │                      │               │
  │  ... (real-time anomaly/incident      │                      │               │
  │   events pushed as they occur) ...    │                      │               │
  │<──────────────────────────────────────│                      │               │
  │                   │                    │                      │               │
  │  XHR GET /slo/                        │                      │               │
  │──────────────────────────────────────>│                      │               │
  │                   │                    │ SELECT COUNT(*) FROM │               │
  │                   │                    │ incidents            │               │
  │                   │                    │ SELECT AVG(duration_ms)               │
  │                   │                    │ FROM execution_log   │               │
  │                   │                    │─────────────────────>│               │
  │                   │                    │<─────────────────────│               │
  │<──────────────────────────────────────│                      │               │
  │  {availability_percent, mttr_seconds, │                      │               │
  │   error_budget, ...}                  │                      │               │
  │                   │                    │                      │               │
```

**Evidence**:
- Frontend serves SPA: `frontend/nginx.conf`
- Incidents query: `backend/routes/incidents.py`, `backend/database.py:391-394`
- WebSocket auth: `backend/main.py:344-389`, `backend/websocket/manager.py:118-172`
- SLO endpoint: `backend/routes/slo.py:89-97`
- Rate limiting: `backend/main.py:206-240`
- RBAC middleware: `backend/rbac.py:84-113`
