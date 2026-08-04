# KORAL Architecture Decision Records (ADR)

## 1. ADR-001: Adopt Python Microservices Architecture
- **Context**: Complex K8s metric ingestion requiring isolation across anomaly detection, AI generation, and execution control.
- **Decision**: 10+ independent Python FastAPI services communicating via HTTP/HTTPS.
- **Alternatives**: Monolith (Faster dev, but blocks isolated scaling), Go (Better performance but slower AI integration).
- **Trade-offs**: Added network complexity, increased memory footprint, but allowed concurrent scaling.
- **Consequences**: Cleaner fault isolation. Added overhead for inter-service auth.

## 2. ADR-002: FastAPI Web Framework
- **Context**: Need for high-throughput ASGI service, native data validation, and OpenAPI auto-generation.
- **Decision**: FastAPI 0.111.x across all Python services.
- **Alternatives**: Flask (Sync), Django (Heavy, ORM locked).
- **Trade-offs**: FastAPI's async capabilities are paired with strict Pydantic validation, standardizing request contracts.
- **Consequences**: Excellent performance, but forces strict adherence to Pydantic model schemas in the team.

## 3. ADR-003: React + Vite Frontend
- **Context**: Original frontend was built with Create React App (CRA).
- **Decision**: Migrate to Vite (Completed in CLAUDE.md Phase 2).
- **Alternatives**: Next.js, SvelteKit.
- **Trade-offs**: Vite is extremely fast with HMR, retains React ecosystem and TypeScript support.
- **Consequences**: Removed CRA legacy tooling. Better build times.

## 4. ADR-004: PostgreSQL Primary Database
- **Context**: Production database requiring JSON support, partitioning, and read replicas.
- **Decision**: PostgreSQL 15 + PgBouncer + dedicated read-only replicas.
- **Alternatives**: MongoDB (Lacks transactional guarantees), MySQL.
- **Trade-offs**: PostgreSQL is the standard for K8s data persistence. Migrations via Alembic.
- **Consequences**: High reliability and scalability, but adds operational burden of managing replicas.

## 5. ADR-005: Prometheus for Metrics
- **Context**: Need time-series metric storage and dashboarding integration.
- **Decision**: Prometheus + Grafana + AlertManager.
- **Alternatives**: InfluxDB, Datadog.
- **Trade-offs**: Industry-standard K8s monitoring toolchain, native integration.
- **Consequences**: Full observability stack out of the box, but limited long-term storage retention without extension.

## 6. ADR-006: LLM Multi-Provider Fallback
- **Context**: AI Engine needs robust natural-language reasoning for incidents.
- **Decision**: GPT-4o (primary) -> Claude-3.5-Sonnet (fallback) -> Rule Engine (no key).
- **Alternatives**: Self-hosted LLM, Fine-tuned model.
- **Trade-offs**: Multi-provider ensures high availability and prevents vendor lock-in.
- **Consequences**: Slight increase in code complexity, manageable cost exposure to third-party APIs.

## 7. ADR-007: Argv-Only Sandbox Execution
- **Context**: Autonomous remediation requires K8s action execution.
- **Decision**: `subprocess.run(argv, shell=False)` with strict parameter validation.
- **Alternatives**: Docker-based sandboxes, gVisor.
- **Trade-offs**: Argv-only is exceptionally safe against shell injection, but limited to specific allowlisted `kubectl` actions.
- **Consequences**: Unbreakable execution boundary, prevented catastrophic command injection vulnerabilities.

## 8. ADR-008: Database ORM/Raw SQL Duality (Bottleneck)
- **Context**: Legacy SQLAlchemy models (`backend/models.py`) exist alongside raw SQL (`backend/database.py`).
- **Decision**: Accepted current state for the V2 release. Unification slated for a later phase.
- **Alternatives**: SQLAlchemy Core, full SQLAlchemy ORM.
- **Trade-offs**: Avoids immediate large-scale refactors.
- **Consequences**: High technical debt and migration risk if schema updates target only one paradigm.
