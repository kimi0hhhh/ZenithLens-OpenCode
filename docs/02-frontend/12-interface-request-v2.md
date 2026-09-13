---
artifact: 12-interface-request
owner: frontend-dev
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [architect, backend-dev]
gate: G-FE-02
---

# 接口需求清单 · 极境 ZenithLens 前端（S3 重跑 · v2 · 契约 v4）

> 唯一法律 = `docs/01-architecture/09-api-contract.md` **v4**。本单**不重定义字段**，只按页面逐条引用契约编号与字段名，
> 便于 `backend-dev` 逐项核对（G-BE-02 红线）。契约缺口集中在 **§10**（需架构师裁定）。
> 前端产出口径：所有请求经 `static/js/api.js`（唯一 fetch 出口，页面层无裸 fetch）；数字展示一律经 `static/js/format.js`；
> **前端不做业务计算**（组合加权、命中率、评分、Δ、求和、分组占比一律取后端）。
> v2 方法：以 skill `implement` 的「按 spec 实现 + 定期类型/测试检查」与 `prototype` 的「原型产物不进交付物」执行。

## 摘要

1. 前端共消费 **51 个面向 UI 的接口**（v2 的 38 + v3 的 15，其中 `/ledger/shadow` 同时服务引擎页与复盘；内部接口 2 个不消费）。
2. v2 前端严格对齐 **契约 v4**：A-07 立方体双口径（`production_layer`/`research_layer`/`default_layer`/`dual_view_note`）、
   A-08 组合权重口径（`weighting_basis`/`weighting_policy_note`）、A-09 竞技场独立色板（`color_scheme`/`color_token_prefix`）、
   A-10 影子盘归档（`retention_policy`/`first_of_day_immutable`/`archive_manifest_at`）已全部落到消费点。
3. 四态统一：请求经 `api.js` → store 切片 `{status: idle|loading|success|empty|error}` → `components.js#mountState` 渲染；
   错误文案按 `error.code`（`copy.js`）映射，未知 code 不吞 `message`。引擎离线按 A-06 走「成功+陈旧」或 `error`，**不得进 `empty`**。
4. 命脉口径：`null` ≠ `0`（未知渲染「未知/—」，**禁止 `+0.00%`**）；未知行金额走独立 `fallback_value`（A-02）；
   估值徽章仅由后端 `valuation_mode`→`mode_label` + `confidence`→`confidence_color_class` 驱动（不前端推断）。
5. 契约缺口 **9 条**（§10）：v4 已解决「加权长文」（`weighting_policy_note`）；残留 `建议列`、`PredictionSummary.tier/market_value`、
   `llm.base_url`、precision 分组 `label`、`window_min_days` 结构、`license_lines`（§5.14）元素键名等，请架构师裁定后版本 +1。
6. mock 现状：后端未就绪期间由 `static/js/mock/mock.js` 提供替身，**默认关闭**（仅 `?mock=1` 或 `localStorage.zl_mock='1'`）；
   mock 已补齐 v4 字段；对接真实后端时视图层零改动。

## 正文

### 0. v4 增量字段（v2 前端新增消费点，逐字引用）

| 增量字段 | 归属对象 | 前端消费点（组件） | 裁定 |
|---|---|---|---|
| `weighting_basis` / `weighting_policy_note` | `PortfolioForecast` §5.7 | 组合卡 `.win` 与 `#pf-note`/`#an-weighting`（`components.js#weightingNote`、`forecastCard`） | A-08 |
| `weighting_basis` | `FrozenParams` §5.14 | 冻结参数表（`engine.js#renderFrozen`） | A-08 |
| `production_layer` / `research_layer` / `default_layer` / `dual_view_note` | `StateCube` §5.25 | 125 格立方体（`engine.js#renderCube`，ddsm 默认 / naive 折叠） | A-07 |
| `color_scheme` / `color_token_prefix` | `ArenaMatrix` §5.24 | 竞技场图例与格色（`engine.js#renderArena` + `components.js#arenaColorVar/arenaClass`） | A-09 |
| `retention_policy` / `first_of_day_immutable` / `archive_manifest_at` | `ShadowLedger` §5.28 | 影子盘台账归档说明（`engine.js#renderShadow`） | A-10 |

> 前端**只读**这些字段：权重口径冻结即展示 `market_value`，不提供改权重的 UI；竞技场只取 `arena_color`，不映射涨跌色；
> 立方体初始层取 `default_layer`，naive 研究口径默认折叠且同屏展示 `dual_view_note`。

