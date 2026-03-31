from __future__ import annotations
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceStatus


class MarkAttendanceRequest(BaseModel):
    user_id: uuid.UUID
    date: date
    status: AttendanceStatus
    notes: str | None = Field(default=None, max_length=1000)


class BulkAttendanceEntry(BaseModel):
    user_id: uuid.UUID
    status: AttendanceStatus


class BulkMarkRequest(BaseModel):
    date: date
    notes: str | None = Field(default=None, max_length=1000)
    entries: list[BulkAttendanceEntry] = Field(default_factory=list)


class AttendanceListItem(BaseModel):
    user_id: uuid.UUID
    emp_id: str
    name: str
    status: str
    marked_by_name: str | None
    check_in: datetime | None
    check_out: datetime | None
    notes: str | None


class AttendanceListResponse(BaseModel):
    data: list[AttendanceListItem]


class AttendanceSummaryResponse(BaseModel):
    present: int
    absent: int
    leave: int
    half_day: int
    total_employees: int


class EmployeeAttendanceSummary(BaseModel):
    present: int
    absent: int
    leave: int
    attendance_percentage: float


class EmployeeAttendanceRecord(BaseModel):
    date: date
    status: AttendanceStatus
    marked_by: str | None
    check_in: datetime | None
    check_out: datetime | None
    notes: str | None
