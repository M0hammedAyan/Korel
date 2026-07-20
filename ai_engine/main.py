"""
KORAL AI Engine
- Uses GPT-4o (primary) and Claude (fallback/secondary)
- Analyzes incidents and anomalies
- Auto-fixes minor issues
- Explains errors in plain English
- Alerts developers via EMAIL for critical/major issues
"""
import os
import json
import asyncio
import smtplib
import httpx
from collections import deque
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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

# ── Config ───────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MAX_TOKENS     = int(os.getenv("AI_MAX_TOKENS", "500"))
BACKEND_URL       = os.getenv("BACKEND_URL", "http://backend:8000")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
ALERT_EMAIL       = os.getenv("ALERT_EMAIL", "")          # recipient
SMTP_HOST         = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER         = os.getenv("SMTP_USER", "")            # sender gmail
SMTP_PASS         = os.getenv("SMTP_PASS", "")            # app password

# ── Auto-detect OpenRouter vs direct OpenAI ──────────────────────────
if OPENAI_API_KEY.startswith("sk-or-"):
    OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
    OPENAI_MODEL    = "openai/gpt-4o"
    OPENAI_HEADERS_EXTRA = {"HTTP-Referer": "https://koral.ai", "X-Title": "KORAL"}
else:
    OPENAI_BASE_URL = "https://api.openai.com/v1"
    OPENAI_MODEL    = "gpt-4o"
    OPENAI_HEADERS_EXTRA = {}

app = FastAPI(title="KORAL AI Engine", version="1.0.0")

# ── CORS Configuration ───────────────────────────────────────────────
# In production, set ALLOWED_ORIGINS env var to comma-separated list
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware, 
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    allow_credentials=True,
)

# Prometheus metrics
REQUEST_COUNT = Counter('koral_ai_requests_total', 'Total HTTP requests to KORAL AI engine')


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        REQUEST_COUNT.inc()
        return await call_next(request)


app.add_middleware(MetricsMiddleware)

# ── In-memory activity log (persisted to SQLite via backend) ─────────
activity_log: deque = deque(maxlen=1000)
ws_clients: list[WebSocket] = []

# ── Severity routing ─────────────────────────────────────────────────
# minor/medium  → AI auto-fixes + reports to user
# high          → AI explains + recommends + reports to user
# critical      → AI explains + alerts developer immediately

SEVERITY_ACTIONS = {
    "medium": "auto_fix",
    "high":   "report",
    "critical": "alert_developer",
}

# ── Pydantic models ──────────────────────────────────────────────────
class IncidentAnalysisRequest(BaseModel):
    incident_id: str
    severity: str
    root_cause: str
    summary: str
    affected_pods: list[str]
    primary_metric: str
    confidence: float
    namespace: str = "koral-system"
    z_score: float = 0.0
    value: float = 0.0

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


# ── GPT-4o call ──────────────────────────────────────────────────────
async def call_gpt(system_prompt: str, user_prompt: str) -> str:
    if not OPENAI_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                **OPENAI_HEADERS_EXTRA,
            }
            r = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "max_tokens": AI_MAX_TOKENS,
                    "temperature": 0.3,
                },
            )
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[GPT error: {e}]"