### 1. 全局壳（每页常显）

| 编号 | 接口 | 调用页面 / 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| G1 | `GET /runtime` §6.1/§5.18 | Topbar+侧栏；启动一次，15s 轮询 | `as_of, staleness{is_stale,latest_date,days_behind,note}, open_count, trade_session, engine_status, port` | 加载=chip「连接中…」+livebar warn 脉冲；成功=`staleness.is_stale` → `#stale-banner`「引擎未运行，展示 <latest_date> 快照」，侧栏滞后文案只用 `days_behind`；失败/超时=livebar warn，不阻塞各视图 |
| G2 | `GET /data-sources/health` §6.10/§5.17 | livebar+设置页；启动一次、probe 后重拉 | `sources[].{source_id,label,status,last_ok_at,fail_count,latency_ms,note}` | 加载=不显示源信息；成功=`bad` 计数 + 设置页 tag(ok/warn/bad/unchecked)；失败=仅保留引擎态不白屏；`latency_ms=null` 不渲染耗时 |
| G3 | `POST /data-sources/probe` §6.10 | 设置页「立即检测」 | 请求 `{source_id:null}`；响应 `Task` §5.15 | 提交中=行内「检测中…」脉冲；成功=1.2s 后重拉 health；失败=toast 保留表格；超时=同失败 |
| G4 | `GET /engine/status` §6.9 | 引擎页 HUD；12s 轮询，离开 `deactivate` | HUD 六卡全字段（`shadow_status/shadow_consecutive_days/shadow_target_days/training_assets/index_only_assets/state_grid_*/avg_samples_per_cell/min_samples_cell/last_retrain_at/next_retrain_at/data_freshness_*`） | `offline`+快照=成功+陈旧条；`offline` 无快照=error；成功=六卡；失败=「无响应」+重试 |

### 2. ① 持仓页 holdings（默认首页）

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| H1 | `GET /holdings?with=valuation,nav,prediction` §6.2/§5.1/§6.2.1 | 进入 Tab；与 precision/portfolio/coverage/predictions 并行 | `rows[].*`（全部 §5.1 字段）、`summary.*`（`total_value/fallback_value/total_value_with_fallback/covered_cost_amount/today_pnl_amt/total_pnl_amt/return_rate/covered_count/total_count/coverage_note/as_of`） | 加载=四卡 `—` 骨架+明细 3 行骨架（**骨架不显示数字**）；成功=金额 `fmt.amt`、比率 `fmt.rate`、涨跌红绿；`market_value=null` 显示「—」并**分列** `fallback_value`；副标题用 `summary.coverage_note`；空数组=`empty`「还没有录入任何持仓」+CTA；失败=`error` 红框+重试（不回退示例）；超时=error |
| H2 | `GET /valuations/precision` §6.3 | 与 H1 并行 | `groups[]{confidence,count,market_value,weight_ratio}`、`mode_distribution[]{mode,mode_label,count,market_value,weight_ratio}`、`weighted_mae_rate`、`industry_baseline_mae_rate`、`window_days` | 加载=三个骨架 chip；成功=`weighted_mae_rate<=industry_baseline_mae_rate` 绿否则金；口径 chip 虚线；失败=条内「估值精度读取失败」+重试（不拖垮四卡）；`weighted_mae_rate=null` 不展示该 chip |
| H3 | `GET /portfolio/forecast` §6.5/§5.7 | 进入 Tab（持仓+分析共用，timeout 30s） | `windows[]`（3 项 T1/T3/T15）全字段，含 **`weighting_basis`/`weighting_policy_note`**；外层 `engine_status/as_of` | 加载=三卡脉冲；成功=`direction==='up'` 且 `coverage_threshold_met` 且窗口已验证才显示「涨」红，否则灰+`direction_reason`；`weighted_p=null`（T3）「—」+「该窗口无概率定式」；覆盖条用 `coverage_ratio`，其余占比用 `excluded_ratio`；**口径由后端 `weighting_basis` 驱动，前端不做加权**；`no_open`=空态；失败=卡内「预测服务暂不可用」+重试；超时=「数据加载较慢」+重试 |
| H4 | `GET /holdings/coverage` §6.11.1/§5.19 | 与 H1 并行 | `tiers[]`（固定 4 A/B/C/D）`{tier,tier_label,color,count,market_value,weight_ratio,description,action_hint,invalidation,member_names}`、`total_count,total_value,invalidation_note,no_solution_count` | 加载=四格骨架；成功=档色用后端 `color`（**不硬编码**）；`weight_ratio=null`「—」；失败=块内「档位读取失败」+重试；超时=同失败 |
| H5 | `GET /holdings/risk` §6.11.2/§5.20 | **`details.fold` 展开才请求**（首屏不阻塞） | `sharpe,var95_rate,downside_vol_rate,max_drawdown_rate,sample_days,stale,computed_at,note` | 加载=四格「…」+脉冲；成功=`var95_rate`/`max_drawdown_rate` **正数即幅度**、负向用 `--down`；null「—」（禁用 0 冒充）；失败=展开区「风险指标计算失败」+重试 |
| H6 | 持仓 CRUD §6.2 | 录入/编辑、加/减仓、删除 | POST `{code,name,group,tier,shares,cost_amount,avg_cost,confirm_days,proxy_code}`；PUT 同可选子集；DELETE→`{deleted_code}`；transactions `{tx_type,shares,price,date,fee_amount}` | 提交中=按钮 loading+防重复；成功=toast+局部刷新（重拉 H1/H3/H4）；失败=`E_VALIDATION`→行内/toast、`E_CONFLICT`→「已存在」，**不假成功**；超时=toast，表单不丢输入；删除走 `dialog` 二次确认，台账历史不删 |
| H7 | `GET /valuations/{code}?history=true` §6.3/§5.2 | 徽章点击（R-UI-03 可追溯） | `valuation.trace_text,mae_rate,dir_hit_rate,n_test,confidence_label,confidence_color_class,written_at,is_first_of_day`；`history[]{written_at,mode_label,is_first_of_day}` | 加载=弹层「加载中…」；成功=当日各次入账，首次标「当日首次口径」；`trace_text` 空**不编造**；失败=toast「读取估值详情失败」；超时=同失败 |

