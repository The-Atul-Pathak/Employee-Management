# Implementation Roadmap

Ordered by dependency and business value. Each phase builds on the previous.

---

## Phase 0 — Foundation (Do First)
These enable everything else.

| # | Task | Prompt # | Why First |
|---|------|----------|-----------|
| 0.1 | Seed pre-made roles on company creation | Prompt 1 | Every other feature needs roles to function |
| 0.2 | Register new features in Super Admin seed | Prompt 14 | Features must exist before they can be assigned |
| 0.3 | Holiday Calendar | Prompt 9 (partial) | Needed for correct leave and payroll calculations |
| 0.4 | Company Settings | Prompt 15 | Working days config needed for payroll |

---

## Phase 1 — Fix Existing Features (High Priority)
Improve what's already built to meet the role-differentiated spec.

| # | Task | Prompt # |
|---|------|----------|
| 1.1 | Dashboard — role-differentiated cards | Prompt 2 |
| 1.2 | Attendance — My Attendance page for employees | Prompt 3 |
| 1.3 | Attendance — Team Lead scoped view | Prompt 3 |
| 1.4 | Leave — Employee self-service page (/my-leaves) | Prompt 4 |
| 1.5 | Leave — Team Lead approval view | Prompt 4 |

---

## Phase 2 — Core New Features (High Value)

| # | Task | Prompt # |
|---|------|----------|
| 2.1 | Announcements | Prompt 5 |
| 2.2 | Document Management | Prompt 6 |
| 2.3 | Shift Management | Prompt 9 |
| 2.4 | Expense Management | Prompt 8 |

---

## Phase 3 — Payroll (Complex but Critical)

| # | Task | Prompt # | Dependency |
|---|------|----------|-----------|
| 3.1 | Payroll Management | Prompt 7 | Needs Shift + Holiday (Phase 0.3, 0.4) |

---

## Phase 4 — HR Lifecycle Features

| # | Task | Prompt # |
|---|------|----------|
| 4.1 | Onboarding Workflow | Prompt 11 |
| 4.2 | Asset Management | Prompt 10 |
| 4.3 | Performance Reviews | Prompt 12 |

---

## Phase 5 — Database Migrations

| # | Task | Prompt # | When |
|---|------|----------|------|
| 5.1 | Create Alembic migrations for all new tables | Prompt 13 | After all model files are created (end of Phase 4) |

---

## Quick Wins (Can Do Anytime)

These don't require other phases to be complete:

1. **My Attendance page** — employee calendar view (Prompt 3, partial)
2. **My Leaves page** — self-service leave history + apply (Prompt 4, partial)
3. **Announcements** — simple broadcast (Prompt 5)
4. **Asset Management** — simple CRUD (Prompt 10)

---

## Estimated Feature Count After All Phases

| Category | Features |
|----------|---------|
| Already built | 8 (attendance, leaves, teams, CRM, projects, tasks, users, notifications, reports) |
| Phase 1 improvements | Not new features, but new pages/views |
| Phase 2-4 new features | 9 (announcements, documents, payroll, expenses, assets, onboarding, performance, shifts, holidays) |
| **Total after completion** | **17 distinct feature modules** |
