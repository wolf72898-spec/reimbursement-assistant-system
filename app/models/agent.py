# -*- coding: utf-8 -*-
"""Agent 编排相关表（提示词7）：决策日志 + 待确认动作（人机中断）"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JsonType = JSON


class AgentStepLog(Base):
    """
    Agent 决策日志表（阶段5分析用）：
    每次工具调用记一行——工具名 / 参数 / 耗时 / 结果摘要 / 轮次。
    """
    __tablename__ = "agent_step_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[int]] = mapped_column(index=True)
    user_id: Mapped[Optional[int]] = mapped_column(index=True)
    round_no: Mapped[int] = mapped_column(Integer, default=0)   # 第几轮决策
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)  # 执行耗时（毫秒）
    result_summary: Mapped[str] = mapped_column(Text, default="")
    # ok=成功 / error=执行出错 / blocked=状态机或用户拒绝 / waiting=转人工确认
    status: Mapped[str] = mapped_column(String(16), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentPendingAction(Base):
    """
    待人工确认动作（create_draft 强制中断）：
    中断时把完整 messages 快照存进来，员工确认后从快照恢复继续执行。
    """
    __tablename__ = "agent_pending_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # action_id
    session_id: Mapped[Optional[int]] = mapped_column(index=True)
    user_id: Mapped[Optional[int]] = mapped_column(index=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    # 中断时刻的完整状态：messages / sources / drafts / tool_trace / round
    snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    # pending → confirmed / rejected / expired
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
