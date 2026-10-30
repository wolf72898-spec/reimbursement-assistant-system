# -*- coding: utf-8 -*-
"""会话与消息表：员工与智能体的多轮对话记录"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 用 SQLite 的 JSON 类型做跨库兼容（PostgreSQL 下换 JSONB 即可）
JsonType = JSON


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="新会话")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), index=True
    )
    # user / assistant / tool
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    # 元数据：意图分类结果、引用的制度条款、token 用量等
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
