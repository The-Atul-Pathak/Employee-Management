from __future__ import annotations

import calendar
import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance, AttendanceStatus
from app.models.leave import LeaveRequest, LeaveStatus
from app.models.payroll import PayrollRun, PayrollRunStatus, Payslip, SalaryStructure
from app.models.shift import Holiday
from app.models.user import User
from app.schemas.payroll import (
    MyPayslipItem,
    MyPayslipsResponse,
    PayrollRunDetail,
    PayrollRunItem,
    PayrollRunListResponse,
    PayrollRunRequest,
    PayslipItem,
    SalaryStructureCreate,
    SalaryStructureItem,
    SalaryStructureListResponse,
)
from app.schemas.user import PaginationMeta


class PayrollService:
    # ── Salary Structures ──────────────────────────────────────────────────────

    async def list_salary_structures(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> SalaryStructureListResponse:
        total_stmt = select(func.count()).select_from(SalaryStructure).where(
            SalaryStructure.company_id == company_id,
            SalaryStructure.deleted_at.is_(None),
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(SalaryStructure)
            .where(
                SalaryStructure.company_id == company_id,
                SalaryStructure.deleted_at.is_(None),
            )
            .order_by(SalaryStructure.effective_from.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        structures = (await db.execute(stmt)).scalars().all()

        user_ids = {s.employee_id for s in structures}
        users: dict[uuid.UUID, User] = {}
        if user_ids:
            user_stmt = select(User).where(User.id.in_(user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        return SalaryStructureListResponse(
            data=[self._to_structure_item(s, users.get(s.employee_id)) for s in structures],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_employee_salary_structure(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> SalaryStructureItem | None:
        stmt = (
            select(SalaryStructure)
            .where(
                SalaryStructure.company_id == company_id,
                SalaryStructure.employee_id == employee_id,
                SalaryStructure.deleted_at.is_(None),
            )
            .order_by(SalaryStructure.effective_from.desc())
            .limit(1)
        )
        structure = (await db.execute(stmt)).scalar_one_or_none()
        if structure is None:
            return None

        user_stmt = select(User).where(User.id == employee_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        return self._to_structure_item(structure, user)

    async def create_salary_structure(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: SalaryStructureCreate,
    ) -> SalaryStructureItem:
        structure = SalaryStructure(
            company_id=company_id,
            employee_id=data.employee_id,
            effective_from=data.effective_from,
            ctc_monthly=data.ctc_monthly,
            basic=data.basic,
            hra=data.hra,
            special_allowance=data.special_allowance,
            pf_employer=data.pf_employer,
            pf_employee=data.pf_employee,
            esi_employer=data.esi_employer,
            esi_employee=data.esi_employee,
            professional_tax=data.professional_tax,
        )
        db.add(structure)
        await db.flush()

        user_stmt = select(User).where(User.id == data.employee_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        return self._to_structure_item(structure, user)

    # ── Payroll Run ────────────────────────────────────────────────────────────

    async def run_payroll(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        run_by: uuid.UUID,
        data: PayrollRunRequest,
    ) -> PayrollRunDetail:
        # Check for existing run
        existing_stmt = select(PayrollRun).where(
            PayrollRun.company_id == company_id,
            PayrollRun.month == data.month,
            PayrollRun.year == data.year,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"Payroll run for {data.month}/{data.year} already exists")

        # Get working days for the month (calendar days minus weekends and holidays)
        working_days = await self._get_working_days(db, company_id, data.year, data.month)

        # Get all active employees with salary structures
        month_start = f"{data.year}-{data.month:02d}-01"
        structures_stmt = (
            select(SalaryStructure)
            .where(
                SalaryStructure.company_id == company_id,
                SalaryStructure.effective_from <= month_start,
                SalaryStructure.deleted_at.is_(None),
            )
            .order_by(SalaryStructure.employee_id, SalaryStructure.effective_from.desc())
        )
        all_structures = (await db.execute(structures_stmt)).scalars().all()

        # Get most recent structure per employee
        employee_structure: dict[uuid.UUID, SalaryStructure] = {}
        for s in all_structures:
            if s.employee_id not in employee_structure:
                employee_structure[s.employee_id] = s

        if not employee_structure:
            raise ValueError("No salary structures found for this period")

        # Get attendance and leave data for all employees
        employee_ids = list(employee_structure.keys())
        attendance_data = await self._get_month_attendance(
            db, company_id, employee_ids, data.year, data.month
        )
        leave_data = await self._get_approved_leave_days(
            db, company_id, employee_ids, data.year, data.month
        )

        # Create payroll run
        payroll_run = PayrollRun(
            company_id=company_id,
            month=data.month,
            year=data.year,
            status=PayrollRunStatus.draft,
            run_by=run_by,
        )
        db.add(payroll_run)
        await db.flush()

        # Generate payslips
        payslips = []
        total_gross = Decimal("0")
        total_deductions = Decimal("0")
        total_net = Decimal("0")

        for emp_id, structure in employee_structure.items():
            att = attendance_data.get(emp_id, {})
            present = Decimal(str(att.get("present", 0) + att.get("half_day", 0) * 0.5))
            leave = Decimal(str(leave_data.get(emp_id, 0)))
            paid_days = present + leave
            lop = max(Decimal("0"), Decimal(str(working_days)) - paid_days)

            # Calculate gross based on ratio of paid_days / working_days
            wd = Decimal(str(working_days)) if working_days > 0 else Decimal("1")
            ratio = paid_days / wd
            gross = (Decimal(str(structure.ctc_monthly)) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            basic = (Decimal(str(structure.basic)) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            hra = (Decimal(str(structure.hra)) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            special = (Decimal(str(structure.special_allowance)) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            pf_ded = Decimal(str(structure.pf_employee))
            esi_ded = Decimal(str(structure.esi_employee)) if structure.esi_employee else None
            pt_ded = Decimal(str(structure.professional_tax))

            deductions = pf_ded + pt_ded + (esi_ded or Decimal("0"))
            net = (gross - deductions).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            payslip = Payslip(
                company_id=company_id,
                payroll_run_id=payroll_run.id,
                employee_id=emp_id,
                month=data.month,
                year=data.year,
                working_days=working_days,
                present_days=float(present),
                leave_days=float(leave),
                lop_days=float(lop),
                gross_salary=float(gross),
                basic=float(basic),
                hra=float(hra),
                special_allowance=float(special),
                pf_deduction=float(pf_ded),
                esi_deduction=float(esi_ded) if esi_ded else None,
                pt_deduction=float(pt_ded),
                tds_deduction=None,
                other_deductions=0,
                net_salary=float(net),
            )
            db.add(payslip)
            payslips.append(payslip)

            total_gross += gross
            total_deductions += deductions
            total_net += net

        payroll_run.total_gross = float(total_gross)
        payroll_run.total_deductions = float(total_deductions)
        payroll_run.total_net = float(total_net)
        await db.flush()

        # Fetch user info for payslips
        user_stmt = select(User).where(User.id.in_(employee_ids))
        users: dict[uuid.UUID, User] = {}
        for u in (await db.execute(user_stmt)).scalars().all():
            users[u.id] = u

        return PayrollRunDetail(
            id=payroll_run.id,
            company_id=payroll_run.company_id,
            month=payroll_run.month,
            year=payroll_run.year,
            status=payroll_run.status,
            total_gross=float(total_gross),
            total_deductions=float(total_deductions),
            total_net=float(total_net),
            run_by=payroll_run.run_by,
            approved_by=payroll_run.approved_by,
            run_at=payroll_run.run_at,
            paid_at=payroll_run.paid_at,
            payslip_count=len(payslips),
            payslips=[self._to_payslip_item(p, users.get(p.employee_id)) for p in payslips],
        )

    async def list_runs(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> PayrollRunListResponse:
        total_stmt = select(func.count()).select_from(PayrollRun).where(
            PayrollRun.company_id == company_id
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(PayrollRun)
            .where(PayrollRun.company_id == company_id)
            .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        runs = (await db.execute(stmt)).scalars().all()

        # Count payslips per run
        run_ids = [r.id for r in runs]
        counts: dict[uuid.UUID, int] = {}
        if run_ids:
            count_stmt = (
                select(Payslip.payroll_run_id, func.count().label("cnt"))
                .where(Payslip.payroll_run_id.in_(run_ids))
                .group_by(Payslip.payroll_run_id)
            )
            for row in (await db.execute(count_stmt)).all():
                counts[row[0]] = row[1]

        return PayrollRunListResponse(
            data=[
                PayrollRunItem(
                    id=r.id,
                    company_id=r.company_id,
                    month=r.month,
                    year=r.year,
                    status=r.status,
                    total_gross=float(r.total_gross),
                    total_deductions=float(r.total_deductions),
                    total_net=float(r.total_net),
                    run_by=r.run_by,
                    approved_by=r.approved_by,
                    run_at=r.run_at,
                    paid_at=r.paid_at,
                    payslip_count=counts.get(r.id, 0),
                )
                for r in runs
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_run_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> PayrollRunDetail:
        run_stmt = select(PayrollRun).where(
            PayrollRun.id == run_id, PayrollRun.company_id == company_id
        )
        run = (await db.execute(run_stmt)).scalar_one_or_none()
        if run is None:
            raise LookupError("Payroll run not found")

        payslip_stmt = select(Payslip).where(Payslip.payroll_run_id == run_id)
        payslips = (await db.execute(payslip_stmt)).scalars().all()

        emp_ids = {p.employee_id for p in payslips}
        users: dict[uuid.UUID, User] = {}
        if emp_ids:
            user_stmt = select(User).where(User.id.in_(emp_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        return PayrollRunDetail(
            id=run.id,
            company_id=run.company_id,
            month=run.month,
            year=run.year,
            status=run.status,
            total_gross=float(run.total_gross),
            total_deductions=float(run.total_deductions),
            total_net=float(run.total_net),
            run_by=run.run_by,
            approved_by=run.approved_by,
            run_at=run.run_at,
            paid_at=run.paid_at,
            payslip_count=len(payslips),
            payslips=[self._to_payslip_item(p, users.get(p.employee_id)) for p in payslips],
        )

    async def update_run_status(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        run_id: uuid.UUID,
        new_status: PayrollRunStatus,
        approved_by: uuid.UUID | None = None,
    ) -> PayrollRunItem:
        run_stmt = select(PayrollRun).where(
            PayrollRun.id == run_id, PayrollRun.company_id == company_id
        )
        run = (await db.execute(run_stmt)).scalar_one_or_none()
        if run is None:
            raise LookupError("Payroll run not found")

        run.status = new_status
        if new_status == PayrollRunStatus.approved and approved_by:
            run.approved_by = approved_by
        if new_status == PayrollRunStatus.paid:
            run.paid_at = datetime.now(timezone.utc)
        await db.flush()

        count_stmt = select(func.count()).select_from(Payslip).where(Payslip.payroll_run_id == run_id)
        count = (await db.execute(count_stmt)).scalar_one()

        return PayrollRunItem(
            id=run.id,
            company_id=run.company_id,
            month=run.month,
            year=run.year,
            status=run.status,
            total_gross=float(run.total_gross),
            total_deductions=float(run.total_deductions),
            total_net=float(run.total_net),
            run_by=run.run_by,
            approved_by=run.approved_by,
            run_at=run.run_at,
            paid_at=run.paid_at,
            payslip_count=count,
        )

    async def get_my_payslips(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID,
        page: int = 1,
        per_page: int = 12,
    ) -> MyPayslipsResponse:
        total_stmt = select(func.count()).select_from(Payslip).where(
            Payslip.company_id == company_id,
            Payslip.employee_id == employee_id,
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Payslip)
            .where(
                Payslip.company_id == company_id,
                Payslip.employee_id == employee_id,
            )
            .order_by(Payslip.year.desc(), Payslip.month.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        payslips = (await db.execute(stmt)).scalars().all()

        return MyPayslipsResponse(
            data=[
                MyPayslipItem(
                    id=p.id,
                    month=p.month,
                    year=p.year,
                    working_days=p.working_days,
                    present_days=float(p.present_days),
                    leave_days=float(p.leave_days),
                    lop_days=float(p.lop_days),
                    gross_salary=float(p.gross_salary),
                    basic=float(p.basic),
                    hra=float(p.hra),
                    special_allowance=float(p.special_allowance),
                    pf_deduction=float(p.pf_deduction),
                    esi_deduction=float(p.esi_deduction) if p.esi_deduction else None,
                    pt_deduction=float(p.pt_deduction),
                    other_deductions=float(p.other_deductions),
                    net_salary=float(p.net_salary),
                )
                for p in payslips
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_working_days(
        self, db: AsyncSession, company_id: uuid.UUID, year: int, month: int
    ) -> int:
        _, days_in_month = calendar.monthrange(year, month)
        # Count Mon-Fri
        working = sum(
            1 for d in range(1, days_in_month + 1)
            if date(year, month, d).weekday() < 5
        )
        # Subtract holidays
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)
        holiday_stmt = select(func.count()).select_from(Holiday).where(
            Holiday.company_id == company_id,
            Holiday.date >= month_start,
            Holiday.date <= month_end,
            Holiday.is_optional == False,  # noqa: E712
        )
        holiday_count = (await db.execute(holiday_stmt)).scalar_one()
        return max(1, working - holiday_count)

    async def _get_month_attendance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_ids: list[uuid.UUID],
        year: int,
        month: int,
    ) -> dict[uuid.UUID, dict]:
        _, days_in_month = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        stmt = select(Attendance).where(
            Attendance.company_id == company_id,
            Attendance.user_id.in_(employee_ids),
            Attendance.date >= month_start,
            Attendance.date <= month_end,
        )
        records = (await db.execute(stmt)).scalars().all()

        result: dict[uuid.UUID, dict] = {eid: {"present": 0, "half_day": 0} for eid in employee_ids}
        for r in records:
            if r.status == AttendanceStatus.present:
                result[r.user_id]["present"] += 1
            elif r.status == AttendanceStatus.half_day:
                result[r.user_id]["half_day"] += 1
        return result

    async def _get_approved_leave_days(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_ids: list[uuid.UUID],
        year: int,
        month: int,
    ) -> dict[uuid.UUID, float]:
        _, days_in_month = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        stmt = select(LeaveRequest).where(
            LeaveRequest.company_id == company_id,
            LeaveRequest.user_id.in_(employee_ids),
            LeaveRequest.status == LeaveStatus.approved,
            LeaveRequest.start_date <= month_end,
            LeaveRequest.end_date >= month_start,
        )
        leaves = (await db.execute(stmt)).scalars().all()

        result: dict[uuid.UUID, float] = {eid: 0.0 for eid in employee_ids}
        for leave in leaves:
            # Clip to month boundaries
            start = max(leave.start_date, month_start)
            end = min(leave.end_date, month_end)
            days = (end - start).days + 1
            result[leave.user_id] += float(leave.total_days if hasattr(leave, "total_days") else days)
        return result

    def _to_structure_item(self, s: SalaryStructure, user: User | None) -> SalaryStructureItem:
        return SalaryStructureItem(
            id=s.id,
            employee_id=s.employee_id,
            employee_name=user.name if user else "",
            employee_emp_id=user.emp_id if user else "",
            effective_from=s.effective_from,
            ctc_monthly=float(s.ctc_monthly),
            basic=float(s.basic),
            hra=float(s.hra),
            special_allowance=float(s.special_allowance),
            pf_employer=float(s.pf_employer),
            pf_employee=float(s.pf_employee),
            esi_employer=float(s.esi_employer) if s.esi_employer else None,
            esi_employee=float(s.esi_employee) if s.esi_employee else None,
            professional_tax=float(s.professional_tax),
            created_at=s.created_at,
        )

    def _to_payslip_item(self, p: Payslip, user: User | None) -> PayslipItem:
        return PayslipItem(
            id=p.id,
            employee_id=p.employee_id,
            employee_name=user.name if user else "",
            employee_emp_id=user.emp_id if user else "",
            month=p.month,
            year=p.year,
            working_days=p.working_days,
            present_days=float(p.present_days),
            leave_days=float(p.leave_days),
            lop_days=float(p.lop_days),
            gross_salary=float(p.gross_salary),
            basic=float(p.basic),
            hra=float(p.hra),
            special_allowance=float(p.special_allowance),
            pf_deduction=float(p.pf_deduction),
            esi_deduction=float(p.esi_deduction) if p.esi_deduction else None,
            pt_deduction=float(p.pt_deduction),
            tds_deduction=float(p.tds_deduction) if p.tds_deduction else None,
            other_deductions=float(p.other_deductions),
            net_salary=float(p.net_salary),
        )


payroll_service = PayrollService()
