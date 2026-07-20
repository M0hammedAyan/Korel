from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from backend.services.processor import fix_history, store_fix_history
from backend.rbac import require_viewer, require_operator
from backend.audit import write_audit
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class FixHistoryEntry(BaseModel):
    incident_id: str = Field(..., description="Incident ID this fix relates to")
    fix_type: str = Field(..., description="Type of fix applied")
    fix_description: str = Field(..., description="Description of what was fixed")
    applied_by: str = Field(..., description="Who applied the fix (AI or Developer name)")
    success: bool = Field(..., description="Whether the fix was successful")
    kubectl_command: Optional[str] = Field(default="", description="kubectl command used")
    error_message: Optional[str] = Field(default="", description="Error message if failed")


@router.get("/fixes/history", dependencies=[Depends(require_viewer)])
def get_fix_history(limit: int = 100, applied_by: Optional[str] = None):
    """Get fix history with optional filtering"""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    if limit > 500:
        limit = 500
    
    result = list(fix_history)[-limit:]
    
    # Filter by applied_by if specified
    if applied_by:
        result = [f for f in result if f.get("applied_by") == applied_by]
    
    logger.info(f"Returning {len(result)} fix history entries (limit={limit}, filter={applied_by})")
    return result


@router.get("/fixes/stats", dependencies=[Depends(require_viewer)])
def get_fix_stats():
    """Get statistics about fixes"""
    total = len(fix_history)
    ai_fixes = len([f for f in fix_history if f.get("applied_by") == "AI"])
    developer_fixes = len([f for f in fix_history if f.get("applied_by") != "AI"])
    successful = len([f for f in fix_history if f.get("success")])
    failed = total - successful
    
    success_rate = (successful / total * 100) if total > 0 else 0
    
    return {
        "total_fixes": total,
        "ai_fixes": ai_fixes,
        "developer_fixes": developer_fixes,
        "successful_fixes": successful,
        "failed_fixes": failed,
        "success_rate": round(success_rate, 2)
    }


@router.get("/fixes/by-incident/{incident_id}", dependencies=[Depends(require_viewer)])
def get_fixes_by_incident(incident_id: str):
    """Get all fixes for a specific incident"""
    result = [f for f in fix_history if f.get("incident_id") == incident_id]
    logger.info(f"Returning {len(result)} fixes for incident {incident_id}")
    return result


@router.post("/fixes/record", dependencies=[Depends(require_operator)])
def record_fix(entry: FixHistoryEntry):
    """Record a new fix (typically called by developers via UI)"""
    try:
        store_fix_history(
            incident_id=entry.incident_id,
            fix_type=entry.fix_type,
            fix_description=entry.fix_description,
            applied_by=entry.applied_by,
            success=entry.success,
            kubectl_command=entry.kubectl_command or "",
            error_message=entry.error_message or ""
        )
        write_audit("fix.recorded", entry.applied_by, entry.incident_id,
                    {"fix_type": entry.fix_type, "success": entry.success})
        return {"status": "recorded", "incident_id": entry.incident_id}
    except Exception as e:
        logger.error(f"Error recording fix: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record fix: {str(e)}")
