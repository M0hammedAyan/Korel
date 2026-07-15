"""
KORAL Remediation Planner - AI-based fix recommendation engine
Analyzes incidents and generates safe remediation plans
"""
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import httpx
import logging
from fastapi import FastAPI, HTTPException, Depends, Response
from pydantic import BaseModel
import sys
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KORAL Remediation Planner",
    version="1.0.0",
    description="AI-based fix recommendation and remediation planning"
)

# ── Configuration ──────────────────────────────────────────────────
BACKEND_URL          = os.getenv("BACKEND_URL", "http://backend:8000")
AI_ENGINE_URL        = os.getenv("AI_ENGINE_URL", "http://ai-engine:8006")
REMEDIATION_ENABLED  = os.getenv("REMEDIATION_ENABLED", "true").lower() == "true"
REMEDIATION_TIMEOUT  = int(os.getenv("REMEDIATION_TIMEOUT", "30"))
DEFAULT_NAMESPACE    = os.getenv("NAMESPACE", "koral-system")
K8S_API_URL          = os.getenv("K8S_API_URL", "https://kubernetes.default.svc")
K8S_TOKEN_FILE       = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CA_FILE          = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def _deployment_from_pod(pod_name: str) -> str:
    """Derive deployment name from pod name by stripping the two trailing hash segments."""
    parts = pod_name.rsplit("-", 2)
    return parts[0] if len(parts) == 3 else pod_name


async def _k8s_get(path: str) -> Optional[dict]:
    """Call the in-cluster Kubernetes API."""
    try:
        token = open(K8S_TOKEN_FILE).read().strip() if os.path.exists(K8S_TOKEN_FILE) else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(verify=K8S_CA_FILE if os.path.exists(K8S_CA_FILE) else False,
                                     timeout=5) as client:
            r = await client.get(f"{K8S_API_URL}{path}", headers=headers)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.debug(f"K8s API call failed ({path}): {e}")
    return None


async def _resolve_namespace(pod_name: str, hint: str) -> str:
    """Return the namespace the pod actually lives in, falling back to hint."""
    for ns_candidate in [hint, DEFAULT_NAMESPACE]:
        data = await _k8s_get(f"/api/v1/namespaces/{ns_candidate}/pods/{pod_name}")
        if data:
            return ns_candidate
    return hint or DEFAULT_NAMESPACE


async def _node_for_pod(pod_name: str, namespace: str) -> str:
    """Return the node name the pod is scheduled on."""
    data = await _k8s_get(f"/api/v1/namespaces/{namespace}/pods/{pod_name}")
    if data:
        return data.get("spec", {}).get("nodeName", "")
    return ""

# ── Models ─────────────────────────────────────────────────────────
class RemediationRequest(BaseModel):
    incident_id: str
    severity: str
    root_cause: str
    affected_pods: List[str]
    primary_metric: str
    z_score: float

class RemediationPlan(BaseModel):
    plan_id: str
    incident_id: str
    severity: str
    root_cause: str
    recommended_action: str
    confidence: float
    affected_pods: List[str]
    parameters: Dict
    ai_reasoning: str
    status: str = "pending"
    created_at: str
    expires_at: str

# ── Approved Commands ──────────────────────────────────────────────
APPROVED_COMMANDS = {
    "restart_pod": {
        "description": "Restart a specific pod",
        "parameters": {"pod_name": "str", "namespace": "str", "grace_period": "int"},
        "severity_threshold": "medium",
        "max_blast_radius": 1,
        "auto_approve_for": ["pod_restart_spike", "application_crash_loop"]
    },
    "restart_deployment": {
        "description": "Rolling restart of deployment",
        "parameters": {"deployment": "str", "namespace": "str", "timeout": "int"},
        "severity_threshold": "high",
        "max_blast_radius": 5,
        "auto_approve_for": ["service_latency_spike", "application_error_spike"]
    },
    "scale_deployment": {
        "description": "Scale deployment replicas",
        "parameters": {"deployment": "str", "namespace": "str", "replicas": "int"},
        "severity_threshold": "high",
        "max_blast_radius": 0,
        "auto_approve_for": ["cpu_saturation", "memory_pressure_or_oom"]
    },
    "clear_cache": {
        "description": "Clear application cache",
        "parameters": {"pod_name": "str", "namespace": "str", "cache_type": "str"},
        "severity_threshold": "medium",
        "max_blast_radius": 1,
        "auto_approve_for": ["storage_io_bottleneck"]
    },
    "drain_node": {
        "description": "Gracefully drain Kubernetes node",
        "parameters": {"node_name": "str", "timeout": "int", "ignore_daemonsets": "bool"},
        "severity_threshold": "critical",
        "max_blast_radius": -1,
        "auto_approve_for": []
    },
    "trigger_debug_logs": {
        "description": "Enable debug logging on pod",
        "parameters": {"pod_name": "str", "namespace": "str", "duration": "int"},
        "severity_threshold": "low",
        "max_blast_radius": 0,
        "auto_approve_for": []
    }
}

