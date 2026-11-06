# -*- coding: utf-8 -*-
"""批量生成 10-详细项目设计方案 与 11-报价与投入产出测算 的排版 HTML（business-modern 骨架）"""
import io, os

RID = "docx-design-20261106091523"
OUT = f"D:/aworkbuddy/报销助手智能体系统/output/{RID}"
SRC = "D:/aworkbuddy/报销助手智能体系统/output/docx-reqdef-20261106090853/stage2/formatted-需求定义文档.html"
s0 = io.open(SRC, encoding="utf-8").read()

CSS_START = s0.index("  <style>")
CSS_END = s0.index("</style>") + len("</style>")
CSS = s0[CSS_START:CSS_END]

def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="docx-page-size" content="A4">
  <title>{title}</title>
{CSS}
</head>
<body>
{body}
</body>
</html>
"""

# ============ 文档 10：详细项目设计方案 ============
d10_body = """
  <section role="cover" class="report-cover">
    <p class="cover-category">工程变更与签证协同 · 详细设计</p>
    <p class="cover-title">详细项目设计方案</p>
    <p class="cover-subtitle">总体架构 · 功能与数据设计 · AI 能力 · 实施计划</p>
    <div class="cover-meta">
      <p>客户：远筑工程（建筑行业） | 版本：V1.0 | 日期：2026-11-06</p>
    </div>
  </section>

  <section role="cover">
    <nav class="doc-toc" aria-label="文档目录">
      <p class="toc-title">目录</p>
      <ol class="toc-list">
        <li><a href="#s1">一、设计目标与范围</a></li>
        <li><a href="#s2">二、总体架构</a></li>
        <li><a href="#s3">三、功能模块设计</a></li>
        <li><a href="#s4">四、数据模型设计</a></li>
        <li><a href="#s5">五、AI 能力设计</a></li>
        <li><a href="#s6">六、接口与权限设计</a></li>
        <li><a href="#s7">七、非功能设计</a></li>
        <li><a href="#s8">八、实施计划与里程碑</a></li>
        <li><a href="#s9">九、测试评估与验收衔接</a></li>
      </ol>
    </nav>
  </section>

  <section role="body" data-page-restart="1">
    <div class="executive-summary">
      <div class="summary-header">
        <h3 class="summary-title">执行摘要</h3>
      </div>
      <div class="summary-body">本方案是《需求定义文档》的下游设计文档，将 R1—R6 六项需求落成可实施的工程技术设计：四层总体架构（接入层 / 业务层 / AI 层 / 数据层），七大业务数据表与领域状态机，十个 Agent 工具与五轮上限的编排 Harness，BM25+向量混合检索的知识问答，以及"AI 起草、人工核定"的 HITL 机制。实施按首期 3 个月试点排布四个里程碑，测试评估与《需求定义文档》的 AC-01～AC-10 验收标准逐条衔接。</div>
    </div>

    <p class="note-para">设计基准：本方案与已实现的 MVP 代码库（FastAPI + SQLAlchemy 异步 + aiosqlite，Agent 编排与 RAG 已具备）对齐，设计描述即实现现状的可验证表达；试点推广阶段的扩展项以"（扩展）"标注。</p>

    <h2 class="section-header" id="s1">一、设计目标与范围</h2>
    <p class="body-para">设计目标：以最小可用产品承载 P0 三项需求（版本分发与交底触达 R1、变更台账与状态机 R2、AI 辅助签证起草 R3），同时为 P1（制度问答 R4）与 P2（读图找差异 R5、管理看板 R6）预留扩展点。设计范围不含业主侧系统改造与电子签章集成（另行立项）。</p>
    <table class="data-table"><thead><tr><th style="width:30%">设计原则</th><th>说明</th></tr></thead><tbody>
      <tr><td>版本唯一可信源</td><td>一切以变更台账为准，旧版本自动作废，杜绝多版本并行</td></tr>
      <tr><td>授权链强制完整</td><td>无书面依据的变更单不可进入待签证状态（对应 AC-02）</td></tr>
      <tr><td>AI 辅助不越权</td><td>AI 起草/建议不落终态，关键动作人工审批，全程留痕可追溯</td></tr>
      <tr><td>可评测可回滚</td><td>30 条评测用例回归 + 上线检查清单五维度，异常可 30 分钟回滚</td></tr>
    </tbody></table>

    <h2 class="section-header" id="s2">二、总体架构</h2>
    <table class="data-table"><thead><tr><th style="width:16%">层</th><th style="width:34%">组成</th><th>职责</th></tr></thead><tbody>
      <tr><td>接入层</td><td>Web 前端（工作台/变更台账/交底中心/签证协同/看板/管理后台）、登录鉴权</td><td>角色化入口，演示账号一键体验，FDE 风格界面</td></tr>
      <tr><td>业务层</td><td>FastAPI 路由：auth / chat(SSE) / expenses / knowledge / admin / construction</td><td>认证、对话、报销辅助、知识库、后台管理、变更与签证领域接口</td></tr>
      <tr><td>AI 层</td><td>Agent Harness（10 工具，5 轮上限）、RAG 混合检索、HITL 中断恢复</td><td>制度问答、状态查询、AI 起草签证、费用校验，决策日志留痕</td></tr>
      <tr><td>数据层</td><td>SQLAlchemy 异步模型 + SQLite（生产可切 PostgreSQL）、文件存储（制度文档/图片）</td><td>七类业务表 + 决策日志表，seed 演示数据</td></tr>
    </tbody></table>
    <p class="body-para">外部依赖：DeepSeek 大模型 API（对话与起草生成）；无向量化能力时 RAG 自动降级为纯 BM25 中文 bigram 检索，保证功能不中断。（扩展）图纸比对服务作为独立worker接入，不阻塞主链路。</p>

    <h2 class="section-header" id="s3">三、功能模块设计</h2>
    <h3 id="s3-1">3.1 需求到模块的映射</h3>
    <table class="data-table"><thead><tr><th style="width:10%">需求</th><th style="width:30%">模块</th><th>关键设计</th></tr></thead><tbody>
      <tr><td>R1</td><td>交底中心</td><td>变更发布生成带版本号交底单；干系人推送；签收留痕（人/时间/版本）；AI 摘要变更要点</td></tr>
      <tr><td>R2</td><td>变更台账</td><td>状态机：在建→交底中→待签证→已确认；新版本创建后旧版自动作废；按项目/状态筛选</td></tr>
      <tr><td>R3</td><td>签证协同</td><td>AI 起草签证单草稿→待核定→人工核定→待确认→已生效/驳回；驳回可改后重提</td></tr>
      <tr><td>R4</td><td>AI 助手（SSE 对话）</td><td>检索问答附引用出处；查不到明确告知；违规意图拒绝</td></tr>
      <tr><td>R5</td><td>（扩展）读图差异提示</td><td>新旧图纸关键差异清单，仅作参考，独立 worker 处理</td></tr>
      <tr><td>R6</td><td>看板</td><td>处理时长/返工/采用率/复核成本统计，按月报表</td></tr>
    </tbody></table>
    <h3 id="s3-2">3.2 Agent 工具集（10 个）</h3>
    <table class="data-table"><thead><tr><th style="width:28%">工具</th><th style="width:14%">类别</th><th>说明</th></tr></thead><tbody>
      <tr><td>search_policy / get_expense_standard</td><td>知识检索</td><td>制度检索（BM25+FAISS 混合、RRF 融合）与费用标准查询</td></tr>
      <tr><td>validate_expense</td><td>校验</td><td>报销费用合规校验（限额/票据/日期规则）</td></tr>
      <tr><td>create_draft / update_draft / get_my_drafts / submit_draft</td><td>报销单</td><td>草稿增改查与提交（辅助演示场景）</td></tr>
      <tr><td>query_changes / get_change_detail</td><td>变更领域</td><td>变更单列表检索与详情（版本/状态/干系人）</td></tr>
      <tr><td>draft_visa</td><td>签证领域</td><td>AI 起草签证单：仅生成"待核定"草稿，人工核定后流转</td></tr>
    </tbody></table>
    <h3 id="s3-3">3.3 编排与 HITL</h3>
    <p class="body-para">Harness 以 5 轮为上限逐步调用工具并汇总答案；每一步写入决策日志表（agent_step_logs）可回放审计。涉及提交类动作时进入 HITL 中断：系统生成确认请求（confirm_request 事件），用户确认后从快照恢复执行，拒绝则终止并记录。该机制同时满足"AI 不自动批准、不直写业务系统"两条红线。</p>

    <h2 class="section-header" id="s4">四、数据模型设计</h2>
    <table class="data-table"><thead><tr><th style="width:24%">表</th><th style="width:26%">关键字段</th><th>说明</th></tr></thead><tbody>
      <tr><td>users</td><td>用户名/密码哈希/角色</td><td>JWT 认证；首个注册用户自动为管理员</td></tr>
      <tr><td>projects</td><td>项目编号/名称/干系人</td><td>领域基座，演示项目：远筑·滨江商务中心</td></tr>
      <tr><td>change_orders</td><td>编号/标题/状态/提出人/项目</td><td>变更单主表，状态机字段约束流转</td></tr>
      <tr><td>change_versions</td><td>版本号/内容/生效标志</td><td>多版本支持；新版本生效即作废旧版本</td></tr>
      <tr><td>briefings</td><td>变更单/版本/签收人/时间</td><td>交底与签收留痕（AC-01 证据）</td></tr>
      <tr><td>visa_orders</td><td>编号/变更单/状态/核定人</td><td>签证单：待核定→待确认→已生效/已驳回</td></tr>
      <tr><td>documents + chunks</td><td>制度文档/切分块/元数据</td><td>RAG 知识库，含《工程变更与签证管理制度》</td></tr>
      <tr><td>agent_step_logs</td><td>会话/轮次/工具/入参出参</td><td>决策日志，审计与评测回放</td></tr>
    </tbody></table>
    <p class="body-para">演示数据由 seed 脚本初始化：5 张变更单（含一张三版本案例）与 6 类角色利益相关者，与业务挖掘报告角色地图一致（顾明岚/林亦舟/唐映秋/秦芮/傅景/叶书）。</p>

    <h2 class="section-header" id="s5">五、AI 能力设计</h2>
    <h3 id="s5-1">5.1 RAG 检索问答</h3>
    <p class="body-para">文档切分后建立 BM25（中文 bigram）与向量（FAISS）双路索引，检索结果以 RRF 融合重排；答案强制携带出处章节号，检索不到时明确告知并引导人工查阅（AC-09）。DeepSeek 不提供向量化时自动降级纯 BM25，功能可用性优先。</p>
    <h3 id="s5-2">5.2 起草生成</h3>
    <p class="body-para">签证起草提示词限定：只依据变更单事实字段生成草稿，缺失字段留空标注"待补充"，不得编造工程量与金额；输出直接落"待核定"状态，等人工核定。</p>
    <h3 id="s5-3">5.3 评测体系</h3>
    <p class="body-para">30 条评测用例覆盖四类：制度问答（含 3 个陷阱题）、工具调用、违规意图、多轮上下文；每次 prompt 或工具变更后全量回归，作为 AC-07 的证据来源。</p>

    <h2 class="section-header" id="s6">六、接口与权限设计</h2>
    <table class="data-table"><thead><tr><th style="width:34%">接口组</th><th>要点</th></tr></thead><tbody>
      <tr><td>/api/auth（register/login/me）</td><td>JWT 签发与身份查询；密码哈希存储</td></tr>
      <tr><td>/api/chat（SSE）</td><td>事件流：status/sources/delta/expense/tool_call/tool_result/confirm_request/done/error</td></tr>
      <tr><td>/api/construction</td><td>项目/变更/版本/交底/签证 CRUD 与状态流转；授权链完整性校验拦截</td></tr>
      <tr><td>/api/knowledge / /api/admin</td><td>知识库管理与后台运营（上传/列表/统计）</td></tr>
    </tbody></table>
    <p class="body-para">权限模型：按角色授权（管理员/造价/施工员/质量安全/业主代表）；质量安全角色对红线事项持一票否决；未授权数据不参与检索；所有写操作留操作日志。</p>

    <h2 class="section-header" id="s7">七、非功能设计</h2>
    <p class="list-para">- <strong>性能：</strong>检索问答 P95 ≤ 5 秒（降级 BM25 后 P95 ≤ 2 秒）；SSE 首字延迟 ≤ 3 秒；（扩展）并发限流按用户维度令牌桶；</p>
    <p class="list-para">- <strong>安全：</strong>JWT 过期与刷新、SQL 参数化、上传文件类型白名单、密钥仅存环境变量不入库；</p>
    <p class="list-para">- <strong>可用性：</strong>异常兜底（模型超时返回降级提示）、冒烟测试 8 项常驻；</p>
    <p class="list-para">- <strong>可回滚：</strong>版本化部署 + 数据库迁移脚本回滚；上线检查清单五维度（数据安全/并发限流/异常兜底/内容安全/回滚预案）作为发布门禁；</p>
    <p class="list-para">- <strong>可观测：</strong>决策日志 + 指标埋点（问答命中率、起草采纳率、确认时长），支撑 R6 看板取数。</p>

    <h2 class="section-header" id="s8">八、实施计划与里程碑</h2>
    <table class="data-table"><thead><tr><th style="width:18%">里程碑</th><th style="width:14%">时间</th><th>交付与出口条件</th></tr></thead><tbody>
      <tr><td>M1 调研与需求基线</td><td>第 1—2 周</td><td>六角色访谈、真实基线指标建立，修正 AC-05/08 目标值</td></tr>
      <tr><td>M2 核心功能上线</td><td>第 3—8 周</td><td>R1/R2/R3 上线，授权链拦截与签收留痕生效，冒烟+评测回归通过</td></tr>
      <tr><td>M3 问答与运营</td><td>第 9—10 周</td><td>R4 制度问答上线，知识库责任人机制生效，基线月报首次出具</td></tr>
      <tr><td>M4 试点验收</td><td>第 11—12 周</td><td>AC-01～AC-10 逐条验收，上线检查清单五维度全过，输出推广建议</td></tr>
    </tbody></table>
    <p class="body-para">R5 读图差异与 R6 看板扩展在 M4 后按试点结论排期，不进入首期关键路径。</p>

    <h2 class="section-header" id="s9">九、测试评估与验收衔接</h2>
    <p class="body-para">测试分层：单元（模型与工具函数）、接口（冒烟 8 项）、评测（30 条回归）、UAT（按 AC 清单逐条演示）。所有验收证据（评测报告、签收留痕、决策日志、月报）归档至项目文档目录，供顾明岚（业务负责人）与傅景（红线审批人）联签确认。上线前完成一次真实单据链的端到端回归，替代合成样本口径。</p>
  </section>
