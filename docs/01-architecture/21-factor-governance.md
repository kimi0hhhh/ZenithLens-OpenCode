---
artifact: 21-factor-governance
owner: architect
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [product-manager, backend-dev, dev-lead, qa, orchestrator]
gate: G-AR-05
---

# 因子治理机制设计 · 极境 ZenithLens

> **本文回答的是"每来一个新因子怎么回测 / 怎么准入"，不是一次性填数。**
> 上游：`docs/PROJECT_BRIEF.md` §5.1/§5.2、`09-api-contract.md` v7（§5.35~§5.37、§6.8）、`08-backend-arch.md` §3。
> 口径来源（可参照、不可抄代码）：legacy 设计 `docs/00-charter/00-design-reference-legacy-v2.html` §评分链/生命周期/四盘 + `02-prd.md` F-14。
> 硬规则：**本文不写实现代码，只给接口与伪代码**；所有字段 `snake_case` + 类型 + 单位 + 精度 + 口径；枚举穷举。
> 变更纪律：机制文本与冻结参数一律**只加不改**；任何阈值/公式改动必须契约版本 +1 并通知双边（架构师硬性约束 3）。

## 摘要

1. 新因子 = 一份**声明式定义**（`FactorDefinition`）：只依赖"截至某日"的行情数据，产出逐日二元信号或打分；**回测器不读因子内部，只调它的纯函数**。
2. 回测 = **六窗走前 CV**（禁随机切分）· purge gap=H+2 · 冻结 holdout 60 日 · placebo≥2pp · 基线=`max(恒涨,恒跌)` 报增量 Δ。
3. 评分链 = 每窗 `lift=命中率÷基线` → k_lift 五档悬崖 → ×窗权重 `8/22/15/10/30/15` → ×准入度 `min(1,独立触发日÷N_w)` → 六窗加总；样本一律按**独立触发日**聚合。
4. 生命线 = **准入三项 AND**（F1/F2/F3）→ **牌照四线**（50/60/70/80）→ **淘汰五线** → **双出口** → 冷冻/复活；盘位由状态迁移唯一决定。
5. 落地接缝 = 后端深度模块 `evaluate(definition, bars_view, frozen_config) -> Scorecard`，复用现有 `gates/ddsm/veto/walk_forward` 原语；契约新端点 `POST /factors/candidates` + `GET /factors/candidates/{id}`。

## 正文

### 0. 领域术语表（CONTEXT · domain-modeling）

> 本表是机制的**共同语言**；字段命名与文案必须用规范术语，禁用 Avoid 列近义词。
> 与 `09-api-contract §1.5` 术语表互补（那边约束 UI 语言，这边约束因子机制语言）。

| 规范术语 | 定义（是什么，不是做什么） | Avoid |
|---|---|---|
| **因子定义** `factor_definition` | 一份声明式、无副作用的计算契约：给定"截至某日"的行情视图，输出该日信号/打分 | 因子脚本、因子代码 |
| **因子** `factor` | 在册（已提交并被引擎登记）的因子记录：定义 + 状态 + 最新评估摘要 | 指标、信号 |
| **候选** `candidate` | 已提交但尚未进入正式盘/影子盘落位的因子实例 | 草稿、临时因子 |
| **记分卡** `scorecard` | 一次回测的完整结果：六窗 + 评分链 + 准入三项 + 牌照判定 | 报告、跑分 |
| **独立触发日** `independent_trigger_days` | 去重叠后的开口日数（本次触发距上一次计数触发 ≥H 交易日才计数），绩效与 t 值一律按它聚合 | 条数、样本数 |
| **走前** `walk_forward` | 只用测试日之前（含 purge）的数据训练、逐日/逐折前推，禁随机切分 | 交叉验证、CV |
| **净化间隔** `purge_gap` | 训练标签与测试点之间的隔离带 = H+2 交易日，防标签泄漏 | gap、间隔 |
| **冻结留出** `holdout` | 最近 60 个交易日，回测/调参期永不可见，只在终判时评估一次 | 测试集、验证集 |
| **安慰剂** `placebo` | 打乱标的/随机同频入场得到的对照 Δ，真因子须超它 ≥2pp | 随机对照、null test |
| **基线** `baseline` | 同测试窗内 `max(恒涨率, 恒跌率)`；一切结论报增量 Δ 不报裸命中率 | 50%、抛硬币 |
| **提升比** `lift` | `命中率 ÷ 基线`，>1 才有信息 | 胜率、准确率 |
| **悬崖分** `k_lift` | lift 查五档悬崖表得到的分数（可负），不对称惩罚噪声 | 权重分 |
| **准入度** `admission` | `min(1, 独立触发日 ÷ N_w)`，样本不足按比例打折 | 置信度 |
| **窗权重** `window_weight` | 六窗在总分中的固定权重 `8/22/15/10/30/15` | 权重 |
| **总分** `total_score` | 六窗 `k_lift×权重×准入度` 之和；驱动牌照与淘汰 | 得分 |
| **共线** `collinearity` | 候选因子与现役因子逐日序列的 Pearson 相关绝对值；F2 要求 <0.7 | 相关性 |
| **增量** `delta_pp` | 候选加入现生产配置后组合 Δ 的变化（百分点） | 提升、增益 |
| **牌照** `license` | 因子"挣得"的等级（候补/试用/续聘T2/正式T3），是**持有态**不是瞬时算出的分 | 等级、评级 |
| **盘位** `pan` | 因子当前所属四盘之一（正式/淘汰影子/有效影子/冷冻），由状态迁移唯一决定 | 分区、状态 |
| **竞技场** `arena` | 同数据/同门/同模型、只换一个因子的六窗对照矩阵 | 排行榜 |
| **留一法** `leave_one_out` | 组合 C 移除单个因子 eᵢ 后重跑，观察 Δ 变化（结构红线判据） | 消融 |
| **bootstrap 分位** `bootstrap_percentile` | 打乱标签重采样 500 次得到总分零分布，用于校准显著性 | 置信区间 |
| **账本** `factor_book` | 追加式（INSERT-ONLY）审计记录集合 | 数据库、表 |
| **冷冻** `frozen` | 淘汰后隔离区，台账全留、禁止直接回生产 | 删除、归档 |
| **复活** `revive` | 冷冻因子回候补重爬准入的路径 | 恢复、启用 |

