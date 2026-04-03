from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Role-differentiated dashboard summary returned by GET /dashboard/summary."""

    role: str  # "admin", "team_lead", "employee"

    # Attendance stats — populated for admin and team_lead
    present: int = 0
    absent: int = 0
    on_leave: int = 0
    half_day: int = 0
    total_members: int = 0

    # Leave stats — populated for admin and team_lead
    pending_leave_approvals: int = 0

    # Admin-only
    total_teams: int = 0

    # Team lead — identifies which team
    team_id: Optional[str] = None
    team_name: Optional[str] = None

    # Employee — today's personal attendance
    today_status: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
