#!/usr/bin/env python3
"""Seed database with demo data."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models import (
    Company,
    CompanyStatus,
    Feature,
    Plan,
    CompanySubscription,
    User,
    UserProfile,
    UserStatus,
    UserRole,
    Role,
    RolesFeature,
    Team,
    Attendance,
    AttendanceStatus,
    LeaveType,
    LeaveBalance,
    Project,
    ProjectTask,
    TaskStatus,
    Lead,
)


async def seed_database():
    """Seed the database with demo data."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("🌱 Seeding database...")

        # 1. Create Plans
        plans = [
            Plan(
                name="Starter",
                description="For small teams",
                monthly_price=Decimal("99.00"),
                yearly_price=Decimal("990.00"),
                max_employees=10,
            ),
            Plan(
                name="Professional",
                description="For growing companies",
                monthly_price=Decimal("299.00"),
                yearly_price=Decimal("2990.00"),
                max_employees=50,
            ),
        ]
        db.add_all(plans)
        await db.flush()
        print(f"✅ Created {len(plans)} plans")

        # 2. Create Features
        features = [
            Feature(code="view_dashboard", name="View Dashboard"),
            Feature(code="manage_users", name="Manage Users"),
            Feature(code="mark_attendance", name="Mark Attendance"),
            Feature(code="apply_leave", name="Apply Leave"),
            Feature(code="manage_projects", name="Manage Projects"),
            Feature(code="manage_tasks", name="Manage Tasks"),
        ]
        db.add_all(features)
        await db.flush()
        print(f"✅ Created {len(features)} features")

        # 3. Create Companies
        company1 = Company(
            id=uuid.uuid4(),
            company_name="Acme Corporation",
            status=CompanyStatus.active,
        )
        db.add(company1)
        await db.flush()
        print(f"✅ Created company")

        # 4. Create Subscription
        subscription = CompanySubscription(
            company_id=company1.id,
            plan_id=plans[0].id,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(subscription)
        await db.flush()
        print(f"✅ Created subscription")

        # 5. Create Roles
        admin_role = Role(
            company_id=company1.id,
            name="Admin",
            description="Company administrator",
        )
        employee_role = Role(
            company_id=company1.id,
            name="Employee",
            description="Regular employee",
        )
        db.add_all([admin_role, employee_role])
        await db.flush()
        print(f"✅ Created roles")

        # 6. Assign features to admin role
        for feature in features:
            db.add(RolesFeature(role_id=admin_role.id, feature_id=feature.id))
        await db.flush()
        print(f"✅ Assigned features to roles")

        # 7. Create Users
        admin_user = User(
            company_id=company1.id,
            email="admin@acme.com",
            emp_id="AC001",
            status=UserStatus.ACTIVE,
            password_hash=hash_password("Admin@123"),
            is_company_admin=True,
            name="Alice Johnson",
        )
        emp_users = [
            User(
                company_id=company1.id,
                email=f"emp{i}@acme.com",
                emp_id=f"AC{100+i}",
                status=UserStatus.ACTIVE,
                password_hash=hash_password(f"Emp{i}@123"),
                is_company_admin=False,
                name=f"Employee {i}",
            )
            for i in range(1, 6)
        ]
        db.add_all([admin_user] + emp_users)
        await db.flush()
        print(f"✅ Created 6 users")

        # 8. Create User Profiles
        for user in [admin_user] + emp_users:
            profile = UserProfile(
                user_id=user.id,
                date_of_birth=datetime(1990, 1, 1).date(),
                phone="+1234567890",
                department="Engineering",
                position="Developer",
                joined_date=datetime.now(timezone.utc).date(),
            )
            db.add(profile)
        await db.flush()
        print(f"✅ Created user profiles")

        # 9. Assign users to roles
        db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
        for user in emp_users:
            db.add(UserRole(user_id=user.id, role_id=employee_role.id))
        await db.flush()
        print(f"✅ Assigned users to roles")

        # 10. Create Teams
        team1 = Team(
            company_id=company1.id,
            name="Engineering",
            description="Engineering team",
            leader_id=admin_user.id,
        )
        db.add(team1)
        await db.flush()
        print(f"✅ Created team")

        # 11. Create Leave Types
        leave_types = [
            LeaveType(company_id=company1.id, name="Casual Leave", quota=12),
            LeaveType(company_id=company1.id, name="Sick Leave", quota=6),
        ]
        db.add_all(leave_types)
        await db.flush()
        print(f"✅ Created leave types")

        # 12. Create Leave Balances
        for user in [admin_user] + emp_users:
            for leave_type in leave_types:
                db.add(LeaveBalance(
                    user_id=user.id,
                    leave_type_id=leave_type.id,
                    balance=leave_type.quota,
                ))
        await db.flush()
        print(f"✅ Created leave balances")

        # 13. Create Attendance Records
        for user in [admin_user] + emp_users:
            for days_ago in range(0, 20):
                date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
                if date.weekday() < 5:  # Weekdays only
                    db.add(Attendance(
                        company_id=company1.id,
                        user_id=user.id,
                        date=date,
                        check_in_time=datetime.combine(date, datetime.min.time()).replace(hour=9, minute=0),
                        check_out_time=datetime.combine(date, datetime.min.time()).replace(hour=17, minute=30),
                        status=AttendanceStatus.PRESENT,
                    ))
        await db.flush()
        print(f"✅ Created attendance records")

        # 14. Create Projects
        project1 = Project(
            company_id=company1.id,
            name="Website Redesign",
            description="Redesign company website",
            team_id=team1.id,
            planned_start_date=datetime.now(timezone.utc).date(),
            planned_end_date=(datetime.now(timezone.utc) + timedelta(days=90)).date(),
        )
        db.add(project1)
        await db.flush()
        print(f"✅ Created project")

        # 15. Create Tasks
        tasks = [
            ProjectTask(
                project_id=project1.id,
                title="Design Mockups",
                description="Create UI mockups",
                assigned_to=emp_users[0].id,
                status=TaskStatus.IN_PROGRESS,
                due_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
            ),
            ProjectTask(
                project_id=project1.id,
                title="Frontend Development",
                description="Build frontend",
                assigned_to=emp_users[1].id,
                status=TaskStatus.PENDING,
                due_date=(datetime.now(timezone.utc) + timedelta(days=30)).date(),
            ),
        ]
        db.add_all(tasks)
        await db.flush()
        print(f"✅ Created tasks")

        # 16. Create Leads
        leads = [
            Lead(
                company_id=company1.id,
                name="Acme Client A",
                email="contact@acmeclient.com",
                phone="+1111111111",
                assigned_to=emp_users[1].id,
            ),
            Lead(
                company_id=company1.id,
                name="TechCorp Client B",
                email="sales@techcorpclient.com",
                phone="+2222222222",
                assigned_to=emp_users[2].id,
            ),
        ]
        db.add_all(leads)

        # Commit all changes
        await db.commit()
        print("\n✨ Database seeded successfully!")
        print("\n📝 Demo Credentials:")
        print("  Admin: admin@acme.com / Admin@123")
        print("  Employees: emp{1-5}@acme.com / Emp{N}@123")


if __name__ == "__main__":
    asyncio.run(seed_database())
