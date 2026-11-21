"""
Dismissed Roles API Router
(src/api/dismissed_roles.py)

REST API endpoints for viewing, managing, searching, adding, and deleting
dismissed job roles across all scraping channels.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.db.dismissed_roles import (
    get_dismissed_roles,
    get_dismissed_roles_stats,
    add_dismissed_role,
    delete_dismissed_role,
    delete_dismissed_roles_batch,
    sync_dismissed_roles_from_posts,
)

router = APIRouter(prefix="/api/dismissed-roles", tags=["Dismissed Roles"])


class AddDismissedRolePayload(BaseModel):
    role_title: str
    source: Optional[str] = "Manual"
    reason: Optional[str] = None


class DeleteBatchDismissedRolesPayload(BaseModel):
    ids: List[str]


@router.get("")
def api_get_dismissed_roles(
    search: Optional[str] = None,
    source: Optional[str] = None,
    order_by: str = Query("name_asc", pattern="^(name_asc|name_desc|recent|oldest|occurrences_desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve paginated list of dismissed roles with search and source filtering."""
    try:
        lim = getattr(limit, "default", limit) if hasattr(limit, "default") else limit
        off = getattr(offset, "default", offset) if hasattr(offset, "default") else offset
        ord_by = getattr(order_by, "default", order_by) if hasattr(order_by, "default") else order_by
        data = get_dismissed_roles(
            search=search,
            source=source,
            order_by=str(ord_by),
            limit=int(lim),
            offset=int(off),
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def api_get_dismissed_roles_stats():
    """Retrieve total count and channel source breakdown for KPI ribbon."""
    try:
        return get_dismissed_roles_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def api_add_dismissed_role(payload: AddDismissedRolePayload):
    """Add a new role title to the dismissed roles registry."""
    if not payload.role_title or not payload.role_title.strip():
        raise HTTPException(status_code=400, detail="Role title is required.")
    try:
        res = add_dismissed_role(
            role_title=payload.role_title.strip(),
            source=payload.source or "Manual",
            reason=payload.reason.strip() if payload.reason else "Manually dismissed",
        )
        return {"success": True, "message": f"Added '{payload.role_title}' to dismissed roles.", "role": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{role_id}")
def api_delete_dismissed_role(role_id: str):
    """Delete / restore a dismissed role from the registry."""
    try:
        deleted = delete_dismissed_role(role_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Role not found in dismissed registry.")
        return {"success": True, "message": "Dismissed role removed successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-batch")
def api_delete_batch_dismissed_roles(payload: DeleteBatchDismissedRolesPayload):
    """Batch delete / restore selected dismissed roles."""
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No role IDs provided.")
    try:
        count = delete_dismissed_roles_batch(payload.ids)
        return {"success": True, "message": f"Successfully removed {count} dismissed role(s).", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
def api_sync_dismissed_roles():
    """Trigger incremental sync of dismissed roles from historical rejected posts."""
    try:
        count = sync_dismissed_roles_from_posts()
        stats = get_dismissed_roles_stats()
        return {"success": True, "message": f"Synced {count} role(s) from posts.", "total": stats["total"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
