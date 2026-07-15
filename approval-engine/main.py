import os
import uuid
import smtplib
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from db import init_db, insert_approval, get_approval, update_approval, list_approvals
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="KORAL Approval Engine", version="1.0.0")

BACKEND_URL             = os.getenv("BACKEND_URL", "http://backend:8000")
APPROVAL_EMAIL          = os.getenv("APPROVAL_EMAIL", "remediation@koral.local")
APPROVAL_RECIPIENTS     = os.getenv("APPROVAL_RECIPIENTS", "admin@example.com").split(",")
APPROVAL_TIMEOUT_MINUTES = int(os.getenv("APPROVAL_TIMEOUT_MINUTES", "30"))
AUTO_APPROVE_MINOR      = os.getenv("AUTO_APPROVE_MINOR", "false").lower() == "true"
SMTP_HOST               = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT               = int(os.getenv("SMTP_PORT", "1025"))
DISABLE_EMAIL           = os.getenv("DISABLE_EMAIL", "true").lower() == "true"


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Approval DB initialised")


class ApprovalRequest(BaseModel):
    plan_id: str
    incident_id: str
    severity: str
    root_cause: str
    recommended_action: str
    confidence: float
    affected_pods: list
    parameters: Dict
    ai_reasoning: str


class ApprovalActionRequest(BaseModel):
    approver_email: Optional[str] = None
    reason: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "approval-engine", "version": "1.0.0",
            "auto_approve_enabled": AUTO_APPROVE_MINOR}


def _send_email(approval_id: str, plan_id: str, severity: str,
                root_cause: str, action: str, affected_pods: list) -> bool:
    if DISABLE_EMAIL:
        logger.info(f"[EMAIL DISABLED] Would send approval email to {APPROVAL_RECIPIENTS}")
        return True
    try:
        subject = f"[KORAL] Remediation Approval Required - {severity.upper()} - {root_cause}"
        approval_link = f"http://koral-dashboard/approval?id={approval_id}"
        html = f"""<html><body>
        <h2>KORAL Remediation Approval Required</h2>
        <p><strong>Severity:</strong> {severity.upper()}</p>
        <p><strong>Root Cause:</strong> {root_cause}</p>
        <p><strong>Recommended Action:</strong> {action}</p>
        <p><strong>Affected Pods:</strong> {', '.join(affected_pods[:5])}{'...' if len(affected_pods) > 5 else ''}</p>
        <p><a href="{approval_link}">Review and Approve</a></p>
        <p><small>Plan ID: {plan_id} | Approval ID: {approval_id} | Expires in {APPROVAL_TIMEOUT_MINUTES} min</small></p>
        </body></html>"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = APPROVAL_EMAIL
        msg["To"] = ", ".join(APPROVAL_RECIPIENTS)
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.sendmail(APPROVAL_EMAIL, APPROVAL_RECIPIENTS, msg.as_string())
        logger.info(f"Sent approval email for {plan_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send approval email: {e}")
        return False


@app.post("/request-approval")
async def request_approval(request: ApprovalRequest):
    approval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=APPROVAL_TIMEOUT_MINUTES)).isoformat()
    created_at = now.isoformat()

    if AUTO_APPROVE_MINOR and request.severity in ["low", "medium"]:
        insert_approval(
            approval_id=approval_id, plan_id=request.plan_id,
            incident_id=request.incident_id, severity=request.severity,
            root_cause=request.root_cause, recommended_action=request.recommended_action,
            confidence=request.confidence, affected_pods=request.affected_pods,
            parameters=request.parameters, ai_reasoning=request.ai_reasoning,
            status="approved", email_sent=False, auto_approved=True,
            created_at=created_at, expires_at=expires_at,
            approver="auto-system", approved_at=created_at,
        )
        logger.info(f"Auto-approved plan {request.plan_id}")
        return {"approval_id": approval_id, "status": "approved",
                "auto_approved": True, "reason": "Auto-approved for minor severity"}

    email_sent = _send_email(
        approval_id, request.plan_id, request.severity,
        request.root_cause, request.recommended_action, request.affected_pods
    )
    insert_approval(
        approval_id=approval_id, plan_id=request.plan_id,
        incident_id=request.incident_id, severity=request.severity,
        root_cause=request.root_cause, recommended_action=request.recommended_action,
        confidence=request.confidence, affected_pods=request.affected_pods,
        parameters=request.parameters, ai_reasoning=request.ai_reasoning,
        status="pending", email_sent=email_sent, auto_approved=False,
        created_at=created_at, expires_at=expires_at,
    )
    logger.info(f"Created approval {approval_id} for plan {request.plan_id}")
    return {"approval_id": approval_id, "status": "pending",
            "email_sent": email_sent, "expires_in_minutes": APPROVAL_TIMEOUT_MINUTES}


@app.patch("/approvals/{approval_id}/approve")
async def approve(approval_id: str, payload: ApprovalActionRequest):
    row = get_approval(approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already {row['status']}")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        update_approval(approval_id, "expired", "", "", "approved_at", datetime.now(timezone.utc).isoformat())
        raise HTTPException(status_code=400, detail="Approval request expired")
    approved_at = datetime.now(timezone.utc).isoformat()
    update_approval(approval_id, "approved",
                    payload.approver_email or "dashboard",
                    payload.reason or "Approved via dashboard",
                    "approved_at", approved_at)
    logger.info(f"Approved {approval_id}")
    return {"approval_id": approval_id, "status": "approved",
            "approved_by": payload.approver_email, "approved_at": approved_at}


@app.patch("/approvals/{approval_id}/reject")
async def reject(approval_id: str, payload: ApprovalActionRequest):
    row = get_approval(approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already {row['status']}")
    rejected_at = datetime.now(timezone.utc).isoformat()
    update_approval(approval_id, "rejected",
                    payload.approver_email or "dashboard",
                    payload.reason or "Rejected via dashboard",
                    "rejected_at", rejected_at)
    logger.info(f"Rejected {approval_id}")
    return {"approval_id": approval_id, "status": "rejected",
            "rejected_by": payload.approver_email, "rejected_at": rejected_at}


# Legacy endpoints kept for backward compatibility
@app.post("/approve")
async def approve_legacy(approval_id: str, approver_email: str, reason: Optional[str] = None):
    return await approve(approval_id, ApprovalActionRequest(approver_email=approver_email, reason=reason))


@app.post("/reject")
async def reject_legacy(approval_id: str, approver_email: str, reason: str):
    return await reject(approval_id, ApprovalActionRequest(approver_email=approver_email, reason=reason))


@app.get("/status/{approval_id}")
async def check_status(approval_id: str):
    row = get_approval(approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"approval_id": approval_id, "status": row["status"],
            "created_at": row["created_at"], "expires_at": row["expires_at"],
            "approver": row.get("approver")}


@app.get("/approvals")
async def list_all(status: Optional[str] = None):
    return list_approvals(status=status)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
