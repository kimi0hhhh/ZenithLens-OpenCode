---
artifact: 09-api-contract
owner: architect
version: v3
status: approved
supersedes: v2
created: 2026-09-12
reviewers: [frontend-dev, backend-dev, qa, product-manager, orchestrator]
gate: G-AR-05
---

# 接口契约 · 极境 ZenithLens

> **本文件是前后端唯一法律**（角色契约 §4）。契约模糊一天，联调返工三天。
> 上游：`docs/01-architecture/07-frontend-arch.md`、`docs/01-architecture/08-backend-arch.md`、`docs/00-charter/03-ui-design.md`。
> 零容忍规则：字段名一律 `snake_case` 且全项目统一；每个字段给**类型 + 单位 + 精度 + 口径说明**；枚举穷举，不出现"等"；时间字段给格式与时区。

## 摘要

1. 共 **30 个接口**，分 9 个域：元信息 / 持仓 CRUD / 实时估值 / 预测 / 组合加权 / 复盘 / 台账 / 因子 / 引擎 / 任务 / 设置。
2. 统一信封 `{ok, data, error, as_of}`；错误码 10 个穷举枚举。
3. 全局数值口径冻结（§1）：概率 `*_p`、比率 `*_rate`/`*_ratio` 一律**小数非百分数**，展示层 ×100；金额元 2 位、份额/净值 4 位、z 值 3 位。
4. **估值 ≠ 净值**：`valuation`（今日预估，可能 official/估算）与 `nav`（官方已公布值）两组独立字段；徽章文案由 `valuation_mode` 唯一定义（§5.2、§6）。
5. 未知口径：`change_rate=null` 表示无任何可信估值；前端必须渲染"未知"，禁止 `+0.00%`。
6. **v2 裁定（G-AR-06 会签，速查）**：当日估值快照改为 **INSERT-ONLY**（`valuation_history.jsonl` 审计源，`valuation-YYYYMMDD.json` 降级为可重建缓存，A-01）；`market_value` **禁止成本价回退**，新增 `fallback_value`/`total_value_with_fallback`（A-02）；组合 `direction` 新增**最小覆盖门槛**（`min_coverage_ratio=0.30`/`min_open_count=3`，A-03）；T+3/T+15 新增 `validated`/`formula_source`，未验证**不得显示 `up`**（A-04）；否决层数据缺失 → `signal=abstain` + `veto_data_missing`（A-05）；引擎离线**禁止用 `empty` 承载**（有旧快照走 stale，无快照走 `error`，A-06）。
7. 变更纪律：v2 相对 v1 的字段增删见 `docs/01-architecture/10-arch-review.md §1`（逐条裁定）；前后端须按 v2 实现，v1 已冻结为历史（`09-api-contract-v1.md`）。
8. **v3 裁定（PROJECT_BRIEF §9 · 40 项 P0 特调组件，2026-09-12）**：v2 只提供"集合级"聚合（如 `/engine/ddsm` 给全局 125 格、`/engine/inputs` 只给 z），**不足以让前端还原 legacy v2 壳的状态立方体 / 六维输入 / 因子治理 / 竞技场 / 置信度徽章 / 时序链 / 影子盘台账**。v3 **只加字段与接口、不改任何既有字段名**，补齐 §9 全部特调组件的数据支撑：新增 **15 个接口**（§4 第 39~53 项）与 **16 个共享对象**（§5.19~§5.34），并对既有对象**追加**字段（`Valuation`/`LedgerEntry`/`FactorPan`/`FactorItem`/`FactorBook`/`/engine/status`/`/engine/inputs`/`/engine/ddsm`/`/engine/frozen-params`）。
9. **v3 数据契约七件套**（硬性约束 #1）：① 逐资产 125 格状态立方体（naive 与 ddsm 两套 P + n + vr 层索引 + 空样本格显式表达）；② 六维输入（原值/z-score/档位/IC 符号/复合 z/是否否决）；③ 因子治理（四盘/评分链每窗 lift·k_lift·权重·独立触发日·准入度·得分·总分/四本账本条目/治理周期/挖掘记录 F1F2F3/生命周期文本来源）；④ 竞技场矩阵（行=配置、列=六窗、格=开口数/命中率/配对 Δ/留一法/警示）；⑤ 影子盘台账（`created_at` INSERT-ONLY + 连续记录进度）；⑥ 估值置信度徽章（mode 五档 + confidence + MAE + 方向命中率 + 样本数 + trace）；⑦ 单信号六步推导链可作数据返回。
10. 变更纪律：v3 相对 v2 的逐条追加见 §8「v3 追加清单」；前后端须按 v3 实现，v2 已冻结为历史（`09-api-contract-v2.md`）；v1/V2 所有既有字段名保持向后兼容。

## 正文

### 1. 全局约定（冻结）

#### 1.1 命名与时间

- 所有字段名 `snake_case`，不使用驼峰（禁止 `navDate`）。
- 日期字段：`*_date`，格式 `YYYY-MM-DD`，时区 `Asia/Shanghai`。
- 时间戳字段：`*_at`，格式 ISO 8601 带偏移，如 `2026-09-12T15:30:00+08:00`，秒级精度。
- 布尔字段：`is_*` 或既有语义名（如 `veto_crowd`），值为 `true/false`，不用 0/1。

#### 1.2 数值单位与精度（全项目统一，展示层 ×100）

| 后缀/字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `*_p`（`p_up`/`weighted_p`/`hit_rate`? 否，`hit_rate` 见下） | number | 概率（小数） | 4 位 | 范围 [0,1]；0.6100 表示 61.00%。展示 ×100 保留 1 位 |
| `*_rate`（`change_rate`/`return_rate`/`hit_rate`/`baseline_rate`/`mae_rate`/`official_change_rate`/`t*_real`） | number | 比率（小数非百分数） | 4 位 | 0.0124 = +1.24%；0.583 = 58.3%。**禁止**出现 12.42 表示 12.42% |
| `*_ratio`（`weight_ratio`/`coverage_ratio`/`excluded_ratio`） | number | 比率（小数） | 4 位 | 范围 [0,1]；1.0 = 100% |
| `delta_pp` | number | 百分点（小数） | 4 位 | 0.099 = +9.9pp；= `hit_rate − baseline_rate` |
| `*_amt`（`total_value`? 无后缀者见注） | number | 元 | 2 位 | 金额；`total_value`/`market_value`/`cost_amount`/`covered_cost_amount`/`open_value`/`coverage_value`/`today_pnl_amt` 均为元 |
| `fallback_value` / `total_value_with_fallback` | number/null | 元 | 2 位 | 未知行按成本计的金额口径（A-02）；可空仅因无持仓，非"未知" |
| `shares` | number | 份 | 4 位 | 基金份额 |
| `nav`/`estimated_nav`/`official_nav`/`previous_nav`/`avg_cost` | number | 元/份 | 4 位 | 单位净值 |
| `z` / `*_z` | number | 标准差倍数 | 3 位 | z-score |
| `mae_rate` | number | 比率（小数） | 4 位 | 平均绝对误差；0.0062 = 0.62% |
| `progress` | number | 比率（小数） | 2 位 | [0,1] |
| `latency_ms` | integer | 毫秒 | 整数 | — |
| `days_behind` | integer | 自然日 | 整数 | 陈旧度 |

**v3 追加单位（追加到上表，不改既有行）**：

| 后缀/字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `*_lift`（`lift`/`k_lift` 除外见注） | number | 倍数 | 4 位 | `lift = 命中率 ÷ 基线`；1.06 = 命中率是基线的 1.06 倍；`k_lift` 为查表后得分（分，4 位，可负） |
| `*_score` / `*_total_score` | number | 分 | 4 位 | 因子评分链得分；可负（悬崖惩罚）；总分 = 六窗得分之和 |
| `*_count`（`count`/`open_count`/`filled_count`/`empty_count`/`record_count`/`nomination_count`） | integer | 个/只/次/条/格 | 整数 | 计数；单位随语义，见字段口径 |
| `*_std`（`p_std_naive`/`p_std_ddsm`） | number | 概率 | 4 位 | 概率分布标准差（[0,0.5]） |
| `*_quantile`（`crowd_quantile`/`klow2_quantile`） | number | 分位 | 4 位 | [0,1]；0.60 = 从低到高第 60 百分位 |
| `*_z`（`z`/`composite_z`） | number | 标准差倍数 | 3 位 | z-score |
| `*_pct` | number | 比率（小数） | 4 位 | 仅用于 v3 新增的"占位比"（如 `valid_coverage_pct`），语义同 `*_ratio`；展示层 ×100 |
| `eligible`/`is_*` | boolean | — | — | 布尔，`true/false` |

#### 1.3 枚举总表（穷举，禁止"等"）

| 枚举名 | 取值 | 中文 |
|---|---|---|
| `valuation_mode` | `official` / `intraday` / `holdings` / `proxy` / `unknown` | 官方净值 / 盘中估算 / 重仓加权 / 代理近似 / 未知 |
| `confidence` | `high` / `mid` / `low` / `unknown` | 高 / 中 / 低 / 无 |
| `coverage_tier` | `A` / `B` / `C` / `D` | 已接入 / 代理已验证 / 代理待验证 / 暴露待定 |
| `signal` | `up` / `gray` / `abstain` | 涨 / 灰（不表态） / 弃权 |
| `gate` | `E1` / `E3` / `none` | 跳空 / 无量急跌 / 未触发 |
| `window` | `T1` / `T3` / `T15` | — |
| `direction` | `up` / `down` / `gray` | 涨 / 跌 / 不表态 |
| `holding_group` | `domestic_index` / `active` / `qdii` / `gold` / `other` | 境内指数 / 主动 / QDII / 黄金 / 其他 |
| `tx_type` | `buy` / `sell` | 加仓 / 减仓 |
| `signal_reason` | `ok` / `gate_not_triggered` / `insufficient_data` / `veto_crowd` / `veto_klow2` / `veto_data_missing` / `below_band` / `tier_not_supported` | 成立/门未触发/数据不足/拥挤度否决/KLOW2 否决/否决层数据缺失/未过出口/档位不支持 |
| `veto_layer_status` | `pass` / `veto` / `missing` | 通过/亮灯否决/数据缺失 |
| `mv_source` | `valuation` / `nav` / `null` | 估值/官方净值/无（**禁 `fallback`**，A-02） |
| `validation_status` | `brief_mandated` / `validated` / `pending_cv` / `failed` | Brief 授权生产链/T+3T+15 已过 CV+placebo/T+3T+15 未验证/T+3T+15 未过 |
| `direction_reason` | `ok` / `no_open` / `insufficient_coverage` / `window_unvalidated` | 成立/无开口/覆盖未达门槛/窗口未验证（A-03/A-04） |
| `data_source_id` | `tencent_kline` / `tencent_rt` / `eastmoney` / `sina_rt` | 腾讯日K / 腾讯实时 / 天天基金 / 新浪实时 |
| `data_source_status` | `ok` / `warn` / `bad` / `unchecked` | 正常 / 波动 / 不通 / 未检测 |
| `engine_status` | `online` / `offline` / `running` / `error` | 在线 / 离线 / 运行中 / 异常 |
| `engine_registry_status` | `active` / `shadow` / `retired` | 生产 / 影子 / 退役 |
| `factor_role` | `adopted` / `shadow_retired` / `shadow_effective` / `frozen` | 正式盘 / 淘汰影子盘 / 有效影子盘 / 冷冻盘 |
| `factor_book` | `adopted_factors` / `scan_history` / `factor_health` / `retired_log` / `shadow_signals` / `factor_arena` | 采纳登记 / 挖掘台账 / 体检台账 / 淘汰台账 / 影子信号 / 因子竞技场 |
| `task_type` | `refresh_quotes` / `refresh_valuation` / `run_prediction` / `backfill_ledger` / `rebuild_ddsm` / `scan_factors` / `run_backtest` | — |
| `task_status` | `queued` / `running` / `done` / `failed` / `cancelled` | — |
| `trade_session` | `pre_open` / `trading` / `closed` / `non_trading_day` | 盘前 / 盘中 / 收盘后 / 非交易日 |
| `baseline_status` | `filled` / `pending` | 已填充 / 待填充 |
| `reconcile_result` | `hit` / `miss` / `abstain` / `pending` | 命中 / 未命中 / 弃权 / 待回填 |
| `llm_provider` | `deepseek` / `qwen` / `moonshot` / `custom` | — |
| `trace_reason` | `not_published` / `missing` / `timeout` / `parse_error` / `hit` / `no_mapping` / `no_report` | 未公布/缺失/超时/解析失败/命中/无映射/无持仓报告 |

**v3 追加枚举（追加到上表，穷举，禁止"等"；仅新增，不改既有取值）**：

| 枚举名 | 取值 | 中文 |
|---|---|---|
| `cube_layer` | `naive` / `ddsm` | 原始离散 / 还原离散 |
| `cube_cell_status` | `filled` / `empty` | 有样本（可估 P）/ 无样本（**无估计值，不得渲染成 0 或 50%**） |
| `factor_window` | `d15` / `d30` / `d60` / `m6` / `m24` / `full` | 15日 / 30日 / 60日 / 6月 / 24月 / 全样本 |
| `factor_status` | `active` / `probation` / `cooling` / `frozen` / `retired` | 现役 / 观察期 / 冷却 / 冷冻 / 已退役 |
| `factor_license` | `none` / `candidate` / `probation` / `renew_t2` / `full_t3` | 未达线(<50) / 候补(独立触发日≥50) / 试用(≥60 且 30日窗 k≥0.5) / 续聘 T2(≥70 且 60日窗 k≥0.7 且持牌满一季) / 正式 T3(≥80 且 24月窗 k≥0.7) |
| `score_judge` | `lift` / `t` / `admission` / `backtest` | 分数裁判 / 闸门裁判 / 折扣裁判 / 晋升裁判（四裁判各管一段） |
| `governance_phase` | `dig_scan` / `scorecard` / `monthly_rank` / `quarterly_review` / `ddsm_retrain` | 挖掘扫描 / 评分卡 / 月榜牌照 / 季复查 / DDSM 重训 |
| `cycle_status` | `scheduled` / `running` / `done` / `skipped` / `error` | 已排期 / 运行中 / 完成 / 跳过 / 异常 |
| `dig_level` | `F1` / `F2` / `F3` | 有效性 / 独立性 / 增量 |
| `dig_result` | `pass` / `fail` / `not_run` / `na` | 通过 / 未通过 / 未执行 / 不适用（前序未过则后续 `na`） |
| `dig_verdict` | `candidate_pool` / `admitted_to_arena` / `rejected_f1` / `rejected_f2` / `rejected_f3` | 回落候选池 / 进入竞技场影子盘 / 未过 F1 / 未过 F2 / 未过 F3 |
| `arena_config_kind` | `production` / `naive_baseline` / `leave_one_out` / `candidate` | 生产配置 / 裸算法基准（参照系，不参与红绿排名） / 留一法 C−eᵢ / 候选配置 |
| `arena_color` | `red` / `green` / `blue` / `yellow` / `base` | 该窗最高 / 该窗最低 / 居中 / 警示（Δ 低于裸算法基准 ▲） / 基准行（不着色） |
| `shadow_progress_status` | `not_started` / `recording` / `qualified` / `gap` | 未启动 / 连续记录中 / 已达 60 日门槛 / 记录中断（有漏单） |
| `shadow_review_status` | `idle` / `ok` / `bad` | 未启动 / 达标（偏差<2pp） / 降级（偏差≥2pp） |
| `execution_path` | `new_position` / `hold_existing` / `onsite_etf` | 新建仓位（吃晚一拍，非信号段）/ 已持有（可执行）/ 场内 ETF（open→close，口径不同） |
| `coverage_invalidation` | `definition_failure` / `data_failure` / `framework_failure` | 定义失效（真死）/ 数据失效（可补）/ 框架失效（待定暴露） |
| `signal_state` | `watching` / `opened` / `no_open` | 监控中 / 已开口 / 无开口（监控中未触发） |
| `hud_card_state` | `on` / `warn` / `bad` | 正常 / 警示 / 异常（HUD 卡配色语义） |

#### 1.4 端口与基址

- 基址：`http://127.0.0.1:<port>`，`port` 默认 **8787**，实际值由 `GET /api/v1/runtime` 的 `port` 返回。
- 所有接口前缀 `/api/v1/`。请求/响应 `Content-Type: application/json; charset=utf-8`。

### 2. 统一响应信封

```json
{
  "ok": true,
  "data": { },
  "error": null,
  "as_of": "2026-09-12"
}
```

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `ok` | boolean | — | — | `true` 表示业务成功；`false` 时 `data=null` 且 `error` 非空 |
| `data` | object/array/null | — | — | 业务数据 |
| `error` | object/null | — | — | 失败时为 `{code, message, detail}`；成功为 null |
| `error.code` | string（枚举 §3） | — | — | 前端据此选文案 |
| `error.message` | string | — | — | 面向用户的可读原因（中文，已脱敏） |
| `error.detail` | object/null | — | — | 可选，字段级校验错误 `{field: reason}` |
| `as_of` | string(date) | — | — | 本响应数据截止日；无数据时为 null |

HTTP 状态码与 `ok` 双轨：成功 `200`，参数/校验 `400`，未找到 `404`，冲突 `409`，服务内部 `500`，引擎不可用 `503`。**前端以 `ok` 为准，HTTP 码仅辅助。**

