"""
KORAL Backend - Remediation Routes
Orchestrates the remediation workflow across all services
"""
import os
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.rbac import require_viewer, require_operator, require_admin
from backend.audit import write_audit
import logging

from backend.database_remediation import (
    add_remediation_plan,
    get_remediation_plan as db_get_remediation_plan,
    list_remediation_plans as db_list_remediation_plans,
    count_remediation_plans as db_count_remediation_plans,
    add_execution,
    get_execution as db_get_execution,
    list_executions as db_list_executions,
    add_verification,
    get_verification as db_get_verification,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remediation", tags=["remediation"])

# ── Configuration ──────────────────────────────────────────────────
REMEDIATION_PLANNER_URL  = os.getenv("REMEDIATION_PLANNER_URL", "http://remediation-planner:8007")
APPROVAL_ENGINE_URL      = os.getenv("APPROVAL_ENGINE_URL", "http://approval-engine:8008")
SANDBOX_EXECUTOR_URL     = os.getenv("SANDBOX_EXECUTOR_URL", "http://sandbox-executor:8009")
VERIFICATION_ENGINE_URL  = os.getenv("VERIFICATION_ENGINE_URL", "http://verification-engine:8010")
NOTIFIER_URL             = os.getenv("NOTIFIER_URL", "http://notifier:8011")
REMEDIATION_ENABLED      = os.getenv("REMEDIATION_ENABLED", "false").lower() == "true"


async def _fetch_pre_metrics(metric: str, pods: list) -> dict:
    """Fetch baseline metrics from verification engine before execution."""
    try:
        pods_param = ",".join(pods[:5])
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{VERIFICATION_ENGINE_URL}/pre-metrics",
                params={"metric": metric, "pods": pods_param},
            )
            if r.status_code == 200:
                return r.json().get("snapshot", {})
    except Exception as e:
        logger.warning(f"Could not fetch pre-metrics: {e}")
    return {}

# ── Models ─────────────────────────────────────────────────────────
class RemediationPlanCreate(BaseModel):
    incident_id: str
    severity: str
    root_cause: str
    affected_pods: list
    primary_metric: str
    z_score: float

class RemediationStatus(BaseModel):
    status: str
    enabled: bool
    plan_count: int
    execution_count: int


class ApprovalActionRequest(BaseModel):
    approver_email: Optional[str] = None
    reason: Optional[str] = None

# NOTE: workflow durability — executions and verifications now persisted in DB

# ── Health Check ──────────────────────────────────────────────────
@router.get("/status", dependencies=[Depends(require_viewer)])
async def remediation_status() -> RemediationStatus:
    """Get remediation system status"""
    import asyncio
    try:
        plan_count = await asyncio.to_thread(db_count_remediation_plans)
    except Exception as e:
        logger.warning(f"Failed to count remediation plans: {e}")
        plan_count = 0

    try:
        execution_count = len(await asyncio.to_thread(db_list_executions, 1000))
    except Exception as e:
        logger.warning(f"Failed to count executions: {e}")
        execution_count = 0

    return RemediationStatus(
        status="operational" if REMEDIATION_ENABLED else "disabled",
        enabled=REMEDIATION_ENABLED,
        plan_count=plan_count,
        execution_count=execution_count,
    )