---

### 1. 因子定义接口（可扩展的核心）

> 设计原则（`codebase-design`）：因子回测器是一个**深度模块**——对外只有一个小接口
> `evaluate(definition, bars_view, frozen_config) -> Scorecard`；所有因子差异被压进
> `definition` 这个数据对象里，回测器**不对因子种类做任何 if-分支**。
> 新增因子 = 新增一份 `definition`，**零改回测器代码**。

#### 1.1 三条不变量（不可协商）

- **I1 · 时点纯净**：因子在 t 日的输出只能由 `date <= t` 的行算出（含 t）。回测器只把
  `bars_view`（截断到 `as_of` 的行情）交给它，且**不给它任何全样本统计量**。
- **I2 · 无副作用**：定义是纯表达式/纯函数；不读写文件、不发网络、不依赖全局状态、不依赖随机数。
- **I3 · 可复现**：同一 `definition + bars_view + frozen_config` 必得同一 `Scorecard`；唯一允许的随机是 DDSM 加噪，用固定种子。

#### 1.2 `FactorDefinition`（提交对象，字段字典）

| 字段 | 类型 | 单位 | 精度 | 口径 |
|---|---|---|---|---|
| `factor_id` | string | — | 8~32 位 `[a-z0-9_]` | 唯一 id；缺省由服务端按 `f_{seq}` 生成；重复 → `E_CONFLICT` |
| `name` | string | — | — | 因子名（展示用，允许中文） |
| `kind` | enum `factor_kind` | — | — | `binary_signal`（逐日 0/1）或 `score`（逐日实数） |
| `orientation` | enum `factor_orientation` | — | — | `higher_bullish`（值越大越看涨）/ `higher_bearish`（值越大越看跌，回测时取负） |
| `role_hint` | enum `factor_role_hint` | — | — | `veto`（亮灯=否决做多）/ `score`（作为打分位进入组合） |
| `horizon` | integer | 交易日 | 整数 | 预测跨度 H，∈ {1,3,15}，默认 1；决定 purge=H+2 |
| `inputs` | array[string] | — | — | 声明读取的输入列，必须 ⊆ §1.3 词汇表；回测器据此做列投影，未声明列不可读 |
| `expression` | object | — | — | 表达式 AST（§1.4）；`kind=binary_signal` 时根节点须为比较布尔 |
| `normalization` | enum `normalization_mode` | — | — | `none` / `zscore_train` / `quantile_train`（见 §1.6 L2） |
| `params` | array[object] | — | — | 可调参数，元素见下；**只在训练段网格搜索**，缺省 `[]` 表示无参数 |
| `veto_threshold` | number/null | 随因子 | 4 位 | `role_hint=veto` 时亮灯阈值（分位 0~1 或原值，随 `normalization`）；`score` 时为 null |
| `note` | string | — | — | 一句话说明（来源/机理假设） |
| `requested_by` | string | — | — | 提交方（`orchestrator`/`architect`/`product-manager`/`human`） |
| `task_id` | string/null | — | — | 外部任务 id（登记用，可空） |

`params` 元素：

| 键 | 类型 | 单位 | 精度 | 口径 |
|---|---|---|---|---|
| `name` | string | — | — | 参数名，`snake_case` |
| `type` | enum `param_type` | — | — | `int` / `float` / `bool` |
| `default` | number/bool | 随参数 | 4 位 | 默认值 |
| `grid` | array[number] | 随参数 | 4 位 | 训练段候选值；**禁止空网格**（有 `params` 即须给 grid，回测器在训练段择一） |

#### 1.3 输入列词汇表（闭集，禁扩展即改版本）

> 只有本表列出的列可被 `inputs` 引用；新增列须契约版本 +1。所有列均为**单资产时序**，
> 由行情适配器按 `date` 升序提供；`bench_*` 指该资产绑定基准（A 档为自身 ETF）。

| 列名 | 单位 | 精度 | 口径 |
|---|---|---|---|
| `open` / `high` / `low` / `close` | 元 | 4 位 | 不复权日线 + 自修除权（>25% 跳变缩放历史） |
| `volume` | 手 | 0 位 | 成交量 |
| `amount` | 元 | 2 位 | 成交额 |
| `ret` | 比率 | 6 位 | `close[t]/close[t-1] − 1` |
| `logret` | 比率 | 6 位 | `ln(close[t]/close[t-1])` |
| `r2` | 比率 | 4 位 | 2 日累计收益（DDSM 维） |
| `om` | 比率 | 4 位 | σ 归一动量 `12日收益/20日波动`（DDSM 维） |
| `vr` | 倍数 | 4 位 | 量比 `volume/20日均量`（DDSM 维 + 拥挤度维） |
| `mom5` | 比率 | 4 位 | 5 日动量 |
| `dev` | 比率 | 4 位 | 乖离率 |
| `vpcorr` | 相关系数 | 4 位 | 量价相关（训练段窗口） |
| `volat` | 比率 | 4 位 | 已实现波动 |
| `skew` | 比率 | 4 位 | 收益偏度 |
| `bench_close` | 元 | 4 位 | 绑定基准收盘价 |
| `bench_ret` | 比率 | 6 位 | 基准日收益 |

#### 1.4 表达式 AST（声明式，非代码；op 穷举）

