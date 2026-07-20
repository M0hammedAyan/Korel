import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
try:
    import prometheus_client
    from prometheus_client import Counter, CONTENT_TYPE_LATEST
    PROM_AVAILABLE = True
except Exception:
    PROM_AVAILABLE = False
    class _DummyCounter:
        def __init__(self, *a, **k):
            pass
        def inc(self):
            pass
    Counter = _DummyCounter
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    class _DummyProm:
        @staticmethod
        def generate_latest():
            return b""
    prometheus_client = _DummyProm()
from pydantic import BaseModel
from ai_core.rca import determine_root_cause, determine_severity, primary_metric
from ai_core.anomaly import IsolationForestDetector
from ai_core.incident import build_incident
from ai_core.correlation import correlate_batch
from ai_core.validator import validate_event, ValidationError

app = FastAPI(title="KORAL Correlation Engine", version="2.0.0")

# Prometheus metrics
REQUEST_COUNT = Counter('koral_correlation_requests_total', 'Total HTTP requests to KORAL correlation engine')


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        REQUEST_COUNT.inc()
        return await call_next(request)


app.add_middleware(MetricsMiddleware)

_detector = IsolationForestDetector(z_threshold=3.0, window_size=300)


class AnomalyIn(BaseModel):
    timestamp: int
    pod: str
    metric: str
    value: float
    z_score: float
    is_anomaly: bool
    namespace: str = "koral-system"
    unit: str = ""
    source: str = ""
    window_size: int = 300


# Metric → sensible unit default
_UNITS = {
    "cpu": "percent", "memory": "MB", "storage": "KB/s",
    "logs": "count", "log_error": "count", "pvc_io": "KB/s",
    "disk": "KB/s", "network": "MB/s", "latency": "ms",
    "restart": "count", "oom_kill": "count",
}

# Map agent metric names → ai_core allowed metrics
_METRIC_MAP = {"storage": "pvc_io", "logs": "log_error"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get('/metrics')
def metrics():
    data = prometheus_client.generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)


@app.post("/correlate")
def correlate(anomaly: AnomalyIn):
    metric = _METRIC_MAP.get(anomaly.metric, anomaly.metric)
    unit = anomaly.unit or _UNITS.get(metric, "value")
    source = anomaly.source or f"{metric}-agent"

    raw_event = {
        "timestamp": anomaly.timestamp,
        "pod": anomaly.pod,
        "namespace": anomaly.namespace,
        "metric": metric,
        "value": anomaly.value,
        "unit": unit,
        "window_size": anomaly.window_size,
        "source": source,
        "z_score": anomaly.z_score,
        "is_anomaly": anomaly.is_anomaly,
    }

    try:
        # Run Isolation Forest scoring — updates z_score and is_anomaly in-place
        event = _detector.detect(raw_event)
    except (ValidationError, Exception) as e:
        # Fallback: validate without IF scoring
        try:
            event = validate_event(raw_event, final=True)
        except ValidationError:
            return _fallback_incident(anomaly, metric, str(e))

    incident = build_incident([event])

    # Use IF-scored z_score for confidence
    scored_z = event.get("z_score", anomaly.z_score)
    confidence = round(min(abs(scored_z) / 5.0, 1.0), 2)

    return {
        "incident_id": incident["incident_id"],
        "timestamp": incident["timestamp"],
        "namespace": incident["namespace"],
        "severity": incident["severity"],
        "root_cause": incident["root_cause"],
        "summary": incident["summary"],
        "affected_pods": incident["affected_pods"],
        "primary_metric": incident["primary_metric"],
        "confidence": confidence,
        "pod_A": anomaly.pod,
        "pod_B": anomaly.pod,
        "metric": metric,
        "correlation": scored_z,
        "root_cause_pod": anomaly.pod,
        "created_at": incident["timestamp"],
        "evidence_count": incident["metadata"]["event_count"],
    }


def _fallback_incident(anomaly: AnomalyIn, metric: str, reason: str) -> dict:
    import uuid
    from datetime import datetime, timezone
    confidence = round(min(abs(anomaly.z_score) / 5.0, 1.0), 2)
    return {
        "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
        "timestamp": anomaly.timestamp,
        "namespace": anomaly.namespace,
        "severity": "high" if abs(anomaly.z_score) >= 3 else "medium",
        "root_cause": f"{metric}_anomaly",
        "summary": f"{metric} anomaly on {anomaly.pod} (z={anomaly.z_score:.2f})",
        "affected_pods": [anomaly.pod],
        "primary_metric": metric,
        "confidence": confidence,
        "pod_A": anomaly.pod,
        "pod_B": anomaly.pod,
        "metric": metric,
        "correlation": anomaly.z_score,
        "root_cause_pod": anomaly.pod,
        "created_at": anomaly.timestamp,
        "evidence_count": 1,
    }


class BatchAnomalyIn(BaseModel):
    events: list
    window_seconds: int = 60


@app.post("/correlate-batch")
def correlate_batch_endpoint(body: BatchAnomalyIn):
    """Correlate multiple events across pods, services, and namespaces."""
    scored_events = []
    for raw in body.events:
        metric = _METRIC_MAP.get(raw.get("metric", ""), raw.get("metric", "cpu"))
        unit = raw.get("unit") or _UNITS.get(metric, "value")
        source = raw.get("source") or f"{metric}-agent"
        event = {
            "timestamp": raw.get("timestamp", 0),
            "pod": raw.get("pod", "unknown"),
            "namespace": raw.get("namespace", "koral-system"),
            "metric": metric,
            "value": raw.get("value", 0.0),
            "unit": unit,
            "window_size": raw.get("window_size", 300),
            "source": source,
            "z_score": raw.get("z_score", 0.0),
            "is_anomaly": raw.get("is_anomaly", False),
        }
        try:
            scored_events.append(validate_event(event, final=True))
        except ValidationError:
            pass

    incidents = correlate_batch(scored_events, window_seconds=body.window_seconds)
    return {"incidents": incidents, "count": len(incidents)}


if __name__ == "__main__":
    import uvicorn
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from shared.mtls import get_uvicorn_ssl_kwargs
    ssl_kwargs = get_uvicorn_ssl_kwargs()
    uvicorn.run("main:app", host="0.0.0.0", port=8005, **ssl_kwargs)
