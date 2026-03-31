from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.project import (
    AssignTeamRequest,
    PlanningRequest,
    ProjectActionResponse,
    ProjectDetailResponse,
    ProjectListResponse,
)
from app.services.project_service import project_service

router = APIRouter()


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectListResponse:
    return await project_service.list_projects(db, current_user["company_id"])


@router.get("/unassigned", response_model=ProjectListResponse)
async def get_unassigned_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectListResponse:
    return await project_service.get_unassigned_projects(db, current_user["company_id"])


@router.post("/{project_id}/assign-team", response_model=ProjectActionResponse)
async def assign_team(
    project_id: uuid.UUID,
    body: AssignTeamRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> ProjectActionResponse:
    try:
        return await project_service.assign_team(
            db=db,
            company_id=current_user["company_id"],
            project_id=project_id,
            team_id=body.team_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project_detail(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectDetailResponse:
    try:
        return await project_service.get_project_detail(
            db=db,
            company_id=current_user["company_id"],
            project_id=project_id,
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{project_id}/planning", response_model=ProjectActionResponse)
async def save_planning(
    project_id: uuid.UUID,
    body: PlanningRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectActionResponse:
    try:
        return await project_service.save_planning(
            db=db,
            company_id=current_user["company_id"],
            project_id=project_id,
            user_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/start", response_model=ProjectActionResponse)
async def start_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectActionResponse:
    try:
        return await project_service.start_project(
            db=db,
            company_id=current_user["company_id"],
            project_id=project_id,
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/complete", response_model=ProjectActionResponse)
async def complete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProjectActionResponse:
    try:
        return await project_service.complete_project(
            db=db,
            company_id=current_user["company_id"],
            project_id=project_id,
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
