# -*- coding: utf-8 -*-
"""
RAG 工具集：文档解析、切片、混合检索。
从原型 rag_prototype.py 迁移，检索端从 FAISS 改为 numpy 内存计算
（一期文档量级 < 数百片，FAISS 在二期文档量大后引入）。
"""
import re
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import embed_texts
from app.models.policy import PolicyChunk, PolicyDocument

# ============================================================
# 【核心复用】文档解析与切片（与原型一致）
# ============================================================


def load_text(raw: bytes, filename: str) -> str:
    """解析上传的 Markdown/TXT 文件，清理图片与链接语法"""
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text


def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list:
    """滑动窗口切片，相邻片重叠防条款截断（二期改按条款结构切分）"""
    chunks, step = [], chunk_size - overlap
    for i in range(0, len(text), step):
        piece = text[i:i + chunk_size]
        if len(piece) < overlap:
            break
        chunks.append(piece)
    return chunks


# ============================================================
# 【核心复用】中文 bigram 分词 + BM25（与原型一致）
# ============================================================


def tokenize_zh(text: str) -> list:
    """中文二元组分词：零依赖的近似分词，BM25 只影响排序够用了"""
    segments = re.split(r"[，。；：、！？\s\n,.;:!?]+", text)
    tokens = []
    for seg in segments:
        if len(seg) <= 2:
            tokens.append(seg)
        else:
            tokens += [seg[i:i + 2] for i in range(len(seg) - 1)]
    return tokens


# ============================================================
# 混合检索器：每次问答时从库中装载全部启用切片，RRF 融合
# ============================================================


async def _load_chunks(db: AsyncSession):
    """装载所有 active 文档的切片（内容 + 所属文档名 + 向量）"""
    rows = await db.execute(
        select(PolicyChunk, PolicyDocument.title, PolicyDocument.version)
        .join(PolicyDocument, PolicyChunk.document_id == PolicyDocument.id)
        .where(PolicyDocument.status == "active")
    )
    return rows.all()


def _rrf_fuse(ranked_lists: list, top_k: int, rrf_k: int = 60) -> list:
    """RRF 排名融合：score = Σ 1/(k+rank)，跨量纲融合的标准做法"""
    scores: dict = {}
    for ranked in ranked_lists:
        for rank, idx in enumerate(ranked):
            if idx < 0:
                continue
            scores[idx] = scores.get(idx, 0) + 1.0 / (rrf_k + rank + 1)
    best = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [idx for idx, _ in best]


async def hybrid_search(
    db: AsyncSession, query: str, top_k: int = 3
) -> Optional[list]:
    """
    BM25 + 向量混合检索 Top-K 片段。
    返回 None 表示知识库为空；向量部分调 Embedding API 失败时
    降级为纯 BM25，保证问答链路不断。
    """
    rows = await _load_chunks(db)
    if not rows:
        return None

    contents = [r[0].content for r in rows]
    embeddings = [r[0].embedding for r in rows]

    # 路 1：BM25 关键词检索
    bm25 = BM25Okapi([tokenize_zh(c) for c in contents])
    bm25_ranked = np.argsort(bm25.get_scores(tokenize_zh(query)))[::-1][:top_k * 3]

    # 路 2：向量检索（余弦相似度，numpy 实现）
    vec_ranked: list = []
    if all(e is not None for e in embeddings):
        try:
            q_vec = np.array(embed_texts([query])[0], dtype="float32")
            mat = np.array(embeddings, dtype="float32")
            # 归一化后点积 = 余弦相似度
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            mat = mat / np.clip(norms, 1e-10, None)
            q_vec = q_vec / max(np.linalg.norm(q_vec), 1e-10)
            sims = mat @ q_vec
            vec_ranked = np.argsort(sims)[::-1][:top_k * 3]
        except Exception:
            vec_ranked = []  # 降级：只用 BM25

    best = _rrf_fuse([list(bm25_ranked), list(vec_ranked)], top_k)
    # 返回带来源的结构：内容 + 所属文档名（供前端展示引用）
    return [
        {"content": rows[i][0].content, "doc_title": f"{rows[i][1]}_v{rows[i][2]}"}
        for i in best
    ]
