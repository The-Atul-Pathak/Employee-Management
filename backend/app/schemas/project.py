from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus, TaskStatus
from app.schemas.user import PaginationMeta


class AssignTeamRequest(BaseModel):
    team_id: uuid.UUID


class PlanningRequest(BaseModel):
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    description: str | None = Field(default=None, max_length=5000)
    scope: str | None = Field(default=None, max_length=5000)
    milestones: list[dict] = Field(default_factory=list)
    deliverables: list[dict] = Field(default_factory=list)
    estimated_budget: Decimal | None = Field(default=None, ge=0)
    priority: str | None = Field(default=None, max_length=50)
    client_requirements: str | None = Field(default=None, max_length=5000)
    risk_notes: str | None = Field(default=None, max_length=5000)
    assumptions: str | None = Field(default=None, max_length=5000)
    dependencies: str | None = Field(default=None, max_length=5000)
    internal_notes: str | None = Field(default=None, max_length=5000)


class ProjectListItem(BaseModel):
    id: uuid.UUID
    project_name: str
    lead_id: uuid.UUID | None
    lead_client_name: str | None
    team_id: uuid.UUID | None
    team_name: str | None
    leader_id: uuid.UUID | None
    leader_name: str | None
    status: ProjectStatus


class ProjectListResponse(BaseModel):
    data: list[ProjectListItem]
    meta: PaginationMeta


class PlanningResponse(BaseModel):
    id: uuid.UUID
    planned_start_date: date | None
    planned_end_date: date | None
    description: str | None
    scope: str | None
    milestones: list[dict]
    deliverables: list[dict]
    estimated_budget: Decimal | None
    priority: str | None
    client_requirements: str | None
    risk_notes: str | None
    assumptions: str | None
    dependencies: str | None
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime


class ProjectTaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None
    status: TaskStatus
    due_date: date | None


class ProjectStatusLogResponse(BaseModel):
    id: uuid.UUID
    old_status: ProjectStatus | None
    new_status: ProjectStatus
    changed_by: uuid.UUID | None
    changed_by_name: str | None
    reason: str | None
    created_at: datetime


class ProjectDetailResponse(BaseModel):
    id: uuid.UUID
    project_name: str
    lead_id: uuid.UUID | None
    lead_client_name: str | None
    lead_contact_email: str | None
    lead_contact_phone: str | None
    team_id: uuid.UUID | None
    team_name: str | None
    leader_id: uuid.UUID | None
    leader_name: str | None
    status: ProjectStatus
    is_leader: bool
    is_admin: bool
    planning: PlanningResponse | None
    tasks: list[ProjectTaskSummary]
    status_logs: list[ProjectStatusLogResponse]
    created_at: datetime
    updated_at: datetime


class ProjectActionResponse(BaseModel):
    id: uuid.UUID
    status: ProjectStatus
    message: str
