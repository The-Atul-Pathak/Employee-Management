from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.expense import ExpenseStatus
from app.schemas.expense import (
    ExpenseCategoryCreate,
    ExpenseCategoryItem,
    ExpenseCategoryListResponse,
    ExpenseCategoryUpdate,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseReview,
    MyExpensesResponse,
)
from app.services.expense_service import expense_service

router = APIRouter()

HR_ROLE_NAMES = {"hr", "human resources", "hr manager", "hr executive", "admin"}


def _is_hr(current_user: dict) -> bool:
    return bool(current_user.get("is_admin")) or current_user.get("role", "").lower() in HR_ROLE_NAMES


# ── Categories ─────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=ExpenseCategoryListResponse)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ExpenseCategoryListResponse:
    return await expense_service.list_categories(
        db=db, company_id=current_user["company_id"]
    )


@router.post("/categories", response_model=ExpenseCategoryItem, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: ExpenseCategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ExpenseCategoryItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await expense_service.create_category(
        db=db, company_id=current_user["company_id"], data=body
    )


@router.put("/categories/{category_id}", response_model=ExpenseCategoryItem)
async def update_category(
    category_id: uuid.UUID,
    body: ExpenseCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ExpenseCategoryItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await expense_service.update_category(
            db=db, company_id=current_user["company_id"], category_id=category_id, data=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        await expense_service.delete_category(
            db=db, company_id=current_user["company_id"], category_id=category_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Expenses ───────────────────────────────────────────────────────────────────

@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    employee_id: Optional[uuid.UUID] = Query(default=None),
    expense_status: Optional[ExpenseStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> ExpenseListResponse:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return await expense_service.list_expenses(
        db=db,
        company_id=current_user["company_id"],
        employee_id=employee_id,
        status_filter=expense_status,
        page=page,
        per_page=per_page,
    )


@router.get("/me", response_model=MyExpensesResponse)
async def get_my_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> MyExpensesResponse:
    return await expense_service.get_my_expenses(
        db=db,
        company_id=current_user["company_id"],
        employee_id=current_user["user_id"],
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=ExpenseItem, status_code=status.HTTP_201_CREATED)
async def create_expense(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    title: str = Form(...),
    amount: float = Form(...),
    expense_date: str = Form(...),
    currency: str = Form(default="INR"),
    description: Optional[str] = Form(default=None),
    category_id: Optional[uuid.UUID] = Form(default=None),
    receipt: Optional[UploadFile] = File(default=None),
) -> ExpenseItem:
    from datetime import date
    from app.schemas.expense import ExpenseCreate

    data = ExpenseCreate(
        category_id=category_id,
        title=title,
        description=description,
        amount=amount,
        currency=currency,
        expense_date=date.fromisoformat(expense_date),
    )
    return await expense_service.create_expense(
        db=db,
        company_id=current_user["company_id"],
        employee_id=current_user["user_id"],
        data=data,
        receipt=receipt,
    )


@router.put("/{expense_id}/review", response_model=ExpenseItem)
async def review_expense(
    expense_id: uuid.UUID,
    body: ExpenseReview,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ExpenseItem:
    if not _is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        return await expense_service.review_expense(
            db=db,
            company_id=current_user["company_id"],
            expense_id=expense_id,
            reviewer_id=current_user["user_id"],
            data=body,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
