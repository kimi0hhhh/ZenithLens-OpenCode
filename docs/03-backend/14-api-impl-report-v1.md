---
artifact: 14-api-impl-report
owner: backend-dev
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [dev-lead, qa, frontend-dev, architect]
gate: G-BE-02
---

# 接口实现报告 · 极境 ZenithLens（OpenCode 独立实现 S3）

> 上游法律：`docs/01-architecture/09-api-contract.md` v3、`docs/01-architecture/08-backend-arch.md` v3、`docs/PROJECT_BRIEF.md` §5.1/§5.3/§9、`docs/00-charter/02-prd.md` F-02/F-06/F-08/F-09/F-10/F-14。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。未读取/引用 FundLens/ZCode 代码；未改 `09-api-contract.md`、`docs/01-architecture/**`、`runtime/**`、`static/**`。

## 摘要

1. 已实现契约 v3 全部 **53 个接口 + /health**，统一信封 `{ok,data,error,as_of}` 与 10 个错误码；`python app.py` 在 Python 3.8.6 实测起服（端口 8791）。
2. 预测核心链落地 Brief §5.1：E1/E3 门 → DDSM（[r2,om,vr]×5 档=125 格、K=4、p=0.25、MIN_N=15、收缩 10）→ 双否决（拥挤度六维 40% / KLOW2 40%）→ 出口 P>0.52；E2/E4 不实现。
3. 估值五档降级链 official→intraday→holdings→proxy→unknown 落地，命中即停并记 `trace`；`unknown` 必 `change_rate=null`；当日估值 INSERT-ONLY（`valuation_history.jsonl`）。
4. 台账 INSERT-ONLY（`ledger/shadow_signals.jsonl` + 独立 `backfill.jsonl`），`created_at` 与 `written_at` 恒等；数据缺失一律显式 `null`/空集，无兜底数字。
5. 30 项逐字段核对通过；9 处偏差/口径解释登记于正文 §4，均不静默。

## 正文

### 1. 启动与产物

- 启动：`python app.py`（默认 `127.0.0.1:8791`；`--port N` 可覆盖）。
- 健康检查：`GET /health`（附加运维端点）、`GET /api/v1/runtime`（真实端口由 `port` 字段回传）。
- 产物（代码根）：
  `app.py`（HTTP + 路由 + 53 接口）、`engine.py`（门/DDSM/双否决/出口/立方体/冻结参数）、
  `holdings.py`（funds_data 导入 + CRUD + 市值/收益）、`estimator.py`（腾讯日K/实时、天天基金、自修除权）、
  `valuation.py`（五档链 + 精度）、`fund_predict.py`（三窗口/组合/六步链/空态/口径）、
  `ledger_api.py`、`factor_board.py`、`risk.py`、`settings.py`、`errors.py`；
  `data/`（`holdings.json`、`cache/bars/*.json`、`snapshot/*`、`health.json`、`backup/`、`logs/`）；
  `ledger/`（INSERT-ONLY 台账）。
- 纯标准库：`http.server / urllib / json / math / statistics / random / threading / datetime / decimal / ssl`。无 pandas/numpy/sklearn/torch。

### 2. 逐接口实现核对表（契约 §4 全 53 项）