"""

# ============ 文档 11：报价与投入产出测算 ============
d11_body = """
  <section role="cover" class="report-cover">
    <p class="cover-category">工程变更与签证协同 · 商务测算</p>
    <p class="cover-title">报价与投入产出测算</p>
    <p class="cover-subtitle">低 / 中 / 高三档方案 · 投入明细 · 产出测算 · 回收期与 ROI</p>
    <div class="cover-meta">
      <p>客户：远筑工程（建筑行业） | 报价有效期：30 天 | 日期：2026-11-06</p>
    </div>
  </section>

  <section role="cover">
    <nav class="doc-toc" aria-label="文档目录">
      <p class="toc-title">目录</p>
      <ol class="toc-list">
        <li><a href="#s1">一、三档方案总览</a></li>
        <li><a href="#s2">二、低档方案明细（18.5 万元）</a></li>
        <li><a href="#s3">三、中档方案明细（28.6 万元，推荐）</a></li>
        <li><a href="#s4">四、高档方案明细（44.9 万元）</a></li>
        <li><a href="#s5">五、产出测算（收益口径）</a></li>
        <li><a href="#s6">六、投入产出比与回收期</a></li>
        <li><a href="#s7">七、商务条款与建议</a></li>
      </ol>
    </nav>
  </section>

  <section role="body" data-page-restart="1">
    <div class="executive-summary">
      <div class="summary-header">
        <h3 class="summary-title">执行摘要</h3>
      </div>
      <div class="summary-highlights">
        <table class="data-table"><thead><tr>
            <th>低档（3 个月）</th><th>中档（3 个月，推荐）</th><th>高档（6 个月）</th><th>中档保守回收期</th>
          </tr></thead><tbody><tr>
            <td><span class="card-value">18.5 万元</span><br><span class="card-trend">P0 核心试点</span></td>
            <td><span class="card-value">28.6 万元</span><br><span class="card-trend">P0+P1 完整交付</span></td>
            <td><span class="card-value">44.9 万元</span><br><span class="card-trend">全量+读图试点</span></td>
            <td><span class="card-value">约 3.9 个月</span><br><span class="card-trend">按 50% 达成口径</span></td>
          </tr></tbody></table>
      </div>
      <div class="summary-body">报价分低、中、高三档：低档 18.5 万元覆盖 P0 三项核心需求的最小试点；中档 28.6 万元（与既有报价单口径一致）为推荐方案，P0 全量 + P1 制度问答 + 完整评测陪跑；高档 44.9 万元在 6 个月窗口内叠加 AI 读图试点与管理看板。产出测算基于访谈口径：返工损失月均 45 万元按减少 30% 计、人工复核按每月 85 单×90 分钟压至 30 分钟计，年化可量化收益约 177 万元；按 50% 保守达成口径约 88 万元/年，中档方案回收期约 3.9 个月，首年 ROI 约 208%。</div>
    </div>

    <p class="note-para">测算口径说明：收益基线来自《典型事件访谈记录》（返工损失约 45 万元/月、每月约 85 个变更、单项核对约 90 分钟），均为访谈估计值；正式合同前以 M1 里程碑建立的真实基线修正本测算。</p>

    <h2 class="section-header" id="s1">一、三档方案总览</h2>
    <table class="data-table"><thead><tr><th style="width:14%">档位</th><th style="width:10%">周期</th><th style="width:12%">报价</th><th style="width:34%">需求覆盖</th><th>适合场景</th></tr></thead><tbody>
      <tr><td>低档</td><td>3 个月</td><td><span class="data-emphasis">18.5 万元</span></td><td>R1+R2+R3（P0 核心），R4 仅基础问答</td><td>预算受限，先验证 P0 价值</td></tr>
      <tr><td>中档（推荐）</td><td>3 个月</td><td><span class="data-emphasis">28.6 万元</span></td><td>R1+R2+R3 全量 + R4 完整问答 + 30 条评测回归 + 全程陪跑</td><td>标准试点，验收闭环最完整</td></tr>
      <tr><td>高档</td><td>6 个月</td><td><span class="data-emphasis">44.9 万元</span></td><td>中档全量 + R5 读图差异试点（≤20 单）+ R6 管理看板</td><td>一次到位，含智能扩展项</td></tr>
    </tbody></table>

    <h2 class="section-header" id="s2">二、低档方案明细（18.5 万元）</h2>
    <table class="data-table"><thead><tr><th style="width:14%">类别</th><th style="width:34%">费用项</th><th style="width:10%">单位×数量</th><th style="width:12%">小计（元）</th><th>说明</th></tr></thead><tbody>
      <tr><td>实施服务</td><td>业务调研与需求定义</td><td>6 人天×4800</td><td>28,800</td><td>聚焦 P0 需求确认与基线</td></tr>
      <tr><td>实施服务</td><td>平台配置与构建集成</td><td>10 人天×4800</td><td>48,000</td><td>变更台账+交底+签证主流程</td></tr>
      <tr><td>实施服务</td><td>AI 起草接入与调优</td><td>6 人天×5600</td><td>33,600</td><td>签证起草提示词调优</td></tr>
      <tr><td>实施服务</td><td>测试评估与试点支持</td><td>4 人天×4800</td><td>19,200</td><td>冒烟+核心评测</td></tr>
      <tr><td>平台订阅</td><td>协同平台订阅（50 用户）</td><td>3 月×8000</td><td>24,000</td><td>试点期</td></tr>
      <tr><td>AI 用量</td><td>文档处理用量包</td><td>2 万次×3000</td><td>6,000</td><td>超出按量另计</td></tr>
      <tr><td>培训交付</td><td>现场培训与手册</td><td>1 场×3600</td><td>3,600</td><td>管理端+现场端合并场</td></tr>
      <tr><td>运维支持</td><td>试点期远程运维</td><td>1 项</td><td>2,600</td><td>5×8 小时</td></tr>
      <tr><td colspan="3"><strong>合计（含税）</strong></td><td><strong>185,000</strong></td><td><strong>人民币壹拾捌万伍仟元整</strong></td></tr>
    </tbody></table>

    <h2 class="section-header" id="s3">三、中档方案明细（28.6 万元，推荐）</h2>
    <p class="body-para">中档与既有《报价单.xlsx》完全同口径，覆盖调研 10 人天、需求设计 8 人天、平台配置 15 人天、AI 接入调优 10 人天、测试陪跑 6 人天，以及平台订阅 3 个月、AI 用量 3 万次、培训 2 场与试点期运维，合计 286,000 元（人民币贰拾捌万陆仟元整）。相对低档的核心增量：完整 RAG 制度问答（附引用出处）、30 条评测用例全量回归、每周复盘与指标对照评估、双端分开培训。</p>

    <h2 class="section-header" id="s4">四、高档方案明细（44.9 万元）</h2>
    <table class="data-table"><thead><tr><th style="width:14%">类别</th><th style="width:34%">费用项</th><th style="width:10%">单位×数量</th><th style="width:12%">小计（元）</th><th>说明</th></tr></thead><tbody>
      <tr><td>实施服务</td><td>中档全量实施服务</td><td>—</td><td>185,000</td><td>调研/设计/配置/测试包干</td></tr>
      <tr><td>专项</td><td>R5 读图差异试点</td><td>8 人天×5600</td><td>44,800</td><td>≤20 单，不达标不扩量</td></tr>
      <tr><td>专项</td><td>R6 管理看板开发</td><td>6 人天×4800</td><td>28,800</td><td>五项基线指标月报自动化</td></tr>
      <tr><td>实施服务</td><td>平台配置扩展与联调</td><td>增量 5 人天×4800</td><td>24,000</td><td>看板数据链路与读图接入</td></tr>
      <tr><td>实施服务</td><td>测试评估扩展</td><td>增量 2 人天×4800</td><td>9,600</td><td>扩展项评测回归</td></tr>
      <tr><td>平台订阅</td><td>协同平台订阅（6 个月）</td><td>6 月×8000</td><td>48,000</td><td>窗口拉长至 6 个月</td></tr>
      <tr><td>AI 用量</td><td>文档与读图用量包</td><td>6 万次×3000</td><td>18,000</td><td>含读图推理用量</td></tr>
      <tr><td>培训交付</td><td>现场培训与手册</td><td>2 场×3600</td><td>7,200</td><td>管理端+现场端</td></tr>
      <tr><td>运维支持</td><td>远程运维（6 个月）</td><td>6 月×2600</td><td>15,600</td><td>5×8 小时</td></tr>
      <tr><td colspan="3"><strong>合计（含税）</strong></td><td><strong>449,400</strong></td><td><strong>人民币肆拾肆万玖仟肆佰元整</strong></td></tr>
    </tbody></table>

    <h2 class="section-header" id="s5">五、产出测算（收益口径）</h2>
    <table class="data-table"><thead><tr><th style="width:22%">收益项</th><th style="width:34%">测算公式（访谈口径）</th><th style="width:20%">年化收益（100% 达成）</th><th>备注</th></tr></thead><tbody>
      <tr><td>返工损失减少</td><td>45 万元/月 × 12 × 30%</td><td>162 万元</td><td>对应 AC-04 版本正确率 100%</td></tr>
      <tr><td>人工复核节省</td><td>85 单/月 ×（90−30 分钟）× 12 ÷ 8 小时 × 1500 元/人日</td><td>约 11.5 万元</td><td>对应 AC-06 核对时长下降 60%</td></tr>
      <tr><td>周期缩短的资金/工期收益</td><td>确认周期 12→6 天，按每月 85 单占压缓释</td><td>保守不计入</td><td>对应 AC-05，仅作定性收益</td></tr>
      <tr><td>签证采用率提升</td><td>补签 3 周→3 天</td><td>保守不计入</td><td>对应 AC-08，利润正向项</td></tr>
      <tr><td><strong>合计（可量化）</strong></td><td>返工 + 人力</td><td><strong>约 177 万元/年</strong></td><td><strong>50% 保守达成口径 ≈ 88 万元/年</strong></td></tr>
    </tbody></table>

    <h2 class="section-header" id="s6">六、投入产出比与回收期</h2>
    <table class="data-table"><thead><tr><th style="width:14%">档位</th><th style="width:14%">投入</th><th style="width:22%">回收期（50% 保守）</th><th style="width:22%">回收期（100% 达成）</th><th>首年 ROI（50% 保守）</th></tr></thead><tbody>
      <tr><td>低档</td><td>18.5 万元</td><td>约 2.5 个月</td><td>约 1.3 个月</td><td>约 376%</td></tr>
      <tr><td>中档（推荐）</td><td>28.6 万元</td><td>约 3.9 个月</td><td>约 1.9 个月</td><td>约 208%</td></tr>
      <tr><td>高档</td><td>44.9 万元</td><td>约 6.1 个月</td><td>约 3.0 个月</td><td>约 96%</td></tr>
    </tbody></table>
    <p class="body-para">测算按月均收益折算（保守口径 88 万/年 ≈ 7.3 万元/月；100% 口径 177 万/年 ≈ 14.8 万元/月），回收期 = 投入 ÷ 月均收益。三档回收期均小于 1 个财年季度窗口的一半，风险可控；中档在"验收闭环完整度"与"投资回收速度"之间平衡最优，故为推荐档位。</p>

    <h2 class="section-header" id="s7">七、商务条款与建议</h2>
    <p class="list-para">- <strong>付款方式：</strong>合同签订 50%、试点验收通过 50%（与既有报价单一致）；高档可改为 40%/30%/30%（M2 上线、M4 验收、扩展项交付）；</p>
    <p class="list-para">- <strong>不含项：</strong>业主侧系统对接改造、电子签章年费、私有化部署另行核算；</p>
    <p class="list-para">- <strong>基线修正条款：</strong>合同约定 M1 里程碑后以真实基线修正 AC-05/08 目标值与本测算，双方书面确认；</p>
    <p class="list-para">- <strong>验收否决项：</strong>安全合规一票否决（AI 不自动批准、不直写业务系统）不达标不进入尾款支付；</p>
    <p class="list-para">- <strong>推荐路径：</strong>首签中档 3 个月试点；试点达标后，R5/R6 以扩展合同方式并入（即高档增量部分，价格不变）。</p>
  </section>
"""

os.makedirs(OUT, exist_ok=True)
io.open(f"{OUT}/stage2-formatted-详细项目设计方案.html", "w", encoding="utf-8").write(
    page("详细项目设计方案：工程变更与签证协同", d10_body))
io.open(f"{OUT}/stage2-formatted-报价与投入产出测算.html", "w", encoding="utf-8").write(
    page("报价与投入产出测算：工程变更与签证协同", d11_body))
print("both html written")
