from __future__ import annotations
from fastapi import APIRouter

from app.api.v1.endpoints import attendance, auth, leads, leaves, notifications, platform, projects, roles, tasks, teams, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(leaves.router, prefix="/leaves", tags=["leaves"])
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
api_router.include_router(roles.features_router, prefix="/features", tags=["features"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