节点两种形态之一：
- 叶子：`{ "column": <§1.3 列名>, "lag": <integer ≥ 0> }`（`lag=0` 即当日）。
- 运算：`{ "op": <enum>, "args": [ <节点>, ... ] }`。

| `op` 分组 | 取值（穷举） | 参数约定 | 语义 |
|---|---|---|---|
| 布尔 `junction_op` | `and` / `or` / `not` | `and`/`or` ≥2 参；`not` 恰 1 参 | 逻辑组合 |
| 比较 `compare_op` | `gt` / `ge` / `lt` / `le` / `eq` | 恰 2 参，返回 0/1 | 阈值比较 |
| 算术 `arith_op` | `add` / `sub` / `mul` / `div` / `neg` / `abs` / `log` | `add/sub` ≥2；`mul` ≥2；`neg/abs/log` 恰 1；`log` 仅对正数 | 逐日算术 |
| 时序 `series_op` | `shift` / `rolling_mean` / `rolling_std` / `rolling_min` / `rolling_max` / `rolling_quantile` / `rank_causal` / `zscore_causal` / `corr_causal` / `ewma` | 见下 | **只允许向后看** |

补充约定（防前视的形式化约束）：
- `shift`：恰 2 参 `[节点, 整数 k]`，**要求 `k >= 0`**（`k=0` 为恒等，禁负值）。
- `rolling_*` / `rank_causal` / `zscore_causal` / `corr_causal` / `ewma`：最后一个参数为**窗口 `w >= 1`**，
  语义为"含当日、向前回溯 w 行"的因果窗口，**窗口右端恒为当日**。
- 除数为 0、`log` 非正、窗口不足 w 行时，该日输出 **null**（非 0），下游按"无信号"处理。

#### 1.5 输出契约

- `kind=binary_signal`：逐日输出 `{0,1}`；1=触发。回测器把 1 日视为"该日开盘可入场"。
- `kind=score`：逐日输出实数；回测器按 `normalization` 在训练段标准化后，用训练段分位决定开口阈值。
- 任一 op 产出 null 的日子 → 该日 `no_signal`，不入样本、不算命中。

#### 1.6 防前视七条铁律 + 校验器（硬性约束 1 的落地）

> 前视 = 因子在 t 日偷看了 >t 的信息。下面七条由回测器**结构性强约束**，不靠自觉。

| # | 铁律 | 校验方式（回测器伪代码） |
|---|---|---|
| L1 | 视图截断 | 只传 `bars_view = bars[date <= as_of]`；调用后断言因子未引用越界（AST 无负 `shift`、无绝对日期常量） |
| L2 | 归一化只用训练段 | `zscore_train`/`quantile_train` 的均值/标准差/断点**每折重算**，样本 = `[start, train_end]`；`as_of` 之后不得出现 |
| L3 | 净化间隔 | `train_end = test_start − (H+2)`；标签日 `t+H` 必须 `≤ train_end` |
| L4 | 禁全样本常量 | AST 内**不允许**出现由全样本估计出的常数；`params.grid` 只在训练段搜索，搜索目标为训练段指标 |
| L5 | 因果窗口 | `rolling_*` 右端恒为当日；`shift` 非负；校验器拒绝任何"居中/未来窗口"形状 |
| L6 | 安慰剂对照 | 同频随机入场 placebo 至少 1 组；真因子 Δ 须超 placebo Δ 的 95 分位 ≥2pp |
| L7 | 冻结留出 | 最近 60 交易日 `holdout` 在搜索/选择期**物理不可读**（数据装配阶段就切掉），仅终判读一次 |

**定义准入前校验（提交即拒）**：AST 出现未声明列、负 `shift`、非正窗口、未知 `op`、
空 `params.grid`、`kind` 与根节点类型不符，任一即 `E_VALIDATION`（`detail` 给字段级原因）。

#### 1.7 参数与调参边界

- 有 `params` 的因子：回测器在**训练段**做小网格搜索（组合数上限 200），选出使训练段总分最高的参数；
  该参数**冻结进记分卡**（`chosen_params`），测试段不得再调。
- 无 `params` 的因子：视为参数已冻结，直接评估。
- 任何"改引擎冻结参数"（`k_noise/p_perturb/min_n/shrink/band/veto_*_quantile/min_coverage_ratio/min_open_count/weighting_basis`）
  均**不属于因子定义**，走 `POST /tasks` 黑名单拒绝（契约 §6.9，A-08）。

---

### 2. 回测执行流程（backtest pipeline）

#### 2.1 触发与任务

```
POST /api/v1/factors/candidates {FactorDefinition}
  → 服务端生成 candidate_id → 落候选账本（INSERT-ONLY，status=submitted）
  → 建 task{type:"run_backtest", params:{candidate_id}}（task_type 已存在，无需新增）
  → 响应 202 {candidate_id, factor_id, status:"backtesting", task_id, submitted_at}
异步：回测完成后 scorecard 落盘（INSERT-ONLY），status → done|failed|rejected
```

- 回测是 CPU 分钟级纯 Python 标准库任务（Brief §5.3），**不联网、不落中间大文件**。
- 并发：同一 `candidate_id` 重复提交禁止并行两次；以 `(definition_hash)` 幂等，同定义已回测则直接回旧记分卡并标 `duplicate`。

#### 2.2 数据装配（只产生"时点纯净"的输入）

1. 取监控资产集合 = A/B 档代理 ETF（`ledger` 交易日历来源）；训练仅用有足够历史的资产。
2. 每资产按 §1.3 组装列，按 `date` 升序；**先切 holdout**（`as_of` 往前 60 交易日），
   回测与调参只用 `holdout_start` 之前的数据；holdout 单独留到 §2.7。
3. 任何一列缺失率 > 20% 的资产从该因子样本剔除（记入 `excluded_assets`）。

#### 2.3 折叠构造（purged walk-forward，禁随机切分）

对每个评估窗口 w（§3.1）内的样本，按测试日 `t` 逐日前推：

