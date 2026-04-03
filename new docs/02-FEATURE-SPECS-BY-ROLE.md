# Feature Specifications — Role-Based Views & Interactions

This document describes every feature, how it works for each role, and what
the UI should show per persona. This is the implementation source of truth for
role-differentiated views.

---

## FEATURE: Attendance Management

### What It Is
Daily tracking of employee presence. Supports: present, absent, half_day, on_leave.

### Admin / HR Manager View

**Page: /attendance (Attendance Dashboard)**

Layout: Date picker at top → defaults to today.

**Cards shown:**
1. **Daily Summary Card** — "42 Present | 5 Absent | 3 On Leave | 2 Half Day | 52 Total"
2. **Present Employees** — Scrollable list with avatar + name + emp_id + check-in time
3. **Absent Employees** — List with "Mark Present" override button per row
4. **On Leave** — List linked to approved leave records
5. **Half Day** — List

**Actions Available:**
- Change date → see any past day's attendance
- Mark/update attendance for any employee (dropdown: Present / Absent / Half Day / On Leave)
- Bulk mark attendance (select multiple → set status)
- Export attendance for selected date range (CSV)
- View attendance history for any individual employee (click name → modal)
- View monthly attendance report (navigate to /reports/attendance)

**Filters:** Department filter (if departments added), Team filter, Status filter

---

### HR Executive View
Same as HR Manager but **cannot edit** attendance retroactively beyond today.
Can mark attendance for today only.

---

### Team Lead View

**Page: /attendance (filtered to their team only)**

Shows only their direct team members. Same card layout but scoped:
1. **My Team Today** — Present / Absent / On Leave counts for team only
2. Employee list filtered to team members

**Actions Available:**
- View their team's attendance for any date
- Cannot mark/edit attendance (read-only by default, configurable)

---

### Employee View

**Page: /my-attendance**

NOT the main /attendance page. Employee sees:
1. **Personal Attendance Status Card for Today** — "Present" / "Absent" / status indicator
2. **Monthly Calendar View** — Color-coded calendar showing their attendance for the current month (green=present, red=absent, yellow=half_day, blue=leave)
3. **Attendance Summary** — Monthly stats: X days present, Y days absent, Z days leave
4. **History Table** — List view of past attendance records with date + status

**Actions Available:**
- Change month/year to view historical attendance
- NO ability to mark or edit their own attendance (HR does this)

---

## FEATURE: Leave Management

### What It Is
Leave application, approval, balance tracking. Types: Casual, Sick, Earned, Unpaid, Comp Off.

### Admin / HR Manager View

**Page: /leaves**

**Tabs:**
1. **Pending Approvals** — All leave requests awaiting action
   - Each row: Employee name | Leave type | Dates | Days | Reason | Applied on | Approve / Reject buttons
   - Approve opens a confirmation + optional comment field
   - Reject opens a mandatory reason field

2. **All Requests** — Complete history with filters:
   - Filter by employee, leave type, status (pending/approved/rejected/cancelled), date range
   - Export to CSV

3. **Leave Balances** — Grid of all employees with balance per leave type
   - Search by employee name
   - Edit balance button (admin can adjust quotas manually)
   - Year selector

4. **Calendar View** — Month view showing who is on leave which day
   - Color-coded by leave type
   - Hover tooltip: Employee name, leave type, approved by

**Actions:**
- Approve / Reject any pending request
- Manually adjust leave balance for any employee
- Apply leave on behalf of an employee
- View leave history for any employee

---

### Team Lead View

**Page: /leaves (filtered to team)**

**Tabs:**
1. **Team Pending** — Leave requests from their team only
   - Can approve/reject if permission granted (configurable per role)
2. **Team Leave Calendar** — See who from their team is away
3. **Team Balances** — Read-only view of team's leave balances

---

### Employee View

**Page: /my-leaves**

**Cards shown:**
1. **Leave Balance Card** — Visual display:
   - Casual: 8 / 12 remaining | progress bar
   - Sick: 3 / 6 remaining | progress bar
   - Earned: 10 / 15 remaining | progress bar
   - Unpaid: Unlimited (shown differently)

