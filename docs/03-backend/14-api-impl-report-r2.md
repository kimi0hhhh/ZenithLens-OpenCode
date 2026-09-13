---
artifact: 14-api-impl-report-r2
owner: backend-dev
version: v8
status: draft
supersedes: v7
created: 2026-09-12
reviewers: [dev-lead, qa, frontend-dev, architect]
gate: G-BE-02
---

# 接口实现报告 · R2 升级轮 · 契约 v9.1~v9.5（修复轮）

> 上游法律：`docs/01-architecture/09-api-contract-r2.md` **v9.5**、`docs/01-architecture/08-backend-arch-r2.md` **v3.2**、`docs/01-architecture/10-arch-review-r2.md` **v7**（§10 BLOCK-1 / §11 C1~C3 / §12 F-6 与 chain_source / §13 影子盘窗口 60）、`docs/04-integration/15-code-review-r2.md` **v4**、`docs/04-integration/16-fake-feature-audit-r2.md`、`docs/00-charter/02-prd-v3.md`、`docs/00-charter/00-dissection-v3.md`。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。R1 工件与 R1 报告（`14-api-impl-report.md` v10）未改动；本报告为 R2 增量（`-r2`）。
> 硬约束回顾：Python 3.8+ 纯标准库；`snake_case` 全项目统一；金额 Decimal/整数分；外部调用全部超时；INSERT-ONLY（重算=先归档后重生成）；冻结参数 K=4/p=0.25/MIN_N=15/BAND=0.02/双否决分位/0.30/3 不动；E2/E4 未复活；永不做空。
> 真机证据（2026-09-12 23:10–23:20 / 修复轮 2026-09-13）见 §5/§6/§9~§15；数据文件实测生成见 §4。

## 摘要

1. **四组模块级变更全部落地**：① 估值通道（全档 `mode|code` 误差通道 v2 / 前 20 重仓 + 港股 / QDII 双段 + 暂态回退 / 日留档 / 预算实现）；② 覆盖扩容（`verify_tiers` C→B 批次 + 三层判定 + 复查日 + 防稀释闸 / 台账 `recompute` 先归档后重生成）；③ 准确率出数（`data/cache/nav/<code>.json` 维护版净值史 / `t*_real` 自动回填 + 复算锚 / 20/60 归档合并 / 基线实测化 / 新模块 `review.py`）；④ 数据源治理（主源声明 / 新浪限定兜底 / `fail_window_7d` + 源事件日志）。新增 `review.py`，其余为既有模块扩展；未新增接口（55 个端点不变），`task_type` +2、`backfill_ledger.params.mode` +1。
2. **契约 v9.1 逐条对照**：§7 字段级 44 项 + §9.1 新增 9 项 + B1~B9 变更 9 项 + 枚举 9 组 + 任务 3 类，全部落位（§2 机器核对表）；未改任何既有字段名。**v9.2 注记**（BLOCK-1）按 §9 修复记录落实现。
3. **修复轮（S4 评审 → 架构终审）**：BLOCK-1（`/review/scores` T3/T15 口径）B1-1..B1-8 全量落地、BLOCK-2（测试污染）隔离修复 + 双跑无污染证据、SHOULD-1（`n_test<20` 挂档支路）随 B1-8 修复——见 **§9 修复记录**。
4. **测试全绿（双跑）**：`python -m unittest discover -s tests -p "test_*.py"` → **234/234 ×2**（R1 基线 117 + R2 轮次新增 117；19 个新增测试文件 + R1 文件内新增断言）；两轮之间 `proxy_quality.json` 等全部产线数据文件哈希不变（无污染，§9.2/§10.3/§11.6/§12.3/§13.4/§14.5/§15.6）。
5. **新数据文件 7 类落盘**（§4）：`nav/<22 只>.json`、`daily/valuation-*.jsonl`、`health-log.jsonl`、`review/tier_reviews.jsonl`、`review/qdii_review.jsonl`、`snapshot/proxy_quality.json`、`snapshot/review_scores.json`（+ `qdii_correction.json`；修复轮已按 B1-5 重生成）。
6. **偏差显式申报 9 条**（§7，无静默修改）；**缺陷修复留痕 2 起**（§8：首轮 `verify_tiers` 形状缺陷；§9：BLOCK-1/2 修复）。
7. **SHOULD 清理轮**（§10）：S2 新浪源 (b) 标注（回填既有 `note` 字段，未改契约；实测 `sina note="仅探测·非主链（近 7 日失败 6 次）…"`）；S3 冷启动 `/holdings` 阻塞修复（历史解析缓存 + 影子盘存在性快路径 + warmup 预热/缓存复用 + 阶段时间戳日志）——ready+1s / +6s / +15s 实测 0.33–0.45s（修复前最坏 39.7s），warmup 完成时间 +11.79s→+6.73s。
8. **S5 修复轮（dev-lead §8.10 后端栏 6 项）**（§11）：R2-D2 主源 path 回契约字面；R2-D3 同型互斥 409 + OSError 可读 + **跨型竞态确认后全局任务串行**；BLOCK-A3 `/ledger/chain` 读时同源重算六步（C1/C3/C4 过）；S-c `scan_factors` 去伪；S-e F10 top20 落到实际产物（5 只 active 全部 `top_n=20`、014320 纳入港股）；NIT D-8/B-5a/F-3 顺手修 + F-6 契约冲突申报（不改值）。
9. **C3 终局小步**（§12）：`LedgerChain.chain_source`（09-r2 **v9.3** §11 新增字段）落码——`stored`/`recomputed`/不可用 null，与 `chain_available` 一致性断言通过；**F-6 确认（09-r2 v9.4 §12）**：`method` 名维持 `eastmoney_f10_top10_weighted`（历史标识），档位以 `top_n` 如实（10/20）——**无需改名**。
10. **v9.5 影子盘窗口 60**（§13，用户指令）：`SHADOW_WINDOW_DAYS` 20→60（唯一常量源）；启动一次补满 60 日、此后每日滚动「来一天换一天」；**增量模式**落地（每日滚动 13.2s→**0.26s**）；沙箱首填 **12.57s**（900 条）；满窗 `qualified` 可达（`consecutive_days=60`、`window_days=60`）；二启冷启动 `/holdings` 0.27–0.43s 不劣于 S3 基线。
11. **断连噪声修复**（§14，用户反馈）：客户端刷新/取消导致的 `ConnectionAborted/Reset/BrokenPipe` 全链静默（`_send`/`_serve_static`/`_handle`/`handle_error` 四层兜底）；实测 stderr Traceback **36 行 → 0**；非断连异常仍 `print_exc + E_UNKNOWN`（不误吞）。
12. **F2 自碰撞伪影修复**（§15）：`_f2_independence`/`_incumbent_series` 按候选身份（含 `crowd6↔crowd` 别名）排除自比对；crowd6 重评 `max_collinearity 1.0→0.0127`（vs klow2）；记录更正**留痕**（`correction.from/to` + note，非静默）。

## 正文

### 1. 四组模块 × 变更 × 落点

| 组 | 变更 | 落点（文件/函数） |
|---|---|---|
| ① 估值通道 | 误差通道 v2（全档 `mode\|code`，D-3 评分对象，40 日滚动窗，n≥5 出统计） | `valuation.build_accuracy` / `accuracy_for` / `_confidence_of` |
| | `conf_reason` 五值按序命中即停（读取层） | `valuation.conf_reason_of` / `_missing_conf_reason`；`public_valuation` 透出 |
| | 官方档显式口径（published≈0 / stale-anchor 照常参与） | `valuation.build_accuracy`（真值=`nav(D)/nav(D−1)−1`，不排除官方档） |
| | 前二十大重仓（topline=20，缓存记 `top_n`，回退如实标注）+ 港股符号 + 美股不计 | `estimator.eastmoney_top_holdings(topline=20)` / `tencent_symbol`（5 位→`hk`）/ `market_of_code` |
| | `detail.{top_n, included_markets, excluded_count}` | `valuation._weighted_holdings` |
| | QDII 双段（加法拼接 + 对齐校验 + 回退矩阵 + 首测门槛/复评 + alignment 计数） | `valuation.qdii_estimate` / `_aligned` / `evaluate_qdii_review` / `append_qdii_review`；`estimator.overseas_ref_quote`（实测 `usNDX`/`hkHSI`） |
| | 日留档（幂等、一文件一快照日、收盘后触发、字段穷举） | `valuation.archive_daily`；双触发：`maintain_nav_history` + `refresh_all` |
| | 预算实现（T-01，删除 `pass` 死代码） | `valuation.refresh_all`（`budget:{exceeded,processed,skipped}` 入 snapshot；stderr warn） |
| ② 覆盖扩容 | C→B 验证批次 + 三层判定 + 复查日 +30 交易日 + 防稀释闸 | `factor_engine.verify_tiers` / `review_verdict` / `_tier_review_evidence`；`data/review/tier_reviews.jsonl` |
| | 验证状态幂等应用（tier/tier_reason/verify_*） | `holdings.apply_tier_reviews` / `sync_proxy_fields`（锁定降档/挂档行）/ `VERIFY_STATUS_LABEL` |
| | 台账按现档位重算（先归档后重生成 + created_at 继承 + 差异摘要 + 0 冲突） | `ledger_api.recompute_shadow_window` / `_archive_records(reason, extra)` |
| | 开口低频口径 | `ledger_api.rolling_open_stats`；`fund_predict.signal_state` |
| ③ 准确率出数 | 维护版净值史（lsjz 分页增量 + 首值冻结 + 失败保旧） | `estimator.lsjz_history`；`valuation.maintain_nav_history` / `load_nav_history` / `nav_pair` |
| | `t*_real` 自动回填 + 复算锚 | `ledger_api.backfill_due` / `write_backfill(method, proxy_code)` / `_apply_backfill` |
| | 20/60 归档合并（`consecutive_days`/`gap_days`/`history_days`/`archive_merged`） | `ledger_api._merged_all` / `shadow_progress` / `shadow_ledger` / `shadow_audit` |
| | 基线实测化（删 `BASELINE_RATE`） | `ledger_api.measured_baseline`；`engine.frozen_params.baseline_method` |
| | `/review/scores` 真实化（新深模块） | `review.py`（`scores` / `build_review_scores` / `_shadow_live`）；`app.h_review_scores`；warmup + `run_backtest` 生成缓存 |
| | `/factors/score-chain` V11 销项 | `factor_board.score_chain`（R1 已实现 `bootstrap_percentiles_measured`/`real_engine`，R2 维持只加不改） |
| ④ 数据源治理 | 主源声明 + 空态 + 导入禁用路径 | `holdings.ensure_holdings` / `main_source_status` / `import_source_status`；`app.h_settings_holdings_data` |
| | 新浪限定兜底（proxy 档 + 个股批量；5s/重试 0/留痕） | `estimator.sina_rt_quote` / `sina_rt_quotes`；`valuation.value_fund` 档4；`estimator.eastmoney_top_holdings` 报价段 |
| | 失败窗口 + 源事件日志 | `settings.record_source` / `get_health` / `_fail_window` / `_append_health_event`；`data/health-log.jsonl` |
| | T-05 合一（F10 解析器只此一份） | `proxy_map.parse_f10_holdings` 委托 `estimator.parse_top_holdings`（兼容别名） |

