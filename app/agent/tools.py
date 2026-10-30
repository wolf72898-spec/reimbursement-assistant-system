# -*- coding: utf-8 -*-
"""
智能体工具集：政策问答与报销字段抽取。
对应架构方案 app/agent/tools.py，提示词模板存放在 prompts/ 下。
"""
import json
from pathlib import Path

from app.agent.llm.client import chat_completion

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


async def answer_policy(question: str, contexts: list) -> str:
    """政策问答：RAG 检索片段 → 拼提示词 → LLM 回答"""
    prompt = (
        _load_prompt("qa.txt")
        .replace("{context}", "\n---\n".join(
            f"片段{i+1}：{c}" for i, c in enumerate(contexts)
        ))
        .replace("{question}", question)
    )
    return chat_completion([{"role": "user", "content": prompt}])


async def extract_expense(dialog: list) -> dict:
    """
    报销字段抽取：把对话原文交给 LLM 抽成结构化 JSON。
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
