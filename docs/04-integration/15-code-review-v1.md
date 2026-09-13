---
artifact: 15-code-review
owner: dev-lead
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [frontend-dev, backend-dev, architect, qa, orchestrator]
gate: G-DL-01
---

# 代码评审与方向纠偏 · 极境 ZenithLens（S4 · OC-S4-DL）

> 上游：`docs/02-frontend/13-frontend-report.md`、`docs/02-frontend/12-interface-request.md`、
> `docs/03-backend/14-api-impl-report.md`、`docs/01-architecture/07-frontend-arch.md`、`08-backend-arch.md`、
> `09-api-contract.md`(v3)、`docs/PROJECT_BRIEF.md` §9、`docs/00-charter/02-prd.md`、`03-ui-design.md`。
> 方法：**先过方向偏差六项 → 再逐项对照 Brief §9 的 40 项组件 → 再起服 curl 实地抽验 → 最后代码设计**。
> 只读源码与报告，未修改任何产品代码 / `09-api-contract` / `runtime/**`，未派发子任务。

## 摘要

1. **方向不偏**：Brief §9 的 40 项特调组件在前端 `static/` 全部落地（40/40），发布态**无假数据填充**——mock 隔离且默认关闭，真实后端缺席时走 error/空态。
2. **门禁 G-DL-01 = CONCERN（有条件放行）**：未触「前端造假数据」红线（判 PASS 级），但实测到 **2 条 BLOCK**（纯前端展示缺陷 + 1 条契约结构漂移），已登记 `open-issues`，修复前不作为可交付版。
3. **G-DL-02 = PASS**：`python app.py` 在 Python 3.8.6 起服，`/` 直出前端，`http://127.0.0.1:8791` 可加载；`build/README-START.md` 三步可启动。
4. **契约缺口 8 条**（其中 6 条阻塞组件按 §9 交付）已逐条定性分流：建议 **架构师裁定 6 条 → 前端/后端改**；**后端 9 条偏差**逐条分流，无「直接转发给前端」。
5. 已知限制与残留风险已列于 `## 下游交接`，并写入 build 说明。

## 正文

### 0. 门禁判定

| 门禁 | 判定 | 依据 |
|---|---|---|
| **G-DL-01 · 组长评审** | **CONCERN** | 方向六项无造假数据红线；但 2 条 BLOCK 未关闭（已登记 `open-issues.md`），其余 CONCERN 项登记排期 |
| **G-DL-02 · 开发版构建** | **PASS** | 产物可独立启动（实测 200）；`README-START.md` 三步内启动；版本随快照时间戳绑定 |

### 1. 方向偏差六项检查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 需求对齐 | ✅ PASS | 40 项组件全部可追溯到 Brief §9 / `02-prd`；未见 PRD 外的自造功能。引擎/因子页的**空集**是「引擎未产出」的诚实状态，非功能缺失。 |
| 2 | 范围蔓延 | ✅ PASS | 全部 §9 组件为 P0 已落地；无「做了 P2 丢 P0」。`mock.js` 属开发替身，默认关闭，非交付功能。 |
| 3 | 职责越界 | ⚠️ CONCERN | 前端**不做**组合加权/命中率/Δ/k_lift（全取后端）。仅 1 处跨接口展示连接：`analyze.js:88` 用 `/holdings` 的 `tier/market_value` 拼预测表（已在 `12-interface-request §3-2` 登记）。后端回传 `mode_label/confidence_color_class` 属契约要求，不算越界。 |
| 4 | 假数据残留 | ✅ PASS（无红线） | `main.js:140` 仅当 `?mock=1`/`localStorage.zl_mock` 才 `import('./mock/mock.js')`，**默认关闭**；真实后端缺席时 `api.js` 抛错进 error 四态。全仓 `grep fetch(` 仅命中 `api.js:60`。**未发现前端造假数据填满界面。** |
| 5 | 契约漂移 | ❌ CONCERN（含 BLOCK） | 见 §4 BLOCK-2：`window_min_days` 结构后端实现 `{window,n_w}` 与契约 §5.14 `{d15:5,...}` 不一致，前端首键取值逻辑失配；`/engine/ddsm/cube` 的 `color_band/legend` 未消费（§4 SHOULD-1）。 |
| 6 | 四态缺失 | ✅ PASS | `components.js#mountState` 统一承载空/加载/错误/成功；`main.js#setDemoState` 提供逐页切换（R-UI-40）；各子块有就地降级文案。 |

