---
artifact: 17-test-plan
owner: qa
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [dev-lead, product-manager, orchestrator]
gate: G-QA-01
---

# 测试计划与用例 · 极境 ZenithLens（OpenCode 独立重做 · S5 重跑 · 契约 v5）

> 上游依据：`PROJECT_BRIEF.md`（§4 失败定义 / §5 核心逻辑 / §9 40 组件）、
> `docs/00-charter/02-prd.md`（v3，F-01..F-17 + R-UI-01..40）、`docs/00-charter/03-ui-design.md`（v3 §8 追溯矩阵）、
> `docs/01-architecture/09-api-contract.md`（v5）、`docs/04-integration/15-code-review.md`（v2）。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。**本文件只定义用例，结果见 `18-test-report.md`。**
> **本轮 skill**：`test-scenarios`（从用户故事/验收标准推场景，强制补正常/边界/异常三件套）、
> `diagnosing-bugs`（缺陷必填根因：先复现→最小化→3~5 假设→定位，禁"疑似"）。
> 按 `capability-map §6` 纪律：skill 只供方法与检查项，**不改变** 17/18/04 的工件结构与 G-QA-01/02 判据。

## 摘要

1. 范围 = Brief §9 的 **40 项特调组件（R-UI-01..40，全 P0）** + PRD 的 **11 个 P0 功能点（F-01..F-11，各 ≥3 条正常/边界/异常）** + **数值口径正确性用例 N-01..N-24** + 交互/CRUD（C-*）。
2. 方法：**实起 `python app.py`(8791) + 真实浏览器（Chrome for Testing）遍历 7 Tab** 采集 DOM 证据，后端逐接口 curl/urllib 复核，全部结果落 `docs/05-qa/evidence/`。
3. 数值类用例单列（N-*）：金融类产品数字错即 P0，界面崩可重试、数字错用户会据此决策。
4. 通过标准（G-QA-02）：**P0 用例 100% 通过、P1 ≥90%、无未关闭致命/严重缺陷**；数据错误一律 P0。
5. 边界：不改产品代码/契约、不改 `runtime/**`、不派发子任务；CRUD 实操后**还原数据**；测毕停服、无孤儿进程。

## 正文

### 1. 环境与前置条件

| 项 | 值 |
|---|---|
| 应用 | `python app.py`，`DEFAULT_PORT=8791`（`app.py:38`），纯标准库，Python 3.8.6 |
| 数据根 | `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json`（22 只持仓） |
| 契约 | `09-api-contract.md` **v5**（53 接口 + /health = 54 路由，`ROUTES` 实测 54） |
| 浏览器 | Chrome for Testing `chromium-1243\chrome-win64\chrome.exe`（`--headless=new --remote-debugging-port=9222`），经自建 CDP 客户端驱动 |
| 浏览器驱动说明 | `agent-browser` daemon 握手失败（`Chrome exited early exit code 3`），按派发约束**改 CDP 直连**，如实登记 |
| 证据目录 | `docs/05-qa/evidence/`（接口 JSON、逐 Tab 截图、`ui_components.json`、`numeric_checks.json`、`crud_checks.json`） |
| 测试数据 | 只读真实数据；CRUD 用临时代码 `999998`，测后删除并核对还原 |

### 2. 测试策略（`test-scenarios` 方法落地）

对每个 P0 功能/组件，按「**测试目标 → 起始条件 → 角色 → 步骤 → 期望 → 边界与错误场景**」六段推导，强制三类：

| 类型 | 含义 | 本文编号前缀 |
|---|---|---|
| 正常 | 典型操作路径 | `*-N` |
| 边界 | 空集/单条/0 值/极值/阈值 | `*-B` |
| 异常 | 外部失败（超时/500/文件缺失/离线） | `*-E` |
| 口径 | 数值与后端一致（±0.01% / 逐字段） | `N-*`、`*-C` |

### 3. 数值口径正确性用例（N-01..N-24 · 金融产品生命线）