### 3. ② 分析页 analyze

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| A1 | `GET /meta/definitions` §6.11.4/§5.22 | 进入 Tab | `formula,signal_time,timing_note,paths[]{path,label,steps,executable,caveat},conclusion` | 加载=折叠区脉冲；成功=B 路径标「可执行」；失败=「口径定义读取失败」；说明型无空态；`conclusion` 指向 `hold_existing`，前端不暗示当天买入 |
| A2 | 三窗口组合卡 | 复用 H3（同源同响应） | 同 H3 | 同 H3；规则长文用后端 `weighting_policy_note`（A-08），前端不硬编码数值规则 |
| A3 | `GET /predictions` §6.4/§5.4 | 进入 Tab | `rows[]{code,gate,gate_label,p_up,ddsm_state,veto_crowd,veto_crowd_status,veto_klow2,veto_klow2_status,signal,signal_label,reason,windows{T1,T3,T15}}`；外层 `engine_status/as_of` | 加载=3 行骨架；成功=`veto_*_status=missing`→「数据缺失」（**不得显示为通过**）；T3/T15 `validation_status=pending_cv`→「观察」灰；空数组=`empty`「今日无资产开口」；失败=「预测明细读取失败」+重试；超时=同失败 |
| A4 | `GET /predictions/{code}` §6.4 | 行点击展开六步链 | `chain[]{step,key,title,status,detail,metrics}`，`metrics` 键枚举同 §6.4 | 加载=弹层「加载中」；成功=六步链（`metrics` 逐键格式化）；失败=toast；`status=missing`→「数据缺失」；出口步必含 `exit_threshold=0.5200` |

### 4. ③ 信号页 signals

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| S1 | `GET /signals/state` §6.11.3/§5.21 | 进入 Tab | `state,monitored_count,total_count,days_since_last_open,last_open{date,code,name,gate,result,t1_real},last_result,empty_note,gates[]{gate,gate_key,label,formula,role,effect_pp,t_value,note},excluded_gates[],or_merge_forbidden` | 加载=脉冲骨架；成功=`no_open` 四事实卡+`empty_note`（强调「不是故障」）；门卡 `effect_pp` 以 pp 展示；失败=「读取信号台账失败」+重试；超时=同失败 |
| S2 | `GET /ledger?limit=60` §6.7/§5.9 | 进入 Tab | `rows[]{date,code,name,tier,gate,p_up,ddsm_state,veto_crowd,veto_klow2,signal,t1_real,chain_available,created_at}` | 加载=脉冲骨架；成功=`signal=up` 红点/弃权空心、`t1_real=null`「待回填」、`chain_available=false` 不请求链；空数组=`empty`「近 60 天无信号」；失败=「台账不可读」+重试；**只读，无编辑/删除入口**（PRD G10） |
| S3 | `GET /ledger/chain?date&code` §6.11.5/§5.34 | 时间线卡片点击 | `chain[]{step,key,title,status,detail,metrics},metrics,source_ledger,created_at` | 点击异步加载（`.ev` 内失败=「链路不可读」）；成功=六步链；`E_NOT_FOUND` 显示不可读；**禁止前端编造步骤数值** |

