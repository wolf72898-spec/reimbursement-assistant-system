# -*- coding: utf-8 -*-
"""生成 05-行业分析.md（自 docx 提取）与 02-项目简报资料/ 4 份简报"""
import json, io, zipfile, re, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------- 05-行业分析.md ----------
z = zipfile.ZipFile("docs/任务4-行业分析.docx")
xml = z.read("word/document.xml").decode("utf-8")
# 按段落切分
paras = []
for pm in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
    t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", pm)).strip()
    if t:
        paras.append(t)
md = ["# 行业分析：建筑行业工程变更与签证协同数智化", "",
      "> 客户：远筑工程（合成业务场景）｜本 md 与 06-行业分析.docx 内容一致，便于在线阅览", ""]
for t in paras:
    if re.match(r"^[一二三四五六七八九十]+、", t):
        md.append(f"\n## {t}\n")
    elif re.match(r"^\d+(\.\d+)*\s", t) or re.match(r"^\d+．", t):
        md.append(f"\n### {t}\n")
    else:
        md.append(t)
        md.append("")
io.open("docs/任务4-行业分析.md", "w", encoding="utf-8").write("\n".join(md))
print("05-行业分析.md", len("\n".join(md)), "chars,", len(paras), "paras")

# ---------- 02-项目简报资料 ----------
os.makedirs("docs/任务2-项目简报资料", exist_ok=True)
d = json.load(io.open("src/interviews/discovery-report.json", encoding="utf-8")) if os.path.exists("src/interviews/discovery-report.json") else json.load(io.open("docs/任务1-六人访谈记录/discovery-report.json", encoding="utf-8"))

def dump(v):
    if isinstance(v, str):
        return v
    return "```json\n" + json.dumps(v, ensure_ascii=False, indent=2) + "\n```"

f1 = f"""# 项目简报 ①：案例背景与开场

> 来源：FDE 训练中心实验室（project=construction-change）任务 2「项目基本简报信息」归档之一，共 4 份

- **案例标题**：{d.get('case', '')}
- **行业**：{d.get('industry', '')}
- **买方/决策人**：{d.get('methodContext', {}).get('buyer', '')}
- **一线操作人**：{d.get('methodContext', {}).get('operator', '')}

## 客户开场原话

> {d.get('opening', '')}

## 案例要点

「一张变更单的三个版本」：现场拿到旧版图纸施工，设计院新版变更图已上传平台但无人做技术交底；变更签证单出现施工员、造价、业主口径三个版本不一致。管理层希望用 AI 改善，但未确定优先环节、验收标准和权限边界。
"""
f2 = ["# 项目简报 ②：需求清单与访谈事实", "",
      "> 实验室机会阶段输出的业务需求条目（含优先级与证据编号）", ""]
for i, r in enumerate(d.get("requirements", []), 1):
    f2.append(f"## {i}. {r.get('title', '')}")
    f2.append(f"- **责任角色**：{r.get('owner', '')}　**状态**：{r.get('status', '')}　**优先级**：{r.get('priority', '')}")
    for ev in r.get("evidence", []):
        f2.append(f"- 证据 [{ev.get('id', '')}]：{ev.get('text', '')}")
    f2.append("")
io.open("docs/任务2-项目简报资料/02-需求清单与访谈事实.md", "w", encoding="utf-8").write("\n".join(f2))

f3 = f"""# 项目简报 ③：方法框架

## 归纳框架

{d.get('framework', '')}

## 方法论上下文

{dump(d.get('methodology', ''))}

## 分析结论

{dump(d.get('analysis', ''))}

## 覆盖范围

{dump(d.get('coverage', ''))}
"""
f4 = f"""# 项目简报 ④：交付衔接与公开来源

## 实验室阶段衔接（handoff）

{dump(d.get('handoff', ''))}

## 公开来源（publicSources）

{dump(d.get('publicSources', ''))}

## 待补缺口（gaps）

{dump(d.get('gaps', ''))}

## 说明

{d.get('note', '')}
"""
io.open("docs/任务2-项目简报资料/01-案例背景与开场.md", "w", encoding="utf-8").write(f1)
io.open("docs/任务2-项目简报资料/03-方法框架与分析.md", "w", encoding="utf-8").write(f3)
io.open("docs/任务2-项目简报资料/04-交付衔接与来源.md", "w", encoding="utf-8").write(f4)
print("4 briefing files written")
