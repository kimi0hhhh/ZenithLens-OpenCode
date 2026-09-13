---
artifact: 15-code-review
owner: dev-lead
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [frontend-dev, backend-dev, architect, qa, orchestrator]
gate: G-DL-01
---

# 代码评审与方向纠偏 · 极境 ZenithLens（S4 按 skill 重跑 · OC-R4-DL · 契约 v4）

> 上游：`docs/02-frontend/13-frontend-report.md`(v2)、`docs/02-frontend/12-interface-request.md`(v2)、
> `docs/02-frontend/14-frontend-fix-report.md`(v1)、`docs/03-backend/14-api-impl-report.md`(v2)、
> `docs/01-architecture/07-frontend-arch.md`(v3)、`08-backend-arch.md`(v4)、`09-api-contract.md`(v4)、
> `docs/00-charter/02-prd.md`(v3)、`03-ui-design.md`(v3)、`PROJECT_BRIEF.md` §9。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。只读源码与报告。
> **本轮 skill**：`code-review`（双轴：Standards 代码规范 + 冒烟/Fowler 气味基线；Spec 对齐 PRD/契约/Brief §9）、
> `triage`（缺口/偏差定性分流状态机）。按 `capability-map §5` 纪律：skill 只供方法与检查项，
> **不改变** `15-code-review` 结构（方向偏差六项 + BLOCK/SHOULD/NIT + 分流表）与门禁判据。
> **实测方法**：起 `python app.py`（8791，Python 3.8.6）curl 真实接口 + 读源码，逐项落地，非只读报告。
> 未修改产品代码 / 契约 / `runtime/**`；未派发子任务。

## 摘要

1. **重跑结论：G-DL-01 = CONCERN（有条件放行）**。头号红线「前端假数据填满界面」**未触发**（mock 默认关闭、全仓唯一 `fetch` 出口），故不判 FAIL；但仍有 **2 条 BLOCK 未关**，登记 `open-issues`，未关不进可交付版。
2. **v1 的 2 条 BLOCK 经实测确认已关闭**：`effect_pp` 不再二次 ×100（`signals.js:93/97` 走 `format.pp()`，实测 E3=3.90pp）；`window_min_days` 冻结表改读 `n_w`（实测 `5/10/15/30/60/120`）。
3. **方向六项**：40 组件齐全（40/40，DOM 容器 + 渲染函数双查）；契约 v4 四条裁定 A-07~A-10 实测落地；四态有 **1 处未接线**（空态非真实数据驱动）；未知≠持平成立；无假数据；口径单一入口成立（含 1 处跨接口展示连接，已登记）。
4. **实地抽验 10 条**（§3）：runtime/holdings/precision/signals/frozen/cube/arena/shadow/portfolio/inputs/静态托管，均为真实后端返回；独立重跑后端 40 条契约测试 `Ran 40 tests ... OK`（Python 3.8.6）。
5. **契约漂移集中**：§5.14 三个 `array[object]`（`window_weights`/`window_min_days`/`license_lines`）后端自定键名与契约示例不一致（前端已双向兼容）——须架构师冻结并版本 +1。
6. 缺口/偏差逐条经 `triage` 定性分流：**无一条「直接转发前端」**。

## 正文

### 0. 门禁判定

| 门禁 | 判定 | 依据 |
|---|---|---|
| **G-DL-01 · 组长评审** | **CONCERN** | 无假数据红线（不判 FAIL）；2 条 BLOCK 未关（登记 `open-issues.md`），其余 SHOULD 排期 |
| **G-DL-02 · 开发版构建** | **CONCERN** | 产物可独立启动（实测 `/`=200、53 接口在服）；但按「BLOCK 不关不进交付」，构建仅作联调/评审用 |

### 1. 方向偏差六项检查（逐项、带证据）

