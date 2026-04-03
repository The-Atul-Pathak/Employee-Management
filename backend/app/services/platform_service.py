from __future__ import annotations
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.access import Feature
from app.models.company import Company, CompanyContact, CompanyStatus
from app.models.plan import BillingCycle, CompanySubscription, Plan, PlanFeature
from app.models.platform_admin import PlatformAdmin, PlatformAdminStatus, PlatformSession
from app.models.user import User, UserStatus
from app.services.holiday_service import seed_company_holidays
from app.services.role_seeder import seed_default_roles
from app.schemas.platform import (
    CompanyAdminCreateRequest,
    CompanyCreateRequest,
    CompanyListItem,
    CompanyResponse,
    ContactResponse,
    FeatureCreateRequest,
    FeatureDeleteCheckResponse,
    FeatureListResponse,
    FeatureResponse,
    FeatureUpdateRequest,
    PlanCreateRequest,
    PlanDeleteCheckResponse,
    PlanFeatureItem,
    PlanListResponse,
    PlanResponse,
    PlanUpdateRequest,
    PlanUsageItem,
    PlatformAdminInfo,
    PlatformLoginResponse,
    SubscriptionResponse,
    SubscriptionUpsertRequest,
    CompanyUpdateRequest,
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PlatformService:
    # ─── Auth ─────────────────────────────────────────────────────────────────

    async def login(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[PlatformLoginResponse, str]:
        result = await db.execute(
            select(PlatformAdmin).where(PlatformAdmin.email == email)
        )
        admin = result.scalar_one_or_none()

        if admin is None or not verify_password(password, admin.password_hash):
            raise ValueError("Invalid credentials")

        if admin.status != PlatformAdminStatus.active:
            raise ValueError("Account is inactive")

        refresh_token = create_refresh_token(
            {"sub": str(admin.id), "scope": "platform"}
        )
        refresh_hash = _hash_token(refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        session = PlatformSession(
            admin_id=admin.id,
            refresh_token_hash=refresh_hash,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        db.add(session)

        admin.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)

        access_token = create_access_token(
            {
                "sub": str(admin.id),
                "sid": str(session.id),
                "scope": "platform",
            }
        )

        return (
            PlatformLoginResponse(
                access_token=access_token,
                admin=PlatformAdminInfo(
                    id=admin.id,
                    name=admin.name,
                    email=admin.email,
                    role=admin.role.value,
                ),
            ),
            refresh_token,
        )

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> str:
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid refresh token")

        if payload.get("type") != "refresh" or payload.get("scope") != "platform":
            raise ValueError("Invalid token")

        refresh_hash = _hash_token(refresh_token)
        result = await db.execute(
            select(PlatformSession).where(
                PlatformSession.refresh_token_hash == refresh_hash,
                PlatformSession.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Session not found or expired")

        admin_result = await db.execute(
            select(PlatformAdmin).where(PlatformAdmin.id == session.admin_id)
        )
        admin = admin_result.scalar_one_or_none()
        if admin is None or admin.status != PlatformAdminStatus.active:
            raise ValueError("Admin account is inactive")

        return create_access_token(
            {"sub": str(admin.id), "sid": str(session.id), "scope": "platform"}
        )

    async def logout(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        result = await db.execute(
            select(PlatformSession).where(PlatformSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()

    # ─── Companies ────────────────────────────────────────────────────────────

    async def list_companies(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(Company)
            .options(selectinload(Company.contacts))
            .where(Company.deleted_at.is_(None))
            .order_by(Company.created_at.desc())
        )
        companies = result.scalars().all()

        items = []
        for c in companies:
            primary = next((ct for ct in c.contacts if ct.is_primary), None)
            items.append(
                CompanyListItem(
                    id=c.id,
                    company_name=c.company_name,
                    industry=c.industry,
                    status=c.status,
                    created_at=c.created_at,
                    primary_contact_name=primary.name if primary else None,
                    primary_contact_email=primary.email if primary else None,
                )
            )
        return {"data": items, "total": len(items)}

    async def create_company(
        self, db: AsyncSession, body: CompanyCreateRequest
    ) -> CompanyResponse:
        company = Company(
            company_name=body.company_name,
            legal_name=body.legal_name,
            industry=body.industry,
            domain=body.domain,
            employee_size_range=body.employee_size_range,
            status=CompanyStatus.trial,
        )
        db.add(company)
        await db.flush()

        contact = CompanyContact(
            company_id=company.id,
            name=body.primary_contact.name,
            email=body.primary_contact.email,
            phone=body.primary_contact.phone,
            is_primary=True,
        )
        db.add(contact)
        await db.flush()

        await seed_default_roles(company.id, db)
        await seed_company_holidays(company.id, db)

        await db.commit()
        company = await self._get_company_with_contacts(db, company.id)
        return await self._company_response(db, company)

    async def get_company(
        self, db: AsyncSession, company_id: uuid.UUID
    ) -> CompanyResponse:
        result = await db.execute(
            select(Company)
            .options(selectinload(Company.contacts))
            .where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        company = result.scalar_one_or_none()
        if company is None:
            raise ValueError("Company not found")
        return await self._company_response(db, company)

    async def update_company(
        self, db: AsyncSession, company_id: uuid.UUID, body: CompanyUpdateRequest
    ) -> CompanyResponse:
        result = await db.execute(
            select(Company)
            .options(selectinload(Company.contacts))
            .where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        company = result.scalar_one_or_none()
        if company is None:
            raise ValueError("Company not found")

        company.company_name = body.company_name
        company.legal_name = body.legal_name
        company.industry = body.industry
        company.domain = body.domain
        company.employee_size_range = body.employee_size_range
        company.status = body.status

        await db.commit()
        company = await self._get_company_with_contacts(db, company.id)
        return await self._company_response(db, company)

    async def _get_company_with_contacts(
        self, db: AsyncSession, company_id: uuid.UUID
    ) -> Company:
        result = await db.execute(
            select(Company)
            .options(selectinload(Company.contacts))
            .where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        company = result.scalar_one_or_none()
        if company is None:
            raise ValueError("Company not found")
        return company

    async def _company_response(
        self, db: AsyncSession, company: Company
    ) -> CompanyResponse:
        sub_result = await db.execute(
            select(CompanySubscription, Plan)
            .join(Plan, Plan.id == CompanySubscription.plan_id)
            .where(
                CompanySubscription.company_id == company.id,
                CompanySubscription.is_active.is_(True),
            )
            .order_by(CompanySubscription.created_at.desc())
            .limit(1)
        )
        row = sub_result.first()
        subscription = None
        if row:
            cs, plan = row
            subscription = SubscriptionResponse(
                id=cs.id,
                plan_id=cs.plan_id,
                plan_name=plan.name,
                billing_cycle=cs.billing_cycle,
                start_date=cs.start_date,
                is_active=cs.is_active,
            )

        return CompanyResponse(
            id=company.id,
            company_name=company.company_name,
            legal_name=company.legal_name,
            industry=company.industry,
            domain=company.domain,
            employee_size_range=company.employee_size_range,
            status=company.status,
            created_at=company.created_at,
            contacts=[
                ContactResponse(
                    id=ct.id,
                    name=ct.name,
                    email=ct.email,
                    phone=ct.phone,
                    is_primary=ct.is_primary,
                )
                for ct in company.contacts
            ],
            subscription=subscription,
        )

    # ─── Company Admin ────────────────────────────────────────────────────────

    async def create_company_admin(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        body: CompanyAdminCreateRequest,
    ) -> dict:
        result = await db.execute(
            select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Company not found")

        existing = await db.execute(
            select(User).where(
                User.company_id == company_id,
                User.email == body.email,
                User.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("A user with this email already exists in the company")

        user = User(
            company_id=company_id,
            emp_id=body.emp_id,
            name=body.name,
            email=body.email,
            password_hash=hash_password(body.password),
            is_company_admin=True,
            status=UserStatus.active,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {"id": user.id, "name": user.name, "email": user.email}

    # ─── Subscription ─────────────────────────────────────────────────────────

    async def upsert_subscription(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        body: SubscriptionUpsertRequest,
    ) -> SubscriptionResponse:
        result = await db.execute(
            select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Company not found")

        plan_result = await db.execute(
            select(Plan).where(Plan.id == body.plan_id, Plan.deleted_at.is_(None))
        )
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            raise ValueError("Plan not found")

        # Deactivate existing subscriptions
        existing_result = await db.execute(
            select(CompanySubscription).where(
                CompanySubscription.company_id == company_id,
                CompanySubscription.is_active.is_(True),
            )
        )
        for old_sub in existing_result.scalars().all():
            old_sub.is_active = False

        new_sub = CompanySubscription(
            company_id=company_id,
            plan_id=body.plan_id,
            billing_cycle=body.billing_cycle,
            start_date=body.start_date,
            is_active=True,
        )
        db.add(new_sub)
        await db.flush()

        await seed_default_roles(company_id, db)

        await db.commit()
        await db.refresh(new_sub)

        return SubscriptionResponse(
            id=new_sub.id,
            plan_id=new_sub.plan_id,
            plan_name=plan.name,
            billing_cycle=new_sub.billing_cycle,
            start_date=new_sub.start_date,
            is_active=new_sub.is_active,
        )

    # ─── Plans ────────────────────────────────────────────────────────────────

    async def list_plans(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(Plan).where(Plan.deleted_at.is_(None)).order_by(Plan.name.asc())
        )
        plans = result.scalars().all()
        return {
            "data": [await self._plan_response(db, p) for p in plans],
            "total": len(plans),
        }

    async def create_plan(self, db: AsyncSession, body: PlanCreateRequest) -> PlanResponse:
        existing = await db.execute(
            select(Plan).where(Plan.name == body.name, Plan.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ValueError("A plan with this name already exists")

        feature_ids = list(dict.fromkeys(body.feature_ids))
        await self._validate_feature_ids(db, feature_ids)

        plan = Plan(
            name=body.name,
            description=body.description,
            monthly_price=body.monthly_price,
            yearly_price=body.yearly_price,
            max_employees=body.max_employees,
        )
        db.add(plan)
        await db.flush()

        for fid in feature_ids:
            db.add(PlanFeature(plan_id=plan.id, feature_id=fid))

        await db.commit()
        await db.refresh(plan)
        return await self._plan_response(db, plan)

    async def update_plan(
        self, db: AsyncSession, plan_id: uuid.UUID, body: PlanUpdateRequest
    ) -> PlanResponse:
        result = await db.execute(
            select(Plan).where(Plan.id == plan_id, Plan.deleted_at.is_(None))
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise ValueError("Plan not found")

        duplicate = await db.execute(
            select(Plan).where(
                Plan.name == body.name,
                Plan.deleted_at.is_(None),
                Plan.id != plan_id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise ValueError("A plan with this name already exists")

        feature_ids = list(dict.fromkeys(body.feature_ids))
        await self._validate_feature_ids(db, feature_ids)

        plan.name = body.name
        plan.description = body.description
        plan.monthly_price = body.monthly_price
        plan.yearly_price = body.yearly_price
        plan.max_employees = body.max_employees

        # Replace plan features
        await db.execute(delete(PlanFeature).where(PlanFeature.plan_id == plan_id))
        for fid in feature_ids:
            db.add(PlanFeature(plan_id=plan.id, feature_id=fid))

        await db.commit()
        await db.refresh(plan)
        return await self._plan_response(db, plan)

    async def _plan_response(self, db: AsyncSession, plan: Plan) -> PlanResponse:
        features_result = await db.execute(
            select(Feature)
            .join(PlanFeature, PlanFeature.feature_id == Feature.id)
            .where(PlanFeature.plan_id == plan.id)
            .order_by(Feature.name.asc())
        )
        features = features_result.scalars().all()
        return PlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            monthly_price=plan.monthly_price,
            yearly_price=plan.yearly_price,
            max_employees=plan.max_employees,
            created_at=plan.created_at,
            features=[PlanFeatureItem(id=f.id, code=f.code, name=f.name) for f in features],
        )

    async def _validate_feature_ids(
        self, db: AsyncSession, feature_ids: list[uuid.UUID]
    ) -> None:
        if not feature_ids:
            return
        result = await db.execute(
            select(func.count()).select_from(Feature).where(Feature.id.in_(feature_ids))
        )
        count = result.scalar_one()
        if count != len(feature_ids):
            raise ValueError("One or more feature IDs are invalid")

    async def check_plan_usage(
        self, db: AsyncSession, plan_id: uuid.UUID
    ) -> PlanDeleteCheckResponse:
        result = await db.execute(
            select(CompanySubscription, Company)
            .join(Company, Company.id == CompanySubscription.company_id)
            .where(
                CompanySubscription.plan_id == plan_id,
                CompanySubscription.is_active.is_(True),
                Company.deleted_at.is_(None),
            )
        )
        rows = result.all()
        affected = [
            PlanUsageItem(company_id=company.id, company_name=company.company_name)
            for _, company in rows
        ]
        return PlanDeleteCheckResponse(can_delete=len(affected) == 0, affected_companies=affected)

    async def delete_plan(self, db: AsyncSession, plan_id: uuid.UUID) -> None:
        usage = await self.check_plan_usage(db, plan_id)
        if not usage.can_delete:
            raise ValueError("Plan is in use by active company subscriptions")

        result = await db.execute(
            select(Plan).where(Plan.id == plan_id, Plan.deleted_at.is_(None))
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise ValueError("Plan not found")

        plan.deleted_at = datetime.now(timezone.utc)
        await db.commit()

    # ─── Features ─────────────────────────────────────────────────────────────

    async def list_features(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(Feature).order_by(Feature.code.asc())
        )
        features = result.scalars().all()
        return {
            "data": [FeatureResponse.model_validate(f) for f in features],
            "total": len(features),
        }

    async def create_feature(
        self, db: AsyncSession, body: FeatureCreateRequest
    ) -> FeatureResponse:
        existing = await db.execute(
            select(Feature).where(Feature.code == body.code)
        )
        if existing.scalar_one_or_none():
            raise ValueError("A feature with this code already exists")

        feature = Feature(code=body.code, name=body.name, description=body.description)
        db.add(feature)
        await db.commit()
        await db.refresh(feature)
        return FeatureResponse.model_validate(feature)

    async def update_feature(
        self, db: AsyncSession, feature_id: uuid.UUID, body: FeatureUpdateRequest
    ) -> FeatureResponse:
        result = await db.execute(
            select(Feature).where(Feature.id == feature_id)
        )
        feature = result.scalar_one_or_none()
        if feature is None:
            raise ValueError("Feature not found")

        feature.name = body.name
        feature.description = body.description
        await db.commit()
        await db.refresh(feature)
        return FeatureResponse.model_validate(feature)

    async def check_feature_usage(
        self, db: AsyncSession, feature_id: uuid.UUID
    ) -> FeatureDeleteCheckResponse:
        result = await db.execute(
            select(Plan.name)
            .join(PlanFeature, PlanFeature.plan_id == Plan.id)
            .where(
                PlanFeature.feature_id == feature_id,
                Plan.deleted_at.is_(None),
            )
        )
        plan_names = [row[0] for row in result.all()]
        return FeatureDeleteCheckResponse(
            can_delete=len(plan_names) == 0,
            affected_plans=plan_names,
        )

    async def delete_feature(self, db: AsyncSession, feature_id: uuid.UUID) -> None:
        usage = await self.check_feature_usage(db, feature_id)
        if not usage.can_delete:
            raise ValueError("Feature is used in one or more plans")

        result = await db.execute(
            select(Feature).where(Feature.id == feature_id)
        )
        feature = result.scalar_one_or_none()
        if feature is None:
            raise ValueError("Feature not found")

        await db.delete(feature)
        await db.commit()

    # ─── Dashboard stats ──────────────────────────────────────────────────────

    async def get_stats(self, db: AsyncSession) -> dict:
        total_companies = await db.scalar(
            select(func.count(Company.id)).where(Company.deleted_at.is_(None))
        )
        active_companies = await db.scalar(
            select(func.count(Company.id)).where(
                Company.deleted_at.is_(None), Company.status == CompanyStatus.active
            )
        )
        total_plans = await db.scalar(
            select(func.count(Plan.id)).where(Plan.deleted_at.is_(None))
        )
        total_features = await db.scalar(select(func.count(Feature.id)))

        return {
            "total_companies": total_companies or 0,
            "active_companies": active_companies or 0,
            "total_plans": total_plans or 0,
            "total_features": total_features or 0,
        }


platform_service = PlatformService()
