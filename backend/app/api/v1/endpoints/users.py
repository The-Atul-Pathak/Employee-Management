from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import UserStatus
from app.schemas.user import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserCreateRequest,
    UserListResponse,
    UserProfileResponse,
    UserSessionResponse,
    UserUpdateRequest,
)
from app.services.user_service import user_service

router = APIRouter()


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: UserStatus | None = Query(default=None, alias="status"),
) -> UserListResponse:
    return await user_service.list_users(
        db=db,
        company_id=current_user["company_id"],
        page=page,
        per_page=per_page,
        search=search,
        status_filter=status_filter,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        user = await user_service.create_user(db, current_user["company_id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"id": str(user.id), "message": "User created successfully"}


@router.put("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        await user_service.update_user(db, current_user["company_id"], user_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "User updated successfully"}


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserProfileResponse:
    try:
        return await user_service.get_user_profile(
            db=db,
            company_id=current_user["company_id"],
            user_id=user_id,
            viewer_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/me/profile", response_model=UserProfileResponse)
async def update_own_profile(
    body: UpdateProfileRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserProfileResponse:
    return await user_service.update_own_profile(
        db=db,
        company_id=current_user["company_id"],
        user_id=current_user["user_id"],
        data=body,
    )


@router.put("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await user_service.change_password(
            db=db,
            company_id=current_user["company_id"],
            user_id=current_user["user_id"],
            current=body.current_password,
            new=body.new_password,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Password updated successfully"}


@router.get("/sessions", response_model=list[UserSessionResponse])
async def list_active_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> list[UserSessionResponse]:
    return await user_service.list_active_sessions(db, current_user["company_id"])


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> Response:
    try:
        await user_service.terminate_session(db, current_user["company_id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
