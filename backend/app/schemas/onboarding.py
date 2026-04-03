from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.onboarding import AssigneeType, OnboardingStatus, TaskCompletionStatus
from app.schemas.user import PaginationMeta


# ── Templates ──────────────────────────────────────────────────────────────────

class TemplateTaskCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    assignee_type: AssigneeType = AssigneeType.hr
    day_offset: int = Field(default=0, ge=0)
    order_index: int = Field(default=0, ge=0)
    is_required: bool = True


class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_default: bool = False
    tasks: list[TemplateTaskCreate] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None


class TemplateTaskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    assignee_type: AssigneeType
    day_offset: int
    order_index: int
    is_required: bool


class TemplateItem(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    is_default: bool
    task_count: int
    created_at: datetime


class TemplateDetail(TemplateItem):
    tasks: list[TemplateTaskItem]


class TemplateListResponse(BaseModel):
    data: list[TemplateItem]


# ── Instances ──────────────────────────────────────────────────────────────────

class InstanceCreate(BaseModel):
    employee_id: uuid.UUID
    template_id: Optional[uuid.UUID] = None
    start_date: date
    target_complete_date: Optional[date] = None


class TaskCompletionUpdate(BaseModel):
    status: TaskCompletionStatus
    notes: Optional[str] = None


class TaskCompletionItem(BaseModel):
    id: uuid.UUID
    template_task_id: uuid.UUID
    task_title: str
    task_description: Optional[str]
    assignee_type: AssigneeType
    day_offset: int
    is_required: bool
    status: TaskCompletionStatus
    completed_by: Optional[uuid.UUID]
    completed_at: Optional[datetime]
    notes: Optional[str]


class OnboardingUserInfo(BaseModel):
    id: uuid.UUID
    name: str
    emp_id: str


class InstanceItem(BaseModel):
    id: uuid.UUID
    employee: OnboardingUserInfo
    template_id: Optional[uuid.UUID]
    template_name: Optional[str]
    start_date: date
    target_complete_date: Optional[date]
    status: OnboardingStatus
    completed_tasks: int
    total_tasks: int
    created_at: datetime


class InstanceDetail(InstanceItem):
    tasks: list[TaskCompletionItem]


class InstanceListResponse(BaseModel):
    data: list[InstanceItem]
    meta: PaginationMeta
