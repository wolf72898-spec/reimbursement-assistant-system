# 报销助手智能体系统

基于 LLM 的企业报销助手：政策问答（RAG）+ 对话式发起报销。FastAPI 异步后端，LLM 供应商可配置。

## 功能（一期）

- **制度问答**：管理员上传报销制度文档 → 切片入库 → 员工提问，系统基于制度文档回答并标注条款出处
- **对话式报销**：员工在对话中描述费用，AI 自动抽取字段生成报销单草稿，缺字段自动追问
- **两角色 RBAC**：首个注册用户自动成为管理员；管理员维护知识库、查看全部报销单

## 快速开始

```bash
pip install -r requirements.txt

# 配置 LLM（.env 或环境变量）
cp .env.example .env   # 填入 RAG_API_KEY

uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs 查看 API 文档
```

第一个注册的用户自动成为管理员。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RAG_API_KEY` | 对话模型 API Key（必填） | - |
| `RAG_BASE_URL` / `RAG_MODEL` | 对话模型供应商与模型 | DeepSeek / deepseek-chat |
| `EMBED_API_KEY` / `EMBED_BASE_URL` / `EMBED_MODEL` | Embedding 供应商 | 千问 / text-embedding-v3 |
| `APP_DATABASE_URL` | 数据库 | SQLite（开发）；生产 PostgreSQL+pgvector |

注：仅配置 DeepSeek（无 Embedding）时自动降级为 BM25 关键词检索；配置 Embedding 后自动启用混合检索（BM25 + 向量 RRF 融合）。

## 架构

四层：入口层（REST/SSE）→ 服务层（认证/会话/报销单/知识库/审计）→ 智能体编排层（意图路由 + RAG 检索 + 字段抽取 + Prompt 管理 + LLM 适配层）→ 数据模型层（SQLAlchemy 异步 + JSON 向量列，二期切 pgvector）。

详细设计见 `docs/需求清单与架构方案.md`。

## 测试

```bash
python -m pytest tests/test_smoke.py -v   # 冒烟测试（无需 API Key）
```

## 目录

```
app/            FastAPI 应用（core/api/models/schemas/agent/rag）
prototype/      阶段1 裸问答原型（单脚本 RAG，供学习对照）
docs/           需求清单与架构方案
tests/          冒烟测试
```

## 后续迭代（见 docs）

OCR 发票识别 → 审批流引擎 → 财务系统对接 → 小程序端 → SSE 流式输出 → pgvector + Alembic
