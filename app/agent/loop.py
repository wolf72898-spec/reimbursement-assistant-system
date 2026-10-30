# -*- coding: utf-8 -*-
"""
Agent 运行循环（提示词6）：LLM 自主决策 + 服务端状态机守门。
- 系统提示词从数据库读取（管理员改完立即生效，提示词5），未配置时回退内置文件
- 流式输出：正文增量逐段产出；工具调用累积完成后统一执行
- SSE 事件：tool_call / tool_result / sources / delta / expense / done / error
- 最多 MAX_ROUNDS 轮，防止死循环
"""
import json
from datetime import date
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import get_async_client, llm_available
from app.agent.registry import (
    EXECUTORS,
    TOOL_SCHEMAS,
    AgentContext,
    tool_summary,
)
from app.core.config import settings
from app.models.prompt import PromptTemplate
from app.models.user import User

MAX_ROUNDS = 8  # 单次提问最多工具调用轮数，防止死循环
_PROMPT_DIR = Path(__file__).parent / "prompts"
_ALLOWED_PROMPTS = {"agent", "qa", "expense"}


async def load_prompt_text(db: AsyncSession, name: str) -> str:
    """
    从数据库读提示词模板（管理员修改后立即生效）。
    库中没有时回退到内置文件（首次启动会播种，正常不会走到回退）。
    """
    default = (_PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
    from sqlalchemy import select
    obj = (
        await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    ).scalar_one_or_none()
    content = obj.content if obj is not None else default
    return content.replace("{today}", date.today().isoformat())


async def seed_prompts(db: AsyncSession) -> None:
    """启动时播种默认提示词模板（已存在的不覆盖，管理员修改优先）"""
    from sqlalchemy import select
    for name in _ALLOWED_PROMPTS:
        exists = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
        ).scalar_one_or_none()
        if exists is None:
            db.add(PromptTemplate(
                name=name,
                content=(_PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8"),
                is_default=True,
            ))
    await db.commit()


async def run_agent(
    db: AsyncSession, user: User, session_id: int, history: list, question: str
):
    """
    运行 Agent 循环，产出 (event, data) 事件序列。
    由 chat.py 转成 SSE 推送；异常一律转 error 事件（响应头已发出的场景）。
    """
    if not llm_available():
        yield "error", {"code": 503, "message": "LLM 未配置，请联系管理员设置 RAG_API_KEY"}
        return

    ctx = AgentContext(db=db, user=user, session_id=session_id)
    system_prompt = await load_prompt_text(db, "agent")
    messages = [
        {"role": "system", "content": system_prompt},
        *[{"role": m["role"], "content": m["content"]} for m in history[-12:]],
        {"role": "user", "content": question},
    ]

    final_text_parts: list = []
    try:
        for _round in range(MAX_ROUNDS):
            # ---- 流式调用（带工具）----
            stream = await get_async_client().chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                temperature=0.3,
                stream=True,
            )
            content_buf: list = []
            # 工具调用累积容器：index -> {id, name, arguments}
            pending_tools: dict = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # 正文增量 → 立即推送（打字机效果）
                if delta.content:
                    content_buf.append(delta.content)
                    yield "delta", {"content": delta.content}
                # 工具调用分片累积
                for tc in delta.tool_calls or []:
                    slot = pending_tools.setdefault(
                        tc.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments

            final_text_parts.append("".join(content_buf))

            # ---- 无工具调用：回答结束，退出循环 ----
            if not pending_tools:
                break

            # ---- 有工具调用：先补一条 assistant 消息（含 tool_calls）----
            assistant_tool_calls = [
                {
                    "id": slot["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
                }
                for i, slot in pending_tools.items()
            ]
            messages.append({
                "role": "assistant",
                "content": "".join(content_buf) or None,
                "tool_calls": assistant_tool_calls,
            })

            # ---- 逐个执行工具（服务端状态机在此守门）----
            for tc in assistant_tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield "tool_call", {"name": name, "args": args}
                executor = EXECUTORS.get(name)
                if executor is None:
                    result = {"error": "TOOL_NOT_FOUND", "message": f"未知工具 {name}"}
                else:
                    # DB 操作都是 async；LLM 同步调用只在检索内不出现，可安全直接执行
                    result = await executor(args, ctx)
                ctx.tool_trace.append({"tool": name, "args": args, "result": result})
                yield "tool_result", {"name": name, "summary": tool_summary(name, result)}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # 引用来源在检索后即可推送
            if ctx.sources:
                yield "sources", {"sources": ctx.sources[:2]}
            if ctx.drafts:
                for did in dict.fromkeys(ctx.drafts):
                    from sqlalchemy import select as _s
                    from app.models.expense import ExpenseDraft as _D
                    d = (await db.execute(_s(_D).where(_D.id == did))).scalar_one_or_none()
                    if d is not None:
                        yield "expense", {
                            "draft_id": d.id, "expense_type": d.expense_type,
                            "total_amount": d.total_amount, "fields": d.fields,
                            "missing_fields": d.missing_fields or [],
                            "status": d.status,
                        }
        else:
            # 超过最大轮数：给出兜底提示
            tail = "这个问题处理步骤较多，已暂停。请补充信息后继续。"
            final_text_parts.append(tail)
            yield "delta", {"content": tail}

        # ---- 完整回答落库（meta 存工具轨迹与引用来源）----
        from app.models.chat import ChatMessage
        full_text = "".join(final_text_parts)
        db.add(ChatMessage(
            session_id=session_id, role="assistant", content=full_text,
            meta={
                "agent": True,
                "tool_trace": ctx.tool_trace,
                "sources": ctx.sources[:2],
                "drafts": list(dict.fromkeys(ctx.drafts)),
            },
        ))
        await db.commit()
        yield "done", {"message": "处理完成", "tool_trace": ctx.tool_trace}

    except Exception as e:  # 流内错误以 error 事件推送
        yield "error", {"code": 500, "message": f"智能体处理异常：{e}"}
