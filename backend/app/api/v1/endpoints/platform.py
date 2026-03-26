from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin
from app.core.config import settings
from app.schemas.platform import (
    CompanyAdminCreateRequest,
    CompanyCreateRequest,
    CompanyFeaturesUpdateRequest,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdateRequest,
    FeatureCreateRequest,
    FeatureDeleteCheckResponse,
    FeatureListResponse,
    FeatureResponse,
    FeatureUpdateRequest,
    PlanCreateRequest,
    PlanDeleteCheckResponse,
    PlanListResponse,
    PlanResponse,
    PlanUpdateRequest,
    PlatformLoginRequest,
    PlatformLoginResponse,
    SubscriptionResponse,
    SubscriptionUpsertRequest,
)
from app.services.platform_service import platform_service

router = APIRouter()

_REFRESH_COOKIE = "platform_refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/platform",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/platform")


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=PlatformLoginResponse)
async def platform_login(
    body: PlatformLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformLoginResponse:
    ip = request.client.host if request.client else "unknown"
    try:
        login_response, refresh_token = await platform_service.login(
            db=db,
            email=body.email,
            password=body.password,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    _set_refresh_cookie(response, refresh_token)
    return login_response


@router.post("/refresh")
async def platform_refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    platform_refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> dict:
    if not platform_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    try:
        access_token = await platform_service.refresh_token(db, platform_refresh_token)
    except ValueError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def platform_logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[dict, Depends(get_current_platform_admin)],
) -> None:
    await platform_service.logout(db, current_admin["session_id"])
    _clear_refresh_cookie(response)


@router.get("/me")
async def platform_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[dict, Depends(get_current_platform_admin)],
) -> dict:
    from sqlalchemy import select
    from app.models.platform_admin import PlatformAdmin

    result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.id == current_admin["admin_id"])
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    return {"id": admin.id, "name": admin.name, "email": admin.email, "role": admin.role.value}


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> dict:
    return await platform_service.get_stats(db)


# ─── Companies ────────────────────────────────────────────────────────────────

@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> CompanyListResponse:
    result = await platform_service.list_companies(db)
    return CompanyListResponse(**result)


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> CompanyResponse:
    try:
        return await platform_service.create_company(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> CompanyResponse:
    try:
        return await platform_service.get_company(db, company_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> CompanyResponse:
    try:
        return await platform_service.update_company(db, company_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/companies/{company_id}/admin", status_code=status.HTTP_201_CREATED)
async def create_company_admin(
    company_id: uuid.UUID,
    body: CompanyAdminCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> dict:
    try:
        return await platform_service.create_company_admin(db, company_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/companies/{company_id}/subscription", response_model=SubscriptionResponse)
async def upsert_subscription(
    company_id: uuid.UUID,
    body: SubscriptionUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> SubscriptionResponse:
    try:
        return await platform_service.upsert_subscription(db, company_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/companies/{company_id}/features")
async def update_company_features(
    company_id: uuid.UUID,
    body: CompanyFeaturesUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> list:
    try:
        return await platform_service.update_company_features(db, company_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─── Plans ────────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=PlanListResponse)
async def list_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> PlanListResponse:
    result = await platform_service.list_plans(db)
    return PlanListResponse(**result)


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> PlanResponse:
    try:
        return await platform_service.create_plan(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    body: PlanUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> PlanResponse:
    try:
        return await platform_service.update_plan(db, plan_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/plans/{plan_id}/usage", response_model=PlanDeleteCheckResponse)
async def check_plan_usage(
    plan_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> PlanDeleteCheckResponse:
    return await platform_service.check_plan_usage(db, plan_id)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> None:
    try:
        await platform_service.delete_plan(db, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ─── Features ─────────────────────────────────────────────────────────────────

@router.get("/features", response_model=FeatureListResponse)
async def list_features(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> FeatureListResponse:
    result = await platform_service.list_features(db)
    return FeatureListResponse(**result)


@router.post("/features", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    body: FeatureCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> FeatureResponse:
    try:
        return await platform_service.create_feature(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/features/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    feature_id: uuid.UUID,
    body: FeatureUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> FeatureResponse:
    try:
        return await platform_service.update_feature(db, feature_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/features/{feature_id}/usage", response_model=FeatureDeleteCheckResponse)
async def check_feature_usage(
    feature_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> FeatureDeleteCheckResponse:
    return await platform_service.check_feature_usage(db, feature_id)


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(
    feature_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(get_current_platform_admin)],
) -> None:
    try:
        await platform_service.delete_feature(db, feature_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
