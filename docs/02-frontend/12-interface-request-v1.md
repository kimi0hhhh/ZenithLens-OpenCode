---
artifact: 12-interface-request
owner: frontend-dev
version: v1
status: draft
supersedes: -
created: 2026-09-12
reviewers: [architect, backend-dev]
gate: G-FE-02
---

# 接口需求清单 · 极境 ZenithLens 前端（S3 · OC-S3-FE）

> 唯一法律 = `docs/01-architecture/09-api-contract.md` v3。本单**不重定义字段**，只按页面逐条引用契约编号与字段名，
> 便于 `backend-dev` 逐项核对（G-BE-02 红线）。发现契约缺口集中在 §3（共 8 条，需架构师裁定）。
> 前端产出口径：`static/js/api.js` 唯一 fetch 出口；字段名与契约 v3 逐字一致；数值展示一律经 `static/js/format.js`。

## 摘要

1. 前端共消费 **40 个接口**（v2 25 个 + v3 新增 15 个）；本单按 7 个页面 + 全局壳分组列出「调用页面 / 时机 / 用途 / 需要字段 / 四态处理 / 排序归属 / 备注」。
2. **四态统一**：所有请求经 `api.js` → store 切片 `{status: idle|loading|success|empty|error}` → 视图用 `components.js#mountState` 渲染；错误文案按 `error.code` 映射（`copy.js`），未知 code 不吞 message。
3. **A-06 落地**：引擎离线时 `/predictions`、`/portfolio/forecast` 若有旧快照走「成功 + 陈旧条」，无快照走 error；`empty` 仅承载「引擎已跑但集合为空」。前端在 `.stalebar` 展示 `as_of`，不用全局一个时间冒充同一时点。
4. **A-02/A-03/A-04/A-05 落地**：未知行 `market_value=null` 分列 `fallback_value`；组合 `direction` 三条件同时满足才显示「涨」；T+3/T+15 未验证走「观察」灰；否决层 `missing` 显示「数据缺失」且 `signal=abstain`。
5. **契约缺口 8 条**（§3）：其中 `建议列`、`/predictions` 的 `tier/market_value`、`llm.base_url`、precision 分组中文标签等为 UI 组件硬需求，请架构师裁定后版本 +1。
6. **mock 现状**：后端未就绪期间，本壳全部接口走 `static/js/mock/mock.js`（**默认关闭**，仅 `?mock=1` 或 `localStorage.zl_mock='1'` 开启）；对接真实后端时无需改视图层。详见 §4。

## 正文

### 1. 全局壳（每页常显）

#### 需求 G1：`GET /runtime`（契约 §6.1 / §5.18）
- 调用页面：全局 Topbar + 侧栏「数据快照」。
- 调用时机：启动一次，之后 15s 轮询。
- 用途：交易时段 chip、快照/滞后 chip、本次开口数、陈旧提示条 `#stale-banner`。
- 需要字段：`as_of`、`staleness.{is_stale,latest_date,days_behind,note}`、`open_count`、`trade_session`、`engine_status`、`port`。
- 前端处理 ├─ 加载中：chip 文案「连接中…」，livebar 保持 warn 脉冲
           ├─ 成功：`staleness.is_stale=true` → 顶部 `#stale-banner`「引擎未运行，展示 <latest_date> 快照」
           ├─ 失败：livebar 转 warn「引擎未运行…」，不阻塞各视图独立加载
           └─ 超时(>8s)：同失败态，用户可在当前视图点重试
- 排序：不涉及。备注：lag 文案仅展示后端 `days_behind`，前端不自行推日期。

#### 需求 G2：`GET /data-sources/health`（§6.10 / §5.17）
- 调用页面：全局 livebar 摘要 + 设置页数据源健康表。
- 调用时机：启动一次；设置页 `POST /data-sources/probe` 后重拉。
- 用途：livebar「N 个数据源不通」+ 设置页 `.kv` 行。
- 需要字段：`sources[].{source_id,label,status,last_ok_at,fail_count,latency_ms,note}`。
- 前端处理 ├─ 加载中：livebar 不显示源信息
           ├─ 成功：`status=bad` 计数；表格用 `status` 枚举映射 tag（ok/warn/bad/unchecked）
           ├─ 失败：livebar 仅保留引擎状态，不白屏
           └─ 超时(>8s)：同失败
- 备注：`latency_ms` 可空，空则不渲染耗时。

#### 需求 G3：`POST /data-sources/probe`（§6.10）
- 调用页面：设置页「立即检测」。
- 调用时机：用户点击。
- 需要字段：请求 `{source_id:null}`；响应 `Task`（§5.15）。
- 前端处理 ├─ 提交中：按钮态 + 行内「检测中…」脉冲
           ├─ 成功：1.2s 后重拉 health
           ├─ 失败：toast「检测失败：<message>」，恢复表格
           └─ 超时(>8s)：同失败

