# -*- coding: utf-8 -*-
"""
Agent 工具注册表（提示词6）：
- TOOL_SCHEMAS：7 个工具的 Function Calling 规范（OpenAI tools 格式）
- AgentContext：一次 Agent 运行的上下文（db 会话 / 用户 / 检索结果收集）
- TICKETS：校验凭证状态机——create_draft 必须携带 validate_expense 签发的有效 ticket

硬约束（服务端强制，模型无法绕过）：
1. create_draft 必须携带有效 ticket（存在/未过期/金额一致）；
2. 金额变更即 ticket 失效，必须重新校验；
3. update_draft 修改金额同样需要新 ticket；
4. submit_draft 要求 missing_fields 为空且状态为 draft。
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import ExpenseDraft
from app.models.user import User
from app.rag.retriever import hybrid_search

# ============================================================
# 工具 schema（Function Calling 规范）
# ============================================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "检索报销制度条文（RAG）。回答任何制度问题前必须先调用本工具，回答只能依据返回的条文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要检索的制度问题，如“北京住宿标准”"}
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense_standard",
            "description": "查询某类费用的报销标准额度（如住宿/交通/餐饮的金额上限）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expense_type": {"type": "string", "description": "费用类型：住宿/交通/餐饮/办公"},
                    "city": {"type": "string", "description": "城市（可选）"},
                    "level": {"type": "string", "description": "职级（可选）：普通员工/经理/总监"},
                },
                "required": ["expense_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_expense",
            "description": "报销要素校验：金额是否超标准、是否超30天时效、是否疑似违规。通过后签发 ticket（10分钟有效），建单必须凭 ticket。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expense_type": {"type": "string", "description": "费用类型：餐饮/交通/差旅/办公"},
                    "amount": {"type": "number", "description": "报销总金额（元）"},
                    "expense_date": {"type": "string", "description": "费用发生日期，格式 YYYY-MM-DD"},
                    "details": {"type": "string", "description": "费用明细说明（可选）"},
                    "city": {"type": "string", "description": "城市（可选）"},
                    "level": {"type": "string", "description": "职级（可选）"},
                },
                "required": ["expense_type", "amount", "expense_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft",
            "description": "创建报销草稿。必须传入 validate_expense 通过后返回的 ticket_id；金额必须与校验时一致，否则会被拒绝。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "validate_expense 返回的凭证ID"},
                    "expense_type": {"type": "string"},
                    "amount": {"type": "number"},
                    "expense_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "details": {"type": "string", "description": "费用明细"},
                },
                "required": ["ticket_id", "expense_type", "amount", "expense_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_draft",
            "description": "补充或修改草稿字段。注意：修改金额必须传入对应新金额的有效 ticket_id，否则仅允许修改明细描述类字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "integer"},
                    "fields": {
                        "type": "object",
                        "description": "要更新的字段，如 {\"expense_date\":\"2026-10-29\",\"details\":\"...\"}",
                    },
                    "ticket_id": {"type": "string", "description": "修改金额时必填"},
                },
                "required": ["draft_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_drafts",
            "description": "查询当前用户自己的报销单草稿列表。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_draft",
            "description": "提交报销单进入审批。要求草稿信息完整（missing_fields 为空）且状态为 draft。",
            "parameters": {
                "type": "object",
                "properties": {"draft_id": {"type": "integer"}},
                "required": ["draft_id"],
            },
        },
    },
]

# 建单类工具（受状态机约束的集合）
GUARDED_TOOLS = {"create_draft", "update_draft", "submit_draft"}

# ============================================================
# 校验凭证（ticket）状态机
# ============================================================

TICKET_TTL_SECONDS = 600  # ticket 有效期 10 分钟
TICKETS: dict = {}  # ticket_id -> {user_id, expense_type, amount, digest, expires_at}


def _amount_digest(amount: float) -> str:
    """金额摘要：绑定校验内容，防止校验后偷改金额"""
    return hashlib.sha256(f"{round(float(amount), 2):.2f}".encode()).hexdigest()[:16]


def _check_ticket(ticket_id: str, user_id: int, amount: float | None = None) -> str | None:
    """
    校验 ticket。返回 None 表示通过，否则返回中文拒绝原因。
    amount 不为 None 时额外校验金额一致（金额变更即失效）。
    """
    t = TICKETS.get(ticket_id)
    if t is None:
        return "未找到有效校验凭证：请先调用 validate_expense 完成校验（create_draft 前必须先校验）"
    if t["user_id"] != user_id:
        return "校验凭证不属于当前用户，请用本人账号重新校验"
    if time.time() > t["expires_at"]:
        TICKETS.pop(ticket_id, None)
        return "校验凭证已过期（10分钟有效），请重新调用 validate_expense"
    if amount is not None and _amount_digest(amount) != t["digest"]:
        return "金额与校验时不一致：旧凭证已失效，请用正确金额重新调用 validate_expense"
    return None


# ============================================================
# 疑似违规关键词（对话审计与校验共用，可解释的规则）
# ============================================================

RISK_KEYWORDS = [
    "拆成两张", "分开发票", "拆开发票", "拆单", "没有发票", "不要发票",
    "找票", "替票", "虚开", "多开点", "多开一些", "先斩后奏", "不报销就没法",
]


def _risk_hits(text: str) -> list:
    return [kw for kw in RISK_KEYWORDS if kw in (text or "")]


# ============================================================
# Agent 运行上下文
# ============================================================


@dataclass
class AgentContext:
    """一次 Agent 会话运行的上下文：工具执行器通过它访问 db / 用户 / 收集结果"""

    db: AsyncSession
    user: User
    session_id: int
    # 本次运行收集的引用来源（SSE sources 事件 + 消息 meta 用）
    sources: list = field(default_factory=list)
    # 本次运行创建/操作的草稿 id（前端报销卡片用）
    drafts: list = field(default_factory=list)
    tool_trace: list = field(default_factory=list)  # 工具调用轨迹（落库审计）


# ============================================================
# 工具执行器（每个返回 dict，错误用中文 message，模型可自愈）
# ============================================================


async def _exec_search_policy(args: dict, ctx: AgentContext) -> dict:
    question = args.get("question", "")
    contexts = await hybrid_search(ctx.db, question, 3)
    if not contexts:
        return {"found": False, "message": "知识库中未检索到相关制度条文"}
    ctx.sources = contexts  # 记录来源，最终随 sources 事件推送
    return {
        "found": True,
        "snippets": [
            f"【{c['doc_title']}】{c['content'][:300]}" for c in contexts
        ],
    }


async def _exec_get_expense_standard(args: dict, ctx: AgentContext) -> dict:
    etype = args.get("expense_type", "")
    city = args.get("city") or ""
    level = args.get("level") or ""
    contexts = await hybrid_search(ctx.db, f"{etype} 标准 {city} {level}", 2)
    if not contexts:
        return {"found": False, "message": "制度中未找到该类费用的标准"}
    # 从条文里提取“X元”形式的额度数字，给出可解释的上限
    import re
    limits = []
    for c in contexts:
        limits += [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*元", c["content"])]
    limits = sorted(set(limits))[:6]
    return {
        "found": True,
        "standard_text": [f"【{c['doc_title']}】{c['content'][:200]}" for c in contexts],
        "amount_limits_found": limits,
    }


async def _exec_validate_expense(args: dict, ctx: AgentContext) -> dict:
    etype = args.get("expense_type", "未分类")
    try:
        amount = round(float(args.get("amount", 0)), 2)
    except (TypeError, ValueError):
        return {"status": "failed", "violations": ["金额格式无法解析，请确认后重试"]}
    raw_date = args.get("expense_date", "")

    violations = []
    # 1) 金额合法性
    if amount <= 0:
        violations.append("金额必须大于 0")

    # 2) 时效校验：费用发生日期距今天不超过 30 天
    try:
        d = datetime.strptime(raw_date, "%Y-%m-%d").date()
        days = (date.today() - d).days
        if days < 0:
            violations.append(f"费用发生日期 {raw_date} 在未来，日期有误")
        elif days > 30:
            violations.append(f"费用发生日期 {raw_date} 距今 {days} 天，超过 30 天报销时效")
    except ValueError:
        violations.append(f"日期 {raw_date or '（缺失）'} 无法解析，格式应为 YYYY-MM-DD")

    # 3) 疑似违规表述
    detail_text = f"{args.get('details', '')}"
    hits = _risk_hits(detail_text)
    if hits:
        violations.append(f"明细中包含疑似违规表述：{'、'.join(hits)}")

    # 4) 对照制度标准：检索条文提取额度上限，超限即拒
    std = await _exec_get_expense_standard(
        {"expense_type": etype, "city": args.get("city"), "level": args.get("level")}, ctx
    )
    limit_note = ""
    if std.get("found") and std.get("amount_limits_found"):
        cap = max(std["amount_limits_found"])
        limit_note = f"制度上限参考：{cap} 元"
        if amount > cap:
            violations.append(
                f"金额 {amount} 元超过制度标准上限 {cap} 元（依据：{std['standard_text'][0][:60]}…）"
            )

    if violations:
        return {"status": "failed", "violations": violations, "ticket": None}

    # 通过 → 签发 ticket（绑定用户/金额摘要/10分钟有效）
    ticket_id = uuid.uuid4().hex[:12]
    TICKETS[ticket_id] = {
        "user_id": ctx.user.id,
        "expense_type": etype,
        "amount": amount,
        "digest": _amount_digest(amount),
        "expires_at": time.time() + TICKET_TTL_SECONDS,
    }
    return {
        "status": "passed",
        "violations": [],
        "ticket": {
            "ticket_id": ticket_id,
            "expires_in_minutes": TICKET_TTL_SECONDS // 60,
            "note": f"校验通过{('，' + limit_note) if limit_note else ''}。请在 10 分钟内调用 create_draft 建单。",
        },
    }


async def _exec_create_draft(args: dict, ctx: AgentContext) -> dict:
    ticket_id = args.get("ticket_id", "")
    try:
        amount = round(float(args.get("amount", 0)), 2)
    except (TypeError, ValueError):
        return {"error": "AMOUNT_INVALID", "message": "金额格式无法解析，无法建单"}

    # ---- 状态机硬校验：无有效 ticket 一律拒绝 ----
    reason = _check_ticket(ticket_id, ctx.user.id, amount)
    if reason:
        return {"error": "VALIDATION_REQUIRED", "message": reason}

    fields = {
        "expense_date": args.get("expense_date", ""),
        "details": args.get("details", ""),
        "city": args.get("city", ""),
    }
    missing = [k for k in ("expense_date", "details") if not fields.get(k)]
    draft = ExpenseDraft(
        user_id=ctx.user.id, session_id=ctx.session_id,
        expense_type=args.get("expense_type", "未分类"),
        total_amount=amount, fields=fields, missing_fields=missing,
    )
    ctx.db.add(draft)
    await ctx.db.commit()
    await ctx.db.refresh(draft)
    ctx.drafts.append(draft.id)
    return {
        "draft_id": draft.id, "expense_type": draft.expense_type,
        "total_amount": draft.total_amount, "missing_fields": missing,
        "message": "草稿已创建" + (f"，还需补充：{'、'.join(missing)}" if missing else "，信息完整"),
    }


async def _exec_update_draft(args: dict, ctx: AgentContext) -> dict:
    draft = await ctx.db.get(ExpenseDraft, int(args.get("draft_id", 0)))
    if draft is None or draft.user_id != ctx.user.id:
        return {"error": "NOT_FOUND", "message": "报销单不存在或无权操作"}
    if draft.status != "draft":
        return {"error": "STATUS_INVALID", "message": "该报销单已提交，不能再修改"}

    fields = args.get("fields") or {}
    new_amount = fields.get("amount")
    if new_amount is not None:
        # ---- 状态机硬校验：改金额必须有匹配新金额的 ticket ----
        try:
            new_amount = round(float(new_amount), 2)
        except (TypeError, ValueError):
            return {"error": "AMOUNT_INVALID", "message": "金额格式无法解析"}
        reason = _check_ticket(args.get("ticket_id", ""), ctx.user.id, new_amount)
        if reason:
            return {"error": "VALIDATION_REQUIRED", "message": f"修改金额被拒绝：{reason}"}
        draft.total_amount = new_amount

    draft.fields = {**(draft.fields or {}), **{
        k: v for k, v in fields.items() if k != "amount"
    }}
    draft.missing_fields = [
        k for k in ("expense_date", "details") if not (draft.fields or {}).get(k)
    ]
    await ctx.db.commit()
    await ctx.db.refresh(draft)
    ctx.drafts.append(draft.id)
    return {
        "draft_id": draft.id, "total_amount": draft.total_amount,
        "missing_fields": draft.missing_fields,
        "message": "草稿已更新" + (f"，还需补充：{'、'.join(draft.missing_fields)}" if draft.missing_fields else "，信息完整"),
    }


async def _exec_get_my_drafts(args: dict, ctx: AgentContext) -> dict:
    rows = await ctx.db.execute(
        select(ExpenseDraft)
        .where(ExpenseDraft.user_id == ctx.user.id)
        .order_by(ExpenseDraft.id.desc())
        .limit(10)
    )
    return {"drafts": [
        {
            "draft_id": d.id, "status": d.status, "expense_type": d.expense_type,
            "total_amount": d.total_amount, "missing_fields": d.missing_fields or [],
        }
        for d in rows.scalars().all()
    ]}


async def _exec_submit_draft(args: dict, ctx: AgentContext) -> dict:
    draft = await ctx.db.get(ExpenseDraft, int(args.get("draft_id", 0)))
    if draft is None or draft.user_id != ctx.user.id:
        return {"error": "NOT_FOUND", "message": "报销单不存在或无权操作"}
    if draft.status != "draft":
        return {"error": "STATUS_INVALID", "message": "该报销单已提交过，请勿重复提交"}
    if draft.missing_fields:
        return {
            "error": "FIELDS_MISSING",
            "message": f"信息不完整，无法提交。还需补充：{'、'.join(draft.missing_fields)}。请先调用 update_draft 补齐。",
        }
    draft.status = "submitted"
    await ctx.db.commit()
    ctx.drafts.append(draft.id)
    return {"draft_id": draft.id, "status": "submitted", "message": "报销单已提交，等待审批"}


EXECUTORS = {
    "search_policy": _exec_search_policy,
    "get_expense_standard": _exec_get_expense_standard,
    "validate_expense": _exec_validate_expense,
    "create_draft": _exec_create_draft,
    "update_draft": _exec_update_draft,
    "get_my_drafts": _exec_get_my_drafts,
    "submit_draft": _exec_submit_draft,
}


def tool_summary(name: str, result: dict) -> str:
    """工具执行结果的一行摘要（SSE 过程展示 + 审计轨迹用）"""
    if name == "search_policy":
        return "检索到制度条文" if result.get("found") else "未检索到相关条文"
    if name == "get_expense_standard":
        return "已查到费用标准" if result.get("found") else "未查到标准"
    if name == "validate_expense":
        if result.get("status") == "passed":
            return "校验通过，已签发凭证"
        return "校验未通过：" + "；".join(result.get("violations", []))
    if name == "create_draft":
        return f"已创建报销单 #{result['draft_id']}" if "draft_id" in result else result.get("message", "建单被拒绝")
    if name == "update_draft":
        return "草稿已更新" if "draft_id" in result else result.get("message", "更新被拒绝")
    if name == "get_my_drafts":
        return f"共 {len(result.get('drafts', []))} 条草稿"
    if name == "submit_draft":
        return result.get("message", "提交结果未知")
    return json.dumps(result, ensure_ascii=False)[:80]
