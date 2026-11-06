# src · 源码与资料归档导览

> 本目录是清单「src」部分的归档入口：**① 问答助手归档 ② MVP 项目（工程架构 / Agent 框架 / 知识库）**。
> MVP 实际代码按 Python 工程惯例放在仓库根目录的 [`app/`](../app/)，本文件给出它们的位置地图。

## ① 问答助手归档

问答助手（现场费用报销场景）是本项目的**第一阶段成果与辅助演示能力**，相关资料归档如下：

| 归档内容 | 位置 |
| --- | --- |
| 六人访谈记录（md / json / csv，42 轮） | [`src/interviews/`](./interviews/) |
| 研发过程文档 01~08（需求评审 → 架构 → 原型 → Agent → 编排 → 上线检查） | [`docs/`](../docs/) |
| 裸问答 RAG 原型（阶段 1 单脚本） | [`prototype/rag_prototype.py`](../prototype/rag_prototype.py) |
| 报销助手工具实现 | [`app/agent/registry.py`](../app/agent/registry.py)（7 个辅助工具） |

## ② MVP 项目三大块

| 模块 | 代码位置 | 说明 |
| --- | --- | --- |
| **工程架构** | [`app/main.py`](../app/main.py) · [`app/core/`](../app/core/) · [`app/api/`](../app/api/) · [`app/models/`](../app/models/) | FastAPI 异步后端：JWT 认证、变更/交底/签证领域接口、SSE 对话、管理后台、状态机强制流转 |
| **Agent 框架** | [`app/agent/`](../app/agent/) | 10 工具注册表 + ticket 约束状态机；Harness 编排（5 轮上限）；HITL 人工闸门（中断/恢复）；决策日志落库 |
| **知识库** | [`app/rag/retriever.py`](../app/rag/retriever.py) · [`storage/policies/`](../storage/policies/) · [`app/api/knowledge.py`](../app/api/knowledge.py) | BM25（中文 bigram）+ FAISS 向量混合检索，RRF 融合；含《工程变更与签证管理制度》等制度文档 |

## ③ 工具脚本

| 脚本 | 用途 |
| --- | --- |
| [`tools/redraw_before_flow.py`](../tools/redraw_before_flow.py) | 生成「改造前」流程图（03-current-process-flow.png） |
| [`tools/gen_after_flow.py`](../tools/gen_after_flow.py) | 生成「改造后」流程图（04-digitized-process-flow.png） |
| [`tools/gen_two_docs.py`](../tools/gen_two_docs.py) | 批量生成详细设计方案 / 报价测算两份 docx 的排版 HTML |
