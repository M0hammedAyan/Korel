"""
Multi-tenancy module for KORAL.

Implements row-level tenant isolation:
  - Each user belongs to exactly one tenant
  - All data queries are automatically filtered by tenant_id
  - Tenant context is resolved from the authenticated user
  - ADMIN users with tenant_id=NULL are "super-admins" (see all tenants)

Tenant model:
  - A tenant represents a team/org that manages specific K8s namespaces
  - Namespaces are mapped to tenants (one namespace belongs to one tenant)
  - Anomalies/incidents are scoped by namespace → automatically tenant-scoped
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request

from backend.database import query_one, query_all, execute, DB_TYPE

logger = logging.getLogger(__name__)


def _ph() -> str:
    """Get SQL placeholder for current DB type."""
    return "%s" if DB_TYPE == "postgres" else "?"


class TenantContext:
    """Resolved tenant context for the current request."""

    def __init__(self, tenant_id: Optional[str], tenant_name: Optional[str], is_super_admin: bool = False):
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.is_super_admin = is_super_admin

    def can_access_tenant(self, target_tenant_id: str) -> bool:
        """Check if this context has access to a given tenant."""
        if self.is_super_admin:
            return True
        return self.tenant_id == target_tenant_id

    def get_filter_sql(self, column: str = "tenant_id") -> tuple:
        """
        Return (sql_fragment, params) to filter queries by tenant.
        Super-admins get no filter (empty string).
        """
        if self.is_super_admin:
            return ("", ())
        return (f" AND {column}={_ph()}", (self.tenant_id,))


def resolve_tenant_from_user(username: str) -> TenantContext:
    """
    Look up the tenant for a given user.
    Returns TenantContext with tenant info or super-admin flag.
    """
    if not username or username.startswith("env:"):
        # Env-var based keys are super-admins (backward compat)
        return TenantContext(tenant_id=None, tenant_name=None, is_super_admin=True)

    sql = f"SELECT tenant_id FROM users WHERE username={_ph()}"
    user = query_one(sql, (username,))

    if not user or not user.get("tenant_id"):
        # Users without tenant_id are super-admins
        return TenantContext(tenant_id=None, tenant_name=None, is_super_admin=True)

    tenant_id = user["tenant_id"]
    sql = f"SELECT name FROM tenants WHERE id={_ph()} AND is_active=1"
    tenant = query_one(sql, (tenant_id,))

    if not tenant:
        return TenantContext(tenant_id=tenant_id, tenant_name="unknown", is_super_admin=False)

    return TenantContext(tenant_id=tenant_id, tenant_name=tenant["name"], is_super_admin=False)


def get_tenant_namespaces(tenant_id: str) -> list:
    """Get all K8s namespaces assigned to a tenant."""
    sql = f"SELECT namespace FROM tenant_namespaces WHERE tenant_id={_ph()}"
    rows = query_all(sql, (tenant_id,))
    return [r["namespace"] for r in rows]


def _get_username_from_request(
    api_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> str:
    """Resolve username from API key or JWT for tenant lookup."""
    import hashlib
    import hmac
    import os
    from backend.auth import DISABLE_AUTH, JWT_SECRET, JWT_ALGORITHM

    if DISABLE_AUTH:
        return "env:admin"

    if api_key:
        # Check env-var role keys — these are super-admin
        for env_var in ("API_KEY_ADMIN", "API_KEY_OPERATOR", "API_KEY_VIEWER", "API_KEY"):
            key = os.getenv(env_var)
            if key and hmac.compare_digest(api_key, key):
                return f"env:{env_var.lower()}"
        # User-managed key — look up username
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        ph = "%s" if DB_TYPE == "postgres" else "?"
        row = query_one(f"SELECT username FROM users WHERE api_key_hash={ph}", (key_hash,))
        if row:
            return row["username"]

    if authorization:
        try:
            import jwt as _jwt
            scheme, token = authorization.split(maxsplit=1)
            if scheme.lower() == "bearer":
                payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                return payload.get("sub", "unknown")
        except Exception:
            pass

    return "unknown"


def get_tenant_context(
    api_key: Optional[str] = Depends(
        lambda api_key=None: api_key  # placeholder; real injection below
    ),
) -> TenantContext:
    """FastAPI dependency — resolves TenantContext from the request credentials."""
    # This is called via get_tenant_context_dep below which has proper Header injection.
    return TenantContext(tenant_id=None, tenant_name=None, is_super_admin=True)


def make_tenant_dep():
    """Return a FastAPI dependency that resolves TenantContext from request headers."""
    from fastapi import Header

    def _dep(
        api_key: Optional[str] = Header(None, alias="X-API-Key"),
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ) -> TenantContext:
        username = _get_username_from_request(api_key, authorization)
        return resolve_tenant_from_user(username)

    return _dep


# Singleton dependency — import and use this in routes
tenant_context_dep = make_tenant_dep()
