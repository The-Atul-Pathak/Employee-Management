# Implementation Prompts — With Context Files

Each prompt below can be given directly to Claude Code (or Claude Codex).
After each prompt, the **Context Files** section lists which files to attach
as context so the AI has full knowledge of the existing system.

---

## PROMPT 1: Seed Pre-Made Roles on Company Creation

**Goal:** When a new company is onboarded (via super admin or API), automatically seed the 9 pre-made roles with correct feature assignments.

**Prompt:**
```
I need you to update the company creation flow to seed pre-made roles automatically.

The system uses a feature-based RBAC model. Roles are company-scoped and linked to features via roles_features table.

Task:
1. In backend/app/services/company_service.py (or wherever company creation happens), after a company is created, call a new function `seed_default_roles(company_id, db)`.
2. Create that function in a new file backend/app/services/role_seeder.py.
3. The function should create the 9 pre-made roles defined in new docs/03-PREMADE-ROLES-SPEC.md.
4. For each role, only assign features that are enabled for that company (check company_features table).
5. If a feature is not enabled for the company, skip assigning it but still create the role.
6. Make it idempotent — if roles already exist (by name), skip creation.

Use existing models: Role, RolesFeature, Feature (look them up in backend/app/models/).
Use async SQLAlchemy sessions consistent with the rest of the codebase.
```

**Context Files:**
- `new docs/03-PREMADE-ROLES-SPEC.md`
- `employee-management-system/backend/app/models/role.py`
- `employee-management-system/backend/app/models/user.py`
- `employee-management-system/backend/app/services/` (scan for company creation service)
- `employee-management-system/backend/app/api/v1/endpoints/roles.py`
- `employee-management-system/docs/DATABASE_SCHEMA.md`

---

## PROMPT 2: Role-Differentiated Dashboard Cards

**Goal:** Make the dashboard show different cards/content based on the user's role and features.

**Prompt:**
```
The dashboard currently shows a generic view. I need it to show role-differentiated content.

The frontend already gets `accessible_pages` and `accessible_features` from GET /auth/me.

Task:
1. In the backend, create a new endpoint GET /api/v1/dashboard/summary that returns a structured object based on the current user's role:
   - If user is admin or has HR features: return { attendance_summary, pending_leaves, pending_task_approvals, total_employees, active_projects, open_leads (if CRM enabled) }
   - If user has TEAM feature (Team Lead): return { team_attendance_summary (team only), team_pending_leaves, team_task_summary }
   - If user has CRM feature only (Sales): return { my_leads_by_stage, todays_followups, my_tasks }
   - For any user (fallback): return { my_attendance_today, my_leave_balance, my_tasks }
   All sections are optional in the response — only include what the user's role can see.

2. In the frontend, update src/app/(dashboard)/page.tsx (or the dashboard page):
   - Fetch from the new endpoint
   - Show cards conditionally based on what's in the response
   - Use existing StatsCard and DataTable components where applicable
   - Each card section should have a loading skeleton

Follow the pattern of existing hooks in src/hooks/ for the data fetching.
```

**Context Files:**
- `new docs/01-FEATURES-OVERVIEW.md` (Dashboard section)
- `new docs/02-FEATURE-SPECS-BY-ROLE.md` (Dashboard cards by role)
- `employee-management-system/frontend/src/app/(dashboard)/page.tsx`
- `employee-management-system/frontend/src/hooks/use-attendance.ts`
- `employee-management-system/frontend/src/hooks/use-leaves.ts`
- `employee-management-system/frontend/src/components/shared/stats-card.tsx`
- `employee-management-system/backend/app/api/v1/endpoints/attendance.py`
- `employee-management-system/backend/app/core/dependencies.py`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 3: Attendance — Role-Differentiated Views

**Goal:** The /attendance page should show full admin view for HR/Admin, team-filtered view for Team Leads, and redirect employees to /my-attendance.