### 2. 契约 v9.1 机器核对表（逐项）

#### 2.1 字段级 44 项（§7.1）

| # | 落点 | 实现位置 | 一致性 |
|---|---|---|---|
| 1-8 | `HoldingRow.{fund_type, fund_type_label, tier_reason, verify_status, verify_status_label, verify_batch_id, verify_note, qdii_lead_note}` | `fund_predict.build_holding_row`（+`holdings.VERIFY_STATUS_LABEL`/`QDII_LEAD_NOTE`） | ✅ 8/8，类型/枚举一致 |
| 9-12 | `Valuation.{fund_type, fund_type_label, conf_reason, qdii_correction}` | `valuation.public_valuation` / `conf_reason_of` / `value_fund` | ✅ 4/4；`conf_reason` 仅 unknown 非 null |
| 13 | `TraceStep.detail`（键恒在；holdings 步穷举键） | `valuation._weighted_holdings` → `value_fund` trace | ✅ 键恒在；非 holdings 步 null |
| 14-16 | `CoveragePanel.{prediction_universe_count, pending_verification_count, prediction_coverage_note}` | `app.h_holdings_coverage` | ✅ 实测 15 / 7 / 「预测覆盖 15/22（+7 待结论）」 |
| 17-19 | `SignalState.{rolling_open_assets, rolling_window_days, low_frequency_note}` | `fund_predict.signal_state` + `ledger_api.rolling_open_stats` | ✅ 实测 11 / 20 / 文案含「约 11 资产」 |
| 20 | `PredictionSummary.qdii_lead_note` | `app._prediction_public`（`/predictions` 与 `/predictions/{code}` 共用） | ✅ 仅 QDII 非 null（测试 `PredictionQdiiLeadNoteTest`） |
| 21-24 | `ShadowProgress.{window_days, archive_merged, history_days, baseline_source}` | `ledger_api.shadow_progress` | ✅ 20 / bool / int / `"measured"` |
| 25 | `ShadowAudit.baseline_source` | `ledger_api.shadow_audit` | ✅ 恒 `measured` |
| 26 | `FrozenParams.baseline_method` | `engine.frozen_params` | ✅ 契约固定文本 |
| 27-29 | `DataSourceHealth.{fail_window_7d, fail_window_days, recent_failures}` | `settings.get_health` | ✅ 自然日窗口 7、≤10 条 `{at,note}` |
| 30-32 | `HoldingsDataSource.{main_source, import_available, import_disabled_reason}` | `app.h_settings_holdings_data` + `holdings.main_source_status`/`import_source_status` | ✅ 实测 count=22 / false / 可读原因 |
| 33 | `LedgerEntry.t1_real_method` | `ledger_api._apply_backfill`/`_decorate` | ✅ 未回填 null；回填恒 `proxy_bar` |
| 34-35 | `ShadowLedger.{backfill_method, backfill_method_note}` | `ledger_api.shadow_ledger` | ✅ 恒 `proxy_bar` + 长文 |
| 36 | `/engine/status.shadow_audit_status` | `app.h_engine_status` | ✅ `idle/ok/bad`；`shadow_status` 进度枚举 |
| 37-40 | `/review/scores.hero.{open_count, sample_period, data_kind}` + 响应 `note` | `review._hero_of` / `build_review_scores` / `_shadow_live` | ✅ 实测 T1 open 61 / period 2025-05-26..2026-06-22 / backtest |
| 41-42 | `/valuations/precision.{window_filled_days, window_status_label}` | `valuation.precision_summary` / `window_filled_days` | ✅ 实测 0 /「累计 0/40 日」（首日 warming，如实） |
| 43-44 | `/factors/score-chain.{bootstrap_percentiles_measured, real_engine}` | `factor_board.score_chain`（R1 已落，V11 销项确认） | ✅ 兄弟字段并存，常量未删 |

#### 2.2 v9.1 新增 9 项（§9.1）

| # | 落点 | 实现 | 一致性 |
|---|---|---|---|
| 1 | `/valuations/precision.estimate_quality` | `valuation.precision_summary`（估算档 intraday/holdings/proxy 分组 + 主指标） | ✅ 键：groups/weighted_mae_rate/count/market_value/weight_ratio/industry_baseline_mae_rate/window_days/window_filled_days/note |
| 2 | `/valuations/precision.official_summary` | 同上（官方档单列，note 含「既成事实」） | ✅ 不参与主指标 |
| 3 | `/valuations/precision.window_phase` | `valuation.window_phase`（warming/first_verdict/mature） | ✅ 实测 warming |
| 4 | `HoldingRow.verify_review_date` | `holdings.apply_tier_reviews` | ✅ 挂档 `2026-10-23`（+30 交易日） |
| 5 | `CoveragePanel.pending_verification_names` | `app.h_holdings_coverage` | ✅ ≤10 只，实测 7 只 |
| 6 | `LedgerEntry.backfill_proxy_code` | `ledger_api._apply_backfill` | ✅ 回填行随行落盘（R-1） |
| 7 | `ReviewScore.sample_window` | `review.py`（恒 `full`） | ✅ 三行均显式 `full` |
| 8 | 枚举 `accuracy_window_phase` | `valuation.window_phase` | ✅ 三值穷举 |
| 9 | `verify_status` 增值 `not_applicable` | `holdings._default_verify_status`（D①「暴露待定」） | ✅ D② 仍 `validation_failed` |

#### 2.3 变更 9 项（§1.2 B1~B9）

| # | 落点 | 实现 | 状态 |
|---|---|---|---|
| B1 | `shadow_status` 取值域（进度枚举）+ `shadow_audit_status` | `app.h_engine_status` 用 `shadow_progress().status` | ✅ 实测 `recording`；无 idle/ok/bad 于 shadow_status |
| B2 | `consecutive_days`/`gap_days` 归档合并 | `ledger_api._merged_all` + calendar union | ✅ 测试可达 >20；缺失归档降级标注 |
| B3 | `baseline_rate` 实测 | `measured_baseline`；progress/ledger/audit 全改 | ✅ 实测 0.5559（shadow_live T1） |
| B4 | `covered_count` 口径文字同步 | `fund_predict.holdings_summary`（R1 已 `change_rate != null`，R2 维持） | ✅ 与 PRD F-01 一致 |
| B5 | `/review/scores` 真实输出 | `review.scores` 全链 | ✅ 实测 backtest/shadow_live 均出数 |
| B6 | `/settings/holdings-data` 语义降级 | `main_source` 新增；`primary_*` 保留 | ✅ 实测 |
| B7 | `POST /ledger/backfill.entries[].method` | `ledger_api.write_backfill`（缺省 `proxy_bar`） | ✅ 非法 method → E_VALIDATION（测试） |
| B8 | 冻结黑名单 + `baseline_method` | `app.FROZEN_PARAM_KEYS` | ✅ 出现即 E_VALIDATION（测试） |
| B9 | `ShadowLedger.field_list` 追加 | `ledger_api.FIELD_LIST`（15 键固定穷举，含 `t1_real_method`/`backfill_proxy_code`） | ✅ 实测 field_list 与契约逐字一致 |

#### 2.4 枚举（9 组穷举）/ 任务（3 类）/ 注记（2 项）

| 项 | 实现位置 | 备注 |
|---|---|---|
| `fund_type` | `estimator.classify_fund_type` + `FUND_TYPE_LABEL` | R1 落地，R2 沿用 |
| `verify_status` 五值 | `holdings.VERIFY_STATUS_LABEL` | 含 `not_applicable`（R-3） |
| `conf_reason` 五值 | `valuation.conf_reason_of` | 按序命中即停；无 `pending_backfill`（R-4/M2） |
| `backfill_method` 单值 | `ledger_api.BACKFILL_METHODS` | 恒 `proxy_bar` |
| `baseline_source` 单值 | `measured_baseline` 调用链 | 恒 `measured` |
| `ledger_refresh_mode` | `app.LEDGER_REFRESH_MODES` + `_run_task` | incremental 缺省 |
| `qdii_correction_method` 单值 | `valuation.qdii_estimate` | `etf_close_plus_overnight` |
| `qdii_fallback_reason` 三值 | `qdii_estimate` 回退矩阵 | overseas_unavailable / alignment_conflict / first_test_failed |
| `accuracy_window_phase` 三值 | `valuation.window_phase` | warming/first_verdict/mature |
| 任务 `maintain_nav_history` / `verify_tiers` | `app.TASK_TYPES` + `_run_task` | 均实测跑通 |
| `backfill_ledger.params.mode` | `app.validate_task_payload` + `_run_task` | recompute 先归档后重生成 |
| G1 QDII 门槛/复评 | `evaluate_qdii_review`（n_test≥20 才判定；复评日预注册；带数字） | 实测 5 只 hold（n_test=0） |
| G2 `domestic.as_of`≡`overseas.trade_date` | 命名未动；语义等价已在字段注释 | 不重命名 |

#### 2.5 端点行为增量（§4）实现对照