### 2. ① 持仓页 holdings（默认首页）

#### 需求 H1：`GET /holdings?with=valuation,nav,prediction`（§6.2 / §5.1 / §6.2.1）
- 调用时机：进入 Tab；与 precision/portfolio/coverage/predictions 并行（`Promise.allSettled`）。
- 用途：资产总览四卡（R-UI-01）、持仓明细表（R-UI-05）、未知格（命脉）。
- 需要字段：`rows[].{code,name,group,group_label,tier,shares,cost_amount,avg_cost,confirm_days,proxy_code,proxy_name,valuation,nav,prediction,market_value,mv_source,fallback_value,weight_ratio,today_pnl_amt,pnl_amt,return_rate,staleness}`；`summary.*`（`total_value/fallback_value/total_value_with_fallback/covered_cost_amount/today_pnl_amt/total_pnl_amt/return_rate/covered_count/total_count/coverage_note/as_of`）。
- 前端处理 ├─ 加载中：四卡 `—` 骨架 + 明细 3 行骨架（`mountState`，**骨架不显示数字**）
           ├─ 成功：金额走 `fmt.amt`、比率走 `fmt.rate`、涨跌红绿；`market_value=null` 显示「—」并分列 `fallback_value`；副标题用 `summary.coverage_note`
           ├─ 空数组：`empty` 态「还没有录入任何持仓」+「录入第一只基金」CTA
           ├─ 失败：`error` 态红框 + `error.code` 文案 + 重试按钮；**不回退示例数据**
           └─ 超时(>8s)：error 态「请求超时」+ 重试
- 排序：前端（按 `group_label` 分组、组内 `market_value` 降序；22 只量级无需分页）。
- 备注：`change_rate=0` 才渲染 `+0.00%`；`null` 一律「未知」斜体灰（**未知≠持平**）。

#### 需求 H2：`GET /valuations/precision`（§6.3）
- 调用时机：与 H1 并行。
- 用途：估值精度汇总条 `.vsum`（R-UI-02）。
- 需要字段：`groups[].{confidence,count,market_value,weight_ratio}`、`mode_distribution[].{mode,mode_label,count,market_value,weight_ratio}`、`weighted_mae_rate`、`industry_baseline_mae_rate`、`window_days`。
- 前端处理 ├─ 加载中：三个骨架 chip
           ├─ 成功：`weighted_mae_rate<=industry_baseline_mae_rate` 达标绿、否则金；口径 chip 虚线
           ├─ 失败：条内「估值精度读取失败」+ 重试（不拖垮四卡）
           └─ 超时(>8s)：同失败
- 备注：**分组中文标签依赖后端**（见 §3 缺口 4）；`weighted_mae_rate=null` 不展示该 chip。

#### 需求 H3：`GET /portfolio/forecast`（§6.5 / §5.7）
- 调用页面：持仓页 + 分析页（同源同一响应，两处共用 `forecastCard`）。
- 调用时机：进入 Tab；timeout 30s（慢接口例外）。
- 用途：三窗口组合预测卡（R-UI-11）。
- 需要字段：`windows[]`（固定 3 项 T1/T3/T15）`{window,weighted_p,coverage_ratio,coverage_value,open_value,total_value,open_count,min_coverage_ratio,min_open_count,coverage_threshold_met,excluded_ratio,threshold_source,direction,direction_reason,weighted_p_threshold,tier_excluded,engine_status,as_of}`；外层 `engine_status/as_of`。
- 前端处理 ├─ 加载中：三卡脉冲「正在计算三窗口预测…」（骨架罩本块）
           ├─ 成功：**`direction==='up'` 且 `coverage_threshold_met` 且窗口已验证**才显示「涨」红；否则灰「不表态」+ `direction_reason` 文案；`weighted_p=null`（T3）显示「—」+「该窗口无概率定式」；覆盖条用 `coverage_ratio`，其余占比用 **后端 `excluded_ratio`**
           ├─ 空态：`weighted_p=null` 且 `direction_reason=no_open` → 「今日无开口」
           ├─ 失败：卡内「预测服务暂不可用」+ 重试，不影响四卡/明细
           └─ 超时(>30s)：卡内「数据加载较慢」+ 重试
- 备注：前端**不做组合加权**；`tier_excluded` 文案直接用后端数组。