**Prompt:**
```
The attendance feature needs role-differentiated views as described in new docs/02-FEATURE-SPECS-BY-ROLE.md (Attendance section).

Task:
1. Backend: Update GET /api/v1/attendance to accept an optional `scope` query param:
   - scope=all (admin/HR) — return all employees
   - scope=team (team_lead) — return only members of the requester's team(s)
   - scope=own (employee) — return only the requester's own records
   The backend should enforce this based on the user's role/permissions, not just trust the param.

2. Backend: Add GET /api/v1/attendance/my — returns only the current user's attendance with month/year filter and calendar-friendly format (array of {date, status} for the month).

3. Frontend: In src/app/(dashboard)/attendance/page.tsx:
   - Check accessible_features from auth store
   - If user has ATTENDANCE admin access → show full admin view (all employees, mark attendance capability)
   - If user is Team Lead → show team-filtered view (same UI but scoped)
   - If user only has own attendance access → redirect to /my-attendance

4. Frontend: Create src/app/(dashboard)/my-attendance/page.tsx:
   - Monthly calendar view (color-coded per status)
   - Summary stats for the month
   - Table list view below calendar
   - Month/year navigation

Make sure the new /my-attendance route is registered as a feature page for the ATTENDANCE feature so roles can access it.
```

**Context Files:**
- `new docs/02-FEATURE-SPECS-BY-ROLE.md`
- `employee-management-system/backend/app/api/v1/endpoints/attendance.py`
- `employee-management-system/backend/app/services/attendance_service.py`
- `employee-management-system/frontend/src/app/(dashboard)/attendance/page.tsx`
- `employee-management-system/frontend/src/hooks/use-attendance.ts`
- `employee-management-system/frontend/src/stores/auth-store.ts`
- `employee-management-system/docs/DATABASE_SCHEMA.md`

---

## PROMPT 4: Leave Management — Team Lead Approval View

**Goal:** Team Leads should be able to see and approve leaves for their team.

**Prompt:**
```
Currently leave approval is only available to company admins. Team Leads need to approve their team's leaves.

Task:
1. Backend: Update the leave approval endpoints to allow users with LEAVE feature + TEAM feature to approve leaves for their team members:
   - A Team Lead can approve/reject a leave only if the requesting employee is in their team
   - The check should be: is the requester a manager of a team that contains this employee?
   - This logic should live in the service layer, not the endpoint

2. Backend: Update GET /api/v1/leaves to support scope=team parameter (similar to attendance). Return only team members' leaves for team leads.

3. Frontend: In src/app/(dashboard)/leaves/page.tsx:
   - If user is admin/HR → show all pending leaves (existing behavior)
   - If user has team approval permission → show a "My Team" tab with team-scoped pending leaves
   - If user is a plain employee → show only their own leave history (redirect to /my-leaves or show personal view)

4. Frontend: Create src/app/(dashboard)/my-leaves/page.tsx for the employee self-service view:
   - Leave balance cards per type (with progress bar)
   - Apply Leave button → modal form
   - My leave history table with status badges
   - Upcoming approved leaves section
```

**Context Files:**
- `new docs/02-FEATURE-SPECS-BY-ROLE.md` (Leave Management section)
- `employee-management-system/backend/app/api/v1/endpoints/leaves.py`
- `employee-management-system/backend/app/services/leave_service.py`
- `employee-management-system/backend/app/models/leave.py`
- `employee-management-system/backend/app/models/team.py`
- `employee-management-system/frontend/src/app/(dashboard)/leaves/page.tsx`
- `employee-management-system/frontend/src/hooks/use-leaves.ts`

---

## PROMPT 5: Announcements Feature — Full Stack

**Goal:** Build the Announcements feature end-to-end.

