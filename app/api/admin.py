# -*- coding: utf-8 -*-
"""
管理端路由：
- /overview：看板统计
- /prompts：提示词模板管理（改完立即生效，存数据库，提示词5）
- /audit：对话审计（违规标记，提示词5）
"""
import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import _ALLOWED_PROMPTS, _PROMPT_DIR, load_prompt_text
from app.agent.registry import _risk_hits
from app.core.deps import get_db, require_admin
from app.models.agent import AgentStepLog
from app.models.chat import ChatMessage, ChatSession
from app.models.expense import ExpenseDraft
from app.models.prompt import PromptTemplate
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================
# 看板概览
# ============================================================


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


# ============================================================
# 提示词模板管理（提示词5）
# ============================================================


class PromptUpdateIn(BaseModel):
    content: str = Field(min_length=10, max_length=20000)


@router.get("/prompts")
async def list_prompts(
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出全部提示词模板（agent/qa/expense）"""
    rows = await db.execute(select(PromptTemplate).order_by(PromptTemplate.id))
    return [
        {
            "name": p.name, "content": p.content, "is_default": p.is_default,
            "updated_at": str(p.updated_at),
        }
        for p in rows.scalars().all()
    ]


@router.put("/prompts/{name}")
async def update_prompt(
    name: str,
    body: PromptUpdateIn,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """保存模板修改，立即生效（回答时从数据库实时读取）"""
    if name not in _ALLOWED_PROMPTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知模板名，允许：{'、'.join(_ALLOWED_PROMPTS)}")
    obj = (
        await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    obj.content = body.content
    obj.is_default = False
    obj.updated_by = user.id
    await db.commit()
    return {"ok": True, "name": name, "message": "已保存，对问答立即生效"}


@router.post("/prompts/{name}/reset")
async def reset_prompt(
    name: str,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """恢复内置默认模板"""
    if name not in _ALLOWED_PROMPTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知模板名，允许：{'、'.join(_ALLOWED_PROMPTS)}")
    obj = (
        await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    obj.content = (_PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
    obj.is_default = True
    await db.commit()
    return {"ok": True, "name": name, "message": "已恢复默认模板"}


# ============================================================
# Agent 决策日志（提示词7）：每轮工具调用记录，供阶段5分析
# ============================================================


@router.get("/traces")
async def agent_traces(
    session_id: int | None = None,
    limit: int = 100,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Agent 决策日志：工具名 / 参数 / 耗时 / 结果摘要 / 轮次 / 状态"""
    limit = min(max(limit, 1), 500)
    q = select(AgentStepLog).order_by(AgentStepLog.id.desc()).limit(limit)
    if session_id is not None:
        q = q.where(AgentStepLog.session_id == session_id)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": s.id, "session_id": s.session_id, "round_no": s.round_no,
            "tool_name": s.tool_name, "arguments": s.arguments,
            "elapsed_ms": s.elapsed_ms, "result_summary": s.result_summary,
            "status": s.status, "created_at": str(s.created_at),
        }
        for s in rows
    ]


# ============================================================
# 对话审计（提示词5）：按员工/时间筛选，违规标记
# ============================================================


@router.get("/audit/users")
async def audit_users(
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """员工下拉列表"""
    rows = await db.execute(select(User).order_by(User.id))
    return [
        {"id": u.id, "username": u.username, "department": u.department, "role": u.role}
        for u in rows.scalars().all()
    ]


@router.get("/audit")
async def audit_messages(
    user_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
    flagged_only: bool = False,
    page: int = 1,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    对话审计：按员工/时间范围筛选对话消息（正序），命中违规规则的标记
    risk_reasons。违规规则（可解释的关键词规则）：拆单/分开发票/没有发票/
    替票/虚开/多开 等规避性表述。
    """
    page = max(page, 1)
    page_size = 30
    q = (
        select(ChatMessage, User.username, User.department)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .join(User, ChatSession.user_id == User.id)
        .order_by(ChatMessage.id.desc())
    )
    if user_id is not None:
        q = q.where(ChatSession.user_id == user_id)
    if start:
        try:
            q = q.where(ChatMessage.created_at >= datetime.fromisoformat(start))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "start 日期格式应为 YYYY-MM-DD")
    if end:
        try:
            q = q.where(ChatMessage.created_at < datetime.fromisoformat(end).replace(
                hour=23, minute=59, second=59
            ))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "end 日期格式应为 YYYY-MM-DD")

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    # flagged_only 时先取最近 500 条再内存过滤（量级足够一期使用）
    if flagged_only:
        rows = (await db.execute(q.limit(500))).all()
    else:
        rows = (await db.execute(q.limit(page_size).offset((page - 1) * page_size))).all()

    items = []
    for msg, username, department in rows:
        hits = _risk_hits(msg.content) if msg.role == "user" else []
        if flagged_only and not hits:
            continue
        items.append({
            "id": msg.id, "session_id": msg.session_id,
            "username": username, "department": department,
            "role": msg.role, "content": msg.content[:500],
            "created_at": str(msg.created_at),
            "flagged": bool(hits),
            "risk_reasons": hits,
        })
    if flagged_only:
        total = len(items)
        items = items[(page - 1) * page_size: page * page_size]
    return {"total": total, "page": page, "page_size": page_size, "items": items}
