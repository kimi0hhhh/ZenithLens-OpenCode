---
artifact: 14-api-impl-report
owner: backend-dev
version: v10
status: draft
supersedes: v9
created: 2026-09-12
reviewers: [dev-lead, qa, frontend-dev, architect]
gate: G-BE-02
---

# 接口实现报告 · 极境 ZenithLens（OpenCode 独立实现 · S3 覆盖度穿透轮 · 契约 v7）

> 上游法律：`docs/01-architecture/09-api-contract.md` **v7**、`docs/01-architecture/21-factor-governance.md`（因子治理机制）、`docs/01-architecture/08-backend-arch.md`、`docs/PROJECT_BRIEF.md` §5.1/§5.2/§5.3。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。round1 工件已备份至 `_archive_round1/`（11 个 `*.py` + `ledger/`）。
> 未读取/引用 FundLens/ZCode 代码；未改 `09-api-contract.md`、`docs/01-architecture/**`、`static/**`、`runtime/**`；未派发子任务。
> **v10 变更范围（task OC-HOLDVAL-BE）**：修「主动基金误用 ETF 做估值锚点」——按用户指正，**主动基金（混合/股票/灵活配置）估值锚点改为「前十大重仓股加权」**：新增 `estimator.classify_fund_type`（active/index_link/qdii/other）、F10 前十抓取解析 `parse_top_holdings`/`fetch_top_holdings`、腾讯批量个股实时 `tencent_rt_quotes`，并实装 `eastmoney_top_holdings`（30 天缓存 + 实时涨跌）；`valuation.value_fund` 主动基金官方未出当日时走 `holdings`（`Σ(w_i×chg_i)/Σw_i`，优先于 proxy，前十不可得才回退 proxy），指数联接/QDII 维持 official/intraday/proxy；`fund_type` 落到持仓字段与 `Valuation`/`HoldingRow`（**只加不改**）。实测 `python app.py`（8791）：`/valuations` **before official:22 → after holdings:5 / official:17**（周六非盘中）；盘中模拟 **before proxy:11/intraday:11 → after holdings:5/intraday:11/proxy:6**。**117/117 测试通过**。契约同步项见 §7 V18。
> **v9 变更范围（task OC-SHADOWSTAT-BE）**：修「影子盘记了 20 日仍显示未启动」——`app.py#h_engine_status` 的 `shadow_status` 由**偏差评估语义**（`shadow_audit()["status"]`：窗口内无"涨"信号→`idle`）改为**进度语义**（`shadow_progress()["status"]`：`not_started/recording/qualified/gap`）；偏差评估**独立保留**为新增字段 `shadow_audit_status`（`idle/ok/bad`）；`shadow_consecutive_days`/`shadow_target_days` 反映台账连续交易日。**既有字段名只加不改**（新增 1 键，未改/未删任何键）。
> **v8 变更范围（task OC-COV-BE）**：① 新增深度模块 `proxy_map.py`——完整 fund→proxy 映射表（22/22）+ 主动基金 F10 持仓穿透（个股→行业 ETF，加权篮子/主代理）；② `holdings.py` 存量数据按 `sync_proxy_fields` 幂等补齐；③ `fund_predict.build_holding_row` 新增 `penetration_trace`；④ `/holdings/coverage` 新增 `no_proxy_count`/`penetrated_count`（只加不改）；⑤ D 档由 **12/22（54.5%）压到 0**，穿透结果标注「待验证」。契约同步项见 §7 V14。
> **v7 变更范围（task OC-FACTOR-BE）**：① 新增深度模块 `factor_engine.py`——`evaluate(definition, assets_bars, frozen_config) -> Scorecard`，实现六窗走前 CV（purge=H+2）、基线 `max(恒涨,恒跌)`、k_lift 五档悬崖、窗权重 `8/22/15/10/30/15`、准入度 `min(1,独立触发日/N_w)`、bootstrap 校准分位、F1/F2/F3、牌照/盘位；② 用真实数据回测引擎在用的 **KLOW2 下影线否决** 与 **拥挤度六维复合否决** 填入 `ledger/adopted_factors.json`（**禁 legacy 示例数字**，R7）；③ 契约 v7 两接口 `POST /factors/candidates`、`GET /factors/candidates/{candidate_id}` 接线 `app.py`；④ `factor_board.score_chain` 增实测分位与 `real_engine` 标记（只加不改）。

> 上游法律：`docs/01-architecture/09-api-contract.md` **v5**、`docs/01-architecture/20-arch-verdict-r2.md`（OC-R4-ARCH）、`docs/01-architecture/08-backend-arch.md` **v5**、`docs/PROJECT_BRIEF.md` §5.1/§5.3/§9、`docs/00-charter/02-prd.md` v3（F-02/F-06/F-09/F-10/F-14）。
> **v3 变更范围（task OC-R4-BE）**：仅落 `20-arch-verdict-r2` 的 5 处最小改动（BLOCK-2 + SHOULD-1/4/5 + 缺口4），未加需求外功能。
> **v4 变更范围（task OC-BUG-BE）**：修终验 F-PM-01(P1)——`/holdings/summary` 的 `covered_count` 由 `market_value != null` 口径改为 `change_rate != null`（可信估值）口径，`coverage_note` 随之生成，`today_pnl_amt` 聚合口径保持一致；未改字段名、未加需求外功能。
> **v5 变更范围（task OC-DATA-BE2）**：修「净值快照非实时」——`valuation.value_fund` 档1 official 不再要求 `official_date==as_of_date`，非盘中时段（周末/收盘后/盘前）以最近一期官方净值为估值（`official` + `nav_date=jzrq`）；仅 A 股盘中允许 `intraday`；`valuation.nav_of` 与 `/runtime.staleness.latest_date` 改读实时净值缓存；启动与 `refresh_valuation` 任务强制批量抓取。未改字段名、未加需求外功能。
> **v6 变更范围（task OC-SHADOW-BE）**：① `backfill_ledger` 实装为**最近 20 交易日滚动影子台账**（真实引擎走前计算、INSERT-ONLY、每日追加+裁剪最旧、幂等、归档）；② 台账行新增 `opened`(bool)；③ `/factors/pans` 各盘新增 `caps` 对象并把正式盘 `rule_text` 明确为「否决位 ≤4 · 打分位 ≤3」，正式盘误导性 `factor_cap` 置 `null`；④ 信号时间线读取全量台账修正「开口落分页外误报无开口」。新增字段只加不改，契约同步项见 §7 V5/V6。

## 摘要

1. **v3 修复轮**执行架构裁定书 R2 的 5 处后端最小改动并重跑回归：① `settings.py` 补 `llm.base_url`（BLOCK-2）；② `engine.py#build_cube` 的 `naive_p` 改研究口径原始频率 + 新增 `naive_low_sample`（SHOULD-5）；③ `app.py` 预测行补 `tier/market_value`（SHOULD-4）；④ `valuation.py#precision_summary` 分组补 `label`（缺口4）；⑤ `engine.frozen_params()` 三数组元素键名冻结到契约形态（SHOULD-1，含一处实操修正）。
2. 契约 **v5 五项裁定**全部落地并实测：`PUT {llm.base_url}` → GET 回读一致；立方体 `valid_coverage_naive_pct` 由 0.0 抬到 **0.92**（研究口径披露的预期结果）；`/predictions` 与 `/holdings` 同 code 的 `tier/market_value` **0 处不一致**；`precision.groups[].label ∈ {高,中,低,无}`。
3. 53 接口 + `/health` 全部实现；`python app.py`（Python 3.8.6）在 **8791** 起服，`/runtime` 回传 `port=8791 / engine_status=online`。
4. 预测核心链冻结口径未动：E1/E3 门 → DDSM（[r2,om,vr]×5=125 格 / K=4 / p=0.25 / MIN_N=15 / 收缩 10）→ 双否决（拥挤度 40% / KLOW2 40%）→ 出口 P>0.52；估值五档 + 台账 INSERT-ONLY 保持，缺失一律显式 `null`。
5. **56/56 测试通过**（`python -m unittest discover -s tests -t .`）；无兜底假数；v3 新增偏差 3 项（V0/V1/V2）显式登记于 §7。
6. **v4 修终验 F-PM-01(P1)**：`GET /api/v1/holdings/summary` 的 `covered_count` 改为按 `change_rate != null`（可信估值）计数，实测 **10/22**（存在 12 只 unknown 时严格 `< total_count`）；`coverage_note` 随之为「可信估值覆盖 10/22 只…」；`today_pnl_amt` 口径不变（仅非 null `change_rate` 行参与）。**59/59 测试通过**（v3 为 56，v4 新增 `HoldingsSummaryCoverageTest` 3 条）。
7. **v5 修净值非实时（task OC-DATA-BE2）**：`value_fund` official 档改为「最近一期官方净值」，非盘中不再误落 `intraday`；`/runtime.staleness.latest_date` 与 `nav_of` 改读实时净值缓存。实测 `/valuations` **official:22 / intraday:0 / unknown:0**，抽查 `nav_date=2026-09-11`（QDII 为 09-10），`/runtime.staleness.latest_date=2026-09-11 / days_behind=1`（修复前 08-25 / 18）。**65/65 测试通过**（v4 为 59，v5 新增 3 类 6 条）。
8. **v6 影子盘 20 交易日滚动回填 + 因子上限口径（task OC-SHADOW-BE）**：`backfill_ledger` 实装为真实引擎走前计算，落 **200 条 / 20 交易日 / 2026-08-17~2026-09-11**（INSERT-ONLY、每日追加+裁剪最旧、重复触发幂等、裁剪全量归档）；台账行新增 `opened`；`/factors/pans` adopted 新增 `caps={veto_max:4,score_max:3}` 且 `rule_text`「否决位 ≤4 · 打分位 ≤3」、误导 `factor_cap` 置 null；信号时间线改读全量台账（`last_open=2026-08-20`）。**70/70 测试通过**（v5 为 65，v6 新增 `test_shadow_backfill_contract.py` 5 条）。
9. **v7 因子回测引擎 + 真回测填盘（task OC-FACTOR-BE）**：新增深度模块 `factor_engine.py`（`evaluate` 唯一对外接口，见 §0e），按机制实现六窗走前 CV（purge=H+2）、基线 `max(恒涨,恒跌)`、k_lift 五档悬崖、窗权重 `8/22/15/10/30/15`、准入度 `min(1,独立触发日/N_w)`、bootstrap 500 校准分位、F1/F2/F3、牌照/盘位。**用真实数据回测引擎在用的两因子**（9 代理 ETF × 320 bar）：`KLOW2 下影线否决` 六窗 lift = **1.3059/1.1459/1.1328/1.1075/1.0720/1.0720**、总分 **61.05**（牌照 probation）；`拥挤度六维复合否决` lift = **1.0000/0.9764/1.0746/1.0326/1.0113/1.0113**、总分 **21.40**（none）。新接口 `POST /factors/candidates`（示例 mom5）实测返回记分卡：`total=31.7`、F1 pass（lift m6=1.0252）/ F2 pass（max\|corr\|=0.0723 vs crowd）/ F3 fail（Δ=−0.0556）、`verdict=rejected_f3`；同定义重复提交幂等（`duplicate=true` 同 candidate_id）。**88/88 测试通过**（v6 为 70，v7 新增 `test_factor_engine_contract.py` 18 条）。
10. **v8 覆盖度 D 档压缩（task OC-COV-BE）**：新增 `proxy_map.py` 完整 **22/22** fund→proxy 映射（A2/B13/C5/D2 设计），并对 2 只主动全市场基金 **持仓穿透**（东财 F10 前十 → 个股→行业 ETF 加权）。**实测分档 before `A10/B0/C0/D12`（D 占 54.5%）→ after `A2/B13/C7/D0`（D 占 0%）**；`/holdings/coverage` 新增 `no_proxy_count=0`、`penetrated_count=2`；`/holdings` 每行新增 `penetration_trace`（前十明细+映射依据）。穿透样例：`025500` 前十 62.34% → **半导体ETF(512480)**；`021528` 前十 72.31% → **通信ETF(515880)**（篮子含消费电子/有色，均标「待验证」）。**100/100 测试通过**（v7 为 88，v8 新增 `test_proxy_map_contract.py` 12 条）。
11. **v10 主动基金重仓加权估值（task OC-HOLDVAL-BE）**：用户指正「主动基金不该用 ETF 做估值锚点」。新增基金类型分类 + F10 前十抓取 + 腾讯批量个股实时；主动基金估值锚点改为 **前十大重仓股加权**（`weighted_change=Σ(w_i×chg_i)/Σw_i`，`estimated_nav=最新官方净值×(1+weighted_change)`），**优先于 proxy**，前十不可得才回退；指数联接/QDII 维持 `official/intraday/proxy`。实测（8791，周六非盘中）`/valuations` **before official:22 → after holdings:5 / official:17**；盘中模拟 **before proxy:11 / intraday:11 → after holdings:5 / intraday:11 / proxy:6**（主动 5 只全部 `holdings`，QDII 6 只 `proxy`，指数联接 11 只 `intraday`）。样例 `014320` trace 含前十加权明细（covered 45.57%、weighted −0.0229、base_nav 2.5664、est 2.5077）。**117/117 测试通过**（新增 `test_active_holdings_contract.py` 13 条）。

## 正文

### 0. v3 修复轮落地与回归（契约 v5 · OC-R4-BE，2026-09-12）

