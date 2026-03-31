from __future__ import annotations
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.access import Feature, Role, RolesFeature, UserRole
from app.models.user import User, UserProfile, UserSession, UserStatus
from app.schemas.user import (
    PaginationMeta,
    UpdateProfileRequest,
    UserCreateRequest,
    UserFeatureResponse,
    UserListItem,
    UserListResponse,
    UserProfileResponse,
    UserRoleResponse,
    UserSessionResponse,
    UserUpdateRequest,
)


class UserService:
    async def list_users(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int,
        per_page: int,
        search: str | None,
        status_filter: UserStatus | None,
    ) -> UserListResponse:
        filters = [
            User.company_id == company_id,
            User.deleted_at.is_(None),
        ]
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.name.ilike(pattern),
                    User.emp_id.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        if status_filter is not None:
            filters.append(User.status == status_filter)

        total_stmt = select(func.count()).select_from(User).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        offset = (page - 1) * per_page
        users_stmt = (
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        users = (await db.execute(users_stmt)).scalars().all()
        user_ids = [user.id for user in users]

        roles_by_user: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
        role_details_by_user: dict[uuid.UUID, list[UserRoleResponse]] = {
            user_id: [] for user_id in user_ids
        }
        if user_ids:
            roles_stmt = (
                select(UserRole.user_id, Role.id, Role.name)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id.in_(user_ids))
                .order_by(Role.name.asc())
            )
            for user_id, role_id, role_name in (await db.execute(roles_stmt)).all():
                roles_by_user.setdefault(user_id, []).append(role_name)
                role_details_by_user.setdefault(user_id, []).append(
                    UserRoleResponse(id=role_id, name=role_name)
                )

        total_pages = math.ceil(total / per_page) if total else 0
        return UserListResponse(
            data=[
                UserListItem(
                    id=user.id,
                    emp_id=user.emp_id,
                    name=user.name,
                    email=user.email,
                    status=user.status,
                    is_company_admin=user.is_company_admin,
                    roles=[] if user.is_company_admin else role_details_by_user.get(user.id, []),
                )
                for user in users
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    async def create_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: UserCreateRequest,
    ) -> User:
        existing_emp_id = await self._get_user_by_emp_id(db, company_id, data.emp_id)
        if existing_emp_id is not None:
            raise ValueError("Employee ID already exists")

        if data.email:
            existing_email = await self._get_user_by_email(db, company_id, data.email)
            if existing_email is not None:
                raise ValueError("Email already exists")

        roles = await self._load_valid_roles(
            db, company_id, [] if data.is_company_admin else data.role_ids
        )

        user = User(
            company_id=company_id,
            emp_id=data.emp_id,
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            is_company_admin=data.is_company_admin,
            status=UserStatus.active,
        )
        db.add(user)
        await db.flush()

        profile = UserProfile(company_id=company_id, user_id=user.id)
        db.add(profile)

        if not data.is_company_admin:
            await self._set_user_roles(db, user.id, roles)

        await db.flush()
        await db.refresh(user)
        return user

    async def update_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UserUpdateRequest,
    ) -> User:
        user = await self._get_user_or_404(db, company_id, user_id)

        if data.emp_id != user.emp_id:
            existing_emp_id = await self._get_user_by_emp_id(db, company_id, data.emp_id)
            if existing_emp_id is not None and existing_emp_id.id != user_id:
                raise ValueError("Employee ID already exists")

        if data.email and data.email != user.email:
            existing_email = await self._get_user_by_email(db, company_id, data.email)
            if existing_email is not None and existing_email.id != user_id:
                raise ValueError("Email already exists")

        roles = await self._load_valid_roles(
            db, company_id, [] if data.is_company_admin else data.role_ids
        )

        user.emp_id = data.emp_id
        user.name = data.name
        user.email = data.email
        if data.password:
            user.password_hash = hash_password(data.password)
        user.status = data.status
        user.is_company_admin = data.is_company_admin

        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        if not data.is_company_admin:
            await self._set_user_roles(db, user.id, roles)

        await db.flush()
        await db.refresh(user)
        return user

    async def delete_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> None:
        if user_id == actor_user_id:
            raise ValueError("You cannot delete your own account")

        user = await self._get_user_or_404(db, company_id, user_id)
        suffix = user.id.hex[:8]

        user.status = UserStatus.terminated
        user.deleted_at = datetime.now(timezone.utc)
        user.emp_id = f"deleted-{suffix}"
        if user.email:
            user.email = f"deleted+{suffix}@deleted.local"

        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        await db.execute(delete(UserSession).where(UserSession.user_id == user_id))
        await db.flush()

    async def get_user_profile(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> UserProfileResponse:
        user = await self._get_user_or_404(db, company_id, user_id)
        profile = await self._get_or_create_profile(db, company_id, user.id)
        roles = await self._get_user_roles(db, user.id)
        features = await self._get_user_features(db, user.id)
        last_login = await self._get_last_login(db, user.id, company_id)
        viewer = await self._get_user_or_404(db, company_id, viewer_id)
        viewer_roles = [] if viewer.is_company_admin else await self._get_user_roles(db, viewer.id)

        can_edit = (
            viewer_id == user_id
            or viewer.is_company_admin
            or any(role.name.strip().lower() in {"hr", "human resources"} for role in viewer_roles)
        )

        return UserProfileResponse(
            id=user.id,
            emp_id=user.emp_id,
            name=user.name,
            email=user.email,
            status=user.status,
            is_company_admin=user.is_company_admin,
            profile_photo_url=user.profile_photo_url,
            phone=profile.phone,
            alt_phone=profile.alt_phone,
            address_line_1=profile.address_line_1,
            address_line_2=profile.address_line_2,
            city=profile.city,
            state=profile.state,
            postal_code=profile.postal_code,
            country=profile.country,
            emergency_contact_name=profile.emergency_contact_name,
            emergency_contact_phone=profile.emergency_contact_phone,
            date_of_birth=profile.date_of_birth,
            date_of_joining=profile.date_of_joining,
            last_login=last_login,
            roles=[UserRoleResponse(id=role.id, name=role.name) for role in roles],
            features=[
                UserFeatureResponse(id=feature.id, code=feature.code, name=feature.name)
                for feature in features
            ],
            can_edit=can_edit,
        )

    async def update_own_profile(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        data: UpdateProfileRequest,
    ) -> UserProfileResponse:
        profile = await self._get_or_create_profile(db, company_id, user_id)

        for field, value in data.model_dump().items():
            setattr(profile, field, value)

        await db.flush()
        return await self.get_user_profile(db, company_id, user_id, user_id)

    async def change_password(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        current: str,
        new: str,
    ) -> None:
        user = await self._get_user_or_404(db, company_id, user_id)
        if not verify_password(current, user.password_hash):
            raise ValueError("Current password is incorrect")

        user.password_hash = hash_password(new)
        await db.flush()

    async def list_active_sessions(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> list[UserSessionResponse]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(
                UserSession.company_id == company_id,
                UserSession.expires_at > now,
                User.deleted_at.is_(None),
            )
            .order_by(UserSession.created_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        return [
            UserSessionResponse(
                id=session.id,
                user_id=user.id,
                user_name=user.name,
                emp_id=user.emp_id,
                email=user.email,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                created_at=session.created_at,
                expires_at=session.expires_at,
            )
            for session, user in rows
        ]

    async def terminate_session(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        stmt = select(UserSession).where(
            UserSession.id == session_id,
            UserSession.company_id == company_id,
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None:
            raise LookupError("Session not found")

        await db.delete(session)
        await db.flush()

    async def _get_user_by_emp_id(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        emp_id: str,
    ) -> User | None:
        stmt = select(User).where(
            User.company_id == company_id,
            User.emp_id == emp_id,
            User.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_user_by_email(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        email: str,
    ) -> User | None:
        stmt = select(User).where(
            User.company_id == company_id,
            User.email == email,
            User.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_user_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        stmt = select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise LookupError("User not found")
        return user

    async def _get_or_create_profile(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserProfile:
        stmt = select(UserProfile).where(
            UserProfile.user_id == user_id,
            UserProfile.company_id == company_id,
            UserProfile.deleted_at.is_(None),
        )
        profile = (await db.execute(stmt)).scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id, company_id=company_id)
            db.add(profile)
            await db.flush()
        return profile

    async def _load_valid_roles(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        role_ids: list[uuid.UUID],
    ) -> list[Role]:
        if not role_ids:
            return []

        stmt = select(Role).where(
            Role.company_id == company_id,
            Role.id.in_(role_ids),
            Role.deleted_at.is_(None),
        )
        roles = (await db.execute(stmt)).scalars().all()
        if len({role.id for role in roles}) != len(set(role_ids)):
            raise ValueError("One or more roles are invalid")
        return roles

    async def _set_user_roles(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        roles: list[Role],
    ) -> None:
        for role in roles:
            db.add(UserRole(user_id=user_id, role_id=role.id))
        await db.flush()

    async def _get_user_roles(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[Role]:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.deleted_at.is_(None),
            )
            .order_by(Role.name.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def _get_user_features(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[Feature]:
        stmt = (
            select(Feature)
            .join(RolesFeature, RolesFeature.feature_id == Feature.id)
            .join(UserRole, UserRole.role_id == RolesFeature.role_id)
            .where(UserRole.user_id == user_id)
            .distinct()
            .order_by(Feature.name.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def _get_last_login(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> datetime | None:
        stmt = select(func.max(UserSession.created_at)).where(
            and_(
                UserSession.user_id == user_id,
                UserSession.company_id == company_id,
            )
        )
        return (await db.execute(stmt)).scalar_one()


user_service = UserService()
