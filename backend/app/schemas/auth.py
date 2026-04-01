from __future__ import annotations
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CompanyLoginRequest(BaseModel):
    company_id: uuid.UUID
    identifier: str = Field(min_length=1, max_length=255)  # emp_id or email
    password: str = Field(min_length=1, max_length=255)


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    emp_id: str
    company_name: str
    is_company_admin: bool


class LoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class TokenPayload(BaseModel):
    sub: str   # user_id
    cid: str   # company_id
    sid: str   # session_id
    exp: int


class RefreshRequest(BaseModel):
    pass


class PageInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_code: str
    page_name: str
    route: str


class RoleInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    emp_id: str
    company_id: uuid.UUID
    company_name: str
    is_company_admin: bool
    roles: list[RoleInfo]
    accessible_pages: list[PageInfo]
