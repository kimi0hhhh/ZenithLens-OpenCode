---
artifact: 09-api-contract-r2
owner: architect
version: v9.5
status: draft
supersedes: 09-api-contract.md（R1 基线内部 v8）
created: 2026-09-12
reviewers: [product-manager]
gate: G-AR-05
---

# 接口契约 · 极境 ZenithLens（R2 升级轮增量 · v9.5）

> 本文件是 `09-api-contract.md`（内部 v8，已 approved）的 **R2 升级轮增量**：只增补/变更 R2 相关条目，**未重排、未重写全文**；未变条目一律**沿用 v8**（引用优先于复制，本文不重抄）。
> 读取顺序：§1 总览 → §2 全局增量 → §3 对象增量 → §4 端点增量 → §5 销项 → §6 可复算口径 → §7 机器核对表 → §8 未变声明 → §9 v9.1 清单 → §10 v9.2 注记 → §11 v9.3 注记 → §12 v9.4 注记 → §13 v9.5 注记。
> 上游：`00-charter/01-requirements-v3.md` / `02-prd-v3.md` / `03-ui-design-v3.md` / `00-dissection-v3.md`；实现现状依据：`03-backend/14-api-impl-report.md`（v10）与代码实测。
> 纪律：字段名一律 `snake_case`；每个新/变字段给**类型 + 单位 + 精度 + 口径**；枚举穷举；时间格式与时区沿用 v8 §1.1。
> **不变式**：v9 未修改/未删除任何既有**字段名**；唯一的取值域变更（`shadow_status`）按 V17 收口并在此显式登记；`PortfolioForecast` / `StateCube` / `ArenaMatrix` / 因子族对象零变更（§8）。
> **v9.1（2026-09-12 · 会签收敛轮）**：按 PM 挑刺 `10-arch-review-pm-r2.md`（D-1..D-4 / R-1..R-5 / N-1..N-4）收敛——**新增 9 / 变更 4 / 注记 2**，逐条见 §9；收敛纪要（双方立场/结论/影响工件）见 `10-arch-review-r2.md` v2 §1/§4。V9.1 未改任何既有字段名；`conf_reason` 为值域收窄（移除 1 值）。
> **v9.2（2026-09-12 · BLOCK-1 终审）**：`/review/scores` 评估范围与口径澄清（T1 接通 / T3/T15 待填充；`formula` ↔ 计算定义一致；`baseline_status` 字面量重申）——见 **§10**；**无字段/枚举变更**；终审纪要 `10-arch-review-r2.md` v4 §10。
> **v9.3（2026-09-13 · C3 链来源标注）**：新增 `LedgerChain.chain_source` + 枚举 `chain_source`（§11）；C1（LLM 测试端点）/ C2（注册表三态机制）**不改契约**；纪要 `10-arch-review-r2.md` v5 §11。
> **v9.4（2026-09-13 · F-6 方法名语义冻结）**：`trace[holdings].detail.method` 维持 `eastmoney_f10_top10_weighted` 并追加语义注记（历史标识；档位以 `top_n` 为准）——见 **§12**；**无字段/枚举变更**；纪要 `10-arch-review-r2.md` v6 §12。
> **v9.5（2026-09-13 · 影子盘窗口 60 · 用户指令）**：`rolling_window_days` / `window_days` 固定值 20→**60**；主文件滚动窗=60 交易日、启动回填满 60、每日滚动；记录为**走前回算口径**（非自然前向积累）——见 **§13**；纪要 `10-arch-review-r2.md` v7 §13。

## 摘要

1. v9 共 **新增 56 项**（字段级 44 + 新对象 1 + 枚举 8 组 + 任务类型 2 + 任务参数 1）、**变更 9 项**（语义/口径/行为，含 `shadow_status` 取值域收口）、**废弃 1 项**（`fail_count` 展示口径）；**v9.1 会签收敛再增 9 项 / 变更 4 项 / 注记 2 项**（§9）。
2. **销项 4 处实现超前契约的待同步**：V3（`covered_count` 口径文字）、V11（`bootstrap_percentiles_measured`）、V17（`shadow_status` 进度枚举 + `shadow_audit_status`）、V18（`fund_type`/`fund_type_label` + `TraceStep.detail`）。
3. R2 四目标的契约落点：估值（`conf_reason` / `qdii_correction` / precision 窗口累计）；覆盖（`verify_status` 四态 + 覆盖计数）；准确率（`t1_real_method` / `/review/scores` 真实出数 / `baseline_source`）；来源（`fail_window_7d` / `main_source`）。
4. 数值验收三式可复算口径成文（§6）：置信度 ≥21/22、覆盖按实计 `(15+k)/22`、Δ 有值；均给出复算式与允许例外。
5. 接口数量仍 **55 个**（53 UI + 2 内部），9 域不变；统一信封与 10 错误码不变；冻结参数**值**（K=4/p=0.25/MIN_N=15/BAND=0.02/双否决分位/0.30/3）不变，仅追加 `baseline_method` 口径说明。

## 正文

### 1. v9 变更总览（新增 / 变更 / 废弃 分类）

#### 1.1 新增（56 项）

| 类别 | 数量 | 明细落点 |
|---|---|---|
| 字段级新增（对既有对象/端点追加） | 44 | `HoldingRow` ×8（§3.1）；`Valuation` ×4（§3.2）；`TraceStep.detail` ×1（§3.3）；`CoveragePanel` ×3（§3.5）；`SignalState` ×3（§3.6）；`PredictionSummary` ×1（§3.7）；`ShadowProgress` ×4 / `ShadowAudit` ×1（§3.8）；`FrozenParams` ×1（§3.9）；`DataSourceHealth` ×3（§3.10）；`HoldingsDataSource` ×3（§3.11）；`LedgerEntry` ×1 / `ShadowLedger` ×2（§3.12）；`/engine/status` ×1（§4.1）；`/review/scores` ×4（§4.2）；`/valuations/precision` ×2（§4.5）；`/factors/score-chain` ×2（§4.9） |
| 共享对象新增 | 1 | `QdiiCorrection`（§3.4，含 `domestic` / `overseas` 内联结构） |
| 枚举新增 | 8 组 | `fund_type` / `verify_status` / `conf_reason` / `backfill_method` / `baseline_source` / `ledger_refresh_mode` / `qdii_correction_method` / `qdii_fallback_reason`（§2.1） |
| 任务类型新增 | 2 | `task_type` 追加 `maintain_nav_history`（数据维护）与 `verify_tiers`（C→B 验证批次 / 代理复核，§4.8） |
| 任务参数新增 | 1 | `POST /tasks` 的 `backfill_ledger.params.mode`（§4.8） |

#### 1.2 变更（9 项，字段名一律不变）

| # | 落点 | 变更性质 | 内容 | 关联 |
|---|---|---|---|---|
| B1 | `/engine/status.shadow_status` | **取值域变更**（V17 收口） | 由 `shadow_review_status`（idle/ok/bad）改为 `shadow_progress_status`（not_started/recording/qualified/gap）；偏差评估迁 `shadow_audit_status`（新增） | V17 / R2-13 |
| B2 | `ShadowProgress.consecutive_days` / `gap_days` | 计算口径修正 | 由「仅主文件」改为「主文件 ∪ 归档」合并计算（去重）；`consecutive_days` 可达 ≥60 | R2-13 |
| B3 | `ShadowProgress.baseline_rate` / `ShadowAudit.baseline_rate` | 口径修正 | 由冻结 0.5830 改为**实测** `max(恒涨率, 恒跌率)`（台账 universe；见 §6.3）；0.5830 不再参与任何计算 | R2-14 |
| B4 | `/holdings/summary.covered_count` | 口径文字同步（V3） | 契约文字由「`market_value != null` 只数（非按 change_rate）」更正为「**`change_rate != null` 只数**」（与实现/PRD F-01 一致）；字段名/类型不变 | V3 / F-PM-01 |
| B5 | `/review/scores` | 行为变更 | 由硬编码全 null → **真实输出**（`data_kind=backtest` 走生产配置六窗走前；`data_kind=shadow_live` 走台账合并 + 实测基线）；未接通窗口仍 `baseline_status=pending` + null | R2-11 |
| B6 | `/settings/holdings-data` | 语义降级 | `primary_path/primary_exists/...` 语义降级为「**可选外部导入源**」；主源改为产品自持 `data/holdings.json`（`main_source` 新增）；前端不得再以 `primary_exists=false` 作误导展示 | R2-15 |
| B7 | `POST /ledger/backfill` | 请求体可选字段 | `entries[]` 允许可选 `method`（enum `backfill_method`，缺省 `proxy_bar`）；写入记录含 `method` | R2-12 |
| B8 | `POST /tasks` 冻结黑名单 | 黑名单扩展 | `FROZEN_PARAM_KEYS` 追加 `baseline_method`（基线口径不可经 API 修改） | R2-14 |
| B9 | `ShadowLedger.field_list` | 数组内容追加 | 追加 `t1_real_method`（字段清单仍为固定穷举） | R2-12 |

