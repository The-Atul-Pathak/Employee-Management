from __future__ import annotations
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.crm import Lead
from app.models.notification import NotificationType
from app.models.project import Project, ProjectPlanning, ProjectStatus, ProjectStatusLog, ProjectTask, TaskStatus
from app.models.team import Team
from app.models.user import User


def _get_notification_service():
    from app.services.notification_service import notification_service
    return notification_service
from app.schemas.project import (
    PlanningRequest,
    PlanningResponse,
    ProjectActionResponse,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectStatusLogResponse,
    ProjectTaskSummary,
)
from app.schemas.user import PaginationMeta


class ProjectService:
    async def list_projects(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> ProjectListResponse:
        leader = aliased(User)
        stmt = (
            select(
                Project.id,
                Project.project_name,
                Project.lead_id,
                Lead.client_name,
                Project.assigned_team_id,
                Team.name,
                Team.manager_id,
                leader.name,
                Project.status,
            )
            .outerjoin(Lead, Lead.id == Project.lead_id)
            .outerjoin(Team, Team.id == Project.assigned_team_id)
            .outerjoin(leader, leader.id == Team.manager_id)
            .where(
                Project.company_id == company_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.created_at.desc(), Project.project_name.asc())
        )
        rows = (await db.execute(stmt)).all()

        items = [
            ProjectListItem(
                id=project_id,
                project_name=project_name,
                lead_id=lead_id,
                lead_client_name=lead_client_name,
                team_id=team_id,
                team_name=team_name,
                leader_id=leader_id,
                leader_name=leader_name,
                status=status,
            )
            for project_id, project_name, lead_id, lead_client_name, team_id, team_name, leader_id, leader_name, status in rows
        ]
        total = len(items)
        return ProjectListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=1,
                per_page=total if total > 0 else 1,
                total_pages=1 if total > 0 else 0,
            ),
        )

    async def get_unassigned_projects(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> ProjectListResponse:
        leader = aliased(User)
        stmt = (
            select(
                Project.id,
                Project.project_name,
                Project.lead_id,
                Lead.client_name,
                Project.assigned_team_id,
                Team.name,
                Team.manager_id,
                leader.name,
                Project.status,
            )
            .outerjoin(Lead, Lead.id == Project.lead_id)
            .outerjoin(Team, Team.id == Project.assigned_team_id)
            .outerjoin(leader, leader.id == Team.manager_id)
            .where(
                Project.company_id == company_id,
                Project.status == ProjectStatus.unassigned,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.created_at.desc(), Project.project_name.asc())
        )
        rows = (await db.execute(stmt)).all()
        items = [
            ProjectListItem(
                id=project_id,
                project_name=project_name,
                lead_id=lead_id,
                lead_client_name=lead_client_name,
                team_id=team_id,
                team_name=team_name,
                leader_id=leader_id,
                leader_name=leader_name,
                status=status,
            )
            for project_id, project_name, lead_id, lead_client_name, team_id, team_name, leader_id, leader_name, status in rows
        ]
        total = len(items)
        return ProjectListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=1,
                per_page=total if total > 0 else 1,
                total_pages=1 if total > 0 else 0,
            ),
        )

    async def assign_team(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> ProjectActionResponse:
        project = await self._get_project_or_404(db, company_id, project_id)
        team = await self._get_team_or_404(db, company_id, team_id)

        project.assigned_team_id = team.id
        project.status = ProjectStatus.assigned
        await db.flush()

        # Notify team leader
        if team.manager_id is not None:
            await _get_notification_service().create_notification(
                db=db,
                company_id=company_id,
                user_id=team.manager_id,
                title="Project Assigned to Your Team",
                message=f"Your team has been assigned to the project: '{project.project_name}'.",
                notification_type=NotificationType.project_assigned,
                entity_type="project",
                entity_id=project.id,
            )

        return ProjectActionResponse(
            id=project.id,
            status=project.status,
            message="Team assigned successfully",
        )

    async def get_project_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectDetailResponse:
        project, is_leader, is_admin, team_name, leader_id, leader_name, lead_client_name, lead_contact_email, lead_contact_phone = (
            await self._get_project_detail_context(db, company_id, project_id, user_id)
        )
        planning = await self._get_planning(db, company_id, project.id)
        tasks = await self._get_tasks(db, company_id, project.id)
        logs = await self._get_status_logs(db, company_id, project.id)

        return ProjectDetailResponse(
            id=project.id,
            project_name=project.project_name,
            lead_id=project.lead_id,
            lead_client_name=lead_client_name,
            lead_contact_email=lead_contact_email,
            lead_contact_phone=lead_contact_phone,
            team_id=project.assigned_team_id,
            team_name=team_name,
            leader_id=leader_id,
            leader_name=leader_name,
            status=project.status,
            is_leader=is_leader,
            is_admin=is_admin,
            planning=planning,
            tasks=tasks,
            status_logs=logs,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def save_planning(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: PlanningRequest,
    ) -> ProjectActionResponse:
        project_status, is_leader, _ = await self.get_project_and_role(db, project_id, company_id, user_id)
        if not is_leader:
            raise PermissionError("Only the team leader can save project planning")

        project = await self._get_project_or_404(db, company_id, project_id)
        planning_stmt = select(ProjectPlanning).where(
            ProjectPlanning.company_id == company_id,
            ProjectPlanning.project_id == project_id,
            ProjectPlanning.deleted_at.is_(None),
        )
        planning = (await db.execute(planning_stmt)).scalar_one_or_none()
        payload = data.model_dump()

        if planning is None:
            planning = ProjectPlanning(
                company_id=company_id,
                project_id=project_id,
                **payload,
            )
            db.add(planning)
        else:
            for field, value in payload.items():
                setattr(planning, field, value)

        if project_status in {ProjectStatus.in_progress, ProjectStatus.completed}:
            raise ValueError("Planning cannot be changed once the project has started")

        project.status = ProjectStatus.planned

        await db.flush()
        return ProjectActionResponse(
            id=project.id,
            status=project.status,
            message="Project planning saved successfully",
        )

    async def start_project(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectActionResponse:
        project_status, is_leader, _ = await self.get_project_and_role(db, project_id, company_id, user_id)
        if not is_leader:
            raise PermissionError("Only the team leader can start the project")
        if project_status != ProjectStatus.planned:
            raise ValueError("Project must be in planned status before it can start")

        project = await self._get_project_or_404(db, company_id, project_id)
        old_status = project.status
        project.status = ProjectStatus.in_progress
        db.add(
            ProjectStatusLog(
                project_id=project.id,
                company_id=company_id,
                old_status=old_status,
                new_status=ProjectStatus.in_progress,
                changed_by=user_id,
                reason="Project started",
            )
        )
        await db.flush()

        return ProjectActionResponse(
            id=project.id,
            status=project.status,
            message="Project started successfully",
        )

    async def complete_project(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectActionResponse:
        project_status, is_leader, _ = await self.get_project_and_role(db, project_id, company_id, user_id)
        if not is_leader:
            raise PermissionError("Only the team leader can complete the project")
        if project_status != ProjectStatus.in_progress:
            raise ValueError("Project must be in progress before it can be completed")

        incomplete_tasks_stmt = select(func.count()).select_from(ProjectTask).where(
            ProjectTask.company_id == company_id,
            ProjectTask.project_id == project_id,
            ProjectTask.deleted_at.is_(None),
            ProjectTask.status != TaskStatus.done,
        )
        incomplete_tasks = (await db.execute(incomplete_tasks_stmt)).scalar_one()
        if incomplete_tasks > 0:
            raise ValueError("All project tasks must be marked done before completion")

        project = await self._get_project_or_404(db, company_id, project_id)
        old_status = project.status
        project.status = ProjectStatus.completed
        db.add(
            ProjectStatusLog(
                project_id=project.id,
                company_id=company_id,
                old_status=old_status,
                new_status=ProjectStatus.completed,
                changed_by=user_id,
                reason="Project completed",
            )
        )
        await db.flush()

        return ProjectActionResponse(
            id=project.id,
            status=project.status,
            message="Project completed successfully",
        )

    async def get_project_and_role(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[ProjectStatus, bool, bool]:
        stmt = (
            select(
                Project.status,
                case((Team.manager_id == user_id, True), else_=False).label("is_leader"),
                case((User.is_company_admin.is_(True), True), else_=False).label("is_admin"),
            )
            .join(User, User.id == user_id)
            .outerjoin(Team, Team.id == Project.assigned_team_id)
            .where(
                Project.id == project_id,
                Project.company_id == company_id,
                Project.deleted_at.is_(None),
                User.id == user_id,
                User.company_id == company_id,
                User.deleted_at.is_(None),
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise LookupError("Project not found")
        return row[0], bool(row[1]), bool(row[2])

    async def _get_project_detail_context(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Project, bool, bool, str | None, uuid.UUID | None, str | None, str | None, str | None, str | None]:
        leader = aliased(User)
        viewer = aliased(User)
        stmt = (
            select(
                Project,
                case((Team.manager_id == user_id, True), else_=False).label("is_leader"),
                case((viewer.is_company_admin.is_(True), True), else_=False).label("is_admin"),
                Team.name,
                Team.manager_id,
                leader.name,
                Lead.client_name,
                Lead.contact_email,
                Lead.contact_phone,
            )
            .outerjoin(Team, Team.id == Project.assigned_team_id)
            .outerjoin(leader, leader.id == Team.manager_id)
            .outerjoin(Lead, Lead.id == Project.lead_id)
            .join(viewer, viewer.id == user_id)
            .where(
                Project.id == project_id,
                Project.company_id == company_id,
                Project.deleted_at.is_(None),
                viewer.company_id == company_id,
                viewer.deleted_at.is_(None),
            )
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise LookupError("Project not found")
        return row

    async def _get_planning(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PlanningResponse | None:
        stmt = select(ProjectPlanning).where(
            ProjectPlanning.company_id == company_id,
            ProjectPlanning.project_id == project_id,
            ProjectPlanning.deleted_at.is_(None),
        )
        planning = (await db.execute(stmt)).scalar_one_or_none()
        if planning is None:
            return None

        return PlanningResponse(
            id=planning.id,
            planned_start_date=planning.planned_start_date,
            planned_end_date=planning.planned_end_date,
            description=planning.description,
            scope=planning.scope,
            milestones=planning.milestones or [],
            deliverables=planning.deliverables or [],
            estimated_budget=planning.estimated_budget,
            priority=planning.priority,
            client_requirements=planning.client_requirements,
            risk_notes=planning.risk_notes,
            assumptions=planning.assumptions,
            dependencies=planning.dependencies,
            internal_notes=planning.internal_notes,
            created_at=planning.created_at,
            updated_at=planning.updated_at,
        )

    async def _get_tasks(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[ProjectTaskSummary]:
        assignee = aliased(User)
        stmt = (
            select(
                ProjectTask.id,
                ProjectTask.title,
                ProjectTask.assigned_to,
                assignee.name,
                ProjectTask.status,
                ProjectTask.due_date,
            )
            .outerjoin(assignee, assignee.id == ProjectTask.assigned_to)
            .where(
                ProjectTask.company_id == company_id,
                ProjectTask.project_id == project_id,
                ProjectTask.deleted_at.is_(None),
            )
            .order_by(ProjectTask.created_at.asc())
        )
        return [
            ProjectTaskSummary(
                id=task_id,
                title=title,
                assigned_to=assigned_to,
                assigned_to_name=assigned_to_name,
                status=status,
                due_date=due_date,
            )
            for task_id, title, assigned_to, assigned_to_name, status, due_date in (await db.execute(stmt)).all()
        ]

    async def _get_status_logs(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[ProjectStatusLogResponse]:
        changed_by_user = aliased(User)
        stmt = (
            select(
                ProjectStatusLog.id,
                ProjectStatusLog.old_status,
                ProjectStatusLog.new_status,
                ProjectStatusLog.changed_by,
                changed_by_user.name,
                ProjectStatusLog.reason,
                ProjectStatusLog.created_at,
            )
            .outerjoin(changed_by_user, changed_by_user.id == ProjectStatusLog.changed_by)
            .where(
                ProjectStatusLog.company_id == company_id,
                ProjectStatusLog.project_id == project_id,
            )
            .order_by(ProjectStatusLog.created_at.desc())
        )
        return [
            ProjectStatusLogResponse(
                id=log_id,
                old_status=old_status,
                new_status=new_status,
                changed_by=changed_by,
                changed_by_name=changed_by_name,
                reason=reason,
                created_at=created_at,
            )
            for log_id, old_status, new_status, changed_by, changed_by_name, reason, created_at in (await db.execute(stmt)).all()
        ]

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

    async def _get_team_or_404(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> Team:
        stmt = select(Team).where(
            Team.id == team_id,
            Team.company_id == company_id,
            Team.deleted_at.is_(None),
        )
        team = (await db.execute(stmt)).scalar_one_or_none()
        if team is None:
            raise LookupError("Team not found")
        return team


project_service = ProjectService()
