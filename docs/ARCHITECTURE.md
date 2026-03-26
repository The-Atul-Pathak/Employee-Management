# EMS Architecture Reference

## Overview
Multi-tenant Employee Management SaaS. Shared database, shared schema.
Every data table has a `company_id` column. Tenant isolation enforced at middleware level.

## Tech Stack
- Backend: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16 + Redis
- Frontend: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query
- Auth: JWT access tokens (15min) + refresh tokens (7 days, httpOnly cookie)

## Backend Layers (STRICT — never skip a layer)
```
Route Handler (thin) → Service (business logic) → Repository (DB queries)
```

- **Route**: Validates input (Pydantic), calls service, returns response. NO business logic here.
- **Service**: All business rules, validation, cross-entity operations. Receives repo via dependency injection.
- **Repository**: SQLAlchemy queries only. No business logic. Returns model instances or None.
- **Model**: SQLAlchemy table definition. No methods beyond relationships.
- **Schema**: Pydantic models for request/response validation.

## Multi-tenancy
- Every request has a `current_user` dependency that includes `company_id`
- Every repository method automatically filters by `company_id`
- Never pass `company_id` as a URL parameter — always derive from auth token
- Integration tests MUST verify cross-tenant isolation

## API Conventions
- All endpoints: `/api/v1/{module}/{resource}`
- List endpoints return: `{"data": [...], "meta": {"total", "page", "per_page", "total_pages"}}`
- Error responses: `{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [...]}}`
- All list endpoints support: `?page=1&per_page=20&search=&sort_by=&sort_order=`

## Database Conventions
- UUID primary keys (not auto-increment integers)
- `created_at`, `updated_at` on every table (DB-level defaults)
- Soft deletes via `deleted_at` timestamp (NULL = active)
- All status columns use PostgreSQL ENUM types
- Composite indexes on (company_id, <frequently_filtered_column>)

## File Structure
```
backend/app/
├── main.py              # FastAPI app, middleware, startup
├── core/
│   ├── config.py        # Settings from env
│   ├── database.py      # SQLAlchemy engine, session
│   ├── security.py      # Password hashing, JWT creation/verification
│   ├── dependencies.py  # get_current_user, get_db, require_admin
│   └── middleware.py     # Rate limiting, tenant context, CORS
├── models/
│   ├── base.py          # Base model with id, created_at, updated_at, deleted_at
│   ├── user.py          # User, UserSession, UserProfile
│   ├── company.py       # Company, CompanyContact, CompanySettings
│   ├── access.py        # Role, Permission, Feature, Plan, Subscription
│   ├── hr.py            # Attendance, LeaveRequest, LeaveBalance
│   ├── team.py          # Team, TeamMember
│   ├── crm.py           # Lead, LeadInteraction
│   └── project.py       # Project, ProjectPlanning, ProjectTask, TaskUpdate
├── schemas/
│   ├── auth.py
│   ├── user.py
│   ├── company.py
│   ├── attendance.py
│   ├── leave.py
│   ├── team.py
│   ├── lead.py
│   └── project.py
├── services/
│   ├── auth_service.py
│   ├── user_service.py
│   ├── attendance_service.py
│   ├── leave_service.py
│   ├── team_service.py
│   ├── lead_service.py
│   └── project_service.py
├── repositories/
│   ├── user_repo.py
│   ├── attendance_repo.py
│   ├── leave_repo.py
│   ├── team_repo.py
│   ├── lead_repo.py
│   └── project_repo.py
└── api/v1/
    ├── router.py         # Collects all routers
    └── endpoints/
        ├── auth.py
        ├── users.py
        ├── attendance.py
        ├── leaves.py
        ├── teams.py
        ├── leads.py
        ├── projects.py
        └── tasks.py
```