| 端点 | 行为 | 实测/测试 |
|---|---|---|
| `GET /review/scores` | backtest=生产配置六窗走前缓存；shadow_live=台账合并+实测基线；未接通 pending+null | ✅ 见 §5；`test_review_scores.py` 6 条 |
| `GET /valuations/precision` | 主指标拆分 + 双时点；全档参考保留 | ✅ 键/语义一致；`test_accuracy_channel.py` |
| `GET /holdings/coverage` | universe/pending/note/names | ✅ 实测 15/7/文案；`test_tier_review.CoveragePendingTest` |
| `GET /signals/state` | 滚动开口 + 低频文案 | ✅ 实测 11/20；断言在 `test_shadow_progress_archive.py` 邻近 |
| `GET /settings/holdings-data` | main_source/import_* | ✅ `test_holdings_main_source.py` 4 条 |
| `GET /engine/status` | 进度/审查分离；合并口径 | ✅ `test_shadow_status_contract.py`（R1）继续全绿 + `test_shadow_progress_archive.py` |
| `GET /ledger` / `/ledger/shadow` / `/review/reconciliation` | `t1_real_method`/`backfill_proxy_code`/`backfill_method*` | ✅ `test_backfill_real.py` 4 条 |
| `POST /ledger/backfill` | `method`/`proxy_code` 可选 | ✅ 同上 |
| `POST /tasks` | +2 类型；mode；黑名单 | ✅ `test_tier_review.py` / `test_holdings_main_source.py`（E_VALIDATION 路径） |
| `GET /factors/score-chain` | V11 兄弟字段并存 | ✅ 只读确认（R1 已实现） |

### 3. 估值通道细节（R2-01/02/03/05）

- **误差通道 v2**（`valuation.build_accuracy`）：键 `mode|code`；评分对象=每个 `(date, code, mode)` 当日最后一条（`written_at` 最大，D-3）；真值 `nav(D)/nav(D−1)−1`（nav_store 权威，回退 `holdings.nav_history` 并记 `source`）；滚动窗=最近 40 个可配对日；`n≥5` 出 `mae_rate/dir_hit_rate`，否则统计值 null（`n_test`/`matched_days` 保留，供 `window_filled_days` 与 `no_samples` 判定）。
- **`conf_reason`**：仅 `confidence=unknown` 非 null；序 ①`mode_unknown` ②`budget_exceeded`（snapshot.budget.skipped）③`valuation_missing` ④`nav_missing`（净值对缺）⑤`no_samples`（n<5），命中即停。
- **前 20**：`eastmoney_top_holdings(topline=20)`；缓存记 `top_n`，重抓失败用旧缓存并如实标注（N-2）；`_weighted_holdings` detail 增 `top_n/included_markets/excluded_count`（实测 active 5 只均 holdings 档）。
- **QDII 双段**：`domestic=境内代理 ETF 最近已收盘段`，`overseas=estimator.overseas_ref_quote(market)`（实测符号 `usNDX`/`hkHSI` 可用；5s/重试 0）；`applied=true` ⇔ 对齐校验通过（`overseas.trade_date > domestic.as_of`，同日比 15:00）；回退三理由穷举且不静默；`first_test_failed` 暂态（复评日预注册，门槛 40 日窗且 n_test≥20）；`alignment_conflict` 事件去重落 `qdii_review.jsonl`（≥5/40 日 → 人工复核事件）。
- **范围如实**：`market_of` 枚举 {US_NDX, HK_HSI}；`163208`（油气）不启用双段（见 §7 偏差 D1）。
- **日留档**：每基金 1 行，字段穷举，文件已存在即返回 0（幂等），盘中不写。
- **预算**：`TOTAL_BUDGET_SEC=20s`，非 force 超时停止；跳过者回退当日已存在记录或短 `skipped` 列表，读取层给 `budget_exceeded`。

### 4. 存储布局与实测数据文件

| 路径 | 状态 | 实测 |
|---|---|---|
| `data/cache/nav/<code>.json` | ★新增 | 22 只（lsjz 分页 ≤250 点，首值冻结）；`fund_official.json`/`fund_valuation.json` 沿用不冲突 |
| `data/snapshot/daily/valuation-YYYYMMDD.jsonl` | ★新增 | `valuation-20260912.jsonl`（22 行，收盘后写，写完只读） |
| `data/health-log.jsonl` | ★新增 | 38 事件（成功/失败均记） |
| `data/review/tier_reviews.jsonl` | ★新增 | 22 行（15 批次行 + 7 修正行；含 1 条 `dilution_gate_alert`） |
| `data/review/qdii_review.jsonl` | ★新增 | 6 行（5 只 hold + 1 条首测事件流） |
| `data/snapshot/proxy_quality.json` | ★新增 | 22 条条目（bars×nav 史重建，与 `accuracy.json` 分键分文件） |
| `data/snapshot/review_scores.json` | ★新增 | 3 horizon 回测缓存（可重建，整文件原子替换） |
| `data/qdii_correction.json` | ★新增 | 开关/复评预注册（默认 enabled=true 待首测；实测 last_review=hold） |
| `data/snapshot/accuracy.json` | 结构 v2 | 首日 `{}`（历史记录仅 2026-09-12，nav 仅至 09-11，无配对 —— 如实空，非缺陷） |

### 5. 数值验收实测（§6 三式）

| # | 口径 | 结果 | 说明 |
|---|---|---|---|
| G2-01 | 非 unknown ≥21/22 | 首日 `window_filled_days=0`（warming）；`conf_reason` 逐只可读（005857 实显 `nav_missing`） | 首日无配对日（记录 09-12 vs 净值 09-11），按验收附则「上线首日按实测 n_test 如实显示」；双时点：首判=满 5 可配对日 |
| G2-02 | vsum 主指标非 null | `estimate_quality.weighted_mae_rate` 当前 null（无 mae 样本）；`groups`/`official_summary` 已单列 | 同上首日 |
| G2-04 | 覆盖按实计 | `/holdings/coverage`：`prediction_universe_count=15`、`pending=7`、「15/22（+7 待结论）」 | 批次后 7 只全部低样本挂档（非降档），k=0 |
| G2-06 | Δ 可复算 | backtest：T1 0.5263 vs 0.5415 → Δ −0.0152（open 61）；**T3/T15 一律 `pending` + null + open_count=0**（v9.2 接通范围=T1，§9.1）；shadow_live T1 1.0/0.5559 → +0.4441 | `sample_period=2025-05-26..2026-06-22`；复算入口 `review.build_review_scores`（同 bars+冻结配置+seed 可复现） |
| G2-07 | 0.5830 退役 | `ledger_api` 无 `BASELINE_RATE`；`measured_baseline`；仅 `engine.frozen_params.baseline_method` 契约固定文本含该 token | grep 产线代码：无计算引用（§16 冻结纪律） |
| G2-08 | 连续记录可达 | `history_days=20`、`archive_merged=false`（当日尚无归档，如实） | 合并算法测试可达 65 日（`test_shadow_progress_archive.py`） |
| 批次 | 7/7 结论 | 7×`hold`（indep 0/4/2/2/3/3/6 <20），复查日 2026-10-23，防稀释闸触发 | 证据=production backtest full 窗；`review_verdict` 层① |

### 6. 测试证据

`python -m unittest discover -s tests -p "test_*.py"` → **Ran 211 tests × 2 … OK**（R1 117 + R2 轮次新增 94；两轮均通过，见 §9.2/§10.3/§11.6 无污染证据）。

| 测试文件（R2 新增，19 个） | 断言要点 | 条数 |
|---|---|---|
| `test_accuracy_channel.py` | 全档键 / D-3 同 mode 最后一条 / 官方 stale-anchor 参与 / conf_reason 按序命中即停 | 6 |
| `test_qdii_correction.py` | 加法拼接 / 三类回退 + 不静默 / 同日钟点 / bar 不足 null / PredictionSummary 标注 | 8 |
| `test_proxy_quality.py` | bars×nav 重建可复算 / 分键分文件 / 无证据 n=0 不编造 | 3 |
| `test_qdii_review.py` | 门槛挂档 / first_test_failed 暂态带数字 / pass 保留 / conflict≥5 复核 | 4 |
| `test_nav_history_contract.py` | 分页 / 增量停页 / 首值冻结 / 失败保旧 / **真实数据零触碰守卫（B2）** | 4 |
| `test_backfill_real.py` | 到期写值+method+proxy_code / 重复零写 / 无 signal 拒绝 / 非法 method | 4 |
| `test_shadow_recompute.py` | 先归档后重生成 / created_at 继承 / 幂等零写 / 0 档位冲突 | 2 |
| `test_shadow_progress_archive.py` | 合并 >20 可达 65 / 归档缺失降级 / measured 口径 / **v9.5：window=60 + qualified 可达 + 走前口径披露** | 4 |
| `test_baseline_measured.py` | 公式 / N=0 null / 常量退役 / Δ 复算 | 4 |
| `test_review_scores.py` | **T1 filled / T3/T15 pending+null+0（B1-1/5）/ formula 随定义（B1-2）/ 枚举无 ok（B1-3）/ note 口径（B1-4）/ hero 一致（B1-6）** / 缓存可重建 / 非法 kind / shadow_live / **cache_fresh（S3）** | 9 |
| `test_health_window.py` | 窗口滚动 / 成功不抹除 / ≤10 条 / 544 不作当前状态 / **S2 新浪标注 3 条** | 7 |
| `test_holdings_main_source.py` | 空态不抛 E_IO / main_source（**D2 契约字面 path**）/ 导入禁用原因 | 4 |
| `test_sina_fallback.py` | 腾讯失败→新浪 / 双失败降级 / 批量仅 A 股（重试 0，**record_source 隔离 B2**）/ 重仓批量兜底 | 5 |
| `test_tier_review.py` | 三 verdict / **n_test<20 挂档（B1-8）/ samples 死参数移除（NIT-1）** / 复查日 +30 交易日 / 降档 tier_reason / 挂档不入 universe / 防稀释 + 生产回测形状回归 | 10 |
| `test_f10_top20.py` | top_n=20 / 港股解析 / 回退如实标注 / excluded_count / **F-6：method 恒定 + top_n∈{10,20}** | 5 |
| `test_history_cache_contract.py` | **S3 历史缓存：重复读单次解析 / 热追加不重解析 / 外部写失效 / 筛选与副本语义** | 4 |
| `test_ledger_chain_recompute.py` | **A3：C1 六步+顺序+exit 0.52+行内对账 / C3 可重算性⇔六步 / C4 sha256 不破 / E_NOT_FOUND / chain_source 三态（stored/recomputed/null）** | 5 |
| `test_disconnect_quiet.py` | **断连族：`_send`/`_serve_static`/`_handle`/`handle_error` 四层静默不打印；非断连异常照抛 + E_UNKNOWN 信封；真起服 RST 风暴零 Traceback** | 9 |
| `test_f2_selfcollision.py` | **F2 自比对排除（含别名 crowd6↔crowd）；真共线仍拒绝（负向）；crowd6/klow2 全栈不回归** | 8 |