> 全部以**后端 API 原值**做算术复算，禁止"看着对"。断言脚本：`evidence/scripts/numeric_checks.py`，结果 `evidence/numeric_checks.json`。

| 用例ID | 类型 | 检查项 | 期望（口径） |
|---|---|---|---|
| N-01 | 口径 | 总资产 | `total_value == Σ rows.market_value`（±0.02 元） |
| N-02 | 口径 | 收益率 | `return_rate == total_pnl_amt / (total_value − total_pnl_amt)`（±0.0002） |
| N-03 | 口径 | 覆盖计数 | `covered_count == total_count == 22` |
| N-04 | 边界 | 未知≠持平 | 存在 `change_rate=null` 行；null 与 `0` 语义区分 |
| N-05 | 口径 | 估值徽章来源 | `valuation.valuation_mode ∈ {official,intraday,holdings,proxy,unknown}` |
| N-06 | 口径 | 降级链路 | `valuation.trace_text` 非空且含五档顺序 |
| N-07 | 口径 | MAE 口径（ratio→%） | `0.002→0.20%`、行业基准 `0.008→0.80%` |
| N-08 | 口径 | `effect_pp` 单位 | 单位=百分点，`E3=3.9→+3.90pp`（禁再 ×100） |
| N-09 | 口径 | 冻结 `N_w` | `[5,10,15,30,60,120]` |
| N-10 | 口径 | 窗权重 | `[8,22,15,10,30,15]` |
| N-11 | 口径 | 冻结常量 | `K=4 / p=0.25 / MIN_N=15 / SHRINK=10 / BAND=0.02` |
| N-12 | 异常 | 无开口不表态 | 三窗口 `weighted_p=null` 且 `direction=gray` |
| N-13 | 口径 | 加权口径 | `weighting_basis=market_value` 且策略说明非空 |
| N-14 | 口径 | 最小覆盖门槛 | `min_coverage_ratio=0.30 / min_open_count=3` |
| N-15 | 口径 | 覆盖度四档 | A/B/C/D 齐全，颜色由后端给 |
| N-16 | 口径 | `naive_p` 研究口径 | `naive_n>0` 即给值（**不受 MIN_N 门控**） |
| N-17 | 口径 | `naive_low_sample` | `naive_n<15` 为 `true` |
| N-18 | 边界 | 空样本不冒充 | `naive_n=0` 格 `P=null`（禁渲染 0/50%） |
| N-19 | 口径 | 立方体规模 | 5 层 × 25 = 125 格 |
| N-20 | **口径** | 对比卡「有效覆盖」 | 字段为 **ratio（0.92/1.0）→ 展示应为 92%/100%**（×100） |
| N-21 | 口径 | 对比卡统计 | 极端格 54→0，标准差与逐格一致 |
| N-22 | 口径 | 预测行字段 | `tier/market_value` 与 `/holdings` 逐只一致（无跨接口分叉） |
| N-23 | 边界 | 概率范围 | `p_up ∈ [0,1]`（小数非百分数） |
| N-24 | 口径 | 出口阈值 | `weighted_p_threshold = 0.52` |

### 4. P0 功能点用例（F-01..F-11 · 每个 ≥3 条正常/边界/异常）

