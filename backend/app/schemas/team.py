from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus
from app.models.team import TeamStatus
from app.schemas.user import PaginationMeta


class TeamUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    manager_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = Field(default_factory=list)


class TeamMemberResponse(BaseModel):
    user_id: uuid.UUID
    emp_id: str
    name: str
    email: str | None
    status: str
    added_at: datetime | None = None


class TeamListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    manager_id: uuid.UUID | None
    manager_name: str | None
    member_count: int
    status: TeamStatus


class TeamListResponse(BaseModel):
    data: list[TeamListItem]
    meta: PaginationMeta


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    manager_id: uuid.UUID | None
    manager_name: str | None
    status: TeamStatus
    members: list[TeamMemberResponse]


class TeamProjectResponse(BaseModel):
    id: uuid.UUID
    project_name: str
    status: ProjectStatus


class TeamDetailsResponse(TeamResponse):
    projects: list[TeamProjectResponse]


class UnassignedProjectItem(BaseModel):
    id: uuid.UUID
    project_name: str
    status: ProjectStatus


class UnassignedProjectsResponse(BaseModel):
    data: list[UnassignedProjectItem]
    total: int


class AssignTeamRequest(BaseModel):
    team_id: uuid.UUID
