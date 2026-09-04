# KORAL

Self-hosted AIOps and observability platform for Kubernetes — detects anomalies, correlates incidents, plans and executes remediation autonomously, and maintains a full audit trail.

---

## What KORAL Does

KORAL closes the full incident-response loop without leaving the cluster:

```
Detect → Correlate → Plan → Approve → Execute → Verify → Audit
```

1. **Detect** — agents continuously poll Prometheus for CPU, memory, storage, and log metrics. Anomalies are flagged using Z-score pre-filtering and Isolation Forest ML re-scoring.
2. **Correlate** — the correlation engine groups anomalies across pods and namespaces into incidents using cross-pod batch correlation.
3. **Plan** — an LLM (GPT-4o or Claude) analyses the incident and generates a ranked remediation plan with confidence scores.
4. **Approve** — the plan is routed through the approval engine. An operator reviews and approves/rejects via the API or frontend.
5. **Execute** — the sandbox executor runs the approved kubectl command inside an isolated environment with CPU, memory, and timeout limits.
6. **Verify** — the verification engine compares pre- and post-execution Prometheus metrics.
7. **Audit** — every auth event, API access, approval decision, execution, and verification is written to a tamper-evident audit table.

---

## Quick Start (Docker Compose)

### Prerequisites

- **Docker** and **Docker Compose v2** (Docker Desktop or standalone)
- **4 GB RAM** minimum (8 GB recommended for full stack)
- An **OpenAI** or **Anthropic** API key (for AI remediation planning)
- **Git** to clone the repository

### Step 1: Clone the Repository

```bash
git clone https://github.com/M0hammedAyan/KORAL.git
cd KORAL
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Open `.env` in your editor and set the following **required** values:

```ini
# REQUIRED — Generate secure random strings (min 32 chars each)
API_KEY=your-main-api-key-here-min-32-chars
API_KEY_ADMIN=your-admin-key-here-min-32-chars
API_KEY_OPERATOR=your-operator-key-here-min-32-chars
API_KEY_VIEWER=your-viewer-key-here-min-32-chars
JWT_SECRET=your-jwt-secret-here-min-32-chars

