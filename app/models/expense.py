# -*- coding: utf-8 -*-
"""报销单草稿表：AI 从对话中抽取的字段落库，可回溯来源会话"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JsonType = JSON


class ExpenseDraft(Base):
    __tablename__ = "expense_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 来源会话，可回溯这张草稿是怎么聊出来的
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True
    )
    # draft / submitted（一期止步于 submitted，审批流二期）
    status: Mapped[str] = mapped_column(String(16), default="draft")
    expense_type: Mapped[str] = mapped_column(String(32), default="未分类")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    # 抽取结果：日期、事由、明细行等，jsonb 便于演进结构
    fields: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    # LLM 标记的缺失字段列表，驱动前端/对话追问
    missing_fields: Mapped[Optional[list[Any]]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