#### 需求 H4：`GET /holdings/coverage`（§6.11.1 / §5.19）
- 调用时机：与 H1 并行。
- 用途：覆盖度四档 `.covbar` +「失效三类」长文（R-UI-04）。
- 需要字段：`tiers[]`（固定 4，A/B/C/D）`{tier,tier_label,color,count,market_value,weight_ratio,description,action_hint,invalidation,member_names}`、`total_count`、`total_value`、`invalidation_note`、`no_solution_count`。
- 前端处理 ├─ 加载中：四格骨架
           ├─ 成功：档色用后端 `color`（**不硬编码**）；`weight_ratio=null` 显示「—」；`invalidation_note` 与「原理无解：N 只」原样渲染
           ├─ 失败：块内「档位读取失败」+ 重试
           └─ 超时(>8s)：同失败

#### 需求 H5：`GET /holdings/risk`（§6.11.2 / §5.20）
- 调用时机：**`details.fold` 展开才请求**（首屏不阻塞）。
- 用途：风险指标折叠区（R-UI-06）。
- 需要字段：`sharpe`、`var95_rate`、`downside_vol_rate`、`max_drawdown_rate`、`sample_days`、`stale`、`computed_at`、`note`。
- 前端处理 ├─ 加载中：四格「…」+脉冲
           ├─ 成功：`var95_rate`/`max_drawdown_rate` **正数即损失幅度**，负值类用 `--down` 展示；null 显示「—」（禁止用 0 冒充）
           ├─ 失败：展开区「风险指标计算失败」+ 重试
           └─ 超时(>30s)：同失败

#### 需求 H6：持仓 CRUD（§6.2）
- 调用页面：录入/编辑 dialog、加/减仓 dialog、删除确认。
- 需要端点与字段：
  - `POST /holdings`：`code,name,group,tier,shares,cost_amount,avg_cost,confirm_days,proxy_code`（`shares` 与 `cost_amount` 至少一项）。
  - `PUT /holdings/{code}`：同 POST 可选子集（`code` 不可改）。
  - `DELETE /holdings/{code}`：响应 `{deleted_code}`。
  - `POST /holdings/{code}/transactions`：`tx_type,shares,price,date,fee_amount`。
- 前端处理 ├─ 提交中：保存按钮 loading + disabled 防重复
           ├─ 成功：toast「已保存/已录入/已加仓/已删仓」+ **局部刷新**（重拉 H1/H3/H4）
           ├─ 失败：`E_VALIDATION`→toast/行内；`E_CONFLICT`（重复 code）→toast「已存在」；**不假成功**
           └─ 超时(>8s)：toast 失败，保持表单不丢输入
- 排序：不涉及。备注：删除二次确认走 `dialog`（不用 `confirm()`）；台账历史不删。

#### 需求 H7：`GET /valuations/{code}?history=true`（§6.3 / §5.2）
- 调用页面：持仓表估值徽章点击（R-UI-03 可追溯）。
- 需要字段：`valuation.trace_text`、`history[].{written_at,mode_label,is_first_of_day}`。
- 前端处理 ├─ 加载中：弹层「加载中…」
           ├─ 成功：列当日各次入账，首次标「当日首次口径」；`trace_text` 为空不编造
           ├─ 失败：toast「读取估值详情失败」；**不编造链路**
           └─ 超时(>8s)：同失败
- 备注：徽章主文案取 `valuation.mode_label` + `confidence_color_class`（后端驱动），本地映射仅作字段缺失兜底。

### 3. ② 分析页 analyze

#### 需求 A1：`GET /meta/definitions`（§6.11.4 / §5.22）
- 用途：T+1 口径 + 三执行路径（R-UI-10）。
- 需要字段：`formula`、`signal_time`、`timing_note`、`paths[].{path,label,steps,executable,caveat}`、`conclusion`。
- 四态：加载=折叠区脉冲；成功=B 路径标「可执行」；失败=「口径定义读取失败」；空态不适用（说明型）。
- 备注：`conclusion` 必须指向 `hold_existing`；前端不暗示当天买入。

#### 需求 A2：三窗口组合预测卡
- 复用 H3（同源同响应），此处不重复。

#### 需求 A3：`GET /predictions`（§6.4 / §5.4）
- 用途：参与预测持仓表（R-UI-12）+ 行点击展开六步链（R-UI-13）。
- 需要字段：`rows[].{code,gate,gate_label,p_up,ddsm_state,veto_crowd,veto_crowd_status,veto_klow2,veto_klow2_status,signal,signal_label,reason,windows{T1,T3,T15}}`、外层 `engine_status/as_of`。
- 前端处理 ├─ 加载中：3 行骨架
           ├─ 成功：`veto_*_status=missing` → 「数据缺失」tag（不得显示为「通过」）；T3/T15 `validation_status=pending_cv` → 「观察」灰；`p_up` 4 位小数
           ├─ 空数组：`empty` 态「今日无资产开口」
           ├─ 失败：`error` 态「预测明细读取失败」+ 重试
           └─ 超时(>30s)：同失败