> 依据 `20-arch-verdict-r2` §2~§6 的「对后端最小可执行规格」逐条实现；来源与断言一一对应。

| # | 裁定 | 落点（文件:函数/字段） | 改动 | 断言/实测证据 |
|---|---|---|---|---|
| BLOCK-2 | `Settings.llm.base_url` | `settings.py`: `DEFAULT_SETTINGS`、`get_settings`（输出键含 `base_url`）、`update_settings`（URL 校验 `^https?://.+`，非法 `E_VALIDATION`/`error.detail.base_url`） | 新增字段：GET 回 `""`（空串非 null）、PUT 原子落盘 | `tests/test_app_contract.py::SettingsBaseUrlV5Test` 4 条；实测 `PUT https://api.deepseek.com/v1` → `GET` 回读一致；非法值 HTTP 400 |
| SHOULD-5 | `naive_p` 研究口径 | `engine.py#naive_p`（`naive_n>0` 即给 `naive_up/naive_n`，**去 MIN_N 门控**）；`engine.py#build_cube` 每格新增 `naive_low_sample`、`status` 改 `filled ⟺ naive_n>0` | 删除 MIN_N 门；empty 两 P 仍 null、`color_band="no_sample"` | `tests/test_engine_contract.py::CubeV5Test` 3 条 + `DdsmTest` v5 2 条；实测 017193：`valid_coverage_naive_pct` 0.0→**0.92**，115 有样本格全带 `naive_low_sample=true`，10 空格两 P null |
| SHOULD-4 | `PredictionSummary.tier/market_value` | `app.py#h_predictions`、`h_prediction_get`（经新助手 `_prediction_public`，market_value 走 `valuation.market_value_of`，无净值则 null、**禁成本回退** A-02） | 两键直出，前端不再跨接口拼装 | `tests/test_app_contract.py::PredictionSummaryV5Test` 3 条；实测 `/predictions` 10 行与 `/holdings` 同 code 的 `tier/market_value` 不一致 **0** 处 |
| 缺口4 | `precision.groups[].label` | `valuation.py#precision_summary`（新增 `CONF_GROUP_LABEL` `high→高/mid→中/low→低/unknown→无`） | 每项补 `label`，键集合 `{confidence,label,count,market_value,weight_ratio}` | `tests/test_valuation_contract.py::PrecisionGroupLabelV5Test` 2 条；实测 `/valuations/precision` `groups[].label = 高,无` |
| SHOULD-1 | `FrozenParams` 三数组键名冻结 | `engine.py#frozen_params`：`window_weights` `{window,weight}`、`window_min_days` `{window,n_w}`、`license_lines` `{license,min_independent_days,window_k}` | 确认前两数组已符合；**修正** `license_lines.candidate` 原 `{...,note}` → `{...,window_k:null}`（见 §7 V1） | `tests/test_engine_contract.py::FrozenParamsV5Test` 3 条；实测三数组键集合恒等（多余/缺失即 FAIL） |

**v5 语义钉死复述**：`MIN_N=15` 只门控生产口径 `ddsm_p`／`ddsm_state`；研究口径 `naive_p` 只要 `naive_n>0` 就给原始频率，低样本由 `naive_low_sample` 标注，不再整片「无样本」。

### 0b. v4 修复轮 · F-PM-01 覆盖口径（task OC-BUG-BE，2026-09-12）

> 终验发现（P1）：`GET /api/v1/holdings/summary` 报 `covered_count=22/22`、「可信估值覆盖 22/22」，但 `today_pnl_amt` 实际只聚合 10 只（`change_rate` 非 null 者）；口径按「有市值（`market_value != null`，含 nav 回填的 unknown 行）」计数，与 PRD F-01 验收②「仅覆盖 N/M 只」不符。

| 项 | 旧实现 | v4 实现（落点） | 断言/实测证据 |
|---|---|---|---|
| `covered_count` | `market_value != null` 的只数（含 nav 回填 unknown 行） | **`change_rate != null` 的只数**（`fund_predict.py#holdings_summary`，逐行取 `valuation.get_cached().change_rate`） | `tests/test_holdings_summary_contract.py::HoldingsSummaryCoverageTest` 3 条；实测当前数据 `covered_count=10 / total_count=22`，`covered_count < total_count = true` |
| `coverage_note` | 由旧 `covered_count` 生成 → 22/22 | 由新 `covered_count` 生成 → 「可信估值覆盖 10/22 只；无未知行按成本计」 | 同上（断言含 `1/2`、`0/2`；全可信时含「全部覆盖」） |
| `today_pnl_amt` | 仅 `change_rate != null` 且 `market_value != null` 行参与 | **不变**（本就与可信估值口径一致；实测 `-290.25` 修复前后同值） | 同上（断言 100−100/1.01≈0.99） |
| `total_value` / `covered_cost_amount` / `total_pnl_amt` / `return_rate` | `market_value != null` 口径（A-02） | **不变**（仅 `covered_count` 口径变更，未动资产/成本字段） | §6 实测字段回归 |

- 边界：`change_rate != null` 但 `market_value == null` 的行计入 `covered_count`（可信覆盖）但不进 `today_pnl`（无市值不可算），与契约「未知行从分子分母同剔」一致。
- 偏差登记：契约 v5（`09-api-contract.md` §6.2.1）文字仍写 `covered_count` 按 `market_value != null`、且注「非按 `change_rate`」；本修复按 PRD F-01 反向落字段（见 §7 V3），**建议架构师将契约同步回 v1 口径**。

### 0c. v5 修复轮 · 净值快照实时化（task OC-DATA-BE2，2026-09-12）

> 问题：上一轮（OC-DATA-BE）`/valuations` 实测 `intraday:11 / unknown:11`，`nav_date` 仍为源文件滞后值 `2026-08-25`；当日为周六（非交易日），不应产出盘中估算 `intraday`。用户诉求：净值快照必须实时抓、反映**最近一期官方净值**。
> 根因：① `valuation.value_fund` 档1 official 命中条件为 `official_date == as_of_date`，非交易日官方净值日（09-11）≠ 当日（09-12）→ official 永不命中 → 误落档2 intraday；② `/runtime.staleness.latest_date` 取 `holdings.latest_nav()` 源文件 `nav_history`（08-25）。

| # | 交付 | 落点（文件:函数） | 改动 | 实测证据 |
|---|---|---|---|---|
| 1 | 最新官方净值为准 | `valuation.py#value_fund` | 档1 `hit1 = official_nav is not None and (not intraday_allowed or official_date == as_of_date)`；非盘中即 `official` 且 `nav_date=jzrq`；官方值走 `estimator.get_official_nav`（FundValuationLast → lsjz） | `/valuations` mode 分布 **official:22 / intraday:0 / unknown:0**（N=22） |
| 2 | 非盘中不产 intraday | `valuation.py#trade_session`、`#_mode_reusable`、`#refresh_all` | 新增 `trade_session()`（pre_open/trading/closed/non_trading_day）；非 `trading` 时档2 trace 记 `tried=false`，`refresh_all` 不复用当日 intraday 缓存 | 今日 `trade_session=non_trading_day`；抽样 `trace=[{official,tried:true,hit:true,reason:hit}]`，无 intraday 命中 |
| 3 | staleness 实时 | `app.py#h_runtime`、`#_latest_nav_date` | latest 取 `estimator.cached_nav_dates()`（FundValuationLast/lsjz 缓存）优先，源文件仅回退；窗口 300s | `/runtime.staleness.latest_date=2026-09-11`、`days_behind=1`、`note="数据快照 2026-09-11"`（修复前 08-25 / 18） |
| 4 | trace 如实 + 失败留痕 | `valuation.py#value_fund` trace、`estimator.record_source` | official hit 记 `reason=hit`；抓取失败回退缓存并 `record_source("eastmoney", False, …)`，全链路无数据才 `unknown`（`change_rate=null`） | 22/22 `reason=hit`，`trace_text="official 命中"` |
| 5 | 启动/任务触发抓取 | `app.py#_warmup`、`#_run_task`；`estimator.refresh_fund_valuation(force=)` | warmup 与 `refresh_valuation` 任务内 `refresh_fund_valuation(force=True)` + `refresh_official_nav`；单源 5s 超时、批量 50/请求、TTL 缓存 | `POST /tasks {type:refresh_valuation}` → `status=done`，`result_summary="估值刷新 22/22"` |

**nav_of 同步**：`valuation.nav_of` 优先读实时官方净值缓存（`estimator.get_official_nav(allow_network=False)`），回退源文件 `nav_history`；实测抽样 `nav.official_nav_date=2026-09-11`，与 `valuation.nav_date` 一致，`nav.official_change_rate` 取 lsjz 官方日涨跌（如 000217 = -0.0143）。

**字段契约**：未新增/改名任何字段；`trace.reason` 仍属冻结枚举 `trace_reason`（非盘中不产 intraday 用 `tried=false, reason="not_published"`）。`trade_session` 复用契约枚举，`app._trade_session` 改为委托 `valuation.trade_session()`（去重复实现）。

### 0d. v6 影子盘 20 交易日滚动回填 + 因子上限口径修正（task OC-SHADOW-BE，2026-09-12）

> 用户诉求：影子盘/信号/因子目前全空——**影子盘当下先抓过去 20 个交易日，每过一天替换一天（滚动 20 个交易日）**；因子正式盘「上限 3」是错的，真实规则为**否决位 ≤4 · 打分位 ≤3**。

**落点与实现**

| # | 交付 | 落点（文件:函数） | 实现要点 | 实测证据 |
|---|---|---|---|---|
| 1 | 20 交易日滚动回填引擎 | `ledger_api.py`: `compute_shadow_window` / `_predict_historical` / `rolling_shadow_backfill` / `_load_proxy_bars` | 交易日历 = 监控 A/B 档代理 K 线日期**并集**（真实盘中日历，非工作日近似）；每 (date, code) 走前预测（`engine.train_model(bars[:t-1])`，purge=H+2 → 标签最晚 t-2，不越界到 t+1；`engine.predict_at` 出 gate/p_up/ddsm_state/双否决/signal）；`opened = signal=="up"` | `GET /ledger` total **200** 条 / **20** 交易日 / **2026-08-17~2026-09-11** / 10 个 A/B 代理资产；`opened=true` **4** 条 |
| 2 | INSERT-ONLY + 滚动替换 | `rolling_shadow_backfill` / `_write_all_signals` / `_archive_records` | 同 (date,code) 已存在即跳过；窗口随最新交易日右移，窗口外旧行**先归档**（`ledger/archive/shadow_signals_archive.jsonl` + `_manifest.jsonl`）再从主文件移除；无新增且无裁剪时**不触碰文件** | 重复触发：`written=0 / trimmed=0 / total=200`（`before==after`）；滚动用例见 `tests/test_shadow_backfill_contract.py`（追加一日 → `written=2 / trimmed=2 / total=40`） |
| 3 | 任务与启动触发 | `app.py#_run_task`（`backfill_ledger` 分支）、`app.py#_warmup` | 任务调用 `rolling_shadow_backfill(20, allow_network=True)`；启动预热末尾自动滚动回填（重复启动幂等） | `POST /api/v1/tasks {type:"backfill_ledger"}` → `status=done`、`result_summary="影子台账回填：窗口 20 日 / 200 条 / 2026-08-17~2026-09-11（新增 0，裁剪 0）"` |
| 4 | 台账行新增 `opened` | `ledger_api.FIELD_LIST`、`_decorate` | 新字段 `opened`(bool) 只加不改；旧行无该字段时按 `signal=="up"` 派生 | `/ledger` 行含 `opened`；`shadow.summary.open_signals=4` |
| 5 | 因子上限口径修正 | `factor_board.py`: `PAN_META["adopted"]`、`pans()` | 正式盘新增 `caps={"veto_max":4,"score_max":3}`；`rule_text` 明确「否决位 ≤4 · 打分位 ≤3」；误导性 `factor_cap`（旧 3）置 `null`；其余盘 `caps=null` | `GET /factors/pans` adopted：`caps.veto_max=4 / caps.score_max=3`、`factor_cap=null` |
| 6 | 信号时间线取真实开口 | `fund_predict.py#_last_open_from_ledger` | 改读全量台账（`read_ledger(limit=None)`），修正「开口落到默认 60 行分页之外时误报无开口」 | 修复前 `last_open=null`；修复后 `last_open={date:2026-08-20, code:002963, gate:E1}`、`days_since_last_open=16` |

**依赖接口回归**：`GET /review/reconciliation` total **200**（据台账）；`GET /ledger/shadow` `summary={total_records:200, open_signals:4, veto_abstains:13}`；`archive_manifest_at=null`（窗口尚未滚动，未产生裁剪归档，属真实状态）。

**真实数据原则**：窗口内每日固定产出所有监控资产的记录；某日无开口则如实 `opened=false`（实测 196/200 为 false），**未使用任何示例/演示数字**；`p_up` 走前计算缺样本时显式 `null`。

**六窗 lift 如实为空**：正式盘因子来自 `ledger/adopted_factors.json`（当前为空），`_factor_item.lift_bars` 无真实六窗评估 → 全部 `lift=null`，**未编造 lift**（保持"因子引擎产出后回填"残留风险）。

### 0e. v7 因子回测引擎 + 真回测填盘（task OC-FACTOR-BE，2026-09-12 · 契约 v7）