| # | 检查项 | 结论 | 证据（实测/源码） |
|---|---|---|---|
| 1 | **40 组件完整性** | ✅ PASS | §2 逐项对照 40/40；`index.html` 容器与 `views/*` 渲染函数双查命中（含 125 格立方体、竞技场、六维、影子盘、四态条） |
| 2 | **契约 v4 一致** | ⚠️ CONCERN（含漂移） | A-07/A-08/A-09/A-10 实测落地（§3 V4~V6）；但 §5.14 三处数组键名漂移（SHOULD-1）；`llm.base_url` 缺口未裁定（BLOCK-2） |
| 3 | **四态（空/加载/错误/成功）** | ⚠️ CONCERN | `components.js#mountState` 四态齐备、`main.js#setDemoState` 可逐页切换；**但 `api.loadSlice` 的 `emptyWhen` 全仓无视图调用**（`grep emptyWhen` 仅 `api.js`），真实空集走 success+就地文案，`empty` 分支只能由演示条触发 → SHOULD-3 |
| 4 | **未知 ≠ 持平** | ✅ PASS | `changeCell/pnlCell/unknownCell`：`null`→「未知/—」，仅 `0` 渲染 `+0.00%`；实测 `/holdings` 无 `+0.00%` 冒充；`change_rate=null` 行独立显示 |
| 5 | **无假数据** | ✅ PASS（不触红线） | 生产路径唯一 fetch 出口 `api.js`（全仓 `fetch(` 仅 1 处）；`main.js:140` 仅 `?mock=1`/`localStorage.zl_mock` 才动态 `import` mock；实起后端各页取真数据，空集页显示「（当前为空）/暂无配置」 |
| 6 | **口径单一入口** | ✅ PASS（1 处展示连接） | 数字全经 `format.js`（金额/概率/比率/Δpp/`pp()`）；徽章由后端 `mode_label`/`confidence_color_class` 驱动；立方体分档只认后端 `color_band`。唯一跨接口展示连接：`analyze.js:91-98` 用 `/holdings` 拼预测表 `tier/market_value`（契约缺口 2，已登记；SMALL，非业务计算） |

> 附带（上游 DoR）：`02-prd.md` v3 与 `03-ui-design.md` v3 的 frontmatter `status=draft`（非 approved），与 `gate-rules.md` DoR「上游工件 status=approved」不符 → 记 CONCERN，报主 Agent/PM（不在本评审改动范围）。

### 2. Brief §9 · 40 项特调组件逐项对照（缺一即方向偏差）

> 对照方式：`static/index.html` DOM 容器 + `static/js/views/*`（或 `components.js`）渲染函数双查，并核数据字段绑定。

