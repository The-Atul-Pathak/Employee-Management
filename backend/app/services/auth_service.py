from __future__ import annotations
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.core.config import settings
from app.models.company import Company, CompanyStatus
from app.models.user import UserStatus
from app.repositories.user_repo import user_repo
from app.schemas.auth import LoginResponse, UserInfo


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    async def login(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        identifier: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[LoginResponse, str]:
        """Returns (LoginResponse, raw_refresh_token)."""
        # Verify company exists and is active
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.deleted_at.is_(None),
            )
        )
        company = result.scalar_one_or_none()
        if company is None:
            raise ValueError("Company not found")
        if company.status != CompanyStatus.active:
            raise ValueError("Company account is not active")

        # Find user by emp_id or email
        if "@" in identifier:
            user = await user_repo.get_by_email(db, company_id, identifier)
        else:
            user = await user_repo.get_by_emp_id(db, company_id, identifier)

        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        if user.status != UserStatus.active:
            raise ValueError("User account is not active")

        # Create refresh token and store its hash
        token_payload = {
            "sub": str(user.id),
            "cid": str(company_id),
        }
        refresh_token = create_refresh_token(token_payload)
        refresh_hash = _hash_token(refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        session = await user_repo.create_session(
            db,
            user_id=user.id,
            company_id=company_id,
            refresh_token_hash=refresh_hash,
            ip=ip,
            user_agent=user_agent,
            expires_at=expires_at,
        )

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "cid": str(company_id),
                "sid": str(session.id),
            }
        )

        user_info = UserInfo(
            id=user.id,
            name=user.name,
            email=user.email,
            emp_id=user.emp_id,
            company_name=company.company_name,
            is_company_admin=user.is_company_admin,
        )
        return LoginResponse(access_token=access_token, user=user_info), refresh_token

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> str:
        """Validate refresh token, return new access token."""
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        refresh_hash = _hash_token(refresh_token)

        # Find the session by matching token hash
        from app.models.user import UserSession

        result = await db.execute(
            select(UserSession).where(
                UserSession.refresh_token_hash == refresh_hash,
                UserSession.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Session not found or expired")

        # Verify user still active
        user = await user_repo.get_by_id(db, session.company_id, session.user_id)
        if user is None or user.status != UserStatus.active:
            raise ValueError("User account is not active")

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "cid": str(session.company_id),
                "sid": str(session.id),
            }
        )
        return access_token

    async def logout(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        await user_repo.delete_session(db, session_id)


auth_service = AuthService()