| # | 契约接口 | 实现位置 | 字段一致性 | 状态 | 备注 |
|---|---|---|---|---|---|
| 1 | GET /runtime | app.py `h_runtime` | ✅ Runtime §5.18 | done | as_of 取估值/预测/台账最新 |
| 2 | GET /holdings | app.py `h_holdings` | ✅ HoldingRow §5.1 | done | 两遍计算 total 后算 weight |
| 3 | GET /holdings/summary | app.py `h_holdings_summary` | ✅ §6.2.1 | done | 四卡口径 |
| 4 | GET /holdings/{code} | app.py `h_holding_get` | ✅ §5.1 | done | 404 E_NOT_FOUND |
| 5 | POST /holdings | app.py `h_holding_create` | ✅ §6.2 | done | 201；E_CONFLICT/E_VALIDATION |
| 6 | PUT /holdings/{code} | app.py `h_holding_update` | ✅ §6.2 | done | 全量覆盖式 |
| 7 | DELETE /holdings/{code} | app.py `h_holding_delete` | ✅ §6.2 | done | 返回 deleted_code |
| 8 | POST /holdings/{code}/transactions | app.py `h_holding_tx` | ✅ §6.2 | done | 摊薄成本口径 |
| 9 | POST /holdings/import | app.py `h_holding_import` | ✅ §6.2 | done | replace/merge；源只读 |
| 10 | GET /valuations | app.py `h_valuations` | ✅ §6.3 | done | mode 筛选 |
| 11 | GET /valuations/{code} | app.py `h_valuation_get` | ✅ §5.2/§6.3 | done | `history=true` 返回 history[] |
| 12 | GET /valuations/precision | valuation.py `precision_summary` | ✅ §6.3 | done | v3 `mode_distribution` |
| 13 | GET /predictions | app.py `h_predictions` | ✅ §5.4 | done | A-06 三态 |
| 14 | GET /predictions/{code} | app.py `h_prediction_get` | ✅ §6.4 | done | 6 步 chain |
| 15 | GET /portfolio/forecast | fund_predict.py `portfolio_forecast` | ✅ §5.7 | done | 门槛 0.30/3 |
| 16 | GET /review/scores | app.py `h_review_scores` | ✅ §5.8 | done | baseline pending 显式留空 |
| 17 | GET /review/reconciliation | ledger_api.py `reconciliation` | ✅ §5.10 | done | result 计算 |
| 18 | GET /review/cv-config | app.py `h_review_cv_config` | ✅ §6.6 | done | holdout_start_date=null |
| 19 | GET /ledger | ledger_api.py `read_ledger` | ✅ §5.9 | done | signals⨝backfill |
| 20 | POST /ledger/entries | ledger_api.py `write_entry` | ✅ §6.7 | done | (date,code) 唯一；E_CONFLICT |
| 21 | POST /ledger/backfill | ledger_api.py `write_backfill` | ✅ §6.7 | done | 只写 t*_real |
| 22 | GET /factors/pans | factor_board.py `pans` | ✅ §5.11 | done | 四盘+rule_text |
| 23 | GET /factors/books | factor_board.py `books` | ✅ §5.13 | done | 六本+schema_fields |
| 24 | GET /factors/score-chain | factor_board.py `score_chain` | ✅ §6.8 | done | 悬崖/窗权重/裁判 |
| 25 | GET /factors/lifecycle | factor_board.py `lifecycle` | ✅ §5.32 | done | 六块规则+source |
| 26 | GET /engine/status | app.py `h_engine_status` | ✅ §6.9 + v3 HUD | done | 六卡一次给全 |
| 27 | GET /engine/inputs | app.py `h_engine_inputs`→engine.inputs_snapshot | ✅ §5.27 | done | raw/z/level/ic_sign/signed_z |
| 28 | GET /engine/ddsm | app.py `h_engine_ddsm` | ✅ §6.9 | done | 125 格+training_summary |
| 29 | GET /engine/frozen-params | engine.py `frozen_params` | ✅ §5.14 | done | 冻结值一致 |
| 30 | GET /engine/registry | app.py `h_engine_registry` | ✅ §6.9 | done | active |
| 31 | GET /tasks | app.py `h_tasks` | ✅ §5.15 | done | |
| 32 | POST /tasks | app.py `h_task_create` | ✅ §6.9 | done | 冻结参数写入即 400 |
| 33 | GET /tasks/{task_id} | app.py `h_task_get` | ✅ §5.15 | done | |
| 34 | GET /settings | settings.py `get_settings` | ✅ §5.16 | done | key 永不回传 |
| 35 | PUT /settings | settings.py `update_settings` | ✅ §6.10 | done | 温度 0/json/shadow 冻结 |
| 36 | GET /data-sources/health | settings.py `get_health` | ✅ §5.17 | done | 固定 4 源 |
| 37 | POST /data-sources/probe | settings.py `probe` | ✅ §6.10 | done | 202 + 任务 |
| 38 | GET /about | app.py `h_about` | ✅ §6.10 | done | |
| 39 | GET /holdings/coverage | app.py `h_holdings_coverage` | ✅ §5.19 | done | 四档+失效三类 |
| 40 | GET /holdings/risk | risk.py `risk_metrics` | ✅ §5.20 | done | 样本不足 null |
| 41 | GET /signals/state | fund_predict.py `signal_state` | ✅ §5.21 | done | 四要素+门卡 |
| 42 | GET /meta/definitions | fund_predict.py `definitions` | ✅ §5.22 | done | 结论指向 B |
| 43 | GET /ledger/chain | ledger_api.py `ledger_chain` | ✅ §5.34 | done | 6 步 |
| 44 | GET /ledger/shadow | ledger_api.py `shadow_ledger` | ✅ §5.28 | done | progress+field_list |
| 45 | GET /engine/ddsm/cube | engine.py `build_cube` | ✅ §5.25 | done | naive/ddsm 双切片 |
| 46 | GET /engine/training-status | engine.py `training_status_of` | ✅ §5.26 | done | 死路穷举 |
| 47 | GET /engine/arena | factor_board.py `arena` | ✅ §5.24 | done | 空集+图例 |
| 48 | GET /engine/shadow-review | ledger_api.py `shadow_audit` | ✅ §5.29 | done | idle/ok/bad |
| 49 | GET /factors/score-detail | factor_board.py `score_detail` | ✅ §5.23 | done | 无因子→404 |
| 50 | GET /factors/books/{book} | factor_board.py `book_detail` | ✅ §6.11.12 | done | records 键=schema_fields |
| 51 | GET /factors/governance-cycle | factor_board.py `governance_cycle` | ✅ §5.30 | done | 五阶段 |
| 52 | GET /factors/dig-records | factor_board.py `dig_records` | ✅ §6.11.14 | done | 空集+panel |
| 53 | GET /settings/holdings-data | app.py `h_settings_holdings_data` | ✅ §5.33 | done | readonly=true |