> 依据 `21-factor-governance.md`（权威机制）与 `09-api-contract.md` v7（§5.35~§5.37、§6.8）。目标：把「新因子如何回测/准入」做成**可复用机制**，并用它跑出引擎在用两因子的**真实六窗记分卡**填进因子盘（R7，禁 legacy 示例数字）。

**落点与实现**

| # | 交付 | 落点（文件:函数） | 实现要点 | 实测证据 |
|---|---|---|---|---|
| 1 | 回测器深度模块 | `factor_engine.py`: `evaluate(definition, assets_bars, frozen_config)` | 因子 = 声明式 AST 纯表达式（`_generic_fired` 逐日求值，归一化**每折只用 `[0,t-(H+2)]` 训练段**）；内置因子复用 `engine` 原语（`features_at`/`VETO_*_QUANTILE`/`_corr`/`quantile`）；六窗走前（`_window_bounds` 以真实交易日并集定边界、holdout 60 日不参与）；基线按**窗口去重叠全测试日集**算 `max(恒涨,恒跌)`；独立触发日按 `t-last>=H` 去重叠 | `tests/test_factor_engine_contract.py`（18 条） |
| 2 | 评分链 | `factor_engine.k_lift_of/cliff_of/admission_of` | k_lift 五档悬崖（≥1.30→1.0 / ≥1.20→0.80 / ≥1.10→0.65 / ≥1.00→0.50 / <1.00→−0.80 / <0.84→−1.3 / null→0）；窗权重 `8/22/15/10/30/15`；`score=k_lift×weight×admission`；`total=Σscore` | 悬崖边界 11 点断言全过（含 1.29/1.30、0.83/0.84） |
| 3 | bootstrap 校准分位 | `_bootstrap_percentiles`（500 次） | 打乱候选每日触发日为同频随机日期、每次跑完整六窗评分链得零分布；输出 `{p50,p90,p95,p99,p995}` 与 `total_score_percentile` | KLOW2 实测 `{p50:-12.4, p90:26.6, p95:38.27, p99:50.0, p995:50.0}`、分位 1.0；crowd6 `{p50:-18.9, p90:21.4, p95:30.5, p99:51.2, p995:51.2}`、分位 0.904（**真实零分布，替换 legacy 常量**，R3） |
| 4 | 准入三项 F1/F2/F3 | `_f2_independence` / `_f3_increment` | F1 `lift(m6)>1` 或 `lift(d60)>1`；F2 与现役逐日信号 `max\|corr\|<0.70`；F3 加入现生产配置后 `Δ≥+0.5pp` 且开口不塌方（`new≥0.5×base`） | mom5：F1 pass / F2 pass（0.0723 vs crowd）/ F3 fail（Δ=−0.0556，开口 27/39=69.2%） |
| 5 | 真回测填盘 | `build_adopted_pan` → `ledger/adopted_factors.json` | 对 `klow2`/`crowd6` 两个 `_builtin` 定义跑 `evaluate`，落 adopted 记录（`role=adopted`、`role_label=否决位`、`status=active`、六窗 lift/score、总分、牌照、backtest 块） | `/factors/pans` adopted `factor_count=2`（见下表） |
| 6 | 契约 v7 两接口 | `app.py`: `h_factors_candidate_submit` / `h_factors_candidate_get`；路由 54/55 | `POST` 校验→落 `factor_candidates.jsonl`（INSERT-ONLY，`definition_hash` 幂等）→回测→落 `scorecards.jsonl`+`scan_history.jsonl`+`factor_arena.jsonl`→202；`GET` 取记分卡（`include_windows=false` 时 `windows=null`） | 见「候选流程实测」 |
| 7 | 评分链接口真实化 | `factor_board.score_chain` | 契约字段 `bootstrap_percentiles` 保持常量；**新增** `bootstrap_percentiles_measured`（实测零分布）与 `real_engine=true` | `GET /factors/score-chain` 回传 `real_engine=true`、`bootstrap_percentiles_measured` 非空 |

**真回测数值（六窗 + 总分，禁 legacy 示例数字）**

| 因子 | d15 lift | d30 lift | d60 lift | m6 lift | m24 lift | full lift | 总分 | 牌照 | 独立触发日(full) | 开口(full) |
|---|---|---|---|---|---|---|---|---|---|---|
| `klow2` KLOW2 下影线否决 | 1.3059 | 1.1459 | 1.1328 | 1.1075 | 1.0720 | 1.0720 | **61.05** | probation | 863 | 954 |
| `crowd6` 拥挤度六维复合否决 | 1.0000 | 0.9764 | 1.0746 | 1.0326 | 1.0113 | 1.0113 | **21.40** | none | 861 | 952 |

- 样本区间 `2025-05-26..2026-06-22`（holdout = 最近 60 交易日 `2026-06-23..2026-09-11` 不入评分）；9 个 A/B 档代理 ETF；`cv_mode=walk_forward`、`purge_gap=H+2`。
- 口径注：机制 §2.4 规定「本项目永不做空，命中=到期上涨」；`orientation` 只决定触发方向。两因子为**否决层**，故 lift 读作「该层亮灯日的上涨概率 ÷ 同窗基线」——`klow2` lift>1 表示「低 KLOW2（下影线弱）日反而更常上涨」，即该层在本样本上**逆选择**；此为真实回测结果，已登记为偏差 V9 供架构师裁定（是否应改为评估「未亮灯/放行日」口径）。
- `crowd6` 的 `verdict=rejected_f2`（与 `klow2` 最大共线 ≥0.70）属候选准入判定；两因子为**引擎在用原语**，盘位仍按 adopted 登记（回测块保留 verdict 供审计）。

**候选流程实测（`python app.py` 8791）**

- `POST /api/v1/factors/candidates`（示例 `mom5 五日动量`：`binary_signal`/`higher_bullish`/`score`/`horizon=1`/`expression=gt(mom5,0)`/`normalization=none`）→ HTTP **202**，`data={candidate_id, factor_id, definition_hash, status:"done", task_id, submitted_at, scorecard}`；记分卡 `total_score=31.7`、`F1=pass`、`F2=pass(max_collinearity=0.0723,collinear_with=crowd)`、`F3=fail(delta_pp=-0.0556, open_count_new=27, open_count_base=39, collapse_ratio=0.6923)`、`verdict=rejected_f3`、`pan=null`、`license=none`、`bootstrap_percentiles` 非空、`total_score_percentile=0.954`。
- 同定义再 `POST` → `duplicate=true` 且回同一 `candidate_id`（`definition_hash` 幂等，数值序列化已规范化 `0.0≡0`）。
- `GET /factors/candidates/{id}` → `status=done`、`verdict=rejected_f3`、`windows` 6 项；`?include_windows=false` → `windows=null`。
- 负向：未声明列 / 负 `lag` / 负 `shift` / 未知 op → `E_VALIDATION`（`error.detail` 字段级）；未知 `candidate_id` → `E_NOT_FOUND`；防前视（改未来 bar 不改过去信号）单测通过。

**账本与缓存**：候选 `ledger/factor_candidates.jsonl`、记分卡 `ledger/scorecards.jsonl`、挖掘 `ledger/scan_history.jsonl`、竞技场 `ledger/factor_arena.jsonl` 均 INSERT-ONLY；两内置因子的复用信号缓存于 `data/cache/factor/signals.json`（按数据指纹+`H` 键，离线可复现）。**R4 路径裁定**：因子账本统一落 `ledger/`（与 `factor_board` 读取一致），不使用 `06-system-arch` 的 `data/factors/`。

### 0f. v8 覆盖度档位补全 + 主动基金持仓穿透（task OC-COV-BE，2026-09-12）

> 用户诉求：持仓覆盖度里 **D「暴露待定」占了大部分（约 12/22）**——独立实现只映射了约 10 只，其余无代理即归 D。要真正解决：**补全 fund→proxy 映射 + 对真·主动全市场基金做持仓穿透**。诚实优先：映射不到仍留 D，禁编造代理，穿透结果标「待验证」。

**落点与实现**

| # | 交付 | 落点（文件:函数） | 实现要点 | 实测证据 |
|---|---|---|---|---|
| 1 | 完整映射表（22/22） | `proxy_map.py`: `PROXY_MAP` | A=行业 ETF 直接对应（半导体 `512480` / 军工 `512660`）；B=代理 ETF 已映射且可取日线（黄金 `518880`、纳指 `513100`、通信 `515880`、电力 `561560`、有色 `512400`、机器人 `562500`、AI `515070`、消费电子 `561600`、中证1000 `512100`、科创创业50 `588300`）；C=拟用/近似（A500 `159352`、恒生 `159920`、油气 `162411`、CPO 近似 `515880`） | 静态 20 只分档计数 **A=2 / B=13 / C=5**（§6 实测） |
| 2 | F10 持仓穿透 | `proxy_map.py`: `fetch_f10_holdings` / `parse_f10_holdings` / `penetrate_rows` | 抓东财 F10 前十（UTF-8 HTML、UA+Referer、5s 超时、重试 1）；正则解析前十；`STOCK_ETF_MAP`（个股→行业 ETF）按权重归集加权篮子，主代理=权重最高 ETF；结果缓存 `data/cache/proxy/penetration.json`（24h TTL） | `025500` 前十 62.34%→`512480`；`021528` 前十 72.31%→`515880`（见下方 trace） |
| 3 | 档位实时同步 | `holdings.py`: `sync_proxy_fields`（`ensure_holdings` 调用） | 不联网，按静态映射+穿透缓存重算全部持仓 `tier/proxy_code/proxy_name/tier_reason/penetration_trace`；幂等，仅变更时落盘 | 存量文件 D12→0（§6 before/after） |
| 4 | 输出接线 | `fund_predict.py#build_holding_row`（`penetration_trace`）、`app.py#h_holdings_coverage`（`no_proxy_count`/`penetrated_count`） | HoldingRow 只加 `penetration_trace`；CoveragePanel 只加两计数键；字段名不改 | `/holdings` 行含 trace；`/holdings/coverage` `no_proxy_count=0`、`penetrated_count=2` |
| 5 | 启动刷新 | `app.py#_warmup` + `proxy_map.refresh_penetrations` | 启动后台刷新穿透缓存（24h 内跳过）；网络失败保留旧缓存，仍留 D 不阻塞 | 缓存 `fetched_at=2026-09-12T13:01:23+08:00`，`report_date=2026-06-30` |

**before / after 分档表（`python app.py` 8791 实测，2026-09-12）**

| 档位 | before 只数 | before 占比 | after 只数 | after 占比 | 变化 |
|---|---|---|---|---|---|
| A 已接入 | 10 | 45.45% | **2** | 9.09% | −8（按完整映射重分：黄金/纳指/各行业降 B，A500 降 C，增半导体/军工 A） |
| B 代理已验证 | 0 | 0% | **13** | 59.09% | +13 |
| C 代理待验证 | 0 | 0% | **7** | 31.82% | +7（含 2 只穿透得出） |
| **D 暴露待定** | **12** | **54.55%** | **0** | **0.0%** | **−12（穿透后 0）** |
| 合计 | 22 | 100% | 22 | 100% | — |

- 补充证据（`/holdings/coverage`）：`no_proxy_count=0`、`penetrated_count=2`；D 档 `market_value=0.0`、`weight_ratio=0.0`。
- B 档「可取到日线」实测：15 个代理 ETF 全部腾讯日K **320 根**、最新 `2026-09-11`（`tencent_kline`）。

**穿透样例 trace（真实 F10，报告期 2026-06-30；标注「待验证」）**

- `025500 东方阿尔法科技智选混合发起C` → tier **C**，主代理 `512480 半导体ETF国联安`（前十映射权重 **62.34%**）：
  前十持仓：兆易创新 8.31 / 香农芯创 7.30 / 江波龙 6.90 / 君正股份 6.82 / 佰维存储 6.80 / 德明利 6.79 / 普冉股份 6.32 / 澜起科技 4.88 / 东芯股份 4.27 / 聚辰股份 3.95（全部→半导体ETF `512480`）。
- `021528 财通成长优选混合C` → tier **C**，主代理 `515880 通信ETF国泰`（前十映射权重 **72.31%**）：
  加权篮子：`515880` 53.30%（新易盛 9.47 / 南亚新材 8.75 / 源杰科技 8.63 / 德福科技 7.92 / 鼎泰高科 7.82 / 大族数控 7.10 / 华正新材 3.61）、`561600 消费电子ETF平安` 14.73%（三环集团 7.93 / 风华高科 6.80）、`512400 有色金属ETF南方` 4.28%（博迁新材，近似）。
- `penetration_trace` 结构：`{method, source, report_date, top10[], basket[], mapped_weight_pct, unmapped[], proxy, proxy_basis, confidence:"low", status:"待验证"}`；穿透不到时仍写 trace（`status="无映射（待补充个股→ETF 映射）"`）并留 D。

**诚实性**：① 映射不到/穿透不到的代码一律 `resolve()` → D、`proxy_code=null`（单测覆盖未知码与空前十）；② 穿透主代理一律 `confidence="low"`、`status="待验证"`，未宣称已验证；③ 未新增任何「看起来对」的兜底数字。

### 0g. v9 影子盘状态接线修正（task OC-SHADOWSTAT-BE，2026-09-12）

> 用户诉求：「影子盘记了最近 20 日还是不启动」。
> 根因：`app.py:658` 的 `shadow_status` 取 `shadow_audit()["status"]`（**偏差评估**：窗口内 `signal=="up"` 且已回填 `t1_real` 者才可算命中率，当前无 → `idle`），而非 `shadow_progress()["status"]`（**进度评估**：台账有 20 个交易日 → `recording`）。两套枚举不相交：`{idle,ok,bad}` vs `{not_started,recording,qualified,gap}`。