### 5. ④ 因子页 factors

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| F1 | `GET /factors/pans` §6.8/§5.11/§5.12 | 进入 Tab | `pans[]`（4 项）`{role,role_label,description,factor_count,factors[],rule_text,pan_status,flow_kind,updated_at,factor_cap,nomination_limit}`；`factors[].{factor_id,name,role,role_label,score,total_score,status,license,license_label,lift_bars[6],independent_trigger_days,death_condition,note,ab_progress,added_at}` | 加载=盘骨架；成功=`rule_text` 原样渲染、`lift_bars` 驱动 bars（只画长度，不重算 lift）、总分/牌照/角色 tag；空盘「（当前为空）」；失败=「因子账本读取失败」+重试；超时=同失败 |
| F2 | `GET /factors/books` + `/factors/books/{book}` §6.8/§6.11.12/§5.13 | 进入 Tab / 点展开 | `books[]{book,book_label,filename,purpose,record_kind,schema_fields,record_count,last_record_at,sample}`；展开 `{record_kind,schema_fields,records[],total,last_record_at}` | 加载=骨架；成功=因子页展示前 4 本、**表头由 `schema_fields` 生成**（不硬编码）；无记录=`records=[]`「待写入」；失败=「账本读取失败」+缺失文件名；只读 |
| F3 | `GET /factors/score-chain` §6.8 | 进入 Tab | `lift_bins[]{min_lift,k_lift,label},window_weights[],formula_text,bootstrap_percentiles{p50,p90,p95,p99,p995},judges[]{judge,scope,metric,note},floor_note,rule_source` | 说明型；成功=长文；失败=占位 |
| F4 | `GET /factors/score-detail?factor_id` §6.11.11/§5.23 | 因子行展开 | `windows[]{window,window_label,lift,k_lift,weight,independent_trigger_days,n_w,admission,score,cliff_hit},total_score,bootstrap_percentiles,judges,formula_text` | 展开异步；成功渲染表；缺失字段「—」（禁止估填）；失败「跑分表读取失败」；**前端不算 `k_lift×权重×准入度`**，直接用 `score`/`total_score` |
| F5 | `GET /factors/governance-cycle` §6.11.13/§5.30 | 进入 Tab | `phases[]{phase,label,cadence,status,last_run_at,next_run_at,rule_text,human_retained},note` | 成功=五卡；空/失败=占位；`last_run_at=null`「—」 |
| F6 | `GET /factors/dig-records` §6.11.14/§5.31 | 进入 Tab | `records[]{scan_date,candidate,f1_result,f1_detail,f2_result,f2_detail,f3_result,f3_detail,verdict,verdict_text,nomination_week,cooldown_until,created_at},panel{nomination_limit,cooldown_days,week_rule}` | 成功=六列表；`na`→「—」；空「尚无挖掘记录」；失败占位 |
| F7 | `GET /factors/lifecycle` §6.8/§5.32 | 进入 Tab | `admission_rules[],license_lines[]{license,threshold,condition,note},retire_rules[],dual_exit[],false_kill_guards[],revive_rules[],source,freeze_note` | 说明型；文本来源由后端 `source` 给出，前端不硬编码规则 |