#### 1.3 废弃（1 项）

| # | 落点 | 登记 | 处置 |
|---|---|---|---|
| C1 | `DataSourceHealth.fail_count` | `deprecated`（键名/类型保留） | 语义登记为「**累计历史失败（审计用）**」；前端**禁止**再作为当前状态展示（544 不得作为当前状态出现），展示口径改读 `fail_window_7d`；历史折叠区可读 `recent_failures`。删除该键须版本 +1 并通知双边 |

---

### 2. 全局约定增量

#### 2.1 枚举追加（9 组，穷举；仅新增，不改既有取值；§1.3 v9/v9.1 分表）

| 枚举名 | 取值 | 中文/口径 |
|---|---|---|
| `fund_type` | `active` / `index_link` / `qdii` / `other` | 主动 / 指数联接 / QDII / 其他（按基金名称关键字分类，QDII 优先于「混合」；分类失败归 `other` 保守走 proxy） |
| `verify_status` | `pending_validation` / `validating` / `validated` / `validation_failed` / `not_applicable` | 待验证 / 验证中（批次进行） / 已验证（升 B） / 验证未通过（降级） / 验证不适用（D①「暴露待定」，v9.1/R-3）；C 档行内四态唯一来源；中文文案由后端 `verify_status_label` 给 |
| `conf_reason` | `no_samples` / `nav_missing` / `valuation_missing` / `mode_unknown` / `budget_exceeded` | 样本不足 / 缺净值 / 缺估值 / 无估值来源 / 估值预算用尽（v9.1/R-4：移除 `pending_backfill`，等待回填语义归 `reconcile_result=pending`）；**仅当 `confidence=unknown` 时非 null**；取值判定**按序命中即停**（见 §3.2） |
| `backfill_method` | `proxy_bar` | **单值**：t*_real 以**代理 ETF 日线涨跌**判定（与预测锚点同源）；新增取值须版本 +1 |
| `baseline_source` | `measured` | **单值**：基线为台账 universe 实测 `max(恒涨率,恒跌率)`；冻结 0.5830 已退役 |
| `ledger_refresh_mode` | `incremental` / `recompute` | 增量（默认，缺口补齐+滚动裁剪） / 按现档位全量重生成滚动窗（旧记录先全量归档） |
| `qdii_correction_method` | `etf_close_plus_overnight` | **单值**：QDII 双段法 = 境内 ETF 收盘段 + 隔夜参照指数段（时间互补加法，见 §3.4） |
| `qdii_fallback_reason` | `overseas_unavailable` / `alignment_conflict` / `first_test_failed` | 隔夜源不可得 / 时间对齐校验失败 / 40 日窗首测不达标后回退单段（判定门槛与复评见 §9.3-G1） |
| `accuracy_window_phase` | `warming` / `first_verdict` / `mature` | **v9.1/D-2**：精度窗双时点——未满 5 可配对日 / ≥5 且 <40（首判就绪） / ≥40（终判就绪） |

#### 2.2 数值口径追加（追加到 v8 §1.2，不改既有行）

| 后缀/字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `verify_batch_id` | string/null | — | — | 验证批次号，格式 `vb_YYYYMMDD_HHMM`；`verify_status=validating` 时必填 |
| `history_days` | integer | 交易日 | 整数 | 主文件 ∪ 归档去重后的可用交易日总数 |
| `rolling_open_assets` | integer | 只 | 整数 | 滚动窗口内实际触发 E1/E3 的**资产数**（去重） |
| `window_filled_days` | integer | 交易日 | 整数 | 40 日精度窗内已积累的可配对交易日数（累计 X/40） |
| `QdiiCorrection.domestic.value` / `overseas.value` | number/null | 比率（小数） | 4 位 | 段收益；0.0121 = +1.21%；缺段 null |
| `QdiiCorrection.domestic.as_of` / `overseas.trade_date` | string(date)/null | — | — | 段数据对应交易日 `YYYY-MM-DD`，时区 `Asia/Shanghai` |
| `recent_failures[].at` | string(timestamp) | — | 秒 | 失败事件时刻（ISO 8601 带偏移）；前端文案「近 7 日」为**自然日**口径（与 `fail_window_days` 一致，N-3） |
| `verify_review_date` | string(date)/null | — | — | 挂档观察复查日（自证据就绪日 +30 交易日；D-4）；非挂档 null |
| `backfill_proxy_code` | string/null | — | 6 位数字 | 回填时所用代理 ETF 代码（复算锚；R-1）；未回填 null |
| `pending_verification_names` | array[string] | — | — | 待结论清单（C 档无结论者名称，≤10 只；D-4） |

> `verify_status_label` / `role_label` 同口径：中文展示文案由**后端产出**，前端不硬编码（沿用 `valuation_mode`/`mode_label` 纪律）。

#### 2.3 时间与命名
沿用 v8 §1.1（`*_date` = `YYYY-MM-DD`，`*_at` = ISO 8601 带偏移，`Asia/Shanghai`）；v9 新增键全部 snake_case，无驼峰。

---

### 3. 共享对象增量（逐字段完备；未列出的对象字段沿用 v8）

#### 3.1 `HoldingRow`（§5.1 v9 追加 8 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `fund_type` | enum `fund_type` | — | — | **V18**：基金类型（估值锚点分流依据：active→holdings 重仓加权；index_link/qdii→official/intraday/proxy） |
| `fund_type_label` | string | — | — | V18：主动/指数联接/QDII/其他 |
| `tier_reason` | string/null | — | — | 档位依据原文（静态映射理由 / 穿透结论 / R2-04 复核结论）；D 档亦必填；前端 tooltip 直读 |
| `verify_status` | enum `verify_status` | — | — | 验证状态（v9.1/R-3 五值）：A/B 档恒 `validated`；C 档四态；**D①（无映射且未穿透）→ `not_applicable`（展示「暴露待定」）**；D②（验证失败降档）→ `validation_failed` |
| `verify_status_label` | string | — | — | 中文文案（待验证/验证中/已验证/验证未通过），后端产出 |
| `verify_batch_id` | string/null | — | — | 最近/进行中批次号；无批次 null |
| `verify_note` | string/null | — | — | 结论摘要（升 B 日期或降级原因）；与 `tier_reason` 互补（note=结论，reason=依据） |
| `verify_review_date` | string(date)/null | — | — | v9.1/D-4：挂档观察复查日（自证据就绪日 +30 交易日）；非挂档 null；行内 tooltip 与覆盖面板「待结论清单」展示 |
| `qdii_lead_note` | string/null | — | — | R2-09：QDII 领先口径标注（"QDII · 境内代理领先净值 1–2 天"）；非 QDII 或非跨市场代理为 null（不显示，不编造） |

