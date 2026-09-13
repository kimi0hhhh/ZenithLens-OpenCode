---
artifact: 12-interface-request-r2
owner: frontend-dev
version: v1
status: draft
supersedes: 12-interface-request.md（R1 v3，原样保留；未变接口沿用其 §1~§8）
created: 2026-09-12
reviewers: [architect, backend-dev]
gate: G-FE-02
---

# 接口需求清单 · 极境 ZenithLens 前端（R2 升级轮 · 契约 v9.1）

> 唯一法律 = `docs/01-architecture/09-api-contract-r2.md` **v9.1**（未变条目沿用 v8，经 R1 `12-interface-request.md` v3 已单）。
> 本单只写 **R2 增量**：每个接口给「页面/组件调用 + 调用时机 + 加载/失败/空数据处理」+ v9.1 所需字段。
> 前端纪律：所有请求经 `static/js/api.js`（唯一 fetch 出口）；数字一律经 `format.js`；**前端不做业务计算**；
> 缺失一律 `—`/留白；`null` ≠ `0`（禁止 `+0.00%`）。mock（`static/js/mock/mock.js`）默认关闭，已同步 v9.1/v9.3 形状。
> **S5 修正（R2-D1）**：分析页空态唯一条件 = `/predictions.rows.length===0`（`open_count=0` 不参与判定；rows>0 恒 success）——
> §3 A1 行与 §9 空态表已同步；断言见 `docs/02-frontend/evidence/verify_r2_ui_states.py` 阶段 C。

## 摘要

1. R2 前端**新增字段级消费 51 项**（HoldingRow 9 / Valuation 4 / TraceStep.detail 1 / CoveragePanel 4 / SignalState 3 / PredictionSummary 1 / ShadowProgress 4 / ShadowAudit 1 / FrozenParams 1 / DataSourceHealth 3 / HoldingsDataSource 3 / LedgerEntry 2 / ShadowLedger 3 / review 5 / precision 5 / engine 2），逐条落点见 §0。
2. 三条命脉接线：① 成绩位出数（`/review/scores` v9 真实输出 + `sample_window` 注明）；② 徽章双层 + `conf_reason` 解释层（五值）；③ 回填态（`result` / `t1_real_method` / 事件链第⑥步 detail）。
3. U-05 影子盘进度改读 `/ledger/shadow.progress`（`archive_merged`/`history_days`/`window_days`/`baseline_source`）；HUD 进度枚举读 `/engine/status.shadow_status`（**不得再出现 idle/ok/bad**），偏差审查读 `shadow_audit_status`。
4. U-06 数据源健康：展示口径改为 `fail_window_7d`（`fail_count` 只允许出现在历史折叠区）；持仓数据卡读 `main_source`，导入按钮由 `import_available` 驱动禁用。
5. 四态统一：`api.js` → store 切片 `{status: idle|loading|success|empty|error}` → `components.js#mountState`；7 页 `emptyWhen` 真实条件见 §9。
6. **契约缺口：R2 无新增**。v9.1 会签字段（D-1..D-4 / R-1..R-5）均已覆盖前端消费点；R1 残留缺口（建议列 `advice` 等）仍按 R1 单 §10 挂账，不阻塞。

## 正文

### 0. R2 新增/变更消费字段 → 组件落点（机器核对表）

