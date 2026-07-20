"""
KORAL Verification Engine - Post-fix validation and effectiveness measurement
Verifies remediation success by comparing pre/post metrics
"""
import os
import json
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import httpx
import logging
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import sys
import statistics
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KORAL Verification Engine",
    version="1.0.0",
    description="Post-fix validation and effectiveness measurement"
)

# ── Configuration ──────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BACKEND_API_KEY = os.getenv("API_KEY_OPERATOR", os.getenv("API_KEY", ""))
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
VERIFICATION_WAIT_SECONDS = int(os.getenv("VERIFICATION_WAIT_SECONDS", "60"))
SUCCESS_THRESHOLD = float(os.getenv("VERIFICATION_SUCCESS_THRESHOLD", "0.7"))
Z_SCORE_IMPROVEMENT_TARGET = float(os.getenv("Z_SCORE_IMPROVEMENT_TARGET", "1.5"))

# Map KORAL metric names to PromQL expressions
_METRIC_QUERIES = {
    "cpu":       'sum(rate(container_cpu_usage_seconds_total{{pod=~"{pods}"}}[2m])) by (pod) * 100',
    "memory":    'sum(container_memory_working_set_bytes{{pod=~"{pods}"}}) by (pod) / 1048576',
    "pvc_io":    'sum(rate(container_fs_reads_bytes_total{{pod=~"{pods}"}}[2m]) + rate(container_fs_writes_bytes_total{{pod=~"{pods}"}}[2m])) by (pod) / 1024',
    "log_error": 'sum(rate(fluentd_output_status_emit_records_total{{pod=~"{pods}"}}[2m])) by (pod)',
    "network":   'sum(rate(container_network_receive_bytes_total{{pod=~"{pods}"}}[2m]) + rate(container_network_transmit_bytes_total{{pod=~"{pods}"}}[2m])) by (pod) / 1048576',
}

# ── Models ─────────────────────────────────────────────────────────
class VerificationRequest(BaseModel):
    execution_id: str
    plan_id: str
    incident_id: str
    affected_pods: List[str]
    primary_metric: str
    pre_metrics: Dict

class VerificationResult(BaseModel):
    verification_id: str
    execution_id: str
    plan_id: str
    status: str
    verification_status: str
    pre_metrics: Dict
    post_metrics: Dict
    improvement_percent: float
    anomaly_resolved: bool
    z_score_delta: float
    verification_details: str
    duration_ms: int

# ── Verification Store ──────────────────────────────────────────────
verification_store = {}

# ── Health Check ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "verification-engine",
        "version": "1.0.0",
        "success_threshold": SUCCESS_THRESHOLD,
        "verification_wait_seconds": VERIFICATION_WAIT_SECONDS
    }

# ── Query Prometheus Metrics ──────────────────────────────────────
async def query_metrics(metric_name: str, pods: List[str]) -> Dict:
    """Query Prometheus for current metric values across affected pods."""
    try:
        pod_regex = "|".join(pods[:5])
        expr_template = _METRIC_QUERIES.get(
            metric_name,
            'avg(rate(container_cpu_usage_seconds_total{{pod=~"{pods}"}}[2m])) by (pod)'
        )
        query = expr_template.format(pods=pod_regex)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
            if r.status_code != 200:
                logger.warning(f"Prometheus returned {r.status_code} for query: {query}")
                return {}
            result = r.json().get("data", {}).get("result", [])
            if not result:
                logger.warning(f"No Prometheus data for metric={metric_name} pods={pods}")
                return {}
            values = [float(item["value"][1]) for item in result if len(item.get("value", [])) > 1]
            if not values:
                return {}
            return {
                "mean":   statistics.mean(values),
                "median": statistics.median(values),
                "stdev":  statistics.stdev(values) if len(values) > 1 else 0.0,
                "min":    min(values),
                "max":    max(values),
                "count":  len(values),
            }
    except Exception as e:
        logger.error(f"Failed to query Prometheus: {e}")
        return {}

# ── Calculate Z-Score ────────────────────────────────────────────
def calculate_z_score(value: float, mean: float, stdev: float) -> float:
    """Calculate Z-score"""
    if stdev == 0:
        return 0
    return (value - mean) / stdev

