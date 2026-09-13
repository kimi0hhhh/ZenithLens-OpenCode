---
artifact: 16-fake-feature-audit-r2
owner: auditor
version: v1
status: draft
supersedes: —
created: 2026-09-13
reviewers: [dev-lead]
gate: —
note: 用户 2026-09-13 追加要求：全代码检查（避免「静态样式 / 假代码 / 假功能」混入交付）。审计方法取 .opencode/skills/intended-vs-implemented（文档意图 vs 实现证据差距法）+ diagnosing-bugs（证据纪律）。只读审计：未修改任何代码/数据/工件；统计脚本置于系统临时目录。
---

# 16 · 全代码假功能审计报告（极境 ZenithLens · R2 交付前红队）

## 摘要

- **审计范围**：代码根 `C:\Users\10719\Documents\ZenithLens-OpenCode\`（14 个后端 `.py` 模块；`static/` 17 个文件：index.html / css / api,store,format,copy,components,main + 7 views + mock；对照 `docs/04-integration/build-r2/`，抽检 30 文件 MD5 全等）。只读；未启动服务；证据 = 源码 + 交付数据快照 + 既有 QA/验收证据。
- **扫描计数**：静态控件 43（21 button / 14 input / 5 select / 3 details）+ 3 dialog + 动态渲染控件（行菜单 · 列菜单 · 重试 · 账本展开 · 时间线卡 · 层选择 · 资产下拉 · 弹窗动作，代码挂载 `addEventListener` 28 处 + 事件委托）；后端路由 **56**（GET 45 / POST 8 / PUT 2 / DELETE 1）；前端 API 调用点 **59**（唯一出口 `api.js:60`）；需求对照 = R1 组件 R-UI-01..40 + R2 需求 R2-01..25 + U-01..12。
- **发现统计**：**BLOCK 3 / SHOULD 6 / NIT 10**（全部含 file:line 或命令证据）。
- **结论：存在假功能（局部，3 条）**——① 设置页「测试连接」按钮空转且谎称「已发起连接测试（异步任务）」；② 设置页「隐藏持仓金额」开关有持久化、无任何展示行为；③ 信号时间线「点击展开事件链」因台账从不写 `_chain` 而恒为「无链路数据」。**不存在系统性假数据**：全部页面数字来自 API 响应；mock 默认关闭且生产路径零引用；未发现演示入口混入；后端关键链（估值五档 / 预测六步 / 台账回填 / 健康计数 / 回测成绩）均有实算痕迹（含独立复算抽样，见 §D）。

---

## 正文

### A. 前端事件接线（死控件清单）

扫描方法：提取 index.html 全部 136 个 id，与生产 JS（排除 mock）交叉比对；对全部静态控件逐一定位 `addEventListener` 与调用链；对动态渲染控件（表格行菜单、列显隐、重试按钮、账本展开、时间线卡、立方体层切换）核对事件委托。

**A-1 · BLOCK ·「测试连接」按钮是空转假功能**
- 位置：`static/js/views/settings.js:15`（绑定）、`:150-152`（实现）；`static/index.html:308`（按钮）
- 证据：`function probe(what) { if (what === 'llm') { toast('已发起连接测试（异步任务）'); return; } }` —— 无 fetch、无 API 调用；后端 56 条路由（`app.py:1055-1112`）无任何 LLM 测试端点，`settings.py` 无网络探测逻辑；唯一 HTTP 出口 `api.js:60`。
- 判定：假功能——按钮宣称「已发起连接测试（异步任务）」，实际未发起任何请求，也无异步任务。R-UI-33 要求「测试连接与保存按钮」（`03-ui-design.md:436`）。
- 建议：二选一——(a) 后端实现 `POST /settings/llm-test`（或任务化探测）并接线；(b) 若无此计划，前端改为「未实现」样式禁用并去掉谎言文案，同时修订 R-UI-33 规格。

**A-2 · BLOCK ·「隐藏持仓金额」开关无任何行为**
- 位置：`static/js/views/settings.js:11-12`（绑定 `sw-hide-holdings`）、`:84-93`（PUT 持久化）；`static/js/store.js:32-35`（`applyPrivacyClass` 只切 `body.masked`）；`static/css/app.css:151-156`（仅 `body.masked .amt` 规则）；`static/index.html:289-290`（开关文案「只隐藏明细行，保留组合总额」）
- 证据：全仓引用 `mask_holdings_only` 仅 3 处（store.js:5 / settings.js:81,87 / mock.js:514），**无任何渲染或样式消费点**；CSS 无 holdings-only 打码规则。实测语义：开关可切换、可保存、可回显，但页面金额不变。
- 判定：假功能——控件状态真实，功能行为缺失（与 A-1 同类）。
- 建议：补 `body.mask-holdings-only` 类 + 明细行 `.amt` 打码（保留组合四卡），或删除该开关并同步 U/R-UI-32 规格。

**A-3 · BLOCK · 信号时间线「点击展开事件链」恒为空**
- 位置：`static/js/views/signals.js:17-22`（展开时 GET `/ledger/chain`）；`ledger_api.py:866-881`（`ledger_chain` 读 `e.get("_chain")`）；`ledger_api.py:386-393`（生产写入路径记录字段仅 date/code/gate/p_up/ddsm_state/veto_*/signal/opened/created_at，**无 `_chain`**）
- 证据：`ledger/shadow_signals.jsonl` 320 行，`"_chain"` 命中 **0** 次（`Select-String -SimpleMatch '"_chain"'` = 0）；QA 证据 `docs/05-qa/evidence-r2/ep2_ledger_shadow.json` 全部行 `chain_available: false`；`ledger_chain` 无值时返回 `chain: []` → `chainHTML` 渲染「无链路数据」（components.js:223）。R2-22/U-04 验收③「事件链第⑥步显示回填值」在时间线入口不可达；PM 终验已将该验收点「改由分析页 `.chain` 验证」（`19-pm-acceptance.md:61`）——但 UI 仍保留「点击展开事件链」承诺（index.html:135）。
- 判定：假功能——可点击、可展开，永远无数据；承诺与行为不一致。
- 建议：写入台账时持久化链（或在 `/ledger/chain` 按行重算六步）；若接受降级，则移除/改写入口文案并把降级写入验收记录。

**A-4 · NIT ·「建议」列恒「—」的占位列**
- 位置：`static/js/views/holdings.js:291`；`static/index.html:80`（列头）
- 证据：`'<td data-col="adv"><span class="tag gray" title="契约缺失建议字段，见 12-interface-request">—</span></td>'`，无任何数据来源；`12-interface-request-r2.md:26,145` 明确该列是 R1 残留缺口挂账。
- 判定：诚实占位（tooltip 明示契约缺口），非欺诈；但作为成品形态展示 0 信息列。
- 建议：保留（挂账）或加「未接入」徽标；dev-lead 可降级为设计取舍。

**A-5 · 其余控件接线结论（PASS）**：导航 7 键（main.js:176-179）、隐私 eye（main.js:181-182）、显示列/录入基金（holdings.js:11-14）、三 dialog 保存/取消（holdings.js:17-22）、风险折叠（holdings.js:24-27）、数据源立即检测（settings.js:18/188-195）、外部导入（settings.js:19/245-258，按 `import_available` 禁用）、Key 显隐/保存（settings.js:16-17）、六维资产下拉与 vr 层切换（engine.js:22-33）、行菜单/列菜单（holdings.js:260-263/318-338）、账本展开（factors.js:18-24）、跑分展开（factors.js:10-16）——全部有真实调用链。`cube-prod-title`、`flavor-badge` 为纯静态文本标签（无控件语义），不计缺陷。

### B. 数据真实性

- **B-1（PASS）唯一 fetch 出口**：`static/js/api.js:60` 是全前端唯一 `fetch(`；生产 JS 无 `XMLHttpRequest`/`sendBeacon`（grep 全量命中仅此一处）。页面不直连网络。
- **B-2（PASS）mock 默认关闭、生产零引用**：开关 `mockEnabled()` 需显式 `?mock=1` 或 `localStorage.zl_mock=1`（api.js:33-39）；main.js:165-168 仅此条件下动态 import；无静态 import；`static/index.html` 不引用 mock；README §演示模式 声明「验收时 mock 默认开启直接 FAIL」。生产 JS 中 `mock` 字样仅 api.js/main.js 的守卫代码。
- **B-3（PASS）无演示入口混入**：grep `demo|演示|state=empty|forceState|debug` 仅命中 mock.js/README 的显式说明；四态由真实数据条件驱动（§C）。
- **B-4（PASS）页面数字全部来自 API 响应**：views 内无字面数据数组；所有展示走 `getSlice`/API 字段（如 holdings.js:92-107、engine.js:133-158、review.js:47-61）。前端零业务计算声明（README §接口运用规范 5）实际遵守：加权 P/MAE/Δ/分档均取后端字段（components.js:`weightingNote`/`valBadge`、engine.js:`cubeSliceHTML` 只认 `color_band`）。
- **B-5（NIT）硬编码字段清单**（当前值与事实一致，但无计算来源）：
  - `app.py:967` `"no_solution_count": 0`（UI 显示「原理无解 0 只」）；`app.py:69` `NO_SOLUTION_TEXT` 定义后零引用（死常量）。当前 22 只全部有代理（数据核查：no_proxy=[]），0 属实；建议改实测或删常量。
  - `app.py:724,842` 与 `engine.py:656` `index_only_assets: 0` 硬编码；契约定义为「仅作特征不产信号的指数只数」（09-api-contract.md:954）。当前无此类资产，0 属实；无统计实现。
  - `fund_predict.py:33-34` `GATE_EFFECT/GATE_T`（E1 0.88/E3 3.90/E2 −3.09/E4 −2.72/t 2.33）为 FundLens 研究常量，UI 以「纯事件效应 +3.90pp」展示；解剖报告已列「可接受但需复核来源、R2 用自家台账独立复算」（`00-dissection-v3.md:210,232`），交付未见复算产物。
  - `components.js:311-317` `CUBE_LEGEND_FALLBACK` 前端备份阈值——与 `engine.py:512-518` 重复；后端 legend 恒在（`build_cube` 返回），该分支为死备份；若触发将造成前后端分档口径分叉风险。
- **B-6（证据）数字可复算抽查**：对 `ledger/backfill.jsonl` 最后一行独立复算——样本 `2026-09-10/012922/proxy 513100/t1_real=-0.008112`，以 `data/cache/bars/513100.json` 重算 `close(T+1)/close(T)-1 = -0.008112`，**逐位一致**（match True）。台账数字非摆拍。

### C. 四态真实触发

- **C-1（PASS）七个视图 emptyWhen 全量接线**：holdings（holdings.js:46-48，rows 空）、analyze（analyze.js:22-29 双源 portfolio/predictions == 空）、signals（signals.js:31-33，ledger rows 空 → `empty_never` 变体）、factors（factors.js:30-32，pans 空）、review（review.js:18-20，scores 空）、engine（engine.js:52-54，offline 且无心跳无快照）、settings（settings.js:37-41，四源全 unchecked）。`mountState` 由状态驱动（components.js:34-71），empty 文案含「为什么空 + 下一步」（copy.js:32-95），idle 按 loading 渲染（components.js:43）。
- **C-2（PASS）无「只有演示按钮才能触发四态」的旧问题**：QA 报告实测 7 页 × 空/载/错 **21/21 真实触发**（`18-test-report-r2.md:88`）；空态下不渲染数字行由 `root.dataset.state` + CSS 控制（holdings.js:67-68）。
- **C-3（NIT）发现时点说明**：当前交付快照 `window_filled_days=0`、`window_phase=warming`（README-START.md:51 已声明），估值徽章/精度条走「unknown + 原因」路径（§E R2-01），非四态缺陷。

### D. 后端假实现

方法：全量 grep `TODO|FIXME|NotImplemented|pass` 无假壳（仅注释/占位命中 2 处为股票字段说明）；对关键链路做「真实计算痕迹」抽查（源码路径 + 交付数据 + 独立复算）。

- **D-1（PASS）估值五档链真实**：`valuation.py:1052-1263 value_fund` 五档逐级判定（official→intraday→holdings→proxy→unknown），每档写 `trace`；09-13 最新 holdings 档记录（025500，`written_at=2026-09-13T00:50:57+08:00`）含 `top_n/report_date/covered_weight_pct/included_markets/excluded_count/top10` 全量 detail，`covered_weight_pct=62.34`；`valuation_history.jsonl` 1497 行真实入账。
- **D-2（PASS）预测六步链真实**：`fund_predict.py:161-201 build_chain` 逐步产出；`data/snapshot/predictions.json` 15 行全部含 `_chain` 且指标非空（抽查：gate 未触发 / DDSM [4,0,3] P=0.5874 / crowd z=-0.054 分位 0.4445）。
- **D-3（PASS）成绩 scores 真实**：`review.py:123-184` 由 `factor_engine.evaluate` 走前回测生成；`data/snapshot/review_scores.json` T1 = 52.63% / 基线 54.15% / Δ −1.52pp / 61 开口，T3/T15 按契约 v9.2 恒 pending（`09-api-contract-r2.md:315` 之外 §10 裁定，README-START.md:41,50）。
- **D-4（PASS）台账与回填真实**：`shadow_signals.jsonl` 320 行（2026-08-17..09-11，20 交易日窗口）；`backfill.jsonl` 304 行 t1_real，抽样独立复算一致（B-6）；`ledger_api.py:510-561 backfill_due` 真算代理日线。
- **D-5（PASS）数据源健康真实**：`settings.py:357-455` 成功/失败均落事件日志（`health-log.jsonl` 82KB），窗口计数 `fail_window_7d` 真算；`estimator.probe_source:1072-1092` 真探测四个源；sina 降级标注按实测（settings.py:288-354）。
- **D-6（SHOULD）`scan_factors` 任务空转**：`app.py:293-295` 对 `scan_factors` 类型不做任何扫描调用，直接 `progress=0.5 → summary="因子扫描完成（本期无新候选写入）"` 并 done。API 消费者会得到「扫描完成」的成功回执（`TASK_TYPES` 在 app.py:78-81 公开该类型）。判假：以成功回执冒充已执行。
- **D-7（SHOULD）引擎注册表为单行常量**：`app.py:859-865` 硬编码 1 条 `{version: oc-s3-v1, status: active, metrics: null, can_rollback: false}`；无 shadow/retired 写入机制（全仓无第二版本来源）。UI 却以「R-UI-27 · 三态：active / shadow / retired」+ 「新版本先以 shadow 并行 20 个交易日…」呈现（index.html:272-277）。判假：三态能力为展示性文案，实际不可达。
- **D-8（NIT）静默吞错习惯**：`app.py:_warmup:1274-1348`、`global_as_of:143-162` 共 13 处 `except Exception: pass`——启动链路失败被吞，`server.err.log` 当前为空不代表链路全绿；建议至少写 stderr 摘要（现有 warmup 阶段打点不含异常原因）。

### E. 承诺 vs 实现对照（R1 40 组件 / R2 25 需求 / U-01..12）

**E-1 R1 组件 R-UI-01..40**：40/40 在代码中有实现引用（脚本核对：0 缺失）；逐项抽查通过，例外并入上文：R-UI-09（A-3 事件链条）、R-UI-05（A-4 建议列）、R-UI-32（A-2 holdings-only）、R-UI-33（A-1 测试连接）、R-UI-27（D-7 三态）。

**E-2 R2-01..25 快照（实现证据 / 缺口）**

| 需求 | 结论 | 证据 / 缺口 |
|---|---|---|
| R2-01 置信度通道 | **SHOULD 缺口（进行中）** | 机制真实（`valuation.py:390-452 build_accuracy`、`_confidence_of:229-242`、conf_reason:496-521）；但交付快照 `accuracy.json` = `{}`，QA `ep2_precision.json` 实测 **22/22 unknown、window 0/40**；README-START.md:51 声明「首日 warming」。P0 验收「≥21/22 非 unknown」在交付时点未达成（数据窗口依赖，非假实现）。 |
| R2-02 重仓前二十+港美 | **SHOULD 缺口（快照未生效）** | 代码支持 `topline=20`（estimator.py:921,927）；但交付缓存 `data/cache/holdings/*.json`（09-12 17:12 写入）仅 10 行且无 top_n；最新 holdings 档记录（09-13 00:50）`top_n=10, included_markets=['A']`。按架构「缓存 top_n<请求值 且过期才重抓」（08-backend-arch-r2.md:125）+30 天 TTL（estimator.py:45），交付快照验收②③（覆盖提升/港美纳入）无证据。 |
| R2-03 QDII 双段 | PASS | `valuation.py:763-820 qdii_estimate` + `qdii_review.jsonl` 32KB；tooltip 校正口径（components.js:138-143）。 |
| R2-04 9 只代理复核 | **SHOULD 缺口** | `tier_reviews.jsonl` 仅 7 只 C 档（018957/021528/021662/022485/025500/163208/457001）；9 只清单中 024239/025857/014320/016665/012922 **无结论行**；README-START.md:53 承认「9 只代理复核（R2-04）属 S5 前事项」。P1 验收「9/9 出结论」未达。 |
| R2-05 跨日留档 | PASS（累计中） | `daily/valuation-20260912.jsonl`、`-20260913.jsonl` 均在；append-only（valuation.py:526-579）。 |
| R2-06 C 档 7 只验证 | PASS | 7/7 出结论（全部 hold + 复查日 2026-10-23 + 防稀释闸触发记录），`tier_reviews.jsonl` 21 行；覆盖口径按实（15/22）。 |
| R2-07 按现档位重算 | PASS | `ledger_api.py:564-618` 幂等重算 + 归档 + 0 冲突断言。 |
| R2-08 低频期望 | PASS | `fund_predict.py:375-394` 滚动 20 交易日开口资产（台账合并集）；空态四要素（signals.js:95-104）。 |
| R2-09 QDII 标注 | PASS | `holdings.py:51` + `fund_predict.py:517-518`；持仓/分析行均出现（holdings.js:278-279、analyze.js:130-131）。 |
| R2-10 出口研究项 | **NIT 缺口** | 全 docs 未见 BAND 0.01/0.02 走前研究报告（grep 仅命中「不做清单」引用）；P2、不阻塞。 |
| R2-11 回测接通 | PASS | `review.py` 全真；T1 出数，T3/T15 按 v9.2 恒 pending（不填估计值）。 |
| R2-12 自动回填 | PASS | backfill 304 行；复算一致（B-6）。 |
| R2-13 20/60 矛盾解除 | PASS | `shadow_progress:641-703` 归档合并 + `history_days`；归档缺失降级标注真实。 |
| R2-14 基线实测化 | PASS | `measured_baseline:496-507`；0.5830 仅存在于「已退役」文案与 mock（grep：engine.py:685-686 文本、mock.js）。 |
| R2-15 主源切换 | PASS | `holdings.py:287-336`；设置页主源卡 + 导入禁用理由（settings.js:224-242）。 |
| R2-16 nav 维护 | PASS | nav 缓存 260 点/只更新至 2026-09-11（最近交易日）；`maintain_nav_history:325-385`。 |
| R2-17 新浪定案 | PASS | 腾讯失败→新浪批量兜底（valuation.py:1200-1204）；降级标注按实测（settings.py:288-354）。 |
| R2-18 计数衰减 | PASS | `fail_window_7d` + 历史折叠（settings.js:167-184）。 |
| R2-19 成绩位填充 | PASS | hero/三窗口/立方体对比卡/因子盘全部出数或「待填充」（review.js:43-62、engine.js:389-397）；走前 Δ 如实「待复现」（engine.py:607-610）。 |
| R2-20 徽章双层 | PASS | `valBadge` 双层 + 7 项 tooltip（components.js:94-147）。 |
| R2-21 四态接线 | PASS | §C。 |
| R2-22 回填态激活 | **部分（BLOCK-3）** | 时间线/对账 hit/miss 真实（signals.js:150-164、review.js:126-131）；**事件链第⑥步不可达**（A-3）。 |
| R2-23 长表/可达 | PASS | sticky（app.css:386）、focus-visible（:393）、Esc/焦点回位（components.js:250-268）、reduced-motion（:413）。 |
| R2-24 验证状态可见 | PASS | 7 只「验证中」+ 批次/复查日 tooltip（holdings.js:274-282、components.js:166-178）。 |
| R2-25 文案字典 | PASS | copy.js 字典 + 组件取词（QA U-12 抽查 0 混用，18-test-report-r2.md:88）。 |

**E-3 U-01..12**：U-01/02/03/05/06/07/08/09/10/11/12 有实现与 QA 证据（18-test-report-r2.md:88）；**U-04 的「事件链」子项不达**（A-3）。

### F. 静态样式冒充功能

- **F-1（SHOULD）评分链「bootstrap 500 校准」显示静态常量**：`factor_board.py:286` `BOOTSTRAP_PERCENTILES={p50:-10.8,...}` 常量经 `:318`（score-chain）与 `:376`（score-detail）下发；前端 `factors.js:195-200` 与 `:141` 直接以「bootstrap 500 校准：P50 −10.8 / P90 38.7…」呈现。契约 v9.2 §4.9 要求兄弟字段 `bootstrap_percentiles_measured`（实测 500 次零分布，09-api-contract-r2.md:315），后端已实现（`factor_engine.measured_bootstrap:1472-1478`；实测样例：klow2 p50=**−12.4**、crowd6 p50=**−18.9**，与页面显示的 −10.8 不同）；前端对 measured 字段**零消费**（grep 无命中）。判：静态数字以实测名义展示，弱化 V11 销项。
- **F-2（SHOULD）引擎注册表「三态」为单行常量**：同 D-7（`app.py:859-865` vs index.html:272-277）——表格形态是成品，机制不存在。
- **F-3（NIT）`score_detail` judges 值恒空**：`factor_board.py:377` 将 judges 全部 `value=None`；UI 渲染出「分数裁判（…）：lift → k_lift 悬崖  note」而没有 value（factors.js:135-142）——字段位存在但永不出数。
- **F-4（NIT）`review.js` 实盘分支不可达**：`let dataKind = null`（review.js:10-11）且无任何 UI 入口赋值；`shadow_live` 标签/实盘 hero 分支（review.js:51-52,76）为死代码路径。后端 `/review/scores?data_kind=shadow_live` 可用，但页面永远只读 backtest。
- **F-5（NIT）版本标识与契约法律不一致**：`index.html:8,31,336` 与 `static/README.md:3,59` 均标「api-contract v9.1」；接口法律实为 **v9.2**（`09-api-contract-r2.md:4`）。字段兼容（前端已按 v9.2 的 pending/枚举实现），仅标识陈旧。
- **F-6（NIT）方法标签陈旧**：`valuation.py:1035` `method="eastmoney_f10_top10_weighted"` 在 R2-02 升级后未改名；最新记录 top_n=10 时无碍，若 top_n=20 生效将误导（建议 `top{N}_weighted` 或去数字）。
- **F-7（NIT）`last_retrain_at` 恒 None**：`engine.py:654,671`、`app.py:730`——HUD「上次重训 —」永远为 —；无重训时间写入点。属诚实空格，但字段位永不点亮。
- **F-8（确认非假）**「待复现 / 待填充 / 待回填 / —」类空位均带原因或契约口径（engine.js:396-397、review.js:72-81、signals.js:164），**不计**为静态冒充；mock 数据（mock.js）默认关闭（B-2），**不计**为生产假数据。

---

## 自验收

- [x] A–F 六节逐项执行且每条发现含 `file:line` 或命令/数据证据（BLOCK 3 / SHOULD 6 / NIT 10）。
- [x] 结论明确：存在假功能 = 是（局部 3 条 BLOCK，清单见摘要与 §A）；无系统性假数据。
- [x] 只读边界：未修改代码/数据/工件；审计脚本置于 `%TEMP%\opencode\zl_audit_*.py`；未启动后端服务（避免写数据）。
- [x] build 与源一致性抽检：30 个代表文件 MD5 全等（app/engine/estimator/valuation/factor_engine 等 + static 全量核心）。
- [x] 实算抽查：估值五档（09-13 holdings 记录含全量 trace）、预测六步（predictions.json 15/15 含 `_chain`）、台账回填独立复算 1 例逐位一致、健康事件日志 82KB 真实、scores 缓存为真实回测产物。
- [x] 未夸大：R2-01/R2-02/R2-04 缺口均标注「数据窗口/缓存/排期」性质并给出证据，不按假实现定性；诚实占位（A-4、F-8）降级 NIT。

## 下游交接

交 `dev-lead` 分流（按 AGENTS.md 缺陷分流规则）：

| # | 建议去向 | 一句话 |
|---|---|---|
| A-1 测试连接空转 | frontend-dev + backend-dev（口径先拍板） | 实现真实探测端点并接线，或禁用+去谎言文案（涉及 R-UI-33 规格修订则由 PM/架构确认） |
| A-2 隐藏持仓金额无行为 | frontend-dev | 补 body 级 holdings-only 打码类并接入 `mask_holdings_only`，或删除开关 |
| A-3 事件链恒空 | backend-dev（首选）→ frontend-dev（降级） | 台账写链或按行重算；若降级需同步 U-04/R2-22 验收记录（PM 已知） |
| D-6 scan_factors 空转 | backend-dev | 实现真实扫描或返回显式未实现（禁止成功回执） |
| D-7/F-2 注册表单行常量 | architect + PM（定义）→ backend-dev | 三态是否有版本机制；无则改 UI 文案为单版本现实 |
| F-1 bootstrap 静态常量 | frontend-dev（改用 measured）+ backend-dev（确认字段） | 页面改读 `bootstrap_percentiles_measured`，或明确标注「兼容常量」 |
| E-2 R2-01 | backend-dev + PM | 数据窗口进行中；下一可配对交易日复核 22/22→非 unknown 链路 |
| E-2 R2-02 | backend-dev | 缓存 TTL 策略复核（交付快照 top_n=10）；补 top20 生效证据 |
| E-2 R2-04 | backend-dev + PM | 9 只复核补齐或明确 S5 范围（README 已声明） |
| NIT 清单（A-4/F-3..F-7/B-5） | dev-lead 批量定级 | 版本标识 v9.2、死常量清理、方法名、judges 值等，不阻塞 |
| D-8 静默吞错 | backend-dev | warmup/global_as_of 异常至少 stderr 摘要 |

> 本报告为 draft，待 dev-lead 评审后由 orchestrator 决定退回修复或登记 open-issues；审计基线 = 2026-09-13 交付快照（含 build-r2 副本），修复后需以本清单逐条复核。