| # | §9 组件 | DOM 容器 | 渲染/数据锚点 | 判定 |
|---|---|---|---|---|
| 9.1-1 | 资产总览四卡+覆盖说明 | `#pa-total/#pa-today/#pa-pnl/#pa-ret` | `holdings.js#renderOverview`；`/holdings` summary | ✅ |
| 9.1-2 | 估值精度汇总条 `.vsum` | `#val-sum` | `renderVSum`；`/valuations/precision`（含 `mode_distribution`） | ✅ |
| 9.1-3 | 估值来源徽章 `.vb` 五档+配色 | `components.js#valBadge` | `Valuation.mode_label/confidence_color_class/mae_rate/dir_hit_rate/trace_text` | ✅ |
| 9.1-4 | 覆盖度四档 `.covbar`+失效三类 | `#cov-bar/#cov-note` | `renderCoverage`；`/holdings/coverage`（`tiers[].color` 取后端） | ✅ |
| 9.1-5 | 持仓明细表（分组/列显隐/T+2/未知≠持平） | `#hd-body` | `renderTable/rowHTML`；`fallback_value` 分列 | ✅ |
| 9.1-6 | 风险指标折叠区 | `#fold-risk/#rk-*` | `loadRisk`（展开才请求）；`/holdings/risk` | ✅ |
| 9.2-7 | 信号空态四要素 | `#sg-empty` | `signals.js#renderEmpty`；`/signals/state` | ✅ |
| 9.2-8 | 触发门 E1/E3 + E2/E4 剔除 | `#sg-gates/#sg-excl` | `renderGates`；`gates/excluded_gates` + `pp()` | ✅ |
| 9.2-9 | 信号时间线 `.tl/.sigcard/.ev` | `#tl-list` | `renderTimeline` + `/ledger/chain` 按需 | ✅ |
| 9.3-10 | T+1 口径+三执行路径 | `#an-defs` | `analyze.js#renderDefs`；`/meta/definitions` | ✅ |
| 9.3-11 | 三窗口组合卡+加权口径 | `#pf-forecast/#an-forecast/#an-weighting` | `forecastCard`+`weightingNote`；A-08 字段 | ✅ |
| 9.3-12 | 参与预测持仓表 | `#an-body` | `renderTable`；`/predictions` + `/holdings` 展示连接 | ✅（见 SHOULD-4） |
| 9.3-13 | 推导链 `.chain` 六步 | `components.js#chainHTML` | `metrics` 逐键格式化；`/predictions/{code}` | ✅ |
| 9.4-14 | 因子四盘+因子行+跑分表 | `#fc-pans`/`.frow`/`.fdet` | `factors.js#renderPans/toggleScoreDetail` | ✅ |
| 9.4-15 | 四本账本+示例记录 | `#fc-books` | `renderBooks/openBook`；`schema_fields` 生成表头 | ✅ |
| 9.4-16 | 评分链长文 | `#fc-score` | `renderScoreChain`；`/factors/score-chain` | ✅ |
| 9.4-17 | 治理周期卡 | `#fc-cycle` | `renderGovernance`；`/factors/governance-cycle` | ✅ |
| 9.4-18 | 最近挖掘记录 F1/F2/F3 | `#fc-scan/#fc-scan-panel` | `renderDigRecords`；`/factors/dig-records` | ✅ |
| 9.4-19 | 生命周期规则长文 | `#fc-life` | `renderLifecycle`；`/factors/lifecycle`（`source` 由后端给） | ✅ |
| 9.5-20 | HUD 六卡 | `#eg-hud` | `engine.js#renderHud`；`/engine/status` | ⚠️（SHOULD-2 枚举错配） |
| 9.5-21 | 影子盘台账+进度+归档说明 | `#eg-ledger*/#eg-prg/#eg-ledger-archive` | `renderShadow`；`/ledger/shadow`（v4 retention 三字段） | ✅ |
| 9.5-22 | 因子竞技场矩阵 | `#eg-arena/#eg-arena-legend` | `renderArena`；只用 `arenaColorVar(color,prefix)` | ✅ |
| 9.5-23 | 训练状态卡 | `#eg-train` | `renderTraining`；`/engine/training-status` | ✅ |
| 9.5-24 | 冻结参数表 | `#eg-frozen` | `renderFrozen`（含 `weighting_basis`；`nwOf`） | ✅ |
| 9.5-25 | 六维输入 z-bar | `#dim-d3/#dim-d6/#dim-asset` | `renderDims`；`/engine/inputs`（3+6） | ✅ |
| 9.5-26 | 125 格立方体 ddsm 默认/naive 折叠 | `#cube-prod/#cube-research/#eg-cube-legend/#cube-dualnote` | `renderCube`+`cubeSliceHTML`；A-07 四字段 | ✅（研究层见 SHOULD-5） |
| 9.5-27 | 引擎注册表三态 | `#eg-registry/#st-registry` | `renderRegistry`（设置页复用） | ✅ |
| 9.6-28 | 历史成绩 hero | `#rv-hero` | `review.js#renderHero`；`/review/scores` | ✅ |
| 9.6-29 | 三窗口 vs 基线（待填充留空） | `#rv-scores` | `renderScores`（`baseline_status=pending`→「待填充」） | ✅ |
| 9.6-30 | 影子盘降级审查条 idle/ok/bad | `#rv-degrade` | `renderDegrade`；`/engine/shadow-review` | ✅ |
| 9.6-31 | 逐笔对账表 | `#rv-body` | `renderRecon`；`/review/reconciliation` | ✅ |
| 9.7-32 | 隐私开关 | `#sw-hide/#sw-hide-holdings` | `settings.js#savePrivacy`；`body.masked` | ✅ |
| 9.7-33 | LLM 接口+三硬约束+温度 0 | `#llm-provider/#llm-url/#llm-key` | `renderLlm/saveLlm` | ⚠️（BLOCK-2：`base_url` 不持久化） |
| 9.7-34 | 数据源健康表 | `#src-box/#src-probe` | `renderSources`；`/data-sources/health` | ✅ |
| 9.7-35 | 持仓数据卡+不一致长文 | `#hd-data/#hd-diff/#hd-import` | `renderHoldingsData`；`/settings/holdings-data` | ✅ |
| 9.7-36 | 关于卡 | `#about-card` | `renderAbout`；`/about` | ✅ |
| 9.8-37 | 三 dialog+popover+toast | `#dlg-fund/#dlg-amt/#dlg-del/#pop/#toast` | `holdings.js` 交互层 | ✅ |
| 9.8-38 | 注销 Service Worker | `main.js:18-23` | 纯前端 | ✅ |
| 9.8-39 | livebar 真实数据接入条 | `#livebar/#live-src` | `main.js#renderLivebar`；`/runtime`+health | ✅ |
| 9.8-40 | 四态覆盖各页 | `#statebar` + `[data-slot]` | `mountState`+`setDemoState` | ⚠️（SHOULD-3：空态未接线） |

