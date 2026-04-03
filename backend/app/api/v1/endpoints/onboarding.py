from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.onboarding import (
    InstanceCreate,
    InstanceDetail,
    InstanceItem,
    InstanceListResponse,
    TaskCompletionUpdate,
    TemplateCreate,
    TemplateDetail,
    TemplateItem,
    TemplateListResponse,
    TemplateUpdate,
)
from app.services.onboarding_service import onboarding_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


# ── Templates ──────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TemplateListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await onboarding_service.list_templates(
        db=db, company_id=current_user["company_id"]
    )


@router.post("/templates", response_model=TemplateDetail, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TemplateDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await onboarding_service.create_template(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def get_template_detail(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TemplateDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await onboarding_service.get_template_detail(
            db=db, company_id=current_user["company_id"], template_id=template_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/templates/{template_id}", response_model=TemplateItem)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TemplateItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await onboarding_service.update_template(
            db=db, company_id=current_user["company_id"], template_id=template_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await onboarding_service.delete_template(
            db=db, company_id=current_user["company_id"], template_id=template_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Instances ──────────────────────────────────────────────────────────────────

@router.get("/instances", response_model=InstanceListResponse)
async def list_instances(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> InstanceListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await onboarding_service.list_instances(
        db=db, company_id=current_user["company_id"], page=page, per_page=per_page
    )


@router.post("/instances", response_model=InstanceDetail, status_code=status.HTTP_201_CREATED)
async def create_instance(
    body: InstanceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> InstanceDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await onboarding_service.create_instance(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.get("/instances/{instance_id}", response_model=InstanceDetail)
async def get_instance_detail(
    instance_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> InstanceDetail:
    try:
        return await onboarding_service.get_instance_detail(
            db=db, company_id=current_user["company_id"], instance_id=instance_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/my", response_model=InstanceDetail)
async def get_my_onboarding(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> InstanceDetail:
    from sqlalchemy import select as sa_select
    from app.models.onboarding import OnboardingInstance

    stmt = sa_select(OnboardingInstance).where(
        OnboardingInstance.company_id == current_user["company_id"],
        OnboardingInstance.employee_id == current_user["user_id"],
        OnboardingInstance.deleted_at.is_(None),
    ).order_by(OnboardingInstance.created_at.desc()).limit(1)

    instance = (await db.execute(stmt)).scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No onboarding found")

    return await onboarding_service.get_instance_detail(
        db=db, company_id=current_user["company_id"], instance_id=instance.id
    )


@router.put("/instances/{instance_id}/tasks/{task_id}", response_model=InstanceDetail)
async def complete_task(
    instance_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskCompletionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> InstanceDetail:
    try:
        return await onboarding_service.complete_task(
            db=db,
            company_id=current_user["company_id"],
            instance_id=instance_id,
            task_id=task_id,
            completed_by=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
