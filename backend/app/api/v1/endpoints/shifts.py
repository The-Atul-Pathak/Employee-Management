from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.shift import (
    AssignShiftRequest,
    EmployeeShiftItem,
    EmployeeShiftListResponse,
    ShiftCreate,
    ShiftItem,
    ShiftListResponse,
    ShiftUpdate,
)
from app.services.shift_service import shift_service

router = APIRouter()


@router.get("", response_model=ShiftListResponse)
async def list_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ShiftListResponse:
    return await shift_service.list_shifts(
        db=db,
        company_id=current_user["company_id"],
    )


@router.post("", response_model=ShiftItem, status_code=status.HTTP_201_CREATED)
async def create_shift(
    body: ShiftCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ShiftItem:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await shift_service.create_shift(
        db=db,
        company_id=current_user["company_id"],
        data=body,
    )


@router.put("/{shift_id}", response_model=ShiftItem)
async def update_shift(
    shift_id: uuid.UUID,
    body: ShiftUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ShiftItem:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await shift_service.update_shift(
            db=db,
            company_id=current_user["company_id"],
            shift_id=shift_id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await shift_service.delete_shift(
            db=db,
            company_id=current_user["company_id"],
            shift_id=shift_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/assignments", response_model=EmployeeShiftListResponse)
async def list_employee_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> EmployeeShiftListResponse:
    return await shift_service.list_employee_shifts(
        db=db,
        company_id=current_user["company_id"],
        page=page,
        per_page=per_page,
    )


@router.post("/assignments", response_model=EmployeeShiftItem, status_code=status.HTTP_201_CREATED)
async def assign_shift(
    body: AssignShiftRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> EmployeeShiftItem:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await shift_service.assign_shift(
            db=db,
            company_id=current_user["company_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
