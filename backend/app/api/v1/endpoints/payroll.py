from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.payroll import PayrollRunStatus
from app.schemas.payroll import (
    MyPayslipsResponse,
    PayrollRunDetail,
    PayrollRunItem,
    PayrollRunListResponse,
    PayrollRunRequest,
    SalaryStructureCreate,
    SalaryStructureItem,
    SalaryStructureListResponse,
)
from app.services.payroll_service import payroll_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


# ── Salary Structures ──────────────────────────────────────────────────────────

@router.get("/salary-structures", response_model=SalaryStructureListResponse)
async def list_salary_structures(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> SalaryStructureListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await payroll_service.list_salary_structures(
        db=db, company_id=current_user["company_id"], page=page, per_page=per_page
    )


@router.post("/salary-structures", response_model=SalaryStructureItem, status_code=status.HTTP_201_CREATED)
async def create_salary_structure(
    body: SalaryStructureCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SalaryStructureItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await payroll_service.create_salary_structure(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.get("/salary-structures/{employee_id}", response_model=Optional[SalaryStructureItem])
async def get_employee_salary_structure(
    employee_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Optional[SalaryStructureItem]:
    if not _is_hr(current_user) and current_user["user_id"] != employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await payroll_service.get_employee_salary_structure(
        db=db, company_id=current_user["company_id"], employee_id=employee_id
    )


# ── Payroll Runs ───────────────────────────────────────────────────────────────

@router.post("/run", response_model=PayrollRunDetail, status_code=status.HTTP_201_CREATED)
async def run_payroll(
    body: PayrollRunRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> PayrollRunDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await payroll_service.run_payroll(
            db=db,
            company_id=current_user["company_id"],
            run_by=current_user["user_id"],
            data=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/runs", response_model=PayrollRunListResponse)
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PayrollRunListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await payroll_service.list_runs(
        db=db, company_id=current_user["company_id"], page=page, per_page=per_page
    )


@router.get("/runs/{run_id}", response_model=PayrollRunDetail)
async def get_run_detail(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> PayrollRunDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await payroll_service.get_run_detail(
            db=db, company_id=current_user["company_id"], run_id=run_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/runs/{run_id}/approve", response_model=PayrollRunItem)
async def approve_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> PayrollRunItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await payroll_service.update_run_status(
            db=db,
            company_id=current_user["company_id"],
            run_id=run_id,
            new_status=PayrollRunStatus.approved,
            approved_by=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/runs/{run_id}/mark-paid", response_model=PayrollRunItem)
async def mark_paid(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> PayrollRunItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await payroll_service.update_run_status(
            db=db,
            company_id=current_user["company_id"],
            run_id=run_id,
            new_status=PayrollRunStatus.paid,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Payslips ───────────────────────────────────────────────────────────────────

@router.get("/payslips/my", response_model=MyPayslipsResponse)
async def get_my_payslips(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=12, ge=1, le=24),
) -> MyPayslipsResponse:
    return await payroll_service.get_my_payslips(
        db=db,
        company_id=current_user["company_id"],
        employee_id=current_user["user_id"],
        page=page,
        per_page=per_page,
    )