> R1 既有 12 个测试文件全部保持通过（原有用例无回归；其中 3 个文件在本轮各追加断言：`test_shadow_backfill_contract` +1、`test_app_contract` +5、`test_factor_arena_contract` +3）；测试均为标准库 unittest、确定性、零联网（外部调用以 mock 替换）。R2 轮次累计新增 117 条（初始 67 + BLOCK 修复轮 6 + SHOULD 清理轮 9 + S5 轮 12 + C3 小步 2 + v9.5 轮 4 + 断连修复轮 9 + F2 修复轮 8）。

### 7. 偏差与实现选择申报（禁静默）

| # | 项 | 内容 | 处置/建议 |
|---|---|---|---|
| D1 | `163208` 油气 QDII 双段未启用 | 参照指数不在 {US_NDX, HK_HSI} 枚举（`market_of`=None）→ `qdii_correction=null`，走既有 proxy 链 | 契约 §3.4 注「163208 参照可得则做」；实现为暂不做。若需做，请架构师增枚举/符号（版本 +1） |
| D2 | 首轮 `verify_tiers` 缺陷（已修复，留痕） | 证据收集传 `{code: bars}` 形状致 `evaluate` 抛错 → 7 只误走一票否决降 D；修复为 `[(code, bars)]` + `_normalize_bars` 兼容 dict + 回归测试 | 修正行已追加（INSERT-ONLY，不改旧行）；数据恢复 C/validating/复查日；详见 §8 |
| D3 | accuracy 条目在 n≥1 即写（统计值仍 n≥5） | 写 entry 是为保留 `matched_days`（`window_filled_days`/`no_samples` 依赖），`mae_rate/dir_hit_rate` 在 n<5 时为 null | 与「n<5 不产出统计」一致；口径注记 |
| D4 | 挂档 `verify_status` 取值 | 批次已跑 → 取 `validating`（契约允许 pending_validation/validating 二者） | 已登记 |
| D5 | `budget_exceeded` 依赖当日 snapshot.budget | 跨日/快照丢失时按序 3 落 `valuation_missing` | 序内行为，已注释 |
| D6 | top20 默认值变更 | `eastmoney_top_holdings` 默认 `topline` 10→20（08-r2 §3.2 R2 启用 20） | 旧调用方获 20；如个别场景需 10，显式传参 |
| D7 | `verify_tiers` 默认 targets = 当前 C 档 | C 档为空 → 空批次（返回 0 只）；R2-04 复核须显式传 9 只清单 | 契约已述 targets 语义 |
| D8 | `daily` 留档首日仅 `20260912` | 归档仅在有当日记录且非盘中时写入；跨日累积由调度保证 | 量级 ≤10KB/日，R2 末复核（architect+backend-dev） |
| D9 | `data/cache/nav/` 混合文件名 | R1 的 `fund_official.json`/`fund_valuation.json` 与 R2 `<code>.json` 同目录 | 文件名不冲突；R3 可做目录细分（登记） |

### 8. 缺陷修复留痕（首轮 verify_tiers）

- **现象**：首轮批次（23:16:08）7 只同秒返回、全部 `downgrade`、`evidence.has_data=false`。
- **定位**：`_tier_review_evidence` 传 `{code: bars}`，`_normalize_bars` 将 dict 键当元素 → `_union_calendar` 对 str 调 `.get` 抛 `AttributeError` → 被兜底 `except` 吞掉 → 走一票否决。
- **修复**：① 调用改 `[(code, bars)]`；② `_normalize_bars` 增加 dict 形态支持（防御）；③ 新增 `ProductionBacktestIntegrationTest`（两种形状均须 `sample_days>0`）。
- **数据修复**（INSERT-ONLY）：第二轮批次（显式 7 只清单）真实结论为 7×`hold`（indep 0/4/2/2/3/3/6）；因旧行已将 tier 置 D，追加 7 条修正行（`tier_before=C→C`、`correction_of=旧批次`）并 `apply_tier_reviews()` 恢复；随后 `apply_tier_reviews()` 幂等返回 0。
- **残留**：`tier_reviews.jsonl` 保留首轮 7 条错误行（审计），最新行口径正确（读端取 last per code）。

### 9. 修复记录（BLOCK-1 / BLOCK-2 / SHOULD-1 · 2026-09-13）

> 依据：`10-arch-review-r2.md` v4 §10（BLOCK-1 终审 + B1-1..B1-8 派发指令）、`09-api-contract-r2.md` v9.2 §10（口径注记）、`15-code-review-r2.md` §3（BLOCK-1/2 + SHOULD-1/NIT-1）。
> 范围纪律：只改后端 `*.py` 与 `tests/**` 与本报告；契约/架构/前端/QA 工件未改；`runtime/**` 未触；未做清单外重构。

#### 9.1 B1-1..B1-8 逐条落地

| # | 修复项 | 改动文件/函数 | 证据（命令/结果断言） |
|---|---|---|---|
| B1-1 | 仅 H=1 评估；T3/T15 一律 `_pending_row` | `review.build_review_scores`（移除 H∈{3,15} 的 evaluate 调用；仅 `production_definition(1)` + `evaluate`） | `test_review_scores.test_t1_filled_and_t3_t15_pending`：T3/T15 `pending` + 三值 null + `open_count=0`；冒烟 10/10 PASS |
| B1-2 | `formula` 与计算定义绑定 | `factor_engine.production_definition` 增 `formula="gate+ddsm+veto"`；`review._formula_of` 从定义取值 | `test_formula_binds_to_computing_definition`（注入变体 `gate+ddsm+veto+test_variant` → T1 行随变体变化） |
| B1-3 | `baseline_status` 枚举 `filled/pending`（禁 `ok`） | `review.py` 三处字面量 | `test_baseline_status_enum_no_ok`：响应全文无 `"baseline_status": "ok"`；枚举穷举 |
| B1-4 | 响应 `note` 口径（pending_cv / 待验证） | `review.T3_T15_NOTE`（build/无缓存/shadow_live 三处 note 追加） | `test_note_mentions_pending_cv_and_transition`：note 含「pending_cv」「待验证」；冒烟断言 |
| B1-5 | 缓存重生成 | `data/snapshot/review_scores.json` 以新结构重新生成（仅 H=1） | 缓存内容见 §9.3-2；`/review/scores` 与缓存逐字段一致 |
| B1-6 | hero 与 T1 值/状态双一致 | `review._hero_of`（由 `scores[0]` 派生） | `test_hero_consistent_with_t1`：hit/baseline/delta/open/sample_period/data_kind 全等；无缓存时 hero 走 pending 文案（不填估计值） |
| B1-7 | 回归测试增补 + 全量证据 | `tests/test_review_scores.py`（8 条） | 双跑 190/190 ×2 OK（§9.2）；T3/T15 pending 复核（缓存 + 冒烟） |
| B1-8 | 层①补 `n_test<20`；删死参数 `samples`（SHOULD-1/NIT-1） | `factor_engine.review_verdict(evidence)` 单参 + `n_test` 支路；`_tier_review_evidence` 补 `evidence["n_test"]`（取代理质量证据道） | `test_n_test_branch_holds`（indep=30 且 n_test=15 → hold；n_test=20 → pass；n_test=None 向后兼容）；`test_dead_samples_param_removed`（签名 `["evidence"]`） |

> B1-1 适用范围按 v9.2「接通范围 = T1」端点级执行：`backtest` 与 `shadow_live` 的 T3/T15 行均为待填充——shadow_live 即使 `t3_real` 已回填也不出数（其计算为「T1 信号 H 期收益」，与 `gate_only/gate+ddsm` 定式不符，属同一类标签/计算分叉）。已由 `test_shadow_live_t1_filled_t3_t15_pending` 锁定；若架构/PM 认为实盘 t*_real 口径应出数，走契约版本 +1 再启。

#### 9.2 B2 测试污染修复（隔离 + 双跑无污染证据）

- **根因修复**：`test_nav_history_contract` setUp/tearDown 增 `valuation.PROXY_QUALITY_PATH`（及 `SNAPSHOT_PATH`）指向临时目录；`maintain_nav_history` 全链不再能覆写真实证据道。
- **全量审计（27 个测试文件）后同批隔离**：
  1. `test_sina_fallback`：`settings.record_source` 置 no-op（原会以假事件写真实 `data/health.json` + `data/health-log.jsonl`）；
  2. `test_ledger_contract` / `test_shadow_status_contract` / `test_baseline_measured` / `test_review_scores`：补 `ARCHIVE_DIR`/`ARCHIVE_SIGNALS_PATH`/`ARCHIVE_MANIFEST_PATH` 读隔离（防真实归档混入合并集断言）；
  3. 其余写入源（factor 账本与缓存、估值 history/accuracy、health、holdings、qdii）经审计已隔离或只读——未发现新的真实路径写入。
- **双跑无污染证据**（先后两次全量 discover，之间对 12 个产线文件做 SHA-256 前后断言）：
  - `run1 rc=0 Ran 190 tests … OK`；`run2 rc=0 Ran 190 tests … OK`；
  - `proxy_quality.json`（sha256 `8c31b80ef53abfcd…`）：run1 前后一致、run2 前后一致；
  - 监控集全体（`proxy_quality / review_scores / accuracy / valuation_history / health / health-log / holdings / qdii_correction / tier_reviews / qdii_review / shadow_signals / backfill`）两轮前后 **零差异**。
- **防再生守卫**：新增 `test_nav_history_contract.test_suite_guard_real_data_paths_untouched`——在隔离路径下执行 `maintain_nav_history` 全链，断言真实 `PROXY_QUALITY_PATH / HISTORY_PATH / ACCURACY_PATH / SNAPSHOT_PATH / DAILY_DIR / NAV_STORE_DIR / LEDGER_DIR` 快照（存在性 + 内容哈希/目录清单）前后相等。

