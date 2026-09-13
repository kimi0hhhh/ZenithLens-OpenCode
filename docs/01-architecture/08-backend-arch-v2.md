---
artifact: 08-backend-arch
owner: architect
version: v2
status: approved
supersedes: v1
created: 2026-09-12
reviewers: [backend-dev, dev-lead, product-manager]
gate: G-AR-04
---

# 后端架构 · 极境 ZenithLens

> 上游：`docs/PROJECT_BRIEF.md` §5.1/§5.2/§5.3、`docs/00-charter/02-prd.md` F-02/F-06/F-09/F-10、`docs/01-architecture/06-system-arch.md`。
> 硬约束：**纯 Python 标准库**、Python 3.8+、可离线复现、单次预测 CPU 分钟级；本文只写伪代码与口径，不写可运行代码。
> 本文落地两件命脉：**预测核心链（E1/E3→DDSM→双否决→出口 0.52）** 与 **估值五档降级链（official/intraday/holdings/proxy/unknown）**。

## 摘要

1. 后端分 4 层：`adapters/`（唯一 I/O 与网络）→ `core/`（纯逻辑：holdings/valuation/gates/ddsm/veto/portfolio/review/ledger/factors/tasks）→ `server/`（路由 + 信封）→ 存储（JSON/JSONL）。
2. **预测核心链冻结**：E1 `low[t]>high[t-1]` / E3 `ret<-2% 且 vr<0.8`（E2/E4 禁用、禁止 OR 合并）→ 三维 `[r2,om,vr]` 各 5 档 =125 格、加噪 `K=4`/`p=0.25`、收缩 `P=(n_up+10×训练涨率)/(n+10)`、`MIN_N=15` → 双否决（拥挤度六维 40% / KLOW2 40%）→ 出口 `P>0.52` 单向做多，**永不做空**。
3. **估值五档降级链冻结**：`official→intraday→holdings→proxy→unknown`，命中即停并记录 `trace`；`unknown` 必须 `change_rate=null`；官方净值回填只写 `nav.*`，不改当日已入账的 `valuation_mode`。
4. 三窗口定式：T+1 完整链、T+3 仅触发做多、T+15 门+DDSM；方法论走前时序 CV（禁随机切分）、purge gap=H+2、placebo≥2pp、冻结 holdout 60 日。
5. 台账 INSERT-ONLY：`signals.jsonl` 只追加；到期回填写独立 `backfill.jsonl`（不改原行），读取时按 `(date, code)` 合并。
6. **v2 裁定（G-AR-06）**：当日估值 **INSERT-ONLY**（`valuation_history.jsonl` 审计源，`valuation-YYYYMMDD.json` 仅缓存，A-01）；`market_value` 不回退成本（未知行 `null` + `fallback_value`，A-02）；组合方向加最小覆盖门槛（0.30/3，A-03）；T+3/T+15 `p` 口径定死且未验证不出方向（T3 `p=null`，A-04）；否决层缺失 → `abstain`（A-05）；引擎离线返回态区分快照/旧快照/无快照（A-06）。

## 正文

### 1. 目录结构与模块

```
core/
  __init__.py
  models.py            # 数据类（Holding/Bar/Nav/ValResult/Prediction/LedgerEntry...）
  holdings.py          # 持仓读写、导入、加/减仓、校验
  valuation.py         # ★ 五档降级链
  gates.py             # ★ E1/E3 触发门
  features.py          # ★ 三维 + 六维特征计算（含分位断点、IC 符号）
  ddsm.py              # ★ 125 格状态模型 + 加噪 + 收缩
  veto.py              # ★ 双否决（拥挤度/KLOW2）
  predict.py           # ★ 串链：gate→ddsm→veto→exit；三窗口
  portfolio.py         # ★ 三窗口组合加权
  review.py            # 成绩 vs 基线、走前 CV、Δ
  ledger.py            # INSERT-ONLY 追加 + backfill 合并
  factors.py           # 四盘/账本/评分链/生命周期
  tasks.py             # 长任务登记与进度
  errors.py            # 错误码常量
core/adapters/
  http_client.py       # stdlib urllib 封装（超时/重试/重定向）
  tencent_kline.py     # 腾讯日K
  tencent_rt.py        # 腾讯实时
  eastmoney.py         # 天天基金（估算/官方净值/重仓）
  sina_rt.py           # 新浪实时
  files.py             # 原子写、jsonl 追加、文件锁
  clock.py             # 交易日/时区（Asia/Shanghai）
server/
  http_server.py       # ThreadingHTTPServer + 路由表
  router.py            # path → handler
  handlers/*.py        # 按域分：holdings/valuation/predict/portfolio/review/ledger/factors/tasks/settings/engine
  envelope.py          # 统一信封与错误码映射
```

