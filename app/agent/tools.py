# -*- coding: utf-8 -*-
"""
智能体工具集：政策问答与报销字段抽取。
对应架构方案 app/agent/tools.py，提示词模板存放在 prompts/ 下。
"""
import json
from pathlib import Path

from app.agent.llm.client import chat_completion, chat_completion_stream

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def build_history(history: list, max_rounds: int = 6) -> str:
    """
    拼接最近对话历史作为上下文（默认 6 轮 = 12 条消息）。
    让 AI 能理解"再补充一下刚才那笔"这类追问。
    """
    lines = [f"{m['role']}: {m['content']}" for m in history[-max_rounds * 2:]]
    return "\n".join(lines) if lines else "（无）"


async def answer_policy(question: str, contexts: list, history: list = None) -> str:
    """政策问答：RAG 检索片段 + 最近对话 → 拼提示词 → LLM 回答"""
    prompt = (
        _load_prompt("qa.txt")
        .replace("{history}", build_history(history or []))
        .replace("{context}", "\n---\n".join(
            f"片段{i+1}（来自 {c['doc_title']}）：{c['content']}"
            for i, c in enumerate(contexts)
        ))
        .replace("{question}", question)
    )
    return chat_completion([{"role": "user", "content": prompt}])


async def answer_policy_stream(question: str, contexts: list, history: list = None):
    """政策问答流式版：逐段产出文本增量（SSE 用）"""
    prompt = (
        _load_prompt("qa.txt")
        .replace("{history}", build_history(history or []))
        .replace("{context}", "\n---\n".join(
            f"片段{i+1}（来自 {c['doc_title']}）：{c['content']}"
            for i, c in enumerate(contexts)
        ))
        .replace("{question}", question)
    )
    async for piece in chat_completion_stream([{"role": "user", "content": prompt}]):
        yield piece


def extract_expense(dialog: list) -> dict:
    """
    报销字段抽取（同步函数，调用方用 asyncio.to_thread 包装避免阻塞事件循环）。
    把对话原文交给 LLM 抽成结构化 JSON。
    注意：模板含 JSON 花括号，必须用 replace 而不是 str.format。
    解析失败时返回带 error 的兜底结构，不抛异常中断链路。
    """
    prompt = _load_prompt("expense.txt").replace(
        "{dialog}",
        "\n".join(f"{m['role']}: {m['content']}" for m in dialog),
    )
    raw = chat_completion([{"role": "user", "content": prompt}])
    # 剥掉模型可能裹上的 ```json 围栏
    raw = raw.strip().removeprefix("```json").removeprefix("```")
    raw = raw.removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "抽取结果解析失败", "raw": raw[:500]}