### 6. ⑤ 复盘页 review

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| R1 | `GET /review/scores` §6.6/§5.8 | 进入 Tab | `scores[]{window,formula,hit_rate,open_count,baseline_rate,baseline_status,delta_pp,cv_mode,purge_gap,holdout_days,data_kind,sample_period,as_of},hero{window,hit_rate,baseline_rate,delta_pp,label}` | 加载=hero 脉冲；成功=`baseline_status=pending`→基线/Δ「待填充」**不着色**、Δ 正负着色、`shadow_live` 标「实盘」；空=`scores=[]`→「尚无成绩记录」；失败=「读取成绩失败」+重试；前端不算 Δ |
| R2 | `GET /review/reconciliation?limit=60` §6.6/§5.10 | 进入 Tab | `rows[]{...LedgerEntry,result},total` | 成功八列；`result=pending`「待回填」；空「暂无台账记录」；失败「台账不可读」；`result` 由后端计算 |
| R3 | `GET /review/cv-config` §6.6 | 进入 Tab | `cv_mode,random_split,purge_gap,placebo_min_pp,holdout_days,holdout_start_date,ledger_policy` | 成功填脚注；失败不阻塞主表；`holdout_start_date=null` 不展示 |
| R4 | `GET /engine/shadow-review` §6.11.10/§5.29 | 进入 Tab | `status,rolling_days,hit_rate,baseline_rate,deviation_pp,threshold_pp,message,checked_at,note` | `idle` 灰条/`ok` 绿条/`bad` 红条；成功显示滚动命中率 vs 基准；失败红条「审查读取失败」 |

### 7. ⑥ 引擎页 engine

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| E1 | HUD | 见 G4 | 见 G4 | 见 G4 |
| E2 | `GET /ledger/shadow?limit=60` §6.11.6/§5.28 | 进入 Tab | `rows[]{...含 created_at},total,summary{...},progress{...},field_list,**retention_policy,first_of_day_immutable,archive_manifest_at**,insert_only_note,as_of` | `not_started`→0/60；`hit_rate=null`→「—」；成功渲染汇总+表（含 `created_at` 列）+归档说明；失败「台账不可读」；**无编辑/删除入口** |
| E3 | `GET /engine/arena` §6.11.9/§5.24 | 进入 Tab | `windows[6],rows[]{config_id,config_name,config_kind,is_leave_one_out,is_highlight,warning,cells[]{window,open_count,hit_rate,paired_delta_pp,is_leave_one_out,warning,color,is_window_max,is_window_min}},legend[],naive_method_note,**color_scheme,color_token_prefix**,as_of` | 成功=矩阵；`warning`→▲（`--arena-yellow`）；格色**只用后端 `color` + `color_token_prefix`**（独立 `--arena-*`，禁复用涨跌色）；空「竞技场暂无配置」；失败占位 |
| E4 | `GET /engine/training-status` §6.11.8/§5.26 | 进入 Tab | `total_cells,filled_cells,coverage_pct,avg_samples_per_cell,min_samples_cell,min_n,noise{k_noise,p_perturb},train_mode,noise_text,retrain_cycle,last_retrain_at,next_retrain_at,retrain_note,training_assets,index_only_assets,dead_ends[]` | 成功四格+长文+死路清单；失败「训练状态不可读」 |
| E5 | `GET /engine/frozen-params` §6.9/§5.14 | 进入 Tab | `k_noise,p_perturb,min_n,shrink,band,veto_crowd_quantile,veto_klow2_quantile,min_coverage_ratio,min_open_count,**weighting_basis**,gate_e1,gate_e3,purge_gap,window_weights[],window_min_days[],license_lines[],change_policy` | 只读表；`change_policy` 常显；**无编辑入口**；`window_min_days` 见 §10 缺口 6 |
| E6 | `GET /engine/inputs?code=` §6.9/§5.27 | 进入 Tab / 切换资产 | `ddsm_3d[]{feature,group,label,raw,raw_unit,z,level,level_label,ic_sign,signed_z,formula},crowd_6d[]`（同结构）、`crowd{composite_z,quantile,quantile_level,quantile_threshold,is_veto,status,klow2,klow2_quantile,klow2_level,klow2_threshold,klow2_is_veto,klow2_status},code,name,train_as_of,snapshot_at` | 成功渲染 z-bar+复合判断；`level=null` 不切档；`status=missing`「数据缺失」（不显示为 pass）；失败「特征不可读」；空「暂无特征快照」；资产下拉取 `/holdings` 的 A/B 档 code；**深链直落引擎页时先补拉 `/holdings`** |
| E7 | `GET /engine/ddsm/cube?code=` §6.11.7/§5.25 | 进入 Tab / 切换资产 | `dims,bins_per_dim,**production_layer,research_layer,default_layer,dual_view_note**,vlabels[5],layers[5]{vr_layer,vr_label,cell_axis,cells[25]{state,vr_layer,status,is_empty,naive_n,naive_p,ddsm_n,ddsm_p,color_band},filled_count,empty_count},comparison{...},legend[],train_as_of,snapshot_at` | 成功=**ddsm 生产口径默认单切片 + naive 研究口径折叠 `<details>`** + vr 层切换 + 图例 + 对比卡 + 长文；`status=empty`/`naive_p=null` → **斜纹「无样本」，绝不渲染 0/50%**；`color_band` 决定格色（前端不重算分档）；`walk_forward_delta_*=null`→「待复现」；失败「状态表不可读」 |
| E8 | `GET /engine/registry` §6.9 | 进入 Tab（+设置页复用） | `engines[]{version,status,note,metrics{hit_rate,baseline_rate,delta_pp},can_rollback}` | 成功表；`active` 绿/`shadow|retired` 灰；失败「注册表读取失败」 |
| E9 | `GET /tasks` §6.9 | 预留 | `tasks[]{task_id,type,status,progress,step,...}` | 当前未直接展示；保留 `loadSlice('tasks')` 能力 |