### 3. 错误码（穷举）

| code | 含义 | 典型 HTTP | 前端文案前缀 |
|---|---|---|---|
| `E_IO` | 本地文件读写失败 | 500 | 读写本地数据失败 |
| `E_PARSE` | 数据/文件解析失败（非合法 JSON） | 500 | 数据格式错误 |
| `E_SOURCE_TIMEOUT` | 外部行情/净值源超时或不可达 | 503 | 数据源暂时不可用 |
| `E_ENGINE_OFFLINE` | 本地引擎未运行/心跳超时 | 503 | 引擎未运行 |
| `E_VALIDATION` | 请求参数不合法（字段级） | 400 | 参数不合法 |
| `E_NOT_FOUND` | 资源不存在（code/task_id 等） | 404 | 未找到 |
| `E_CONFLICT` | 唯一性冲突（同日同 code 台账、重复 code） | 409 | 已存在 |
| `E_PORT` | 端口全部占用（仅启动日志，不走 API） | — | — |
| `E_VERSION` | Python 版本/运行时不满足（仅启动） | — | — |
| `E_UNKNOWN` | 未归类错误 | 500 | 发生未知错误 |

### 4. 接口总览

| # | 方法 | 路径 | 调用方 | 用途 |
|---|---|---|---|---|
| 1 | GET | `/api/v1/runtime` | 全局壳/Topbar | 快照日期、陈旧度、开口数、交易时段、端口 |
| 2 | GET | `/api/v1/holdings` | 持仓页 | 持仓行（含估值/净值/预测） |
| 3 | GET | `/api/v1/holdings/summary` | 持仓页四卡 | 组合四数汇总 |
| 4 | GET | `/api/v1/holdings/{code}` | 编辑弹窗 | 单只持仓详情 |
| 5 | POST | `/api/v1/holdings` | 录入弹窗 | 新建持仓 |
| 6 | PUT | `/api/v1/holdings/{code}` | 编辑弹窗 | 编辑持仓 |
| 7 | DELETE | `/api/v1/holdings/{code}` | 行操作+二次确认 | 删除持仓 |
| 8 | POST | `/api/v1/holdings/{code}/transactions` | 加仓/减仓弹窗 | 加/减仓 |
| 9 | POST | `/api/v1/holdings/import` | 设置页 | 从 `funds_data.json` 重新导入 |
| 10 | GET | `/api/v1/valuations` | 持仓/分析页 | 全量估值（五档） |
| 11 | GET | `/api/v1/valuations/{code}` | 徽章详情 | 单只估值 + trace |
| 12 | GET | `/api/v1/valuations/precision` | 持仓页估值精度卡 | 置信度分组汇总 |
| 13 | GET | `/api/v1/predictions` | 分析/信号页 | 全量预测（三窗口） |
| 14 | GET | `/api/v1/predictions/{code}` | 链路展开 | 单只预测 + 6 步链路 |
| 15 | GET | `/api/v1/portfolio/forecast` | 持仓/分析页 | 三窗口组合加权 |
| 16 | GET | `/api/v1/review/scores` | 复盘页 | 三窗口成绩 vs 基线 |
| 17 | GET | `/api/v1/review/reconciliation` | 复盘页逐笔对账 | 台账 + 判定 |
| 18 | GET | `/api/v1/review/cv-config` | 复盘页口径 | 走前 CV 参数 |
| 19 | GET | `/api/v1/ledger` | 信号/引擎页 | 台账列表（合并回填） |
| 20 | POST | `/api/v1/ledger/entries` | 引擎（内部） | 写入一条开口记录 |
| 21 | POST | `/api/v1/ledger/backfill` | 引擎（内部） | 回填到期实际涨跌 |
| 22 | GET | `/api/v1/factors/pans` | 因子页 | 四盘 |
| 23 | GET | `/api/v1/factors/books` | 因子页 | 账本 |
| 24 | GET | `/api/v1/factors/score-chain` | 因子页 | 评分链 |
| 25 | GET | `/api/v1/factors/lifecycle` | 因子页 | 生命周期规则 |
| 26 | GET | `/api/v1/engine/status` | 引擎页 HUD/轮询 | 引擎状态 |
| 27 | GET | `/api/v1/engine/inputs` | 引擎页 | 六维/三维快照 |
| 28 | GET | `/api/v1/engine/ddsm` | 引擎页 | 125 格状态表 |
| 29 | GET | `/api/v1/engine/frozen-params` | 引擎页 | 冻结参数 |
| 30 | GET | `/api/v1/engine/registry` | 设置页 | 引擎注册表 |
| 31 | GET | `/api/v1/tasks` | 引擎页 | 任务列表 |
| 32 | POST | `/api/v1/tasks` | 手动触发 | 创建任务 |
| 33 | GET | `/api/v1/tasks/{task_id}` | 轮询 | 任务进度/结果 |
| 34 | GET | `/api/v1/settings` | 设置页 | 读取设置 |
| 35 | PUT | `/api/v1/settings` | 设置页 | 保存设置 |
| 36 | GET | `/api/v1/data-sources/health` | 设置/Topbar | 数据源健康 |
| 37 | POST | `/api/v1/data-sources/probe` | 设置页 | 立即探测 |
| 38 | GET | `/api/v1/about` | 设置页 | 版本/免责 |

**v3 新增接口（39~52，支撑 §9 特调组件；详见 §6.11）**

| # | 方法 | 路径 | 调用方 | 用途 |
|---|---|---|---|---|
| 39 | GET | `/api/v1/holdings/coverage` | 持仓页覆盖度四档 | 四档只数/市值/占比 + 失效三类长文 |
| 40 | GET | `/api/v1/holdings/risk` | 持仓页风险折叠区（按需） | Sharpe/VaR95/下行风险/最大回撤 |
| 41 | GET | `/api/v1/signals/state` | 信号页空态/触发门卡 | 空态四要素 + E1/E3 卡 + E2/E4 剔除说明 |
| 42 | GET | `/api/v1/meta/definitions` | 分析页口径定义 | T+1 口径 + 三条执行路径 |
| 43 | GET | `/api/v1/ledger/chain` | 信号时间线点击展开 | 单信号六步推导链（可作数据返回） |
| 44 | GET | `/api/v1/ledger/shadow` | 引擎页影子盘台账 | 台账行 + 连续记录进度 + INSERT-ONLY 字段说明 |
| 45 | GET | `/api/v1/engine/ddsm/cube` | 引擎页状态立方体 | 逐资产 125 格 naive/ddsm 双切片 + 对比卡 |
| 46 | GET | `/api/v1/engine/training-status` | 引擎页训练状态卡 | 125 格/有样本格/平均样本/最少样本 + 加噪说明 + 已证伪死路 |
| 47 | GET | `/api/v1/engine/arena` | 引擎页因子竞技场 | 矩阵：行=配置、列=六窗、格=开口/命中/配对Δ/留一法/警示 |
| 48 | GET | `/api/v1/engine/shadow-review` | 复盘页降级审查条 | idle/ok/bad 三态 + 滚动 60 日命中率 vs 基准 |
| 49 | GET | `/api/v1/factors/score-detail` | 因子页展开跑分表 | 每窗 lift/k_lift/权重/独立触发日/准入度/得分 + 总分 |
| 50 | GET | `/api/v1/factors/books/{book}` | 因子页账本展开 | 单本账本条目（含示例记录，只读） |
| 51 | GET | `/api/v1/factors/governance-cycle` | 因子页治理周期卡 | 五阶段排期/上次/下次/状态/规则文本 |
| 52 | GET | `/api/v1/factors/dig-records` | 因子页最近挖掘记录 | F1/F2/F3 判定记录 |
| 53 | GET | `/api/v1/settings/holdings-data` | 设置页持仓数据卡 | 两份 funds_data.json 来源/时间/不一致长文 |

> 上表 38 行含内部接口（20/21）；面向 UI 的接口共 36 个。**v3 追加 15 个只读接口（39~53，见上）**，全部面向 UI、无写端点；合计 53 行、面向 UI 51 个。下文按域展开。

---

### 5. 共享对象字段字典

> 端点响应直接用对象名引用本节，字段口径只在此定义一次（引用优先于复制）。

#### 5.1 `HoldingRow`（`GET /holdings` 数组元素）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `code` | string | — | 6 位数字 | 基金代码；不以 0 开头的也按 string 返回 |
| `name` | string | — | — | 基金名称 |
| `group` | enum `holding_group` | — | — | 类别 |
| `group_label` | string | — | — | 中文标签（境内指数/主动/QDII/黄金/其他） |
| `tier` | enum `coverage_tier` | — | — | A/B/C/D |
| `shares` | number | 份 | 4 位 | 持有份额 |
| `cost_amount` | number | 元 | 2 位 | 累计投入成本 |
| `avg_cost` | number | 元/份 | 4 位 | `cost_amount / shares`；shares=0 时 null |
| `confirm_days` | integer | 交易日 | 整数 | 确认天数，取值 ∈ {1,2,3} |
| `proxy_code` | string/null | — | — | 代理 ETF 代码；D 档为 null |
| `proxy_name` | string/null | — | — | 代理 ETF 名称 |
| `valuation` | `Valuation` | — | — | 见 §5.2（今日预估） |
| `nav` | `Nav` | — | — | 见 §5.3（官方已公布值，独立字段） |
| `prediction` | `PredictionSummary`/null | — | — | 见 §5.4；C/D 档或数据不足为 null |
| `market_value` | number/null | 元 | 2 位 | `shares × (valuation.estimated_nav ?? nav.official_nav)`；两者皆无时 **null**（禁止用成本价冒充市值，A-02） |
| `mv_source` | enum `mv_source` | — | — | `valuation` / `nav` / `null`；`null` 时 `market_value` 必为 `null` |
| `fallback_value` | number | 元 | 2 位 | 仅当 `market_value=null` 时 = `cost_amount`，否则 0；UI 必须与 `market_value` 分列/分行展示，**不得混入市值列** |
| `weight_ratio` | number/null | 比率 | 4 位 | `market_value / summary.total_value`；`market_value=null` 时 `null`（不计入分母） |
| `today_pnl_amt` | number/null | 元 | 2 位 | 仅当 `valuation.change_rate` 非 null 时 = `market_value − market_value/(1+change_rate)`；否则 null |
| `pnl_amt` | number | 元 | 2 位 | `market_value − cost_amount` |
| `return_rate` | number/null | 比率 | 4 位 | `pnl_amt / cost_amount`；成本 0 时 null |
| `staleness` | `Staleness` | — | — | 见 §5.6 |

#### 5.2 `Valuation`（今日预估；可能 official 也可能是估算）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `valuation_mode` | enum `valuation_mode` | — | — | **唯一决定徽章文案**；前五档降级链命中结果 |
| `mode_label` | string | — | — | 官方净值/盘中估算/重仓加权/代理近似/未知 |
| `change_rate` | number/null | 比率 | 4 位 | 今日预估涨跌；**null 表示未知**；0.0178 = +1.78% |
| `estimated_nav` | number/null | 元/份 | 4 位 | 今日预估净值 |
| `source_label` | string | — | — | 来源说明（如"腾讯实时估算净值"） |
| `confidence` | enum `confidence` | — | — | 由 `mae_rate` 对照行业基准 0.008 得出 |
| `mae_rate` | number/null | 比率 | 4 位 | 该档回测平均绝对误差；0.0062 = 0.62% |
| `nav_date` | string(date)/null | — | — | 本估值所依据的最后一个官方净值日期 |
| `trace` | array[`TraceStep`] | — | — | 降级链路，见 §5.2.1；**禁止编造** |
| `written_at` | string(timestamp) | — | 秒 | 本估值记录**入账时刻**（写 `valuation_history.jsonl`）；INSERT-ONLY，已入账记录不可改写 |
| `run_id` | string | — | — | 产生本记录的估值任务 id；同一次刷新内多基金共享 |
| `is_first_of_day` | boolean | — | — | 是否为该 `(date, code)` 当日**首次**入账记录（当日基准口径，不可被后续覆盖） |
| `history_available` | boolean | — | — | 是否存在 ≥1 条历史记录（供 `/valuations/{code}?history=true` 回溯） |
| `dir_hit_rate` | number/null | 比率 | 4 位 | **v3 追加**：方向命中率（近 `accuracy_window_days` 回测，估算方向 vs 官方方向）；驱动徽章悬浮"方向命中率" |
| `n_test` | integer/null | 交易日 | 整数 | **v3 追加**：精度回测有效样本日数；驱动徽章悬浮"样本 N 个交易日" |
| `accuracy_window_days` | integer | 交易日 | 整数 | **v3 追加**：精度统计窗口，固定 40（与估值精度汇总同口径） |
| `industry_baseline_mae_rate` | number | 比率 | 4 位 | **v3 追加**：行业基准 MAE，固定 0.008（0.80%） |
| `confidence_label` | string | — | — | **v3 追加**：`误差达标`/`误差中等`/`误差偏大`/`无可信估算`（由 `confidence` 唯一映射） |
| `confidence_color_class` | string | — | — | **v3 追加**：`ch`/`cm`/`cl`/`cu`（high/mid/low/unknown 对应样式类，避免前端硬编码；与 UI §2 一致） |
| `trace_text` | string/null | — | — | **v3 追加**：`trace` 的可读降级链串，如 `official 未出 → intraday 命中`；`trace` 缺失时 null（前端**不得编造**） |
| `as_of` | string(date) | — | — | 估值数据截止日 |

> **A-01 口径**：`GET /valuations` 与 `/valuations/{code}` 默认返回该 `(date, code)` **最新一条**（按 `written_at`）记录；`/valuations/{code}?history=true` 额外返回 `history: Valuation[]`（按 `written_at` 升序，含当日全部入账记录）。首次入账记录的 `mode`/`trace` 永久保留，后续刷新与官方回填只能**追加**。

**5.2.1 `TraceStep`**

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `mode` | enum `valuation_mode` | — | — | 本步尝试的档位 |
| `tried` | boolean | — | — | 是否实际尝试 |
| `hit` | boolean | — | — | 是否命中 |
| `reason` | enum `trace_reason` | — | — | 命中/未命中原因 |

#### 5.3 `Nav`（官方已公布净值；与估值**独立、互不覆盖**）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `official_nav` | number/null | 元/份 | 4 位 | 官方最新已公布净值；未公布 null |
| `official_nav_date` | string(date)/null | — | — | 官方净值对应交易日 |
| `official_change_rate` | number/null | 比率 | 4 位 | `official_nav/previous_nav − 1`；无前值 null |
| `previous_nav` | number/null | 元/份 | 4 位 | 上一公布日净值 |
| `is_today_official` | boolean | — | — | `official_nav_date == as_of`；徽章据此区分"既成事实 vs 估算" |

> **估值≠净值关键口径**：`Valuation.change_rate` 是"系统今日预估"；`Nav.official_change_rate` 是"基金公司已公布事实"。官方净值回填**只写 `nav.*`**，并把当日新产生的估值记录**追加**到 `valuation_history.jsonl`；当日**已入账**的 `mode`/`trace` 永不改写（A-01）。

#### 5.4 `PredictionSummary`（列表用）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `code` | string | — | — | 基金代码 |
| `gate` | enum `gate` | — | — | E1/E3/none |
| `gate_label` | string | — | — | 跳空/无量急跌/未触发 |
| `p_up` | number/null | 概率 | 4 位 | T+1 收缩概率 P（见 08 §4.3）；不足 MIN_N 时向全局收缩后仍给出 |
| `ddsm_state` | array[3] integer | — | 整数 | 真实档位 `[r2档, om档, vr档]`，每维 ∈ {0,1,2,3,4} |
| `veto_crowd` | boolean | — | — | 拥挤度否决是否亮灯（`status=missing` 时为 false，但**不得**据此输出 up） |
| `veto_crowd_status` | enum `veto_layer_status` | — | — | pass/veto/missing（A-05） |
| `veto_klow2` | boolean | — | — | KLOW2 否决是否亮灯 |
| `veto_klow2_status` | enum `veto_layer_status` | — | — | pass/veto/missing；`high==low` 等缺数据 → `missing`（A-05） |
| `signal` | enum `signal` | — | — | up/gray/abstain；任一否决层 `missing` → 强制 `abstain`（A-05） |
| `signal_label` | string | — | — | 涨/灰/弃权 |
| `reason` | enum `signal_reason` | — | — | 信号原因 |
| `windows` | object | — | — | 键为 `T1`/`T3`/`T15`，值见 §5.5 |
| `as_of` | string(date) | — | — | 预测数据截止日 |

