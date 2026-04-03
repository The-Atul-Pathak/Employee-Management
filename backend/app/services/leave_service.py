from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.access import Role, UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.company import Company
from app.models.leave import LeaveBalance, LeaveRequest, LeaveStatus, LeaveType
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.leave import (
    ApplyLeaveRequest,
    LeaveBalanceItem,
    LeaveBalanceResponse,
    LeaveDetailResponse,
    LeaveListItem,
    LeaveListResponse,
    LeaveUserInfo,
    MyLeaveItem,
    MyLeavesResponse,
    ReviewLeaveRequest,
)
from app.schemas.user import PaginationMeta

# Imported lazily to avoid circular imports
def _get_notification_service():
    from app.services.notification_service import notification_service
    return notification_service


DEFAULT_LEAVE_QUOTAS: dict[LeaveType, Decimal] = {
    LeaveType.casual: Decimal("12"),
    LeaveType.sick: Decimal("12"),
    LeaveType.earned: Decimal("18"),
    LeaveType.unpaid: Decimal("0"),
    LeaveType.comp_off: Decimal("0"),
}
HR_ROLE_NAMES = {"hr", "human resources"}


class LeaveService:
    async def apply_leave(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ApplyLeaveRequest,
    ) -> LeaveDetailResponse:
        await self._get_user_or_404(db, company_id, user_id)
        total_days = self._validate_leave_dates(data.start_date, data.end_date)

        await self._ensure_no_overlapping_approved_leave(
            db=db,
            company_id=company_id,
            user_id=user_id,
            start_date=data.start_date,
            end_date=data.end_date,
        )

        if await self._is_balance_tracking_enabled(db, company_id, data.leave_type):
            days_by_year = self._split_days_by_year(data.start_date, data.end_date)
            for year, days in days_by_year.items():
                balances = await self.initialize_leave_balances(
                    db=db,
                    company_id=company_id,
                    user_id=user_id,
                    year=year,
                )
                balance = self._find_balance(balances, data.leave_type, year)
                if self._to_decimal(balance.remaining) < days:
                    raise ValueError(f"Insufficient leave balance for {year}")

        leave_request = LeaveRequest(
            company_id=company_id,
            user_id=user_id,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            total_days=float(total_days),
            reason=data.reason.strip() if data.reason else None,
            status=LeaveStatus.pending,
        )
        db.add(leave_request)
        await db.flush()
        return await self.get_leave_detail(db, company_id, leave_request.id)

    async def get_my_leaves(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MyLeavesResponse:
        stmt = (
            select(LeaveRequest)
            .where(
                LeaveRequest.company_id == company_id,
                LeaveRequest.user_id == user_id,
            )
            .order_by(LeaveRequest.applied_at.desc(), LeaveRequest.created_at.desc())
        )
        leaves = (await db.execute(stmt)).scalars().all()
        return MyLeavesResponse(
            data=[
                MyLeaveItem(
                    id=leave.id,
                    leave_type=leave.leave_type,
                    start_date=leave.start_date,
                    end_date=leave.end_date,
                    total_days=float(leave.total_days),
                    reason=leave.reason,
                    status=leave.status,
                    applied_at=leave.applied_at,
                    reviewed_at=leave.reviewed_at,
                    review_notes=leave.review_notes,
                )
                for leave in leaves
            ]
        )

    async def cancel_leave(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        leave_id: uuid.UUID,
    ) -> LeaveDetailResponse:
        leave = await self._get_leave_or_404(db, company_id, leave_id)
        if leave.user_id != user_id:
            raise PermissionError("You can only cancel your own leave requests")
        if leave.status != LeaveStatus.pending:
            raise ValueError("Only pending leave requests can be cancelled")

        leave.status = LeaveStatus.cancelled
        await db.flush()
        return await self.get_leave_detail(db, company_id, leave.id)

    async def get_all_leaves(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        status_filter: LeaveStatus | None,
        page: int,
        per_page: int,
    ) -> LeaveListResponse:
        user_alias = aliased(User)
        filters = [LeaveRequest.company_id == company_id]
        if status_filter is not None:
            filters.append(LeaveRequest.status == status_filter)

        total_stmt = select(func.count()).select_from(LeaveRequest).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(LeaveRequest, user_alias)
            .join(user_alias, user_alias.id == LeaveRequest.user_id)
            .where(*filters)
            .order_by(LeaveRequest.applied_at.desc(), LeaveRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await db.execute(stmt)).all()

        return LeaveListResponse(
            data=[
                LeaveListItem(
                    id=leave.id,
                    user=self._build_user_info(user),
                    leave_type=leave.leave_type,
                    start_date=leave.start_date,
                    end_date=leave.end_date,
                    total_days=float(leave.total_days),
                    status=leave.status,
                    applied_at=leave.applied_at,
                )
                for leave, user in rows
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_leave_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        leave_id: uuid.UUID,
    ) -> LeaveDetailResponse:
        requester = aliased(User)
        reviewer = aliased(User)
        stmt = (
            select(LeaveRequest, requester, reviewer)
            .join(requester, requester.id == LeaveRequest.user_id)
            .outerjoin(reviewer, reviewer.id == LeaveRequest.reviewed_by)
            .where(
                LeaveRequest.id == leave_id,
                LeaveRequest.company_id == company_id,
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise LookupError("Leave request not found")

        leave, user, review_user = row
        return LeaveDetailResponse(
            id=leave.id,
            user=self._build_user_info(user),
            leave_type=leave.leave_type,
            start_date=leave.start_date,
            end_date=leave.end_date,
            total_days=float(leave.total_days),
            reason=leave.reason,
            status=leave.status,
            applied_at=leave.applied_at,
            reviewed_at=leave.reviewed_at,
            review_notes=leave.review_notes,
            reviewer=self._build_user_info(review_user) if review_user is not None else None,
            created_at=leave.created_at,
        )

    async def review_leave(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        leave_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        data: ReviewLeaveRequest,
    ) -> LeaveDetailResponse:
        if data.status not in {LeaveStatus.approved, LeaveStatus.rejected}:
            raise ValueError("Review status must be approved or rejected")

        leave = await self._get_leave_or_404(db, company_id, leave_id)
        if leave.status != LeaveStatus.pending:
            raise ValueError("Only pending leave requests can be reviewed")

        await self._get_user_or_404(db, company_id, reviewer_id)

        leave.status = data.status
        leave.reviewed_by = reviewer_id
        leave.reviewed_at = datetime.now(timezone.utc)
        leave.review_notes = data.review_notes.strip() if data.review_notes else None

        if data.status == LeaveStatus.approved:
            if await self._is_balance_tracking_enabled(db, company_id, leave.leave_type):
                days_by_year = self._split_days_by_year(leave.start_date, leave.end_date)
                for year, days in days_by_year.items():
                    balances = await self.initialize_leave_balances(
                        db=db,
                        company_id=company_id,
                        user_id=leave.user_id,
                        year=year,
                    )
                    balance = self._find_balance(balances, leave.leave_type, year)
                    if self._to_decimal(balance.remaining) < days:
                        raise ValueError(f"Insufficient leave balance for {year}")
                    balance.used = float(self._to_decimal(balance.used) + days)
                    balance.remaining = float(self._to_decimal(balance.remaining) - days)

            await self._mark_attendance_for_leave(
                db=db,
                company_id=company_id,
                user_id=leave.user_id,
                reviewer_id=reviewer_id,
                start_date=leave.start_date,
                end_date=leave.end_date,
                leave_type=leave.leave_type,
            )

        await db.flush()

        # Send notification to the employee
        notif_type = NotificationType.leave_approved if data.status == LeaveStatus.approved else NotificationType.leave_rejected
        notif_title = "Leave Approved" if data.status == LeaveStatus.approved else "Leave Rejected"
        notif_message = (
            f"Your {leave.leave_type.value} leave from {leave.start_date} to {leave.end_date} has been "
            f"{'approved' if data.status == LeaveStatus.approved else 'rejected'}."
        )
        await _get_notification_service().create_notification(
            db=db,
            company_id=company_id,
            user_id=leave.user_id,
            title=notif_title,
            message=notif_message,
            notification_type=notif_type,
            entity_type="leave_request",
            entity_id=leave.id,
        )

        return await self.get_leave_detail(db, company_id, leave.id)

    async def get_leave_balances(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        year: int,
    ) -> LeaveBalanceResponse:
        await self.initialize_leave_balances(db, company_id, user_id, year)
        stmt = (
            select(LeaveBalance)
            .where(
                LeaveBalance.company_id == company_id,
                LeaveBalance.user_id == user_id,
                LeaveBalance.year == year,
            )
            .order_by(LeaveBalance.leave_type.asc())
        )
        balances = (await db.execute(stmt)).scalars().all()
        return LeaveBalanceResponse(
            data=[
                LeaveBalanceItem(
                    leave_type=balance.leave_type,
                    total_quota=float(balance.total_quota),
                    used=float(balance.used),
                    remaining=float(balance.remaining),
                )
                for balance in balances
            ]
        )

    async def initialize_leave_balances(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        year: int,
    ) -> list[LeaveBalance]:
        await self._get_user_or_404(db, company_id, user_id)
        existing_stmt = select(LeaveBalance).where(
            LeaveBalance.company_id == company_id,
            LeaveBalance.user_id == user_id,
            LeaveBalance.year == year,
        )
        existing = (await db.execute(existing_stmt)).scalars().all()
        balances_by_type = {balance.leave_type: balance for balance in existing}
        quotas = await self._get_default_quotas(db, company_id)

        created = False
        for leave_type in LeaveType:
            if leave_type in balances_by_type:
                continue

            total_quota = quotas.get(leave_type, DEFAULT_LEAVE_QUOTAS[leave_type])
            balance = LeaveBalance(
                company_id=company_id,
                user_id=user_id,
                leave_type=leave_type,
                year=year,
                total_quota=float(total_quota),
                used=0,
                remaining=float(total_quota),
            )
            db.add(balance)
            balances_by_type[leave_type] = balance
            created = True

        if created:
            await db.flush()

        return [balances_by_type[leave_type] for leave_type in LeaveType]

    async def ensure_leave_manager_access(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        user = await self._get_user_or_404(db, company_id, user_id)
        if user.is_company_admin:
            return

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
        if not role_names.intersection(HR_ROLE_NAMES):
            raise PermissionError("Admin or HR access required")

    async def ensure_team_lead_or_manager_access(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Allow admin, HR, or any user who manages at least one active team."""
        try:
            await self.ensure_leave_manager_access(db, company_id, user_id)
            return
        except PermissionError:
            pass

        from app.models.team import Team, TeamStatus

        team_stmt = select(Team.id).where(
            Team.company_id == company_id,
            Team.manager_id == user_id,
            Team.status == TeamStatus.active,
        ).limit(1)
        team_id = (await db.execute(team_stmt)).scalar_one_or_none()
        if team_id is None:
            raise PermissionError("Admin, HR, or team lead access required")

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

    async def get_team_leaves(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        manager_id: uuid.UUID,
        status_filter: LeaveStatus | None,
        page: int,
        per_page: int,
    ) -> LeaveListResponse:
        member_ids = await self.get_team_member_ids(db, company_id, manager_id)
        if not member_ids:
            return LeaveListResponse(
                data=[],
                meta=PaginationMeta(total=0, page=page, per_page=per_page, total_pages=0),
            )

        user_alias = aliased(User)
        filters = [
            LeaveRequest.company_id == company_id,
            LeaveRequest.user_id.in_(member_ids),
        ]
        if status_filter is not None:
            filters.append(LeaveRequest.status == status_filter)

        total_stmt = select(func.count()).select_from(LeaveRequest).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(LeaveRequest, user_alias)
            .join(user_alias, user_alias.id == LeaveRequest.user_id)
            .where(*filters)
            .order_by(LeaveRequest.applied_at.desc(), LeaveRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await db.execute(stmt)).all()

        return LeaveListResponse(
            data=[
                LeaveListItem(
                    id=leave.id,
                    user=self._build_user_info(user),
                    leave_type=leave.leave_type,
                    start_date=leave.start_date,
                    end_date=leave.end_date,
                    total_days=float(leave.total_days),
                    status=leave.status,
                    applied_at=leave.applied_at,
                )
                for leave, user in rows
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def is_team_member(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        manager_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> bool:
        member_ids = await self.get_team_member_ids(db, company_id, manager_id)
        return target_user_id in member_ids

    async def ensure_leave_access(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        if actor_user_id == target_user_id:
            await self._get_user_or_404(db, company_id, actor_user_id)
            return
        await self.ensure_leave_manager_access(db, company_id, actor_user_id)

    async def _get_user_or_404(
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

    async def _get_leave_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        leave_id: uuid.UUID,
    ) -> LeaveRequest:
        stmt = select(LeaveRequest).where(
            LeaveRequest.id == leave_id,
            LeaveRequest.company_id == company_id,
        )
        leave = (await db.execute(stmt)).scalar_one_or_none()
        if leave is None:
            raise LookupError("Leave request not found")
        return leave

    async def _ensure_no_overlapping_approved_leave(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> None:
        stmt = select(LeaveRequest).where(
            LeaveRequest.company_id == company_id,
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == LeaveStatus.approved,
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        overlap = (await db.execute(stmt)).scalar_one_or_none()
        if overlap is not None:
            raise ValueError("Leave overlaps with an approved leave request")

    async def _is_balance_tracking_enabled(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        leave_type: LeaveType,
    ) -> bool:
        company = await self._get_company_or_404(db, company_id)
        settings = company.settings or {}
        leave_settings = settings.get("leave_management", {})
        type_settings = (leave_settings.get("leave_types") or {}).get(leave_type.value, {})
        track_balance = type_settings.get("track_balance")
        if track_balance is None:
            return leave_type != LeaveType.unpaid
        return bool(track_balance)

    async def _get_default_quotas(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> dict[LeaveType, Decimal]:
        company = await self._get_company_or_404(db, company_id)
        settings = company.settings or {}
        leave_settings = settings.get("leave_management", {})
        default_quota_map = leave_settings.get("default_quotas") or {}
        leave_type_settings = leave_settings.get("leave_types") or {}

        quotas = dict(DEFAULT_LEAVE_QUOTAS)
        for leave_type in LeaveType:
            configured = default_quota_map.get(leave_type.value)
            if configured is None:
                configured = (leave_type_settings.get(leave_type.value) or {}).get("default_quota")
            if configured is not None:
                quotas[leave_type] = Decimal(str(configured))
        return quotas

    async def _get_company_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> Company:
        stmt = select(Company).where(
            Company.id == company_id,
            Company.deleted_at.is_(None),
        )
        company = (await db.execute(stmt)).scalar_one_or_none()
        if company is None:
            raise LookupError("Company not found")
        return company

    async def _mark_attendance_for_leave(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        start_date: date,
        end_date: date,
        leave_type: LeaveType,
    ) -> None:
        current = start_date
        while current <= end_date:
            stmt = select(Attendance).where(
                Attendance.company_id == company_id,
                Attendance.user_id == user_id,
                Attendance.date == current,
            )
            attendance = (await db.execute(stmt)).scalar_one_or_none()
            note = f"Approved {leave_type.value} leave"
            if attendance is None:
                attendance = Attendance(
                    company_id=company_id,
                    user_id=user_id,
                    date=current,
                    status=AttendanceStatus.leave,
                    marked_by=reviewer_id,
                    notes=note,
                )
                db.add(attendance)
            else:
                attendance.status = AttendanceStatus.leave
                attendance.marked_by = reviewer_id
                attendance.notes = note
            current += timedelta(days=1)

    def _validate_leave_dates(self, start_date: date, end_date: date) -> Decimal:
        if end_date < start_date:
            raise ValueError("End date must be on or after start date")
        if start_date < datetime.now(timezone.utc).date():
            raise ValueError("Leave cannot start in the past")
        return Decimal((end_date - start_date).days + 1)

    def _find_balance(
        self,
        balances: list[LeaveBalance],
        leave_type: LeaveType,
        year: int,
    ) -> LeaveBalance:
        for balance in balances:
            if balance.leave_type == leave_type and balance.year == year:
                return balance
        raise LookupError("Leave balance not found")

    def _build_user_info(self, user: User) -> LeaveUserInfo:
        return LeaveUserInfo(
            id=user.id,
            emp_id=user.emp_id,
            name=user.name,
            email=user.email,
        )

    def _split_days_by_year(self, start_date: date, end_date: date) -> dict[int, Decimal]:
        days_by_year: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        current = start_date
        while current <= end_date:
            days_by_year[current.year] += Decimal("1")
            current += timedelta(days=1)
        return dict(days_by_year)

    def _to_decimal(self, value: Decimal | float | int) -> Decimal:
        return value if isinstance(value, Decimal) else Decimal(str(value))


leave_service = LeaveService()