| # | 字段（v9.1） | 消费组件/函数 | 用途 |
|---|---|---|---|
| 1-9 | `HoldingRow.{fund_type, fund_type_label, tier_reason, verify_status, verify_status_label, verify_batch_id, verify_note, verify_review_date, qdii_lead_note}` | `holdings.js#rowHTML / predCell`（`components.js#verifyTag`） | 验证四态行内标签 + tooltip（含复查日）+ QDII 标注 |
| 10-13 | `Valuation.{fund_type, fund_type_label, conf_reason, qdii_correction}` | `components.js#valBadge` | unknown 原因（五值）+ QDII 校正行 |
| 14 | `TraceStep.detail`（`trace[holdings].detail`） | `components.js#valBadge`（第⑦项） | 披露口径：`report_date` / `covered_weight_pct` / `top_n` / `included_markets` |
| 15-18 | `CoveragePanel.{prediction_universe_count, pending_verification_count, prediction_coverage_note, pending_verification_names}` | `holdings.js#renderCoverage` | 覆盖按实计 + 待结论清单 |
| 19-21 | `SignalState.{rolling_open_assets, rolling_window_days, low_frequency_note}` | `signals.js#renderEmpty / renderGates` | 低频期望说明 + 滚动口径 |
| 22 | `PredictionSummary.qdii_lead_note` | `analyze.js#renderTable` | 信号卡 QDII chip |
| 23-26 | `ShadowProgress.{window_days, archive_merged, history_days, baseline_source}` | `engine.js#renderHud / renderShadow / #eg-prg-note` | 进度真实化 + 口径注 |
| 27 | `ShadowAudit.baseline_source` | `engine.js`（随 shadow-review 展示） | 实测基线口径 |
| 28 | `FrozenParams.baseline_method` | `engine.js#renderFrozen` | 基线口径入表 |
| 29-31 | `DataSourceHealth.{fail_window_7d, fail_window_days, recent_failures}` | `settings.js#renderSources` | 时间窗计数 + 历史折叠 |
| 32-34 | `HoldingsDataSource.{main_source, import_available, import_disabled_reason}` | `settings.js#renderHoldingsData / importHoldings` | 主源口径 + 导入禁用 |
| 35-36 | `LedgerEntry.{t1_real_method, backfill_proxy_code}` | `signals.js#renderTimeline`、`review.js#renderRecon` | 回填口径 tooltip（复算锚） |
| 37-39 | `ShadowLedger.{backfill_method, backfill_method_note, field_list}` | `engine.js#renderShadow` | 字段清单/口径长文 |
| 40-44 | `/review/scores`：`hero.{open_count, sample_period, data_kind}` + 响应 `note` + `scores[].sample_window` | `review.js#renderHero / renderScores` | 三段式成绩位 + 全样本窗注明 |
| 45-49 | `/valuations/precision`：`estimate_quality.*`、`official_summary.*`、`window_filled_days`、`window_status_label`、`window_phase` | `holdings.js#renderVSum` | 主指标 = 估算档；官方档单列 chip |
| 50-51 | `/engine/status.{shadow_status, shadow_audit_status}` | `engine.js#renderHud` | 进度 × 偏差分离表达 |
| — | `/factors/score-chain.{bootstrap_percentiles_measured, real_engine}` | 未消费（契约只加不改；前端保持常量口径展示，不新增） | 备案，不阻塞 |

### 1. 全局壳（每页常显）

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| G1 | `GET /runtime` | Topbar + 侧栏 + livebar（`main.js#renderRuntime`） | 启动一次，15s 轮询 | `as_of, staleness{is_stale,latest_date,days_behind}, open_count, trade_session, engine_status, port` | 加载=「连接中…」+ warn 脉冲；成功=滞后 ≤1 交易日时为正常态（文案由 `days_behind` 直出，前端不做交易日折算）；失败=仅保留引擎态，不阻塞视图 |
| G2 | `GET /data-sources/health` | livebar 坏源计数 + 设置页卡片（`main.js#renderLiveSources`、`settings.js#renderSources`） | 启动一次；probe 后重拉 | `sources[]`：v9.1 追加 `fail_window_7d/fail_window_days/recent_failures`（§3.10） | 加载=不显示源信息；成功=`bad` 计数；失败=「检测失败」不白屏；`fail_window_7d=0` 显示「近 7 日失败 0 次」 |
| G3 | `POST /data-sources/probe` | 设置页「立即检测」（含空态主行动按钮） | 点击 | 请求 `{source_id:null}` → `Task` | 提交中=行内「检测中…」；成功=1.2s 后重拉 health 并重渲染四态；失败=toast 保留表格 |
| G4 | `GET /engine/status` | 引擎页 HUD（`engine.js#renderHud`） | 进入 Tab + 12s 轮询；离开 `deactivate` | **`shadow_status`（进度枚举 not_started/recording/qualified/gap）× `shadow_audit_status`（idle/ok/bad）**、`shadow_consecutive_days/shadow_target_days`、HUD 其余字段沿用 R1 | 加载=「正在连接本地引擎…」；成功=进度与偏差**分卡内两行**表达；**心跳缺失且无快照 = empty（U-03）**；失败=「引擎无响应」+重试 |