**Prompt:**
```
Build the Announcements feature for the rAIze EMS platform. This is a new feature that does not exist yet.

The full spec is in new docs/04-NEW-FEATURES-SPECS.md (Announcements section).

Task:
1. Backend — Data model:
   Create backend/app/models/announcement.py with the Announcement and AnnouncementRead SQLAlchemy models per the spec.

2. Backend — Schema:
   Create backend/app/schemas/announcement.py with Pydantic schemas for create, update, response.

3. Backend — Service:
   Create backend/app/services/announcement_service.py with:
   - create_announcement(data, company_id, author_id, db)
   - list_announcements(company_id, user_id, user_role_ids, user_team_ids, db) — filters by target_type/target_ids
   - get_announcement(id, company_id, user_id, db) — also marks as read
   - update_announcement, delete_announcement
   - get_unread_count(company_id, user_id, db)

4. Backend — Router:
   Create backend/app/api/v1/endpoints/announcements.py with all endpoints from the spec. Register it in backend/app/main.py.

5. Frontend — Hook:
   Create frontend/src/hooks/use-announcements.ts using React Query (follow existing hook patterns).

6. Frontend — Page:
   Create frontend/src/app/(dashboard)/announcements/page.tsx:
   - Admin/HR view: list of announcements with create button, view counts
   - Employee view: list of announcements (unread bold), click to read
   - Create announcement modal with: title, body (simple textarea for now), target audience (all/roles/teams), pin toggle, expiry date

7. Frontend — Sidebar:
   Add Announcements to the sidebar navigation (it should already work via accessible_pages once the feature page is registered).

Follow all existing code patterns: async SQLAlchemy, company_id isolation, JWT auth, TanStack Query, shadcn/ui components.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/models/notification.py` (similar pattern)
- `employee-management-system/backend/app/schemas/notification.py`
- `employee-management-system/backend/app/services/notification_service.py`
- `employee-management-system/backend/app/api/v1/endpoints/notifications.py`
- `employee-management-system/frontend/src/hooks/use-notifications.ts`
- `employee-management-system/frontend/src/app/(dashboard)/` (any page for pattern reference)
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 6: Document Management — Full Stack

**Goal:** Build the Document Management feature end-to-end.

**Prompt:**
```
Build the Document Management feature for the rAIze EMS platform. Full spec in new docs/04-NEW-FEATURES-SPECS.md (Document Management section).

For file storage: use the local filesystem in development (store in /uploads/{company_id}/{type}/{filename}). The download endpoint returns the file directly. We'll migrate to S3 later.

Task:
1. Backend — Models: Create backend/app/models/document.py (Document + DocumentRequest models).
2. Backend — Schemas: Create backend/app/schemas/document.py
3. Backend — Service: Create backend/app/services/document_service.py
4. Backend — Router: Create backend/app/api/v1/endpoints/documents.py
   - File upload endpoint should use FastAPI's UploadFile
   - Validate: max 10MB, allowed types: pdf, doc, docx, jpg, png
   - Store file to local /uploads dir, save path in document.file_url
   - Download endpoint: read file from disk and stream it

5. Frontend — Hook: frontend/src/hooks/use-documents.ts
6. Frontend — Pages:
   - frontend/src/app/(dashboard)/documents/page.tsx (admin/HR view with tabs: Company Docs / Employee Docs)
   - frontend/src/app/(dashboard)/my-documents/page.tsx (employee self-service)

For the admin Employee Docs tab: show a user selector → then show that user's document folder.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/models/user.py` (for FK reference patterns)
- `employee-management-system/backend/app/api/v1/endpoints/reports.py` (for file streaming pattern)
- `employee-management-system/backend/app/core/config.py`
- `employee-management-system/docs/ARCHITECTURE.md`
- `employee-management-system/docs/DATABASE_SCHEMA.md`

---

## PROMPT 7: Payroll Management — Full Stack

**Goal:** Build the Payroll feature. This is the most complex new feature.

**Prompt:**
```
Build the Payroll Management feature for the rAIze EMS platform. Full spec in new docs/04-NEW-FEATURES-SPECS.md (Payroll section).

This is India-specific payroll: PF (12% employee + 12% employer), ESI (if gross < 21000), Professional Tax (Maharashtra: ₹200/month standard), TDS (skip for now — add as manual entry).

Task:
1. Backend — Models: Create backend/app/models/payroll.py (SalaryStructure, PayrollRun, Payslip).
2. Backend — Schemas: Create backend/app/schemas/payroll.py
3. Backend — Service: Create backend/app/services/payroll_service.py with:
   - create_or_update_salary_structure(employee_id, data, db)
   - run_payroll(month, year, company_id, run_by, db):
     * Get all active employees
     * For each employee, get their salary structure
     * Get attendance for month (present days, LOP days, leave days)
     * Calculate gross = (monthly_gross / working_days) × (present + leave days)
     * Calculate deductions: PF = basic × 12%, ESI = gross × 0.75% if gross < 21000, PT = 200
     * Net = Gross - Deductions
     * Create Payslip record
     * Create PayrollRun record with totals
   - approve_payroll_run(run_id, db)
   - mark_paid(run_id, db)

4. Backend — Router: Create backend/app/api/v1/endpoints/payroll.py
5. Backend — PDF Payslip: Create backend/app/services/payslip_pdf_service.py using `reportlab` or `weasyprint`. Generate a simple payslip PDF with company name, employee name, month, salary breakdown.
6. Frontend — Hook: frontend/src/hooks/use-payroll.ts
7. Frontend — Pages:
   - /payroll — Admin view with tabs: Salary Structures | Run Payroll | Payslips
   - /my-payslips — Employee view: list of months → download payslip PDF

For "Run Payroll" tab: show a table preview of all employees with their calculated gross/deductions/net before approving. Admin clicks "Run for [Month] [Year]" → sees preview → confirms → payroll is saved.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/services/attendance_service.py`
- `employee-management-system/backend/app/services/leave_service.py`
- `employee-management-system/backend/app/models/attendance.py`
- `employee-management-system/backend/app/api/v1/endpoints/reports.py`
- `employee-management-system/docs/DATABASE_SCHEMA.md`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 8: Expense Management — Full Stack

