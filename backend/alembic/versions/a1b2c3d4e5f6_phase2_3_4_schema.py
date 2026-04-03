"""Phase 2/3/4: announcements, documents, expenses, payroll, assets, onboarding, performance

Revision ID: a1b2c3d4e5f6
Revises: dba3ef618d9c
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dba3ef618d9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Phase 2: Announcements ────────────────────────────────────────────────

    op.create_table(
        'announcements',
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Enum('all', 'roles', 'teams', name='announcementtargettype'), nullable=False),
        sa.Column('target_ids', postgresql.ARRAY(sa.UUID(as_uuid=True)), nullable=True),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('author_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_announcements_id'), ['id'], unique=False)
        batch_op.create_index('ix_announcements_company_id', ['company_id'], unique=False)

    op.create_table(
        'announcement_reads',
        sa.Column('announcement_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['announcement_id'], ['announcements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('announcement_id', 'user_id'),
    )

    # ── Phase 2: Documents ────────────────────────────────────────────────────

    op.create_table(
        'documents',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=True),
        sa.Column('document_type', sa.Enum('offer_letter', 'contract', 'id_proof', 'payslip', 'appraisal', 'other', name='documenttype'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_id'), ['id'], unique=False)
        batch_op.create_index('ix_documents_employee_id', ['employee_id'], unique=False)

    op.create_table(
        'document_requests',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('requested_by', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.Enum('offer_letter', 'contract', 'id_proof', 'payslip', 'appraisal', 'other', name='documenttype'), nullable=False, postgresql_existing_type=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'fulfilled', 'rejected', name='documentrequeststatus'), nullable=False),
        sa.Column('fulfilled_document_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fulfilled_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('document_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_requests_id'), ['id'], unique=False)

    # ── Phase 2: Expenses ─────────────────────────────────────────────────────

    op.create_table(
        'expense_categories',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('expense_categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_expense_categories_id'), ['id'], unique=False)

    op.create_table(
        'expenses',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('receipt_path', sa.String(length=500), nullable=True),
        sa.Column('receipt_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'reimbursed', name='expensestatus'), nullable=False),
        sa.Column('reviewer_id', sa.UUID(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_expenses_id'), ['id'], unique=False)
        batch_op.create_index('ix_expenses_employee_id', ['employee_id'], unique=False)

    # ── Phase 3: Payroll ──────────────────────────────────────────────────────

    op.create_table(
        'salary_structures',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('effective_from', sa.String(length=10), nullable=False),
        sa.Column('ctc_monthly', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('basic', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('hra', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('special_allowance', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pf_employer', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pf_employee', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('esi_employer', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('esi_employee', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('professional_tax', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'employee_id', 'effective_from', name='uq_salary_structure'),
    )
    with op.batch_alter_table('salary_structures', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_salary_structures_id'), ['id'], unique=False)
        batch_op.create_index('ix_salary_structures_employee_id', ['employee_id'], unique=False)

    op.create_table(
        'payroll_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('draft', 'approved', 'paid', name='payrollrunstatus'), nullable=False),
        sa.Column('total_gross', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('total_deductions', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('total_net', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('run_by', sa.UUID(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'month', 'year', name='uq_payroll_run'),
    )
    with op.batch_alter_table('payroll_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payroll_runs_id'), ['id'], unique=False)

    op.create_table(
        'payslips',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('payroll_run_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('working_days', sa.Integer(), nullable=False),
        sa.Column('present_days', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('leave_days', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('lop_days', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('gross_salary', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('basic', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('hra', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('special_allowance', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pf_deduction', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('esi_deduction', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pt_deduction', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tds_deduction', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('other_deductions', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('net_salary', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payroll_run_id'], ['payroll_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payroll_run_id', 'employee_id', name='uq_payslip'),
    )
    with op.batch_alter_table('payslips', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payslips_id'), ['id'], unique=False)
        batch_op.create_index('ix_payslips_employee_id', ['employee_id'], unique=False)

    # ── Phase 4: Assets ───────────────────────────────────────────────────────

    op.create_table(
        'assets',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('asset_tag', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.Enum('laptop', 'phone', 'monitor', 'keyboard', 'headset', 'other', name='assetcategory'), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('purchase_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('status', sa.Enum('available', 'assigned', 'in_repair', 'retired', name='assetstatus'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'asset_tag', name='uq_asset_tag'),
    )
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assets_id'), ['id'], unique=False)

    op.create_table(
        'asset_assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('assigned_by', sa.UUID(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('returned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('condition_out', sa.String(length=255), nullable=True),
        sa.Column('condition_in', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('asset_assignments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_asset_assignments_id'), ['id'], unique=False)

    # ── Phase 4: Onboarding ───────────────────────────────────────────────────

    op.create_table(
        'onboarding_templates',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('onboarding_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_onboarding_templates_id'), ['id'], unique=False)

    op.create_table(
        'onboarding_template_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('assignee_type', sa.Enum('hr', 'it', 'manager', 'employee', name='assigneetype'), nullable=False),
        sa.Column('day_offset', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['template_id'], ['onboarding_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('onboarding_template_tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_onboarding_template_tasks_id'), ['id'], unique=False)

    op.create_table(
        'onboarding_instances',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('target_complete_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('in_progress', 'completed', 'overdue', name='onboardingstatus'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['onboarding_templates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('onboarding_instances', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_onboarding_instances_id'), ['id'], unique=False)
        batch_op.create_index('ix_onboarding_instances_employee_id', ['employee_id'], unique=False)

    op.create_table(
        'onboarding_task_completions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('instance_id', sa.UUID(), nullable=False),
        sa.Column('template_task_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'skipped', name='taskcompletionstatus'), nullable=False),
        sa.Column('completed_by', sa.UUID(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['completed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['instance_id'], ['onboarding_instances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_task_id'], ['onboarding_template_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('onboarding_task_completions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_onboarding_task_completions_id'), ['id'], unique=False)

    # ── Phase 4: Performance Reviews ──────────────────────────────────────────

    op.create_table(
        'review_cycles',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('cycle_type', sa.Enum('quarterly', 'half_yearly', 'annual', 'custom', name='reviewcycletype'), nullable=False),
        sa.Column('review_from', sa.Date(), nullable=False),
        sa.Column('review_to', sa.Date(), nullable=False),
        sa.Column('submission_deadline', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'active', 'closed', 'published', name='reviewcyclestatus'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('review_cycles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_cycles_id'), ['id'], unique=False)

    op.create_table(
        'review_criteria',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cycle_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_score', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['cycle_id'], ['review_cycles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('review_criteria', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_criteria_id'), ['id'], unique=False)

    op.create_table(
        'performance_reviews',
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('cycle_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('reviewer_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'self_assessment_done', 'in_review', 'submitted', 'published', name='performancereviewstatus'), nullable=False),
        sa.Column('overall_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('reviewer_comments', sa.Text(), nullable=True),
        sa.Column('employee_response', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cycle_id'], ['review_cycles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('performance_reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_performance_reviews_id'), ['id'], unique=False)
        batch_op.create_index('ix_performance_reviews_employee_id', ['employee_id'], unique=False)

    op.create_table(
        'review_scores',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('review_id', sa.UUID(), nullable=False),
        sa.Column('criteria_id', sa.UUID(), nullable=False),
        sa.Column('self_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('reviewer_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('reviewer_comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['criteria_id'], ['review_criteria.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_id'], ['performance_reviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'criteria_id', name='uq_review_score'),
    )
    with op.batch_alter_table('review_scores', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_scores_id'), ['id'], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('review_scores')
    op.drop_table('performance_reviews')
    op.drop_table('review_criteria')
    op.drop_table('review_cycles')
    op.drop_table('onboarding_task_completions')
    op.drop_table('onboarding_instances')
    op.drop_table('onboarding_template_tasks')
    op.drop_table('onboarding_templates')
    op.drop_table('asset_assignments')
    op.drop_table('assets')
    op.drop_table('payslips')
    op.drop_table('payroll_runs')
    op.drop_table('salary_structures')
    op.drop_table('expenses')
    op.drop_table('expense_categories')
    op.drop_table('document_requests')
    op.drop_table('documents')
    op.drop_table('announcement_reads')
    op.drop_table('announcements')

    # Drop enums
    for name in [
        'performancereviewstatus', 'reviewcyclestatus', 'reviewcycletype',
        'taskcompletionstatus', 'onboardingstatus', 'assigneetype',
        'assetstatus', 'assetcategory',
        'payrollrunstatus',
        'expensestatus', 'documentrequeststatus', 'documenttype',
        'announcementtargettype',
    ]:
        op.execute(f'DROP TYPE IF EXISTS {name}')
