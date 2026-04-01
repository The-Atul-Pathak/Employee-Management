from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.attendance import Attendance, AttendanceStatus
from app.models.crm import Lead
from app.models.leave import LeaveRequest
from app.models.project import Project
from app.models.team import Team
from app.models.user import User, UserStatus

router = APIRouter()


def _csv_response(headers: list[str], rows: list[list], filename: str) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_month(month: str) -> tuple[date, date]:
    try:
        year_int, month_int = (int(x) for x in month.split("-", 1))
        start_date = date(year_int, month_int, 1)
    except (ValueError, TypeError):
        raise ValueError("Month must be in YYYY-MM format")
    last_day = monthrange(year_int, month_int)[1]
    return start_date, date(year_int, month_int, last_day)


@router.get("/attendance")
async def attendance_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    format: str = Query(default="json", pattern=r"^(json|csv)$"),
):
    try:
        start_date, end_date = _parse_month(month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    company_id = current_user["company_id"]

    stmt = (
        select(
            User.emp_id,
            User.name,
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)), 0
            ).label("present"),
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)), 0
            ).label("absent"),
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)), 0
            ).label("leave"),
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.half_day, 1), else_=0)), 0
            ).label("half_day"),
            func.count(Attendance.id).label("total_marked"),
        )
        .outerjoin(
            Attendance,
            and_(
                Attendance.company_id == company_id,
                Attendance.user_id == User.id,
                Attendance.date >= start_date,
                Attendance.date <= end_date,
            ),
        )
        .where(
            User.company_id == company_id,
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
        .group_by(User.id, User.emp_id, User.name)
        .order_by(User.name.asc())
    )
    rows = (await db.execute(stmt)).all()

    def _compute_row(emp_id, name, present, absent, leave, half_day, total_marked):
        present = int(present)
        absent = int(absent)
        leave = int(leave)
        half_day = int(half_day)
        total_marked = int(total_marked)
        units = present + half_day * 0.5
        pct = round((units / total_marked) * 100, 2) if total_marked else 0.0
        return emp_id, name, present, absent, leave, half_day, total_marked, pct

    computed = [_compute_row(*r) for r in rows]

    if format == "csv":
        headers = ["Emp ID", "Name", "Present", "Absent", "Leave", "Half Day", "Total Marked", "Attendance %"]
        return _csv_response(headers, [list(r) for r in computed], f"attendance_{month}.csv")

    return {
        "month": month,
        "data": [
            {
                "emp_id": emp_id,
                "name": name,
                "present": present,
                "absent": absent,
                "leave": leave,
                "half_day": half_day,
                "total_marked": total_marked,
                "attendance_percentage": pct,
            }
            for emp_id, name, present, absent, leave, half_day, total_marked, pct in computed
        ],
    }


@router.get("/leaves")
async def leaves_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    year: int = Query(..., ge=2000, le=2100),
    format: str = Query(default="json", pattern=r"^(json|csv)$"),
):
    company_id = current_user["company_id"]

    stmt = (
        select(
            User.emp_id,
            User.name,
            LeaveRequest.leave_type,
            LeaveRequest.start_date,
            LeaveRequest.end_date,
            LeaveRequest.total_days,
            LeaveRequest.status,
        )
        .join(User, User.id == LeaveRequest.user_id)
        .where(
            LeaveRequest.company_id == company_id,
            func.extract("year", LeaveRequest.start_date) == year,
            User.deleted_at.is_(None),
        )
        .order_by(User.name.asc(), LeaveRequest.start_date.asc())
    )
    rows = (await db.execute(stmt)).all()

    if format == "csv":
        headers = ["Emp ID", "Name", "Leave Type", "Start Date", "End Date", "Total Days", "Status"]
        csv_rows = [
            [emp_id, name, leave_type.value, str(start_date), str(end_date), float(total_days), leave_status.value]
            for emp_id, name, leave_type, start_date, end_date, total_days, leave_status in rows
        ]
        return _csv_response(headers, csv_rows, f"leaves_{year}.csv")

    return {
        "year": year,
        "data": [
            {
                "emp_id": emp_id,
                "name": name,
                "leave_type": leave_type.value,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "total_days": float(total_days),
                "status": leave_status.value,
            }
            for emp_id, name, leave_type, start_date, end_date, total_days, leave_status in rows
        ],
    }


@router.get("/projects")
async def projects_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    format: str = Query(default="json", pattern=r"^(json|csv)$"),
):
    company_id = current_user["company_id"]
    leader = aliased(User)

    stmt = (
        select(
            Project.project_name,
            Lead.client_name,
            Team.name,
            leader.name,
            Project.status,
        )
        .outerjoin(Lead, Lead.id == Project.lead_id)
        .outerjoin(Team, Team.id == Project.assigned_team_id)
        .outerjoin(leader, leader.id == Team.manager_id)
        .where(
            Project.company_id == company_id,
            Project.deleted_at.is_(None),
        )
        .order_by(Project.project_name.asc())
    )
    rows = (await db.execute(stmt)).all()

    if format == "csv":
        headers = ["Project Name", "Client", "Team", "Team Leader", "Status"]
        csv_rows = [
            [project_name, client_name or "", team_name or "", leader_name or "", proj_status.value]
            for project_name, client_name, team_name, leader_name, proj_status in rows
        ]
        return _csv_response(headers, csv_rows, "projects_report.csv")

    return {
        "data": [
            {
                "project_name": project_name,
                "client": client_name,
                "team": team_name,
                "leader": leader_name,
                "status": proj_status.value,
            }
            for project_name, client_name, team_name, leader_name, proj_status in rows
        ]
    }
