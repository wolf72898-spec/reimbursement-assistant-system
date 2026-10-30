# -*- coding: utf-8 -*-
"""演示数据播种：一个项目 + 5 个变更单（含多版本、交底、签证），首次启动自动写入。

故事线来自实验室案例「一张变更单的三个版本」：
三层梁柱节点钢筋变更先后出了 3 版图纸，V3 才被现场签收；签证金额与版本严格同源。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change import Briefing, ChangeOrder, ChangeVersion, Project, VisaOrder


async def seed_changes(db: AsyncSession) -> None:
    """幂等：已有项目则跳过"""
    exists = await db.scalar(select(func.count()).select_from(Project))
    if exists:
        return

    now = datetime.now()
    project = Project(
        code="YZ-BJ-01",
        name="远筑 · 滨江商务中心",
        owner="远筑置业",
        contractor="远筑工程",
        manager="顾明岚",
        status="在建",
        baseline={"rework_count": 9, "version_accuracy": 0.72, "review_cost": 18600},
    )
    db.add(project)
    await db.flush()

    def d(days_ago: float) -> datetime:
        return now - timedelta(days=days_ago)

    # ---------- 1. 三层梁柱节点钢筋代换（三版本，待核定） ----------
    c1 = ChangeOrder(
        project_id=project.id, code="CH-2026-0001", title="三层梁柱节点钢筋代换",
        category="设计变更", location="3F 梁柱节点",
        reason="设计院复核后要求 HRB400 替代 HRB335，节点箍筋加密；V2 补强了锚固长度，V3 修正了节点大样。",
        status="待核定", priority="高", initiator="林亦舟", owner_role="唐映秋",
        amount_impact=86400.0, schedule_impact=3, current_version=3,
        created_at=d(6.2), updated_at=d(0.4),
    )
    db.add(c1)
    await db.flush()
    for no, summary, valid, ago in [
        (1, "初版：节点钢筋代换，锚固长度未复核", False, 6.2),
        (2, "补强锚固长度，未同步节点大样", False, 4.0),
        (3, "修正节点大样并补充工程量计算式（现行版本）", True, 1.5),
    ]:
        db.add(
            ChangeVersion(
                change_id=c1.id, version_no=no, summary=summary,
                file_name=f"CH-2026-0001-V{no}.pdf", is_valid=valid,
                uploaded_by="秦芮", created_at=d(ago),
            )
        )
    for role, name, status, ago in [
        ("现场施工员", "林亦舟", "已签收", 1.2),
        ("造价工程师", "唐映秋", "已签收", 1.1),
        ("质量安全", "傅景", "已签收", 1.0),
    ]:
        db.add(
            Briefing(
                change_id=c1.id, version_no=3, role=role, assignee=name, status=status,
                due_at=d(0.5), signed_at=d(ago), note="依据 V3 交底，V1/V2 已作废",
                created_at=d(1.5),
            )
        )
    db.add(
        VisaOrder(
            change_id=c1.id, code="VZ-2026-0001", title="三层梁柱节点钢筋代换 · 签证单",
            amount=86400.0,
            quantity_desc="HRB400 钢筋 12.6t × 5,180 元/t = 65,268 元；箍筋加密人工 218 工日 × 97 元 = 21,132 元",
            status="待核定", source_version=3, created_by="唐映秋", drafted_by_ai=True,
            created_at=d(0.9),
        )
    )

    # ---------- 2. 幕墙预埋件位置调整（交底中，有未签收） ----------
    c2 = ChangeOrder(
        project_id=project.id, code="CH-2026-0002", title="二层幕墙预埋件位置调整",
        category="设计变更", location="2F 东立面",
        reason="幕墙深化设计调整分格，预埋件偏移 120mm，需现场按新图植筋。",
        status="交底中", priority="高", initiator="顾明岚", owner_role="林亦舟",
        amount_impact=42000.0, schedule_impact=2, current_version=2,
        created_at=d(3.6), updated_at=d(0.2),
    )
    db.add(c2)
    await db.flush()
    for no, summary, valid, ago in [
        (1, "初版：预埋件整体外移 120mm", False, 3.6),
        (2, "复核后局部保留原埋件，仅调整 6 处（现行版本）", True, 0.6),
    ]:
        db.add(
            ChangeVersion(
                change_id=c2.id, version_no=no, summary=summary,
                file_name=f"CH-2026-0002-V{no}.pdf", is_valid=valid,
                uploaded_by="秦芮", created_at=d(ago),
            )
        )
    for role, name, status, ago in [
        ("现场施工员", "林亦舟", "已签收", 0.3),
        ("造价工程师", "唐映秋", "待签收", None),
        ("质量安全", "傅景", "待签收", None),
    ]:
        db.add(
            Briefing(
                change_id=c2.id, version_no=2, role=role, assignee=name, status=status,
                due_at=now + timedelta(days=1) if status == "待签收" else d(0.3),
                signed_at=d(ago) if ago else None,
                note="依据 V2 重新交底" if status == "待签收" else "已确认新图",
                created_at=d(0.6),
            )
        )

    # ---------- 3. 地下室防水材料代用（已确认） ----------
    c3 = ChangeOrder(
        project_id=project.id, code="CH-2026-0003", title="地下室底板防水材料代用",
        category="材料代用", location="B1 底板",
        reason="原设计 SBS 卷材供货周期不足，等价代用高分子自粘卷材，需业主确认。",
        status="已确认", priority="中", initiator="唐映秋", owner_role="顾明岚",
        amount_impact=28600.0, schedule_impact=-1, current_version=1,
        created_at=d(9.0), updated_at=d(2.4),
    )
    db.add(c3)
    await db.flush()
    db.add(
        ChangeVersion(
            change_id=c3.id, version_no=1, summary="高分子自粘卷材代用 SBS，做法不变",
            file_name="CH-2026-0003-V1.pdf", is_valid=True, uploaded_by="秦芮",
            created_at=d(9.0),
        )
    )
    for role, name in [("现场施工员", "林亦舟"), ("造价工程师", "唐映秋"), ("质量安全", "傅景")]:
        db.add(
            Briefing(
                change_id=c3.id, version_no=1, role=role, assignee=name, status="已签收",
                due_at=d(8.5), signed_at=d(8.4), note="材料样板已现场确认", created_at=d(9.0),
            )
        )
    db.add(
        VisaOrder(
            change_id=c3.id, code="VZ-2026-0002", title="地下室底板防水材料代用 · 签证单",
            amount=28600.0,
            quantity_desc="高分子自粘卷材 1,650 ㎡ × 42 元/㎡ = 69,300 元，冲减原 SBS 卷材 40,700 元",
            status="已确认", source_version=1, created_by="唐映秋", reviewer="叶书",
            created_at=d(8.0), confirmed_at=d(2.4),
        )
    )

    # ---------- 4. 临时道路硬化现场签证（待签证） ----------
    c4 = ChangeOrder(
        project_id=project.id, code="CH-2026-0004", title="场地东侧临时道路硬化",
        category="现场签证", location="场地东侧",
        reason="雨季车辆陷车，按业主要求增设 120m 临时道路硬化，费用待签证。",
        status="待签证", priority="中", initiator="林亦舟", owner_role="唐映秋",
        amount_impact=15800.0, schedule_impact=0, current_version=1,
        created_at=d(2.8), updated_at=d(1.0),
    )
    db.add(c4)
    await db.flush()
    db.add(
        ChangeVersion(
            change_id=c4.id, version_no=1, summary="临时道路 120m×3.5m，C25 混凝土 150mm 厚",
            file_name="CH-2026-0004-V1.pdf", is_valid=True, uploaded_by="秦芮",
            created_at=d(2.8),
        )
    )
    for role, name in [("现场施工员", "林亦舟"), ("造价工程师", "唐映秋"), ("质量安全", "傅景")]:
        db.add(
            Briefing(
                change_id=c4.id, version_no=1, role=role, assignee=name, status="已签收",
                due_at=d(2.3), signed_at=d(2.2), note="现场交底并拍照留证", created_at=d(2.8),
            )
        )

    # ---------- 5. 钢结构防火涂料厚度调整（已驳回） ----------
    c5 = ChangeOrder(
        project_id=project.id, code="CH-2026-0005", title="钢结构防火涂料厚度调整",
        category="设计变更", location="屋面钢结构",
        reason="消防审查要求耐火极限提升至 2.0h，涂料厚度由 3mm 调整至 4.5mm。",
        status="已驳回", priority="低", initiator="傅景", owner_role="唐映秋",
        amount_impact=52000.0, schedule_impact=1, current_version=2,
        created_at=d(5.4), updated_at=d(1.8),
    )
    db.add(c5)
    await db.flush()
    for no, summary, valid, ago in [
        (1, "初版：涂层加厚至 4.5mm，未附检测报告", False, 5.4),
        (2, "补充检测报告，工程量未重新核价（现行版本）", True, 3.0),
    ]:
        db.add(
            ChangeVersion(
                change_id=c5.id, version_no=no, summary=summary,
                file_name=f"CH-2026-0005-V{no}.pdf", is_valid=valid,
                uploaded_by="秦芮", created_at=d(ago),
            )
        )
    for role, name in [("现场施工员", "林亦舟"), ("造价工程师", "唐映秋"), ("质量安全", "傅景")]:
        db.add(
            Briefing(
                change_id=c5.id, version_no=2, role=role, assignee=name, status="已签收",
                due_at=d(2.8), signed_at=d(2.7), note="已交底", created_at=d(3.0),
            )
        )
    db.add(
        VisaOrder(
            change_id=c5.id, code="VZ-2026-0003", title="钢结构防火涂料厚度调整 · 签证单",
            amount=52000.0,
            quantity_desc="涂料增厚 1.5mm，面积 3,200 ㎡，单价 16.25 元/㎡",
            status="已驳回", source_version=2, created_by="唐映秋", reviewer="叶书",
            created_at=d(2.6),
        )
    )

    await db.commit()
    print("[seed] 工程变更演示数据已写入：1 个项目 / 5 个变更 / 12 个版本 / 15 条交底 / 3 张签证")