- 排序：前端（按市值降序，市值来自 H1 显示连接）。
- 备注：**契约缺口**：`PredictionSummary` 无 `tier`/`market_value`，前端从 `GET /holdings` 按 `code` 做**展示连接**（非业务计算）；见 §3 缺口 2。

#### 需求 A4：`GET /predictions/{code}`（§6.4 `chain`）
- 用途：单只六步推导链（R-UI-13）。
- 需要字段：`chain[].{step,key,title,status,detail,metrics}`，`metrics` 键枚举同 §6.4。
- 四态：加载=弹层「加载中」；成功=六步链；失败=toast「读取推导链失败」；`status=missing` 显示「数据缺失」。
- 备注：出口步必含 `exit_threshold=0.5200`。

### 4. ③ 信号页 signals

#### 需求 S1：`GET /signals/state`（§6.11.3 / §5.21）
- 用途：空态四要素（R-UI-07）+ 触发门 E1/E3 卡与 E2/E4 剔除（R-UI-08）。
- 需要字段：`state`、`monitored_count`、`total_count`、`days_since_last_open`、`last_open{date,code,name,gate,result,t1_real}`、`last_result`、`empty_note`、`gates[]{gate,gate_key,label,formula,role,effect_pp,t_value,note}`、`excluded_gates[]`、`or_merge_forbidden`。
- 前端处理 ├─ 加载中：脉冲骨架
           ├─ 成功：`state=no_open` 渲染四事实卡 + `empty_note`（强调「不是故障」）；门卡 `effect_pp` 以 pp 展示
           ├─ 失败：`error` 态「读取信号台账失败」+ 重试
           └─ 超时(>8s)：同失败
- 备注：`gates`/`excluded_gates` 各固定 2 项由后端保证。

#### 需求 S2：`GET /ledger?limit=60`（§6.7 / §5.9）
- 用途：信号时间线 `.tl/.tl-item/.sigcard`（R-UI-09）。
- 需要字段：`rows[].{date,code,name,tier,gate,p_up,ddsm_state,veto_crowd,veto_klow2,signal,t1_real,chain_available,created_at}`。
- 前端处理 ├─ 加载中：脉冲骨架
           ├─ 成功：`signal=up` 红点/弃权空心；`t1_real=null` → 「待回填」；`chain_available=false` 不请求链
           ├─ 空数组：`empty` 态「近 60 天无信号」
           ├─ 失败：`error` 态「台账不可读」+ 重试
           └─ 超时(>8s)：同失败
- 备注：**只读**，无编辑/删除入口（PRD G10）。

#### 需求 S3：`GET /ledger/chain?date&code`（§6.11.5 / §5.34）
- 用途：时间线卡片点击展开事件链 `.ev`。
- 需要字段：`chain[].{step,key,title,status,detail,metrics}`、`source_ledger`、`created_at`。
- 四态：点击时异步加载（`.ev` 内「链路不可读」为失败态）；成功渲染六步；`E_NOT_FOUND` 显示不可读。
- 备注：禁止前端编造步骤数值。

### 5. ④ 因子页 factors

#### 需求 F1：`GET /factors/pans`（§6.8 / §5.11 / §5.12）
- 用途：因子四盘 + 因子行 + 六窗 lift bars（R-UI-14）。
- 需要字段：`pans[]`（固定 4，顺序 正式/淘汰影子/有效影子/冷冻）`{role,role_label,description,factor_count,factors[],rule_text,pan_status,flow_kind,updated_at,factor_cap,nomination_limit}`；`factors[].{factor_id,name,role,role_label,score,total_score,status,license,license_label,lift_bars[6],independent_trigger_days,death_condition,note,ab_progress,added_at}`。
- 前端处理 ├─ 加载中：盘骨架
           ├─ 成功：盘 `rule_text` 原样渲染；`lift_bars` 驱动 bars；总分与牌照/角色 tag
           ├─ 空盘：盘内「（当前为空）」
           ├─ 失败：`error` 态「因子账本读取失败」+ 重试
           └─ 超时(>30s)：同失败
- 备注：盘色/健康语义取 `pan_status`（on/warn/bad），前端不硬编码。

