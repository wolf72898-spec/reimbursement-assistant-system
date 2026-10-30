# -*- coding: utf-8 -*-
"""
AgentHarness —— 智能体编排骨架（提示词7）。

【框架选型：自研轻量 Harness，不引入 LangChain/LangGraph】
理由：
1. 本项目工具带副作用（建单/提交）且被服务端状态机守门，需要完全掌控
   "执行前拦截"——HITL 人机确认中断在重框架里要绕 event/checkpointer 一大圈；
2. 前端走自研 SSE 事件协议（tool_call/tool_result/confirm_request/expense…），
   重框架的事件模型对不上，还要写适配层；
3. 循环本体只有 ~100 行，零新增依赖，调试直观。
Harness = 编排循环 + 工具注册表(registry) + 状态机(ticket) + 日志(agent_step_logs)
        + 中断恢复(agent_pending_actions)，后期要换 LangGraph 时这五块可平移。

【执行循环】模型决策 → 执行工具（状态机守门 + create_draft 强制中断）→
结果回填 → 再决策，最多 MAX_ROUNDS=5 轮。

【人机确认（HITL）】模型决定 create_draft 时不直接执行：
1. 把草稿参数 + 完整对话快照存入 agent_pending_actions；
2. 通过 SSE confirm_request 事件把草稿内容发给员工；
3. 员工点「确认/取消」→ POST /api/chat/confirm → resume() 从快照恢复：
   确认则真正建单并继续循环，取消则以"用户拒绝"回填让模型善后。

【决策日志】每次工具调用写一行 agent_step_logs（工具名/参数/耗时/结果摘要/轮次）。
"""
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm.client import get_async_client, llm_available
from app.agent.registry import (
    EXECUTORS,
    TOOL_SCHEMAS,
    AgentContext,
    tool_summary,
)
from app.core.config import settings
from app.models.agent import AgentPendingAction, AgentStepLog
from app.models.chat import ChatMessage
from app.models.expense import ExpenseDraft
from app.models.prompt import PromptTemplate
from app.models.user import User

MAX_ROUNDS = 5          # 单次提问最多 5 轮决策（提示词7要求）
_PROMPT_DIR = Path(__file__).parent / "prompts"
_ALLOWED_PROMPTS = {"agent", "qa", "expense"}


# ============================================================
# 提示词模板加载（存数据库，管理员改完立即生效）
# ============================================================


