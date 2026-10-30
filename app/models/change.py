# -*- coding: utf-8 -*-
"""工程变更与签证协同领域模型：项目 / 变更单 / 变更版本 / 交底任务 / 签证单

设计要点（对应设计方案）：
- 版本唯一：ChangeVersion 用 is_valid 标记唯一有效版本，新版本上传即旧版作废；
- 交底必达：每个有效版本生成 Briefing 任务，签收留痕（signed_at + 签收人）；
- 签证同源：VisaOrder 通过 change_id + source_version 关联变更，杜绝三个版本不一致；
- 留痕可审计：状态流转时间字段（submitted/confirmed/completed）全部落库。
"""
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JsonType = JSON


class Project(Base):
    """工程项目（一个项目下多个变更）"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    owner: Mapped[str] = mapped_column(String(64), default="")       # 业主
    contractor: Mapped[str] = mapped_column(String(64), default="")  # 总包
    manager: Mapped[str] = mapped_column(String(64), default="")     # 项目经理
    status: Mapped[str] = mapped_column(String(16), default="在建")
    # 现状基线（用于看板对照：返工次数、人工复核成本等无法从单据推导的指标）
    baseline: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChangeOrder(Base):
    """变更单：登记即编号，状态机驱动流转"""

    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(24), default="设计变更")  # 设计变更/现场签证/材料代用/工期调整
    reason: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(64), default="")          # 部位
    status: Mapped[str] = mapped_column(String(16), default="待交底", index=True)
    priority: Mapped[str] = mapped_column(String(8), default="中")
    initiator: Mapped[str] = mapped_column(String(64), default="")         # 发起人
    owner_role: Mapped[str] = mapped_column(String(64), default="")        # 责任人
    amount_impact: Mapped[float] = mapped_column(Float, default=0.0)       # 预计金额影响（元）
    schedule_impact: Mapped[int] = mapped_column(Integer, default=0)       # 工期影响（天）
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ChangeVersion(Base):
    """变更版本：同一变更的新旧图纸/说明，is_valid=True 的仅有一条"""

    __tablename__ = "change_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("change_orders.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text, default="")      # 本版变更摘要
    file_name: Mapped[str] = mapped_column(String(128), default="")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Briefing(Base):
    """技术交底任务：按角色定向推送，签收留痕"""

    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("change_orders.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    role: Mapped[str] = mapped_column(String(32), default="")     # 施工员/班组长/造价/质量安全
    assignee: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="待签收", index=True)  # 待签收/已签收/已超时
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VisaOrder(Base):
    """签证单：AI 起草 → 造价核定 → 业主确认，来源版本唯一"""

    __tablename__ = "visa_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("change_orders.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    quantity_desc: Mapped[str] = mapped_column(Text, default="")   # 工程量与计算式
    status: Mapped[str] = mapped_column(String(16), default="草稿", index=True)
    # 草稿/待核定/待业主确认/已确认/已驳回
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    reviewer: Mapped[str] = mapped_column(String(64), default="")
    drafted_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
