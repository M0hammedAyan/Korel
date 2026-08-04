# KORAL Deployment Architecture

## 1. Overview
The KORAL platform embraces multi-modal scaling and deployment contexts spanning local Docker Compose pipelines intended for developer iterations, to multi-tenant distributed enterprise environments on Kubernetes scaling gracefully through Helm.

---

## 2. Infrastructure Patterns

### Development Context: `docker-compose.yml`
Designed to bootstrap the entire 12+ service micro-cluster alongside metric targets effortlessly.
1. **Network Namespace**: Single bridged software defined network (`networks: [koral]`).
2. **Persistent Volumes**: `koral-data`, `approval-data`, `postgres-data`, `prometheus-data`, `grafana-data` attached cleanly to prevent transient state wiping across component restarts.
3. **Implicit Dependency Graphing**: Uses robust health-check pinging (`condition: service_healthy`) over `pgbouncer -> postgres` and `frontend -> backend` sequences.

### Core Production Stack: `k8s/`
Utilises discrete native manifest mapping files mapping to `Ingress`, `HorizontalPodAutoscaler`, `PodDisruptionBudget`, `NetworkPolicy`, `RoleBinding`, and target `Deployment`.

```yaml
k8s/
├── alertmanager.yaml         # Alert routing configurations
├── fluentbit.yaml            # Forwarding targets mapping across standard out
├── hpa.yaml                  # Target metrics governing backend / correlation autoscaling
├── ingress.yaml              # Edge Load balancing layer configured 
├── koral-deployment.yaml     # Application node configurations
├── koral-secrets.yaml        # Encryption boundaries
├── koral-service.yaml        # Intra-cluster discovery bindings
├── network-policies.yaml     # Zero-trust inter-pod communication 
├── pdb.yaml                  # Disruption budgets governing evictions
├── postgres-deployment.yaml  # Stateful Postgres persistence config
├── prometheus-deployment.yaml# Metric collection config
└── rbac.yaml                 # Subject access rules maps to sandboxing
```

---

## 3. High Availability (HA) Mechanisms
**Backend Application Node Limits**
- `hpa.yaml` establishes boundaries driving CPU utilisation percentage checks to scale node counts seamlessly under load spikes created by anomalous telemetry storms. Note: Evidence dictates "Current: 5-15 replicas" in the previous architectural analysis documents.
- Disruption budgets `pdb.yaml` enforces rules preventing Kubernetes eviction controllers from killing necessary services during drain.

**Database Tier HA**
- The integration of **PgBouncer** inside the architecture unblocks the FastAPI application thread's overhead connecting to PostgreSQL, ensuring connections are re-used gracefully under massive WebSocket ingestion bursts.
- KORAL explicitly references the adoption of "read replicas + table partitioning" ensuring querying analytics across dashboards does not block live ingress performance tuning.

---

## 4. Orchestration Security Context
1. **Network Policies**: Explicitly defined in `k8s/network-policies.yaml`, enabling the implementation of default-deny postures where (example) the frontend layer physically cannot route packets to the PostgreSQL service layer directly.
2. **Cluster Access Strategy**: The sandbox controller routes all operations by issuing binaries through executing `kubectl` mapped downwards into `remediation-planner/main.py:38`. Token injection occurs natively via ServiceAccounts.

---

## 5. Scaling Strategy
Because Correlation Engine mathematically evaluates IsolationForest matrix arrays dynamically on streams mapping through Numpy (`X_train = np.array(history_values)`), Horizontal Pod Autoscaling (HPA) targets must allocate specific pod scheduling thresholds preventing OOM kill scenarios mapping specifically against CPU utilization percentage caps.

## 6. Disaster Recovery & Upgrades
- Deployments support native declarative rolling upgrade schemas guaranteeing no-downtime iterations (assuming Alembic migrations inside `000*.py` are backwards compatible against older application schemas scaling alongside them).
