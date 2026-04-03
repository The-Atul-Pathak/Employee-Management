# New Features — Detailed Specifications

Features to build to reach industry standard. Each spec includes the data model,
API endpoints, and UI requirements.

---

## FEATURE: Announcements / Noticeboard

### Purpose
Internal broadcast system. Replace email blasts and WhatsApp forwards.

### Data Model

```
announcements
  id              UUID PK
  company_id      UUID FK (tenant isolation)
  title           VARCHAR(255) NOT NULL
  body            TEXT NOT NULL (store as HTML from rich text editor)
  author_id       UUID FK → users
  target_type     ENUM: all | roles | teams  (who can see this)
  target_ids      UUID[] NULLABLE (role IDs or team IDs depending on target_type)
  is_pinned       BOOLEAN DEFAULT false
  expires_at      TIMESTAMP NULLABLE
  created_at      TIMESTAMP
  updated_at      TIMESTAMP
  deleted_at      TIMESTAMP NULLABLE

announcement_reads
  id              UUID PK
  announcement_id UUID FK
  user_id         UUID FK
  read_at         TIMESTAMP
  UNIQUE (announcement_id, user_id)
```

### API Endpoints

```
GET    /api/v1/announcements         — List visible announcements for current user
POST   /api/v1/announcements         — Create announcement (admin/HR)
GET    /api/v1/announcements/{id}    — Get single announcement (mark as read)
PUT    /api/v1/announcements/{id}    — Update announcement
DELETE /api/v1/announcements/{id}    — Soft delete
POST   /api/v1/announcements/{id}/read — Mark as read
GET    /api/v1/announcements/unread-count — For notification badge
```

### UI Components
- AnnouncementCard: title, author, date, preview text, unread indicator
- AnnouncementDetail: full rich text view, who posted, when, read count
- CreateAnnouncementForm: title, rich text body, target audience picker, pin toggle, expiry date
- Unread count badge in sidebar navigation

---

## FEATURE: Document Management

### Purpose
Central store for company documents + per-employee document folders.

### Data Model

```
documents
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(255)
  description     TEXT NULLABLE
  category        ENUM: hr_policy | legal | template | employee_doc | other
  doc_type        ENUM: company | employee
  employee_id     UUID NULLABLE FK → users (null = company-wide doc)
  file_url        VARCHAR(500)  (stored in S3/local storage)
  file_size       INTEGER (bytes)
  mime_type       VARCHAR(100)
  uploaded_by     UUID FK → users
  visibility      ENUM: all | roles  (for company-wide docs)
  visible_to_roles UUID[] NULLABLE
  version         INTEGER DEFAULT 1
  created_at      TIMESTAMP
  updated_at      TIMESTAMP
  deleted_at      TIMESTAMP NULLABLE

document_requests
  id              UUID PK
  company_id      UUID FK
  employee_id     UUID FK → users
  document_name   VARCHAR(255)
  requested_by    UUID FK → users
  status          ENUM: pending | uploaded | acknowledged
  deadline        DATE NULLABLE
  created_at      TIMESTAMP
```

### API Endpoints

```
GET    /api/v1/documents                     — List company documents visible to user
POST   /api/v1/documents/company             — Upload company document
GET    /api/v1/documents/employee/{user_id}  — List employee's personal documents
POST   /api/v1/documents/employee/{user_id}  — Upload employee document
DELETE /api/v1/documents/{id}               — Soft delete
GET    /api/v1/documents/{id}/download       — Get signed download URL
POST   /api/v1/documents/request            — Request document from employee
GET    /api/v1/documents/requests           — List pending requests for self
PUT    /api/v1/documents/requests/{id}      — Fulfill request (upload)
```

### UI Components
- DocumentGrid: Card layout per category with file type icon
- DocumentUploadModal: Drag-and-drop + file picker, category, visibility settings
- EmployeeDocumentFolder: Per-employee document list (HR view)
- MyDocuments: Employee self-service view
- DocumentRequestBanner: Notification to employee that HR needs a document

---

## FEATURE: Payroll Management

### Purpose
Monthly salary processing with payslip generation.
Note: India-specific (PF 12% employee + 12% employer, ESI if salary < 21k, TDS)

### Data Model