**结论：40/40 落地，无缺失、无方向偏差；3 项带 CONCERN（HUD 标签 / LLM Base / 空态接线）。**

### 3. 实地抽验（起服 `python app.py` 8791 + curl 真实接口，共 10 条；Python 3.8.6）

环境：`python app.py`（`DEFAULT_PORT=8791`，`app.py:38`）；`/api/v1/*` 真实请求。

| # | 抽验 | 实测结果 | 判读 |
|---|---|---|---|
| V1 | `GET /runtime` | `port=8791` `engine_status=online` `as_of=2026-09-12`；`staleness.is_stale=true`、`latest_date=2026-08-25`、`days_behind=18`、`open_count=0` | 起服正常；快照滞后如实上报 |
| V2 | `GET /holdings` | 22 行；`total_value=53092.77`、`covered_count=22/22`、`fallback_value=0.0`；`mv_source∈{nav,valuation}`（无 `fallback`，符合 A-02） | 未知/降级如实；成本未混入市值 |
| V3 | `GET /valuations/precision` | `weighted_mae_rate=0.002`、`industry_baseline_mae_rate=0.008`、`mode_distribution=proxy:10,unknown:12`；`groups` 元素**无 `label`**（缺口 4） | 与后端报告一致；前端用 `CONF_LABEL` 兜底 |
| V4 | `GET /portfolio/forecast` | T1 `weighting_basis=market_value`、`weighting_policy_note` 非空(52)、`direction=gray`、`weighted_p=null`、`coverage_ratio=0.0` | A-08 落地；无开口不硬造方向 |
| V5 | `GET /engine/ddsm/cube?code=017193` | `production_layer=ddsm`/`research_layer=naive`/`default_layer=ddsm`/`dual_view_note`(93)；5 层×25=125；有值格 `ddsm_p=0.3923`、`color_band="P<0.45 看跌"`（命中 `legend`）；无值格全 `—` 不渲染 0/50% | A-07 落地；空样本不冒充 |
| V6 | `GET /engine/frozen-params` | `window_min_days=[{window,n_w}]`→`5/10/15/30/60/120`；`window_weights=[{window,weight}]`→`8/22/15/10/30/15`；`weighting_basis=market_value`；`license_lines=[{license,min_independent_days,window_k}]` | v1 BLOCK-2 关闭；**三处结构均与 §5.14 示例键名不同**（SHOULD-1） |
| V7 | `GET /signals/state` | `state=no_open`；`gates` E3=`effect_pp 3.9`、E1=`0.88`；`excluded` E2=`-3.09`、E4=`-2.72` | v1 BLOCK-1 关闭：前端 `pp()` 渲染 `+3.90pp/-3.09pp`，无 `390pp` |
| V8 | `GET /engine/arena` | `color_scheme=performance_rank`、`color_token_prefix=--arena-`、`rows=0`（诚实空集） | A-09 落地；空集非假数据 |
| V9 | `GET /ledger/shadow` | `retention_policy=first_of_day_immutable_full_archive`、`first_of_day_immutable=true`、`archive_manifest_at=null`、`progress.status=not_started` | A-10 落地；归档时间如实 null |
| V10 | 静态托管 + 契约测试 | `GET /`=200（app.py 直出 `static/**`）；`python -m unittest discover -s tests -t .` → `Ran 40 tests ... OK` | build 一步启动；后端 40/40 独立复现 |

