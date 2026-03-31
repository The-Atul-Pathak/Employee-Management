from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.notification import NotificationListResponse, UnreadCountResponse
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> NotificationListResponse:
    return await notification_service.get_user_notifications(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UnreadCountResponse:
    return await notification_service.get_unread_count(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
    )


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_as_read(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    try:
        await notification_service.mark_as_read(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            notification_id=notification_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_as_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    await notification_service.mark_all_as_read(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
    )
