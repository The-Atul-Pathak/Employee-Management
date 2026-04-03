from __future__ import annotations
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.attendance import (
    AttendanceListResponse,
    AttendanceSummaryResponse,
    BulkMarkRequest,
    EmployeeAttendanceRecord,
    EmployeeAttendanceSummary,
    MarkAttendanceRequest,
)
from app.services.attendance_service import attendance_service

router = APIRouter()


async def _require_attendance_manager(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    allowed = await attendance_service.can_manage_attendance(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        is_company_admin=current_user["is_company_admin"],
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR access required",
        )
    return current_user


@router.get("", response_model=AttendanceListResponse)
async def get_daily_attendance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    target_date: date = Query(..., alias="date"),
    scope: str = Query(default="all"),
) -> AttendanceListResponse:
    return await attendance_service.get_daily_attendance_scoped(
        db=db,
        company_id=current_user["company_id"],
        target_date=target_date,
        scope=scope,
        manager_id=current_user["user_id"] if scope == "team" else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def mark_attendance(
    body: MarkAttendanceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(_require_attendance_manager)],
) -> dict:
    try:
        await attendance_service.mark_attendance(
            db=db,
            company_id=current_user["company_id"],
            data=body,
            marked_by_user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Attendance marked successfully"}


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_mark_attendance(
    body: BulkMarkRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(_require_attendance_manager)],
) -> dict:
    try:
        for entry in body.entries:
            await attendance_service.mark_attendance(
                db=db,
                company_id=current_user["company_id"],
                data=MarkAttendanceRequest(
                    user_id=entry.user_id,
                    date=body.date,
                    status=entry.status,
                    notes=body.notes,
                ),
                marked_by_user_id=current_user["user_id"],
            )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Bulk attendance marked successfully", "count": len(body.entries)}


@router.get("/summary", response_model=AttendanceSummaryResponse)
async def get_daily_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    target_date: date = Query(..., alias="date"),
    scope: str = Query(default="all"),
) -> AttendanceSummaryResponse:
    return await attendance_service.get_daily_summary_scoped(
        db=db,
        company_id=current_user["company_id"],
        target_date=target_date,
        scope=scope,
        manager_id=current_user["user_id"] if scope == "team" else None,
    )


@router.get("/user/{user_id}/summary", response_model=EmployeeAttendanceSummary)
async def get_employee_monthly_summary(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> EmployeeAttendanceSummary:
    try:
        return await attendance_service.get_employee_monthly_summary(
            db=db,
            company_id=current_user["company_id"],
            user_id=user_id,
            month=month,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/user/{user_id}/records", response_model=list[EmployeeAttendanceRecord])
async def get_employee_monthly_records(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> list[EmployeeAttendanceRecord]:
    try:
        return await attendance_service.get_employee_monthly_records(
            db=db,
            company_id=current_user["company_id"],
            user_id=user_id,
            month=month,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/check-in")
async def self_check_in(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await attendance_service.self_check_in(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Checked in successfully"}


@router.post("/check-out")
async def self_check_out(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await attendance_service.self_check_out(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Checked out successfully"}