2. **Upcoming Approved Leaves** — List of future approved leaves

3. **My Leave History** — Table with all past requests + statuses

4. **Apply Leave Button** → Opens form:
   - Leave Type (dropdown)
   - From Date (date picker)
   - To Date (date picker)
   - Reason (textarea, optional)
   - Days count auto-calculated (excluding weekends/holidays if configured)
   - Validates: sufficient balance, no overlapping approved leave

**Actions:**
- Apply for leave
- Cancel pending or future approved leave (with confirmation)
- View status of pending applications

---

## FEATURE: Team Management

### What It Is
Organizational grouping. One manager per team. Multiple members.

### Admin View

**Page: /teams**

Grid of team cards, each showing:
- Team name
- Manager avatar + name
- Member count
- Active projects linked

**Actions:**
- Create team (name, manager, initial members)
- Edit team (rename, change manager, add/remove members)
- Delete team (soft delete, warns if projects attached)
- View full team roster

**Team Detail Page: /teams/[id]**
- Team header (name, manager)
- Member list with role badges
- Linked projects
- Recent team activity

---

### Team Lead View

**Page: /teams (shows only their team)**

Team Lead sees a single card for their own team.

**Team Detail Page:**
- Can view their team's full roster
- Can see their team's task summary
- CANNOT add/remove members (admin action)
- CANNOT change the manager

---

### Employee View

**Page: /teams (read-only, shows their team only)**

Card showing:
- Their team name
- Manager contact info
- Their teammates list (name + role)
- Cannot edit anything

---

## FEATURE: CRM / Leads

### What It Is
Sales pipeline from lead creation to deal won/lost and project conversion.

### Admin / Sales Manager View

**Page: /leads**

**Views: Table view + Kanban board toggle**

Kanban columns: New → Contacted → Follow-up → Negotiation → Won / Lost

**Each lead card shows:**
- Company / contact name
- Value (₹)
- Assigned sales rep
- Last interaction date
- Next follow-up date (highlighted if overdue)

**Admin-only features:**
- See ALL leads from ALL sales reps
- Reassign leads between reps
- View pipeline analytics: conversion rate, avg deal size, revenue forecast

**Lead Detail Page:**
- Full contact info
- Activity log (all interactions with timestamps)
- Add interaction (call, email, meeting, demo)
- Convert to Project (when status = won)

---

### Sales Executive View

**Page: /leads (own leads only)**

- ONLY sees leads assigned to them
- Can create new leads (auto-assigned to self)
- Can update status, log interactions
- CANNOT see other reps' leads
- CANNOT reassign leads
- CANNOT see pipeline analytics

---

### Other Roles
- No access to /leads page

---

## FEATURE: Project Delivery

### What It Is
Client project lifecycle from assignment through completion.

### Admin / Project Manager View

**Page: /projects**

Table showing all projects with:
- Project name | Client | Status | Team | Start date | Target date | Budget

**Actions:**
- Create project
- Assign to team
- View/edit planning details (milestones, deliverables, budget, risks)
- Change status with notes
- View audit trail of status changes

**Project Detail: /projects/[id]**
- Planning tab: scope, milestones, deliverables, risks
- Tasks tab: all tasks within project
- Team tab: assigned team
- Activity tab: status change history

---

### Developer / Contributor View

**Page: /projects (only projects they are on)**

- Read-only project overview
- Can see tasks assigned to them within the project
- CANNOT edit project details, milestones, or budget

---

## FEATURE: Task Execution

### What It Is
Work items within projects. Workflow: pending_approval → active → in_progress → review → done.

### Admin / PM View

**Page: /tasks**

Full task board or table. Can:
- Create tasks and assign to users
- Approve/reject tasks in "pending_approval" state
- Review submitted tasks (move from "review" to "done" or send back)
- See all tasks across all projects
- Filter by project, assignee, status, priority

---

### Team Lead View