# ── Verify Remediation ──────────────────────────────────────────
@app.get("/pre-metrics")
async def get_pre_metrics(metric: str, pods: str):
    """Fetch current metric snapshot before remediation executes."""
    pod_list = [p.strip() for p in pods.split(",") if p.strip()]
    data = await query_metrics(metric, pod_list)
    return {"metric": metric, "pods": pod_list, "snapshot": data}


@app.post("/verify", response_model=VerificationResult)
async def verify_remediation(request: VerificationRequest):
    """Verify remediation effectiveness"""
    
    verification_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    logger.info(f"Verifying remediation: exec={request.execution_id}, metric={request.primary_metric}")
    
    # Wait for metrics to stabilize
    logger.info(f"Waiting {VERIFICATION_WAIT_SECONDS}s for metrics to stabilize...")
    await asyncio.sleep(VERIFICATION_WAIT_SECONDS)
    
    # Query post-remediation metrics
    post_metrics = await query_metrics(request.primary_metric, request.affected_pods)
    
    if not post_metrics:
        logger.warning("Failed to retrieve post-remediation metrics")
        return VerificationResult(
            verification_id=verification_id,
            execution_id=request.execution_id,
            plan_id=request.plan_id,
            status="failed",
            verification_status="inconclusive",
            pre_metrics=request.pre_metrics,
            post_metrics={},
            improvement_percent=0.0,
            anomaly_resolved=False,
            z_score_delta=0.0,
            verification_details="Could not retrieve post-remediation metrics",
            duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        )
    
    pre_mean  = request.pre_metrics.get("mean", 0.0)
    pre_stdev = request.pre_metrics.get("stdev", 1.0) or 1.0
    post_mean = post_metrics.get("mean", 0.0)

    improvement_percent = ((pre_mean - post_mean) / pre_mean * 100) if pre_mean > 0 else 0.0

    # Z-score delta: how many pre-stdev units did the mean drop?
    z_score_delta = (pre_mean - post_mean) / pre_stdev
    
    # Determine if remediation was successful
    success = (
        improvement_percent >= SUCCESS_THRESHOLD * 100 or
        z_score_delta >= Z_SCORE_IMPROVEMENT_TARGET
    )
    
    details = (
        f"Pre-remediation mean: {pre_mean:.2f} (stdev: {pre_stdev:.2f})\n"
        f"Post-remediation mean: {post_mean:.2f}\n"
        f"Improvement: {improvement_percent:.1f}%\n"
        f"Z-score delta: {z_score_delta:.2f}\n"
        f"Success: {success}"
    )
    
    result = VerificationResult(
        verification_id=verification_id,
        execution_id=request.execution_id,
        plan_id=request.plan_id,
        status="success" if success else "partial_success",
        verification_status="resolved" if success else "improving",
        pre_metrics=request.pre_metrics,
        post_metrics=post_metrics,
        improvement_percent=improvement_percent,
        anomaly_resolved=success,
        z_score_delta=z_score_delta,
        verification_details=details.strip(),
        duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    )

    # Store result in-memory
    verification_store[verification_id] = result.dict()

    # Persist to backend DB
    try:
        from shared.mtls import get_mtls_client
        headers = {"X-API-Key": BACKEND_API_KEY} if BACKEND_API_KEY else {}
        async with get_mtls_client(timeout=10) as client:
            await client.post(
                f"{BACKEND_URL}/remediation/verifications",
                json=result.dict(),
                headers=headers,
            )
    except Exception as e:
        logger.warning(f"Failed to persist verification to backend: {e}")

    logger.info(f"Verification complete: {verification_id} - status={result.verification_status}")

    return result

# ── Get Verification Result ──────────────────────────────────────
@app.get("/result/{verification_id}", response_model=VerificationResult)
async def get_verification(verification_id: str):
    """Get verification result"""
    if verification_id not in verification_store:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    return VerificationResult(**verification_store[verification_id])

# ── Metrics ──────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from shared.mtls import get_uvicorn_ssl_kwargs
    ssl_kwargs = get_uvicorn_ssl_kwargs()
    uvicorn.run(app, host="0.0.0.0", port=8010, workers=2, **ssl_kwargs)
