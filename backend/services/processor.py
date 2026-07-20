import asyncio
import os
import uuid
import httpx
import json
from datetime import datetime, timezone
from typing import Dict
from contextlib import nullcontext
from tenacity import retry, stop_after_attempt, wait_exponential
import pybreaker
from backend.database import (
    insert_anomaly, insert_incident, update_incident, get_incidents,
    execute, query_all, query_one
)

try:
    from opentelemetry import trace
    TRACER = trace.get_tracer(__name__)
except Exception:
    TRACER = None

from collections import deque

CORRELATION_URL = os.getenv("CORRELATION_ENGINE_URL", "http://localhost:8005")
AI_ENGINE_URL   = os.getenv("AI_ENGINE_URL", "http://localhost:8006")

CORRELATION_BREAKER = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30)
AI_BREAKER = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30)

_MAX_LIST = 1000

# ── In-memory cache (fast reads, bounded) ───────────────────────────
anomalies: deque = deque(maxlen=_MAX_LIST)
incidents: deque = deque(maxlen=_MAX_LIST)
correlations: deque = deque(maxlen=_MAX_LIST)
fix_history: deque = deque(maxlen=_MAX_LIST)
graph_data: Dict = {"nodes": [], "edges": []}

# Load existing data from DB on startup
def _load_from_db():
    try:
        rows = get_incidents(limit=200)
        for row in reversed(rows):
            if isinstance(row, dict):
                inc = dict(row)
            else:
                inc = {
                    "incident_id": row.get("incident_id"),
                    "timestamp": row.get("timestamp"),
                    "namespace": row.get("namespace"),
                    "severity": row.get("severity"),
                    "root_cause": row.get("root_cause"),
                    "summary": row.get("summary"),
                    "affected_pods": json.loads(row.get("affected_pods") or "[]"),
                    "primary_metric": row.get("primary_metric"),
                    "confidence": row.get("confidence"),
                    "evidence_count": row.get("evidence_count"),
                    "created_at": row.get("created_at"),
                    "ai_explanation": row.get("ai_explanation"),
                    "ai_action": row.get("ai_action"),
                    "ai_model": row.get("ai_model"),
                }
            inc["affected_pods"] = json.loads(inc.get("affected_pods") or "[]") if isinstance(inc.get("affected_pods"), str) else inc.get("affected_pods", [])
            incidents.append(inc)
        print(f"[db] Loaded {len(incidents)} incidents from database")
    except Exception as e:
        print(f"[db] load error: {e}")

_load_from_db()


