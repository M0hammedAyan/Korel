from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import JSONResponse
import os
import hmac
import signal
import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, CONTENT_TYPE_LATEST
    PROM_AVAILABLE = True
except Exception:
    PROM_AVAILABLE = False
    class _DummyCounter:
        def __init__(self, *a, **k):
            pass
        def inc(self):
            pass
        def observe(self, *a, **k):
            pass
        def set(self, *a, **k):
            pass
    Counter = _DummyCounter
    Gauge = _DummyCounter
    Histogram = _DummyCounter
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    class _DummyProm:
        @staticmethod
        def generate_latest():
            return b""
    prometheus_client = _DummyProm()
from contextlib import asynccontextmanager
from backend.routes.anomalies import router as anomalies_router
from backend.routes.incidents import router as incidents_router
from backend.routes.graph import router as graph_router
from backend.routes.correlations import router as correlations_router
from backend.routes.feedback import router as feedback_router
from backend.routes.ai import router as ai_router
from backend.routes.fixes import router as fixes_router
from backend.routes.remediation import router as remediation_router
from backend.routes.audit import router as audit_router
from backend.routes.slo import router as slo_router
from backend.routes.users import router as users_router
from backend.routes.tenants import router as tenants_router
from backend.routes.federation import router as federation_router
from backend.routes.sla import router as sla_guarantees_router
from backend.websocket.manager import manager
from backend.auth import get_allowed_origins, validate_api_key, DISABLE_AUTH
from backend.database import init_db, close_db_pool, query_one
import logging
import sys
import time
from collections import defaultdict
from typing import Dict, Tuple
import httpx
from backend.middleware import RequestIDMiddleware, ErrorResponseMiddleware, AuditAccessMiddleware
from backend.errors import standard_response
from backend.resilience import CircuitBreaker, call_with_circuit
from backend.rate_limit_redis import check_rate_limit, connect_redis
from shared.mtls import is_mtls_enabled, get_mtls_client, get_uvicorn_ssl_kwargs


