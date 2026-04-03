from __future__ import annotations

import math
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentRequest, DocumentRequestStatus, DocumentType
from app.models.user import User
from app.schemas.document import (
    DocumentItem,
    DocumentListResponse,
    DocumentRequestItem,
    DocumentRequestListResponse,
    DocumentUploadBody,
    DocumentUserInfo,
    FulfillRequestBody,
)
from app.schemas.user import PaginationMeta


class DocumentService:
    def _upload_dir(self, company_id: uuid.UUID, doc_type: str) -> Path:
        p = Path(settings.UPLOAD_DIR) / str(company_id) / "documents" / doc_type
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def _get_user_info(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def upload_document(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        uploader_id: uuid.UUID,
        body: DocumentUploadBody,
        file: UploadFile,
    ) -> DocumentItem:
        # Save file
        upload_dir = self._upload_dir(company_id, body.document_type.value)
        unique_name = f"{uuid.uuid4()}_{file.filename}"
        file_path = upload_dir / unique_name

        content = await file.read()
        file_path.write_bytes(content)

        doc = Document(
            company_id=company_id,
            employee_id=body.employee_id,
            uploaded_by=uploader_id,
            document_type=body.document_type,
            title=body.title,
            file_path=str(file_path),
            file_name=file.filename or unique_name,
            mime_type=file.content_type or "application/octet-stream",
            file_size=len(content),
        )
        db.add(doc)
        await db.flush()

        employee = await self._get_user_info(db, body.employee_id)
        uploader = await self._get_user_info(db, uploader_id)
        return self._to_item(doc, employee, uploader)

    async def list_documents(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        doc_type: DocumentType | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> DocumentListResponse:
        filters = [
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        ]
        if employee_id:
            filters.append(Document.employee_id == employee_id)
        if doc_type:
            filters.append(Document.document_type == doc_type)

        total_stmt = select(func.count()).select_from(Document).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        docs = (await db.execute(stmt)).scalars().all()

        employee_ids = {d.employee_id for d in docs}
        uploader_ids = {d.uploaded_by for d in docs if d.uploaded_by}
        all_user_ids = employee_ids | uploader_ids

        users: dict[uuid.UUID, User] = {}
        if all_user_ids:
            user_stmt = select(User).where(User.id.in_(all_user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        items = [
            self._to_item(d, users.get(d.employee_id), users.get(d.uploaded_by) if d.uploaded_by else None)
            for d in docs
        ]

        return DocumentListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_document_path(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        is_admin: bool,
    ) -> tuple[str, str, str]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        )
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if doc is None:
            raise LookupError("Document not found")

        if not is_admin and doc.employee_id != requesting_user_id:
            raise PermissionError("Access denied")

        return doc.file_path, doc.file_name, doc.mime_type

    async def delete_document(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        )
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if doc is None:
            raise LookupError("Document not found")

        from datetime import datetime, timezone
        doc.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    # ── Document Requests ──────────────────────────────────────────────────────

    async def create_request(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        doc_type: DocumentType,
        notes: str | None,
    ) -> DocumentRequestItem:
        req = DocumentRequest(
            company_id=company_id,
            requested_by=user_id,
            document_type=doc_type,
            notes=notes,
            status=DocumentRequestStatus.pending,
        )
        db.add(req)
        await db.flush()

        user = await self._get_user_info(db, user_id)
        return self._to_request_item(req, user)

    async def list_requests(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> DocumentRequestListResponse:
        filters = [
            DocumentRequest.company_id == company_id,
            DocumentRequest.deleted_at.is_(None),
        ]
        if user_id:
            filters.append(DocumentRequest.requested_by == user_id)

        total_stmt = select(func.count()).select_from(DocumentRequest).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(DocumentRequest)
            .where(*filters)
            .order_by(DocumentRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        requests = (await db.execute(stmt)).scalars().all()

        user_ids = {r.requested_by for r in requests}
        users: dict[uuid.UUID, User] = {}
        if user_ids:
            user_stmt = select(User).where(User.id.in_(user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        return DocumentRequestListResponse(
            data=[self._to_request_item(r, users.get(r.requested_by)) for r in requests],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def fulfill_request(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        data: FulfillRequestBody,
    ) -> DocumentRequestItem:
        stmt = select(DocumentRequest).where(
            DocumentRequest.id == request_id,
            DocumentRequest.company_id == company_id,
            DocumentRequest.deleted_at.is_(None),
        )
        req = (await db.execute(stmt)).scalar_one_or_none()
        if req is None:
            raise LookupError("Document request not found")

        req.status = data.status
        await db.flush()

        user = await self._get_user_info(db, req.requested_by)
        return self._to_request_item(req, user)

    def _to_item(
        self,
        doc: Document,
        employee: User | None,
        uploader: User | None,
    ) -> DocumentItem:
        def _user_info(u: User | None) -> DocumentUserInfo | None:
            if u is None:
                return None
            return DocumentUserInfo(id=u.id, name=u.name, emp_id=u.emp_id)

        return DocumentItem(
            id=doc.id,
            employee=_user_info(employee),
            uploaded_by=_user_info(uploader),
            document_type=doc.document_type,
            title=doc.title,
            file_name=doc.file_name,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            created_at=doc.created_at,
        )

    def _to_request_item(
        self,
        req: DocumentRequest,
        user: User | None,
    ) -> DocumentRequestItem:
        def _user_info(u: User | None) -> DocumentUserInfo | None:
            if u is None:
                return None
            return DocumentUserInfo(id=u.id, name=u.name, emp_id=u.emp_id)

        return DocumentRequestItem(
            id=req.id,
            requested_by=_user_info(user),
            document_type=req.document_type,
            notes=req.notes,
            status=req.status,
            fulfilled_document_id=req.fulfilled_document_id,
            created_at=req.created_at,
        )


document_service = DocumentService()
