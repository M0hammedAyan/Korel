# Known Issues

## Critical

None currently identified.

## High

1. Frontend lacks comprehensive test coverage
2. Some API error responses are inconsistent across services
3. Performance benchmarks not automated in CI

## Medium

4. `DummyCounter`/`DummyProm` used as Prometheus fallback in some services — no real metrics exported when Prometheus client is unavailable
5. Correlation engine cohesion is low (0.16) — main.py may need splitting
6. 224 weakly-connected nodes in Graphify — possible documentation gaps and missing edge definitions
7. No automated E2E test pipeline

## Low

8. Some shell scripts lack error handling
9. Inline comments in some modules are sparse
10. OpenAPI response models not defined for all routes