#### 5.5 `WindowResult`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `window` | — | — | T1/T3/T15 |
| `formula` | string | — | — | 定式：`gate+ddsm+veto` / `gate_only` / `gate+ddsm` |
| `formula_source` | string | — | — | `brief_5.1`（T1）/ `arch_baseline_v1`（T3/T15，Brief §5.1 未定义，A-04） |
| `validation_status` | enum `validation_status` | — | — | T1=`brief_mandated`；T3/T15 初始 `pending_cv`，过走前 CV 且 placebo≥2pp 后转 `validated`（A-04） |
| `validated` | boolean | — | — | `validation_status==validated` 的布尔别名；T1 恒 true（Brief 授权，非 CV 结论） |
| `direction` | enum `direction` | — | — | up/down/gray；**仅当** `validation_status ∈ {brief_mandated, validated}` 且定式出口成立才可 `up`；T3/T15 未验证时**强制 gray**（A-04）。本项目不产生 down 信号，down 仅用于回填统计 |
| `provisional_direction` | enum `direction` | — | — | 定式名义方向（未验证窗口的观察值，仅引擎页/审计可见，**不得**出现在组合卡或信号页的"涨"色上） |
| `p` | number/null | 概率 | 4 位 | 概率口径：T1 = DDSM 收缩 P；**T3 = null**（`gate_only` 定式无概率模型，禁止后端自造）；T15 = DDSM 收缩 P（标签 `close[t+15]>close[t]`）（A-04） |
| `provisional_p` | number/null | 概率 | 4 位 | 未验证窗口的名义概率；T3 恒 null；仅供观察，不参与组合 `weighted_p` |
| `open` | boolean | — | — | 该窗口是否开口（`formula` 定式口径） |
| `hit_rate` | number/null | 比率 | 4 位 | 走前 CV 回测命中率；无数据 null |
| `baseline_rate` | number/null | 比率 | 4 位 | 同期 `max(恒涨率,恒跌率)`；无数据 null |
| `delta_pp` | number/null | 百分点 | 4 位 | `hit_rate − baseline_rate`；任一缺失 null |

#### 5.6 `Staleness`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `is_stale` | boolean | — | — | 数据 `as_of` 落后于当前交易日 |
| `latest_date` | string(date)/null | — | — | 实际最新数据日期 |
| `days_behind` | integer | 自然日 | 整数 | 当前日 − latest_date |
| `note` | string | — | — | 可读提示（如"数据快照 2026-08-24"） |

#### 5.7 `PortfolioForecast`（`GET /portfolio/forecast` 数组元素）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `window` | — | — | T1/T3/T15 |
| `weighted_p` | number/null | 概率 | 4 位 | 只对开口且 `p != null` 的仓位按市值加权；无开口或该窗口无概率（T3）→ null |
| `coverage_ratio` | number | 比率 | 4 位 | 覆盖市值占比 = `open_value/total_value` |
| `coverage_value` | number | 元 | 2 位 | 参与加权的开口市值合计 |
| `open_value` | number | 元 | 2 位 | 同 `coverage_value`（语义别名，两者恒等） |
| `total_value` | number | 元 | 2 位 | 全组合**可信市值**合计（`market_value != null` 的持仓；未知行不计入分母，A-02） |
| `open_count` | integer | 只 | 整数 | 开口只数 |
| `min_coverage_ratio` | number | 比率 | 4 位 | **冻结常量 = 0.30**（架构口径，非 API 参数，A-03） |
| `min_open_count` | integer | 只 | 整数 | **冻结常量 = 3**（架构口径，A-03） |
| `coverage_threshold_met` | boolean | — | — | `coverage_ratio >= min_coverage_ratio` **且** `open_count >= min_open_count` |
| `excluded_ratio` | number | 比率 | 4 位 | `1 − coverage_ratio`；前端文案"其余 X% 不表态" |
| `threshold_source` | string | — | — | `brief_5.1`（0.52 源自单资产出口）/ `architecture`（组合层沿用 0.52 的标注） |
| `direction` | enum `direction` | — | — | **仅当** `weighted_p > 0.52` **且** `coverage_threshold_met` **且** 窗口 `validation_status ∈ {brief_mandated, validated}` → up；否则 gray（A-03/A-04） |
| `direction_reason` | enum `direction_reason` | — | — | ok/no_open/insufficient_coverage/window_unvalidated |
| `weighted_p_threshold` | number | 概率 | 4 位 | 固定 0.5200（=Brief §5.1 单资产出口 0.5+BAND，组合层沿用并标注来源） |
| `tier_excluded` | array[string] | — | — | 被排除的档位，**含组合中实际存在的** C/D 档（无则不出现；非"固定含 C/D"，A-03 措辞修正） |
| `engine_status` | enum `engine_status` | — | — | 生产该窗口的引擎状态；`offline` 且携带旧快照时前端渲染陈旧态而非空态（A-06） |
| `as_of` | string(date) | — | — | — |

#### 5.8 `ReviewScore`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `window` | — | — | T1/T3/T15 |
| `formula` | string | — | — | 定式 |
| `hit_rate` | number/null | 比率 | 4 位 | 走前 CV 命中率 |
| `open_count` | integer | 笔 | 整数 | 开口样本数 |
| `baseline_rate` | number/null | 比率 | 4 位 | `max(恒涨率, 恒跌率)` |
| `baseline_status` | enum `baseline_status` | — | — | filled/pending |
| `delta_pp` | number/null | 百分点 | 4 位 | `hit_rate − baseline_rate`；pending 时 null |
| `cv_mode` | string | — | — | 固定 `walk_forward` |
| `purge_gap` | string | — | — | 固定 `H+2` |
| `holdout_days` | integer | 交易日 | 整数 | 固定 60 |
| `data_kind` | string | — | — | `backtest` / `shadow_live`（视觉必须可区分） |
| `sample_period` | string | — | — | 样本区间，如 `2024-01-01..2026-08-31` |
| `as_of` | string(date) | — | — | — |

#### 5.9 `LedgerEntry`（读取时已合并回填）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `date` | string(date) | — | — | 开口日 T |
| `code` | string | — | — | 基金代码 |
| `name` | string | — | — | 基金名称（读取时关联持仓） |
| `tier` | enum `coverage_tier` | — | — | 写入时档位 |
| `gate` | enum `gate` | — | — | 触发门 |
| `p_up` | number | 概率 | 4 位 | T+1 概率 |
| `ddsm_state` | array[3] integer | — | 整数 | 档位三元组 |
| `veto_crowd` | boolean | — | — | 拥挤度否决 |
| `veto_klow2` | boolean | — | — | KLOW2 否决 |
| `signal` | enum `signal` | — | — | 写入时信号（回填不改） |
| `market_value` | number | 元 | 2 位 | 写入时市值 |
| `cost_est` | number | 元 | 2 位 | 写入时成本估算 |
| `t1_real` | number/null | 比率 | 4 位 | 到期实际涨跌（回填） |
| `t3_real` | number/null | 比率 | 4 位 | 到期实际涨跌（回填） |
| `t15_real` | number/null | 比率 | 4 位 | 到期实际涨跌（回填） |
| `written_at` | string(timestamp) | — | 秒 | 收盘写盘时间 |
| `is_backfilled` | boolean | — | — | 三个 `t*_real` 是否齐备 |
| `created_at` | string(timestamp) | — | 秒 | **v3 追加**：本行**入账时刻**的规范字段（与 `written_at` 同一时刻，二者恒等；`written_at` 为 v2 兼容别名，不得改动）。INSERT-ONLY：写入后永不修改 |
| `record_seq` | integer | — | 整数 | **v3 追加**：台账内递增序号（读取时按 `(created_at, code)` 生成，仅供展示排序，非主键） |
| `source_file` | string | — | — | **v3 追加**：恒 `shadow_signals.jsonl`（影子盘信号层唯一来源，便于审计溯源） |
| `chain_available` | boolean | — | — | **v3 追加**：是否能取到六步推导链（`true` 时前端可调 `/ledger/chain` 展开） |

#### 5.10 `ReconcileRow`

在 `LedgerEntry` 基础上追加：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `result` | enum `reconcile_result` | — | — | `t1_real>0` 且 signal=up → hit；`t1_real≤0` → miss；signal=abstain → abstain；未回填 → pending |

#### 5.11 `FactorPan`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `role` | enum `factor_role` | — | — | 正式盘/淘汰影子盘/有效影子盘/冷冻盘 |
| `role_label` | string | — | — | 中文 |
| `description` | string | — | — | 盘面用途 |
| `factor_count` | integer | 个 | 整数 | 盘内因子数 |
| `factors` | array[`FactorItem`] | — | — | 见 §5.12 |
| `rule_text` | string | — | — | **v3 追加**：逐盘 rule 长文（源：legacy v2 壳四盘 rule；正式盘=总数上限与月检留一法，淘汰影子盘=A/B 对照，有效影子盘=准入三项 AND，冷冻盘=复活路径），文本由后端配置返回，前端不硬编码 |
| `pan_status` | enum `hud_card_state` | — | — | **v3 追加**：盘面健康语义（on/warn/bad），驱动盘头配色 |
| `flow_kind` | string | — | — | **v3 追加**：`promotion`（晋升回路）/ `revival`（复活回路）/ `none`；正式盘与影子盘为 promotion，冷冻盘为 revival |
| `updated_at` | string(timestamp)/null | — | 秒 | **v3 追加**：盘面最近更新时间 |
| `factor_cap` | integer/null | 个 | 整数 | **v3 追加**：该盘因子上限（正式盘：否决位 ≤4、打分位受状态空间约束 ≤3；其他盘 null 表示不限），源 legacy v2 壳四盘 rule |
| `nomination_limit` | integer/null | 个/周 | 整数 | **v3 追加**：每周提名上限（有效影子盘/候选池 = 3，冷却 90 天）；其他盘 null |

#### 5.12 `FactorItem`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `factor_id` | string | — | — | 因子唯一 id |
| `name` | string | — | — | 因子名 |
| `role` | enum `factor_role` | — | — | 当前角色 |
| `role_label` | string | — | — | **v3 追加**：角色中文（否决位/打分位/候补位/已剔除） |
| `score` | number/null | 分 | 4 位 | 六窗加权总分；缺失 null（= `total_score` 的 v2 别名，二者恒等） |
| `total_score` | number/null | 分 | 4 位 | **v3 追加**：六窗加权总分；与 `score` 恒等（明确展示口径） |
| `status` | enum `factor_status` | — | — | **v3 收紧为穷举**：active/probation/cooling/frozen/retired |
| `license` | enum `factor_license` | — | — | **v3 追加**：牌照（四线 50/60/70/80） |
| `license_label` | string | — | — | **v3 追加**：牌照中文（未达线/候补/试用/续聘 T2/正式 T3） |
| `lift_bars` | array[`FactorLiftBar`] | — | — | **v3 追加**：六窗 lift bars（见 §5.23），固定 6 项（顺序 `factor_window` 穷举顺序） |
| `independent_trigger_days` | integer/null | 交易日 | 整数 | **v3 追加**：独立触发日数（数据卫生 #1：绩效与 t 一律按独立触发日聚合，不用条口径）；驱动准入度 |
| `death_condition` | string/null | — | — | **v3 追加**：采纳当天预注册的死亡条件原文（正式盘必填） |
| `note` | string | — | — | **v3 追加**：一句话说明（如"15 日窗亮眼但长窗衰减"） |
| `ab_progress` | object/null | — | — | **v3 追加**：A/B 对照进度 `{day, total_days, delta_after_removal_pp, conclusion}`；非 A/B 盘 null |
| `added_at` | string(date) | — | — | 入盘日 |

#### 5.13 `FactorBook`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `book` | enum `factor_book` | — | — | 账本标识 |
| `book_label` | string | — | — | **v3 追加**：账本中文（采纳登记表/挖掘台账/体检台账/淘汰台账/影子信号/因子竞技场） |
| `filename` | string | — | — | 落盘文件名 |
| `purpose` | string | — | — | 用途 |
| `record_kind` | string | — | — | **v3 追加**：记录结构标识（`adopted_record`/`scan_record`/`health_record`/`retired_record`/`signal_record`/`arena_record`），供前端按类型渲染展开表 |
| `schema_fields` | array[string] | — | — | **v3 追加**：该账本条目的字段名清单（穷举），前端据此生成表头而不硬编码 |
| `record_count` | integer | 条 | 整数 | 记录数 |
| `last_record_at` | string(timestamp)/null | — | 秒 | 最近记录时间 |
| `sample` | array[object]/null | — | — | 最近 1~3 条示例（只读）；完整条目见 `GET /factors/books/{book}`（§6.11.12） |

#### 5.14 `FrozenParams`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `k_noise` | integer | 副本数 | 整数 | **冻结 = 4** |
| `p_perturb` | number | 概率 | 4 位 | **冻结 = 0.25** |
| `min_n` | integer | 样本数 | 整数 | **冻结 = 15** |
| `shrink` | integer | 伪计数 | 整数 | **冻结 = 10** |
| `band` | number | 概率 | 4 位 | **冻结 = 0.02**（出口阈值 0.5+band=0.52） |
| `veto_crowd_quantile` | number | 分位 | 4 位 | **冻结 = 0.60**（最拥挤 40% 否决） |
| `veto_klow2_quantile` | number | 分位 | 4 位 | **冻结 = 0.40**（最不利 40% 否决） |
| `min_coverage_ratio` | number | 比率 | 4 位 | **冻结 = 0.30**（组合方向最小覆盖市值占比，A-03） |
| `min_open_count` | integer | 只 | 整数 | **冻结 = 3**（组合方向最小开口数，A-03） |
| `gate_e1` | string | — | — | **v3 追加**：`low[t] > high[t-1]`（E1 跳空，文本冻结） |
| `gate_e3` | string | — | — | **v3 追加**：`ret < -0.02 且 vr < 0.8`（E3 无量急跌，文本冻结） |
| `purge_gap` | string | — | — | **v3 追加**：固定 `H+2` |
| `window_weights` | array[object] | — | — | **v3 追加**：六窗权重 `[{window:"d15",weight:8},{d30:22},{d60:15},{m6:10},{m24:30},{full:15}]`（合计 100，次序同 `factor_window`） |
| `window_min_days` | array[object] | — | — | **v3 追加**：准入度分母 `N_w`：`{d15:5,d30:10,d60:15,m6:30,m24:60,full:120}` |
| `license_lines` | array[object] | — | — | **v3 追加**：牌照四线 `[{license:"candidate",min_independent_days:50,note:"只记账不参与生产"},{license:"probation",min_independent_days:60,window_k:0.5},{license:"renew_t2",min_independent_days:70,window_k:0.7},{license:"full_t3",min_independent_days:80,window_k:0.7}]` |
| `change_policy` | string | — | — | 固定提示"任何一项改动必须重走六关" |

#### 5.15 `Task`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `task_id` | string | — | — | 唯一 id（如 `tsk_20260912_153000_ab12`） |
| `type` | enum `task_type` | — | — | 任务类型 |
| `status` | enum `task_status` | — | — | 状态 |
| `progress` | number | 比率 | 2 位 | [0,1] |
| `step` | string | — | — | 当前步骤可读文案 |
| `submitted_at` | string(timestamp) | — | 秒 | — |
| `started_at` | string(timestamp)/null | — | 秒 | — |
| `finished_at` | string(timestamp)/null | — | 秒 | — |
| `error` | object/null | — | — | 同信封 error |
| `result_summary` | string/null | — | — | 完成摘要（如"估值刷新 22/22"） |

#### 5.16 `Settings`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `privacy.masked` | boolean | — | — | 隐藏全部金额 |
| `privacy.mask_holdings_only` | boolean | — | — | 仅隐藏明细行金额 |
| `llm.enabled` | boolean | — | — | 事件编码开关 |
| `llm.provider` | enum `llm_provider` | — | — | 服务商 |
| `llm.model` | string | — | — | 模型名 |
| `llm.api_key_set` | boolean | — | — | **只回传是否已设置，永不回传 key 明文** |
| `llm.temperature` | number | — | 1 位 | 固定 0 |
| `llm.output_format` | string | — | — | 固定 `json` |
| `llm.mode` | string | — | — | 固定 `shadow`（观察区，不做最终预测） |
| `port` | integer | — | 整数 | 服务端口 |
| `auto_refresh` | boolean | — | — | 是否自动刷新行情 |
| `refresh_interval_sec` | integer | 秒 | 整数 | 建议 300 |
| `theme` | string | — | — | 固定 `light` |

#### 5.17 `DataSourceHealth`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `source_id` | enum `data_source_id` | — | — | 数据源 |
| `label` | string | — | — | 显示名 |
| `status` | enum `data_source_status` | — | — | 正常/波动/不通/未检测 |
| `last_ok_at` | string(timestamp)/null | — | 秒 | 最近成功时间 |
| `fail_count` | integer | 次 | 整数 | 累计失败次数 |
| `latency_ms` | integer/null | 毫秒 | 整数 | 最近一次耗时 |
| `note` | string | — | — | 备注 |

#### 5.18 `Runtime`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `server_time` | string(timestamp) | — | 秒 | 服务器当前时间 |
| `port` | integer | — | 整数 | 实际端口 |
| `as_of` | string(date)/null | — | — | 全局数据截止日 |
| `staleness` | `Staleness` | — | — | 见 §5.6 |
| `open_count` | integer | 只 | 整数 | 本次 T+1 开口数 |
| `trade_session` | enum `trade_session` | — | — | 交易时段 |
| `engine_status` | enum `engine_status` | — | — | 引擎状态摘要 |

---

#### 5.19 `CoveragePanel`（`GET /holdings/coverage`，UI：持仓页覆盖度四档）

`CoveragePanel`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `tiers` | array[`CoverageTier`] | — | — | 固定 4 项，顺序 A/B/C/D |
| `total_count` | integer | 只 | 整数 | 持仓总数 |
| `total_value` | number | 元 | 2 位 | 可信市值合计（口径同 §6.2.1 `total_value`） |
| `invalidation_note` | string | — | — | 「失效三类」长文（定义失效/数据失效/框架失效），文本由后端配置返回 |
| `no_solution_count` | integer | 只 | 整数 | 原理无解只数（本期固定 0，附文案"原理无解：N 只"） |
| `as_of` | string(date)/null | — | — | — |

