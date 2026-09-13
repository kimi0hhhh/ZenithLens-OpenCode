---
artifact: 07-frontend-arch-r2
owner: architect
version: v3.1
status: draft
supersedes: 07-frontend-arch.md（R1 基线 v4）
created: 2026-09-12
reviewers: [product-manager]
gate: G-AR-03
---

# 前端架构 · 极境 ZenithLens（R2 升级轮增量）

> 本文是 `07-frontend-arch.md`（R1 v4）的**增量设计**：只写 R2 变更（U-01..U-12 的组件/状态/接口支撑），未变部分（目录结构、单一 store、api.js 唯一出口、format.js、StateBlock 四态容器、命脉组件三件）**沿用 R1 v4，不重抄**。
> 上游：`03-ui-design-v3.md` §3（U-01..U-12）与 §4（四态全量定义）、`04-ui-wireframe-v3.html`；字段法律：`09-api-contract-r2.md` **v9.1**。
> 硬约束延续：零第三方依赖、无构建、原生 ES module；所有请求经 `api.js`；数值只经 `format.js`；**禁止 mock/假数据进生产路径**。
> **v3.1（2026-09-12 · 会签收敛）**：按 09 v9.1 同步——vsum 主指标改读 `estimate_quality.weighted_mae_rate` + 官方档单列 chip（D-1）；`history_days` 展示位（Q3）；D① 档文案「暴露待定」+ `verify_review_date`/待结论清单（D-4）；`scores[].sample_window` 注明（R-2）；`conf_reason` 五值（R-4）。

## 摘要

1. R2 前端 = **12 项升级点的组件级增量**（U-01..U-12），落在 16 个既有组件触点（03-ui §8 的 15 行，28/29 合行）上；**目录结构零变更**（views/ 7 个 + components.js 扩容，不新增视图）。
2. 三条命脉升级：成绩位出数（U-01，读 `/review/scores` v9 字段）、徽章双层编码 + `conf_reason` 解释层（U-02）、回填态激活（U-04，读 `t1_real`/`result`/事件链第⑥步）。
3. 四态升级为**真实触发**（U-03）：7 页 `emptyWhen` 逐页重定义（§4 表），success 前不得渲染任何数字、error 不得回退示例数据（沿用铁律）。
4. 基准补课（对照 legacy v2）：sticky 表头、`:focus-visible` 焦点环、Esc + 焦点回位、fold hover（U-09/U-10，纯 CSS + dialog.js 增量）。
5. 文案单一来源：`copy.js` 扩容为**文案字典实现层**（U-12），新增 `conf_reason` **五值** / `verify_status` 五值（含 `not_applicable`「暴露待定」）/ `backfill_method_note` / `low_frequency_note` 文案映射；组件不得硬编码。

## 正文

### 1. 改动概览（U 升级点 × 文件 × 接口字段）

