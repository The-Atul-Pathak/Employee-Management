from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetAssignment, AssetStatus
from app.models.user import User
from app.schemas.asset import (
    AssetAssignmentItem,
    AssetAssignRequest,
    AssetCreate,
    AssetDetail,
    AssetItem,
    AssetListResponse,
    AssetReturnRequest,
    AssetUpdate,
    AssetUserInfo,
)
from app.schemas.user import PaginationMeta


class AssetService:
    async def _get_user(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    async def list_assets(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> AssetListResponse:
        filters = [Asset.company_id == company_id, Asset.deleted_at.is_(None)]

        total_stmt = select(func.count()).select_from(Asset).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Asset)
            .where(*filters)
            .order_by(Asset.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        assets = (await db.execute(stmt)).scalars().all()

        # Get current assignees
        asset_ids = [a.id for a in assets]
        assignees: dict[uuid.UUID, User] = {}
        if asset_ids:
            assign_stmt = select(AssetAssignment).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.returned_at.is_(None),
            )
            assignments = (await db.execute(assign_stmt)).scalars().all()
            emp_ids = {a.employee_id for a in assignments}
            if emp_ids:
                user_stmt = select(User).where(User.id.in_(emp_ids))
                emp_map: dict[uuid.UUID, User] = {}
                for u in (await db.execute(user_stmt)).scalars().all():
                    emp_map[u.id] = u
                for a in assignments:
                    assignees[a.asset_id] = emp_map.get(a.employee_id)  # type: ignore

        return AssetListResponse(
            data=[self._to_item(a, assignees.get(a.id)) for a in assets],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_asset_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> AssetDetail:
        stmt = select(Asset).where(
            Asset.id == asset_id, Asset.company_id == company_id, Asset.deleted_at.is_(None)
        )
        asset = (await db.execute(stmt)).scalar_one_or_none()
        if asset is None:
            raise LookupError("Asset not found")

        assign_stmt = (
            select(AssetAssignment)
            .where(AssetAssignment.asset_id == asset_id)
            .order_by(AssetAssignment.assigned_at.desc())
        )
        assignments = (await db.execute(assign_stmt)).scalars().all()

        user_ids = {a.employee_id for a in assignments} | {a.assigned_by for a in assignments if a.assigned_by}
        users: dict[uuid.UUID, User] = {}
        if user_ids:
            user_stmt = select(User).where(User.id.in_(user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        current_assignee = None
        for a in assignments:
            if a.returned_at is None:
                current_assignee = users.get(a.employee_id)
                break

        history = [
            AssetAssignmentItem(
                id=a.id,
                employee=self._user_info(users.get(a.employee_id)),
                assigned_by=self._user_info(users.get(a.assigned_by) if a.assigned_by else None),
                assigned_at=a.assigned_at,
                returned_at=a.returned_at,
                condition_out=a.condition_out,
                condition_in=a.condition_in,
                notes=a.notes,
            )
            for a in assignments
        ]

        return AssetDetail(
            **self._to_item(asset, current_assignee).__dict__,
            assignment_history=history,
        )

    async def create_asset(
        self, db: AsyncSession, company_id: uuid.UUID, data: AssetCreate
    ) -> AssetItem:
        asset = Asset(
            company_id=company_id,
            asset_tag=data.asset_tag,
            name=data.name,
            category=data.category,
            brand=data.brand,
            model=data.model,
            serial_number=data.serial_number,
            purchase_date=data.purchase_date,
            purchase_price=data.purchase_price,
            notes=data.notes,
            status=AssetStatus.available,
        )
        db.add(asset)
        await db.flush()
        return self._to_item(asset, None)

    async def update_asset(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        asset_id: uuid.UUID,
        data: AssetUpdate,
    ) -> AssetItem:
        stmt = select(Asset).where(
            Asset.id == asset_id, Asset.company_id == company_id, Asset.deleted_at.is_(None)
        )
        asset = (await db.execute(stmt)).scalar_one_or_none()
        if asset is None:
            raise LookupError("Asset not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(asset, field, value)
        await db.flush()
        return self._to_item(asset, None)

    async def delete_asset(
        self, db: AsyncSession, company_id: uuid.UUID, asset_id: uuid.UUID
    ) -> None:
        stmt = select(Asset).where(
            Asset.id == asset_id, Asset.company_id == company_id, Asset.deleted_at.is_(None)
        )
        asset = (await db.execute(stmt)).scalar_one_or_none()
        if asset is None:
            raise LookupError("Asset not found")
        asset.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    async def assign_asset(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        asset_id: uuid.UUID,
        assigner_id: uuid.UUID,
        data: AssetAssignRequest,
    ) -> AssetItem:
        stmt = select(Asset).where(
            Asset.id == asset_id, Asset.company_id == company_id, Asset.deleted_at.is_(None)
        )
        asset = (await db.execute(stmt)).scalar_one_or_none()
        if asset is None:
            raise LookupError("Asset not found")
        if asset.status == AssetStatus.assigned:
            raise ValueError("Asset is already assigned")

        assignment = AssetAssignment(
            company_id=company_id,
            asset_id=asset_id,
            employee_id=data.employee_id,
            assigned_by=assigner_id,
            condition_out=data.condition_out,
            notes=data.notes,
        )
        db.add(assignment)
        asset.status = AssetStatus.assigned
        await db.flush()

        emp = await self._get_user(db, data.employee_id)
        return self._to_item(asset, emp)

    async def return_asset(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        asset_id: uuid.UUID,
        data: AssetReturnRequest,
    ) -> AssetItem:
        stmt = select(Asset).where(
            Asset.id == asset_id, Asset.company_id == company_id, Asset.deleted_at.is_(None)
        )
        asset = (await db.execute(stmt)).scalar_one_or_none()
        if asset is None:
            raise LookupError("Asset not found")
        if asset.status != AssetStatus.assigned:
            raise ValueError("Asset is not currently assigned")

        assign_stmt = select(AssetAssignment).where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.returned_at.is_(None),
        )
        assignment = (await db.execute(assign_stmt)).scalar_one_or_none()
        if assignment:
            assignment.returned_at = datetime.now(timezone.utc)
            assignment.condition_in = data.condition_in
            if data.notes:
                assignment.notes = data.notes

        asset.status = AssetStatus.available
        await db.flush()
        return self._to_item(asset, None)

    async def get_employee_assets(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> list[AssetItem]:
        assign_stmt = select(AssetAssignment).where(
            AssetAssignment.company_id == company_id,
            AssetAssignment.employee_id == employee_id,
            AssetAssignment.returned_at.is_(None),
        )
        assignments = (await db.execute(assign_stmt)).scalars().all()
        asset_ids = [a.asset_id for a in assignments]

        if not asset_ids:
            return []

        asset_stmt = select(Asset).where(Asset.id.in_(asset_ids), Asset.deleted_at.is_(None))
        assets = (await db.execute(asset_stmt)).scalars().all()

        emp = await self._get_user(db, employee_id)
        return [self._to_item(a, emp) for a in assets]

    def _user_info(self, u: User | None) -> AssetUserInfo | None:
        if u is None:
            return None
        return AssetUserInfo(id=u.id, name=u.name, emp_id=u.emp_id)

    def _to_item(self, a: Asset, assignee: User | None) -> AssetItem:
        return AssetItem(
            id=a.id,
            asset_tag=a.asset_tag,
            name=a.name,
            category=a.category,
            brand=a.brand,
            model=a.model,
            serial_number=a.serial_number,
            purchase_date=a.purchase_date,
            purchase_price=float(a.purchase_price) if a.purchase_price else None,
            status=a.status,
            notes=a.notes,
            current_assignee=self._user_info(assignee),
            created_at=a.created_at,
        )


asset_service = AssetService()
