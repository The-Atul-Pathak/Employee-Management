from __future__ import annotations
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.models.access import Role, UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.user import User, UserStatus
from app.schemas.attendance import (
    AttendanceListItem,
    AttendanceListResponse,
    AttendanceSummaryResponse,
    EmployeeAttendanceRecord,
    EmployeeAttendanceSummary,
    MarkAttendanceRequest,
)


class AttendanceService:
    async def get_daily_attendance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
    ) -> AttendanceListResponse:
        marker = aliased(User)
        stmt = (
            select(
                User.id,
                User.emp_id,
                User.name,
                Attendance.status,
                marker.name,
                Attendance.check_in_time,
                Attendance.check_out_time,
                Attendance.notes,
            )
            .outerjoin(
                Attendance,
                and_(
                    Attendance.company_id == company_id,
                    Attendance.user_id == User.id,
                    Attendance.date == target_date,
                ),
            )
            .outerjoin(marker, marker.id == Attendance.marked_by)
            .where(
                User.company_id == company_id,
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
            .order_by(User.name.asc())
        )
        rows = (await db.execute(stmt)).all()
        return AttendanceListResponse(
            data=[
                AttendanceListItem(
                    user_id=user_id,
                    emp_id=emp_id,
                    name=name,
                    status=attendance_status.value if attendance_status else "Unmarked",
                    marked_by_name=marked_by_name,
                    check_in=check_in,
                    check_out=check_out,
                    notes=notes,
                )
                for user_id, emp_id, name, attendance_status, marked_by_name, check_in, check_out, notes in rows
            ]
        )

    async def mark_attendance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: MarkAttendanceRequest,
        marked_by_user_id: uuid.UUID,
    ) -> None:
        await self._validate_markable_date(data.date)
        await self._ensure_active_user(db, company_id, data.user_id)
        await self._ensure_active_user(db, company_id, marked_by_user_id)

        stmt = insert(Attendance).values(
            company_id=company_id,
            user_id=data.user_id,
            date=data.date,
            status=data.status,
            marked_by=marked_by_user_id,
            notes=data.notes,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Attendance.company_id, Attendance.user_id, Attendance.date],
            set_={
                "status": data.status,
                "marked_by": marked_by_user_id,
                "notes": data.notes,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        await db.flush()

    async def get_daily_summary(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
    ) -> AttendanceSummaryResponse:
        stmt = (
            select(
                func.count(User.id),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.half_day, 1), else_=0)),
                    0,
                ),
            )
            .select_from(User)
            .outerjoin(
                Attendance,
                and_(
                    Attendance.company_id == company_id,
                    Attendance.user_id == User.id,
                    Attendance.date == target_date,
                ),
            )
            .where(
                User.company_id == company_id,
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
        )
        total_employees, present, absent, leave, half_day = (await db.execute(stmt)).one()
        return AttendanceSummaryResponse(
            present=present,
            absent=absent,
            leave=leave,
            half_day=half_day,
            total_employees=total_employees,
        )

    async def get_employee_monthly_summary(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        month: str,
    ) -> EmployeeAttendanceSummary:
        await self._ensure_user_exists(db, company_id, user_id)
        start_date, end_date = self._parse_month(month)

        stmt = select(
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Attendance.status == AttendanceStatus.present, 1.0),
                        (Attendance.status == AttendanceStatus.half_day, 0.5),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
            func.count(Attendance.id),
        ).where(
            Attendance.company_id == company_id,
            Attendance.user_id == user_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )

        present, absent, leave, attendance_units, total_marked = (await db.execute(stmt)).one()
        percentage = round((attendance_units / total_marked) * 100, 2) if total_marked else 0.0

        return EmployeeAttendanceSummary(
            present=present,
            absent=absent,
            leave=leave,
            attendance_percentage=percentage,
        )

    async def get_employee_monthly_records(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        month: str,
    ) -> list[EmployeeAttendanceRecord]:
        await self._ensure_user_exists(db, company_id, user_id)
        start_date, end_date = self._parse_month(month)
        marker = aliased(User)

        stmt = (
            select(
                Attendance.date,
                Attendance.status,
                marker.name,
                Attendance.check_in_time,
                Attendance.check_out_time,
                Attendance.notes,
            )
            .outerjoin(marker, marker.id == Attendance.marked_by)
            .where(
                Attendance.company_id == company_id,
                Attendance.user_id == user_id,
                Attendance.date >= start_date,
                Attendance.date <= end_date,
            )
            .order_by(Attendance.date.asc())
        )
        rows = (await db.execute(stmt)).all()
        return [
            EmployeeAttendanceRecord(
                date=record_date,
                status=attendance_status,
                marked_by=marked_by_name,
                check_in=check_in,
                check_out=check_out,
                notes=notes,
            )
            for record_date, attendance_status, marked_by_name, check_in, check_out, notes in rows
        ]

    async def self_check_in(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        await self._ensure_active_user(db, company_id, user_id)
        now = datetime.now(timezone.utc)
        today = now.date()

        existing = await self._get_attendance(db, company_id, user_id, today)
        if existing is not None:
            raise ValueError("Attendance already marked for today")

        db.add(
            Attendance(
                company_id=company_id,
                user_id=user_id,
                date=today,
                status=AttendanceStatus.present,
                check_in_time=now,
                marked_by=user_id,
            )
        )
        await db.flush()

    async def self_check_out(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        await self._ensure_active_user(db, company_id, user_id)
        now = datetime.now(timezone.utc)
        today = now.date()

        attendance = await self._get_attendance(db, company_id, user_id, today)
        if attendance is None or attendance.check_in_time is None:
            raise ValueError("Check-in required before check-out")
        if attendance.check_out_time is not None:
            raise ValueError("Already checked out for today")

        attendance.check_out_time = now
        await db.flush()

    async def can_manage_attendance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        is_company_admin: bool,
    ) -> bool:
        if is_company_admin:
            return True

        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.company_id == company_id,
                Role.deleted_at.is_(None),
            )
        )
        role_names = [name.strip().lower() for name in (await db.execute(stmt)).scalars().all()]
        return any(name in {"hr", "human resources"} for name in role_names)

    async def _ensure_user_exists(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        stmt = select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise LookupError("User not found")
        return user

    async def _ensure_active_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        user = await self._ensure_user_exists(db, company_id, user_id)
        if user.status != UserStatus.active:
            raise ValueError("User is not active")
        return user

    async def _get_attendance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        target_date: date,
    ) -> Attendance | None:
        stmt = select(Attendance).where(
            Attendance.company_id == company_id,
            Attendance.user_id == user_id,
            Attendance.date == target_date,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _validate_markable_date(self, target_date: date) -> None:
        today = date.today()
        if target_date > today:
            raise ValueError("Attendance cannot be marked for a future date")

        max_days = settings.ATTENDANCE_MARK_PAST_DAYS_LIMIT
        if target_date < today - timedelta(days=max_days):
            raise ValueError(
                f"Attendance cannot be marked more than {max_days} days in the past"
            )

    async def get_team_member_ids(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        manager_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        from app.models.team import Team, TeamMember, TeamStatus

        team_stmt = select(Team.id).where(
            Team.company_id == company_id,
            Team.manager_id == manager_id,
            Team.status == TeamStatus.active,
        )
        team_id = (await db.execute(team_stmt)).scalar_one_or_none()
        if team_id is None:
            return []

        member_stmt = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        return [uid for (uid,) in (await db.execute(member_stmt)).all()]

    async def get_daily_attendance_scoped(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
        scope: str = "all",
        manager_id: uuid.UUID | None = None,
    ) -> AttendanceListResponse:
        if scope == "team" and manager_id is not None:
            member_ids = await self.get_team_member_ids(db, company_id, manager_id)
            if not member_ids:
                return AttendanceListResponse(data=[])
            return await self._get_attendance_for_users(db, company_id, member_ids, target_date)
        return await self.get_daily_attendance(db, company_id, target_date)

    async def get_daily_summary_scoped(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_date: date,
        scope: str = "all",
        manager_id: uuid.UUID | None = None,
    ) -> AttendanceSummaryResponse:
        if scope == "team" and manager_id is not None:
            member_ids = await self.get_team_member_ids(db, company_id, manager_id)
            if not member_ids:
                return AttendanceSummaryResponse(
                    present=0, absent=0, leave=0, half_day=0, total_employees=0
                )
            return await self._get_summary_for_users(db, company_id, member_ids, target_date)
        return await self.get_daily_summary(db, company_id, target_date)

    async def _get_attendance_for_users(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        target_date: date,
    ) -> AttendanceListResponse:
        marker = aliased(User)
        stmt = (
            select(
                User.id,
                User.emp_id,
                User.name,
                Attendance.status,
                marker.name,
                Attendance.check_in_time,
                Attendance.check_out_time,
                Attendance.notes,
            )
            .outerjoin(
                Attendance,
                and_(
                    Attendance.company_id == company_id,
                    Attendance.user_id == User.id,
                    Attendance.date == target_date,
                ),
            )
            .outerjoin(marker, marker.id == Attendance.marked_by)
            .where(
                User.company_id == company_id,
                User.id.in_(user_ids),
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
            .order_by(User.name.asc())
        )
        rows = (await db.execute(stmt)).all()
        return AttendanceListResponse(
            data=[
                AttendanceListItem(
                    user_id=user_id,
                    emp_id=emp_id,
                    name=name,
                    status=attendance_status.value if attendance_status else "Unmarked",
                    marked_by_name=marked_by_name,
                    check_in=check_in,
                    check_out=check_out,
                    notes=notes,
                )
                for user_id, emp_id, name, attendance_status, marked_by_name, check_in, check_out, notes in rows
            ]
        )

    async def _get_summary_for_users(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        target_date: date,
    ) -> AttendanceSummaryResponse:
        stmt = (
            select(
                func.count(User.id),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.present, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.absent, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.leave, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Attendance.status == AttendanceStatus.half_day, 1), else_=0)),
                    0,
                ),
            )
            .select_from(User)
            .outerjoin(
                Attendance,
                and_(
                    Attendance.company_id == company_id,
                    Attendance.user_id == User.id,
                    Attendance.date == target_date,
                ),
            )
            .where(
                User.company_id == company_id,
                User.id.in_(user_ids),
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
        )
        total_employees, present, absent, leave, half_day = (await db.execute(stmt)).one()
        return AttendanceSummaryResponse(
            present=present,
            absent=absent,
            leave=leave,
            half_day=half_day,
            total_employees=total_employees,
        )

    def _parse_month(self, month: str) -> tuple[date, date]:
        try:
            year, month_value = month.split("-", maxsplit=1)
            year_int = int(year)
            month_int = int(month_value)
            start_date = date(year_int, month_int, 1)
        except (ValueError, TypeError):
            raise ValueError("Month must be in YYYY-MM format")

        last_day = monthrange(start_date.year, start_date.month)[1]
        end_date = date(start_date.year, start_date.month, last_day)
        return start_date, end_date


attendance_service = AttendanceService()