| U | 升级点 | 文件（落点） | 消费字段（v9） |
|---|---|---|---|
| U-01 | 成绩位填充 | `views/review.js`（hero/三窗口）、`views/engine.js#renderCube`（对比卡）、`views/factors.js`（空盘） | `/review/scores`：`hero.{hit_rate,baseline_rate,delta_pp,open_count,sample_period,data_kind}`、`note`、`scores[]`、`baseline_status`；`StateCube.comparison.walk_forward_delta_*` |
| U-02 | 双层徽章 + 全口径 tooltip | `components.js#valBadge`、`views/holdings.js`（vsum） | `valuation_mode`/`mode_label`/`confidence_color_class`/`confidence_label`/`trace_text`/`mae_rate`/`dir_hit_rate`/`n_test`/`accuracy_window_days`/`conf_reason`/`trace[holdings].detail.{report_date,covered_weight_pct}`；`/valuations/precision.{groups[].label,weighted_mae_rate,window_filled_days,window_status_label}` |
| U-03 | 四态全量接线 | 7 个 `views/*.js`（emptyWhen） | 各页真实数据条件（§4） |
| U-04 | 回填态激活 | `views/signals.js`（时间线/事件链）、`views/review.js`（对账）、`views/analyze.js`（推导链第⑥步复用） | `LedgerEntry.{t1_real,result,t1_real_method}`、`/ledger/chain` 第⑥步 |
| U-05 | 影子盘进度真实化 | `views/engine.js`、`components.js#progressBar` | `ShadowProgress.{consecutive_days,target_days,archive_merged,history_days,window_days,baseline_source}` |
| U-06 | 数据源健康升级 | `views/settings.js`、`views/holdings.js`（设置卡） | `/data-sources/health.{fail_window_7d,fail_window_days,recent_failures}`；`/runtime.staleness`；`/settings/holdings-data.{main_source,import_available,import_disabled_reason}` |
| U-07 | C 档验证四态 | `views/holdings.js`（行内标签） | `HoldingRow.{verify_status,verify_status_label,verify_batch_id,verify_note,tier_reason}` |
| U-08 | QDII 领先标注 | `views/holdings.js`、`views/signals.js` | `HoldingRow.qdii_lead_note`、`PredictionSummary.qdii_lead_note` |
| U-09 | sticky 表头 | `css/app.css`（全站 `thead th`） | —（纯样式） |
| U-10 | 键盘与焦点 | `css/app.css`、`components.js#dialog` | —（纯交互） |
| U-11 | 数字口径悬浮统一 | `components.js`（新增口径 tip 帮助函数）、各视图关键数字 | 各字段口径（09 §2/§3） |
| U-12 | 文案字典纪律 | `copy.js`（字典实现层） | `conf_reason`/`verify_status` 等文案映射 |

### 2. 组件增量设计

#### 2.1 `ValBadge`（U-02）— 双层编码 + 7 项 tooltip
- **第一层（来源底色）**：由 `valuation_mode` 映射 `.vb.l0~.l3`（official/intraday=绿系、holdings=金、proxy=灰、unknown=虚线灰；与 03-ui §2 对齐）；**第二层（置信度描边）**：沿用 `confidence_color_class`（`ch/cm/cl/cu`）。两层独立 class 拼接，**不得合并成一个颜色**。
- **tooltip 组装（固定 7 项，缺项留白不编造）**：① 来源说明（`mode_label`/`source_label`）② 降级链路（`trace_text`，缺失只显示 mode）③ MAE（`mae_rate` 小数→format）④ 方向命中率（`dir_hit_rate`）⑤ 样本数（`n_test`）⑥ 回测窗（`accuracy_window_days`=40）⑦ 披露口径（`trace[holdings].detail.report_date` + `covered_weight_pct`；非 holdings 档不显示该行）。
- **unknown 原因**：`confidence=unknown` 时 tooltip 必显 `conf_reason` 文案（copy.js **五值**映射：mode_unknown/budget_exceeded/valuation_missing/nav_missing/no_samples）；**禁止裸"未知"**。
- 点击展开当日入账历史（R1 已有）保留；`qdii_correction`（非 null 时）追加一行「QDII 校正：双段/单段（原因）」，`note` 直出。

#### 2.2 `vsum` 估值精度条（U-02/U-01；v3.1/D-1 修订）
- **主指标改读 `estimate_quality.weighted_mae_rate`（估算档：intraday/holdings/proxy）**；官方档以「既成事实」单列 chip（`official_summary.{count,weight_ratio}`），**不混入主指标**；全档 `weighted_mae_rate` 仅作参考展示并标注「全档参考」。
- 估算档分组 chip 读 `estimate_quality.groups[].label`（高/中/低/无）；主指标为 null 时显示「暂无法计算」+ 原因 chip（由 `estimate_quality.groups` 空组/`conf_reason` 归因，前端不推断口径）。
- 追加「累计 `window_filled_days`/40 日」标注（`window_status_label` 直出）；`window_phase` 驱动「首判就绪/终判就绪」文案。

