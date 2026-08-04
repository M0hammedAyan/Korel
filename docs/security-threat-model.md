# KORAL Security Threat Model

## 1. Authentication & API Security

### Threat: Missing Internal Service Authentication
- **Description**: The auxiliary microservices (`remediation-planner`, `approval-engine`, `sandbox-executor`, `verification-engine`) expose port-level endpoints without verifying JWTs or `X-API-Key` headers. While restricted to the internal Kubernetes namespace conceptually, any compromised pod or internal actor can interact with these services (e.g., executing arbitrary remediation plans by directly calling `:8009/execute`).
- **Severity**: **High**
- **Likelihood**: Medium
- **Impact**: Arbitrary command execution inside the cluster via the sandbox executor if the internal network is breached.
- **Evidence**: `sandbox-executor/main.py:284` (`@app.post("/execute")` has no `Depends(require_operator)`) vs. `backend/routes/remediation.py:192` (which protects it via `Depends(require_admin)`).

### Threat: Hardcoded/Default API Keys in Environments
- **Description**: Security defaults like `JWT_SECRET=koral-jwt-secret-token-super-random-2024` are printed in `docker-compose.yml` and `.env.example`.
- **Severity**: **Medium**
- **Likelihood**: Low (Devops usually override, but risk of oversight).
- **Impact**: Forging of JWT tokens granting Admin privileges.
- **Evidence**: `docker-compose.yml:85`, `backend/auth.py:26`.

### Threat: WebSocket Authentication Bypass
- **Description**: WebSocket clients can transmit API keys via query string parameters (`ws://.../ws/live?api_key=<key>`).
- **Severity**: **Low**
- **Likelihood**: Medium
- **Impact**: API keys might be logged in front-end load balancer access logs or reverse-proxy routing tables.
- **Evidence**: `backend/main.py:348`.

---

## 2. Authorization & RBAC

### Threat: Static Role Privilege Matrix
- **Description**: `backend/rbac.py` uses an `IntEnum` for `Role` (`VIEWER=1, OPERATOR=2, ADMIN=3`). `require_role(minimum)` permits tiered horizontal escalation (an `ADMIN` can implicitly invoke `OPERATOR` endpoints). While sound for basic authorization, granular resource-level containment (tenant A altering tenant B's anomalies) relies strictly on namespace headers rather than IAM logic.
- **Severity**: **Low**
- **Likelihood**: Medium
- **Evidence**: `backend/rbac.py`.

---

## 3. Command Execution & Sandboxing

### Strengths Found:
- **Argv Constraint**: The Sandbox Executor categorically refuses shell string evaluation (`shell=False`) in `subprocess.run()`. Command construction uses strict closures building discrete arguments (`["kubectl", "delete", "pod/..."]`).
- **Regex Validation**: Parameters supplied to the sandbox undergo strict sanitation. For example, `k8s_name` types must match `^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$` preventing directory traversal `../` or shell injections `; rm -rf /`.
- **Namespace Lockdown**: By default `ALLOW_CROSS_NAMESPACE` is false, and executions are locked to the `koral-system` (or configured) namespace using static string assertions.
- **Blast Radius Protection**: Maximum pod disruption is capped by `MAX_PODS_PER_FIX` (default 5).

### Threat: Malicious K8s Config Map Mounts / In-Cluster Escapes
- **Description**: Although the executor is robust against injection, a compromised API Server connection enables `kubectl` inside the pod to impact the host node if RBAC permissions for the underlying Service Account map to cluster-level admin. 
- **Severity**: **Medium**
- **Mitigation Needed**: Ensure execution pod runs under an explicit least-privilege `ServiceAccount` in `k8s/koral-deployment.yaml`.

---

## 4. Supply Chain & Inter-Service Tunnelling

### Strengths Found:
- **mTLS Architecture**: `shared/mtls.py` uses `ssl.CERT_REQUIRED` and mandates TLSv1.2 with specific Cipher suites (`ECDHE+AESGCM:ECDHE+CHACHA20`) to encrypt and authenticate all cross-service traffic natively.

### Threat: SSRF via External Services
- **Description**: LLM payloads (GPT-4o / Claude) transport internal K8s cluster contexts, incident ID names, and metrics over public TLS channels to Anthropic/OpenAI APIs.
- **Severity**: **Low**
- **Mitigation Needed**: Data loss prevention (DLP) masks for internal cluster taxonomy before dispatching to `/analyze` logic in the AI Engine.

---

## 5. OWASP API Top 10 Alignment

1. **Broken Object Level Authorization (BOLA)**: Needs verifying that querying `/incidents/{id}` enforces namespace ownership bindings aligned to Tenant IDs.
2. **Broken Authentication**: Covered by `X-API-Key` & JWT logic.
3. **Broken Object Property Level Authorization**: Addressed natively via Pydantic model serialization parsing out invalid/unwanted object properties. 
4. **Unrestricted Resource Consumption**: Mitigated by `redis:7-alpine` token buckets `RATE_LIMIT_IP = 100`, `RATE_LIMIT_API_KEY = 500`.
5. **Security Misconfiguration**: Warning triggers logged dynamically if `JWT_SECRET` equals the deployment default.

---

## Summary of Key Recommendations
- **Priority 1**: Implement `backend.auth` JWT / `X-API-Key` middleware decorators recursively across ALL sub-microservices, removing public surface access inside the overlay network.
- **Priority 2**: Modify K8s daemonset / role-bindings ensuring the `sandbox-executor` cannot scale deployments outside approved internal scopes.
