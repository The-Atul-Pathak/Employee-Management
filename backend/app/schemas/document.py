from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentRequestStatus, DocumentType
from app.schemas.user import PaginationMeta


class DocumentUploadBody(BaseModel):
    employee_id: uuid.UUID
    document_type: DocumentType
    title: str = Field(..., max_length=255)


class DocumentUserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    emp_id: str


class DocumentItem(BaseModel):
    id: uuid.UUID
    employee: DocumentUserInfo
    uploaded_by: Optional[DocumentUserInfo]
    document_type: DocumentType
    title: str
    file_name: str
    mime_type: str
    file_size: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    data: list[DocumentItem]
    meta: PaginationMeta


class DocumentRequestCreate(BaseModel):
    document_type: DocumentType
    notes: Optional[str] = Field(default=None, max_length=2000)


class DocumentRequestItem(BaseModel):
    id: uuid.UUID
    requested_by: DocumentUserInfo
    document_type: DocumentType
    notes: Optional[str]
    status: DocumentRequestStatus
    fulfilled_document_id: Optional[uuid.UUID]
    created_at: datetime


class DocumentRequestListResponse(BaseModel):
    data: list[DocumentRequestItem]
    meta: PaginationMeta


class FulfillRequestBody(BaseModel):
    status: DocumentRequestStatus