`CoverageTier`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `tier` | enum `coverage_tier` | — | — | A/B/C/D |
| `tier_label` | string | — | — | A 已接入 / B 代理已验证 / C 代理待验证 / D 暴露待定 |
| `color` | string | — | — | 展示色 `#rrggbb`（来自后端 token，前端不硬编码） |
| `count` | integer | 只 | 整数 | 该档只数 |
| `market_value` | number | 元 | 2 位 | 该档可信市值合计（未知行不计入） |
| `weight_ratio` | number/null | 比率 | 4 位 | `market_value / total_value`；分母为 0 时 null（UI 显示"—"） |
| `description` | string | — | — | 档位说明长文 |
| `action_hint` | string | — | — | 信号列读法（信号已可用/接线即可用/验证后可用/穿透后可用） |
| `invalidation` | enum `coverage_invalidation` | — | — | 失效类型 |
| `member_names` | array[string] | — | — | 前 3 只名称（后端生成，前端不做截断逻辑） |

#### 5.20 `RiskMetrics`（`GET /holdings/risk`，UI：持仓页风险折叠区）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `sharpe` | number/null | 倍数 | 4 位 | 年化 Sharpe；样本不足 null |
| `var95_rate` | number/null | 比率 | 4 位 | 95% 日 VaR，**正数表示损失幅度**（0.0230 = 2.30%）；历史模拟法 |
| `downside_vol_rate` | number/null | 比率 | 4 位 | 下行风险（下行日收益标准差，年化） |
| `max_drawdown_rate` | number/null | 比率 | 4 位 | 最大回撤，**正数表示幅度**（0.1800 = 18.00%） |
| `sample_days` | integer | 交易日 | 整数 | 回看窗口，固定 250 |
| `stale` | boolean | — | — | ETF 缓存落后于当前交易日 |
| `computed_at` | string(timestamp)/null | — | 秒 | 计算时间；未计算 null |
| `note` | string | — | — | 口径说明（慢接口，按需计算） |

#### 5.21 `SignalState`（`GET /signals/state`，UI：信号页空态/触发门卡）

`SignalState`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `state` | enum `signal_state` | — | — | watching/opened/no_open |
| `as_of` | string(date)/null | — | — | 快照日 |
| `monitored_count` | integer | 只 | 整数 | 监控中只数（A+B 档） |
| `total_count` | integer | 只 | 整数 | 持仓总只数 |
| `days_since_last_open` | integer/null | 交易日 | 整数 | 距上次开口交易日数；无历史 null |
| `last_open` | object/null | — | — | `{date, code, name, gate, result, t1_real}`；无 null |
| `last_result` | enum `reconcile_result` | — | — | 上次结果（hit/miss/abstain/pending） |
| `empty_note` | string | — | — | 空态文案（"这是常态，不是故障"） |
| `gates` | array[`GateCard`] | — | — | 固定 2 项（E1/E3） |
| `excluded_gates` | array[`GateCard`] | — | — | 固定 2 项（E2/E4，剔除说明） |
| `or_merge_forbidden` | boolean | — | — | 固定 true（四类事件**禁止 OR 合并**） |

`GateCard`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `gate` | enum `gate` | — | — | E1/E3；剔除卡为固定文本 E2/E4（不进入 `gate` 枚举运行值） |
| `gate_key` | string | — | — | `E1`/`E3`/`E2`/`E4`（含剔除项，便于前端 key） |
| `label` | string | — | — | 跳空/无量急跌/放量上涨/点火 |
| `formula` | string | — | — | 定式文本（E1 `low[t] > high[t-1]`；E3 `ret < -0.02 且 vr < 0.8`） |
| `role` | string | — | — | `primary`（E3）/`secondary`（E1）/`excluded`（E2/E4） |
| `effect_pp` | number/null | 百分点 | 4 位 | 纯事件效应（E1 +0.88 / E3 +3.90 / E4 −2.72 / E2 −3.09） |
| `t_value` | number/null | — | 3 位 | t 值（E3 +2.33） |
| `note` | string | — | — | 说明 |

#### 5.22 `DefinitionCard` / `ExecutionPath`（`GET /meta/definitions`，UI：分析页口径定义）

`DefinitionCard`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `formula` | string | — | — | 固定 `up = 1 若 close[T+1] > close[T]` |
| `signal_time` | string | — | — | 固定 `T 日 15:30 收盘后` |
| `timing_note` | string | — | — | 场外 15:00 截止 vs 信号 15:30 的时序坑长文 |
| `paths` | array[`ExecutionPath`] | — | — | 固定 3 项（A/B/C） |
| `conclusion` | string | — | — | 结论指向 B（持有/赎回决策），**无"当天可买入"暗示** |

`ExecutionPath`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `path` | enum `execution_path` | — | — | new_position/hold_existing/onsite_etf |
| `label` | string | — | — | A 新建仓位 / B 已持有仓位 / C 场内 ETF |
| `steps` | string | — | — | 执行步骤文本 |
| `executable` | boolean | — | — | B=true；A/C=false |
| `caveat` | string | — | — | 口径差异说明 |

#### 5.23 `FactorScoreDetail` / `FactorScoreWindow` / `FactorLiftBar`（`GET /factors/score-detail`，UI：因子页展开跑分表）

`FactorScoreDetail`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `factor_id` | string | — | — | 因子 id |
| `name` | string | — | — | 因子名 |
| `total_score` | number/null | 分 | 4 位 | 六窗得分之和（= `FactorItem.total_score`） |
| `windows` | array[`FactorScoreWindow`] | — | — | 固定 6 项（顺序同 `factor_window`） |
| `bootstrap_percentiles` | object | — | — | `{p50,p90,p95,p99,p995}`＝`−10.8 / 38.7 / 48.4 / 61.7 / 64.1`（bootstrap 500 随机因子校准，固定展示常量） |
| `judges` | array[object] | — | — | 四裁判 `{judge, scope, metric, value, note}`；`judge` 枚举 `score_judge` |
| `formula_text` | string | — | — | 评分链长文（悬崖 + 窗权重 + 准入度） |

`FactorScoreWindow`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `factor_window` | — | — | 六窗 |
| `window_label` | string | — | — | 15日/30日/60日/6月/24月/全样本 |
| `lift` | number/null | 倍数 | 4 位 | `命中率 ÷ 基线`；无数据 null |
| `k_lift` | number | 分 | 4 位 | 悬崖查表：≥1.30→1.0 / ≥1.20→0.80 / ≥1.10→0.65 / ≥1.00→0.50 / <1.00→−0.80 / <0.84→−1.3（`lift` null 时 0） |
| `weight` | number | 分 | 4 位 | 窗权重：`8/22/15/10/30/15` |
| `independent_trigger_days` | integer | 交易日 | 整数 | 独立触发日数（非条数） |
| `n_w` | integer | 交易日 | 整数 | 准入度分母 `N_w = 5/10/15/30/60/120` |
| `admission` | number | 比率 | 4 位 | `min(1, independent_trigger_days / n_w)` |
| `score` | number | 分 | 4 位 | `k_lift × weight × admission` |
| `cliff_hit` | string/null | — | — | 命中的悬崖档位标签（如 `≥1.20`）；`lift` null 时 null |

`FactorLiftBar`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `factor_window` | — | — | 六窗 |
| `window_label` | string | — | — | 同上 |
| `lift` | number/null | 倍数 | 4 位 | 六窗 lift，驱动 bars 长度 |

#### 5.24 `ArenaMatrix` / `ArenaRow` / `ArenaCell`（`GET /engine/arena`，UI：引擎页因子竞技场）

`ArenaMatrix`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `windows` | array[object] | — | — | 固定 6 项 `{window, window_label}`（列） |
| `rows` | array[`ArenaRow`] | — | — | 行=配置（含生产行、裸算法基准行、留一法行、候选行） |
| `legend` | array[object] | — | — | 固定 5 项 `{color, label}`：red 该窗最高 / green 该窗最低 / blue 居中 / yellow ▲ 警示（Δ 低于裸算法基准）/ base 基准行不着色 |
| `naive_method_note` | string | — | — | 留一法（C − eᵢ）说明长文 |
| `as_of` | string(date)/null | — | — | — |

`ArenaRow`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `config_id` | string | — | — | 配置 id |
| `config_name` | string | — | — | 配置名（因子名） |
| `config_kind` | enum `arena_config_kind` | — | — | production/naive_baseline/leave_one_out/candidate |
| `is_leave_one_out` | boolean | — | — | 是否留一法行（C − eᵢ） |
| `is_highlight` | boolean | — | — | 是否生产行（前端加"生产"标签） |
| `warning` | boolean | — | — | 整行警示（任格 Δ 低于裸算法基准） |
| `cells` | array[`ArenaCell`] | — | — | 固定 6 格（列同上） |

`ArenaCell`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `window` | enum `factor_window` | — | — | 该列窗口 |
| `open_count` | integer | 次 | 整数 | 开口数 |
| `hit_rate` | number/null | 比率 | 4 位 | 命中率；无开口 null |
| `paired_delta_pp` | number/null | 百分点 | 4 位 | 配对 Δ（相对基线）；无数据 null |
| `is_leave_one_out` | boolean | — | — | 该格是否留一法结果 |
| `warning` | boolean | — | — | Δ 低于裸算法基准（加因子反而更差）→ ▲ |
| `color` | enum `arena_color` | — | — | 格配色 |
| `is_window_max` | boolean | — | — | 该窗跨配置最高 |
| `is_window_min` | boolean | — | — | 该窗跨配置最低（裸算法基准行不参与红绿排名） |

#### 5.25 `StateCube` / `CubeSlice` / `CubeCell` / `CubeComparison`（`GET /engine/ddsm/cube`，UI：引擎页状态立方体）

`StateCube`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `code` | string | — | — | 资产代码 |
| `name` | string | — | — | 资产名 |
| `dims` | array[string] | — | — | 固定 `["r2","om","vr"]` |
| `bins_per_dim` | integer | 档 | 整数 | 固定 5 |
| `vlabels` | array[string] | — | — | 固定 `["≈0.55","≈0.75","≈0.95","≈1.20","≈1.55"]`（vr 层量比标签） |
| `layers` | array[`CubeSlice`] | — | — | 固定 5 层（vr 档 0~4） |
| `comparison` | `CubeComparison` | — | — | 对比卡（naive vs ddsm） |
| `legend` | array[object] | — | — | 固定 5 项 `{min_p,max_p,label}`：`[0,0.45) P<0.45 看跌` / `[0.45,0.52) 0.45–0.52 中性` / `[0.52,0.58) 0.52–0.58 弱看涨` / `[0.58,1] >0.58 强看涨` / `no_sample 无样本`（斜纹） |
| `train_as_of` | string(date)/null | — | — | 训练段截止日 |
| `snapshot_at` | string(timestamp)/null | — | 秒 | 快照时间 |

`CubeSlice`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `vr_layer` | integer | 档 | 整数 | vr 层索引 0~4 |
| `vr_label` | string | — | — | 如 `≈0.95` |
| `cell_axis` | object | — | — | `{row:"r2", col:"om"}`（横轴 om、纵轴 r2） |
| `cells` | array[`CubeCell`] | — | — | 固定 25 项（r2 0~4 × om 0~4） |
| `filled_count` | integer | 格 | 整数 | 该层有样本格数 |
| `empty_count` | integer | 格 | 整数 | 该层无样本格数 |

`CubeCell`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `state` | array[3] integer | — | 整数 | `[r2档, om档, vr档]`，每维 ∈ {0..4} |
| `vr_layer` | integer | 档 | 整数 | = `state[2]` |
| `status` | enum `cube_cell_status` | — | — | filled/empty；**empty 格必须显式返回，不得省略** |
| `is_empty` | boolean | — | — | `status==empty` 的布尔别名 |
| `naive_n` | integer | 样本 | 整数 | 原始离散计数（不加噪） |
| `naive_p` | number/null | 概率 | 4 位 | 原始离散 P；empty 时 **null**（无估计值，禁止渲染为 0 或 50%） |
| `ddsm_n` | integer | 样本 | 整数 | 还原离散计数（加噪后 ×5） |
| `ddsm_p` | number/null | 概率 | 4 位 | 还原离散 P（加噪+收缩）；empty 时 null |
| `color_band` | string/null | — | — | 命中的图例标签；empty 时 `no_sample` |

`CubeComparison`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `valid_coverage_naive_pct` | number | 比率 | 4 位 | naive 有效覆盖率（有值格/125） |
| `valid_coverage_ddsm_pct` | number | 比率 | 4 位 | ddsm 有效覆盖率 |
| `mean_naive` / `mean_ddsm` | number/null | 概率 | 4 位 | 全格 P 均值（仅有效格） |
| `p_std_naive` / `p_std_ddsm` | number/null | 概率 | 4 位 | P 标准差 |
| `p_range_naive` / `p_range_ddsm` | number/null | 概率 | 4 位 | P 极差（max−min） |
| `extreme_count_naive` / `extreme_count_ddsm` | integer | 格 | 整数 | 极端格数（P<0.25 或 P>0.75） |
| `empty_count_naive` / `empty_count_ddsm` | integer | 格 | 整数 | 无样本格数 |
| `walk_forward_delta_naive_pp` | number/null | 百分点 | 4 位 | 不加噪版本走前 Δ（legacy 实测 −3.9%；后端须可追溯） |
| `walk_forward_delta_ddsm_pp` | number/null | 百分点 | 4 位 | 加噪版本走前 Δ（legacy 实测 +1.6~5.5pp） |
| `walk_forward_delta_ddsm_lo_pp` / `_hi_pp` | number/null | 百分点 | 4 位 | 上述区间下/上界 |
| `note` | string | — | — | 对比卡长文（左烂右好机理 + DiffsFormer 佐证 + 已证伪加噪） |

#### 5.26 `TrainingStatus`（`GET /engine/training-status`，UI：引擎页训练状态卡）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `total_cells` | integer | 格 | 整数 | 固定 125（5×5×5） |
| `filled_cells` | integer | 格 | 整数 | 有样本格数 |
| `coverage_pct` | number | 比率 | 4 位 | `filled_cells/125` |
| `avg_samples_per_cell` | number/null | 样本 | 4 位 | 有样本格平均样本数 |
| `min_samples_cell` | integer | 样本 | 整数 | 最少样本格样本数 |
| `min_n` | integer | 样本 | 整数 | 冻结 15 |
| `noise` | object | — | — | `{k_noise, p_perturb}`（=4/0.25） |
| `train_mode` | string | — | — | 训练方式长文（逐资产/全样本/季度滚动/无逐资产调参） |
| `noise_text` | string | — | — | 加噪增强长文（含"边缘格 n=3→n≈15 越过 MIN_N"） |
| `retrain_cycle` | string | — | — | 固定 `quarterly` |
| `last_retrain_at` | string(date)/null | — | — | 上次重训日 |
| `next_retrain_at` | string(date)/null | — | — | 下次重训日（季度滚动） |
| `retrain_note` | string | — | — | 重训周期长文（原年→季，属参数变更须重走六关，标注待验证） |
| `training_assets` | integer | 只 | 整数 | 训练资产数（含仅作特征的指数） |
| `index_only_assets` | integer | 只 | 整数 | 仅作特征、不产出信号的指数只数 |
| `dead_ends` | array[string] | — | — | 已证伪死路穷举（第4/5维、DDSM 用于 T+3、逐资产路由、loss-guided、IC 自适应） |

#### 5.27 `EngineInputItem` / `CrowdComposite`（`GET /engine/inputs` 增强，UI：引擎页六维输入）

`EngineInputItem`（`ddsm_3d` 与 `crowd_6d` 元素均用此结构）：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `feature` | string | — | — | `r2`/`om`/`vr`（DDSM 三维）或 `mom5`/`vr`/`dev`/`vpcorr`/`volat`/`skew`（拥挤度六维） |
| `group` | string | — | — | `ddsm_3d` / `crowd_6d` |
| `label` | string | — | — | 中文名（2日累计收益/σ归一动量/量比/5日动量/乖离率/量价相关/波动率/偏度） |
| `raw` | number/null | 随特征 | 4 位 | **原值**（未标准化）；`raw_unit` 给出单位 |
| `raw_unit` | string | — | — | 原值单位（`比率`/`倍数`/`相关系数`） |
| `z` | number/null | 标准差倍数 | 3 位 | z-score（**只用训练段**均值/标准差） |
| `level` | integer/null | 档 | 整数 | 档位；DDSM 三维 ∈ {0..4}，拥挤度六维可为 null（不切档） |
| `level_label` | string/null | — | — | 档位标签（如 `3/5`） |
| `ic_sign` | string | — | — | 训练段 IC 符号：`+`/`-`/`0` |
| `signed_z` | number/null | 标准差倍数 | 3 位 | `z × sign(ic_sign)`（复合前的每维贡献） |
| `formula` | string | — | — | 该维定义文本（来源 08 §4.1） |

