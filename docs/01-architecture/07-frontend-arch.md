---
artifact: 07-frontend-arch
owner: architect
version: v4
status: approved
supersedes: v3
created: 2026-09-12
reviewers: [frontend-dev, dev-lead, product-manager]
gate: G-AR-03
---

# 前端架构 · 极境 ZenithLens

> 上游：`docs/00-charter/03-ui-design.md`、`docs/00-charter/04-ui-wireframe.html`、`docs/01-architecture/06-system-arch.md`。
> 约束（Brief §5.3）：**零第三方依赖、无构建步骤**——原生 HTML/CSS/ES2019 JS，由 `server/` 静态托管。
> 本文落地 UI 设计的四态与三个命脉组件；字段口径以 `09-api-contract.md` 为唯一法律。
>
> **v3 重跑方法（skill 驱动）**：
> - `codebase-design`：§2 模块划分改用**深模块词汇**（Module / Interface / Seam / Adapter / Depth），§2.2 给出**接缝地图**与删除测试。
> - `domain-modeling`：术语以 `05 §0` / `09 §1.5` 为准，"估值/净值""开口/命中""弃权/灰""覆盖度/置信度"在组件命名中不得混用。
> - `grill-with-docs`：§5.4（组合卡）与 §5.7/§5.8（立方体/竞技场）承接第二轮 A-07/A-09。

## 摘要

1. 前端 = **一个壳（app shell）+ 7 视图 + 3 命脉组件 + 1 四态容器 + §9 特调组件集**；无框架、无打包、无 npm，浏览器原生 ES module 直接加载。
2. 状态管理采用**单一全局 store + 订阅重渲染**（约 60 行原生实现），不引入 Redux/Vuex；所有数据只来自 `api.js`，**禁止任何 mock/假数据进生产路径**。
3. 统一四态 `StateBlock`（empty/loading/error/success + success+陈旧）与统一错误码映射是本文两条硬约束，直接对应 PRD 铁律 1「不造假」。
4. 三个命脉组件：`ValBadge`（读后端 `valuation_mode`）、`UnknownCell`（阻断 `+0.00%`）、`PrivacyMask`（金额打码）。
5. 加载策略：首屏并行 3 请求、切片渲染；引擎状态 12s 轮询；长任务 2s 轮询；任一接口失败只影响所属 StateBlock。
6. **v2 裁定延续（G-AR-06）**：`empty` 只表示"引擎已跑但集合为空"，**引擎离线不得进 `empty`**（A-06）；未知行金额走独立 `fallback_value`（A-02）；组合方向未达覆盖门槛不显示"涨"（A-03）；T+3/T+15 未验证窗口统一"观察/未验证"样式（A-04）；否决层数据缺失在链路第③/④步显示"数据缺失"，不可显示为"通过"（A-05）。
7. **v3 第二轮裁定（G-AR-06 v2）**：§9 的 40 项特调组件全部有专属渲染组件与数据来源（§5.5~§5.13）；立方体 `naive` 为研究口径、**默认折叠**，`ddsm` 为生产口径默认展开（A-07）；竞技场配色只用后端 `arena_color`，与全站涨跌色**解耦**（A-09）；影子盘台账展示 `created_at` 与归档说明（A-10）。
8. **深模块原则**：`api.js` 是前端**唯一的网络 Adapter**，`format.js` 是**唯一的数值格式化深模块**，`StateBlock` 是**唯一的四态深模块**；三者都不允许被各视图绕过。
9. **v4 契约同步（S4 评审 · 契约 v5）**：前端口径随 `09-api-contract` v5 收口——① 设置页 LLM `base_url` 直读/直写契约字段（BLOCK-2）；② 分析页参与预测表改直读 `PredictionSummary.tier/market_value`，删除对 `/holdings` 的跨接口拼装（SHOULD-4）；③ 立方体研究层低样本格叠加 `naive_low_sample` 角标、去除 `{d15:...}`/`{candidate:...}` 旧形态兜底（SHOULD-1/5）；④ `.vsum` 分组标签读 `groups[].label`（缺口4）。详见 §4.14。

