# Pre-Made Roles Specification

When a new company is onboarded, the system should automatically seed these
roles. The company admin can edit, delete, or create new ones — but these
templates provide a working starting point.

---

## Role 1: HR Manager

**Purpose:** Full HR department head with complete HR operations access.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| User Management | FULL (create, edit, deactivate users + manage roles) |
| Attendance | FULL (view all, mark for anyone, edit past records) |
| Leave Management | FULL (view all, approve/reject, adjust balances) |
| Team Management | VIEW_ALL (see all teams, cannot create/delete) |
| Documents | FULL (upload, manage, request from employees) |
| Announcements | MANAGE (create, edit own announcements) |
| Payroll | FULL (run payroll, manage salary structures) |
| Reports | FULL (all report types, all employees) |
| Onboarding | FULL |
| Offboarding | FULL |
| Performance Reviews | FULL |

**Dashboard Cards Shown:**
- Today's attendance summary (all employees)
- Pending leave approvals count
- New employee onboarding in-progress
- Recent announcements drafts
- Payroll due reminder (if current month not run)
- Pending expense claims
- Module navigation grid (all HR modules)

---

## Role 2: HR Executive

**Purpose:** Day-to-day HR operations. Cannot create users or run payroll.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| User Management | VIEW_ALL only (no create/edit/deactivate) |
| Attendance | MANAGE (view all, mark today, cannot edit past) |
| Leave Management | MANAGE (view all, approve/reject, cannot adjust balances) |
| Documents | MANAGE (upload company docs, view employee docs, request uploads) |
| Announcements | VIEW_ALL |
| Reports | LIMITED (attendance + leave reports only) |

**Dashboard Cards Shown:**
- Today's attendance summary
- Pending leave approvals count
- Module navigation for HR features

---

## Role 3: Team Lead