#### 需求 F2：`GET /factors/books`（§6.8 / §5.13）与 `GET /factors/books/{book}`（§6.11.12）
- 用途：四本账本 + 示例记录（R-UI-15）。
- 需要字段：`books[]`（固定 6）`{book,book_label,filename,purpose,record_kind,schema_fields,record_count,last_record_at,sample}`；展开响应 `{book,book_label,record_kind,schema_fields,records[],total,last_record_at}`。
- 前端处理 ├─ 加载中：骨架
           ├─ 成功：因子页展示前 4 本；**表头由 `schema_fields` 生成**（不硬编码）
           ├─ 无记录：`records=[]` → 「待写入」
           ├─ 失败：`error` 态「账本读取失败」+ 缺失文件名
           └─ 超时(>30s)：同失败
- 备注：只读，无编辑/删除。

#### 需求 F3：`GET /factors/score-chain`（§6.8）
- 用途：评分链长文（R-UI-16）。
- 需要字段：`lift_bins[]{min_lift,k_lift,label}`、`window_weights[]{window,window_label,weight}`、`formula_text`、`bootstrap_percentiles{p50,p90,p95,p99,p995}`、`judges[]{judge,scope,metric,note}`、`floor_note`、`rule_source`。
- 四态：说明型；成功=长文；失败显示占位。

#### 需求 F4：`GET /factors/score-detail?factor_id`（§6.11.11 / §5.23）
- 用途：因子行展开跑分表（R-UI-14）。
- 需要字段：`windows[]{window,window_label,lift,k_lift,weight,independent_trigger_days,n_w,admission,score,cliff_hit}`、`total_score`、`bootstrap_percentiles`、`judges`、`formula_text`。
- 四态：展开时异步；成功渲染表；缺失字段显示「—」（禁止估填）；失败「跑分表读取失败」。
- 备注：前端**不做 `k_lift×权重×准入度` 计算**，直接用后端 `score`/`total_score`。

#### 需求 F5：`GET /factors/governance-cycle`（§6.11.13 / §5.30）
- 用途：治理周期卡（R-UI-17）。字段：`phases[]{phase,label,cadence,status,last_run_at,next_run_at,rule_text,human_retained}`、`note`。
- 四态：成功=五卡；空/失败显示占位文案。

#### 需求 F6：`GET /factors/dig-records`（§6.11.14 / §5.31）
- 用途：最近挖掘记录表（R-UI-18）。字段：`records[]{scan_date,candidate,f1_result,f1_detail,f2_result,f2_detail,f3_result,f3_detail,verdict,verdict_text,nomination_week,cooldown_until,created_at}`、`panel{nomination_limit,cooldown_days,week_rule}`。
- 四态：成功=六列表；`na`→「—」；空「尚无挖掘记录」；失败占位。

#### 需求 F7：`GET /factors/lifecycle`（§6.8 / §5.32）
- 用途：生命周期规则长文（R-UI-19）。字段：`admission_rules[]`、`license_lines[]{license,threshold,condition,note}`、`retire_rules[]`、`dual_exit[]`、`false_kill_guards[]`、`revive_rules[]`、`source`、`freeze_note`。
- 四态：说明型；文本来源由后端 `source` 给出，前端不硬编码规则。

### 6. ⑤ 复盘页 review

#### 需求 R1：`GET /review/scores`（§6.6 / §5.8）
- 用途：历史成绩 hero（R-UI-28）+ 三窗口 vs 基线表（R-UI-29）。
- 需要字段：`scores[]{window,formula,hit_rate,open_count,baseline_rate,baseline_status,delta_pp,cv_mode,purge_gap,holdout_days,data_kind,sample_period,as_of}`、`hero{window,hit_rate,baseline_rate,delta_pp,label}`。
- 前端处理 ├─ 加载中：hero 脉冲
           ├─ 成功：`baseline_status=pending` → 基线/Δ 显示「待填充」**不着色**；Δ 正负着色；`data_kind=shadow_live` 标「实盘」
           ├─ 空：`scores=[]` → 「尚无成绩记录」
           ├─ 失败：`error` 态「读取成绩失败」+ 重试
           └─ 超时(>30s)：同失败
- 备注：前端不计算 Δ（直接用 `delta_pp`）。

#### 需求 R2：`GET /review/reconciliation?limit=60`（§6.6 / §5.10）
- 用途：逐笔对账表（R-UI-31）。字段：`ReconcileRow`（= `LedgerEntry` + `result`）。
- 四态：成功八列；`result=pending`「待回填」；空「暂无台账记录」；失败「台账不可读」。
- 备注：`result` 由后端按规则计算，前端不判定。

#### 需求 R3：`GET /review/cv-config`（§6.6）
- 用途：复盘口径悬浮（purge/holdout）。字段：`cv_mode,random_split,purge_gap,placebo_min_pp,holdout_days,holdout_start_date,ledger_policy`。
- 四态：成功填入脚注；失败不阻塞主表。