依赖方向：`server → core → adapters → (网络/文件)`；`core` 纯逻辑不 import `server`；测试可把 adapters 换成内存假实现。

### 2. 数据模型（字段口径以 09 契约为准）

| 模型 | 关键字段 | 来源 |
|---|---|---|
| `Holding` | `code, name, group, tier, shares, cost_amount, avg_cost, confirm_days, proxy_code, proxy_name, nav` | `data/holdings.json` |
| `Bar` | `date, open, high, low, close, volume` | `data/cache/bars/<code>.json` |
| `NavPoint` | `date, nav` | `data/cache/nav/<code>.json` |
| `ValResult` | `code, valuation_mode, change_rate, estimated_nav, source_label, confidence, mae, nav_date, trace[], as_of` | `core/valuation.py` |
| `Prediction` | `code, tier, gate, p_up, ddsm_state[3], veto_crowd, veto_klow2, signal, windows{T1,T3,T15}` | `core/predict.py` |
| `PortfolioForecast` | `window, weighted_p, coverage_ratio, coverage_value, open_count, open_value, excluded_ratio, as_of` | `core/portfolio.py` |
| `LedgerEntry` | `date, code, gate, p_up, ddsm_state, veto_crowd, veto_klow2, signal, tier, market_value, cost_est, written_at` | `core/ledger.py` |
| `BackfillEntry` | `date, code, t1_real, t3_real, t15_real, backfilled_at` | `core/ledger.py` |

### 3. 估值五档降级链（命脉之一）

#### 3.1 取数顺序（命中即停，记录 trace）

```
value_fund(holding, as_of_date):
  trace = []
  # 档1 official：官方当日净值已公布
  nav_d = eastmoney.official_nav(code)                  # 返回 {date, nav}
  nav_prev = nav_history.before(nav_d.date)
  trace.append({mode:"official", tried:true, hit: nav_d.date == as_of_date})
  if nav_d.date == as_of_date:
      return ValResult(mode="official",
                       change_rate = nav_d.nav/nav_prev.nav - 1,
                       estimated_nav = nav_d.nav,
                       nav_date = nav_d.date, trace, confidence=conf_of("official", code))

  # 档2 intraday：行情源盘中估算净值
  est = eastmoney.intraday_estimate(code) or tencent.estimate(code)
  trace.append({mode:"intraday", tried:true, hit: est is not None})
  if est is not None:
      return ValResult(mode="intraday", change_rate=est.change_rate, ...)

  # 档3 holdings：前十大重仓当日涨跌加权
  hold = eastmoney.top_holdings(code)                   # 带 fetched_at，30 天缓存
  trace.append({mode:"holdings", tried:true, hit: hold is not None})
  if hold is not None:
      wsum = Σ(weight_i × day_change_i) / Σ(weight_i)
      return ValResult(mode="holdings", change_rate=wsum, ...)

  # 档4 proxy：代理 ETF 当日涨跌 × 最新官方净值
  px = proxy_map.get(code)
  trace.append({mode:"proxy", tried: px is not None, hit: px is not None and bar_ok(px)})
  if px is not None and bar_ok(px):
      etf_ret = day_change(px, as_of_date)
      return ValResult(mode="proxy", change_rate=etf_ret,
                       estimated_nav = nav_prev.nav * (1+etf_ret), ...)

  # 档5 unknown：只标净值截止日，不冒充今日
  return ValResult(mode="unknown", change_rate=None, estimated_nav=None,
                   nav_date = nav_prev.date, confidence="unknown", trace)
```

#### 3.2 硬规则

