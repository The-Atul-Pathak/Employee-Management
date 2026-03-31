from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.leave import LeaveStatus, LeaveType
from app.schemas.user import PaginationMeta


class ApplyLeaveRequest(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)


class ReviewLeaveRequest(BaseModel):
    status: LeaveStatus
    review_notes: str | None = Field(default=None, max_length=2000)


class LeaveUserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    emp_id: str
    name: str
    email: str | None


class LeaveListItem(BaseModel):
    id: uuid.UUID
    user: LeaveUserInfo
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    status: LeaveStatus
    applied_at: datetime


class LeaveListResponse(BaseModel):
    data: list[LeaveListItem]
    meta: PaginationMeta


class LeaveDetailResponse(BaseModel):
    id: uuid.UUID
    user: LeaveUserInfo
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    reason: str | None
    status: LeaveStatus
    applied_at: datetime
    reviewed_at: datetime | None
    review_notes: str | None
    reviewer: LeaveUserInfo | None
    created_at: datetime


class LeaveBalanceItem(BaseModel):
    leave_type: LeaveType
    total_quota: float
    used: float
    remaining: float


class LeaveBalanceResponse(BaseModel):
    data: list[LeaveBalanceItem]


class MyLeaveItem(BaseModel):
    id: uuid.UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    reason: str | None
    status: LeaveStatus
    applied_at: datetime
    reviewed_at: datetime | None
    review_notes: str | None


class MyLeavesResponse(BaseModel):
    data: list[MyLeaveItem]