```
salary_structures
  id              UUID PK
  company_id      UUID FK
  employee_id     UUID FK → users
  effective_from  DATE
  ctc_monthly     DECIMAL(12,2)
  basic           DECIMAL(12,2)
  hra             DECIMAL(12,2)
  special_allowance DECIMAL(12,2)
  pf_employer     DECIMAL(12,2)
  pf_employee     DECIMAL(12,2)
  esi_employer    DECIMAL(12,2) NULLABLE
  esi_employee    DECIMAL(12,2) NULLABLE
  professional_tax DECIMAL(12,2)
  created_at      TIMESTAMP
  updated_at      TIMESTAMP

payroll_runs
  id              UUID PK
  company_id      UUID FK
  month           INTEGER (1-12)
  year            INTEGER
  status          ENUM: draft | approved | paid
  total_gross     DECIMAL(14,2)
  total_deductions DECIMAL(14,2)
  total_net       DECIMAL(14,2)
  run_by          UUID FK → users
  approved_by     UUID NULLABLE FK → users
  run_at          TIMESTAMP
  paid_at         TIMESTAMP NULLABLE
  UNIQUE (company_id, month, year)

payslips
  id              UUID PK
  company_id      UUID FK
  payroll_run_id  UUID FK
  employee_id     UUID FK
  month           INTEGER
  year            INTEGER
  working_days    INTEGER
  present_days    DECIMAL(5,2)  (half days counted as 0.5)
  leave_days      DECIMAL(5,2)
  lop_days        DECIMAL(5,2)  (Loss of Pay)
  gross_salary    DECIMAL(12,2)
  basic           DECIMAL(12,2)
  hra             DECIMAL(12,2)
  special_allowance DECIMAL(12,2)
  pf_deduction    DECIMAL(12,2)
  esi_deduction   DECIMAL(12,2) NULLABLE
  pt_deduction    DECIMAL(12,2)
  tds_deduction   DECIMAL(12,2) NULLABLE
  other_deductions DECIMAL(12,2) DEFAULT 0
  net_salary      DECIMAL(12,2)
  created_at      TIMESTAMP
```

### API Endpoints

```
GET    /api/v1/payroll/salary-structures              — List all (admin)
POST   /api/v1/payroll/salary-structures              — Create/update salary structure
GET    /api/v1/payroll/salary-structures/{user_id}    — Get for specific employee
POST   /api/v1/payroll/run                            — Initiate payroll run for month/year
GET    /api/v1/payroll/runs                           — List all runs
GET    /api/v1/payroll/runs/{id}                      — Get run details
PUT    /api/v1/payroll/runs/{id}/approve              — Approve payroll run
PUT    /api/v1/payroll/runs/{id}/mark-paid            — Mark as paid
GET    /api/v1/payroll/payslips                       — List all payslips (admin)
GET    /api/v1/payroll/payslips/my                    — My payslips (employee)
GET    /api/v1/payroll/payslips/{id}/download         — Download PDF payslip
```

### Calculation Logic

```
Payslip calculation per employee per month:
1. Get their salary structure (most recent effective_from ≤ month start)
2. Get attendance for the month:
   - Count present days, half days (count as 0.5), LOP days
   - Days on approved leave DO NOT count as LOP
3. Calculate gross: (gross_salary / working_days) × (present_days + leave_days)
4. Deduct: PF employee share, ESI employee share (if eligible), PT
5. Net = Gross - Deductions
```

---

## FEATURE: Expense Management

### Purpose
Employee expense claims and reimbursement tracking.

### Data Model

```
expense_categories
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(100)  (Travel, Food, Software, Equipment, Other)
  created_at      TIMESTAMP

expenses
  id              UUID PK
  company_id      UUID FK
  employee_id     UUID FK → users
  category_id     UUID FK → expense_categories
  amount          DECIMAL(10,2)
  currency        VARCHAR(3) DEFAULT 'INR'
  expense_date    DATE
  description     TEXT
  receipt_url     VARCHAR(500) NULLABLE
  status          ENUM: draft | submitted | approved | rejected | paid
  submitted_at    TIMESTAMP NULLABLE
  reviewed_by     UUID NULLABLE FK → users
  reviewed_at     TIMESTAMP NULLABLE
  review_notes    TEXT NULLABLE
  paid_at         TIMESTAMP NULLABLE
  created_at      TIMESTAMP
  updated_at      TIMESTAMP
```

### API Endpoints

