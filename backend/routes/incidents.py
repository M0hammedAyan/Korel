from fastapi import APIRouter, HTTPException, Depends
from backend.services.processor import incidents
from backend.rbac import require_viewer
from backend.audit import write_audit
from backend.tenancy import tenant_context_dep, TenantContext, get_tenant_namespaces
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/incidents", dependencies=[Depends(require_viewer)])
def list_incidents(limit: int = 50, tc: TenantContext = Depends(tenant_context_dep)):
    """Get recent incidents — filtered to the caller's tenant namespaces."""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    if limit > 500:
        limit = 500
    if tc.is_super_admin:
        result = list(incidents)[-limit:]
    else:
        allowed_ns = set(get_tenant_namespaces(tc.tenant_id))
        result = [i for i in incidents if i.get("namespace") in allowed_ns][-limit:]
    logger.info(f"Returning {len(result)} incidents (limit={limit})")
    return result
