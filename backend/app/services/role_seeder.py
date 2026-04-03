from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Feature, Role, RolesFeature
from app.models.plan import CompanySubscription, Plan, PlanFeature

# Pre-made role definitions: name, description, and feature codes to assign.
# Feature codes must match the codes in the features table (seeded via seed.py / platform admin).
_ROLE_DEFINITIONS: list[dict] = [
    {
        "name": "HR Manager",
        "description": "Full HR department head with complete HR operations access.",
        "features": [
            "USER_MGMT",
            "ATTENDANCE",
            "LEAVE",
            "PAYROLL",
            "DOCUMENTS",
            "ANNOUNCEMENTS",
            "REPORTS",
            "ONBOARDING",
            "OFFBOARDING",
            "PERFORMANCE",
        ],
    },
    {
        "name": "HR Executive",
        "description": "Day-to-day HR operations. Cannot create users or run payroll.",
        "features": ["ATTENDANCE", "LEAVE", "DOCUMENTS", "REPORTS"],
    },
    {
        "name": "Team Lead",
        "description": "First-level manager who oversees a direct team.",
        "features": ["TEAM", "ATTENDANCE", "LEAVE", "TASK", "PROJECT", "ANNOUNCEMENTS"],
    },
    {
        "name": "Sales Manager",
        "description": "Sales department head managing pipeline and reps.",
        "features": ["CRM", "PROJECT", "TASK", "REPORTS", "EXPENSE"],
    },
    {
        "name": "Sales Executive",
        "description": "Individual sales contributor.",
        "features": ["CRM", "TASK", "LEAVE", "ATTENDANCE", "EXPENSE"],
    },
    {
        "name": "Project Manager",
        "description": "Manages project delivery. No HR access, no CRM access.",
        "features": ["PROJECT", "TASK", "TEAM", "REPORTS", "LEAVE", "ATTENDANCE"],
    },
    {
        "name": "Developer",
        "description": "Individual contributor executing tasks within projects.",
        "features": ["TASK", "PROJECT", "LEAVE", "ATTENDANCE", "DOCUMENTS"],
    },
    {
        "name": "Finance",
        "description": "Finance team member with payroll and expense visibility.",
        "features": ["PAYROLL", "EXPENSE", "REPORTS", "USER_MGMT"],
    },
    {
        "name": "Employee",
        "description": "Default role for all staff. Pure self-service.",
        "features": ["ATTENDANCE", "LEAVE", "TASK", "DOCUMENTS", "PAYROLL", "EXPENSE"],
    },
]


async def seed_default_roles(company_id: uuid.UUID, db: AsyncSession) -> None:
    """Create the 9 pre-made roles for a company and assign their enabled features.

    Idempotent:
    - Roles that already exist by name are not re-created.
    - Feature assignments that already exist are not duplicated.
    - Features not enabled for the company's subscription plan are skipped.
    """
    enabled_features = await _get_company_enabled_features(company_id, db)
    enabled_by_code: dict[str, uuid.UUID] = {f.code: f.id for f in enabled_features}

    for role_def in _ROLE_DEFINITIONS:
        role = await _get_or_create_role(db, company_id, role_def)
        await _assign_missing_features(db, role.id, role_def["features"], enabled_by_code)

    await db.flush()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


async def _get_company_enabled_features(
    company_id: uuid.UUID, db: AsyncSession
) -> list[Feature]:
    """Return Feature rows that are available to the company via its active plan."""
    stmt = (
        select(Feature)
        .join(PlanFeature, PlanFeature.feature_id == Feature.id)
        .join(Plan, Plan.id == PlanFeature.plan_id)
        .join(CompanySubscription, CompanySubscription.plan_id == Plan.id)
        .where(
            CompanySubscription.company_id == company_id,
            CompanySubscription.is_active.is_(True),
            Plan.deleted_at.is_(None),
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def _get_or_create_role(
    db: AsyncSession,
    company_id: uuid.UUID,
    role_def: dict,
) -> Role:
    stmt = select(Role).where(
        Role.company_id == company_id,
        Role.name == role_def["name"],
        Role.deleted_at.is_(None),
    )
    role = (await db.execute(stmt)).scalar_one_or_none()
    if role is None:
        role = Role(
            company_id=company_id,
            name=role_def["name"],
            description=role_def.get("description"),
        )
        db.add(role)
        await db.flush()
    return role


async def _assign_missing_features(
    db: AsyncSession,
    role_id: uuid.UUID,
    feature_codes: list[str],
    enabled_by_code: dict[str, uuid.UUID],
) -> None:
    """Add RolesFeature rows for any feature not already assigned to the role."""
    # Load existing assignments for this role in one query.
    existing_stmt = select(RolesFeature.feature_id).where(RolesFeature.role_id == role_id)
    already_assigned: set[uuid.UUID] = set(
        (await db.execute(existing_stmt)).scalars().all()
    )

    for code in feature_codes:
        feature_id = enabled_by_code.get(code)
        if feature_id is None:
            # Feature not in company's plan — skip.
            continue
        if feature_id in already_assigned:
            # Already assigned — skip.
            continue
        db.add(RolesFeature(role_id=role_id, feature_id=feature_id))
        already_assigned.add(feature_id)
