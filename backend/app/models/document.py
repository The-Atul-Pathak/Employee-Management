from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BaseModel


class DocumentType(str, enum.Enum):
    offer_letter = "offer_letter"
    contract = "contract"
    id_proof = "id_proof"
    payslip = "payslip"
    appraisal = "appraisal"
    other = "other"


class DocumentRequestStatus(str, enum.Enum):
    pending = "pending"
    fulfilled = "fulfilled"
    rejected = "rejected"


class Document(BaseModel):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_company_employee", "company_id", "employee_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        PgEnum(DocumentType, name="document_type", create_type=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)


class DocumentRequest(BaseModel):
    __tablename__ = "document_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        PgEnum(DocumentType, name="document_type", create_type=False),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentRequestStatus] = mapped_column(
        PgEnum(DocumentRequestStatus, name="document_request_status", create_type=True),
        nullable=False,
        default=DocumentRequestStatus.pending,
    )
    fulfilled_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