### 2. ① 持仓页 holdings

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| H1 | `GET /holdings?with=valuation,nav,prediction` | 四卡 `#pa-*`、明细表 `#hd-body`（`holdings.js`） | 进入 Tab；与 precision/coverage/portfolio/predictions 并行 | R2 追加（v9.1 §3.1/§3.2/§3.3）：`verify_*` 9 项、`qdii_lead_note`、`tier_reason`；`valuation.conf_reason`（五值）、`valuation.qdii_correction`、`trace[holdings].detail` | 加载=四卡 `—` 骨架；成功=行内验证标签（C/D 或 validating/failed）、QDII chip、徽章双层+7 项 tooltip；**rows=0 → empty**「还没有录入任何持仓」+「录入第一只基金」；失败=红框+重试（不回落示例） |
| H2 | `GET /valuations/precision` | 估值精度条 `#val-sum`（`holdings.js#renderVSum`） | 与 H1 并行 | **主指标 `estimate_quality.weighted_mae_rate`（估算档）**；`estimate_quality.groups[].label`；`official_summary.{count,weight_ratio,note}`（单列 chip）；`window_filled_days/window_status_label/window_phase`；`weighted_mae_rate/groups` 降级为「全档参考」 | 加载=骨架；成功=主指标 chip（≤基准绿 / 超基准金）+ 官方档 chip + 全档参考虚线 chip；**主指标 null →「估算档暂无法计算」+ 原因 chip（`conf_reason` 文案由字典映射，不推断）**；失败=条内「估值精度读取失败」不拖垮四卡 |
| H3 | `GET /holdings/coverage` | 覆盖度四档 + 待结论清单（`holdings.js#renderCoverage`） | 与 H1 并行 | R2 追加：`prediction_universe_count`、`pending_verification_count`、`prediction_coverage_note`、`pending_verification_names` | 成功=cov-note 追加「预测覆盖 …（待结论 n 只，不计入覆盖增长）」+ 待结论清单；失败=块内「档位读取失败」+重试 |
| H4 | `GET /valuations/{code}?history=true` | 徽章点击展开入账历史 | 徽章点击 | `valuation.conf_reason/qdii_correction`、`history[]` | 加载=弹层「加载中…」；成功=当日入账；失败=toast；`trace_text` 缺失不编造 |
| H5 | 持仓 CRUD / `POST /holdings/{code}/transactions` | 3 dialog（`holdings.js`） | 录入/编辑/加减仓/删除 | 同 R1（无 R2 变更） | 成功=toast+局部刷新；失败=`E_VALIDATION` 行内/toast，不假成功 |

### 3. ② 分析页 analyze

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| A1 | `GET /portfolio/forecast` | 三窗口卡 `#an-forecast` | 进入 Tab（与 predictions/holdings/defs 并行） | 同 R1（`weighting_basis/weighting_policy_note` 等） | 加载=三卡脉冲；成功=窗口卡 + 加权口径（`open_count=0` 按既有灰/零口径展示）；失败=「预测服务暂不可用」+重试；**本片不参与页面空态判定**（S5/R2-D1 修正：空态唯一条件=`/predictions.rows=0`，见 §9） |
| A2 | `GET /predictions` | 预测表 `#an-body` | 进入 Tab | R2 追加 `qdii_lead_note`（§3.7）；`tier/market_value` 直读（不跨接口拼装） | 加载=3 行骨架；成功=行 QDII chip、`veto_*_status=missing`→「数据缺失」；**rows=0（且组合无开口）→ empty**；失败=「预测明细读取失败」+重试 |
| A3 | `GET /predictions/{code}` | 行点击推导链（`analyze.js#openChain`） | 行点击 | `chain[].detail`（⑥输出步由后端给回填值/待回填） | 弹层加载；成功=六步链 + ⑥回填值直出；失败=toast |