**落点与实现**

| # | 交付 | 落点（文件:函数） | 实现要点 | 实测证据 |
|---|---|---|---|---|
| 1 | `shadow_status` 改进度语义 | `app.py#h_engine_status` | `progress = ledger_api.shadow_progress()`；`shadow_status = progress.get("status","not_started")`（`not_started/recording/qualified/gap`） | `GET /engine/status` → `shadow_status=recording`（修复前 `idle`） |
| 2 | 偏差评估独立字段（只加不改） | `app.py#h_engine_status` | 新增 `shadow_audit_status = audit.get("status","idle")`（`idle/ok/bad`，契约 §5.29 `/engine/shadow-review` 语义）；`audit` 仍取自 `shadow_audit()` | 同一响应 `shadow_audit_status=idle`（无 up 信号，如实），与 `shadow_status` 并存 |
| 3 | 连续交易日如实 | `app.py#h_engine_status`（沿用 `progress["consecutive_days"]`） | `shadow_consecutive_days` 取 `shadow_progress()` 台账连续交易日；`shadow_target_days` 恒 60 | `shadow_consecutive_days=20`、`shadow_target_days=60`（台账 320 行 / 20 交易日 / 2026-08-17~2026-09-11） |

**语义钉死**：`shadow_status` 从此回答「**记录进行到哪一步**」（进度），`shadow_audit_status` 回答「**偏差是否达标**」（审查）。二者可同时存在且不互相覆盖——进度 `recording` 时审查仍可 `idle`（未满 60 日无足够命中样本）。

**回归与测试**：新增 `tests/test_shadow_status_contract.py` 4 条——① 有台账（20 个连续工作日）→ `shadow_status=recording`、`consecutive_days=20`；② 无台账 → `not_started`、`consecutive_days=0`；③ audit 与 progress 分离（全 `gray` 无命中 → progress `recording` / audit `idle`，两字段同时存在且各取各自值）；④ 全 `up` 且回填命中率 0.6（偏差 1.7pp<2pp）→ audit `ok`，`shadow_status` 仍 `recording`（不受审查结论影响）。**104/104 测试通过**（v8 为 100，v9 新增 4 条）。

### 0h. v10 主动基金重仓加权估值（task OC-HOLDVAL-BE，2026-09-12）

> 用户指正：**主动基金不该用 ETF 做估值锚点，应改用「前十大重仓股加权」**（主流平台做法）；此前实现把主动基金也走了 `proxy`(ETF)，不对。
> 边界：`预测锚点 ≠ 估值锚点`——**估值**用重仓加权；**预测（方向信号）仍需可交易代理 ETF 的价格序列**（基金自身净值 T+1/T+2 无日内历史），此点不变。

**1）基金类型分类（`estimator.classify_fund_type`，落到持仓字段 `fund_type`）**

| 类型 | 判定（按名称关键字） | 本期 22 只 |
|---|---|---|
| `active` 主动 | 含「混合/股票/灵活」且非 QDII/指数/ETF联接 | 025500 / 018957 / 021528 / 013566 / 014320（5） |
| `index_link` 指数联接 | 含「指数/ETF/联接/LOF/黄金」 | 11 只 |
| `qdii` QDII | 含「QDII/全球/亚洲/海外/纳指/标普/油气/美元…」 | 6 只 |
| `other` 其他 | 均不匹配（保守走 proxy） | 0 |

QDII 标记优先于「混合」，避免 QDII 混合基金被误做重仓加权；分类结果写入持仓 JSON、`Valuation`、`HoldingRow`（只加不改）。

**2）重仓加权链（`valuation.value_fund` + `estimator.eastmoney_top_holdings`）**

| # | 交付 | 落点（文件:函数） | 实现要点 |
|---|---|---|---|
| 1 | 前十大抓取解析 | `estimator.fetch_top_holdings` / `parse_top_holdings` | 天天基金 F10 `FundArchivesDatas.aspx?type=jjcc&code=<code>&topline=10`（HTML；UA+Referer；5s 超时）；取当期第一个 `<table>` 的 `序号/股票代码/股票名称/占净值比例%`；30 天缓存落 `data/cache/holdings/<code>.json` |
| 2 | 个股实时（批量） | `estimator.tencent_rt_quotes` | 腾讯 `qt.gtimg.cn/q=<sh|sz><code>,…` 一次批量请求全部 A 股持仓；`change_rate = price/prev_close − 1`；非 6 位代码（如港股 `01347`）不入报价，`day_change=null` 如实剔除 |
| 3 | 加权公式 | `valuation._weighted_holdings` | `weighted_change = Σ(w_i×chg_i)/Σw_i`；仅 `weight` 与 `day_change` 均非 null 者参与；`estimated_nav = 最新官方净值 × (1+weighted_change)`；`detail` 记录前十逐只 `weight/day_change/contribution/used` 与 `covered_weight_pct/total_weight_pct` |
| 4 | 五档链改锚 | `valuation.value_fund` | 主动基金：`official` 仅当**当日官方已发布**（`nav_date==as_of`）命中，否则 `intraday` 记 `tried=false`、直接走 `holdings`；**优先于 proxy**，前十不可得才回退 `proxy`；指数联接/QDII/其他：不做重仓加权（`holdings tried=false`），维持 `official→intraday→proxy` |
| 5 | 字段落位（只加不改） | `valuation.public_valuation` / `fund_predict.build_holding_row` / `holdings.sync_proxy_fields` | `Valuation` 与 `HoldingRow` 新增 `fund_type`/`fund_type_label`；`trace[holdings].detail` 承载加权过程；持仓 JSON `fund_type` 由 `sync_proxy_fields` 幂等回填 |

**3）自证 before/after（实测，2026-09-12）**

- **`python app.py`（8791，周六 `trade_session=non_trading_day`）`GET /api/v1/valuations` N=22**：
  - **before**（v9 存量快照）：`official:22`（主动基金因「非盘中取最近一期官方净值」而全部 `official`，**并未暴露 proxy 问题**）。
  - **after**：`holdings:5 / official:17`——5 只主动全部 `holdings`（`mode_label=重仓加权`）；11 只指数联接 + 6 只 QDII 维持 `official`。
- **盘中模拟**（`value_fund(session="trading", as_of=2026-09-14)`，官方未出当日）：
  - **before**（旧链，主动也走 intraday/proxy）：`proxy:11 / intraday:11`（5 只主动全部落 proxy）。
  - **after**：`holdings:5 / intraday:11 / proxy:6`——主动 5 → `holdings`；指数联接 11 → `intraday`；QDII 6 → `proxy`（盘中估算无数据，回退代理）。
- **样例 trace（`014320` 东方阿尔法产业混合C，实测 `/api/v1/valuations/014320`）**：
  - `valuation_mode=holdings`、`mode_label=重仓加权`、`change_rate=-0.0229`、`estimated_nav=2.5077`、`nav_date=2026-09-11`、`fund_type=active/主动`。
  - `trace = [official tried/not_published, intraday tried=false, holdings hit]`；`holdings.detail.report_date=2026-06-30`、`covered_weight_pct=45.57`、`total_weight_pct=50.36`、`weighted_change=-0.0229`、`base_nav=2.5664`、`estimated_nav=2.5077`；`top10` 含 10 行（`603986 兆易创新` w6.84 chg−0.0245 … `01347 华虹半导体` w4.79 `day_change=null used=false`）。
  - 校验：`Σ contributions = −1.0423`，`Σ contributions / 45.57 = −0.02287` ✓；`2.5664 × (1−0.0229) = 2.5077` ✓。
- 5 只主动实测 `holdings` 与 covered 权重：`025500` 62.34% / `018957` 67.98% / `021528` 72.31% / `013566` 76.13% / `014320` 45.57%（`014320` 第十大含港股 `01347` 无 A 股实时报价，如实剔除）。

**4）诚实性与边界**：F10 不可得 / 个股报价缺失 → 对应 `day_change=null` 且 `used=false`（不编造）；前十整体不可得 → `holdings tried=true/hit=false/reason=no_report` 并回退 proxy；全链无数据 → `unknown`（`change_rate=null`）。外部单源 5s 超时、重试 1；纯标准库（`urllib/re/json`）。`confidence` 无 `(holdings, code)` 回测样本时如实 `unknown`（不估填）。

### 1. 重跑方法与使用的 skill（本文件为证）

| skill | 用在哪 | 产出 |
|---|---|---|
| `tdd`（红-绿，契约字段优先） | 先建 `tests/`（契约字段断言）→ 跑红 → 实现 → 全绿 | `tests/test_engine_contract.py`、`test_portfolio_contract.py`、`test_ledger_contract.py`、`test_valuation_contract.py`、`test_factor_arena_contract.py`、`test_app_contract.py` |
| `diagnosing-bugs`（先复现再改） | 红测复现 round1 立方体 empty 格 `ddsm_p` 非 null（违反 §5.25/A-07）→ 定位 `engine.build_cube` → 最小修复 | `engine.py:551` `dp_val` 分支 |
| `capability-map §4` 纪律 | skill 只供方法，不改工件结构与门禁判据（handoff-schema / gate-rules 优先） | 本报告四块正文结构 |

关键接缝（seam）= `/api/v1/*` 端点与 `core` 纯函数（`engine.predict_at`/`build_cube`、`fund_predict.portfolio_forecast`、`valuation.public_valuation`、`ledger_api.*`、`app.validate_task_payload`）。

### 2. 启动与产物

- 启动：`python app.py`（默认 `127.0.0.1:8791`，`--port N` 覆盖）；健康检查 `GET /health` 与 `GET /api/v1/runtime`。
- 模块：`app.py`（HTTP+路由+53 接口）、`engine.py`、`holdings.py`、`estimator.py`、`valuation.py`、`fund_predict.py`、`ledger_api.py`、`factor_board.py`、`risk.py`、`settings.py`、`errors.py`；`tests/`（40 断言）。
- 纯标准库：`http.server/urllib/json/math/statistics/random/threading/datetime/decimal/ssl`。`data/`（holdings/cache/snapshot/tasks）、`ledger/`（INSERT-ONLY）。
- 持仓只读 `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json`（`holdings.PRIMARY_PATH`），不改写。

### 3. v4 追加落地与验收断言（A-07~A-10）

| 裁定 | 落点（函数） | 响应字段（实测值） | 断言 |
|---|---|---|---|
| A-07 立方体双口径 | `engine.build_cube`（`engine.py` §9.1） | `production_layer="ddsm"` / `research_layer="naive"` / `default_layer="ddsm"` / `dual_view_note` 非空；empty 格 `naive_p=null` **且** `ddsm_p=null` | `test_engine_contract.CubeV4Test` 3 条 |
| A-08 组合权重冻结 | `fund_predict.portfolio_forecast`（`fund_predict.py:29/327`） | 每窗 `weighting_basis="market_value"` + `weighting_policy_note`（含"置信度"拒用说明）；响应恒带 | `test_portfolio_contract.PortfolioV4Test` 6 条 |
| A-09 竞技场色板解耦 | `factor_board.arena`（`factor_board.py:479/521/583`） | `color_scheme="performance_rank"`、`color_token_prefix="--arena-"`；格色 ∈ {red,green,blue,yellow,base}，**无 up/down** | `test_factor_arena_contract.ArenaLegendTest` 2 条 |
| A-10 台账归档保留 | `ledger_api.shadow_ledger`（`ledger_api.py:29/317`） | `retention_policy="first_of_day_immutable_full_archive"`、`first_of_day_immutable=true`、`archive_manifest_at` | `test_ledger_contract.LedgerV4Test` 2 条 |
| A-08 API 黑名单 | `app.FROZEN_PARAM_KEYS` + `app.validate_task_payload`（`app.py:67/76`）；`h_task_create` 调用点 | `POST /tasks` 传 `weighting_basis/min_coverage_ratio/min_open_count` → `E_VALIDATION` | `test_app_contract` 4 条 |

补充：`engine.frozen_params()` 增 `weighting_basis="market_value"`（契约 §5.14 v4 追加）；v4 不改既有字段名（§9.4），实测仍保留全部 v3 字段。

### 4. 逐接口实现核对（契约 §4 全 53 项 + /health）

