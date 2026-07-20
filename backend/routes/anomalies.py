from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
try:
    from pydantic import field_validator
except ImportError:
    from pydantic import validator as field_validator
from backend.websocket.manager import manager
from backend.services.processor import process_anomaly, anomalies
from backend.rbac import require_viewer, require_operator
from backend.tenancy import tenant_context_dep, TenantContext, get_tenant_namespaces
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class AnomalyPayload(BaseModel):
    timestamp: int = Field(..., description="Unix timestamp", gt=0)
    pod: str = Field(..., description="Pod name", min_length=1)
    metric: str = Field(..., description="Metric type (cpu, memory, storage, logs)")
    value: float = Field(..., description="Metric value")
    z_score: float = Field(..., description="Z-score for anomaly detection")
    is_anomaly: bool = Field(..., description="Whether this is flagged as an anomaly")
    namespace: str = Field(default="koral-system", description="Kubernetes namespace")
    unit: str = Field(default="value", description="Unit of measurement")
    source: str = Field(default="", description="Source agent")
    window_size: int = Field(default=300, description="Detection window size in seconds", gt=0)

    @field_validator('metric')
    @classmethod
    def validate_metric(cls, v):
        allowed = ['cpu', 'memory', 'storage', 'logs', 'pvc_io', 'log_error', 'network', 'latency']
        if v not in allowed:
            logger.warning(f"Unknown metric type: {v}")
        return v

    @field_validator('namespace')
    @classmethod
    def validate_namespace(cls, v):
        if not v or len(v) == 0:
            return "koral-system"
        return v


@router.post("/anomalies", status_code=202, dependencies=[Depends(require_operator)])
async def receive_anomaly(payload: AnomalyPayload):
    """Receive anomaly data from agents and process it"""
    try:
        logger.info(f"Received anomaly: {payload.pod}/{payload.metric} = {payload.value} (z={payload.z_score:.2f}, anomaly={payload.is_anomaly})")
        payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        await process_anomaly(payload_dict, manager.broadcast)
        return {"status": "accepted", "incident_id": None}
    except Exception as e:
        logger.error(f"Error processing anomaly: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process anomaly: {str(e)}")


@router.get("/anomalies", dependencies=[Depends(require_viewer)])
def list_anomalies(limit: int = 100, tc: TenantContext = Depends(tenant_context_dep)):
    """Get recent anomalies — filtered to the caller's tenant namespaces."""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    if limit > 1000:
        limit = 1000
    if tc.is_super_admin:
        return list(anomalies)[-limit:]
    allowed_ns = set(get_tenant_namespaces(tc.tenant_id))
    filtered = [a for a in anomalies if a.get("namespace") in allowed_ns]
    return filtered[-limit:]
