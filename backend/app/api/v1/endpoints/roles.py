from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.role import (
    FeatureBundleResponse,
    RoleCreateRequest,
    RoleListResponse,
    RoleUpdateRequest,
)
from app.services.role_service import role_service

router = APIRouter()
features_router = APIRouter()


@router.get("", response_model=list[RoleListResponse])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[RoleListResponse]:
    return await role_service.list_roles(db, current_user["company_id"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        role = await role_service.create_role(db, current_user["company_id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"id": str(role.id), "message": "Role created successfully"}


@router.put("/{role_id}")
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        await role_service.update_role(db, current_user["company_id"], role_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Role updated successfully"}


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> Response:
    try:
        await role_service.delete_role(db, current_user["company_id"], role_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@features_router.get("", response_model=list[FeatureBundleResponse])
async def list_company_features(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[FeatureBundleResponse]:
    return await role_service.get_company_features(db, current_user["company_id"])
