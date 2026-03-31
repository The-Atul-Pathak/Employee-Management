#!/usr/bin/env python3

import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models import Company, CompanyStatus, User, UserStatus, Role, UserRole


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("🌱 Seeding demo users...")
        company_id = uuid.uuid4()
        company = Company(id=company_id, company_name="Demo", status=CompanyStatus.active)
        db.add(company)
        await db.flush()

        role = Role(company_id=company_id, name="Employee")
        db.add(role)
        await db.flush()

        admin = User(company_id=company_id, email="admin@demo.com", emp_id="001", name="Admin",
                    status=UserStatus.active, password_hash=hash_password("Admin@123"), is_company_admin=True)
        emp1 = User(company_id=company_id, email="emp1@demo.com", emp_id="002", name="Emp1",
                   status=UserStatus.active, password_hash=hash_password("Emp@123"))
        
        db.add_all([admin, emp1])
        await db.flush()

        db.add(UserRole(user_id=admin.id, role_id=role.id))
        db.add(UserRole(user_id=emp1.id, role_id=role.id))
        await db.commit()
        
        print("✨ Done! Credentials:")
        print("  admin@demo.com / Admin@123")
        print("  emp1@demo.com / Emp@123")


asyncio.run(seed())