| 用例ID | 功能 | 类型 | 步骤/输入 | 期望 |
|---|---|---|---|---|
| T-F01-N | F-01 资产总览 | 正常 | 打开持仓页 | 22 只汇总；四卡总额/今日/累计/收益非空，口径副标题可见 |
| T-F01-B | F-01 | 边界 | 持仓空集 / 仅 1 只 / 成本=0 | 空态四要素或占位；成本 0 时收益率显"—"，不显 `+Inf%`/脏值 |
| T-F01-E | F-01 | 异常 | `/holdings` 500 或断网 | 错误态文案 + 「重试」按钮，不白屏、不以 0 冒充 |
| T-F01-C | F-01 | 口径 | 复算 | 见 N-01/N-02 |
| T-F02-N | F-02 估值五档 | 正常 | 看估值来源列 | 五档枚举（官方/盘中/重仓/代理/未知）由 `valuation_mode` 驱动 |
| T-F02-B | F-02 | 边界 | 数据只有 proxy/unknown | 仅渲染实际档位，不补假档 |
| T-F02-E | F-02 | 异常 | 三源全失败 | 落 `unknown`，显「未知」，不显 0 |
| T-F02-C | F-02 | 口径 | 徽章语义 | mode 与徽章文案一一对应，无静态硬编码 |
| T-F03-N | F-03 徽章+降级链 | 正常 | 悬浮 `.vb` | title 含降级链路 trace + MAE + 方向命中率 + 样本数 |
| T-F03-B | F-03 | 边界 | `trace` 缺失 | 不崩，退化为未知徽章 |
| T-F03-E | F-03 | 异常 | `nav_date` 缺失 | 显"—"，不编造日期 |
| T-F03-C | F-03 | 口径 | `.ch/.cm/.cl/.cu` | 颜色类由 `confidence_color_class` 给 |
| T-F04-N | F-04 未知态渲染 | 正常 | 看 null 行 | `pct/今日盈亏 null → 未知/—` |
| T-F04-B | F-04 | 边界 | 恰好 0 | 渲染 `+0.00%`（与"未知"区分） |
| T-F04-E | F-04 | 异常 | 全部未知 | 页面不出现任何 `+0.00%` 冒充未知 |
| T-F04-C | F-04 | 口径 | 全站扫描 | `+0.00%` 计数 = 0（数据非空时） |
| T-F05-N | F-05 覆盖度 A/B/C/D | 正常 | 看 `.covbar` | 四档：只数/市值/占比 + 失效三类长文 |
| T-F05-B | F-05 | 边界 | B/C 档为 0 | 显 0 只 · ¥0.00，不隐藏档位 |
| T-F05-E | F-05 | 异常 | 档位未知 | 落 D 档「暴露待定」 |
| T-F05-C | F-05 | 口径 | 占比和 | 四档 `weight_ratio` 之和 ≈ 1 |
| T-F06-N | F-06 单只方向预测 | 正常 | 看 `/predictions/{code}` | `p_up∈[0,1]`，触发门/DDSM/否决/出口字段齐全 |
| T-F06-B | F-06 | 边界 | `gate=none` | 仍算 `p_up` 但不开口（`open=false`），不伪造方向 |
| T-F06-E | F-06 | 异常 | 数据缺失 | `signal=abstain` + `veto_data_missing`（A-05） |
| T-F06-C | F-06 | 口径 | 出口 | `P>0.52` 才 `up`，否则 `gray`；基线不裸报命中率 |
| T-F07-N | F-07 信号链路 6 步 | 正常 | 点预测行展开 | 弹窗 6×`.chain-item`（触发门→DDSM→拥挤度→KLOW2→出口→入账） |
| T-F07-B | F-07 | 边界 | 某层 `missing` | 标「数据缺失」，不省略、不编值 |
| T-F07-E | F-07 | 异常 | 无链路数据 | 显「无链路数据」 |
| T-F07-C | F-07 | 口径 | 每步指标 | 每步带具体数值（ret/vr/档位/P/z/分位/下影线比） |
| T-F08-N | F-08 组合加权预测 | 正常 | 看三窗口卡 | T+1/T+3/T+15 + 加权口径长文 |
| T-F08-B | F-08 | 边界 | 无开口 | `weighted_p=—`、覆盖 0.0%、明确"灰≠看平" |
| T-F08-E | F-08 | 异常 | 引擎离线 | 走 stale/error 四态，不以 empty 承载（A-06） |
| T-F08-C | F-08 | 口径 | 门槛 | 覆盖 ≥30% 且开口 ≥3 只才出方向；C/D 档不计入 |
| T-F09-N | F-09 台账 INSERT-ONLY | 正常 | 看影子台账 | 行 + 连续进度 0/60 + 字段说明 |
| T-F09-B | F-09 | 边界 | 空台账 | `not_started`，显「尚未启动」，不编记录 |
| T-F09-E | F-09 | 异常 | 尝试改台账 | 无 PUT/DELETE 路由（404） |
| T-F09-C | F-09 | 口径 | 回填 | 仅 `t1/t3/t15_real` 由 backfill 回填，原行不改 |
| T-F10-N | F-10 回测成绩 vs 基线 | 正常 | 看复盘页 | hero + 三窗口表（命中/基线/Δ） |
| T-F10-B | F-10 | 边界 | 未产出 | 显「待填充」，**不填估计值** |
| T-F10-E | F-10 | 异常 | 无成绩文件 | 空态「暂无成绩记录」 |
| T-F10-C | F-10 | 口径 | 基线 | 基线 = `max(恒涨,恒跌)`，报 Δ 非裸命中率 |
| T-F11-N | F-11 数据/部分可靠性 | 正常 | 看 livebar + 数据源 | livebar 显示已接入 + 数据源健康表 |
| T-F11-B | F-11 | 边界 | 某源 bad | livebar 提示「N 个数据源不通」 |
| T-F11-E | F-11 | 异常 | 引擎离线/快照滞后 | livebar warn + 滞后天数如实 |
| T-F11-C | F-11 | 口径 | 快照日期 | 与 `/runtime.staleness.latest_date` 一致 |

