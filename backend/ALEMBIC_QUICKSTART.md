# Alembic Quick Start

## One-Time Setup

```bash
# Install dependencies
pip install alembic sqlalchemy

# Apply initial migration (creates all tables)
cd backend
alembic upgrade head
```

## Common Commands

```bash
# Check current migration status
alembic current

# View all migrations
alembic history

# Create new migration after schema changes
alembic revision --autogenerate -m "your_change_description"

# Apply pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Rollback to specific migration
alembic downgrade 001
```

## When You Add a New Model

1. **Define your model** in `app/models/`
2. **Import it** in `app/models/__init__.py`
3. **Generate migration:**
   ```bash
   alembic revision --autogenerate -m "add_new_table"
   ```
4. **Review the migration file** in `alembic/versions/`
5. **Apply it:**
   ```bash
   alembic upgrade head
   ```

## Migration File Locations

- Migration files: `alembic/versions/`
- Config: `alembic.ini`
- Environment: `alembic/env.py`
- Template: `alembic/script.py.mako`

## Database Connection

The migrations connect to PostgreSQL using:
- Host: `DB_HOST` (from .env, default: localhost)
- Port: `DB_PORT` (from .env, default: 5432)
- Database: `DB_NAME` (from .env, default: ems_db)
- User: `DB_USER` (from .env, default: postgres)
- Password: `DB_PASSWORD` (from .env, default: postgres)

## Initial Migration Summary

**Migration File:** `alembic/versions/001_initial.py`

**Creates:**
- ✅ 4 ENUM types (user_status, company_status, platform_admin_role, platform_admin_status)
- ✅ 11 tables with all columns
- ✅ Foreign key constraints
- ✅ Unique constraints
- ✅ Indexes
- ✅ Server defaults

**Order of creation:**
1. ENUMs created first
2. Companies table (no foreign keys)
3. Dependent tables (company_contacts, users, roles, features)
4. Junction tables (user_roles, roles_features)
5. Platform admin tables (platform_admins, platform_sessions)
