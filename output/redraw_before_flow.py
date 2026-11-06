# -*- coding: utf-8 -*-
"""重绘改造前流程图：8节点 + 痛点标注 + 典型事件还原面板（融入访谈量化数据）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False

CREAM = "#faf3e3"; BROWN = "#8a6d3b"; DARK = "#2b2b2b"
RED = "#c0392b"; RED_BG = "#fdeceb"; PANEL_BG = "#fff8ee"; PANEL_EDGE = "#b08a4f"

nodes = [
    ("1", "设计院发布变更通知", "纸面/邮件传递，无统一入口", None),
    ("2", "新版图纸上传平台", "系统不提醒，知悉靠巧合", "【痛点】无自动通知"),
    ("3", "口头/微信群转达交底", "谁有空谁转，无签收记录", "【痛点】交底缺失·口头指令无留痕"),
    ("4", "现场按旧图施工", "拿到的是旧版，版本错位", "【痛点】按旧图施工"),
    ("5", "发现差异后返工", "已完工程拆改，材料人工双损", "【痛点】返工损失 月均45万元"),
    ("6", "变更签证单人工填写", "施工/造价/业主各执一版", "【痛点】三个版本不一致"),
    ("7", "造价人工核定", "反复对量核价，周期拖长", "【痛点】补签被拒·授权链不清"),
    ("8", "业主确认与归档", "口径不一引发争议，记录分散", "【痛点】签证争议/利润流失"),
]

fig, ax = plt.subplots(figsize=(14.5, 12.5), dpi=110)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
fig.patch.set_facecolor("white")

# ---------- 标题 ----------
ax.text(50, 96.5, "【改造前 · 现状人工流程】远筑工程 · 工程变更与签证协同 —— 现状流程图",
        ha="center", va="center", fontsize=20, fontweight="bold", color="#B03A2E")
ax.text(50, 93.2, "“一张变更单的三个版本”：人工驱动、版本失控、事后补救（融入典型事件 GC-2026-0117 与访谈量化数据）",
        ha="center", va="center", fontsize=10.5, color="#666666")

# ---------- 左列：8 节点 ----------
top_y, bot_y = 87.5, 13.0
ys = [top_y - i * (top_y - bot_y) / 7 for i in range(8)]

for i, (num, title, sub, pain) in enumerate(nodes):
    y = ys[i]
    box = FancyBboxPatch((7, y - 3.4), 46, 6.8,
                         boxstyle="round,pad=0.6,rounding_size=1.2",
                         fc=CREAM, ec=BROWN, lw=1.6)
    ax.add_patch(box)
    c = Circle((11.2, y), 1.55, fc=BROWN, ec="none")
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
                                     color=BROWN, lw=1.8))
    if pain:
        px = 57.5
        pb = FancyBboxPatch((px, y - 2.3), 21.5, 4.6,
                            boxstyle="round,pad=0.4,rounding_size=0.8",
                            fc=RED_BG, ec=RED, lw=1.3, linestyle="--")
        ax.add_patch(pb)
        ax.text(px + 10.75, y, pain, ha="center", va="center",
                fontsize=9.5, color=RED, fontweight="bold")
        ax.plot([53.6, px], [y, y], color=RED, lw=1.0, linestyle="--", alpha=0.6)

# ---------- 右侧：典型事件还原面板 ----------
px0, pw = 81.5, 17.5
py0, ph = 13.0, 74.5
panel = FancyBboxPatch((px0, py0), pw, ph,
                       boxstyle="round,pad=0.6,rounding_size=1.4",
                       fc=PANEL_BG, ec=PANEL_EDGE, lw=2.0)
ax.add_patch(panel)
cx = px0 + pw / 2

ax.text(cx, py0 + ph - 3.2, "典型事件还原", ha="center", va="center",
        fontsize=13.5, fontweight="bold", color=RED)
ax.text(cx, py0 + ph - 6.2, "GC-2026-0117（示例编号）", ha="center", va="center",
        fontsize=10, color="#555555")
ax.text(cx, py0 + ph - 9.0, "口头指令增加管线 → 补签被拒", ha="center", va="center",
        fontsize=10.5, fontweight="bold", color=DARK)

events = [
    ("10月中旬", "甲方口头要求：走廊增加约\n30米桥架＋6个喷淋支管"),
    ("当晚开工", "两班组施工约2天完工\n无书面指令、无交底签收"),
    ("月底报签", "签证被驳回：授权链无法\n确认指令来源与书面依据"),
    ("次月受理", "补设计回复＋监理确认\n前后拖延约3周"),
]
ey = py0 + ph - 13.0
for tag, desc in events:
    tag_b = FancyBboxPatch((px0 + 1.0, ey - 1.25), 5.0, 2.5,
                           boxstyle="round,pad=0.3,rounding_size=0.6",
                           fc=RED, ec="none")
    ax.add_patch(tag_b)
    ax.text(px0 + 3.5, ey, tag, ha="center", va="center", fontsize=7.5,
            color="white", fontweight="bold")
    ax.text(px0 + 6.8, ey, desc, ha="left", va="center", fontsize=7.6, color=DARK)
    ey -= 6.6

# 量化指标块
qy = py0 + ph - 42.5
qb = FancyBboxPatch((px0 + 1.3, qy - 13.5), pw - 2.6, 14.0,
                    boxstyle="round,pad=0.4,rounding_size=0.8",
                    fc="white", ec=PANEL_EDGE, lw=1.2)
ax.add_patch(qb)
ax.text(cx, qy + 1.6, "访谈量化基线", ha="center", va="center",
        fontsize=10.5, fontweight="bold", color=BROWN)
metrics = [
    "变更确认平均 12 天 → 目标 6 天",
    "返工损失 月均 45 万元 → 减 30%",
    "每月约 85 个变更",
    "每项核对图纸与签字 约 90 分钟",
]
my = qy - 1.2
for m in metrics:
    ax.text(px0 + 2.6, my, "● " + m, ha="left", va="center",
            fontsize=8.8, color=DARK)
    my -= 2.6

# 事件教训
ly = py0 + 9.5
lb = FancyBboxPatch((px0 + 1.3, ly - 7.0), pw - 2.6, 8.0,
                    boxstyle="round,pad=0.4,rounding_size=0.8",
                    fc=RED_BG, ec=RED, lw=1.2, linestyle="--")
ax.add_patch(lb)
ax.text(cx, ly + 1.8, "事件教训", ha="center", va="center",
        fontsize=10, fontweight="bold", color=RED)
lesson = ("口头指令无留痕 → 授权链断裂 →\n签证立不住，活干了拿不到钱；\n"
          "与旧图施工叠加时返工与补签\n两头损失")
ax.text(cx, ly - 2.2, lesson, ha="center", va="center", fontsize=8.4, color=DARK)

# ---------- 底部注脚 ----------
ax.text(50, 6.5,
        "现状痛点：处理时长 12 天 · 月均返工损失 45 万元 · 版本正确率无保障 · 口头指令签证采用率低 · 每项核对约 90 分钟",
        ha="center", va="center", fontsize=10.5, color="#555555")
ax.text(50, 3.6,
        "（量化基线来源：业务访谈事实库 f00/f02/f10/f11/f12/f15；事件细节为合成场景示例口径，正式引用前须经造价核对）",
        ha="center", va="center", fontsize=8.5, color="#999999")

plt.tight_layout()
out = r"D:\aworkbuddy\报销助手智能体系统\docs\construction-change\03-current-process-flow.png"
plt.savefig(out, dpi=110, bbox_inches="tight", facecolor="white")
print("saved:", out)
