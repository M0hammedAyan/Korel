from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.services.processor import correlations
from backend.rbac import require_viewer
from backend.tenancy import tenant_context_dep, TenantContext, get_tenant_namespaces

router = APIRouter()


@router.get("/correlations", dependencies=[Depends(require_viewer)])
def list_correlations(limit: int = 100, tc: TenantContext = Depends(tenant_context_dep)):
    if tc.is_super_admin:
        return list(correlations)[-limit:]
    allowed_ns = set(get_tenant_namespaces(tc.tenant_id))
    filtered = [c for c in correlations if c.get("namespace") in allowed_ns]
    return filtered[-limit:]