#### 9.3 修复后验证证据

1. **测试双跑**：190/190 × 2（2026-09-13 00:2x；R1 117 + R2 73；修复轮净增 6 条）——BLOCK 修复轮完成时点；SHOULD 清理轮后为 **199/199**（见 §10.3）。
2. **缓存重生成**（B1-5）：`review.build_review_scores()` → `generated_at=2026-09-13T00:23:54+08:00`；
   `scores = [T1 gate+ddsm+veto / filled / 0.5263 / 61, T3 gate_only / pending / null / 0, T15 gate+ddsm / pending / null / 0]`；
   `hero = {hit_rate:0.5263, baseline_rate:0.5415, delta_pp:-0.0152, open_count:61, data_kind:backtest}`；note 含 `pending_cv` + 「待验证」。
3. **起服冒烟**（自寻 OS 空闲端口 54191；`/engine/status.pid == 拉起进程 PID 31092` 证明服务进程身份）：`/health ok`；`backtest` 断言 **10/10 PASS**；`shadow_live` **8/8 PASS**（T3/T15 pending；hero==T1；无 `"ok"` 字面量）；关闭后端口释放 `True`。
4. **端口说明**：本机 8791/8792/8793/8794 等端口被 ZCode universal-demo harness 预占（监听进程为 `runtime/server.py`，非 `app.py`）→ 冒烟改用 OS 分配空闲端口 + PID 身份核对，避免「打到别的服务」的伪证。

### 10. 修复记录（SHOULD 清理轮：S2 新浪源标注 / S3 冷启动预热 · 2026-09-13）

> 依据：`10-arch-review-r2.md` §2 裁定③（新浪=限定兜底；长期不可用按 (b) 标注降级，「由后端实测决定，结论回填健康页」）、`08-backend-arch-r2.md` §6.3 加严②；`15-code-review-r2.md` §3 SHOULD-2/SHOULD-3。
> 范围纪律：只改后端 `*.py` 与 `tests/**` 与本报告；**未改契约字段**（S2 回填既有 `DataSourceHealth.note`）；`runtime/**` 未触；未引入第三方依赖。

#### 10.1 S2 · 新浪源 (b) 标注（不改契约字段）

| 项 | 内容 |
|---|---|
| 承载字段 | `DataSourceHealth.note`（既有字段；**未新增/未改名字段**） |
| 判定（`settings._sina_degraded`） | 任一命中即标：① 连续失败 ≥3（事件尾部）；② 近 7 自然日失败 ≥3 次；③ 最近事件失败且距最近成功 ≥7 日（无成功记录按首次失败起算）。条件衰减/恢复后自动摘除（保留原 note；原因随实测刷新） |
| 文案 | `仅探测·非主链（<原因>）；<原 note>`（原因示例：`近 7 日失败 6 次`） |
| 可测化注记 | 适配层未捕获 HTTP 状态码（`http_get` 统一返回 None）；「4xx 持续 7 天」以「近 7 日失败 ≥3 次」可测化近似（不区分 4xx 与网络失败）。如需严格 4xx 追踪，需适配层登记状态码——属契约外增强，已登记不移改 |
| 回填位置 | 写盘 + 读取双路：`record_source` 落盘前回填 `health.json` 的既有 `note`；`get_health` 读取时按当前事件复算刷新（均不改契约字段） |
| 证据（真机） | `/api/v1/data-sources/health`：`sina_rt.status=bad`、`fail_window_7d=6`、`note="仅探测·非主链（近 7 日失败 6 次）；sina batch unreachable"`；真实 probe 一次成功后 `data/health.json` 持久化 `note="仅探测·非主链（近 7 日失败 6 次）"`（断言 PASS） |
| 测试 | `test_health_window.SinaDegradeAnnotationTest` 3 条：反复失败→带标注（API + `health.json` 双断言，且不波及他源）；低于阈值（单败+成功）→不带标注；长期无成功（≥7 日）→带标注 |

#### 10.2 S3 · 冷启动 `/holdings` 阻塞修复

- **根因（实测定位）**：起服预热 `rolling_shadow_backfill` 每次启动对 20 日窗做全量走前重算（约 300 次训练，~5.5s CPU 密集），期间 `/holdings` 行构建为纯 Python 路径、在 GIL 争抢下从 0.3s 放大到 **5.2–39.7s**（`/health` 仍 0.01s，证明非服务级阻塞）。另有 `read_history` 全量 JSONL（MB 级）每请求多次重复解析（22 基金 × 多路径 ≈ 66+ 次）。
- **修复**：
  1. `valuation.read_history` 增按 `(path, mtime_ns, size)` 的解析缓存（写后失效；`append_history` 热缓存同步追加），消除重复整文件解析；
  2. `ledger_api.rolling_shadow_backfill` 增**存在性快路径**（`_shadow_window_fast_check`，零训练）：窗口内应有记录齐备（`expected ⊆ have`）且无需裁剪时跳过重算——与原逻辑「fresh 空且 trimmed 空→零写入」严格等价；
  3. `app._warmup` 开头显式预热读缓存（history/snapshot/predictions），并对当日已生成的 `review.scores` 缓存直接复用（`review.cache_fresh()`；`run_backtest` 任务仍强制重生成）；
  4. `_warmup` 增阶段时间戳日志（`[warmup] +N.NNs <stage>`，stderr）——即验收要求的「时间戳日志」。
- **冷启动时延实测**（`coldstart_probe.py`；自寻 OS 空闲端口 + `/engine/status.pid` 进程身份核对）：

| 请求时点 | 修复前 | 修复后 |
|---|---|---|
| ready+1s（验收口径：1 秒内发起） | 0.97s（旧数据） | **0.33s** |
| ready+6s（dev-lead 复现点） | **5.27–5.41s（三次一致）**、最坏 39.7s | **0.45–0.63s** |
| ready+15s | 39.69s | **0.34s** |
| 预热全程每 0.5s 时序（30 点） | +5.85s 单点 5.17s | 全部 **0.32–0.63s**（无 >1s 点） |

- **预热自身**：阶段日志显示 `done` 从 +11.79s 提前至 **+6.73s**（快路径省 5.5s CPU；重算在有新交易日/缺口时自动恢复全量）。
- **测试**：`test_history_cache_contract` 4 条（重复读只解析一次 / 热追加不重解析 / 外部写失效 / 筛选与副本语义）；`test_shadow_backfill_contract.test_warm_start_fast_path_skips_recompute`（快路径下 `compute_shadow_window` 调用数 0）；`test_review_scores.test_cache_fresh_for_startup_reuse`。

#### 10.3 回归证据

- 全量测试 **199/199 × 2 全绿**（R1 117 + R2 82；本轮净增 9 条：S2 3 + S3 4+1+1）。
- 无污染双跑：`proxy_quality.json`（sha256 `d430c8c9043682c2…`）与 12 个产线文件两轮前后零差异（守卫用例 `test_suite_guard_real_data_paths_untouched` 保持）。
- 起服冒烟（OS 空闲端口）：`pid` 身份核对 True；冷起 `/holdings` 0.33s / 22 行；`/data-sources/health` sina 标注断言 PASS；关闭后端口释放 True。

### 11. 修复记录（S5 后端栏：R2-D2 / R2-D3 / BLOCK-A3 / S-c / S-e / NIT · 2026-09-13）

> 依据：`15-code-review-r2.md` v4 §8.10 后端栏（含 §8.2/§8.3/§8.7/§8.8/§8.9 细则）与 `16-fake-feature-audit-r2.md`（D-2/D-3/A-3/D-6/F-1/F-3/F-6/B-5a/D-8）。
> 范围纪律：只改后端 `*.py` 与 `tests/**` 与本报告；契约/架构/前端/QA 工件未改；`runtime/**` 未触；§8.10 以外无额外重构。

#### 11.1 §8.10 后端栏逐项结果

| 项 | 指令 | 改动 | 证据/断言 |
|---|---|---|---|
| R2-D2 | `main_source.path` 回契约字面 | `holdings.main_source_status()` → `"data/holdings.json"`（内部仍用绝对路径） | 单测更新 + 无盘符/反斜杠断言；真机 `/settings/holdings-data.main_source.path=="data/holdings.json"`、exists=true/count=22 |
| R2-D3 | 同型互斥 409 + OSError 可读 | `app.start_task` 前置 `_reject_running_same_type`（E_CONFLICT，message「同型任务进行中：<tid>；可 GET /tasks 查询」）；`_run_task` 新增 OSError→E_IO 可读（WinError 走 stderr）；其余异常收敛为「内部错误（详见服务日志）」 | 新增 5 条用例：409 且不落 failed/无第二线程、完成后可再提交、OSError 无 WinError 子串、全局串行无交叉、S-c 诚实回执 |
| R2-D3③ | 跨型竞态确认 → 全局串行并回报 | **确认**：`maintain_nav_history` 与 `backfill_ledger` 均内联 `backfill_due`，同写 `backfill.jsonl`（并发可产生重复行）→ 加 `_TASK_EXEC_LOCK` **全局任务串行**（最小版） | 串行用例（跨型 start/end 不交叉）；已 `say` 回报 dev-lead；队列化/自动合并挂账 R3 |
| BLOCK-A3 | `/ledger/chain` 读时同源重算六步 + `chain_available`=可重算性 | `ledger_api._bars_index_for_chain / _chain_recomputable / _recompute_chain`；复用 `fund_predict.build_chain`；`_decorate` 判定改可重算性（轻量零训练、离线 bars） | C1/C3/C4 见 §11.2；真机 `012922/2026-09-11` → 6 步、exit=0.52、p_up/ddsm 与行对账一致 |
| S-c | `scan_factors` 去伪 | summary/step 改「因子扫描未接入（无扫描器实现）…未执行扫描、未产出候选」；final step 不再覆盖为「完成」 | 单测断言 summary+step 含「未接入」且无「扫描完成」；真机任务回执一致（§11.6） |
| S-e | R2-02 top20 补证据 | force 重抓 active F10（topline=20）；产物级复核 | 5 只 active 全部 `top_n=20 / 20 行`；估值记录 detail `top_n=20`：025500 covered 62.34→**78.09**、018957→90.63、021528 72.31→**84.18**、013566→94.44、014320→80.24 且 `included_markets=['A','HK']`（港股纳入） |
| NIT D-8 | warmup/global_as_of 静默 except → stderr 摘要 | 新增 `_swallow(stage,e)`；`global_as_of` 4 处 + `_warmup` 10 处替换 | stderr `[warn] <stage>: <type>: <msg≤160>`；不改变行为 |
| NIT B-5a | 死常量 + `no_solution_count` 实测 | 删除死常量 `NO_SOLUTION_TEXT`；`no_solution_count` 改实测（无代理且无穿透映射） | 当前实测 0（与事实一致）；grep 无死常量引用 |
| NIT F-3 | judges.value 恒空 | `factor_board.score_detail` 从 adopted 记录回填 lift/admission/backtest 实测值；`t` 保持 null（记录未存，前端按「待接入」） | 新增用例断言三值回填 + t 为 None |
| NIT F-6 | method 名去数字 | **不改**：契约 §3.3 冻结「恒 `eastmoney_f10_top10_weighted`（支持 top_n=20，method 名不变）」——改值即 G-BE-02 字段级 FAIL | 申报见 §11.4；如需改名须契约版本 +1（architect） |
| F-1 后端侧 | bootstrap 实测可用 | 核验：`/factors/score-chain.bootstrap_percentiles_measured` 实测 `{p50:-12.4,p90:26.6,p95:38.27,p99:50.0,p995:50.0}`；常量按 v9 §4.9 兄弟并存 | 页面切换属前端 S-a；后端字段已就绪（新增 2 条用例：measured 非空透出 / 未产出 null） |