### 5. R-UI-01..40 逐项用例（全 P0 · 缺一即 G-FE-01 不通过）

> 每项至少覆盖：正常渲染 / 边界（空集/0 值/缺字段）/ 异常（接口失败） / 口径（数值来源）。结果与证据见 `18-test-report.md` §4。

| 用例ID | 组件 | 页 | 正常 | 边界 | 异常 | 口径/判定锚点 |
|---|---|---|---|---|---|---|
| T-UI-01 | 资产总览四卡+口径 | 持仓 | 四卡有值 | 空集/成本0 | 接口失败→错误态 | `#pa-*`；N-01/N-02 |
| T-UI-02 | 估值精度汇总 `.vsum` | 持仓 | chip 分组+加权 MAE vs 0.80% | MAE 缺失只显 chip | 全缺失 | `groups[].label/weight_ratio` |
| T-UI-03 | 估值徽章 `.vb` 五档+`.ch/.cm/.cl/.cu` | 持仓 | 徽章+悬浮 trace/MAE/命中 | trace 缺失→未知 | `nav_date` 缺失 | `mode_label/confidence_color_class` |
| T-UI-04 | 覆盖度 `.covbar`+失效三类 | 持仓 | 四档只数/市值/占比 | 档为 0 显 0 | 档未知→D | `tiers[].color` |
| T-UI-05 | 持仓明细表（分组/列显隐/T+2/未知≠持平） | 持仓 | 22 行分组；列 popover；T+2 标注 | null→未知/— | 接口失败 | `changeCell/pnlCell`；无 `+0.00%` 冒充 |
| T-UI-06 | 风险指标折叠区 | 持仓 | 展开才请求 | 数据不足显占位 | 请求失败 toast | `/holdings/risk` |
| T-UI-07 | 信号空态四要素 | 信号 | 监控 N/M、距上次、上次开口、上次结果 | 0/0 只 | 无记录 | `/signals/state` |
| T-UI-08 | 触发门 E1/E3 + E2/E4 剔除 | 信号 | 两门卡 | — | — | `pp()` 渲染 `±x.xxpp`（非 390pp） |
| T-UI-09 | 信号时间线 `.tl/.sigcard/.ev` | 信号 | 近 60 天时间线 | 空→占位 | 台账损坏 | `/ledger` |
| T-UI-10 | T+1 口径+三执行路径 | 分析 | 折叠区长文+三条路径 | — | 接口失败 | `/meta/definitions` |
| T-UI-11 | 三窗口组合卡+加权口径 | 分析/持仓 | 三卡+三条加权规则 | 无开口显 0% | 服务失败 | A-08 字段 |
| T-UI-12 | 参与预测持仓表 | 分析 | 10 行（档/触发/P/否决/三窗口/市值） | 无开口行 | 失败→占位 | `/predictions` + tier/mv |
| T-UI-13 | 推导链 `.chain/.chain-item` 六步 | 分析 | 点行→弹窗 6 步 | 某步 missing | 无链路 | `/predictions/{code}` |
| T-UI-14 | 因子四盘+因子行+跑分表 | 因子 | 四盘 rule 长文 | 盘为空显「当前为空」 | 账本损坏 | `/factors/pans` |
| T-UI-15 | 四本账本+示例 | 因子 | 4 账本用途+字段 | 无记录 | 文件缺失 | `/factors/books` |
| T-UI-16 | 评分链长文 | 因子 | k_lift 悬崖+bootstrap+四裁判 | — | — | `/factors/score-chain` |
| T-UI-17 | 治理周期卡 | 因子 | 5 周期卡 | — | — | `/factors/governance-cycle` |
| T-UI-18 | 最近挖掘记录 F1/F2/F3 | 因子 | 表头字段齐 | 无记录 | — | `/factors/dig-records` |
| T-UI-19 | 生命周期规则长文 | 因子 | 准入/牌照/淘汰/双出口/防误杀/冷冻 | — | — | `/factors/lifecycle` |
| T-UI-20 | HUD 六卡 | 引擎 | 6 卡+HUD 值 | 影子盘 idle | 引擎无响应 | `/engine/status` |
| T-UI-21 | 影子盘台账+进度+字段 | 引擎 | 表+0/60 进度 | 空台账 | — | `/ledger/shadow` |
| T-UI-22 | 因子竞技场矩阵 | 引擎 | 行=配置/列=六窗/legend | 空集诚实 | 无数据 | `color_scheme/prefix` |
| T-UI-23 | 训练状态卡 | 引擎 | 125 格/样本/加噪/死路 | — | — | `/engine/training-status` |
| T-UI-24 | 冻结参数表 | 引擎 | 全参数只读 | — | — | N-09/10/11 |
| T-UI-25 | 六维输入 z-bar | 引擎 | 3+6 维 z-bar | 资产无数据 | 接口失败 | `/engine/inputs` |
| T-UI-26 | 125 格立方体 naive/DDSM | 引擎 | 生产 ddsm 默认+研究 naive 折叠+对比卡 | n=0 无样本格 | 未训练 | **N-19/20/21**；`color_band` |
| T-UI-27 | 引擎注册表三态 | 引擎/设置 | active/shadow/retired | 无版本 | — | `/engine/registry` |
| T-UI-28 | 历史成绩 hero | 复盘 | 命中+基线+Δ | 待产出 | 无成绩 | `/review/scores` |
| T-UI-29 | 三窗口 vs 基线 | 复盘 | 三行（待填充留空） | 未产出 | 无文件 | `baseline_status=pending` |
| T-UI-30 | 影子盘降级审查条 | 复盘 | idle/ok/bad | idle | — | `/engine/shadow-review` |
| T-UI-31 | 逐笔对账表 | 复盘 | 字段齐 | 无记录 | — | `/review/reconciliation` |
| T-UI-32 | 隐私开关 | 设置 | 金额打码，占比/涨跌保留 | 刷新保持 | 存储失败不阻塞 | `body.masked` + `.amt` |
| T-UI-33 | LLM 接口+三硬约束+温度0 | 设置 | 服务商/Base/模型/Key | Base 空可存 | 非法 URL→错误 | `base_url` GET/PUT 往返 |
| T-UI-34 | 数据源健康表 | 设置 | 4 源+状态/时间/失败数 | unchecked | 全不通 | `/data-sources/health` |
| T-UI-35 | 持仓数据卡+不一致长文 | 设置 | 源路径/只数/一致性+偏差实证 | 文件缺失提示 | 读取失败 | `/settings/holdings-data` |
| T-UI-36 | 关于卡 | 设置 | 版本/引擎/存储/审计/免责 | — | — | `/about` |
| T-UI-37 | 三 dialog+popover+toast | 全域 | 录入/加仓/删除确认 | 非法代码 toast | 重复录入 toast | DOM 存在 + CRUD |
| T-UI-38 | 注销 Service Worker | 全域 | 进页注销 SW | 不支持时 try/catch | — | `main.js:18-23` |
| T-UI-39 | livebar 真实数据接入条 | 全域 | 接入状态+快照 | 引擎离线 warn | 源不通提示 | `/runtime`+health |
| T-UI-40 | 四态覆盖各页 | 全域 | 成功态 | 空态 | 错误/加载态 | `mountState` + `emptyWhen` 接线 |

