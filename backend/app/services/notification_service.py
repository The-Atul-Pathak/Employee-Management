from __future__ import annotations

import math
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.schemas.notification import NotificationItem, NotificationListResponse, UnreadCountResponse
from app.schemas.user import PaginationMeta


class NotificationService:
    async def create_notification(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: NotificationType,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
    ) -> None:
        notification = Notification(
            company_id=company_id,
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(notification)
        await db.flush()

    async def get_user_notifications(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> NotificationListResponse:
        filters = [
            Notification.company_id == company_id,
            Notification.user_id == user_id,
        ]

        total_stmt = select(func.count()).select_from(Notification).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        notifications = (await db.execute(stmt)).scalars().all()

        return NotificationListResponse(
            data=[self._to_item(n) for n in notifications],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_unread_count(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UnreadCountResponse:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.company_id == company_id,
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        count = (await db.execute(stmt)).scalar_one()
        return UnreadCountResponse(count=count)

    async def mark_as_read(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.company_id == company_id,
            Notification.user_id == user_id,
        )
        notification = (await db.execute(stmt)).scalar_one_or_none()
        if notification is None:
            raise LookupError("Notification not found")
        notification.is_read = True
        await db.flush()

    async def mark_all_as_read(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        stmt = select(Notification).where(
            Notification.company_id == company_id,
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        notifications = (await db.execute(stmt)).scalars().all()
        for n in notifications:
            n.is_read = True
        await db.flush()

    def _to_item(self, n: Notification) -> NotificationItem:
        return NotificationItem(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            entity_type=n.entity_type,
            entity_id=n.entity_id,
            created_at=n.created_at,
        )


notification_service = NotificationService()
