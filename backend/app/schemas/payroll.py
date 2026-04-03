from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.payroll import PayrollRunStatus
from app.schemas.user import PaginationMeta


class SalaryStructureCreate(BaseModel):
    employee_id: uuid.UUID
    effective_from: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    ctc_monthly: float = Field(..., gt=0)
    basic: float = Field(..., ge=0)
    hra: float = Field(default=0, ge=0)
    special_allowance: float = Field(default=0, ge=0)
    pf_employer: float = Field(default=0, ge=0)
    pf_employee: float = Field(default=0, ge=0)
    esi_employer: Optional[float] = None
    esi_employee: Optional[float] = None
    professional_tax: float = Field(default=0, ge=0)


class SalaryStructureItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_emp_id: str
    effective_from: str
    ctc_monthly: float
    basic: float
    hra: float
    special_allowance: float
    pf_employer: float
    pf_employee: float
    esi_employer: Optional[float]
    esi_employee: Optional[float]
    professional_tax: float
    created_at: datetime


class SalaryStructureListResponse(BaseModel):
    data: list[SalaryStructureItem]
    meta: PaginationMeta


class PayrollRunRequest(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)


class PayslipItem(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_emp_id: str
    month: int
    year: int
    working_days: int
    present_days: float
    leave_days: float
    lop_days: float
    gross_salary: float
    basic: float
    hra: float
    special_allowance: float
    pf_deduction: float
    esi_deduction: Optional[float]
    pt_deduction: float
    tds_deduction: Optional[float]
    other_deductions: float
    net_salary: float


class PayrollRunItem(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    month: int
    year: int
    status: PayrollRunStatus
    total_gross: float
    total_deductions: float
    total_net: float
    run_by: Optional[uuid.UUID]
    approved_by: Optional[uuid.UUID]
    run_at: datetime
    paid_at: Optional[datetime]
    payslip_count: int = 0


class PayrollRunDetail(PayrollRunItem):
    payslips: list[PayslipItem]


class PayrollRunListResponse(BaseModel):
    data: list[PayrollRunItem]
    meta: PaginationMeta


class MyPayslipItem(BaseModel):
    id: uuid.UUID
    month: int
    year: int
    working_days: int
    present_days: float
    leave_days: float
    lop_days: float
    gross_salary: float
    basic: float
    hra: float
    special_allowance: float
    pf_deduction: float
    esi_deduction: Optional[float]
    pt_deduction: float
    other_deductions: float
    net_salary: float


class MyPayslipsResponse(BaseModel):
    data: list[MyPayslipItem]
    meta: PaginationMeta