```
train_end(t) = t − (H+2)           # purge gap
train(t)     = [window_start, train_end(t)]
test(t)      = {t}
```

- 展开窗（expanding）：`window_start` 固定，`train` 随 t 增长。
- **禁**：随机 k-fold、shuffle、未来数据补足、全样本归一化。
- 每折**重新**做 L2 归一化与 L4 参数搜索。

#### 2.4 逐窗执行

对每个窗口 w 和每个测试日 t：
1. 因子在 `bars_view[≤ t]` 上产出当日信号（`1`/`0` 或分数→阈值）。
2. 若不开门 → `no_signal`，跳过。
3. 若开门 → 记录 `t`、`entry=open[t+1]`（T 日收盘后信号，T+1 执行口径）、
   实现涨跌 `t*_real`（`close[t+H]/close[t] − 1`，H=1 时与产品 T+1 口径一致）。
4. 命中定义：`H` 到期涨跌 > 0 记为 hit（本项目**永不做空**，方向恒为"涨"）。
5. 计算同窗口同测试集上的基线（§3.3）。

#### 2.5 独立触发日聚合（数据卫生 #1）

> 实证依据：legacy KLOW2 614 条仅 359 独立日；条口径 t=4.40 → 聚类稳健 3.09。

```
last_counted = -inf
for t in openings_sorted:
    if t - last_counted >= H:      # 与上一次计数触发不重叠
        count_independent(t); last_counted = t
```

- 命中率、基线、t 值**全部按独立触发日聚合**，不按条数。
- `open_count`（总开口数）与 `independent_trigger_days`（去重叠）**两个都要报**，前者用于 UI 展示与 F3 塌方判定，后者用于准入度与显著性。

#### 2.6 安慰剂（placebo）对照

- 生成同频随机入场（保持每日触发率相同、日期随机打乱）≥1 组（默认 200 组重采样用于分位）。
- `placebo_delta_pp` = 对照组 Δ 的 95 分位；准入要求 `delta_pp − placebo_delta_pp >= 0.02`（≥2pp）。
- placebo 与真实因子**同折叠、同基线**，否则不算。

#### 2.7 冻结留出（holdout）

- 最近 60 交易日，从 §2.2 起就不进入训练/选参。
- 仅在候选**通过 F1/F2/F3 且申请晋升**时评估一次；结果写入记分卡的 `holdout` 块。
- holdout 表现与六窗总分**不一致**时（如总分高但 holdout Δ<0），判 `holdout_mismatch`，**不得晋升**（这是过拟合保险丝）。

#### 2.8 输出记分卡 `Scorecard`

见契约 §5.37。核心字段：六窗数组（lift/k_lift/weight/admission/score/cliff_hit/t/delta）、
`total_score`、`bootstrap_percentiles` + `total_score_percentile`、`f1/f2/f3`、`admission`、
`license`、`pan`、`max_collinearity`/`collinear_with`、`delta_pp`、`open_count`、
`independent_trigger_days`、`sample_days`、`placebo_delta_pp`、`verdict`。

---

### 3. 六窗走前口径

#### 3.1 六窗定义（`factor_window` 穷举）

| 窗 | `window` | 回看口径 | 交易日近似 | 权重 `window_weight` | 准入分母 `N_w` |
|---|---|---|---|---|---|
| 15 日 | `d15` | 最近 15 个交易日 | 15 | 8 | 5 |
| 30 日 | `d30` | 最近 30 个交易日 | 30 | 22 | 10 |
| 60 日 | `d60` | 最近 60 个交易日 | 60 | 15 | 15 |
| 6 月 | `m6` | 最近 6 个自然月 | ~120 | 10 | 30 |
| 24 月 | `m24` | 最近 24 个自然月 | ~480 | 30 | 60 |
| 全量 | `full` | 该因子首个可用日至 `holdout_start` | 全样本 | 15 | 120 |

> `window_weight` 与 `N_w` 是**冻结参数**（契约 §5.14 `window_weights`/`window_min_days`），
> 本文与契约逐值一致；改动须契约版本 +1。

#### 3.2 走前折叠公式（逐窗定义）

```
window_sample(w) = bars[window_start(w) : window_end]
window_end       = as_of − 恰为 holdout 起点（含）之前
for t in window_sample(w):
    train = [window_start(w), t − (H+2)]
    signal(t) = definition.apply(bars[≤t], normalization_fit(train))   # 每折重拟合
```

#### 3.3 基线与 Δ（报增量，不报裸命中率）

```
hit_rate(w)      = hits(w) / independent_trigger_days(w)
always_up(w)     = P(close[t+H] > close[t])   # 同测试日、同独立触发日口径
always_down(w)   = 1 − always_up(w)
baseline_rate(w) = max(always_up(w), always_down(w))
delta_pp(w)      = hit_rate(w) − baseline_rate(w)
lift(w)          = hit_rate(w) / baseline_rate(w)
```

- 基线**必须按独立触发日**、在**同一测试日集合**上计算，禁止跨窗拼。
- 任一窗口无独立触发日 → 该窗 `lift=null`（记分卡字段给 null，UI 显示"—"，**禁止估填**）。

#### 3.4 样本充分性门槛（防误杀三保险之一）

- `open_count < 20` → 该窗**不出结论**（`lift` 仍可展示但标 `low_sample=true`）。
- 候选整体 `independent_trigger_days(full) < 20` → 直接判 `insufficient_data`，不进 F2/F3。

---

### 4. 评分链（scoring chain）

#### 4.1 提升比

`lift = 命中率 ÷ 基线`（§3.3）。`lift=1.06` 表示命中率是基线的 1.06 倍。

#### 4.2 k_lift 悬崖表（五档，不对称惩罚）