## 正文

### 1. 目录结构

```
web/
  index.html                 # 单页外壳（唯一 HTML）
  css/
    tokens.css               # 设计 token：颜色/圆角/玻璃/等宽（含 §A-09 竞技场独立色板 token）
    base.css                 # reset + 排版 + blob 背景
    layout.css               # sidebar/topbar/main + 响应式断点
    components.css           # Card/StatCard/ValBadge/DataTable/Timeline/StateBlock...
    views.css                # 各视图局部样式
  js/
    main.js                  # 入口：初始化 store、注册路由、首屏拉取
    api.js                   # ★ 唯一 fetch 出口（含错误码映射、超时）
    store.js                 # 全局状态 + subscribe/dispatch
    router.js                # 7 Tab 切换（hash 路由，无整页跳转）
    format.js                # ★ 唯一致值格式化（decimal → 显示）
    components/
      state-block.js         # 四态容器（empty/loading/error/success/stale）
      val-badge.js           # 估值来源徽章（命脉）
      unknown-cell.js        # 未知态单元格（命脉）
      privacy-mask.js        # 金额打码（命脉）
      data-table.js          # 等宽数字表（分组/折叠/显示列）
      stat-card.js           # 汇总卡
      timeline.js            # 信号时间线
      coverage-bar.js        # 覆盖度四档 .covbar（9.1-4）
      risk-fold.js           # 风险指标折叠区（9.1-6）
      signal-state.js        # 信号空态四要素 + 触发门卡（9.2-7/8）
      gate-card.js           # E1/E3 卡 + E2/E4 剔除（9.2-8）
      chain.js               # 六步推导链 .chain/.ev（9.2-9/9.3-13）
      cube-view.js           # 125 格状态立方体双切片（9.5-26）
      training-card.js       # 训练状态卡（9.5-23）
      arena-matrix.js        # 因子竞技场矩阵（9.5-22）
      shadow-ledger.js       # 影子盘台账 + 进度条（9.5-21）
      six-dim-bars.js        # 六维输入 z-bar（9.5-25）
      factor-pan.js          # 因子四盘 + 因子行（9.4-14）
      score-detail.js        # 展开跑分表（9.4-14）
      governance-card.js     # 治理周期卡（9.4-17）
      dig-table.js           # 挖掘记录表（9.4-18）
      dialog.js / popover.js / toast.js
      switch.js
    views/
      holdings.js            # ① 持仓
      analyze.js             # ② 分析
      signals.js             # ③ 信号
      factors.js             # ④ 因子
      review.js              # ⑤ 复盘
      engine.js              # ⑥ 引擎
      settings.js            # ⑦ 设置
    state/
      copy.js                # 四态文案 + 错误码文案（与 UI 设计 §4 逐条对齐）
```

### 2. 模块划分与职责（深模块视角）

| 模块 | Interface（调用方必须知道的全部） | Depth / 硬规则 |
|---|---|---|
| `api.js` | `request(path, opts) -> Envelope`；超时（默认 8s / 长任务 30s）；统一抛 `ApiError{code,message}`；错误码→文案 | **唯一网络 Adapter**；组件不得直接 `fetch`；删除测试：删掉它 → fetch/超时/错误映射会在每个视图重现 → 保留 |
| `store.js` | `getState/setState/subscribe`；状态形状对视图可见 | 视图只读 state、只通过 action 改；不缓存派生真值（total 由后端给）；删掉它 → 各视图自持状态与跨视图同步逻辑重现 → 保留 |
| `format.js` | `fmtPct/fmtP/fmtDeltaPP/fmtAmt/fmtNav/fmtZ/fmtDate/fmtTs` | **唯一数值格式深模块**；概率 ×100 保留 1 位、比率 ×100 保留 2 位带符号、金额 2 位千分位；组件不得自实现百分比逻辑；删掉它 → "12.42% vs 0.1242"会在各视图重现 → 保留 |
| `router.js` | `route()`→视图；切换不重拉已加载数据 | 无二级页面跳转，下钻用展开/弹窗 |
| `components/*` | 无状态优先，输入 props 输出 DOM | `ValBadge`/`UnknownCell`/`PrivacyMask` 为命脉，单独单测 |
| `views/*` | 组合组件 + 调 api + 管理本视图四态 | 每个视图必须显式声明当前 `state` |