#### 需求 R4：`GET /engine/shadow-review`（§6.11.10 / §5.29）
- 用途：影子盘降级审查条（R-UI-30）。字段：`status`、`rolling_days`、`hit_rate`、`baseline_rate`、`deviation_pp`、`threshold_pp`、`message`、`checked_at`、`note`。
- 四态：`idle` 灰条 / `ok` 绿条 / `bad` 红条；成功显示滚动命中率 vs 基准；失败红条「审查读取失败」。

### 7. ⑥ 引擎页 engine

#### 需求 E1：`GET /engine/status`（§6.9）—— 12s 轮询
- 用途：HUD 六卡（R-UI-20）。字段：`status,pid,port,version,active_engine_version,started_at,last_heartbeat_at,last_success_at,snapshot_as_of,shadow_status,shadow_consecutive_days,shadow_target_days,training_assets,index_only_assets,state_grid_total_cells,state_grid_filled_cells,state_grid_coverage_pct,avg_samples_per_cell,min_samples_cell,last_retrain_at,next_retrain_at,data_freshness_snapshot_date,data_freshness_days_behind`。
- 四态：`offline` + 快照 → 成功 + 陈旧条；`offline` 无快照 → error；成功渲染六卡；失败「无响应」+ 重试。
- 备注：离开页面停止轮询（`deactivate`）。

#### 需求 E2：`GET /ledger/shadow?limit=60`（§6.11.6 / §5.28）
- 用途：影子盘台账表 + 连续记录进度条 + 字段说明（R-UI-21）。字段：`rows[]`（`LedgerEntry` 含 `created_at`）、`total`、`summary{total_records,open_signals,veto_abstains,backfilled_count,hit_rate,baseline_rate}`、`progress{status,consecutive_days,target_days,progress_ratio,start_date,target_date,gap_days,hit_rate,baseline_rate,deviation_pp,note}`、`field_list`、`insert_only_note`。
- 四态：`not_started` → 进度 0/60；`hit_rate=null` → 「—」；成功渲染。
- 备注：只读，`created_at` INSERT-ONLY。

#### 需求 E3：`GET /engine/arena`（§6.11.9 / §5.24）
- 用途：因子竞技场矩阵（R-UI-22）。字段：`windows[6]`、`rows[]{config_id,config_name,config_kind,is_leave_one_out,is_highlight,warning,cells[]{window,open_count,hit_rate,paired_delta_pp,is_leave_one_out,warning,color,is_window_max,is_window_min}}`、`legend[]`、`naive_method_note`、`as_of`。
- 四态：成功=矩阵；`warning` → 金 ▲；配色**只用后端 `color`**（red/green/blue/yellow/base）；空「竞技场暂无配置」；失败占位。
- 备注：裸算法基准行不参与红绿排名（后端保证）。

#### 需求 E4：`GET /engine/training-status`（§6.11.8 / §5.26）
- 用途：训练状态卡（R-UI-23）。字段：`total_cells,filled_cells,coverage_pct,avg_samples_per_cell,min_samples_cell,min_n,noise{k_noise,p_perturb},train_mode,noise_text,retrain_cycle,last_retrain_at,next_retrain_at,retrain_note,training_assets,index_only_assets,dead_ends[]`。
- 四态：成功四格 + 长文 + 死路清单；失败「训练状态不可读」。

#### 需求 E5：`GET /engine/frozen-params`（§6.9 / §5.14）
- 用途：冻结参数表（R-UI-24）。字段：`k_noise,p_perturb,min_n,shrink,band,veto_crowd_quantile,veto_klow2_quantile,min_coverage_ratio,min_open_count,gate_e1,gate_e3,purge_gap,window_weights[],window_min_days[],license_lines[],change_policy`。
- 四态：只读表；行悬停解释；`change_policy` 常显；**无编辑入口**。
- 备注：见 §3 缺口 6（`window_min_days` 结构）。

#### 需求 E6：`GET /engine/inputs?code=`（§6.9 / §5.27）
- 用途：六维输入 z-bar（R-UI-25）。字段：`ddsm_3d[]{feature,group,label,raw,raw_unit,z,level,level_label,ic_sign,signed_z,formula}`、`crowd_6d[]`（同结构）、`crowd{composite_z,quantile,quantile_level,quantile_threshold,is_veto,status,klow2,klow2_quantile,klow2_level,klow2_threshold,klow2_is_veto,klow2_status}`、`code,name,train_as_of,snapshot_at`。
- 四态：成功渲染 z-bar 与复合判断；`level=null` 六维不切档；失败「特征不可读」；空「暂无特征快照」。
- 备注：资产下拉从 `/holdings` 的 A/B 档 code 生成；切换即重拉 inputs + cube。