#### 11.2 BLOCK-A3 事件链（C1/C3/C4）

- **实现**：定位 bar t → `bars[:t-1]` 训练（H=1）→ `engine.predict_at` → `fund_predict.build_chain`（同源，避免双实现）；**不可复现即空链，不编造步骤数值**；读时不写台账。
- **C1（真机）**：`012922 / 2026-09-11` → `chain` 长度 6、key 顺序 `gate/ddsm/veto_crowd/veto_klow2/exit/output`、`exit_threshold=0.5200`、`metrics.p_up=0.5886` / `ddsm_state=[4,0,3]` 与行内一致；单测以合成 bars + 同源预计算行再断言（4 条）。
- **C3**：`chain_available` = 可重算性（有代理离线 bars 含该 date 且训练段 ≥ `MIN_N*2+FEATURE_WARMUP+1`）；单测覆盖 true(6 步) / 无代理 false+空链 / 超窗日期 false+空链；真机 `/ledger` 抽样 8/8 true 且均有 6 步。
- **C4**：调用前后 `shadow_signals.jsonl` sha256 不变（单测断言）；接口全链零写（`get_bars(allow_network=False)` + 训练只读）。
- 字段与枚举：未新增/未改名（v8 §5.34 `LedgerChain.chain` / `chain_available` 语义内收口）。

#### 11.3 R2-D3 细节与挂账

- 同型互斥在**提交侧**拒绝：存在同 `type` 且 `queued/running` → `E_CONFLICT`（409）；不落 failed、不启线程；完成后可再次提交；串行提交 `done` 不受影响。
- OSError（含 WinError）→ `error={code:E_IO, message:"任务执行失败：本地数据文件被占用或不可用"}`；原文仅 stderr（`[task] <tid> OSError: ...`）。其余异常 → 「内部错误（详见服务日志）」。
- 跨型竞态：确认 `maintain_nav_history` × `backfill_ledger` 同写 `backfill.jsonl`（并发重复行风险）→ 最小版**全局任务串行锁**；用例验证跨型无交叉。
- **挂账（R3）**：任务队列化/去重自动合并 + 原生错误统一映射（已 `say` 回报 dev-lead；范围与理由入 open-issues）。

#### 11.4 申报（禁静默）

1. **F-6 与契约冲突**：审计建议 method 去数字/随 top_n 生成；契约 `09-r2 §3.3` 冻结 method 值（支持 top_n=20 也不变）→ 实现**不改值**（字段级一致优先）；如需改名请 architect 版本 +1。
2. **S-e 缓存 TTL 备注**：本机已 force 刷新至 top_n=20（30 天 TTL 内不再重抓属预期）；若源侧 F10 只得 10 行，代码按实际 `top_n` 如实标注（不静默降档，N-2）。
3. **F-3 部分回填**：`t` 裁判值不在 adopted 记录内 → 保持 null（前端按「待接入」）；如需全量四值需扩展 `_adopted_record` 存储（涉机制文档，R2 后评估）。
4. **NIT-2 备注**：`archive_merged=false` 的 note 仍为「归档缺失或不可读」二合一文案（审计归 NIT 挂账项，本轮不改）；如需区分「未生成/不可读」随前端文案轮一并处理。

#### 11.5 审计断言接口面（A/S/C 后端侧）

- **A-3**：C1/C3/C4 见 §11.2（真机 + 单测）。**S-c**：step/summary 无「扫描完成」（真机 + 单测）。**S-e**：top_n=20 产物证据（§11.1）。
- 其余：S1~S4 / A1 / A2 / F-5 属前端；D-7 / F-2（注册表三态）属架构 C2——后端**不新增「三态已运作」表述**，注册表维持现状单版本行，候裁定。

#### 11.6 回归证据

- 全量测试 **211/211 × 2 全绿**（R1 117 + R2 轮次新增 94；S5 轮净增 12：A3 4 + D3/S-c 5 + F-1/F-3 3）——C3 小步后为 **213/213 ×2**（见 §12.3）。
- 无污染双跑：`proxy_quality.json`（sha256 `98b94d43dec81a67…`）与 12 个产线文件两轮前后零差异（守卫用例保持）。
- 起服冒烟（OS 空闲端口 + PID 身份核对）：`main_source.path` 契约字面 ✓；`chain_available` 8/8 + C1 六步对账 ✓；`scan_factors` 诚实回执 ✓；端口释放 ✓。

### 12. 修复记录（C3 采纳：`chain_source` 落码 · 09-r2 v9.3 · 2026-09-13）

> 依据：`09-api-contract-r2.md` **v9.3 §11**（新增 `LedgerChain.chain_source` + 枚举 `chain_source`）、**v9.4 §12**（F-6 方法名语义冻结）、`10-arch-review-r2.md` v6 §12.2/§12.3。
> 范围：只改 `ledger_api.py` 与 `tests/**` 与本报告；无其他模块改动；INSERT-ONLY 与 `chain_available` 判定不动。

#### 12.1 落码

| 项 | 契约 | 实现 | 断言 |
|---|---|---|---|
| `LedgerChain.chain_source` | enum `chain_source`/null：`stored`（写入时缓存链）/`recomputed`（读时同源重算）/不可用 null；`chain_available=false` ⇔ null（不得编造） | `ledger_api.ledger_chain`：命中 `e["_chain"]` → `"stored"`（原样返回）；`_recompute_chain` 成功 → `"recomputed"`；否则 `chain=[]` + `chain_source=null` | 单测 3 态 + 一致性：`stored`（注入 `_chain` 行→原样返回且行 `chain_available=true`）；`recomputed`（合成 bars 同源对账）；`null`（无代理/超窗日期→`chain=[]`）；available 行 `chain_source ∈ {stored,recomputed}` |

- **枚举穷举**：`stored` / `recomputed`（新增取值须版本 +1）；响应未新增/未改其他字段。
- **真机**：BLOCK-A3 已核（§11.2）——当前台账无存量 `_chain`，所有可复现行实际走 `recomputed`；`stored` 保留给未来写入时缓存行（BLOCK-A3 可选优化，未启用）。

#### 12.2 F-6 确认（零改动）

- `trace[holdings].detail.method` 维持 `eastmoney_f10_top10_weighted`（**历史标识**）；档位以 `top_n` 如实（10/20）——契约 v9.4 §12 已定，**无需改名**。
- 断言：`test_f10_top20.test_f6_method_frozen_and_top_n_enum`（method 恒定 + `top_n ∈ {10,20}`）；S-e 产物证据 top_n=20（§11.1）。

#### 12.3 测试与无污染

- 全量 **213/213 × 2 全绿**（R1 117 + R2 轮次新增 96；本小步净增 2：chain_source 1 + F-6 1）——v9.5 轮后为 **217/217**（见 §13.4）。
- 无污染双跑：`proxy_quality.json`（sha256 `98b94d43dec81a67…`）与 12 个产线文件两轮前后零差异（守卫用例保持）。

### 13. 修复记录（v9.5 影子盘窗口 60 · 用户指令 · 2026-09-13）

> 依据：用户指令「影子盘直接补满 60 天，来一天换一天」；`10-arch-review-r2.md` v7 §13（改动点 B-1..B-8 + 计算量评估 + qualified 语义）、`09-api-contract-r2.md` v9.5 §13、`08-backend-arch-r2.md` v3.2。
> 范围：只改 `ledger_api.py` / `app.py` / `fund_predict.py` 与 `tests/**` 与本报告；契约/前端/QA 工件未改；`runtime/**` 未触；无清单外重构。

#### 13.1 B-1..B-8 逐条结果

