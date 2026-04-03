from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementItem,
    AnnouncementListResponse,
    AnnouncementUpdate,
    UnreadAnnouncementCount,
)
from app.services.announcement_service import announcement_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> AnnouncementListResponse:
    return await announcement_service.list_announcements(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
    )


@router.get("/unread-count", response_model=UnreadAnnouncementCount)
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UnreadAnnouncementCount:
    return await announcement_service.get_unread_count(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
    )


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    await announcement_service.mark_all_read(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
    )


@router.get("/{announcement_id}", response_model=AnnouncementItem)
async def get_announcement(
    announcement_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AnnouncementItem:
    try:
        return await announcement_service.get_announcement(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            announcement_id=announcement_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("", response_model=AnnouncementItem, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    body: AnnouncementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AnnouncementItem:
    if not current_user.get("is_admin") and current_user.get("role", "").lower() not in HR_ROLE_NAMES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await announcement_service.create_announcement(
        db=db,
        company_id=current_user["company_id"],
        author_id=current_user["user_id"],
        data=body,
    )


@router.put("/{announcement_id}", response_model=AnnouncementItem)
async def update_announcement(
    announcement_id: uuid.UUID,
    body: AnnouncementUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AnnouncementItem:
    if not current_user.get("is_admin") and current_user.get("role", "").lower() not in HR_ROLE_NAMES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await announcement_service.update_announcement(
            db=db,
            company_id=current_user["company_id"],
            announcement_id=announcement_id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not current_user.get("is_admin") and current_user.get("role", "").lower() not in HR_ROLE_NAMES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await announcement_service.delete_announcement(
            db=db,
            company_id=current_user["company_id"],
            announcement_id=announcement_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
