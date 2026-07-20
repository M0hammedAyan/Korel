# Technical Debt

## Architecture

- `main.py` in correlation-engine, ai-engine, and other services contains too many responsibilities — consider modular decomposition
- Several services share duplicate utility code that could be extracted to the `shared/` package

## Code Quality

- Some services use `_DummyCounter`/`_DummyProm` Prometheus stubs instead of real metrics
- Inconsistent error response format across API routes
- Several shell scripts in `scripts/` lack `set -euo pipefail`

## Testing

- Frontend tests are minimal
- Missing performance regression tests
- No contract tests between services

## Documentation

- API docs are incomplete (some routes lack OpenAPI response models)
- Developer setup guide is fragmented
- No architecture decision records (ADR) for past decisions

## Infrastructure

- Some CI jobs could be parallelized
- No canary deployment strategy in Helm
- Backup/restore scripts need production validation