# ── Root Cause to Action Mapping ──────────────────────────────────
REMEDIATION_STRATEGIES = {
    "cpu_saturation": {
        "primary_action": "scale_deployment",
        "parameters": {"replicas": 3},
        "confidence": 0.95,
        "reasoning": "CPU saturation typically resolved by horizontal scaling"
    },
    "memory_pressure_or_oom": {
        "primary_action": "scale_deployment",
        "parameters": {"replicas": 2},
        "confidence": 0.90,
        "reasoning": "Memory pressure resolved by distributing load across more pods"
    },
    "storage_io_bottleneck": {
        "primary_action": "clear_cache",
        "parameters": {"cache_type": "all"},
        "confidence": 0.85,
        "reasoning": "Storage I/O bottleneck often caused by stale cache"
    },
    "network_latency_degradation": {
        "primary_action": "restart_pod",
        "parameters": {"grace_period": 30},
        "confidence": 0.75,
        "reasoning": "Network issues may resolve with pod restart to re-establish connections"
    },
    "application_crash_loop": {
        "primary_action": "restart_pod",
        "parameters": {"grace_period": 60},
        "confidence": 0.80,
        "reasoning": "Restart pod to attempt recovery from crash loop"
    },
    "service_latency_spike": {
        "primary_action": "restart_deployment",
        "parameters": {"timeout": 300},
        "confidence": 0.85,
        "reasoning": "Rolling restart to recover service health"
    },
    "pod_restart_spike": {
        "primary_action": "restart_pod",
        "parameters": {"grace_period": 30},
        "confidence": 0.80,
        "reasoning": "Single pod restart to stabilize"
    },
    "application_error_spike": {
        "primary_action": "restart_deployment",
        "parameters": {"timeout": 300},
        "confidence": 0.85,
        "reasoning": "Rolling restart to recover from application errors"
    },
    "unknown_anomalous_behavior": {
        "primary_action": "trigger_debug_logs",
        "parameters": {"duration": 600},
        "confidence": 0.50,
        "reasoning": "Enable debug logging to understand anomalous behavior"
    }
}

# ── Health Check ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "remediation-planner",
        "version": "1.0.0",
        "remediation_enabled": REMEDIATION_ENABLED
    }