### 4. ③ 信号页 signals

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| S1 | `GET /signals/state` | 空态卡 `#sg-empty`、门卡 `#sg-gates/#sg-excl` | 进入 Tab（与 ledger 并行） | R2 追加：`rolling_open_assets`、`rolling_window_days`、`low_frequency_note`（§3.6）；四要素沿用 | 成功=今日无信号卡（四要素 + 滚动开口 + 低频说明）/ 今日已开口卡；失败=「读取信号台账失败」+重试 |
| S2 | `GET /ledger?limit=60` | 时间线 `#tl-list`（`signals.js#renderTimeline`） | 进入 Tab | `result`（未到期=null 时按契约判定式回退）、`t1_real`、`t1_real_method`、`backfill_proxy_code` | 加载=「正在读取信号台账…」；成功=`result=hit/miss` 圆点着色，**待回填仅当 `t1_real=null`**，已回填行 tooltip 给口径+代理代码；**rows=0 → empty 变体①「影子盘尚未开始记录」+ 启动说明（U-03）**；失败=「读取信号台账失败」+重试 |
| S3 | `GET /ledger/chain?date&code` | 时间线卡片点击 `.ev` | 卡片点击 | 同 R1；⑥输出步 detail 由后端给（回填值/待回填） | 异步加载；失败=「链路不可读」；禁编造步骤数值 |

### 5. ④ 因子页 factors

R2 前端**零变更**（U-01 仅“空盘显示（当前为空）”保留、U-12 文案字典不涉因子枚举）。`/factors/*` 沿用 R1 单 §5。
> `/factors/score-chain` 的 `bootstrap_percentiles_measured`/`real_engine` 为 v9 只加字段，前端**不消费**（保持常量分位展示，避免超额交付）。

### 6. ⑤ 复盘页 review

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| R1 | `GET /review/scores`（默认 backtest；`data_kind` 可透传） | hero `#rv-hero` + 三窗口 `#rv-scores` | 进入 Tab | `hero.{hit_rate, baseline_rate, delta_pp, open_count, sample_period, data_kind}` + 响应 `note`；`scores[].sample_window`（恒 full）+ `baseline_status` | 加载=hero 脉冲；成功=三段式（命中率+基线+Δ）+ 回测/实盘 tag + 开口/样本期；`baseline_status=pending` → 基线「待填充」、Δ「—」不着色；**scores=[] → empty**「尚无成绩记录，引擎未产出回测」（待填充≠0 说明）；失败=「读取成绩失败」+重试 |
| R2 | `GET /review/reconciliation?limit=60` | 逐笔对账 `#rv-body` | 进入 Tab | `result`（hit/miss/abstain/pending）、`t1_real`、`t1_real_method`、`backfill_proxy_code` | 成功=判定列 hit/miss 徽章（**待回填仅当 `t1_real=null`**）；回填行 tooltip「回填口径 + 代理」；空=「暂无台账记录」；失败=「台账不可读」 |
| R3 | `GET /review/cv-config` | 口径脚注 `#rv-score-note` | 进入 Tab | 同 R1 | 失败不阻塞主表 |
| R4 | `GET /engine/shadow-review` | 降级审查条 `#rv-degrade` | 进入 Tab | `status/rolling_days/hit_rate/baseline_rate/deviation_pp/message/note`（`baseline_rate`=实测基线，直读不换算） | idle 灰 / ok 绿 / bad 红；失败=红条 |

