from fastapi import APIRouter, Depends
from backend.services.processor import graph_data, incidents
from backend.rbac import require_viewer
from backend.tenancy import tenant_context_dep, TenantContext, get_tenant_namespaces

router = APIRouter()


@router.get("/graph", dependencies=[Depends(require_viewer)])
def get_graph(tc: TenantContext = Depends(tenant_context_dep)):
    if tc.is_super_admin:
        return graph_data
    # Filter graph nodes to pods that appear in the tenant's incidents
    allowed_ns = set(get_tenant_namespaces(tc.tenant_id))
    allowed_pods = {
        pod
        for inc in incidents
        if inc.get("namespace") in allowed_ns
        for pod in (inc.get("affected_pods") or [])
    }
    nodes = [n for n in graph_data["nodes"] if n["id"] in allowed_pods]
    node_ids = {n["id"] for n in nodes}
    edges = [
        e for e in graph_data["edges"]
        if e["source"] in node_ids and e["target"] in node_ids
    ]
    return {"nodes": nodes, "edges": edges}