#### 2.1 状态管理方案

**方案：单一 store + 订阅重渲染（自制，约 60 行）。**

```js
// store.js 形状（伪代码）
state = {
  route: "holdings",
  privacy: { masked: false },
  runtime: { as_of: null, stale: false, open_count: 0 },
  holdings: { status: "idle", data: null, error: null },      // 四态
  valuations: { status: "idle", data: null, error: null },
  forecast: { status: "idle", data: null, error: null },
  review: { status: "idle", data: null, error: null },
  ledger: { status: "idle", data: null, error: null },
  factors: { status: "idle", data: null, error: null },
  engine: { status: "idle", data: null, error: null },
  settings: { status: "idle", data: null, error: null },
  cube: { status: "idle", data: null, error: null, sheet: "ddsm", vr_layer: 2 },
  arena: { status: "idle", data: null, error: null },
  task: { id: null, status: "idle", progress: 0, step: "" },
}
```

- **每个数据切片自带四态**（`status: idle|loading|success|empty|error|stale` + `data` + `error`）。视图渲染时读自己的切片，互不牵连。
- **订阅机制**：`subscribe(viewFn)`；`setState(patch)` 后对变更切片触发对应视图重渲染（按 `route` 定向，不整页重绘）。
- **不引入框架的理由**：视图仅 7 个、状态扁平、无复杂列表 diff；引框架需构建步骤，违反零依赖底线。代价：需手工管理重渲染范围；在 7 视图规模可控。
- **禁止项**：store 中不得存放由其他字段可推出的"真值"（例如 total 由后端返回，不在前端 Σ 之后再当事实源）；前端可做求和**仅用于自检展示一致性**，不一致必须报错而非静默以自己为准。

#### 2.2 接缝地图与删除测试（codebase-design）

| 模块 | Seam（接口所在位置） | Adapter | 删除测试 |
|---|---|---|---|
| `api.js` | 前端 → 后端 HTTP 接缝 | 真实 fetch（测试可注入 fake） | 删掉 → 各视图各自 fetch/解析信封/错误映射 → 在赚深度，保留 |
| `format.js` | 数值 → 展示串 | 无（纯函数） | 删掉 → 百分比/金额/日期格式化逻辑分散 → 保留 |
| `state-block.js` | 四态渲染接缝 | 传入四态 props | 删掉 → 每视图自拼空/加载/错误/陈旧 → 保留（对应 A-06 硬规则） |
| `val-badge.js` | 估值 → 徽章 | 无 | 删掉 → 五档文案/配色/trace 在各页重现 → 保留 |

### 3. 四态统一处理公约（与产品经理 UI §5.4 对齐）

所有数据视图必须经 `StateBlock` 渲染，禁止自行拼凑空/错态。

