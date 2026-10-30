# -*- coding: utf-8 -*-
"""工程变更与签证协同业务接口

路由分组：
- /api/projects      项目
- /api/changes       变更台账（登记 / 版本 / 状态流转 / 详情）
- /api/briefings     交底任务（签收）
- /api/visas         签证单（起草 / 造价核定 / 业主确认）
- /api/dashboard     数据看板指标

状态机（服务端强制，与设计方案一致）：
待交底 → 交底中 → 待签证 → 待核定 → 待业主确认 → 已确认 → 已归档
任一状态 → 已作废；签证确认后才允许归档。
"""
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.change import Briefing, ChangeOrder, ChangeVersion, Project, VisaOrder
from app.models.user import User

router = APIRouter(prefix="/api", tags=["construction"])

# 合法状态流转表（from → 允许的 to）
TRANSITIONS = {
    "待交底": {"交底中", "已作废"},
    "交底中": {"待签证", "已作废"},
    "待签证": {"待核定", "已作废"},
    "待核定": {"待业主确认", "已作废"},
    "待业主确认": {"已确认", "已驳回", "已作废"},
    "已确认": {"已归档"},
    "已驳回": {"待核定", "已作废"},
    "已归档": set(),
    "已作废": set(),
}


# ============================================================
# 请求体
# ============================================================
class ChangeIn(BaseModel):
    project_id: int
    title: str = Field(min_length=2, max_length=200)
    category: str = "设计变更"
    reason: str = ""
    location: str = ""
    priority: str = "中"
    amount_impact: float = 0.0
    schedule_impact: int = 0
    owner_role: str = ""


class VersionIn(BaseModel):
    summary: str = Field(min_length=2)
    file_name: str = ""
    briefing_roles: list[str] = ["现场施工员", "造价工程师", "质量安全"]


class SignIn(BaseModel):
    note: str = "已阅读并理解本版变更内容"


class VisaIn(BaseModel):
    change_id: int
    amount: float = 0.0
    quantity_desc: str = ""
    title: str = ""


class ReviewIn(BaseModel):
    action: str  # 核价 / 确认 / 驳回
    note: str = ""


# ============================================================
# 工具函数
# ============================================================
async def _next_code(db: AsyncSession, prefix: str, model) -> str:
    """生成业务编号：CH-2026-0001 / VZ-2026-0001"""
    year = datetime.now().year
    count = await db.scalar(select(func.count()).select_from(model))
    return f"{prefix}-{year}-{(count or 0) + 1:04d}"


def _change_dict(c: ChangeOrder, project_name: str = "") -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "title": c.title,
        "project_id": c.project_id,
        "project_name": project_name,
        "category": c.category,
        "reason": c.reason,
        "location": c.location,
        "status": c.status,
        "priority": c.priority,
        "initiator": c.initiator,
        "owner_role": c.owner_role,
        "amount_impact": c.amount_impact,
        "schedule_impact": c.schedule_impact,
        "current_version": c.current_version,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ============================================================
# 项目
# ============================================================
@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.scalars(select(Project).order_by(Project.id))).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "owner": p.owner,
            "contractor": p.contractor,
            "manager": p.manager,
            "status": p.status,
            "baseline": p.baseline or {},
        }
        for p in rows
    ]


