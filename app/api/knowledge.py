# -*- coding: utf-8 -*-
"""
知识库路由（管理员）：制度文档上传与列表。
上传链路：存原件 → 解析 → 切片 → Embedding → 入库。
"""
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import embed_texts, llm_available
from app.core.config import settings
from app.core.deps import get_db, require_admin
from app.models.policy import PolicyChunk, PolicyDocument
from app.rag.retriever import load_text, split_text
from sqlalchemy.orm import Session as _S  # noqa: F401

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=201, responses={503: {"description": "Embedding 未配置"}})
async def upload_document(
    file: UploadFile,
    doc_type: str = "通用",
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    上传制度文档（Markdown/TXT）。
    同名文档重复上传时版本 +1，旧版归档。
    """
    if not llm_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Embedding 未配置，无法向量化"
        )
    raw = await file.read()
    text = load_text(raw, file.filename or "doc.md")
    if not text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文档内容为空")

    # 同名文档 → 旧版归档，新版本号 +1
    title = os.path.splitext(file.filename or "未命名")[0]
    old = (
        await db.execute(
            select(PolicyDocument)
            .where(PolicyDocument.title == title, PolicyDocument.status == "active")
        )
    ).scalars().all()
    version = 1
    if old:
        version = max(d.version for d in old) + 1
        for d in old:
            d.status = "archived"

    # 原件落盘（二期换对象存储）
    os.makedirs(settings.POLICY_DIR, exist_ok=True)
    safe_name = f"{title}_v{version}.md"
    path = os.path.join(settings.POLICY_DIR, safe_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    # 切片 + 向量化
    doc = PolicyDocument(
        title=title, doc_type=doc_type, file_path=path,
        version=version, status="active", uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()

    chunks = split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    # Embedding 失败时降级为纯 BM25 检索（如仅配置 DeepSeek 时），链路不断
    try:
        vectors = embed_texts(chunks)
    except Exception:
        vectors = [None] * len(chunks)
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        db.add(
            PolicyChunk(
                document_id=doc.id, chunk_index=i, content=chunk,
                embedding=vec, token_count=len(chunk),
            )
        )
    await db.commit()
    return {"id": doc.id, "title": title, "version": version, "chunks": len(chunks)}


@router.get("/documents")
async def list_documents(
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看知识库文档列表"""
    rows = await db.execute(
        select(PolicyDocument).order_by(PolicyDocument.id.desc())
    )
    return [
        {
            "id": d.id, "title": d.title, "doc_type": d.doc_type,
            "version": d.version, "status": d.status, "created_at": str(d.created_at),
        }
        for d in rows.scalars().all()
    ]