> 另抽 `/engine/inputs?code=017193`（`ddsm_3d=3`、`crowd_6d=6`、`crowd.is_veto=true`）、`/settings`（`llm.api_key_set=false`、**无 `base_url`**）、`/about`（`version=0.1.0`、`python_min=3.8`），均与契约/报告一致。

### 4. 代码设计评审（Standards 轴 + 冒烟基线）

#### BLOCK（必须改，未关不进交付）

- **BLOCK-1 · HUD「影子盘」状态枚举错配（前端，标签恒「—」）**
  - 位置：`static/js/views/engine.js:113-114`。
  - 现象：后端 `/engine/status.shadow_status` 按契约 §6.9 返回 `shadow_review_status`（`idle/ok/bad`），前端却用 `PROGRESS_TAG`（键为 `shadow_progress_status`：`not_started/recording/qualified/gap`）查表 → `ptag` 恒落 `['—','gray']`，HUD 影子盘卡状态字永远显示「—」。
  - 期望：新增 `{idle:'未启动', ok:'达标', bad:'降级'}` 映射（或直接读 `progress.status` + `shadow_status` 双字段分别用各自枚举表）。
  - 定性：**前端实现缺陷**（契约无误）。违反 G-DL-01 方向表「需求对齐/契约漂移」。修复人：frontend-dev。

- **BLOCK-2 · LLM `base_url` 静默丢弃（契约缺口 → 后端；P0 组件 9.7-33 不完整）**
  - 位置：`settings.py#get_settings:96-115`（输出白名单无 `base_url`）、`#update_settings:138-166`（`llm` 分支忽略 `base_url`，且**不报错**）；前端 `settings.js#saveLlm:103-117` 已 PUT/读取 `base_url`。
  - 现象：设置页「Base URL」可输入并提交，但后端既不回传也不落盘；刷新后丢失（静默数据丢失），组件 9.7-33「服务商/Base/模型/Key」的 Base 形同虚设。实测 `/settings.llm` 无 `base_url` 键。
  - 期望：契约 §5.16 增 `llm.base_url`（`GET` 回传、`PUT` 可写），后端实现；未裁定前后端不得自造字段（`09 §1.6` 接口唯一性纪律）。
  - 定性：**契约缺口（架构师裁定）→ 后端实现**。未关前该 P0 组件不完整，故列 BLOCK。

#### SHOULD（建议改，可排下轮）

- **SHOULD-1 · §5.14 三处 `array[object]` 键名漂移**：契约示例为 `window_weights:[{d15:8}…]`、`window_min_days:{d15:5,…}`、`license_lines:[{candidate:50}…]`；后端 v2 统一为 `{window,weight}` / `{window,n_w}` / `{license,min_independent_days,window_k}`。前端已双向兼容（`engine.js#nwOf/licenseName/licenseDays`），**无显示错误**，但构成双份真相 → 请架构师在 §5.14 冻结为后端形态并版本 +1，通知双边。定性：契约歧义（架构师）。
- **SHOULD-2 ·（已被 BLOCK-1 覆盖，此处仅登记同类）** HUD 其余字段以 `/engine/status` 一次给全（符合 §6.9 v3 口径），仅 `shadow_status` 映射错。
- **SHOULD-3 · 四态「空态」未接线**：`api.loadSlice(name,path,opts,emptyWhen)` 的 `emptyWhen` 全仓无调用（`grep emptyWhen` 仅 `api.js`），真实空集一律 `status=success`；`mountState` 的 `empty` 分支只能由 `setDemoState('empty')` 演示条触发。12-interface-request 明示「空数组=`empty`」。定性：前端实现（接线缺失）。
- **SHOULD-4 · 跨接口展示连接**：`analyze.js:90-107` 用 `/holdings` 拼预测表 `tier/market_value`（契约缺口 2；`PredictionSummary` §5.4 无该两字段）。非业务计算，但属前端拼装 → 架构师裁定补字段后改直读。定性：契约缺口（架构师）→ 后端。
- **SHOULD-5 · A-07 研究口径 `naive` 实际无对照内容**：`build_cube` 以 `status=filled if (naive_p is not None or ddsm_n>0)` 标记单元格，`naive_p` 又以 `MIN_N` 门控；实测 017193 `valid_coverage_naive_pct=0.0`（115/125 格 `naive_p=null`，其中 10 格 `naive_n=0`），研究层整片显示「无样本」。契约 §5.25 仅规定 `empty` 时 `naive_p=null`，未规定 `n<MIN_N` 也置 null。定性：契约语义歧义（架构师）→ 后端；否则组件 9.5-26「naive/DDSM 对照」名存实亡。
- **SHOULD-6 · 静态文案重复后端常量**：`index.html:128`（K=4/p=0.25/MIN_N=15/SHRINK=10/BAND=0.02/purge=H+2）、`:102`（var95/drawdown 正数口径）、`:284`（升级协议 shadow 20 日）与后端 `engine.frozen_params` 重复。建议改由字段驱动或注明「来源：`/engine/frozen-params`」。定性：前端（低风险展示债）。

