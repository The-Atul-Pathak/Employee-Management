from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CompanySettings(BaseModel):
    """Company-wide HR configuration stored as JSONB in companies.settings."""

    working_days: list[int] = Field(
        default=[1, 2, 3, 4, 5],
        description="ISO weekday numbers: 1=Mon … 7=Sun",
    )
    work_hours_per_day: float = Field(default=8.0, ge=1, le=24)
    attendance_cutoff_time: str = Field(
        default="10:00",
        description="Time string HH:MM after which check-in counts as late",
    )
    leave_year_start_month: int = Field(
        default=1,
        ge=1,
        le=12,
        description="Month the leave year starts (1=Jan, 4=Apr for Indian FY)",
    )
    auto_mark_absent: bool = False
    allow_self_attendance: bool = False
    probation_days: int = Field(default=90, ge=0)
    notice_period_days: int = Field(default=30, ge=0)
    currency: str = Field(default="INR", max_length=3)
    timezone: str = Field(default="Asia/Kolkata", max_length=50)
    date_format: str = Field(default="DD/MM/YYYY", max_length=20)


class CompanySettingsResponse(BaseModel):
    settings: CompanySettings
