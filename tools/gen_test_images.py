# -*- coding: utf-8 -*-
"""根据 tests/evidence/results.json 生成每个场景的可视化测试过程图（PNG）"""
import json, io, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

results = json.load(io.open("tests/evidence/results.json", encoding="utf-8"))
os.makedirs("Test/evidence", exist_ok=True)

GREEN = "#2E8B57"; RED = "#C0392B"; DARK = "#1F3A2E"
THEMES = {
    "S1": ("#E8F3EC", "#2E8B57", "正常场景"),
    "S2": ("#FFF8E7", "#B7791F", "边界场景"),
    "S3": ("#FDECEC", "#C0392B", "对抗场景"),
    "S4": ("#EAF2FB", "#2B6CB0", "权限场景"),
    "S5": ("#F3E8FF", "#6B46C1", "故障场景"),
}

for sc in results["scenarios"]:
    sid = sc["id"]
    if sid == "S0":
        continue
    fill, border, tag = THEMES[sid]
    steps = sc["steps"]
    n = len(steps)
    fig_h = max(6, 1.55 * n + 2.6)
    fig, ax = plt.subplots(figsize=(13.2, fig_h), dpi=110)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    fig.patch.set_facecolor("white")

    passed_n = sum(1 for x in steps if x["ok"])
    ax.text(50, 96.5, f"【{tag}】{sc['name']} —— 可视化测试过程",
            ha="center", va="center", fontsize=17, fontweight="bold", color=border)
    ax.text(50, 92.6, f"{sc['desc']}    通过率：{passed_n}/{n} 步",
            ha="center", va="center", fontsize=10, color="#666666")

    top, bot = 88.0, 4.0
    ys = [top - i * (top - bot) / max(n - 1, 1) for i in range(n)]
    bh = (top - bot) / max(n - 1, 1) * 0.52

    for i, st in enumerate(steps):
        y = ys[i]
        ok = st["ok"]
        bcol = GREEN if ok else RED
        box = FancyBboxPatch((3, y - bh / 2), 58, bh,
                             boxstyle="round,pad=0.35,rounding_size=0.8",
                             fc=fill, ec=bcol, lw=1.3)
        ax.add_patch(box)
        mark = "√" if ok else "×"
        ax.text(6.2, y, mark, ha="center", va="center", fontsize=13,
                fontweight="bold", color=bcol)
        ax.text(9.5, y + bh * 0.18, f"{i+1}. {st['name']}", ha="left", va="center",
                fontsize=10.5, fontweight="bold", color=DARK)
        ax.text(9.5, y - bh * 0.26, f"{st['method']} {st['path']}   →   HTTP {st['status']}",
                ha="left", va="center", fontsize=8.2, color="#777777")
        res = st["note"] or json.dumps(st["response"], ensure_ascii=False)[:60]
        rb = FancyBboxPatch((64, y - bh / 2), 33, bh,
                            boxstyle="round,pad=0.35,rounding_size=0.8",
                            fc="white", ec=bcol, lw=1.1, linestyle=(0, (4, 3)))
        ax.add_patch(rb)
        res = res.replace("✓", "√").replace("✗", "×")
        lines = res if len(res) <= 38 else res[:37] + "…"
        ax.text(65.8, y, lines, ha="left", va="center", fontsize=8.2, color=DARK)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((32, y - bh / 2 - 0.2), (32, ys[i + 1] + bh / 2 + 0.2),
                                         arrowstyle="-|>", mutation_scale=13, color=bcol, lw=1.5))

    out = f"Test/evidence/{sid}-{tag}.png"
    plt.savefig(out, bbox_inches="tight", facecolor="white", dpi=110)
    plt.close(fig)
    print("saved", out)