| 状态 | 触发 | 渲染 | 铁律 |
|---|---|---|---|
| `loading` | 请求发出、未返回 | 脉冲点/骨架 + 文案（`copy.js` 按视图取） | 骨架**不得**显示任何数字 |
| `empty` | 请求成功、集合为空**且** `engine_status ∈ {online, running}` | 居中标题 + 副文案 + 事实卡 + 行动按钮 | 区分"空"与"错"：无信号是**常态**，文案须写明"不是故障"。**A-06：`engine_status=offline` 一律不得进本态** |
| `error` | 请求失败或 `ok=false`（含 `E_ENGINE_OFFLINE` 且无任何快照） | 红框 + 可读原因（来自 `error.message`）+ 重试按钮 | **不得**回退示例数据；不得静默空白 |
| `success` + 陈旧 `stale` | 请求成功但 `engine_status=offline` 且携带旧快照（`as_of` 为旧日期） | 正常内容 + **强制陈旧提示条**"引擎未运行，展示 <date> 快照" | 陈旧提示不得省略；数字与 `as_of` 同屏（A-06） |
| `success` | 有数据 | 真实内容 | 只显示后端返回值；未知用命脉组件 |

**关键实现约定**：

- `STATE_COPY` 文案与 UI 设计 §4.1~§4.7 的表格逐条对应（`state/copy.js`）。
- 同一页可有多个 StateBlock（如持仓页的总览卡、明细表分别成态）；一个接口失败不使其他块进入 error。
- 重试按钮重新调用该切片的加载 action，不刷新整页。
- **多切片陈旧**：若估值与预测 `as_of` 不同，各自 StateBlock 标注各自时间，禁止一个全局时间掩盖（A-06 衍生）。

### 4. 命脉组件细规（v3 由 3 个扩为 3+10 组）

#### 4.1 `ValBadge`（估值来源徽章，9.1-3）

- 输入：`valuation_mode`、`confidence`、`confidence_color_class`、`confidence_label`、`source_label`、`trace`/`trace_text`、`nav_date`、`mae_rate`、`dir_hit_rate`、`n_test`、`written_at`、`is_first_of_day`、`history_available`。
- 文案映射（**来自后端 `valuation_mode`，禁止前端硬编码映射以外的推断**）：
  `official→官方净值 / intraday→盘中估算 / holdings→重仓加权 / proxy→代理近似 / unknown→未知`。
- 配色：按 `confidence_color_class`（`ch`→绿 / `cm`→金 / `cl`→红 / `cu`→虚线灰），**来源名与置信度分离**，置信度优先着色（UI §5.1）。
- 悬浮/展开：`source_label` + 降级链路（用 `trace_text`，如 `official 未出 → intraday 命中`）+ `mae_rate` + `dir_hit_rate` + `n_test` + **入账时间 `written_at`**。
- **可追溯（A-01）**：徽章详情提供"当日入账历史"入口，调 `GET /valuations/{code}?history=true`，按 `written_at` 升序列出当日各次入账，首次入账标"当日首次口径"；默认不展示，不得改写主徽章口径。
- 硬规则：`trace_text` 缺失时**只显示 mode 文案，不编造链路**；`nav_date` 缺失显示"净值截止日未知"。

#### 4.2 `UnknownCell`（未知态，9.1-5/9.1-8）

- 判定：`change_rate === null || undefined || typeof !== "number" || Number.isNaN(...)` → 未知。
- 渲染：涨跌列 `<span class="unk">未知</span>`（斜体灰）；今日盈亏 `—`。
- 汇总（A-02）：若存在未知持仓，`total_value` 只含可信行；未知行金额**单独一格**显示 `fallback_value`（成本口径），文案"未知行按成本计 ¥X（不计入总资产市值口径）"，并附 `total_value_with_fallback`。副标题必须出现"可信估值覆盖 N/M 只"（N/M 来自后端 `coverage_note`/`covered_count`，不由前端数）。
- **禁止**：`Number(null)`、`Number("")`、`parseFloat` 后当 0；`change_rate === 0` 才渲染 `+0.00%`；**禁止**把 `fallback_value` 填入 `market_value` 列或加总进 `total_value`。

#### 4.3 `PrivacyMask`（隐私打码，9.7-32）

- 开关来自 `settings.privacy.masked`，切换时 `PUT /api/v1/settings` 持久化。
- 实现：给所有金额节点加类 `amt`；`masked` 时用 CSS 模糊 + `••••` 覆盖（样式参照线框）。
- 只作用于展示，**不改变 store 中的数值**，也不影响任何计算/导出。

