"""
KORAL Sandbox Executor - Safe command execution with allowlist and validation
Executes approved remediation commands with strict safety controls
"""
import os
import json
import uuid
import subprocess
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple, Any
import re
import httpx
import logging
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import sys
from executor import SandboxExecutor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KORAL Sandbox Executor",
    version="1.0.0",
    description="Safe command execution with strict safety controls"
)

sandbox_executor = SandboxExecutor(os.path.join(os.path.dirname(__file__), "allowed_commands.yaml"))

# ── Configuration ──────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
REMEDIATION_PLANNER_URL = os.getenv("REMEDIATION_PLANNER_URL", "http://remediation-planner:8007")
REMEDIATION_TIMEOUT = int(os.getenv("REMEDIATION_TIMEOUT_SECONDS", "300"))
MAX_PODS_PER_FIX = int(os.getenv("REMEDIATION_MAX_PODS_PER_FIX", "5"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
NAMESPACE = os.getenv("NAMESPACE", "koral-system")
ALLOW_CROSS_NAMESPACE = os.getenv("ALLOW_CROSS_NAMESPACE", "false").lower() == "true"

MAX_STDIO_CHARS = int(os.getenv("EXECUTOR_MAX_STDIO_CHARS", "2000"))

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_SAFE_K8S_RES_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}(/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127})?$")

# ── Models ─────────────────────────────────────────────────────────
class ExecutionRequest(BaseModel):
    approval_id: str
    plan_id: str
    incident_id: str
    command: str
    parameters: Dict
    affected_pods: List[str]

class ExecutionResult(BaseModel):
    execution_id: str
    plan_id: str
    status: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    pod_failures: List[str]
    blast_radius: int
    verification_status: str = "pending"

# ── Approved Commands (argv-only; no shell) ─────────────────────────
# IMPORTANT: This service must never execute arbitrary shell strings.
# Every approved action maps to a fixed argv shape with strictly validated parameters.
APPROVED_COMMANDS: Dict[str, Dict[str, Any]] = {
    # Note: Kubernetes does not support "rollout restart pod". Safe pod restart is delete (controller recreates).
    "restart_pod": {
        "params": {"pod_name": "k8s_name", "namespace": "k8s_name", "grace_period": "int"},
        "build_argv": lambda p: [
            "kubectl", "delete", f"pod/{p['pod_name']}", "-n", p["namespace"], f"--grace-period={p['grace_period']}"
        ],
    },
    "restart_deployment": {
        "params": {"deployment": "k8s_name", "namespace": "k8s_name"},
        "build_argv": lambda p: [
            "kubectl", "rollout", "restart", f"deployment/{p['deployment']}", "-n", p["namespace"]
        ],
    },
    "scale_deployment": {
        "params": {"deployment": "k8s_name", "namespace": "k8s_name", "replicas": "int"},
        "build_argv": lambda p: [
            "kubectl", "scale", f"deployment/{p['deployment']}", f"--replicas={p['replicas']}", "-n", p["namespace"]
        ],
    },
    "clear_cache": {
        "params": {"pod_name": "k8s_name", "namespace": "k8s_name"},
        "build_argv": lambda p: [
            "kubectl", "exec", p["pod_name"], "-n", p["namespace"], "--", "rm", "-rf", "/cache"
        ],
    },
    # Kept for later hardening (node actions are high-blast-radius). Still allowlisted, but should remain gated by approval policy.
    "drain_node": {
        "params": {"node_name": "k8s_name", "timeout_seconds": "int"},
        "build_argv": lambda p: [
            "kubectl", "drain", p["node_name"], "--ignore-daemonsets", "--delete-emptydir-data", f"--timeout={p['timeout_seconds']}s"
        ],
    },
    "trigger_debug_logs": {
        "params": {"pod_name": "k8s_name", "namespace": "k8s_name"},
        "build_argv": lambda p: [
            "kubectl", "exec", p["pod_name"], "-n", p["namespace"], "--", "sh", "-lc", "export LOG_LEVEL=DEBUG; echo OK"
        ],
        # NOTE: this still uses a shell inside the pod, not on the executor node. This is intentionally limited.
    },
}

# ── Execution Store ─────────────────────────────────────────────────
execution_store = {}

# ── Health Check ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "sandbox-executor",
        "version": "1.0.0",
        "dry_run": DRY_RUN,
        "timeout_seconds": REMEDIATION_TIMEOUT
    }

