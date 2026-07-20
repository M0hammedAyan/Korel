"""
Tenant Management API — KORAL Multi-Tenancy

Provides:
  - Tenant CRUD (create, list, update, deactivate)
  - Namespace-to-tenant mapping
  - Assign/remove users from tenants

All endpoints require ADMIN role.
"""
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from backend.rbac import require_admin
from backend.audit import write_audit
from backend.database import execute, query_all, query_one, DB_TYPE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])


def _ph(n: int = 1) -> str:
    p = "%s" if DB_TYPE == "postgres" else "?"
    return ", ".join([p] * n)


# ── Models ───────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    display_name: str = Field(..., min_length=2, max_length=128)
    namespaces: list[str] = Field(default_factory=list)


class TenantUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    is_active: Optional[bool] = None


class NamespaceAssign(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=128)


class UserAssign(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/", dependencies=[Depends(require_admin)])
def create_tenant(body: TenantCreate):
    """Create a new tenant with optional namespace mappings."""
    # Check uniqueness
    sql = f"SELECT id FROM tenants WHERE name={_ph()}"
    if query_one(sql, (body.name,)):
        raise HTTPException(status_code=409, detail="Tenant name already exists")

    tenant_id = f"tn_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()

    sql = f"INSERT INTO tenants (id, name, display_name, is_active, created_at, updated_at) VALUES ({_ph(6)})"
    execute(sql, (tenant_id, body.name, body.display_name, 1, now, now))

    # Assign namespaces
    for ns in body.namespaces:
        _assign_namespace(tenant_id, ns)

    write_audit("tenant.created", "admin", body.name, {
        "tenant_id": tenant_id,
        "namespaces": body.namespaces,
    })

    return {
        "status": "created",
        "tenant_id": tenant_id,
        "name": body.name,
        "namespaces": body.namespaces,
    }


@router.get("/", dependencies=[Depends(require_admin)])
def list_tenants(active_only: bool = True):
    """List all tenants."""
    if active_only:
        rows = query_all("SELECT * FROM tenants WHERE is_active=1 ORDER BY created_at DESC")
    else:
        rows = query_all("SELECT * FROM tenants ORDER BY created_at DESC")

    if not rows:
        return {"tenants": [], "count": 0}

    # Single query for all namespaces, then group in Python
    tenant_ids = [row["id"] for row in rows]
    ph = ", ".join([_ph() for _ in tenant_ids])
    ns_rows = query_all(
        f"SELECT tenant_id, namespace FROM tenant_namespaces WHERE tenant_id IN ({ph})",
        tuple(tenant_ids),
    )
    ns_map: dict = {}
    for r in ns_rows:
        ns_map.setdefault(r["tenant_id"], []).append(r["namespace"])

    for row in rows:
        row["namespaces"] = ns_map.get(row["id"], [])

    return {"tenants": rows, "count": len(rows)}


@router.get("/{tenant_id}", dependencies=[Depends(require_admin)])
def get_tenant(tenant_id: str):
    """Get tenant details including namespaces and user count."""
    sql = f"SELECT * FROM tenants WHERE id={_ph()}"
    tenant = query_one(sql, (tenant_id,))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get namespaces
    ns_sql = f"SELECT namespace FROM tenant_namespaces WHERE tenant_id={_ph()}"
    ns_rows = query_all(ns_sql, (tenant_id,))
    tenant["namespaces"] = [r["namespace"] for r in ns_rows]

    # Get user count
    user_sql = f"SELECT COUNT(*) as count FROM users WHERE tenant_id={_ph()}"
    user_count = query_one(user_sql, (tenant_id,))
    tenant["user_count"] = user_count["count"] if user_count else 0

    return tenant


@router.patch("/{tenant_id}", dependencies=[Depends(require_admin)])
def update_tenant(tenant_id: str, body: TenantUpdate):
    """Update tenant display name or active status."""
    sql = f"SELECT id FROM tenants WHERE id={_ph()}"
    if not query_one(sql, (tenant_id,)):
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates = []
    params = []
    now = datetime.now(timezone.utc).isoformat()

    if body.display_name is not None:
        updates.append(f"display_name={_ph()}")
        params.append(body.display_name)
    if body.is_active is not None:
        updates.append(f"is_active={_ph()}")
        params.append(1 if body.is_active else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append(f"updated_at={_ph()}")
    params.append(now)
    params.append(tenant_id)

    sql = f"UPDATE tenants SET {', '.join(updates)} WHERE id={_ph()}"
    execute(sql, tuple(params))

    write_audit("tenant.updated", "admin", tenant_id, body.model_dump(exclude_none=True))
    return {"status": "updated", "tenant_id": tenant_id}


@router.post("/{tenant_id}/namespaces", dependencies=[Depends(require_admin)])
def add_namespace(tenant_id: str, body: NamespaceAssign):
    """Assign a K8s namespace to a tenant."""
    sql = f"SELECT id FROM tenants WHERE id={_ph()}"
    if not query_one(sql, (tenant_id,)):
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Check if namespace already assigned
    sql = f"SELECT tenant_id FROM tenant_namespaces WHERE namespace={_ph()}"
    existing = query_one(sql, (body.namespace,))
    if existing:
        if existing["tenant_id"] == tenant_id:
            raise HTTPException(status_code=409, detail="Namespace already assigned to this tenant")
        raise HTTPException(status_code=409, detail="Namespace already assigned to another tenant")

    _assign_namespace(tenant_id, body.namespace)
    write_audit("tenant.namespace_added", "admin", tenant_id, {"namespace": body.namespace})
    return {"status": "assigned", "tenant_id": tenant_id, "namespace": body.namespace}


@router.delete("/{tenant_id}/namespaces/{namespace}", dependencies=[Depends(require_admin)])
def remove_namespace(tenant_id: str, namespace: str):
    """Remove a namespace from a tenant."""
    sql = f"DELETE FROM tenant_namespaces WHERE tenant_id={_ph()} AND namespace={_ph()}"
    execute(sql, (tenant_id, namespace))
    write_audit("tenant.namespace_removed", "admin", tenant_id, {"namespace": namespace})
    return {"status": "removed", "tenant_id": tenant_id, "namespace": namespace}


@router.post("/{tenant_id}/users", dependencies=[Depends(require_admin)])
def assign_user_to_tenant(tenant_id: str, body: UserAssign):
    """Assign an existing user to a tenant."""
    sql = f"SELECT id FROM tenants WHERE id={_ph()}"
    if not query_one(sql, (tenant_id,)):
        raise HTTPException(status_code=404, detail="Tenant not found")

    sql = f"SELECT id FROM users WHERE username={_ph()}"
    if not query_one(sql, (body.username,)):
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc).isoformat()
    sql = f"UPDATE users SET tenant_id={_ph()}, updated_at={_ph()} WHERE username={_ph()}"
    execute(sql, (tenant_id, now, body.username))

    write_audit("tenant.user_assigned", "admin", tenant_id, {"username": body.username})
    return {"status": "assigned", "tenant_id": tenant_id, "username": body.username}


@router.delete("/{tenant_id}/users/{username}", dependencies=[Depends(require_admin)])
def remove_user_from_tenant(tenant_id: str, username: str):
    """Remove a user from a tenant (sets tenant_id to NULL → super-admin)."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"UPDATE users SET tenant_id=NULL, updated_at={_ph()} WHERE username={_ph()} AND tenant_id={_ph()}"
    execute(sql, (now, username, tenant_id))

    write_audit("tenant.user_removed", "admin", tenant_id, {"username": username})
    return {"status": "removed", "tenant_id": tenant_id, "username": username}


# ── Helpers ──────────────────────────────────────────────────────────

def _assign_namespace(tenant_id: str, namespace: str):
    sql = f"INSERT INTO tenant_namespaces (tenant_id, namespace) VALUES ({_ph(2)})"
    execute(sql, (tenant_id, namespace))
