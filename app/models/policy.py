# -*- coding: utf-8 -*-
"""
制度文档表 + 切片表。
设计说明：embedding 一期存 JSON 数组（跨库可移植，检索在内存用 numpy）；
文档量上百份后切换 pgvector（_postgres 下把该列换成 Vector 类型 + HNSW 索引）。
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JsonType = JSON


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    # 差旅标准 / 发票规则 / 审批流程 ...
    doc_type: Mapped[str] = mapped_column(String(64), default="通用")
    file_path: Mapped[str] = mapped_column(String(512))
    # 同名文档重新上传则 version+1，旧版标 archived
    version: Mapped[int] = mapped_column(Integer, default=1)
    # processing / active / archived
    status: Mapped[str] = mapped_column(String(16), default="active")
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("policy_documents.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # 向量以 JSON 数组存储（见类注释的 pgvector 迁移说明）
    embedding: Mapped[Optional[list[Any]]] = mapped_column(JsonType, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
