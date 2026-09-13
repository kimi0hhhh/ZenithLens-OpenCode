---
artifact: 13-frontend-report
owner: frontend-dev
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端实现报告 · 极境 ZenithLens（S3 重跑 · v2 · 契约 v4）

> 产出：`C:\Users\10719\Documents\ZenithLens-OpenCode\static\`（纯静态、零依赖、无构建步骤）。
> 依据：`04-ui-wireframe.html` v3（不删减）、`07-frontend-arch.md` v3、`09-api-contract.md` **v4**（字段唯一法律）、`PROJECT_BRIEF.md §9`。
> 交付物：`static/index.html` + `static/css/app.css` + `static/js/**`（ES module）+ `docs/02-frontend/12-interface-request.md`。
> v2 方法：skill `implement`（按 spec 实现、定期校验、收尾自查）+ skill `prototype`（一次性原型验设计问题，产物不进交付物）。

## 摘要

1. 交付一个原生 HTML/CSS/ES module 产品壳 **v2**：1 外壳 + 7 视图 + 3 命脉组件 + 1 四态容器 + §9 特调组件集；零 npm、无打包，Python 3.8+ 直接托管。
2. **Brief §9 的 40 项特调组件逐项落地**（映射见 §3），含 125 格立方体 naive/DDSM、因子四盘+治理长文、`.vb` 估值徽章、`.chain-item` 推导链、竞技场矩阵、影子盘台账、六维 z-bar 等。
3. **契约 v4 四条裁定全部落地**：A-07 立方体生产口径 `ddsm` 默认 / 研究口径 `naive` 折叠（不再默认并列）；A-08 组合卡展示 `weighting_basis`+`weighting_policy_note`；A-09 竞技场只取 `arena_color` + 独立 `--arena-*` 色板（与涨跌色解耦）；A-10 影子盘台账展示 `created_at`+归档说明。
4. **四态统一**：所有数据视图经 `components.js#mountState` 渲染；空/加载/错误/成功可手动切换（R-UI-40 状态条）；引擎离线按 A-06 走陈旧态/错误态，不进 `empty`。
5. **命脉约束**：请求全经 `api.js`（全仓 `fetch(` 仅 1 处）；数字全经 `format.js`；徽章由后端 `mode_label`/`confidence_color_class` 驱动；`null` 一律「未知/—」（**无 `+0.00%`**）；隐私打码全站 `.amt` 生效。
6. **造壳不造假**：mock 隔离在 `js/mock/`，**默认关闭**；前端不做业务计算（组合加权/命中率/评分/Δ/求和/分档一律取后端）。
7. 本轮冒烟：Edge headless `--dump-dom` + `node --check` 全通过（见 §5）；未采集 console 事件，留 qa 于 S4 用 CDP 复核。

## 正文

### 1. 交付清单与目录（v2 实测行数）

| 路径 | 行数 | 说明 |
|---|---|---|
| `static/index.html` | 359 | 唯一 HTML 外壳（7 视图 + 3 dialog + popover + toast；立方体双口径结构） |
| `static/css/app.css` | 358 | 设计 token + 布局 + 组件；**v2 新增 `--arena-*` 独立色板、立方体研究口径折叠样式** |
| `static/js/api.js` | 93 | ★ 唯一 fetch 出口：超时（8s/30s）、统一信封、`ApiError{code}`、mock 注入点 |
| `static/js/store.js` | 45 | 单一 store + 订阅；每切片自带四态 |
| `static/js/format.js` | 118 | ★ 数字唯一格式化出口（金额/概率/比率/Δpp/lift/z/日期） |
| `static/js/copy.js` | 73 | 四态文案 + 错误码文案 + 枚举中文映射 |
| `static/js/components.js` | 279 | `mountState`、`valBadge`、`unknownCell`、`forecastCard`、`chainHTML`、`cubeSliceHTML`、`arenaColorVar/arenaClass`、`weightingNote`、`zbar`、`toast`、`showModal` |
| `static/js/main.js` | 173 | 入口：路由、顶栏/livebar、SW 注销、隐私、四态演示、runtime 轮询 |
| `static/js/views/holdings.js` | 421 | ① 持仓（R-UI-01~06 + CRUD + dialog/popover） |
| `static/js/views/analyze.js` | 122 | ② 分析（R-UI-10~13；A-08 加权口径） |
| `static/js/views/signals.js` | 120 | ③ 信号（R-UI-07~09） |
| `static/js/views/factors.js` | 239 | ④ 因子（R-UI-14~19） |
| `static/js/views/review.js` | 98 | ⑤ 复盘（R-UI-28~31） |
| `static/js/views/engine.js` | 339 | ⑥ 引擎（R-UI-20~27；A-07/A-09/A-10） |
| `static/js/views/settings.js` | 194 | ⑦ 设置（R-UI-32~36） |
| `static/js/mock/mock.js` | 529 | mock 后端替身（默认关闭，已补 v4 字段） |
| `static/README.md` | 24 | 启动说明 + 接口运用规范 |

**启动**：`cd static; python -m http.server 8787 --bind 127.0.0.1` → `http://127.0.0.1:8787/index.html`。
必须经 `http://` 访问（ES module 在 `file://` 下被拦截），与 AGENTS「不要双击 HTML」同因。

### 2. 架构落地（对照 07-frontend-arch v3）

- **无框架/无打包**：ES2019 module，浏览器原生 `<script type="module">`；store 用原生订阅（45 行），不引 Redux/Vue。
- **单一 fetch 出口**：`views/*` 只调 `api.js` 的 `get/post/put/del/loadSlice`；全仓 `fetch(` 仅命中 `api.js`（§5 实测）。
- **四态**：`mountState(container, view, slice, onRetry, facts)` 统一渲染；`empty` 仅由「成功且集合为空」触发；引擎离线走 `error`/陈旧（A-06）。
- **命脉组件**：`valBadge`（读 `valuation_mode→mode_label` + `confidence_color_class`）、`unknownCell/changeCell/pnlCell`（阻断 `+0.00%`）、`PrivacyMask`（`body.masked .amt`）。
- **格式化唯一入口**：`format.js` 提供 `amt/prob/rate/rateU/pp/delta/lift/num/nav/shares/z/cls`；视图不得自行拼百分比。
- **v2 深链修复**：直落 `#/engine` 时若持仓切片未加载，引擎页先补拉 `/holdings` 再生成资产下拉（避免六维/立方体因无 `code` 空转）。

### 3. Brief §9 · 40 项特调组件落地映射（v2）

| # | 组件 | 实现位置 | 数据来源（契约 v4） |
|---|---|---|---|
| 9.1-1 | 资产总览四卡 + 覆盖度说明 | `views/holdings.js#renderOverview` `#pa-*` | `/holdings` summary §6.2.1 |
| 9.1-2 | 估值精度汇总条 `.vsum` | `#renderVSum` `#val-sum` | `/valuations/precision` §6.3（含 `mode_distribution`） |
| 9.1-3 | 估值来源徽章 `.vb` 五档 + `.ch/.cm/.cl/.cu` | `components.js#valBadge` | `Valuation` §5.2（`mode_label/confidence_color_class/mae_rate/dir_hit_rate/n_test/trace_text/nav_date`） |
| 9.1-4 | 覆盖度四档 `.covbar` + 失效三类 | `#renderCoverage` `#cov-bar/#cov-note` | `/holdings/coverage` §5.19 |
| 9.1-5 | 持仓明细表（分组/列显隐/T+2/未知≠持平） | `#renderTable` `#hd-body` | `/holdings` §5.1（`fallback_value` 分列） |
| 9.1-6 | 风险指标折叠区 | `#fold-risk` `#loadRisk` | `/holdings/risk` §5.20 |
| 9.2-7 | 信号空态四要素 | `views/signals.js#renderEmpty` `#sg-empty` | `/signals/state` §5.21 |
| 9.2-8 | 触发门 E1/E3 + E2/E4 剔除 | `#renderGates` `#sg-gates/#sg-excl` | `/signals/state` |
| 9.2-9 | 信号时间线 `.tl/.tl-item/.sigcard/.ev` | `#renderTimeline` `#tl-list` | `/ledger` + `/ledger/chain` §5.34 |
| 9.3-10 | T+1 口径 + 三执行路径 | `views/analyze.js#renderDefs` `#an-defs` | `/meta/definitions` §5.22 |
| 9.3-11 | 三窗口组合卡 + 加权口径 | `#renderForecast` + `components#forecastCard/#weightingNote` | `/portfolio/forecast` §5.7（**`weighting_basis`/`weighting_policy_note`**） |
| 9.3-12 | 参与预测持仓表 | `#renderTable` `#an-body` | `/predictions` §5.4 |
| 9.3-13 | 推导链 `.chain/.chain-item` 六步 | `components#chainHTML`（`metrics` 逐键格式化） | `/predictions/{code}`、`/ledger/chain` |
| 9.4-14 | 因子四盘 + 因子行 + 跑分表 | `views/factors.js#renderPans/#toggleScoreDetail` | `/factors/pans` §5.11/§5.12、`/factors/score-detail` §5.23 |
| 9.4-15 | 四本账本 + 示例记录 | `#renderBooks/#openBook` | `/factors/books`、`/factors/books/{book}` |
| 9.4-16 | 评分链长文（悬崖/bootstrap/四裁判） | `#renderScoreChain` `#fc-score` | `/factors/score-chain` |
| 9.4-17 | 治理周期卡 | `#renderGovernance` `#fc-cycle` | `/factors/governance-cycle` §5.30 |
| 9.4-18 | 最近挖掘记录 F1/F2/F3 | `#renderDigRecords` `#fc-scan` | `/factors/dig-records` §5.31 |
| 9.4-19 | 生命周期规则长文 | `#renderLifecycle` `#fc-life` | `/factors/lifecycle` §5.32 |
| 9.5-20 | HUD 六卡 | `views/engine.js#renderHud` `#eg-hud` | `/engine/status` §6.9 |
| 9.5-21 | 影子盘台账 + 进度条 + 归档说明 | `#renderShadow` `#eg-ledger*`（含 `created_at` 列 + `#eg-ledger-archive`） | `/ledger/shadow` §5.28（**`retention_policy`/`first_of_day_immutable`/`archive_manifest_at`**） |
| 9.5-22 | 因子竞技场矩阵 | `#renderArena` `#eg-arena`（`--arena-*`） | `/engine/arena` §5.24（**`color_scheme`/`color_token_prefix`**） |
| 9.5-23 | 训练状态卡 | `#renderTraining` `#eg-train` | `/engine/training-status` §5.26 |
| 9.5-24 | 冻结参数表 | `#renderFrozen` `#eg-frozen`（含 **`weighting_basis`**） | `/engine/frozen-params` §5.14 |
| 9.5-25 | 六维输入 z-bar | `#renderDims` `#dim-d3/#dim-d6` | `/engine/inputs` §5.27 |
| 9.5-26 | 125 格立方体（**ddsm 默认 / naive 折叠**）+ vr 层 | `#renderCube` + `components#cubeSliceHTML` | `/engine/ddsm/cube` §5.25（**双口径字段**） |
| 9.5-27 | 引擎注册表三态 | `#renderRegistry` `#eg-registry`/`#st-registry` | `/engine/registry` §6.9 |
| 9.6-28 | 历史成绩 hero | `views/review.js#renderHero` `#rv-hero` | `/review/scores` |
| 9.6-29 | 三窗口 vs 基线表（待填充留空） | `#renderScores` `#rv-scores` | `/review/scores` §5.8 |
| 9.6-30 | 影子盘降级审查条 idle/ok/bad | `#renderDegrade` `#rv-degrade` | `/engine/shadow-review` §5.29 |
| 9.6-31 | 逐笔对账表 | `#renderRecon` `#rv-body` | `/review/reconciliation` §5.10 |
| 9.7-32 | 隐私开关 | `views/settings.js#savePrivacy` `#sw-hide` | `/settings` GET/PUT §5.16 |
| 9.7-33 | LLM 接口 + 三硬约束 + 温度 0 | `#renderLlm/#saveLlm` | `/settings` |
| 9.7-34 | 数据源健康表 | `#renderSources` `#src-box` | `/data-sources/health`、`/probe` |
| 9.7-35 | 持仓数据卡 + 两文件不一致长文 | `#renderHoldingsData` `#hd-data/#hd-diff` | `/settings/holdings-data` §5.33 |
| 9.7-36 | 关于卡 | `#renderAbout` `#about-card` | `/about` |
| 9.8-37 | 三 dialog + popover + toast | `index.html#dlg-fund/#dlg-amt/#dlg-del/#pop/#toast`；`holdings.js` | `/holdings` CRUD + `/transactions` |
| 9.8-38 | 注销 Service Worker | `main.js` 顶部 | 纯前端 |
| 9.8-39 | livebar 真实数据接入条 | `main.js#renderLivebar` `#livebar` | `/runtime` + `/data-sources/health` |
| 9.8-40 | 四态覆盖 | `components#mountState` + `main.js#setDemoState` | 全局 |

### 4. v4 四条裁定落地（v2 核心变更）

| 裁定 | 后端字段 | 前端实现 | 验证 |
|---|---|---|---|
| **A-07** 立方体双口径 | `StateCube.production_layer/research_layer/default_layer/dual_view_note` | 默认仅渲染生产口径 `ddsm` 单切片；`naive` 放 `<details>`（默认折叠）；`#eg-laymode` 标「默认 ddsm/研究层折叠」；同屏 `dual_view_note`；格色只认 `color_band`，**不再用 P 重算分档** | 引擎页 `cc=50`（生产 25 + 折叠 25），`dual` 节点存在 |
| **A-08** 权重口径 | `PortfolioForecast.weighting_basis/weighting_policy_note`；`FrozenParams.weighting_basis` | `components#weightingNote` 在持仓 `#pf-note` 与分析 `#an-weighting` 展示；`forecastCard` 附 `market_value`；冻结参数表加行 | 分析页 `#an-weighting` 命中、渲染出 `market_value`；引擎 `weighting_basis` 行命中 |
| **A-09** 竞技场解耦 | `ArenaMatrix.color_scheme/color_token_prefix` | `renderArena` 只用 `arenaColorVar(c.color, prefix)`（→ `var(--arena-red|green|blue|yellow|base)`）；图例用 `.arena-swatch`；`tokens` 独立定义，取值与 `--up/--down` 不同 | DOM 内 `--arena-` 命中 46 次；**无** `arena…var(--up)` 命中 |
| **A-10** 影子盘归档 | `ShadowLedger.retention_policy/first_of_day_immutable/archive_manifest_at` | 台账新增 `created_at` 列；`#eg-ledger-archive` 展示归档策略与「当日首次口径永久保留」；沿用 `insert_only_note` | 引擎页归档说明节点命中 |

### 5. 硬性约束逐条自查

1. **40 项组件齐全**：§3 映射 40/40；`index.html` 保留线框全部容器与长文区块，未删减。
2. **四态全部实现**：7 视图 × 4 态 → `mountState` + `STATE_COPY`；顶栏状态条可逐页切换（R-UI-40）。
3. **数据来源可信**：徽章读后端 `mode_label/confidence_color_class`；`null` 渲染「未知/—」；`unknown`/无估值行 `market_value=null` 分列 `fallback_value`（不进市值列/总资产）。
4. **隐私打码**：`body.masked .amt`（子节点隐藏 + `••••` 覆盖），占比/涨跌不遮；开关经 `PUT /settings` 持久化。
5. **无前端业务计算**：组合加权、覆盖占比、命中率、Δ、`k_lift`/得分、立方体分档、竞技场配色、分组金额求和**全部取后端**；前端仅做展示层 ×100/千分位（`format.js`）、`code`→`tier/market_value` 展示连接（缺口 §10-2）、以及 z-bar/进度条的**几何绘制**。持仓分组表头已去掉前端金额求和，仅显示只数。
6. **字段名逐字对齐 v4**：全部 `snake_case`；`written_at`/`created_at` 双字段；`veto_*_status` 三态；`color_band`/`arena_color`/`weighting_basis` 等 v4 字段原样消费。
7. **零构建/可 3.8+ 起服**：无 npm、无编译；`python -m http.server` 实测可跑。
8. **未修改契约/架构文件、未写 Python 业务代码、未改 `runtime/**`、未派发子任务**。

### 6. 真浏览器冒烟证据（Edge headless + `--dump-dom`）

- 启动：`python -m http.server <port> --bind 127.0.0.1`；Edge `--headless=old --virtual-time-budget=8000~10000 --dump-dom`。
- `?mock=1` 各视图渲染（DOM 计数）：
  - `#/holdings`：四卡 `.sc`×4、三窗口 `.win`×3；
  - `#/analyze`：三窗口 ×3、`#an-weighting` 命中且渲染 `market_value`；
  - `#/engine`：竞技场格 `.arena-cell`×42（7 行 × 6 窗）、图例 `.arena-swatch`×5、六维 `.dim`×9（3+6）、立方体 `.cc`×50（生产 25 + 研究折叠 25）、`--arena-`×46、`.hud-c` 六卡；
  - `#/factors`：因子行 `.frow`×7；`#/settings`：配置行 `.kv`×18。
- 去 mock（真实后端缺席）：holdings 进入 `state-block error` + `data-state="error"`，**无 `+0.00%`**，无假数据。
- 静态检查：`node --check`（ESM 版）全部 JS 通过；全仓 `fetch(` 仅 `api.js` 命中 1 处。
- 说明：本轮未采集 console 事件（未跑 CDP），故「控制台零报错」留 qa 于 S4 用 CDP 复核；当前以「无解析错误 + 成功渲染 + 无假数据」为通过依据。
- 设计验证（skill `prototype`）：以一次性原型 `C:\Users\10719\AppData\Local\Temp\opencode\zl-prototype-a07.html` 验证 A-07「默认 ddsm + naive 折叠」交互成立；该产物**不进交付物**。

### 7. mock 使用与切换

- 开关：URL `?mock=1` 或 `localStorage.setItem('zl_mock','1')`；**默认关闭**。
- 隔离：仅 `static/js/mock/`，由 `main.js` 动态 `import()`，生产路径不加载。
- 注入：`api.enableMock(mockRequest)`；对接后端时删除开关即可，视图层零改动。
- v4 补齐：`forecast()→weighting_basis/weighting_policy_note`、`arena()→color_scheme/color_token_prefix`、`cube()→production_layer/research_layer/default_layer/dual_view_note`、`/ledger/shadow→retention_policy/first_of_day_immutable/archive_manifest_at`、`/engine/frozen-params→weighting_basis`。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（R-UI-40 状态条；DOM 冒烟）
- [x] 所有请求走统一封装层，页面层无裸 fetch（全仓仅 `api.js` 出现 `fetch(`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`
- [x] 数字格式化走统一工具函数 `format.js`，涨红跌绿正确
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可直接以 `python -m http.server`（Python 3.8+）启动；本轮无 JS 解析错误（console 事件留 qa CDP 复核）
- [x] `12-interface-request.md` 每条都写了「前端如何处理」四态
- [x] 40 项特调组件逐项落地（§3）
- [x] v4 四条裁定（A-07~A-10）全部落地（§4）；`--arena-*` 与涨跌色解耦实测
- [x] 未派发子任务；未改 `runtime/**`；未写后端业务代码

## 下游交接

- **主消费方**：`dev-lead`（G-FE-01 评审）。需其执行：核对 §3 映射 40/40、§4 的 v4 四条裁定、确认无假数据/无前端业务计算、抽查四态与命脉组件。
- **次消费方**：`backend-dev`（按 `12-interface-request` v2 实现，v4 追加字段必带）、`qa`（负向用例：未知不含 `+0.00%`、徽章=mode、立方体空样本格不渲染 0/50%、**空样本格 `naive_p=null`**、竞技场色值不得等于涨跌色 token、影子盘无编辑入口、`weighting_basis` 非 `market_value` 时 `/tasks` 拒绝）。
- **契约缺口**：`12-interface-request` §10（建议列、`/predictions` 的 `tier/market_value`、`llm.base_url`、precision 标签、`window_min_days` 结构、`license_lines` 键名）待架构师裁定；未裁定前前端保持降级/双形态兼容，不阻塞联调。
- **残留风险**：
  1. 引擎页立方体/竞技场宽屏信息密度高，≤900px 已改单列/横滚，仍需 UI 走查（责任人：frontend-dev，期限：S4）。
  2. 多接口并行 `as_of` 不同时，目前仅全局/引擎页标时点，未逐卡标时（责任人：frontend-dev，期限：S4）。
  3. `holdings` 的建议列、`analyze` 的 tier/市值目前依赖占位/展示连接，待缺口裁定后改为直读（责任人：frontend-dev，期限：S3 收口）。
  4. 本轮未采集 console 事件（责任人：qa，期限：S4）。
  5. ES module 需经 `http://127.0.0.1` 访问（责任人：dev-lead，期限：S5，README 已写）。