async def load_prompt_text(db: AsyncSession, name: str) -> str:
    """从数据库读提示词模板；库中没有时回退内置文件"""
    default = (_PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
    obj = (
        await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    ).scalar_one_or_none()
    content = obj.content if obj is not None else default
    from datetime import date
    return content.replace("{today}", date.today().isoformat())


async def seed_prompts(db: AsyncSession) -> None:
    """启动时播种默认提示词模板（管理员已自定义的不覆盖）"""
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


# ============================================================
# 编排骨架
# ============================================================


class AgentHarness:
    """一次 Agent 运行的完整编排水合对象：可 run（新提问）也可 resume（确认后恢复）"""

    def __init__(self, db: AsyncSession, user: User, session_id: int):
        self.db = db
        self.user = user
        self.session_id = session_id
        self.ctx = AgentContext(db=db, user=user, session_id=session_id)
        self.messages: list = []   # 发给 LLM 的完整消息列表（含工具结果）
        self.round = 0             # 当前决策轮次

    # ---------- 决策日志 ----------

    async def _log_step(self, tool_name: str, args: dict, elapsed_ms: int,
                        summary: str, status: str = "ok") -> None:
        """每次工具执行后写决策日志（供阶段5分析）"""
        self.db.add(AgentStepLog(
            session_id=self.session_id, user_id=self.user.id,
            round_no=self.round, tool_name=tool_name, arguments=args,
            elapsed_ms=elapsed_ms, result_summary=summary[:500], status=status,
        ))
        await self.db.commit()

    # ---------- 单轮：流式调用 LLM 并累积工具调用 ----------

    async def _decide(self) -> tuple[list, list]:
        """
        调用 LLM（流式、带工具）。
        返回 (正文片段列表, 待执行工具调用列表)。
        正文增量不在这里推送——由调用方 yield，这里只负责累积。
        """
        content_buf: list = []
        pending_tools: dict = {}  # index -> {id, name, arguments}
        stream = await get_async_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=self.messages,
            tools=TOOL_SCHEMAS,
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_buf.append(delta.content)
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
        return content_buf, list(pending_tools.values())

    async def _execute_tool(self, tc: dict):
        """执行单个工具调用：守门 → 计时 → 日志。返回 (result, interrupt_action|None)"""
        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        t0 = time.monotonic()

        # ---- HITL 强制中断：create_draft 一律先转人工确认 ----
        if name == "create_draft":
            # 同一会话已有待确认动作时不再叠加，避免堆积
            existing = (
                await self.db.execute(select(AgentPendingAction).where(
                    AgentPendingAction.session_id == self.session_id,
                    AgentPendingAction.status == "pending",
                ))
            ).scalar_one_or_none()
            if existing is not None:
                result = {"error": "CONFIRM_PENDING",
                          "message": "已有一张草稿等待你确认，请先在上方卡片点「确认创建」或「取消」"}
                await self._log_step(name, args, int((time.monotonic() - t0) * 1000),
                                     tool_summary(name, result), status="blocked")
                return result, None
            action = AgentPendingAction(
                id=uuid.uuid4().hex[:16],
                session_id=self.session_id, user_id=self.user.id,
                tool_name=name, arguments=args,
                snapshot=self._snapshot(),
                status="pending",
            )
            self.db.add(action)
            await self.db.commit()
            await self._log_step(name, args, int((time.monotonic() - t0) * 1000),
                                 "已拦截，等待员工确认草稿内容", status="waiting")
            return None, action  # interrupt

        # ---- 普通工具：状态机在执行器内部守门 ----
        executor = EXECUTORS.get(name)
        if executor is None:
            result = {"error": "TOOL_NOT_FOUND", "message": f"未知工具 {name}"}
            await self._log_step(name, args, 0, result["message"], status="error")
            return result, None
        try:
            result = await executor(args, self.ctx)
        except Exception as e:  # 工具内部异常不炸整条链路
            result = {"error": "TOOL_ERROR", "message": f"工具执行异常：{e}"}
        elapsed = int((time.monotonic() - t0) * 1000)
        blocked = bool(result.get("error"))
        await self._log_step(name, args, elapsed, tool_summary(name, result),
                             status="blocked" if blocked else "ok")
        return result, None

    def _snapshot(self) -> dict:
        """中断时刻的完整状态快照（resume 时恢复）"""
        return {
            "messages": self.messages,
            "round": self.round,
            "sources": self.ctx.sources[:2],
            "drafts": list(dict.fromkeys(self.ctx.drafts)),
            "tool_trace": self.ctx.tool_trace,
        }

    def _restore(self, snapshot: dict) -> None:
        self.messages = snapshot.get("messages", [])
        self.round = snapshot.get("round", 0)
        self.ctx.sources = snapshot.get("sources", [])
        self.ctx.drafts = snapshot.get("drafts", [])
        self.ctx.tool_trace = snapshot.get("tool_trace", [])

    # ---------- 主循环 ----------

    async def run(self, question: str, history: list):
        """新提问：产出 (event, data) 事件序列，可能以 done 或 confirm_request 结束"""
        if not llm_available():
            yield "error", {"code": 503, "message": "LLM 未配置，请联系管理员设置 RAG_API_KEY"}
            return
        system_prompt = await load_prompt_text(self.db, "agent")
        self.messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in history[-12:]],
            {"role": "user", "content": question},
        ]
        async for ev in self._loop():
            yield ev

    async def resume(self, action_id: str, approved: bool):
        """确认/取消后：从快照恢复，回填工具结果，继续循环"""
        action = await self.db.get(AgentPendingAction, action_id)
        if action is None:
            yield "error", {"code": 404, "message": "确认请求不存在或已过期"}
            return
        if action.status != "pending":
            yield "error", {"code": 409, "message": f"该请求已处理过（{action.status}），请勿重复操作"}
            return
        self._restore(action.snapshot or {})
        t0 = time.monotonic()
        if approved:
            # 确认 → 真正执行建单（此时状态机校验已在 validate 阶段完成，
            # create_draft 执行器会再校验一次 ticket，双保险）
            executor = EXECUTORS["create_draft"]
            result = await executor(action.arguments or {}, self.ctx)
            action.status = "confirmed"
            summary = tool_summary("create_draft", result)
        else:
            # 取消 → 以"用户拒绝"回填，让模型向用户致歉并给出替代建议
            result = {"error": "USER_REJECTED",
                      "message": "用户取消创建该报销单。请简短确认取消，不要再次尝试建单。"}
            action.status = "rejected"
            summary = "用户取消建单"
        action.decided_at = datetime.utcnow()
        await self.db.commit()
        await self._log_step("create_draft", action.arguments or {},
                             int((time.monotonic() - t0) * 1000), summary,
                             status="ok" if approved else "blocked")

        # 把工具结果回填进快照里的消息序列，继续循环
        self.messages.append({
            "role": "tool",
            "tool_call_id": (action.snapshot or {}).get("_interrupted_call_id", "call_confirm"),
            "content": json.dumps(result, ensure_ascii=False),
        })
        if "draft_id" in result:
            self.ctx.drafts.append(result["draft_id"])
        async for ev in self._loop():
            yield ev

    async def _loop(self):
        """核心循环：决策 → 执行 → 回填 → 再决策，最多 MAX_ROUNDS 轮"""
        final_text_parts: list = []
        try:
            while self.round < MAX_ROUNDS:
                self.round += 1
                content_buf, tools = await self._decide()

                # 正文增量立即推送（打字机）
                for piece in content_buf:
                    yield "delta", {"content": piece}
                final_text_parts.append("".join(content_buf))

                # 无工具调用 → 模型认为任务完成
                if not tools:
                    break

                # 把带 tool_calls 的 assistant 消息补进序列
                assistant_msg = {
                    "role": "assistant",
                    "content": "".join(content_buf) or None,
                    "tool_calls": [
                        {"id": t.get("id") or f"call_{i}", "type": "function",
                         "function": {"name": t["name"], "arguments": t["arguments"] or "{}"}}
                        for i, t in enumerate(tools)
                    ],
                }
                self.messages.append(assistant_msg)

                interrupted = False
                for i, t in enumerate(tools):
                    name = t["name"]
                    try:
                        args = json.loads(t["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    yield "tool_call", {"name": name, "args": args}
                    result, action = await self._execute_tool(
                        {"function": {"name": name, "arguments": t["arguments"] or "{}"}}
                    )
                    summary = ("已拦截，等待员工确认草稿内容" if action is not None
                               else tool_summary(name, result or {}))
                    yield "tool_result", {"name": name, "summary": summary}

                    if action is not None:
                        # ---- 强制中断：把快照里的 tool_call_id 记下来，resume 用 ----
                        # 注意：JSON 字段原地修改不会触发 SQLAlchemy 变更检测，
                        # 必须重新赋值 + flag_modified
                        from sqlalchemy.orm.attributes import flag_modified
                        action.snapshot = {**(action.snapshot or {}),
                                           "_interrupted_call_id": assistant_msg["tool_calls"][i]["id"]}
                        flag_modified(action, "snapshot")
                        self.db.add(action)
                        await self.db.commit()
                        yield "confirm_request", {
                            "action_id": action.id,
                            "draft": action.arguments,
                        }
                        interrupted = True
                        break  # 流结束，等待员工确认后 resume

                    # 结果回填
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": assistant_msg["tool_calls"][i]["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    self.ctx.tool_trace.append({"tool": name, "args": args, "result": result})

                if interrupted:
                    return

                # 检索/草稿类事件随轮次推送
                if self.ctx.sources:
                    yield "sources", {"sources": self.ctx.sources[:2]}
                for did in dict.fromkeys(self.ctx.drafts):
                    d = (await self.db.execute(
                        select(ExpenseDraft).where(ExpenseDraft.id == did)
                    )).scalar_one_or_none()
                    if d is not None:
                        yield "expense", {
                            "draft_id": d.id, "expense_type": d.expense_type,
                            "total_amount": d.total_amount, "fields": d.fields,
                            "missing_fields": d.missing_fields or [],
                            "status": d.status,
                        }
            else:
                # 达到 5 轮上限仍未完成 → 兜底提示
                tail = f"这个问题步骤较多（已 {MAX_ROUNDS} 轮），先暂停。你可以补充信息后继续。"
                final_text_parts.append(tail)
                yield "delta", {"content": tail}

            # ---- 收尾：统一补发来源与草稿卡片（覆盖"恢复后直接出文字"的路径）----
            if self.ctx.sources:
                yield "sources", {"sources": self.ctx.sources[:2]}
            for did in dict.fromkeys(self.ctx.drafts):
                d = (await self.db.execute(
                    select(ExpenseDraft).where(ExpenseDraft.id == did)
                )).scalar_one_or_none()
                if d is not None:
                    yield "expense", {
                        "draft_id": d.id, "expense_type": d.expense_type,
                        "total_amount": d.total_amount, "fields": d.fields,
                        "missing_fields": d.missing_fields or [],
                        "status": d.status,
                    }

            # 完整回答落库（meta 存工具轨迹与来源）
            full_text = "".join(final_text_parts)
            self.db.add(ChatMessage(
                session_id=self.session_id, role="assistant", content=full_text,
                meta={
                    "agent": True, "rounds": self.round,
                    "tool_trace": self.ctx.tool_trace,
                    "sources": self.ctx.sources[:2],
                    "drafts": list(dict.fromkeys(self.ctx.drafts)),
                },
            ))
            await self.db.commit()
            yield "done", {"message": "处理完成", "rounds": self.round,
                           "tool_trace": self.ctx.tool_trace}

        except Exception as e:
            yield "error", {"code": 500, "message": f"智能体处理异常：{e}"}


# ============================================================
# 兼容旧入口（chat.py / main.py 引用）
# ============================================================


async def run_agent(db: AsyncSession, user: User, session_id: int, history: list, question: str):
    """旧接口兼容：包装 AgentHarness.run"""
    harness = AgentHarness(db, user, session_id)
    async for ev in harness.run(question, history):
        yield ev