### 7. ⑥ 引擎页 engine

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| E1 | `GET /ledger/shadow?limit=60` | 台账表 `#eg-ledger-rows` + 进度条 `#eg-prg/#eg-prg-note` | 进入 Tab | `progress.{consecutive_days, target_days, progress_ratio, **window_days, archive_merged, history_days, baseline_source**, note}`；`backfill_method`、`backfill_method_note`、`field_list`（含 `t1_real_method/backfill_proxy_code`） | 成功=真实 x/60 + 口径注（归档合并/降级）+ `history_days`；字段清单 + INSERT-ONLY + 回填口径长文；失败=「台账不可读」；**无编辑/删除入口** |
| E2 | HUD（同 G4） | `#eg-hud` | 12s 轮询 | 同 G4 | 同 G4；`shadow_consecutive_days` 与 E1 一致（同口径） |
| E3 | `GET /engine/ddsm/cube?code` | 立方体 + 对比卡 `#eg-cmp` | 进入 Tab / 切资产 | `comparison.walk_forward_delta_naive_pp / *_ddsm_pp`（null → 前端「待复现」） | 成功=切片/图例/对比卡；`walk_forward_delta_*=null` 显示「待复现」（禁填数）；失败=「状态表不可读」 |
| E4 | `GET /engine/frozen-params` | 冻结参数表 `#eg-frozen` | 进入 Tab | R2 追加 `baseline_method`（§3.9） | 只读；改参须重走六关提示常显；无编辑入口 |
| E5 | `/engine/arena`、`/engine/training-status`、`/engine/inputs`、`/engine/registry` | 各自面板 | 进入 Tab | 同 R1 | 同 R1 |

### 8. ⑦ 设置页 settings

| 编号 | 接口 | 页面/组件调用 | 调用时机 | 需要字段（v9.1） | 前端四态处理 |
|---|---|---|---|---|---|
| T1 | `GET /settings` / `PUT /settings` | 隐私/LLM 表单 | 进入 Tab / 提交 | 同 R1 | 隐私开关联动 `body.masked`；失败=toast 不丢已填 |
| T2 | `GET /settings/holdings-data` | 持仓数据卡 `#hd-data` + 导入按钮 `#hd-import` | 进入 Tab / 导入后 | R2 追加：`main_source.{path,exists,modified_at,count,readonly}`、`import_available`、`import_disabled_reason`（§3.11；`primary_*` 降级为可选导入源） | 成功=主源行（data/holdings.json）+ 外部导入源状态；**`import_available=false` → 按钮 disabled + reason 直出（不裸报 E_IO）**；失败=「主源缺失」可读提示 |
| T3 | `POST /holdings/import` | 导入按钮 | 点击（可用时） | `{mode:'replace'}` → `{imported_count,source,...}` | 提交中禁用；成功=toast+重拉 holdings/holdings-data；失败=toast |
| T4 | 数据源健康（同 G2） | `#src-box` | 进入 Tab | `fail_window_7d` 等 | **累计 `fail_count` 仅折叠区（历史审计）**；`recent_failures[]` 折叠可查；四源均显示时间戳 |
| T5 | `GET /about`、`GET /engine/registry` | 只读卡 / 表 | 进入 Tab | 同 R1 | 说明型 |

### 9. 四态与错误映射（R2 全量）

- 入口唯一：`api.js#request`；错误码映射 `copy.js#ERROR_COPY`（10 枚举），未知 code 不吞 `message`；超时 8s/慢接口 30s。
- 四态：`loading` 骨架/脉冲（不渲染数字）/ `empty`（成功且集合为空实条件，见下表）/ `error`（原因+重试，不回退示例）/ `success`。
- **R2 空态真实条件（`emptyWhen`）与文案要素**：

