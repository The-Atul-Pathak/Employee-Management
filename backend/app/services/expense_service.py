from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.user import User
from app.schemas.expense import (
    ExpenseCategoryCreate,
    ExpenseCategoryItem,
    ExpenseCategoryListResponse,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseReview,
    ExpenseUserInfo,
    MyExpenseItem,
    MyExpensesResponse,
)
from app.schemas.user import PaginationMeta


class ExpenseService:
    def _receipt_dir(self, company_id: uuid.UUID) -> Path:
        p = Path(settings.UPLOAD_DIR) / str(company_id) / "receipts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def _get_user(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_category(
        self, db: AsyncSession, company_id: uuid.UUID, category_id: uuid.UUID
    ) -> ExpenseCategory | None:
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.company_id == company_id,
            ExpenseCategory.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    # ── Categories ──────────────────────────────────────────────────────────────

    async def list_categories(
        self, db: AsyncSession, company_id: uuid.UUID
    ) -> ExpenseCategoryListResponse:
        stmt = (
            select(ExpenseCategory)
            .where(
                ExpenseCategory.company_id == company_id,
                ExpenseCategory.deleted_at.is_(None),
            )
            .order_by(ExpenseCategory.name)
        )
        cats = (await db.execute(stmt)).scalars().all()
        return ExpenseCategoryListResponse(
            data=[ExpenseCategoryItem.model_validate(c) for c in cats]
        )

    async def create_category(
        self, db: AsyncSession, company_id: uuid.UUID, data: ExpenseCategoryCreate
    ) -> ExpenseCategoryItem:
        cat = ExpenseCategory(
            company_id=company_id,
            name=data.name,
            description=data.description,
        )
        db.add(cat)
        await db.flush()
        return ExpenseCategoryItem.model_validate(cat)

    async def update_category(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        category_id: uuid.UUID,
        data: ExpenseCategoryUpdate,
    ) -> ExpenseCategoryItem:
        cat = await self._get_category(db, company_id, category_id)
        if cat is None:
            raise LookupError("Category not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cat, field, value)
        await db.flush()
        return ExpenseCategoryItem.model_validate(cat)

    async def delete_category(
        self, db: AsyncSession, company_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        cat = await self._get_category(db, company_id, category_id)
        if cat is None:
            raise LookupError("Category not found")
        cat.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    # ── Expenses ────────────────────────────────────────────────────────────────

    async def create_expense(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID,
        data: ExpenseCreate,
        receipt: UploadFile | None = None,
    ) -> ExpenseItem:
        receipt_path: str | None = None
        receipt_name: str | None = None

        if receipt and receipt.filename:
            upload_dir = self._receipt_dir(company_id)
            unique_name = f"{uuid.uuid4()}_{receipt.filename}"
            file_path = upload_dir / unique_name
            content = await receipt.read()
            file_path.write_bytes(content)
            receipt_path = str(file_path)
            receipt_name = receipt.filename

        expense = Expense(
            company_id=company_id,
            employee_id=employee_id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            amount=data.amount,
            currency=data.currency,
            expense_date=data.expense_date,
            receipt_path=receipt_path,
            receipt_name=receipt_name,
            status=ExpenseStatus.pending,
        )
        db.add(expense)
        await db.flush()

        employee = await self._get_user(db, employee_id)
        cat = await self._get_category(db, company_id, data.category_id) if data.category_id else None
        return self._to_item(expense, employee, cat, None)

    async def list_expenses(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status_filter: ExpenseStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> ExpenseListResponse:
        filters = [Expense.company_id == company_id, Expense.deleted_at.is_(None)]
        if employee_id:
            filters.append(Expense.employee_id == employee_id)
        if status_filter:
            filters.append(Expense.status == status_filter)

        total_stmt = select(func.count()).select_from(Expense).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Expense)
            .where(*filters)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        expenses = (await db.execute(stmt)).scalars().all()

        user_ids = {e.employee_id for e in expenses} | {e.reviewer_id for e in expenses if e.reviewer_id}
        cat_ids = {e.category_id for e in expenses if e.category_id}

        users: dict[uuid.UUID, User] = {}
        if user_ids:
            user_stmt = select(User).where(User.id.in_(user_ids))
            for u in (await db.execute(user_stmt)).scalars().all():
                users[u.id] = u

        cats: dict[uuid.UUID, ExpenseCategory] = {}
        if cat_ids:
            cat_stmt = select(ExpenseCategory).where(ExpenseCategory.id.in_(cat_ids))
            for c in (await db.execute(cat_stmt)).scalars().all():
                cats[c.id] = c

        items = [
            self._to_item(
                e,
                users.get(e.employee_id),
                cats.get(e.category_id) if e.category_id else None,
                users.get(e.reviewer_id) if e.reviewer_id else None,
            )
            for e in expenses
        ]

        return ExpenseListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def get_my_expenses(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        employee_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> MyExpensesResponse:
        filters = [
            Expense.company_id == company_id,
            Expense.employee_id == employee_id,
            Expense.deleted_at.is_(None),
        ]

        total_stmt = select(func.count()).select_from(Expense).where(*filters)
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(Expense)
            .where(*filters)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        expenses = (await db.execute(stmt)).scalars().all()

        cat_ids = {e.category_id for e in expenses if e.category_id}
        cats: dict[uuid.UUID, ExpenseCategory] = {}
        if cat_ids:
            cat_stmt = select(ExpenseCategory).where(ExpenseCategory.id.in_(cat_ids))
            for c in (await db.execute(cat_stmt)).scalars().all():
                cats[c.id] = c

        items = [
            MyExpenseItem(
                id=e.id,
                category_id=e.category_id,
                category_name=cats[e.category_id].name if e.category_id and e.category_id in cats else None,
                title=e.title,
                description=e.description,
                amount=float(e.amount),
                currency=e.currency,
                expense_date=e.expense_date,
                receipt_name=e.receipt_name,
                status=e.status,
                review_notes=e.review_notes,
                reviewed_at=e.reviewed_at,
                created_at=e.created_at,
            )
            for e in expenses
        ]

        return MyExpensesResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=math.ceil(total / per_page) if total else 0,
            ),
        )

    async def review_expense(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        expense_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        data: ExpenseReview,
    ) -> ExpenseItem:
        stmt = select(Expense).where(
            Expense.id == expense_id,
            Expense.company_id == company_id,
            Expense.deleted_at.is_(None),
        )
        expense = (await db.execute(stmt)).scalar_one_or_none()
        if expense is None:
            raise LookupError("Expense not found")
        if expense.status != ExpenseStatus.pending:
            raise ValueError("Expense is not in pending state")

        expense.status = data.status
        expense.review_notes = data.review_notes
        expense.reviewer_id = reviewer_id
        expense.reviewed_at = datetime.now(timezone.utc)
        await db.flush()

        employee = await self._get_user(db, expense.employee_id)
        cat = await self._get_category(db, company_id, expense.category_id) if expense.category_id else None
        reviewer = await self._get_user(db, reviewer_id)
        return self._to_item(expense, employee, cat, reviewer)

    def _to_item(
        self,
        e: Expense,
        employee: User | None,
        cat: ExpenseCategory | None,
        reviewer: User | None,
    ) -> ExpenseItem:
        def _user_info(u: User | None) -> ExpenseUserInfo | None:
            if u is None:
                return None
            return ExpenseUserInfo(id=u.id, name=u.name, emp_id=u.emp_id)

        return ExpenseItem(
            id=e.id,
            employee=_user_info(employee),
            category_id=e.category_id,
            category_name=cat.name if cat else None,
            title=e.title,
            description=e.description,
            amount=float(e.amount),
            currency=e.currency,
            expense_date=e.expense_date,
            receipt_name=e.receipt_name,
            status=e.status,
            reviewer=_user_info(reviewer),
            review_notes=e.review_notes,
            reviewed_at=e.reviewed_at,
            created_at=e.created_at,
        )


expense_service = ExpenseService()
