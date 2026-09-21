"""
FastAPI router for system health diagnostics, dashboard stats, and conversion analytics.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from src.db import get_stats, get_analytics_summary
from src.services.health_service import get_system_health

router = APIRouter(prefix="/api", tags=["Stats & Health"])


@router.get("/health")
def api_get_health():
    """Return live session connectivity status for LinkedIn, ChatGPT, Gmail, and DB."""
    try:
        return get_system_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def api_get_stats():
    """Return counts for dashboard metrics cards."""
    try:
        stats = get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
def api_get_analytics(days: Optional[int] = Query(30, ge=0, le=365)):
    """Return aggregated analytics for dashboard charts (applied trend, scraping inflow, status breakdown, etc.)."""
    try:
        data = get_analytics_summary(days=days)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