- **原子性**：一次 `value_fund` 要么返回一个确定 mode，要么返回 `unknown`；**同一基金同日对外展示只允许一个 mode**（取最新入账记录），但入账历史可多条。
- **当日 INSERT-ONLY（A-01）**：每次 `value_fund` 产出的估值记录**追加**写入 `data/snapshot/valuation_history.jsonl`（含 `date/code/valuation_mode/change_rate/estimated_nav/trace/written_at/run_id/is_first_of_day`）；`data/snapshot/valuation-YYYYMMDD.json` 是**可重建缓存**（可整文件覆盖），不得作为审计依据。当日**首次**入账记录的 `mode`/`trace` 永久保留，后续刷新与官方回填只追加、不覆盖。读取默认取 `(date, code)` 最新一条，徽章可回溯全部历史。
- **不降级替代**：代理缺失时**宁可 unknown**，不得用其他代理/其他基金顶替（PRD F-02 异常）。
- **trace 穷举**：`trace` 按尝试顺序列出全部档位与 hit/miss，供前端展示真实降级链路。
- **置信度**：`confidence` 由该 mode 的历史 MAE 对照行业基准 0.80% 得到：`mae ≤ 0.8`→high，`0.8 < mae ≤ 1.2`→mid，`mae > 1.2`→low，`unknown`→unknown（阈值冻结点，来源见残留风险）。
- **估值 ≠ 净值**：`ValResult.change_rate/estimated_nav` 是"今日预估"；官方已公布值存 `NavPoint`，经 `GET /holdings` 以 `nav.official_nav / nav.official_nav_date / nav.official_change_rate` 独立字段返回。**官方回填不改当日估值 mode**（写入 `nav.*` 与快照分离）。
- **超时阈值**：单源请求 5s 超时、最多重试 1 次；五档总预算 20s，超出即 unknown 并对该源记一次失败（供数据源健康）。

### 4. 预测核心链（命脉之二）

#### 4.1 特征定义（★ 本期冻结，须与研究笔记复核）

**DDSM 三维 `[r2, om, vr]`：**

| 特征 | 定义（冻结） | 单位/范围 |
|---|---|---|
| `r2` | 近 `L=5` 个交易日对数收益对时间做线性回归的 R²（趋势线性度） | [0,1] |
| `om` | 隔夜动量 `open[t]/close[t-1] − 1` | 小数 |
| `vr` | 量比 = `volume[t] / mean(volume[t-20..t-1])` | 倍数 |

**拥挤度六维 `[mom5, vr, dev, vpcorr, volat, skew]`：**

| 特征 | 定义（冻结） |
|---|---|
| `mom5` | 5 日累计收益 `close[t]/close[t-5] − 1` |
| `vr` | 同 DDSM 的量比 |
| `dev` | 乖离率 `close[t]/MA20(close) − 1` |
| `vpcorr` | 近 20 日 `return` 与 `volume_change` 的相关系数 |
| `volat` | 近 20 日日收益标准差 |
| `skew` | 近 20 日日收益偏度 |

> 每条均为"本期冻结定义"，来源为 Brief §5.1 特征名 + 架构裁定。若研究笔记口径不同 → `09-api-contract` 版本 +1 并通知前后端（残留风险 1）。

#### 4.2 触发门（仅 E1/E3）

```
gate_of(bar, prev, vr):
  ret = bar.close/prev.close - 1
  if bar.low > prev.high:            return "E1"      # 跳空
  if ret < -0.02 and vr < 0.8:       return "E3"      # 无量急跌
  return None
```

- **E2/E4 不实现**（已证伪）；**禁止 OR 合并 E1/E3 之外的任何条件**。
- 门不命中 → 不进入 DDSM，`signal=gray`，注明原因（数据不足/未触发）。

#### 4.3 DDSM（三维五档 = 125 格）