**Goal:** Build expense claim and reimbursement tracking.

**Prompt:**
```
Build the Expense Management feature. Spec in new docs/04-NEW-FEATURES-SPECS.md (Expense Management section).

Task:
1. Backend — Models: Create backend/app/models/expense.py (ExpenseCategory, Expense).
2. Backend — Schemas: Create backend/app/schemas/expense.py
3. Backend — Service: Create backend/app/services/expense_service.py
4. Backend — Router: Create backend/app/api/v1/endpoints/expenses.py
   - GET /expenses: admin sees all (filterable by employee, status, date range); employees see own
   - The scope decision should be made in the service based on current user's is_company_admin flag and role
   - Receipt upload: accept file upload (image/pdf, max 5MB), store same as documents

5. Frontend — Hook: frontend/src/hooks/use-expenses.ts
6. Frontend — Pages:
   - /expenses — Shows different content by role:
     * Admin/Finance: tabs "Pending Approval" | "All Expenses" with approve/reject actions
     * Employee: my expenses list + "Submit Expense" button
   - Submit Expense modal: amount, category, date, description, receipt upload (drag and drop)
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `new docs/02-FEATURE-SPECS-BY-ROLE.md`
- `employee-management-system/backend/app/api/v1/endpoints/documents.py` (if built, for upload pattern)
- `employee-management-system/backend/app/models/leave.py` (for workflow pattern reference)
- `employee-management-system/backend/app/services/leave_service.py`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 9: Shift & Holiday Calendar

**Goal:** Define work shifts and public holidays. These feed into attendance and payroll.

**Prompt:**
```
Build the Shift Management and Holiday Calendar features. Spec in new docs/04-NEW-FEATURES-SPECS.md.

These are configuration features used by HR to set up the company's working schedule.

Task:
1. Backend — Models: Create backend/app/models/shift.py (Shift, EmployeeShift, Holiday).
2. Backend — Schemas + Services + Routers for shifts and holidays.
3. Holiday calendar: Pre-populate Indian national holidays for 2025 when a company is created (or offer a "Load Standard Holidays" button). National holidays: Republic Day (Jan 26), Holi (March 14), Good Friday (April 18), Ambedkar Jayanti (Apr 14), Labour Day (May 1), Independence Day (Aug 15), Gandhi Jayanti (Oct 2), Diwali (Oct 20-21), Christmas (Dec 25).

4. Frontend:
   - /settings/shifts — List shifts, create/edit shift modal
   - /settings/holidays — Calendar view of holidays with add/remove capability
   - These live under a Company Settings section in the sidebar (for admin only)

5. Integration: Update attendance payslip calculation to skip holidays as working days.
   Update leave application to skip holidays when counting leave days.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/services/attendance_service.py`
- `employee-management-system/backend/app/services/leave_service.py`
- `employee-management-system/backend/app/models/attendance.py`
- `employee-management-system/docs/DATABASE_SCHEMA.md`

---

## PROMPT 10: Asset Management

**Goal:** Track IT assets and assignments.

**Prompt:**
```
Build the Asset Management feature. Spec in new docs/04-NEW-FEATURES-SPECS.md (Asset Management section).

This is a straightforward CRUD feature with an assignment workflow.

