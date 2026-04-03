from __future__ import annotations

import uuid
from datetime import date, timezone, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.access import Role, UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.team import Team, TeamMember, TeamStatus
from app.models.user import User, UserStatus
from app.schemas.dashboard import DashboardSummary

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive"}


async def _is_hr_role(db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Role.company_id == company_id,
            Role.deleted_at.is_(None),
        )
    )
    role_names = {name.strip().lower() for (name,) in (await db.execute(stmt)).all()}
    return bool(role_names.intersection(HR_ROLE_NAMES))


async def _get_managed_team(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[Team]:
    stmt = select(Team).where(
        Team.company_id == company_id,
        Team.manager_id == user_id,
        Team.status == TeamStatus.active,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_team_member_ids(
    db: AsyncSession,
    team_id: uuid.UUID,
) -> list[uuid.UUID]:
    stmt = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    return [uid for (uid,) in (await db.execute(stmt)).all()]


async def _build_admin_summary(
    db: AsyncSession,
    company_id: uuid.UUID,
    today: date,
) -> DashboardSummary:
    # Attendance summary
    attn_stmt = (
        select(
            func.count(User.id),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.half_day, 1), else_=0)), 0),
        )
        .select_from(User)
        .outerjoin(
            Attendance,
            and_(
                Attendance.company_id == company_id,
                Attendance.user_id == User.id,
                Attendance.date == today,
            ),
        )
        .where(
            User.company_id == company_id,
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
    )
    total, present, absent, on_leave, half_day = (await db.execute(attn_stmt)).one()

    # Pending leaves
    pending_stmt = select(func.count()).select_from(LeaveRequest).where(
        LeaveRequest.company_id == company_id,
        LeaveRequest.status == LeaveStatus.pending,
    )
    pending = (await db.execute(pending_stmt)).scalar_one()

    # Total active teams
    teams_stmt = select(func.count()).select_from(Team).where(
        Team.company_id == company_id,
        Team.status == TeamStatus.active,
    )
    total_teams = (await db.execute(teams_stmt)).scalar_one()

    return DashboardSummary(
        role="admin",
        present=present,
        absent=absent,
        on_leave=on_leave,
        half_day=half_day,
        total_members=total,
        pending_leave_approvals=pending,
        total_teams=total_teams,
    )


async def _build_team_lead_summary(
    db: AsyncSession,
    company_id: uuid.UUID,
    team: Team,
    today: date,
) -> DashboardSummary:
    member_ids = await _get_team_member_ids(db, team.id)
    team_size = len(member_ids)

    if not member_ids:
        return DashboardSummary(
            role="team_lead",
            team_id=str(team.id),
            team_name=team.name,
            total_members=0,
        )

    # Attendance summary for team
    attn_stmt = (
        select(
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Attendance.status == AttendanceStatus.half_day, 1), else_=0)), 0),
        )
        .select_from(User)
        .outerjoin(
            Attendance,
            and_(
                Attendance.company_id == company_id,
                Attendance.user_id == User.id,
                Attendance.date == today,
            ),
        )
        .where(
            User.company_id == company_id,
            User.id.in_(member_ids),
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
    )
    present, absent, on_leave, half_day = (await db.execute(attn_stmt)).one()

    # Pending leaves for team members
    pending_stmt = select(func.count()).select_from(LeaveRequest).where(
        LeaveRequest.company_id == company_id,
        LeaveRequest.user_id.in_(member_ids),
        LeaveRequest.status == LeaveStatus.pending,
    )
    pending = (await db.execute(pending_stmt)).scalar_one()

    return DashboardSummary(
        role="team_lead",
        team_id=str(team.id),
        team_name=team.name,
        present=present,
        absent=absent,
        on_leave=on_leave,
        half_day=half_day,
        total_members=team_size,
        pending_leave_approvals=pending,
    )


async def _build_employee_summary(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    today: date,
) -> DashboardSummary:
    stmt = select(Attendance).where(
        Attendance.company_id == company_id,
        Attendance.user_id == user_id,
        Attendance.date == today,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()

    return DashboardSummary(
        role="employee",
        today_status=record.status.value if record else None,
        check_in=record.check_in_time.isoformat() if record and record.check_in_time else None,
        check_out=record.check_out_time.isoformat() if record and record.check_out_time else None,
    )


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DashboardSummary:
    user_id: uuid.UUID = current_user["user_id"]
    company_id: uuid.UUID = current_user["company_id"]
    today = date.today()

    if current_user["is_company_admin"] or await _is_hr_role(db, company_id, user_id):
        return await _build_admin_summary(db, company_id, today)

    team = await _get_managed_team(db, company_id, user_id)
    if team is not None:
        return await _build_team_lead_summary(db, company_id, team, today)

    return await _build_employee_summary(db, company_id, user_id, today)
