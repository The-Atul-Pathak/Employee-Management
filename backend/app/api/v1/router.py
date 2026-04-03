from __future__ import annotations
from fastapi import APIRouter

from app.api.v1.endpoints import (
    announcements,
    assets,
    attendance,
    auth,
    company,
    dashboard,
    documents,
    expenses,
    holidays,
    leads,
    leaves,
    notifications,
    onboarding,
    payroll,
    performance,
    platform,
    projects,
    reports,
    roles,
    shifts,
    tasks,
    teams,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
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
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(holidays.router, prefix="/holidays", tags=["holidays"])
api_router.include_router(company.router, prefix="/company", tags=["company"])
api_router.include_router(announcements.router, prefix="/announcements", tags=["announcements"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(shifts.router, prefix="/shifts", tags=["shifts"])
api_router.include_router(payroll.router, prefix="/payroll", tags=["payroll"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])