### 8. ⑦ 设置页 settings

| 编号 | 接口 | 时机 | 需要字段（v4） | 前端四态处理 |
|---|---|---|---|---|
| T1 | `GET /settings` / `PUT /settings` §6.10/§5.16 | 进入 Tab | `privacy.masked,privacy.mask_holdings_only,llm.{enabled,provider,model,api_key_set,temperature,output_format,mode,base_url},port,auto_refresh,refresh_interval_sec,theme` | 加载=表单脉冲；成功=开关联动 `body.masked`（全站 `.amt` 打码，占比/涨跌保留），Key 只显示 `api_key_set`（**永不回显明文**）；失败=toast，已填内容不丢；温度/输出格式只读；`base_url` 见 §10 缺口 3 |
| T2 | `GET /settings/holdings-data` §6.11.15/§5.33 | 进入 Tab | `primary_path,primary_exists,primary_modified_at,primary_count,legacy_path,legacy_exists,legacy_modified_at,legacy_count,consistent,diff_fields[],readonly,diff_note,checked_at` | 成功=数据卡+长文；`consistent=false` 红 tag+`diff_fields`；失败「读取数据文件失败」；`readonly` 恒 true |
| T3 | `POST /holdings/import` §6.2 | 设置页「重新导入」 | 请求 `{mode:'replace'}`；响应 `{imported_count,source,imported_at,warnings[]}` | 提交中禁用；成功 toast+重拉 holdings/holdings-data；失败 toast（`E_IO`/`E_PARSE`）；本期只用 `replace` |
| T4 | `GET /about` §6.10 | 进入 Tab | `product_name,version,api_version,python_min,deployment,storage_note,disclaimer,built_at` | 说明型；成功=只读卡 |

### 9. 四态统一与错误映射（全接口通用）

- 请求入口唯一：`api.js#request` → 统一信封 `{ok,data,error,as_of}`；非 `ok` 抛 `ApiError{code,message,detail}`；超时（默认 8s / 慢接口 30s）→ `E_TIMEOUT`；网络失败 → `E_NETWORK`。
- 错误文案：`copy.js#ERROR_COPY` 按契约 §3 的 10 个枚举映射；未知 code 显示「发生未知错误：<message>」，**不吞 message**。
- 四态：`loading`（骨架/脉冲，**不得显示数字**）/ `empty`（仅「成功且集合为空」，且引擎离线不得进本态，A-06）/ `error`（红框+可读原因+重试，**不回退示例数据**）/ `success`（真实内容）；成功+引擎离线且带旧快照 → `success` + 强制陈旧条。
- 多切片陈旧：估值与预测 `as_of` 不同则各自标注，不用一个全局时间掩盖。
- 重试：只重发该切片请求，不整页刷新。

### 10. 契约缺口（前端实现受阻，请架构师裁定；**不自行发明接口/字段**）

> 补法均为**只加字段、不改名**（符合契约 §8/§9 纪律）。v4 已解决第 5 条（`weighting_policy_note`），其中标注 ✅。

