"""
Multi-Cluster Federation API — KORAL

Enables managing multiple Kubernetes clusters from a single KORAL backend.
Each cluster is registered with connection details and can be queried for
aggregated anomalies, incidents, and health status.

Federation model:
  - Central KORAL backend acts as the control plane
  - Remote clusters run KORAL agents + correlation engine
  - Central backend polls remote cluster APIs for aggregated data
  - Anomalies/incidents are tagged with cluster_id for cross-cluster correlation
"""
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.rbac import require_admin, require_viewer, require_operator
from backend.audit import write_audit
from backend.database import execute, query_all, query_one, DB_TYPE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/federation", tags=["federation"])


def _ph(n: int = 1) -> str:
    p = "%s" if DB_TYPE == "postgres" else "?"
    return ", ".join([p] * n)


# ── Models ───────────────────────────────────────────────────────────

class ClusterRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    display_name: str = Field(..., max_length=128)
    api_endpoint: str = Field(..., min_length=8, max_length=512)
    region: str = Field(default="", max_length=64)
    provider: str = Field(default="", max_length=32)  # eks, gke, aks, on-prem
    tenant_id: Optional[str] = None


class ClusterUpdate(BaseModel):
    display_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None


class ClusterHealthReport(BaseModel):
    status: str = Field(...)  # healthy, degraded, unreachable
    node_count: int = Field(default=0)
    pod_count: int = Field(default=0)
    anomaly_count_24h: int = Field(default=0)
    incident_count_24h: int = Field(default=0)
    last_heartbeat: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/clusters", dependencies=[Depends(require_admin)])
def register_cluster(body: ClusterRegister):
    """Register a new remote cluster for federation."""
    # Check uniqueness
    sql = f"SELECT id FROM federated_clusters WHERE name={_ph()}"
    if query_one(sql, (body.name,)):
        raise HTTPException(status_code=409, detail="Cluster name already registered")

    cluster_id = f"cl_{secrets.token_hex(8)}"
    cluster_token = f"cltk_{secrets.token_urlsafe(32)}"
    now = datetime.now(timezone.utc).isoformat()

    sql = (
        f"INSERT INTO federated_clusters "
        f"(id, name, display_name, api_endpoint, region, provider, cluster_token, tenant_id, "
        f"is_active, status, created_at, updated_at) "
        f"VALUES ({_ph(12)})"
    )
    execute(sql, (
        cluster_id, body.name, body.display_name, body.api_endpoint,
        body.region, body.provider, cluster_token, body.tenant_id,
        1, "registered", now, now,
    ))

    write_audit("federation.cluster_registered", "admin", body.name, {
        "cluster_id": cluster_id,
        "region": body.region,
        "provider": body.provider,
    })

    return {
        "status": "registered",
        "cluster_id": cluster_id,
        "name": body.name,
        "cluster_token": cluster_token,
        "message": "Store the cluster_token securely. Remote agents use this to authenticate.",
    }


@router.get("/clusters", dependencies=[Depends(require_viewer)])
def list_clusters(active_only: bool = True):
    """List all federated clusters."""
    if active_only:
        sql = "SELECT id, name, display_name, region, provider, status, is_active, last_heartbeat, created_at FROM federated_clusters WHERE is_active=1 ORDER BY name"
    else:
        sql = "SELECT id, name, display_name, region, provider, status, is_active, last_heartbeat, created_at FROM federated_clusters ORDER BY name"

    rows = query_all(sql)
    return {"clusters": rows, "count": len(rows)}


