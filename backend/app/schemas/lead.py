from __future__ import annotations
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.crm import LeadStatus
from app.schemas.user import PaginationMeta


class LeadCreateRequest(BaseModel):
    client_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    assigned_to: uuid.UUID | None = None
    next_follow_up_date: date | None = None


class LeadUpdateRequest(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, max_length=100)
    status: LeadStatus | None = None
    assigned_to: uuid.UUID | None = None
    next_follow_up_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_name: str
    contact_email: EmailStr | None
    contact_phone: str | None
    status: LeadStatus
    source: str | None
    notes: str | None
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None
    created_by: uuid.UUID
    next_follow_up_date: date | None
    last_interaction_at: datetime | None
    project_created: bool
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    data: list[LeadListItem]
    meta: PaginationMeta


class TodaysFollowupsResponse(BaseModel):
    data: list[LeadListItem]
    total: int


class LeadInteractionCreateRequest(BaseModel):
    interaction_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    interaction_at: datetime | None = None


class LeadInteractionResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    interaction_type: str
    description: str
    logged_by: uuid.UUID
    logged_by_name: str | None
    interaction_at: datetime
    created_at: datetime
