"""
KORAL Notifier - Multi-channel notification service
Sends alerts via Telegram, Email, and Slack
"""
import os
import json
import logging
import smtplib
from datetime import datetime, timezone
from typing import Dict, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import sys
from notification.telegram import send_telegram_alert, format_telegram_message
from backend.slack_notify import send_slack_alert
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KORAL Notifier",
    version="1.0.0",
    description="Multi-channel notification service"
)

# ── Configuration ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", os.getenv("SLACK_WEBHOOK", ""))
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "koral@example.com")
NOTIFICATION_RECIPIENTS = os.getenv("NOTIFICATION_RECIPIENTS", "admin@example.com").split(",")
DISABLE_EMAIL = os.getenv("DISABLE_EMAIL", "true").lower() == "true"
DISABLE_TELEGRAM = os.getenv("DISABLE_TELEGRAM", "true").lower() == "true"
DISABLE_SLACK = os.getenv("DISABLE_SLACK", "true").lower() == "true"

# ── Models ─────────────────────────────────────────────────────────
class Notification(BaseModel):
    incident_id: str
    severity: str
    root_cause: str
    status: str
    message: str
    affected_pods: List[str]
    service: Optional[str] = None
    issue: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence: Optional[float] = None
    remediation_plan_id: Optional[str] = None
    execution_id: Optional[str] = None
    verification_id: Optional[str] = None

# ── Health Check ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "notifier",
        "version": "1.0.0",
        "telegram_enabled": not DISABLE_TELEGRAM and bool(TELEGRAM_BOT_TOKEN),
        "email_enabled": not DISABLE_EMAIL,
        "slack_enabled": not DISABLE_SLACK and bool(SLACK_WEBHOOK_URL)
    }

# ── Send Email Notification ──────────────────────────────────────
async def send_email_notification(notification: Notification) -> bool:
    """Send email notification"""
    if DISABLE_EMAIL:
        logger.info(f"[EMAIL DISABLED] Would send to {NOTIFICATION_RECIPIENTS}")
        return True
    
    try:
        subject = f"[KORAL] {notification.severity.upper()} - {notification.root_cause}: {notification.status}"
        
        html_body = f"""
        <html>
        <body>
        <h2>KORAL Alert</h2>
        <table border="1" cellpadding="10">
        <tr><td><strong>Incident ID</strong></td><td>{notification.incident_id}</td></tr>
        <tr><td><strong>Severity</strong></td><td>{notification.severity.upper()}</td></tr>
        <tr><td><strong>Root Cause</strong></td><td>{notification.root_cause}</td></tr>
        <tr><td><strong>Status</strong></td><td>{notification.status}</td></tr>
        <tr><td><strong>Message</strong></td><td>{notification.message}</td></tr>
        <tr><td><strong>Affected Pods</strong></td><td>{', '.join(notification.affected_pods[:5])}</td></tr>
        {f'<tr><td><strong>Remediation Plan</strong></td><td>{notification.remediation_plan_id}</td></tr>' if notification.remediation_plan_id else ''}
        {f'<tr><td><strong>Execution ID</strong></td><td>{notification.execution_id}</td></tr>' if notification.execution_id else ''}
        {f'<tr><td><strong>Verification ID</strong></td><td>{notification.verification_id}</td></tr>' if notification.verification_id else ''}
        </table>
        <p><small>Generated: {datetime.now(timezone.utc).isoformat()}</small></p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = NOTIFICATION_EMAIL
        msg["To"] = ", ".join(NOTIFICATION_RECIPIENTS)
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.sendmail(NOTIFICATION_EMAIL, NOTIFICATION_RECIPIENTS, msg.as_string())
        
        logger.info(f"Sent email notification for {notification.incident_id}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

# ── Send Telegram Notification ──────────────────────────────────
async def send_telegram_notification(notification: Notification) -> bool:
    """Send Telegram notification"""
    if DISABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN:
        logger.info("[TELEGRAM DISABLED] Would send to Telegram")
        return True
    try:
        message = format_telegram_message(notification.model_dump())
        return await send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
    except Exception as e:
        logger.error(f"Failed to send Telegram: {e}")
        return False

# ── Send Slack Notification ──────────────────────────────────────
async def send_slack_notification(notification: Notification) -> bool:
    """Send Slack notification"""
    if DISABLE_SLACK or not SLACK_WEBHOOK_URL:
        logger.info("[SLACK DISABLED] Would send to Slack")
        return True

    try:
        return send_slack_alert(
            service=notification.service or "backend",
            issue=notification.issue or notification.message,
            root_cause=notification.root_cause,
            suggested_fix=notification.suggested_fix or notification.message,
            confidence=notification.confidence if notification.confidence is not None else notification.severity,
        )
    except Exception as e:
        logger.error(f"Failed to send Slack: {e}")
        return False

# ── Send Notification ────────────────────────────────────────────
@app.post("/notify")
async def send_notification(notification: Notification):
    """Send multi-channel notification"""
    
    logger.info(f"Sending notification for {notification.incident_id}: {notification.severity}")
    
    results = {
        "incident_id": notification.incident_id,
        "email": await send_email_notification(notification),
        "slack": await send_slack_notification(notification),
        "telegram": await send_telegram_notification(notification)
    }
    
    return results

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
    uvicorn.run(app, host="0.0.0.0", port=8011, workers=2, **ssl_kwargs)
