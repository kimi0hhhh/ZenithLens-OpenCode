---
artifact: 13-frontend-report
owner: frontend-dev
version: v1
status: draft
supersedes: -
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端实现报告 · 极境 ZenithLens（S3 · OC-S3-FE）

> 产出：`C:\Users\10719\Documents\ZenithLens-OpenCode\static\`（纯静态、零依赖、无构建步骤）。
> 依据：`04-ui-wireframe.html` v2（不删减）、`07-frontend-arch.md` v2、`09-api-contract.md` v3（字段唯一法律）。
> 交付物：`static/index.html` + `static/css/app.css` + `static/js/**`（ES 模块）+ `docs/02-frontend/12-interface-request.md`。

## 摘要

1. 交付一个原生 HTML/CSS/ES module 产品壳：**1 个外壳 + 7 个视图 + 3 个命脉组件 + 1 个四态容器**，由 `python -m http.server` 或后端 `server/` 直接托管，无 npm、无打包、Python 3.8+ 可跑。
2. **Brief §9 的 40 项特调组件逐项落地**（映射见 §3），含 125 格立方体 naive/DDSM 双切片、因子四盘+治理长文、`.vb` 估值徽章、`.chain-item` 推导链、竞技场矩阵、影子盘台账、六维 z-bar、估值精度汇总、覆盖度四档、信号时间线、三 dialog/popover/toast、livebar。
3. **四态统一**：所有数据视图经 `components.js#mountState` 渲染；空/加载/错误/成功可手动演示（R-UI-40 状态条），且经真浏览器验证。
4. **命脉约束落地**：所有请求经 `api.js`（无裸 fetch）；数字格式化唯一入口 `format.js`；估值徽章由后端 `mode_label/confidence_color_class` 驱动；`null` 一律「未知/—」（无 `+0.00%`）；隐私打码全站 `.amt` 生效。
5. **造壳不造假**：mock 隔离在 `static/js/mock/`，**默认关闭**（`?mock=1` 或 `localStorage.zl_mock='1'` 才开）；前端不做组合加权/命中率等业务计算，仅做展示连接与格式化。
6. 真浏览器（Edge headless + CDP）冒烟：`?mock=1` 下 7 视图全部 `success`、**控制台零报错**；去掉 mock 后正确进入 error 四态（无假数据）。证据见 §5。

## 正文

### 1. 交付清单与目录

| 路径 | 行数 | 说明 |
|---|---|---|
| `static/index.html` | 358 | 唯一 HTML 外壳（7 视图 + 3 dialog + popover + toast 容器） |
| `static/css/app.css` | 334 | 设计 token + 布局 + 组件样式（玻璃拟态、涨红跌绿、响应式断点） |
| `static/js/api.js` | 93 | ★ 唯一 fetch 出口：超时（8s/30s）、统一信封、`ApiError{code}`、mock 注入点 |
| `static/js/store.js` | 45 | 单一 store + 订阅重渲染；每切片自带四态 |
| `static/js/format.js` | 113 | ★ 数字唯一格式化出口（金额/概率/比率/Δpp/lift/z/日期） |
| `static/js/copy.js` | 71 | 四态文案 + 错误码文案 + 枚举中文映射 |
| `static/js/components.js` | 214 | `mountState`、`valBadge`、`unknownCell`、`forecastCard`、`chainHTML`、`cubeSliceHTML`、`zbar`、`toast`、`showModal` 等 |
| `static/js/main.js` | 173 | 入口：路由、顶栏/livebar、SW 注销、隐私、四态演示、runtime 轮询 |
| `static/js/views/holdings.js` | 420 | ① 持仓（R-UI-01~06 + CRUD + dialog/popover） |
| `static/js/views/analyze.js` | 113 | ② 分析（R-UI-10~13） |
| `static/js/views/signals.js` | 120 | ③ 信号（R-UI-07~09） |
| `static/js/views/factors.js` | 239 | ④ 因子（R-UI-14~19） |
| `static/js/views/review.js` | 98 | ⑤ 复盘（R-UI-28~31） |
| `static/js/views/engine.js` | 288 | ⑥ 引擎（R-UI-20~27） |
| `static/js/views/settings.js` | 194 | ⑦ 设置（R-UI-32~36） |
| `static/js/mock/mock.js` | 516 | mock 后端替身（默认关闭，字段按契约 v3） |
| `static/README.md` | — | 启动说明 + 接口运用规范 |

**启动**：`cd static; python -m http.server 8787 --bind 127.0.0.1` → 浏览器 `http://127.0.0.1:8787/index.html`。
必须经 `http://` 访问（ES module 在 `file://` 下被浏览器拦截），与 AGENTS「不要双击 HTML」同因。

### 2. 架构落地（对照 07-frontend-arch）

- **无框架/无打包**：ES2019 module，浏览器原生 `<script type="module">` 加载；不引入 Redux/Vue，store 用原生订阅（45 行）。
- **单一 fetch 出口**：`views/*` 只调 `api.js` 的 `get/post/put/del/loadSlice`；全仓 `grep "fetch("` 仅命中 `api.js`。超时按路径名单（风险/预测/复盘/因子/引擎重计算 30s，其余 8s）。
- **四态**：`mountState(container, view, slice, onRetry, facts)` 统一渲染；`empty` 仅由「成功且集合为空」触发（`loadSlice` 的 `emptyWhen`），引擎离线走 error/陈旧（A-06）。
- **命脉组件**：`valBadge`（读 `valuation_mode→mode_label` + `confidence_color_class`）、`unknownCell/changeCell/pnlCell`（阻断 `+0.00%`）、`PrivacyMask`（`body.masked .amt`）。
- **格式化唯一入口**：`format.js` 提供 `amt/prob/rate/delta/lift/score/nav/shares/z/cls` 等，视图不得自行拼百分比。
- **响应式**：≥1100 侧栏常驻；900~1100 两列；≤900 侧栏转底栏、表格/卡片单列。

### 3. Brief §9 · 40 项特调组件落地映射

| # | 组件 | 实现位置 | 数据来源（契约） |
|---|---|---|---|
| 9.1-1 | 资产总览四卡 + 覆盖度说明 | `views/holdings.js#renderOverview` `#pa-*` | `/holdings` summary |
| 9.1-2 | 估值精度汇总条 `.vsum` | `#renderVSum` `#val-sum` | `/valuations/precision` |
| 9.1-3 | 估值来源徽章 `.vb` 五档 + `.ch/.cm/.cl/.cu` | `components.js#valBadge` | `Valuation{mode_label,confidence_color_class,mae_rate,dir_hit_rate,n_test,trace_text,nav_date}` |
| 9.1-4 | 覆盖度四档 `.covbar` + 失效三类 | `#renderCoverage` `#cov-bar/#cov-note` | `/holdings/coverage` |
| 9.1-5 | 持仓明细表（分组/列显隐/T+2/未知≠持平） | `#renderTable` `#hd-body` | `/holdings` |
| 9.1-6 | 风险指标折叠区 | `#fold-risk` `#loadRisk` | `/holdings/risk` |
| 9.2-7 | 信号空态四要素 | `views/signals.js#renderEmpty` `#sg-empty` | `/signals/state` |
| 9.2-8 | 触发门 E1/E3 + E2/E4 剔除 | `#renderGates` `#sg-gates/#sg-excl` | `/signals/state` |
| 9.2-9 | 信号时间线 `.tl/.tl-item/.sigcard/.ev` | `#renderTimeline` `#tl-list` | `/ledger` + `/ledger/chain` |
| 9.3-10 | T+1 口径 + 三执行路径 | `views/analyze.js#renderDefs` `#an-defs` | `/meta/definitions` |
| 9.3-11 | 三窗口组合卡 + 加权规则 | `#renderForecast` + `components#forecastCard` | `/portfolio/forecast` |
| 9.3-12 | 参与预测持仓表 | `#renderTable` `#an-body` | `/predictions` |
| 9.3-13 | 推导链 `.chain/.chain-item` 六步 | `components#chainHTML` | `/predictions/{code}`、`/ledger/chain` |
| 9.4-14 | 因子四盘 + 因子行 + 跑分表 | `views/factors.js#renderPans/#toggleScoreDetail` | `/factors/pans`、`/factors/score-detail` |
| 9.4-15 | 四本账本 + 示例记录 | `#renderBooks/#openBook` | `/factors/books`、`/factors/books/{book}` |
| 9.4-16 | 评分链长文（悬崖/bootstrap/四裁判） | `#renderScoreChain` `#fc-score` | `/factors/score-chain` |
| 9.4-17 | 治理周期卡 | `#renderGovernance` `#fc-cycle` | `/factors/governance-cycle` |
| 9.4-18 | 最近挖掘记录 F1/F2/F3 | `#renderDigRecords` `#fc-scan` | `/factors/dig-records` |
| 9.4-19 | 生命周期规则长文 | `#renderLifecycle` `#fc-life` | `/factors/lifecycle` |
| 9.5-20 | HUD 六卡 | `views/engine.js#renderHud` `#eg-hud` | `/engine/status` |
| 9.5-21 | 影子盘台账 + 进度条 + 字段说明 | `#renderShadow` `#eg-ledger*` | `/ledger/shadow` |
| 9.5-22 | 因子竞技场矩阵 | `#renderArena` `#eg-arena` | `/engine/arena` |
| 9.5-23 | 训练状态卡 | `#renderTraining` `#eg-train` | `/engine/training-status` |
| 9.5-24 | 冻结参数表 | `#renderFrozen` `#eg-frozen` | `/engine/frozen-params` |
| 9.5-25 | 六维输入 z-bar | `#renderDims` `#dim-d3/#dim-d6` | `/engine/inputs` |
| 9.5-26 | 125 格立方体 naive/DDSM + vr 层 | `#renderCube` + `components#cubeSliceHTML` | `/engine/ddsm/cube` |
| 9.5-27 | 引擎注册表三态 | `#renderRegistry` `#eg-registry`/`#st-registry` | `/engine/registry` |
| 9.6-28 | 历史成绩 hero | `views/review.js#renderHero` `#rv-hero` | `/review/scores` |
| 9.6-29 | 三窗口 vs 基线表（待填充留空） | `#renderScores` `#rv-scores` | `/review/scores` |
| 9.6-30 | 影子盘降级审查条 idle/ok/bad | `#renderDegrade` `#rv-degrade` | `/engine/shadow-review` |
| 9.6-31 | 逐笔对账表 | `#renderRecon` `#rv-body` | `/review/reconciliation` |
| 9.7-32 | 隐私开关 | `views/settings.js#savePrivacy` `#sw-hide` | `/settings` PUT/GET |
| 9.7-33 | LLM 接口 + 三硬约束 + 温度 0 | `#renderLlm/#saveLlm` | `/settings` |
| 9.7-34 | 数据源健康表 | `#renderSources` `#src-box` | `/data-sources/health`、`/probe` |
| 9.7-35 | 持仓数据卡 + 两份文件不一致长文 | `#renderHoldingsData` `#hd-data/#hd-diff` | `/settings/holdings-data` |
| 9.7-36 | 关于卡 | `#renderAbout` `#about-card` | `/about` |
| 9.8-37 | 三 dialog + popover + toast | `index.html#dlg-fund/#dlg-amt/#dlg-del/#pop/#toast`；`holdings.js` | `/holdings` CRUD + `/transactions` |
| 9.8-38 | 注销 Service Worker | `main.js` 顶部 | 纯前端 |
| 9.8-39 | livebar 真实数据接入条 | `main.js#renderLivebar` `#livebar` | `/runtime` + `/data-sources/health` |
| 9.8-40 | 四态覆盖 | `components#mountState` + `main.js#setDemoState` | 全局 |

### 4. 硬性约束逐条自查

1. **40 项组件齐全**：§3 映射 40/40；`index.html` 保留线框全部容器与长文区块，未删减。
2. **四态全部实现**：7 视图 × 4 态 → `mountState` + `STATE_COPY`；顶栏状态条可逐页切换（R-UI-40）。
3. **数据来源可信**：估值徽章读后端 `mode_label/confidence_color_class`；`null` 渲染「未知/—」；`unknown` 行 `market_value=null` 分列 `fallback_value`。
4. **隐私打码**：`body.masked .amt`（含子节点隐藏 + `••••` 覆盖），占比/涨跌不遮；开关经 `PUT /settings` 持久化。
5. **无前端业务计算**：组合加权 `weighted_p`、覆盖占比、命中率、Δ、k_lift/得分、Δ 全取后端；前端唯一"算术"是展示层 ×100/千分位（`format.js`）与把 `code` 连接到 `holdings` 的 `tier/market_value`（展示连接，已在 `12-interface-request` §3-2 登记缺口）。
6. **字段名逐字对齐 v3**：全部 `snake_case`，无驼峰；`written_at`/`created_at` 双字段并存；`veto_*_status` 三态。
7. **零构建/可 3.8+ 起服**：无 npm、无编译；`python -m http.server` 实测可跑。
8. **控制台无报错**：CDP 实测（§5）。
9. **未修改契约/架构文件、未写 Python 业务代码、未改 `runtime/**`、未派发子任务**。

### 5. 真浏览器冒烟证据（Edge headless + CDP）

- 启动：静态服务 `python -m http.server 8795`；`?mock=1` 加载 `index.html`。
- 结果（`document` 运行时读取）：
  - holdings：`success`，明细 12 行（8 持仓 + 4 分组），精度分组 4、组合卡 3、覆盖四档 4；
  - analyze：参与预测 5 行；signals：门卡 2、时间线 5；factors：四盘 4、账本 4、挖掘 5、生命周期文本；
  - review：hero `58.3%`、逐笔 5；engine：HUD 6、竞技场 7 行、立方体 25 格/层、六维 `3+6`、注册表 3；
  - settings：数据源 4、关于卡完整；`console` 事件为空，无 `Runtime.exceptionThrown`。
- 交互断言：
  - 未知行 `025500`：涨跌列「未知」、今日盈亏「—」，**不含 `+0.00%`**（未知≠持平 ✓）。
  - 徽章：`017412→官方净值`、`008087→代理近似`、`014320→盘中估算`、`025500→未知`（mode 驱动 ✓）。
  - 隐私按钮：`body.masked=true`（35 个 `.amt` 打码），再点恢复 ✓。
  - 四态条：空/加载/错误文案正确，回成功态后 12 行恢复 ✓。
  - dialog 打开/关闭、行菜单 popover（加仓/减仓/编辑/删除）、时间线展开六步链 ✓。
- 去 mock（真实后端缺席）：holdings 进入 `error` 态「读取持仓失败 / 数据格式错误」+ 重试，livebar warn，**无假数据** ✓。

### 6. mock 使用与切换

- 开关：URL `?mock=1` 或 `localStorage.setItem('zl_mock','1')`；**默认关闭**。
- 隔离：仅 `static/js/mock/`，由 `main.js` 动态 `import()`，生产路径不加载。
- 注入：`api.enableMock(mockRequest)`；对接后端时删除开关即可，视图层零改动。
- 覆盖：40 个只读接口 + 8 个写接口（CRUD/transaction/import/probe/settings）的替身响应，字段按 v3。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（R-UI-40 状态条 + CDP 验证）
- [x] 所有请求走统一封装层，页面层无裸 fetch（全仓仅 `api.js` 出现 `fetch(`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`
- [x] 数字格式化走统一工具函数 `format.js`，涨红跌绿正确
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可直接以 `python -m http.server`（Python 3.8+）启动，控制台无报错
- [x] `12-interface-request.md` 每条都写了「前端如何处理」四态
- [x] 40 项特调组件逐项落地（§3）

## 下游交接

- **主消费方**：`dev-lead`（G-FE-01 评审）。需其执行：核对 §3 映射 40/40、确认无假数据/无前端业务计算、抽查四态与命脉组件。
- **次消费方**：`backend-dev`（按 `12-interface-request` 实现 40 接口）、`qa`（按四态与命脉组件建负向用例：未知不含 `+0.00%`、徽章=mode、立方体空样本格不渲染 0/50%、影子盘无编辑入口）。
- **契约缺口**：`12-interface-request` §3（建议列、`/predictions` 的 `tier/market_value`、`llm.base_url`、precision 标签、组合规则长文、`window_min_days` 结构）待架构师裁定；未裁定前前端保持降级展示，不阻塞联调。
- **残留风险**：
  1. 引擎页立方体/竞技场宽屏信息密度高，≤900px 已改为单列/横滚，仍需 UI 走查（责任人：frontend-dev，期限：S4）。
  2. 多接口并行 `as_of` 不同时，目前仅全局/引擎页标时点，未逐卡标时（责任人：frontend-dev，期限：S4）。
  3. `holdings` 的建议列、`analyze` 的 tier/市值目前依赖展示连接/占位，待缺口裁定后改为直读（责任人：frontend-dev，期限：S3 收口）。
  4. ES module 需经 `http://127.0.0.1` 访问（责任人：dev-lead，期限：S5，README 已写）。
