from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import redis_client
from app.core.config import settings
from app.models.company import Company
from app.repositories.user_repo import user_repo
from app.schemas.auth import (
    CompanyLoginRequest,
    LoginResponse,
    MeResponse,
    RoleInfo,
)
from app.services.auth_service import auth_service
from app.services.role_service import role_service

router = APIRouter()

_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60  # seconds
_REFRESH_COOKIE = "refresh_token"


async def _check_login_rate_limit(ip: str) -> None:
    key = f"login_attempts:{ip}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, _RATE_LIMIT_WINDOW)
    if count > _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/login", response_model=LoginResponse)
async def login(
    body: CompanyLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    ip = request.client.host if request.client else "unknown"
    await _check_login_rate_limit(ip)

    try:
        login_response, refresh_token = await auth_service.login(
            db=db,
            company_id=body.company_id,
            identifier=body.identifier,
            password=body.password,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    _set_refresh_cookie(response, refresh_token)
    return login_response


@router.post("/refresh")
async def refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> dict:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        access_token = await auth_service.refresh_token(db, refresh_token)
    except ValueError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    await auth_service.logout(db, current_user["session_id"])
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeResponse)
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MeResponse:
    user_id: uuid.UUID = current_user["user_id"]
    company_id: uuid.UUID = current_user["company_id"]

    user = await user_repo.get_by_id(db, company_id, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Load company name
    company_result = await db.execute(
        select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    )
    company = company_result.scalar_one_or_none()
    company_name = company.company_name if company else ""

    from app.models.access import Role, UserRole

    roles_result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Role.deleted_at.is_(None),
        )
        .order_by(Role.name.asc())
    )
    roles = roles_result.scalars().all()
    pages = await role_service.get_user_accessible_pages(
        db=db,
        user_id=user_id,
        company_id=company_id,
        is_admin=user.is_company_admin,
    )

    return MeResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        emp_id=user.emp_id,
        company_id=company_id,
        company_name=company_name,
        is_company_admin=user.is_company_admin,
        roles=[RoleInfo(id=r.id, name=r.name) for r in roles],
        accessible_pages=pages,
    )
