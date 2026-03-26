# Alembic Migration Guide

## Setup Complete ✅

Alembic has been configured for database migrations with the following components:

### Files Created

1. **alembic.ini** - Main Alembic configuration file
2. **alembic/env.py** - Python environment that:
   - Imports all SQLAlchemy models (for autogenerate detection)
   - Configures async SQLAlchemy engine
   - Handles both offline and online migrations
3. **alembic/script.py.mako** - Template for generated migration files
4. **alembic/versions/001_initial.py** - Initial migration that creates:
   - All 4 ENUM types (user_status, company_status, platform_admin_role, platform_admin_status)
   - All 11 tables with proper foreign key dependencies
   - All indexes and constraints

## Running Migrations

### Prerequisites

Make sure you have Alembic installed:

```bash
pip install alembic sqlalchemy
```

### Apply the Initial Migration

To create all tables in your database:

```bash
cd backend
alembic upgrade head
```

This will:
1. Create all ENUM types first
2. Create tables in dependency order (companies → users → roles → features → etc.)
3. Create all indexes and constraints
4. Mark the migration as applied in the `alembic_version` table

### Verify Migration Status

```bash
alembic current    # Show current migration revision
alembic history    # Show all migration history
```

## Creating New Migrations

When you add new tables or modify existing ones:

### 1. Auto-Generate Migration

```bash
alembic revision --autogenerate -m "describe_your_changes"
```

Example:
```bash
alembic revision --autogenerate -m "add_department_table"
```

### 2. Review the Generated Migration

The migration will be created in `alembic/versions/` with a timestamp prefix.
**Always review it** before applying to ensure it reflects your intended changes.

### 3. Apply the Migration

```bash
alembic upgrade head
```

## Rollback

To rollback the last migration:

```bash
alembic downgrade -1
```

To rollback to a specific revision:

```bash
alembic downgrade 001  # Rollback to initial migration
```

## Important Notes

### ENUM Types

The initial migration creates ENUM types with `create_type=True`. The models specify `create_type=False` to avoid duplicating creation. Alembic handles the creation.

**Create order matters!** ENUMs must be created before tables that use them. The initial migration handles this.

### Foreign Key Dependencies

Tables are created in this order:
1. `companies` (no dependencies)
2. `company_contacts` → `companies`
3. `users` → `companies`
4. `user_sessions` → `users`, `companies`
5. `user_profiles` → `users`, `companies`
6. `roles` → `companies`
7. `features` (no dependencies)
8. `feature_pages` → `features`
9. `user_roles` → `users`, `roles`
10. `roles_features` → `roles`, `features`
11. `platform_admins` (no dependencies)
12. `platform_sessions` → `platform_admins`

### Async Support

The `env.py` is configured for async SQLAlchemy:
- Uses `create_async_engine()` for online migrations
- Properly handles async context managers
- Works with PostgreSQL async driver (asyncpg)

## Environment Variables

Alembic reads database configuration from environment variables via `app.core.config.settings`:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ems_db
DB_USER=postgres
DB_PASSWORD=postgres
```

These are loaded from the `.env` file in the backend directory.

## Troubleshooting

### "Target database is not up to date"

Your database schema doesn't match the migrations. Either:
- Apply pending migrations: `alembic upgrade head`
- Or downgrade to a known state: `alembic downgrade <revision>`

### "Can't locate revision identified by 'head'"

No migrations have been applied yet. Run:
```bash
alembic upgrade head
```

### PostgreSQL ENUM Issues

If you get ENUM-related errors:
1. Ensure PostgreSQL is running
2. Check that the database exists and you can connect
3. For manual ENUM cleanup, connect to psql and run:
   ```sql
   DROP TYPE IF EXISTS user_status CASCADE;
   DROP TYPE IF EXISTS company_status CASCADE;
   DROP TYPE IF EXISTS platform_admin_role CASCADE;
   DROP TYPE IF EXISTS platform_admin_status CASCADE;
   ```

## Best Practices

1. **Always review migrations** before applying to production
2. **Test migrations** on a dev database first
3. **Keep migrations small** - one logical change per migration
4. **Never edit applied migrations** - create new migrations for changes
5. **Use descriptive messages** - `alembic revision --autogenerate -m "add_department_table"` not `"update"`
6. **Commit migrations** to version control with your code changes
