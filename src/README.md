# src · 源码与资料归档导览

> 本目录对应任务清单「src」部分：**src-1 问答助手归档 ｜ src-2 MVP 项目（工程架构 / Agent 框架 / 知识库 / ≥3 处人工确认点）**。
> MVP 实际代码按 Python 工程惯例放在仓库根目录的 [`app/`](../app/)，本目录提供交付文档与位置地图。

## src-1 · 问答助手归档

📄 交付文档：[`01-问答助手归档说明.md`](./01-问答助手归档说明.md) —— 问答助手五个演进阶段（裸问答原型 → SSE 服务化 → 知识库管理 → Agent 工具化 → Harness 工程化）与资料归档位置。

| 归档内容 | 位置 |
| --- | --- |
| 裸问答 RAG 原型（阶段 1 单脚本） | [`prototype/rag_prototype.py`](../prototype/rag_prototype.py) |
| 对话与知识库接口 | [`app/api/chat.py`](../app/api/chat.py) · [`app/api/knowledge.py`](../app/api/knowledge.py) |
| 知识库源文档 | [`storage/policies/`](../storage/policies/) |
| 研发过程文档 01~08 | [`docs/`](../docs/) |

## src-2 · MVP 项目

📄 交付文档：[`02-MVP项目说明.md`](./02-MVP项目说明.md) · [`02-MVP项目说明.docx`](./02-MVP项目说明.docx) —— 工程架构、Agent 框架、知识库、**4 处人工确认点**（要求至少 3 处）。

| 模块 | 代码位置 | 说明 |
| --- | --- | --- |
| **工程架构** | [`app/main.py`](../app/main.py) · [`app/core/`](../app/core/) · [`app/api/`](../app/api/) · [`app/models/`](../app/models/) | FastAPI 异步后端：JWT 认证、变更/交底/签证领域接口、SSE 对话、管理后台、状态机强制流转 |
| **Agent 框架** | [`app/agent/`](../app/agent/) | 10 工具注册表；Harness 编排（5 轮上限）；HITL 人工闸门（中断/恢复）；决策日志落库 |
| **知识库** | [`app/rag/retriever.py`](../app/rag/retriever.py) · [`storage/policies/`](../storage/policies/) | BM25（中文 bigram）+ FAISS 混合检索，RRF 融合，无向量自动降级 |

**人工确认 / 审核点（4 处）**：① 交底签收确认（签收才流转）；② 签证造价人工核价；③ 业主确认生效；④ AI 起草 HITL 中断确认（AI 只起草、人工核定）。AI 不自动批准任何业务动作、不直接写入业务系统。

## ③ 测试与部署

测试方案 / 五类场景报告 / 上线部署地址：见仓库根目录 [`Test/`](../Test/README.md)。

## ④ 工具脚本

| 脚本 | 用途 |
| --- | --- |
| [`tools/redraw_before_flow.py`](../tools/redraw_before_flow.py) | 生成「改造前」流程图 |
| [`tools/gen_after_flow.py`](../tools/gen_after_flow.py) | 生成「改造后」流程图 |
| [`tools/gen_two_docs.py`](../tools/gen_two_docs.py) | 批量生成设计方案 / 报价测算 docx |
| [`tools/gen_test_docs.py`](../tools/gen_test_docs.py) | 批量生成测试方案与场景报告 docx |
| [`tools/run_scenarios.py`](../tools/run_scenarios.py) | 五类场景端到端测试脚本（httpx） |
