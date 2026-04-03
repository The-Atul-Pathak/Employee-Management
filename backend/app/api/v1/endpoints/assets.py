from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.asset import (
    AssetAssignRequest,
    AssetCreate,
    AssetDetail,
    AssetItem,
    AssetListResponse,
    AssetReturnRequest,
    AssetUpdate,
)
from app.services.asset_service import asset_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


@router.get("", response_model=AssetListResponse)
async def list_assets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> AssetListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await asset_service.list_assets(
        db=db, company_id=current_user["company_id"], page=page, per_page=per_page
    )


@router.post("", response_model=AssetItem, status_code=status.HTTP_201_CREATED)
async def create_asset(
    body: AssetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AssetItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await asset_service.create_asset(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.get("/my", response_model=list[AssetItem])
async def get_my_assets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[AssetItem]:
    return await asset_service.get_employee_assets(
        db=db,
        company_id=current_user["company_id"],
        employee_id=current_user["user_id"],
    )


@router.get("/employee/{employee_id}", response_model=list[AssetItem])
async def get_employee_assets(
    employee_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[AssetItem]:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await asset_service.get_employee_assets(
        db=db, company_id=current_user["company_id"], employee_id=employee_id
    )


@router.get("/{asset_id}", response_model=AssetDetail)
async def get_asset_detail(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AssetDetail:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await asset_service.get_asset_detail(
            db=db, company_id=current_user["company_id"], asset_id=asset_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{asset_id}", response_model=AssetItem)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AssetItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await asset_service.update_asset(
            db=db, company_id=current_user["company_id"], asset_id=asset_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await asset_service.delete_asset(
            db=db, company_id=current_user["company_id"], asset_id=asset_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{asset_id}/assign", response_model=AssetItem)
async def assign_asset(
    asset_id: uuid.UUID,
    body: AssetAssignRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AssetItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await asset_service.assign_asset(
            db=db,
            company_id=current_user["company_id"],
            asset_id=asset_id,
            assigner_id=current_user["user_id"],
            data=body,
        )
    except (LookupError, ValueError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, LookupError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/{asset_id}/return", response_model=AssetItem)
async def return_asset(
    asset_id: uuid.UUID,
    body: AssetReturnRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AssetItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await asset_service.return_asset(
            db=db, company_id=current_user["company_id"], asset_id=asset_id, data=body
        )
    except (LookupError, ValueError) as exc:
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, LookupError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))
