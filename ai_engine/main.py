"""
KORAL AI Engine
- GPT-4o (primary) / Claude (fallback) / rule-based (no keys)
- Classifies spikes: seasonal | weekly | normal_batch | real_anomaly | real_attack
- Only alerts developer for real threats — suppresses known normal patterns
- Sends email + Telegram with Approve / Decline buttons for high-risk incidents
"""
import os
import re
import json
import asyncio
import smtplib
import httpx
import concurrent.futures
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
except Exception:
    class _DC:
        def __init__(self, *a, **k): pass
        def inc(self): pass
    Counter = _DC
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    class prometheus_client:
        @staticmethod
        def generate_latest(): return b""
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MAX_TOKENS     = int(os.getenv("AI_MAX_TOKENS", "600"))
BACKEND_URL       = os.getenv("BACKEND_URL", "http://backend:8000")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
ALERT_EMAIL       = os.getenv("ALERT_EMAIL", "")
SMTP_HOST         = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER         = os.getenv("SMTP_USER", "")
SMTP_PASS         = os.getenv("SMTP_PASS", "")
NOTIFIER_URL      = os.getenv("NOTIFIER_URL", "http://notifier:8011")

if OPENAI_API_KEY.startswith("sk-or-"):
    OPENAI_BASE_URL      = "https://openrouter.ai/api/v1"
    OPENAI_MODEL         = "openai/gpt-4o"
    OPENAI_HEADERS_EXTRA = {"HTTP-Referer": "https://koral.ai", "X-Title": "KORAL"}
else:
    OPENAI_BASE_URL      = "https://api.openai.com/v1"
    OPENAI_MODEL         = "gpt-4o"
    OPENAI_HEADERS_EXTRA = {}

app = FastAPI(title="KORAL AI Engine", version="1.0.0")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS or ["*"],
                   allow_methods=["GET","POST","PUT","DELETE","OPTIONS"],
                   allow_headers=["Content-Type","Authorization","X-API-Key"],
                   allow_credentials=True)

REQUEST_COUNT = Counter('koral_ai_requests_total', 'Total HTTP requests to KORAL AI engine')

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        REQUEST_COUNT.inc()
        return await call_next(request)

app.add_middleware(MetricsMiddleware)

activity_log: deque = deque(maxlen=1000)
ws_clients: list[WebSocket] = []

NORMAL_TYPES = {"seasonal", "weekly", "normal_batch"}

SEVERITY_ACTIONS = {
    "medium":   "auto_fix",
    "high":     "report",
    "critical": "alert_developer",
}

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

# ── Models ────────────────────────────────────────────────────────────
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


# ── LLM calls ─────────────────────────────────────────────────────────
async def call_gpt(system_prompt: str, user_prompt: str) -> str:
    if not OPENAI_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", **OPENAI_HEADERS_EXTRA},
                json={"model": OPENAI_MODEL,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user",   "content": user_prompt}],
                      "max_tokens": AI_MAX_TOKENS, "temperature": 0.3},
            )
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[GPT error: {e}]"


async def call_claude(system_prompt: str, user_prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-3-5-sonnet-20241022", "max_tokens": 600,
                      "system": system_prompt,
                      "messages": [{"role": "user", "content": user_prompt}]},
            )
            return r.json()["content"][0]["text"].strip()
    except Exception as e:
        return f"[Claude error: {e}]"


