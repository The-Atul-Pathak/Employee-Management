from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetCategory, AssetStatus
from app.schemas.user import PaginationMeta


class AssetCreate(BaseModel):
    asset_tag: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    category: AssetCategory
    brand: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    notes: Optional[str] = None


class AssetUpdate(BaseModel):
    asset_tag: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, max_length=255)
    category: Optional[AssetCategory] = None
    brand: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    status: Optional[AssetStatus] = None
    notes: Optional[str] = None


class AssetAssignRequest(BaseModel):
    employee_id: uuid.UUID
    condition_out: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None


class AssetReturnRequest(BaseModel):
    condition_in: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None


class AssetUserInfo(BaseModel):
    id: uuid.UUID
    name: str
    emp_id: str


class AssetAssignmentItem(BaseModel):
    id: uuid.UUID
    employee: Optional[AssetUserInfo]
    assigned_by: Optional[AssetUserInfo]
    assigned_at: datetime
    returned_at: Optional[datetime]
    condition_out: Optional[str]
    condition_in: Optional[str]
    notes: Optional[str]


class AssetItem(BaseModel):
    id: uuid.UUID
    asset_tag: str
    name: str
    category: AssetCategory
    brand: Optional[str]
    model: Optional[str]
    serial_number: Optional[str]
    purchase_date: Optional[date]
    purchase_price: Optional[float]
    status: AssetStatus
    notes: Optional[str]
    current_assignee: Optional[AssetUserInfo]
    created_at: datetime


class AssetDetail(AssetItem):
    assignment_history: list[AssetAssignmentItem]


class AssetListResponse(BaseModel):
    data: list[AssetItem]
    meta: PaginationMeta