**头号信号（造假数据）未触发 → 不判 FAIL。** 但第 5 项引出的数字/结构错误见 §4，故 G-DL-01 记 CONCERN。

### 2. Brief §9 特调组件 40 项对照（缺一即方向偏差）

> 对照方式：`static/index.html` 容器 + 视图渲染函数双查，确认每项既有 DOM 容器又有后端字段绑定。

| # | 组件 | 落地位置（file:line） | 判定 |
|---|---|---|---|
| 9.1-1 | 资产总览四卡+覆盖说明 | `views/holdings.js:71` `#pa-*` | ✅ |
| 9.1-2 | 估值精度汇总 `.vsum` | `views/holdings.js:93` `#val-sum` | ✅ |
| 9.1-3 | 估值来源徽章 `.vb` 五档+配色 | `components.js:68` | ✅ |
| 9.1-4 | 覆盖度四档 `.covbar`+失效三类 | `views/holdings.js:135` `#cov-bar` | ✅ |
| 9.1-5 | 持仓明细表（分组/列显隐/T+2/未知≠持平） | `views/holdings.js:155` `#hd-body` | ✅ |
| 9.1-6 | 风险指标折叠区 | `views/holdings.js:281` `#fold-risk` | ✅ |
| 9.2-7 | 信号空态四要素 | `views/signals.js:48` `#sg-empty` | ✅ |
| 9.2-8 | 触发门 E1/E3 + E2/E4 剔除 | `views/signals.js:82` `#sg-gates/#sg-excl` | ✅ |
| 9.2-9 | 信号时间线 `.tl/.sigcard/.ev` | `views/signals.js:104` `#tl-list` | ✅ |
| 9.3-10 | T+1 口径+三执行路径 | `views/analyze.js:41` `#an-defs` | ✅ |
| 9.3-11 | 三窗口组合卡+加权三规则 | `views/analyze.js:60` `#pf-forecast/#an-forecast` | ✅ |
| 9.3-12 | 参与预测持仓表 | `views/analyze.js:71` `#an-body` | ✅ |
| 9.3-13 | 推导链 `.chain` 六步 | `components.js:128` / `analyze.js:117` | ✅ |
| 9.4-14 | 因子四盘+因子行+跑分表 | `views/factors.js:56` `#fc-pans` | ✅ |
| 9.4-15 | 四本账本+示例记录 | `views/factors.js:137` `#fc-books` | ✅ |
| 9.4-16 | 评分链长文 | `views/factors.js:174` `#fc-score` | ✅ |
| 9.4-17 | 治理周期卡 | `views/factors.js:197` `#fc-cycle` | ✅ |
| 9.4-18 | 最近挖掘记录 F1/F2/F3 | `views/factors.js:210` `#fc-scan` | ✅ |
| 9.4-19 | 生命周期规则长文 | `views/factors.js:233` `#fc-life` | ✅ |
| 9.5-20 | HUD 六卡 | `views/engine.js:100` `#eg-hud` | ✅ |
| 9.5-21 | 影子盘台账+进度条+字段说明 | `views/engine.js:118` `#eg-ledger` | ✅ |
| 9.5-22 | 因子竞技场矩阵 | `views/engine.js:162` `#eg-arena` | ✅ |
| 9.5-23 | 训练状态卡 | `views/engine.js:191` `#eg-train` | ✅ |
| 9.5-24 | 冻结参数表 | `views/engine.js:208` `#eg-frozen` | ✅（值错见 BLOCK-2） |
| 9.5-25 | 六维输入 z-bar | `views/engine.js:234` `#dim-d3/#dim-d6` | ✅ |
| 9.5-26 | 125 格立方体 naive/DDSM+vr 层 | `views/engine.js:263` + `components.js:177` | ✅ |
| 9.5-27 | 引擎注册表三态 | `views/engine.js:296` `#eg-registry/#st-registry` | ✅ |
| 9.6-28 | 历史成绩 hero | `views/review.js:36` `#rv-hero` | ✅ |
| 9.6-29 | 三窗口 vs 基线（待填充留空） | `views/review.js:51` `#rv-scores` | ✅ |
| 9.6-30 | 影子盘降级审查条 idle/ok/bad | `views/review.js:73` `#rv-degrade` | ✅ |
| 9.6-31 | 逐笔对账表 | `views/review.js:90` `#rv-body` | ✅ |
| 9.7-32 | 隐私开关 | `views/settings.js:51` `#sw-hide` | ✅ |
| 9.7-33 | LLM 接口+三硬约束+温度 0 | `views/settings.js:81` + `index.html:298` | ✅ |
| 9.7-34 | 数据源健康表 | `views/settings.js:133` `#src-box` | ✅ |
| 9.7-35 | 持仓数据卡+两文件不一致长文 | `views/settings.js:172` `#hd-data/#hd-diff` | ✅ |
| 9.7-36 | 关于卡 | `views/settings.js:202` `#about-card` | ✅ |
| 9.8-37 | 三 dialog+popover+toast | `index.html:347` + `views/holdings.js:308` | ✅ |
| 9.8-38 | 注销 Service Worker | `main.js:18` | ✅ |
| 9.8-39 | livebar 真实数据接入条 | `main.js:86` `#livebar` | ✅ |
| 9.8-40 | 四态覆盖各页 | `components.js:20` + `index.html:42` | ✅ |

