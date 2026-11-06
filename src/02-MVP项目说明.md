# src-2 交付物 · MVP 项目说明（工程架构 / Agent 框架 / 知识库 / 人工确认点）

> 对应任务清单 **src-2：MVP 项目——工程架构，Agent 框架，知识库，至少 3 处人工确认或审核点**（本系统实际含 **4 处**）。

## 一、工程架构（四层）

| 层 | 组成 | 位置 |
| --- | --- | --- |
| 接入层 | 全中文单页前端（7 视图：工作台/变更台账/交底中心/签证协同/看板/AI 助手/管理后台），JWT 登录、SSE 打字机 | [`app/static/index.html`](../app/static/index.html) |
| 接口层 | FastAPI 路由：auth / construction（领域业务）/ chat / expenses / knowledge / admin | [`app/api/`](../app/api/) |
| Agent 层 | 10 工具注册表 + Harness 编排（5 轮上限、决策日志、HITL 中断恢复） | [`app/agent/`](../app/agent/) |
| 数据层 | SQLAlchemy async + SQLite（生产可切 PostgreSQL）；7 类业务表 + 决策日志 | [`app/models/`](../app/models/) |

业务数据模型：`Project / ChangeOrder / ChangeVersion / Briefing / VisaOrder`（[`app/models/change.py`](../app/models/change.py)），双状态机：变更单（在建→交底中→待签证→已确认）、签证单（待核定→待业主确认→已生效/已驳回），旧版本自动作废。

## 二、Agent 框架（10 工具 + HITL）

- **领域工具（7）**：`query_changes`（查变更台账）、`get_change_detail`（变更详情+版本）、`draft_visa`（AI 起草签证）、`search_policy`（制度检索）、`get_expense_standard`（标准查询）、`validate_expense`（合规校验）、草稿/提交类工具
- **约束机制**：5 轮上限防失控；每步决策写入 `agent_step_logs`；AI 起草签证必须经人工核定后才生效（HITL 中断-恢复）
- **检索底座**：BM25（中文 bigram）+ FAISS 混合检索 + RRF 融合；无 Embedding 时自动降级纯 BM25（[`prototype/rag_prototype.py`](../prototype/rag_prototype.py) 同源算法）

## 三、知识库

- 源文档：[`storage/policies/`](../storage/policies/)（工程变更与签证管理制度 v1、报销制度示例 v1）
- 管理链路：上传 → 自动切片 → 索引 → 问答附引用出处（管理后台上传/删除可视化）

## 四、人工确认 / 审核点（4 处，满足"至少 3 处"）

| # | 确认点 | 环节 | 实现 |
| --- | --- | --- | --- |
| ① | **交底签收** | 交底推送后，施工方必须移动端签收，变更才算"交底必达"并自动流转 | 交底中心签收按钮 → 状态机推进 |
| ② | **造价核价** | 签证单进入"待核定"后，造价工程师核价（可驳回），通过才进入"待业主确认" | 签证协同「核价」按钮 |
| ③ | **业主确认** | 核价通过后由业主方终审确认 / 驳回，确认即生效归档 | 签证协同「确认 / 驳回」按钮 |
| ④ | **AI 起草 HITL** | AI 助手起草的签证仅生成草稿，必须人工核定通过才写入业务数据 | `draft_visa` 工具 + Harness 人工闸门 |

设计原则：**AI 辅助不越权**——AI 只做检索、比对、起草与问答，任何状态流转与金额核定均由对应角色人工触发，全程留痕可审计。

## 五、运行与部署

- 本地：`pip install -r requirements.txt && uvicorn app.main:app --port 8000`（首个注册用户自动成为管理员）
- 线上：见 [`Test/08-上线部署网站地址.md`](../Test/08-上线部署网站地址.md)
- 演示账号：`zhangsan / abc123456`（启动自动播种）
