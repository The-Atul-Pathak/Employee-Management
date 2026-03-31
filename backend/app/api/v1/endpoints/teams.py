from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.team import (
    AssignTeamRequest,
    TeamDetailsResponse,
    TeamListResponse,
    TeamResponse,
    TeamUpsertRequest,
    UnassignedProjectsResponse,
)
from app.services.team_service import team_service

router = APIRouter()


@router.get("", response_model=TeamListResponse)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TeamListResponse:
    return await team_service.list_teams(db, current_user["company_id"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        team = await team_service.create_team(db, current_user["company_id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"id": str(team.id), "message": "Team created successfully"}


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TeamResponse:
    try:
        return await team_service.get_team(db, current_user["company_id"], team_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{team_id}/details", response_model=TeamDetailsResponse)
async def get_team_details(
    team_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TeamDetailsResponse:
    try:
        return await team_service.get_team_details(db, current_user["company_id"], team_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{team_id}")
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        await team_service.update_team(db, current_user["company_id"], team_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Team updated successfully"}


@router.get("/unassigned-projects", response_model=UnassignedProjectsResponse)
async def list_unassigned_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UnassignedProjectsResponse:
    return await team_service.list_unassigned_projects(db, current_user["company_id"])


@router.put("/unassigned-projects/{project_id}/assign")
async def assign_team_to_project(
    project_id: uuid.UUID,
    body: AssignTeamRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    try:
        await team_service.assign_team_to_project(db, current_user["company_id"], project_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"message": "Team assigned successfully"}


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_team(
    team_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> Response:
    try:
        await team_service.archive_team(db, current_user["company_id"], team_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