# ── Fix history tracking ─────────────────────────────────────────────
def store_fix_history(incident_id: str, fix_type: str, fix_description: str, 
                      applied_by: str, success: bool, kubectl_command: str = "",
                      error_message: str = ""):
    """Store a fix action in the history database"""
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO fix_history
            (incident_id, fix_type, fix_description, applied_by, success,
             error_message, kubectl_command, timestamp, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """ if os.getenv("DB_TYPE") == "postgres" else """
            INSERT INTO fix_history
            (incident_id, fix_type, fix_description, applied_by, success,
             error_message, kubectl_command, timestamp, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """
        execute(sql, (
            incident_id, fix_type, fix_description, applied_by, int(success),
            error_message, kubectl_command, int(datetime.now(timezone.utc).timestamp()),
            timestamp
        ))
        
        # Add to in-memory cache
        fix_entry = {
            "incident_id": incident_id,
            "fix_type": fix_type,
            "fix_description": fix_description,
            "applied_by": applied_by,
            "success": success,
            "error_message": error_message,
            "kubectl_command": kubectl_command,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "created_at": timestamp
        }
        fix_history.append(fix_entry)
        print(f"[fix_history] Stored: {fix_type} by {applied_by} for {incident_id}")
    except Exception as e:
        print(f"[fix_history] Error storing fix: {e}")


# ── Main anomaly processor ───────────────────────────────────────────
async def process_anomaly(data: dict, broadcast_fn):
    anomalies.append(data)

    # Persist anomaly
    try:
        insert_anomaly(
            data.get("timestamp"), data.get("pod"), data.get("namespace", "koral-system"),
            data.get("metric"), data.get("value"), data.get("unit", ""),
            data.get("z_score"), int(data.get("is_anomaly", False)),
            data.get("window_size", 300), data.get("source", "")
        )
    except Exception as e:
        print(f"[db] anomaly insert error: {e}")

    await broadcast_fn({"type": "anomaly", "payload": data})

    if not data.get("is_anomaly"):
        return

    # Call correlation engine
    try:
        result = await _call_correlation_engine(data)
        if result and getattr(result, "status_code", 0) == 200:
            payload = result.json()
            if "correlation" in payload:
                correlations.append(payload)
            _handle_correlation_result(payload)
            await broadcast_fn({"type": "incident", "payload": payload})
            asyncio.create_task(_call_ai_engine(payload, data, broadcast_fn))
        else:
            fallback_incident = _rule_engine_incident(data)
            _handle_correlation_result(fallback_incident)
            await broadcast_fn({"type": "incident", "payload": fallback_incident})
            asyncio.create_task(_call_ai_engine(fallback_incident, data, broadcast_fn))
    except Exception as e:
        print(f"[processor] correlation engine unreachable: {e}")
        fallback_incident = _rule_engine_incident(data)
        _handle_correlation_result(fallback_incident)
        await broadcast_fn({"type": "incident", "payload": fallback_incident})
        asyncio.create_task(_call_ai_engine(fallback_incident, data, broadcast_fn))


async def _call_ai_engine(incident: dict, anomaly: dict, broadcast_fn):
    try:
        ai_payload = {
            "incident_id": incident.get("incident_id", ""),
            "severity":    incident.get("severity", "medium"),
            "root_cause":  incident.get("root_cause", ""),
            "summary":     incident.get("summary", ""),
            "affected_pods": incident.get("affected_pods", []),
            "primary_metric": incident.get("primary_metric", anomaly.get("metric", "")),
            "confidence":  incident.get("confidence", 0.5),
            "namespace":   incident.get("namespace", "koral-system"),
            "z_score":     anomaly.get("z_score", 0.0),
            "value":       anomaly.get("value", 0.0),
        }
        r = await _call_ai_engine_request(ai_payload)
        if r.status_code == 200:
            ai_result = r.json()
            # Attach AI explanation to the incident
            incident["ai_explanation"] = ai_result.get("explanation", "")
            incident["ai_message"]     = ai_result.get("user_message", "")
            incident["ai_action"]      = ai_result.get("action_type", "")
            incident["ai_model"]       = ai_result.get("model_used", "")
            # Update DB
            _update_incident_ai(incident)
            # Broadcast updated incident with AI data
            await broadcast_fn({"type": "incident_ai", "payload": incident})
        else:
            _apply_rule_engine_fallback(incident, anomaly)
            _update_incident_ai(incident)
            await broadcast_fn({"type": "incident_ai", "payload": incident})
    except Exception as e:
        print(f"[processor] AI engine unreachable: {e}")
        _apply_rule_engine_fallback(incident, anomaly)
        _update_incident_ai(incident)
        await broadcast_fn({"type": "incident_ai", "payload": incident})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def _post_json_sync(url: str, payload: dict, timeout: float):
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=5.0)) as client:
        return client.post(url, json=payload)


async def _call_correlation_engine(payload: dict):
    span_ctx = TRACER.start_as_current_span("correlation.request") if TRACER else nullcontext()
    with span_ctx as span:
        if span is not None:
            span.set_attribute("dependency.name", "correlation-engine")
        return await asyncio.to_thread(
            CORRELATION_BREAKER.call,
            _post_json_sync,
            f"{CORRELATION_URL}/correlate",
            payload,
            10,
        )


async def _call_ai_engine_request(payload: dict):
    span_ctx = TRACER.start_as_current_span("ai.request") if TRACER else nullcontext()
    with span_ctx as span:
        if span is not None:
            span.set_attribute("dependency.name", "ai-engine")
        return await asyncio.to_thread(
            AI_BREAKER.call,
            _post_json_sync,
            f"{AI_ENGINE_URL}/analyze",
            payload,
            10,
        )


def _rule_engine_incident(anomaly: dict) -> dict:
    metric = anomaly.get("metric", "unknown")
    severity_score = abs(float(anomaly.get("z_score", 0.0) or 0.0))
    severity = "critical" if severity_score >= 4.5 else "high" if severity_score >= 3.0 else "medium"
    incident_id = anomaly.get("incident_id") or f"INC-{uuid.uuid4().hex[:6].upper()}"
    return {
        "incident_id": incident_id,
        "timestamp": anomaly.get("timestamp"),
        "namespace": anomaly.get("namespace", "koral-system"),
        "severity": severity,
        "root_cause": f"{metric}_anomaly",
        "summary": anomaly.get("summary") or f"{metric} anomaly on {anomaly.get('pod', 'unknown')}",
        "affected_pods": [anomaly.get("pod")] if anomaly.get("pod") else [],
        "primary_metric": metric,
        "confidence": round(min(severity_score / 5.0, 1.0), 2),
        "evidence_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root_cause_pod": anomaly.get("pod"),
        "correlation": severity_score,
    }


def _apply_rule_engine_fallback(incident: dict, anomaly: dict) -> None:
    metric = anomaly.get("metric", "unknown")
    severity_score = abs(float(anomaly.get("z_score", 0.0) or 0.0))
    incident.setdefault("ai_explanation", f"Rule engine fallback detected a {metric} anomaly with z-score {severity_score:.2f}.")
    incident.setdefault("ai_message", incident["ai_explanation"])
    incident["ai_action"] = "review_incident"
    incident["ai_model"] = "RuleEngine"


def _update_incident_ai(incident: dict):
    try:
        update_incident(
            incident.get("incident_id"),
            incident.get("ai_explanation", ""),
            incident.get("ai_action", ""),
            incident.get("ai_model", ""),
        )
    except Exception as e:
        print(f"[db] ai update error: {e}")


def _handle_correlation_result(result: dict):
    if "incident_id" not in result:
        result["incident_id"] = f"INC-{uuid.uuid4().hex[:6].upper()}"
    if "created_at" not in result:
        result["created_at"] = datetime.now(timezone.utc).isoformat()
    incidents.append(result)

    # Persist incident
    try:
        insert_incident(
            result.get("incident_id"), result.get("timestamp"),
            result.get("namespace", "koral-system"), result.get("severity", "medium"),
            result.get("root_cause", ""), result.get("summary", ""),
            result.get("affected_pods", []),
            result.get("primary_metric", ""), result.get("confidence", 0.5),
            result.get("evidence_count", 1)
        )
    except Exception as e:
        print(f"[db] incident insert error: {e}")

    # Update graph
    affected = result.get("affected_pods", [])
    root = result.get("root_cause_pod")

    _node_sql = (
        "INSERT OR IGNORE INTO graph_nodes VALUES (?,?,?)"
        if os.getenv("DB_TYPE", "sqlite") != "postgres"
        else "INSERT INTO graph_nodes VALUES (%s,%s,%s) ON CONFLICT DO NOTHING"
    )
    _edge_sql = (
        "INSERT OR IGNORE INTO graph_edges VALUES (?,?)"
        if os.getenv("DB_TYPE", "sqlite") != "postgres"
        else "INSERT INTO graph_edges VALUES (%s,%s) ON CONFLICT DO NOTHING"
    )

    for pod in affected:
        if not any(n["id"] == pod for n in graph_data["nodes"]):
            graph_data["nodes"].append({"id": pod, "label": pod, "status": "problem"})
            try:
                execute(_node_sql, (pod, pod, "problem"))
            except Exception: pass

    if root and not any(n["id"] == root for n in graph_data["nodes"]):
        graph_data["nodes"].append({"id": root, "label": root, "status": "problem"})
        try:
            execute(_node_sql, (root, root, "problem"))
        except Exception: pass

    for pod in affected:
        if root and pod != root:
            edge = {"source": root, "target": pod}
            if edge not in graph_data["edges"]:
                graph_data["edges"].append(edge)
                try:
                    execute(_edge_sql, (root, pod))
                except Exception: pass

    if root and len(affected) == 1 and len(graph_data["nodes"]) > 1:
        for existing in graph_data["nodes"]:
            if existing["id"] != root:
                edge = {"source": root, "target": existing["id"]}
                if edge not in graph_data["edges"]:
                    graph_data["edges"].append(edge)
                    try:
                        execute(_edge_sql, (root, existing["id"]))
                    except Exception: pass
                break

