from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.holiday import HolidayBulkLoad, HolidayCreate, HolidayResponse
from app.services.holiday_service import holiday_service

router = APIRouter()


@router.get("", response_model=list[HolidayResponse])
async def list_holidays(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    year: int | None = None,
) -> list[HolidayResponse]:
    if year is None:
        year = date.today().year
    return await holiday_service.list_holidays(db, current_user["company_id"], year)


@router.post("", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    body: HolidayCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> HolidayResponse:
    try:
        return await holiday_service.create_holiday(db, current_user["company_id"], body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.commit()


@router.post("/bulk", response_model=list[HolidayResponse], status_code=status.HTTP_201_CREATED)
async def bulk_load_holidays(
    body: HolidayBulkLoad,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> list[HolidayResponse]:
    result = await holiday_service.bulk_load_standard_holidays(
        db, current_user["company_id"], body.year
    )
    await db.commit()
    return result


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> None:
    try:
        await holiday_service.delete_holiday(db, current_user["company_id"], holiday_id)
        await db.commit()
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
