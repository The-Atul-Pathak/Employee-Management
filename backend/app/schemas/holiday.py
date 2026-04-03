from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.shift import HolidayType


class HolidayCreate(BaseModel):
    name: str
    date: date
    holiday_type: HolidayType = HolidayType.national
    is_optional: bool = False


class HolidayBulkLoad(BaseModel):
    year: int


class HolidayResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    date: date
    holiday_type: HolidayType
    is_optional: bool
    year: int
    created_at: datetime

    model_config = {"from_attributes": True}