**v3 全量核对**：§8.1 对既有对象的追加字段全部存在（`Valuation` 7 字段、`LedgerEntry` 4 字段、`FactorItem` 10 字段、`FactorPan` 6 字段、`FactorBook` 3 字段、`FrozenParams` 6 字段、`/engine/status` 14 字段、`EngineInputItem` 7 字段 + `crowd`、`training_summary`、评分链 4 字段、生命周期 4 字段、`mode_distribution`）；§8.4「不改既有字段名」经核对成立。

### 3. 核心逻辑实现口径（可追溯）

- **触发门**（engine.py `gate_of`）：E1 `low[t] > high[t-1]`；E3 `ret < -0.02 and vr < 0.8`，`ret=close[t]/close[t-1]-1`。E2/E4 不实现。来源 Brief §5.1。
- **DDSM**（engine.py `train_from_samples`/`ddsm_p`）：三维 r2/om/vr，分位断点 20/40/60/80；加噪 `K=4`、`p=0.25` 副本**只进训练计数**；出值 `ddsm_p=(n_up+10×train_rate)/(n+10)`；`naive_p` 仅 `n≥MIN_N=15` 给出，否则 null（A-05）。固定随机种子 `20260912`（写入快照）保证可复现。
- **双否决**（engine.py `veto_status`）：拥挤度六维按训练段 IC 符号等权复合 z，`composite_z ≥ 训练段 60 分位` 否决；KLOW2 `=(min(open,close)-low)/(high-low) ≤ 训练段 40 分位` 否决；任一维统计缺失 → `missing`，缺数据不放行。
- **出口**（engine.py `EXIT_THRESHOLD=0.52`）：`P>0.52` 且无否决且门触发 → `up`，否则 `gray`/`abstain`；**不存在 down/做空分支**。任一否决层 `missing` → `abstain`/`veto_data_missing`（A-05）。
- **三窗口**（fund_predict.py `_build_windows`）：T1 `gate+ddsm+veto`（`brief_mandated`，`p`=DDSM P）；T3 `gate_only`（`pending_cv`，`p=null`）；T15 `gate+ddsm`（`pending_cv`，`p`=H=15 DDSM P）；T3/T15 `direction=gray` + `provisional_*`（A-04）。
- **组合加权**（fund_predict.py `portfolio_forecast`）：仅 A/B 档开口且 `p!=null` 按市值加权；C/D 进 `tier_excluded`；门槛 `0.30/3` 强制 gray；未验证窗口 `weighted_p=null`（T3 无 p；T15 未验证不进组合）。
- **估值五档**（valuation.py `value_fund`）：official（官方 `jzrq==as_of`）→ intraday（天天基金 `gszzl`）→ holdings（重仓，本期无抓取→`no_report`）→ proxy（代理 ETF 实时/日线）→ unknown（`change_rate=null`）；`trace` 穷举 tried/hit/reason；`change_rate` 为**小数**（估算百分比已 ÷100）。
- **估值≠净值**：`Valuation.*`（今日预估）与 `Nav.*`（官方已公布）独立字段；官方回填只写 `nav.*`，不改当日已入账 mode。
- **INSERT-ONLY**：估值写 `data/snapshot/valuation_history.jsonl`（快照文件仅为可重建缓存）；台账写 `ledger/shadow_signals.jsonl`，回填写 `ledger/backfill.jsonl`。
- **行情**：腾讯 `web.ifzq.gtimg.cn` 日K（不复权）+ `self_adjust`：单日跳变 >25% 时按比例缩放之前历史 OHLC；实时走 `qt.gtimg.cn`。

