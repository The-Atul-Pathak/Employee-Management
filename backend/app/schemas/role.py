from __future__ import annotations
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RoleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    features: list[str]


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    feature_ids: list[uuid.UUID] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    feature_ids: list[uuid.UUID] = Field(default_factory=list)


class FeatureBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