1. **R-UI-05 建议列无数据源**：`HoldingRow` §5.1 无 `advice` 字段；Brief §9.1-5 要求「建议列」。前端现渲染 `—`（title 标注契约缺失）。请求追加 `advice`（枚举 `add/hold/reduce/watch`）+ 可选 `advice_label`，由后端产出，前端只展示。
2. **R-UI-12 参与预测表缺 `tier`/`market_value`**：`PredictionSummary` §5.4 无 `tier`、`market_value`。前端现从 `/holdings` 按 `code` 做**展示连接**（非业务计算）。请求追加 `tier`、`market_value`（元，2 位）。
3. **R-UI-33 LLM `base_url` 缺失**：`Settings.llm` §5.16 无 `base_url`。请求追加 `llm.base_url`（string，PUT 可写、GET 回传）。
4. **R-UI-02 估值精度分组中文标签缺失**：`/valuations/precision` 的 `groups` 元素仅 `{confidence,count,market_value,weight_ratio}`。请求为元素追加 `label`（或复用 `Valuation.confidence_label` 映射）。
5. ✅ **已解决（v4）**：组合加权长文——`PortfolioForecast.weighting_policy_note`（A-08）。
6. **R-UI-24 `window_min_days` 结构不明确**：§5.14 仅注 `array[object]`，示例 `[{d15:5},...]` 未给元素键名。前端两者兼容（`n_w` 优先，否则取首键）。请求明确为 `[{window:"d15", min_days:5}, ...]`（与 `window_weights` 对齐）。
7. **R-UI-17 治理周期 `last_run_at` 可空**（非阻塞）：前端已显示「—」，确认可空语义即可。
8. **顶层 `empty` 与 `engine_status` 的判定权**：`/holdings`、`/signals/state` 等响应未统一携带 `engine_status`；前端仅对 `/predictions`、`/portfolio/forecast` 依 A-06 区分陈旧态。若非必经可维持现状；若需同样陈旧态，请追加 `engine_status`。
9. **`FrozenParams.license_lines`（§5.14）元素键名未冻结**：示例为 `[{candidate:50},{probation:60,window_k:0.5},...]`，与 §5.32 `{license,threshold,condition,note}` 不一致。前端两者兼容（`license`/首键 + `min_independent_days`/`threshold`），请求统一为 §5.32 形态。

## 自验收

- [x] 每个接口写明「调用页面/时机 + 用途 + 需要字段 + 前端如何四态处理」
- [x] 字段名全部引用 `09-api-contract.md` **v4**（逐字一致），未自造字段
- [x] v4 增量字段（A-07/A-08/A-09/A-10）逐条落到消费点（§0）
- [x] 明确标注 mock 依赖与默认关闭开关（§6 摘要；`mock/` 隔离）
- [x] 契约缺口集中列出（§10，共 9 条，需架构师裁定）
- [x] 未修改任何契约/架构文件；未写 Python 业务代码；未改 `runtime/**`；未派发子任务

## 下游交接

- **主消费方**：`backend-dev`。需其执行：按 §1~§8 逐接口实现，字段名与 v4 逐字一致（G-BE-02 红线）；**v4 追加字段必带**（`weighting_basis`/`weighting_policy_note`、`production_layer`/`research_layer`/`default_layer`/`dual_view_note`、`color_scheme`/`color_token_prefix`、`retention_policy`/`first_of_day_immutable`/`archive_manifest_at`、`FrozenParams.weighting_basis`）；`created_at` INSERT-ONLY 且与 `written_at` 恒等；立方体空样本格显式返回 `naive_p=null`、`color_band='no_sample'`。
- **次消费方**：`architect`（裁定 §10 缺口并版本 +1 通知双边）、`dev-lead`（评审方向偏差）、`qa`（按四态与命脉组件建负向用例）。
- **契约缺口处理**：§10 的 1~4、6、9 若在 S3 内不裁定，前端保持当前降级展示（建议列「—」、precision 显示本地映射、LLM Base 仅前端暂存不回传、license/window_min_days 双形态兼容），不阻塞联调，但 G-FE-01 复盘时需说明。
- **mock**：`static/js/mock/mock.js` 为后端替身，**默认关闭**；已补齐 v4 字段；验收时若发现 mock 默认开启即判 FAIL。
- **残留风险**：
  1. 125 格立方体与竞技场矩阵在 ≤900px 需横向滚动/折叠（责任人：frontend-dev，期限：S4）。
  2. 多接口并行时 `as_of` 可能不同，现仅在全局/引擎页标注，尚未逐卡标时点（责任人：frontend-dev，期限：S4）。
  3. ES module 必须经 `http://127.0.0.1` 访问，双击 HTML 会因 `file://` 限制失效（责任人：dev-lead，期限：S5，README 已注明）。