| 条件 | `k_lift` | 标签 `label` |
|---|---|---|
| `lift ≥ 1.30` | 1.0000 | `≥1.30` |
| `1.20 ≤ lift < 1.30` | 0.8000 | `≥1.20` |
| `1.10 ≤ lift < 1.20` | 0.6500 | `≥1.10` |
| `1.00 ≤ lift < 1.10` | 0.5000 | `≥1.00` |
| `0.84 ≤ lift < 1.00` | −0.8000 | `<1.00` |
| `lift < 0.84` | −1.3000 | `<0.84` |
| `lift = null` | 0.0000 | `null` |

> 地板说明：`k_lift<1.00→−0.80` 是天花板，`<0.84→−1.3`；**宁可错杀弱势因子**，用不对称惩罚压噪声。

#### 4.3 窗权重

固定 `8/22/15/10/30/15`（对应 d15/d30/d60/m6/m24/full，合计 100）。短窗权重低（抗噪）、中长窗权重高（要求稳定）。

#### 4.4 准入度（折扣裁判）

`admission(w) = min(1, independent_trigger_days(w) / N_w)`，`N_w = 5/10/15/30/60/120`。
样本不足按比例打折；`independent_trigger_days` 为 0/null → `admission=0`。

#### 4.5 总分

```
score(w)      = k_lift(w) × window_weight(w) × admission(w)
total_score   = Σ_w score(w)         # 六窗逐窗累加
```

- 某窗 `lift=null` 时其 `k_lift=0`、`admission=0` → 该窗贡献 0（等价于缺席，不是惩罚）。
- 六窗全部 `lift=null` → `total_score=null`（UI 显示"—"）。

#### 4.6 bootstrap 校准分位（显著性校准）

- 对候选的**每日信号日期**做 500 次打乱（保存触发频率、随机换日期），每次跑完整六窗评分链 → 得 `total_score` 零分布。
- 输出分位 `bootstrap_percentiles = {p50, p90, p95, p99, p995}` 与 `total_score_percentile`（本因子总分在零分布中的位置）。
- **当前契约登记的固定值** `−10.8 / 38.7 / 48.4 / 61.7 / 64.1` 为 legacy 演示常量；
  真实引擎产出后**必须替换为本产品实测零分布**，未产出前相关接口返回 null 并标注"待复现"（残留风险 9）。
- 判读建议（非硬门禁）：`total_score ≥ p95` 才称"随机之上"；`< p75` 进入 A/B 观察区。

#### 4.7 四裁判（谁也不能同时当运动员和裁判员）

| `judge` | 角色 | 度量 | 用法 |
|---|---|---|---|
| `lift` | 分数裁判 | `lift → k_lift` 悬崖 | 决定每窗得分 |
| `t` | 闸门裁判 | 独立触发日聚合的 t 值 | 显著性未过不放行 |
| `admission` | 折扣裁判 | 独立触发日 ÷ N_w | 样本不足按比例打折 |
| `backtest` | 晋升裁判 | 实测 Δ 与 A/B | 最终晋升以走前回测 + A/B 为准 |

---

### 5. 准入 - 牌照 - 淘汰

#### 5.1 准入三项 AND（`F1 ∧ F2 ∧ F3`）

| 项 | 名称 | 精确判据 | 失败结果 |
|---|---|---|---|
| F1 | 有效性 | `lift(m6) > 1.00` **或** `lift(d60) > 1.00`（近 6 月或近 60 日任一超基线） | `rejected_f1` |
| F2 | 独立性 | `max_collinearity < 0.70`，其中 `max_collinearity = max_i |corr(candidate_series, incumbenti_series)|`，序列为训练段逐日信号/打分 | `rejected_f2` |
| F3 | 增量 | 加入现生产配置后 `delta_pp ≥ +0.5pp` **且** `open_count_new ≥ 0.5 × open_count_base`（开口不塌方>50%） | `rejected_f3` |

- 前序未过 → 后续标 `na`（不适用），不出无意义数值。
- `max_collinearity` 与 `collinear_with`（与谁共线最高）**必须回传**，供审计。
- F3 的 `delta_pp` 用与现生产配置**同数据/同门/同模型**的对照（只多一个候选因子），即竞技场 `candidate` 行。

#### 5.2 牌照四线（`factor_license` 穷举）

> **口径裁定**：50/60/70/80 为**总分线**（总分量纲）；legacy 佐证：候补 ≥50 的随机通过率
> ~5% ≈ bootstrap 零分布 p95=48.4。`FrozenParams.license_lines[].min_independent_days`
> 为**样本充分性下限**（独立触发日），与总分线**不同名不同义、并行满足**（见 §11 风险 R2）。

| 牌照 | `license` | 总分线 | 附加条件（窗 k） | 样本下限 | 生产权限 |
|---|---|---|---|---|---|
| 未达线 | `none` | `< 50` | — | — | 不入盘 |
| 候补 | `candidate` | `≥ 50` | — | 独立触发日 ≥ 50 | 只记账，不参与生产 |
| 试用 | `probation` | `≥ 60` | `k_lift(d30) ≥ 0.5` | 独立触发日 ≥ 60 | 影子观察，不参与生产 |
| 续聘 T2 | `renew_t2` | `≥ 70` | `k_lift(d60) ≥ 0.7` | 独立触发日 ≥ 70 且持牌满一季 | 可回生产（经 A/B） |
| 正式 T3 | `full_t3` | `≥ 80` | `k_lift(m24) ≥ 0.7` | 独立触发日 ≥ 80 | 正式生产 |

- **牌照是持有态**：升级在月度/季度评审时按上表授予；一旦授予，不因某一日总分抖动即时降级，降级走 §5.3/§5.4。
- 牌照线为冻结参数，改动须契约版本 +1。

#### 5.3 淘汰五线（任一触发即进入双出口流程）