#### 4.4 `CoverageBar`（覆盖度四档 .covbar，9.1-4）

- 输入：`CoveragePanel`（§5.19）；固定渲染 4 段 A/B/C/D，色值取后端 `color`（不硬编码）。
- 每段：档位标签 + 只数 + 市值占比（`weight_ratio=null` 显示"—"）+ 信号列读法 `action_hint`。
- 展开：`invalidation_note`（失效三类长文）+ `no_solution_count` 文案"原理无解：N 只"（本期 0）。

#### 4.5 `RiskFold`（风险指标折叠区，9.1-6）

- 折叠展开才请求 `/holdings/risk`（慢接口）；字段 null → "—"，**禁止 0 冒充**。
- `var95_rate`/`max_drawdown_rate` 以后端正数表示损失，展示为"VaR95 2.30%"（不加负号）。

#### 4.6 `SignalState` + `GateCard`（信号空态四要素 + 触发门卡，9.2-7/9.2-8）

- 输入：`SignalState`（§5.21）；空态文案 `empty_note` 必含"这是常态，不是故障"。
- 渲染 `gates`（E1/E3，`role=primary/secondary`）与 `excluded_gates`（E2/E4，`role=excluded`）；`or_merge_forbidden=true` 固定文案"禁止 OR 合并"。
- `state=no_open` 是合法空态；引擎离线走 §3 四态规则，不得进 empty（A-06）。

#### 4.7 `Timeline` + `Chain`（信号时间线 + 六步推导链，9.2-9/9.3-13）

- `Timeline` 列表项 `.tl-item` 点击展开 `.ev` 事件链，数据来自 `GET /ledger/chain?date&code`。
- `Chain` 固定 6 步（① 触发门 ② DDSM ③ 拥挤度否决 ④ KLOW2 否决 ⑤ 出口 ⑥ 输出/回填），每步 `status ∈ {on,off,missing}`：
  - `missing` 渲染"数据缺失"（灰），**不得渲染为通过**；任一否决层 missing → 总 `signal=abstain`（A-05）。
  - 出口步显示 `exit_threshold=52.0%`；`p_up` 未达阈值时状态 off。
- 数值一律经 `format.js`；不编造步骤数值（`metrics` 缺键即显示"数据缺失"）。

#### 4.8 `CubeView`（125 格状态立方体双切片，9.5-26 · A-07）

- 输入：`StateCube`（§5.25）；顶部两个口径切换 **`ddsm`（生产口径，默认）** / **`naive`（研究口径）**，切换只换切片，不重拉。
- 默认态：**展示 `ddsm`**；`naive` 折叠在"研究口径（未加噪真实档位）"标签下，展开时同屏强制显示口径差异说明（`comparison.note`），**禁止默认并列**。
- vr 层切换（0~4）5 个 tab；每层 5×5 网格（横轴 om、纵轴 r2）。
- 每格：颜色由 `color_band` + 图例；悬停显示 `state`、`n`（naive_n/ddsm_n）、`P`（naive_p/ddsm_p）。**v4/v5**：研究口径 `naive_low_sample=true`（`naive_n<15`）的格叠加「低样本·仅供审计」角标；`naive_p` 为原始频率（`naive_n>0` 即给），研究层不再因 MIN_N 整片「无样本」（SHOULD-5）。
- `status=empty`/`is_empty=true` → 渲染**斜纹"无样本"**，**禁止**渲染为 0/50%（PRD G3）。
- 对比卡展示 `valid_coverage_*`、`p_std_*`、`extreme_count_*`、`walk_forward_delta_*`（null 时"—"并标"待复现"）。

#### 4.9 `TrainingCard`（训练状态卡，9.5-23）

