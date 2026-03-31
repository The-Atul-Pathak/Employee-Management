from __future__ import annotations
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModel


class ProjectStatus(str, enum.Enum):
    unassigned = "unassigned"
    assigned = "assigned"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    on_hold = "on_hold"


class TaskStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    active = "active"
    in_progress = "in_progress"
    review = "review"
    done = "done"
    rejected = "rejected"
    blocked = "blocked"


class Project(BaseModel):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_company_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        PgEnum(ProjectStatus, name="project_status", create_type=True),
        nullable=False,
        default=ProjectStatus.unassigned,
    )

    planning: Mapped[Optional["ProjectPlanning"]] = relationship(
        "ProjectPlanning", back_populates="project", uselist=False, lazy="select"
    )
    tasks: Mapped[list["ProjectTask"]] = relationship(
        "ProjectTask", back_populates="project", lazy="select"
    )
    status_logs: Mapped[list["ProjectStatusLog"]] = relationship(
        "ProjectStatusLog", back_populates="project", lazy="select"
    )


class ProjectPlanning(BaseModel):
    __tablename__ = "project_planning"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_planning_project_id"),
        Index("ix_project_planning_company_id", "company_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planned_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    milestones: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    deliverables: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    estimated_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    client_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assumptions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="planning")


class ProjectTask(BaseModel):
    __tablename__ = "project_tasks"
    __table_args__ = (
        Index("ix_project_tasks_company_assigned_status", "company_id", "assigned_to", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        PgEnum(TaskStatus, name="task_status", create_type=True),
        nullable=False,
        default=TaskStatus.active,
    )
    dependency_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")


class TaskUpdate(Base):
    __tablename__ = "task_updates"
    __table_args__ = (
        Index("ix_task_updates_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    update_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    old_status: Mapped[Optional[TaskStatus]] = mapped_column(
        PgEnum(TaskStatus, name="task_status", create_type=False),
        nullable=True,
    )
    new_status: Mapped[Optional[TaskStatus]] = mapped_column(
        PgEnum(TaskStatus, name="task_status", create_type=False),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProjectStatusLog(Base):
    __tablename__ = "project_status_logs"
    __table_args__ = (
        Index("ix_project_status_logs_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[Optional[ProjectStatus]] = mapped_column(
        PgEnum(ProjectStatus, name="project_status", create_type=False),
        nullable=True,
    )
    new_status: Mapped[ProjectStatus] = mapped_column(
        PgEnum(ProjectStatus, name="project_status", create_type=False),
        nullable=False,
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="status_logs")
