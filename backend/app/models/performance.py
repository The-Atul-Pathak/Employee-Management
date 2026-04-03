from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModel


class ReviewCycleType(str, enum.Enum):
    quarterly = "quarterly"
    half_yearly = "half_yearly"
    annual = "annual"
    custom = "custom"


class ReviewCycleStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"
    published = "published"


class PerformanceReviewStatus(str, enum.Enum):
    pending = "pending"
    self_assessment_done = "self_assessment_done"
    in_review = "in_review"
    submitted = "submitted"
    published = "published"


class ReviewCycle(BaseModel):
    __tablename__ = "review_cycles"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cycle_type: Mapped[ReviewCycleType] = mapped_column(
        PgEnum(ReviewCycleType, name="review_cycle_type", create_type=True),
        nullable=False,
    )
    review_from: Mapped[date] = mapped_column(Date, nullable=False)
    review_to: Mapped[date] = mapped_column(Date, nullable=False)
    submission_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReviewCycleStatus] = mapped_column(
        PgEnum(ReviewCycleStatus, name="review_cycle_status", create_type=True),
        nullable=False,
        default=ReviewCycleStatus.draft,
    )


class ReviewCriteria(Base):
    __tablename__ = "review_criteria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PerformanceReview(BaseModel):
    __tablename__ = "performance_reviews"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[PerformanceReviewStatus] = mapped_column(
        PgEnum(PerformanceReviewStatus, name="performance_review_status", create_type=True),
        nullable=False,
        default=PerformanceReviewStatus.pending,
    )
    overall_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    reviewer_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewScore(Base):
    __tablename__ = "review_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("performance_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criteria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_criteria.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    self_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewer_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewer_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