**Purpose:** First-level manager who oversees a direct team.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| Team Management | OWN (view/manage their own team only) |
| Attendance | TEAM (view their team's attendance, mark if permitted) |
| Leave Management | TEAM (view team leaves, approve/reject if permitted) |
| Tasks | TEAM (create tasks for team, see team's tasks, approve completions) |
| Projects | VIEW (read-only overview of projects their team is on) |
| Announcements | TEAM (can post to their team only) |

**Dashboard Cards Shown:**
- My team's attendance today (scoped to team)
- Team's pending leave requests
- Team's task status summary (pending / in-progress / blocked)
- My own assigned tasks
- Upcoming leaves in team (calendar view)

---

## Role 4: Sales Manager

**Purpose:** Sales department head managing pipeline and reps.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| CRM / Leads | FULL (all leads, reassign, analytics) |
| Projects | MANAGE (create projects from won leads, manage delivery) |
| Tasks | FULL (within their projects) |
| Reports | LIMITED (CRM + project reports only) |
| Announcements | VIEW |
| Expense Management | TEAM (approve team's expenses) |

**Dashboard Cards Shown:**
- Pipeline value by stage (Kanban summary)
- Today's follow-ups due (count)
- Open leads / won this month / lost this month
- Team's task progress
- Overdue tasks

---

## Role 5: Sales Executive

**Purpose:** Individual sales contributor.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| CRM / Leads | OWN (only their own leads) |
| Tasks | OWN (only their own tasks) |
| Leave Management | OWN (apply, view own) |
| Attendance | OWN (view own) |
| Expense Management | OWN (submit expense claims) |
| Announcements | VIEW |

**Dashboard Cards Shown:**
- My leads by stage
- Today's follow-ups due
- My tasks (top 5 urgent)
- My leave balance
- Greeting + today's attendance

---

## Role 6: Project Manager

**Purpose:** Manages project delivery. No HR access, no CRM access.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| Projects | FULL (manage all projects, planning, milestones) |
| Tasks | FULL (create, assign, approve within projects) |
| Team Management | VIEW_ALL |
| Reports | LIMITED (project reports only) |
| Leave Management | OWN + VIEW for planning purposes |
| Attendance | OWN |
| Announcements | VIEW |

**Dashboard Cards Shown:**
- Active projects status summary
- Tasks due this week (across all projects)
- Blocked tasks count
- Team availability (who is on leave today)
- Upcoming project milestones

---

## Role 7: Developer / Contributor

**Purpose:** Individual contributor executing tasks within projects.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| Tasks | OWN (view and update own tasks only) |
| Projects | VIEW (read-only, only projects they're on) |
| Leave Management | OWN |
| Attendance | OWN |
| Announcements | VIEW |
| Documents | VIEW (company docs only) + OWN (personal docs) |

**Dashboard Cards Shown:**
- Greeting + today's attendance
- My assigned tasks (sorted by priority + due date)
- My leave balance
- Upcoming leave (if any approved)
- Project progress for projects I'm on

---

## Role 8: Finance

**Purpose:** Finance team member with payroll and expense visibility.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| Payroll | FULL (run payroll, manage salary structures, download payslips) |
| Expense Management | FULL (approve all, export to accounting) |
| Reports | FULL |
| User Management | VIEW_ALL (to check employee records for payroll) |
| Announcements | VIEW |

**Dashboard Cards Shown:**
- Payroll status this month (run / not run)
- Pending expense approvals count
- Total payroll amount this month
- Employees pending salary structure setup

---

## Role 9: Employee (Base Role)

**Purpose:** Default role for all staff with no other specific role. Pure self-service.

**Feature Permissions:**
| Feature | Permission Level |
|---------|----------------|
| Attendance | OWN (view own records only) |
| Leave Management | OWN (apply, view own balance and history) |
| Tasks | OWN (view and update own tasks only) |
| Documents | OWN (view shared company docs + own personal docs) |
| Payroll | OWN (view own payslips only) |
| Expense Management | OWN (submit expense claims, track status) |
| Announcements | VIEW |

**Dashboard Cards Shown:**
- Greeting + today's status
- My leave balance
- My attendance this month summary
- My pending leave applications
- My assigned tasks
- Quick actions: Apply Leave, View Attendance, Download Payslip

---

## Seeding Logic

When a new company is created:

```
1. Create role "HR Manager" → assign features: [USER_MGMT, ATTENDANCE, LEAVE, PAYROLL, DOCUMENTS, ANNOUNCEMENTS, REPORTS, ONBOARDING, OFFBOARDING, PERFORMANCE]
2. Create role "HR Executive" → assign features: [ATTENDANCE, LEAVE, DOCUMENTS, REPORTS (limited)]
3. Create role "Team Lead" → assign features: [TEAM, ATTENDANCE (team), LEAVE (team), TASK, PROJECT (view), ANNOUNCEMENTS (team)]
4. Create role "Sales Manager" → assign features: [CRM, PROJECT, TASK, REPORTS (limited), EXPENSE]
5. Create role "Sales Executive" → assign features: [CRM (own), TASK (own), LEAVE, ATTENDANCE, EXPENSE (own)]
6. Create role "Project Manager" → assign features: [PROJECT, TASK, TEAM (view), REPORTS (limited)]
7. Create role "Developer" → assign features: [TASK (own), PROJECT (view), LEAVE, ATTENDANCE, DOCUMENTS (view)]
8. Create role "Finance" → assign features: [PAYROLL, EXPENSE, REPORTS, USER_MGMT (view)]
9. Create role "Employee" → assign features: [ATTENDANCE (own), LEAVE, TASK (own), DOCUMENTS (view), PAYROLL (own), EXPENSE (own)]
```

Only assign features that the company's subscription plan includes. If CRM is not in their plan, skip creating CRM-related roles or skip assigning that feature to the role.

---

## Permission Granularity Model

Current system works at "feature page" level — a role either has access to a page or doesn't. For future:

**Recommended enhancement: Action-level permissions**

Each feature should define actions (beyond just page access):

```
attendance:view_own         — see own attendance
attendance:view_team        — see team attendance  
attendance:view_all         — see all employees' attendance
attendance:mark             — mark attendance for others
attendance:edit_past        — edit attendance for past dates
attendance:export           — download attendance reports
```

This enables finer control, e.g.: HR Executive can `attendance:view_all` and `attendance:mark` but NOT `attendance:edit_past`.

For the current implementation, this can be approximated by creating separate feature pages per permission level (e.g., "Attendance - Admin View" vs "Attendance - My View") and assigning the right page to each role.