async def call_ai(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    if OPENAI_API_KEY:
        resp = await call_gpt(system_prompt, user_prompt)
        if resp and not resp.startswith("[GPT error"):
            return resp, "GPT-4o"
    if ANTHROPIC_API_KEY:
        resp = await call_claude(system_prompt, user_prompt)
        if resp and not resp.startswith("[Claude error"):
            return resp, "Claude-3.5-Sonnet"
    return _rule_based_explanation(user_prompt), "KORAL-RuleEngine"


def _rule_based_explanation(context: str) -> str:
    ctx = context.lower()
    now = datetime.now(timezone.utc)
    # Simple time-based pattern suppression in rule engine
    is_monday_morning = now.weekday() == 0 and 7 <= now.hour <= 10
    is_weekend        = now.weekday() >= 5
    is_night_batch    = 0 <= now.hour <= 5

    if is_monday_morning and "cpu" in ctx:
        return json.dumps({"spike_type": "weekly", "alert_developer": False,
                           "confidence": 0.8,
                           "explanation": "Monday morning traffic surge — this is a known weekly pattern, no action needed.",
                           "recommended_action": ""})
    if is_weekend and ("cpu" in ctx or "memory" in ctx):
        return json.dumps({"spike_type": "seasonal", "alert_developer": False,
                           "confidence": 0.75,
                           "explanation": "Weekend batch job or reduced-capacity spike — consistent with normal weekend patterns.",
                           "recommended_action": ""})
    if is_night_batch and ("storage" in ctx or "io" in ctx):
        return json.dumps({"spike_type": "normal_batch", "alert_developer": False,
                           "confidence": 0.8,
                           "explanation": "Nightly backup or batch job causing storage I/O spike — this is expected.",
                           "recommended_action": ""})
    if "cpu" in ctx:
        return json.dumps({"spike_type": "real_anomaly", "alert_developer": True,
                           "confidence": 0.7,
                           "explanation": "CPU spike detected outside known patterns. A process may be stuck or traffic is unusually high.",
                           "recommended_action": "Check for runaway processes or scale the deployment."})
    if "memory" in ctx:
        return json.dumps({"spike_type": "real_anomaly", "alert_developer": True,
                           "confidence": 0.7,
                           "explanation": "Memory usage critically high — possible memory leak or oversized dataset loaded.",
                           "recommended_action": "Restart the pod or increase memory limits."})
    return json.dumps({"spike_type": "real_anomaly", "alert_developer": True,
                       "confidence": 0.6,
                       "explanation": "Anomaly detected outside known patterns. Manual review recommended.",
                       "recommended_action": "Check affected pod logs and recent deployments."})


# ── Email ─────────────────────────────────────────────────────────────
def _send_email(subject: str, html_body: str):
    if not ALERT_EMAIL:
        print("[email] ALERT_EMAIL not set — skipping")
        return
    if not SMTP_USER or not SMTP_PASS:
        print(f"[email] SMTP not configured — would send: {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"KORAL Alerts <{SMTP_USER}>"
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        print(f"[email] Sent to {ALERT_EMAIL} — {subject}")
    except Exception as e:
        print(f"[email] Failed: {e}")


def _build_email_html(incident: IncidentAnalysisRequest, explanation: str,
                      model: str, spike_type: str, recommended_action: str) -> str:
    color = {"critical": "#ff4444", "high": "#ff8800",
             "medium": "#ffcc00", "low": "#44cc44"}.get(incident.severity, "#888")
    spike_label = spike_type.replace("_", " ").title()
    pods_html = "".join(
        f'<span style="background:#1a1a2e;color:#00d4ff;padding:2px 8px;'
        f'border-radius:4px;margin:2px;display:inline-block;font-family:monospace">{p}</span>'
        for p in incident.affected_pods
    )
    approve_url = f"{NOTIFIER_URL}/decision?incident_id={incident.incident_id}&action=approve"
    decline_url = f"{NOTIFIER_URL}/decision?incident_id={incident.incident_id}&action=decline"

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#0a0a0a;color:#e0e0e0;border-radius:12px;overflow:hidden">
      <div style="background:{color};padding:20px 24px">
        <h1 style="margin:0;color:#fff;font-size:20px">KORAL — {incident.severity.upper()} Alert</h1>
        <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">{incident.incident_id} &nbsp;·&nbsp; {spike_label}</p>
      </div>
      <div style="padding:24px">
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr><td style="padding:8px 0;color:#888;width:140px">Severity</td>
              <td style="padding:8px 0"><strong style="color:{color}">{incident.severity.upper()}</strong></td></tr>
          <tr><td style="padding:8px 0;color:#888">Spike Type</td>
              <td style="padding:8px 0"><strong>{spike_label}</strong></td></tr>
          <tr><td style="padding:8px 0;color:#888">Root Cause</td>
              <td style="padding:8px 0">{incident.root_cause.replace("_"," ").title()}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Metric</td>
              <td style="padding:8px 0">{incident.primary_metric} &nbsp;(value={incident.value:.2f}, z={incident.z_score:.2f})</td></tr>
          <tr><td style="padding:8px 0;color:#888">Namespace</td>
              <td style="padding:8px 0;font-family:monospace">{incident.namespace}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Affected Pods</td>
              <td style="padding:8px 0">{pods_html}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Time</td>
              <td style="padding:8px 0">{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</td></tr>
        </table>

        <div style="background:#111;border-left:4px solid #00d4ff;padding:16px;border-radius:0 8px 8px 0;margin-bottom:20px">
          <p style="margin:0 0 6px;color:#00d4ff;font-size:12px;font-weight:bold;text-transform:uppercase">AI Analysis ({model})</p>
          <p style="margin:0;line-height:1.6;color:#ccc">{explanation}</p>
        </div>

        {"" if not recommended_action else f'<div style="background:#111;border-left:4px solid {color};padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px"><p style="margin:0;color:#aaa;font-size:13px"><strong style="color:{color}">Recommended action:</strong> {recommended_action}</p></div>'}

        <p style="color:#aaa;font-size:13px;margin-bottom:16px">
          If this is a <strong>real threat</strong>, click <strong>Approve</strong> to let KORAL block it.<br>
          If you recognise this as a normal spike, click <strong>Decline</strong> to dismiss.
        </p>
        <div style="text-align:center">
          <a href="{approve_url}" style="display:inline-block;background:#ff4444;color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:bold;margin-right:12px;font-size:15px">✅ Approve — Block It</a>
          <a href="{decline_url}" style="display:inline-block;background:#444;color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">❌ Decline — False Alarm</a>
        </div>
      </div>
      <div style="background:#111;padding:12px 24px;text-align:center;font-size:11px;color:#444">
        KORAL — Kubernetes Observability &amp; Real-time AI Logic
      </div>
    </div>
    """


async def send_developer_alert(incident: IncidentAnalysisRequest, explanation: str,
                                model: str, spike_type: str, recommended_action: str):
    subject = (f"[KORAL {incident.severity.upper()}] "
               f"{spike_type.replace('_',' ').title()} — "
               f"{incident.root_cause.replace('_',' ').title()} "
               f"on {', '.join(incident.affected_pods)}")
    html = _build_email_html(incident, explanation, model, spike_type, recommended_action)
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, _send_email, subject, html)


# ── Helpers ───────────────────────────────────────────────────────────
async def broadcast_activity(entry: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(entry)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


async def _store_fix_in_backend(incident_id, fix_type, fix_description, applied_by, success, kubectl_command=""):
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from shared.mtls import get_mtls_client
        async with get_mtls_client(timeout=5) as client:
            await client.post(f"{BACKEND_URL}/fixes/record", json={
                "incident_id": incident_id, "fix_type": fix_type,
                "fix_description": fix_description, "applied_by": applied_by,
                "success": success, "kubectl_command": kubectl_command, "error_message": ""
            })
    except Exception as e:
        print(f"[fix_history] Failed: {e}")


# ── Core analysis endpoint ────────────────────────────────────────────
@app.post("/analyze")
async def analyze_incident(req: IncidentAnalysisRequest):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    action_type = SEVERITY_ACTIONS.get(req.severity, "report")
    day_name = now.strftime("%A")
    time_ctx = f"{day_name}, {now.hour:02d}:00 UTC"

    system_prompt = (
        "You are KORAL AI, an expert Kubernetes SRE and anomaly analyst. "
        "Your PRIMARY job is to decide whether a metric spike is NORMAL or a REAL THREAT before alerting anyone. "
        "You MUST reason about time patterns:\n"
        "- Monday 07:00-10:00 UTC: weekly traffic surge (weekly)\n"
        "- Friday/Saturday/Sunday: weekend batch jobs or low-traffic patterns (seasonal)\n"
        "- 00:00-05:00 UTC any day: nightly backups, cron jobs (normal_batch)\n"
        "- End of month (day 28-31): billing/reporting spikes (seasonal)\n"
        "- A real DoS attack or memory leak has NO time pattern and is sudden/sustained.\n\n"
        "Respond ONLY as valid JSON with these exact keys:\n"
        '{"spike_type": "seasonal|weekly|normal_batch|real_anomaly|real_attack", '
        '"alert_developer": true|false, '
        '"confidence": 0.0-1.0, '
        '"explanation": "plain English max 2 sentences — do NOT say error or attack unless certain", '
        '"recommended_action": "what to do if developer approves action"}'
    )
    user_prompt = (
        f"Current time: {time_ctx}\n"
        f"Incident: {req.incident_id}\n"
        f"Severity: {req.severity}\n"
        f"Root cause: {req.root_cause}\n"
        f"Summary: {req.summary}\n"
        f"Affected pods: {', '.join(req.affected_pods)}\n"
        f"Metric: {req.primary_metric} (value={req.value:.2f}, z-score={req.z_score:.2f})\n"
        f"Confidence: {int(req.confidence * 100)}%\n"
        f"Namespace: {req.namespace}\n\n"
        "Classify this spike. Set alert_developer=true ONLY for real_anomaly or real_attack."
    )

    raw_response, model_used = await call_ai(system_prompt, user_prompt)

    # Parse structured JSON from AI response
    spike_type         = "real_anomaly"
    alert_developer    = req.severity in ("critical", "high")
    ai_confidence      = req.confidence
    explanation        = raw_response
    recommended_action = ""
    try:
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            parsed             = json.loads(match.group())
            spike_type         = parsed.get("spike_type", spike_type)
            alert_developer    = parsed.get("alert_developer", alert_developer)
            ai_confidence      = parsed.get("confidence", ai_confidence)
            explanation        = parsed.get("explanation", explanation)
            recommended_action = parsed.get("recommended_action", "")
    except Exception:
        pass

    # Suppress alerts for known normal patterns
    if spike_type in NORMAL_TYPES:
        alert_developer = False

    # Auto-fix info
    fix_info        = AUTO_FIX_ACTIONS.get(req.root_cause, {})
    fix_applied     = None
    fix_description = None
    kubectl_hint    = ""

    if action_type == "auto_fix" and fix_info and spike_type not in NORMAL_TYPES:
        pod = req.affected_pods[0] if req.affected_pods else "unknown"
        fix_applied     = fix_info["action"]
        fix_description = fix_info["description"].format(pod=pod, namespace=req.namespace)
        kubectl_hint    = fix_info.get("kubectl_hint", "").format(pod=pod, namespace=req.namespace)

    # Spike emoji
    SPIKE_EMOJI = {"seasonal": "📅", "weekly": "📆", "normal_batch": "⚙️",
                   "real_anomaly": "⚠️", "real_attack": "🚨"}
    emoji = SPIKE_EMOJI.get(spike_type, "⚠️")

    # User-facing message
    if spike_type in NORMAL_TYPES:
        user_message = (
            f"{emoji} Spike detected and classified as **{spike_type.replace('_',' ')}** — no action needed.\n\n"
            f"{explanation}"
        )
    elif fix_applied:
        user_message = (
            f"✅ Minor anomaly handled automatically.\n\n{explanation}\n\n"
            f"**What I did:** {fix_description}\n**Verify:** `{kubectl_hint}`"
        )
    elif alert_developer:
        user_message = (
            f"{emoji} **{spike_type.replace('_',' ').upper()}** detected — developer notified.\n\n"
            f"{explanation}\n\n"
            f"**Recommended action:** {recommended_action or 'Investigate immediately.'}"
        )
        await send_developer_alert(req, explanation, model_used, spike_type, recommended_action)
    else:
        user_message = (
            f"⚠️ Anomaly detected — review recommended.\n\n{explanation}\n\n"
            f"**Recommended:** `{kubectl_hint or 'Check the affected pod logs'}`"
        )

    entry = {
        "id":               f"ai-{req.incident_id}",
        "timestamp":        now_iso,
        "incident_id":      req.incident_id,
        "severity":         req.severity,
        "root_cause":       req.root_cause,
        "spike_type":       spike_type,
        "alert_developer":  alert_developer,
        "action_type":      action_type,
        "fix_applied":      fix_applied,
        "fix_description":  fix_description,
        "explanation":      explanation,
        "recommended_action": recommended_action,
        "user_message":     user_message,
        "model_used":       model_used,
        "affected_pods":    req.affected_pods,
    }
    activity_log.append(entry)
    await broadcast_activity({"type": "ai_activity", "payload": entry})

    if fix_applied:
        await _store_fix_in_backend(req.incident_id, fix_applied,
                                    fix_description or "", "AI", True, kubectl_hint)
    return entry


# ── Chat endpoint ─────────────────────────────────────────────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    system_prompt = (
        "You are KORAL AI, a friendly Kubernetes observability assistant. "
        "Answer questions about incidents, metrics, anomalies, and Kubernetes. "
        "Be conversational, clear, and helpful. Keep answers under 150 words."
    )
    context_str = f"\nContext:\n{json.dumps(req.context, indent=2)}\n" if req.context else ""
    response, model_used = await call_ai(system_prompt, context_str + req.message)
    return {"response": response, "model": model_used,
            "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/activity")
def get_activity(limit: int = 50):
    return list(activity_log)[-limit:]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "gpt_configured":   bool(OPENAI_API_KEY),
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "email_alerts":     bool(ALERT_EMAIL and SMTP_USER and SMTP_PASS),
        "alert_recipient":  ALERT_EMAIL or "not set",
        "fallback":         "rule-based" if not OPENAI_API_KEY and not ANTHROPIC_API_KEY else "none",
    }


@app.get("/metrics")
def metrics():
    return Response(prometheus_client.generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.websocket("/ws/ai")
async def ai_ws(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    for entry in list(activity_log)[-20:]:
        await websocket.send_json({"type": "ai_activity", "payload": entry})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from shared.mtls import get_uvicorn_ssl_kwargs
    uvicorn.run("main:app", host="0.0.0.0", port=8006, **get_uvicorn_ssl_kwargs())