### 4. 偏差与口径解释（不静默；需架构师/产品裁定）

| # | 契约/来源 | 实现 | 性质 | 建议 |
|---|---|---|---|---|
| D1 | §1.4 端口默认 8787 | 实际 8791，`/runtime.port` 回传 8791 | 派发指定；契约允许 actual via /runtime | 确认 8791 为 OpenCode 版固定口 |
| D2 | 代理映射未在契约冻结 | 10 只指数/黄金联接按同指数场内 ETF 映射为 **A**；12 只 QDII/主动无验证代理记 **D** | 实现配置假设 | architect 复核 PROXY_MAP（holdings.py）后再升 B/C |
| D3 | §5.33 `legacy_path` | 取 `…\app_data\funds_data.json.bak`（同目录旧快照，滞后数日） | 旧位置精确路径未在契约给出 | 确认 legacy 路径定义 |
| D4 | §5.2 MAE/方向命中率 | proxy 档用 nav_history 与代理日线重叠样本计算（实测 `n_test=7`，`mae≈0.002`，`dir_hit=0.857`）；其余 mode null | 真实小样本，非估计值；`accuracy_window_days` 仍报 40 | 40 日回测产出后回填 |
| D5 | §4.5 vs A-05 顺序 | 门未触发优先 → `gray/gate_not_triggered`（仍计算并返回否决状态）；门触发后否决 `missing` → `abstain` | 口径解释 | architect 确认该优先级 |
| D6 | §5.7 T15 `p` 与「未验证不进组合」 | `WindowResult.p` 给 DDSM P，但组合 `weighted_p=null` | 按 §5.7 尾注实现 | 无需改 |
| D7 | §6.2 `import.merge` 未冻结 | 按 `code` 合并（新覆盖旧），默认 `replace` | 契约自身登记 CONCERN | 本期 UI 只用 replace |
| D8 | §9.3 因子治理数值 | 四盘/六本账本/挖掘/竞技场在引擎未产出时返回空集/null；`rule_text`/评分链/生命周期文本来自 PRD F-14 + Brief §9；`bootstrap_percentiles`/`effect_pp` 为契约固定展示常量 | 遵守残留风险 9，禁用 legacy 数字冒充实测 | 因子引擎产出后回填 |
| D9 | §3.1 holdings 档 | 未实现重仓页抓取（HTML 脆弱）→ trace `tried=true/hit=false/reason=no_report` | 诚实降级 | 后续可补 30 天缓存抓取 |

**附加（附加不改既有）**：`GET /health` 运维端点；`app.py` 只读服务 `static/**`（不写前端文件），使 `http://127.0.0.1:8791/` 可直接加载前端。

### 5. 实测证据（2026-09-12，Python 3.8.6）

