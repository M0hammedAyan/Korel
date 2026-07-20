# Dependencies

## Runtime Dependencies

| Dependency | Version | Used By |
|---|---|---|
| Python | >=3.11 | All backend services |
| FastAPI | >=0.110 | All API services |
| Uvicorn | >=0.29 | All API services |
| SQLAlchemy | >=2.0 | Backend, Approval Engine |
| Alembic | 1.13.1 | Database migrations |
| psycopg2-binary | >=2.9 | PostgreSQL driver |
| aiosqlite | >=0.20 | SQLite async driver |
| prometheus-client | >=0.19 | Metrics export |
| httpx | >=0.27 | HTTP client |
| websockets | >=12.0 | WebSocket support |
| PyJWT | >=2.8 | JWT authentication |
| scikit-learn | >=1.4 | Isolation Forest |
| rrcf | >=0.4 | RRCF detector |
| numpy | >=1.26 | Numerical computation |
| pandas | >=2.2 | Data processing |
| openai | >=1.12 | GPT-4o integration |
| anthropic | >=0.23 | Claude integration |
| redis | >=5.0 | Rate limiting, caching |
| aiofiles | >=23.2 | Async file operations |
| python-multipart | >=0.0.9 | Form data parsing |
| jinja2 | >=3.1 | Email templates |

## Frontend Dependencies

| Dependency | Version |
|---|---|
| React | ^18 |
| TypeScript | ^5 |
| Vite | ^5 |
| react-router-dom | ^6 |
| recharts | ^2 |
| d3 | ^7 |
| axios | ^1 |

## Infrastructure Dependencies

| Component | Version |
|---|---|
| PostgreSQL | 16 |
| Redis | 7-alpine |
| Prometheus | latest |
| Grafana | latest |
| AlertManager | latest |
| Docker | 24+ |
| Kubernetes | 1.28+ |
| Helm | 3+ |
| cert-manager | 1.14+ |
| PgBouncer | latest |
