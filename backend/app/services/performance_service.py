from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance import (
    PerformanceReview,
    PerformanceReviewStatus,
    ReviewCriteria,
    ReviewCycle,
    ReviewCycleStatus,
    ReviewScore,
)
from app.models.user import User
from app.schemas.performance import (
    CriteriaItem,
    CycleCreate,
    CycleDetail,
    CycleItem,
    CycleListResponse,
    CycleUpdate,
    ReviewCreate,
    ReviewDetail,
    ReviewItem,
    ReviewListResponse,
    ReviewScoreItem,
    ReviewSubmit,
    ReviewUserInfo,
    SelfAssessmentSubmit,
)
from app.schemas.user import PaginationMeta


class PerformanceService:
    async def _get_user(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    def _user_info(self, u: User | None) -> ReviewUserInfo | None:
        if u is None:
            return None
        return ReviewUserInfo(id=u.id, name=u.name, emp_id=u.emp_id)

    # ── Cycles ─────────────────────────────────────────────────────────────────

    async def list_cycles(self, db: AsyncSession, company_id: uuid.UUID) -> CycleListResponse:
        stmt = (
            select(ReviewCycle)
            .where(ReviewCycle.company_id == company_id, ReviewCycle.deleted_at.is_(None))
            .order_by(ReviewCycle.review_from.desc())
        )
        cycles = (await db.execute(stmt)).scalars().all()

        cycle_ids = [c.id for c in cycles]
        counts: dict[uuid.UUID, int] = {}
        if cycle_ids:
            count_stmt = (
                select(PerformanceReview.cycle_id, func.count().label("cnt"))
                .where(
                    PerformanceReview.cycle_id.in_(cycle_ids),
                    PerformanceReview.deleted_at.is_(None),
                )
                .group_by(PerformanceReview.cycle_id)
            )
            for row in (await db.execute(count_stmt)).all():
                counts[row[0]] = row[1]

        return CycleListResponse(
            data=[
                CycleItem(
                    id=c.id,
                    name=c.name,
                    cycle_type=c.cycle_type,
                    review_from=c.review_from,
                    review_to=c.review_to,
                    submission_deadline=c.submission_deadline,
                    status=c.status,
                    review_count=counts.get(c.id, 0),
                    created_at=c.created_at,
                )
                for c in cycles
            ]
        )

    async def get_cycle_detail(
        self, db: AsyncSession, company_id: uuid.UUID, cycle_id: uuid.UUID
    ) -> CycleDetail:
        stmt = select(ReviewCycle).where(
            ReviewCycle.id == cycle_id,
            ReviewCycle.company_id == company_id,
            ReviewCycle.deleted_at.is_(None),
        )
        cycle = (await db.execute(stmt)).scalar_one_or_none()
        if cycle is None:
            raise LookupError("Review cycle not found")

        criteria_stmt = (
            select(ReviewCriteria)
            .where(ReviewCriteria.cycle_id == cycle_id)
            .order_by(ReviewCriteria.order_index)
        )
        criteria = (await db.execute(criteria_stmt)).scalars().all()

        return CycleDetail(
            id=cycle.id,
            name=cycle.name,
            cycle_type=cycle.cycle_type,
            review_from=cycle.review_from,
            review_to=cycle.review_to,
            submission_deadline=cycle.submission_deadline,
            status=cycle.status,
            created_at=cycle.created_at,
            criteria=[CriteriaItem.model_validate(c) for c in criteria],
        )

    async def create_cycle(
        self, db: AsyncSession, company_id: uuid.UUID, data: CycleCreate
    ) -> CycleDetail:
        cycle = ReviewCycle(
            company_id=company_id,
            name=data.name,
            cycle_type=data.cycle_type,
            review_from=data.review_from,
            review_to=data.review_to,
            submission_deadline=data.submission_deadline,
            status=ReviewCycleStatus.draft,
        )
        db.add(cycle)
        await db.flush()

        criteria_objs = []
        for c in data.criteria:
            criteria_obj = ReviewCriteria(
                cycle_id=cycle.id,
                name=c.name,
                description=c.description,
                max_score=c.max_score,
                order_index=c.order_index,
            )
            db.add(criteria_obj)
            criteria_objs.append(criteria_obj)
        await db.flush()

        return CycleDetail(
            id=cycle.id,
            name=cycle.name,
            cycle_type=cycle.cycle_type,
            review_from=cycle.review_from,
            review_to=cycle.review_to,
            submission_deadline=cycle.submission_deadline,
            status=cycle.status,
            created_at=cycle.created_at,
            criteria=[CriteriaItem.model_validate(c) for c in criteria_objs],
        )

    async def update_cycle(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        cycle_id: uuid.UUID,
        data: CycleUpdate,
    ) -> CycleItem:
        stmt = select(ReviewCycle).where(
            ReviewCycle.id == cycle_id,
            ReviewCycle.company_id == company_id,
            ReviewCycle.deleted_at.is_(None),
        )
        cycle = (await db.execute(stmt)).scalar_one_or_none()
        if cycle is None:
            raise LookupError("Review cycle not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cycle, field, value)
        await db.flush()

        count_stmt = select(func.count()).select_from(PerformanceReview).where(
            PerformanceReview.cycle_id == cycle_id,
            PerformanceReview.deleted_at.is_(None),
        )
        count = (await db.execute(count_stmt)).scalar_one()

        return CycleItem(
            id=cycle.id,
            name=cycle.name,
            cycle_type=cycle.cycle_type,
            review_from=cycle.review_from,
            review_to=cycle.review_to,
            submission_deadline=cycle.submission_deadline,
            status=cycle.status,
            review_count=count,
            created_at=cycle.created_at,
        )

    # ── Reviews ────────────────────────────────────────────────────────────────

    async def list_reviews(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        cycle_id: uuid.UUID | None = None,
        employee_id: uuid.UUID | None = None,
        reviewer_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> ReviewListResponse:
        filters = [
            PerformanceReview.company_id == company_id,
            PerformanceReview.deleted_at.is_(None),
        ]
        if cycle_id:
            filters.append(PerformanceReview.cycle_id == cycle_id)
        if employee_id:
            filters.append(PerformanceReview.employee_id == employee_id)
        if reviewer_id:
            filters.append(PerformanceReview.reviewer_id == reviewer_id)

        total_stmt = select(func.count()).select_from(PerformanceReview).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(PerformanceReview)
            .where(*filters)
            .order_by(PerformanceReview.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        reviews = (await db.execute(stmt)).scalars().all()

        user_ids = {r.employee_id for r in reviews} | {r.reviewer_id for r in reviews}
        cycle_ids = {r.cycle_id for r in reviews}

        users: dict[uuid.UUID, User] = {}
        if user_ids:
            user_stmt = select(User).where(User.id.in_(user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        cycles: dict[uuid.UUID, ReviewCycle] = {}
        if cycle_ids:
            cyc_stmt = select(ReviewCycle).where(ReviewCycle.id.in_(cycle_ids))
            for c in (await db.execute(cyc_stmt)).scalars().all():
                cycles[c.id] = c

        return ReviewListResponse(
            data=[
                ReviewItem(
                    id=r.id,
                    cycle_id=r.cycle_id,
                    cycle_name=cycles[r.cycle_id].name if r.cycle_id in cycles else "",
                    employee=self._user_info(users.get(r.employee_id)),
                    reviewer=self._user_info(users.get(r.reviewer_id)),
                    status=r.status,
                    overall_score=float(r.overall_score) if r.overall_score else None,
                    submitted_at=r.submitted_at,
                    published_at=r.published_at,
                    created_at=r.created_at,
                )
                for r in reviews
            ],
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def create_review(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        cycle_id: uuid.UUID,
        data: ReviewCreate,
    ) -> ReviewItem:
        cycle_stmt = select(ReviewCycle).where(
            ReviewCycle.id == cycle_id, ReviewCycle.company_id == company_id
        )
        cycle = (await db.execute(cycle_stmt)).scalar_one_or_none()
        if cycle is None:
            raise LookupError("Review cycle not found")

        review = PerformanceReview(
            company_id=company_id,
            cycle_id=cycle_id,
            employee_id=data.employee_id,
            reviewer_id=data.reviewer_id,
            status=PerformanceReviewStatus.pending,
        )
        db.add(review)
        await db.flush()

        employee = await self._get_user(db, data.employee_id)
        reviewer = await self._get_user(db, data.reviewer_id)

        return ReviewItem(
            id=review.id,
            cycle_id=cycle_id,
            cycle_name=cycle.name,
            employee=self._user_info(employee),
            reviewer=self._user_info(reviewer),
            status=review.status,
            overall_score=None,
            submitted_at=None,
            published_at=None,
            created_at=review.created_at,
        )

    async def get_review_detail(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> ReviewDetail:
        stmt = select(PerformanceReview).where(
            PerformanceReview.id == review_id,
            PerformanceReview.company_id == company_id,
            PerformanceReview.deleted_at.is_(None),
        )
        review = (await db.execute(stmt)).scalar_one_or_none()
        if review is None:
            raise LookupError("Review not found")

        return await self._build_review_detail(db, review)

    async def submit_review(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        review_id: uuid.UUID,
        data: ReviewSubmit,
    ) -> ReviewDetail:
        stmt = select(PerformanceReview).where(
            PerformanceReview.id == review_id,
            PerformanceReview.company_id == company_id,
            PerformanceReview.deleted_at.is_(None),
        )
        review = (await db.execute(stmt)).scalar_one_or_none()
        if review is None:
            raise LookupError("Review not found")

        review.status = PerformanceReviewStatus.submitted
        review.reviewer_comments = data.reviewer_comments
        review.overall_score = data.overall_score
        review.submitted_at = datetime.now(timezone.utc)

        # Upsert scores
        for score_data in data.scores:
            score_stmt = select(ReviewScore).where(
                ReviewScore.review_id == review_id,
                ReviewScore.criteria_id == score_data.criteria_id,
            )
            score = (await db.execute(score_stmt)).scalar_one_or_none()
            if score is None:
                score = ReviewScore(review_id=review_id, criteria_id=score_data.criteria_id)
                db.add(score)
            score.reviewer_score = score_data.reviewer_score
            score.reviewer_comment = score_data.reviewer_comment

        await db.flush()
        return await self._build_review_detail(db, review)

    async def submit_self_assessment(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        review_id: uuid.UUID,
        employee_id: uuid.UUID,
        data: SelfAssessmentSubmit,
    ) -> ReviewDetail:
        stmt = select(PerformanceReview).where(
            PerformanceReview.id == review_id,
            PerformanceReview.company_id == company_id,
            PerformanceReview.employee_id == employee_id,
            PerformanceReview.deleted_at.is_(None),
        )
        review = (await db.execute(stmt)).scalar_one_or_none()
        if review is None:
            raise LookupError("Review not found")

        review.status = PerformanceReviewStatus.self_assessment_done
        for score_data in data.scores:
            score_stmt = select(ReviewScore).where(
                ReviewScore.review_id == review_id,
                ReviewScore.criteria_id == score_data.criteria_id,
            )
            score = (await db.execute(score_stmt)).scalar_one_or_none()
            if score is None:
                score = ReviewScore(review_id=review_id, criteria_id=score_data.criteria_id)
                db.add(score)
            score.self_score = score_data.self_score

        await db.flush()
        return await self._build_review_detail(db, review)

    async def _build_review_detail(
        self, db: AsyncSession, review: PerformanceReview
    ) -> ReviewDetail:
        cycle_stmt = select(ReviewCycle).where(ReviewCycle.id == review.cycle_id)
        cycle = (await db.execute(cycle_stmt)).scalar_one_or_none()

        employee = await self._get_user(db, review.employee_id)
        reviewer = await self._get_user(db, review.reviewer_id)

        # Criteria for this cycle
        criteria_stmt = (
            select(ReviewCriteria)
            .where(ReviewCriteria.cycle_id == review.cycle_id)
            .order_by(ReviewCriteria.order_index)
        )
        criteria = (await db.execute(criteria_stmt)).scalars().all()
        criteria_map = {c.id: c for c in criteria}

        # Scores
        score_stmt = select(ReviewScore).where(ReviewScore.review_id == review.id)
        scores = (await db.execute(score_stmt)).scalars().all()
        score_map = {s.criteria_id: s for s in scores}

        score_items = []
        for c in criteria:
            s = score_map.get(c.id)
            score_items.append(ReviewScoreItem(
                criteria_id=c.id,
                criteria_name=c.name,
                max_score=c.max_score,
                self_score=s.self_score if s else None,
                reviewer_score=s.reviewer_score if s else None,
                reviewer_comment=s.reviewer_comment if s else None,
            ))

        return ReviewDetail(
            id=review.id,
            cycle_id=review.cycle_id,
            cycle_name=cycle.name if cycle else "",
            employee=self._user_info(employee),
            reviewer=self._user_info(reviewer),
            status=review.status,
            overall_score=float(review.overall_score) if review.overall_score else None,
            submitted_at=review.submitted_at,
            published_at=review.published_at,
            created_at=review.created_at,
            reviewer_comments=review.reviewer_comments,
            employee_response=review.employee_response,
            scores=score_items,
        )


performance_service = PerformanceService()
