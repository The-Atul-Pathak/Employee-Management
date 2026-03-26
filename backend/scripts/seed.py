"""
Seed script for development test data.

Run from the backend directory:
    python -m scripts.seed

Idempotent — safe to run multiple times; existing records are skipped.

NOTE: There is no Team model in the current schema. The team concept is
represented here as a comment block and will be wired up once the Team
table/model is added to the codebase.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timezone, datetime
from pathlib import Path

# Ensure the backend package root is on sys.path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.access import (
    CompanyFeature,
    Feature,
    FeaturePage,
    Role,
    RolesFeature,
    UserRole,
)
from app.models.company import Company, CompanyStatus
from app.models.platform_admin import PlatformAdmin, PlatformAdminRole, PlatformAdminStatus
from app.models.user import User, UserProfile, UserStatus


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

SUPER_ADMIN = {
    "name": "admin",
    "email": "admin@raize.in",
    "password": "admin123",
    "role": PlatformAdminRole.SUPER_ADMIN,
    "status": PlatformAdminStatus.active,
}

COMPANY = {
    "company_name": "rAIze Technologies",
    "legal_name": "rAIze Technologies Pvt. Ltd.",
    "domain": "raize.in",
    "industry": "Technology",
    "employee_size_range": "11-50",
    "status": CompanyStatus.active,
}

# Each feature: (code, name, description, pages)
# pages: list of (page_code, page_name, route, description)
FEATURES = [
    (
        "HR_CORE",
        "HR Core",
        "Core human resources management",
        [
            ("hr_dashboard", "HR Dashboard", "/hr/dashboard", "Main HR dashboard"),
            ("hr_employees", "Employees", "/hr/employees", "Employee list and management"),
            ("hr_onboarding", "Onboarding", "/hr/onboarding", "Employee onboarding workflows"),
            ("hr_offboarding", "Offboarding", "/hr/offboarding", "Employee offboarding workflows"),
        ],
    ),
    (
        "PAYROLL",
        "Payroll",
        "Payroll processing and management",
        [
            ("payroll_dashboard", "Payroll Dashboard", "/payroll/dashboard", "Payroll overview"),
            ("payroll_runs", "Payroll Runs", "/payroll/runs", "Process and manage payroll runs"),
            ("payroll_reports", "Payroll Reports", "/payroll/reports", "Payroll analytics and reports"),
        ],
    ),
    (
        "LEAVE",
        "Leave Management",
        "Employee leave and attendance tracking",
        [
            ("leave_dashboard", "Leave Dashboard", "/leave/dashboard", "Leave overview"),
            ("leave_requests", "Leave Requests", "/leave/requests", "Manage leave requests"),
            ("leave_calendar", "Leave Calendar", "/leave/calendar", "Team leave calendar"),
        ],
    ),
    (
        "CRM",
        "CRM",
        "Customer relationship management",
        [
            ("crm_dashboard", "CRM Dashboard", "/crm/dashboard", "CRM overview"),
            ("crm_leads", "Leads", "/crm/leads", "Lead management"),
            ("crm_contacts", "Contacts", "/crm/contacts", "Contact management"),
            ("crm_deals", "Deals", "/crm/deals", "Deal pipeline"),
        ],
    ),
    (
        "REPORTS",
        "Reports",
        "Company-wide reporting and analytics",
        [
            ("reports_dashboard", "Reports Dashboard", "/reports/dashboard", "Reports overview"),
            ("reports_custom", "Custom Reports", "/reports/custom", "Build custom reports"),
        ],
    ),
]

# HR role gets HR_CORE, PAYROLL, LEAVE, REPORTS
HR_FEATURE_CODES = {"HR_CORE", "PAYROLL", "LEAVE", "REPORTS"}
# Sales role gets CRM, REPORTS
SALES_FEATURE_CODES = {"CRM", "REPORTS"}

COMPANY_ADMIN = {
    "emp_id": "ADMIN001",
    "name": "Company Admin",
    "email": "companyadmin@raize.in",
    "password": "password123",
    "is_company_admin": True,
    "status": UserStatus.active,
}

EMPLOYEES = [
    {
        "emp_id": "EMP001",
        "name": "Alice HR",
        "email": "alice@raize.in",
        "password": "password123",
        "is_company_admin": False,
        "status": UserStatus.active,
        "role": "HR",
        "profile": {
            "phone": "+91-9000000001",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "date_of_joining": date(2023, 6, 1),
        },
    },
    {
        "emp_id": "EMP002",
        "name": "Bob Sales",
        "email": "bob@raize.in",
        "password": "password123",
        "is_company_admin": False,
        "status": UserStatus.active,
        "role": "Sales",
        "profile": {
            "phone": "+91-9000000002",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "date_of_joining": date(2023, 9, 1),
        },
    },
    {
        "emp_id": "EMP003",
        "name": "Carol Sales",
        "email": "carol@raize.in",
        "password": "password123",
        "is_company_admin": False,
        "status": UserStatus.active,
        "role": "Sales",
        "profile": {
            "phone": "+91-9000000003",
            "city": "Delhi",
            "state": "Delhi",
            "country": "India",
            "date_of_joining": date(2024, 1, 15),
        },
    },
]

ROLES = [
    {
        "name": "HR",
        "description": "Human Resources team with access to HR, Payroll, Leave, and Reports features",
        "feature_codes": HR_FEATURE_CODES,
    },
    {
        "name": "Sales",
        "description": "Sales team with access to CRM and Reports features",
        "feature_codes": SALES_FEATURE_CODES,
    },
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"  {msg}")


def log_section(title: str) -> None:
    print(f"\n[{title}]")


async def get_or_create(session: AsyncSession, model, lookup: dict, defaults: dict) -> tuple:
    """Return (instance, created). Looks up by `lookup` fields; creates with lookup+defaults if missing."""
    stmt = select(model).filter_by(**lookup)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj is not None:
        return obj, False
    obj = model(**lookup, **defaults)
    session.add(obj)
    await session.flush()
    return obj, True


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_platform_admin(session: AsyncSession) -> PlatformAdmin:
    log_section("Platform Super Admin")
    admin, created = await get_or_create(
        session,
        PlatformAdmin,
        lookup={"email": SUPER_ADMIN["email"]},
        defaults={
            "name": SUPER_ADMIN["name"],
            "password_hash": hash_password(SUPER_ADMIN["password"]),
            "role": SUPER_ADMIN["role"],
            "status": SUPER_ADMIN["status"],
        },
    )
    log(f"{'Created' if created else 'Skipped (exists)'}: platform admin '{admin.name}' ({admin.email})")
    return admin


async def seed_company(session: AsyncSession) -> Company:
    log_section("Company")
    company, created = await get_or_create(
        session,
        Company,
        lookup={"company_name": COMPANY["company_name"]},
        defaults={k: v for k, v in COMPANY.items() if k != "company_name"},
    )
    log(f"{'Created' if created else 'Skipped (exists)'}: company '{company.company_name}'")
    return company


async def seed_features(session: AsyncSession) -> dict[str, Feature]:
    """Create features and their pages. Returns mapping of code -> Feature."""
    log_section("Features & Feature Pages")
    feature_map: dict[str, Feature] = {}

    for code, name, description, pages in FEATURES:
        feature, created = await get_or_create(
            session,
            Feature,
            lookup={"code": code},
            defaults={"name": name, "description": description},
        )
        log(f"  Feature {'created' if created else 'skipped'}: {code}")
        feature_map[code] = feature

        for page_code, page_name, route, page_desc in pages:
            _, page_created = await get_or_create(
                session,
                FeaturePage,
                lookup={"feature_id": feature.id, "page_code": page_code},
                defaults={"page_name": page_name, "route": route, "description": page_desc},
            )
            log(f"    Page {'created' if page_created else 'skipped'}: {page_code} -> {route}")

    return feature_map


async def seed_company_features(
    session: AsyncSession, company: Company, feature_map: dict[str, Feature]
) -> None:
    log_section("Company Subscription (all features enabled)")
    for code, feature in feature_map.items():
        _, created = await get_or_create(
            session,
            CompanyFeature,
            lookup={"company_id": company.id, "feature_id": feature.id},
            defaults={"enabled": True},
        )
        log(f"  {'Enabled' if created else 'Already enabled'}: {code} for '{company.company_name}'")


async def seed_roles(
    session: AsyncSession, company: Company, feature_map: dict[str, Feature]
) -> dict[str, Role]:
    log_section("Roles")
    role_map: dict[str, Role] = {}

    for role_def in ROLES:
        role, created = await get_or_create(
            session,
            Role,
            lookup={"company_id": company.id, "name": role_def["name"]},
            defaults={"description": role_def["description"]},
        )
        log(f"  {'Created' if created else 'Skipped'}: role '{role.name}'")
        role_map[role_def["name"]] = role

        for code in role_def["feature_codes"]:
            if code not in feature_map:
                continue
            _, rf_created = await get_or_create(
                session,
                RolesFeature,
                lookup={"role_id": role.id, "feature_id": feature_map[code].id},
                defaults={},
            )
            log(f"    {'Mapped' if rf_created else 'Already mapped'}: {code} -> {role.name}")

    return role_map


async def seed_user(
    session: AsyncSession,
    company: Company,
    emp_id: str,
    name: str,
    email: str,
    password: str,
    is_company_admin: bool,
    status: UserStatus,
) -> tuple[User, bool]:
    return await get_or_create(
        session,
        User,
        lookup={"company_id": company.id, "emp_id": emp_id},
        defaults={
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "is_company_admin": is_company_admin,
            "status": status,
        },
    )


async def seed_company_admin(session: AsyncSession, company: Company) -> User:
    log_section("Company Admin User")
    admin, created = await seed_user(
        session,
        company,
        emp_id=COMPANY_ADMIN["emp_id"],
        name=COMPANY_ADMIN["name"],
        email=COMPANY_ADMIN["email"],
        password=COMPANY_ADMIN["password"],
        is_company_admin=COMPANY_ADMIN["is_company_admin"],
        status=COMPANY_ADMIN["status"],
    )
    log(f"{'Created' if created else 'Skipped (exists)'}: company admin '{admin.name}' ({admin.emp_id})")
    return admin


async def seed_employees(
    session: AsyncSession, company: Company, role_map: dict[str, Role]
) -> list[User]:
    log_section("Employees")
    users: list[User] = []

    for emp_def in EMPLOYEES:
        user, created = await seed_user(
            session,
            company,
            emp_id=emp_def["emp_id"],
            name=emp_def["name"],
            email=emp_def["email"],
            password=emp_def["password"],
            is_company_admin=emp_def["is_company_admin"],
            status=emp_def["status"],
        )
        log(f"  {'Created' if created else 'Skipped'}: {user.name} ({user.emp_id})")
        users.append(user)

        # Profile
        profile_data = emp_def.get("profile", {})
        if profile_data:
            _, prof_created = await get_or_create(
                session,
                UserProfile,
                lookup={"user_id": user.id},
                defaults={"company_id": company.id, **profile_data},
            )
            log(f"    Profile {'created' if prof_created else 'skipped'}")

        # Role assignment
        role_name = emp_def.get("role")
        if role_name and role_name in role_map:
            _, ur_created = await get_or_create(
                session,
                UserRole,
                lookup={"user_id": user.id, "role_id": role_map[role_name].id},
                defaults={},
            )
            log(f"    Role {'assigned' if ur_created else 'already assigned'}: {role_name}")

    return users


def print_team_summary(admin: User, employees: list[User]) -> None:
    """
    NOTE: No Team model exists in the current schema.
    Once a Team / TeamMember model is added, wire it up here.
    The logical team for this seed would be:
      - Team name: "Engineering"
      - Manager:   {admin.name} ({admin.emp_id})
      - Members:   {', '.join(e.name for e in employees)}
    """
    log_section("Team (schema not yet available)")
    log(f"Manager : {admin.name} ({admin.emp_id})")
    for emp in employees:
        log(f"Member  : {emp.name} ({emp.emp_id})")
    log("Skipped: Team model does not exist yet — add it to the schema and update this script.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run() -> None:
    print("=" * 60)
    print("  Employee Management System — Seed Script")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            admin = await seed_platform_admin(session)
            company = await seed_company(session)
            feature_map = await seed_features(session)
            await seed_company_features(session, company, feature_map)
            role_map = await seed_roles(session, company, feature_map)
            company_admin = await seed_company_admin(session, company)
            employees = await seed_employees(session, company, role_map)

    print_team_summary(company_admin, employees)

    print("\n" + "=" * 60)
    print("  Seed complete.")
    print("=" * 60)
    print()
    print("  Credentials summary")
    print("  -------------------")
    print(f"  Platform super admin : {SUPER_ADMIN['email']} / {SUPER_ADMIN['password']}")
    print(f"  Company admin        : {COMPANY_ADMIN['email']} / {COMPANY_ADMIN['password']}")
    for emp in EMPLOYEES:
        print(f"  {emp['name']:<20} : {emp['email']} / {emp['password']}")
    print()


if __name__ == "__main__":
    asyncio.run(run())
