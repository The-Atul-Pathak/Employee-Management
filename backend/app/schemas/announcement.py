from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.announcement import AnnouncementTargetType
from app.schemas.user import PaginationMeta


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=255)
    body: str
    target_type: AnnouncementTargetType = AnnouncementTargetType.all
    target_ids: Optional[list[uuid.UUID]] = None
    is_pinned: bool = False
    expires_at: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    body: Optional[str] = None
    target_type: Optional[AnnouncementTargetType] = None
    target_ids: Optional[list[uuid.UUID]] = None
    is_pinned: Optional[bool] = None
    expires_at: Optional[datetime] = None


class AnnouncementAuthorInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class AnnouncementItem(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    author: Optional[AnnouncementAuthorInfo]
    target_type: AnnouncementTargetType
    target_ids: Optional[list[uuid.UUID]]
    is_pinned: bool
    expires_at: Optional[datetime]
    is_read: bool
    created_at: datetime
    updated_at: datetime


class AnnouncementListResponse(BaseModel):
    data: list[AnnouncementItem]
    meta: PaginationMeta


class UnreadAnnouncementCount(BaseModel):
    count: int