#### 需求 E7：`GET /engine/ddsm/cube?code=`（§6.11.7 / §5.25）
- 用途：125 格状态立方体 naive vs DDSM（R-UI-26）。字段：`dims`、`bins_per_dim`、`vlabels[5]`、`layers[5]{vr_layer,vr_label,cell_axis,cells[25]{state,vr_layer,status,is_empty,naive_n,naive_p,ddsm_n,ddsm_p,color_band},filled_count,empty_count}`、`comparison{valid_coverage_naive_pct,valid_coverage_ddsm_pct,mean_*,p_std_*,p_range_*,extreme_count_*,empty_count_*,walk_forward_delta_*}`、`legend[]`、`train_as_of`、`snapshot_at`。
- 四态：成功=双 5×5 切片 + vr 层切换 + 图例 + 对比卡 + 长文；`status=empty`/`naive_p=null` → **斜纹「无样本」，绝不渲染 0/50%**；失败「状态表不可读」。
- 备注：`walk_forward_delta_*` 未产出前为 null → 显示「待复现」。

#### 需求 E8：`GET /engine/registry`（§6.9）
- 用途：引擎注册表三态（R-UI-27，引擎页 + 设置页）。字段：`engines[]{version,status,note,metrics{hit_rate,baseline_rate,delta_pp},can_rollback}`。
- 四态：成功表；`active` 绿/`shadow|retired` 灰；失败「注册表读取失败」。

#### 需求 E9：`GET /tasks`（§6.9，可选）
- 用途：手动刷新估值/预测的任务轮询（预留）。字段：`tasks[]{task_id,type,status,progress,step,...}`。
- 四态：当前引擎页未直接展示任务列表；保留 `loadSlice('tasks')` 能力。

### 8. ⑦ 设置页 settings

#### 需求 T1：`GET /settings` / `PUT /settings`（§6.10 / §5.16）
- 用途：隐私开关（R-UI-32）、LLM 表单（R-UI-33）。
- 需要字段：`privacy.masked`、`privacy.mask_holdings_only`、`llm.{enabled,provider,model,api_key_set,temperature,output_format,mode,base_url}`、`port`、`auto_refresh`、`refresh_interval_sec`、`theme`。
- 前端处理 ├─ 加载中：表单禁用/脉冲
           ├─ 成功：开关联动 `body.masked`（全站 `.amt` 打码，占比/涨跌保留）；Key 只显示 `api_key_set`，**永不回显明文**
           ├─ 失败：toast「保存配置失败」；已填内容不丢
           └─ 超时(>8s)：同失败
- 备注：温度/输出格式只读；`base_url` 见 §3 缺口 3。

#### 需求 T2：`GET /settings/holdings-data`（§6.11.15 / §5.33）
- 用途：持仓数据卡 + 两份 `funds_data.json` 不一致长文（R-UI-35）。字段：`primary_path,primary_exists,primary_modified_at,primary_count,legacy_path,legacy_exists,legacy_modified_at,legacy_count,consistent,diff_fields[],readonly,diff_note,checked_at`。
- 四态：成功=数据卡 + 长文；`consistent=false` 红 tag + `diff_fields`；失败「读取数据文件失败」。
- 备注：`readonly` 恒 true，产品不改写源文件。

#### 需求 T3：`POST /holdings/import`（§6.2）
- 用途：设置页「重新导入」。字段：请求 `{mode:'replace'}`；响应 `{imported_count,source,imported_at,warnings[]}`。
- 四态：提交中禁用；成功 toast「已导入 N 只」+ 重拉 holdings/holdings-data；失败 toast `E_IO`/`E_PARSE`。
- 备注：本期只用 `replace`（`merge` 语义未冻结，见契约 §7 缺口声明）。

#### 需求 T4：`GET /about`（§6.10）
- 用途：关于卡（R-UI-36）。字段：`product_name,version,api_version,python_min,deployment,storage_note,disclaimer,built_at`。
- 四态：说明型；成功=只读卡。

### 9. 缺字段汇总（供架构师裁定）

见 §3「契约缺口」。

## §3 契约缺口（前端实现受阻，请架构师裁定；**不自行发明接口/字段**）

> 缺口按"不补则组件无法按 §9 交付"排序。补法均为**只加字段，不改名**（符合契约 §8 纪律）。

1. **R-UI-05 建议列无数据源**
   - 现象：`HoldingRow`（§5.1）无「建议/advice」字段；Brief §9.1-5 要求明细表有「建议列」。
   - 前端现状：渲染 `—` 并标 title「契约缺失建议字段」。
   - 请求：新增 `advice`（枚举 `add/hold/reduce/watch`）与可选 `advice_label`，由后端按规则产出；前端只展示不自算。