# ── Claude call ──────────────────────────────────────────────────────
async def call_claude(system_prompt: str, user_prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 600,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            return r.json()["content"][0]["text"].strip()
    except Exception as e:
        return f"[Claude error: {e}]"


# ── Pick best available model ────────────────────────────────────────
async def call_ai(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """Returns (response_text, model_used)"""
    if OPENAI_API_KEY:
        resp = await call_gpt(system_prompt, user_prompt)
        if resp and not resp.startswith("[GPT error"):
            return resp, "GPT-4o"
    if ANTHROPIC_API_KEY:
        resp = await call_claude(system_prompt, user_prompt)
        if resp and not resp.startswith("[Claude error"):
            return resp, "Claude-3.5-Sonnet"
    # No API keys — use rule-based fallback
    return _rule_based_explanation(user_prompt), "KORAL-RuleEngine"


# ── Rule-based fallback (no API keys needed) ─────────────────────────
def _rule_based_explanation(context: str) -> str:
    ctx = context.lower()
    if "cpu_saturation" in ctx or "cpu" in ctx:
        return ("CPU usage has spiked abnormally. This usually means a process is stuck in a loop "
                "or a sudden traffic surge hit the service. The affected pod is consuming more CPU "
                "than its historical baseline. Consider checking for runaway processes or scaling the deployment.")
    if "memory_pressure" in ctx or "memory" in ctx or "oom" in ctx:
        return ("Memory usage is critically high. The pod may be approaching its memory limit and "
                "could be OOM-killed soon. This is often caused by a memory leak or an unusually "
                "large dataset being loaded. Consider restarting the pod or increasing memory limits.")
    if "storage" in ctx or "pvc_io" in ctx or "io" in ctx:
        return ("Storage I/O is abnormally high. A process is writing or reading data at an "
                "unusual rate. This can slow down the entire node. Check for log flooding, "
                "database write storms, or backup jobs running unexpectedly.")
    if "log_error" in ctx or "application_error" in ctx:
        return ("The application is generating errors at an abnormal rate. This indicates "
                "application-level failures — check the pod logs for stack traces, "
                "failed connections, or configuration errors.")
    if "network" in ctx or "latency" in ctx:
        return ("Network latency has spiked. Pods are taking longer than usual to communicate. "
                "This could be caused by network congestion, a misconfigured service mesh, "
                "or an overloaded downstream service.")
    return ("An anomaly was detected in your Kubernetes cluster. The AI engine has flagged "
            "this as requiring attention. Check the affected pods and review recent deployments.")


# ── Auto-fix actions ─────────────────────────────────────────────────
AUTO_FIX_ACTIONS = {
    "cpu_saturation": {
        "action": "throttle_check",
        "description": "Verified CPU limits are set. Flagged pod for horizontal scaling review.",
        "kubectl_hint": "kubectl top pod {pod} -n {namespace}",
    },
    "memory_pressure_or_oom": {
        "action": "memory_check",
        "description": "Checked memory limits. Recommended increasing memory request by 20%.",
        "kubectl_hint": "kubectl describe pod {pod} -n {namespace} | grep -A5 Limits",
    },
    "storage_io_bottleneck": {
        "action": "io_check",
        "description": "Identified high I/O pod. Flagged for PVC size review.",
        "kubectl_hint": "kubectl get pvc -n {namespace}",
    },
    "application_error_spike": {
        "action": "log_tail",
        "description": "Tailed error logs. Found repeated error pattern. Flagged for developer review.",
        "kubectl_hint": "kubectl logs {pod} -n {namespace} --tail=50",
    },
    "application_crash_loop": {
        "action": "restart_check",
        "description": "Detected crash loop. Checked restart count. Escalating to developer.",
        "kubectl_hint": "kubectl describe pod {pod} -n {namespace}",
    },
}


# ── Send email alert ────────────────────────────────────────────────
def _send_email(subject: str, html_body: str):
    """Sends email synchronously — called from a thread to avoid blocking."""
    if not ALERT_EMAIL:
        print("[email] ALERT_EMAIL not set — skipping")
        return
    if not SMTP_USER or not SMTP_PASS or SMTP_PASS == "your-16-char-app-password-here":
        print(f"[email] SMTP not configured — would have sent to {ALERT_EMAIL}")
        print(f"[email] Subject: {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"KORAL Alerts <{SMTP_USER}>"
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        print(f"[email] Alert sent to {ALERT_EMAIL} — {subject}")
    except Exception as e:
        print(f"[email] Failed to send: {e}")


def _build_email_html(incident: IncidentAnalysisRequest, explanation: str, model: str) -> str:
    severity_color = {
        "critical": "#ff4444",
        "high":     "#ff8800",
        "medium":   "#ffcc00",
        "low":      "#44cc44",
    }.get(incident.severity, "#888888")

    pods_html = "".join(
        f'<span style="background:#1a1a2e;color:#00d4ff;padding:2px 8px;'
        f'border-radius:4px;margin:2px;display:inline-block;font-family:monospace">'
        f'{p}</span>' for p in incident.affected_pods
    )

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a0a;color:#e0e0e0;border-radius:12px;overflow:hidden">
      <div style="background:{severity_color};padding:20px 24px">
        <h1 style="margin:0;color:#fff;font-size:20px">KORAL — {incident.severity.upper()} Incident Detected</h1>
        <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">{incident.incident_id}</p>
      </div>
      <div style="padding:24px">
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr><td style="padding:8px 0;color:#888;width:140px">Severity</td>
              <td style="padding:8px 0"><strong style="color:{severity_color}">{incident.severity.upper()}</strong></td></tr>
          <tr><td style="padding:8px 0;color:#888">Root Cause</td>
              <td style="padding:8px 0">{incident.root_cause.replace("_"," ").title()}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Namespace</td>
              <td style="padding:8px 0;font-family:monospace">{incident.namespace}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Metric</td>
              <td style="padding:8px 0">{incident.primary_metric} (z-score: {incident.z_score:.2f})</td></tr>
          <tr><td style="padding:8px 0;color:#888">Confidence</td>
              <td style="padding:8px 0">{int(incident.confidence * 100)}%</td></tr>
          <tr><td style="padding:8px 0;color:#888">Affected Pods</td>
              <td style="padding:8px 0">{pods_html}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Time</td>
              <td style="padding:8px 0">{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</td></tr>
        </table>

        <div style="background:#111;border-left:4px solid #00d4ff;padding:16px;border-radius:0 8px 8px 0;margin-bottom:20px">
          <p style="margin:0 0 6px;color:#00d4ff;font-size:12px;font-weight:bold;text-transform:uppercase">AI Analysis ({model})</p>
          <p style="margin:0;line-height:1.6;color:#ccc">{explanation}</p>
        </div>

        <div style="background:#1a0a0a;border:1px solid {severity_color}44;border-radius:8px;padding:16px">
          <p style="margin:0 0 8px;color:{severity_color};font-weight:bold">Action Required</p>
          <p style="margin:0;color:#aaa;font-size:13px">This incident requires immediate manual intervention.
          Log in to the KORAL dashboard and check the affected pods.</p>
          <div style="margin-top:12px;background:#111;padding:10px;border-radius:6px;font-family:monospace;font-size:12px;color:#51cf66">
            kubectl describe pod {incident.affected_pods[0] if incident.affected_pods else "&lt;pod&gt;"} -n {incident.namespace}<br>
            kubectl logs {incident.affected_pods[0] if incident.affected_pods else "&lt;pod&gt;"} -n {incident.namespace} --tail=50
          </div>
        </div>
      </div>
      <div style="background:#111;padding:12px 24px;text-align:center;font-size:11px;color:#444">
        KORAL — Kubernetes Observability with Real-time AI Logic
      </div>
    </div>
    """


async def send_developer_alert(incident: IncidentAnalysisRequest, explanation: str, model: str):
    """Send email + optional Slack webhook."""
    subject = f"[KORAL {incident.severity.upper()}] {incident.root_cause.replace('_',' ').title()} on {', '.join(incident.affected_pods)}"
    html    = _build_email_html(incident, explanation, model)

    # Send email in a thread so it doesn't block the async loop
    import concurrent.futures
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, _send_email, subject, html)

    # Also send Slack if configured
    if ALERT_WEBHOOK_URL:
        try:
            slack_msg = {
                "text": f"KORAL {incident.severity.upper()} — {incident.root_cause} on {', '.join(incident.affected_pods)}",
                "blocks": [{
                    "type": "section",
                    "text": {"type": "mrkdwn",
                             "text": f"*KORAL {incident.severity.upper()} ALERT*\n"
                                     f"Incident: `{incident.incident_id}`\n"
                                     f"Root cause: {incident.root_cause}\n"
                                     f"Pods: {', '.join(incident.affected_pods)}\n"
                                     f"AI: {explanation}"}
                }]
            }
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(ALERT_WEBHOOK_URL, json=slack_msg)
        except Exception as e:
            print(f"[slack] webhook failed: {e}")


# ── Broadcast to connected WebSocket clients ─────────────────────────
async def broadcast_activity(entry: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(entry)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


# ── Store fix history in backend ─────────────────────────────────────
async def _store_fix_in_backend(incident_id: str, fix_type: str, fix_description: str,
                                 applied_by: str, success: bool, kubectl_command: str = ""):
    """Store fix history by calling backend API"""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from shared.mtls import get_mtls_client
        async with get_mtls_client(timeout=5) as client:
            await client.post(
                f"{BACKEND_URL}/fixes/record",
                json={
                    "incident_id": incident_id,
                    "fix_type": fix_type,
                    "fix_description": fix_description,
                    "applied_by": applied_by,
                    "success": success,
                    "kubectl_command": kubectl_command,
                    "error_message": ""
                }
            )
        print(f"[fix_history] Stored {fix_type} for {incident_id}")
    except Exception as e:
        print(f"[fix_history] Failed to store: {e}")


# ── Core analysis endpoint ───────────────────────────────────────────
@app.post("/analyze")
async def analyze_incident(req: IncidentAnalysisRequest):
    now = datetime.now(timezone.utc).isoformat()
    action_type = SEVERITY_ACTIONS.get(req.severity, "report")

    # Build AI prompt
    system_prompt = (
        "You are KORAL AI, an expert Kubernetes SRE assistant. "
        "You analyze infrastructure incidents and explain them clearly to both developers and non-technical users. "
        "Be concise, specific, and actionable. Use plain English. No jargon unless necessary. "
        "Format: 1 sentence what happened, 1 sentence why, 1 sentence what to do."
    )
    user_prompt = (
        f"Incident: {req.incident_id}\n"
        f"Severity: {req.severity}\n"
        f"Root cause classification: {req.root_cause}\n"
        f"Summary: {req.summary}\n"
        f"Affected pods: {', '.join(req.affected_pods)}\n"
        f"Primary metric: {req.primary_metric} (value={req.value:.2f}, z-score={req.z_score:.2f})\n"
        f"Confidence: {int(req.confidence * 100)}%\n"
        f"Namespace: {req.namespace}\n\n"
        f"Explain this incident in plain English and tell the user what is happening and what should be done."
    )

    explanation, model_used = await call_ai(system_prompt, user_prompt)

    # Determine auto-fix
    fix_info = AUTO_FIX_ACTIONS.get(req.root_cause, {})
    fix_applied = None
    fix_description = None

    if action_type == "auto_fix" and fix_info:
        fix_applied = fix_info["action"]
        fix_description = fix_info["description"].format(
            pod=req.affected_pods[0] if req.affected_pods else "unknown",
            namespace=req.namespace,
        )
        kubectl_hint = fix_info.get("kubectl_hint", "").format(
            pod=req.affected_pods[0] if req.affected_pods else "unknown",
            namespace=req.namespace,
        )
    else:
        kubectl_hint = ""

    # Build user-facing message
    if action_type == "auto_fix":
        user_message = (
            f"✅ Minor issue detected and handled automatically.\n\n"
            f"{explanation}\n\n"
            f"**What I did:** {fix_description}\n"
            f"**Run this to verify:** `{kubectl_hint}`"
        )
    elif action_type == "report":
        user_message = (
            f"⚠️ Issue detected — requires your attention.\n\n"
            f"{explanation}\n\n"
            f"**Recommended action:** `{kubectl_hint or 'Check the affected pod logs'}`"
        )
    else:  # alert_developer
        user_message = (
            f"🚨 Critical issue — developer alert sent.\n\n"
            f"{explanation}\n\n"
            f"**This requires immediate manual intervention.** "
            f"The on-call developer has been notified."
        )
        await send_developer_alert(req, explanation, model_used)

    # Log the activity
    entry = {
        "id": f"ai-{req.incident_id}",
        "timestamp": now,
        "incident_id": req.incident_id,
        "severity": req.severity,
        "root_cause": req.root_cause,
        "action_type": action_type,
        "fix_applied": fix_applied,
        "fix_description": fix_description,
        "explanation": explanation,
        "user_message": user_message,
        "model_used": model_used,
        "affected_pods": req.affected_pods,
    }
    activity_log.append(entry)
    await broadcast_activity({"type": "ai_activity", "payload": entry})

    # Store fix history in backend database
    if fix_applied:
        await _store_fix_in_backend(
            incident_id=req.incident_id,
            fix_type=fix_applied,
            fix_description=fix_description or "",
            applied_by="AI",
            success=True,
            kubectl_command=kubectl_hint
        )

    return entry


# ── Chat endpoint (user asks questions) ─────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    system_prompt = (
        "You are KORAL AI, a friendly Kubernetes observability assistant. "
        "You help users understand what is happening in their cluster. "
        "Answer questions about incidents, metrics, anomalies, and Kubernetes concepts. "
        "Be conversational, clear, and helpful. Keep answers under 150 words."
    )

    context_str = ""
    if req.context:
        context_str = f"\nCurrent system context:\n{json.dumps(req.context, indent=2)}\n"

    response, model_used = await call_ai(system_prompt, context_str + req.message)

    return {
        "response": response,
        "model": model_used,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Activity log endpoint ────────────────────────────────────────────
@app.get("/activity")
def get_activity(limit: int = 50):
    return list(activity_log)[-limit:]


# ── Health ───────────────────────────────────────────────────────────
@app.get("/health")
def health():
    email_ready = bool(ALERT_EMAIL and SMTP_USER and SMTP_PASS and SMTP_PASS != "your-16-char-app-password-here")
    return {
        "status": "ok",
        "gpt_configured": bool(OPENAI_API_KEY),
        "gpt_endpoint": OPENAI_BASE_URL if OPENAI_API_KEY else "not configured",
        "gpt_model": OPENAI_MODEL if OPENAI_API_KEY else "not configured",
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "email_alerts": email_ready,
        "alert_recipient": ALERT_EMAIL if ALERT_EMAIL else "not set",
        "slack_alerts": bool(ALERT_WEBHOOK_URL),
        "fallback": "rule-based" if not OPENAI_API_KEY and not ANTHROPIC_API_KEY else "none",
    }


@app.get('/metrics')
def metrics():
    data = prometheus_client.generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)


# ── WebSocket for live AI activity feed ─────────────────────────────
@app.websocket("/ws/ai")
async def ai_ws(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    # Send existing log on connect
    for entry in list(activity_log)[-20:]:
        await websocket.send_json({"type": "ai_activity", "payload": entry})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from shared.mtls import get_uvicorn_ssl_kwargs
    ssl_kwargs = get_uvicorn_ssl_kwargs()
    uvicorn.run("main:app", host="0.0.0.0", port=8006, **ssl_kwargs)
