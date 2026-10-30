# -*- coding: utf-8 -*-
"""报销单路由：草稿 CRUD 与提交。审批流二期接入。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import ExpenseDraft
from app.models.user import User
from app.schemas import ExpenseOut, ExpenseSubmitIn

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("/my", response_model=list[ExpenseOut])
async def my_expenses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的报销单（含对话生成的草稿与手工创建的）"""
    rows = await db.execute(
        select(ExpenseDraft)
        .where(ExpenseDraft.user_id == user.id)
        .order_by(ExpenseDraft.id.desc())
    )
    return rows.scalars().all()


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    body: ExpenseSubmitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手工创建报销单（不经对话抽取的入口）"""
    draft = ExpenseDraft(
        user_id=user.id,
        expense_type=body.expense_type,
        total_amount=body.total_amount,
        fields=body.fields,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return draft


@router.post("/{expense_id}/submit", response_model=ExpenseOut)
async def submit_expense(
    expense_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交草稿（draft → submitted）。审批流转在一期之后。"""
    draft = await db.get(ExpenseDraft, expense_id)
    if draft is None or draft.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报销单不存在")
    draft.status = "submitted"
    await db.commit()
    await db.refresh(draft)
    return draft


@router.get("", response_model=list[ExpenseOut])
async def all_expenses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看全部报销单"""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    rows = await db.execute(select(ExpenseDraft).order_by(ExpenseDraft.id.desc()))
    return rows.scalars().all()