# REQUIRED for AI features (at least one)
OPENAI_API_KEY=sk-your-openai-key
# OR
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Database (these defaults work out of the box for Docker)
DB_TYPE=postgres
DB_HOST=postgres
DB_PORT=5432
DB_NAME=koral
DB_USER=postgres
DB_PASS=koralpass123
```

To generate secure random keys on Linux/Mac:
```bash
openssl rand -base64 32
```

On Windows PowerShell:
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

### Step 3: Start the Stack

```bash
docker compose up -d
```

This pulls/builds all 15+ services. First run takes 5–10 minutes depending on your internet speed.

### Step 4: Verify Services Are Running

```bash
docker compose ps
```

All services should show `Up` or `healthy`. Check the backend:

```bash
curl -H "X-API-Key: YOUR_API_KEY_VIEWER" http://localhost:8080/health/live
```

Expected: `{"status": "ok"}`

### Step 5: Access the Application

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend Dashboard |
| http://localhost:8080 | Backend API |
| http://localhost:8080/docs | Interactive API Documentation (Swagger) |
| http://localhost:3001 | Grafana Dashboards (admin / koral-admin) |
| http://localhost:9090 | Prometheus |
| http://localhost:9093 | AlertManager |

---

## Port Mapping

When running via Docker Compose, the following host ports are used:

| Host Port | Internal Port | Service |
|-----------|---------------|---------|
| 3000 | 3000 | Frontend |
| 8080 | 8000 | Backend API |
| 8001 | 8001 | CPU Agent |
| 8002 | 8002 | Memory Agent |
| 8003 | 8003 | Storage Agent |
| 8004 | 8004 | Log Agent |
| 8005 | 8005 | Correlation Engine |
| 8006 | 8006 | AI Engine |
| 8007 | 8007 | Remediation Planner |
| 8008 | 8008 | Approval Engine |
| 8009 | 8009 | Sandbox Executor |
| 8010 | 8010 | Verification Engine |
| 8011 | 8011 | Notifier |
| 9090 | 9090 | Prometheus |
| 3001 | 3000 | Grafana |
| 9093 | 9093 | AlertManager |
| 6379 | 6379 | Redis |
| 5432 | 5432 | PostgreSQL |
| 6432 | 6432 | PgBouncer |

---

## Authentication & API Keys

All API routes (except `/health/*` and `/metrics`) require an `X-API-Key` header.

### Role Hierarchy

| Role | Key Variable | Permissions |
|------|--------------|-------------|
| ADMIN | `API_KEY_ADMIN` | Full access — audit log, user management, execute remediation |
| OPERATOR | `API_KEY_OPERATOR` | Post anomalies, create plans, approve remediation |
| VIEWER | `API_KEY_VIEWER` | Read-only access to all GET endpoints |

The legacy `API_KEY` grants OPERATOR-level access for backward compatibility.

### Example API Calls

```bash
# List anomalies (viewer)
curl -H "X-API-Key: YOUR_VIEWER_KEY" http://localhost:8080/anomalies

# Post an anomaly (operator)
curl -X POST http://localhost:8080/anomalies \
  -H "X-API-Key: YOUR_OPERATOR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"timestamp":1700000000,"pod":"test-pod","metric":"cpu","value":85.5,"z_score":3.2,"is_anomaly":true,"namespace":"default","unit":"percent","source":"manual","window_size":300}'

# Query audit log (admin only)
curl -H "X-API-Key: YOUR_ADMIN_KEY" http://localhost:8080/audit?limit=20

# Create a user (admin only)
curl -X POST http://localhost:8080/users/invite \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","role":"operator"}'
```

### WebSocket Real-Time Events

```
ws://localhost:8080/ws/live?api_key=YOUR_API_KEY
```

All role-scoped keys work for WebSocket connections.

---

## Local Development (Without Docker)

### Backend

```bash
python -m venv .venv
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt

# Set environment
export DB_TYPE=sqlite
export API_KEY=dev-key
export API_KEY_ADMIN=dev-admin
export API_KEY_OPERATOR=dev-operator
export API_KEY_VIEWER=dev-viewer
export JWT_SECRET=dev-secret
export DISABLE_AUTH=false
export OTEL_SDK_DISABLED=true

# Run
uvicorn backend.main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:3000 with proxy to backend.

### Run Tests

```bash
# All tests (84 tests)
pytest tests/ --ignore=tests/load -v

# Quick run
pytest tests/ --ignore=tests/load -q
```

---

## Kubernetes Deployment (Helm)

For production Kubernetes deployment, KORAL includes a parameterized Helm chart.

### Prerequisites

- Kubernetes cluster (1.25+)
- Helm 3.x installed
- `kubectl` configured for your cluster
- cert-manager installed (for mTLS — optional)

### Install

```bash
# Dev environment (single replicas, auth disabled, no remediation)
helm install koral ./helm/koral -f ./helm/koral/values-dev.yaml

# Staging
helm install koral ./helm/koral \
  -f ./helm/koral/values-staging.yaml \
  --set secrets.apiKey=YOUR_KEY \
  --set secrets.jwtSecret=YOUR_SECRET \
  --set secrets.dbPass=YOUR_DB_PASSWORD

# Production (HA, mTLS, read replicas, full pipeline)
helm install koral ./helm/koral \
  -f ./helm/koral/values-prod.yaml \
  --set secrets.apiKey=YOUR_KEY \
  --set secrets.apiKeyAdmin=YOUR_ADMIN_KEY \
  --set secrets.apiKeyOperator=YOUR_OPERATOR_KEY \
  --set secrets.apiKeyViewer=YOUR_VIEWER_KEY \
  --set secrets.jwtSecret=YOUR_JWT_SECRET \
  --set secrets.dbPass=YOUR_DB_PASSWORD \
  --set secrets.openaiApiKey=YOUR_OPENAI_KEY
```

### Verify Helm Deployment

```bash
helm status koral
kubectl get pods -n koral-system
kubectl port-forward svc/backend 8000:8000 -n koral-system
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/health/live
```

### Environment Differences

| Feature | Dev | Staging | Prod |
|---------|-----|---------|------|
| Replicas | 1 | 2 | 3+ |
| HPA | Off | On (2-5) | On (3-15) |
| Auth | Disabled | Enabled | Enabled |
| mTLS | Off | Off | On (cert-manager) |
| Read Replicas | Off | Off | 2 replicas |
| Remediation | Off | Dry-run | Enabled |
| Network Policies | Off | On | On |
| Notifications | Off | Slack only | All channels |

---

## Load Testing

```bash
# Quick smoke test (100 users, 60s)
locust -f load_tests/locustfile.py --headless -u 100 -r 10 -t 60s --host http://localhost:8080

# Soak test (500 users, 30 min)
locust -f load_tests/locustfile.py --headless -u 500 -r 20 -t 30m --tags soak --host http://localhost:8080

# Chaos injection (error scenarios)
locust -f load_tests/locustfile.py --headless -u 200 -r 10 -t 5m --tags chaos --host http://localhost:8080
```

SLO targets enforced by the test runner:
- p50 < 100ms
- p95 < 500ms
- p99 < 1000ms
- Error rate < 1%

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Agents (CPU / Memory / Storage / Log)                       │
│  Z-score pre-filter → POST /anomalies                        │
└────────────────────┬─────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────────┐
│  Backend  :8000                                              │
│  FastAPI · RBAC · Auth · Audit · SLO · WebSocket · Users     │
│       │              │              │              │          │
│  Correlation    Remediation    Approval    Federation        │
│  Engine :8005   Planner :8007  Engine :8008                  │
│  (Isolation     AI plans       Human-in-loop                 │
│   Forest ML)         │                                        │
│               Sandbox Executor :8009                         │
│               Verification Engine :8010                      │
│               Notifier :8011                                 │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
   PostgreSQL :5432      Prometheus :9090    Remote Clusters
   + Read Replicas       Grafana :3001      (Federation)
   (PgBouncer :6432)     AlertManager :9093
         │
   React/Vite Frontend :3000
```

---

## Services

| Service | Port | Purpose |
|---|---|---|
| backend | 8000 | Core API — auth, RBAC, anomalies, incidents, SLO, audit, WebSocket, users, tenants, federation |
| correlation-engine | 8005 | Isolation Forest anomaly detection, incident grouping, cross-pod correlation |
| ai-engine | 8006 | LLM proxy — GPT-4o / Claude integration |
| remediation-planner | 8007 | AI-driven fix recommendation, dynamic K8s discovery |
| approval-engine | 8008 | Approval workflow with PostgreSQL persistence |
| sandbox-executor | 8009 | Isolated kubectl execution with resource limits |
| verification-engine | 8010 | Pre/post Prometheus metrics comparison |
| notifier | 8011 | Slack, Telegram, Email notifications |
| prometheus | 9090 | Metrics collection |
| grafana | 3001 | Dashboards (4 auto-provisioned) |
| alertmanager | 9093 | Alert routing — Slack, Email, webhook |
| postgres | 5432 | Primary database (partitioned by month) |
| pgbouncer | 6432 | Connection pooling |
| redis | 6379 | Distributed rate limiting |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| Frontend | React 18, TypeScript, Vite |
| Database | PostgreSQL (prod, partitioned), SQLite (dev), PgBouncer, Read Replicas |
| Monitoring | Prometheus, Grafana, AlertManager |
| AI/ML | Isolation Forest (anomaly detection), OpenAI GPT-4o, Anthropic Claude |
| Auth | Role-scoped API keys + JWT + per-user managed keys |
| Security | mTLS (cert-manager), Cosign image signing, SBOM attestation |
| Rate limiting | Redis (in-memory fallback) |
| Container | Docker Compose (dev), Helm chart (prod), K8s with HPA/PDB/NetworkPolicies |
| CI/CD | GitHub Actions — lint, test, build, sign, scan |

---

## API Overview

All routes except `/health/*` and `/metrics` require an `X-API-Key` header.

| Prefix | Minimum Role | Description |
|---|---|---|
| `GET /anomalies` | VIEWER | List detected anomalies |
| `POST /anomalies` | OPERATOR | Ingest a new anomaly reading |
| `GET /incidents` | VIEWER | List correlated incidents |
| `GET /correlations` | VIEWER | List correlation results |
| `GET /graph` | VIEWER | Dependency graph data |
| `GET /fixes/history` | VIEWER | Fix history |
| `POST /fixes/record` | OPERATOR | Record a fix |
| `GET /remediation/status` | VIEWER | Remediation system status |
| `POST /remediation/plans` | OPERATOR | Create a remediation plan |
| `POST /remediation/execute/:id` | ADMIN | Execute an approved plan |
| `GET /slo/` | VIEWER | Full SLO summary |
| `GET /sla/targets` | VIEWER | SLA target definitions |
| `GET /sla/compliance` | VIEWER | Current SLA compliance status |
| `GET /sla/degradation` | VIEWER | Graceful degradation state |
| `GET /audit` | ADMIN | Query the audit log |
| `POST /users/invite` | ADMIN | Create a user with API key |
| `POST /users/:name/rotate-key` | ADMIN | Rotate a user's API key |
| `GET /users/:name/audit` | ADMIN | Per-user audit trail |
| `POST /tenants/` | ADMIN | Create a tenant |
| `POST /tenants/:id/namespaces` | ADMIN | Assign namespace to tenant |
| `POST /federation/clusters` | ADMIN | Register a remote cluster |
| `GET /federation/overview` | VIEWER | Cross-cluster aggregated status |
| `WS /ws/live` | Any valid key | Real-time event stream (role-filtered) |
| `GET /health/live` | None | Liveness probe |
| `GET /metrics` | None | Prometheus scrape endpoint |

---

## Features

- **RBAC** — three roles (VIEWER / OPERATOR / ADMIN) enforced on every route
- **User management** — invite users, rotate keys, per-user audit trails, key expiry
- **Multi-tenancy** — team isolation via namespace-to-tenant mapping
- **Multi-cluster federation** — register and monitor remote clusters from one dashboard
- **Anomaly detection** — two-tier: Z-score pre-filter (agents) + Isolation Forest ML (correlation engine)
- **Incident correlation** — single-pod and batch cross-pod correlation
- **LLM remediation planning** — GPT-4o or Claude generates fix plans with reasoning
- **Approval workflow** — plans require explicit approval before execution
- **Sandboxed execution** — commands run with CPU, memory, timeout, and filesystem limits
- **Prometheus verification** — pre/post metrics comparison with improvement percentage
- **SLO tracking** — availability, MTTR, detection latency, remediation success rate, error budget
- **SLA guarantees** — quantified targets, compliance reporting, graceful degradation
- **Audit log** — every auth event, fix, approval, execution, and verification persisted
- **4 Grafana dashboards** — auto-provisioned on startup
- **mTLS** — inter-service mutual TLS via cert-manager (production)
- **SBOM & supply chain** — Trivy scanning, Cosign signing, CycloneDX/SPDX attestation
- **PostgreSQL partitioning** — monthly range partitions on anomalies/audit for scale
- **Read replicas** — separate read/write database routing
- **WebSocket RBAC** — role-aware real-time streaming with channel subscriptions
- **Redis rate limiting** — per-IP and per-key limits with in-memory fallback
- **Helm chart** — parameterized for dev/staging/prod with HPA, PDB, network policies

---

## Troubleshooting

### Services won't start

```bash
# Check logs for a specific service
docker compose logs backend
docker compose logs correlation-engine

# Rebuild after code changes
docker compose build --no-cache backend
docker compose up -d
```

### Database migration errors

```bash
# Run migrations manually
docker compose exec backend alembic upgrade head
```

### Port conflicts

If port 3000, 8080, or 9090 is already in use:

```bash
# Change frontend port
FRONTEND_PORT=3000 docker compose up -d

# Or edit .env
FRONTEND_PORT=3000
```

### API returns 401

- Check your `X-API-Key` header matches one of the keys in `.env`
- Ensure `DISABLE_AUTH` is not set to `true` in production
- Try the VIEWER key for GET endpoints, OPERATOR for POST

### OpenTelemetry errors in tests

The `otel-collector` connection errors at the end of test runs are harmless — the OTLP exporter tries to ship traces but there's no collector running locally. They don't affect test results.

---

## Project Structure

```
KORAL/
├── backend/                    Core FastAPI application
│   ├── routes/                 API route modules (anomalies, incidents, users, tenants, federation, sla, ...)
│   ├── websocket/              WebSocket manager with RBAC
│   ├── auth.py                 API key + JWT validation
│   ├── rbac.py                 Role resolution (env keys + DB user keys)
│   ├── tenancy.py              Multi-tenant context resolution
│   ├── audit.py                Audit log writer
│   └── database.py             SQLite/PostgreSQL with read replica routing
├── correlation-engine/         Isolation Forest ML + incident correlation
├── ai_engine/                  LLM proxy (GPT-4o / Claude)
├── remediation-planner/        AI fix recommendations
├── approval-engine/            Approval workflow
├── sandbox-executor/           Isolated kubectl execution
├── verification-engine/        Pre/post metrics comparison
├── notifier/                   Slack / Telegram / Email
├── agents/                     Per-metric K8s polling agents
├── frontend/                   React + TypeScript + Vite
├── shared/                     Shared modules (mTLS helper)
├── database/                   Connection pool (primary + read replica)
├── helm/koral/                 Helm chart (dev/staging/prod values)
├── k8s/                        Raw K8s manifests (legacy, use Helm instead)
├── infra/                      Grafana dashboards, AlertManager config
├── alembic/                    Database migrations (6 versions)
├── tests/                      Test suite (84 tests)
├── load_tests/                 Locust load tests (soak + chaos)
├── .github/workflows/          CI/CD + SBOM + supply chain security
├── docker-compose.yml          Development stack
├── docker-compose-prod.yml     Production stack
└── .env.example                Environment variable template
```

---

## Environment Variables

All variables are documented in `.env.example`. Key groups:

| Group | Variables |
|---|---|
| Database | `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_READ_HOST` |
| Auth | `API_KEY`, `API_KEY_ADMIN`, `API_KEY_OPERATOR`, `API_KEY_VIEWER`, `JWT_SECRET`, `DISABLE_AUTH` |
| AI / LLM | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| Alerting | `ALERT_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SLACK_WEBHOOK_URL` |
| Services | `BACKEND_URL`, `CORRELATION_ENGINE_URL`, `AI_ENGINE_URL`, `PROMETHEUS_URL`, `REDIS_URL` |
| Tuning | `LOG_LEVEL`, `Z_THRESHOLD`, `POLL_INTERVAL` |
| SLA | `SLA_AVAILABILITY_TARGET`, `SLA_DETECTION_LATENCY_P95_S`, `SLA_API_LATENCY_P95_MS` |

---

## License

MIT
