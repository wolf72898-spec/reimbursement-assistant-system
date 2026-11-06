# -*- coding: utf-8 -*-
"""改造后（数智化）流程图：与 03 改造前同构，绿色主题，标题明示【改造后】"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

GREEN_D = "#1E7145"; GREEN_B = "#2E8B57"; MINT = "#E8F3EC"; DARK = "#1F3A2E"

nodes = [
    ("1", "设计变更统一数字入口", "平台唯一权威版本，自动登记与编号", ""),
    ("2", "AI 比对差异与影响识别", "新旧图自动比对，输出工序/工程量/造价影响", "【收益】影响提前暴露"),
    ("3", "交底任务自动生成与推送", "按角色/工序定向推送，App 消息触达", "【收益】交底 100% 触达"),
    ("4", "现场移动端签收确认", "未签收自动升级提醒（保留人工确认）", "【收益】版本正确率保障"),
    ("5", "AI 起草变更签证单", "引用变更与工程量数据，版本唯一、来源可溯", "【收益】返工大幅下降"),
    ("6", "多方在线协同评审", "造价核定、质量安全审查留痕（保留人工审批）", "【收益】签证单版本一致"),
    ("7", "电子确认与自动归档", "电子签章确认，自动关联变更与台账", ""),
    ("8", "数据看板与持续改进", "五项指标实时可测，反馈沉淀进规则库", "【收益】指标基线可测可控"),
]

fig, ax = plt.subplots(figsize=(14.5, 12.5), dpi=110)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
fig.patch.set_facecolor("white")

ax.text(50, 96.5, "【改造后 · 数智化流程】远筑工程 · 工程变更与签证协同 —— 数智化转型后流程图",
        ha="center", va="center", fontsize=20, fontweight="bold", color=GREEN_D)
ax.text(50, 93.2, "“数据驱动 + AI 辅助 + 人工把关”：版本唯一、交底必达、签证同源、留痕可审计（权限边界与人工确认予以保留）",
        ha="center", va="center", fontsize=10.5, color="#666666")

top_y, bot_y = 87.5, 13.0
ys = [top_y - i * (top_y - bot_y) / 7 for i in range(8)]

for i, (num, title, sub, gain) in enumerate(nodes):
    y = ys[i]
    box = FancyBboxPatch((7, y - 3.4), 46, 6.8,
                         boxstyle="round,pad=0.6,rounding_size=1.2",
                         fc=MINT, ec=GREEN_B, lw=1.6)
    ax.add_patch(box)
    c = Circle((11.2, y), 1.55, fc=GREEN_B, ec="none")
    ax.add_patch(c)
    ax.text(11.2, y, num, ha="center", va="center", fontsize=11,
            fontweight="bold", color="white")
    ax.text(14.5, y + 1.35, title, ha="left", va="center",
            fontsize=12.5, fontweight="bold", color=DARK)
    ax.text(14.5, y - 1.6, sub, ha="left", va="center",
            fontsize=9.5, color="#777777")
    if i < 7:
        ax.add_patch(FancyArrowPatch((30, y - 4.2), (30, ys[i + 1] + 4.2),
                                     arrowstyle="-|>", mutation_scale=16,
                                     color=GREEN_B, lw=1.8))
    if gain:
        gb = FancyBboxPatch((57.5, y - 2.3), 21.5, 4.6,
                            boxstyle="round,pad=0.4,rounding_size=1.0",
                            fc="white", ec=GREEN_B, lw=1.2, linestyle=(0, (4, 3)))
        ax.add_patch(gb)
        ax.text(68.2, y, gain, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color=GREEN_D)
        ax.add_patch(FancyArrowPatch((53.8, y), (57.1, y),
                                     arrowstyle="-|>", mutation_scale=12,
                                     color=GREEN_B, lw=1.3, linestyle=(0, (3, 2))))

ax.text(50, 8.2, "目标：变更处理时长 ↓50%+ · 版本错位返工 ↓80%+ · 签证单版本不一致归零 · 复核成本可视可算",
        ha="center", va="center", fontsize=11.5, color=GREEN_D, fontweight="bold")
ax.text(50, 5.4, "（数字化节点依据《需求定义文档》R1-R6 改造方向设计；量化目标与 AC-01～AC-10 验收标准同口径）",
        ha="center", va="center", fontsize=9, color="#999999")

plt.tight_layout()
plt.savefig("docs/construction-change/04-digitized-process-flow.png",
            bbox_inches="tight", facecolor="white", dpi=110)
print("saved 04")