`CrowdComposite`（`crowd` 对象）：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `composite_z` | number | 标准差倍数 | 3 位 | 六维按 IC 符号等权复合 z |
| `quantile` | number | 分位 | 4 位 | 复合 z 在训练段触发样本中的分位 |
| `quantile_level` | integer | 档 | 整数 | 分位档 1~5 |
| `quantile_threshold` | number | 分位 | 4 位 | 冻结 0.60（最拥挤 40%） |
| `is_veto` | boolean | — | — | 是否否决（`quantile >= 0.60`） |
| `status` | enum `veto_layer_status` | — | — | pass/veto/missing |
| `klow2` | number/null | 比率 | 4 位 | 下影线占振幅比 |
| `klow2_quantile` | number/null | 分位 | 4 位 | KLOW2 在训练段分位 |
| `klow2_level` | integer/null | 档 | 整数 | 分位档 1~5 |
| `klow2_threshold` | number | 分位 | 4 位 | 冻结 0.40（最不利 40%） |
| `klow2_is_veto` | boolean | — | — | 是否否决（`klow2_quantile <= 0.40`） |
| `klow2_status` | enum `veto_layer_status` | — | — | pass/veto/missing |

#### 5.28 `ShadowLedger` / `ShadowProgress`（`GET /ledger/shadow`，UI：引擎页影子盘台账）

`ShadowLedger`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `rows` | array[`LedgerEntry`] | — | — | §5.9（含 v3 `created_at`），按 `created_at` 倒序 |
| `total` | integer | 条 | 整数 | 台账总条数 |
| `summary` | object | — | — | `{total_records, open_signals, veto_abstains, backfilled_count, hit_rate, baseline_rate}`；`hit_rate` 比率 4 位可 null |
| `progress` | `ShadowProgress` | — | — | 连续记录进度 |
| `field_list` | array[string] | — | — | 固定穷举：`date/code/gate/p_up/ddsm_state/veto_crowd/veto_klow2/signal/t1_real/t3_real/t15_real/created_at` |
| `insert_only_note` | string | — | — | 字段说明长文（收盘时点固定写盘、事后不可改、到期自动回填） |
| `as_of` | string(date)/null | — | — | — |

`ShadowProgress`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `status` | enum `shadow_progress_status` | — | — | not_started/recording/qualified/gap |
| `consecutive_days` | integer | 交易日 | 整数 | 连续无漏单交易日数 |
| `target_days` | integer | 交易日 | 整数 | 冻结 60（上线门槛） |
| `progress_ratio` | number | 比率 | 2 位 | `min(1, consecutive_days/60)` |
| `start_date` | string(date)/null | — | — | 起点（首次入账日） |
| `target_date` | string(date)/null | — | — | 预计达标日 |
| `gap_days` | integer | 交易日 | 整数 | 漏单交易日数（>0 → status=gap） |
| `hit_rate` | number/null | 比率 | 4 位 | 滚动命中率 |
| `baseline_rate` | number | 比率 | 4 位 | 冻结 0.5830（58.3% 基准） |
| `deviation_pp` | number/null | 百分点 | 4 位 | `hit_rate − baseline_rate` |
| `note` | string | — | — | 门槛说明（连续 60 日无漏单且偏差 <2pp 才具上线资格） |

#### 5.29 `ShadowAudit`（`GET /engine/shadow-review`，UI：复盘页降级审查条）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `status` | enum `shadow_review_status` | — | — | idle/ok/bad（idle=影子盘未启动） |
| `rolling_days` | integer | 交易日 | 整数 | 固定 60 |
| `hit_rate` | number/null | 比率 | 4 位 | 滚动 60 日命中率 |
| `baseline_rate` | number | 比率 | 4 位 | 冻结 0.5830 |
| `deviation_pp` | number/null | 百分点 | 4 位 | 偏离度 |
| `threshold_pp` | number | 百分点 | 4 位 | 冻结 0.02（偏离 >2pp 自动标红降级） |
| `message` | string | — | — | 条幅文案（idle 显示"影子盘尚未启动…"） |
| `checked_at` | string(timestamp)/null | — | 秒 | 检查时间 |
| `note` | string | — | — | 长文（回测再漂亮也只是回测，最后保险是影子盘） |

#### 5.30 `GovernanceCycle` / `CyclePhase`（`GET /factors/governance-cycle`，UI：因子页治理周期卡）

`GovernanceCycle`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `phases` | array[`CyclePhase`] | — | — | 固定 5 项 |
| `note` | string | — | — | 长文（机器自动裁判，人只留机制变更权与紧急停机权） |

`CyclePhase`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `phase` | enum `governance_phase` | — | — | dig_scan/scorecard/monthly_rank/quarterly_review/ddsm_retrain |
| `label` | string | — | — | 下次挖掘扫描/下次评分卡/下次月榜·牌照/下次季复查/下次 DDSM 重训 |
| `cadence` | string | — | — | 周六/周日/每月 1 日/每季首月/每季 |
| `status` | enum `cycle_status` | — | — | scheduled/running/done/skipped/error |
| `last_run_at` | string(date)/null | — | — | 上次执行 |
| `next_run_at` | string(date)/null | — | — | 下次排期 |
| `rule_text` | string | — | — | 该阶段说明（提名 ≤3、冷却 90 天、月榜只产生提名不直接变更生产等） |
| `human_retained` | string | — | — | 人工保留权说明（机制变更权/紧急停机权） |

#### 5.31 `DigRecord`（`GET /factors/dig-records`，UI：因子页最近挖掘记录）

`DigRecord`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `record_id` | string | — | — | 记录 id |
| `scan_date` | string(date) | — | — | 扫描日 |
| `candidate` | string | — | — | 候选因子名（如 RESI30） |
| `f1_result` | enum `dig_result` | — | — | F1 有效性（近 6 月或近 60 日任一超基线） |
| `f1_detail` | string | — | — | 详情（如 `✓`） |
| `f2_result` | enum `dig_result` | — | — | F2 独立性（与现役最大共线 <0.7） |
| `f2_detail` | string | — | — | 共线值（如 `0.31`） |
| `f3_result` | enum `dig_result` | — | — | F3 增量（加入后 Δ≥+0.5pp 且开口不塌方） |
| `f3_detail` | string | — | — | Δ（如 `+0.6pp`） |
| `verdict` | enum `dig_verdict` | — | — | 判定 |
| `verdict_text` | string | — | — | 判定中文（如"未过 F3，回落候选池"） |
| `nomination_week` | string | — | — | 提名周（ISO 周） |
| `cooldown_until` | string(date)/null | — | — | 冷却到期日（冷却 90 天） |
| `created_at` | string(timestamp) | — | 秒 | 记录时间 |

`panel`（响应外层）：`{nomination_limit:3, cooldown_days:90, week_rule:"每周提名 ≤3"}`。

#### 5.32 `LifecycleRules`（`GET /factors/lifecycle` 增强，UI：因子页生命周期长文）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `admission_rules` | array[string] | — | — | 准入三项 AND：F1/F2/F3 文本 |
| `license_lines` | array[object] | — | — | 牌照四线 `{license, threshold, condition, note}`（候补 50 / 试用 60 / 续聘 T2 70 / 正式 T3 80） |
| `retire_rules` | array[string] | — | — | 淘汰五线（急性熔断/缓性衰减/结构红线/分数失守）文本 |
| `dual_exit` | array[string] | — | — | 双出口（软出口降级梯/硬出口 A/B 对照 60 交易日） |
| `false_kill_guards` | array[string] | — | — | 防误杀三保险（条件绩效口径/开口<20 不出结论/A/B 期牌照冻结） |
| `revive_rules` | array[string] | — | — | 冷冻复活（触发条件与路径，禁止直接回生产） |
| `source` | string | — | — | **文本来源**，如 `docs/00-charter/00-design-reference-legacy-v2.html §四盘/生命周期` + `docs/00-charter/02-prd.md` F-14 |
| `freeze_note` | string | — | — | 规则文本冻结声明（改动须重走六关） |

#### 5.33 `HoldingsDataSource`（`GET /settings/holdings-data`，UI：设置页持仓数据卡）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `primary_path` | string | — | — | `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json` |
| `primary_exists` | boolean | — | — | 是否存在 |
| `primary_modified_at` | string(timestamp)/null | — | 秒 | 文件修改时间 |
| `primary_count` | integer | 只 | 整数 | 源文件持仓只数 |
| `legacy_path` | string | — | — | 旧位置那份 funds_data.json 路径 |
| `legacy_exists` | boolean | — | — | 是否存在 |
| `legacy_modified_at` | string(timestamp)/null | — | 秒 | 文件修改时间 |
| `legacy_count` | integer | 只 | 整数 | 旧文件持仓只数 |
| `consistent` | boolean | — | — | 两份是否一致（内容/时间任一不同即 false） |
| `diff_fields` | array[string] | — | — | 不一致字段名清单（一致时 []） |
| `readonly` | boolean | — | — | 固定 true（产品**不改写**源文件） |
| `diff_note` | string | — | — | 「估值≠净值的实证」长文（旧文件会滞后数日） |
| `checked_at` | string(timestamp) | — | 秒 | 检查时间 |

#### 5.34 `LedgerChain`（`GET /ledger/chain`，UI：信号时间线点击展开六步推导链）

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `date` | string(date) | — | — | 开口日 |
| `code` | string | — | — | 基金代码 |
| `name` | string | — | — | 基金名 |
| `gate` | enum `gate` | — | — | 触发门 |
| `signal` | enum `signal` | — | — | 写入时信号 |
| `p_up` | number | 概率 | 4 位 | 写入时 T+1 概率 |
| `chain` | array[`ChainStep`] | — | — | 固定 6 步（结构同 §6.4，`key` = gate/ddsm/veto_crowd/veto_klow2/exit/output） |
| `metrics` | object | — | — | 关键数值（键枚举同 §6.4 `metrics`） |
| `source_ledger` | string | — | — | 恒 `shadow_signals.jsonl` |
| `created_at` | string(timestamp) | — | — | 入账时刻 |

---

### 6. 接口详述

#### 6.1 元信息

##### GET /api/v1/runtime
- 调用方：全局壳/Topbar 首屏，之后 12s 轮询。
- 请求参数：无。
- 响应 200 `data`：`Runtime`（§5.18）。
- 错误：`E_IO`（runtime.json 不可读）。
- 口径：`as_of` 取估值/预测/台账三者中最新者可用的日期，并在 `staleness` 中说明滞后。

#### 6.2 持仓 CRUD

##### GET /api/v1/holdings
- 调用方：持仓页首屏、明细表。
- 请求参数（query）：
  - `with`：string，可选，逗号分隔，取值 `valuation,nav,prediction,summary`；默认 `valuation,nav,prediction`。
  - `group`：enum `holding_group`，可选，筛选类别。
- 响应 200 `data`：`{ rows: HoldingRow[], summary: HoldingsSummary }`（rows 见 §5.1，summary 见 §6.2.1）。
- 错误：`E_IO` / `E_PARSE`（holdings.json 损坏）。
- 口径：`market_value` 优先用估值，其次官方净值，**两者皆无则 `null`**（`mv_source=null`，并给 `fallback_value=cost_amount`）；禁止成本价进入 `market_value`（A-02）。`today_pnl_amt` 仅对非 null `change_rate` 计算。

**6.2.1 `HoldingsSummary`**

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `total_value` | number | 元 | 2 位 | `Σ market_value`（仅 `market_value != null` 的可信行；与明细逐行求和误差=0，满足 F-01） |
| `fallback_value` | number | 元 | 2 位 | `Σ fallback_value`（无估值行按成本计的金额，A-02） |
| `total_value_with_fallback` | number | 元 | 2 位 | `total_value + fallback_value`；仅作"含未知行成本口径"的辅助展示，主数字用 `total_value` |
| `covered_cost_amount` | number | 元 | 2 位 | `Σ cost_amount`（仅计入 `market_value != null` 的行） |
| `today_pnl_amt` | number/null | 元 | 2 位 | `Σ today_pnl_amt`（未知行从分子分母同剔）；全未知 null |
| `total_pnl_amt` | number | 元 | 2 位 | `total_value − covered_cost_amount`（仅可信行的累计收益） |
| `return_rate` | number | 比率 | 4 位 | `total_pnl_amt / covered_cost_amount`；`covered_cost_amount=0` 时 null |
| `covered_count` | integer | 只 | 整数 | `market_value != null` 的只数（非按 `change_rate`，官方回填行也算，A-02） |
| `total_count` | integer | 只 | 整数 | 持仓总只数 |
| `coverage_note` | string | — | — | 必须含两段：可信覆盖（"可信估值覆盖 N/M 只"）+ 成本口径声明（"另有 X 元未知行按成本计，合计 total_value_with_fallback"）；N=M 时写"全部覆盖" |
| `as_of` | string(date)/null | — | — | — |

##### GET /api/v1/holdings/{code}
- 调用方：编辑弹窗、行详情。
- 路径参数：`code`（6 位数字）。
- 响应 200 `data`：`HoldingRow`（§5.1）。
- 错误：`E_NOT_FOUND`（无此 code）。
- 口径：与列表同字段，含完整 `valuation.trace`。

##### POST /api/v1/holdings
- 调用方：录入弹窗。
- 请求体：

| 字段 | 类型 | 必填 | 校验口径 |
|---|---|---|---|
| `code` | string | 是 | 6 位数字；已存在 → `E_CONFLICT` |
| `name` | string | 是 | 非空 |
| `group` | enum `holding_group` | 是 | 穷举内 |
| `tier` | enum `coverage_tier` | 是 | 穷举内 |
| `shares` | number | 与 `cost_amount` 至少一项 | ≥0，4 位 |
| `cost_amount` | number | 与 `shares` 至少一项 | ≥0，2 位 |
| `avg_cost` | number | 否 | 有则据此反推 cost_amount（`avg_cost×shares`） |
| `confirm_days` | integer | 是 | ∈ {1,2,3} |
| `proxy_code` | string/null | 否 | 6 位数字或 null |

- 响应 201 `data`：新建的 `HoldingRow`。
- 错误：`E_VALIDATION`（`detail` 给出字段级原因）/ `E_CONFLICT`。
- 口径：写入 `data/holdings.json`（原子替换）；不改写桌面 `funds_data.json`。

##### PUT /api/v1/holdings/{code}
- 调用方：编辑弹窗。
- 请求体：同 POST 的可选子集（`code` 不可改）。
- 响应 200 `data`：更新后的 `HoldingRow`。
- 错误：`E_NOT_FOUND` / `E_VALIDATION`。
- 口径：全量覆盖式更新；未传字段保持原值。

##### DELETE /api/v1/holdings/{code}
- 调用方：行操作 → 二次确认。
- 响应 200 `data`：`{ "deleted_code": "014320" }`。
- 错误：`E_NOT_FOUND`。
- 口径：只删产品自持 `holdings.json`；台账中历史记录**不删**（审计保留）。

##### POST /api/v1/holdings/{code}/transactions
- 调用方：加仓/减仓弹窗。
- 请求体：

| 字段 | 类型 | 必填 | 口径 |
|---|---|---|---|
| `tx_type` | enum `tx_type` | 是 | buy/sell |
| `shares` | number | 是 | >0，4 位；sell 不得超过当前份额 → 否则 `E_VALIDATION` |
| `price` | number | 是 | 成交净值，元/份，4 位 |
| `date` | string(date) | 是 | 交易确认日 |
| `fee_amount` | number | 否 | 元，2 位，默认 0 |

- 响应 200 `data`：变更后的 `HoldingRow`。
- 错误：`E_NOT_FOUND` / `E_VALIDATION`。
- 口径：buy → `shares += tx.shares`、`cost_amount += tx.shares×price + fee_amount`；sell → `shares −= tx.shares`、`cost_amount -= tx.shares×avg_cost`（摊薄成本口径，不含在途申赎）。

##### POST /api/v1/holdings/import
- 调用方：设置页"重新导入"。
- 请求体：`{ "mode": "replace" }`，`mode` ∈ `replace` / `merge`（默认 `replace`）。
- 响应 200 `data`：`{ "imported_count": 22, "source": "app_data/funds_data.json", "imported_at": "...", "warnings": [] }`。
- 错误：`E_IO`（源文件不存在/不可读）/ `E_PARSE`。
- 口径：源文件固定为 `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json`；只读不改；`replace` 覆盖产品持仓（导入前自动备份到 `data/backup/`）。

#### 6.3 实时估值

##### GET /api/v1/valuations
- 调用方：持仓页、分析页。
- 请求参数（query）：`mode`（enum `valuation_mode`，可选，筛选）。
- 响应 200 `data`：`{ "rows": [ {code, name, valuation, nav} ] }`（`valuation` §5.2、`nav` §5.3）。
- 错误：`E_SOURCE_TIMEOUT`（五档全失败时仍返回 `unknown` 行，不报错；仅当无法读取本地缓存时报错）。
- 口径：同一基金同日**对外展示**只有一个 `valuation_mode`（取 `(date, code)` 最新入账记录）；`unknown` 行 `change_rate=null`。当日历史（含首次入账与后续刷新）存于 `valuation_history.jsonl`，INSERT-ONLY（A-01）。

##### GET /api/v1/valuations/{code}
- 调用方：徽章详情展开。
- 请求参数（query）：`history`（boolean，可选，默认 false）。
- 响应 200 `data`：`{ code, name, valuation, nav, history? }`；`history=true` 时 `history` 为 `Valuation[]`（按 `written_at` 升序，含当日全部入账记录，A-01）。
- 错误：`E_NOT_FOUND`。
- 口径：`valuation.trace` 完整返回，前端据此拼接降级链路；无 trace 时不得编造。`history` 仅供"可追溯当时用的哪一档"，前端默认不展示，徽章详情可展开。