| # | 契约接口 | 实现位置 | 字段一致性 | 状态 | v4 备注 |
|---|---|---|---|---|---|
| 1 | GET /runtime | app.py `h_runtime` | ✅ Runtime §5.18 | done | |
| 2 | GET /holdings | app.py `h_holdings` | ✅ HoldingRow §5.1 | done | **v8 行新增 `penetration_trace`（只加）** |
| 3 | GET /holdings/summary | app.py `h_holdings_summary` | ✅ §6.2.1 | done | **v4 `covered_count` 改可信估值口径（10/22）** |
| 4 | GET /holdings/{code} | app.py `h_holding_get` | ✅ §5.1 | done | |
| 5 | POST /holdings | app.py `h_holding_create` | ✅ §6.2 | done | 201/E_CONFLICT/E_VALIDATION |
| 6 | PUT /holdings/{code} | app.py `h_holding_update` | ✅ §6.2 | done | |
| 7 | DELETE /holdings/{code} | app.py `h_holding_delete` | ✅ §6.2 | done | 台账历史不删 |
| 8 | POST /holdings/{code}/transactions | app.py `h_holding_tx` | ✅ §6.2 | done | 摊薄成本 |
| 9 | POST /holdings/import | app.py `h_holding_import` | ✅ §6.2 | done | 源只读 |
| 10 | GET /valuations | app.py `h_valuations` | ✅ §6.3 | done | |
| 11 | GET /valuations/{code} | app.py `h_valuation_get` | ✅ §5.2 | done | history=true |
| 12 | GET /valuations/precision | valuation.py `precision_summary` | ✅ §6.3 | done | mode_distribution |
| 13 | GET /predictions | app.py `h_predictions` | ✅ §5.4 | done | A-06 三态 |
| 14 | GET /predictions/{code} | app.py `h_prediction_get` | ✅ §6.4 | done | 6 步 chain |
| 15 | GET /portfolio/forecast | fund_predict.py `portfolio_forecast` | ✅ §5.7 | done | **v4 `weighting_basis`** |
| 16 | GET /review/scores | app.py `h_review_scores` | ✅ §5.8 | done | pending 留空 |
| 17 | GET /review/reconciliation | ledger_api.py `reconciliation` | ✅ §5.10 | done | **v6 据台账实测 total=200** |
| 18 | GET /review/cv-config | app.py `h_review_cv_config` | ✅ §6.6 | done | holdout null |
| 19 | GET /ledger | ledger_api.py `read_ledger` | ✅ §5.9 | done | **v6 行含 `opened`，实测 20 交易日/200 条** |
| 20 | POST /ledger/entries | ledger_api.py `write_entry` | ✅ §6.7 | done | INSERT-ONLY |
| 21 | POST /ledger/backfill | ledger_api.py `write_backfill` | ✅ §6.7 | done | 独立文件 |
| 22 | GET /factors/pans | factor_board.py `pans` | ✅ §5.11 + §7 V6 | done | **v6 新增 `caps`，rule_text 明示上限** |
| 23 | GET /factors/books | factor_board.py `books` | ✅ §5.13 | done | 六本 |
| 24 | GET /factors/score-chain | factor_board.py `score_chain` | ✅ §6.8 | done | |
| 25 | GET /factors/lifecycle | factor_board.py `lifecycle` | ✅ §5.32 | done | |
| 26 | GET /engine/status | app.py `h_engine_status` | ✅ §6.9 | done | HUD 14 字段 + **v9 `shadow_status` 改进度语义、新增 `shadow_audit_status`** |
| 27 | GET /engine/inputs | app.py `h_engine_inputs` | ✅ §5.27 | done | raw/z/level/ic_sign |
| 28 | GET /engine/ddsm | app.py `h_engine_ddsm` | ✅ §6.9 | done | 125 格 |
| 29 | GET /engine/frozen-params | engine.py `frozen_params` | ✅ §5.14 | done | **v4 `weighting_basis`** |
| 30 | GET /engine/registry | app.py `h_engine_registry` | ✅ §6.9 | done | |
| 31 | GET /tasks | app.py `h_tasks` | ✅ §5.15 | done | |
| 32 | POST /tasks | app.py `h_task_create`→`validate_task_payload` | ✅ §6.9 | done | **v4 黑名单扩 3 键** |
| 33 | GET /tasks/{task_id} | app.py `h_task_get` | ✅ §5.15 | done | |
| 34 | GET /settings | settings.py `get_settings` | ✅ §5.16 | done | key 不回传 |
| 35 | PUT /settings | settings.py `update_settings` | ✅ §6.10 | done | 温度 0 冻结 |
| 36 | GET /data-sources/health | settings.py `get_health` | ✅ §5.17 | done | 4 源 |
| 37 | POST /data-sources/probe | app.py `h_sources_probe` | ✅ §6.10 | done | 202 |
| 38 | GET /about | app.py `h_about` | ✅ §6.10 | done | |
| 39 | GET /holdings/coverage | app.py `h_holdings_coverage` | ✅ §5.19 | done | 四档+失效三类；**v8 新增 `no_proxy_count`/`penetrated_count`** |
| 40 | GET /holdings/risk | risk.py `risk_metrics` | ✅ §5.20 | done | 样本不足 null |
| 41 | GET /signals/state | fund_predict.py `signal_state` | ✅ §5.21 | done | 四要素+门卡 |
| 42 | GET /meta/definitions | fund_predict.py `definitions` | ✅ §5.22 | done | 结论指向 B |
| 43 | GET /ledger/chain | ledger_api.py `ledger_chain` | ✅ §5.34 | done | 6 步 |
| 44 | GET /ledger/shadow | ledger_api.py `shadow_ledger` | ✅ §5.28 | done | **v4 retention 三字段** |
| 45 | GET /engine/ddsm/cube | engine.py `build_cube` | ✅ §5.25 | done | **v4 双口径四字段** |
| 46 | GET /engine/training-status | engine.py `training_status_of` | ✅ §5.26 | done | 死路穷举 |
| 47 | GET /engine/arena | factor_board.py `arena` | ✅ §5.24 | done | **v4 color 两字段** |
| 48 | GET /engine/shadow-review | ledger_api.py `shadow_audit` | ✅ §5.29 | done | idle/ok/bad |
| 49 | GET /factors/score-detail | factor_board.py `score_detail` | ✅ §5.23 | done | |
| 50 | GET /factors/books/{book} | factor_board.py `book_detail` | ✅ §6.11.12 | done | records 键=schema_fields |
| 51 | GET /factors/governance-cycle | factor_board.py `governance_cycle` | ✅ §5.30 | done | 五阶段 |
| 52 | GET /factors/dig-records | factor_board.py `dig_records` | ✅ §6.11.14 | done | |
| 53 | GET /settings/holdings-data | app.py `h_settings_holdings_data` | ✅ §5.33 | done | readonly=true |
| 54 | POST /factors/candidates ★v7 | app.py `h_factors_candidate_submit`→`factor_engine.submit_candidate` | ✅ §5.36/§5.37/§6.8 | done | **202；提交定义+回测+记分卡；INSERT-ONLY** |
| 55 | GET /factors/candidates/{candidate_id} ★v7 | app.py `h_factors_candidate_get`→`factor_engine.get_scorecard` | ✅ §5.37/§6.8 | done | **include_windows；backtesting 骨架** |

> 路由表 `app.ROUTES` 共 **56** 条（55 接口 + `/health`），由 `test_app_contract` 断言。

### 5. 核心逻辑实现口径（可追溯）

- **触发门** `engine.gate_of`：E1 `low[t]>high[t-1]`；E3 `ret<-0.02 且 vr<0.8`。E2/E4 不实现、禁止 OR 合并（来源 Brief §5.1）。
- **DDSM** `engine.train_from_samples`：分位断点 20/40/60/80；加噪 `K=4`/`p=0.25` 副本**只进训练计数**（`ddsm`），出值用**真实档位**（`naive`/`ddsm_state`）；`ddsm_p=(n_up+10×train_rate)/(n+10)`；`naive_p` 仅 `n≥MIN_N=15` 给出否则 null。固定种子 `SEED=20260912`。
- **双否决** `engine.veto_status`：拥挤度六维按训练段 IC 符号等权复合 z，`≥60 分位` 否决；KLOW2 `≤40 分位` 否决；任一维缺失 → `missing`。
- **出口** `engine.EXIT_THRESHOLD=0.52`：`P>0.52` 且无否决且门触发 → `up`；任一否决层 `missing` → `abstain/veto_data_missing`；**无 down/做空分支**。
- **三窗口** `fund_predict._build_windows`：T1 `gate+ddsm+veto`（`brief_mandated`，p=DDSM P）；T3 `gate_only`（`pending_cv`，`p=null`）；T15 `gate+ddsm`（`pending_cv`，p=H15 DDSM，`direction=gray` + `provisional_*`）。
- **组合** `fund_predict.portfolio_forecast`：A/B 开口且 `p!=null` 按可信市值加权（**v4 冻结**）；门槛 `0.30/3` 未达强制 gray；C/D 进 `tier_excluded`；`excluded_ratio=1-coverage_ratio`。
- **估值五档** `valuation.value_fund`：official→intraday→holdings→proxy→unknown，命中即停记 `trace`；**v5 修复**：official 取「最近一期官方净值」，非 A 股盘中时段（`trade_session ∈ {pre_open,closed,non_trading_day}`）直接命中，仅 `trading` 才允许档2 `intraday`（非盘中该步 `tried=false`）；**v10**：按 `fund_type` 分流——主动基金 official 仅当日已发布才命中，否则 `holdings`（前十大重仓加权，优先于 proxy，前十不可得回退 proxy），指数联接/QDII 不做重仓加权；`unknown` 必 `change_rate=null`；置信度对照 `0.008`：`≤0.008 high / ≤0.012 mid / else low`；金额经 `Decimal`。
- **估值≠净值**：`valuation.public_valuation` 与 `valuation.nav_of` 独立；官方回填只写 `nav.*`，不改当日已入账 mode。**v5 修复**：`nav_of` 优先读实时官方净值缓存（`get_official_nav`），源文件 `nav_history` 仅回退。
- **INSERT-ONLY**：估值追加 `data/snapshot/valuation_history.jsonl`（`valuation.json` 仅缓存）；台账追加 `ledger/shadow_signals.jsonl`，回填独立 `ledger/backfill.jsonl`，`(date,code)` 唯一，`created_at==written_at`。
- **行情** `estimator.get_bars`：腾讯日K + `self_adjust`（>25% 跳变缩放历史 OHLC）；单源 5s 超时、重试 1。

### 6. 测试与实测证据（2026-09-12，Python 3.8.6 · 契约 v7）

- **单元/契约测试**：`cd <代码根>; python -m unittest discover -s tests -t .` → `Ran 117 tests ... OK`（0 失败 0 错误；v2 为 40，v3 新增 16 条，v4 新增 3 条，v5 新增 6 条，v6 新增 5 条，v7 新增 18 条，v8 新增 12 条，v9 新增 4 条，**v10 新增 13 条：`test_active_holdings_contract.py`——基金类型分类/QDII 优先、F10 前十解析（含 5 位港股码）、加权公式 Σ(w×chg)/Σw 与缺报价剔除、主动→holdings（trace 含明细）、前十不可得→回退 proxy、当日 official 优先、指数联接跳过重仓走 proxy、HoldingRow 暴露 `fund_type`**）。
- **起服**：`python app.py` → `GET /api/v1/runtime` 200，`port=8791`、`engine_status=online`、`as_of=2026-09-12`。
- **端点冒烟**：31 个只读 GET（含 `/engine/ddsm/cube?code=017193`、`/engine/arena`、`/ledger/shadow`、`/portfolio/forecast`）全部 `ok=true`。
- **v4 字段实测（回归保持）**：`cube.production_layer=ddsm / research_layer=naive / default_layer=ddsm / dual_view_note` 非空；`portfolio.weighting_basis=market_value`；`arena.color_scheme=performance_rank / color_token_prefix=--arena-`；`shadow.retention_policy=first_of_day_immutable_full_archive / first_of_day_immutable=true`；`frozen.weighting_basis=market_value`。
- **v5 字段实测（本轮新增）**：
  - `PUT /settings {llm:{base_url:"https://api.deepseek.com/v1"}}` → `GET /settings` 回读一致；非法值 `api.deepseek.com` → HTTP 400 `E_VALIDATION`；清除 `""` 后再读为 `""`。
  - `/predictions` 10 行行键含 `tier/market_value`，与 `/holdings` 同 code 值 **0 mismatch**；`/predictions/017193` 同字段 + `chain` 6 步。
  - `/engine/ddsm/cube?code=017193`：125 格，115 有样本（`status=filled`、`naive_p` 非 null、`naive_low_sample=true`），10 空格（两 P null、`color_band="no_sample"`、`naive_low_sample=true`）；`valid_coverage_naive_pct=0.92`（旧实现 0.0）。
  - `/engine/frozen-params`：`window_weights/window_min_days/license_lines` 元素键集合分别为 `{window,weight}`/`{window,n_w}`/`{license,min_independent_days,window_k}`；`license_lines.candidate.window_k=null`。
  - `/valuations/precision`：`groups[].label = 高,无`。
- **v4 覆盖口径实测（本轮新增）**：`python app.py`（8791）起服后 `GET /api/v1/holdings/summary` → `covered_count=10`、`total_count=22`、`covered_count < total_count=true`、`coverage_note="可信估值覆盖 10/22 只；无未知行按成本计"`、`today_pnl_amt=-290.25`（与修复前一致，证明只聚合可信行）。
- **v5 净值实时化实测（本轮新增，2026-09-12 周六 `trade_session=non_trading_day`）**：
  - `GET /api/v1/valuations`：`rows=22`，mode 分布 **official:22 / intraday:0 / unknown:0**；抽查 `nav_date`：`000217=2026-09-11`、`017193=2026-09-11`、`008087=2026-09-11`、`024239(QDII)=2026-09-10`（QDII 官方净值按惯例滞后一日；**均非 08-25**）。
  - `GET /api/v1/runtime`：`trade_session=non_trading_day`、`as_of=2026-09-12`、`staleness.latest_date=2026-09-11`、`days_behind=1`、`note="数据快照 2026-09-11"`（修复前 `08-25 / 18`）。
  - 抽样 `GET /api/v1/valuations/017193`：`valuation.valuation_mode=official`、`change_rate=-0.0394`、`nav_date=2026-09-11`、`trace=[{mode:official,tried:true,hit:true,reason:hit}]`、`trace_text="official 命中"`；`nav.official_nav_date=2026-09-11`。
  - `POST /api/v1/tasks {type:refresh_valuation}`：`status=done`、`result_summary="估值刷新 22/22"`（任务内强制批量抓取生效）。
  - 数据源：`FundValuationLast`（`NAV`=dwjz / `PDATE`=jzrq，批量 50/请求）+ `lsjz`（`DWJZ`/`FSRQ`/`JZZZL` 补官方日涨跌），单源 5s 超时/重试 1，`record_source("eastmoney", …)` 留痕；详见 §7 V4。
