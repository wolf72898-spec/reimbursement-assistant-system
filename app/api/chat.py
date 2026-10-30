# -*- coding: utf-8 -*-
"""
对话路由：会话管理与消息问答。
一期返回 JSON 非流式；SSE 流式输出为二期改造点（接口路径不变）。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import llm_available
from app.agent.router import classify_intent
from app.agent.tools import answer_policy, extract_expense
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.expense import ExpenseDraft
from app.models.user import User
from app.rag.retriever import hybrid_search
from app.schemas import MessageIn, MessageOut, SessionOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新的对话会话"""
    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的会话"""
    rows = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return rows.scalars().all()


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageOut,
    responses={503: {"description": "LLM 未配置"}},
)
async def send_message(
    session_id: int,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    核心问答接口。链路：
    存用户消息 → 意图路由 →（问答）RAG检索+LLM /（报销）字段抽取+存草稿
    → 存助手消息 → 返回。
    """
    if not llm_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LLM 未配置（设置 RAG_API_KEY 环境变量后重启）",
        )
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    # 1. 落库用户消息
    user_msg = ChatMessage(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    await db.flush()

    intent = classify_intent(body.content)
    meta: dict = {"intent": intent}
    if intent == "qa":
        # ---- 路 1：制度问答（RAG）----
        contexts = await hybrid_search(db, body.content, settings.TOP_K)
        if contexts is None:
            reply = "知识库还没有上传任何制度文档，请联系管理员先上传。"
        else:
            meta["contexts"] = contexts
            reply = await answer_policy(body.content, contexts)
    else:
        # ---- 路 2：报销发起（字段抽取 → 存草稿）----
        history = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(6)
        )
        dialog = [{"role": m.role, "content": m.content} for m in reversed(history.scalars().all())]
        extracted = await extract_expense(dialog)
        meta["extracted"] = extracted
        if "error" not in extracted:
            draft = ExpenseDraft(
                user_id=user.id,
                session_id=session_id,
                expense_type=extracted.get("expense_type", "未分类"),
                total_amount=float(extracted.get("total_amount") or 0),
                fields=extracted.get("fields", {}),
                missing_fields=extracted.get("missing_fields", []),
            )
            db.add(draft)
            missing = extracted.get("missing_fields") or []
            reply = (
                f"已为你生成报销单草稿（{extracted.get('expense_type', '未分类')}，"
                f"金额 {extracted.get('total_amount', 0)} 元）。"
                + (f"还需要补充：{'、'.join(missing)}。" if missing else "信息完整。")
            )
        else:
            reply = "抱歉，信息抽取出了点问题，请换个说法再试一次。"

    # 2. 落库助手消息并返回
    assistant_msg = ChatMessage(
        session_id=session_id, role="assistant", content=reply, meta=meta
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话历史消息"""
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id)
    )
    return rows.scalars().all()