Task:
1. Backend — Models: Create backend/app/models/asset.py (Asset, AssetAssignment).
2. Backend — Schemas + Service + Router: standard CRUD + assign/return endpoints.
3. Frontend:
   - /assets — Admin view: asset inventory table with status badges (available/assigned/in_repair)
     * Each row: asset tag, name, category, assigned to (if any), actions
     * "Assign" button → modal: select employee from dropdown, condition note
     * "Return" button → modal: condition note, notes
   - /my-assets — Employee view: list of assets currently assigned to them (read-only)
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/models/user.py`
- `employee-management-system/backend/app/api/v1/endpoints/users.py`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 11: Onboarding Workflow

**Goal:** Structured new-hire checklist.

**Prompt:**
```
Build the Onboarding Workflow feature. Spec in new docs/04-NEW-FEATURES-SPECS.md (Onboarding section).

Task:
1. Backend — Models: Create backend/app/models/onboarding.py (OnboardingTemplate, OnboardingTemplateTask, OnboardingInstance, OnboardingTaskCompletion).
2. Backend — Schemas + Service + Router.
3. Integration: When creating a new user (POST /api/v1/users), accept an optional onboarding_template_id. If provided, create an OnboardingInstance for that user.
4. Frontend:
   - /settings/onboarding — Admin view to manage templates (create/edit template, manage task list)
   - /onboarding — HR monitoring view: table of employees currently in onboarding with progress %
   - /my-onboarding — New employee view: their personal checklist with completion capability
5. Send a notification to the new employee when onboarding is assigned.
   Use existing notification system (notification_service.py).
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/backend/app/api/v1/endpoints/users.py`
- `employee-management-system/backend/app/services/user_service.py`
- `employee-management-system/backend/app/services/notification_service.py`
- `employee-management-system/backend/app/models/notification.py`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 12: Performance Reviews

**Goal:** Periodic employee evaluation cycles with manager reviews.

**Prompt:**
```
Build the Performance Review feature. Spec in new docs/04-NEW-FEATURES-SPECS.md (Performance Reviews section).

Task:
1. Backend — Models: Create backend/app/models/performance_review.py.
2. Backend — Schemas + Service + Router with these key operations:
   - Create review cycle (HR)
   - Auto-generate PerformanceReview records for each employee based on their team manager as reviewer
   - Employee submits self-assessment (fills self_score per criteria)
   - Manager submits review (fills reviewer_score per criteria + comments)
   - Admin publishes cycle (makes results visible to employees)

3. Frontend:
   - /performance — Admin/HR view: list of cycles, create cycle, monitor completion %
   - /performance/[cycle_id] — Cycle detail: table of all reviews with status
   - /my-reviews — Employee view: list of their past reviews (after published) + pending self-assessment
   - /performance/review/[review_id] — Review form (manager fills this for their reportee)

Reviewer assignment logic: use the team manager. If employee is in a team, their manager is their reviewer. If not in a team, fall back to any user with HR Manager role.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `new docs/03-PREMADE-ROLES-SPEC.md`
- `employee-management-system/backend/app/models/team.py`
- `employee-management-system/backend/app/services/team_service.py`
- `employee-management-system/backend/app/services/notification_service.py`
- `employee-management-system/docs/DATABASE_SCHEMA.md`
- `employee-management-system/docs/ARCHITECTURE.md`

---

## PROMPT 13: Alembic Migrations for All New Tables

**Goal:** Create database migration scripts for all new features.

**Prompt:**
```
Create Alembic migration scripts for all the new database tables added by the new features.

New models added:
- Announcement, AnnouncementRead (from announcements feature)
- Document, DocumentRequest (from document management)
- SalaryStructure, PayrollRun, Payslip (from payroll)
- ExpenseCategory, Expense (from expense management)
- Asset, AssetAssignment (from asset management)
- Shift, EmployeeShift, Holiday (from shift management)
- OnboardingTemplate, OnboardingTemplateTask, OnboardingInstance, OnboardingTaskCompletion (from onboarding)
- ReviewCycle, ReviewCriteria, PerformanceReview, ReviewScore (from performance reviews)

Task:
1. Review existing migration structure in backend/alembic/versions/
2. Create a single new migration file: backend/alembic/versions/0002_add_new_features.py
3. The migration should:
   - Create all new ENUM types first
   - Create all new tables with correct columns, types, constraints
   - Add foreign keys referencing existing tables (companies, users, teams)
   - Add appropriate indexes: (company_id, ...) composite indexes per ARCHITECTURE.md conventions
4. Include the downgrade() function to reverse all changes.

Follow the exact patterns from existing migration files in backend/alembic/versions/.
```

