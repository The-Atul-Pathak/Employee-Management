from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModel


class PayrollRunStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    paid = "paid"


class SalaryStructure(BaseModel):
    __tablename__ = "salary_structures"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", "effective_from",
            name="uq_salary_structures_company_employee_from",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    ctc_monthly: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    basic: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    special_allowance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    pf_employer: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    pf_employee: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    esi_employer: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    esi_employee: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    professional_tax: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "month", "year", name="uq_payroll_runs_company_month_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayrollRunStatus] = mapped_column(
        PgEnum(PayrollRunStatus, name="payroll_run_status", create_type=True),
        nullable=False,
        default=PayrollRunStatus.draft,
    )
    total_gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_net: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    run_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payslips_run_employee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    present_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    leave_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    lop_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    gross_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    basic: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    special_allowance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pf_deduction: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    esi_deduction: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    pt_deduction: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tds_deduction: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    other_deductions: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