> 规则：`verify_status` 与 `tier` 必须自洽——`validated` 不可伴随 `tier=C/D`（除 D 档降级说明外）；升 B 后 `tier` 与信号列同步更新（R2-24 验收③）。
> **`tier=D` 的两种情形（v9 收编，覆盖度档位判定表的补充）**：① v8 原义「无映射且未穿透」→ `verify_status=not_applicable` + label「暴露待定」（v9.1/R-3）；② **验证未通过被明示降档**（`verify_status=validation_failed` + `tier_reason` 必填原因 + 从预测 universe 移出）——R2-04/R2-06 的处置出口，防止"超标且无结论"状态存在。D 档一律 `proxy_code` 可保留为审计证据，但**不产信号、不进 universe**。
> **挂档观察断言（v9.1/D-4）**：挂档行（`verify_status=pending_validation/validating` 且 `verify_review_date` 非 null）**不得计入「已验证/预测覆盖增长」，不进 universe**；复查日自**证据就绪日**起算（+30 交易日），到期强制进入降档/升档判定；>3 只同时挂档 → 触发架构×PM 复审（视为验证批次设计异常）。

#### 3.2 `Valuation`（§5.2 v9 追加 4 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `fund_type` | enum `fund_type` | — | — | V18 |
| `fund_type_label` | string | — | — | V18 |
| `conf_reason` | enum `conf_reason`/null | — | — | R2-01/v9.1：仅 `confidence=unknown` 时非 null；判定**按序命中即停**（R-4）：mode=unknown 无来源 → `mode_unknown`；预算跳过 → `budget_exceeded`；无当日记录 → `valuation_missing`；有记录但净值对缺 → `nav_missing`；有净值对但 `n_test<5` → `no_samples` |
| `qdii_correction` | `QdiiCorrection`/null | — | — | R2-03：QDII 校正记录；非 QDII 或未走双段为 null |

**置信度通道口径（R2-01 落定，不新增字段名）**：`confidence` / `mae_rate` / `dir_hit_rate` / `n_test` / `accuracy_window_days`（=40）语义沿用 v8，但**样本来源扩容**（v8 仅 `proxy|code` → v9 全档 `mode|code`）：
- 评分对象（v9.1/D-3 修订）= 每个 `(date, code, mode)` 的**当日最后一条**记录（同 mode 同日多轮取最后；不同 mode 同日各自成样本、各自归键 `mode|code`）——保证 holdings/proxy 等非官方档不被"当日最终一条"挤出样本。
- 误差 = `|估值 change_rate − 官方 change_rate|`；官方 change_rate = `nav(D)/nav(D−1) − 1`（前一公布日）；不可配对的日期不进入样本（不填 0）。
- 滚动窗口 = 最近 **40 个可配对交易日**；`n_test ≥ 5` 才产出统计（否则 `confidence=unknown` + `conf_reason=no_samples`）；`n_test` 逐日累计。
- 官方档的显式口径：若记录 `nav_date == D`（当日官方已发布），其误差≈0（既成事实，非估计）；若 `nav_date < D`（官方未发布、以最近一期净值为锚），照常参与误差统计——tooltip 必须展示该口径（R2-20）。

#### 3.3 `TraceStep.detail`（§5.2.1 v9 追加 1 字段，V18 收编）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `detail` | object/null | — | — | 该步结构化明细；缺失为 null（键恒在时由后端保证，前端不得编造）。**当前仅 `holdings` 步定义**（穷举键见下）；其余步为 null，未来新增须版本 +1 |

`trace[holdings].detail` 键（穷举；`holdings` 步命中/未命中均可携带）：

| 键 | 类型 | 单位 | 精度 | 口径 |
|---|---|---|---|---|
| `method` | string | — | — | 恒 `eastmoney_f10_top10_weighted`；**v9.4 注记**：名含 `top10` 为**历史标识**（v8 首版口径），v9 起实际档位由 `top_n` 承担（10/20）；本标识冻结，改名须版本 +1 并评估历史记录兼容（见 §12） |
| `formula` | string | — | — | 恒 `weighted_change = sum(w_i * chg_i) / sum(w_i)` |
| `top_n` | integer | 名 | 整数 | 实际抓取档位：10（默认）或 20（R2-02 启用后）；回退时如实给 10 |
| `report_date` | string(date)/null | — | — | 季报披露截止日（tooltip 必示） |
| `top10` | array[object] | — | — | 持仓明细：`{rank, stock_code, stock_name, weight_pct, day_change, contribution, used}`；`weight_pct` 百分数 2 位（v8 §5.38 单位例外同口径）；`day_change` 比率 4 位；`used=false` 表示缺报价被剔除 |
| `covered_weight_pct` | number | 百分数 | 2 位 | 参与加权的权重合计（前 10/20 之和） |
| `total_weight_pct` | number | 百分数 | 2 位 | 前十/二十可解析权重合计 |
| `weighted_change` | number/null | 比率 | 4 位 | 加权涨跌（Σw×chg/Σw） |
| `base_nav` | number/null | 元/份 | 4 位 | 估算基准净值（最近一期官方） |
| `base_nav_date` | string(date)/null | — | — | 基准净值对应日 |
| `estimated_nav` | number/null | 元/份 | 4 位 | `base_nav × (1 + weighted_change)` |
| `included_markets` | array[string] | — | — | R2-02：纳入的市场，取值 ⊆ `["A","HK","US"]` |
| `excluded_count` | integer | 只 | 整数 | R2-02：因缺报价/非 A 股不支持被剔除的标的数（不编造，如实计） |

#### 3.4 `QdiiCorrection`（新共享对象 §5.39；R2-03 / ISSUE-ZL-R2-01 裁定落地）

> 归属：`Valuation.qdii_correction`。适用范围：`fund_type=qdii` 且代理为跨市场 ETF（024239/016665/012922 ← 513100；457001/021662 ← 159920；163208 ← 162411 视参照可得性）。
> **算法（架构冻结）**：双段 = 时间互补的加法拼接，**不引入学习权重**：
> `change_rate = domestic.value + overseas.value`，仅当两段均可得且**时间对齐校验通过**（overseas 时段收盘时刻晚于 domestic 交易日 A 股收盘 15:00）时 `applied=true`；任一段缺失/校验失败 → 回退单段（`applied=false`）并给 `fallback_reason`，**不得静默**。

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `applied` | boolean | — | — | 是否启用双段校正 |
| `method` | enum `qdii_correction_method` | — | — | 单值 `etf_close_plus_overnight` |
| `domestic` | object | — | — | `{value: number/null 比率 4 位, as_of: string(date)/null}`：境内代理 ETF 最近已收盘交易日 `close/close−1` |
| `overseas` | object/null | — | — | `{value: number/null 比率 4 位, ref_code: string, trade_date: string(date)/null, source: string}`：隔夜参照指数收益；不可得 null（`applied=false` 时允许 null） |
| `fallback_reason` | enum `qdii_fallback_reason`/null | — | — | `applied=true` 恒 null；false 时必填（兜底路径：首测不达标 → `first_test_failed`，产线回退单段）。**v9.1/G1 判定门槛**：`first_test_failed` 仅可在 **40 个可配对日窗且 `n_test≥20`** 时判定；未达门槛挂档观察；回退为**暂态**（预注册复评日：每 20 可配对日复评 + 隔夜源变更即复评），回退结论必须带数字（单段实测 MAE + 与目标差距） |
| `note` | string | — | — | 口径说明长文（tooltip 直出；含"双段=境内收盘+隔夜参照，不构成投资建议"措辞） |

#### 3.5 `CoveragePanel`（§5.19 v9 追加 3 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `prediction_universe_count` | integer | 只 | 整数 | 进入预测 universe 的只数（A+B 档）；`= tiers[A].count + tiers[B].count` |
| `pending_verification_count` | integer | 只 | 整数 | C 档且无结论的只数（`verify_status ∈ {pending_validation, validating}`）；D 档降级另计 |
| `prediction_coverage_note` | string | — | — | 覆盖文案：批次中「预测覆盖 15/22（+7 待结论）」；出结论后「预测覆盖 (15+k)/22」（**按实计**，k=升 B 只数；见 §6.2） |
| `pending_verification_names` | array[string] | — | — | v9.1/D-4：待结论清单（C 档无结论者名称，≤10 只；覆盖面板「待结论清单」数据源） |

