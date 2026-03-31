from __future__ import annotations
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus


class UserRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    emp_id: str
    name: str
    email: EmailStr | None
    status: UserStatus
    is_company_admin: bool
    roles: list[UserRoleResponse]


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class UserListResponse(BaseModel):
    data: list[UserListItem]
    meta: PaginationMeta


class UserCreateRequest(BaseModel):
    emp_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=255)
    is_company_admin: bool = False
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    emp_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)
    status: UserStatus
    is_company_admin: bool = False
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    emp_id: str
    name: str
    email: EmailStr | None
    status: UserStatus
    is_company_admin: bool
    profile_photo_url: str | None
    phone: str | None
    alt_phone: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    date_of_birth: date | None
    date_of_joining: date | None
    last_login: datetime | None
    roles: list[UserRoleResponse]
    features: list[UserFeatureResponse]
    can_edit: bool


class UpdateProfileRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=50)
    alt_phone: str | None = Field(default=None, max_length=50)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=50)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class UserSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    emp_id: str
    email: EmailStr | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    expires_at: datetime
