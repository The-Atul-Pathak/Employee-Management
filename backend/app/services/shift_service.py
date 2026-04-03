from __future__ import annotations

import math
import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import EmployeeShift, Shift
from app.models.user import User
from app.schemas.shift import (
    AssignShiftRequest,
    EmployeeShiftItem,
    EmployeeShiftListResponse,
    ShiftCreate,
    ShiftItem,
    ShiftListResponse,
    ShiftUpdate,
)
from app.schemas.user import PaginationMeta


class ShiftService:
    async def list_shifts(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> ShiftListResponse:
        stmt = (
            select(Shift)
            .where(Shift.company_id == company_id)
            .order_by(Shift.is_default.desc(), Shift.name)
        )
        shifts = (await db.execute(stmt)).scalars().all()
        return ShiftListResponse(data=[ShiftItem.model_validate(s) for s in shifts])

    async def create_shift(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: ShiftCreate,
    ) -> ShiftItem:
        if data.is_default:
            await db.execute(
                update(Shift)
                .where(Shift.company_id == company_id, Shift.is_default == True)  # noqa: E712
                .values(is_default=False)
            )

        shift = Shift(
            company_id=company_id,
            name=data.name,
            start_time=data.start_time,
            end_time=data.end_time,
            grace_minutes=data.grace_minutes,
            is_default=data.is_default,
        )
        db.add(shift)
        await db.flush()
        return ShiftItem.model_validate(shift)

    async def update_shift(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
        data: ShiftUpdate,
    ) -> ShiftItem:
        stmt = select(Shift).where(Shift.id == shift_id, Shift.company_id == company_id)
        shift = (await db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise LookupError("Shift not found")

        if data.is_default is True:
            await db.execute(
                update(Shift)
                .where(Shift.company_id == company_id, Shift.is_default == True)  # noqa: E712
                .values(is_default=False)
            )

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(shift, field, value)
        await db.flush()
        return ShiftItem.model_validate(shift)

    async def delete_shift(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        shift_id: uuid.UUID,
    ) -> None:
        stmt = select(Shift).where(Shift.id == shift_id, Shift.company_id == company_id)
        shift = (await db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise LookupError("Shift not found")
        await db.delete(shift)
        await db.flush()

    async def list_employee_shifts(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> EmployeeShiftListResponse:
        total_stmt = select(func.count()).select_from(EmployeeShift).where(
            EmployeeShift.company_id == company_id
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(EmployeeShift)
            .where(EmployeeShift.company_id == company_id)
            .order_by(EmployeeShift.effective_from.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        employee_shifts = (await db.execute(stmt)).scalars().all()

        if not employee_shifts:
            return EmployeeShiftListResponse(
                data=[],
                meta=PaginationMeta(total=0, page=page, per_page=per_page, total_pages=0),
            )

        user_ids = {es.employee_id for es in employee_shifts}
        shift_ids = {es.shift_id for es in employee_shifts}

        users: dict[uuid.UUID, User] = {}
        user_stmt = select(User).where(User.id.in_(user_ids))
        for u in (await db.execute(user_stmt)).scalars().all():
            users[u.id] = u

        shifts: dict[uuid.UUID, Shift] = {}
        shift_stmt = select(Shift).where(Shift.id.in_(shift_ids))
        for s in (await db.execute(shift_stmt)).scalars().all():
            shifts[s.id] = s

        items = []
        for es in employee_shifts:
            emp = users.get(es.employee_id)
            shift = shifts.get(es.shift_id)
            items.append(EmployeeShiftItem(
                id=es.id,
                employee_id=es.employee_id,
                employee_name=emp.name if emp else "",
                employee_emp_id=emp.emp_id if emp else "",
                shift_id=es.shift_id,
                shift_name=shift.name if shift else "",
                effective_from=str(es.effective_from),
                effective_to=str(es.effective_to) if es.effective_to else None,
            ))

        return EmployeeShiftListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def assign_shift(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: AssignShiftRequest,
    ) -> EmployeeShiftItem:
        # Verify shift exists
        shift_stmt = select(Shift).where(Shift.id == data.shift_id, Shift.company_id == company_id)
        shift = (await db.execute(shift_stmt)).scalar_one_or_none()
        if shift is None:
            raise LookupError("Shift not found")

        effective_from = date.fromisoformat(data.effective_from)
        effective_to = date.fromisoformat(data.effective_to) if data.effective_to else None

        employee_shift = EmployeeShift(
            company_id=company_id,
            employee_id=data.employee_id,
            shift_id=data.shift_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        db.add(employee_shift)
        await db.flush()

        emp_stmt = select(User).where(User.id == data.employee_id)
        emp = (await db.execute(emp_stmt)).scalar_one_or_none()

        return EmployeeShiftItem(
            id=employee_shift.id,
            employee_id=employee_shift.employee_id,
            employee_name=emp.name if emp else "",
            employee_emp_id=emp.emp_id if emp else "",
            shift_id=employee_shift.shift_id,
            shift_name=shift.name,
            effective_from=str(employee_shift.effective_from),
            effective_to=str(employee_shift.effective_to) if employee_shift.effective_to else None,
        )


shift_service = ShiftService()
