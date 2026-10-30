# -*- coding: utf-8 -*-
"""管理端路由：系统概览统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models.chat import ChatSession
from app.models.expense import ExpenseDraft
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
async def overview(
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """看板概览：用户数 / 会话数 / 报销单数（按状态）"""
    users = await db.scalar(select(func.count()).select_from(User))
    sessions = await db.scalar(select(func.count()).select_from(ChatSession))
    drafts = await db.scalar(
        select(func.count()).select_from(ExpenseDraft)
        .where(ExpenseDraft.status == "draft")
    )
    submitted = await db.scalar(
        select(func.count()).select_from(ExpenseDraft)
        .where(ExpenseDraft.status == "submitted")
    )
    return {
        "users": users,
        "sessions": sessions,
        "drafts": drafts,
        "submitted": submitted,
    }