| 页 | emptyWhen（前端实现判定） | 空态文案（为什么空 + 下一步） |
|---|---|---|
| 持仓 | `rows.length===0` | 「还没有录入任何持仓」+ 数据源路径 + 「录入第一只基金」按钮 |
| 分析 | **唯一条件 `predictions.rows.length===0`**（S5/R2-D1 修正：`open_count` 不参与；rows>0 恒 success） | 「今日没有触发开口的资产」+ 四要素事实卡（数字直读接口）+ 低频说明；「为什么空」二分支：监控集合为空 / 无预测记录 |
| 信号 | `ledger.rows.length===0` | 变体①「影子盘尚未开始记录」+ 台账/监控/滚动开口/下一步；变体②（有台账无开口）为页内「今日无信号」四要素 + `low_frequency_note` |
| 因子 | `pans.length===0` | 「因子库为空，等待首次扫描」+ 周提名说明 |
| 复盘 | `scores.length===0`（或无 hero） | 「尚无成绩记录，引擎未产出回测」+「待填充≠0」说明 |
| 引擎 | `status=offline 且 last_heartbeat_at=null 且 snapshot_as_of=null` | 「引擎离线」+ 最近成功时间 + 启动指引（有快照走 success+陈旧，A-06 不倒退） |
| 设置 | health 行全为 `unchecked` 或无行 | 「尚未检测数据源」+「立即检测」按钮 |

- 负向断言（供 qa）：`empty` 态 view-main 隐藏（无数字行）；`error` 不回退示例；`+0.00%` 零出现；`待填充/待回填` 不出现在已接通/已到期场景。

### 10. mock 与残留

- `static/js/mock/mock.js`：**默认关闭**（仅 `?mock=1` / `localStorage.zl_mock='1'`）；已同步 v9.1 形状：
  `conf_reason`（五值示例）、`fund_type`、`verify_*`（含 `verify_review_date`）、`qdii_correction`、`trace[holdings].detail`、
  `estimate_quality`/`official_summary`/`window_*`、`fail_window_7d`/`recent_failures`、`main_source`/`import_*`、
  `progress{archive_merged,history_days,baseline_source}`、`sample_window`、`t1_real_method/backfill_proxy_code`、`baseline_method`。
- 契约缺口：**R2 无新增**。R1 单 §10 残留项（如建议列）维持挂账；若后端在 v9.1 之外新增 `conf_reason`/`verify_status` 取值，须版本 +1 并同步 `copy.js` 字典。

## 自验收

- [x] 每个 R2 触达接口写明「页面/组件调用 + 调用时机 + 加载/失败/空数据处理」
- [x] 字段全部逐字引用 `09-api-contract-r2.md` v9.1（未自造字段；未消费字段显式标注）
- [x] U-01..U-12 的接口支撑逐条落到消费点（§0 机器核对表 51 项）
- [x] 四态 `emptyWhen` 7 页真实条件与文案要素（§9），与 03-ui-design-v3 §4 一致
- [x] mock 同步 v9.1 且默认关闭；未修改契约/架构文件；未改 `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `backend-dev`**：按 v9.1 §7+§9 逐项落字段（重点：`conf_reason` 五值按序命中即停；`verify_status` 五值 + `verify_review_date`；`estimate_quality`/`official_summary`；`progress.archive_merged/history_days`；`fail_window_7d`；`main_source/import_*`；`sample_window`；`t1_real_method` 恒 `proxy_bar` + `backfill_proxy_code`；`shadow_status` 不得回退 idle/ok/bad）。契约未定行为不得双输出。
- **次消费方 `qa`**（S4 联调用例重点）：四态真实触发（§9 表）、`conf_reason` unknown 文案、双层徽章同屏可区分、vsum 主指标=估算档 + 官方 chip 单列、hit/miss 与 `t1_real` 一致、待回填仅未到期、sticky/focus/Esc、`+0.00%` 负向、`import_available=false` 禁用路径。
- **残留风险**：① `estimate_quality.groups` 若后端暂缺 → 前端回退全档 `groups`（展示主指标仍读估算档，null 时显示暂无法计算）；② `trace[holdings].detail` 缺失 → 第⑦项留白不编造；③ R1 集成脚本（`docs/02-frontend/evidence/verify_shadow_*.py`）依赖真实后端 8791 + CDP，属 S4 联调，本轮以契约字段自查 + 静态断言替代。
