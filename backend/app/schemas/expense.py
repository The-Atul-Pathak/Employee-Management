from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.expense import ExpenseStatus
from app.schemas.user import PaginationMeta


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class ExpenseCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ExpenseCategoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool


class ExpenseCategoryListResponse(BaseModel):
    data: list[ExpenseCategoryItem]


class ExpenseCreate(BaseModel):
    category_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    currency: str = Field(default="INR", max_length=3)
    expense_date: date


class ExpenseReview(BaseModel):
    status: ExpenseStatus
    review_notes: Optional[str] = Field(default=None, max_length=2000)


class ExpenseUserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    emp_id: str


class ExpenseItem(BaseModel):
    id: uuid.UUID
    employee: ExpenseUserInfo
    category_id: Optional[uuid.UUID]
    category_name: Optional[str]
    title: str
    description: Optional[str]
    amount: float
    currency: str
    expense_date: date
    receipt_name: Optional[str]
    status: ExpenseStatus
    reviewer: Optional[ExpenseUserInfo]
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


class ExpenseListResponse(BaseModel):
    data: list[ExpenseItem]
    meta: PaginationMeta


class MyExpenseItem(BaseModel):
    id: uuid.UUID
    category_id: Optional[uuid.UUID]
    category_name: Optional[str]
    title: str
    description: Optional[str]
    amount: float
    currency: str
    expense_date: date
    receipt_name: Optional[str]
    status: ExpenseStatus
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


class MyExpensesResponse(BaseModel):
    data: list[MyExpenseItem]
    meta: PaginationMeta