##### GET /api/v1/valuations/precision
- 调用方：持仓页估值精度汇总。
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `groups` | array[object] | — | — | 每项 `{confidence, count, market_value, weight_ratio}`；`confidence` 枚举 §1.3 |
| `weighted_mae_rate` | number/null | 比率 | 4 位 | 市值加权 MAE；无可统计样本 null |
| `industry_baseline_mae_rate` | number | 比率 | 4 位 | 固定 0.008（0.80%）；来源为回测口径，待后端可追溯（残留风险） |
| `window_days` | integer | 交易日 | 整数 | 统计窗口，固定 40 |
| `mode_distribution` | array[object] | — | — | **v3 追加**：每项 `{mode, mode_label, count, market_value, weight_ratio}`，按 `valuation_mode` 五档穷举（official/intraday/holdings/proxy/unknown）；供 `.vsum` 展示来源分布，与 `groups`（置信度分组）互补 |

- 错误：`E_IO`。

#### 6.4 预测

##### GET /api/v1/predictions
- 调用方：分析页、信号页。
- 请求参数（query）：`tier`（enum `coverage_tier`，可选，可多值逗号分隔）；`signal`（enum `signal`，可选）。
- 响应 200 `data`：`{ "rows": PredictionSummary[], "engine_status": enum, "as_of": string|null }`（§5.4）。
- 错误 / 空态口径（A-06，**禁止用 `empty` 承载故障**）：
  1. 当日快照存在 → `ok=true`，`engine_status ∈ {online, running}`，正常返回（`rows=[]` 才是合法 `empty`："引擎已跑，今日无开口"）。
  2. 当日无快照但存在**旧快照** → `ok=true`，返回旧快照 `rows` 且 `as_of=旧日期`，`engine_status=offline`；前端渲染**陈旧态 + "引擎未运行，展示 <date> 快照"**，不是 `empty`。
  3. 完全无快照 → `ok=false`，`error.code=E_ENGINE_OFFLINE`（HTTP 503），前端渲染 `error` 态"引擎未运行"。
- 口径：C/D 档可返回 `prediction=null` 或 `signal` 定式为不支持；前端据此显示"待验证/暴露待定"。T+3/T+15 未验证窗口的 `direction` 恒 `gray`（A-04）。

##### GET /api/v1/predictions/{code}
- 调用方：链路展开（6 步）。
- 响应 200 `data`：在 `PredictionSummary` 基础上追加：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `chain` | array[`ChainStep`] | — | — | 固定 6 步，见下 |

`ChainStep`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `step` | integer | — | 整数 | 1..6 |
| `key` | string | — | — | `gate`/`ddsm`/`veto_crowd`/`veto_klow2`/`exit`/`output` |
| `title` | string | — | — | ①触发门…⑥输出 |
| `status` | string | — | — | `on`（亮灯/通过）/`off`（未亮灯）/`missing`（数据缺失） |
| `detail` | string | — | — | 可读描述 |
| `metrics` | object | — | — | 关键数值，见下 |

`metrics` 键（枚举，缺失该键表示数据缺失）：`ret_rate`（比率，小数）、`vr`（倍数，4 位）、`r2`（[0,1]，4 位）、`om`（比率，4 位）、`ddsm_state`（array[3]、整数）、`p_up`（概率，4 位）、`crowd_z`（z 值，3 位）、`crowd_quantile`（比率，4 位）、`klow2`（比率，4 位）、`klow2_quantile`（比率，4 位）、`band`（概率，4 位）、`exit_threshold`（概率，4 位，固定 0.5200）、`veto_crowd_status`、`veto_klow2_status`（枚举 `veto_layer_status`）。

- 错误：`E_NOT_FOUND`（无此 code）。
- 口径：出口步必须返回 `exit_threshold=0.52`；`P≤0.52` 步状态为 off。任一否决层 `status=missing` → 该步 `status=missing`（**不得记为 off/通过**），且总 `signal=abstain`、`reason=veto_data_missing`（A-05）。

#### 6.5 组合加权

##### GET /api/v1/portfolio/forecast
- 调用方：持仓页/分析页三窗口卡。
- 响应 200 `data`：`{ "windows": PortfolioForecast[], "engine_status": enum, "as_of": string|null }`（§5.7），固定 3 项。
- 错误 / 空态口径（A-06）：与 §6.4 `/predictions` 同规则——当日快照存在（含引擎已跑且无开口）→ `ok=true`；无当日快照但有旧快照 → `ok=true` + `engine_status=offline` + `as_of=旧日期`（陈旧态）；完全无快照 → `ok=false` + `E_ENGINE_OFFLINE`（error 态）。**禁止**把引擎离线折成 `empty`。
- 口径：只纳入 A/B 档开口仓位；C/D 出现在 `tier_excluded`（仅列组合中实际存在者）；`weighted_p=null` 时界面"今日无开口/该窗口无概率"；`excluded_ratio>0` 必须显式展示。组合 `direction` 需同时满足出口阈值与最小覆盖门槛（§5.7，A-03）。

#### 6.6 复盘

##### GET /api/v1/review/scores
- 调用方：复盘页成绩表/hero。
- 请求参数（query）：`data_kind`（`backtest`/`shadow_live`，默认 `backtest`）。
- 响应 200 `data`：`{ "scores": ReviewScore[], "hero": {window, hit_rate, baseline_rate, delta_pp, label} }`。
- 错误：`E_IO`（成绩文件缺失 → 空态）。
- 口径：`baseline_status=pending` 时 `baseline_rate` 与 `delta_pp` 为 null，界面显示"待填充"，**不得填估计值**；`data_kind=shadow_live` 且样本不足时返回 `scores: []` 且 `note` 说明"影子盘未启动/样本不足"。

##### GET /api/v1/review/reconciliation
- 调用方：复盘页逐笔对账。
- 请求参数（query）：`limit`（integer，默认 60）、`offset`（integer，默认 0）。
- 响应 200 `data`：`{ "rows": ReconcileRow[], "total": integer }`。
- 错误：`E_IO`。
- 口径：按 `date` 倒序；`result` 由 §5.10 规则计算。

##### GET /api/v1/review/cv-config
- 调用方：复盘页口径说明悬浮。
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `cv_mode` | string | — | — | 固定 `walk_forward` |
| `random_split` | boolean | — | — | 固定 false（禁随机切分） |
| `purge_gap` | string | — | — | 固定 `H+2` |
| `placebo_min_pp` | number | 百分点 | 4 位 | 固定 0.02（≥2pp） |
| `holdout_days` | integer | 交易日 | 整数 | 固定 60 |
| `holdout_start_date` | string(date)/null | — | — | 冻结起始时点；未定 null（残留风险） |
| `ledger_policy` | string | — | — | 固定 `insert_only` |

- 错误：`E_IO`。

#### 6.7 台账

##### GET /api/v1/ledger
- 调用方：信号页时间线、引擎页台账、复盘逐笔。
- 请求参数（query）：`limit`（默认 60）、`offset`（默认 0）、`code`（可选）、`from`/`to`（date，可选）。
- 响应 200 `data`：`{ "rows": LedgerEntry[], "total": integer }`（§5.9）。
- 错误：`E_IO`。
- 口径：读取时按 `(date, code)` 左连接 `backfill.jsonl`；只读，**无编辑/删除端点**（PRD G10）。

##### POST /api/v1/ledger/entries
- 调用方：本地引擎（收盘时点）。
- 请求体：`date, code, gate, p_up, ddsm_state, veto_crowd, veto_klow2, signal, market_value, cost_est`（类型/口径同 §5.9）。
- 响应 201 `data`：`{ "written": true, "date": "...", "code": "..." }`。
- 错误：`E_CONFLICT`（同日同 code 已存在）/ `E_VALIDATION` / `E_IO`。
- 口径：仅允许追加；服务端强制 `(date, code)` 唯一；`signal` 写入即冻结。

##### POST /api/v1/ledger/backfill
- 调用方：本地引擎（启动时 + 收盘后）。
- 请求体：`{ "entries": [ {date, code, t1_real, t3_real, t15_real} ] }`，未到期的键可省略。
- 响应 200 `data`：`{ "backfilled_count": integer, "skipped": integer }`。
- 错误：`E_VALIDATION`（存在无对应 signal 的 date+code）/ `E_IO`。
- 口径：写入独立 `backfill.jsonl`，**不改 `signals.jsonl` 原行**；只写 `t*_real`。

#### 6.8 因子

##### GET /api/v1/factors/pans
- 响应 200 `data`：`{ "pans": FactorPan[] }`（§5.11），固定 4 项（顺序：正式盘、淘汰影子盘、有效影子盘、冷冻盘）。
- 错误：`E_IO`（盘面/账本缺失 → 空态）。

##### GET /api/v1/factors/books
- 响应 200 `data`：`{ "books": FactorBook[] }`（§5.13），固定 6 项（枚举 `factor_book` 穷举）。
- 错误：`E_IO`。
- 口径：UI 因子页展示前 4 本（adopted_factors/scan_history/factor_health/retired_log），后 2 本（shadow_signals/factor_arena）在引擎页展示；接口一次返回全部并带 `filename`。

##### GET /api/v1/factors/score-chain
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `lift_bins` | array[object] | — | — | 每项 `{min_lift, k_lift, label}`；`min_lift` 比率 4 位，`k_lift` 分数 4 位；悬崖表穷举：≥1.30→1.0 / ≥1.20→0.80 / ≥1.10→0.65 / ≥1.00→0.50 / <1.00→−0.80 / <0.84→−1.3 |
| `window_weights` | array[object] | — | — | 六窗 `{window, window_label, weight}`，权重穷举 `8/22/15/10/30/15`（合计 100，次序同 `factor_window`） |
| `formula_text` | string | — | — | 评分链可读说明 |
| `bootstrap_percentiles` | object | — | — | **v3 追加**：`{p50,p90,p95,p99,p995}`＝`−10.8 / 38.7 / 48.4 / 61.7 / 64.1`（bootstrap 500 校准分位，固定展示常量） |
| `judges` | array[object] | — | — | **v3 追加**：四裁判 `{judge, scope, metric, note}`，`judge` ∈ `lift`（管分数）/`t`（管闸门）/`admission`（管折扣）/`backtest`（管晋升） |
| `floor_note` | string | — | — | **v3 追加**：地板说明（k_lift <1.00 → −0.80 天花板，<0.84 → −1.3；不对称惩罚即噪声抑制器） |
| `rule_source` | string | — | — | **v3 追加**：文本来源，固定 `docs/00-charter/00-design-reference-legacy-v2.html §评分链` |

- 错误：`E_IO`。

##### GET /api/v1/factors/lifecycle
- 响应 200 `data`：`LifecycleRules`（§5.32，v3 由 v2 的 `{admission_rules,retire_rules,revive_rules}` **扩充**为含 `license_lines`/`dual_exit`/`false_kill_guards`/`source`；v2 三个字段名保留不变）。文本来源由后端给出（`source` 字段），前端不硬编码规则。
- 错误：`E_IO`。

#### 6.9 引擎与任务

##### GET /api/v1/engine/status
- 调用方：引擎页 HUD，12s 轮询。
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `status` | enum `engine_status` | — | — | 在线/离线/运行中/异常 |
| `pid` | integer/null | — | 整数 | 引擎进程 id |
| `port` | integer | — | 整数 | 服务端口 |
| `version` | string | — | — | 引擎版本 |
| `active_engine_version` | string | — | — | 当前 active 注册版本 |
| `started_at` | string(timestamp)/null | — | 秒 | — |
| `last_heartbeat_at` | string(timestamp)/null | — | 秒 | 最近心跳 |
| `last_success_at` | string(timestamp)/null | — | 秒 | 最近一次成功预测时间 |
| `snapshot_as_of` | string(date)/null | — | — | 预测快照日期 |
| `shadow_status` | enum `shadow_review_status` | — | — | **v3 追加**：影子盘三态（HUD「影子盘」卡） |
| `shadow_consecutive_days` | integer | 交易日 | 整数 | **v3 追加**：连续记录日数（HUD 副文案 `N / 60`） |
| `shadow_target_days` | integer | 交易日 | 整数 | **v3 追加**：冻结 60 |
| `training_assets` | integer | 只 | 整数 | **v3 追加**：训练资产数（HUD「训练资产」卡） |
| `index_only_assets` | integer | 只 | 整数 | **v3 追加**：仅作特征、不产出信号的指数只数 |
| `state_grid_total_cells` | integer | 格 | 整数 | **v3 追加**：固定 125（HUD「状态格覆盖」卡） |
| `state_grid_filled_cells` | integer | 格 | 整数 | **v3 追加**：有样本格数 |
| `state_grid_coverage_pct` | number | 比率 | 4 位 | **v3 追加**：`filled/125` |
| `avg_samples_per_cell` | number/null | 样本 | 4 位 | **v3 追加**：平均样本/格 |
| `min_samples_cell` | integer | 样本 | 整数 | **v3 追加**：最少样本格样本数 |
| `last_retrain_at` | string(date)/null | — | — | **v3 追加**：上次重训日（HUD「上次重训」卡） |
| `next_retrain_at` | string(date)/null | — | — | **v3 追加**：下次重训日 |
| `data_freshness_snapshot_date` | string(date)/null | — | — | **v3 追加**：数据快照日（HUD「数据新鲜度」卡） |
| `data_freshness_days_behind` | integer | 交易日 | 整数 | **v3 追加**：滞后交易日数 |

- 错误：`E_IO`（返回 `status=offline` 且 HTTP 200，前端据此显示离线态）。
- **v3 口径**：HUD 六卡由本接口一次给全（影子盘/引擎版本/训练资产/状态格覆盖/上次重训/数据新鲜度）；前端不再另发请求拼装。`version`/`active_engine_version` 沿用 v2。

##### GET /api/v1/engine/inputs
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `ddsm_3d` | array[`EngineInputItem`] | — | — | 固定 3 项（`feature` ∈ `r2`/`om`/`vr`），结构见 §5.27（v3 在 v2 的 `{feature,level,z}` 上**追加** `raw/raw_unit/z/ic_sign/signed_z/formula/label`） |
| `crowd_6d` | array[`EngineInputItem`] | — | — | 固定 6 项（`feature` ∈ `mom5`/`vr`/`dev`/`vpcorr`/`volat`/`skew`），结构同 §5.27 |
| `crowd` | `CrowdComposite` | — | — | **v3 追加**：复合拥挤度 + KLOW2（见 §5.27），驱动 z-bar 复合判断行 |
| `code` | string/null | — | — | **v3 追加**：当前快照资产代码（一键切换资产） |
| `name` | string/null | — | — | **v3 追加**：资产名 |
| `train_as_of` | string(date)/null | — | — | 训练段截止日 |
| `snapshot_at` | string(timestamp)/null | — | — | 快照时间 |

- 错误：`E_IO`（无快照 → 空数组 + `snapshot_at=null`）。
- **v3 口径**：三维/六维每维必须带 `raw`（原值）+ `z`（z-score）+ `level`（档位，六维可 null）+ `ic_sign`（训练段 IC 符号）+ `signed_z`；`crowd.composite_z` 为六维按 `ic_sign` 等权复合结果。z-score/分位/IC 符号**只用训练段**（逐年走前，purge=H+2）。

##### GET /api/v1/engine/ddsm
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `dims` | array[string] | — | — | 固定 `["r2","om","vr"]` |
| `bins_per_dim` | integer | 档 | 整数 | 固定 5 |
| `cells` | array[object] | — | — | 125 项 `{state:[3], p:number|null, n:integer, filled:boolean}`（原 v2 全资产聚合表；**逐资产双切片请用 `/engine/ddsm/cube` §6.11.7**） |
| `noise` | object | — | — | `{k_noise, p_perturb}`（同 §5.14） |
| `legend` | array[object] | — | — | 热力色带 `{min_p, max_p, label}`，穷举：`[0,0.45) P<0.45 看跌` / `[0.45,0.52) 中性` / `[0.52,0.58) 弱看涨` / `[0.58,1] 强看涨` |
| `training_summary` | object | — | — | **v3 追加**：`{filled_cells, coverage_pct, avg_samples_per_cell, min_samples_cell}`（同 §5.26 口径） |

- 错误：`E_IO`。
- **v3 口径**：本接口保留 v2 的"全资产聚合 125 格"语义；`GET /engine/ddsm?code=` 可加 v3 查询参数 `code` 返回该资产的 ddsm 单元格（但不含 naive 对照），naive/ddsm 双切片与 vr 层切换统一走 §6.11.7。

##### GET /api/v1/engine/frozen-params
- 响应 200 `data`：`FrozenParams`（§5.14）。**v3 追加**：`gate_e1`/`gate_e3`/`purge_gap`/`window_weights`/`window_min_days`/`license_lines`（冻结参数表补充门/方法/窗权重/牌照线，供引擎页"冻结参数表"一次给全）。
- 错误：`E_IO`。

##### GET /api/v1/engine/registry
- 响应 200 `data`：`{ "engines": [ {version, status, note, metrics:{hit_rate, baseline_rate, delta_pp}, can_rollback} ] }`；`status` 枚举 `engine_registry_status`。
- 错误：`E_IO`。

