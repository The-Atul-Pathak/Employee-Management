#!/usr/bin/env python3
"""Seed database with platform data and demo content.

Idempotent: safe to run multiple times.  Existing records (matched by
unique key) are skipped, not duplicated.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.core.security import hash_password
from app.models.access import Feature, FeaturePage, Role, RolesFeature, UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.company import Company, CompanyContact, CompanyStatus
from app.models.leave import LeaveBalance, LeaveType
from app.models.plan import BillingCycle, CompanySubscription, Plan, PlanFeature
from app.models.platform_admin import PlatformAdmin, PlatformAdminRole, PlatformAdminStatus
from app.models.team import Team, TeamMember
from app.models.user import User, UserProfile, UserStatus

# ─── Feature registry ─────────────────────────────────────────────────────────
#
# Each entry: (code, name, description, pages)
# pages: list of (page_code, page_name, route)
#
FEATURES: list[tuple[str, str, str, list[tuple[str, str, str]]]] = [
    (
        "USER_MGMT",
        "User Management",
        "Manage employees, roles, and access",
        [
            ("users_admin", "Users - Admin", "/users"),
            ("my_profile", "My Profile", "/my-profile"),
        ],
    ),
    (
        "ATTENDANCE",
        "Attendance",
        "Track daily attendance and check-in/out",
        [
            ("attendance_admin", "Attendance - Admin", "/attendance"),
            ("my_attendance", "My Attendance", "/my-attendance"),
        ],
    ),
    (
        "LEAVE",
        "Leave Management",
        "Apply for and approve leave requests",
        [
            ("leaves_admin", "Leaves - Admin", "/leaves"),
            ("my_leaves", "My Leaves", "/my-leaves"),
        ],
    ),
    (
        "TEAM",
        "Team Management",
        "Create and manage teams",
        [
            ("teams", "Teams", "/teams"),
        ],
    ),
    (
        "CRM",
        "Sales CRM",
        "Lead pipeline and customer tracking",
        [
            ("leads", "Leads", "/leads"),
        ],
    ),
    (
        "PROJECT",
        "Project Management",
        "Plan and track project delivery",
        [
            ("projects", "Projects", "/projects"),
        ],
    ),
    (
        "TASK",
        "Task Management",
        "Assign and track tasks",
        [
            ("tasks", "Tasks", "/tasks"),
        ],
    ),
    (
        "REPORTS",
        "Reports",
        "Attendance, leave, and operational reports",
        [
            ("reports", "Reports", "/reports"),
        ],
    ),
    (
        "ANNOUNCEMENTS",
        "Announcements & Noticeboard",
        "Post and view company announcements",
        [
            ("announcements", "Announcements", "/announcements"),
        ],
    ),
    (
        "DOCUMENTS",
        "Document Management",
        "Upload and manage HR documents",
        [
            ("documents_admin", "Documents - Admin", "/documents"),
            ("my_documents", "My Documents", "/my-documents"),
        ],
    ),
    (
        "PAYROLL",
        "Payroll Management",
        "Run payroll and manage salary structures",
        [
            ("payroll_admin", "Payroll - Admin", "/payroll"),
            ("my_payslips", "My Payslips", "/my-payslips"),
        ],
    ),
    (
        "EXPENSE",
        "Expense Management",
        "Submit and approve expense claims",
        [
            ("expenses", "Expenses", "/expenses"),
        ],
    ),
    (
        "ASSETS",
        "Asset Management",
        "Track and assign IT assets",
        [
            ("assets_admin", "Assets - Admin", "/assets"),
            ("my_assets", "My Assets", "/my-assets"),
        ],
    ),
    (
        "ONBOARDING",
        "Onboarding Workflow",
        "Structured new-hire onboarding checklists",
        [
            ("onboarding_admin", "Onboarding - Admin", "/onboarding"),
            ("my_onboarding", "My Onboarding", "/my-onboarding"),
            ("onboarding_settings", "Onboarding Templates", "/settings/onboarding"),
        ],
    ),
    (
        "OFFBOARDING",
        "Offboarding Workflow",
        "Exit checklist and full-and-final settlement",
        [
            ("offboarding_admin", "Offboarding - Admin", "/offboarding"),
        ],
    ),
    (
        "PERFORMANCE",
        "Performance Reviews",
        "Periodic appraisal cycles with manager reviews",
        [
            ("performance_admin", "Performance - Admin", "/performance"),
            ("my_reviews", "My Reviews", "/my-reviews"),
        ],
    ),
    (
        "SHIFTS",
        "Shift Management",
        "Define work shifts and assign employees",
        [
            ("shifts_settings", "Shift Management", "/settings/shifts"),
        ],
    ),
    (
        "HOLIDAYS",
        "Holiday Calendar",
        "Define public and company holidays",
        [
            ("holidays_settings", "Holiday Calendar", "/settings/holidays"),
        ],
    ),
]

# ─── Plan definitions ──────────────────────────────────────────────────────────
#
# (name, description, monthly_price, yearly_price, max_employees, feature_codes)
#
PLANS: list[tuple[str, str, Decimal, Decimal, int, list[str]]] = [
    (
        "Starter",
        "For small teams — core HR essentials",
        Decimal("99.00"),
        Decimal("990.00"),
        25,
        ["USER_MGMT", "ATTENDANCE", "LEAVE", "ANNOUNCEMENTS", "DOCUMENTS", "HOLIDAYS"],
    ),
    (
        "Growth",
        "For growing companies — full HR + operations",
        Decimal("299.00"),
        Decimal("2990.00"),
        100,
        [
            "USER_MGMT",
            "ATTENDANCE",
            "LEAVE",
            "ANNOUNCEMENTS",
            "DOCUMENTS",
            "HOLIDAYS",
            "TEAM",
            "CRM",
            "PROJECT",
            "TASK",
            "EXPENSE",
            "ASSETS",
            "ONBOARDING",
            "SHIFTS",
            "PAYROLL",
            "REPORTS",
        ],
    ),
    (
        "Business",
        "For established businesses — all features",
        Decimal("599.00"),
        Decimal("5990.00"),
        500,
        [
            "USER_MGMT",
            "ATTENDANCE",
            "LEAVE",
            "ANNOUNCEMENTS",
            "DOCUMENTS",
            "HOLIDAYS",
            "TEAM",
            "CRM",
            "PROJECT",
            "TASK",
            "EXPENSE",
            "ASSETS",
            "ONBOARDING",
            "SHIFTS",
            "PAYROLL",
            "REPORTS",
            "PERFORMANCE",
            "OFFBOARDING",
        ],
    ),
]


async def seed_database() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("🌱 Seeding database...")

        # ── 1. Platform Admin ──────────────────────────────────────────────────
        existing_admin = (
            await db.execute(
                select(PlatformAdmin).where(PlatformAdmin.email == "admin@raize.io")
            )
        ).scalar_one_or_none()

        if existing_admin is None:
            db.add(
                PlatformAdmin(
                    name="Super Admin",
                    email="admin@raize.io",
                    password_hash=hash_password("SuperAdmin@123"),
                    role=PlatformAdminRole.SUPER_ADMIN,
                    status=PlatformAdminStatus.active,
                )
            )
            await db.flush()
            print("✅ Created platform admin")
        else:
            print("⏭  Platform admin already exists")

        # ── 2. Features ────────────────────────────────────────────────────────
        feature_map: dict[str, Feature] = {}
        for code, name, description, pages in FEATURES:
            feat = (
                await db.execute(select(Feature).where(Feature.code == code))
            ).scalar_one_or_none()

            if feat is None:
                feat = Feature(code=code, name=name, description=description)
                db.add(feat)
                await db.flush()
                print(f"  ✅ Feature: {code}")
            else:
                print(f"  ⏭  Feature already exists: {code}")

            feature_map[code] = feat

            for page_code, page_name, route in pages:
                existing_page = (
                    await db.execute(
                        select(FeaturePage).where(
                            FeaturePage.feature_id == feat.id,
                            FeaturePage.page_code == page_code,
                        )
                    )
                ).scalar_one_or_none()
                if existing_page is None:
                    db.add(
                        FeaturePage(
                            feature_id=feat.id,
                            page_code=page_code,
                            page_name=page_name,
                            route=route,
                        )
                    )

        await db.flush()
        print(f"✅ Features and feature pages seeded ({len(FEATURES)} features)")

        # ── 3. Plans ───────────────────────────────────────────────────────────
        for plan_name, description, monthly, yearly, max_emp, feature_codes in PLANS:
            plan = (
                await db.execute(
                    select(Plan).where(Plan.name == plan_name, Plan.deleted_at.is_(None))
                )
            ).scalar_one_or_none()

            if plan is None:
                plan = Plan(
                    name=plan_name,
                    description=description,
                    monthly_price=monthly,
                    yearly_price=yearly,
                    max_employees=max_emp,
                )
                db.add(plan)
                await db.flush()
                print(f"  ✅ Plan: {plan_name}")
            else:
                print(f"  ⏭  Plan already exists: {plan_name}")

            # Assign features to plan (idempotent)
            existing_plan_features = set(
                row[0]
                for row in (
                    await db.execute(
                        select(PlanFeature.feature_id).where(PlanFeature.plan_id == plan.id)
                    )
                ).all()
            )
            for code in feature_codes:
                feat = feature_map.get(code)
                if feat and feat.id not in existing_plan_features:
                    db.add(PlanFeature(plan_id=plan.id, feature_id=feat.id))
                    existing_plan_features.add(feat.id)

        await db.flush()
        print(f"✅ Plans seeded ({len(PLANS)} plans)")

        # ── 4. Demo company ────────────────────────────────────────────────────
        demo_company = (
            await db.execute(
                select(Company).where(
                    Company.company_name == "Acme Corporation",
                    Company.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if demo_company is None:
            demo_company = Company(
                company_name="Acme Corporation",
                legal_name="Acme Corporation Pvt. Ltd.",
                industry="Technology",
                domain="acme.com",
                employee_size_range="11-50",
                status=CompanyStatus.active,
            )
            db.add(demo_company)
            await db.flush()

            db.add(
                CompanyContact(
                    company_id=demo_company.id,
                    name="Alice Johnson",
                    email="alice@acme.com",
                    phone="+919876543210",
                    is_primary=True,
                )
            )
            await db.flush()
            print("✅ Created demo company: Acme Corporation")
        else:
            print("⏭  Demo company already exists")

        # ── 5. Demo subscription (Growth plan) ─────────────────────────────────
        growth_plan = (
            await db.execute(
                select(Plan).where(Plan.name == "Growth", Plan.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

        if growth_plan:
            existing_sub = (
                await db.execute(
                    select(CompanySubscription).where(
                        CompanySubscription.company_id == demo_company.id,
                        CompanySubscription.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if existing_sub is None:
                db.add(
                    CompanySubscription(
                        company_id=demo_company.id,
                        plan_id=growth_plan.id,
                        billing_cycle=BillingCycle.monthly,
                        start_date=date.today(),
                        is_active=True,
                    )
                )
                await db.flush()
                print("✅ Created demo subscription (Growth plan)")
            else:
                print("⏭  Demo subscription already exists")

        # ── 6. Demo admin user ─────────────────────────────────────────────────
        admin_user = (
            await db.execute(
                select(User).where(
                    User.company_id == demo_company.id,
                    User.email == "admin@acme.com",
                    User.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if admin_user is None:
            admin_user = User(
                company_id=demo_company.id,
                emp_id="AC001",
                name="Alice Johnson",
                email="admin@acme.com",
                password_hash=hash_password("Admin@123"),
                is_company_admin=True,
                status=UserStatus.active,
            )
            db.add(admin_user)
            await db.flush()

            db.add(
                UserProfile(
                    user_id=admin_user.id,
                    company_id=demo_company.id,
                    date_of_joining=date.today(),
                )
            )
            await db.flush()
            print("✅ Created demo admin user: admin@acme.com / Admin@123")
        else:
            print("⏭  Demo admin user already exists")

        # ── 7. Demo employees ──────────────────────────────────────────────────
        emp_users: list[User] = []
        for i in range(1, 6):
            emp = (
                await db.execute(
                    select(User).where(
                        User.company_id == demo_company.id,
                        User.email == f"emp{i}@acme.com",
                        User.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if emp is None:
                emp = User(
                    company_id=demo_company.id,
                    emp_id=f"AC{100 + i}",
                    name=f"Employee {i}",
                    email=f"emp{i}@acme.com",
                    password_hash=hash_password(f"Emp{i}@123"),
                    is_company_admin=False,
                    status=UserStatus.active,
                )
                db.add(emp)
                await db.flush()

                db.add(
                    UserProfile(
                        user_id=emp.id,
                        company_id=demo_company.id,
                        date_of_joining=date.today(),
                    )
                )
                await db.flush()

            emp_users.append(emp)

        print(f"✅ Demo employees ready ({len(emp_users)})")

        # ── 8. Demo team ───────────────────────────────────────────────────────
        demo_team = (
            await db.execute(
                select(Team).where(
                    Team.company_id == demo_company.id,
                    Team.name == "Engineering",
                    Team.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()

        if demo_team is None:
            demo_team = Team(
                company_id=demo_company.id,
                name="Engineering",
                description="Engineering team",
                manager_id=admin_user.id,
            )
            db.add(demo_team)
            await db.flush()

            for emp in emp_users:
                db.add(TeamMember(team_id=demo_team.id, user_id=emp.id))
            await db.flush()
            print("✅ Created demo team: Engineering")
        else:
            print("⏭  Demo team already exists")

        # ── 9. Demo leave balances ─────────────────────────────────────────────
        current_year = date.today().year
        leave_quotas = {
            LeaveType.casual: 12.0,
            LeaveType.sick: 6.0,
            LeaveType.earned: 15.0,
        }
        for user in [admin_user] + emp_users:
            for leave_type, quota in leave_quotas.items():
                existing_bal = (
                    await db.execute(
                        select(LeaveBalance).where(
                            LeaveBalance.company_id == demo_company.id,
                            LeaveBalance.user_id == user.id,
                            LeaveBalance.leave_type == leave_type,
                            LeaveBalance.year == current_year,
                        )
                    )
                ).scalar_one_or_none()

                if existing_bal is None:
                    db.add(
                        LeaveBalance(
                            company_id=demo_company.id,
                            user_id=user.id,
                            leave_type=leave_type,
                            year=current_year,
                            total_quota=quota,
                            used=0,
                            remaining=quota,
                        )
                    )
        await db.flush()
        print("✅ Demo leave balances seeded")

        # ── 10. Demo attendance records ────────────────────────────────────────
        today = date.today()
        for user in [admin_user] + emp_users:
            for days_ago in range(0, 20):
                att_date = today - timedelta(days=days_ago)
                if att_date.weekday() >= 5:  # Skip weekends
                    continue
                existing_att = (
                    await db.execute(
                        select(Attendance).where(
                            Attendance.company_id == demo_company.id,
                            Attendance.user_id == user.id,
                            Attendance.date == att_date,
                        )
                    )
                ).scalar_one_or_none()

                if existing_att is None:
                    check_in = datetime.combine(att_date, datetime.min.time()).replace(
                        hour=9, minute=0, tzinfo=timezone.utc
                    )
                    check_out = datetime.combine(att_date, datetime.min.time()).replace(
                        hour=17, minute=30, tzinfo=timezone.utc
                    )
                    db.add(
                        Attendance(
                            company_id=demo_company.id,
                            user_id=user.id,
                            date=att_date,
                            status=AttendanceStatus.present,
                            check_in_time=check_in,
                            check_out_time=check_out,
                        )
                    )
        await db.flush()
        print("✅ Demo attendance records seeded")

        await db.commit()
        print("\n✨ Database seeded successfully!")
        print("\n📝 Platform Admin:")
        print("  Email: admin@raize.io")
        print("  Password: SuperAdmin@123")
        print("\n📝 Demo Company (Acme Corporation):")
        print("  Admin: admin@acme.com / Admin@123")
        print("  Employees: emp{1-5}@acme.com / Emp{N}@123")


if __name__ == "__main__":
    asyncio.run(seed_database())
