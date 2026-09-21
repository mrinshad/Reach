"""
Reach API Package
Aggregates all modular endpoint routers into a unified APIRouter.
"""

from fastapi import APIRouter

from .posts import router as posts_router
from .tasks import router as tasks_router
from .stats import router as stats_router
from .settings import router as settings_router

api_router = APIRouter()
api_router.include_router(posts_router)
api_router.include_router(tasks_router)
api_router.include_router(stats_router)
api_router.include_router(settings_router)

__all__ = ["api_router", "posts_router", "tasks_router", "stats_router", "settings_router"]
