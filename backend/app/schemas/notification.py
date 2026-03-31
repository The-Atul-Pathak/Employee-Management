from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.notification import NotificationType
from app.schemas.user import PaginationMeta


class NotificationItem(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    type: NotificationType
    is_read: bool
    entity_type: str | None
    entity_id: uuid.UUID | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    data: list[NotificationItem]
    meta: PaginationMeta


class UnreadCountResponse(BaseModel):
    count: int