- **v6 影子盘回填实测（本轮新增，2026-09-12 · `python app.py` 8791）**：
  - `POST /api/v1/tasks {type:"backfill_ledger"}` → `status=done`、`result_summary="影子台账回填：窗口 20 日 / 200 条 / 2026-08-17~2026-09-11（新增 0，裁剪 0）"`。
  - `GET /api/v1/ledger?limit=1000`：`total=200`、`rows=200`、distinct 交易日 **20**、范围 **2026-08-17~2026-09-11**；`opened=true` **4** 条（否则如实 `opened=false` 196 条）；`gate` 分布 `none:179 / E1:16 / E3:5`；`signal` 分布 `gray:183 / abstain:13 / up:4`。
  - **幂等**：再次 `POST /tasks {type:"backfill_ledger"}` → `done`，`GET /ledger` total `200→200`（不翻倍、不重复写同日同码）。
  - `GET /factors/pans` adopted：`caps={"veto_max":4,"score_max":3}`、`factor_cap=null`、`rule_text` 含「否决位 ≤4 · 打分位 ≤3」；其余三盘 `caps=null` 且键存在。
  - `GET /review/reconciliation?limit=1000`：`total=200`（据台账实时派生）；`GET /ledger/shadow`：`summary={total_records:200, open_signals:4, veto_abstains:13}`、`archive_manifest_at=null`（窗口尚未滚动，如实为空）。
  - `GET /signals/state`：`last_open={date:2026-08-20, code:002963, gate:E1}`、`days_since_last_open=16`（修复前因默认分页 60 行而误报 `last_open=null`）。
- **v7 因子回测实测（本轮新增，2026-09-12 · `python app.py` 8791）**：
  - `GET /api/v1/factors/pans` adopted：`factor_count=2`；`klow2` 六窗 lift `1.3059/1.1459/1.1328/1.1075/1.0720/1.0720`、`total_score=61.05`、`license=probation`；`crowd6` lift `1.0000/0.9764/1.0746/1.0326/1.0113/1.0113`、`total_score=21.40`、`license=none`；两因子 `role=adopted`、`role_label=否决位`、`lift_bars` 均非 null（**真实回测，非 legacy 数字**）。
  - `POST /api/v1/factors/candidates`（mom5）→ 202 `status=done`，记分卡 `F1=pass / F2=pass(0.0723) / F3=fail(Δ=-0.0556)`、`verdict=rejected_f3`、`total_score=31.7`、`bootstrap_percentiles` 非空；重复提交 `duplicate=true` 同 `candidate_id`；`GET /factors/candidates/{id}` → `status=done` + 6 窗；`?include_windows=false` → `windows=null`。
  - `GET /api/v1/factors/score-chain`：`real_engine=true`、`bootstrap_percentiles_measured` 非空（取自 adopted 实测零分布）、契约字段 `bootstrap_percentiles` 保留常量。
  - 防前视：负 `shift`/负 `lag`/未声明列 → `E_VALIDATION`；单测「改未来 40 根 bar 后过去信号不变」通过；内置因子归一化（q40/六维 z）**每折只用 `[0,t-(H+2)]` 训练段**。
- **v8 覆盖度穿透实测（本轮新增，2026-09-12 · `python app.py` 8791）**：
  - `GET /api/v1/holdings/coverage`：`total_count=22`、`no_proxy_count=0`、`penetrated_count=2`；`tiers` = A **2**（weight 4.70%）/ B **13**（58.35%）/ C **7**（36.95%）/ D **0**（0.0%）——**D 由 12 只（54.55%）降到 0**。
  - `GET /api/v1/holdings`：22 行 `tier` 与设计一致（半导体/军工 A；黄金/纳指/通信/电力/有色/机器人/AI/消费电子/中证1000/科创创业50 B；A500/恒生/油气/CPO 近似 + 2 只穿透 C）；`025500`/`021528` 行含 `penetration_trace`（前十明细+加权篮子），其余行为 `null`。
  - 穿透缓存 `data/cache/proxy/penetration.json`：`025500`→`512480`、`021528`→`515880`，`report_date=2026-06-30`、`fetched_at=2026-09-12T13:01:23+08:00`、`status=待验证`。
  - 代理日线：15 个代理 ETF 全 `tencent_kline` **320 根**、最新 `2026-09-11`。
  - `GET /api/v1/runtime`：`port=8791`、`engine_status=online`、`as_of=2026-09-12`。
- **v9 影子盘状态接线实测（本轮新增，2026-09-12 · `python app.py` 8791）**：
  - 台账现状：`GET /api/v1/ledger` 实测 **320 行 / 20 个交易日 / 2026-08-17~2026-09-11**；`ledger_api.shadow_progress()` → `status=recording`、`consecutive_days=20`；`ledger_api.shadow_audit()` → `status=idle`（窗口内无 `up`+回填命中样本）。
  - `GET /api/v1/engine/status` → `shadow_status=**recording**`（修复前 `idle`）、`shadow_audit_status=**idle**`（新增，如实）、`shadow_consecutive_days=**20**`、`shadow_target_days=**60**`、`status=online`。
  - 新单测 `tests/test_shadow_status_contract.py` 4 条：有台账→`recording`/20 日、无台账→`not_started`/0 日、audit 与 progress 分离（gray→progress`recording`+audit`idle`）、全 up 且命中率 0.6 → audit `ok` 而 `shadow_status` 仍 `recording`。
- **v10 主动基金重仓加权实测（本轮新增，2026-09-12 周六 `trade_session=non_trading_day`，`python app.py` 8791）**：
  - `GET /api/v1/valuations` mode 分布：**before `official:22` → after `holdings:5 / official:17`**；5 只主动（`025500/018957/021528/013566/014320`）全部 `holdings`（`mode_label=重仓加权`），指数联接/QDII 维持官方口径。
  - 盘中模拟（`session=trading`、`as_of=2026-09-14`）：**before `proxy:11/intraday:11` → after `holdings:5/intraday:11/proxy:6`**；主动 5 → `holdings`、指数联接 11 → `intraday`、QDII 6 → `proxy`（**主动不再出现在 `proxy` 中**）。
  - `GET /api/v1/valuations/014320`：`holdings` + `trace.detail` 前十 10 行、`covered_weight_pct=45.57`、`weighted_change=-0.0229`、`base_nav=2.5664`、`estimated_nav=2.5077`（Σ贡献校验通过）。
  - `GET /api/v1/holdings`：22 行含 `fund_type/fund_type_label`（active 5 / index_link 11 / qdii 6）。
  - `GET /api/v1/runtime`：`trade_session=non_trading_day`、`as_of=2026-09-12`、`port=8791`、`engine_status=online`。
  - 新单测 `tests/test_active_holdings_contract.py` 13 条全绿。
- **负向**：`validate_task_payload` 传 `weighting_basis/min_coverage_ratio/min_open_count` → `E_VALIDATION`（测试）；台账同日同 code → `E_CONFLICT`、回填无 signal → `E_VALIDATION`（测试）；无台账删改路由（测试）。

### 7. 偏差与口径解释（不静默；需架构师/产品裁定）

> **v10 新增契约同步项（task OC-HOLDVAL-BE，字段只加不改，需 architect 升契约版本）**：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V18 | §5.1 `HoldingRow` / §5.2 `Valuation`（原字段无基金类型） | **新增** `fund_type`(enum `active/index_link/qdii/other`) 与 `fund_type_label`(string)；`trace[holdings].detail` 承载前十加权过程（`{method,formula,report_date,top10[{rank,stock_code,stock_name,weight_pct,day_change,contribution,used}],covered_weight_pct,total_weight_pct,weighted_change,base_nav,base_nav_date,estimated_nav}`）。**未改/未删任何既有字段名**（`valuation_mode` 仍含 `holdings`，`mode_label` 仍「重仓加权」） | **纯新增字段 + 既有 `holdings` 档实装**（此前该档形同虚设，从未真正抓取） | 请 architect 在 §5.1/§5.2 补 `fund_type`/`fund_type_label` 与 `TraceStep.detail`；确认 `fund_type` 枚举与「主动基金 official 仅当日已发布才命中、否则重仓加权」的分流口径 |

> **v9 新增契约同步项（task OC-SHADOWSTAT-BE，字段只加不改，需 architect 升契约版本）**：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V17 | §6.9 `/engine/status.shadow_status`（枚举 `shadow_review_status` = `idle/ok/bad`，注「影子盘三态」） | **字段改名实为语义切换**：`shadow_status` 现输出**进度枚举** `not_started/recording/qualified/gap`（= §5.28 `/ledger/shadow.progress.status` 的同一枚举），原 `idle/ok/bad` 偏差评估迁至**新增** `shadow_audit_status`（`idle/ok/bad`）。既有键名未删，新增 1 键 | **枚举语义迁移 + 纯新增字段**（用户 2026-09-12 诉求「有记录不应显示未启动」；进度与审查是两回事） | 请 architect 在 §6.9 把 `shadow_status` 枚举改为 `shadow_progress_status`，并补 `shadow_audit_status`(enum `shadow_review_status`)；前端 HUD「影子盘」状态字须改读 `shadow_status` 的**进度枚举**（现状 `static/js/views/engine.js` 仍按 `idle/ok/bad` 映射，属前端契约同步项，**本轮未改 `static/**`**） |

> **v8 新增契约同步项（task OC-COV-BE，字段只加不改，需 architect 升契约版本）**：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V14 | §5.1 `HoldingRow`（原字段止于 `staleness`） | 每行**新增** `penetration_trace`(object/null)：主动基金持仓穿透记录 `{method, source, report_date, top10[], basket[], mapped_weight_pct, unmapped[], proxy, proxy_basis, confidence, status}`；无穿透为 `null` | **纯新增字段**（未改/未删既有字段名） | 请 architect 在 §5.1 补 `penetration_trace`（或收编为独立共享对象） |
| V15 | §5.19 `CoveragePanel`（原 6 字段） | **新增** `no_proxy_count`(int) 无代理只数、`penetrated_count`(int) 经穿透补全只数 | **纯新增字段** | 请 architect 在 §5.19 补两计数键 |
| V16 | §5.1 `tier`/`proxy_code` 语义 | 本次把 `holdings.PROXY_MAP` 从 10 只扩到 **20 只静态 + 2 只穿透**；`tier` 由 A=10/D=12 重分为 A=2/B=13/C=7/D=0（**销 v2 偏差 D2**）。C 档 `proxy_code` 非 null（拟用/穿透代理），仅 D 档为 null，与 §5.1 注「D 档为 null」一致 | **配置口径落地**（非字段/类型变更） | 请 architect 确认 A/B/C 分类与「C 档可带 `proxy_code`」口径；穿透主代理一律「待验证」 |

> **v7 新增偏差与口径裁定（task OC-FACTOR-BE；均为「机制文本歧义」或「只加不改」，需 architect 收口）**：

| # | 契约/机制来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V7 | 机制 §3.3「基线必须按独立触发日、在同一测试日集合上计算」 | 基线按**窗口内去重叠的全测试日集**（不限定触发日）算 `max(恒涨,恒跌)`；`hit_rate` 才按独立触发日 | **口径裁定**：若基线也限定在触发日，则 `baseline=max(P(涨),P(跌)|触发)` 恒 ≥ `hit_rate`，`lift≤1` 恒成立，评分链失去意义（标准 lift 需条件 vs 无条件） | 请 architect 明确 §3.3 措辞为「同一测试**窗**全测试日集」；若确为触发日口径，则评分链需重设计 |
| V8 | 机制 §2.4「命中 = 到期上涨，永不做空」+ §1.2「higher_bearish 回测取负」 | `hit=fwd>0` 恒成立；`orientation` 只决定触发方向（`higher_bearish` 在低值触发）；否决层 lift 读作「亮灯日上涨率÷基线」 | **口径裁定**：否决层（veto）语义与通用方向因子不同名不同义 | 请 architect 裁定否决层是否应评估「放行日（未亮灯）」口径；本实现按字面机制落地并如实报数 |
| V9 | §5.36「`role_hint=veto` 时 `veto_threshold` 必填」 | `kind=binary_signal` 时阈值由布尔表达式承载，允许 `veto_threshold=null`（仅 `kind=score` 强制必填） | **校验放宽**（避免与表达式重复定义阈值） | 请 architect 在 §5.36 补「binary_signal 免填」 |
| V10 | §6.8 `POST` 成功 `status` 恒 `backtesting`（异步） | 本实现回测为 CPU 秒级纯本地任务，**同步完成**：`data.status=done` 且内联 `data.scorecard`（6 个契约字段仍在，另加只读字段） | **新增内联字段 + 状态取值**（枚举 `candidate_status` 含 `done`，未改名） | 请 architect 确认「同步返回 done 内联记分卡」可接受；若不接受，改为建 task 异步 |
| V11 | §6.8 `score-chain.bootstrap_percentiles` 契约固定常量 | 保留常量，**新增** `bootstrap_percentiles_measured`（实测零分布）与 `real_engine=true` | **纯新增字段**（R3：真实引擎产出后须替换；此处以兄弟字段并存，避免改契约既有键） | 请 architect 决定是否将 `bootstrap_percentiles` 直接替换为实测值并升版本 |
| V12 | §5.35/§7.3 盘位与 `factor_id` 未规定引擎在用因子的 id | 两内置因子 id 定为 `klow2` / `crowd6`（8 位内），`_builtin` 标记只存于内存定义、不落磁盘；adopted 记录不含 `_builtin` | **命名约定新增** | 请 architect 在机制 §9.3 登记内置因子 id |
| V13 | R4 因子账本路径（`06-system-arch` 写 `data/factors/`） | 统一落 `ledger/factor_candidates.jsonl`、`ledger/scorecards.jsonl`、`ledger/scan_history.jsonl`、`ledger/factor_arena.jsonl`；复用信号缓存 `data/cache/factor/signals.json` | **路径收口**（与 `factor_board` 读取一致，机制 §11 R4 授权 backend 统一） | 请 architect 确认 R4 收口方向 |

