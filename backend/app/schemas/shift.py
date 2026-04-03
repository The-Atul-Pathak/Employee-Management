from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import PaginationMeta


class ShiftCreate(BaseModel):
    name: str = Field(..., max_length=100)
    start_time: time
    end_time: time
    grace_minutes: int = Field(default=15, ge=0, le=120)
    is_default: bool = False


class ShiftUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    grace_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    is_default: Optional[bool] = None


class ShiftItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    grace_minutes: int
    is_default: bool
    created_at: datetime


class ShiftListResponse(BaseModel):
    data: list[ShiftItem]


class AssignShiftRequest(BaseModel):
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    effective_from: str  # ISO date string YYYY-MM-DD
    effective_to: Optional[str] = None


class EmployeeShiftItem(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_emp_id: str
    shift_id: uuid.UUID
    shift_name: str
    effective_from: str
    effective_to: Optional[str]


class EmployeeShiftListResponse(BaseModel):
    data: list[EmployeeShiftItem]
    meta: PaginationMeta