```
# 训练段统计（只允许用训练段，禁穿越）
bounds[d][k] = 训练段该维的 20/40/60/80 分位断点（d∈{r2,om,vr}，k=0..4）
cell(bar) = [ bin(r2), bin(om), bin(vr) ]          # 每维 5 档 → 125 格

# 训练：加噪 K=4，每维以 p=0.25 概率 ±1 档（加噪副本只进训练计数）
for sample in train:
    for k in 1..K:                                  # K=4 个加噪副本
        for d in {r2,om,vr}:
            if rand() < 0.25: cell_d = clamp(cell_d + choice(-1,+1), 0, 4)
        add train_cell_noised → label(up = close[next_H] > close[t])

# 出值：用未加噪的真实档位 real_cell；收缩到训练段全局涨率
real_cell = cell(bar)                               # 真实档位，不加噪
n      = obs[real_cell].count
n_up   = obs[real_cell].up_count
train_rate = 训练段整体涨率
if n >= MIN_N(15):
    P = (n_up + SHRINK(10) × train_rate) / (n + SHRINK(10))
else:
    P = train_rate                                  # 样本不足 → 向全局收缩
```

- **加噪只进训练（A-05 钉死）**：`add cell` 的 K=4 加噪副本**仅**用于训练段计数；出值 `obs[target_cell]` 与 `p_up` 的 target 一律为**未加噪的真实档位**，`ddsm_state` 也返回真实档位三元组。伪代码里两者不得混用；实现须分两个变量名（`train_cell_noised` vs `real_cell`）。
- 参数 `K=4 / p=0.25 / MIN_N=15 / SHRINK=10` **冻结**，改动须重走六关（引擎页标注）。

#### 4.4 双否决

```
# ① 拥挤度：六维各自按训练段 IC 符号等权复合 z
z_d    = (x_d - mean_train_d) / std_train_d
sign_d = sign(IC_d)          # IC = 该维与 forward return 的训练段相关，取符号
crowd  = mean(z_d × sign_d for d in six_dims)
if 六维任一训练段统计缺失:                        # 训练段不足/均值方差缺失（A-05）
    veto_crowd_status = "missing"
elif crowd >= quantile_train(crowd, 0.60):       # 处训练段最拥挤 40%
    veto_crowd = True;  veto_crowd_status = "veto"
else:
    veto_crowd_status = "pass"

# ② KLOW2：下影线占振幅比，最不利 40% 否决
if high == low:                                  # 一字板等 → status=missing（A-05）
    veto_klow2_status = "missing"                # 不作 pass，不记 True
else:
    klow2 = (min(open,close) - low) / (high - low)
    veto_klow2_status = "veto" if klow2 <= quantile_train(klow2, 0.40) else "pass"
# 拥挤度同理：训练段不足/均值方差缺失 → veto_crowd_status = "missing"
```

- **任一否决亮灯** → `signal=abstain`（弃权），并在链路第③/④步展示亮灯。
- **任一否决层 `status=missing` → 也不得放行（A-05）**：`signal=abstain`、`reason=veto_data_missing`，链路该步 `status=missing`（禁止记 `off`/通过）。这是"未知≠持平"在否决层的落地：读不到就弃权，不在最该保守处乐观。
- 分位断点、IC 符号、均值方差**只用训练段**（防穿越）。

#### 4.5 出口与多窗口定式

```
if veto_crowd_status == "missing" or veto_klow2_status == "missing":
                                signal = "abstain"; reason = "veto_data_missing"
elif veto_crowd or veto_klow2:  signal = "abstain"
elif P > 0.5 + BAND(0.02):      signal = "up"       # 单向做多
else:                           signal = "gray"
# 永远不存在 "down"/做空 分支
```

| 窗口 | 定式 | 来源 | `p` 口径（A-04 定死） | `direction` 生产规则 |
|---|---|---|---|---|
| T+1 | 门 + DDSM + 双否决 | `brief_5.1`（`validation_status=brief_mandated`） | DDSM 收缩 P | 出口成立即 `up`（Brief 授权，不受 `validated` 约束） |
| T+3 | 仅触发做多 | `arch_baseline_v1`（Brief §5.1 未定义，`pending_cv`） | **`p = null`**（`gate_only` 无概率模型，禁止后端自造） | 未验证 → 生产 `direction=gray`；`provisional_direction=up if gate`（仅引擎页观察） |
| T+15 | 门 + DDSM | `arch_baseline_v1`（同上，`pending_cv`） | DDSM 收缩 P，标签 `close[t+15]>close[t]` | 未验证 → 生产 `direction=gray`；`provisional_*` 仅供观察 |

