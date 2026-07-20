from fastapi import APIRouter, Depends
from backend.rbac import require_viewer
from backend.database import query_all, query_one, DB_TYPE
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slo", tags=["slo"])

_PH = "%s" if DB_TYPE == "postgres" else "?"


def _availability() -> dict:
    row = query_one(
        "SELECT COUNT(*) as total FROM incidents"
        if DB_TYPE == "postgres" else
        "SELECT COUNT(*) as total FROM incidents"
    )
    total = (row or {}).get("total", 0)
    resolved_sql = (
        "SELECT COUNT(*) as resolved FROM verification_results WHERE verification_status='resolved'"
    )
    resolved_row = query_one(resolved_sql)
    resolved = (resolved_row or {}).get("resolved", 0)
    rate = round(resolved / total * 100, 2) if total > 0 else 100.0
    return {"availability_percent": rate, "total_incidents": total, "resolved": resolved}


def _mttr() -> dict:
    sql = (
        "SELECT AVG(duration_ms) as avg_ms, MIN(duration_ms) as min_ms, MAX(duration_ms) as max_ms "
        "FROM execution_log WHERE execution_status='success'"
    )
    row = query_one(sql) or {}
    avg_ms = row.get("avg_ms") or 0
    return {
        "mttr_seconds": round((avg_ms or 0) / 1000, 1),
        "mttr_min_seconds": round((row.get("min_ms") or 0) / 1000, 1),
        "mttr_max_seconds": round((row.get("max_ms") or 0) / 1000, 1),
    }


def _detection_latency() -> dict:
    try:
        if DB_TYPE == "sqlite":
            # SQLite: created_at is an ISO string; timestamp is a Unix int stored in the incident.
            # Compute latency as the difference between created_at (parsed epoch) and timestamp.
            sql = (
                "SELECT AVG("
                "  CAST(strftime('%s', created_at) AS REAL) - CAST(timestamp AS REAL)"
                ") as avg_latency_sec FROM incidents WHERE timestamp IS NOT NULL AND created_at IS NOT NULL"
            )
        else:
            sql = (
                "SELECT EXTRACT(EPOCH FROM AVG("
                "  created_at::timestamptz - TO_TIMESTAMP(timestamp)"
                ")) as avg_latency_sec FROM incidents WHERE timestamp IS NOT NULL"
            )
        row = query_one(sql) or {}
        latency = row.get("avg_latency_sec") or 0
    except Exception:
        latency = 0
    return {"avg_detection_latency_seconds": round(float(latency or 0), 1)}


def _remediation_success() -> dict:
    total_row = query_one("SELECT COUNT(*) as total FROM verification_results") or {}
    success_row = query_one(
        "SELECT COUNT(*) as success FROM verification_results WHERE verification_status='resolved'"
    ) or {}
    total = total_row.get("total", 0)
    success = success_row.get("success", 0)
    rate = round(success / total * 100, 2) if total > 0 else 0.0
    return {"remediation_success_rate": rate, "total_verifications": total, "successful": success}


def _error_budget() -> dict:
    avail = _availability()
    target = 99.9
    used = max(0.0, target - avail["availability_percent"])
    budget_remaining = round(max(0.0, target - 100.0 + avail["availability_percent"]), 3)
    return {
        "slo_target_percent": target,
        "availability_percent": avail["availability_percent"],
        "error_budget_used_percent": round(used, 3),
        "error_budget_remaining_percent": budget_remaining,
    }


@router.get("/", dependencies=[Depends(require_viewer)])
def slo_summary():
    return {
        **_availability(),
        **_mttr(),
        **_detection_latency(),
        **_remediation_success(),
        "error_budget": _error_budget(),
    }


@router.get("/availability", dependencies=[Depends(require_viewer)])
def slo_availability():
    return _availability()


@router.get("/mttr", dependencies=[Depends(require_viewer)])
def slo_mttr():
    return _mttr()


@router.get("/detection-latency", dependencies=[Depends(require_viewer)])
def slo_detection_latency():
    return _detection_latency()


@router.get("/remediation-success", dependencies=[Depends(require_viewer)])
def slo_remediation_success():
    return _remediation_success()


@router.get("/error-budget", dependencies=[Depends(require_viewer)])
def slo_error_budget():
    return _error_budget()