#### 2.3 成绩位（U-01）
- `review.js#renderHero`：命中率/基线/Δ 三段式；`hero.data_kind` 显示「回测」/「实盘」tag（沿用现有 visual 区分）；`hero.open_count`、`hero.sample_period` 以 mini 文案展示；`note` 直出。
- 三窗口行：`baseline_status=pending` → 「待填充」样式（`.flat`），数值 null；**不得出现估计值**（负向断言）；`sample_window`（恒 `full`）以口径注展示「全样本窗」，**不得与因子页六样本窗混用**（v3.1/R-2）。
- 立方体对比卡：`walk_forward_delta_*` 为 null → 「待复现」标注（禁止填数）；出数后按 `delta` 格式化。
- 因子页空盘：「（当前为空）」保留，不得用 legacy 示例数字。

#### 2.4 回填态（U-04）
- 时间线 `.tl-item`：`result=hit/miss` 着色；`pending` 仅当 `t1_real=null`；`t1_real_method` 驱动 tooltip「命中判定=代理 ETF 涨跌方向」。
- 对账表判定列同上；事件链第⑥步：`output` 步 detail 由后端给（回填值/待回填），前端不编造。
- 刷新一致性：状态来自后端响应，不做前端缓存假象。

#### 2.5 影子盘进度（U-05）
- 进度条 `consecutive_days/target_days`（真实 x/60）；口径注「归档合并计算」当 `archive_merged=true`，否则「按主文件计算（归档不可读）」；**副文案/tooltip 展示 `history_days`**（「可用历史 X 日（含归档）」——「可达 ≥60」的唯一 UI 证据，v3.1/Q3）。
- HUD 影子盘状态字读 `shadow_status` 进度枚举（R2 后端已切）；「达标/降级」读 `shadow_audit_status`（分离表达，沿用 engine.js 现有 PROGRESS_TAG/AUDIT_TAG）。
- 台账表列由 `field_list` 驱动（v9 含 `t1_real_method`）；`insert_only_note` + `backfill_method_note` 展示。

#### 2.6 数据源健康（U-06）
- 失败计数展示 `fail_window_7d` + 「近 7 日失败 n 次」标签；`recent_failures` 折叠区（历史审计）；累计 `fail_count` 仅折叠区内注「累计历史」。
- 新浪行按实测三态 + 时间戳渲染（后端 `record_source` 自然留痕）。
- nav 滞后读 `/runtime.staleness`（≤1 交易日显示正常态）；持仓数据卡：主源状态读 `main_source`；导入按钮 `import_available=false` → 禁用 + `import_disabled_reason` 直出（不出现 E_IO 堆栈）。

#### 2.7 验证状态（U-07；v3.1/R-3+D-4 修订）
- 行内标签（`verify_status` + `verify_status_label`）：待验证（灰）/ 验证中（金，带 `verify_batch_id`）/ 已验证（绿，note 含升 B 日期）/ 验证未通过（红，`verify_note` 原因）/ **D①「暴露待定」（`not_applicable`，不读作"待验证"）**；tooltip 直读 `tier_reason`。
- **挂档观察行**：显示 `verify_review_date`（复查日）+ 样本量；复查日同步出现在覆盖面板「待结论清单」（`pending_verification_names`）；挂档行不计入「已验证/预测覆盖增长」的展示口径。
- 升 B 后行内档位与信号列同步（数据刷新后重渲染，不做前端推导）。

#### 2.8 QDII 标注（U-08）
- 持仓 QDII 行与信号卡：`qdii_lead_note` 非 null 时渲染 chip；文案后端产出（前端不硬编码「1–2 天」数字）。