# ── Security Headers Middleware ────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Inject OWASP-recommended security response headers on every HTTP response.
    Adds defense-in-depth against clickjacking, MIME sniffing, and information disclosure.
    """
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    }

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    OTEL_AVAILABLE = True
except Exception:
    OTEL_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

_ip_requests: Dict[Tuple[str, int], list[float]] = defaultdict(list)
_key_requests: Dict[Tuple[str, int], list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_IP = 100
RATE_LIMIT_API_KEY = 500
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://ai-engine:8006")
CORRELATION_ENGINE_URL = os.getenv("CORRELATION_ENGINE_URL", "http://correlation-engine:8005")
REDIS_URL = os.getenv("REDIS_URL", "")


def _configure_tracing(app: FastAPI) -> None:
    if not OTEL_AVAILABLE:
        return
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() in ("true", "1", "yes"):
        logger.info("OpenTelemetry tracing disabled via OTEL_SDK_DISABLED")
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "koral-backend")})
    )
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318/v1/traces")
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/metrics,/health,/health/live,/health/ready,/docs,/openapi.json,/redoc",
    )


if PROM_AVAILABLE:
    REQUEST_LATENCY = Histogram(
        "koral_backend_request_latency_seconds",
        "HTTP request latency for the KORAL backend",
        ["method", "path"],
    )
    ERROR_COUNT = Counter("koral_backend_errors_total", "Total HTTP 5xx responses from the backend")
    WEBSOCKET_CLIENTS = Gauge("koral_backend_websocket_clients", "Connected backend websocket clients")
else:
    REQUEST_LATENCY = None
    ERROR_COUNT = Counter("koral_backend_errors_total", "Total HTTP 5xx responses from the backend")
    WEBSOCKET_CLIENTS = Gauge("koral_backend_websocket_clients", "Connected backend websocket clients")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KORAL Backend starting up...")
    app.state.shutting_down = False
    shutdown_event = asyncio.Event()
    app.state.shutdown_event = shutdown_event

    def _request_shutdown() -> None:
        if not shutdown_event.is_set():
            logger.info("Shutdown signal received; stopping request intake")
            app.state.shutting_down = True
            shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except Exception:
            pass

    try:
        await asyncio.wait_for(asyncio.to_thread(init_db), timeout=10)
        logger.info("Database initialized and loaded")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
    app.state.redis = await connect_redis(REDIS_URL)
    logger.info("All routes registered")
    logger.info("Backend ready to accept connections")
    yield
    app.state.shutting_down = True
    if getattr(app.state, "redis", None):
        try:
            await app.state.redis.aclose()
        except Exception:
            pass
    try:
        await asyncio.wait_for(manager.close_all(), timeout=30)
    except Exception as e:
        logger.warning(f"WebSocket shutdown completed with errors: {e}")
    try:
        await asyncio.wait_for(asyncio.to_thread(close_db_pool), timeout=5)
    except Exception as e:
        logger.warning(f"Database pool shutdown completed with errors: {e}")
    logger.info("KORAL Backend shutting down...")


app = FastAPI(title="KORAL Backend", lifespan=lifespan)
_configure_tracing(app)

# Prometheus metrics
REQUEST_COUNT = Counter('koral_backend_requests_total', 'Total HTTP requests to KORAL backend')


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            REQUEST_COUNT.inc()
            if REQUEST_LATENCY is not None:
                REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(time.perf_counter() - started)
            if status_code >= 500:
                ERROR_COUNT.inc()


app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuditAccessMiddleware)
app.add_middleware(ErrorResponseMiddleware)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in {"/health", "/health/live", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        if getattr(request.app.state, "shutting_down", False):
            return JSONResponse({"detail": "Service shutting down"}, status_code=503)

        now = time.time()
        window = int(now // RATE_LIMIT_WINDOW)
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key", "")
        redis = getattr(request.app.state, "redis", None)

        if redis is not None:
            if not await check_rate_limit(redis, f"ip:{client_ip}", RATE_LIMIT_IP, RATE_LIMIT_WINDOW):
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            if api_key and not await check_rate_limit(redis, f"key:{api_key[:32]}", RATE_LIMIT_API_KEY, RATE_LIMIT_WINDOW):
                return JSONResponse({"detail": "API key rate limit exceeded"}, status_code=429)
        else:
            def _allow(bucket: Dict[Tuple[str, int], list[float]], key: str, limit: int) -> bool:
                entries = bucket[(key, window)]
                entries[:] = [ts for ts in entries if now - ts < RATE_LIMIT_WINDOW]
                if len(entries) >= limit:
                    return False
                entries.append(now)
                return True

            if not _allow(_ip_requests, client_ip, RATE_LIMIT_IP):
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            if api_key and not _allow(_key_requests, api_key, RATE_LIMIT_API_KEY):
                return JSONResponse({"detail": "API key rate limit exceeded"}, status_code=429)

        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    allow_credentials=True,
)

app.include_router(anomalies_router)
app.include_router(incidents_router)
app.include_router(graph_router)
app.include_router(correlations_router)
app.include_router(feedback_router)
app.include_router(ai_router)
app.include_router(fixes_router)
app.include_router(remediation_router)
app.include_router(audit_router)
app.include_router(slo_router)
app.include_router(users_router)
app.include_router(tenants_router)
app.include_router(federation_router)
app.include_router(sla_guarantees_router)


async def _dependency_health(url: str) -> bool:
    try:
        async with get_mtls_client(timeout=2.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:
        return False


async def _database_health() -> bool:
    try:
        await asyncio.wait_for(asyncio.to_thread(query_one, "SELECT 1"), timeout=2.0)
        return True
    except Exception:
        return False


def _websocket_health() -> bool:
    return isinstance(getattr(manager, "active", None), list)


@app.get("/health/live")
def health_live():
    return {"status": "ok", "live": True, "service": "koral-backend"}


@app.get("/health/ready")
async def health_ready():
    return await health()


@app.get("/health")
async def health():
    database_ok = await _database_health()
    correlation_ok = await _dependency_health(f"{CORRELATION_ENGINE_URL}/health")
    ai_ok = await _dependency_health(f"{AI_ENGINE_URL}/health")
    websocket_ok = _websocket_health()

    payload = {
        "status": "healthy" if all([database_ok, correlation_ok, ai_ok, websocket_ok]) else "degraded",
        "database": "healthy" if database_ok else "unhealthy",
        "correlation_engine": "healthy" if correlation_ok else "unhealthy",
        "ai_engine": "healthy" if ai_ok else "unhealthy",
        "websocket": "healthy" if websocket_ok else "unhealthy",
    }
    if payload["status"] != "healthy":
        return JSONResponse(payload, status_code=503)
    return payload


@app.get("/metrics")
def metrics():
    data = prometheus_client.generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "KORAL Backend",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "anomalies": "/anomalies",
            "incidents": "/incidents",
            "graph": "/graph",
            "correlations": "/correlations",
            "fixes": "/fixes/history",
            "websocket": "/ws/live"
        }
    }


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates with role-aware RBAC.

    Authentication via query param or header:
      - ws://host/ws/live?api_key=<key>
      - Header: X-API-Key: <key>

    Supports env-var keys (admin/operator/viewer) and user-managed keys.
    Messages are filtered by role — admin-only events won't reach viewers.
    """
    from backend.websocket.manager import authenticate_websocket, WSRole

    if not DISABLE_AUTH:
        api_key = websocket.query_params.get("api_key") or websocket.headers.get("X-API-Key")
        auth_result = await authenticate_websocket(api_key)
        if auth_result is None:
            await websocket.close(code=4401)
            return
        role, username = auth_result
    else:
        role, username = WSRole.ADMIN, "development"

    conn = await manager.connect(websocket, role=role, username=username)
    WEBSOCKET_CLIENTS.set(manager.get_connection_count())

    try:
        while True:
            data = await websocket.receive_text()
            # Handle client subscription messages
            try:
                import json as _json
                msg = _json.loads(data)
                if msg.get("type") == "subscribe" and "channel" in msg:
                    conn.subscriptions.add(msg["channel"])
                elif msg.get("type") == "unsubscribe" and "channel" in msg:
                    conn.subscriptions.discard(msg["channel"])
            except (ValueError, TypeError):
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        WEBSOCKET_CLIENTS.set(manager.get_connection_count())
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        WEBSOCKET_CLIENTS.set(manager.get_connection_count())


if __name__ == "__main__":
    import uvicorn
    ssl_kwargs = get_uvicorn_ssl_kwargs()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, **ssl_kwargs)
