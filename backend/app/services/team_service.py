from __future__ import annotations
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.project import Project, ProjectStatus
from app.models.team import Team, TeamMember, TeamStatus
from app.models.user import User, UserStatus
from app.schemas.team import (
    AssignTeamRequest,
    TeamDetailsResponse,
    TeamListItem,
    TeamListResponse,
    TeamMemberResponse,
    TeamProjectResponse,
    TeamResponse,
    TeamUpsertRequest,
    UnassignedProjectItem,
    UnassignedProjectsResponse,
)
from app.schemas.user import PaginationMeta


class TeamService:
    async def list_teams(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> TeamListResponse:
        manager = aliased(User)
        member_count_subquery = (
            select(
                TeamMember.team_id.label("team_id"),
                func.count(TeamMember.id).label("member_count"),
            )
            .group_by(TeamMember.team_id)
            .subquery()
        )

        stmt = (
            select(
                Team.id,
                Team.name,
                Team.description,
                Team.manager_id,
                manager.name,
                func.coalesce(member_count_subquery.c.member_count, 0),
                Team.status,
            )
            .outerjoin(manager, manager.id == Team.manager_id)
            .outerjoin(member_count_subquery, member_count_subquery.c.team_id == Team.id)
            .where(
                Team.company_id == company_id,
                Team.deleted_at.is_(None),
            )
            .order_by(Team.name.asc())
        )
        rows = (await db.execute(stmt)).all()

        items = [
            TeamListItem(
                id=team_id,
                name=name,
                description=description,
                manager_id=manager_id,
                manager_name=manager_name,
                member_count=member_count,
                status=status,
            )
            for team_id, name, description, manager_id, manager_name, member_count, status in rows
        ]
        total = len(items)
        return TeamListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=1,
                per_page=total if total > 0 else 1,
                total_pages=1 if total > 0 else 0,
            ),
        )

    async def create_team(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: TeamUpsertRequest,
    ) -> Team:
        normalized_name = data.name.strip()
        await self._ensure_team_name_available(db, company_id, normalized_name)

        manager = await self._load_manager(db, company_id, data.manager_id)
        members = await self._load_active_members(db, company_id, data.member_ids)

        team = Team(
            company_id=company_id,
            name=normalized_name,
            description=data.description,
            manager_id=manager.id if manager else None,
            status=TeamStatus.active,
        )
        db.add(team)
        await db.flush()

        await self._set_team_members(db, team.id, members)
        await db.flush()
        await db.refresh(team)
        return team

    async def get_team(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> TeamResponse:
        team = await self._get_team_or_404(db, company_id, team_id)
        manager_name = await self._get_manager_name(db, company_id, team.manager_id)
        members = await self._get_team_members(db, company_id, team.id)
        return TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            manager_id=team.manager_id,
            manager_name=manager_name,
            status=team.status,
            members=members,
        )

    async def get_team_details(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> TeamDetailsResponse:
        team_response = await self.get_team(db, company_id, team_id)

        projects_stmt = (
            select(Project.id, Project.project_name, Project.status)
            .where(
                Project.company_id == company_id,
                Project.assigned_team_id == team_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.project_name.asc())
        )
        projects = [
            TeamProjectResponse(id=project_id, project_name=project_name, status=status)
            for project_id, project_name, status in (await db.execute(projects_stmt)).all()
        ]

        return TeamDetailsResponse(**team_response.model_dump(), projects=projects)

    async def update_team(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
        data: TeamUpsertRequest,
    ) -> Team:
        team = await self._get_team_or_404(db, company_id, team_id)
        normalized_name = data.name.strip()
        await self._ensure_team_name_available(
            db,
            company_id,
            normalized_name,
            exclude_team_id=team_id,
        )

        manager = await self._load_manager(db, company_id, data.manager_id)
        members = await self._load_active_members(db, company_id, data.member_ids)

        team.name = normalized_name
        team.description = data.description
        team.manager_id = manager.id if manager else None

        await db.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
        await self._set_team_members(db, team.id, members)

        await db.flush()
        await db.refresh(team)
        return team

    async def list_unassigned_projects(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> UnassignedProjectsResponse:
        stmt = (
            select(Project.id, Project.project_name, Project.status)
            .where(
                Project.company_id == company_id,
                Project.assigned_team_id.is_(None),
                Project.deleted_at.is_(None),
            )
            .order_by(Project.project_name.asc())
        )
        rows = (await db.execute(stmt)).all()
        items = [
            UnassignedProjectItem(id=project_id, project_name=project_name, status=status)
            for project_id, project_name, status in rows
        ]
        return UnassignedProjectsResponse(data=items, total=len(items))

    async def assign_team_to_project(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        project_id: uuid.UUID,
        data: AssignTeamRequest,
    ) -> None:
        project_stmt = select(Project).where(
            Project.id == project_id,
            Project.company_id == company_id,
            Project.deleted_at.is_(None),
        )
        project = (await db.execute(project_stmt)).scalar_one_or_none()
        if project is None:
            raise LookupError("Project not found")

        team = await self._get_team_or_404(db, company_id, data.team_id)
        project.assigned_team_id = team.id
        project.status = ProjectStatus.assigned
        await db.flush()

    async def archive_team(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> None:
        team = await self._get_team_or_404(db, company_id, team_id)
        team.status = TeamStatus.archived
        await db.flush()

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

    async def _ensure_team_name_available(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        name: str,
        exclude_team_id: uuid.UUID | None = None,
    ) -> None:
        stmt = select(Team).where(
            Team.company_id == company_id,
            Team.name == name,
            Team.deleted_at.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None and existing.id != exclude_team_id:
            raise ValueError("Team name already exists")

    async def _load_manager(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        manager_id: uuid.UUID | None,
    ) -> User | None:
        if manager_id is None:
            return None

        stmt = select(User).where(
            User.id == manager_id,
            User.company_id == company_id,
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
        manager = (await db.execute(stmt)).scalar_one_or_none()
        if manager is None:
            raise ValueError("Manager must be an active user in the same company")
        return manager

    async def _load_active_members(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        member_ids: list[uuid.UUID],
    ) -> list[User]:
        unique_member_ids = list(dict.fromkeys(member_ids))
        if not unique_member_ids:
            return []

        stmt = select(User).where(
            User.company_id == company_id,
            User.id.in_(unique_member_ids),
            User.status == UserStatus.active,
            User.deleted_at.is_(None),
        )
        members = (await db.execute(stmt)).scalars().all()
        if len({member.id for member in members}) != len(unique_member_ids):
            raise ValueError("All team members must be active users in the same company")

        users_by_id = {member.id: member for member in members}
        return [users_by_id[member_id] for member_id in unique_member_ids]

    async def _set_team_members(
        self,
        db: AsyncSession,
        team_id: uuid.UUID,
        members: list[User],
    ) -> None:
        for member in members:
            db.add(TeamMember(team_id=team_id, user_id=member.id))

    async def _get_manager_name(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        manager_id: uuid.UUID | None,
    ) -> str | None:
        if manager_id is None:
            return None

        stmt = select(User.name).where(
            User.id == manager_id,
            User.company_id == company_id,
            User.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_team_members(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> list[TeamMemberResponse]:
        stmt = (
            select(
                User.id,
                User.emp_id,
                User.name,
                User.email,
                User.status,
                TeamMember.added_at,
            )
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(
                TeamMember.team_id == team_id,
                User.company_id == company_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.name.asc())
        )
        return [
            TeamMemberResponse(
                user_id=user_id,
                emp_id=emp_id,
                name=name,
                email=email,
                status=status.value,
                added_at=added_at,
            )
            for user_id, emp_id, name, email, status, added_at in (await db.execute(stmt)).all()
        ]


team_service = TeamService()
