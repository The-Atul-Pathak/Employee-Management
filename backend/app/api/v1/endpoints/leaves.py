from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.leave import LeaveStatus
from app.schemas.leave import (
    ApplyLeaveRequest,
    LeaveBalanceResponse,
    LeaveDetailResponse,
    LeaveListResponse,
    MyLeavesResponse,
    ReviewLeaveRequest,
)
from app.services.leave_service import leave_service

router = APIRouter()


@router.post("", response_model=LeaveDetailResponse, status_code=status.HTTP_201_CREATED)
async def apply_leave(
    body: ApplyLeaveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> LeaveDetailResponse:
    try:
        return await leave_service.apply_leave(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/me", response_model=MyLeavesResponse)
async def get_my_leaves(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MyLeavesResponse:
    return await leave_service.get_my_leaves(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
    )


@router.get("/balances", response_model=LeaveBalanceResponse)
async def get_leave_balances(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    user_id: uuid.UUID | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> LeaveBalanceResponse:
    target_user_id = user_id or current_user["user_id"]
    target_year = year or datetime.now(timezone.utc).year
    try:
        await leave_service.ensure_leave_access(
            db=db,
            company_id=current_user["company_id"],
            actor_user_id=current_user["user_id"],
            target_user_id=target_user_id,
        )
        return await leave_service.get_leave_balances(
            db=db,
            company_id=current_user["company_id"],
            user_id=target_user_id,
            year=target_year,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.put("/{leave_id}/cancel", response_model=LeaveDetailResponse)
async def cancel_leave(
    leave_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> LeaveDetailResponse:
    try:
        return await leave_service.cancel_leave(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            leave_id=leave_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=LeaveListResponse)
async def get_all_leaves(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    status_filter: LeaveStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> LeaveListResponse:
    try:
        await leave_service.ensure_leave_manager_access(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
        )
        return await leave_service.get_all_leaves(
            db=db,
            company_id=current_user["company_id"],
            status_filter=status_filter,
            page=page,
            per_page=per_page,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/{leave_id}", response_model=LeaveDetailResponse)
async def get_leave_detail(
    leave_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> LeaveDetailResponse:
    try:
        detail = await leave_service.get_leave_detail(
            db=db,
            company_id=current_user["company_id"],
            leave_id=leave_id,
        )
        await leave_service.ensure_leave_access(
            db=db,
            company_id=current_user["company_id"],
            actor_user_id=current_user["user_id"],
            target_user_id=detail.user.id,
        )
        return detail
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.put("/{leave_id}/review", response_model=LeaveDetailResponse)
async def review_leave(
    leave_id: uuid.UUID,
    body: ReviewLeaveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> LeaveDetailResponse:
    try:
        await leave_service.ensure_leave_manager_access(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
        )
        return await leave_service.review_leave(
            db=db,
            company_id=current_user["company_id"],
            leave_id=leave_id,
            reviewer_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
