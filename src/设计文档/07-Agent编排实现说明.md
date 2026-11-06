# 提示词 7 · Agent 编排实现说明（Harness 执行循环 + HITL + 决策日志）

## 一、框架选型：自研轻量 Harness（接受推荐）

**结论：不引入 LangChain/LangGraph/AutoGen，自研 `AgentHarness`（`app/agent/harness.py`，约 250 行，零新增依赖）。**

理由：
1. **工具带副作用且被状态机守门**——本项目需要"执行前拦截"（create_draft 强制人工确认），重框架里要做这件事得绕 event/checkpointer 一大圈；Harness 里就是一行 if + 快照落库；
2. **前端走自研 SSE 事件协议**（tool_call / tool_result / confirm_request / expense…），重框架的事件模型对不上，硬接还要写适配层；
3. 循环本体极小、调试直观；Harness 的四块组成（编排循环 / 工具注册表 / ticket 状态机 / 日志+中断表）将来要迁 LangGraph 时可整体平移。

## 二、执行循环（最多 5 轮）

```
提问 → [第 n 轮] LLM 决策（流式，带工具表）
        ├─ 无工具调用 → 输出即最终回答 → 落库 → done
        └─ 有工具调用 → 逐个执行（create_draft 强制中断转人工确认）
                          ↓ 结果以 role=tool 消息回填
        → [第 n+1 轮] 再决策 … 最多 5 轮，超限给兜底提示
```

- 每轮决策记录到 **agent_step_logs 表**：工具名 / 参数 / 耗时(elapsed_ms) / 结果摘要 / 轮次 / 状态（ok / error / blocked / waiting）
- 管理端查询：`GET /api/admin/traces?session_id=&limit=`

## 三、create_draft 强制中断（人机在环，HITL）

```
模型决定 create_draft
  → 不执行！生成 AgentPendingAction（草稿参数 + 完整 messages 快照落库）
  → SSE 推 confirm_request 事件（草稿内容 + action_id）
  → 流结束，前端渲染确认卡片（✓确认创建 / ✕取消）
  → 员工点击 → POST /api/chat/confirm {action_id, approved}
       ├─ approved=true  → 恢复快照 → 真正建单（ticket 双保险再验一次）→ 继续循环
       └─ approved=false → 回填"用户拒绝"结果 → 模型向用户致歉善后（不能再次建单）
```

- 同一会话同时只允许一个待确认动作（重复触发返回 `CONFIRM_PENDING`）
- 重复确认返回 409；快照存数据库，服务重启后仍可恢复

## 四、三个典型对话流程的预期轨迹

### a.「出差上海3天住宿标准是多少」——只查制度，不建单
```
轮1: get_expense_standard(住宿, 上海)          → 返回标准条文与额度
轮2: （可能）search_policy("上海住宿标准")      → 补充条文
终答: 按职级列出上海住宿上限 + 引用条款出处
agent_step_logs: 1~2 行 ok；无建单类调用
```

### b.「帮我报上个月去北京的差旅」——完整链路含中断
```
轮1: validate_expense(差旅, ?, "上个月")        → failed：日期无法解析/超30天时效
     模型向用户追问：具体日期、金额、票据
轮2: （用户补齐后）validate_expense(差旅, 1200, 2026-09-28, 北京)
     → 若超时效 → failed，解释制度；若通过 → 签发 ticket
轮3: create_draft(ticket_id, …)                → ⚡强制中断，confirm_request
     【员工确认卡片：类型/金额/日期/明细】
确认后: 恢复执行 → 草稿创建 → done（ expense 卡片 + "可在我的报销单提交"）
agent_step_logs: validate(failed→ok)、create(waiting→ok)
```

### c.「这个发票能报吗」——只校验给结论
```
轮1: validate_expense(类型, 金额, 日期)         → passed / failed + violations
终答: 直接给结论（可报 / 不可报+违规原因+制度依据），不建单
agent_step_logs: 1 行
```

## 五、关键代码索引

| 文件 | 职责 |
|------|------|
| `app/agent/harness.py` | AgentHarness：`run()` 新提问 / `resume()` 确认恢复 / `_decide()` 单轮流式决策 / `_execute_tool()` 守门执行 / `_log_step()` 决策日志 |
| `app/models/agent.py` | `agent_step_logs` 决策日志表、`agent_pending_actions` 中断快照表 |
| `app/api/chat.py` | `POST /api/chat/stream`（主循环）、`POST /api/chat/confirm`（确认恢复，SSE） |
| `app/api/admin.py` | `GET /api/admin/traces` 决策日志查询 |
| `app/static/index.html` | 确认卡片 + `resolveConfirm()` + 共用 SSE 泵 `pumpStream()` |
