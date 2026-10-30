# -*- coding: utf-8 -*-
"""
LLM 统一适配层：对话 + Embedding 都走 OpenAI 兼容协议。
换供应商 = 改环境变量（RAG_BASE_URL / RAG_MODEL / RAG_API_KEY），代码不动。
对应架构方案 app/agent/llm/，从原型 rag_prototype.py 迁移而来。
"""
from typing import Optional

from openai import OpenAI

from app.core.config import settings


def _client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def llm_available() -> bool:
    """是否配置了 LLM Key（未配置时相关接口返回 503 而非报错崩溃）"""
    return bool(settings.LLM_API_KEY)


def chat_completion(messages: list, temperature: float = 0.3) -> str:
    """
    调用对话模型（非流式；SSE 流式在二期接入）。
    temperature=0.3：报销场景要求严谨，降低编造概率。
    """
    client = _client(settings.LLM_API_KEY, settings.LLM_BASE_URL)
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def embed_texts(texts: list) -> list:
    """
    批量文本向量化，返回 [[float,...], ...]。
    Embedding 供应商独立配置（典型组合：DeepSeek 对话 + 千问向量）。
    """
    client = _client(settings.EMBED_API_KEY, settings.EMBED_BASE_URL)
    resp = client.embeddings.create(model=settings.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]
