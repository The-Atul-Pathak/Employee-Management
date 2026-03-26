from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.company import CompanyStatus
from app.models.plan import BillingCycle


# ─── Auth ────────────────────────────────────────────────────────────────────

class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PlatformAdminInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: str


class PlatformLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: PlatformAdminInfo


# ─── Companies ───────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)


class CompanyCreateRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=100)
    domain: Optional[str] = Field(default=None, max_length=255)
    employee_size_range: Optional[str] = Field(default=None, max_length=50)
    primary_contact: ContactCreate


class CompanyUpdateRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=100)
    domain: Optional[str] = Field(default=None, max_length=255)
    employee_size_range: Optional[str] = Field(default=None, max_length=50)
    status: CompanyStatus


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    is_primary: bool


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    billing_cycle: BillingCycle
    start_date: date
    end_date: Optional[date]
    is_active: bool


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    legal_name: Optional[str]
    industry: Optional[str]
    domain: Optional[str]
    employee_size_range: Optional[str]
    status: CompanyStatus
    created_at: datetime
    contacts: list[ContactResponse]
    subscription: Optional[SubscriptionResponse]


class CompanyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    industry: Optional[str]
    status: CompanyStatus
    created_at: datetime
    primary_contact_name: Optional[str]
    primary_contact_email: Optional[str]


class CompanyListResponse(BaseModel):
    data: list[CompanyListItem]
    total: int


# ─── Company Admin ────────────────────────────────────────────────────────────

class CompanyAdminCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    emp_id: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


# ─── Subscription ─────────────────────────────────────────────────────────────

class SubscriptionUpsertRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: BillingCycle
    start_date: date
    end_date: Optional[date] = None


# ─── Company Features ─────────────────────────────────────────────────────────

class CompanyFeaturesUpdateRequest(BaseModel):
    feature_ids: list[uuid.UUID]  # full replacement — these features will be enabled


# ─── Plans ───────────────────────────────────────────────────────────────────

class PlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None
    monthly_price: Decimal = Field(ge=0)
    yearly_price: Decimal = Field(ge=0)
    max_employees: int = Field(ge=1)


class PlanUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None
    monthly_price: Decimal = Field(ge=0)
    yearly_price: Decimal = Field(ge=0)
    max_employees: int = Field(ge=1)


class PlanUsageItem(BaseModel):
    company_id: uuid.UUID
    company_name: str


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    monthly_price: Decimal
    yearly_price: Decimal
    max_employees: int
    created_at: datetime


class PlanListResponse(BaseModel):
    data: list[PlanResponse]
    total: int


class PlanDeleteCheckResponse(BaseModel):
    can_delete: bool
    affected_companies: list[PlanUsageItem]


# ─── Features ────────────────────────────────────────────────────────────────

class FeatureCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None


class FeatureUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None


class FeatureUsageItem(BaseModel):
    company_id: uuid.UUID
    company_name: str
    enabled: bool


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: Optional[str]


class FeatureListResponse(BaseModel):
    data: list[FeatureResponse]
    total: int


class FeatureDeleteCheckResponse(BaseModel):
    can_delete: bool
    affected_companies: list[FeatureUsageItem]
