# KORAL Database Audit (Extended)

## 1. Overview
KORAL uses a hybrid approach to persistence. 
- **Development Profile**: SQLite (`data/koral.db`)
- **Production Profile**: PostgreSQL 15 via PgBouncer 1.18 connection pooling.
- **ORM / Query Engine**: Codebase relies heavily on parameterised raw SQL statements inside `backend/database.py`, alongside a partially adopted SQLAlchemy model layer in `backend/models.py`.

---

## 2. Table Inventory (Schema Definition via Raw SQL / Alembic)

| Table | Purpose | Ownership/Writer | Primary Key | Missing B-Tree Indexes |
|---|---|---|---|---|
| `anomalies` | Raw threshold violations detected by agents | `backend` (POST /anomalies) | `id` (INTEGER) | `timestamp`, `namespace`, `pod` |
| `incidents` | Correlated anomaly groupings built by correlation-engine | `backend` | `id` (INTEGER), `incident_id` (UNIQUE) | `timestamp`, `severity` |
| `remediation_plans` | Plans proposed by remediation-planner | `backend` | `id`, `plan_id` (UNIQUE) | `status` |
| `approval_history` | State machine tracking human approval flow | `approval-engine` | `id`, `approval_id` (UNIQUE) | `plan_id` |
| `execution_log` | Output, status, duration of sandbox commands | `sandbox-executor` | `id`, `execution_id` (UNIQUE) | `execution_status` |
| `verification_results` | Pre/post metrics and delta verification | `verification-engine`| `id`, `verification_id` (UNIQUE) | `verification_status`|
| `fix_history` | Log of manual/AI fixes for tracing | `backend` | `id` | `incident_id` |
| `audit` | Immutable global security/ops audit trail | `backend` | `id` | (`event_type`, `created_at`) |
| `users` | SaaS RBAC definitions & hashed API keys | `backend` | `id`, `username`, `email` | **Yes:** `api_key_hash`, `role` |
| `tenants` | Multi-tenancy grouping | `backend` | `id` | N/A |
| `tenant_namespaces` | Maps Kubernetes namespaces to tenants | `backend` | `(tenant_id, namespace)` | **Yes:** `namespace` |
| `federated_clusters` | Fleet manager topology metadata | `backend` | `id`, `name` | `status` |

---

## 3. The ORM vs. Raw SQL Dichotomy (Crucial Inconsistency)

The codebase exhibits an architectural duality that poses a critical technical debt risk:

1. **`backend/database.py` (The Executing Layer)** 
   - Owns the 12 tables listed above. 
   - Uses `sqlite3` or `psycopg2.extras.RealDictCursor` depending on `DB_TYPE`.
   - Actually manages the database connection, the migrations process, and the core routing queries.

2. **`backend/models.py` (The SQLAlchemy Layer)**
   - Defines a schema with PostgreSQL UUID data types: `User`, `Organization`, `Project`, `Agent`, `Task`, `Execution`, `Memory`, `Sandbox`, `Integration`, `AuditLog`.
   - Uses declarative base (`from sqlalchemy.ext.declarative import declarative_base`).
   - Uses `UUID` fields where `backend/database.py` uses `TEXT` generic IDs.
   - Creates foreign key relationships explicitly (`owner_id = Column(UUID, ForeignKey('users.id'))`).
   - **Warning**: These SQLAlchemy models appear to be a ghost schema. `approval-engine`, `sandbox-executor`, `verification-engine`, and `backend/routes/remediation.py` bypass these models to perform direct JSON inserts into the legacy raw SQL tables dynamically created in `backend/database.py`.

---

## 4. Migrations & State Evolution

**Alembic (`alembic/versions/`)**
Contains 7 migration files that sequentially build the schema that aligns with `backend/database.py` (not the SQLAlchemy ORM definitions).
- `0001_initial_schema.py`
- `0002_add_audit_table.py`
- `0003_add_users_table.py`
- `0004_partition_anomalies_audit.py` (Note: PostgreSQL partition implementation details present)
- `0005_add_multi_tenancy.py`
- `0006_add_federation.py`
- `0007_koral_v2_detection_tables.py`

*Finding: Migrations successfully bridge schema versioning, however, `backend/database.py` explicitly contains a `schema CREATE TABLE IF NOT EXISTS` block for SQLite bootstrap that duplicates Alembic functionality in dev environments.*

---

## 5. Relationships & Constraints

Because the operational schema is defined predominantly via string interpolation and raw `psycopg2` dictionary cursors, explicit database-level Foreign Keys are rare.

- `tenant_namespaces.tenant_id -> tenants.id` is explicitly defined via FOREIGN KEY constraint (`backend/database.py:215`). 
- **Missing Foreign Keys:** 
  - `remediation_plans.incident_id` does not formally link to `incidents.incident_id`.
  - `approval_history.plan_id` does not formally link to `remediation_plans.plan_id`.
  - Application logic relies entirely on the API payload to maintain referential integrity across the microservice state machine.

---

## 6. Connection Pooling & Scalability
- **PgBouncer**: Employed in transaction-pooling mode (`PGBOUNCER_POOL_MODE=transaction` in docker-compose.yml file). Port `6432`.
- **psycopg2 thread pool**: Overlaid with `psycopg2.pool.ThreadedConnectionPool` inside `database/pool.py`.
- **Read Replicas**: `database.py` exports `_get_read_db()` which points to `DB_READ_HOST`. Read operations from FastAPI use this read replica implicitly.

---

## 7. Metrics & Instrumentation
The database driver is fully decorated with OpenTelemetry spans and Prometheus Histograms:
- `koral_db_query_duration_seconds` (Prometheus Histogram wrapped around `query_one()`, `query_all()`, and `execute()`)
- `koral_db_active_connections` (Prometheus Gauge tracking `get_pool_status()`)
- OpenTelemetry Spans injected over `db.query_one` and `db.execute` if `OTEL_AVAILABLE = True`.

---

## 8. Data Partitioning Strategy
- Reference to partitioning in `0004_partition_anomalies_audit.py`.
- **Evidence**: CLAUDE.md cites "PostgreSQL read replicas + table partitioning for anomaly/event tables = DONE". This ensures scalable cleanup of unbounded high-frequency metric events. 

## 9. Conclusion
- The database is heavily optimized for write-throughput and reads via connection pooling and optional read-replica segregation. 
- The schema is loosely coupled, mimicking a NoSQL document pattern cast over RDBMS JSON-string columns (e.g. `affected_pods` is stored as JSON string-encoded TEXT in the `incidents` table).
- The inconsistency between `backend/models.py` and real operation models introduces a significant risk factor if developers attempt to adopt SQLAlchemy within this repository.