@router.get("/clusters/{cluster_id}", dependencies=[Depends(require_viewer)])
def get_cluster(cluster_id: str):
    """Get details for a specific cluster."""
    sql = f"SELECT id, name, display_name, api_endpoint, region, provider, status, is_active, tenant_id, last_heartbeat, node_count, pod_count, anomaly_count_24h, incident_count_24h, created_at, updated_at FROM federated_clusters WHERE id={_ph()}"
    cluster = query_one(sql, (cluster_id,))
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.patch("/clusters/{cluster_id}", dependencies=[Depends(require_admin)])
def update_cluster(cluster_id: str, body: ClusterUpdate):
    """Update cluster details."""
    sql = f"SELECT id FROM federated_clusters WHERE id={_ph()}"
    if not query_one(sql, (cluster_id,)):
        raise HTTPException(status_code=404, detail="Cluster not found")

    updates = []
    params = []
    now = datetime.now(timezone.utc).isoformat()

    if body.display_name is not None:
        updates.append(f"display_name={_ph()}")
        params.append(body.display_name)
    if body.api_endpoint is not None:
        updates.append(f"api_endpoint={_ph()}")
        params.append(body.api_endpoint)
    if body.region is not None:
        updates.append(f"region={_ph()}")
        params.append(body.region)
    if body.is_active is not None:
        updates.append(f"is_active={_ph()}")
        params.append(1 if body.is_active else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append(f"updated_at={_ph()}")
    params.append(now)
    params.append(cluster_id)

    sql = f"UPDATE federated_clusters SET {', '.join(updates)} WHERE id={_ph()}"
    execute(sql, tuple(params))

    write_audit("federation.cluster_updated", "admin", cluster_id, body.model_dump(exclude_none=True))
    return {"status": "updated", "cluster_id": cluster_id}


@router.post("/clusters/{cluster_id}/heartbeat", dependencies=[Depends(require_operator)])
def cluster_heartbeat(cluster_id: str, body: ClusterHealthReport):
    """
    Receive a heartbeat from a remote cluster.
    Called periodically by the remote KORAL backend to report status.
    """
    sql = f"SELECT id FROM federated_clusters WHERE id={_ph()}"
    if not query_one(sql, (cluster_id,)):
        raise HTTPException(status_code=404, detail="Cluster not found")

    now = datetime.now(timezone.utc).isoformat()
    sql = (
        f"UPDATE federated_clusters SET "
        f"status={_ph()}, node_count={_ph()}, pod_count={_ph()}, "
        f"anomaly_count_24h={_ph()}, incident_count_24h={_ph()}, "
        f"last_heartbeat={_ph()}, updated_at={_ph()} "
        f"WHERE id={_ph()}"
    )
    execute(sql, (
        body.status, body.node_count, body.pod_count,
        body.anomaly_count_24h, body.incident_count_24h,
        body.last_heartbeat or now, now, cluster_id,
    ))

    return {"status": "acknowledged", "cluster_id": cluster_id}


@router.delete("/clusters/{cluster_id}", dependencies=[Depends(require_admin)])
def deregister_cluster(cluster_id: str):
    """Deactivate a federated cluster."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"UPDATE federated_clusters SET is_active=0, status='deregistered', updated_at={_ph()} WHERE id={_ph()}"
    execute(sql, (now, cluster_id))

    write_audit("federation.cluster_deregistered", "admin", cluster_id, {})
    return {"status": "deregistered", "cluster_id": cluster_id}


@router.get("/overview", dependencies=[Depends(require_viewer)])
def federation_overview():
    """Get aggregated metrics across all federated clusters."""
    sql = "SELECT COUNT(*) as total, SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active FROM federated_clusters"
    totals = query_one(sql, ())

    sql = "SELECT SUM(node_count) as nodes, SUM(pod_count) as pods, SUM(anomaly_count_24h) as anomalies, SUM(incident_count_24h) as incidents FROM federated_clusters WHERE is_active=1"
    metrics = query_one(sql, ())

    # Mark stale clusters (no heartbeat in 5 minutes)
    stale_threshold = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stale_sql = (
        "SELECT COUNT(*) as stale FROM federated_clusters WHERE is_active=1 AND last_heartbeat IS NOT NULL "
        "AND last_heartbeat < datetime('now', '-5 minutes')"
        if DB_TYPE == "sqlite" else
        "SELECT COUNT(*) as stale FROM federated_clusters WHERE is_active=1 AND last_heartbeat IS NOT NULL "
        "AND last_heartbeat < NOW() - INTERVAL '5 minutes'"
    )
    try:
        stale_row = query_one(stale_sql, ()) or {}
        stale_count = stale_row.get("stale", 0)
    except Exception:
        stale_count = 0

    return {
        "clusters_total": totals.get("total", 0) if totals else 0,
        "clusters_active": totals.get("active", 0) if totals else 0,
        "clusters_stale": stale_count,
        "total_nodes": metrics.get("nodes", 0) if metrics else 0,
        "total_pods": metrics.get("pods", 0) if metrics else 0,
        "total_anomalies_24h": metrics.get("anomalies", 0) if metrics else 0,
        "total_incidents_24h": metrics.get("incidents", 0) if metrics else 0,
    }