#### NIT（可不改）

- **NIT-1 · `/engine/ddsm` legend 与 `/engine/ddsm/cube` 不一致**：前者 `label="中性"`（`app.py:655`），后者/契约 §5.25 为 `"0.45–0.52 中性"`；且该端点前端未消费（死接口）。建议统一或标注仅内部用。
- **NIT-2 · `components.js:198-210` `CUBE_LEGEND_FALLBACK`/`CUBE_BAND_STYLES`** 硬编码分档阈值 0.45/0.52/0.58，仅无数据兜底时使用；与后端 `CUBE_LEGEND` 重复。
- **NIT-3 · `holdings.js#loadRisk`** `riskLoaded` 为模块级全局，刷新后不再重拉；切换资产不重算。
- **NIT-4 · `engine.js`** 冗余包装 `getState$`、`loadInputs` 内 `try{}catch{}` 空吞（保留 error 切片，可接受但建议注释）。

> 严重度分布：**BLOCK 2 / SHOULD 6 / NIT 4**。非「全 NIT」，亦非「全 BLOCK」。

### 5. 缺口 / 偏差 · `triage` 定性分流表

> 分流口径同 `revision-loop.md §1`：做错了→开发；做对了但定义不该→PM；做对了但结构撑不住→架构师；两边没错是话说岔→架构师改契约。**无「直接转发前端」。**

| 条目 | 现象 | 定性 | 分流 | 处置 |
|---|---|---|---|---|
| BLOCK-1 | HUD `shadow_status` 恒「—」 | 前端实现 | **前端** | 加 `idle/ok/bad` 映射；不涉契约 |
| BLOCK-2 | `llm.base_url` 不持久化 | 契约缺字段（§5.16） | **架构师 → 后端** | §5.16 追加 `llm.base_url`，版本 +1，后端 GET/PUT |
| SHOULD-1 | §5.14 三数组键名漂移 | 契约歧义 | **架构师 → 后端+前端** | 冻结为 `{window,weight}`/`{window,n_w}`/`{license,min_independent_days,window_k}` |
| SHOULD-3 | `emptyWhen` 未接线 | 前端实现 | **前端** | 各视图对空集合传 `emptyWhen`，走 `mountState` empty |
| SHOULD-4 | 预测表展示连接 `tier/market_value` | 契约缺字段 | **架构师 → 后端** | §5.4 `PredictionSummary` 追加两字段，前端改直读 |
| SHOULD-5 | 研究口径 `naive` 无有效覆盖 | 契约语义未定义 | **架构师 → 后端** | 明确 `naive_p` 是否以 `MIN_N` 门控；否则对照组件无内容 |
| V3/缺口4 | precision `groups` 无中文 `label` | 契约缺字段 | **架构师 → 后端/前端** | 追加 `label` 或前端统一枚举映射（现 `CONF_LABEL` 已兜底） |
| V2/上游 | `02-prd.md` v3、`03-ui-design.md` v3 `status=draft` | 上游工件未 approved（DoR） | **PM / 主 Agent** | PRD/UI 定稿过会签；非本轮代码改动 |
| 后端 D1~D9（14-report §7） | 端口 8791 / 代理映射 / legacy_path / proxy 小样本 / 门优先 / T15 / merge / 因子空集 / no_report | 契约定义 / 配置假设 / 数据成熟度（非算错） | **架构师（多数）/ PM（常量口径）/ 后端（排期增强）** | 逐条已在 14-report 登记，本轮复核无新增；不转发前端 |
| A-10 归档轮转未定时驱动 | `archive_manifest_at=null`，无轮转任务 | 残留风险（诚实 null） | **后端** | 阈值与定时器排期（14-report 残留风险 7） |

