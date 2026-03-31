from __future__ import annotations
import math
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.crm import Lead, LeadInteraction, LeadStatus
from app.models.notification import NotificationType
from app.models.project import Project, ProjectStatus
from app.models.user import User, UserStatus


def _get_notification_service():
    from app.services.notification_service import notification_service
    return notification_service
from app.schemas.lead import (
    LeadCreateRequest,
    LeadInteractionCreateRequest,
    LeadInteractionResponse,
    LeadListItem,
    LeadListResponse,
    LeadUpdateRequest,
    TodaysFollowupsResponse,
)
from app.schemas.user import PaginationMeta


class LeadService:
    async def create_lead(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        created_by: uuid.UUID,
        data: LeadCreateRequest,
    ) -> Lead:
        await self._ensure_active_user(db, company_id, created_by)
        assigned_user = await self._load_active_user(db, company_id, data.assigned_to)

        lead = Lead(
            company_id=company_id,
            client_name=data.client_name.strip(),
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            status=LeadStatus.new,
            source=data.source,
            notes=data.notes,
            assigned_to=assigned_user.id if assigned_user else None,
            created_by=created_by,
            next_follow_up_date=data.next_follow_up_date,
            project_created=False,
        )
        db.add(lead)
        await db.flush()
        await db.refresh(lead)

        # Notify assigned user
        if lead.assigned_to is not None and lead.assigned_to != created_by:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=lead.assigned_to,
                title="New Lead Assigned",
                message=f"You have been assigned a new lead: '{lead.client_name}'.",
                notification_type=NotificationType.lead_assigned,
                entity_type="lead",
                entity_id=lead.id,
            )

        return lead

    async def list_leads(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int,
        per_page: int,
        status_filter: LeadStatus | None,
        assigned_to_filter: uuid.UUID | None,
        search: str | None,
    ) -> LeadListResponse:
        assigned_user = aliased(User)
        filters = [
            Lead.company_id == company_id,
            Lead.deleted_at.is_(None),
        ]

        if status_filter is not None:
            filters.append(Lead.status == status_filter)
        if assigned_to_filter is not None:
            filters.append(Lead.assigned_to == assigned_to_filter)
        normalized_search = search.strip() if search else None
        if normalized_search:
            pattern = f"%{normalized_search}%"
            filters.append(
                or_(
                    Lead.client_name.ilike(pattern),
                    Lead.contact_email.ilike(pattern),
                    Lead.contact_phone.ilike(pattern),
                    Lead.source.ilike(pattern),
                    Lead.notes.ilike(pattern),
                )
            )

        total_stmt = select(func.count()).select_from(Lead).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Lead, assigned_user.name)
            .outerjoin(assigned_user, assigned_user.id == Lead.assigned_to)
            .where(*filters)
            .order_by(Lead.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await db.execute(stmt)).all()

        return LeadListResponse(
            data=[
                self._build_lead_item(lead=lead, assigned_to_name=assigned_to_name)
                for lead, assigned_to_name in rows
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_todays_followups(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        is_company_admin: bool,
    ) -> TodaysFollowupsResponse:
        await self._ensure_active_user(db, company_id, user_id)
        assigned_user = aliased(User)
        today = date.today()
        filters = [
            Lead.company_id == company_id,
            Lead.deleted_at.is_(None),
            Lead.next_follow_up_date == today,
        ]
        if not is_company_admin:
            filters.append(Lead.assigned_to == user_id)
        stmt = (
            select(Lead, assigned_user.name)
            .outerjoin(assigned_user, assigned_user.id == Lead.assigned_to)
            .where(*filters)
            .order_by(Lead.created_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        items = [
            self._build_lead_item(lead=lead, assigned_to_name=assigned_to_name)
            for lead, assigned_to_name in rows
        ]
        return TodaysFollowupsResponse(data=items, total=len(items))

    async def update_lead(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        lead_id: uuid.UUID,
        data: LeadUpdateRequest,
    ) -> Lead:
        lead = await self._get_lead_or_404(db, company_id, lead_id)
        updates = data.model_dump(exclude_unset=True)
        previous_status = lead.status
        previous_assigned_to = lead.assigned_to

        if "assigned_to" in updates:
            assigned_user = await self._load_active_user(db, company_id, data.assigned_to)
            lead.assigned_to = assigned_user.id if assigned_user else None

        if "client_name" in updates and data.client_name is not None:
            lead.client_name = data.client_name.strip()
        if "contact_email" in updates:
            lead.contact_email = data.contact_email
        if "contact_phone" in updates:
            lead.contact_phone = data.contact_phone
        if "source" in updates:
            lead.source = data.source
        if "status" in updates and data.status is not None:
            lead.status = data.status
        if "next_follow_up_date" in updates:
            lead.next_follow_up_date = data.next_follow_up_date
        if "notes" in updates:
            lead.notes = data.notes

        if previous_status != LeadStatus.won and lead.status == LeadStatus.won:
            existing_project_stmt = select(Project).where(
                Project.company_id == company_id,
                Project.lead_id == lead.id,
                Project.deleted_at.is_(None),
            )
            existing_project = (await db.execute(existing_project_stmt)).scalar_one_or_none()
            if existing_project is None and not lead.project_created:
                db.add(
                    Project(
                        company_id=company_id,
                        lead_id=lead.id,
                        project_name=f"{lead.client_name.strip()} Project",
                        status=ProjectStatus.unassigned,
                    )
                )
            lead.project_created = True

        await db.flush()
        await db.refresh(lead)

        # Notify newly assigned user if assignment changed
        if (
            "assigned_to" in updates
            and lead.assigned_to is not None
            and lead.assigned_to != previous_assigned_to
        ):
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=lead.assigned_to,
                title="Lead Assigned to You",
                message=f"You have been assigned the lead: '{lead.client_name}'.",
                notification_type=NotificationType.lead_assigned,
                entity_type="lead",
                entity_id=lead.id,
            )

        return lead

    async def log_interaction(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        lead_id: uuid.UUID,
        user_id: uuid.UUID,
        data: LeadInteractionCreateRequest,
    ) -> LeadInteraction:
        lead = await self._get_lead_or_404(db, company_id, lead_id)
        await self._ensure_active_user(db, company_id, user_id)

        interaction_time = data.interaction_at or datetime.now(timezone.utc)
        interaction = LeadInteraction(
            lead_id=lead.id,
            interaction_type=data.interaction_type.strip(),
            description=data.description.strip(),
            logged_by=user_id,
            interaction_at=interaction_time,
        )
        db.add(interaction)
        lead.last_interaction_at = interaction_time

        await db.flush()
        await db.refresh(interaction)
        return interaction

    async def get_interactions(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> list[LeadInteractionResponse]:
        await self._get_lead_or_404(db, company_id, lead_id)
        logger = aliased(User)
        stmt = (
            select(LeadInteraction, logger.name)
            .join(logger, logger.id == LeadInteraction.logged_by)
            .where(LeadInteraction.lead_id == lead_id)
            .order_by(LeadInteraction.interaction_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        return [
            LeadInteractionResponse(
                id=interaction.id,
                lead_id=interaction.lead_id,
                interaction_type=interaction.interaction_type,
                description=interaction.description,
                logged_by=interaction.logged_by,
                logged_by_name=logged_by_name,
                interaction_at=interaction.interaction_at,
                created_at=interaction.created_at,
            )
            for interaction, logged_by_name in rows
        ]

    async def _get_lead_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> Lead:
        stmt = select(Lead).where(
            Lead.id == lead_id,
            Lead.company_id == company_id,
            Lead.deleted_at.is_(None),
        )
        lead = (await db.execute(stmt)).scalar_one_or_none()
        if lead is None:
            raise LookupError("Lead not found")
        return lead

    async def _load_active_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> User | None:
        if user_id is None:
            return None
        stmt = select(User).where(
            User.id == user_id,
            User.company_id == company_id,
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise LookupError("User not found")
        return user

    async def _ensure_active_user(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        await self._load_active_user(db, company_id, user_id)

    @staticmethod
    def _build_lead_item(lead: Lead, assigned_to_name: str | None) -> LeadListItem:
        return LeadListItem(
            id=lead.id,
            client_name=lead.client_name,
            contact_email=lead.contact_email,
            contact_phone=lead.contact_phone,
            status=lead.status,
            source=lead.source,
            notes=lead.notes,
            assigned_to=lead.assigned_to,
            assigned_to_name=assigned_to_name,
            created_by=lead.created_by,
            next_follow_up_date=lead.next_follow_up_date,
            last_interaction_at=lead.last_interaction_at,
            project_created=lead.project_created,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )


lead_service = LeadService()
