# -*- coding: utf-8 -*-
"""
对话路由：会话管理、非流式问答（兼容保留）与 SSE 流式问答（主入口）。
"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import llm_available
from app.agent.loop import run_agent
from app.agent.router import classify_intent
from app.agent.tools import answer_policy, build_history, extract_expense
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.expense import ExpenseDraft
from app.models.user import User
from app.rag.retriever import hybrid_search
from app.schemas import MessageIn, MessageOut, SessionOut, StreamIn

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================================
# 会话管理
# ============================================================


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


# ============================================================
# 公共逻辑：会话校验 + 历史装载（流式/非流式共用）
# ============================================================


async def _load_context(db: AsyncSession, user: User, session_id: int, question: str):
    """校验会话归属、保存用户消息、装载最近 6 轮历史"""
    if not llm_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LLM 未配置，请联系管理员设置 RAG_API_KEY",
        )
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    if session.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该会话")

    # 用户消息先落库（中途断连也不丢）
    db.add(ChatMessage(session_id=session_id, role="user", content=question))
    await db.commit()

    # 最近 6 轮历史（12 条消息）
    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(12)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(rows.scalars().all())
    ]
    return history


# ============================================================
# 非流式接口（兼容保留）
# ============================================================


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
    """非流式问答（旧版兼容）。主入口请用 /api/chat/stream。"""
    history = await _load_context(db, user, session_id, body.content)

    intent = classify_intent(body.content)
    meta: dict = {"intent": intent}
    if intent == "qa":
        contexts = await hybrid_search(db, body.content, settings.TOP_K)
        if contexts is None:
            reply = "知识库还没有上传任何制度文档，请联系管理员先上传。"
        else:
            meta["contexts"] = contexts
            reply = await answer_policy(body.content, contexts, history)
    else:
        dialog = history + [{"role": "user", "content": body.content}]
        extracted = await asyncio.to_thread(extract_expense, dialog)
        meta["extracted"] = extracted
        reply, _ = _handle_expense_result(db, user, session_id, extracted)
        await db.commit()

    assistant_msg = ChatMessage(
        session_id=session_id, role="assistant", content=reply, meta=meta
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg


def _handle_expense_result(db, user, session_id: int, extracted: dict):
    """把抽取结果落库为草稿，返回 (回复文案, 是否建草稿)"""
    if "error" in extracted:
        return "抱歉，信息抽取出了点问题，请换个说法再试一次。", False
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
    return reply, True


# ============================================================
# SSE 流式接口（主入口）
# ============================================================


def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 消息"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream", responses={503: {"description": "LLM 未配置"}})
async def stream_message(
    body: StreamIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE 流式对话主入口（Agent 模式，提示词6）。
    LLM 自主决策调用工具，事件序列（动态）：
    tool_call → tool_result → sources → delta* → expense → done
    HTTP 级错误（401/403/404/422/503）在流开始前直接返回 JSON。
    """
    history = await _load_context(db, user, body.session_id, body.question)

    async def event_gen():
        try:
            yield _sse("status", {"message": "智能体思考中…"})
            async for event, data in run_agent(db, user, body.session_id, history, body.question):
                yield _sse(event, data)
        except Exception as e:  # 流内错误以 error 事件推送（响应头已发出）
            yield _sse("error", {"code": 500, "message": f"服务异常：{e}"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