**分流纪律核对**：BLOCK-1/3 为「做错了→前端」；BLOCK-2、SHOULD-1/4/5 为「定义不清→架构师（改契约）」；DoR 为「上游定义→PM」。**无一条把需求/契约缺陷当 bug 直接派给前端。**

### 6. 假数据判定（头号红线 · 复核）

- 生产路径（无 `?mock`）唯一 fetch 出口 `api.js#request`；`main.js:140` 仅当 `?mock=1`/`localStorage.zl_mock='1'` 才动态 `import('./mock/mock.js')`，**默认关闭**且隔离在 `static/js/mock/`。
- 实起后端后各页取真实数据（§3）；factors/arena/ledger 空集显示「（当前为空）/暂无配置/尚无挖掘记录」，**未用 mock 数字补位**。
- **结论：未触碰 G-DL-01「前端造假数据」红线 → 不判 FAIL。**（但 BLOCK 未关 → 门禁 CONCERN。）

## 自验收

- [x] 方向偏差六个检查项全部过过一遍，结论落盘（§1；含 v4 一致/四态/未知≠持平/无假数据/口径单入口）
- [x] 逐项对照 Brief §9 的 40 项组件是否都在前端（§2，40/40，DOM+渲染函数双查）
- [x] 实地抽验 ≥3 条：起 `python app.py`(8791) + curl 真实接口（§3，共 10 条）+ 独立跑后端契约测试 40/40
- [x] 代码评审问题标注 BLOCK/SHOULD/NIT 严重度（§4：2/6/4）
- [x] 缺口/偏差经 `triage` 逐条定性分流，无「直接转发」（§5）
- [x] 使用并回传 skill 列表：`code-review`（双轴）、`triage`（分流状态机）
- [x] BLOCK 已登记 `open-issues`（BLOCK-1、BLOCK-2）
- [x] 开发版可独立启动，README-START 三步内可跑（§3 V10 `/`=200）
- [x] 已知限制清单已写明（下游交接）
- [x] 未修改产品代码 / `09-api-contract` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `frontend-dev`**：修 **BLOCK-1**（`engine.js:113` HUD 状态枚举改 `idle/ok/bad`）、**SHOULD-3**（`emptyWhen` 接线）；SHOULD-4 待契约裁定。**不派生功能**（超额交付禁令）。
- **次消费方 `backend-dev`**：按架构师裁定实现缺口 2/4、§5.14 键名冻结、`llm.base_url`；确认 A-10 轮转阈值。
- **架构师**：终裁 **BLOCK-2 + SHOULD-1/4/5 + 缺口4**，契约版本 +1 通知双边；复核 14-report D2/D3/D5/D7。
- **PM / 主 Agent**：`02-prd.md` v3 / `03-ui-design.md` v3 由 draft 定稿过会签（DoR）；D8 常量口径。
- **qa**：重点负向用例——`effect_pp` 必渲染 `±x.xxpp`（非 390pp）、冻结表 `N_w=5/10/15/30/60/120`、立方体空样本格不得渲染 0/50%、隐私打码、未知≠持平、mock 默认关闭。
- **残留风险**：
  1. BLOCK-1 HUD 标签（责任人 frontend-dev，期限：本轮修复后销项）。
  2. BLOCK-2 `llm.base_url` 契约缺口（责任人 architect→backend-dev，期限：S4 收口）。
  3. §5.14 结构漂移（责任人 architect，期限：S4 收口）。
  4. 因子/引擎/影子盘大面积空集依赖引擎产出（责任人 architect，期限：S3 回测后）。
  5. 数据快照滞后 18 天（`latest_date=2026-08-25`）——数据管线新鲜度（责任人 backend-dev，期限：S4）。
  6. 桌面 exe 打包未做（责任人 dev-lead/backend-dev，期限：S5）。
- **未覆盖**：`16-build` 之外的打包分发；性能压测；多用户（Brief §7 明确不做）。