**结论：40/40 落地，无方向偏差。**

### 3. 实地抽验（起服 curl + 读源码，≥3 条）

环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`，`app.py:38`）后台起服；`/api/v1/*` 真实请求。

| # | 抽验 | 实测结果 | 判读 |
|---|---|---|---|
| V1 | `GET /api/v1/runtime` | `200 ok`，`port=8791`，`engine_status=online`，`staleness.is_stale=true / latest_date=2026-08-25 / days_behind=18`，`open_count=0` | 起服正常；**快照滞后 18 天如实上报**，未伪装新鲜 |
| V2 | `GET /holdings` | 22 行；`summary.total_value=53092.77`，`covered_count=22/22`；`mv_source=nav`；`025500 tier=D` 无 `prediction`（C/D 档为 null） | 未知/降级如实；未见成本回退 |
| V3 | `GET /valuations/precision` | `weighted_mae_rate=0.002`，`industry_baseline_mae_rate=0.008`，`mode_distribution=proxy:10, unknown:12` | 与 14-report 一致；MAE 为真实小样本 |
| V4 | `GET /predictions` + `/portfolio/forecast` | 预测 10 行，`gate=none`、`signal=gray`、`p_up≈0.7381`；组合三窗口 `direction=gray`、`weighted_p=null`、`open_count=0`、`coverage_threshold_met=false` | `gate=none→gray`（D5 优先级）按契约；无开口不硬造方向 |
| V5 | `GET /engine/ddsm/cube?code=017193` | `dims=r2,om,vr`，`bins=5`，5 层×25 格；filled 格 `ddsm_p=0.3923`、`ddsm_n=11`、`color_band` 字段在；`comparison.walk_forward_delta_*_pp=null` | 空样本/未回测**显式 null**，无 0/50% 冒充 |
| V6 | `GET /engine/frozen-params` | `window_min_days=[{"window":"d15","n_w":5},...]` | 结构=`{window,n_w}`，**与契约 §5.14 `{d15:5,...}` 不符** → BLOCK-2 |
| V7 | `GET /signals/state` | `gates`: E3 `effect_pp=3.9`、E1 `0.88`；`excluded`: E2 `-3.09`、E4 `-2.72`（契约 §5.4 `effect_pp` 单位=百分点） | 前端 `×100` → 显示 `+390.00pp` / `-309.00pp` → BLOCK-1 |
| V8 | 静态托管 | `GET /`=200（25814B，含 `js/main.js`）、`GET /js/api.js`=200、`GET /css/app.css`=200 | `app.py` 直出前端，build 可一步启动 |
| V9 | 源码核假数据 | `grep "fetch("` 仅 `api.js:60`；`mock` 仅 `main.js:140` 条件加载 | 无裸 fetch、mock 默认关闭 |

### 4. 代码设计评审（BLOCK / SHOULD / NIT）

#### BLOCK（必须改，未关不进交付）

- **BLOCK-1 · `effect_pp` 二次 ×100（数字错误，生产路径）**
  - 位置：`static/js/views/signals.js:93` 与 `:97`。
  - 现象：后端按契约 §5.4 返回 `effect_pp` 单位=**百分点**（E3=3.9、E1=0.88、E2=−3.09、E4=−2.72）。前端 `(g.effect_pp * 100).toFixed(2) + 'pp'` → 渲染 `+390.00pp` / `-309.00pp`。
  - 期望：直接 `effect_pp.toFixed(2)+'pp'`（或经统一 `format` 的 pp 出口）。
  - 根因：前端把「百分点」当「小数比率」处理，与 `delta_pp`/`rate` 口径混淆。
  - 定性：**前端实现缺陷**（契约无误）。违反 Brief §4「数字错误→直接失败」。

- **BLOCK-2 · `window_min_days` 结构漂移致冻结表显示错值**
  - 位置：后端 `engine.py`/`app.py` 返回 `{window,n_w}`；前端 `static/js/views/engine.js:222` 用 `w[Object.keys(w)[0]]` 取「首键」。
  - 现象：契约 §5.14 定义为 `{d15:5,d30:10,...}`；后端改为 `{window:"d15",n_w:5}`。前端取首键拿到的是 `"d15"`（窗口名）而非分母 `5`，冻结参数表「准入度分母 N_w」一栏显示 `d15 / d30 / d60 / m6 / m24 / full`，**语义错误**。
  - 期望：契约明确结构为 `[{window, n_w}]`，前端改读 `w.n_w`；或后端回退契约 `{d15:5,...}`。
  - 根因：契约 §5.14 只注 `array[object]` 未定键名（缺口 6），后端自定 `{window,n_w}`，前端按旧假设取首键。
  - 定性：**契约歧义（架构师）→ 后端/前端双边对齐**。

#### SHOULD（建议改，可排下轮）

- **SHOULD-1 · 立方体颜色/图例未消费后端字段**：契约给 `cell.color_band`（实测存在）与 `comparison` 旁 `legend[]`（`{min_p,max_p,label}`），但 `components.js:170` 的 `CUBE_BANDS` 自算阈值、`index.html:265-271` 写死图例 → 后端阈值一改即分叉。建议改读 `color_band`/`legend`。
- **SHOULD-2 · 跨接口展示连接**：`analyze.js:82-98` 用 `/holdings` 拼预测表 `tier/market_value`；契约缺口 2 裁定后应改直读，消除前端拼装。
- **SHOULD-3 · mock 随静态目录发布**：`static/js/mock/mock.js` 保留在交付物中（默认关闭）。建议交付包剔除或加显式 `MOCK` 徽章校验，防误开。
- **SHOULD-4 · DDSM 对比列硬编码结论**：`engine.js:281` 固定输出「全部 N 格有值」，未依据 `comparison.empty_count_ddsm`；若某资产 DDSM 仍有空格会误导。
- **SHOULD-5 · 精度分组显示原始枚举**：`holdings.js:103` 直接渲染 `high/mid/low/unknown`，待契约缺口 4 补 `label` 后改中文。

#### NIT（可不改）

- **NIT-1 · 静态 `0.80%` 硬编码**：`index.html:64` 写死「行业基准 MAE 0.80%」，与契约固定值 `industry_baseline_mae_rate=0.008` 重复；建议引用后端同值或注明来源。
- **NIT-2 · 常量重复**：`copy.js:69` 的 `DIRECTION_REASON` 与 `components.js:216` 的 `DIR_REASON` 内容重复。
- **NIT-3 · `cube` 多取一次 slice**：`engine.js:265`/`:269` 两次 `getSlice('cube')`，可合并。

> 严重度分布：BLOCK 2 / SHOULD 5 / NIT 3。非「全 NIT」，亦非「全 BLOCK」。

### 5. 前端 6 条契约缺口 · 定性分流

> 来源：`13-frontend-report.md` 下游交接列出的 6 条阻塞缺口（`12-interface-request §3` 1~6；§3 的 7~8 为非阻塞，附后）。

| # | 缺口 | 定性 | 分流 | 处置建议 |
|---|---|---|---|---|
| 1 | 建议列无 `advice` 字段 | 契约缺字段（缺数据源） | **架构师** → 后端 | 契约追加 `advice/advice_label`，后端按规则产出；前端改为直读（当前渲染「—」，无假造） |
| 2 | `PredictionSummary` 无 `tier/market_value` | 契约缺字段 | **架构师** → 后端 | 追加两字段，前端去掉跨接口展示连接 |
| 3 | `Settings.llm` 无 `base_url` | 契约缺字段 | **架构师** → 后端 | 追加 `llm.base_url`（`GET/PUT` 可读写）；实测 `/settings` 返回 `base_url` 为空 |
| 4 | precision `groups` 无中文 `label` | 契约缺字段（§8 明言不改元素） | **架构师** → 后端/前端 | 追加 `label`，或前端用统一枚举映射；当前显示原始枚举 |
| 5 | 组合「加权三规则」长文无字段 | 契约缺文案字段 | **架构师 + PM** | 追加可选 `rules_text`；现状前端用静态产品文案（非业务数字），可接受 |
| 6 | `window_min_days` 结构未定义 | 契约歧义（**已引发 BLOCK-2**） | **架构师** → 后端+前端 | 冻结为 `[{window,n_w}]` 并双方对齐；见 §4 BLOCK-2 |
| 7 | `CyclePhase.last_run_at` 可空 | 非阻塞语义确认 | 架构师 | 前端已显示「—」，仅确认语义 |
| 8 | 顶层 `empty` 与 `engine_status` 判定权 | 非阻塞 | 架构师 | 现状 error/成功两态处理，可接受 |

**共性结论**：6 条阻塞缺口中 **5 条是「契约只加字段不改名」即可闭合的缺字段**，应由架构师终裁并版本 +1；**1 条（#6）是已致显示错误的歧义**，优先级最高。**不要求前端自造字段。**

### 6. 后端 9 条偏差 · 定性分流

> 来源：`14-api-impl-report.md §4` D1~D9。逐条「先定性再分流」。

| # | 偏差 | 定性 | 分流 | 处置 |
|---|---|---|---|---|
| D1 | 端口 8787→8791 | 契约与派发不一致（非缺陷） | **架构师**（改 §1.4 或确认 `/runtime.port` 为准） | 已由派发指定 8791；建议契约注记 |
| D2 | 代理映射未冻结（10 只 A / 12 只 D） | 配置假设，非实现错 | **架构师** 复核 `PROXY_MAP` | 定稿后升级 B/C（不阻塞本轮） |
| D3 | `legacy_path` 取值未定义 | 契约缺定义 | **架构师** 确认定义 | 现状取 `.bak`，可接受 |
| D4 | proxy MAE/命中率样本仅 7 日 | 数据成熟度（非算错） | **后端 + 架构师** | 40 日回测产出后回填；当前小样本已标 `n_test` |
| D5 | 门优先 / 否决 missing 优先 | 口径解释 | **架构师** 确认优先级 | 与 §4.5/A-05 一致，无需改 |
| D6 | T15 给 `p` 但组合 `weighted_p=null` | 按契约尾注实现 | **无需分流**（符合 §5.7） | 关闭 |
| D7 | `import.merge` 语义未冻结 | 契约自身 CONCERN | **架构师** | 本期 UI 只用 `replace`，可接受 |
| D8 | 因子治理空集/常量、bootstrap/effect_pp 为固定展示常量 | 部分为「引擎未产出」，部分为契约常量 | **架构师（引擎交付）+ PM（常量口径）** | 空集诚实；常量需标注来源，禁止 legacy 数字冒充实测 |
| D9 | holdings 档未抓重仓（`no_report`） | 诚实降级，非缺陷 | **后端**（排期增强） | 现状 `trace` 明示 `hit=false`，不阻塞 |

**分流纪律**：无一条「直接转发前端」。凡「做对了但定义不清」→ 架构师；「做对了但不该这么定义」→ PM；「实现错」→ 前端/后端。

### 7. 假数据判定（头号信号）

- 生产路径（无 `?mock`）唯一 fetch 出口 `api.js`；`main.js:140` 条件动态 `import` mock。
- 实起后端后各页取真实数据（见 §3），空集页（factors/arena/ledger）显示「（当前为空）/暂无配置/待写入」，**未用 mock 数字补位**。
- 结论：**未触碰 G-DL-01「前端造假数据」红线 → 不判 FAIL**。

## 自验收

- [x] 方向偏差六个检查项全部过过一遍，结论落盘（§1）
- [x] 代码评审问题标注了 BLOCK/SHOULD/NIT 严重度（§4：2/5/3）
- [x] 缺陷全部完成定性分流，无「直接转发」（§5、§6）
- [x] 所有 BLOCK 问题已登记到 `open-issues`（BLOCK-1、BLOCK-2）
- [x] 开发版可独立启动，README-START 三步内可跑（实测 `/`=200）
- [x] 已知限制清单已写明（下游交接）
- [x] Brief §9 的 40 项组件逐项对照（§2，40/40）
- [x] 未修改产品代码 / `09-api-contract` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `frontend-dev`**：修 **BLOCK-1**（`signals.js:93/97` `effect_pp` 去 `×100`）与 **BLOCK-2**（`engine.js:222` 改读 `n_w`，待契约冻结）；处理 SHOULD-1/4/5。**不派生功能**。
- **次消费方 `backend-dev`**：按架构师裁定对齐缺口 1~6；确认 D2/D8 输出与契约常量来源标注。
- **架构师**：终裁 6 条契约缺口（尤其 #6 `window_min_days`），版本 +1 通知双边；确认 D1/D3/D5/D7。
- **PM**：缺口 5（`rules_text`）与 D8 的常量口径；确认 D8「固定展示常量」不得冒充实测。
- **qa**：重点建负向用例——`effect_pp` 必须渲染 `x.xxpp`（非 390pp）、立方体空样本格不得渲染 0/50%、`window_min_days` 语义、隐私打码、未知≠持平。
- **残留风险**：
  1. `effect_pp` 显示错误（BLOCK-1，责任人 frontend-dev，期限：本轮修复后）。
  2. `window_min_days` 语义错误（BLOCK-2，责任人 architect+frontend-dev/backend-dev，期限：S4 收口）。
  3. 因子/引擎/影子盘大面积空集依赖引擎产出（责任人 architect，期限：S3 回测后）。
  4. 数据快照滞后 18 天（`latest_date=2026-08-25`）——数据管线新鲜度（责任人 backend-dev，期限：S4）。
  5. 桌面 exe 打包未做（责任人 dev-lead/backend-dev，期限：S5）。
- **未覆盖**：`16-build` 之外的打包分发；性能压测；多用户（Brief §7 明确不做）。