#### 2.9 长表与可访问性（U-09/U-10）
- `app.css`：`thead th{position:sticky;top:0;z-index:2;background:rgba(248,249,246,.94);backdrop-filter:blur(10px)}`；`:focus-visible` 焦点环（`outline:2px solid var(--ink); outline-offset:2px`）；`details.fold>summary:hover` 反馈；`prefers-reduced-motion` 下动画降级为静态。
- `dialog`：Esc 关闭 + 焦点回位（记录触发元素）；toast `aria-live="polite"`。
- 旧内核不支持 sticky → 普通表头（不报错，降级路径已在 03-ui §6 声明）。

#### 2.10 数字口径悬浮（U-11）与文案字典（U-12）
- `components.js` 增统一口径标签帮助函数（tooltip = 「分子/分母或样本/窗口/来源」模板）；总资产/今日盈亏/累计收益/收益率/加权 P/覆盖占比/Δ/MAE/进度等关键数字接入。
- `copy.js` 字典表扩充（词 × 场景 × 禁止）：`未知 / — / 待填充 / 待回填 / 不表态 / 低样本 / 数据缺失`（R1 已有）+ **v9/v9.1 新增映射**：`conf_reason` **五值**、`verify_status` 五值、`accuracy_window_phase` 三值、`shadow_status` 四值、`qdii_fallback_reason` 三值、`backfill_method_note`/`low_frequency_note` 由后端直出（前端只做兜底）。“既成事实”作为官方档口径词条入字典（v3.1/D-1）。新增文案必须先入字典再进组件。

### 3. 状态与数据流

- **store 切片零新增**：复用 `scores/recon/shadowReview/engineStatus/holdings/ledger/...`；`review.js` 增加 `data_kind` 参数透传（/review/scores 默认 backtest）。
- 轮询不变（引擎 12s、任务 2s）；`/review/scores` 不轮询（随页面激活拉取）。
- `mock/mock.js` 仅测试隔离用（默认关闭）：R2 需同步 v9 字段形状（`shadow_status` 已是进度枚举；补 `conf_reason`/`verify_*`/`import_*` 字段形状），**不得进入生产路径**。

### 4. 四态全量定义落地（emptyWhen 逐页，对应 03-ui §4 表）

| 页 | emptyWhen 真实条件（前端判定） | 文案来源 | 加载/错误 |
|---|---|---|---|
| 持仓 | `rows.length === 0`（非"全部未知"） | `StateBlock` + 数据源路径 + 录入按钮 | 骨架 / 「读取持仓失败：<原因>」+ 重试 |
| 分析 | 监控集合为空 或 全部资产无预测记录 | 「今日没有触发开口的资产」+ 四要素事实卡 | 三窗口脉冲 / 原因 + 重试 |
| 信号 | 台账为空 → 变体①；有台账但窗口内无开口 → 变体② | 变体①「影子盘尚未开始记录」；变体② `empty_note`/`low_frequency_note` | 「正在读取信号台账…」/ 原因 + 重试 |
| 因子 | 四盘均无因子 | 「因子库为空，等待首次扫描」 | 盘面骨架 / 缺失文件名 |
| 复盘 | 无成绩缓存或全窗口 pending | 「尚无成绩记录，引擎未产出回测」+「待填充≠0」 | hero 脉冲 / 原因 + 重试 |
| 引擎 | 引擎心跳缺失 | 「引擎离线」+ 最近成功时间 | 「正在连接本地引擎…」/ 错误码 + 重试 |
| 设置 | 数据源从未检测 | 「尚未检测数据源」+「立即检测」 | 行内「检测中…」/ 配置读写失败不丢已填 |

**硬断言（QA 负向）**：`empty` 态不得渲染任何数字行；`error` 态不得回退示例数据；`+0.00%` 零出现（`unknown` 走 `UnknownCell`）；`待填充/待回填` 不得出现在已接通/已到期场景。

### 5. 数值展示口径增量（与 09 §2 一致）