> **v6 新增契约同步项（task OC-SHADOW-BE，字段只加不改，需 architect 升契约版本）**：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V5 | §5.9 / §5.28 台账 `signal_record` 字段集（原 12 字段，无 `opened`） | 台账行**新增** `opened`(bool) = T1 是否开口（`signal=="up"`）；`FIELD_LIST` 追加，旧行读取时按 `signal` 派生 | **纯新增字段**（未改/未删既有字段名） | 请 architect 在 `09-api-contract` 台账 schema 补 `opened`；`/factors/books` 的 `shadow_signals.schema_fields` 随 `FIELD_LIST` 同步 |
| V6 | §5.11 四盘 schema（原 `factor_cap` 单值；正式盘旧值 `3`） | 各盘**新增** `caps` 键：adopted `{"veto_max":4,"score_max":3}`、其余 `null`；adopted `factor_cap` 置 `null`（去误导）；`rule_text` 明确「否决位 ≤4 · 打分位 ≤3」 | **新增键 + 一处既有键取值改 null**（用户 2026-09-12 更正真实规则） | 请 architect 在 `09-api-contract` 四盘 schema 增 `caps`，并确认 `factor_cap` 废弃/保留；前端「上限」须改读 `caps.veto_max/caps.score_max`，不得再读 `factor_cap=3` |

> **v5 新增偏差（task OC-DATA-BE2）**：

| # | 派发/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V4 | 派发指定数据源 `https://fundgz.1234567.com.cn/js/<code>.js`（JSONP，含 `dwjz`/`jzrq`） | 实测该地址 HTTP 200 但返回 404 错误页（旧 JSONP 已于 2026-07-21 下线，见 `estimator.py` 顶部注释）；改用同语义 `FundValuationLast`（`NAV`≡dwjz、`PDATE`≡jzrq）+ `lsjz`（`DWJZ`/`FSRQ`/`JZZZL`）作为官方净值与官方日涨跌来源 | **数据源替换，非需求变更**（fundgz 已不可用） | 请 architect/主 Agent 知悉：官方净值以天天基金 `FundValuationLast` 为准；如需其他源请另立数据源卡 |

> **v3 新增偏差**（本轮实现中发现，均为「实现未对齐契约」或既有缺陷，非需求变更）：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| V1 | §5.14 `license_lines` 元素 `{license,min_independent_days,window_k}`（v5 冻结） | 原实现 `candidate` 元素为 `{license,min_independent_days,note}`，缺 `window_k` | 与 v5 键名冻结冲突（裁定书 §3.1 假设「无需改代码」与实际不符） | 已按 v5 修正为 `window_k:null`（`note` 移除）；请 dev-lead 复核 |
| V2 | §6.10 `base_url` 校验（v5） | 仅对已知键 `base_url` 实现落盘与校验；其余未知 `llm.*` 键仍按原样静默忽略 | 未越权收紧请求体（新增未知键拒绝可能误伤前端扩展） | 如契约要求「未知键一律报错」，请 architect 明确后另轮实现 |
| V3 | §6.2.1 `covered_count`（v5：`market_value != null` 的只数，注「非按 `change_rate`，官方回填行也算」） | 按 PRD F-01 验收②改为 `change_rate != null`（可信估值）计数；`market_value != null` 的 nav 回填 unknown 行不再计入 | 实现与契约 v5 文字冲突，但与 PRD F-01 + 09-api-contract-v1 §475 原口径一致（终验 P1 要求如此） | 请 architect 将 §6.2.1 同步回 v1 口径并升契约版本；`total_value` 等资产字段保持 `market_value` 口径不变 |

> **v2 偏差（保持登记，本轮未改）**：

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| D1 | §1.4 默认端口 8787 | 实际 8791，`/runtime.port` 回传 8791 | 派发指定 OpenCode 版固定口 | 确认 8791 |
| D2 | 代理映射未在契约冻结 | `holdings.PROXY_MAP` 10 只指数/黄金联接记 A；12 只 QDII/主动记 D | 实现配置假设 | architect 复核后升 B/C |
| D3 | §5.33 `legacy_path` | 取同目录 `funds_data.json.bak` | 旧位置精确路径未给出 | 确认 legacy 路径定义 |
| D4 | §5.2 MAE/方向命中率 | proxy 档按 nav_history 与代理日线重叠样本算（小样本，其余 mode null） | 真实小样本非估计 | 40 日回测产出后回填 |
| D5 | §4.5 vs A-05 顺序 | 门未触发优先 `gray/gate_not_triggered`；门触发后否决 missing → `abstain` | 口径解释 | architect 确认优先级 |
| D6 | §5.7 T15 `p` 与「未验证不进组合」 | `WindowResult.p` 给 DDSM P，但组合 `weighted_p=null` | 按 §5.7 尾注 | 无需改 |
| D7 | §6.2 `import.merge` 语义 | 按 `code` 合并（新覆盖旧），默认 `replace` | 契约自身登记 CONCERN | 本期 UI 只用 replace |
| D8 | §9.3 因子治理数值 | 六本账本/竞技场/治理未产出时返回空集/null；常量文本来自 PRD F-14 + Brief §9 | 遵守残留风险 9，禁 legacy 数字冒充 | 因子引擎产出后回填 |
| D9 | §3.1 holdings 档 | 未实现重仓页抓取（HTML 脆弱）→ trace `tried=true/hit=false/reason=no_report` | 诚实降级 | 后续可否补抓取 |
| V0 | `settings._load_raw` 默认值浅拷贝 | 默认分支返回 `dict(DEFAULT_SETTINGS)`，就地写入会跨调用污染模块级默认（测试暴露） | 既有缺陷（非本轮引入） | 已改 `copy.deepcopy`；请 dev-lead 复核 |

> A-10 的**归档轮转动作**（复制历史行到 `ledger/archive/YYYYMM.jsonl` 并截断主文件）尚未由定时器驱动；字段与主文件保留策略已就位，`archive_manifest_at` 在未归档时返回 null。轮转阈值见 08 §残留风险 10（backend-dev，S3）。
> **立方体对比卡口径注**：`comparison.valid_coverage_ddsm_pct` 按 `model["ddsm"]` 现有键计，与逐格 `ddsm_p`（empty 时 null）口径不同，v5 判定式下仍为 1.0；此为既有统计定义（本轮未改），如前端需与逐格一致请 architect 裁定。

## 自验收

- [x] 契约中每个接口都已实现，无遗漏（55/55 + /health；v7 增 `POST/GET /factors/candidates`）
- [x] 逐字段比对：字段名 snake_case、类型、单位、精度、枚举一致（§4；v5 追加字段见 §0）
- [x] **v5 五项裁定逐条落字段级并断言**（BLOCK-2/SHOULD-1/4/5/缺口4；§0 表）
- [x] 每个接口的 4xx/5xx 分支可构造并验证（`E_VALIDATION`/`E_NOT_FOUND`/`E_CONFLICT`/`E_ENGINE_OFFLINE`）
- [x] 所有边界情况已处理（除零/空/NaN/缺失/超时；外部源 5s 超时 + 重试 1；base_url 空串合法）
- [x] 业务口径在代码注释中标注 PRD/契约来源
- [x] 无"看起来对"的兜底数字；缺失一律显式 null/空集（unknown 必 change_rate=null；empty 格两 P 均 null；孤儿预测行 tier/mv=null）
- [x] 服务可独立启动（`python app.py`，8791；附 `/health`、`/runtime`）
- [x] 所有偏差已列出，无静默修改（§7：v6 新增 V5/V6 + v5 V4 + v3 V0/V1/V2 + v2 九项 D1~D9）
- [x] 台账 INSERT-ONLY、回填独立文件、`(date,code)` 唯一、`created_at==written_at`
- [x] **F-PM-01(P1)** `covered_count` 按可信估值（`change_rate != null`）计数，存在 unknown 行时 `< total_count`（实测 10/22）；`coverage_note` 与之同步
- [x] **OC-DATA-BE2 净值实时化**：非交易日/收盘后 `official` 命中且 `nav_date=` 最近一期官方净值（实测 22/22 official；抽查 2026-09-11，QDII 09-10；**非 08-25**），周末/收盘后不产出 `intraday`（非盘中该步 `tried=false`）
- [x] **OC-DATA-BE2 staleness**：`/runtime.staleness.latest_date=2026-09-11`、`days_behind=1`（修复前 08-25 / 18），`nav_of` 同步取实时缓存
- [x] **OC-DATA-BE2 触发抓取**：`_warmup` 与 `refresh_valuation` 任务内强制批量抓取（测试 + `POST /tasks` 实测 `done 22/22`）；外部源 5s 超时/重试 1/TTL 缓存；字段名未改（`trace.reason` 仍属冻结枚举）
- [x] **OC-SHADOW-BE 影子盘 20 交易日滚动回填**：真实引擎（走前 purge=H+2）逐日产出，`/ledger` 实测 **200 条 / 20 交易日 / 2026-08-17~2026-09-11**，无开口日如实 `opened=false`（196/200），**无示例数字**；重复触发幂等（200→200）；窗口滚动时裁剪最旧一天并全量归档（单测覆盖 `written=2/trimmed=2`）
- [x] **OC-SHADOW-BE 因子上限口径**：`/factors/pans` adopted `caps={veto_max:4,score_max:3}`、`rule_text`「否决位 ≤4 · 打分位 ≤3」、误导性 `factor_cap` 置 null（§0d、§7 V6）
- [x] **OC-SHADOW-BE 新增字段只加不改**：台账 `opened`(bool) 新增；`opened` 已入 `FIELD_LIST`；契约同步项 V5/V6 已登记（§7）
- [x] **OC-SHADOW-BE 信号时间线取真实数据**：`/signals/state.last_open={date:2026-08-20, code:002963, gate:E1}`（修复前因默认分页误报 null）
- [x] **OC-FACTOR-BE 回测器深度模块**：`factor_engine.evaluate` 唯一接口；六窗走前 CV（禁随机切分）、purge=H+2、holdout 60 日不入评分；基线 `max(恒涨,恒跌)`；k_lift 五档悬崖边界单测全过；窗权重 `8/22/15/10/30/15`；准入度 `min(1,独立触发日/N_w)`（N_w=5/10/30/15/60/120 对应六窗）；总分=Σ(k_lift×权重×准入度)
- [x] **OC-FACTOR-BE 真回测填盘（R7）**：`ledger/adopted_factors.json` 落 `klow2`/`crowd6`，六窗 lift 与总分均来自真实数据回测（KLOW2 总分 **61.05**、crowd6 **21.40**），**无 legacy 示例数字**；样本不足/不可算一律 `null`
- [x] **OC-FACTOR-BE 新因子接口**：`POST /factors/candidates`（校验→INSERT-ONLY 候选账本→回测→记分卡→scan_history/factor_arena 留痕→202）与 `GET /factors/candidates/{id}`（`include_windows`）；F1/F2/F3 与盘位判定落地；同 `definition_hash` 幂等
- [x] **OC-FACTOR-BE 防前视**：因子=只依赖「截至某日」数据的 AST；负 `shift`/负 `lag`/未声明列提交即拒；归一化每折只用训练段；单测「改未来 bar 不改过去信号」通过
- [x] **OC-FACTOR-BE bootstrap**：500 次打乱得真实零分布分位（Scorecard `bootstrap_percentiles`/`total_score_percentile`）；score-chain 以新增兄弟字段承载实测值
- [x] **OC-COV-BE 完整映射 22/22**：`proxy_map.PROXY_MAP` 覆盖 20 只静态 + 2 只穿透；静态分档 A=2/B=13/C=5；未知码 `resolve`→D 且 `proxy_code=null`（单测）
- [x] **OC-COV-BE 持仓穿透**：`025500`/`021528` 抓东财 F10 前十→个股→行业 ETF 加权；主代理 `512480`/`515880`，`penetration_trace` 含前十明细+篮子，标注「待验证」；穿透不到/空前十仍留 D（单测覆盖）
- [x] **OC-COV-BE D 档显著下降（自证 before/after）**：`A10/B0/C0/D12`（D 54.55%）→ **`A2/B13/C7/D0`（D 0%）**；`/holdings/coverage` `no_proxy_count=0`、`penetrated_count=2`（§0f/§6 实测）
- [x] **OC-COV-BE 无编造代理**：`sync_proxy_fields` 仅按映射/穿透缓存重算，不联网、不生成假代理；网络失败保留旧缓存并留 D
- [x] **OC-SHADOWSTAT-BE 影子盘状态接线**：`shadow_status` 改进度语义（`not_started/recording/qualified/gap`），有台账即为 `recording`（实测 20 日不再显示未启动）；偏差评估独立为新增 `shadow_audit_status`（`idle/ok/bad`）；`shadow_consecutive_days=20`/`shadow_target_days=60`；既有字段名只加不改（§0g/§7 V17）
- [x] **OC-HOLDVAL-BE 基金类型分类**：`estimator.classify_fund_type` 落 `fund_type` 到持仓/`Valuation`/`HoldingRow`（active 5 / index_link 11 / qdii 6 / other 0）；QDII 优先于「混合」；字段只加不改（§0h/§7 V18）
- [x] **OC-HOLDVAL-BE 主动基金重仓加权（自证 before/after）**：主动基金估值锚点 = 前十大重仓股加权（`Σ(w_i×chg_i)/Σw_i`，优先于 proxy，前十不可得回退 proxy）；实测 `/valuations` **before official:22 → after holdings:5/official:17**；盘中模拟 **before proxy:11/intraday:11 → after holdings:5/intraday:11/proxy:6**（主动不再出现 `proxy`）
- [x] **OC-HOLDVAL-BE 样例 trace**：`014320` `trace[holdings].detail` 含前十 10 行 + `covered_weight_pct/total_weight_pct/weighted_change/base_nav/estimated_nav`；校验 Σ贡献/covered=−0.0229、2.5664×(1−0.0229)=2.5077
- [x] **OC-HOLDVAL-BE 指数联接/QDII 不受影响**：`holdings tried=false`，维持 `official/intraday/proxy`（盘中模拟 11 只指数联接 → `intraday`、6 只 QDII → `proxy`）
- [x] **OC-HOLDVAL-BE 诚实性**：个股报价缺失/港股码 → `day_change=null used=false`（不编造）；前十不可得 → `no_report` 回退 proxy；外部 5s 超时、纯标准库
- [x] 纯 Python 标准库；Python 3.8.6 实测可起服；**117/117** 契约测试全绿（v8 为 100，v9 新增 `test_shadow_status_contract.py` 4 条，v10 新增 `test_active_holdings_contract.py` 13 条）