```
GET    /api/v1/expenses                    — List expenses (admin: all, user: own)
POST   /api/v1/expenses                    — Create expense claim
PUT    /api/v1/expenses/{id}              — Update draft expense
PUT    /api/v1/expenses/{id}/submit       — Submit for approval
PUT    /api/v1/expenses/{id}/approve      — Approve expense (manager/finance)
PUT    /api/v1/expenses/{id}/reject       — Reject expense with reason
PUT    /api/v1/expenses/{id}/mark-paid    — Mark as paid (finance)
DELETE /api/v1/expenses/{id}             — Delete draft expense
GET    /api/v1/expenses/summary           — Monthly summary stats
```

---

## FEATURE: Asset Management

### Purpose
Track company-owned IT assets and their assignment to employees.

### Data Model

```
assets
  id              UUID PK
  company_id      UUID FK
  asset_tag       VARCHAR(50) UNIQUE within company
  name            VARCHAR(255)
  category        ENUM: laptop | phone | monitor | keyboard | headset | other
  brand           VARCHAR(100) NULLABLE
  model           VARCHAR(100) NULLABLE
  serial_number   VARCHAR(100) NULLABLE
  purchase_date   DATE NULLABLE
  purchase_price  DECIMAL(10,2) NULLABLE
  status          ENUM: available | assigned | in_repair | retired
  notes           TEXT NULLABLE
  created_at      TIMESTAMP
  updated_at      TIMESTAMP

asset_assignments
  id              UUID PK
  company_id      UUID FK
  asset_id        UUID FK → assets
  employee_id     UUID FK → users
  assigned_by     UUID FK → users
  assigned_at     TIMESTAMP
  returned_at     TIMESTAMP NULLABLE
  condition_out   VARCHAR(100) NULLABLE  (condition when assigned)
  condition_in    VARCHAR(100) NULLABLE  (condition when returned)
  notes           TEXT NULLABLE
```

### API Endpoints

```
GET    /api/v1/assets                        — List all assets (admin)
POST   /api/v1/assets                        — Add asset
PUT    /api/v1/assets/{id}                  — Update asset details
GET    /api/v1/assets/{id}                  — Asset detail with assignment history
POST   /api/v1/assets/{id}/assign           — Assign to employee
POST   /api/v1/assets/{id}/return           — Record return
GET    /api/v1/assets/employee/{user_id}    — Assets assigned to employee
GET    /api/v1/assets/my                    — My assigned assets (employee self-service)
```

---

## FEATURE: Onboarding Workflow

### Purpose
Structured first-week checklist for new employees. Ensures nothing falls through the cracks.

### Data Model

```
onboarding_templates
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(255)  (e.g., "Software Developer Onboarding")
  description     TEXT NULLABLE
  is_default      BOOLEAN DEFAULT false
  created_at      TIMESTAMP

onboarding_template_tasks
  id              UUID PK
  template_id     UUID FK
  title           VARCHAR(255)
  description     TEXT NULLABLE
  assignee_type   ENUM: hr | it | manager | employee
  day_offset      INTEGER  (due on day N after joining date)
  order_index     INTEGER
  is_required     BOOLEAN DEFAULT true

onboarding_instances
  id              UUID PK
  company_id      UUID FK
  employee_id     UUID FK → users
  template_id     UUID FK NULLABLE
  start_date      DATE
  target_complete_date DATE NULLABLE
  status          ENUM: in_progress | completed | overdue
  created_at      TIMESTAMP

onboarding_task_completions
  id              UUID PK
  instance_id     UUID FK
  template_task_id UUID FK
  status          ENUM: pending | completed | skipped
  completed_by    UUID NULLABLE FK → users
  completed_at    TIMESTAMP NULLABLE
  notes           TEXT NULLABLE
```

### API Endpoints

```
GET    /api/v1/onboarding/templates              — List templates
POST   /api/v1/onboarding/templates              — Create template
PUT    /api/v1/onboarding/templates/{id}         — Update template
GET    /api/v1/onboarding/instances              — List active onboardings (HR)
POST   /api/v1/onboarding/instances              — Start onboarding for employee
GET    /api/v1/onboarding/instances/{id}         — Get onboarding checklist
PUT    /api/v1/onboarding/instances/{id}/tasks/{task_id} — Complete/skip a task
GET    /api/v1/onboarding/my                     — Get my onboarding checklist (employee)
```

---

## FEATURE: Shift Management