##### GET /api/v1/tasks
- 请求参数（query）：`status`（枚举 `task_status`，可选）、`limit`（默认 20）。
- 响应 200 `data`：`{ "tasks": Task[] }`（§5.15）。
- 错误：`E_IO`。

##### POST /api/v1/tasks
- 请求体：

| 字段 | 类型 | 必填 | 口径 |
|---|---|---|---|
| `type` | enum `task_type` | 是 | 穷举内 |
| `params` | object | 否 | 类型相关参数（如 `run_backtest` 的 `window`）；不得用于改冻结参数 |

- 响应 202 `data`：`Task`。
- 错误：`E_VALIDATION`（试图修改冻结参数 → 明确拒绝）/ `E_ENGINE_OFFLINE`。
- 口径：`params` **不得**包含 `k_noise/p_perturb/min_n/shrink/band/veto_*_quantile`，出现即 `E_VALIDATION`（冻结参数不可经 API 修改，PRD F-15）。

##### GET /api/v1/tasks/{task_id}
- 响应 200 `data`：`Task`。
- 错误：`E_NOT_FOUND`。

#### 6.10 设置与数据源

##### GET /api/v1/settings
- 响应 200 `data`：`Settings`（§5.16）。
- 错误：`E_IO`（缺失时返回默认值 + `is_default=true`）。

##### PUT /api/v1/settings
- 请求体：`Settings` 的可选子集；`llm.api_key` 若传入则只落本地且**绝不回显/不回传**。
- 响应 200 `data`：更新后的 `Settings`（`api_key` 永不出现，仅 `api_key_set`）。
- 错误：`E_VALIDATION`。
- 口径：`llm.temperature` 固定 0、`llm.output_format` 固定 json，传入其他值即 `E_VALIDATION`；`llm.mode` 只读 shadow。

##### GET /api/v1/data-sources/health
- 响应 200 `data`：`{ "sources": DataSourceHealth[] }`（§5.17），固定 4 项（枚举 `data_source_id`）。
- 错误：`E_IO`。

##### POST /api/v1/data-sources/probe
- 请求体：`{ "source_id": "tencent_kline" \| null }`（null = 全部探测）。
- 响应 202 `data`：`Task`（探测为异步任务，前端轮询）。
- 错误：`E_VALIDATION`。

##### GET /api/v1/about
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `product_name` | string | — | — | 固定 `极境 ZenithLens` |
| `version` | string | — | — | 产品版本 |
| `api_version` | string | — | — | 固定 `v1` |
| `python_min` | string | — | — | 固定 `3.8` |
| `deployment` | string | — | — | 固定 `local_single_user` |
| `storage_note` | string | — | — | "全部本地存储，数据不出本机" |
| `disclaimer` | string | — | — | "不构成投资建议" |
| `built_at` | string(timestamp)/null | — | 秒 | 构建时间 |

- 错误：`E_IO`。

---

### 6.11 v3 新增接口详述（39~53）

> 全部为**只读 GET**、无写端点；均套用统一信封（§2），`data` 结构见对应共享对象。
> 每个接口标注**前端消费点（页/组件）**，供 `frontend-dev` 逐项落地 §9 的 40 项组件。

#### 6.11.1 GET /api/v1/holdings/coverage
- 调用方（消费点）：**持仓页**「覆盖度四档 `.covbar`」+「失效三类」长文。
- 请求参数：无。
- 响应 200 `data`：`CoveragePanel`（§5.19）。
- 错误：`E_IO`。
- 口径：`weight_ratio = market_value / total_value`，未知行不计入分子分母；`invalidation_note` 必含"定义失效／数据失效／框架失效"三类；`no_solution_count` 附文案"原理无解：N 只"。

#### 6.11.2 GET /api/v1/holdings/risk
- 调用方：**持仓页**「风险指标折叠区」（`.fold` 展开才请求，慢接口）。
- 请求参数：`days`（integer，可选，默认 250）。
- 响应 200 `data`：`RiskMetrics`（§5.20）。
- 错误：`E_IO`。
- 口径：`var95_rate`/`max_drawdown_rate` 均以**正数表示损失幅度**；样本不足时对应字段 null，UI 显示"—"，禁止用 0 冒充。

#### 6.11.3 GET /api/v1/signals/state
- 调用方：**信号页**「最新信号空态四要素」+「触发门 E1/E3 卡 + E2/E4 剔除说明」。
- 请求参数：无。
- 响应 200 `data`：`SignalState`（§5.21）。
- 错误：`E_IO`。
- 口径：`state=no_open` 时 `empty_note` 必写"这是常态，不是故障"；`gates` 与 `excluded_gates` 各固定 2 项；`or_merge_forbidden` 恒 true（四类事件禁止 OR 合并）。

#### 6.11.4 GET /api/v1/meta/definitions
- 调用方：**分析页**「T+1 口径定义折叠区 + 三条执行路径」。
- 请求参数：无。
- 响应 200 `data`：`DefinitionCard`（§5.22）。
- 错误：`E_IO`。
- 口径：`formula` 固定 `up = 1 若 close[T+1] > close[T]`；`paths` 固定 3 项；`conclusion` 必须指向 `hold_existing`（B），**不得暗示当天买入**。

#### 6.11.5 GET /api/v1/ledger/chain
- 调用方：**信号页**信号时间线 `.tl-item` 点击展开事件链 `.ev`（§9.2-9）；**分析页**可复用六步链。
- 请求参数：`date`（date，必填）、`code`（string，必填）。
- 响应 200 `data`：`LedgerChain`（§5.34）。
- 错误：`E_NOT_FOUND`（无该条台账）/ `E_IO`。
- 口径：固定 6 步（① 触发门 ② DDSM ③ 拥挤度否决 ④ KLOW2 否决 ⑤ 出口 ⑥ 输出/回填）；`metrics` 键枚举同 §6.4；出口步必返 `exit_threshold=0.5200`；任一否决层 `missing` → 该步 `status=missing` 且总 `signal=abstain`（A-05）。**禁止编造步骤数值**。

#### 6.11.6 GET /api/v1/ledger/shadow
- 调用方：**引擎页**「影子盘台账表 + 连续记录进度条（0/60）+ 字段说明（INSERT-ONLY）」（§9.5-21）；**复盘页**逐笔对账可复用 `rows`。
- 请求参数：`limit`（integer，默认 60）、`offset`（integer，默认 0）。
- 响应 200 `data`：`ShadowLedger`（§5.28）。
- 错误：`E_IO`。
- 口径：`rows` 按 `created_at` 倒序；`created_at` 为规范入账时刻（与 `written_at` 恒等），INSERT-ONLY；`progress.status=not_started` 时 `consecutive_days=0`、`progress_ratio=0`；`hit_rate` 无回填样本时 null（UI 显示"—"）。

#### 6.11.7 GET /api/v1/engine/ddsm/cube
- 调用方：**引擎页**「125 格状态立方体：naive vs DDSM 双 5×5 切片 + vr 层切换 + 悬停 n/P + 对比卡 + 长文」（§9.5-26）。
- 请求参数：`code`（string，必填，资产代码）；`vr_layer`（integer，可选，0~4；缺省返回全部 5 层）。
- 响应 200 `data`：`StateCube`（§5.25）。
- 错误：`E_NOT_FOUND`（无该资产）/ `E_IO`。
- 口径：每格必须同时给 `naive_p`/`naive_n` 与 `ddsm_p`/`ddsm_n`；`status=empty` 的格**必须显式返回**（`naive_p=null`、`ddsm_p=null`），前端渲染斜纹"无样本"，**禁止**渲染为 0 或 50%；`comparison` 四指标（有效覆盖/P 标准差/极端格数/走前 Δ）齐备；naive 用**未加噪真实档位**计数，ddsm 用加噪+收缩结果（A-05）。

#### 6.11.8 GET /api/v1/engine/training-status
- 调用方：**引擎页**「训练状态卡（125 格/有样本格/平均样本/最少样本 + 加噪说明 + 已证伪死路）」（§9.5-23）。
- 请求参数：无。
- 响应 200 `data`：`TrainingStatus`（§5.26）。
- 错误：`E_IO`。
- 口径：`noise` 与 §5.14 冻结值一致；`dead_ends` 穷举已证伪死路（第 4/5 维、DDSM 用于 T+3、逐资产路由、loss-guided 加噪、IC 自适应加噪），前端逐条展示"勿重试"。

#### 6.11.9 GET /api/v1/engine/arena
- 调用方：**引擎页**「因子竞技场矩阵（行=配置、列=六窗、格=开口/命中/配对 Δ；红绿蓝黄配色 + 留一法行 + 警示 ▲）」（§9.5-22）。
- 请求参数：无。
- 响应 200 `data`：`ArenaMatrix`（§5.24）。
- 错误：`E_IO`。
- 口径：列固定 6 窗（`factor_window` 顺序）；格内三数 = `open_count · hit_rate · paired_delta_pp`；配色规则：同窗跨配置比较最高红、最低绿、其余蓝，Δ 低于裸算法基准标黄 ▲；`naive_baseline` 行**不参与红绿排名**；`leave_one_out` 行标记 `is_leave_one_out=true`；留一法移除后 Δ 升 ≥0.5pp 持续 30 天 = 结构红线（`warning=true`）。

#### 6.11.10 GET /api/v1/engine/shadow-review
- 调用方：**复盘页**「影子盘降级审查条（idle/ok/bad 三态）」（§9.6-30）。
- 请求参数：无。
- 响应 200 `data`：`ShadowAudit`（§5.29）。
- 错误：`E_IO`。
- 口径：`status=idle`（未启动）时 `hit_rate=null`，`message` 给"影子盘尚未启动…"长文；`abs(deviation_pp) >= 0.02` → `bad` 并红色降级条。

#### 6.11.11 GET /api/v1/factors/score-detail
- 调用方：**因子页**「因子行展开跑分表：每窗 lift / k_lift / 权重 / 独立触发日 / 准入度 / 得分 + 总分」（§9.4-14）。
- 请求参数：`factor_id`（string，必填）。
- 响应 200 `data`：`FactorScoreDetail`（§5.23）。
- 错误：`E_NOT_FOUND` / `E_IO`。
- 口径：每窗 `score = k_lift × weight × admission`，`total_score = Σ score`；`k_lift` 悬崖穷举（≥1.30→1.0 / ≥1.20→0.80 / ≥1.10→0.65 / ≥1.00→0.50 / <1.00→−0.80 / <0.84→−1.3）；`admission = min(1, independent_trigger_days / n_w)`；数据缺失字段为 null，UI 显示"—"（禁止估填）。

#### 6.11.12 GET /api/v1/factors/books/{book}
- 调用方：**因子页**「四本账本展开：用途 + 最近记录/示例条目」（§9.4-15）；引擎页可读 `shadow_signals`/`factor_arena`。
- 路径参数：`book` ∈ `factor_book`（§1.3 六本穷举）。
- 请求参数：`limit`（integer，默认 20）、`offset`（integer，默认 0）。
- 响应 200 `data`：`{ book, book_label, record_kind, schema_fields, records: object[], total, last_record_at }`；`records` 元素键与 `schema_fields` 一致（如采纳登记表含 `factor_id/role/death_condition/license/adopted_at`）。
- 错误：`E_NOT_FOUND`（未知 book）/ `E_IO`。
- 口径：只读，无编辑/删除；账本无记录时 `records=[]`、`total=0`，UI 显示"待写入"。

#### 6.11.13 GET /api/v1/factors/governance-cycle
- 调用方：**因子页**「治理周期卡（挖掘/评分/月榜/季复查/重训）」（§9.4-17）。
- 请求参数：无。
- 响应 200 `data`：`GovernanceCycle`（§5.30）。
- 错误：`E_IO`。
- 口径：`phases` 固定 5 项；`cadence` 文本穷举（周六/周日/每月 1 日/每季首月/每季）；月榜只产生提名、不直接变更生产。

#### 6.11.14 GET /api/v1/factors/dig-records
- 调用方：**因子页**「最近挖掘记录表（F1/F2/F3 判定）」（§9.4-18）。
- 请求参数：`limit`（integer，默认 20）。
- 响应 200 `data`：`{ records: DigRecord[], panel: {nomination_limit, cooldown_days, week_rule} }`（§5.31）。
- 错误：`E_IO`。
- 口径：`f1/f2/f3_result` 穷举 `dig_result`；前序未过则后续 `na`（UI 显示"—"）；`verdict` 穷举 `dig_verdict`。

#### 6.11.15 GET /api/v1/settings/holdings-data
- 调用方：**设置页**「持仓数据卡 + 两份 funds_data.json 不一致长文（估值≠净值的实证）」（§9.7-35）。
- 请求参数：无。
- 响应 200 `data`：`HoldingsDataSource`（§5.33）。
- 错误：`E_IO`（两份文件皆不可读时）；单份缺失不报错，`*_exists=false`。
- 口径：`readonly` 恒 true（**产品不改写源文件**）；`consistent=false` 时 `diff_fields` 给出差异字段，`diff_note` 解释旧文件会滞后数日。

---

### 7. UI 接口覆盖核对表

| UI 页面/组件 | 依赖接口 | 覆盖 |
|---|---|---|
| 持仓页四卡 | `/holdings`（summary）、`/runtime` | ✅ |
| 持仓页估值精度 | `/valuations/precision` | ✅ |
| 持仓页三窗口 | `/portfolio/forecast` | ✅ |
| 持仓页覆盖度 | `/holdings`（tier）、`/predictions` | ✅ |
| 持仓明细表 | `/holdings` | ✅ |
| 估值徽章 + trace | `/valuations/{code}` | ✅ |
| 未知态 | `/holdings`（`change_rate=null`） | ✅ |
| 分析页三窗口 + 参与明细 | `/portfolio/forecast`、`/predictions` | ✅ |
| 分析页 6 步链路 | `/predictions/{code}`（chain） | ✅ |
| 信号页时间线 | `/ledger` | ✅ |
| 信号页触发条件 | 静态文案（E1/E3，契约 §1.3 `gate`） | ✅ |
| 因子页四盘/账本/评分链/生命周期 | `/factors/*` | ✅ |
| 复盘页成绩/hero | `/review/scores` | ✅ |
| 复盘页逐笔对账 | `/review/reconciliation` | ✅ |
| 复盘页 CV 口径 | `/review/cv-config` | ✅ |
| 引擎页 HUD/台账/参数/六维/125 格 | `/engine/status`、`/ledger`、`/engine/frozen-params`、`/engine/inputs`、`/engine/ddsm` | ✅ |
| 设置页隐私/LLM/数据源/注册表/持仓/关于 | `/settings`、`/data-sources/health`、`/data-sources/probe`、`/engine/registry`、`/holdings/import`、`/about` | ✅ |
| 加/减仓/编辑/删除 | `/holdings` CRUD + `/transactions` | ✅ |
| 手动刷新估值/预测 | `/tasks`（POST + 轮询） | ✅ |
| Topbar 快照/陈旧/开口数 | `/runtime` | ✅ |
| 覆盖度四档 + 失效三类 | `/holdings/coverage` | ✅ v3 |
| 风险指标折叠区 | `/holdings/risk` | ✅ v3 |
| 信号空态四要素 + 触发门卡 | `/signals/state` | ✅ v3 |
| T+1 口径 + 三执行路径 | `/meta/definitions` | ✅ v3 |
| 信号时间线六步链 | `/ledger/chain` | ✅ v3 |
| 影子盘台账 + 连续记录进度 | `/ledger/shadow` | ✅ v3 |
| 125 格状态立方体（naive vs ddsm） | `/engine/ddsm/cube` | ✅ v3 |
| 训练状态卡 | `/engine/training-status` | ✅ v3 |
| 因子竞技场矩阵 | `/engine/arena` | ✅ v3 |
| 影子盘降级审查条 | `/engine/shadow-review` | ✅ v3 |
| 因子行展开跑分表 | `/factors/score-detail` | ✅ v3 |
| 单本账本展开 | `/factors/books/{book}` | ✅ v3 |
| 治理周期卡 | `/factors/governance-cycle` | ✅ v3 |
| 最近挖掘记录 F1/F2/F3 | `/factors/dig-records` | ✅ v3 |
| 设置页持仓数据卡 + 两份文件不一致 | `/settings/holdings-data` | ✅ v3 |
| 估值徽章精度（MAE/方向命中率/样本数/trace） | `/valuations/{code}`（`Valuation` v3 追加字段） | ✅ v3 |
| 引擎 HUD 六卡 | `/engine/status`（v3 追加字段） | ✅ v3 |
| 六维输入原值/z/档位/IC/复合 | `/engine/inputs`（v3 追加字段 + `crowd`） | ✅ v3 |
| 冻结参数表（门/方法/窗权重/牌照线） | `/engine/frozen-params`（v3 追加字段） | ✅ v3 |

#### 7.1 PROJECT_BRIEF §9 · 40 项特调组件 → 数据接口核对

> 依据 `docs/PROJECT_BRIEF.md §9`。**缺一即 G-FE-01 不通过**。本表证明"契约已为每一项提供完整数据支撑"。