## 下游交接

- **主消费方 `dev-lead`**：按 G-BE-01 冒烟（起服 + `/holdings` + 一条估值 + 一条预测 + 立方体/竞技场/影子盘 + v4 双口径 + **v5 五处** + **v4 §0b F-PM-01** + **v5 §0c 净值实时化** + **v6 §0d 影子盘 20 日回填 / caps / opened** + **v7 §0e 因子回测器 / 真回测填盘 / 候选两接口** + **v8 §0f 覆盖度穿透：`/holdings/coverage` 分档 A2/B13/C7/D0、`/holdings` 行 `penetration_trace`**）与 G-BE-02 逐字段核对（对照 §0/§0b/§0c/§0d/§0e/§0f/§4/§7，法律为契约 v7）；重点复核 V1/V3/V4/V5/V6、**v8 V14~V16（`penetration_trace`、`no_proxy_count`/`penetrated_count`、A/B/C 分类与 C 档带代理）**、**v9 V17（`shadow_status` 改进度语义 + 新增 `shadow_audit_status`）** 与 **v10 V18（`fund_type`/`fund_type_label`、`trace[holdings].detail`、主动基金估值锚点 = 重仓加权：`/valuations` before official:22 → after holdings:5/official:17）**。
- **抄送 `frontend-dev`**：**v10 本轮（字段只加不改，前端可直接读）**——`/holdings` 行与 `/valuations`（及 `/holdings/{code}`）的 `valuation` 新增 `fund_type`/`fund_type_label`（`active=主动/index_link=指数联接/qdii=QDII/other=其他`），可用于标注基金类型；主动基金 `valuation_mode` 现为 `holdings`（`mode_label=重仓加权`），徽章按既有 `valuation_mode` 映射渲染即可（无需硬编码），如需展示加权依据读 `valuation.trace[holdings].detail`（前十明细/covered 权重/weighted_change/base_nav）。`mode_label`/`source_label` 文案未变（「重仓加权」/「前十大重仓加权」）。**v9 本轮（需前端同步，后端未改 `static/**`）**——`/engine/status` 的 `shadow_status` **取值域已变为进度枚举** `not_started/recording/qualified/gap`，HUD「影子盘」状态字须按此枚举渲染（`recording=记录中 / qualified=已达标 / gap=有漏单 / not_started=未启动`），**不得再用 `idle/ok/bad` 映射**（现状 `static/js/views/engine.js` 的 `SHADOW_STATUS_TAG` 会再次出现「—」）；偏差评估迁至**新增**字段 `shadow_audit_status`（`idle/ok/bad`），如仍要展示「达标/降级」请改读该字段。**v8**——`/holdings` 行新增 `penetration_trace`(object/null)，可在穿透行展示「前十穿透→主代理（待验证）」详情；`/holdings/coverage` 新增 `no_proxy_count`/`penetrated_count`；`tier` 语义不变（D 含义不变，本期实测 D=0），既有渲染无需改。v5 收口四处——`Settings.llm.base_url` 直读/直写；预测表直读 `rows[].tier/market_value`（删 `/holdings` 拼装）；立方体研究层低样本角标读 `naive_low_sample`（`naive_p` 现在有值，勿再整片判无样本）；`.vsum` 读 `groups[].label`。**v6 本轮**：因子正式盘「上限」改读 `pans[role=adopted].caps`（`veto_max=4` / `score_max=3`），**禁止再读 `factor_cap`（已置 null）**；影子台账行新增 `opened`(bool) 可直接用于开口标；信号时间线 `last_open` 现在为真实值（2026-08-20），不得因 `t1_real=null` 而隐藏。**v5 保持**：`ValBadge` 在非盘中将普遍显示「官方净值」徽章、`nav_date=2026-09-11`（QDII 09-10），前端不得按 `is_today_official` 判空或隐藏。
- **次消费方 `qa`**：**v10 本轮**——5 只主动基金（`025500/018957/021528/013566/014320`）`valuation_mode` 必须为 `holdings`、`trace` 末步 `holdings hit=true` 且 `detail.top10` 非空；`estimated_nav` 必须 = `detail.base_nav × (1+detail.weighted_change)`；`change_rate` 必须 = `Σ(detail.top10[].contribution)/detail.covered_weight_pct`；`day_change=null` 的标的必须 `used=false` 且不计入 `covered_weight_pct`；指数联接/QDII 行的 `trace` 中 `holdings` 必须 `tried=false`（不得做重仓加权）；`fund_type` 必须与名称分类一致（QDII/指数联接优先于「混合」）。v5 负向——`base_url` 非法值必须 `E_VALIDATION`、未配置回 `""` 非 null；empty 格仍不得渲染 0/50%；`naive_low_sample=true` 格须叠加「低样本·仅供审计」且不得当可信估计；`/predictions` 与 `/holdings` 同 code 的 `tier/market_value` 必须一致。**v6 本轮**：`POST /tasks {type:"backfill_ledger"}` 两次后 `/ledger` total 不得翻倍（幂等）；`/ledger` 行须含 `opened` 且与 `signal=="up"` 一致；`/factors/pans` adopted 必须 `caps={veto_max:4,score_max:3}`；无开口日须如实 `gate=none / opened=false`，不得出现示例数字。**v5 保持**：周末/收盘后 `/valuations` 不得出现 `intraday`；`nav_date` 必须是最新官方净值日（非 `2026-08-25`）；`/runtime.staleness.latest_date` 与实际抓取值一致。**v7 本轮**：未声明列/负 `shift`/负 `lag`/未知 op/空 `params.grid` 必须 `E_VALIDATION` 且 `error.detail` 给字段级原因；同 `definition_hash` 重复提交必须幂等（同 `candidate_id`、`duplicate=true`）；未知 `candidate_id` 必须 `E_NOT_FOUND`；`GET ...?include_windows=false` 必须 `windows=null`；六窗 `lift` 无独立触发日必须 `null`（禁估填）；`frozen_config_hash` 变化后旧记分卡不可比；`/factors/pans` adopted 的六窗 lift 不得为 legacy 常量。**v9 本轮**：有台账时 `/engine/status.shadow_status` 必须 ∈ `{recording,qualified,gap}`（**不得为 `idle`**）、`shadow_audit_status` 必须 ∈ `{idle,ok,bad}` 且两字段并存；`shadow_consecutive_days` 必须等于台账连续交易日数（当前 20）。
- **残留风险（含责任人与期限）**：
  1. V1 `license_lines` 键名修正（backend-dev，本轮已落，dev-lead 复核）。
  2. V2 未知 `llm.*` 键静默忽略策略待 architect 明确（architect，S4 收口）。
  3. 立方体对比卡 `valid_coverage_ddsm_pct` 与逐格口径不一致（architect，S4 收口）。
  4. **（已销）代理映射未验证（D2）**：v8 已扩到 22/22 完整映射并做 2 只主动基金持仓穿透（D 12→0）；**映射本身为产品领域配置、穿透结果标「待验证」**，是否将 A/B/C 分类与穿透主代理写入契约由 architect 收口（V16）。
  5. proxy MAE/方向命中率小样本（D4）→ 40 日回测产出后回填（backend-dev，S3）。
  6. `self_adjust` >25% 阈值未用真实除权案例验证；volume 未同步缩放（backend-dev，S3）。
  7. **（已销）holding 档未抓重仓（D9）**：v10 已实装 F10 前十抓取 + 个股实时，主动基金重仓加权落地（实测 5/5 `holdings`）；残留：`014320` 第十大含港股 `01347` 无 A 股实时报价（`day_change=null` 如实剔除，covered 45.57%）；如需覆盖港股需另立数据源卡（architect，可选）。
  8. T+3/T+15 `validation_status=pending_cv`、`direction=gray` 待真实 CV+placebo 升格（architect，S3 回测后）。
  9. 因子六本账本/竞技场/治理数值待引擎产出（architect + backend-dev，S3）。
  10. A-10 归档轮转阈值未定，定时驱动未接（backend-dev，S3）。
  11. `legacy_path` 与 `import.merge` 语义待契约确认（architect，S3 前）。
  12. V3 `covered_count` 已按 PRD F-01 改为可信估值口径，契约 §6.2.1 文字待同步（architect，S4 收口）。
  13. 数据源 `fundgz` 已下线（V4），官方净值依赖天天基金 `FundValuationLast`/`lsjz` 可用性；两接口长期不可用时回落源文件 `nav_history`（08-25 滞后）并已 `record_source` 留痕（backend-dev，长期）。
  14. `trade_session` 未纳入法定节假日日历（仅按周末 + 时段判定）：法定节假日若落在工作日 09:30-15:00，会被判为 `trading` 而尝试 intraday（周末场景已修复，本轮实测通过）。如需精确排除节假日需引入交易日历（architect 裁定是否本期纳入）。
  15. **V5/V6 契约同步**：台账新增 `opened`、四盘新增 `caps` 且 adopted `factor_cap` 置 null，需 architect 升 `09-api-contract` 版本并同步四盘/台账 schema（architect，S4 收口）。
  16. **（已销）六窗 lift 空**：`ledger/adopted_factors.json` 已由真实回测填入 `klow2`/`crowd6`（见 §0e）；`/factors/pans` `lift_bars` 非 null（KLOW2 总分 61.05 / crowd6 21.40）。
  17. **v7 口径待架构师裁定**：V7（基线测试日集）、V8（否决层 hit 语义）、V9（binary_signal 免 `veto_threshold`）、V10（POST 同步返回 `done` + 内联记分卡）、V11（bootstrap 兄弟字段是否转正）、V12（内置因子 id）、V13（因子账本路径收口）——均已在 §7 登记，**不阻塞** `/factors/*` 读取（相关字段只加不改、不可算为 null）。
  18. **holdout 与 placebo 未对候选执行**：机制 §2.6/§2.7 的 placebo 95 分位与冻结留出仅在「通过 F1/F2/F3 且申请晋升」时评估；本实现 `holdout=null`、`placebo_delta_pp=null`，`total_score_percentile` 由 bootstrap 零分布给出（architect 确认是否本期补 placebo 独立对照）。
  19. **V17 契约与前端同步（architect + frontend-dev，S4 收口）**：`/engine/status.shadow_status` 枚举已从 `idle/ok/bad` 迁为进度枚举 `not_started/recording/qualified/gap`，偏差评估迁至新增 `shadow_audit_status`；契约 §6.9 需同步，前端 HUD 映射需改（后端本轮未动 `static/**`，**前端不改则 HUD 影子盘状态字可能再次显示「—」**）。
  20. **holdings 档 confidence 暂无回测**：`build_accuracy` 本期仍只回测 `proxy` 档；`holdings` 无 `(mode, code)` MAE → `confidence=unknown`（不估填）。重仓加权 MAE 回测需历史前十权重 + 个股日线（数据成本较高），建议 architect 裁定是否纳入 40 日回测（architect + backend-dev，S4/S5）。
- **未覆盖**：前端组件与四态（`07-frontend-arch`/`03-ui-design`）、桌面 exe 打包（S5）。
