# KORAL Configuration Audit

## 1. Overview
KORAL heavily implements twelve-factor app principles by mapping core state configuration directly to environment variables. Configurations are centralized primarily inside the `docker-compose.yml` overlay map and Helm values files.

---

## 2. Global Services Configuration Variables

### Database & Caching
| Variable | Default Value | Purpose | Overridden In | Risk / Note |
|---|---|---|---|---|
| `DB_TYPE` | `postgres` | Persistance engine adapter target | `backend/database.py` | Required for scaling |
| `DB_HOST` | `postgres` | Target database pod | `docker-compose.yml` | None |
| `DATABASE_URL` | `postgresql://postgres:koralpass123@postgres:5432/koral` | SQLAlchemy/Alembic link | `docker-compose.yml` | **High Risk**: Embedded secret |
| `REDIS_URL` | `redis://redis:6379/0` | Rate limiting target | `backend/main.py:91` | None |

### Authentication & Keys
| Variable | Default Value | Purpose | Example Scope | Risk / Note |
|---|---|---|---|---|
| `API_KEY` | `koral-dev-api-key-2024` | Legacy Operator access token | `.env.example` | Deprecate in favor of role keys |
| `API_KEY_ADMIN` | `koral-admin-key-secret` | High-privilege CLI / Exec context | `.env.example` | Required for system tasks |
| `API_KEY_OPERATOR` | `koral-operator-key-secret` | Anomaly generation endpoints | `docker-compose.yml` | None |
| `API_KEY_VIEWER` | `koral-viewer-key-readonly` | Dashboard reporting | `docker-compose.yml`| None |
| `JWT_SECRET` | `koral-jwt-secret...2024` | Hash signing cryptographic key | `backend/auth.py` | **High Risk**: Must rotate in Prod |
| `DISABLE_AUTH` | `false` | Disables token dependencies in DEV | `docker-compose.yml` | Dangerous if exposed |

### External APIs
| Variable | Default Value | Purpose | Overridden In | Risk / Note |
|---|---|---|---|---|
| `OPENAI_API_KEY` | N/A | GPT-4o integration | `ai_engine/main.py` | Cost exposure |
| `ANTHROPIC_API_KEY`| N/A | Claude fallback processing | `ai_engine/main.py` | Cost exposure |

### Remediation & Execution Timeouts
| Variable | Default Value | Purpose | Example Scope | Risk / Note |
|---|---|---|---|---|
| `REMEDIATION_TIMEOUT_SECONDS` | `300` | Subprocess sig-term kill trigger | `remediation-planner/main.py` | Needs adjustment for long drains |
| `REMEDIATION_MAX_PODS_PER_FIX` | `5` | Blast radius ceiling for commands | `sandbox-executor/main.py` | Critical safety threshold |
| `DRY_RUN` | `true` | Supresses actual kubectl changes | `sandbox-executor/main.py` | Fail-safe default |
| `ALLOW_CROSS_NAMESPACE` | `false` | Prevents executions outside system | `sandbox-executor/main.py` | Security control |

---

## 3. Communication Limits & Retries
- Agents parameterize `POLL_INTERVAL=10`. This specifies loop sleep timing between agent iterations to calculate metric z-scores (`agents/base_agent.py:17`).
- `Z_THRESHOLD=2.5`: Configurable scalar marking standard deviations from rolling metric baselines to classify outliers. Needs empirical tuning per service cluster.
- OpenTelemetry (`OTEL_SDK_DISABLED="true"`): Temporarily disables tracing overhead out-of-the-box ensuring leaner dev profile (`docker-compose.yml:87`).

---

## 4. Kubernetes Service Accounts
- `remediation-planner` defaults its HTTP connections wrapping `verify=K8S_CA_FILE` mapping down to `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`.
- This ensures intra-cluster communication honors kube-apiserver certificates dynamically injected by deployments.

## 5. Summary & Risks
**Missing Validation**: There is minimal startup validation on environment integrity. E.g., Booting `sandbox-executor` without identifying valid K8S API keys results in runtime execution crashes later, rather than failing immediately dynamically.

**Mitigation**: Implement `BaseSettings` configurations directly consuming Pydantic settings validators inside microservices rather than `os.getenv()`.
