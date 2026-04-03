from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.company import Company
from app.schemas.company_settings import CompanySettings, CompanySettingsResponse

router = APIRouter()

_SETTINGS_KEY = "hr_settings"


def _parse_settings(raw: dict | None) -> CompanySettings:
    data = (raw or {}).get(_SETTINGS_KEY, {})
    return CompanySettings.model_validate(data)


@router.get("/settings", response_model=CompanySettingsResponse)
async def get_company_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CompanySettingsResponse:
    company = (
        await db.execute(
            select(Company).where(
                Company.id == current_user["company_id"],
                Company.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanySettingsResponse(settings=_parse_settings(company.settings))


@router.put("/settings", response_model=CompanySettingsResponse)
async def update_company_settings(
    body: CompanySettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
) -> CompanySettingsResponse:
    company = (
        await db.execute(
            select(Company).where(
                Company.id == current_user["company_id"],
                Company.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    existing = dict(company.settings or {})
    existing[_SETTINGS_KEY] = body.model_dump()
    company.settings = existing

    await db.commit()
    await db.refresh(company)
    return CompanySettingsResponse(settings=_parse_settings(company.settings))