| # | 项 | 实现 | 断言/证据 |
|---|---|---|---|
| B-1 | 常量 20→60 | `SHADOW_WINDOW_DAYS = 60`（唯一常量源；注释引 v9.5 §13） | `WindowConstantTest.test_constant_is_60` |
| B-2 | app 引用核验（271/284/1375） | 启动回填/重算/任务全走常量；backfill 任务 step 文案动态 `%d` 常量 | 负向测试 + 源码 grep：无 `days=20`、无「20 交易日」（§13.4） |
| B-3 | fund_predict 默认回退 | 顶层 `import ledger_api`；`rolling_window_days` 默认与回退均引用常量；`low_frequency_note` 改 60 日口径（不含静态基线数字，旧「20 交易日约 11 资产」零残留） | `inspect.getsource` 断言 + 旧文案负向断言 |
| B-4 | 统计窗随 60 | `rolling_open_stats()` 默认常量；`signal_state.rolling_window_days=60` | 单测 + 实测（§13.2/§13.3） |
| B-5 | 启动回填深度 60 | 首启一次补满（首填 = 全窗日期 × 资产）；warmup/任务/重算统一常量 | 沙箱首填 900 条 / 12.57s；临时副本首启 `total=920`（600 新行 + 既有 20 日行按 INSERT-ONLY 保留） |
| B-6 | 测试更新 + 新增 | `test_shadow_backfill_contract`（窗口 60 / 深度默认 / 幂等 / 一进一出 / 常量零残留 9 条）、`test_shadow_progress_archive`（window 60 + qualified 可达 + 走前口径披露）、`test_shadow_status_contract`（60 日 seed → qualified）、`test_shadow_recompute`（默认深度） | **217/217 ×2 全绿**；滚动用例 `written=15/trimmed=15` 与副本实测一致 |
| B-7 | 归档/裁剪/manifest | `window_days` 随 60；`reason`/幂等/`created_at` 继承不变；先归档后重写 | 沙箱 manifest `window_days=60 / count=15`、archive 首行=被裁日 2026-06-22；既有重算测试 0 冲突 |
| B-8 | 计算量实测与打点（含增量模式） | 10-r2 §13.4 认可的**增量模式**：仅缺键日期×资产做走前单点计算；快路径保留 | 每日滚动 **13.22s→0.26s**；冷启动复验见 §13.3 |

#### 13.2 计算量实测（沙箱：真实 bars 只读 + 临时 ledger，不污染产线）

| 场景 | 实测 | 说明 |
|---|---|---|
| 首填 60 日（15 资产） | **12.57s**（样本 12.57/13.27s；900 条） | 优于架构预估 15–17s |
| 快路径重跑（窗口齐备） | **0.01s** | 零训练零写入 |
| 每日滚动「来一天换一天」（增量） | **0.26s**（written=15 / trimmed=15 / total=900） | 优化前全量重算 13.22s → 约 50× |
| 进度口径 | `status=qualified`、`consecutive_days=60`、`window_days=60`、`gap_days=0`、`history_days=60` | 滚动后 consec=61（归档合并自然增长，目标 60 不变） |

- **增量等价性**：既有 `(date,code)` 行原样保留（全量路径本就不覆盖它们），新增行同源公式（`bars[:t-1]`、H=1、purge=H+2）；幂等 / INSERT-ONLY / 归档语义逐条不变。
- **文案诚实性（v9.5 §13.3）**：`shadow_progress.note` 更新为「窗口 60 交易日；记录按走前口径回算补全（非自然积累）；上线资格建议结合实盘观察另行评估」；`shadow_audit.note` 同步标注走前回算；`low_frequency_note` 不含静态基线数字（PM 重定稿可替换，接口字段直读）。

#### 13.3 冷启动复验（临时副本双启；跑后删除，产线零改动）

| 启动 | /holdings +1s | +6s | +15s | +25s | 预热 done |
|---|---|---|---|---|---|
| 首启（一次性补满 60 日） | 0.54s | 0.49s | **4.88s**（补满 CPU 窗内） | 0.25s | +22.95s |
| 二启（快路径 + 增量） | 0.40s | 0.43s | 0.32s | 0.27s | +7.12s（滚动阶段 0.39s） |

- **稳态（二启及以后）≤0.43s，不劣化于 S3 基线**（0.32–0.45s）；每日滚动走增量（0.26s）→ 无每日 CPU 争抢。
- **残留（登记）**：升级后**首次启动**存在一次性 ~5s 的 `/holdings` 瞬时时延（补满 60 日 CPU 窗）；属一次性迁移成本，非稳态行为。

#### 13.4 旧 20 值零残留与回归

- 产线 `app.py / ledger_api.py / fund_predict.py`：`SHADOW_WINDOW_DAYS=60`；无 `days=20`、无 `rolling_window_days": 20`、无「20 交易日约 11 资产」文案（负向测试 `test_no_stale_20_in_shadow_call_chain` + 源码 grep）。
- 全量 **217/217 × 2 全绿**（R1 117 + R2 轮次新增 100；v9.5 轮净增 4：窗口/常量负向 3 + qualified 可达 1）；`proxy_quality.json`（sha256 `98b94d43dec81a67…`）与 12 个产线文件两轮前后零差异。

### 14. 修复记录（客户端断连噪声零堆栈 · 用户反馈 · 2026-09-13）

> 用户反馈：交付包控制台大量 `ConnectionAbortedError: [WinError 10053] 你的主机中的软件中止了一个已建立的连接` 全量堆栈刷屏。诊断：浏览器刷新/切页/取消请求 → 客户端先断开 → 服务端写响应失败；属**正常客户端行为**，不应打堆栈。契约/业务语义零变更。

#### 14.1 诊断（修复前实测）

- 复现探针（RST 断开：`SO_LINGER=0` 后 close，模拟刷新/取消）对 API + 静态各发 24 次请求：stderr **36 行 Traceback / 36 次 `ConnectionResetError`（WinError 10054）**；服务本身仍可用（风暴后 `/health` ok）。
- 噪声三条路径：① `_send` 的 `end_headers()+write`；② `_serve_static` 同款 write；③ `_handle` 的 `except Exception` 把断连当内部错误 → `traceback.print_exc()` + 二次写 → socketserver `handle_error` 再打一层堆栈。

#### 14.2 修法（最小改动，`app.py`）

| # | 落点 | 改动 |
|---|---|---|
| 1 | 断连族定义 | `DISCONNECT_ERRORS = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)`（3.8+ 兼容）；`DISCONNECT_SUPPRESSED` 进程内计数（count/last_at，测试可见） |
| 2 | `_send` | `end_headers()+write` 包 try/except：断连族 → 计数后静默 return；**其他异常继续抛**（不吞真错） |
| 3 | `_serve_static` | 主 write 同款兜底 |
| 4 | `_handle` | `except Exception` 先判断连族 → 直接 return（不打印、不发二次信封）；非断连族保持 `print_exc + E_UNKNOWN 信封` |
| 5 | 服务器类 | 新增 `QuietThreadingHTTPServer(ThreadingHTTPServer)`：`handle_error` 断连族 → 静默 + 计数；其他异常走默认堆栈（真错可见）；`main()` 改用该类 |

- 未新增/修改任何 API 字段；计数为进程内诊断量。

#### 14.3 实测（修复前后对比，同探针同参数）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| Traceback 行数 | 36 | **0** |
| ConnectionReset/Aborted/BrokenPipe/WinError 计数 | 36（含 10054） | **0** |
| RST 风暴后 `/health` | ok | **ok**（功能不受影响） |

#### 14.4 测试断言（`test_disconnect_quiet` 9 条）

- `_send`：三族 × (write/end_headers) 均不抛且计数 +1；`ValueError` 照抛（不误吞）。
- `_serve_static`：`BrokenPipeError` 静默；`ValueError` 照抛。
- `_handle`：注入断连 → stderr 为空、无信封；注入 `RuntimeError` → stderr 含 Traceback 且 `E_UNKNOWN` 信封（真错可见）。
- `handle_error`：断连静默 + 计数；`RuntimeError` → 默认 `handle_error` 被调用（mock 断言）。
- 真起服 + RST 风暴：stderr 无 Traceback、风暴后 `/health` ok。

#### 14.5 回归

- 全量 **226/226 × 2 全绿**（R1 117 + R2 轮次新增 109；本轮净增 9）；`proxy_quality.json`（sha256 `98b94d43dec81a67…`）与 12 个产线文件两轮前后零差异。

### 15. 修复记录（F2 自碰撞伪影 · crowd6 重评与记录更正 · 2026-09-13）

> 发现：F2 独立性检验把候选与自身别名比对（crowd6 的 `_builtin=crowd` 与现役 `crowd` 同源）→ `max_collinearity=1.0 / collinear_with="crowd"` → 记录 `rejected_f2`，属**假失败**。
> 范围：只改 `factor_engine.py`（`_f2_independence` / `_incumbent_series` + 身份助手）、`tests/**`、`ledger/adopted_factors.json` 的 crowd6 记录更正（留痕）与本报告；冻结参数与业务判定未动；`runtime/**` 未触。

#### 15.1 伪影成因

- `_incumbent_series` 原排除逻辑 = `name == definition["factor_id"]`；crowd6 的 factor_id 为 `crowd6`，而现役键为 `crowd` → 未排除；crowd6 经 `BUILTINS` 解析后的信号实现与 `crowd` 完全相同 → 自比对 corr≡1.0。
- 影响面：仅 crowd6 记录（klow2 的 factor_id 与现役键同名，未受影响）；不影响窗口评分 / F1 / F3。

#### 15.2 修法（最小改动）

- 新增 `_candidate_identity_ids(definition)`：身份集合 = `factor_id` / `name` / `_builtin` 键 / 同实现的全部 `BUILTINS` 键名与实现名（crowd6↔crowd 均可识别）。
- `_incumbent_series`：按身份集合排除自比对；`_f2_independence`：同集合二次过滤（即使调用方直传 `inc_series` 也不会自比）。其余因子比对逻辑不变（阈值/窗口/口径不动）。

#### 15.3 crowd6 重评（真实 bars 只读，2026-09-13）

| 项 | 原记录（2026-09-12） | 重评（修复后） |
|---|---|---|
| `max_collinearity` | 1.0（伪影） | **0.0127** |
| `collinear_with` | `"crowd"`（自身别名） | **`"klow2"`** |
| `verdict` | `rejected_f2`（假失败） | `rejected_f1`（重评实值；见下注） |
| klow2 对照 | 0.0398 vs crowd / admitted | 0.0127 vs crowd / admitted（不回归） |

- **注（诚实披露）**：重评时行情缓存已于 **2026-09-13 15:26** 刷新（320 根；原快照 `scored_at=2026-09-12T12:49`），F1/总分同步漂移（total 21.4→−80.0、m6 lift 1.0326→0.9916），故 verdict 以重评实值为准并**一并更正留痕**；F2 伪影修正本身成立（原快照中 F2 为该批唯一失败项，修复后其 F2 通过）。

#### 15.4 记录更正留痕（不静默）