**Context Files:**
- `employee-management-system/backend/alembic/versions/` (all existing migration files)
- `employee-management-system/backend/app/models/` (all new model files created in earlier prompts)
- `employee-management-system/docs/DATABASE_SCHEMA.md`
- `employee-management-system/docs/ARCHITECTURE.md`
- `employee-management-system/backend/ALEMBIC_QUICKSTART.md`

---

## PROMPT 14: Register New Features in Super Admin

**Goal:** Add all new features to the platform's feature registry so they can be toggled per company.

**Prompt:**
```
The platform has a Feature registry managed by the super admin. New features need to be registered there so they can be added to plans and enabled per company.

Task:
1. Update backend/scripts/seed.py to add the new features:
   - ANNOUNCEMENTS: "Announcements & Noticeboard"
   - DOCUMENTS: "Document Management"
   - PAYROLL: "Payroll Management"
   - EXPENSES: "Expense Management"
   - ASSETS: "Asset Management"
   - ONBOARDING: "Onboarding Workflow"
   - OFFBOARDING: "Offboarding Workflow"
   - PERFORMANCE: "Performance Reviews"
   - SHIFTS: "Shift Management"
   - HOLIDAYS: "Holiday Calendar"

2. For each feature, add its feature_pages (routes):
   - ANNOUNCEMENTS: /announcements (admin view), /my-announcements (employee view -- though same page, different display)
   - DOCUMENTS: /documents, /my-documents
   - PAYROLL: /payroll, /my-payslips
   - EXPENSES: /expenses
   - ASSETS: /assets, /my-assets
   - ONBOARDING: /onboarding, /my-onboarding, /settings/onboarding
   - PERFORMANCE: /performance, /my-reviews
   - SHIFTS: /settings/shifts
   - HOLIDAYS: /settings/holidays

3. Update the plan definitions in seed.py:
   - Starter plan: USER_MGMT + ATTENDANCE + LEAVE + ANNOUNCEMENTS + DOCUMENTS + HOLIDAYS
   - Growth plan: Everything in Starter + TEAM + CRM + PROJECT + TASK + EXPENSES + ASSETS + ONBOARDING + SHIFTS + PAYROLL
   - Business plan: Everything + PERFORMANCE + OFFBOARDING

Make the seed script idempotent (check if feature exists before creating).
```

**Context Files:**
- `new docs/01-FEATURES-OVERVIEW.md`
- `employee-management-system/backend/scripts/seed.py`
- `employee-management-system/backend/app/models/feature.py` (or wherever Feature model is)
- `employee-management-system/backend/app/api/v1/endpoints/features.py`
- `employee-management-system/docs/DATABASE_SCHEMA.md`

---

## PROMPT 15: Company Settings Page

**Goal:** Build the Company Settings section where admins configure working days, shifts, and other preferences.

**Prompt:**
```
Build the Company Settings feature in the frontend. This is an admin-only section.

Task:
1. Backend: Create/update an endpoint GET/PUT /api/v1/company/settings that handles the company_settings fields defined in new docs/04-NEW-FEATURES-SPECS.md (Company Settings section).
   Add a company_settings table or extend the existing companies table with these fields.

2. Frontend: Create a Settings section in the sidebar (admin only, under a "Settings" group).
   - /settings — General settings page: working days toggle (Mon-Fri checkboxes), timezone picker, currency, date format
   - /settings/shifts — Shift management (from Prompt 9)
   - /settings/holidays — Holiday calendar (from Prompt 9)
   - /settings/onboarding — Onboarding templates (from Prompt 11)
   - /settings/roles — Move the Roles tab here from User Management (or keep it there, just add link)

For the general settings form, use React Hook Form + Zod validation. All settings save immediately on submit with a success toast.
```

**Context Files:**
- `new docs/04-NEW-FEATURES-SPECS.md`
- `employee-management-system/frontend/src/app/(dashboard)/` (existing pages for layout reference)
- `employee-management-system/frontend/src/components/layout/sidebar.tsx`
- `employee-management-system/backend/app/models/company.py` (or equivalent)
- `employee-management-system/backend/app/api/v1/endpoints/` (for endpoint pattern reference)
- `employee-management-system/docs/ARCHITECTURE.md`
