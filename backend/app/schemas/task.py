from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.project import TaskStatus
from app.schemas.user import PaginationMeta


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    priority: str | None = Field(default=None, max_length=50)
    dependency_task_id: uuid.UUID | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    priority: str | None = Field(default=None, max_length=50)
    dependency_task_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=5000)


class TaskApproveRequest(BaseModel):
    approve: bool


class TaskStatusUpdateRequest(BaseModel):
    new_status: TaskStatus
    note: str | None = Field(default=None, max_length=5000)


class TaskListItem(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    title: str
    description: str | None
    assigned_to: uuid.UUID | None
    assignee_name: str | None
    created_by: uuid.UUID | None
    creator_name: str | None
    start_date: date | None
    due_date: date | None
    estimated_hours: Decimal | None
    priority: str | None
    status: TaskStatus
    dependency_task_id: uuid.UUID | None
    latest_note: str | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    data: list[TaskListItem]
    meta: PaginationMeta
