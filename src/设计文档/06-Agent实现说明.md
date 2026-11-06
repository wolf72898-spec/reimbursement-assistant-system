# 提示词 6 · Agent 实现说明（自主决策 + 服务端状态机）

> 对应提示词 6 与《04-Agent工具与调用约束设计.md》的一期落地。
> 系统已从"固定流程问答"升级为 LLM 自主决策的智能体：模型自己决定调用哪些工具、按什么顺序，服务端状态机保证它"想跳步也跳不了"。

## 一、7 个工具（Function Calling 规范，代码在 `app/agent/registry.py`）

| 工具 | 功能 | 约束 |
|------|------|------|
| `search_policy` | RAG 检索制度条文 | 无 |
| `get_expense_standard` | 查费用标准额度 | 无 |
| `validate_expense` | 金额超标/30天时效/违规表述校验，通过签发 ticket（10 分钟有效） | — |
| `create_draft` | 创建报销草稿 | **必须携带有效 ticket，金额一致** |
| `update_draft` | 补充/修改草稿 | **改金额必须携带匹配新金额的 ticket** |
| `get_my_drafts` | 查询自己的草稿 | 仅本人 |
| `submit_draft` | 提交报销单 | **missing_fields 为空且状态 draft** |

## 二、调用顺序约束（服务端强制，实测验证）

```
validate_expense (passed → ticket)
      ↓ 必须携带
create_draft （验 ticket：存在 / 未过期 / 金额摘要一致）
      ↓
update_draft （改金额要新 ticket） → submit_draft（信息完整才放行）
```

实测结果（自动化验证）：
- ❌ 无 ticket 直接建单 → `VALIDATION_REQUIRED`，拒绝
- ❌ 校验 38 元后建单写 380 元 → 金额摘要不一致，拒绝
- ✅ 校验 38 元后按原金额建单 → 成功

Agent 循环最多 8 轮防死循环；拒绝响应带中文修正指引，模型收到后自动回到正轨（自愈）。

## 三、真实运行示例（DeepSeek 实测）

**问："去北京出差住宿标准是多少？"**
工具序列：`get_expense_standard → search_policy`，回答按职级列出上限表格并附制度出处。

**问："我要报销 2026-10-28 的打车费 38 元"**
工具序列：`validate_expense → create_draft`，生成报销单卡片（38 元），信息完整可提交。

## 四、SSE 事件流（前端全程可视化）

```
tool_call   → 前端显示"调用 validate_expense …"
tool_result → 显示"✓ 校验通过，已签发凭证"（失败显示 ⚠ 原因）
sources     → 引用来源折叠块
delta*      → 正文打字机输出
expense     → 报销单卡片（金额/明细/待补充项）
done        → 结束
```

## 五、关键文件

| 文件 | 职责 |
|------|------|
| `app/agent/registry.py` | 工具 schema + 执行器 + ticket 状态机 + 违规关键词 |
| `app/agent/loop.py` | Agent 循环（流式工具调用累积、事件产出、系统提示词从数据库读取） |
| `app/agent/prompts/agent.txt` | 三段式默认系统提示词 |
| `app/api/chat.py` | `/api/chat/stream` SSE 主入口 |