### Purpose
Define work shifts (day/night/custom) and assign to employees.
Connects with attendance for auto-validation.

### Data Model

```
shifts
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(100)  (Morning Shift, Night Shift, Flexible)
  start_time      TIME
  end_time        TIME
  grace_minutes   INTEGER DEFAULT 15  (late by this many minutes = still "present")
  is_default      BOOLEAN DEFAULT false
  created_at      TIMESTAMP

employee_shifts
  id              UUID PK
  company_id      UUID FK
  employee_id     UUID FK
  shift_id        UUID FK
  effective_from  DATE
  effective_to    DATE NULLABLE
  UNIQUE (company_id, employee_id, effective_from)
```

### API Endpoints

```
GET    /api/v1/shifts                            — List shifts
POST   /api/v1/shifts                            — Create shift
PUT    /api/v1/shifts/{id}                      — Update shift
DELETE /api/v1/shifts/{id}                      — Delete shift
POST   /api/v1/shifts/assign                    — Assign shift to employee(s)
GET    /api/v1/shifts/employee/{user_id}        — Get employee's current shift
```

---

## FEATURE: Holiday Calendar

### Purpose
Define public and company holidays. Attendance and leave calculations use this.

### Data Model

```
holidays
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(255)
  date            DATE
  holiday_type    ENUM: national | regional | company
  is_optional     BOOLEAN DEFAULT false
  year            INTEGER
  created_at      TIMESTAMP
  UNIQUE (company_id, date)
```

### API Endpoints

```
GET    /api/v1/holidays          — List holidays for current year
POST   /api/v1/holidays          — Add holiday
POST   /api/v1/holidays/bulk     — Bulk import standard holidays
DELETE /api/v1/holidays/{id}    — Remove holiday
```

---

## FEATURE: Performance Reviews

### Purpose
Periodic evaluation of employee performance. Manager rates reportee.

### Data Model

```
review_cycles
  id              UUID PK
  company_id      UUID FK
  name            VARCHAR(255)  (Q1 2025 Review, Annual 2024)
  cycle_type      ENUM: quarterly | half_yearly | annual | custom
  review_from     DATE
  review_to       DATE
  submission_deadline DATE
  status          ENUM: draft | active | closed | published
  created_at      TIMESTAMP

review_criteria
  id              UUID PK
  cycle_id        UUID FK
  name            VARCHAR(255)  (Quality of Work, Teamwork, etc.)
  description     TEXT NULLABLE
  max_score       INTEGER DEFAULT 5
  order_index     INTEGER

performance_reviews
  id              UUID PK
  company_id      UUID FK
  cycle_id        UUID FK
  employee_id     UUID FK → users (being reviewed)
  reviewer_id     UUID FK → users (reviewing)
  status          ENUM: pending | self_assessment_done | in_review | submitted | published
  overall_score   DECIMAL(3,2) NULLABLE
  reviewer_comments TEXT NULLABLE
  employee_response TEXT NULLABLE
  submitted_at    TIMESTAMP NULLABLE
  published_at    TIMESTAMP NULLABLE

review_scores
  id              UUID PK
  review_id       UUID FK
  criteria_id     UUID FK
  self_score      INTEGER NULLABLE
  reviewer_score  INTEGER NULLABLE
  reviewer_comment TEXT NULLABLE
```

---

## FEATURE: Company Settings Enhancement

### Purpose
Company-wide configuration for the HR system.

### Settings to Add

```
company_settings (extend existing or new table)
  company_id              UUID PK FK
  working_days            INTEGER[] DEFAULT [1,2,3,4,5]  (1=Mon...7=Sun)
  work_hours_per_day      DECIMAL(4,2) DEFAULT 8.0
  attendance_cutoff_time  TIME DEFAULT '10:00:00'
  leave_year_start        INTEGER DEFAULT 1  (month: 1=April for Indian FY, or 1=Jan)
  auto_mark_absent        BOOLEAN DEFAULT false
  allow_self_attendance   BOOLEAN DEFAULT false
  probation_days          INTEGER DEFAULT 90
  notice_period_days      INTEGER DEFAULT 30
  currency                VARCHAR(3) DEFAULT 'INR'
  timezone                VARCHAR(50) DEFAULT 'Asia/Kolkata'
  date_format             VARCHAR(20) DEFAULT 'DD/MM/YYYY'
```
