---
artifact: 09-api-contract
owner: architect
version: v2
status: approved
supersedes: v1
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

> 上表 38 行含内部接口（20/21）；面向 UI 的接口共 36 个。下文按域展开。

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

#### 5.12 `FactorItem`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `factor_id` | string | — | — | 因子唯一 id |
| `name` | string | — | — | 因子名 |
| `role` | enum `factor_role` | — | — | 当前角色 |
| `score` | number/null | 分 | 4 位 | 六窗加权总分；缺失 null |
| `status` | string | — | — | 状态（如 `active`/`probation`/`cooling`） |
| `added_at` | string(date) | — | — | 入盘日 |

#### 5.13 `FactorBook`

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `book` | enum `factor_book` | — | — | 账本标识 |
| `filename` | string | — | — | 落盘文件名 |
| `purpose` | string | — | — | 用途 |
| `record_count` | integer | 条 | 整数 | 记录数 |
| `last_record_at` | string(timestamp)/null | — | 秒 | 最近记录时间 |
| `sample` | array[object]/null | — | — | 最近 1~3 条示例（只读） |

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
| `window_weights` | array[object] | — | — | 六窗 `{window_label, weight}`，权重穷举 `8/22/15/10/30/15`（合计 100） |
| `formula_text` | string | — | — | 评分链可读说明 |

- 错误：`E_IO`。

##### GET /api/v1/factors/lifecycle
- 响应 200 `data`：`{ "admission_rules": [string], "retire_rules": [string], "revive_rules": [string] }`，文本穷举，基于 PRD F-14。
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

- 错误：`E_IO`（返回 `status=offline` 且 HTTP 200，前端据此显示离线态）。

##### GET /api/v1/engine/inputs
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `ddsm_3d` | array[object] | — | — | 每项 `{feature, level, z}`；`feature` ∈ `r2`/`om`/`vr`，`level` ∈ {0..4}，`z` 3 位 |
| `crowd_6d` | array[object] | — | — | 每项 `{feature, z}`；`feature` ∈ `mom5`/`vr`/`dev`/`vpcorr`/`volat`/`skew`（穷举 6 项） |
| `train_as_of` | string(date)/null | — | — | 训练段截止日 |
| `snapshot_at` | string(timestamp)/null | — | 秒 | 快照时间 |

- 错误：`E_IO`（无快照 → 空数组 + `snapshot_at=null`）。

##### GET /api/v1/engine/ddsm
- 响应 200 `data`：

| 字段 | 类型 | 单位 | 精度 | 口径说明 |
|---|---|---|---|---|
| `dims` | array[string] | — | — | 固定 `["r2","om","vr"]` |
| `bins_per_dim` | integer | 档 | 整数 | 固定 5 |
| `cells` | array[object] | — | — | 125 项 `{state:[3], p:number|null, n:integer, filled:boolean}` |
| `noise` | object | — | — | `{k_noise, p_perturb}`（同 §5.14） |
| `legend` | array[object] | — | — | 热力色带 `{min_p, max_p, label}`，穷举：`[0,0.45) P<0.45 看跌` / `[0.45,0.52) 中性` / `[0.52,0.58) 弱看涨` / `[0.58,1] 强看涨` |

- 错误：`E_IO`。

##### GET /api/v1/engine/frozen-params
- 响应 200 `data`：`FrozenParams`（§5.14）。
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

**缺口声明**：`/holdings/import` 的 `merge` 语义（以 `code` 为准的字段合并规则）尚未逐字段冻结，登记为 CONCERN 候选（责任人：architect，期限：S3 前）；本期 UI 只用 `replace`。

## 自验收

- [x] 契约覆盖 UI 所需全部接口：持仓 CRUD（2/4~9）、实时估值（10~12）、预测（13~14）、组合加权（15）、复盘（16~18）、台账（19~21）、因子（22~25）、任务（31~33）、设置（34~38）
- [x] 每个字段都有类型 + 单位 + 精度 + 口径说明（§1.2 全局 + §5 共享对象 + §6 端点特有）
- [x] 字段名全项目 `snake_case`，无驼峰混用
- [x] 所有枚举穷举列出（§1.3，22 个枚举，无"等"）
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

## 下游交接

- **主消费方**：`frontend-dev` / `backend-dev`（**并行**，双方严格按契约实现；不得单方面改字段名）。
  - frontend-dev：所有请求经 `api.js`；`ValBadge` 读 `valuation_mode`；`UnknownCell` 阻断 `+0.00%`；数值一律经 `format.js` 转换（§1.2）。新增：A-02 `fallback_value` **分列**展示；A-03 未达门槛不显示"涨"；A-04 未验证窗口不用"涨"色；A-06 引擎离线走陈旧态/错误态（**不得** empty）。
  - backend-dev：逐字段对齐（G-BE-02 红线）；`unknown` 必须 `null`；台账/冻结参数红线不可破。新增：A-01 写 `valuation_history.jsonl`（快照仅缓存）；A-02 不给 `market_value` 回退；A-05 否决层缺失即 `abstain`。
- **次消费方**：`qa`。需其执行：按 §1.2 口径与 §7 覆盖表建 P0 用例，重点负向断言 G2/G3/G4/G5/G8/G10（对照 PRD §3）。
- **残留风险**（每项含责任人与期限）：
  1. **三维 `[r2,om,vr]` 与六维特征公式未与研究笔记复核** → 若改，契约版本 +1 并通知双边（责任人：architect，期限：S3 前）。
  2. **`/holdings/import` 的 `merge` 逐字段规则未冻结** → 本期只用 `replace`（责任人：architect，期限：S3 前）。
  3. **T+3/T+15 基线口径未知** → `baseline_status=pending`、`delta_pp=null`，界面"待填充"（责任人：architect，期限：S3 前）。
  4. **`industry_baseline_mae_rate=0.008` 无来源统计口径** → 后端给出窗口/样本前，UI 文案降级为"误差参考"（责任人：architect + backend-dev，期限：S3）。
  5. **`holdout_start_date` 未定** → `/review/cv-config` 先返回 null（责任人：architect + dev-lead，期限：S5 绑定排期）。
  6. **T+3/T+15 尚未过走前 CV + placebo** → `validation_status=pending_cv`、`direction=gray`、`provisional_*` 仅引擎页可见；过检后由 architect 升 `validated` 并版本 +1（责任人：architect，期限：S3 回测产出后）。
  7. **`valuation_history.jsonl` 增速** → 每次刷新 22 行、日归档；若按分钟级刷新需评估体积上限并加归档策略（责任人：backend-dev，期限：S3）。
- **契约变更纪律**：本文件 `approved` 后任何字段变更必须版本号 +1 并 `say` 通知 frontend-dev + backend-dev（角色契约硬性约束 3）。
- **未覆盖**：算法实现细节（`08-backend-arch`）、前端组件树（`07-frontend-arch`）。
