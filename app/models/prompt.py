# -*- coding: utf-8 -*-
"""提示词模板表：管理员可在后台修改，保存后立即对问答生效（提示词5）"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 模板名：agent（智能体系统提示词）/ qa（问答）/ expense（字段抽取）
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    # True 表示与代码内置默认一致（reset 后回到该状态）
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
