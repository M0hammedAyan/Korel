# Graph Report - KORAL  (2026-07-15)

## Corpus Check
- 195 files · ~102,126 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1863 nodes · 2914 edges · 131 communities (103 shown, 28 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 169 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a696d68e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- validate_event
- main.py
- main.py
- remediation.py
- database.py
- prometheus_client.py
- BaseAgent
- ViewerUser
- test_backend_integration.py
- .is_allowed
- DetectorBase
- KORAL — Complete Agent Build & Test Specification
- KORAL
- RRCFStreamDetector
- package.json
- main.py
- CardinalityViolation
- make_seasonal_series
- CLAUDE.md
- KORAL — Industry Research & Market Gap Analysis
- main.py
- write_audit
- rbac.py
- .authenticate_request
- processor.py
- compilerOptions
- STLDecomposer
- main.py
- App.tsx
- FalcoEventStore
- federation.py
- AnomalyResult
- ci_local_run.sh
- api.ts
- VictoriaMetricsClient
- ConnectionManager
- correlation.py
- main.py
- pool.py
- sla.py
- evaluate
- main.py
- query_one
- deploy-phase2-security.sh
- version-bump.sh
- performance.py
- TestSTLSufficientData
- mtls.py
- models.py
- validate_event
- integration_test.py
- fixes.py
- incident.py
- IsolationForestDetector
- RemediationDashboard.tsx
- deploy-phase3-database.sh
- setup-production.sh
- test_user_management.py
- email_service.py
- Dashboard.tsx
- edge_cases.py
- KORAL activeContext.md
- init_db
- process_feedback
- compilerOptions
- DetectorFactory
- test_multi_tenancy.py
- TestRRCFInterface
- ErrorBoundary
- Incidents.tsx
- TenantContext
- TestWebSocketAuth
- adaptive_threshold.py
- env.py
- process_events
- telegram.py
- validate-production.sh
- feedback_loop.py
- TestTenantCRUD
- 0004_partition_anomalies_audit.py
- demo_validator.py
- TestUserInvite
- WebSocketService
- slack_notify.py
- clear_incidents.py
- verify-current-health.sh
- TestUserTenantAssignment
- KPICard.tsx
- backup.sh
- restore.sh
- health-check.sh
- TestUserDeactivation
- TestUserKeyAuth
- TestUserUpdate
- __init__.py
- __init__.py
- setup.sh
- copilot-instructions.md
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- bootstrap.sh
- deploy-all.sh
- deploy-grafana.sh
- deploy-production.sh
- setup-infra.sh
- teardown.sh
- quickstart.sh

## God Nodes (most connected - your core abstractions)
1. `query_one()` - 42 edges
2. `write_audit()` - 33 edges
3. `execute()` - 32 edges
4. `AnomalyResult` - 30 edges
5. `query_all()` - 22 edges
6. `RRCFStreamDetector` - 22 edges
7. `STLIFDetector` - 22 edges
8. `KORAL — Complete Agent Build & Test Specification` - 21 edges
9. `validate_event()` - 19 edges
10. `compilerOptions` - 19 edges

## Surprising Connections (you probably didn't know these)
- `AnomalyIn` --uses--> `ValidationError`  [INFERRED]
  correlation-engine/main.py → AIML/Member1_work/ai_core/validator.py
- `BatchAnomalyIn` --uses--> `ValidationError`  [INFERRED]
  correlation-engine/main.py → AIML/Member1_work/ai_core/validator.py
- `_DummyCounter` --uses--> `ValidationError`  [INFERRED]
  correlation-engine/main.py → AIML/Member1_work/ai_core/validator.py
- `_DummyProm` --uses--> `ValidationError`  [INFERRED]
  correlation-engine/main.py → AIML/Member1_work/ai_core/validator.py
- `MetricsMiddleware` --uses--> `ValidationError`  [INFERRED]
  correlation-engine/main.py → AIML/Member1_work/ai_core/validator.py

## Import Cycles
- None detected.

## Communities (131 total, 28 thin omitted)

### Community 0 - "validate_event"
Cohesion: 0.05
Nodes (61): Deque, HistoryPoint, KoralEvent, Rolling Z-score anomaly detection for Project KORAL events., Compute Z-scores from a per-pod, per-metric rolling time window., Validate, score, and annotate one event., Score events in timestamp order to keep the rolling window stable., RollingZScoreDetector (+53 more)

### Community 1 - "main.py"
Cohesion: 0.05
Nodes (37): close_db_pool(), Dispose the shared PostgreSQL pool on shutdown., standard_response(), _configure_tracing(), _database_health(), _dependency_health(), _DummyCounter, _DummyProm (+29 more)

### Community 2 - "main.py"
Cohesion: 0.05
Nodes (32): DryRunExecutor, Any, ExecutionOutcome, Any, SandboxExecutor, _coerce_and_validate_params(), execute_command_safely(), execute_remediation() (+24 more)

### Community 3 - "remediation.py"
Cohesion: 0.06
Nodes (54): add_execution(), add_remediation_plan(), add_verification(), count_remediation_plans(), get_execution(), get_remediation_plan(), get_verification(), init_remediation_db() (+46 more)

### Community 4 - "database.py"
Cohesion: 0.07
Nodes (46): Audit logging — writes to the audit table for key system events., execute(), execute_many(), _get_db(), _get_read_db(), _observe_pool_metrics(), query_all(), Database module for KORAL - supports SQLite (dev) and PostgreSQL (prod) (+38 more)

### Community 5 - "prometheus_client.py"
Cohesion: 0.06
Nodes (34): call_with_circuit(), CircuitBreaker, State, _deliver_slack(), _format_message(), Slack notification helper for KORAL incidents., send_slack_alert(), Enum (+26 more)

### Community 6 - "BaseAgent"
Cohesion: 0.07
Nodes (20): BaseAgent, compute_z_score(), deque, CpuAgent, LogAgent, MemoryAgent, StorageAgent, compute_dynamic_threshold() (+12 more)

### Community 7 - "ViewerUser"
Cohesion: 0.05
Nodes (20): HttpUser, AdminUser, ChaosUser, check_slo(), KoralUser, OperatorUser, KORAL Load Tests — Soak, Latency Percentile Targets, and Chaos Injection.  Usage, Simulates an agent/operator posting anomalies and recording fixes. (+12 more)

### Community 9 - ".is_allowed"
Cohesion: 0.07
Nodes (24): BaseHTTPMiddleware, Request, RateLimitConfig, RateLimiter, RateLimitMiddleware, Rate Limiting Middleware for KORAL Backend Implements token bucket and sliding, Add current request to window, Get request count in current window (+16 more)

### Community 10 - "DetectorBase"
Cohesion: 0.07
Nodes (28): ABC, BaseSettings, Config, KoralSettings, KORAL Configuration — Pydantic Settings v2.  All configuration is environment-, All KORAL environment variables. Grouped by subsystem., ConfirmationResult, DetectorBase (+20 more)

### Community 11 - "KORAL — Complete Agent Build & Test Specification"
Cohesion: 0.05
Nodes (38): 0. PRIME DIRECTIVE FOR AGENT, 10.1 Port Shifting (Zero-Downtime), 10.2 Quarantine (Network Isolation), 10.3 Selective Pod Shutdown (3-of-3 Gated), 10. LAYER 4 — ACTION ENGINE, 11.1 Standard Alert Message Format, 11.2 Alert Routing Matrix, 11.3 Alert Events Per Layer (+30 more)

### Community 12 - "KORAL"
Cohesion: 0.05
Nodes (38): API Overview, API returns 401, Architecture, Authentication & API Keys, Backend, Database migration errors, Environment Differences, Environment Variables (+30 more)

### Community 13 - "RRCFStreamDetector"
Cohesion: 0.07
Nodes (23): datetime, Batch variant: processes series sequentially, returns all results., Returns most recent anomaly score without updating tree., Normalize raw codisp to 0.0 - 1.0 using adaptive percentile.          Uses his, Confidence based on how far above/below threshold the score is.         Score a, Real-time streaming anomaly detection using Robust Random Cut Forest.      Per, Process one data point. Returns AnomalyResult immediately.         Side effect:, RRCFStreamDetector (+15 more)

### Community 14 - "package.json"
Cohesion: 0.06
Nodes (35): axios, d3, dependencies, axios, d3, react, react-dom, react-router-dom (+27 more)

### Community 15 - "main.py"
Cohesion: 0.09
Nodes (26): ai_ws(), analyze_incident(), broadcast_activity(), _build_email_html(), call_ai(), call_claude(), call_gpt(), chat() (+18 more)

### Community 16 - "CardinalityViolation"
Cohesion: 0.10
Nodes (15): CardinalityGuard, CardinalityViolation, Exception, Cardinality Guard — prevents label explosion in VictoriaMetrics.  High-cardina, Raised when a metric would violate cardinality rules., Enforces cardinality rules on all metric labels before storage.      Rules:, Validate labels against cardinality rules.         Raises CardinalityViolation, Return current cardinality counts per label. (+7 more)

### Community 17 - "make_seasonal_series"
Cohesion: 0.09
Nodes (17): make_seasonal_series(), trend + seasonal + residual should approximately equal original., Should return residual when enough data., Should return original series when not enough data., detect_many should return list of AnomalyResults., A clean seasonal signal should produce very few anomalies., A large spike injected into seasonal signal should be detected., When sufficient data, STL should be applied. (+9 more)

### Community 18 - "CLAUDE.md"
Cohesion: 0.07
Nodes (26): Architecture, Audit Events, Auth, Authentication Rules, Backend Route Map, CI/CD Requirements, Code Quality Standards, Completed (+18 more)

### Community 19 - "KORAL — Industry Research & Market Gap Analysis"
Cohesion: 0.07
Nodes (27): 1.1 The Pain: Downtime Costs, 1.2 The Pain: Wasted Kubernetes Spend, 1.3 The Pain: Operations Team Burnout, 1. What Industry Needs (Why They'll Buy), 2. What Enterprises Expect from AI in Kubernetes, 3.1 The Big Players, 3.2 Specialized Tools, 3.3 The Fundamental Market Gaps (+19 more)

### Community 20 - "main.py"
Cohesion: 0.17
Nodes (23): _conn(), _conn_pg(), _conn_sqlite(), get_approval(), init_db(), insert_approval(), list_approvals(), _ph() (+15 more)

### Community 21 - "write_audit"
Cohesion: 0.14
Nodes (26): Any, Fire-and-forget audit write. Never raises — logs on failure., write_audit(), add_namespace(), _assign_namespace(), assign_user_to_tenant(), create_tenant(), get_tenant() (+18 more)

### Community 22 - "rbac.py"
Cohesion: 0.12
Nodes (22): create_jwt(), DecodeError, _DummyJWT, ExpiredSignatureError, get_allowed_origins(), Exception, Validate JWT token from Authorization header, Get CORS allowed origins (+14 more)

### Community 23 - ".authenticate_request"
Cohesion: 0.11
Nodes (14): AuthenticationTracker, EnhancedAuthenticator, get_authenticated_user(), Request, Enhanced Authentication Middleware with Security Features Implements API key, J, Authenticate HTTP request                  Returns:             Tuple of (aut, FastAPI dependency for authentication, Track authentication attempts for security (+6 more)

### Community 24 - "processor.py"
Cohesion: 0.13
Nodes (21): get_incidents(), insert_anomaly(), insert_incident(), Insert an anomaly record, Insert an incident record, Update incident with AI analysis, update_incident(), AnomalyPayload (+13 more)

### Community 25 - "compilerOptions"
Cohesion: 0.08
Nodes (25): compilerOptions, allowImportingTsExtensions, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+17 more)

### Community 26 - "STLDecomposer"
Cohesion: 0.12
Nodes (16): Series, Convenience: decompose and return only the residual.         If decomposition f, Check if the trend component shows significant monotonic drift.         Used by, Result of STL decomposition., Check that residual has non-null values., Decomposes time series into trend + seasonal + residual using STL.      Parame, Returns True only if series spans >= 2 full periods.         STL needs at minim, Decompose a time series into trend, seasonal, and residual.          Returns S (+8 more)

### Community 27 - "main.py"
Cohesion: 0.12
Nodes (22): create_remediation_plan(), _deployment_from_pod(), get_plan(), _k8s_get(), list_approved_commands(), metrics(), _node_for_pod(), BaseModel (+14 more)

### Community 28 - "App.tsx"
Cohesion: 0.11
Nodes (15): App(), client, Header(), HeaderProps, Sidebar(), root, root, DependencyGraph() (+7 more)

### Community 29 - "FalcoEventStore"
Cohesion: 0.12
Nodes (13): FalcoEvent, FalcoEventStore, parse_falcosidekick_payload(), Falco Event Consumer — receives events from Falcosidekick webhook.  Falco even, Quick check: does this pod have any Falco event that indicates an attack?, Clear all events for a pod (after incident is resolved)., Parse a Falcosidekick webhook JSON payload into a FalcoEvent.      Falcosideki, Parsed Falco event from Falcosidekick webhook. (+5 more)

### Community 30 - "federation.py"
Cohesion: 0.14
Nodes (20): cluster_heartbeat(), ClusterHealthReport, ClusterRegister, ClusterUpdate, deregister_cluster(), federation_overview(), get_cluster(), list_clusters() (+12 more)

### Community 31 - "AnomalyResult"
Cohesion: 0.13
Nodes (13): AnomalyResult, Standard anomaly detection result from any KORAL detector., Map anomaly score to severity level., datetime, Series, Normalize IF decision score to 0.0 - 1.0 range.          IF decision_function, Confidence based on how clearly anomalous/normal the point is., Return neutral results when insufficient data. (+5 more)

### Community 32 - "ci_local_run.sh"
Cohesion: 0.10
Nodes (19): ALLOWED_ORIGINS, ANTHROPIC_API_KEY, API_KEY, BACKEND_URL, DB_HOST, DB_NAME, DB_PASS, DB_PORT (+11 more)

### Community 33 - "api.ts"
Cohesion: 0.17
Nodes (14): D3Link, D3Node, fmt(), SLOPage(), api, client, wsService, Anomaly (+6 more)

### Community 34 - "VictoriaMetricsClient"
Cohesion: 0.13
Nodes (13): CardinalityViolation, DataFrame, datetime, Exception, VictoriaMetrics Client — Remote write + MetricsQL query.  Handles:   - Queryi, Query returning multiple series (e.g., per-pod results).         Returns dict m, Enforce cardinality rules before writing.         Raises CardinalityViolation i, Write KORAL's self-monitoring metrics to VictoriaMetrics.          Each metric (+5 more)

### Community 35 - "ConnectionManager"
Cohesion: 0.13
Nodes (10): ConnectionManager, WebSocket, A WebSocket connection with RBAC metadata., Role-aware WebSocket connection manager., Accept a WebSocket connection and register it with role metadata., Remove a connection by its WebSocket reference., Send a message to all connections that meet the minimum role requirement, Send a message to a specific connected user. (+2 more)

### Community 36 - "correlation.py"
Cohesion: 0.16
Nodes (17): correlate_batch(), KoralEvent, Cross-pod, cross-service, cross-namespace correlation for batch events., Group anomalous events by namespace + time window, then by root-cause bucket., _service_from_pod(), _window_key(), build_incident(), Incident (+9 more)

### Community 37 - "main.py"
Cohesion: 0.15
Nodes (12): AnomalyIn, BatchAnomalyIn, correlate(), correlate_batch_endpoint(), _DummyCounter, _DummyProm, _fallback_incident(), metrics() (+4 more)

### Community 38 - "pool.py"
Cohesion: 0.20
Nodes (16): _build_url(), close_pool(), _create_pool(), get_engine(), get_pool_status(), get_read_engine(), install_psycopg2_pool(), Shared SQLAlchemy connection pools for KORAL.  Supports:   - Primary (read-wr (+8 more)

### Community 39 - "sla.py"
Cohesion: 0.13
Nodes (15): _estimate_api_latency_p95(), _estimate_detection_latency_p95(), get_degradation_status(), get_sla_compliance(), get_sla_targets(), SLA Guarantees API — KORAL  Provides:   - Quantified uptime targets (SLOs wit, Calculate current SLA compliance for the active period.     Compares actual met, Return current graceful degradation status.     Shows which dependencies are he (+7 more)

### Community 40 - "evaluate"
Cohesion: 0.15
Nodes (16): test_evaluate_empty_inputs(), test_evaluate_no_detections(), test_false_positive_not_in_ground_truth(), test_fpr_zero_alerts(), test_multiple_anomalies_all_detected(), test_precision_zero_alerts(), test_recall_zero_ground_truth(), test_sudden_spike_detected() (+8 more)

### Community 41 - "main.py"
Cohesion: 0.16
Nodes (14): get_pre_metrics(), get_verification(), metrics(), BaseModel, query_metrics(), KORAL Verification Engine - Post-fix validation and effectiveness measurement V, Fetch current metric snapshot before remediation executes., Verify remediation effectiveness (+6 more)

### Community 42 - "query_one"
Cohesion: 0.25
Nodes (15): get_incident(), query_one(), Execute query and return first row as dict (uses read replica if available), Get specific incident, _availability(), _detection_latency(), _error_budget(), _mttr() (+7 more)

### Community 43 - "deploy-phase2-security.sh"
Cohesion: 0.42
Nodes (15): check_prerequisites(), install_audit_logging(), install_pod_security_standards(), install_sealed_secrets(), install_secret_rotation(), install_tls_mtls(), log_error(), log_info() (+7 more)

### Community 44 - "version-bump.sh"
Cohesion: 0.27
Nodes (14): bump_version(), check_on_main_branch(), check_working_directory(), get_current_version(), log_error(), log_info(), log_success(), log_warning() (+6 more)

### Community 45 - "performance.py"
Cohesion: 0.12
Nodes (15): test_filter_top_anomalies_limits_to_10(), test_sample_metrics_reduces_volume(), cache_correlation(), clear_old_cache(), compute_threshold_cached(), filter_top_anomalies(), get_cached_correlation(), Performance Optimization Layer — caching, sampling, and latency reduction. (+7 more)

### Community 46 - "TestSTLSufficientData"
Cohesion: 0.12
Nodes (10): make_flat_series(), Series, A monotonically increasing trend should be detected., With insufficient data, should fall back to raw IF., Empty series should return empty list., Generate a flat series with noise., Less than 2 periods should return False., At least 2 periods should return True. (+2 more)

### Community 47 - "mtls.py"
Cohesion: 0.15
Nodes (13): AsyncClient, get_mtls_client(), get_service_url(), get_ssl_context(), get_uvicorn_ssl_kwargs(), is_mtls_enabled(), KORAL mTLS Helper — Shared module for mutual TLS between services.  When MTLS_, Get kwargs to pass to uvicorn.run() for TLS server mode.      Returns: (+5 more)

### Community 48 - "models.py"
Cohesion: 0.35
Nodes (13): Agent, AuditLog, Execution, Integration, Memory, Organization, Project, Sandbox (+5 more)

### Community 49 - "validate_event"
Cohesion: 0.29
Nodes (13): Any, KoralEvent, ValueError, Validation for Project KORAL metric events., Raised when an incoming KORAL event violates the shared contract., Validate and normalize a single KORAL event.      Args:         event: Incomi, Validate a batch of KORAL events., _require_int() (+5 more)

### Community 50 - "integration_test.py"
Cohesion: 0.20
Nodes (12): Integration Test — validates full system flow: simulation → agent → backend → co, Verify agents are sending anomalies to backend., Verify correlation engine is generating correlations., Verify incidents are being created with root causes., Verify dependency graph is accessible., Run all integration tests and return results., run_integration_tests(), test_anomaly_detection() (+4 more)

### Community 51 - "fixes.py"
Cohesion: 0.18
Nodes (12): FixHistoryEntry, get_fix_history(), get_fix_stats(), get_fixes_by_incident(), BaseModel, Get fix history with optional filtering, Get statistics about fixes, Get all fixes for a specific incident (+4 more)

### Community 52 - "incident.py"
Cohesion: 0.28
Nodes (8): Isolation Forest anomaly detection for Project KORAL events.  Replaces the previ, Incident construction for Project KORAL anomaly output., End-to-end Project KORAL anomaly and incident pipeline., Rule-based root cause analysis for anomalous KORAL events., Incident, KoralEvent, TypedDict, Shared Project KORAL event and incident schema constants.

### Community 53 - "IsolationForestDetector"
Cohesion: 0.21
Nodes (8): IsolationForestDetector, Deque, HistoryPoint, KoralEvent, Score events in timestamp order to keep the rolling window stable., Return (pseudo_z, is_anomaly) for the incoming value.          Pseudo-z maps IF', Per-pod, per-metric Isolation Forest with a rolling time window.      Parameters, Validate, score, and annotate one event.

### Community 54 - "RemediationDashboard.tsx"
Cohesion: 0.18
Nodes (10): ApprovalRequest, ApprovalWorkflow(), Props, RemediationPlan, RemediationMetrics, RemediationOperation, RemediationStatus(), RemediationDashboard() (+2 more)

### Community 55 - "deploy-phase3-database.sh"
Cohesion: 0.44
Nodes (11): apply_phase3_manifests(), build_and_push_backup_image(), check_prerequisites(), log_err(), log_info(), log_ok(), log_warn(), main() (+3 more)

### Community 56 - "setup-production.sh"
Cohesion: 0.47
Nodes (11): create_secrets(), generate_configurations(), install_system_components(), log_error(), log_info(), log_success(), log_warn(), main() (+3 more)

### Community 57 - "test_user_management.py"
Cohesion: 0.17
Nodes (4): Tests for the User Management API (Task 4)., TestKeyRotation, TestPerUserAudit, TestUserAccess

### Community 58 - "email_service.py"
Cohesion: 0.25
Nodes (10): _build_batch_summary_html(), _build_fix_report_html(), _deliver_email(), KORAL Email Service — Anomaly Fix Notifications Sends detailed fix reports back, Build professional HTML email report., Send batch summary of all fixes performed in a time period.          Args:, Build HTML for batch summary report., Send detailed anomaly fix report to developer.          Args:         inciden (+2 more)

### Community 59 - "Dashboard.tsx"
Cohesion: 0.25
Nodes (9): ACTION_LABELS, AIAssistant(), aiClient, ChatMessage, ChartPoint, Dashboard(), formatTime(), formatTimestamp() (+1 more)

### Community 60 - "edge_cases.py"
Cohesion: 0.24
Nodes (7): Edge-Case Tests — no data, sudden spike, multiple anomalies, overlapping inciden, Same pod+metric appearing twice in ground truth should not inflate TP., test_dynamic_threshold_single_value(), test_dynamic_threshold_spike(), test_overlapping_incidents_no_double_count(), compute_dynamic_threshold(), Returns mean + k * std for a list of recent metric values.

### Community 61 - "KORAL activeContext.md"
Cohesion: 0.22
Nodes (8): Blocking Issues, Completed in This Session, Current Phase, Do Not Touch, KORAL activeContext.md, Last Completed Task, Last Known State, Next Task

### Community 62 - "init_db"
Cohesion: 0.22
Nodes (5): init_db(), Initialize database schema, Tests for WebSocket RBAC — role-aware connection validation (Task 5)., TestWebSocketSubscriptions, TestWebSocketUserKey

### Community 63 - "process_feedback"
Cohesion: 0.28
Nodes (8): FeedbackPayload, BaseModel, receive_feedback(), _load(), process_feedback(), Feedback Loop — adjusts thresholds when backend reports false positives., Call this when backend sends feedback on an incident.     is_correct=False → fal, _save()

### Community 64 - "compilerOptions"
Cohesion: 0.22
Nodes (8): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include, vite.config.ts

### Community 65 - "DetectorFactory"
Cohesion: 0.22
Nodes (5): DetectorFactory, Creates and caches detector instances per metric series.      RRCF detectors a, Return number of active detector instances., Clear all cached detectors. Use when resetting state., Remove a specific detector (e.g., when a pod is terminated).

### Community 66 - "test_multi_tenancy.py"
Cohesion: 0.22
Nodes (3): Tests for Multi-Tenancy API (Task 7)., TestNamespaceMapping, TestTenantAccess

### Community 67 - "TestRRCFInterface"
Cohesion: 0.22
Nodes (5): Detect must return a properly typed AnomalyResult., detect_many should return a list of AnomalyResults., get_score() should return the last computed score., get_score() with no data should return 0.0., TestRRCFInterface

### Community 68 - "ErrorBoundary"
Cohesion: 0.25
Nodes (3): ErrorBoundary, Props, State

### Community 69 - "Incidents.tsx"
Cohesion: 0.36
Nodes (6): AI_ACTION_INFO, IncidentCard(), Props, ROOT_CAUSE_LABELS, Incidents(), Incident

### Community 70 - "TenantContext"
Cohesion: 0.29
Nodes (4): Resolved tenant context for the current request., Check if this context has access to a given tenant., Return (sql_fragment, params) to filter queries by tenant.         Super-admins, TenantContext

### Community 72 - "adaptive_threshold.py"
Cohesion: 0.48
Nodes (6): get_threshold(), _load_config(), Dynamic Anomaly Threshold System — adaptive k-sigma thresholds per metric., Feed a new sample; returns the current k threshold for this metric., _save_config(), update_threshold()

### Community 73 - "env.py"
Cohesion: 0.47
Nodes (4): get_url(), run_migrations_offline(), run_migrations_online(), SQLAlchemy metadata used by Alembic autogenerate.

### Community 74 - "process_events"
Cohesion: 0.33
Nodes (6): _group_anomalies(), process_events(), Incident, IncidentKey, KoralEvent, Validate events, detect anomalies, run RCA, and build incidents.      Incident

### Community 75 - "telegram.py"
Cohesion: 0.33
Nodes (5): format_telegram_message(), Telegram notification helpers for KORAL Notifier., Send a message via Telegram Bot API., Format a notification dict into a Telegram-friendly message., send_telegram_alert()

### Community 76 - "validate-production.sh"
Cohesion: 0.60
Nodes (5): fail(), info(), pass(), validate-production.sh script, warn()

### Community 77 - "feedback_loop.py"
Cohesion: 0.47
Nodes (5): _load(), process_feedback(), Feedback Loop — adjusts thresholds when backend reports false positives., Call this when backend sends feedback on an incident.     is_correct=False → fal, _save()

### Community 79 - "0004_partition_anomalies_audit.py"
Cohesion: 0.50
Nodes (3): _generate_monthly_partitions(), Generate CREATE TABLE statements for monthly partitions., upgrade()

### Community 80 - "demo_validator.py"
Cohesion: 0.70
Nodes (4): _get(), _poll(), run(), validate_scenario()

### Community 83 - "slack_notify.py"
Cohesion: 0.50
Nodes (3): Slack notification helper for KORAL Notifier., Send a Slack alert via incoming webhook., send_slack_alert()

### Community 84 - "clear_incidents.py"
Cohesion: 0.83
Nodes (3): clear(), _clear_sqlite(), _count_sqlite()

### Community 85 - "verify-current-health.sh"
Cohesion: 0.83
Nodes (3): check_docker_service(), check_endpoint(), verify-current-health.sh script

## Knowledge Gaps
- **224 isolated node(s):** `SoftDeleteMixin`, `ci_local_run.sh script`, `DB_TYPE`, `DB_HOST`, `DB_PORT` (+219 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValidationError` connect `validate_event` to `main.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `update_threshold()` connect `adaptive_threshold.py` to `BaseAgent`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AnomalyResult` (e.g. with `RRCFStreamDetector` and `STLIFDetector`) actually correct?**
  _`AnomalyResult` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `SoftDeleteMixin`, `ci_local_run.sh script`, `DB_TYPE` to the rest of the system?**
  _224 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `validate_event` be split into smaller, more focused modules?**
  _Cohesion score 0.054945054945054944 - nodes in this community are weakly interconnected._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05357142857142857 - nodes in this community are weakly interconnected._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05200501253132832 - nodes in this community are weakly interconnected._