# ── Create Remediation Plan ──────────────────────────────────────
@router.post("/plans", dependencies=[Depends(require_operator)])
async def create_remediation_plan(incident: RemediationPlanCreate):
    """Create remediation plan via AI analysis"""
    
    if not REMEDIATION_ENABLED:
        raise HTTPException(status_code=503, detail="Remediation system not enabled")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{REMEDIATION_PLANNER_URL}/create-plan",
                json=incident.dict()
            )
            
            if response.status_code == 200:
                plan = response.json()
                try:
                    add_remediation_plan(
                        plan_id=plan["plan_id"],
                        incident_id=plan["incident_id"],
                        severity=plan.get("severity"),
                        root_cause=plan.get("root_cause"),
                        recommended_action=plan.get("recommended_action"),
                        confidence=plan.get("confidence"),
                        affected_pods=plan.get("affected_pods", []),
                        parameters=plan.get("parameters", {}),
                        ai_reasoning=plan.get("ai_reasoning", ""),
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist plan {plan.get('plan_id')}: {e}")
                logger.info(f"Created remediation plan: {plan['plan_id']}")
                return plan
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to create plan")
    
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Get Remediation Plan ──────────────────────────────────────────
@router.get("/plans/{plan_id}", dependencies=[Depends(require_viewer)])
async def get_remediation_plan(plan_id: str):
    """Get remediation plan details"""
    import asyncio
    plan = await asyncio.to_thread(db_get_remediation_plan, plan_id)
    if plan:
        return plan
    raise HTTPException(status_code=404, detail="Plan not found")

# ── Request Approval ──────────────────────────────────────────────
@router.post("/approve/{plan_id}", dependencies=[Depends(require_operator)])
async def request_approval(plan_id: str):
    """Request approval for remediation plan"""
    
    plan = db_get_remediation_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{APPROVAL_ENGINE_URL}/request-approval",
                json={
                    "plan_id": plan["plan_id"],
                    "incident_id": plan["incident_id"],
                    "severity": plan["severity"],
                    "root_cause": plan["root_cause"],
                    "recommended_action": plan["recommended_action"],
                    "confidence": plan["confidence"],
                    "affected_pods": plan["affected_pods"],
                    "parameters": plan["parameters"],
                    "ai_reasoning": plan["ai_reasoning"]
                }
            )
            
            if response.status_code == 200:
                approval = response.json()
                write_audit("remediation.approval_requested", "system", plan_id,
                            {"approval_id": approval.get("approval_id"), "severity": plan.get("severity")})
                logger.info(f"Approval requested: {approval['approval_id']}")
                return approval
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to request approval")
    
    except Exception as e:
        logger.error(f"Error requesting approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Execute Remediation ──────────────────────────────────────────
@router.post("/execute/{plan_id}", dependencies=[Depends(require_admin)])
async def execute_remediation(plan_id: str, approval_id: str):
    """Execute approved remediation plan"""
    
    plan = db_get_remediation_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            # Check approval status AND expiry
            approval_check = await client.get(
                f"{APPROVAL_ENGINE_URL}/status/{approval_id}"
            )
            if approval_check.status_code != 200:
                raise HTTPException(status_code=403, detail="Could not verify approval status")
            approval_data = approval_check.json()
            if approval_data.get("status") != "approved":
                raise HTTPException(status_code=403, detail="Plan not approved")
            # Enforce expiry at execution time
            expires_at_str = approval_data.get("expires_at")
            if expires_at_str:
                try:
                    from datetime import datetime, timezone
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at < datetime.now(timezone.utc):
                        raise HTTPException(status_code=403, detail="Approval has expired")
                except HTTPException:
                    raise
                except Exception:
                    pass  # malformed date — let it through rather than block

            # Collect pre-execution baseline metrics
            pre_metrics = await _fetch_pre_metrics(
                plan.get("primary_metric", plan.get("recommended_action", "cpu")),
                plan["affected_pods"],
            )
            logger.info(f"Pre-metrics for {plan_id}: {pre_metrics}")

            # Execute command
            response = await client.post(
                f"{SANDBOX_EXECUTOR_URL}/execute",
                json={
                    "approval_id": approval_id,
                    "plan_id": plan["plan_id"],
                    "incident_id": plan["incident_id"],
                    "command": plan["recommended_action"],
                    "parameters": plan["parameters"],
                    "affected_pods": plan["affected_pods"],
                }
            )
            if response.status_code == 200:
                execution = response.json()
                execution["pre_metrics"] = pre_metrics
                try:
                    add_execution(
                        execution_id=execution["execution_id"],
                        plan_id=plan["plan_id"],
                        incident_id=plan["incident_id"],
                        command=plan.get("recommended_action", ""),
                        parameters=plan.get("parameters", {}),
                        execution_status=execution.get("status", "success"),
                        start_time=execution.get("start_time", ""),
                        end_time=execution.get("end_time", ""),
                        duration_ms=execution.get("duration_ms", 0),
                        stdout=execution.get("stdout", ""),
                        stderr=execution.get("stderr", ""),
                        exit_code=execution.get("exit_code", 0),
                        blast_radius=execution.get("blast_radius", 0),
                        pod_failures=execution.get("pod_failures", []),
                        pre_metrics=pre_metrics,
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist execution {execution.get('execution_id')}: {e}")
                write_audit("remediation.executed", "system", plan_id,
                            {"execution_id": execution["execution_id"],
                             "command": plan.get("recommended_action"),
                             "affected_pods": plan.get("affected_pods")})
                logger.info(f"Executed remediation: {execution['execution_id']}")
                return execution
            else:
                raise HTTPException(status_code=response.status_code, detail="Execution failed")
    
    except Exception as e:
        logger.error(f"Error executing remediation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Verify Remediation ──────────────────────────────────────────
@router.post("/verify/{execution_id}", dependencies=[Depends(require_operator)])
async def verify_remediation(execution_id: str, plan_id: str, primary_metric: str):
    """Verify remediation effectiveness"""
    
    execution = db_get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    plan = db_get_remediation_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            response = await client.post(
                f"{VERIFICATION_ENGINE_URL}/verify",
                json={
                    "execution_id": execution_id,
                    "plan_id": plan_id,
                    "incident_id": plan["incident_id"],
                    "affected_pods": plan["affected_pods"],
                    "primary_metric": primary_metric,
                    "pre_metrics": execution.get("pre_metrics") or {},
                }
            )
            
            if response.status_code == 200:
                verification = response.json()
                try:
                    add_verification(
                        verification_id=verification["verification_id"],
                        execution_id=execution_id,
                        plan_id=plan_id,
                        incident_id=plan["incident_id"],
                        verification_status=verification.get("verification_status", ""),
                        pre_metrics=verification.get("pre_metrics", {}),
                        post_metrics=verification.get("post_metrics", {}),
                        improvement_percent=verification.get("improvement_percent", 0.0),
                        anomaly_resolved=verification.get("anomaly_resolved", False),
                        z_score_delta=verification.get("z_score_delta", 0.0),
                        verification_details=verification.get("verification_details", ""),
                        duration_ms=verification.get("duration_ms", 0),
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist verification {verification.get('verification_id')}: {e}")
                write_audit("remediation.verified", "system", plan_id,
                            {"verification_id": verification["verification_id"],
                             "status": verification.get("verification_status"),
                             "improvement_percent": verification.get("improvement_percent")})
                logger.info(f"Verification complete: {verification['verification_id']}")
                return verification
            else:
                raise HTTPException(status_code=response.status_code, detail="Verification failed")
    
    except Exception as e:
        logger.error(f"Error verifying remediation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Send Notification ──────────────────────────────────────────
@router.post("/notify/{incident_id}", dependencies=[Depends(require_operator)])
async def send_remediation_notification(incident_id: str, severity: str, root_cause: str, 
                                       status: str, message: str, affected_pods: list,
                                       plan_id: Optional[str] = None,
                                       execution_id: Optional[str] = None):
    """Send remediation notification"""
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{NOTIFIER_URL}/notify",
                json={
                    "incident_id": incident_id,
                    "severity": severity,
                    "root_cause": root_cause,
                    "status": status,
                    "message": message,
                    "affected_pods": affected_pods,
                    "remediation_plan_id": plan_id,
                    "execution_id": execution_id
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Notification sent for {incident_id}")
                return response.json()
            else:
                logger.warning(f"Notification failed: {response.status_code}")
                return {}
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {}

# ── List Plans ──────────────────────────────────────────────────
@router.get("/plans", dependencies=[Depends(require_viewer)])
async def list_remediation_plans(limit: int = 100):
    """List all remediation plans"""
    import asyncio
    try:
        plans_list = await asyncio.to_thread(db_list_remediation_plans, limit)
    except Exception as e:
        logger.warning(f"Failed to list remediation plans: {e}")
        plans_list = []

    return {
        "count": len(plans_list),
        "plans": plans_list
    }

# ── List Executions ────────────────────────────────────────────
@router.get("/executions", dependencies=[Depends(require_viewer)])
async def list_executions_route(limit: int = 100):
    """List all execution records"""
    import asyncio
    executions_list = await asyncio.to_thread(db_list_executions, limit)
    return {
        "count": len(executions_list),
        "executions": executions_list
    }


# ── Compatibility Endpoints For Legacy Frontend ──────────────────
@router.get("/operations", dependencies=[Depends(require_viewer)])
async def list_operations(limit: int = 100):
    """Legacy endpoint: returns operations as a flat array."""
    try:
        plans_list = db_list_remediation_plans(limit=limit)
    except Exception as e:
        logger.warning(f"Failed to list operations from plans: {e}")
        plans_list = []

    operations = []
    all_executions = db_list_executions(limit=1000)
    exec_by_plan = {e.get("plan_id"): e for e in all_executions}

    for plan in plans_list:
        execution = exec_by_plan.get(plan.get("plan_id"))
        operations.append(
            {
                "plan_id": plan.get("plan_id"),
                "incident_id": plan.get("incident_id"),
                "status": plan.get("status", "pending"),
                "recommended_action": plan.get("recommended_action", "N/A"),
                "severity": plan.get("severity", "medium"),
                "created_at": plan.get("created_at", datetime.now(timezone.utc).isoformat()),
                "updated_at": plan.get("updated_at", datetime.now(timezone.utc).isoformat()),
                "execution_status": execution.get("execution_status") if execution else None,
                "verification_status": None,
                "improvement_percent": None,
            }
        )

    return operations


@router.get("/approvals", dependencies=[Depends(require_viewer)])
async def list_pending_approvals():
    """Legacy endpoint: returns pending approvals as an array."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{APPROVAL_ENGINE_URL}/approvals")
            if response.status_code == 200 and isinstance(response.json(), list):
                return response.json()
    except Exception as e:
        logger.debug(f"Approvals endpoint unavailable, returning empty list: {e}")

    return []


@router.patch("/approvals/{approval_id}/approve", dependencies=[Depends(require_operator)])
async def approve_approval(approval_id: str, payload: ApprovalActionRequest):
    """Legacy endpoint: approve an approval request."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{APPROVAL_ENGINE_URL}/approvals/{approval_id}/approve",
                json={
                    "approver_email": payload.approver_email,
                    "reason": payload.reason,
                },
            )
            if response.status_code < 400:
                result = response.json() if response.content else {"status": "approved", "approval_id": approval_id}
                write_audit("remediation.approved", payload.approver_email or "dashboard", approval_id,
                            {"reason": payload.reason})
                return result
            raise HTTPException(status_code=response.status_code, detail="Approval engine rejected the request")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval engine unavailable for approve {approval_id}: {e}")
        raise HTTPException(status_code=503, detail="Approval engine unavailable — cannot approve")


@router.patch("/approvals/{approval_id}/reject", dependencies=[Depends(require_operator)])
async def reject_approval(approval_id: str, payload: ApprovalActionRequest):
    """Legacy endpoint: reject an approval request."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{APPROVAL_ENGINE_URL}/approvals/{approval_id}/reject",
                json={
                    "reason": payload.reason,
                },
            )
            if response.status_code < 400:
                result = response.json() if response.content else {"status": "rejected", "approval_id": approval_id}
                write_audit("remediation.rejected", payload.approver_email or "dashboard", approval_id,
                            {"reason": payload.reason})
                return result
            raise HTTPException(status_code=response.status_code, detail="Approval engine rejected the request")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval engine unavailable for reject {approval_id}: {e}")
        raise HTTPException(status_code=503, detail="Approval engine unavailable — cannot process rejection")