- 输入：`TrainingStatus`（§5.26）；展示 125 格/有样本格/覆盖率/平均样本/最少样本 + 加噪说明 `noise_text` + 已证伪死路 `dead_ends`（逐条"勿重试"）。

#### 4.10 `ArenaMatrix`（因子竞技场矩阵，9.5-22 · A-09）

- 输入：`ArenaMatrix`（§5.24）；行=配置、列=六窗；每格显示 `open_count · hit_rate · paired_delta_pp`。
- 配色：**只用后端 `arena_color`**（red/green/blue/yellow/base），**与全站涨跌红绿解耦**——竞技场色板走 `tokens.css` 中独立 `--arena-*` 变量，图例文案由 `legend` 给出（"该窗最高/最低/居中/警示/基准"），不得复用 `--up/--down`。
- 留一法行标 `is_leave_one_out`；生产行标 `is_highlight`；警示格/行加 ▲（`warning=true`）；`naive_baseline` 行不着红绿。

#### 4.11 `ShadowLedger`（影子盘台账 + 进度，9.5-21 · A-10）

- 输入：`ShadowLedger`（§5.28）；表格列由 `field_list` 驱动（含 `created_at`）；进度条 `progress_ratio` + "N/60"。
- 字段说明 `insert_only_note` + 归档说明（"当日首次口径永久保留，历史行全量归档"）。
- 无编辑/删除入口（G10）；`hit_rate=null` 显示"—"。

#### 4.12 `SixDimBars`（六维输入 z-bar，9.5-25）

- 输入：`/engine/inputs` 的 `ddsm_3d` + `crowd_6d` + `crowd`（§5.27）。
- 每维一行：`label` + 原值（带 `raw_unit`）+ z-bar（`z`，正负向不同色）+ 档位（`level/level_label`，六维可空）+ IC 符号 `ic_sign`。
- 复合行：`crowd.composite_z` + `quantile` + `is_veto`/`status`；`klow2` 分位行。`status=missing` → 显示"数据缺失"，不得显示为 pass（A-05）。

#### 4.13 `FactorPan` + `ScoreDetail` + `GovernanceCard` + `DigTable`（9.4-14/16/17/18）

- `FactorPan`：四盘 tab，逐盘 `rule_text` 长文（后端给，不硬编码）；因子行展示 `total_score` + 六窗 `lift_bars` + `license`/`license_label` + `status` + `role_label`；展开调 `/factors/score-detail` 显示 `k_lift` 悬崖/窗权重/独立触发日/准入度/得分 + `bootstrap_percentiles` + `judges`。
- `GovernanceCard`：`GovernanceCycle` 五阶段（`cadence`/`status`/`next_run_at`/`rule_text`）。
- `DigTable`：`DigRecord` 行 F1/F2/F3（`na` 显示"—"）+ `verdict_text` + 冷却 `cooldown_until`。
- 账本无记录时显示"待写入"，**禁止 legacy 示例数字冒充**（残留风险 9）。

#### 4.14 v5 契约同步的组件约定（只按契约取值，不加功能）

- **设置页 LLM 卡**：Base URL 输入框 `v-model` 绑定契约 `Settings.llm.base_url`（§5.16 v5），保存走 `PUT /settings`；切换 `provider` 时预填各服务商默认 Base 供用户确认（**不自动静默改写**）。`GET` 未配置回 `""`，不显示占位假值。禁止把 Base 仅存前端内存（BLOCK-2）。
- **分析页参与预测表**：`tier`/`market_value` 直接读 `GET /predictions` 的 `rows[]`（§5.4 v5）；**删除**用 `/holdings` 按 `code` 拼装的展示连接；`market_value=null` 走 `UnknownCell`「—」。
- **估值精度汇总条 `.vsum`**：分组标签读 `groups[].label`（§6.3 v5）；仅在为空时回退本地 `CONF_LABEL` 常量并登记。
- **冻结参数表**：`window_weights`/`window_min_days`/`license_lines` 按 v5 冻结键名 `{window,weight}`/`{window,n_w}`/`{license,min_independent_days,window_k}` 解析，删除 `{d15:...}`/`{candidate:...}` 旧形态兜底（SHOULD-1）。

