from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.performance import (
    PerformanceReviewStatus,
    ReviewCycleStatus,
    ReviewCycleType,
)
from app.schemas.user import PaginationMeta


# ── Cycles ─────────────────────────────────────────────────────────────────────

class CriteriaCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    max_score: int = Field(default=5, ge=1, le=10)
    order_index: int = Field(default=0, ge=0)


class CycleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    cycle_type: ReviewCycleType
    review_from: date
    review_to: date
    submission_deadline: date
    criteria: list[CriteriaCreate] = []


class CycleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    status: Optional[ReviewCycleStatus] = None
    submission_deadline: Optional[date] = None


class CriteriaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    max_score: int
    order_index: int


class CycleItem(BaseModel):
    id: uuid.UUID
    name: str
    cycle_type: ReviewCycleType
    review_from: date
    review_to: date
    submission_deadline: date
    status: ReviewCycleStatus
    review_count: int = 0
    created_at: datetime


class CycleDetail(CycleItem):
    criteria: list[CriteriaItem]


class CycleListResponse(BaseModel):
    data: list[CycleItem]


# ── Reviews ────────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    employee_id: uuid.UUID
    reviewer_id: uuid.UUID


class ScoreSubmit(BaseModel):
    criteria_id: uuid.UUID
    self_score: Optional[int] = Field(default=None, ge=1, le=10)
    reviewer_score: Optional[int] = Field(default=None, ge=1, le=10)
    reviewer_comment: Optional[str] = None


class ReviewSubmit(BaseModel):
    reviewer_comments: Optional[str] = None
    overall_score: Optional[float] = Field(default=None, ge=0, le=5)
    scores: list[ScoreSubmit] = []


class SelfAssessmentSubmit(BaseModel):
    scores: list[ScoreSubmit] = []


class ReviewUserInfo(BaseModel):
    id: uuid.UUID
    name: str
    emp_id: str


class ReviewScoreItem(BaseModel):
    criteria_id: uuid.UUID
    criteria_name: str
    max_score: int
    self_score: Optional[int]
    reviewer_score: Optional[int]
    reviewer_comment: Optional[str]


class ReviewItem(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    cycle_name: str
    employee: ReviewUserInfo
    reviewer: ReviewUserInfo
    status: PerformanceReviewStatus
    overall_score: Optional[float]
    submitted_at: Optional[datetime]
    published_at: Optional[datetime]
    created_at: datetime


class ReviewDetail(ReviewItem):
    reviewer_comments: Optional[str]
    employee_response: Optional[str]
    scores: list[ReviewScoreItem]


class ReviewListResponse(BaseModel):
    data: list[ReviewItem]
    meta: PaginationMeta