# ── Create Remediation Plan ──────────────────────────────────────
@app.post("/create-plan", response_model=RemediationPlan)
async def create_remediation_plan(request: RemediationRequest):
    """Generate AI-based remediation plan"""
    if not REMEDIATION_ENABLED:
        raise HTTPException(status_code=503, detail="Remediation not enabled")
    
    logger.info(f"Creating remediation plan for incident {request.incident_id}")
    
    # Get remediation strategy for root cause
    strategy = REMEDIATION_STRATEGIES.get(
        request.root_cause,
        REMEDIATION_STRATEGIES["unknown_anomalous_behavior"]
    )
    
    plan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=1)).isoformat()

    action = strategy['primary_action']
    base_params = strategy['parameters'].copy()

    # Resolve real namespace and deployment/pod from affected_pods
    primary_pod = request.affected_pods[0] if request.affected_pods else ""
    namespace = await _resolve_namespace(primary_pod, DEFAULT_NAMESPACE) if primary_pod else DEFAULT_NAMESPACE
    deployment = _deployment_from_pod(primary_pod) if primary_pod else "unknown"

    if action == "scale_deployment":
        complete_params = {
            "deployment": deployment,
            "namespace": namespace,
            "replicas": base_params.get("replicas", 3),
        }
    elif action == "restart_deployment":
        complete_params = {
            "deployment": deployment,
            "namespace": namespace,
            "timeout": base_params.get("timeout", 300),
        }
    elif action == "restart_pod":
        complete_params = {
            "pod_name": primary_pod or "unknown",
            "namespace": namespace,
            "grace_period": base_params.get("grace_period", 30),
        }
    elif action == "clear_cache":
        complete_params = {
            "pod_name": primary_pod or "unknown",
            "namespace": namespace,
            "cache_type": base_params.get("cache_type", "all"),
        }
    elif action == "drain_node":
        node = await _node_for_pod(primary_pod, namespace) if primary_pod else ""
        complete_params = {
            "node_name": node or "unknown",
            "timeout": base_params.get("timeout", 300),
            "ignore_daemonsets": True,
        }
    elif action == "trigger_debug_logs":
        complete_params = {
            "pod_name": primary_pod or "unknown",
            "namespace": namespace,
            "duration": base_params.get("duration", 600),
        }
    else:
        complete_params = base_params
    
    ai_reasoning = (
        f"Incident Analysis:\n"
        f"- Root Cause: {request.root_cause}\n"
        f"- Severity: {request.severity}\n"
        f"- Affected Pods: {len(request.affected_pods)} (namespace: {namespace})\n"
        f"- Z-Score: {request.z_score:.2f}\n\n"
        f"Recommended Action: {strategy['primary_action']}\n"
        f"Confidence: {strategy['confidence']:.0%}\n"
        f"Reasoning: {strategy['reasoning']}\n\n"
        f"Parameters: {json.dumps(complete_params)}"
    )
    
    plan = RemediationPlan(
        plan_id=plan_id,
        incident_id=request.incident_id,
        severity=request.severity,
        root_cause=request.root_cause,
        recommended_action=strategy["primary_action"],
        confidence=strategy["confidence"],
        affected_pods=request.affected_pods,
        parameters=complete_params,
        ai_reasoning=ai_reasoning.strip(),
        status="pending",
        created_at=now.isoformat(),
        expires_at=expires_at
    )
    
    # Store plan in backend
    try:
        async with httpx.AsyncClient(timeout=REMEDIATION_TIMEOUT) as client:
            await client.post(
                f"{BACKEND_URL}/remediation/plans",
                json=plan.dict()
            )
    except Exception as e:
        logger.error(f"Failed to store plan: {e}")
        # Continue anyway - plan created locally
    
    logger.info(f"Created remediation plan {plan_id}: {plan.recommended_action}")
    return plan

# ── Get Remediation Plan ──────────────────────────────────────────
@app.get("/plan/{plan_id}", response_model=RemediationPlan)
async def get_plan(plan_id: str):
    """Retrieve remediation plan"""
    try:
        async with httpx.AsyncClient(timeout=REMEDIATION_TIMEOUT) as client:
            response = await client.get(f"{BACKEND_URL}/remediation/plans/{plan_id}")
            if response.status_code == 200:
                return RemediationPlan(**response.json())
    except Exception as e:
        logger.error(f"Failed to retrieve plan: {e}")
    
    raise HTTPException(status_code=404, detail="Plan not found")

# ── List Approved Commands ──────────────────────────────────────────
@app.get("/approved-commands")
async def list_approved_commands():
    """List all approved remediation commands"""
    return {
        "commands": APPROVED_COMMANDS,
        "total": len(APPROVED_COMMANDS),
        "remediation_enabled": REMEDIATION_ENABLED
    }

# ── Validate Plan Execution ──────────────────────────────────────
@app.post("/validate-execution")
async def validate_execution(plan_id: str, command: str, parameters: Dict):
    """Validate if execution is safe"""
    if command not in APPROVED_COMMANDS:
        return {
            "valid": False,
            "reason": f"Command '{command}' not in approved list"
        }
    
    cmd_spec = APPROVED_COMMANDS[command]
    
    # Validate parameters
    for param_name, param_type in cmd_spec["parameters"].items():
        if param_name not in parameters:
            return {
                "valid": False,
                "reason": f"Missing required parameter: {param_name}"
            }
    
    return {
        "valid": True,
        "command": command,
        "blast_radius_limit": cmd_spec["max_blast_radius"],
        "severity_required": cmd_spec["severity_threshold"]
    }

# ── Metrics ──────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007, workers=2)