### 5. 数值展示口径（与 09-api-contract §1 一致）

| 后端字段类型 | 含义 | 前端展示 |
|---|---|---|
| `*_p`（如 `p_up`） | 概率，小数 [0,1] | ×100，保留 1 位，如 `0.583 → 58.3%` |
| `*_rate` / `*_ratio` / `pct` | 比率，小数非百分数 | ×100，保留 2 位，带 +/−，如 `0.0124 → +1.24%` |
| `delta_pp` | 增量，小数（0.099=9.9pp） | ×100，保留 1 位，如 `+9.9pp` |
| `*_amt` / `*_value` | 金额，元 | 2 位 + 千分位，`¥53,243.28`；masked → `••••` |
| `shares` | 份额，份 | 4 位小数 |
| `nav` / `price` | 净值，元/份 | 4 位小数 |
| `z` / `lift` / `k_lift` / `score` | z 值/倍数/分数 | z 值 3 位；lift 4 位；score 4 位 |
| 日期 | `YYYY-MM-DD` | 原样 + 可选"周x" |
| 时间戳 | ISO 8601 带时区 | 本地 `HH:mm`（时区 `Asia/Shanghai`） |

**硬规则**：格式化只发生在 `format.js`；组件不得各自实现百分比逻辑，避免"12.42% vs 0.1242"分叉（PRD 失败定义）。

### 6. 错误处理统一口径

```js
// api.js 伪代码
async function request(path, opts) {
  try {
    const res = await fetchWithTimeout(BASE + path, opts, timeoutFor(path));
    const body = await res.json().catch(() => { throw new ApiError("E_PARSE", "返回不是合法 JSON"); });
    if (!body.ok) throw new ApiError(body.error.code, body.error.message);
    return body;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e.name === "AbortError") throw new ApiError("E_TIMEOUT", "请求超时");
    throw new ApiError("E_NETWORK", "无法连接本地服务");
  }
}
```

- 视图捕获后：`store.setState({ [slice]: {status:"error", error:{code,message}} })` → `StateBlock` 渲染。
- `error.code` 显示文案映射集中在 `copy.js`；未知 code 统一显示"发生未知错误：<message>"，不吞掉 message。
- 控制台可 `console.error` 便于排查，但**不得**把密钥/持仓金额打进日志（隐私）。

### 7. 日志与可观测性

- 前端无自建日志服务；仅：
  1. `console.error` 记录失败接口与错误码（不含金额/密钥）；
  2. Topbar 的 `LiveBar` 展示 `runtime` 状态（正常/波动/不通/陈旧）；
  3. 引擎页轮询 `GET /engine/status`，展示 HUD 六卡与心跳。
- 真实日志在**后端**（`server/`），前端只负责展示后端给的 `runtime`/`data_sources`。

### 8. 路由与交互

- hash 路由：`#/holdings`、`#/analyze`…；默认 `#/holdings`。
- 无二级页面：所有下钻用 `details`/弹窗/气囊，关闭回原位（UI IA §1）。
- 危险操作（删除持仓）走二次确认对话框；台账页**无**任何编辑/删除入口。
- 响应式断点：≥1100 侧栏常驻；900~1100 卡片两列；≤900 侧栏转底部栏、表格单列。
- Service Worker 主动注销，保证每次最新界面（9.8-38）。

## 自验收