| # | 线 | 精确判据 |
|---|---|---|
| 1 | 急性熔断 | 连错 5 次 **或** `d15 命中率 < 基线 − 15pp` |
| 2 | 缓性衰减 | 滚动 60 日 `lift < 1.00` 连续 30 个交易日 |
| 3 | 结构红线 | `lift(m24) < 1.00` **或** 留一法移除后组合 `Δ` 升 ≥0.5pp（持续 30 天） |
| 4 | 分数失守 | `total_score < 39` 连续两期降级；`< 19` 进 A/B；`< −11` 隔离进冷冻 |
| 5 | 开口塌方 | 候选加入后开口数下降 >50%（与 F3 同一判据的持续版） |

#### 5.4 双出口

- **软出口（降级梯）**：`full_t3 → renew_t2 → probation → candidate`，逐级降，**台账全留**。
- **硬出口（A/B 对照）**：移出生产但在盘继续跑 60 交易日；
  - 移出后组合 `Δ ≥ 移出前 + 0.5pp`（或持平且方差降）→ **淘汰正确** → 进冷冻盘；
  - 移出后组合变差 ≥0.5pp → **判误杀** → 无损回原牌照级。
  - A/B 未满 60 日或 `open_count < 20` → 不出结论，不出盘。

#### 5.5 防误杀三保险

1. **条件绩效口径**：分 regime 判读，牛市不杀熊市因子（按独立触发日聚合，不用条口径）。
2. **开口 <20 不出结论**：样本不足时只观察、不淘汰、不晋升。
3. **A/B 期间牌照冻结**：不因短期波动淘汰，误杀可无损回位。

#### 5.6 冷冻与复活

- 冷冻盘**不是坟墓**：台账全保留。
- 复活触发（任一）：① regime 切到有利状态；② 新信息源解锁；③ 冷冻满 90 天重扫。
- 复活路径：**回候补（`candidate` 线）重爬**，重新走准入三项 AND + A/B 60 日；
  **禁止直接回生产**；复活机制变更须重走六关。

---

### 6. 新因子端到端流程（状态机 L0~L9）

```
L0 提交定义      POST /factors/candidates（FactorDefinition）→ 落候选账本 status=submitted
L1 静态校验      §1.6 提交即拒（未声明列/负shift/空网格/类型不符）→ E_VALIDATION
L2 回测执行      purged walk-forward × 六窗 × placebo × 独立触发日聚合 → Scorecard
L3 准入判定      F1 ∧ F2 ∧ F3
   ├─ 未过 F1/F2/F3 → verdict=rejected_*，回候选池，冷却 90 天
   └─ 全过          → 进有效影子盘（role=shadow_effective），牌照=候选/试用
L4 影子观察      独立记账、不参与生产；周提名 ≤3；累计独立触发日与总分
L5 牌照评审      月度/季度按 §5.2 授予/升级牌照；持牌满一季方可续聘
L6 A/B 对照      §5.4 硬出口：移出 vs 保留 60 交易日，按组合 Δ 定结论
L7 转正          牌照 ≥ 续聘 且 A/B 判"该留" 且 池子未满/有旧因子让位 → 正式盘
L8 持续体检      月检留一法 + 季复查 + 分数失守扫描 → 触发淘汰五线 → 双出口
L9 冷冻/复活     淘汰正确 → 冷冻盘；复活触发 → 回候补重爬
```

- 全流程**机器自动裁判**；人只保留**机制变更权**与**紧急停机权**（不逐因子拍板）。
- 提名上限：每周 ≤3；冷却 90 天（契约 §5.11 `nomination_limit` / §5.31 `panel`）。

---

### 7. 盘位判定（pan / role / status）

#### 7.1 盘位 `factor_role`（四盘，穷举）与展示四盘映射

| `factor_role` | 展示盘 | 含义 | 生产权限 |
|---|---|---|---|
| `adopted` | 正式盘 | 已转正、参与组合决策 | 生产 |
| `shadow_retired` | 淘汰影子盘 | 曾生产、现做 A/B 对照 60 日 | 只读 |
| `shadow_effective` | 有效影子盘 | 准入三项 AND 通过、待晋升 | 只读 |
| `frozen` | 冷冻盘 | 已淘汰/失守、禁止直接回生产 | 无 |

#### 7.2 生命周期状态 `factor_status`（穷举）

| `factor_status` | 含义 | 与盘位关系 |
|---|---|---|
| `active` | 现役、正常 | 通常 `adopted` |
| `probation` | 观察期 | `shadow_effective` |
| `cooling` | 冷却（分数走低但未出盘） | `adopted` 或 `shadow_effective` |
| `frozen` | 冷冻 | `frozen` |
| `retired` | 已退役（历史） | `frozen`（历史态） |

#### 7.3 盘位判定规则（由状态迁移唯一决定，不再有第二真相）

```
若 license ∈ {renew_t2, full_t3} 且 A/B 判"该留" 且 正式盘未满 → role=adopted
若 已转正 且 触发淘汰五线 → role=shadow_retired（进 A/B）
若 准入三项 AND 通过且未转正 → role=shadow_effective
若 A/B 判"淘汰正确" 或 分数失守 < −11 → role=frozen
```
- 正式盘上限：否决位 ≤4、打分位 ≤3（契约 §5.11 `caps`）；满员须有旧因子让位（**在位者无终身制**）。
- 同一时刻一个 `factor_id` 只在一个盘位；历史盘位变更全量写入账本。

---

### 8. 账本与留痕

#### 8.1 六本 UI 账本（沿用契约 §5.13，不改）

`adopted_factors` / `scan_history` / `factor_health` / `retired_log` / `shadow_signals` / `factor_arena`。
其中 `scan_history` 登记每次挖掘的 F1/F2/F3 判定（候选正式入库前的快照）。

#### 8.2 候选提交与回测的留痕（v7 新增，独立于六本 UI 账本）

