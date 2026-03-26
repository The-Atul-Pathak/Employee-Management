# Database Schema Reference

## Core Enums
```sql
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'terminated');
CREATE TYPE leave_status AS ENUM ('pending', 'approved', 'rejected', 'cancelled');
CREATE TYPE attendance_status AS ENUM ('present', 'absent', 'leave', 'half_day');
CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'follow_up', 'negotiation', 'won', 'lost');
CREATE TYPE project_status AS ENUM ('unassigned', 'assigned', 'planned', 'in_progress', 'completed', 'on_hold');
CREATE TYPE task_status AS ENUM ('pending_approval', 'active', 'in_progress', 'review', 'done', 'rejected', 'blocked');
CREATE TYPE leave_type AS ENUM ('casual', 'sick', 'earned', 'unpaid', 'comp_off');
CREATE TYPE company_status AS ENUM ('trial', 'active', 'suspended', 'cancelled');
```

## Tables (Listed by Module)

### Platform
- **platform_admins**: id(UUID), name, email, password_hash, role(SUPER_ADMIN|SUPPORT), status, last_login_at, created_at, updated_at
- **platform_sessions**: id(UUID), admin_id(FK), ip_address, user_agent, created_at, expires_at

### Companies
- **companies**: id(UUID), company_name, legal_name, domain, industry, employee_size_range, status(company_status), settings(JSONB), created_at, updated_at, deleted_at
- **company_contacts**: id(UUID), company_id(FK), name, email, phone, designation, is_primary, created_at

### Subscriptions & Features
- **plans**: id(UUID), name, price_monthly, price_yearly, max_employees, is_active, created_at
- **features**: id(UUID), code(UNIQUE), name, description, created_at
- **company_subscriptions**: id(UUID), company_id(FK), plan_id(FK), start_date, end_date, status, auto_renew, created_at
- **company_features**: id(UUID), company_id(FK), feature_id(FK), enabled, enabled_at (UNIQUE: company_id + feature_id)
- **feature_pages**: id(UUID), feature_id(FK), page_code, page_name, route, description (UNIQUE: feature_id + page_code)

### Users & Access Control
- **users**: id(UUID), company_id(FK), emp_id, name, email, password_hash, status(user_status), is_company_admin, profile_photo_url, created_at, updated_at, deleted_at (UNIQUE: company_id + emp_id) (UNIQUE: company_id + email WHERE email IS NOT NULL)
- **user_sessions**: id(UUID), user_id(FK), company_id(FK), refresh_token_hash, ip_address, user_agent, created_at, expires_at
- **user_profiles**: id(UUID), user_id(FK UNIQUE), company_id(FK), phone, alt_phone, address_line_1, address_line_2, city, state, postal_code, country, emergency_contact_name, emergency_contact_phone, date_of_birth, date_of_joining, created_at, updated_at
- **roles**: id(UUID), company_id(FK), name, description, created_at (UNIQUE: company_id + name)
- **user_roles**: id(UUID), user_id(FK), role_id(FK) (UNIQUE: user_id + role_id)
- **roles_features**: id(UUID), role_id(FK), feature_id(FK) (UNIQUE: role_id + feature_id)

### HR
- **attendance**: id(UUID), company_id(FK), user_id(FK), date, status(attendance_status), check_in_time, check_out_time, marked_by(FK), notes, created_at, updated_at (UNIQUE: company_id + user_id + date)
- **leave_requests**: id(UUID), company_id(FK), user_id(FK), leave_type(leave_type), start_date, end_date, total_days, reason, status(leave_status), applied_at, reviewed_by(FK), reviewed_at, review_notes, created_at
- **leave_balances**: id(UUID), company_id(FK), user_id(FK), leave_type(leave_type), year, total_quota, used, remaining, created_at, updated_at (UNIQUE: company_id + user_id + leave_type + year)

### Teams
- **teams**: id(UUID), company_id(FK), name, description, manager_id(FK→users), status, created_at, updated_at, deleted_at (UNIQUE: company_id + name)
- **team_members**: id(UUID), team_id(FK), user_id(FK), added_at (UNIQUE: team_id + user_id)

### CRM
- **leads**: id(UUID), company_id(FK), client_name, contact_email, contact_phone, status(lead_status), source, notes, assigned_to(FK→users), created_by(FK→users), next_follow_up_date, last_interaction_at, project_created, created_at, updated_at
- **lead_interactions**: id(UUID), lead_id(FK), interaction_type, description, logged_by(FK→users), interaction_at, created_at

### Projects
- **projects**: id(UUID), company_id(FK), lead_id(FK), project_name, assigned_team_id(FK→teams), status(project_status), created_at, updated_at
- **project_planning**: id(UUID), project_id(FK UNIQUE), company_id(FK), planned_start_date, planned_end_date, description, scope, milestones(JSONB), deliverables(JSONB), estimated_budget, priority, client_requirements, risk_notes, assumptions, dependencies, internal_notes, created_at, updated_at
- **project_tasks**: id(UUID), project_id(FK), company_id(FK), title, description, assigned_to(FK→users), created_by(FK→users), start_date, due_date, estimated_hours, priority, status(task_status), dependency_task_id(FK→project_tasks), created_at, updated_at
- **task_updates**: id(UUID), task_id(FK), company_id(FK), updated_by(FK→users), update_type, old_status, new_status, note, created_at
- **project_status_logs**: id(UUID), project_id(FK), company_id(FK), old_status, new_status, changed_by(FK→users), reason, created_at

### System
- **audit_trail**: id(UUID), company_id(FK), user_id(FK), entity_type, entity_id, action, old_values(JSONB), new_values(JSONB), ip_address, created_at
- **notifications**: id(UUID), company_id(FK), user_id(FK), title, message, type, is_read, entity_type, entity_id, created_at

## Key Indexes
- Every FK column gets an index
- (company_id, status) on users, leads, projects, teams
- (company_id, user_id, date) on attendance
- (company_id, user_id, leave_type, year) on leave_balances
- (company_id, next_follow_up_date) on leads
- (company_id, assigned_to, status) on project_tasks