#### 3.6 `SignalState`（§5.21 v9 追加 3 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `rolling_open_assets` | integer | 只 | 整数 | **R2-08 口径（v9.5 随窗更新）**：滚动 **60** 交易日实际触发 E1/E3 的资产数（去重；台账口径，非日开口数） |
| `rolling_window_days` | integer | 交易日 | 整数 | 固定 **60**（v9.5 起；用户指令 2026-09-13；原 20） |
| `low_frequency_note` | string | — | — | 低频期望说明（v9.5 起为 **60 交易日口径**；文案与基线由 PM 重定——原「20 交易日约 11 资产」不再适用）；文案后端产出 |

> `empty_note` 四要素（监控中 N/M、距上次开口、上次开口、上次结果）沿用 v8；R2-08 仅追加低频说明与滚动口径字段。

#### 3.7 `PredictionSummary`（§5.4 v9 追加 1 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `qdii_lead_note` | string/null | — | — | 同 `HoldingRow.qdii_lead_note`；仅 QDII 行非 null（信号卡标注） |

#### 3.8 `ShadowProgress` / `ShadowAudit`（§5.28 / §5.29）

**`ShadowProgress` v9 追加 4 字段 + 2 处口径修正**：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window_days` | integer | 交易日 | 整数 | 主文件滚动窗口，固定 **60**（v9.5 起；用户指令 2026-09-13；原 20）；更早记录由归档承接 |
| `archive_merged` | boolean | — | — | 连续/漏单计算是否含归档记录（归档缺失不可读时为 false，并在 `note` 标注口径降级） |
| `history_days` | integer | 交易日 | 整数 | 主文件 ∪ 归档去重后的可用交易日总数（R2-13 的"可达 ≥60"证据字段） |
| `baseline_source` | enum `baseline_source` | — | — | 恒 `measured` |

口径修正（B2/B3）：
- `consecutive_days`：数据集 = 主文件 ∪ 归档（按 `(date, code)` 去重）中的日期集；自最新日期向前逐交易日回溯的连续数；**可达 ≥60**（不再被窗口封顶；v9.5 窗=60，启动回填满后可立即达 60——**记录为走前回算，非自然前向积累**）。
- `gap_days`：在 `[start_date, last_date]` 内，监控资产代理 K 线日期**并集**（交易日历）中存在、而合并集无任何记录的交易日数。
- `baseline_rate`：实测值（§6.3）；`deviation_pp = hit_rate − baseline_rate`；`note` 更新为"连续 60 个交易日无漏单且偏差 <2pp 才具上线资格；连续天数按归档合并计算"。**v9.5 口径（同版补记）**：`note` 文案按 §13.3 重定（记录为走前回算；禁止上线资格暗示），PM 供词后生效。

**`ShadowAudit` v9 追加 1 字段**：`baseline_source`（enum `baseline_source`，恒 `measured`）；`baseline_rate` 改实测（B3）。

#### 3.9 `FrozenParams`（§5.14 v9 追加 1 字段）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `baseline_method` | string | — | — | 固定文本："`max(恒涨率,恒跌率)`，按台账 universe（全部资产-日）实测；0.5830 已退役"；**改动须重走六关**（随 `change_policy`） |

#### 3.10 `DataSourceHealth`（§5.17 v9 追加 3 字段 + `fail_count` 废弃）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `fail_window_7d` | integer | 次 | 整数 | **展示口径**：近 7 日（`fail_window_days`）失败次数；成功不抹除窗口内历史，按时间窗滚动自然衰减 |
| `fail_window_days` | integer | 自然日 | 整数 | 固定 7 |
| `recent_failures` | array[object] | — | — | 最近 ≤10 条失败事件 `{at, note}`（`at` 秒级时间戳，`note` 可读原因）；历史折叠区数据源；不含隐私信息 |

`fail_count`：C1 废弃登记（§1.3）。

#### 3.11 `HoldingsDataSource`（§5.33 v9 追加 3 字段 + 语义降级）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `main_source` | object | — | — | **产品自持主源**：`{path: "data/holdings.json", exists: boolean, modified_at: string(timestamp)/null, count: integer, readonly: false}`（可写主源；缺失时启动引导导入） |
| `import_available` | boolean | — | — | 可选外部导入源（`primary_path`）是否存在且可读；`false` → 前端**禁用**导入按钮 |
| `import_disabled_reason` | string/null | — | — | 不可用时的可读说明（"源文件不存在：<path>；可用 CSV/手工录入"）；可用时 null |

语义降级（B6）：`primary_*` / `legacy_*` 字段保留（向后兼容），语义 = **可选导入源状态**（不再代表"主源"）。前端展示规则：主源状态读 `main_source`；导入入口行为读 `import_available` / `import_disabled_reason`；`consistent` / `diff_fields` / `diff_note` 保留（估值≠净值实证长文继续有效）。

#### 3.12 `LedgerEntry` / `ShadowLedger`（§5.9 / §5.28）

**`LedgerEntry` v9 追加 1 字段**：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `t1_real_method` | enum `backfill_method`/null | — | — | 该行 t*_real 的回填口径；未回填 null；**本期唯一取值 `proxy_bar`**（代理 ETF 日线涨跌，与预测锚点同源；见 §6/ADR-0008） |
| `backfill_proxy_code` | string/null | — | 6 位数字 | **v9.1/R-1**：该行最近一次回填所用代理 ETF 代码（复算锚——换代理后以「回填时映射」复算）；未回填 null |

**`ShadowLedger` v9 追加 2 字段 + `field_list` 追加**：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `backfill_method` | enum `backfill_method` | — | — | 恒 `proxy_bar`（本盘回填口径，页面口径标注数据源） |
| `backfill_method_note` | string | — | — | 口径长文（"命中判定=代理 ETF 涨跌方向；净值口径见估值误差通道"）；前端不硬编码 |
| `field_list` | array[string] | — | — | **v9 追加 `t1_real_method`；v9.1 追加 `backfill_proxy_code`**；固定穷举：`date/code/gate/p_up/ddsm_state/veto_crowd/veto_klow2/signal/opened/t1_real/t3_real/t15_real/t1_real_method/backfill_proxy_code/created_at` |

#### 3.13 `/engine/status`（§6.9 v9 字段修正 + 1 新增）

- `shadow_status`：类型不变（enum），取值域收口为 `shadow_progress_status`（not_started/recording/qualified/gap）——**B1**。
- 新增 `shadow_audit_status`（enum `shadow_review_status`，idle/ok/bad）：偏差评估三态，独立于进度——V17/R2-13。

---

### 4. 端点行为增量（其余 45 个端点零变更，沿用 v8）

#### 4.1 `GET /engine/status`（B1 + 新增）
- 响应新增 `shadow_audit_status`；`shadow_status` 按进度枚举输出（**不得再返回 idle/ok/bad**）。
- `shadow_consecutive_days`：按合并口径（§3.8）；`shadow_target_days=60` 不变。
- 调用方：引擎页 HUD（12s 轮询）；前端映射：`recording=记录中 / qualified=记录窗已满 60 交易日（走前回算）/ gap=有缺口 / not_started=未启动`；「达标/降级」读 `shadow_audit_status`。**v9.5 口径（同版补记）**：`qualified` 仅指记录窗完整度（走前回算），**禁止**暗示「上线资格」（文案见 §13.3）。

#### 4.2 `GET /review/scores`（B5；R2-11）
- 调用方：复盘页 hero / 三窗口表。
- 行为：不再硬编码 null——
  - `data_kind=backtest`（默认）：生产配置（E1/E3→DDSM→双否决→出口）作为内置因子经 `factor_engine.evaluate` 六窗走前，取结果回填 `scores[]` 与 `hero`；未接通窗口 `baseline_status=pending`、数值 null（不得填估计值）。**v9.1/R-2 维度成文**：`scores[]` 行 = **持有期 horizon**（T1/T3/T15，各自定式，按 H=1/3/15 分别评估）；每行主值取该 horizon 的**全样本窗（full）**结果（`sample_window` 恒 `full` 明示）；`evaluate` 的六个**样本窗**（d15…full）归因子页/记分卡，**不得混入本页**充当"三窗口"。
  - `data_kind=shadow_live`：来自台账合并（t*_real 回填）+ **实测基线**；样本不足时 `scores[]` 可为空并 `note` 说明。
- 响应 `hero` v9 追加：`open_count`（integer，笔）、`sample_period`（string/null）、`data_kind`（string，与请求一致）；响应级追加 `note`（string，可读口径/样本说明）。`scores[]` 行 v9.1 追加 `sample_window`（string，恒 `full`）。
- 口径：`基线 = max(恒涨率,恒跌率)`（窗口内去重叠全测试日集）；`delta_pp = hit_rate − baseline_rate`；回测与实盘由 `data_kind` 区分（视觉/文案可区分，沿用 v8 §5.8）。
- **v9.2 注记（BLOCK-1）**：上述「按 H=1/3/15 分别评估」为**未来接通路径**表述；**R2 实际接通范围 = T1**，T3/T15 保持 `pending`+null（未接通），详见 §10。

#### 4.3 `GET /review/reconciliation`（无字段变化）
- 行内 `t1_real_method` 随 `LedgerEntry` 透出（未回填 null）；`result` 规则不变（§5.10）。

#### 4.4 `GET /settings/holdings-data`（B6）
- 响应增补 `main_source` / `import_available` / `import_disabled_reason`（§3.11）；前端展示规则见 §3.11。

#### 4.5 `GET /valuations/precision`（R2-05 / R2-01 / v9.1 D-1+D-2）
- 响应追加：`window_filled_days`（integer，累计 X/40）、`window_status_label`（string，"累计 12/40 日"/"已满 40 日"）、`window_phase`（enum `accuracy_window_phase`，双时点）。
- **v9.1/D-1 主指标修订**：新增 `estimate_quality`（object）与 `official_summary`（object，见 §9.1）；**vsum 主指标 = `estimate_quality.weighted_mae_rate`（估算档：intraday/holdings/proxy）**；官方档为「既成事实」单列 chip，不参与主指标；既有 `weighted_mae_rate` / `groups[]`（全档）保留为**参考口径**（语义登记为「全档参考」，不得再作主指标展示）。
- `mode_distribution` 沿用 v8；R2-01 全档通道接通后由 `mode|code` 统计驱动。

#### 4.6 `GET /signals/state`（R2-08）
- 响应追加 `rolling_open_assets` / `rolling_window_days` / `low_frequency_note`（§3.6）；`empty_note` 四要素口径不变。

#### 4.7 `GET /holdings/coverage`（R2-06 / R2-24）
- 响应追加 `prediction_universe_count` / `pending_verification_count` / `prediction_coverage_note`（§3.5）；成员行 `verify_status` 经 `/holdings` 行读取（覆盖面板展示 C 档验证进度）。

#### 4.8 `POST /tasks`（R2-07 / R2-14 / R2-16）
- `type` 枚举追加 2 项：
  - `maintain_nav_history`：维护 `data/cache/nav/<code>.json`（lsjz 分页增量补全，幂等去重）+ 重算估值误差通道（`accuracy.json` v2）；幂等可重复执行。
  - `verify_tiers`：对 `params.targets`（string 数组，缺省 = C 档 7 只；R2-04 复核时传 9 只清单）逐只跑**单资产生产配置**六窗走前回测，按 R2-06/R2-04 规则出结论并落盘 `data/review/tier_reviews.jsonl`（INSERT-ONLY）+ 幂等更新 holdings（`tier`/`tier_reason`/`verify_status`/`verify_batch_id`/`verify_note`）。结论判定：`lift≥1.0 且 Δ≥0 且独立触发日≥20 → 升 B`；样本不足（独立触发日<20）→ 维持 C + 复查日；样本足且不达标 → 明示降档（见 10-arch-review-r2 §2.4）。
- `backfill_ledger` 新增可选 `params.mode`（enum `ledger_refresh_mode`，缺省 `incremental`）：
  - `incremental`：现有行为（缺口补齐 + 滚动裁剪 + 到期 t*_real 回填，见下）。
  - `recompute`：按**现档位**全量重生成滚动窗——旧记录**先全量归档**（`reason=recompute_by_current_tier`）再从主文件移除后重生成；INSERT-ONLY 记录级语义不破（旧记录可归档复读，首次口径行不丢）。
- `backfill_ledger` 行为扩展（R2-12）：到期信号按代理日线自动写 `t*_real`（独立 `backfill.jsonl`，追加 `method` 字段）；已到期 up 信号回填覆盖率目标 100%；标的日线缺失 → 标记"数据缺失待补"不移除记录。**v9.1/R-1**：写入行同时记 `proxy_code`（所用代理）；`POST /ledger/backfill` 请求体 `entries[]` 允许可选 `proxy_code`（缺省取该基金当前映射）；换代理事件写 `tier_reviews.jsonl`（映射变更时点，供复算追溯）。
- 冻结黑名单（B8）追加 `baseline_method`：`params` 出现 `k_noise/p_perturb/min_n/shrink/band/veto_*_quantile/min_coverage_ratio/min_open_count/weighting_basis/baseline_method` 任一 → `E_VALIDATION`。

#### 4.9 `GET /factors/score-chain`（V11 销项，只加不改）
- 响应追加 `bootstrap_percentiles_measured`（object/null，真实引擎 500 次零分布实测分位；未产出 null）与 `real_engine`（boolean）；既有 `bootstrap_percentiles` 常量保留（兄弟字段并存），删除常量须版本 +1。

#### 4.10 `GET /ledger` / `GET /ledger/shadow`（R2-07 / R2-12）
- `GET /ledger`：行内追加 `t1_real_method`；滚动窗口口径（v9.5：最近 **60** 交易日、INSERT-ONLY、裁剪全量归档）。
- `GET /ledger/shadow`：追加 `backfill_method` / `backfill_method_note` / `field_list` 更新（§3.12）；`progress` 按 §3.8 口径；`archive_manifest_at` 语义不变（recompute 归档也写 `_manifest.jsonl`）。

---

### 5. R1 实现超前契约 · 待同步项销项（V3/V11/V17/V18）

| # | 原登记（14-api-impl-report） | v9 裁定 | 落点 |
|---|---|---|---|
| V3 | `covered_count` 按 `change_rate != null`，与 v8 文字冲突 | **实现为准，契约文字同步**（B4） | §4.7 注 / v8 §6.2.1 更正 |
| V11 | `bootstrap_percentiles_measured` 兄弟字段并存 | **接受并存**（只加不改；常量保留） | §4.9 |
| V17 | `shadow_status` 改进度枚举 + 新增 `shadow_audit_status` | **接受**（B1）；前端同步已完成（`engine.js` PROGRESS_TAG/AUDIT_TAG 实测存在） | §4.1 |
| V18 | `fund_type`/`fund_type_label` + `trace[holdings].detail` | **接受并入契约**（§3.1/§3.2/§3.3） | §3 |
| V5/V6/V14/V15/V16 | v6/v8 已销项（`opened`/`caps`/`penetration_trace`/计数/分档表） | 维持 v8 原样，v9 不再展开 | 沿用 v8 §11/§13 |
| V7~V10/V12/V13 | 因子机制口径（基线测试日集/否决层语义/binary 免填/同步返回/内置 id/账本路径） | **不在本契约范围**：登记为 `21-factor-governance.md` 的 R2 后修订项（不改字段名、不阻塞 `/factors/*`） | 10-arch-review-r2 §架构债 |

---

### 6. 数值验收可复算口径（R2 三式；对应 PRD G2-01/04/06）

#### 6.1 置信度非 unknown ≥21/22（G2-01）
- **复算式**：`非unknown只数 = |{ h ∈ 持仓 : confidence(mode_h|code_h) != "unknown" }|`，其中 `mode_h` = `/holdings` 行 `valuation.valuation_mode`。
- 数据源：`accuracy.json`（v9 结构：全档 `mode|code`）→ `confidence` 按 `mae_rate` 对照 0.008/0.012 分档（沿用 v8 阈值）。
- **允许的 unknown 情形（穷举，必须带 `conf_reason`）**：`no_samples`（n_test<5）/ `nav_missing` / `valuation_missing` / `mode_unknown` / `budget_exceeded`（v9.1/R-4 五值；判定按序命中即停）。
- 验收补充：≥21/22 为**当日目标**；上线首日按实测报告"n_test 尚小"如实显示（不阻止非 unknown 判定，但 tooltip 展示 n）。
- **v9.1/D-2(b) 双时点**：首判 = 上线后满 **5 个可配对日**（`window_phase=first_verdict`，全档首出值）；终判 = 满 **40 个可配对日**（`window_phase=mature`，R2-01 终值验收时点）。

#### 6.2 预测覆盖按实计（G2-04）
- **复算式**：`预测覆盖 = (15 + k) / 22`，`k = |{ h : 原C档名单 ∧ h.tier ∈ {A,B} ∧ h.verify_status = "validated" }|`；原 C 档名单 = `{022485, 025500, 018957, 021528, 457001, 021662, 163208}`。
- 展示：批次中 `15/22（+7 待结论）`；结论后按实计（`(15+k)/22`）；未通过者 `tier=D` 并移出 universe（`verify_status=validation_failed` + `verify_note` 原因）。
- 一致性断言：`prediction_universe_count` 必须 == `/holdings` 中 tier ∈ {A,B} 的行数（QA 负向断言）。

#### 6.3 Δ 有值可复算（G2-06）＋ 实测基线（G2-07）
- **Δ 复算式**：`delta_pp = hit_rate − baseline_rate`；`hit_rate` = 独立触发日口径命中率；`baseline_rate = max(恒涨率,恒跌率)`（**同一测试窗内的去重叠全测试日集**，不用 legacy 常量）。
- 数据源：`factor_engine.evaluate(生产配置, 代理日线缓存, frozen_config)`；**同 bars 缓存 + 同 `frozen_config_hash` + 固定 seed → 重复调用结果一致**（幂等，QA 复算口径）。
- 影子盘实测基线：`baseline_rate(measured) = max( Σ[t1_real>0]/N , Σ[t1_real<0]/N )`，universe = 合并台账全部 `(date, code)` 且 `t1_real` 非 null 的行；`N` 为行数；`N=0` → null（不填 0.5830）。
- 断言：`grep 0.5830` 于产线代码/运行数据（除历史归档）**0 引用**；`/engine/frozen-params.baseline_method` 非空。

---

### 7. v9 追加清单（机器核对表；backend-dev 逐项对照、qa 负向断言）

#### 7.1 字段级（44 项）

| # | 落点 | 类型 | 关联需求 |
|---|---|---|---|
| 1-8 | `HoldingRow.{fund_type, fund_type_label, tier_reason, verify_status, verify_status_label, verify_batch_id, verify_note, qdii_lead_note}` | see §3.1 | V18 / R2-06/09/24 |
| 9-12 | `Valuation.{fund_type, fund_type_label, conf_reason, qdii_correction}` | see §3.2 | V18 / R2-01/03 |
| 13 | `TraceStep.detail` | object/null | V18 / R2-02/20 |
| 14-16 | `CoveragePanel.{prediction_universe_count, pending_verification_count, prediction_coverage_note}` | int/string | R2-06 |
| 17-19 | `SignalState.{rolling_open_assets, rolling_window_days, low_frequency_note}` | int/string | R2-08 |
| 20 | `PredictionSummary.qdii_lead_note` | string/null | R2-09 |
| 21-24 | `ShadowProgress.{window_days, archive_merged, history_days, baseline_source}` | see §3.8 | R2-13/14 |
| 25 | `ShadowAudit.baseline_source` | enum | R2-14 |
| 26 | `FrozenParams.baseline_method` | string | R2-14 |
| 27-29 | `DataSourceHealth.{fail_window_7d, fail_window_days, recent_failures}` | see §3.10 | R2-18 |
| 30-32 | `HoldingsDataSource.{main_source, import_available, import_disabled_reason}` | see §3.11 | R2-15 |
| 33 | `LedgerEntry.t1_real_method` | enum/null | R2-12 |
| 34-35 | `ShadowLedger.{backfill_method, backfill_method_note}` | see §3.12 | R2-12 |
| 36 | `/engine/status.shadow_audit_status` | enum | V17 |
| 37-40 | `/review/scores.hero.{open_count, sample_period, data_kind}` + 响应 `note` | see §4.2 | R2-11 |
| 41-42 | `/valuations/precision.{window_filled_days, window_status_label}` | int/string | R2-05 |
| 43-44 | `/factors/score-chain.{bootstrap_percentiles_measured, real_engine}` | object/null + bool | V11 |

#### 7.2 对象 / 枚举 / 任务（11 项）
- 对象：`QdiiCorrection`（§3.4）。
- 枚举 8 组（§2.1）：`fund_type` / `verify_status` / `conf_reason` / `backfill_method` / `baseline_source` / `ledger_refresh_mode` / `qdii_correction_method` / `qdii_fallback_reason`。
- 任务：`task_type += maintain_nav_history | verify_tiers`；`backfill_ledger.params.mode`（§4.8）。

#### 7.3 变更核对（9 项）
见 §1.2 B1~B9；其中 **B1 为取值域变更**（唯一一处非"只加"项），前端 HUD 必须按进度枚举渲染，后端不得再输出 idle/ok/bad 于 `shadow_status`。

#### 7.4 v9.1 核对（会签收敛：9 新增 / 4 变更 / 2 注记）
见 §9；与 §7.1/§7.2 合并即为 v9.1 全量机器核对表（字段级 44+9、枚举 9 组、任务 3 类）。

---

### 8. 未变条目声明（沿用 v8，不重抄）

- 统一信封（§2）、错误码 10 个（§3）、端口与基址（§1.4）、命名与时间（§1.1 v8）**零变更**。
- 接口数量 **55 个**、§4 总览与 §6.11 端点清单**零新增/零删除**（v9/v9.1 无新端点）。
- 以下对象**零变更**：`Nav` / `WindowResult` / `PortfolioForecast`（含 `weighting_basis` 冻结）/ `ReviewScore`（除 hero 与 v9.1 的 `sample_window` 外）/ `FactorPan` / `FactorItem` / `FactorBook` / `Task` / `Settings` / `Runtime` / `RiskMetrics` / `DefinitionCard` / `FactorScoreDetail` / `ArenaMatrix` / `StateCube` / `TrainingStatus` / `EngineInputItem` / `CrowdComposite` / `GovernanceCycle` / `DigRecord` / `LifecycleRules` / `Factor` / `FactorDefinition` / `Scorecard` / `PenetrationTrace` 家族。
- 冻结参数**值**零变更：`k_noise=4 / p_perturb=0.25 / min_n=15 / shrink=10 / band=0.02 / veto_crowd_quantile=0.60 / veto_klow2_quantile=0.40 / min_coverage_ratio=0.30 / min_open_count=3`；E2/E4 禁复活、永不做空、INSERT-ONLY 语义、`(date,code)` 唯一、回填独立文件——全部维持。
- 未变条目的逐项索引见 v8 §4（接口总览）与 §8~§13（历史追加台账）。

---

### 9. v9.1 追加清单（会签收敛轮 · D-1..D-4 / R-1..R-5 处置）

> 来源：`10-arch-review-pm-r2.md`（PM 挑刺：4 实质分歧 + 5 修订 + 4 NIT）→ 逐条收敛纪要（双方立场/最终结论/影响工件）见 `10-arch-review-r2.md` v2 §1/§4。
> **不变式**：v9.1 未修改任何既有字段名；**新增 9 项、变更 4 项、口径注记 2 项**；`conf_reason` 为值域收窄（移除 1 值，见 M2）。

#### 9.1 新增（9 项）

| # | 落点 | 类型 | 口径 | 关联 |
|---|---|---|---|---|
| 1 | `/valuations/precision.estimate_quality` | object | 估算档（intraday/holdings/proxy）质量组：`{groups[], weighted_mae_rate, count, market_value, weight_ratio, industry_baseline_mae_rate, window_days, window_filled_days, note}`；**vsum 主指标 = `weighted_mae_rate`（估算档）**；`groups[]` 元素结构同 v8 `groups`（`{confidence,label,count,market_value,weight_ratio}`），仅估算档 | D-1 |
| 2 | `/valuations/precision.official_summary` | object | 官方档单列：`{count, market_value, weight_ratio, weighted_mae_rate, note}`（note 含「既成事实」口径）；不参与主指标 | D-1 |
| 3 | `/valuations/precision.window_phase` | enum `accuracy_window_phase` | `warming` / `first_verdict` / `mature`（双时点，见 §6.1） | D-2(b) |
| 4 | `HoldingRow.verify_review_date` | string(date)/null | 挂档观察复查日（自证据就绪日 +30 交易日）；非挂档 null | D-4 |
| 5 | `CoveragePanel.pending_verification_names` | array[string] | 待结论清单（C 档无结论者名称，≤10 只） | D-4 |
| 6 | `LedgerEntry.backfill_proxy_code` | string/null | 回填时所用代理代码（复算锚） | R-1 |
| 7 | `ReviewScore.sample_window` | string | 恒 `full`（主值取全样本窗；六样本窗归因子页） | R-2 |
| 8 | 枚举 `accuracy_window_phase` | `warming` / `first_verdict` / `mature` | 枚举表见 §2.1 | D-2(b) |
| 9 | `verify_status` 增值 `not_applicable` | — | D①「暴露待定」；D② 仍 `validation_failed` | R-3 |

#### 9.2 变更（4 项，字段名一律不变）

| # | 落点 | 变更性质 | 内容 | 关联 |
|---|---|---|---|---|
| M1 | 评分对象口径（§3.2） | 口径修正 | 「当日最终展示记录」→「每个 `(date,code,mode)` 当日**最后一条**」 | D-3 |
| M2 | `conf_reason` 值域（§2.1/§3.2/§6.1） | **值域收窄** | 移除 `pending_backfill`（等待回填语义归 `reconcile_result=pending`）；判定按序命中即停 | R-4 |
| M3 | `/valuations/precision.weighted_mae_rate`（全档） | 语义登记 | 降级为「全档参考」；vsum 主指标改 `estimate_quality.weighted_mae_rate` | D-1 |
| M4 | `ShadowLedger.field_list` | 数组内容追加 | 追加 `backfill_proxy_code` | R-1 |

#### 9.3 口径注记（2 项）
- **G1（QDII 首测门槛与复评）**：`first_test_failed` 仅可在 **40 个可配对日窗且 `n_test≥20`** 时判定（未达门槛挂档观察，不得宣布首测失败）；回退为**暂态**——`data/qdii_correction.json` 预注册 `next_review_date`（每 20 可配对日复评 + 隔夜源变更即复评）；回退结论必须带数字（单段实测 MAE + 与 1.50%/1.00% 目标的差距）；`alignment_conflict` 40 日窗内 ≥5 次 → 人工复核参照源是否误杀（计数入 `data/review/qdii_review.jsonl`）。
- **G2（命名等价，N-1）**：`QdiiCorrection.domestic.as_of` ≡ `overseas.trade_date`（段数据对应交易日，语义等价），不重命名；`overseas.source` 为来源标识。

#### 9.4 会签条目 → 落点映射（10-r2 v2 §4 契约变更记录同源）

| 条目 | 处置 | 落点 |
|---|---|---|
| D-1 | 部分采纳（拆分 + 主指标修订；官方档徽章保留、全档参考并列） | §9.1-1/2、§9.2-M3、§4.5 |
| D-2 | 采纳（证据道 + 双时点 + 收口硬约束） | §9.1-3/8、§6.1；08 §3.1b/§4.4/§7.4 |
| D-3 | 采纳 | §9.2-M1、§3.2 |
| D-4 | 采纳 | §9.1-4/5、§3.1；08 §4.1/§4.4 |
| R-1 | 采纳 | §9.1-6、§9.2-M4、§3.12、§4.8 |
| R-2 | 采纳 | §9.1-7、§4.2 |
| R-3 | 采纳 | §9.1-9、§3.1 |
| R-4 | 采纳 | §9.2-M2、§2.1、§3.2、§6.1 |
| R-5 | 采纳 | §9.3-G1、§3.4 |

### 10. v9.2 注记（BLOCK-1 终审 · 口径澄清；2026-09-12）

> 来源：S4 集成评审 `15-code-review-r2.md` BLOCK-1 → 终审纪要 `10-arch-review-r2.md` v4 §10.1。**本注记无字段/枚举变更**，仅澄清 §4.2 的评估范围与接通路径。

1. **§4.2 的「按 H=1/3/15 分别评估」为接通路径表述，非 R2 现状**：R2 实际接通范围 = **T1**（Brief-mandated 全链）；T3/T15 行一律 `baseline_status=pending` + `hit_rate/baseline_rate/delta_pp=null` + `open_count=0`（「待填充」），`formula` 保留各自定式标签（`gate_only` / `gate+ddsm`）。
2. **接通条件（未来版本）**：T3/T15 各自定式完成走前 CV（purge=H+2）+ placebo≥2pp + holdout 纪律（六关）→ 架构版本 +1（含 A-04 `validation_status` 升格联动）→ 后端按**各自定式**评估出数。
3. **`ReviewScore.formula` 语义重申**：必须与**该行计算所用的定义**一致；禁止标签与计算路径分叉（BLOCK-1 根因）。
4. **`baseline_status` 字面量重申**：取值域 §1.3 冻结为 `filled` / `pending`；`ok` 等其他字面量一律禁止（对应 10-r2 v4 §10.4 B1-3）。

### 11. v9.3 注记（C3 链来源标注；2026-09-13）

> 来源：C1/C2/C3 裁定（`10-arch-review-r2.md` v5 §11）。**仅新增 1 字段 + 1 枚举**；C1（LLM 测试端点）/ C2（注册表三态机制）**不改契约**。

1. **新增字段**：`LedgerChain.chain_source`（enum `chain_source`/null）——六步链的**来源标注**；`chain_available=false` 时为 null（不得编造）。归属对象与端点：`§5.34 LedgerChain` / `GET /ledger/chain`（v8 沿用，仅追加）。
2. **新增枚举** `chain_source`（穷举）：`stored`（写入时缓存的链）/ `recomputed`（读时按**写入同源口径**重算：`bars[:t-1]`、H=1、六步、`exit_threshold=0.5200`）。新增取值须版本 +1。
3. **口径**：`recomputed` 非原始记录，属同源可复现重算；前端可标注来源（时间线 tooltip，可选）；QA 断言：available 行 `chain_source ∈ {stored, recomputed}`，unavailable 行 null + `chain=[]`。
4. **范围注**：本字段为 BLOCK-A3「不新增字段」约束的**唯一豁免**（架构批准）；其余 BLOCK-A3 约束（`chain_available` 判定、前端分支文案、INSERT-ONLY 不动台账）不变。

### 12. v9.4 注记（F-6 方法名语义冻结；2026-09-13）

> 来源：F-6 裁定（`10-arch-review-r2.md` v6 §12.1）。**无字段/枚举变更**——仅对既有冻结值追加语义注记。

1. `trace[holdings].detail.method` 恒 `eastmoney_f10_top10_weighted`：名含 `top10` 为**历史标识**（v8 首版口径为前十持仓）；v9 起实际抓取档位由 `top_n` 字段承担（10/20），**方法名冻结**。
2. 审计判定口径：档位以 `top_n` 为准（名与数解耦）；QA 可断言 `method` 恒定 **且** `top_n ∈ {10,20}`。
3. 改名条件：须版本 +1 并评估历史记录（`valuation_history.jsonl` INSERT-ONLY 旧记录豁免读数）兼容；当前不触发。
4. 关联：同一字面量在持仓穿透（`penetration_method`，真实 top10 口径）中继续使用，不受本注记影响。

### 13. v9.5 注记（影子盘窗口 20→60 · 用户指令；2026-09-13）

> 来源：用户指令（2026-09-13）「影子盘直接补满 60 天，来一天换一天」；纪要 `10-arch-review-r2.md` v7 §13。**固定值变更 2 处**，其余字段/枚举不动。

1. **固定值变更**：`SignalState.rolling_window_days` 固定 20 → **60**；`ShadowProgress.window_days`「主文件滚动窗口」固定 20 → **60**。v8 中「滚动窗口 = 最近 20 个交易日」相关表述（§1.5 术语表「滚动窗口」、§5.9、§5.28、§6.7）自本版起以 **60** 为准。
2. **语义**：主文件滚动窗 = **60 交易日**；**启动即回填满 60 日**，此后每日滚动（进一天、出一天）；更早记录继续由 `archive/shadow_signals_archive.jsonl` 承接（`first_of_day_immutable_full_archive` 语义不变）；`shadow_target_days=60` **不变**。
3. **口径诚实性（强制）**：窗口内记录为**走前回算口径**（与既有 warmup/rolling 重算机制一致——在历史 bars 上按 `bars[:t-1]` 逐点走前计算），**非自然前向积累**；`consecutive_days` / `qualified` / `hit_rate` 等展示不得暗示"实盘连续观察"；`qualified` 文案建议「记录窗已满 60 交易日（走前回算）」（PM 入库）。
4. **连带更新**：`rolling_open_assets`（R2-08）随统计窗=60；`low_frequency_note` 文案与基线由 **PM 重定**（原「20 交易日约 11 资产」不再适用）。
5. **计算量与幂等**：60 日窗 ≈900 次走前单点训练 ≈15–17s CPU（启动首跑；实测锚 300 次/5.5s 线性外推）；幂等断言（`(date,code)` 跳过 / `created_at` 继承 / 先归档后重写）逐条保持；每日滚动建议保留快路径，必要时评估增量模式（见 10-r2 §13.4）。

## 自验收

- [x] 增量方式合规：只增补/变更 R2 相关条目，未重排、未重写全文；未变条目声明「沿用 v8」（§8）
- [x] 每个新/变字段有**类型 + 单位 + 精度 + 口径**；无驼峰；时间格式与时区沿用 v8
- [x] 新增枚举 8 组**穷举**，无"等"；单值枚举显式标注
- [x] 4 处实现超前契约待同步（V3/V11/V17/V18）逐条销项（§5）
- [x] `shadow_status` 取值域变更为唯一非"只加"项，显式登记（B1）并给前端映射
- [x] 数值三式可复算口径成文（§6：≥21/22 / (15+k)/22 / Δ + 实测基线）
- [x] 冻结纪律核对：K=4/p=0.25/MIN_N=15/BAND=0.02/双否决分位未改；E2/E4 未复活；永不做空未触碰；INSERT-ONLY 语义未破（recompute 先归档后重生成）
- [x] 新增黑名单 `baseline_method`；`/tasks` 参数不可改冻结口径
- [x] 未写实现代码（仅字段表与口径）；未修改 R1 既有工件；未触碰 `runtime/**`
- [x] 四项 open-issues 的契约落点：R2-01 算法（§3.4 双段+回退）、R2-02 排期（§5 不涉及字段）、R2-03 sina（无字段变更，行为在 08/10）、R2-04 边界（`verify_status`/`verify_note` 承接）
- [x] **v9.1 会签收敛**：D-1（`estimate_quality`/`official_summary` 主指标拆分）、D-2（`window_phase` 双时点）、D-3（评分对象改「同 mode 当日最后一条」）、D-4（`verify_review_date`/`pending_verification_names`）、R-1（`backfill_proxy_code`）、R-2（`sample_window` + horizon 成文）、R-3（`not_applicable`）、R-4（`conf_reason` 五值+优先级）、R-5（首测门槛/复评——§9.3-G1）逐条落 §9
- [x] **v9.1 不变式**：未改任何既有字段名；`conf_reason` 为值域收窄（1 值移除，已登记）；其余为新增/注记
- [x] **v9.2 注记**：BLOCK-1 口径澄清（T1 接通 / T3/T15 待填充；`formula` ↔ 定义一致；`baseline_status` 字面量重申）——**无字段/枚举变更**（09 §10）
- [x] **v9.3 注记**：C3 新增 `LedgerChain.chain_source` + 枚举 `chain_source`（穷举 2 值）；C1/C2 不改契约（09 §11）
- [x] **v9.4 注记**：F-6 方法名语义冻结（历史标识 + `top_n` 承担档位；**无字段变更**，09 §12）
- [x] **v9.5 注记**：影子盘窗口 20→60（`rolling_window_days`/`window_days` 固定值变更 2 处；走前回算口径诚实注记；running R2-08 文案 PM 重定；09 §13）

## 下游交接

- **主消费方**：`frontend-dev` / `backend-dev`（并行，严格按 **v9.1** 实现；v9.1 未覆盖处一律回读 v8）。
  - backend-dev：按 §7 机器核对表 + §9 逐项落字段；B1 做好 `shadow_status` 取值域切换（不得双输出）；`conf_reason` **五值 + 按序命中即停**（v9.1/R-4）；`QdiiCorrection` 双段算法按 §3.4（含对齐校验与回退不静默、首测门槛/复评 §9.3-G1）；`t1_real_method` 恒 `proxy_bar`、`backfill_proxy_code` 随行落盘（R-1）；精度条主指标 `estimate_quality.weighted_mae_rate`（D-1）；`estimate_quality`/`official_summary`/`window_phase` 按 §9.1；`fail_count` 停更展示值（保留累计）。改后重跑 `tests/` 全绿并把断言写回 `14-api-impl-report`（新版本）。
  - frontend-dev：U-01~U-12 按 `03-ui-design-v3.md` 逐项落地；`ValBadge` 双层编码 + 7 项 tooltip 读 `confidence/trace_text/mae_rate/dir_hit_rate/n_test/accuracy_window_days` + `trace[holdings].detail` 披露口径；unknown 读 `conf_reason`；HUD 读进度枚举；**vsum 主指标改读 `estimate_quality.weighted_mae_rate` + 官方档 chip（`official_summary`）**；复盘页 `scores[].sample_window` 注明"全样本窗"；覆盖面板读 `pending_verification_names` / `verify_review_date`；设置页持仓卡读 `main_source/import_*`。
- **次消费方**：`qa`。负向断言：`conf_reason` 仅在 unknown 时非 null；`baseline_source` 恒 `measured` 且 `0.5830` 零引用；`t1_real` 无来源不写（E_VALIDATION 维持）；recompute 后旧记录可在归档复读；`shadow_status` 不得出现 `idle/ok/bad`；`import_available=false` 时按钮禁用路径存在；`verify_status` 与 `tier` 自洽断言。
- **残留风险**（责任人 / 期限）：
  1. QDII 隔夜参照指数源（腾讯美股/港股指数符号）未实测 → 后端实现时探测确认；探测失败按 `overseas_unavailable` 回退单段（backend-dev，S3 开发首日）。
  2. `verify_batch_id` 批次号生成规则（`vb_YYYYMMDD_HHMM`）为架构约定 → 若与 R2-06 实际批次节奏不符，由 architect 版本 +1 修订（architect，S3）。
  3. `trace[holdings].detail` 的 `included_markets` 枚举值 `A/HK/US` 为约定 → 港股接入实测后若需增市场值，版本 +1（backend-dev + architect，S3）。
  4. V7~V13 因子机制口径未并入本契约（归 `21-factor-governance` 修订）→ 不阻塞 `/factors/*` 读取（architect，R2 末评估）。
- **未覆盖**：模块级实现设计（`08-backend-arch-r2`）、前端组件树（`07-frontend-arch-r2`）、算法伪代码细节（08）、会签问题清单（`10-arch-review-r2`）。