> 为不破坏"`factor_book` 固定 6 本"的 UI 契约，候选流水**不进 `factor_book` 枚举**，
> 而以**独立追加式存储**承载，仅由新端点读写。

| 存储 | 形态 | 记录 | 口径 |
|---|---|---|---|
| `factor_candidates.jsonl` | JSONL 追加 | 每次提交一条 `{candidate_id, factor_id, definition_hash, definition, requested_by, submitted_at, status}` | INSERT-ONLY；同 `definition_hash` 幂等 |
| `scorecards.jsonl` | JSONL 追加 | 每次回测一条 `Scorecard` 全文 | INSERT-ONLY；同 `(candidate_id, definition_hash, frozen_config_hash)` 幂等 |
| `factor_health.jsonl` | 既有 | 周期体检追加 `{factor_id, check_date, license, total_score, independent_trigger_days, status, alert}` | INSERT-ONLY |

- **INSERT-ONLY 铁律**：候选与记分卡写入后不可编辑/删除；重跑产生**新**记录（版本化 `run_seq`），不覆盖旧记录。
- `frozen_config_hash`：对 `FrozenParams` 全量序列化取哈希；冻结参数一变即旧记分卡不可比（审计可追）。
- 数据来源：`definition` 原文随记分卡留存，保证"任何一次判定可回溯凭什么、用的什么数据、历史上赢过多少次"（Brief §3 可审计）。

#### 8.3 留痕最小集（每因子必可回答）

1. 定义原文与哈希；2. 六窗分子分母（hits / independent_trigger_days / open_count）；
3. 基线率与 Δ；4. placebo Δ；5. F1/F2/F3 与共线对手；6. 牌照与盘位变更时刻；7. A/B 结论与误杀回位。

---

### 9. 与引擎的接缝

#### 9.1 分层与模块（对齐 `08-backend-arch`）

```
adapters/   读取 bars 缓存、写 jsonl（唯一 I/O）
  └─ core/factor_eval.py   纯逻辑深度模块：evaluate(definition, bars_view, frozen_config) -> Scorecard
core/gates.py / ddsm.py / veto.py   既有原语（复用，不重写）
  └─ core/factors.py      治理视图（四盘/账本/评分链/生命周期，只读派生）
server/handlers/factors.py   路由 + 信封（新端点挂这里）
```

#### 9.2 深度模块接口（唯一对外）

```
evaluate(definition: FactorDefinition,
         bars_view: BarsView,          # 已截断到 as_of、已切 holdout
         frozen_config: FrozenParams) -> Scorecard
```

- **小接口**：一个函数、三个参数；回测器**不 import 因子、不 eval 代码、不读因子内部**。
- **大实现**：折叠构造、每折归一化、六窗聚合、placebo、bootstrap、准入三项、牌照判定全在内部。
- **可测**：用 2 个替身（因果假因子应得正分 / 未来假因子应被 L1 拒）即可覆盖接口；内部单测用内存 `BarsView`。
- **删除测试**：删掉该模块，回测逻辑会在挖掘/体检/A/B/竞技场四处重现 → 它挣得了存在。

#### 9.3 复用引擎原语（口径不双份）

- 信号链复用 `gate(E1/E3)`、`ddsm(125格)`、`veto(crowd/klow2)` 现有实现；候选因子只做**换一项**对照。
- 组合 Δ（F3/留一法）复用 `portfolio` 组合加权与 `review` 基线口径；禁止在因子模块另写一套基线。
- `frozen_config` 直接取 `engine.frozen_params()`，保证窗权重/牌照线/门槛全项目单源。

#### 9.4 接缝边界（本机制不做什么）

- **不**提供因子热更新/在线生效：转正须走 §6 状态机，禁止"提交即上生产"。
- **不**允许 API 改冻结参数（走 `POST /tasks` 黑名单）。
- **不**接受任意 Python 代码/第三方依赖（Brief §5.1/§5.3 零依赖可复现）。
- **不**新增盘位或账本枚举值（保持 6 本账本、4 盘不变）。

#### 9.5 幂等与确定性

- 提交：`definition_hash` 幂等；回测：`(candidate_id, definition_hash, frozen_config_hash)` 幂等。
- 重跑同参数 → 同 `Scorecard`（除 `scored_at`）；DDSM 加噪固定种子。
- 异步任务遵守 `GET /tasks/{id}` 轮询协议，超 90 秒的命令先发心跳（编排纪律）。

---

### 10. 契约对齐（v7）

| 机制对象 | 契约落点（v7） | 说明 |
|---|---|---|
| `FactorDefinition` | §5.36 + `POST /factors/candidates`（§6.8） | 提交对象字段字典 |
| `Factor` | §5.35 | 在册因子全量记录（`FactorItem` 是列表投影） |
| `Scorecard` / `ScorecardWindow` | §5.37 + `GET /factors/candidates/{candidate_id}`（§6.8） | 六窗 lift/k_lift/权重/准入度/总分/F1F2F3/牌照/盘位/共线/Δ/样本 |
| 新枚举 | §1.3 v7 追加表 | `factor_kind`/`factor_orientation`/`factor_role_hint`/`candidate_status`/`backtest_verdict`/`normalization_mode`/`expression_op` 各组 |
| 计数 | §4 总览 | 接口 53 → **55**；面向 UI 51 → **53**（新端点可 UI 触发） |

- v7 遵循"**只加不改**"：不改任何既有字段名/类型；不改 `factor_book` 六本、不改四盘枚举。
- 新端点只做"提交 + 取记分卡"，**晋升/淘汰不在本端点**（仍由治理周期与状态机驱动），避免范围蔓延。

---

### 11. 开放问题与残留风险（每项含责任人与期限）