- 标签定义：`up = 1 若 close[T+H] > close[T]`（H=1/3/15）。
- `p_up` 为 T+1 的收缩概率；T+3/T+15 的 `p` 严格按上表，**未验证窗口不得进组合 `weighted_p`**（T3 无 p，T15 的 p 仅 `provisional_p`）。
- **验证升格**：T+3/T+15 各自定式过走前 CV 且 placebo Δ≥2pp 后，由 architect 将 `validation_status` 升为 `validated`、`validated=true`，契约版本 +1 并通知双边；未升格前引擎页只展示"未验证/观察"。

#### 4.6 方法论（任何新结论必过）

- 走前时序 CV，**禁随机切分**；purge gap = `H+2`。
- placebo 检验 Δ ≥ 2pp；冻结 holdout 60 日**禁调参**。
- 基线 = `max(恒涨率, 恒跌率)`；成绩主指标 = `delta = hit_rate − baseline`。
- 台账 INSERT-ONLY；结果可复现（固定随机种子，种子写入快照）。

### 5. 组合三窗口加权（命脉之三）

```
forecast(window):
  pool = [h for h in holdings if h.tier in ("A","B")
          and pred[h].window[window].open and pred[h].window[window].p is not None]
  # 规则①：只算开口且该窗口有概率 p 的仓位；灰从分子分母同剔
  # 规则②：C/D 档不参与
  # 规则③：market_value 为 null 的未知行不进分母（A-02）
  w_i   = market_value(h_i)                          # 市值权重
  weighted_p      = Σ(w_i × p_i) / Σ(w_i)             # 无合格开口 → null
  coverage_value  = Σ(w_i)
  total_value     = Σ(market_value(h) for h if market_value is not None)
  coverage_ratio  = coverage_value / total_value
  excluded_ratio  = 1 - coverage_ratio                 # "其余 X% 不表态"
  # A-03 组合方向门槛（冻结常量，硬约束）
  threshold_met   = coverage_ratio >= 0.30 and open_count >= 3
  direction       = "up" if weighted_p > 0.52 and threshold_met and window_validated
                    else "gray"
```

- 无任何开口/该窗口无概率 → `weighted_p=null, open_count=0`，界面"今日无开口"或"该窗口无概率"。
- **覆盖门槛（A-03）**：`min_coverage_ratio=0.30`、`min_open_count=3` 为冻结常量（NOT API 参数，防止被调松）；未达门槛 `direction=gray` + `direction_reason=insufficient_coverage`，文案"覆盖不足，不构成组合结论"。`weighted_p` 仍照常返回供透明查看。
- 覆盖 < 100% 时契约必返 `excluded_ratio`，前端显式写"其余 X% 不表态"。
- 灰仓位**不得**以 0.5 计入（PRD G8）。

### 6. 台账与回填

```
write_signal(pred):                       # 收盘时点
  with file_lock("ledger"):
      if exists((date, code)): return E_CONFLICT       # 同日同 code 拒绝重复
      append_jsonl("data/ledger/signals.jsonl", entry)

backfill_due(today):                       # 启动时 + 每日收盘后
  for e in signals where not fully_backfilled(e):
      if today >= e.date + H:
          append_jsonl("data/ledger/backfill.jsonl",
                       {date:e.date, code:e.code, t{H}_real: actual_return(e, H)})
# 读取：signals LEFT JOIN backfill ON (date, code)；不改原行
```

- 原文件 `signals.jsonl` **只增不改**；回填写独立文件，满足 INSERT-ONLY 与可追溯。
- 回填只写 `t*_real`，`signal/gate/p_up/...` 保持写入时值。
- 唯一性：(date, code) 不可重复。

### 7. 错误码与日志