- [x] 给出目录结构与模块划分
- [x] 状态管理方案（单一 store + 订阅）并说明不引框架的理由与代价
- [x] 前端架构写明「加载/错误/空态/成功/陈旧」统一约定，与 UI 设计四态对齐
- [x] 三个命脉组件单独细规（ValBadge / UnknownCell / PrivacyMask）
- [x] 错误处理统一口径（ApiError + code 映射 + 不回退假数据）
- [x] 日志与可观测性口径（前端只展示后端状态，不回传隐私）
- [x] 数值展示口径唯一入口 `format.js`，避免口径分叉
- [x] 未写实现代码（仅伪代码/形状说明）
- [x] A-02：未知行成本走独立 `fallback_value`，禁混入市值列/总资产
- [x] A-03：组合卡"涨"需同时满足出口、覆盖门槛、窗口已验证三条件，`direction_reason` 有文案
- [x] A-04：T+3/T+15 未验证走"观察"样式，`provisional_direction` 不进卡片
- [x] A-06：四态新增"success+陈旧"行，`empty` 明确要求 `engine_status ∈ {online,running}`
- [x] **codebase-design**：§2.2 接缝地图 + 删除测试覆盖 api/format/state-block/val-badge
- [x] **v3**：§9 的 40 项特调组件均落到专属组件（§1 目录 + §4.4~§4.13 细规），数据来源对应 09 契约
- [x] **v3 A-07**：立方体 ddsm 默认展开、naive 研究口径默认折叠，口径切换不并列
- [x] **v3 A-09**：竞技场配色只用后端 `arena_color`，独立 `--arena-*` token，与涨跌色解耦
- [x] **v3 A-10**：影子盘台账展示 `created_at` 与归档说明，无编辑/删除入口
- [x] **v4（契约 v5 同步）**：§4.14 覆盖 LLM `base_url` 直读写、预测表直读 `tier/market_value`、精度分组 `label`、冻结表三数组键名——全部只按契约取值，未加功能

## 下游交接

- **主消费方**：`frontend-dev`。需其执行：按本目录落 7 视图与全部组件；`ValBadge` 读 `valuation_mode`、`UnknownCell` 阻断 `+0.00%`、`PrivacyMask` 只作用展示；所有请求经 `api.js`；§9 的 40 项组件按 §4 逐项落地，**缺一即 G-FE-01 不通过**。**v4（契约 v5）**：按 §4.14 收口四处——设置页 LLM `base_url`、预测表 `tier/market_value` 直读、精度分组 `label`、冻结参数三数组键名（含删除旧形态兜底）。
- **次消费方**：`qa`。需其执行：按四态与命脉组件建负向用例（G3/G4/G5/G2），重点断言"无假数据""未知不含 `+0.00%`""徽章=mode"；v3 追加"空样本格不渲染 0/50%""竞技场不复用涨跌色""台账无编辑入口"。
- **残留风险**：
  1. **125 格立方体 + 竞技场信息密度高**，窄屏需折叠/横滚（责任人：frontend-dev，期限：S4）。
  2. **顺序加载导致的口径时间差**：首屏多请求并行，若估值与组合预测 `as_of` 不同，需分切片标注时间（责任人：frontend-dev，期限：S4）。
  3. **ES module 的 file:// 限制**：必须经 `http://127.0.0.1` 访问（与 AGENTS「不要双击 HTML」同因）；README 需写明（责任人：dev-lead，期限：S5）。
  4. **A-06 陈旧态与全局 `as_of` 的显示一致性**：多接口并行时 `engine_status`/`as_of` 可能不同，按切片各自标注（责任人：frontend-dev，期限：S4）。
  5. **A-04 观察样式的视觉区分度**：T+3/T+15 "未验证"样式需与 T+1 一眼可分，且不误用涨红（责任人：frontend-dev + product-manager，期限：S4）。
  6. **A-07 naive/ddsm 口径切换的认知负担**：需 UI 走查确认默认折叠不造成"看不到研究口径"的误解（责任人：frontend-dev + product-manager，期限：S4）。
- **未覆盖**：接口逐字段（`09-api-contract`）、后端模块（`08-backend-arch`）、ADR 正文（`10-arch-review §ADR`）。
