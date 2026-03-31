from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.crm import LeadStatus
from app.schemas.lead import (
    LeadCreateRequest,
    LeadInteractionCreateRequest,
    LeadInteractionResponse,
    LeadListResponse,
    LeadUpdateRequest,
    TodaysFollowupsResponse,
)
from app.services.lead_service import lead_service

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        lead = await lead_service.create_lead(
            db=db,
            company_id=current_user["company_id"],
            created_by=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"id": str(lead.id), "message": "Lead created successfully"}


@router.get("", response_model=LeadListResponse)
async def list_leads(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    assigned_to_filter: uuid.UUID | None = Query(default=None, alias="assigned_to"),
    search: str | None = Query(default=None),
) -> LeadListResponse:
    return await lead_service.list_leads(
        db=db,
        company_id=current_user["company_id"],
        page=page,
        per_page=per_page,
        status_filter=status_filter,
        assigned_to_filter=assigned_to_filter,
        search=search,
    )


@router.get("/today", response_model=TodaysFollowupsResponse)
async def get_todays_followups(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TodaysFollowupsResponse:
    try:
        return await lead_service.get_todays_followups(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            is_company_admin=current_user["is_company_admin"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{lead_id}")
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await lead_service.update_lead(
            db=db,
            company_id=current_user["company_id"],
            lead_id=lead_id,
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"message": "Lead updated successfully"}


@router.post("/{lead_id}/interactions", status_code=status.HTTP_201_CREATED)
async def log_interaction(
    lead_id: uuid.UUID,
    body: LeadInteractionCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        interaction = await lead_service.log_interaction(
            db=db,
            company_id=current_user["company_id"],
            lead_id=lead_id,
            user_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"id": str(interaction.id), "message": "Interaction logged successfully"}


@router.get("/{lead_id}/interactions", response_model=list[LeadInteractionResponse])
async def get_interactions(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[LeadInteractionResponse]:
    try:
        return await lead_service.get_interactions(
            db=db,
            company_id=current_user["company_id"],
            lead_id=lead_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