- 错误码集中在 `core/errors.py`（枚举见 `09-api-contract §3`）：`E_IO / E_PARSE / E_SOURCE_TIMEOUT / E_ENGINE_OFFLINE / E_VALIDATION / E_NOT_FOUND / E_CONFLICT / E_PORT / E_VERSION / E_UNKNOWN`。
- 服务端日志：`logging` 标准库，输出到 `data/logs/server-YYYYMMDD.log`；**不得**记录 API Key、持仓具体金额（隐私）。
- 外部源调用记录：源名 / URL（去参）/ 耗时 / 结果 / 失败计数 → 供数据源健康。
- 随机种子、参数集、数据 `as_of` 写入预测快照，保证可复现。

### 8. 确定性与零依赖

- 只用标准库：`http.server, json, urllib.request, os, sys, math, statistics, datetime, logging, threading, random, hashlib`。
- 所有随机加噪使用固定种子（存快照）；同输入 + 同种子 → 同输出。
- 网络失败不得导致进程崩溃：适配层统一捕获并转 error 结果。

## 自验收

- [x] 后端架构落地 Brief §5.1 核心逻辑：E1/E3 门 → DDSM（[r2,om,vr]/5 档/K=4/p=0.25/MIN_N=15/收缩 10）→ 双否决（拥挤度六维 40% / KLOW2 40%）→ 出口 P>0.52
- [x] 估值五档降级链 official/intraday/holdings/proxy/unknown 完整落地，unknown 必为 null
- [x] 估值≠净值字段分离，官方回填不改当日估值 mode
- [x] 三窗口定式、方法论（走前 CV/purge=H+2/holdout/placebo）写明
- [x] 台账 INSERT-ONLY + 独立回填文件方案
- [x] 组合加权三规则（只开口/C-D 排除/覆盖占比）伪代码化
- [x] 目录/模块/数据模型/错误码/日志/零依赖口径齐全
- [x] 未写可运行代码（仅伪代码）
- [x] A-01：估值链路产出追加写 `valuation_history.jsonl`（INSERT-ONLY），快照仅为可重建缓存
- [x] A-02：组合/汇总口径中 `market_value` 不落成本回退，未知行内存 `fallback_value`
- [x] A-03：组合方向覆盖门槛 0.30/3 写进伪代码，未达门槛强制 gray
- [x] A-04：T+3 `p=null`、T+15 `p`=DDSM(H=15)；未验证窗口 `direction=gray` + `provisional_*`
- [x] A-05：KLOW2/拥挤度 `missing` → `abstain`；加噪只进训练、出值用真实档位
- [x] A-06：`/predictions`、`/portfolio/forecast` 三态返回（快照/旧快照/无快照）在 handler 层落地

## 下游交接

- **主消费方**：`backend-dev`。需其执行：按 `core/` 模块落实现，预测链参数与估值五档**逐字对齐**本文件；接口字段严格对齐 `09-api-contract`（G-BE-02 红线：字段名不一致 FAIL）。
- **次消费方**：`dev-lead`。需其执行：G-BE-01 冒烟（起服 + 一条持仓估值 + 一条预测）、G-BE-02 逐字段核对。
- **残留风险**：
  1. **三维/六维特征公式为架构冻结定义，尚未与研究笔记复核** → 若不一致须改契约（版本 +1）并通知前后端（责任人：architect + backend-dev，期限：S3 前）。
  2. **T+3/T+15 基线口径未知** → 复盘页先"待填充"，不得填估计值（责任人：architect，期限：S3 前）。
  3. **重仓股数据的时点（季报）滞后** 会使 holdings 档在季报切换期失真，需在 `source_label` 标注报告期（责任人：backend-dev，期限：S3）。
  4. **腾讯 K 线自修除权 25% 阈值** 未用真实除权案例验证，误判会污染 `r2/vr`（责任人：backend-dev，期限：S3）。
  5. **T+3/T+15 `validation_status` 升格需真实回测** → 未升格前恒 `gray`（§4.5）；回测产出后 architect 复核（责任人：architect，期限：S3 回测后）。
  6. **组合门槛 0.30/3 为架构口径**（Brief 未规定组合阈值）→ 若回测显示误杀/误放，须连同 T+3/T+15 一起走 `10-arch-review` 复议（责任人：architect + product-manager，期限：S3）。
- **未覆盖**：接口逐字段清单与枚举（`09-api-contract`）、前端组件（`07-frontend-arch`）。