### 6. 交互与 CRUD 用例（C-01..C-16）

| 用例ID | 类型 | 步骤 | 期望 |
|---|---|---|---|
| C-01 | 正常 | `POST /holdings` 建档 | 201，返回新行 |
| C-02 | 正常 | 建档后查询 | 22→23 |
| C-03 | 异常 | 重复代码建档 | 409 `E_CONFLICT` |
| C-04 | 异常 | 非法代码（非 6 位） | 400 `E_VALIDATION` |
| C-05 | 正常 | `PUT` 改名/份额 | 200，回读一致 |
| C-06 | 正常 | `GET` 单条 | 更新后值 |
| C-07 | 异常 | 不存在代码 | 404 `E_NOT_FOUND` |
| C-08 | 正常 | `DELETE` | 返回 `deleted_code` |
| C-09 | 还原 | 删除后核对 | 22 只、总额一致 |
| C-10 | 异常 | 重复删除 | 404 |
| C-11 | 正常 | `llm.base_url` PUT→GET | 往返持久化 |
| C-12 | 异常 | 非法 base_url | 400 `E_VALIDATION` |
| C-13 | 还原 | base_url 复位 | 与初值一致 |
| C-14 | 异常 | `PUT/DELETE /ledger/entries` | 404（INSERT-ONLY） |
| C-15 | 正常 | 隐私开关切换 | 打码开→关，状态持久化 |
| C-16 | 正常 | 推导链弹窗 | 6×`.chain-item` |

