from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserSession


class UserRepository:
    async def get_by_emp_id(
        self, db: AsyncSession, company_id: uuid.UUID, emp_id: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.company_id == company_id,
                User.emp_id == emp_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(
        self, db: AsyncSession, company_id: uuid.UUID, email: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.company_id == company_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.company_id == company_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        refresh_token_hash: str,
        ip: str | None,
        user_agent: str | None,
        expires_at: datetime,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            company_id=company_id,
            refresh_token_hash=refresh_token_hash,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def get_session(
        self, db: AsyncSession, session_id: uuid.UUID
    ) -> UserSession | None:
        result = await db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def delete_session(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        await db.execute(
            delete(UserSession).where(UserSession.id == session_id)
        )

    async def delete_all_user_sessions(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> None:
        await db.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )


user_repo = UserRepository()