| # | 风险 | 处置 | 责任人 | 期限 |
|---|---|---|---|---|
| R1 | 六窗 `m6`/`m24` 交易日近似（120/480）与真实交易日历可能有 ±5% 漂移 | 回测器按**真实交易日历**取窗口边界，近似值仅作文档说明 | architect + backend-dev | S3 |
| R2 | `FrozenParams.license_lines[].min_independent_days` 命名与 legacy"总分线"语义**不同名不同义**，易被消费成总分线 | 本文 §5.2 明确二指标并行；建议 v7 追加 `min_total_score` 兄弟字段（只加不改）后由契约收口 | architect | S3 |
| R3 | `bootstrap_percentiles` 现为 legacy 演示常量 | 真实引擎产出后替换；未产出前返回 null + "待复现"标注（与契约残留风险 9 一致） | backend-dev + architect | 因子引擎产出后 |
| R4 | 因子账本目录：`06-system-arch` 写 `data/factors/`，`factor_board.py` 读 `ledger/`，存在路径漂移 | 由 backend-dev 统一并回报，机制不动存储实现 | backend-dev | S3 |
| R5 | `placebo` 重采样次数（500）与 `params` 网格上限（200）为架构口径，未实测收敛 | 以实测 CPU 预算校准，改值须契约版本 +1 | architect + backend-dev | S4 |
| R6 | 共线度量为 Pearson 单一口径，极端尾部可能低估非线性共线 | 先按单口径落地；若发现漏判，追加 `spearman` 并版本 +1 | architect | S4 |
| R7 | KLOW2 下影线否决 / 拥挤度六维复合两个引擎在用因子的真实六窗回测尚未产出 | 本机制落地后由 backend-dev 用新端点跑出真实记分卡填入因子盘，**不得沿用 legacy 示例数字** | backend-dev + architect | S3 |
| R8 | holdout 60 日与影子盘 60 日为两个不同"60 日"，文案须区分（前者禁调参、后者连续记录门槛） | 契约/UI 文案分别标注 | product-manager + architect | S3 |

---

## 自验收

- [x] 因子定义接口**可扩展**：新因子 = 一份 `FactorDefinition`（纯表达式），回测器不分支因子内部（§1，`codebase-design` 深度模块）
- [x] **防前视**写成七条铁律 + 校验方式（L1 截断 / L2 训练段归一化 / L3 purge / L4 禁全样本常量 / L5 因果窗口 / L6 placebo / L7 holdout），并明确"只用 train_end 前数据"（§1.6、§2.2）
- [x] 六窗走前口径（禁随机切分 / purge=H+2 / 基线 `max(恒涨,恒跌)` / 报 Δ）逐条定义（§3）
- [x] 评分链完整：lift → k_lift 五档悬崖 → 窗权重 `8/22/15/10/30/15` → 准入度 `min(1,独立触发日÷N_w)` → 六窗加总（§4）
- [x] 准入三项 AND（F1 有效性 / F2 独立性 / F3 增量）精确到可执行判据（§5.1）
- [x] 牌照四线（50/60/70/80）+ 淘汰五线 + 双出口 + 防误杀三保险 + 冷冻复活全写（§5）
- [x] 新因子端到端流程 L0~L9 与盘位判定规则（§6/§7），`factor_role`/`factor_status` 穷举
- [x] 账本 INSERT-ONLY、候选/记分卡留痕、`frozen_config_hash` 可追溯（§8）
- [x] 与引擎接缝：深度模块 `evaluate(...)`、复用 gates/ddsm/veto/portfolio 原语、边界与幂等（§9）
- [x] 每字段有类型 + 单位 + 精度 + 口径；枚举穷举；字段名 `snake_case`（§1.2/§1.3/§1.4、契约 §5.35~§5.37）
- [x] 数字带来源：牌照线来自 legacy 随机通过率 ≈ bootstrap p95；独立触发日来自 legacy KLOW2 614→359 实证（§2.5/§5.2）
- [x] 未写实现代码（仅伪代码/接口/字段）；未改 `static/**`、后端 `*.py`、`runtime/**`；未派发子任务
- [x] 与契约 v7 对齐并声明"只加不改"（§10）

## 下游交接

- **主消费方 `backend-dev`**：按 §9 落地 `core/factor_eval.py` 的 `evaluate(...)` 深度模块，复用 `engine.frozen_params()` 与既有 gates/ddsm/veto；实现契约 v7 的 `POST /factors/candidates`、`GET /factors/candidates/{id}`；候选/记分卡落 `factor_candidates.jsonl`/`scorecards.jsonl`（INSERT-ONLY）。**先落地机制，再用它跑 KLOW2 与拥挤度六维的真实六窗回测填盘**（R7）。
- **主消费方 `frontend-dev`**：因子页"提交候选/查看记分卡"（若纳入 UI）只读契约字段；六窗 bars 读 `ScorecardWindow.lift`，跑分表读 `k_lift/weight/admission/score`，缺失一律"—"，**不得本地推算/估算**；牌照只读 `license`/`license_label`。
- **次消费方 `qa`**：负向断言——未声明列的 AST 被 `E_VALIDATION` 拒；负 `shift` 被拒；同 `definition_hash` 重复提交幂等；`GET /factors/candidates/{id}` 在回测未完成时 `status=backtesting` 且六窗为 null；`frozen_config` 改动后旧记分卡 `frozen_config_hash` 不匹配；INSERT-ONLY（无删除/编辑端点）。
- **次消费方 `product-manager`**：核对 §7 四盘/生命周期长文与 `02-prd.md` F-14 一致；确认 R8 两个"60 日"文案区分。
- **残留风险**：见 §11 R1~R8，其中 **R2（license 线命名歧义）** 与 **R7（真实回测未产出）** 为最高优先，须在 S3 内收口；未收口前相关接口返回 null/空集，**禁止用 legacy 示例数字冒充实测**。
- **变更纪律**：机制文本与冻结参数 `approved` 后任何改动须契约版本 +1 并 `say` 通知 frontend-dev + backend-dev。
