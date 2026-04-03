from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.performance import (
    CycleCreate,
    CycleDetail,
    CycleItem,
    CycleListResponse,
    CycleUpdate,
    ReviewCreate,
    ReviewDetail,
    ReviewItem,
    ReviewListResponse,
    ReviewSubmit,
    SelfAssessmentSubmit,
)
from app.services.performance_service import performance_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


# ── Cycles ─────────────────────────────────────────────────────────────────────

@router.get("/cycles", response_model=CycleListResponse)
async def list_cycles(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CycleListResponse:
    return await performance_service.list_cycles(
        db=db, company_id=current_user["company_id"]
    )


@router.post("/cycles", response_model=CycleDetail, status_code=status.HTTP_201_CREATED)
async def create_cycle(
    body: CycleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CycleDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await performance_service.create_cycle(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.get("/cycles/{cycle_id}", response_model=CycleDetail)
async def get_cycle_detail(
    cycle_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CycleDetail:
    try:
        return await performance_service.get_cycle_detail(
            db=db, company_id=current_user["company_id"], cycle_id=cycle_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/cycles/{cycle_id}", response_model=CycleItem)
async def update_cycle(
    cycle_id: uuid.UUID,
    body: CycleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CycleItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await performance_service.update_cycle(
            db=db, company_id=current_user["company_id"], cycle_id=cycle_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Reviews ────────────────────────────────────────────────────────────────────

@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    cycle_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> ReviewListResponse:
    # HR sees all; employees see their own
    employee_id = None if _is_hr(current_user) else current_user["user_id"]
    return await performance_service.list_reviews(
        db=db,
        company_id=current_user["company_id"],
        cycle_id=cycle_id,
        employee_id=employee_id,
        page=page,
        per_page=per_page,
    )


@router.post("/cycles/{cycle_id}/reviews", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
async def create_review(
    cycle_id: uuid.UUID,
    body: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReviewItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await performance_service.create_review(
            db=db, company_id=current_user["company_id"], cycle_id=cycle_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
async def get_review_detail(
    review_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReviewDetail:
    try:
        return await performance_service.get_review_detail(
            db=db, company_id=current_user["company_id"], review_id=review_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/reviews/{review_id}/submit", response_model=ReviewDetail)
async def submit_review(
    review_id: uuid.UUID,
    body: ReviewSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReviewDetail:
    try:
        return await performance_service.submit_review(
            db=db, company_id=current_user["company_id"], review_id=review_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/reviews/{review_id}/self-assessment", response_model=ReviewDetail)
async def submit_self_assessment(
    review_id: uuid.UUID,
    body: SelfAssessmentSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReviewDetail:
    try:
        return await performance_service.submit_self_assessment(
            db=db,
            company_id=current_user["company_id"],
            review_id=review_id,
            employee_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
