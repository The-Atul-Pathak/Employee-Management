# rAIze EMS — Feature Set & Industry Standards Research

## Current Platform State

The platform already has these working modules:
- **Attendance Management** — mark, view, bulk operations
- **Leave Management** — apply, approve, balance tracking
- **Team Management** — create teams, assign manager, add members
- **Sales CRM (Leads)** — pipeline, interactions, lead-to-project conversion
- **Project Delivery** — planning, milestones, status workflow
- **Task Execution** — assignment, dependencies, approval workflow
- **User Management** — CRUD, sessions, custom roles + features RBAC
- **Notifications** — in-app, 12 event types
- **Reports** — attendance, leaves, projects (CSV/JSON)
- **Super Admin Portal** — companies, plans, features, subscriptions

---

## Industry Standard Features Gap Analysis

For a mid-size business EMS targeting Indian companies (10–200 employees), industry benchmarks (Zoho People, GreytHR, Keka, Darwinbox) show the following modules are expected:

### Missing / Incomplete Features

| Priority | Feature | Reason Gap Exists |
|----------|---------|-------------------|
| HIGH | **Payroll Management** | Core HR feature — most platforms die without it |
| HIGH | **Shift & Schedule Management** | Attendance without shifts is half a product |
| HIGH | **Document Management** | Offer letters, contracts, ID proofs — compliance need |
| HIGH | **Announcements / Noticeboard** | Internal comms — widely expected |
| MEDIUM | **Performance Reviews** | Appraisals — common in HR suites |
| MEDIUM | **Expense Management** | Reimbursements — sales/field teams need this |
| MEDIUM | **Asset Management** | Laptop/phone assignments — IT tracking |
| MEDIUM | **Employee Self-Service Portal** | Profile edit requests, document downloads |
| MEDIUM | **Onboarding Workflow** | Structured new-hire process |
| MEDIUM | **Offboarding Workflow** | Exit checklist, FnF settlement |
| LOW | **Job Posting & Recruitment** | Applicant tracking — ATS basics |
| LOW | **Training & Learning** | Course assignment, completion tracking |
| LOW | **Helpdesk / Ticketing** | IT requests, HR queries |
| LOW | **Survey & Feedback** | Pulse surveys, eNPS |
| LOW | **Calendar Integration** | Sync leaves with Google/Outlook |

---

## Recommended Pre-Made Roles

Based on industry standard HRMS patterns, these pre-made roles should ship with every new company:

| Role Name | Feature Bundle | Description |
|-----------|---------------|-------------|
| **Company Admin** | ALL features | System-level admin, bypasses all role checks |
| **HR Manager** | USER_MGMT + ATTENDANCE + LEAVE + PAYROLL + DOCUMENT + ONBOARDING + OFFBOARDING + REPORTS | Full HR operations |
| **HR Executive** | ATTENDANCE + LEAVE + USER_MGMT (view only) + REPORTS | Day-to-day HR tasks, no user creation |
| **Team Lead** | TEAM + TASK + ATTENDANCE (view team) + LEAVE (view team) | Manage own team's work and attendance |
| **Sales Manager** | CRM + PROJECT + TASK + REPORTS | Sales pipeline and delivery oversight |
| **Sales Executive** | CRM (own leads only) + TASK (own tasks) | Individual contributor in sales |
| **Project Manager** | PROJECT + TASK + TEAM (view) + REPORTS | Delivery management |
| **Developer / Contributor** | TASK + PROJECT (view) | IC who executes tasks |
| **Finance** | PAYROLL + EXPENSE + REPORTS | Finance team access |
| **Employee** | LEAVE (own) + ATTENDANCE (own) + TASK (own) + DOCUMENT (own) | Base employee, self-service only |

> **Note:** The "pre-made" roles are templates. The company admin can edit, delete, or create new roles. They are seeded at company creation time.

---

## Role-Permission Matrix (Feature Level)

This matrix shows what each role can DO within each feature:

### Legend
- **FULL** — Can create, read, update, delete all records in the feature
- **MANAGE** — Can read all + create/update, no delete
- **VIEW_ALL** — Read-only access to all records in the feature
- **OWN** — Can only see/edit their own records
- **TEAM** — Can see/edit records for their direct team members
- **—** — No access

| Feature | Admin | HR Manager | HR Executive | Team Lead | Sales Manager | Sales Exec | PM | Dev | Finance | Employee |
|---------|-------|-----------|-------------|-----------|--------------|-----------|-----|-----|---------|---------|
| Users | FULL | MANAGE | VIEW_ALL | — | — | — | — | — | — | OWN profile |
| Attendance | FULL | FULL | MANAGE | TEAM | VIEW_ALL | OWN | OWN | OWN | OWN | OWN |
| Leave | FULL | FULL | MANAGE | TEAM approve | VIEW_ALL | OWN | OWN | OWN | OWN | OWN |
| Teams | FULL | VIEW_ALL | — | OWN team | VIEW_ALL | — | VIEW_ALL | — | — | — |
| CRM/Leads | FULL | — | — | — | FULL | OWN leads | — | — | — | — |
| Projects | FULL | — | — | — | FULL | VIEW | FULL | VIEW | — | — |
| Tasks | FULL | — | — | TEAM | FULL | OWN | FULL | OWN | — | OWN |
| Payroll | FULL | FULL | — | — | — | — | — | — | FULL | OWN slip |
| Documents | FULL | FULL | MANAGE | — | — | — | — | — | — | OWN |
| Reports | FULL | FULL | LIMITED | — | LIMITED | — | LIMITED | — | FULL | — |
| Announcements | FULL | MANAGE | — | TEAM | — | — | — | — | — | VIEW |
| Expenses | FULL | VIEW_ALL | — | TEAM approve | OWN | OWN | OWN | OWN | FULL | OWN |
| Assets | FULL | VIEW_ALL | — | — | — | — | — | — | — | OWN |

---

## Feature Card Visibility by Role

### What "cards" appear on the Dashboard for each role:

**Company Admin / HR Manager:**
- Today's Attendance Summary (Present / Absent / On Leave / Total)
- Pending Leave Approvals (count + quick approve)
- Pending Task Approvals (count)
- Active Projects Summary
- Open Leads (if CRM enabled)
- Module Navigation Grid (all enabled modules)
- Recent Activity Feed
- Team Headcount Stats

**HR Executive:**
- Today's Attendance Summary (read-only)
- Pending Leave Approvals
- Employee Directory quick-search
- Module cards for HR features only

**Team Lead:**
- My Team's Attendance Today (just their team)
- Team's Pending Leaves
- My Team's Tasks Status (pending / in progress / done)
- My Assigned Tasks
- Module cards for their features

**Sales Manager / Sales Executive:**
- My Leads Pipeline summary (by stage)
- Today's Follow-ups Due
- My Tasks
- Open/Won/Lost stats (manager sees all, exec sees own)

**Project Manager / Developer:**
- Active Projects status
- My Assigned Tasks
- Task deadlines approaching
- Project milestone summary

**Regular Employee:**
- Greeting + attendance status for today
- My Leave Balance summary
- My Pending Leave Requests
- My Assigned Tasks (top 5)
- Quick action buttons: Apply Leave, View Attendance