### 7. 判定标准

- **G-QA-01（本计划）**：存在 R-UI-01..40 逐项用例；P0 功能每个 ≥3 条（正常/边界/异常）；含数值口径用例。
- **G-QA-02（执行后）**：P0 用例 100% 通过、P1 ≥90%、无未关闭致命/严重缺陷；数据错误一律 P0。
- 失败用例必须可稳定复现并附证据（截图/接口原文），否则无效。

## 自验收

- [x] R-UI-01..40 逐项用例已列（§5，40/40）
- [x] P0 功能 F-01..F-11 每个 ≥3 条正常/边界/异常（§4）
- [x] 含数值口径正确性用例（§3，N-01..N-24）
- [x] 含交互/CRUD 用例（§6）
- [x] 每条用例给了期望（可判定的口径/字段/阈值），实际结果留待 `18-test-report`
- [x] 使用并声明 skill：`test-scenarios`、`diagnosing-bugs`
- [x] 未修改产品代码 / `09-api-contract` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `dev-lead`**：按本计划核对 `18-test-report.md` 的未通过项与 `04-defects.md`，用 `triage` 分流。
- **次消费方 `product-manager`**：§3 口径用例与 §5 R-UI 用例可直接复用为 G-PM-05 终验走查清单。
- **残留风险**：
  1. 空集/错误态多依赖「四态演示条」触发，真实空数据无法就地构造（责任人 qa，期限：下轮补数据夹具）。
  2. 契约版本 v4/v5 标注不一致（见 `04-defects.md` D-03），影响范围待 dev-lead 定性。
  3. 数值用例 N-20 已预判口径风险（ratio×100），执行前不作结论，以实测为准。