# ── Validate Execution ─────────────────────────────────────────────
def _coerce_and_validate_params(command: str, parameters: Dict) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Coerce types and strictly validate parameters for an approved command."""

    if command not in APPROVED_COMMANDS:
        return False, f"Command '{command}' not approved", None

    spec = APPROVED_COMMANDS[command]
    expected = spec["params"]

    # Strict allowlist of keys (no extras).
    extra = set(parameters.keys()) - set(expected.keys())
    if extra:
        return False, f"Unexpected parameters: {sorted(list(extra))}", None

    missing = [k for k in expected.keys() if k not in parameters]
    if missing:
        return False, f"Missing parameter(s): {missing}", None

    coerced: Dict[str, Any] = {}
    for key, typ in expected.items():
        raw = parameters.get(key)
        if typ == "int":
            try:
                coerced[key] = int(raw)
            except Exception:
                return False, f"Parameter '{key}' must be int", None
        elif typ == "k8s_name":
            if not isinstance(raw, str) or not _SAFE_NAME_RE.match(raw):
                return False, f"Parameter '{key}' must be a safe Kubernetes name", None
            coerced[key] = raw
        else:
            return False, f"Unsupported parameter type '{typ}' for '{key}'", None

    # Namespace containment by default
    if "namespace" in coerced and not ALLOW_CROSS_NAMESPACE:
        if coerced["namespace"] != NAMESPACE:
            return False, f"Cross-namespace execution blocked (namespace must be '{NAMESPACE}')", None

    # Guard rails
    if command == "scale_deployment":
        if coerced["replicas"] < 0 or coerced["replicas"] > 50:
            return False, "replicas out of allowed range (0..50)", None
    if command == "restart_pod":
        if coerced["grace_period"] < 0 or coerced["grace_period"] > 600:
            return False, "grace_period out of allowed range (0..600)", None
    if command == "drain_node":
        if coerced["timeout_seconds"] < 30 or coerced["timeout_seconds"] > 3600:
            return False, "timeout_seconds out of allowed range (30..3600)", None

    return True, None, coerced


def validate_execution(command: str, parameters: Dict, affected_pods: List[str]) -> tuple:
    """Validate execution parameters and blast radius."""
    
    ok, err, _ = _coerce_and_validate_params(command, parameters)
    if not ok:
        return False, err
    
    # Check blast radius
    blast_radius = len(affected_pods)
    
    if blast_radius > MAX_PODS_PER_FIX:
        return False, f"Blast radius {blast_radius} exceeds limit {MAX_PODS_PER_FIX}"
    
    return True, None

# ── Execute Command ──────────────────────────────────────────────
async def execute_command_safely(command: str, parameters: Dict) -> Dict:
    """Execute command with safety controls"""
    
    execution_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    try:
        ok, err, coerced = _coerce_and_validate_params(command, parameters)
        if not ok or coerced is None:
            return {
                "execution_id": execution_id,
                "status": "rejected",
                "exit_code": 2,
                "stdout": "",
                "stderr": err or "Rejected",
                "duration_ms": 0,
            }

        cmd_spec = APPROVED_COMMANDS[command]
        argv = cmd_spec["build_argv"](coerced)

        # Defensive: ensure argv is a list[str] and tokens are safe-ish.
        if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
            raise ValueError("Invalid argv from command builder")
        for token in argv:
            if len(token) > 512 or "\n" in token or "\r" in token:
                raise ValueError("Invalid argv token")
        logger.info(f"[Execution {execution_id}] argv={argv}")
        
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would execute argv={argv}")
            return {
                "execution_id": execution_id,
                "status": "success",
                "exit_code": 0,
                "stdout": "[DRY_RUN] Command would execute successfully (argv allowlist)",
                "stderr": "",
                "duration_ms": 100
            }
        
        # Execute with timeout
        try:
            result = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=REMEDIATION_TIMEOUT
            )
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return {
                "execution_id": execution_id,
                "status": "success" if result.returncode == 0 else "failed",
                "exit_code": result.returncode,
                "stdout": (result.stdout or "")[:MAX_STDIO_CHARS],
                "stderr": (result.stderr or "")[:MAX_STDIO_CHARS],
                "duration_ms": int(duration)
            }
        
        except subprocess.TimeoutExpired:
            return {
                "execution_id": execution_id,
                "status": "timeout",
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {REMEDIATION_TIMEOUT}s",
                "duration_ms": int(REMEDIATION_TIMEOUT * 1000)
            }
    
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return {
            "execution_id": execution_id,
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        }

# ── Execute Remediation ──────────────────────────────────────────
@app.post("/execute", response_model=ExecutionResult)
async def execute_remediation(request: ExecutionRequest):
    """Execute approved remediation command"""
    logger.info(f"Execute request: plan={request.plan_id}, command={request.command}")
    cmd_result = await sandbox_executor.submit(request)
    result = ExecutionResult(**cmd_result)
    execution_store[result.execution_id] = result.dict()
    logger.info(f"Execution complete: {result.execution_id} - status={result.status}")
    return result


@app.on_event("startup")
async def _startup():
    sandbox_executor.start()


@app.on_event("shutdown")
async def _shutdown():
    await sandbox_executor.stop()

# ── Get Execution History ──────────────────────────────────────────
@app.get("/executions/{plan_id}")
async def get_executions(plan_id: str):
    """Get execution history for a plan"""
    executions = [
        exec_data for exec_data in execution_store.values()
        if exec_data.get("plan_id") == plan_id
    ]
    return {"executions": executions, "count": len(executions)}

# ── Metrics ──────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8009)