| §9 项 | 组件 | 数据接口/对象 |
|---|---|---|
| 9.1-1 | 资产总览四卡 + 今日盈亏口径与覆盖度 | `/holdings`（§6.2.1）、`/holdings/summary` |
| 9.1-2 | 估值精度汇总条 `.vsum` | `/valuations/precision`（§6.3；v3 加 `mode_distribution` 见 §8） |
| 9.1-3 | 估值来源徽章五档 + 置信度配色 + trace/MAE/方向命中率/样本数 | `Valuation` §5.2（v3 追加 `dir_hit_rate`/`n_test`/`confidence_color_class`/`trace_text`） |
| 9.1-4 | 覆盖度四档 `.covbar` + 失效三类 | `/holdings/coverage`（§6.11.1 / §5.19） |
| 9.1-5 | 持仓明细表（分组/列显隐/T+2/建议/未知≠持平） | `/holdings`（§5.1） |
| 9.1-6 | 风险指标折叠区 | `/holdings/risk`（§6.11.2 / §5.20） |
| 9.2-7 | 信号空态四要素 | `/signals/state`（§6.11.3 / §5.21） |
| 9.2-8 | 触发门 E1/E3 卡 + E2/E4 剔除 | `/signals/state`（`gates`/`excluded_gates`） |
| 9.2-9 | 信号时间线 + 事件链 `.ev` | `/ledger` + `/ledger/chain`（§6.11.5 / §5.34） |
| 9.3-10 | T+1 口径 + 三执行路径 | `/meta/definitions`（§6.11.4 / §5.22） |
| 9.3-11 | 三窗口组合预测卡 + 加权三规则 | `/portfolio/forecast`（§5.7） |
| 9.3-12 | 参与预测持仓表 | `/predictions`（§5.4） |
| 9.3-13 | 推导链 `.chain` 六步 | `/predictions/{code}`（§6.4）+ `/ledger/chain`（§6.11.5） |
| 9.4-14 | 因子四盘 + 因子行 + 展开跑分表 | `/factors/pans`（§5.11/§5.12 v3 追加）+ `/factors/score-detail`（§6.11.11 / §5.23） |
| 9.4-15 | 四本账本 + 示例记录 | `/factors/books`（§5.13 v3 追加）+ `/factors/books/{book}`（§6.11.12） |
| 9.4-16 | 评分链长文（悬崖/bootstrap/四裁判） | `/factors/score-chain`（v3 追加 `bootstrap_percentiles`/`judges`/`floor_note`） |
| 9.4-17 | 治理周期卡 | `/factors/governance-cycle`（§6.11.13 / §5.30） |
| 9.4-18 | 最近挖掘记录 F1/F2/F3 | `/factors/dig-records`（§6.11.14 / §5.31） |
| 9.4-19 | 生命周期规则长文 + 来源 | `/factors/lifecycle`（§5.32，v3 追加 `license_lines`/`dual_exit`/`false_kill_guards`/`source`） |
| 9.5-20 | HUD 卡（影子盘/版本/训练资产/状态格覆盖/上次重训/数据新鲜度） | `/engine/status`（v3 追加字段） |
| 9.5-21 | 影子盘台账表 + 连续记录进度 + INSERT-ONLY 字段说明 | `/ledger/shadow`（§6.11.6 / §5.28） |
| 9.5-22 | 因子竞技场矩阵 | `/engine/arena`（§6.11.9 / §5.24） |
| 9.5-23 | 训练状态卡（125 格/样本/加噪/死路） | `/engine/training-status`（§6.11.8 / §5.26） |
| 9.5-24 | 冻结参数表 | `/engine/frozen-params`（§5.14 v3 追加） |
| 9.5-25 | 六维输入（三维+六维，原值/z/档位/IC/复合） | `/engine/inputs`（v3 增强 / §5.27） |
| 9.5-26 | 125 格状态立方体（naive vs DDSM + vr 层 + 对比卡） | `/engine/ddsm/cube`（§6.11.7 / §5.25） |
| 9.5-27 | 引擎注册表三态 | `/engine/registry`（§6.9） |
| 9.6-28 | 历史成绩 hero | `/review/scores`（`hero`） |
| 9.6-29 | 三窗口 vs 同期基线表（待填充显式留空） | `/review/scores`（§5.8） |
| 9.6-30 | 影子盘降级审查条 idle/ok/bad | `/engine/shadow-review`（§6.11.10 / §5.29） |
| 9.6-31 | 逐笔对账表 | `/review/reconciliation`（§5.10） |
| 9.7-32 | 隐私开关 | `/settings`（§5.16） |
| 9.7-33 | LLM 接口 + 三硬约束 + 温度 0 | `/settings`（§5.16） |
| 9.7-34 | 数据源健康表 | `/data-sources/health`（§5.17） |
| 9.7-35 | 持仓数据卡 + 两份 funds_data.json 不一致 | `/settings/holdings-data`（§6.11.15 / §5.33） |
| 9.7-36 | 关于卡 | `/about`（§6.10） |
| 9.8-37 | 录入/编辑/加减仓/删除 dialog + popover + toast | `/holdings` CRUD + `/transactions`（§6.2）；纯前端交互 |
| 9.8-38 | 注销 Service Worker | 纯前端（不涉契约） |
| 9.8-39 | 真实数据接入条 livebar | `/runtime` + `/data-sources/health`（§5.17/§5.18） |
| 9.8-40 | 四种状态（空/加载/错误/成功） | 全局 `StateBlock`（07 §4）；接口层三态见 A-06 |

**缺口声明**：`/holdings/import` 的 `merge` 语义（以 `code` 为准的字段合并规则）尚未逐字段冻结，登记为 CONCERN 候选（责任人：architect，期限：S3 前）；本期 UI 只用 `replace`。

### 8. v3 追加清单（只加不改，不变式核对）

> 本节是 v3 相对 v2 的**逐条追加台账**，供 `backend-dev` 实现（G-BE-02 逐字段核对）与 `dev-lead` 回归。
> **不变式**：v3 **未修改/未删除任何 v2 既有字段名**；所有变更均为"新增字段 / 新增接口 / 收紧为穷举枚举（不改名）"。

#### 8.1 对既有对象的追加（字段名 → 归属对象）

| 追加字段 | 归属对象 | 前端消费点 |
|---|---|---|
| `dir_hit_rate` / `n_test` / `accuracy_window_days` / `industry_baseline_mae_rate` / `confidence_label` / `confidence_color_class` / `trace_text` | `Valuation` §5.2 | 持仓/分析页 ValBadge 悬浮（9.1-3） |
| `created_at` / `record_seq` / `source_file` / `chain_available` | `LedgerEntry` §5.9 | 引擎页影子盘台账（9.5-21）/ 信号页（9.2-9） |
| `role_label` / `score`→`total_score` / `status`→枚举 / `license` / `license_label` / `lift_bars` / `independent_trigger_days` / `death_condition` / `note` / `ab_progress` | `FactorItem` §5.12 | 因子页因子行（9.4-14） |
| `rule_text` / `pan_status` / `flow_kind` / `updated_at` / `factor_cap` / `nomination_limit` | `FactorPan` §5.11 | 因子页四盘 rule（9.4-14） |
| `book_label` / `record_kind` / `schema_fields` | `FactorBook` §5.13 | 因子页四本账本（9.4-15） |
| `gate_e1` / `gate_e3` / `purge_gap` / `window_weights` / `window_min_days` / `license_lines` | `FrozenParams` §5.14 | 引擎页冻结参数表（9.5-24） |
| HUD 14 字段（影子盘/训练资产/状态格/重训/新鲜度） | `/engine/status` §6.9 | 引擎页 HUD（9.5-20） |
| `EngineInputItem` 增 `group/label/raw/raw_unit/ic_sign/signed_z/formula` + `crowd` | `/engine/inputs` §6.9 / §5.27 | 引擎页六维输入（9.5-25） |
| `training_summary` | `/engine/ddsm` §6.9 | 引擎页状态表（9.5-26 辅助） |
| `bootstrap_percentiles` / `judges` / `floor_note` / `rule_source` | `/factors/score-chain` §6.8 | 因子页评分链长文（9.4-16） |
| `license_lines` / `dual_exit` / `false_kill_guards` / `source` | `/factors/lifecycle` §6.8 | 因子页生命周期长文（9.4-19） |
| `mode_distribution` | `/valuations/precision` §6.3 | 持仓页估值精度汇总（9.1-2） |

#### 8.2 新增接口（39~53）

见 §4 总览与 §6.11 详述。全部只读 GET、无写端点、无新增错误码。

#### 8.3 新增枚举（19 个）

见 §1.3「v3 追加枚举」。全部穷举，无"等"。

#### 8.4 不改既有字段名（红线）

- `/valuations/precision` 的 `groups` 元素仍为 `{confidence, count, market_value, weight_ratio}`，v3 **只追加** `mode_distribution`，不改元素字段。
- `/engine/inputs` 元素仍保留 v2 的 `feature`/`level`/`z`，v3 只追加。
- `/engine/ddsm` 的 `cells` 仍保留 `{state,p,n,filled}`，v3 只追加 `training_summary`。
- `LedgerEntry` 仍保留 `written_at`，v3 新增 `created_at` 为同刻规范字段，二者恒等。


## 自验收

- [x] 契约覆盖 UI 所需全部接口：持仓 CRUD（2/4~9）、实时估值（10~12）、预测（13~14）、组合加权（15）、复盘（16~18）、台账（19~21）、因子（22~25）、任务（31~33）、设置（34~38）
- [x] 每个字段都有类型 + 单位 + 精度 + 口径说明（§1.2 全局 + §5 共享对象 + §6 端点特有）
- [x] 字段名全项目 `snake_case`，无驼峰混用
- [x] 所有枚举穷举列出（§1.3，共 41 个：v2 22 个 + v3 追加 19 个，无"等"）
- [x] 给出"估值≠净值"来源字段（`valuation.*` vs `nav.*`）与徽章口径（`valuation_mode` 唯一驱动）
- [x] `unknown` 口径明确：`change_rate=null`，禁 `+0.00%`
- [x] 台账 INSERT-ONLY、`(date,code)` 唯一、回填独立文件
- [x] 冻结参数不可经 API 修改（`POST /tasks` 校验）
- [x] 错误码穷举（10 个）
- [x] 未写实现代码（仅契约与 JSON 示例）
- [x] A-01：当日估值 INSERT-ONLY（`written_at`/`run_id`/`is_first_of_day`/`history`），快照降级为缓存
- [x] A-02：`market_value` 禁成本回退（`mv_source=null` + `fallback_value`/`total_value_with_fallback`/`covered_cost_amount`）
- [x] A-03：组合方向最小覆盖门槛（`min_coverage_ratio=0.30`/`min_open_count=3`）+ `direction_reason` + 0.52 口径标注
- [x] A-04：`validated`/`validation_status`/`formula_source` + T3 `p=null` + 未验证强制 gray
- [x] A-05：`veto_*_status` 三态 + `veto_data_missing` → abstain
- [x] A-06：引擎离线三态返回（快照/旧快照/无快照），禁 `empty` 承载故障
- [x] **v3**：状态立方体逐资产 125 格、naive 与 ddsm 两套 P、样本数 n、vr 层索引、空样本格显式表达（§5.25 / §6.11.7）
- [x] **v3**：六维输入含原值 + z-score + 档位 + IC 符号 + 复合 z + 是否否决（§5.27 / §6.9 `/engine/inputs`）
- [x] **v3**：因子治理含四盘状态、评分链（每窗 lift/k_lift/权重/独立触发日/准入度/得分/总分）、四本账本条目、治理周期、挖掘记录 F1/F2/F3、生命周期规则文本来源（§5.11~§5.13、§5.23、§5.30~§5.32、§6.11.11~§6.11.14）
- [x] **v3**：竞技场矩阵行=配置、列=六窗、格=开口数/命中率/配对 Δ/留一法/警示（§5.24 / §6.11.9）
- [x] **v3**：影子盘台账 `date/code/gate/p_up/ddsm_state/veto_crowd/veto_klow2/signal/t1_real/t3_real/t15_real/created_at` INSERT-ONLY + 连续记录进度（§5.28 / §6.11.6）
- [x] **v3**：估值置信度徽章 mode 五档 + confidence(high/mid/low/unknown) + mae + 方向命中率 + n_test + trace（§5.2 追加 / §6.3）
- [x] **v3**：单信号六步推导链可作数据返回（§5.34 `/ledger/chain` + v2 `/predictions/{code}`）
- [x] **v3**：40 项特调组件逐项映射到接口/对象（§7.1），缺一即 G-FE-01 不通过
- [x] **v3**：只加字段/接口，**未改任何既有字段名**；追加台账见 §8，全部字段 snake_case + 类型/单位/精度/口径，枚举穷举（§1.3）
- [x] **v3**：所有新增字段/接口均标注前端消费点（页/组件）；未写代码、未读 FundLens/ZCode、未改 `runtime/**`、未派发子任务

## 下游交接

- **主消费方**：`frontend-dev` / `backend-dev`（**并行**，双方严格按契约实现；不得单方面改字段名）。
  - frontend-dev：所有请求经 `api.js`；`ValBadge` 读 `valuation_mode`；`UnknownCell` 阻断 `+0.00%`；数值一律经 `format.js` 转换（§1.2）。新增：A-02 `fallback_value` **分列**展示；A-03 未达门槛不显示"涨"；A-04 未验证窗口不用"涨"色；A-06 引擎离线走陈旧态/错误态（**不得** empty）。**v3**：按 §7.1 逐项落地 40 项特调组件；立方体空样本格渲染斜纹"无样本"（禁 0/50%）；竞技场配色只用后端 `arena_color`；影子盘台账用 `created_at`；六维输入用 `raw/z/level/ic_sign/composite_z` 渲染 z-bar；推导链用 `/ledger/chain`。
  - backend-dev：逐字段对齐（G-BE-02 红线）；`unknown` 必须 `null`；台账/冻结参数红线不可破。新增：A-01 写 `valuation_history.jsonl`（快照仅缓存）；A-02 不给 `market_value` 回退；A-05 否决层缺失即 `abstain`；**v3 按 §8「v3 追加清单」实现**：立方体只读资产返回 naive/ddsm 双 P（naive 用未加噪真实档位）；`LedgerEntry.created_at` INSERT-ONLY 且与 `written_at` 恒等；评分链 `k_lift/权重/准入度/得分` 数值逐窗计算；竞技场 `factor_arena.jsonl` 驱动（留一法行 + 警示标记）。
- **次消费方**：`qa`。需其执行：按 §1.2 口径与 §7 覆盖表建 P0 用例，重点负向断言 G2/G3/G4/G5/G8/G10（对照 PRD §3）。**v3 追加负向用例**：空样本格不得渲染为 0/50%；影子盘台账无编辑/删除端点（G10）；`created_at` 写入后不可改；评分链缺失字段为 null 而非 0；竞技场裸算法基准行不着红绿。
- **残留风险**（每项含责任人与期限）：
  1. **三维 `[r2,om,vr]` 与六维特征公式未与研究笔记复核** → 若改，契约版本 +1 并通知双边（责任人：architect，期限：S3 前）。
  2. **`/holdings/import` 的 `merge` 逐字段规则未冻结** → 本期只用 `replace`（责任人：architect，期限：S3 前）。
  3. **T+3/T+15 基线口径未知** → `baseline_status=pending`、`delta_pp=null`，界面"待填充"（责任人：architect，期限：S3 前）。
  4. **`industry_baseline_mae_rate=0.008` 无来源统计口径** → 后端给出窗口/样本前，UI 文案降级为"误差参考"（责任人：architect + backend-dev，期限：S3）。
  5. **`holdout_start_date` 未定** → `/review/cv-config` 先返回 null（责任人：architect + dev-lead，期限：S5 绑定排期）。
  6. **T+3/T+15 尚未过走前 CV + placebo** → `validation_status=pending_cv`、`direction=gray`、`provisional_*` 仅引擎页可见；过检后由 architect 升 `validated` 并版本 +1（责任人：architect，期限：S3 回测产出后）。
  7. **`valuation_history.jsonl` 增速** → 每次刷新 22 行、日归档；若按分钟级刷新需评估体积上限并加归档策略（责任人：backend-dev，期限：S3）。
  8. **v3 状态立方体走前 Δ 数值来源**（naive −3.9%、ddsm +1.6~5.5pp）来自 legacy v2 壳演示，**非本产品回测产出** → 后端须回测产出后回填，未产出前 `walk_forward_delta_*` 返回 null 且 UI 标注"待复现"（责任人：architect + backend-dev，期限：S3）。
  9. **v3 因子治理/竞技场数值**（评分链、bootstrap 分位、牌照线、A/B 结果）来自 legacy v2 壳展示常量与示例 → 后端 `factor_arena.jsonl`/`scan_history.jsonl` 产出前，相关接口返回空集或 null，UI 显示"待写入/—"，**禁止用 legacy 示例数字冒充实测**（责任人：architect + backend-dev，期限：S3）。
  10. **v3 `created_at` 与 v2 `written_at` 双字段并存** → 二者恒等；后续若清理需走版本 +1，本期保留双写兼容（责任人：architect，期限：S4 前评估）。
- **契约变更纪律**：本文件 `approved` 后任何字段变更必须版本号 +1 并 `say` 通知 frontend-dev + backend-dev（角色契约硬性约束 3）。
- **未覆盖**：算法实现细节（`08-backend-arch`）、前端组件树（`07-frontend-arch`）。