- `QdiiCorrection.*.value`、`mae_rate`、`dir_hit_rate` 等比率 → `format.js` ×100 保留 2 位带符号；`weight_pct`（detail 内）为**百分数直显**（沿用 v8 §5.38 单位例外，不加 ×100）。
- `window_filled_days`/`history_days`/`open_count` → 整数；`sample_period` 字符串直显。
- 新字段一律经 `format.js`，组件不得自实现（沿用 v4 §5 硬规则）。

### 6. 错误处理与可观测性（沿用 + 扩展）

- `api.js` 错误映射不变；新增错误文案走 `copy.js`（如导入源缺失的禁用说明不经 error 通道，走 `import_disabled_reason`）。
- 前端 console 不输出金额/密钥（沿用）；可观测性仍由后端 `/runtime`、`/data-sources/health`、`/engine/status` 提供。

## 自验收

- [x] 12 项升级点（U-01..U-12）逐项给出组件/状态/接口支撑（§1/§2），全部字段引用 09 v9
- [x] 目录结构零变更；状态管理（单一 store + 订阅）沿用，仅说明新增参数与字段消费
- [x] 四态全量接线给出 7 页 `emptyWhen` 真实条件表（§4），含加载/错误文案与负向断言
- [x] 不倒退声明：涨红跌绿 / 未知≠0.00% / 隐私打码 / 徽章 mode 驱动 / INSERT-ONLY 无入口 / 灰不加权 均未触碰
- [x] legacy v2 基准三处（sticky / focus / fold-hover）补齐路径明确（§2.9）
- [x] 文案字典（`conf_reason`/`verify_status`/`shadow_status` 等）单一来源 `copy.js`，组件不硬编码
- [x] 未写实现代码（仅组件规格与伪代码级说明）；未修改 R1 既有工件；未触碰 `runtime/**`
- [x] 残留风险与降级路径逐条列出（下游交接）
- [x] **v3.1 会签收敛同步**：vsum 主指标/官方 chip（D-1）、`history_days` 展示（Q3）、D① 文案与复查日/待结论清单（D-4/R-3）、`sample_window`（R-2）、`conf_reason` 五值（R-4）——全部以 09 v9.1 为准

## 下游交接

- **主消费方**：`frontend-dev`。按 §2 逐组件落地；U-01..U-12 与 03-ui-v3 §8 触点表**双向自检**；所有字段直读 09 **v9.1**，缺失一律"—"/留白，**不得本地推算**。缺一即 G-FE-01 不通过。
- **次消费方**：`qa`。用例重点：四态真实触发（§4 表）；`conf_reason` unknown 文案（五值）；双层徽章同屏可区分；**vsum 主指标=估算档、官方 chip 单列**；hit/miss 与 `t1_real` 符号一致；sticky/focus/Esc 三处；`+0.00%` 负向；`待填充` 无估计值；`import_available=false` 禁用路径；挂档行 `verify_review_date` 展示与「不计覆盖增长」。
- **残留风险**（责任人 / 期限）：
  1. 旧内核（老 WebView）sticky/`backdrop-filter` 可能不生效 → 已定义降级为普通表头，不阻塞（frontend-dev，S4）。
  2. 立方体对比卡走前 Δ 若 R2-11 未延伸产出 naive/ddsm 两变体 → 保持「待复现」标注（architect + backend-dev，S5 前评估是否纳入）。
  3. `verify_status` 四态的批次节奏依赖 R2-06 批次执行 → 批次未完成时统一「验证中」（product-manager，S3 复核）。
  4. `conf_reason` 文案与后端**五值**枚举的最终一致性 → 以 09 v9.1 为准，若后端实现新增理由须版本 +1（frontend-dev + architect，S3）。
- **未覆盖**：契约逐字段（`09-api-contract-r2`）、后端算法（`08-backend-arch-r2`）、系统五问（`06-system-arch-r2`）、会签问题（`10-arch-review-r2`）。