- `ledger/adopted_factors.json` → crowd6：F2 / verdict / 总分 / 窗口等更新为**重评实值**；新增 `correction` 块：
  `from {max_collinearity:1.0, collinear_with:"crowd", verdict:"rejected_f2"}` →
  `to {0.0127, "klow2", "rejected_f1"}` + `reason`（伪影成因）+ `rescore_note`（行情刷新漂移说明 + 14 报告 §15 索引）；`note` 追加「2026-09-13 修正」原文；`added_at` 保留原值。
- 未改写其他因子记录；klow2 的漂移（61.05→51.2）登记为**后续全盘重评候选**（不在本轮范围）。

#### 15.5 测试断言（`test_f2_selfcollision` 8 条）

- 身份集合含别名（crowd6↔crowd）；`_incumbent_series` 排除别名（crowd6 → 仅 `klow2`；klow2 → 仅 `crowd`）。
- 仅自身别名时全排除 → `pass` + null（不再 1.0 fail）；混有真因子时 `collinear_with="klow2"` 且 <1。
- **负向**：真共线（不同身份、同信号）仍 `fail` + `max_collinearity=1.0`（不被误放）。
- 全栈：crowd6 `evaluate` 不再出现 vs `"crowd"`；klow2 重评仍比对 `crowd` 且 <1（不回归）。

#### 15.6 回归

- 全量 **234/234 × 2 全绿**（R1 117 + R2 轮次新增 117；本轮净增 8）；`proxy_quality.json`（sha256 `98b94d43dec81a67…`）与 12 个产线文件两轮前后零差异。

### 16. 冻结纪律与红线核对

| 红线 | R2 状态 |
|---|---|
| E2/E4 禁复活、禁 OR 合并 | 未触碰（门仍 E1/E3） |
| K=4/p=0.25/MIN_N=15/SHRINK=10/BAND=0.02/双否决分位 | `engine.frozen_params` 未改值；仅追加 `baseline_method` 口径文本 |
| 永不做空 | 未触碰 |
| INSERT-ONLY | 保持；重算=先归档后重生成；回填独立文件；修正行只追加不改 |
| 组合权重 = 可信市值 | `weighting_basis` 恒 `market_value`；黑名单新增 `baseline_method` |
| `0.5830` | 产线计算零引用；仅契约固定文本含 token（D-9/§5） |
| T+3/T+15 未验证不出 up | 未触碰（`/review/scores` 属复盘展示，不产信号） |

### 17. 启动与健康检查

- 启动：`cd C:\Users\10719\Documents\ZenithLens-OpenCode && python app.py`（默认 `127.0.0.1:8791`，可用 `--port` 覆盖；Python 3.8+）。
- 健康：`GET /api/v1/health`、`GET /api/v1/runtime`（`trade_session`/`staleness`）、`GET /api/v1/engine/status`（进度/审查分离）。
- 新任务：`POST /api/v1/tasks {"type":"maintain_nav_history"}`、`{"type":"verify_tiers","params":{"targets":[...]}}`、`{"type":"backfill_ledger","params":{"mode":"recompute"}}`。

## 自验收

- [x] 契约 v9.1 每个新增/变更条目都已实现，无遗漏（§2 机器核对表逐项）—— 44 + 9 + B1~B9 + 枚举 9 + 任务 3 + 注记 2；**v9.2 注记按 §9.1 落地**
- [x] 逐字段比对：字段名/类型/单位/精度/枚举值一致；无 camelCase；`snake_case` 全项目统一；`baseline_status` 枚举 `filled/pending`（禁 `ok`，§9.1-B1-3）
- [x] 每个新行为的 4xx/5xx 分支可构造并验证（E_VALIDATION：data_kind/method/targets/冻结参数；E_CONFLICT：INSERT-ONLY；E_NOT_FOUND；E_IO 空态改可读提示）
- [x] 边界情况已处理（除零/空列表/NaN 不产出/净值缺/超时/归档不可读/预算超时）
- [x] 业务口径注释标注来源（PRD F2-xx / 契约 §x / 08-r2 §x / 09-r2 v9.2 §10 / ADR-0007~0015）
- [x] 无「看起来对」的兜底数字：缺数据一律 null + 原因（`conf_reason` 五值 / `baseline_rate=null` / pending；T3/T15 待填充）
- [x] 服务可独立启动（`python app.py` 默认 8791；修复轮以 OS 空闲端口 + PID 身份核对冒烟通过，§9.3/§10.3）
- [x] 偏差 9 条显式列于 §7，无静默修改；缺陷修复留痕 §8；修复记录 §9（B1/B2/S1）/ §10（S2/S3）/ §11（S5 后端栏）逐条
- [x] 测试：**234/234 双跑全绿**（R1 117 + R2 轮次新增 117），含 INSERT-ONLY 幂等、复算、双通道分离、负向断言、S3 缓存/快路径、A3 链重算 + chain_source 三态、D3 互斥/串行；产线数据零污染（§9.2/§10.3/§11.6/§12.3）
- [x] S2：新浪 (b) 标注回填既有 `note`（未改契约字段）；S3：冷启动 `/holdings` ready+1s/+6s/+15s 实测 ≤0.45s（修复前最坏 39.7s）
- [x] S5（§8.10 后端栏）：D2/D3/A3/S-c/S-e 全落地；NIT D-8/B-5a/F-3 顺手修；F-6 依 v9.4 §12 确认（method 名维持 + top_n 如实，零改动）；C3 chain_source 落码（§12）；v9.5 影子盘窗口 60 + 增量滚动（§13）；客户端断连零堆栈（§14，RST 风暴 Traceback 36→0）；F2 自碰撞伪影修复 + crowd6 重评/记录更正留痕（§15）
- [x] 未改前端 `static/**`、未改 R1 既有工件、未触 `runtime/**`；报告以 `-r2` 命名

## 下游交接

- **主消费方**：`dev-lead`（G-BE-01 冒烟：按 §17 起服；四目标各一条链路：`maintain_nav_history`→accuracy v2、`verify_tiers`、`backfill_ledger`、`/review/scores` 两口径、`/health`；**B1/B2/S1 复验按 §9；S2/S3 复验按 §10；S5 后端栏复验按 §11（A3 C1/C3/C4、D2/D3、S-c/S-e）；C3 复验按 §12（chain_source 三态 + F-6 确认）；v9.5 复验按 §13（窗口 60 / 增量滚动 / qualified / 冷启动）；断连修复复验按 §14（RST 风暴零堆栈）；F2 修复复验按 §15（自比对排除 + crowd6 重评）**）。
- **次消费方**：
  - `frontend-dev`：按 `09-api-contract-r2` v9.4 消费新增字段——`conf_reason`（unknown 徽章）、`estimate_quality.weighted_mae_rate`（vsum 主指标）+ `official_summary`（官方 chip）、`window_phase/window_filled_days`、`pending_verification_names/verify_review_date`、`main_source/import_*`、`scores[].sample_window`、`qdii_lead_note`、**`chain_source`（时间线 tooltip 可标注链来源）**。
  - `qa`：负向断言建议——`conf_reason` 仅 unknown 非 null；`baseline_source` 恒 measured 且旧常量零引用；`t*_real` 无来源不写（E_VALIDATION）；recompute 旧记录可归档复读；`shadow_status` 无 idle/ok/bad；`import_available=false` 禁用路径；挂档行不入 universe；双证据道不得互相引用；**`chain_source`：available 行 ∈ {stored, recomputed}、unavailable 行 null + `chain=[]`**。
- **残留风险**（责任人 / 期限）：
  1. `163208` 双段参照指数缺枚举 → 是否补 `US_OIL` 类参照由 architect 裁定（architect，S5 前；未决期间 correction=null，不影响估值链）。
  2. 首日 `accuracy.json` 空、`window_filled_days=0` → 首判（满 5 可配对日）与终判（40 日）依赖每日 `maintain_nav_history` 正常跑（backend-dev，随调度；失败回退=`unknown+nav_missing`，不静默）。
  3. QDII 首测样本积累：当前 5 只 `hold`（n_test=0），首个判定需 40 日窗+20 样本（~4-8 周）；复评日已预注册（backend-dev + PM 跟踪）。
  4. 批次 7 只挂档（>3）已触发防稀释闸事件 → 需架构×PM 复审纪要（architect + PM，S5 前）。
  5. 日留档与 `valuation_history.jsonl` 双写体积 → R2 末复核（backend-dev + architect，S5）。
  6. 首轮 `tier_reviews` 错误行保留（INSERT-ONLY 审计），读端 last-wins；若 QA 需要清理须走版本化脚本（不手工删）。
  7. S2 注记：「4xx 持续 7 天」阈值以「近 7 日失败 ≥3 次」可测化近似（适配层未登记 HTTP 状态码）→ 如需严格 4xx 追踪，由架构裁定是否放开适配层登记（architect，R2 末评估；当前标注已在健康页生效，不阻塞）。
  8. **F-6 待裁定**：`method` 值契约冻结（§3.3）vs 审计建议去数字 → 后端按契约不改；如需改名由 architect 版本 +1（architect，R2 末评估）。
  9. **R2-D3 挂账 R3**：任务队列化/去重自动合并 + 原生错误统一映射（本轮仅最小版：同型 409 + OSError 可读 + 跨型全局串行）；范围与理由已回报 dev-lead。
  10. **v9.5 首启一次性瞬时时延**：升级后首次启动的补满 60 日 CPU 窗内 `/holdings` 实测有一过性 ~5s（稳态/次日增量后 ≤0.43s）；属一次性迁移成本（已登记，无代码残留项）。
  11. **v9.5 前端文案**：`qualified` 措辞与「滚动 60 日 · 回算口径（启动回填）」标注由前端按 09 v9.5 §13.3 落地（backend 已提供 `note` 披露与 `window_days=60` 字段）。
  12. **全盘 adopted 记录漂移**：行情刷新（2026-09-13 15:26，320 根）后 klow2 重评 total 61.05→51.2（F2 仍 pass）；crowd6 已按 §15 更正留痕；其余因子记录未重评 → 建议 S5 前评估全盘重评（backend-dev + architect）。
- **未覆盖**：前端组件/交互（07-r2）、系统五问（06-r2）、产品能力视图（05-r2）、PM 终验红线（19-pm-acceptance）、因子机制 V7~V13 文档修订（21-factor-governance，R2 后）。
