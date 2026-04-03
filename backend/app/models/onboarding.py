from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModel


class AssigneeType(str, enum.Enum):
    hr = "hr"
    it = "it"
    manager = "manager"
    employee = "employee"


class OnboardingStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"


class TaskCompletionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class OnboardingTemplate(BaseModel):
    __tablename__ = "onboarding_templates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OnboardingTemplateTask(Base):
    __tablename__ = "onboarding_template_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_type: Mapped[AssigneeType] = mapped_column(
        PgEnum(AssigneeType, name="assignee_type", create_type=True),
        nullable=False,
        default=AssigneeType.hr,
    )
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OnboardingInstance(BaseModel):
    __tablename__ = "onboarding_instances"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_complete_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[OnboardingStatus] = mapped_column(
        PgEnum(OnboardingStatus, name="onboarding_status", create_type=True),
        nullable=False,
        default=OnboardingStatus.in_progress,
    )


class OnboardingTaskCompletion(Base):
    __tablename__ = "onboarding_task_completions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_template_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[TaskCompletionStatus] = mapped_column(
        PgEnum(TaskCompletionStatus, name="task_completion_status", create_type=True),
        nullable=False,
        default=TaskCompletionStatus.pending,
    )
    completed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
