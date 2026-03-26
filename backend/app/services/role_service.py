from __future__ import annotations
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import CompanyFeature, Feature, FeaturePage, Role, RolesFeature, UserRole
from app.schemas.auth import PageInfo
from app.schemas.role import (
    FeatureBundleResponse,
    RoleCreateRequest,
    RoleListResponse,
    RoleUpdateRequest,
)


class RoleService:
    async def list_roles(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> list[RoleListResponse]:
        stmt = (
            select(Role, Feature.code)
            .outerjoin(RolesFeature, RolesFeature.role_id == Role.id)
            .outerjoin(Feature, Feature.id == RolesFeature.feature_id)
            .where(
                Role.company_id == company_id,
                Role.deleted_at.is_(None),
            )
            .order_by(Role.name.asc(), Feature.code.asc())
        )
        rows = (await db.execute(stmt)).all()

        roles_by_id: dict[uuid.UUID, RoleListResponse] = {}
        for role, feature_code in rows:
            item = roles_by_id.get(role.id)
            if item is None:
                item = RoleListResponse(
                    id=role.id,
                    name=role.name,
                    description=role.description,
                    features=[],
                )
                roles_by_id[role.id] = item
            if feature_code is not None:
                item.features.append(feature_code)

        return list(roles_by_id.values())

    async def create_role(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: RoleCreateRequest,
    ) -> Role:
        await self._ensure_role_name_available(db, company_id, data.name)
        features = await self._load_enabled_company_features(db, company_id, data.feature_ids)

        role = Role(
            company_id=company_id,
            name=data.name.strip(),
            description=data.description,
        )
        db.add(role)
        await db.flush()

        await self._set_role_features(db, role.id, features)
        await db.flush()
        await db.refresh(role)
        return role

    async def update_role(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        role_id: uuid.UUID,
        data: RoleUpdateRequest,
    ) -> Role:
        role = await self._get_role_or_404(db, company_id, role_id)
        await self._ensure_role_name_available(db, company_id, data.name, exclude_role_id=role_id)
        features = await self._load_enabled_company_features(db, company_id, data.feature_ids)

        role.name = data.name.strip()
        role.description = data.description

        await db.execute(delete(RolesFeature).where(RolesFeature.role_id == role.id))
        await self._set_role_features(db, role.id, features)

        await db.flush()
        await db.refresh(role)
        return role

    async def delete_role(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> None:
        role = await self._get_role_or_404(db, company_id, role_id)

        assigned_users_stmt = (
            select(func.count())
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.role_id == role_id,
                Role.company_id == company_id,
                Role.deleted_at.is_(None),
            )
        )
        assigned_users = (await db.execute(assigned_users_stmt)).scalar_one()
        if assigned_users > 0:
            raise ValueError("Role is assigned to one or more users")

        await db.delete(role)
        await db.flush()

    async def get_company_features(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> list[FeatureBundleResponse]:
        stmt = (
            select(Feature)
            .join(CompanyFeature, CompanyFeature.feature_id == Feature.id)
            .where(
                CompanyFeature.company_id == company_id,
                CompanyFeature.enabled.is_(True),
            )
            .order_by(Feature.name.asc())
        )
        features = (await db.execute(stmt)).scalars().all()
        return [
            FeatureBundleResponse(id=feature.id, code=feature.code, name=feature.name)
            for feature in features
        ]

    async def get_user_accessible_pages(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        is_admin: bool,
    ) -> list[PageInfo]:
        if is_admin:
            stmt = (
                select(
                    FeaturePage.page_code,
                    FeaturePage.page_name,
                    FeaturePage.route,
                )
                .join(Feature, Feature.id == FeaturePage.feature_id)
                .join(CompanyFeature, CompanyFeature.feature_id == Feature.id)
                .where(
                    CompanyFeature.company_id == company_id,
                    CompanyFeature.enabled.is_(True),
                )
                .distinct()
                .order_by(FeaturePage.page_name.asc())
            )
        else:
            stmt = (
                select(
                    FeaturePage.page_code,
                    FeaturePage.page_name,
                    FeaturePage.route,
                )
                .join(Feature, Feature.id == FeaturePage.feature_id)
                .join(CompanyFeature, CompanyFeature.feature_id == Feature.id)
                .join(RolesFeature, RolesFeature.feature_id == Feature.id)
                .join(UserRole, UserRole.role_id == RolesFeature.role_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    UserRole.user_id == user_id,
                    Role.company_id == company_id,
                    Role.deleted_at.is_(None),
                    CompanyFeature.company_id == company_id,
                    CompanyFeature.enabled.is_(True),
                )
                .distinct()
                .order_by(FeaturePage.page_name.asc())
            )

        rows = (await db.execute(stmt)).all()
        return [
            PageInfo(
                page_code=page_code,
                page_name=page_name,
                route=route,
            )
            for page_code, page_name, route in rows
        ]

    async def _get_role_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> Role:
        stmt = select(Role).where(
            Role.id == role_id,
            Role.company_id == company_id,
            Role.deleted_at.is_(None),
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            raise LookupError("Role not found")
        return role

    async def _ensure_role_name_available(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        name: str,
        exclude_role_id: uuid.UUID | None = None,
    ) -> None:
        normalized_name = name.strip()
        stmt = select(Role).where(
            Role.company_id == company_id,
            Role.name == normalized_name,
            Role.deleted_at.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None and existing.id != exclude_role_id:
            raise ValueError("Role name already exists")

    async def _load_enabled_company_features(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        feature_ids: list[uuid.UUID],
    ) -> list[Feature]:
        if not feature_ids:
            return []

        unique_feature_ids = list(dict.fromkeys(feature_ids))
        stmt = (
            select(Feature)
            .join(CompanyFeature, CompanyFeature.feature_id == Feature.id)
            .where(
                CompanyFeature.company_id == company_id,
                CompanyFeature.enabled.is_(True),
                Feature.id.in_(unique_feature_ids),
            )
        )
        features = (await db.execute(stmt)).scalars().all()
        if len({feature.id for feature in features}) != len(unique_feature_ids):
            raise ValueError("One or more feature IDs are invalid for this company")
        return features

    async def _set_role_features(
        self,
        db: AsyncSession,
        role_id: uuid.UUID,
        features: list[Feature],
    ) -> None:
        for feature in features:
            db.add(RolesFeature(role_id=role_id, feature_id=feature.id))


role_service = RoleService()
