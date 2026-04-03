from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.document import DocumentType
from app.schemas.document import (
    DocumentItem,
    DocumentListResponse,
    DocumentRequestCreate,
    DocumentRequestItem,
    DocumentRequestListResponse,
    DocumentUploadBody,
    FulfillRequestBody,
)
from app.services.document_service import document_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    employee_id: Optional[uuid.UUID] = Query(default=None),
    document_type: Optional[DocumentType] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> DocumentListResponse:
    # Non-admins can only see their own documents
    target_employee = employee_id
    if not _is_hr(current_user):
        target_employee = current_user["user_id"]

    return await document_service.list_documents(
        db=db,
        company_id=current_user["company_id"],
        employee_id=target_employee,
        doc_type=document_type,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=DocumentItem, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    employee_id: uuid.UUID = Form(...),
    document_type: DocumentType = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
) -> DocumentItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    body = DocumentUploadBody(employee_id=employee_id, document_type=document_type, title=title)
    return await document_service.upload_document(
        db=db,
        company_id=current_user["company_id"],
        uploader_id=current_user["user_id"],
        body=body,
        file=file,
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> FileResponse:
    try:
        file_path, file_name, mime_type = await document_service.get_document_path(
            db=db,
            company_id=current_user["company_id"],
            document_id=document_id,
            requesting_user_id=current_user["user_id"],
            is_admin=_is_hr(current_user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    return FileResponse(path=file_path, filename=file_name, media_type=mime_type)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await document_service.delete_document(
            db=db,
            company_id=current_user["company_id"],
            document_id=document_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Document Requests ──────────────────────────────────────────────────────────

@router.get("/requests", response_model=DocumentRequestListResponse)
async def list_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> DocumentRequestListResponse:
    user_id = None if _is_hr(current_user) else current_user["user_id"]
    return await document_service.list_requests(
        db=db,
        company_id=current_user["company_id"],
        user_id=user_id,
        page=page,
        per_page=per_page,
    )


@router.post("/requests", response_model=DocumentRequestItem, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: DocumentRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DocumentRequestItem:
    return await document_service.create_request(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        doc_type=body.document_type,
        notes=body.notes,
    )


@router.patch("/requests/{request_id}", response_model=DocumentRequestItem)
async def fulfill_request(
    request_id: uuid.UUID,
    body: FulfillRequestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DocumentRequestItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await document_service.fulfill_request(
            db=db,
            company_id=current_user["company_id"],
            request_id=request_id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
