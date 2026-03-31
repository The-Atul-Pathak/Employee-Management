from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.task import (
    TaskApproveRequest,
    TaskCreateRequest,
    TaskListResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
    TaskListItem,
)
from app.services.task_service import task_service

router = APIRouter()


@router.get("/tasks", response_model=TaskListResponse)
async def list_company_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    project_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
) -> TaskListResponse:
    try:
        return await task_service.list_tasks(
            db,
            current_user["company_id"],
            project_id=project_id,
            page=page,
            per_page=per_page,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TaskListResponse:
    try:
        return await task_service.list_tasks(db, current_user["company_id"], project_id=project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/tasks/{task_id}", response_model=TaskListItem)
async def get_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> TaskListItem:
    try:
        return await task_service.get_task(db, current_user["company_id"], task_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        task = await task_service.create_task(
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

    return {"id": str(task.id), "message": "Task created successfully"}


@router.post("/projects/{project_id}/tasks/suggest", status_code=status.HTTP_201_CREATED)
async def suggest_task(
    project_id: uuid.UUID,
    body: TaskCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        task = await task_service.suggest_task(
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

    return {"id": str(task.id), "message": "Task suggestion submitted successfully"}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await task_service.update_task(
            db=db,
            company_id=current_user["company_id"],
            task_id=task_id,
            user_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Task updated successfully"}


@router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: uuid.UUID,
    body: TaskApproveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await task_service.approve_task(
            db=db,
            company_id=current_user["company_id"],
            task_id=task_id,
            user_id=current_user["user_id"],
            approve=body.approve,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Task reviewed successfully"}


@router.post("/tasks/{task_id}/status")
async def update_task_status(
    task_id: uuid.UUID,
    body: TaskStatusUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await task_service.update_task_status(
            db=db,
            company_id=current_user["company_id"],
            task_id=task_id,
            user_id=current_user["user_id"],
            new_status=body.new_status,
            note=body.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Task status updated successfully"}


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    try:
        await task_service.complete_task(
            db=db,
            company_id=current_user["company_id"],
            task_id=task_id,
            user_id=current_user["user_id"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Task completed successfully"}