2. **R-UI-12 参与预测表缺 `tier`/`market_value`**
   - 现象：`PredictionSummary`（§5.4）无 `tier`、`market_value`；组件需「档」与「市值」两列。
   - 前端现状：从 `GET /holdings` 按 `code` 做**展示连接**（非业务计算）。
   - 请求：在 `PredictionSummary` 追加 `tier`、`market_value`（元，2 位），避免前端跨接口拼装。
3. **R-UI-33 LLM `base_url` 缺失**
   - 现象：`Settings.llm`（§5.16）无 `base_url`；组件需「Base URL」输入并持久化。
   - 请求：追加 `llm.base_url`（string），`PUT` 可写、`GET` 回传。
4. **R-UI-02 估值精度分组中文标签缺失**
   - 现象：`/valuations/precision` 的 `groups` 元素仅 `{confidence,count,market_value,weight_ratio}`；UI 需「误差达标/中等/偏大/无可信估算」。
   - 前端现状：显示原始枚举（high/mid/low/unknown）。
   - 请求：为 `groups` 元素追加 `label`（或复用 `Valuation.confidence_label` 的映射），保持既有字段不变。
5. **R-UI-11 加权三规则长文无字段**
   - 现象：`PortfolioForecast`（§5.7）无规则长文字段；UI 设计要求「加权三规则」长文。
   - 前端现状：用产品说明性静态文案（非业务数值）。
   - 请求：可选追加 `rules_text`（string），由后端返回；前端优先渲染后端文本。
6. **R-UI-24 `window_min_days` 结构不明确**
   - 现象：`FrozenParams.window_min_days`（§5.14）仅注为 `array[object]`，未给元素键名；现按 `[{d15:5},...]` 解析（取首个键）。
   - 请求：明确为 `[{window:"d15", min_days:5}, ...]`（与 `window_weights` 对齐）。
7. **R-UI-17 治理周期 `last_run_at` 可空**（非阻塞）
   - 现象：`CyclePhase.last_run_at` 可空；前端已显示「—」。
   - 请求：确认可空语义即可，无需改字段。
8. **顶层 `empty` 与 `engine_status` 的判定权**
   - 现象：`/holdings`、`/signals/state` 等响应未统一携带 `engine_status`；前端仅能对 `/predictions`、`/portfolio/forecast` 依 A-06 区分「旧快照陈旧态」。
   - 请求：非必经；若上述端点也需陈旧态，请追加 `engine_status`（与 §5.7 一致），否则前端以 error/成功两态处理。

## 自验收

- [x] 每个接口写明「调用页面 + 调用时机 + 用途 + 需要字段 + 前端如何处理四态」
- [x] 字段名全部引用 `09-api-contract.md` v3（逐字一致），未自造字段
- [x] 明确标注 mock 依赖（§4）与默认关闭开关
- [x] 契约缺口集中列出（§3，共 8 条，需架构师裁定）
- [x] 未修改任何契约文件；未写 Python 业务代码；未改 `runtime/**`

## 下游交接

- **主消费方**：`backend-dev`。需其执行：按本单 §1~§8 逐接口实现，字段名与 v3 逐字一致（G-BE-02 红线）；实现顺序建议 `/runtime → /holdings → /valuations/precision → /portfolio/forecast → /holdings/coverage → /predictions → /review/* → /ledger* → /factors/* → /engine/* → /settings*`；`created_at` INSERT-ONLY 且与 `written_at` 恒等；立方体空样本格显式返回 `naive_p=null`。
- **次消费方**：`architect`（裁定 §3 缺口并版本 +1 通知双边）、`dev-lead`（评审方向偏差）、`qa`（按四态与命脉组件建负向用例）。
- **契约缺口处理**：§3 的 1~6 若在 S3 内不裁定，前端保持当前降级展示（建议列「—」、precision 显示枚举、LLM Base 仅前端暂存不回传），不阻塞联调，但 G-FE-01 复盘时需说明。
- **mock**：`static/js/mock/mock.js` 为后端替身，**默认关闭**；`backend-dev` 接口就绪后，前端不改视图层即可切换。验收时若发现 mock 默认开启即判 FAIL。
- **残留风险**：
  1. 125 格热力图与竞技场矩阵在 ≤900px 需横向滚动/折叠（责任人：frontend-dev，期限：S4）。
  2. 多接口并行时 `as_of` 可能不同，现仅在全局/引擎页标注，尚未逐卡标时点（责任人：frontend-dev，期限：S4）。
  3. ES module 必须经 `http://127.0.0.1` 访问，双击 HTML 会因 `file://` 限制失效（责任人：dev-lead，期限：S5，README 已注明）。