**Page: /tasks (filtered to team's tasks)**

- See tasks assigned to their team members
- Can approve team members' task completions for review
- Create tasks for team members

---

### Developer / Employee View

**Page: /my-tasks**

- Sees only tasks assigned to them
- Can update status: active → in_progress → review
- Can add progress notes
- CANNOT create, reassign, or approve tasks

---

## FEATURE: Announcements (NEW — to be built)

### What It Is
Internal broadcast system. Admin/HR posts announcements visible to all or targeted groups.

### Admin / HR View

**Page: /announcements**

- Create announcement: Title, Body (rich text), Target audience (all / specific roles / specific teams), Pinned (yes/no), Expiry date (optional)
- Edit/delete own announcements
- See view count per announcement
- See list of all announcements

### Employee View

- See announcements posted to "all" or their role/team
- Pinned announcements appear at top
- Unread indicator (bold + dot)
- Cannot post announcements

---

## FEATURE: Documents (NEW — to be built)

### What It Is
Company document store + employee personal documents.

### Admin / HR View

**Page: /documents**

**Tabs:**
1. **Company Documents** — HR policies, SOPs, holiday calendar, offer templates
   - Upload, categorize (HR Policy / Legal / Templates / Other)
   - Set visibility: All employees / Specific roles
   - Version history

2. **Employee Documents** — Per-employee folder
   - View/upload documents for any employee: offer letter, ID proof, appraisal letter
   - Request document from employee (they get a notification to upload)

### Employee View

**Page: /my-documents**

- See company documents shared with their role
- See their own personal document folder
- Download allowed, upload only when HR requests
- Cannot see other employees' documents

---

## FEATURE: Payroll (NEW — to be built)

### What It Is
Monthly salary processing, payslip generation, and basic compliance.

### Admin / HR Manager / Finance View

**Page: /payroll**

**Tabs:**
1. **Run Payroll** — Select month → Review auto-calculations → Approve → Mark as Paid
2. **Salary Structures** — Define CTC breakup per employee (Basic, HRA, allowances, deductions)
3. **Payslips** — Browse and download payslips for any employee for any month
4. **Deductions** — PF, ESI, TDS entries

### Employee View

**Page: /my-payslips**

- View and download their own payslips for any month
- See current salary structure (read-only)
- CANNOT see other employees' salaries

---

## FEATURE: Expense Management (NEW — to be built)

### What It Is
Claim and reimbursement of business expenses.

### Admin / Finance View

- See all expense claims
- Approve / reject with notes
- Export for accounting

### Manager / Team Lead View
- See and approve expenses for their team

### Employee View
- Submit expense claim: amount, category, date, receipt upload
- Track approval status
- See payment status (paid / pending)

---

## FEATURE: Asset Management (NEW — to be built)

### What It Is
Track company-owned devices and assets assigned to employees.

### Admin View
- Add assets (laptop, phone, etc.) with serial number
- Assign asset to employee
- Unassign and mark as returned
- Asset inventory overview

### Employee View
- See assets currently assigned to them
- Cannot edit anything

---

## FEATURE: Onboarding Workflow (NEW — to be built)

### What It Is
Structured checklist for new hires to complete in their first days.

### Admin / HR View
- Create onboarding templates (ordered task list)
- Assign template to new employee at creation time
- Monitor completion progress per new hire
- Complete admin-side tasks (IT setup, access provisioning)

### New Employee View
- Personal onboarding checklist
- Mark tasks complete
- Upload required documents
- Progress indicator

---

## FEATURE: Offboarding Workflow (NEW — to be built)

### What It Is
Exit process management.

### Admin / HR View
- Initiate offboarding for an employee (set exit date)
- Assign offboarding checklist
- Track: asset return, knowledge transfer, FnF status
- Generate experience letter

### Exiting Employee View
- See their offboarding tasks
- Acknowledge exit checklist items

---

## FEATURE: Performance Reviews (NEW — to be built)

### What It Is
Periodic employee evaluation cycles.

### Admin / HR View
- Create review cycle (quarterly / annual)
- Assign reviewers (manager reviews reportee)
- View all review scores and comments
- Publish results to employees

### Manager / Team Lead View
- Rate their team members on defined criteria
- Add comments per criterion
- Submit review before deadline

### Employee View
- See their own review results (after published)
- Self-assessment form (before manager reviews)
- Historical review records
