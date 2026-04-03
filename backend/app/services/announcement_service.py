from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement, AnnouncementRead, AnnouncementTargetType
from app.models.access import Role, UserRole
from app.models.team import Team, TeamMember
from app.models.user import User
from app.schemas.announcement import (
    AnnouncementAuthorInfo,
    AnnouncementCreate,
    AnnouncementItem,
    AnnouncementListResponse,
    AnnouncementUpdate,
    UnreadAnnouncementCount,
)
from app.schemas.user import PaginationMeta


class AnnouncementService:
    async def _get_user_role_ids(
        self, db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        stmt = select(UserRole.role_id).where(
            UserRole.user_id == user_id,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_user_team_ids(
        self, db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        stmt = select(TeamMember.team_id).where(
            TeamMember.user_id == user_id,
            TeamMember.company_id == company_id,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _is_visible(
        self,
        announcement: Announcement,
        user_role_ids: list[uuid.UUID],
        user_team_ids: list[uuid.UUID],
    ) -> bool:
        if announcement.target_type == AnnouncementTargetType.all:
            return True
        if announcement.target_type == AnnouncementTargetType.roles:
            if not announcement.target_ids:
                return True
            return any(rid in announcement.target_ids for rid in user_role_ids)
        if announcement.target_type == AnnouncementTargetType.teams:
            if not announcement.target_ids:
                return True
            return any(tid in announcement.target_ids for tid in user_team_ids)
        return False

    async def list_announcements(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> AnnouncementListResponse:
        now = datetime.now(timezone.utc)
        user_role_ids = await self._get_user_role_ids(db, company_id, user_id)
        user_team_ids = await self._get_user_team_ids(db, company_id, user_id)

        base_filters = [
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        ]

        stmt = (
            select(Announcement)
            .where(*base_filters)
            .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        )
        all_announcements = (await db.execute(stmt)).scalars().all()

        visible = [a for a in all_announcements if self._is_visible(a, user_role_ids, user_team_ids)]
        total = len(visible)
        paginated = visible[(page - 1) * per_page : page * per_page]

        # Fetch read records
        read_ids: set[uuid.UUID] = set()
        if paginated:
            ann_ids = [a.id for a in paginated]
            read_stmt = select(AnnouncementRead.announcement_id).where(
                AnnouncementRead.user_id == user_id,
                AnnouncementRead.announcement_id.in_(ann_ids),
            )
            read_ids = set((await db.execute(read_stmt)).scalars().all())

        # Fetch authors
        author_ids = {a.author_id for a in paginated if a.author_id}
        authors: dict[uuid.UUID, User] = {}
        if author_ids:
            author_stmt = select(User).where(User.id.in_(author_ids))
            for u in (await db.execute(author_stmt)).scalars().all():
                authors[u.id] = u

        items = []
        for a in paginated:
            author_user = authors.get(a.author_id) if a.author_id else None
            items.append(self._to_item(a, is_read=a.id in read_ids, author=author_user))

        return AnnouncementListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_announcement(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        announcement_id: uuid.UUID,
    ) -> AnnouncementItem:
        stmt = select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
        )
        announcement = (await db.execute(stmt)).scalar_one_or_none()
        if announcement is None:
            raise LookupError("Announcement not found")

        # Mark as read
        read_stmt = select(AnnouncementRead).where(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == user_id,
        )
        existing_read = (await db.execute(read_stmt)).scalar_one_or_none()
        if existing_read is None:
            db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user_id))
            await db.flush()

        author: User | None = None
        if announcement.author_id:
            author_stmt = select(User).where(User.id == announcement.author_id)
            author = (await db.execute(author_stmt)).scalar_one_or_none()

        return self._to_item(announcement, is_read=True, author=author)

    async def create_announcement(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        author_id: uuid.UUID,
        data: AnnouncementCreate,
    ) -> AnnouncementItem:
        announcement = Announcement(
            company_id=company_id,
            author_id=author_id,
            title=data.title,
            body=data.body,
            target_type=data.target_type,
            target_ids=data.target_ids,
            is_pinned=data.is_pinned,
            expires_at=data.expires_at,
        )
        db.add(announcement)
        await db.flush()

        author_stmt = select(User).where(User.id == author_id)
        author = (await db.execute(author_stmt)).scalar_one_or_none()

        return self._to_item(announcement, is_read=False, author=author)

    async def update_announcement(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        announcement_id: uuid.UUID,
        data: AnnouncementUpdate,
    ) -> AnnouncementItem:
        stmt = select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
        )
        announcement = (await db.execute(stmt)).scalar_one_or_none()
        if announcement is None:
            raise LookupError("Announcement not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(announcement, field, value)
        await db.flush()

        author: User | None = None
        if announcement.author_id:
            author_stmt = select(User).where(User.id == announcement.author_id)
            author = (await db.execute(author_stmt)).scalar_one_or_none()

        return self._to_item(announcement, is_read=False, author=author)

    async def delete_announcement(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        announcement_id: uuid.UUID,
    ) -> None:
        stmt = select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
        )
        announcement = (await db.execute(stmt)).scalar_one_or_none()
        if announcement is None:
            raise LookupError("Announcement not found")
        announcement.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    async def get_unread_count(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UnreadAnnouncementCount:
        now = datetime.now(timezone.utc)
        user_role_ids = await self._get_user_role_ids(db, company_id, user_id)
        user_team_ids = await self._get_user_team_ids(db, company_id, user_id)

        base_filters = [
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        ]

        stmt = select(Announcement).where(*base_filters)
        all_announcements = (await db.execute(stmt)).scalars().all()
        visible_ids = [
            a.id for a in all_announcements
            if self._is_visible(a, user_role_ids, user_team_ids)
        ]

        if not visible_ids:
            return UnreadAnnouncementCount(count=0)

        read_stmt = select(func.count()).select_from(AnnouncementRead).where(
            AnnouncementRead.user_id == user_id,
            AnnouncementRead.announcement_id.in_(visible_ids),
        )
        read_count = (await db.execute(read_stmt)).scalar_one()
        return UnreadAnnouncementCount(count=max(0, len(visible_ids) - read_count))

    async def mark_all_read(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        now = datetime.now(timezone.utc)
        base_filters = [
            Announcement.company_id == company_id,
            Announcement.deleted_at.is_(None),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        ]
        stmt = select(Announcement.id).where(*base_filters)
        all_ids = list((await db.execute(stmt)).scalars().all())

        if not all_ids:
            return

        read_stmt = select(AnnouncementRead.announcement_id).where(
            AnnouncementRead.user_id == user_id,
            AnnouncementRead.announcement_id.in_(all_ids),
        )
        already_read = set((await db.execute(read_stmt)).scalars().all())

        for ann_id in all_ids:
            if ann_id not in already_read:
                db.add(AnnouncementRead(announcement_id=ann_id, user_id=user_id))
        await db.flush()

    def _to_item(
        self,
        a: Announcement,
        is_read: bool,
        author: User | None,
    ) -> AnnouncementItem:
        return AnnouncementItem(
            id=a.id,
            title=a.title,
            body=a.body,
            author=AnnouncementAuthorInfo(id=author.id, name=author.name) if author else None,
            target_type=a.target_type,
            target_ids=a.target_ids,
            is_pinned=a.is_pinned,
            expires_at=a.expires_at,
            is_read=is_read,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )


announcement_service = AnnouncementService()