# ============================================================
# 变更台账
# ============================================================
@router.get("/changes")
async def list_changes(
    status: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    project_id: Optional[int] = None,
    limit: int = Query(200, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ChangeOrder, Project.name).join(Project, Project.id == ChangeOrder.project_id)
    if status and status != "全部":
        stmt = stmt.where(ChangeOrder.status == status)
    if category and category != "全部":
        stmt = stmt.where(ChangeOrder.category == category)
    if project_id:
        stmt = stmt.where(ChangeOrder.project_id == project_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (ChangeOrder.title.like(like))
            | (ChangeOrder.code.like(like))
            | (ChangeOrder.location.like(like))
        )
    stmt = stmt.order_by(desc(ChangeOrder.updated_at)).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [_change_dict(c, pname) for c, pname in rows]


@router.post("/changes", status_code=201)
async def create_change(
    body: ChangeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """登记变更：编号唯一 → 建首版版本 → 自动生成交底任务 → 状态进入交底中"""
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    code = await _next_code(db, "CH", ChangeOrder)
    change = ChangeOrder(
        project_id=body.project_id,
        code=code,
        title=body.title,
        category=body.category,
        reason=body.reason,
        location=body.location,
        priority=body.priority,
        amount_impact=body.amount_impact,
        schedule_impact=body.schedule_impact,
        initiator=user.username,
        owner_role=body.owner_role or project.manager,
        status="交底中",
        current_version=1,
    )
    db.add(change)
    await db.flush()

    db.add(
        ChangeVersion(
            change_id=change.id,
            version_no=1,
            summary=body.reason or "首次发布版本",
            file_name=f"{code}-V1.pdf",
            is_valid=True,
            uploaded_by=user.username,
        )
    )
    for role in ("现场施工员", "造价工程师", "质量安全"):
        db.add(
            Briefing(
                change_id=change.id,
                version_no=1,
                role=role,
                assignee="待指派",
                status="待签收",
                due_at=datetime.now() + timedelta(days=2),
            )
        )
    await db.commit()
    await db.refresh(change)
    return _change_dict(change, project.name)


@router.get("/changes/{change_id}")
async def get_change(
    change_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    change = await db.get(ChangeOrder, change_id)
    if change is None:
        raise HTTPException(404, "变更单不存在")
    project = await db.get(Project, change.project_id)
    versions = (
        await db.scalars(
            select(ChangeVersion)
            .where(ChangeVersion.change_id == change_id)
            .order_by(desc(ChangeVersion.version_no))
        )
    ).all()
    briefings = (
        await db.scalars(
            select(Briefing).where(Briefing.change_id == change_id).order_by(Briefing.id)
        )
    ).all()
    visas = (
        await db.scalars(
            select(VisaOrder).where(VisaOrder.change_id == change_id).order_by(desc(VisaOrder.id))
        )
    ).all()
    data = _change_dict(change, project.name if project else "")
    data["versions"] = [
        {
            "id": v.id,
            "version_no": v.version_no,
            "summary": v.summary,
            "file_name": v.file_name,
            "is_valid": v.is_valid,
            "uploaded_by": v.uploaded_by,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]
    data["briefings"] = [_briefing_dict(b) for b in briefings]
    data["visas"] = [_visa_dict(v) for v in visas]
    return data


@router.post("/changes/{change_id}/versions", status_code=201)
async def upload_version(
    change_id: int,
    body: VersionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传新版本：旧版自动作废（版本唯一），并重新生成交底任务"""
    change = await db.get(ChangeOrder, change_id)
    if change is None:
        raise HTTPException(404, "变更单不存在")
    if change.status in ("已归档", "已作废"):
        raise HTTPException(400, "已归档或作废的变更不允许上传新版本")

    old = (
        await db.scalars(
            select(ChangeVersion).where(
                ChangeVersion.change_id == change_id, ChangeVersion.is_valid.is_(True)
            )
        )
    ).all()
    for v in old:
        v.is_valid = False

    new_no = (change.current_version or 1) + 1
    code = change.code
    db.add(
        ChangeVersion(
            change_id=change_id,
            version_no=new_no,
            summary=body.summary,
            file_name=body.file_name or f"{code}-V{new_no}.pdf",
            is_valid=True,
            uploaded_by=user.username,
        )
    )
    change.current_version = new_no
    change.status = "交底中"
    # 旧版本的交底任务作废（标记备注），按新版本重建
    for b in (
        await db.scalars(select(Briefing).where(Briefing.change_id == change_id))
    ).all():
        b.status = "已失效"
    for role in body.briefing_roles:
        db.add(
            Briefing(
                change_id=change_id,
                version_no=new_no,
                role=role,
                assignee="待指派",
                status="待签收",
                due_at=datetime.now() + timedelta(days=2),
                note=f"依据 V{new_no} 重新交底，此前版本已作废",
            )
        )
    await db.commit()
    return {"ok": True, "version_no": new_no}


@router.post("/changes/{change_id}/archive")
async def archive_change(
    change_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    change = await db.get(ChangeOrder, change_id)
    if change is None:
        raise HTTPException(404, "变更单不存在")
    if change.status != "已确认":
        raise HTTPException(400, "签证未确认的变更不允许归档")
    change.status = "已归档"
    await db.commit()
    return {"ok": True, "status": change.status}


# ============================================================
# 交底
# ============================================================
def _briefing_dict(b: Briefing) -> dict[str, Any]:
    return {
        "id": b.id,
        "change_id": b.change_id,
        "version_no": b.version_no,
        "role": b.role,
        "assignee": b.assignee,
        "status": b.status,
        "due_at": b.due_at.isoformat() if b.due_at else None,
        "signed_at": b.signed_at.isoformat() if b.signed_at else None,
        "note": b.note,
    }


@router.get("/briefings")
async def list_briefings(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Briefing, ChangeOrder, Project.name).join(
        ChangeOrder, ChangeOrder.id == Briefing.change_id
    ).join(Project, Project.id == ChangeOrder.project_id)
    if status and status != "全部":
        stmt = stmt.where(Briefing.status == status)
    stmt = stmt.order_by(Briefing.id.desc()).limit(200)
    rows = (await db.execute(stmt)).all()
    out = []
    for b, c, pname in rows:
        d = _briefing_dict(b)
        d.update(
            {
                "change_code": c.code,
                "change_title": c.title,
                "project_name": pname,
                "priority": c.priority,
                "current_version": c.current_version,
            }
        )
        out.append(d)
    return out


@router.post("/briefings/{briefing_id}/sign")
async def sign_briefing(
    briefing_id: int,
    body: SignIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """现场签收交底：留痕签收人与时间；全部签收后变更自动进入待签证"""
    b = await db.get(Briefing, briefing_id)
    if b is None:
        raise HTTPException(404, "交底任务不存在")
    if b.status == "已签收":
        raise HTTPException(400, "该交底已签收，无需重复操作")
    b.status = "已签收"
    b.signed_at = datetime.now()
    b.assignee = user.username
    b.note = body.note

    change = await db.get(ChangeOrder, b.change_id)
    pending = await db.scalar(
        select(func.count())
        .select_from(Briefing)
        .where(
            Briefing.change_id == b.change_id,
            Briefing.version_no == change.current_version,
            Briefing.status == "待签收",
            Briefing.id != b.id,
        )
    )
    if change and change.status == "交底中" and not pending:
        change.status = "待签证"
    await db.commit()
    return {"ok": True, "change_status": change.status if change else None}


# ============================================================
# 签证
# ============================================================
def _visa_dict(v: VisaOrder) -> dict[str, Any]:
    return {
        "id": v.id,
        "change_id": v.change_id,
        "code": v.code,
        "title": v.title,
        "amount": v.amount,
        "quantity_desc": v.quantity_desc,
        "status": v.status,
        "source_version": v.source_version,
        "created_by": v.created_by,
        "reviewer": v.reviewer,
        "drafted_by_ai": v.drafted_by_ai,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "confirmed_at": v.confirmed_at.isoformat() if v.confirmed_at else None,
    }


@router.get("/visas")
async def list_visas(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(VisaOrder, ChangeOrder.code, ChangeOrder.title, ChangeOrder.location).join(
        ChangeOrder, ChangeOrder.id == VisaOrder.change_id
    )
    if status and status != "全部":
        stmt = stmt.where(VisaOrder.status == status)
    stmt = stmt.order_by(desc(VisaOrder.id)).limit(200)
    rows = (await db.execute(stmt)).all()
    out = []
    for v, ccode, ctitle, loc in rows:
        d = _visa_dict(v)
        d.update({"change_code": ccode, "change_title": ctitle, "location": loc})
        out.append(d)
    return out


@router.post("/visas", status_code=201)
async def create_visa(
    body: VisaIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """起草签证单：来源版本取变更当前有效版本（同源），状态待核定"""
    change = await db.get(ChangeOrder, body.change_id)
    if change is None:
        raise HTTPException(404, "变更单不存在")
    if change.status not in ("待签证", "待核定", "待业主确认", "已驳回"):
        raise HTTPException(400, f"当前变更状态为「{change.status}」，尚不能起草签证（需完成交底）")
    code = await _next_code(db, "VZ", VisaOrder)
    visa = VisaOrder(
        change_id=change.id,
        code=code,
        title=body.title or f"{change.title} · 签证单",
        amount=body.amount,
        quantity_desc=body.quantity_desc,
        status="待核定",
        source_version=change.current_version,
        created_by=user.username,
    )
    db.add(visa)
    change.status = "待核定"
    await db.commit()
    await db.refresh(visa)
    return _visa_dict(visa)


@router.post("/visas/{visa_id}/review")
async def review_visa(
    visa_id: int,
    body: ReviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """签证评审：造价核价 → 业主确认 → 驳回"""
    v = await db.get(VisaOrder, visa_id)
    if v is None:
        raise HTTPException(404, "签证单不存在")
    change = await db.get(ChangeOrder, v.change_id)
    now = datetime.now()

    if body.action == "核价":
        if v.status != "待核定":
            raise HTTPException(400, f"当前状态「{v.status}」不允许核价")
        v.status = "待业主确认"
        v.reviewer = user.username
        if change:
            change.status = "待业主确认"
    elif body.action == "确认":
        if v.status != "待业主确认":
            raise HTTPException(400, f"当前状态「{v.status}」不允许确认")
        v.status = "已确认"
        v.confirmed_at = now
        v.reviewer = user.username
        if change:
            change.status = "已确认"
    elif body.action == "驳回":
        v.status = "已驳回"
        v.reviewer = user.username
        if change:
            change.status = "已驳回"
    else:
        raise HTTPException(400, "未知操作，仅支持 核价 / 确认 / 驳回")

    if body.note:
        v.quantity_desc = (v.quantity_desc or "") + f"\n[评审意见] {body.note}"
    await db.commit()
    return {"ok": True, "status": v.status, "change_status": change.status if change else None}


# ============================================================
# 数据看板
# ============================================================
@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """五项基线指标 + 分布统计"""
    project = await db.scalar(select(Project).order_by(Project.id))
    baseline = (project.baseline or {}) if project else {}

    total = await db.scalar(select(func.count()).select_from(ChangeOrder)) or 0
    by_status_rows = (
        await db.execute(select(ChangeOrder.status, func.count()).group_by(ChangeOrder.status))
    ).all()
    by_status = {s: n for s, n in by_status_rows}
    by_cat_rows = (
        await db.execute(select(ChangeOrder.category, func.count()).group_by(ChangeOrder.category))
    ).all()
    by_category = {c: n for c, n in by_cat_rows}

    pending_briefings = await db.scalar(
        select(func.count()).select_from(Briefing).where(Briefing.status == "待签收")
    ) or 0
    signed_briefings = await db.scalar(
        select(func.count()).select_from(Briefing).where(Briefing.status == "已签收")
    ) or 0
    total_briefings = await db.scalar(select(func.count()).select_from(Briefing)) or 0

    visa_total = await db.scalar(select(func.coalesce(func.sum(VisaOrder.amount), 0.0))) or 0.0
    visa_confirmed = await db.scalar(
        select(func.count()).select_from(VisaOrder).where(VisaOrder.status == "已确认")
    ) or 0
    visa_all = await db.scalar(select(func.count()).select_from(VisaOrder)) or 0

    # 处理时长：已确认/已归档变更从登记到当前（开发期用 updated_at 近似）
    cycle_rows = (
        await db.execute(
            select(ChangeOrder.created_at, ChangeOrder.updated_at).where(
                ChangeOrder.status.in_(["已确认", "已归档"])
            )
        )
    ).all()
    cycle_days = [
        round((u - c).total_seconds() / 86400, 1) for c, u in cycle_rows if c and u
    ]
    avg_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else 0.0

    # 近 7 天新增变更（趋势）
    today = datetime.now().date()
    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        n = await db.scalar(
            select(func.count())
            .select_from(ChangeOrder)
            .where(func.date(ChangeOrder.created_at) == day.isoformat())
        ) or 0
        trend.append({"date": day.strftime("%m-%d"), "count": n})

    return {
        "project": {
            "name": project.name if project else "",
            "code": project.code if project else "",
            "manager": project.manager if project else "",
        },
        "metrics": {
            "total_changes": total,
            "pending_briefings": pending_briefings,
            "briefing_rate": round(signed_briefings / total_briefings, 3) if total_briefings else 0,
            "avg_cycle_days": avg_cycle,
            "visa_total": visa_total,
            "visa_adoption": round(visa_confirmed / visa_all, 3) if visa_all else 0,
            # 基线类指标（需项目样本采集，当前为基线参考值）
            "rework_count": baseline.get("rework_count", 0),
            "version_accuracy": baseline.get("version_accuracy", 0),
            "review_cost": baseline.get("review_cost", 0),
        },
        "by_status": by_status,
        "by_category": by_category,
        "trend": trend,
    }