- `python app.py` 起服成功，`/api/v1/runtime` 200，`port=8791`，`trade_session` 由本地时间推导。
- `/api/v1/holdings` 22 行；A 档 10 行估值 `proxy`（真实代理 ETF 日内涨跌），12 行 `unknown`（change_rate=null）；`mv_source` 分布 `valuation:10 / nav:12 / null:0`（A-02：未知行走官方净值，不用成本回退）。
- `/api/v1/valuations/precision`：`mode_distribution` proxy 10 / unknown 12；`weighted_mae_rate≈0.002`，分组 high 10。
- `/api/v1/predictions` 10 行（A 档），T3 `p=null`、T1/T15 `p` 为真实 DDSM 收缩概率，`ddsm_state` 三元组 0–4。
- 负向：`POST /tasks` 带 `min_n` → 400 `E_VALIDATION`；同日同 code 台账 → 409 `E_CONFLICT`；`/holdings/999999` → 404；`DELETE /ledger/entries` → 404（无删改端点，G10）。
- 立方体：5 层 × 25 格，空样本格 `status=empty`/`naive_p=null` 显式返回（不给 0/50%）；`walk_forward_delta_* = null`（未回测，不冒充实测）。

## 自验收

- [x] 契约中每个接口都已实现，无遗漏（53/53 + /health）
- [x] 逐字段比对：字段名 snake_case、类型、单位、精度、枚举一致（§2、§8.1/§8.4 核对）
- [x] 每个接口的 4xx/5xx 分支可构造并验证（E_VALIDATION/E_NOT_FOUND/E_CONFLICT/E_ENGINE_OFFLINE 实测）
- [x] 所有边界情况已处理（除零/空/NaN/缺失/超时；外部源 5s 超时 + 重试 1 次）
- [x] 业务口径在代码注释中标注 PRD/契约来源
- [x] 无"看起来对"的兜底数字；缺失一律显式 null/空集（unknown 必 change_rate=null）
- [x] 服务可独立启动（`python app.py`，附 /health、/runtime）
- [x] 所有偏差已列出，无静默修改（§4，9 项）
- [x] 台账 INSERT-ONLY、回填独立文件、`(date,code)` 唯一
- [x] 纯 Python 标准库；Python 3.8.6 实测可起服

## 下游交接

- **主消费方 `dev-lead`**：按 G-BE-01 冒烟（起服 + `/holdings` + 一条估值 + 一条预测 + 立方体/竞技场/影子盘各一条）与 G-BE-02 逐字段核对（对照 §2 表与 §4 偏差）。
- **抄送 `frontend-dev`**：mock → 真实接口切换；重点用 `valuation_mode`/`confidence_color_class`/`trace_text`/`dir_hit_rate`/`n_test`、A-02 `fallback_value` 分列、A-03 未达门槛不显示"涨"、A-06 离线走陈旧/错误态、立方体空样本格斜纹、竞技场 `arena_color`、台账 `created_at`。
- **次消费方 `qa`**：按 G2~G12 建 P0 用例；v3 负向：空样本格不得渲染 0/50%；台账无编辑/删除；`created_at` 不可改；评分链缺失字段为 null；竞技场裸算法行不着红绿。
- **残留风险（含责任人与期限）**：
  1. 代理映射未验证（D2）→ architect 复核后升 B/C（期限 S3 内）。
  2. proxy MAE/方向命中率仅 7 个重叠交易日（D4）→ 40 日回测产出后回填（backend-dev，S3）。
  3. holdings 档未抓取重仓（D9）→ 影响降级链深度（backend-dev，S3）。
  4. `self_adjust` >25% 阈值未用真实除权案例验证；volume 未同步缩放（backend-dev，S3）。
  5. T+3/T+15 `validation_status=pending_cv`、`direction=gray` 待真实 CV+placebo 升格（architect，S3 回测后）。
  6. 因子六本账本/竞技场/治理数值待引擎产出（architect + backend-dev，S3）。
  7. `legacy_path` 与 `import.merge` 语义待契约确认（architect，S3 前）。
- **未覆盖**：前端组件与四态（`07-frontend-arch`/`03-ui-design`）、桌面 exe 打包（S5）。
