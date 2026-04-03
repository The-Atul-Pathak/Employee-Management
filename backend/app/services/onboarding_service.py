from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import (
    OnboardingInstance,
    OnboardingStatus,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OnboardingTaskCompletion,
    TaskCompletionStatus,
)
from app.models.user import User
from app.schemas.onboarding import (
    InstanceCreate,
    InstanceDetail,
    InstanceItem,
    InstanceListResponse,
    OnboardingUserInfo,
    TaskCompletionItem,
    TaskCompletionUpdate,
    TemplateCreate,
    TemplateDetail,
    TemplateItem,
    TemplateListResponse,
    TemplateTaskItem,
    TemplateUpdate,
)
from app.schemas.user import PaginationMeta


class OnboardingService:
    # ── Templates ──────────────────────────────────────────────────────────────

    async def list_templates(
        self, db: AsyncSession, company_id: uuid.UUID
    ) -> TemplateListResponse:
        stmt = (
            select(OnboardingTemplate)
            .where(
                OnboardingTemplate.company_id == company_id,
                OnboardingTemplate.deleted_at.is_(None),
            )
            .order_by(OnboardingTemplate.is_default.desc(), OnboardingTemplate.created_at.desc())
        )
        templates = (await db.execute(stmt)).scalars().all()

        # Count tasks per template
        t_ids = [t.id for t in templates]
        counts: dict[uuid.UUID, int] = {}
        if t_ids:
            count_stmt = (
                select(OnboardingTemplateTask.template_id, func.count().label("cnt"))
                .where(OnboardingTemplateTask.template_id.in_(t_ids))
                .group_by(OnboardingTemplateTask.template_id)
            )
            for row in (await db.execute(count_stmt)).all():
                counts[row[0]] = row[1]

        return TemplateListResponse(
            data=[
                TemplateItem(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    is_default=t.is_default,
                    task_count=counts.get(t.id, 0),
                    created_at=t.created_at,
                )
                for t in templates
            ]
        )

    async def get_template_detail(
        self, db: AsyncSession, company_id: uuid.UUID, template_id: uuid.UUID
    ) -> TemplateDetail:
        stmt = select(OnboardingTemplate).where(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.company_id == company_id,
            OnboardingTemplate.deleted_at.is_(None),
        )
        template = (await db.execute(stmt)).scalar_one_or_none()
        if template is None:
            raise LookupError("Template not found")

        task_stmt = (
            select(OnboardingTemplateTask)
            .where(OnboardingTemplateTask.template_id == template_id)
            .order_by(OnboardingTemplateTask.order_index)
        )
        tasks = (await db.execute(task_stmt)).scalars().all()

        return TemplateDetail(
            id=template.id,
            name=template.name,
            description=template.description,
            is_default=template.is_default,
            task_count=len(tasks),
            created_at=template.created_at,
            tasks=[TemplateTaskItem.model_validate(t) for t in tasks],
        )

    async def create_template(
        self, db: AsyncSession, company_id: uuid.UUID, data: TemplateCreate
    ) -> TemplateDetail:
        template = OnboardingTemplate(
            company_id=company_id,
            name=data.name,
            description=data.description,
            is_default=data.is_default,
        )
        db.add(template)
        await db.flush()

        tasks = []
        for task_data in data.tasks:
            task = OnboardingTemplateTask(
                template_id=template.id,
                title=task_data.title,
                description=task_data.description,
                assignee_type=task_data.assignee_type,
                day_offset=task_data.day_offset,
                order_index=task_data.order_index,
                is_required=task_data.is_required,
            )
            db.add(task)
            tasks.append(task)
        await db.flush()

        return TemplateDetail(
            id=template.id,
            name=template.name,
            description=template.description,
            is_default=template.is_default,
            task_count=len(tasks),
            created_at=template.created_at,
            tasks=[TemplateTaskItem.model_validate(t) for t in tasks],
        )

    async def update_template(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        template_id: uuid.UUID,
        data: TemplateUpdate,
    ) -> TemplateItem:
        stmt = select(OnboardingTemplate).where(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.company_id == company_id,
            OnboardingTemplate.deleted_at.is_(None),
        )
        template = (await db.execute(stmt)).scalar_one_or_none()
        if template is None:
            raise LookupError("Template not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        await db.flush()

        count_stmt = select(func.count()).select_from(OnboardingTemplateTask).where(
            OnboardingTemplateTask.template_id == template_id
        )
        count = (await db.execute(count_stmt)).scalar_one()

        return TemplateItem(
            id=template.id,
            name=template.name,
            description=template.description,
            is_default=template.is_default,
            task_count=count,
            created_at=template.created_at,
        )

    async def delete_template(
        self, db: AsyncSession, company_id: uuid.UUID, template_id: uuid.UUID
    ) -> None:
        stmt = select(OnboardingTemplate).where(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.company_id == company_id,
            OnboardingTemplate.deleted_at.is_(None),
        )
        template = (await db.execute(stmt)).scalar_one_or_none()
        if template is None:
            raise LookupError("Template not found")
        template.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    # ── Instances ──────────────────────────────────────────────────────────────

    async def list_instances(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> InstanceListResponse:
        filters = [
            OnboardingInstance.company_id == company_id,
            OnboardingInstance.deleted_at.is_(None),
        ]
        total_stmt = select(func.count()).select_from(OnboardingInstance).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(OnboardingInstance)
            .where(*filters)
            .order_by(OnboardingInstance.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        instances = (await db.execute(stmt)).scalars().all()

        emp_ids = {i.employee_id for i in instances}
        tmpl_ids = {i.template_id for i in instances if i.template_id}

        users: dict[uuid.UUID, User] = {}
        if emp_ids:
            user_stmt = select(User).where(User.id.in_(emp_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        templates: dict[uuid.UUID, OnboardingTemplate] = {}
        if tmpl_ids:
            tmpl_stmt = select(OnboardingTemplate).where(OnboardingTemplate.id.in_(tmpl_ids))
            for t in (await db.execute(tmpl_stmt)).scalars().all():
                templates[t.id] = t

        # Get completion counts
        inst_ids = [i.id for i in instances]
        completion_counts: dict[uuid.UUID, tuple[int, int]] = {}
        if inst_ids:
            for instance in instances:
                comp_stmt = select(OnboardingTaskCompletion).where(
                    OnboardingTaskCompletion.instance_id == instance.id
                )
                comps = (await db.execute(comp_stmt)).scalars().all()
                done = sum(1 for c in comps if c.status == TaskCompletionStatus.completed)
                completion_counts[instance.id] = (done, len(comps))

        items = []
        for i in instances:
            emp = users.get(i.employee_id)
            tmpl = templates.get(i.template_id) if i.template_id else None
            done, total_tasks = completion_counts.get(i.id, (0, 0))
            items.append(InstanceItem(
                id=i.id,
                employee=OnboardingUserInfo(id=emp.id, name=emp.name, emp_id=emp.emp_id) if emp else None,
                template_id=i.template_id,
                template_name=tmpl.name if tmpl else None,
                start_date=i.start_date,
                target_complete_date=i.target_complete_date,
                status=i.status,
                completed_tasks=done,
                total_tasks=total_tasks,
                created_at=i.created_at,
            ))

        return InstanceListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def create_instance(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: InstanceCreate,
    ) -> InstanceDetail:
        instance = OnboardingInstance(
            company_id=company_id,
            employee_id=data.employee_id,
            template_id=data.template_id,
            start_date=data.start_date,
            target_complete_date=data.target_complete_date,
            status=OnboardingStatus.in_progress,
        )
        db.add(instance)
        await db.flush()

        # Create task completions from template
        tasks: list[OnboardingTemplateTask] = []
        template_name: str | None = None
        if data.template_id:
            task_stmt = (
                select(OnboardingTemplateTask)
                .where(OnboardingTemplateTask.template_id == data.template_id)
                .order_by(OnboardingTemplateTask.order_index)
            )
            tasks = list((await db.execute(task_stmt)).scalars().all())

            tmpl_stmt = select(OnboardingTemplate).where(OnboardingTemplate.id == data.template_id)
            tmpl = (await db.execute(tmpl_stmt)).scalar_one_or_none()
            if tmpl:
                template_name = tmpl.name

            for task in tasks:
                completion = OnboardingTaskCompletion(
                    instance_id=instance.id,
                    template_task_id=task.id,
                    status=TaskCompletionStatus.pending,
                )
                db.add(completion)
            await db.flush()

        emp_stmt = select(User).where(User.id == data.employee_id)
        emp = (await db.execute(emp_stmt)).scalar_one_or_none()

        return InstanceDetail(
            id=instance.id,
            employee=OnboardingUserInfo(id=emp.id, name=emp.name, emp_id=emp.emp_id) if emp else None,
            template_id=instance.template_id,
            template_name=template_name,
            start_date=instance.start_date,
            target_complete_date=instance.target_complete_date,
            status=instance.status,
            completed_tasks=0,
            total_tasks=len(tasks),
            created_at=instance.created_at,
            tasks=[
                TaskCompletionItem(
                    id=t.id,
                    template_task_id=t.id,
                    task_title=t.title,
                    task_description=t.description,
                    assignee_type=t.assignee_type,
                    day_offset=t.day_offset,
                    is_required=t.is_required,
                    status=TaskCompletionStatus.pending,
                    completed_by=None,
                    completed_at=None,
                    notes=None,
                )
                for t in tasks
            ],
        )

    async def get_instance_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        instance_id: uuid.UUID,
    ) -> InstanceDetail:
        stmt = select(OnboardingInstance).where(
            OnboardingInstance.id == instance_id,
            OnboardingInstance.company_id == company_id,
            OnboardingInstance.deleted_at.is_(None),
        )
        instance = (await db.execute(stmt)).scalar_one_or_none()
        if instance is None:
            raise LookupError("Onboarding instance not found")

        return await self._build_instance_detail(db, instance)

    async def complete_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        instance_id: uuid.UUID,
        task_id: uuid.UUID,
        completed_by: uuid.UUID,
        data: TaskCompletionUpdate,
    ) -> InstanceDetail:
        comp_stmt = select(OnboardingTaskCompletion).where(
            OnboardingTaskCompletion.id == task_id,
            OnboardingTaskCompletion.instance_id == instance_id,
        )
        comp = (await db.execute(comp_stmt)).scalar_one_or_none()
        if comp is None:
            raise LookupError("Task not found")

        comp.status = data.status
        comp.notes = data.notes
        if data.status == TaskCompletionStatus.completed:
            comp.completed_by = completed_by
            comp.completed_at = datetime.now(timezone.utc)
        await db.flush()

        # Check if all tasks done
        inst_stmt = select(OnboardingInstance).where(OnboardingInstance.id == instance_id)
        instance = (await db.execute(inst_stmt)).scalar_one_or_none()
        if instance:
            all_comps_stmt = select(OnboardingTaskCompletion).where(
                OnboardingTaskCompletion.instance_id == instance_id
            )
            all_comps = (await db.execute(all_comps_stmt)).scalars().all()
            required = [c for c in all_comps]
            if all(c.status in (TaskCompletionStatus.completed, TaskCompletionStatus.skipped) for c in required):
                instance.status = OnboardingStatus.completed
                await db.flush()

        return await self._build_instance_detail(db, instance)

    async def _build_instance_detail(
        self, db: AsyncSession, instance: OnboardingInstance
    ) -> InstanceDetail:
        emp_stmt = select(User).where(User.id == instance.employee_id)
        emp = (await db.execute(emp_stmt)).scalar_one_or_none()

        template_name: str | None = None
        if instance.template_id:
            tmpl_stmt = select(OnboardingTemplate).where(OnboardingTemplate.id == instance.template_id)
            tmpl = (await db.execute(tmpl_stmt)).scalar_one_or_none()
            if tmpl:
                template_name = tmpl.name

        comp_stmt = select(OnboardingTaskCompletion).where(
            OnboardingTaskCompletion.instance_id == instance.id
        )
        completions = (await db.execute(comp_stmt)).scalars().all()

        task_ids = [c.template_task_id for c in completions]
        tasks: dict[uuid.UUID, OnboardingTemplateTask] = {}
        if task_ids:
            task_stmt = select(OnboardingTemplateTask).where(OnboardingTemplateTask.id.in_(task_ids))
            for t in (await db.execute(task_stmt)).scalars().all():
                tasks[t.id] = t

        done = sum(1 for c in completions if c.status == TaskCompletionStatus.completed)

        task_items = []
        for c in sorted(completions, key=lambda x: tasks.get(x.template_task_id, x).order_index if hasattr(tasks.get(x.template_task_id, x), 'order_index') else 0):
            t = tasks.get(c.template_task_id)
            task_items.append(TaskCompletionItem(
                id=c.id,
                template_task_id=c.template_task_id,
                task_title=t.title if t else "",
                task_description=t.description if t else None,
                assignee_type=t.assignee_type if t else "hr",
                day_offset=t.day_offset if t else 0,
                is_required=t.is_required if t else True,
                status=c.status,
                completed_by=c.completed_by,
                completed_at=c.completed_at,
                notes=c.notes,
            ))

        return InstanceDetail(
            id=instance.id,
            employee=OnboardingUserInfo(id=emp.id, name=emp.name, emp_id=emp.emp_id) if emp else None,
            template_id=instance.template_id,
            template_name=template_name,
            start_date=instance.start_date,
            target_complete_date=instance.target_complete_date,
            status=instance.status,
            completed_tasks=done,
            total_tasks=len(completions),
            created_at=instance.created_at,
            tasks=task_items,
        )


onboarding_service = OnboardingService()
