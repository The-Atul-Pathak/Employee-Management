from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.notification import NotificationType
from app.models.project import Project, ProjectStatus, ProjectTask, TaskStatus, TaskUpdate
from app.models.team import Team, TeamMember
from app.models.user import User, UserStatus
from app.schemas.task import TaskCreateRequest, TaskListItem, TaskListResponse, TaskUpdateRequest
from app.schemas.user import PaginationMeta


def _get_notification_service():
    from app.services.notification_service import notification_service
    return notification_service


ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.active: {TaskStatus.in_progress},
    TaskStatus.in_progress: {TaskStatus.review, TaskStatus.blocked},
}


class TaskService:
    async def list_tasks(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> TaskListResponse:
        if project_id is not None:
            await self._get_project_or_404(db, company_id, project_id)

        assignee = aliased(User)
        creator = aliased(User)
        latest_note = (
            select(TaskUpdate.note)
            .where(
                TaskUpdate.task_id == ProjectTask.id,
                TaskUpdate.company_id == company_id,
                TaskUpdate.note.is_not(None),
            )
            .order_by(TaskUpdate.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )

        filters = [
            ProjectTask.company_id == company_id,
            ProjectTask.deleted_at.is_(None),
        ]
        if project_id is not None:
            filters.append(ProjectTask.project_id == project_id)

        total_stmt = select(func.count()).select_from(ProjectTask).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(ProjectTask, Project.project_name, assignee.name, creator.name, latest_note)
            .join(Project, Project.id == ProjectTask.project_id)
            .outerjoin(assignee, assignee.id == ProjectTask.assigned_to)
            .outerjoin(creator, creator.id == ProjectTask.created_by)
            .where(*filters)
            .order_by(ProjectTask.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await db.execute(stmt)).all()
        items = [
            TaskListItem(
                id=task.id,
                project_id=task.project_id,
                project_name=project_name,
                title=task.title,
                description=task.description,
                assigned_to=task.assigned_to,
                assignee_name=assignee_name,
                created_by=task.created_by,
                creator_name=creator_name,
                start_date=task.start_date,
                due_date=task.due_date,
                estimated_hours=task.estimated_hours,
                priority=task.priority,
                status=task.status,
                dependency_task_id=task.dependency_task_id,
                latest_note=latest_note_value,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task, project_name, assignee_name, creator_name, latest_note_value in rows
        ]
        return TaskListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=(total + per_page - 1) // per_page if total else 0,
            ),
        )

    async def get_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> TaskListItem:
        assignee = aliased(User)
        creator = aliased(User)
        latest_note = (
            select(TaskUpdate.note)
            .where(
                TaskUpdate.task_id == ProjectTask.id,
                TaskUpdate.company_id == company_id,
                TaskUpdate.note.is_not(None),
            )
            .order_by(TaskUpdate.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(ProjectTask, Project.project_name, assignee.name, creator.name, latest_note)
            .join(Project, Project.id == ProjectTask.project_id)
            .outerjoin(assignee, assignee.id == ProjectTask.assigned_to)
            .outerjoin(creator, creator.id == ProjectTask.created_by)
            .where(
                ProjectTask.id == task_id,
                ProjectTask.company_id == company_id,
                ProjectTask.deleted_at.is_(None),
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise LookupError("Task not found")

        task, project_name, assignee_name, creator_name, latest_note_value = row
        return TaskListItem(
            id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            description=task.description,
            assigned_to=task.assigned_to,
            assignee_name=assignee_name,
            created_by=task.created_by,
            creator_name=creator_name,
            start_date=task.start_date,
            due_date=task.due_date,
            estimated_hours=task.estimated_hours,
            priority=task.priority,
            status=task.status,
            dependency_task_id=task.dependency_task_id,
            latest_note=latest_note_value,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    async def create_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TaskCreateRequest,
    ) -> ProjectTask:
        project, team = await self._get_project_and_team_or_404(db, company_id, project_id)
        self._ensure_project_in_progress(project)
        self._ensure_leader(team, user_id)
        self._validate_task_dates(data.start_date, data.due_date)

        assignee = await self._load_project_member(db, company_id, team.id, data.assigned_to)
        dependency_task_id = await self._validate_dependency_task(
            db=db,
            company_id=company_id,
            project_id=project_id,
            dependency_task_id=data.dependency_task_id,
        )

        task = ProjectTask(
            project_id=project.id,
            company_id=company_id,
            title=data.title.strip(),
            description=self._clean_optional_text(data.description),
            assigned_to=assignee.id if assignee else None,
            created_by=user_id,
            start_date=data.start_date,
            due_date=data.due_date,
            estimated_hours=data.estimated_hours,
            priority=self._clean_optional_text(data.priority),
            status=TaskStatus.active,
            dependency_task_id=dependency_task_id,
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)

        # Notify assignee if different from creator
        if assignee is not None and assignee.id != user_id:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=assignee.id,
                title="New Task Assigned",
                message=f"You have been assigned a new task: '{task.title}'.",
                notification_type=NotificationType.task_assigned,
                entity_type="project_task",
                entity_id=task.id,
            )

        return task

    async def suggest_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TaskCreateRequest,
    ) -> ProjectTask:
        project, team = await self._get_project_and_team_or_404(db, company_id, project_id)
        self._ensure_project_in_progress(project)
        self._validate_task_dates(data.start_date, data.due_date)
        is_member = await self._is_project_member(db, company_id, team.id, user_id)
        if not is_member:
            raise PermissionError("Only project team members can suggest tasks")
        if team.manager_id == user_id:
            raise PermissionError("Leader cannot use the suggest task flow")

        assignee = await self._load_project_member(db, company_id, team.id, data.assigned_to)
        dependency_task_id = await self._validate_dependency_task(
            db=db,
            company_id=company_id,
            project_id=project_id,
            dependency_task_id=data.dependency_task_id,
        )

        task = ProjectTask(
            project_id=project.id,
            company_id=company_id,
            title=data.title.strip(),
            description=self._clean_optional_text(data.description),
            assigned_to=assignee.id if assignee else None,
            created_by=user_id,
            start_date=data.start_date,
            due_date=data.due_date,
            estimated_hours=data.estimated_hours,
            priority=self._clean_optional_text(data.priority),
            status=TaskStatus.pending_approval,
            dependency_task_id=dependency_task_id,
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)

        # Notify team leader of suggested task
        if team.manager_id is not None:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=team.manager_id,
                title="Task Suggestion Pending Approval",
                message=f"A team member suggested a task: '{task.title}'. Review and approve or reject it.",
                notification_type=NotificationType.task_suggested,
                entity_type="project_task",
                entity_id=task.id,
            )

        return task

    async def approve_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        approve: bool,
    ) -> ProjectTask:
        task, project, team = await self._get_task_with_project_team_or_404(db, company_id, task_id)
        self._ensure_leader(team, user_id)
        if task.status != TaskStatus.pending_approval:
            raise ValueError("Only pending approval tasks can be reviewed")

        task.status = TaskStatus.active if approve else TaskStatus.rejected
        await db.flush()
        await db.refresh(task)

        # Notify the assignee of approval/rejection
        if task.assigned_to is not None:
            notif_type = NotificationType.task_approved if approve else NotificationType.task_rejected
            notif_title = "Task Approved" if approve else "Task Rejected"
            notif_msg = (
                f"Your suggested task '{task.title}' has been {'approved and is now active' if approve else 'rejected'}."
            )
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=task.assigned_to,
                title=notif_title,
                message=notif_msg,
                notification_type=notif_type,
                entity_type="project_task",
                entity_id=task.id,
            )

        return task

    async def update_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TaskUpdateRequest,
    ) -> ProjectTask:
        task, _, team = await self._get_task_with_project_team_or_404(db, company_id, task_id)
        is_admin = await self._is_company_admin(db, company_id, user_id)
        is_leader = team.manager_id == user_id
        is_assignee = task.assigned_to == user_id

        if not any([is_admin, is_leader, is_assignee]):
            raise PermissionError("You do not have permission to update this task")

        privileged_update = any(
            value is not None
            for value in [
                data.title,
                data.description,
                data.assigned_to,
                data.start_date,
                data.due_date,
                data.estimated_hours,
                data.priority,
                data.dependency_task_id,
            ]
        )
        if privileged_update and not (is_admin or is_leader):
            raise PermissionError("Only the project leader can edit task details")

        if privileged_update:
            self._validate_task_dates(data.start_date or task.start_date, data.due_date or task.due_date)
            if data.title is not None:
                task.title = data.title.strip()
            if data.description is not None:
                task.description = self._clean_optional_text(data.description)
            if data.assigned_to is not None:
                assignee = await self._load_project_member(db, company_id, team.id, data.assigned_to)
                task.assigned_to = assignee.id if assignee else None
            if data.start_date is not None:
                task.start_date = data.start_date
            if data.due_date is not None:
                task.due_date = data.due_date
            if data.estimated_hours is not None:
                task.estimated_hours = data.estimated_hours
            if data.priority is not None:
                task.priority = self._clean_optional_text(data.priority)
            if data.dependency_task_id is not None:
                task.dependency_task_id = await self._validate_dependency_task(
                    db=db,
                    company_id=company_id,
                    project_id=task.project_id,
                    dependency_task_id=data.dependency_task_id,
                )

        if data.note is not None:
            db.add(
                TaskUpdate(
                    task_id=task.id,
                    company_id=company_id,
                    updated_by=user_id,
                    update_type="note",
                    note=self._clean_optional_text(data.note),
                )
            )

        await db.flush()
        await db.refresh(task)
        return task

    async def update_task_status(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        new_status: TaskStatus,
        note: str | None,
    ) -> ProjectTask:
        task, _, team = await self._get_task_with_project_team_or_404(db, company_id, task_id)
        is_assignee = task.assigned_to == user_id
        is_leader = team.manager_id == user_id
        is_admin = await self._is_company_admin(db, company_id, user_id)

        if task.status == TaskStatus.review and new_status == TaskStatus.done:
            if not (is_leader or is_admin):
                raise PermissionError("Only the project leader can complete tasks in review")
        elif task.status == TaskStatus.review and new_status == TaskStatus.in_progress:
            if not (is_leader or is_admin):
                raise PermissionError("Only the project leader can request changes")
        else:
            if not is_assignee:
                raise PermissionError("Only the assignee can update task status")
            allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(task.status, set())
            if new_status not in allowed_targets:
                raise ValueError(
                    f"Invalid status transition from {task.status.value} to {new_status.value}"
                )

        old_status = task.status
        task.status = new_status
        db.add(
            TaskUpdate(
                task_id=task.id,
                company_id=company_id,
                updated_by=user_id,
                update_type="status_change",
                old_status=old_status,
                new_status=new_status,
                note=self._clean_optional_text(note),
            )
        )
        await db.flush()
        await db.refresh(task)

        # Notify team leader when task submitted for review
        if new_status == TaskStatus.review and team.manager_id is not None:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=team.manager_id,
                title="Task Ready for Review",
                message=f"Task '{task.title}' has been submitted for your review.",
                notification_type=NotificationType.task_submitted_review,
                entity_type="project_task",
                entity_id=task.id,
            )

        return task

    async def complete_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectTask:
        task, _, team = await self._get_task_with_project_team_or_404(db, company_id, task_id)
        self._ensure_leader(team, user_id)
        if task.status != TaskStatus.review:
            raise ValueError("Only tasks in review can be completed")

        task.status = TaskStatus.done
        await db.flush()
        await db.refresh(task)

        # Notify assignee that task is done
        if task.assigned_to is not None:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=task.assigned_to,
                title="Task Completed",
                message=f"Your task '{task.title}' has been marked as done by the team leader.",
                notification_type=NotificationType.task_approved,
                entity_type="project_task",
                entity_id=task.id,
            )

        return task

    async def _get_project_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Project:
        stmt = select(Project).where(
            Project.id == project_id,
            Project.company_id == company_id,
            Project.deleted_at.is_(None),
        )
        project = (await db.execute(stmt)).scalar_one_or_none()
        if project is None:
            raise LookupError("Project not found")
        return project

    async def _get_project_and_team_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> tuple[Project, Team]:
        stmt = (
            select(Project, Team)
            .join(
                Team,
                and_(
                    Team.id == Project.assigned_team_id,
                    Team.company_id == company_id,
                    Team.deleted_at.is_(None),
                ),
            )
            .where(
                Project.id == project_id,
                Project.company_id == company_id,
                Project.deleted_at.is_(None),
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            project = await self._get_project_or_404(db, company_id, project_id)
            if project.assigned_team_id is None:
                raise ValueError("Project is not assigned to a team")
            raise LookupError("Assigned team not found")
        return row

    async def _get_task_with_project_team_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> tuple[ProjectTask, Project, Team]:
        stmt = (
            select(ProjectTask, Project, Team)
            .join(
                Project,
                and_(
                    Project.id == ProjectTask.project_id,
                    Project.company_id == company_id,
                    Project.deleted_at.is_(None),
                ),
            )
            .join(
                Team,
                and_(
                    Team.id == Project.assigned_team_id,
                    Team.company_id == company_id,
                    Team.deleted_at.is_(None),
                ),
            )
            .where(
                ProjectTask.id == task_id,
                ProjectTask.company_id == company_id,
                ProjectTask.deleted_at.is_(None),
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is not None:
            return row

        task_stmt = select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.company_id == company_id,
            ProjectTask.deleted_at.is_(None),
        )
        task = (await db.execute(task_stmt)).scalar_one_or_none()
        if task is None:
            raise LookupError("Task not found")
        raise ValueError("Task project is not assigned to a valid team")

    async def _load_project_member(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> User | None:
        if user_id is None:
            return None
        stmt = (
            select(User)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(
                TeamMember.team_id == team_id,
                User.id == user_id,
                User.company_id == company_id,
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise ValueError("Assigned user must be an active project team member")
        return user

    async def _is_company_admin(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        stmt = select(User.is_company_admin).where(
            User.id == user_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
        return bool((await db.execute(stmt)).scalar_one_or_none())

    async def _is_project_member(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        stmt = (
            select(TeamMember.id)
            .join(User, User.id == TeamMember.user_id)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
                User.company_id == company_id,
                User.status == UserStatus.active,
                User.deleted_at.is_(None),
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none() is not None

    async def _validate_dependency_task(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        dependency_task_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if dependency_task_id is None:
            return None

        stmt = select(ProjectTask.id).where(
            ProjectTask.id == dependency_task_id,
            ProjectTask.project_id == project_id,
            ProjectTask.company_id == company_id,
            ProjectTask.deleted_at.is_(None),
        )
        dependency = (await db.execute(stmt)).scalar_one_or_none()
        if dependency is None:
            raise LookupError("Dependency task not found")
        return dependency

    @staticmethod
    def _ensure_project_in_progress(project: Project) -> None:
        if project.status != ProjectStatus.in_progress:
            raise ValueError("Tasks can only be managed when the project is in progress")

    @staticmethod
    def _ensure_leader(team: Team, user_id: uuid.UUID) -> None:
        if team.manager_id is None or team.manager_id != user_id:
            raise PermissionError("Only the project leader can perform this action")

    @staticmethod
    def _validate_task_dates(start_date, due_date) -> None:
        if start_date is not None and due_date is not None and due_date < start_date:
            raise ValueError("Due date cannot be earlier than start date")

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


task_service = TaskService()
