<div align="center">

# 🏗️ 工程变更与签证协同智能体系统

**面向建筑工程场景的数智化协同平台 · 内置 AI 智能体套件**

*版本唯一 · 交底必达 · 签证同源 · 留痕可审计*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-异步后端-009688?logo=fastapi&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-供应商可配置-8A2BE2)
![Status](https://img.shields.io/badge/智能体底座-可运行-success)

</div>

---

## 📖 项目简介

围绕建筑工程中最容易"扯皮"的 **工程变更与签证协同** 环节，构建一套数智化协同方案：
解决"现场拿到旧图施工、新图无人交底、签证单三个版本不一致"的行业典型痛点。

系统以 **AI 智能体底座**（RAG 检索问答 + Function Calling 工具调用 + 人工确认闭环）为核心引擎，
**报销助手智能体** 是底座之上的第一个已落地辅助模块，验证了从"文档检索 → 智能起草 → 人工确认 → 审计留痕"
的完整链路，可平移复用到变更交底、签证起草等工程场景。

## ✨ 核心能力

### 🧠 智能体底座（已实现，可运行）

| 能力 | 说明 |
|------|------|
| 🔍 **混合检索问答** | BM25 + 向量检索 RRF 融合，回答标注条款出处；仅 DeepSeek 时自动降级 BM25 |
| 🛠️ **Function Calling** | 7 个工具注册表 + 服务端 ticket 状态机（10 分钟有效、金额篡改即失效） |
| 🔁 **Agent Harness** | 自研编排循环（最多 5 轮），决策日志逐轮落库（tool / args / 耗时 / 状态） |
| ⏸️ **人机协同 HITL** | 高风险动作强制中断人工确认，确认后恢复执行，取消后自动善后 |
| 📡 **SSE 流式界面** | 打字机输出、检索状态、来源折叠、报销卡片、确认卡片，全中文界面 |
| 🔐 **RBAC 双角色** | JWT 认证，首个注册用户自动成为管理员，管理后台三标签面板 |

### 🏗️ 工程变更与签证协同（设计方案 → 平移路线）

| 模块 | 目标 | 状态 |
|------|------|------|
| 统一变更入口 | 变更登记唯一版本源，旧版自动作废 | 📋 设计方案 |
| AI 比对与交底推送 | 新旧图差异识别，按角色推送签收 | 📋 设计方案 |
| 签证单 AI 起草 | 引用变更与工程量数据，多方在线协同 | 📋 设计方案 |
| 数据看板 | 五项基线指标实时可测（时长/返工/正确率/采用率/成本） | 📋 设计方案 |
| 报销助手智能体 | 底座参考实现：RAG 问答 + 对话式报销草稿 | ✅ **可运行** |

## 🚀 快速开始

```bash
pip install -r requirements.txt

# 配置 LLM（.env 或环境变量）
cp .env.example .env   # 填入 RAG_API_KEY

uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000        中文聊天界面（智能体模式）
# 打开 http://127.0.0.1:8000/docs   API 文档
```

> 第一个注册的用户自动成为管理员。

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RAG_API_KEY` | 对话模型 API Key（必填） | - |
| `RAG_BASE_URL` / `RAG_MODEL` | 对话模型供应商与模型 | DeepSeek / deepseek-chat |
| `EMBED_API_KEY` / `EMBED_BASE_URL` / `EMBED_MODEL` | Embedding 供应商 | 千问 / text-embedding-v3 |
| `APP_DATABASE_URL` | 数据库 | SQLite（开发）；生产 PostgreSQL + pgvector |

## 📚 文档导航

**工程项目（工程变更与签证协同）**

| 交付物 | 说明 |
|--------|------|
| 📄 [业务挖掘报告](docs/construction-change/01-业务挖掘报告.md) | 实验室系统生成：机会清单 · 指标基线 · 利益相关者地图 |
| 📊 [行业分析](docs/construction-change/02-行业分析.docx) | 建筑行业数智化转型分析（Word） |
| 🗺️ [现状流程图](docs/construction-change/03-现状流程图.png) / [转型后流程图](docs/construction-change/04-数智化转型后流程图.png) | 人工现状 vs 数智化流程对比 |
| 💰 [报价单](docs/construction-change/05-报价单.xlsx) | 首期试点 3 个月打包价 28.6 万元明细 |
| 📐 [设计方案](docs/construction-change/06-设计方案.docx) | 四层架构 · 功能设计 · 权限红线 · 实施计划 |

**智能体研发（报销助手智能体 · 底座实现）**

| 文档 | 说明 |
|------|------|
| [需求评审](docs/01-需求评审十问与决策.md) / [架构方案](docs/02-技术架构方案.md) | 十问决策 + 四层架构选型 |
| [Agent 工具设计](docs/04-Agent工具与调用约束设计.md) | 7 工具 + 调用顺序约束 |
| [Agent 编排](docs/07-Agent编排实现说明.md) | Harness 循环 · 决策日志 · HITL 轨迹 |
| [评测用例](tests/evaluation_cases.json) | 30 条：制度/工具调用/违规意图/多轮上下文 |

## 🧪 测试

```bash
python -m pytest tests/test_smoke.py -v   # 冒烟测试（无需 API Key）
```

## 📁 目录结构

```
app/                        FastAPI 智能体应用（core/api/models/agent/rag/static）
├── agent/registry.py       7 工具注册表 + ticket 状态机
├── agent/harness.py        Agent 编排循环（5 轮上限 + HITL 中断恢复）
├── rag/retriever.py        BM25 + 向量混合检索（RRF 融合）
└── static/index.html       全中文聊天界面（SSE 流式）
docs/construction-change/   工程变更与签证协同项目交付物（6 件套）
prototype/                  阶段1 裸问答原型（单脚本 RAG）
tests/                      冒烟测试 + 30 条评测用例
```

## 🗺️ 路线图

```
✅ 智能体底座（RAG + 工具调用 + HITL + 审计）
✅ 报销助手智能体（参考实现，端到端可运行）
✅ 工程变更与签证协同设计方案（业务挖掘/行业分析/流程图/报价/设计）
⬜ 变更登记与版本管理模块（P1）
⬜ AI 图纸比对与交底签收闭环（P2）
⬜ 签证单起草多方协同 + 数据看板（P3）
```

---

<div align="center">

*合成业务场景说明：工程变更与签证协同相关资料基于 FDE 实验室合成样本，真实接口与业务验收需另行核实*

</div>
