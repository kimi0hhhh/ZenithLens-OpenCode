---
artifact: 08-backend-arch-r2
owner: architect
version: v3.2
status: draft
supersedes: 08-backend-arch.md（R1 基线 v5）
created: 2026-09-12
reviewers: [product-manager]
gate: G-AR-04
---

# 后端架构 · 极境 ZenithLens（R2 升级轮增量）

> 本文是 `08-backend-arch.md`（R1 v5）的**增量设计**：只写 R2 变更的模块与算法落点，未变部分（6 层结构、预测核心链、估值五档顺序、冻结参数、INSERT-ONLY 语义）**沿用 R1 v5，不重抄**。
> 契约法律：`09-api-contract-r2.md`（v9.1）。需求：`01-requirements-v3.md` R2-01..25；解剖现状：`00-dissection-v3.md`（代码事实依据，已与代码逐模块核对）。
> 硬约束不变：纯 Python 标准库、Python 3.8+、可离线复现；本文只写伪代码与口径，**不写可运行代码**。
> R2 增量的原则：**全部改动落在既有 6 层内，不新增层**；新增 1 个薄模块 `review.py`（§5.1）、其余为既有模块扩展。
> **v3.1（2026-09-12 · 会签收敛轮）**：按 `10-arch-review-pm-r2.md` 与 `10-arch-review-r2.md` v2 收敛 D-1..D-4 / R-1..R-5——新增 §3.1b 代理质量重建证据道（D-2）、修订 §3.1 评分对象（D-3）、§3.3 QDII 门槛/复评（R-5）、§4.1 复查日与防稀释闸（D-4）、§4.2 差异摘要（N-4）、§4.4 证据来源、§5.2 复算锚（R-1）、§7.4 收口硬约束（D-2c）；契约同步见 09 v9.1。
> **v3.2（2026-09-13 · 用户指令轮）**：影子盘窗口 20→60（用户指令）——§4.3 / §5.3 更新 + 新增 §5.5 设计核验（启动回填 60 / 每日滚动 / 计算量 ≈15–17s / 幂等保持 / 冷启动复验）；契约同步见 09 v9.5。

## 摘要

1. R2 后端 = **四组模块级变更**：估值通道（valuation/estimator）、覆盖扩容（factor_engine/ledger_api/holdings）、准确率出数（review 新增/ledger_api/factor_engine）、数据源治理（estimator/settings）。三份命脉数据流：`nav_history 维护 → accuracy v2 全档通道`；`t1_real 回填 → 影子盘成绩`；`生产配置回测 → /review/scores`。**v3.1（会签收敛）**：增设**代理质量重建证据道**（§3.1b，D-2(a)——R2-04 首选证据，nav 史就绪后立即重建）；评分对象修订（D-3：同 mode 当日最后一条）；QDII 首测门槛/复评暂态化（R-5）；回填复算锚（R-1）；防稀释闸（D-4）。
2. **四项 open-issues 全部在本文落实现口径**：① QDII 双段算法与回退（§3.3）；② R2-04 排期依赖（§7.4）；③ 新浪兜底限定接入（§6.3）；④ 首测不达标挂档/降档边界（§4.4）。
3. 新增存储 7 处：`data/cache/nav/<code>.json`（维护版净值史）、`data/snapshot/daily/valuation-YYYYMMDD.jsonl`（每日留档）、`data/health-log.jsonl`（源事件日志）、`data/review/tier_reviews.jsonl`（验证/复核结论，INSERT-ONLY）、`data/snapshot/review_scores.json`（成绩缓存，可重建）、**v3.1 新增** `data/snapshot/proxy_quality.json`（代理质量重建证据道，D-2）、`data/review/qdii_review.jsonl`（QDII 首测/复评与 alignment 计数，INSERT-ONLY，R-5）。
4. 技术债处置：T-01 预算实现（§3.5）、T-05 两份 F10 解析器合一（§3.2）；T-02/T-03/T-04 维持延后（§9）。
5. 冻结纪律与红线逐条核对：K=4/p=0.25/MIN_N=15/BAND=0.02 未改；E2/E4 未复活；永不做空；台账 INSERT-ONLY（recompute=先归档后重生成）；`0.5830` 彻底退役（§5.4）。

## 正文

### 1. 改动概览（模块 × 变更类型）

| 模块 | 变更类型 | 内容 | 关联 |
|---|---|---|---|
| `review.py` | **新增（薄模块）** | `/review/scores` 成绩组装：生产配置回测缓存 + 影子盘实盘成绩 + hero | R2-11 |
| `valuation.py` | 扩展 | `build_accuracy` v2（全档 `mode\|code`）；`value_fund` 档3 top20 + 档4 QDII 双段；日留档 `archive_daily`；预算实现；`precision_summary` 窗口字段 | R2-01/02/03/05 |
| `estimator.py` | 扩展 | `lsjz_history`（分页净值史）；`overseas_ref_quote`（隔夜参照）；港股符号 + `sina_rt_quotes` 批量兜底；F10 `topline=20` + 解析器合一（T-05） | R2-02/03/16/17 |
| `ledger_api.py` | 扩展 | `backfill_due`（t*_real 自动回填，`proxy_bar`）；`recompute_shadow_window`；`measured_baseline`；`shadow_progress` 归档合并；删 `BASELINE_RATE` | R2-07/12/13/14 |
| `factor_engine.py` | 扩展 | `production_definition` + `evaluate_production`（内置因子 `production`）；`verify_tiers`（单资产生产配置判定） | R2-06/11 |
| `holdings.py` | 扩展 | 主源口径（`data/holdings.json` 首源）；`verify` 元数据同步；`apply_tier_reviews` | R2-06/15/24 |
| `settings.py` | 扩展 | `health-log.jsonl` 事件日志 + `fail_window_7d`/`recent_failures` 计算 | R2-18 |
| `app.py` | 扩展 | `/review/scores` 真实化；`/settings/holdings-data` 主源字段；任务类型 2 个；warmup 序列调整；coverage/signals 新字段 | R2-08/11/15/16 |
| 存储 | 新增 5 / 修改 1 | 见摘要 3 与 §2 | — |

> 未列模块零变更；预测核心链（gate/DDSM/双否决/出口）、组合加权、因子治理主链、立方体/竞技场派生**一律不动**。

### 2. 存储布局增量

```
data/
  cache/
    nav/<code>.json            # ★新增：维护版净值史 {code, updated_at, points:[{date, nav}]}
                               #   （由 maintain_nav_history 增量维护；按 date 去重、不覆盖既有日期）
  snapshot/
    daily/valuation-YYYYMMDD.jsonl  # ★新增：每日估值留档（每基金 1 行，收盘后写一次，写完只读）
    accuracy.json              # 结构 v2：键 mode|code；每项 + updated_at / matched_days
    review_scores.json         # ★新增：成绩缓存（可重建；整文件原子替换）
    proxy_quality.json         # ★新增(v3.1)：代理质量重建证据道（bars×nav 史；R2-04 首选证据，D-2）
  health-log.jsonl             # ★新增：数据源事件日志（append-only；{at, source_id, ok, latency_ms, note}）
  review/tier_reviews.jsonl    # ★新增：C→B 验证 / 9 只代理复核结论（INSERT-ONLY）
  review/qdii_review.jsonl     # ★新增(v3.1)：QDII 双段首测/复评与 alignment_conflict 计数（INSERT-ONLY，R-5）
  snapshot/valuation_history.jsonl  # 沿用：当日逐次入账审计源（INSERT-ONLY）
  ledger/shadow_signals.jsonl + backfill.jsonl + archive/  # 沿用；backfill 行追加 method + proxy_code
```

### 3. 估值通道（R2-01/02/03/05）实现设计

#### 3.1 误差通道 v2（`valuation.build_accuracy`，R2-01）
```
build_accuracy_v2(hold_list):
  nav_store = load_nav_history()                 # §6.1 维护版净值史（回退 holdings.nav_history，标注 source）
  for h in hold_list:
      recs = read_history(code=h.code)           # 全部日期的估值入账（INSERT-ONLY）
      by_day = group recs by date
      samples = []
      for D, day_recs in by_day:                 # D 为估值日
          pair = nav_pair(nav_store, D)          # (nav(D), nav(D-1))；缺任一端 → skip（不填 0）
          if pair is None: continue
          real = nav(D)/nav(D-1) - 1
          for mode, mrecs in group day_recs by mode:   # ★v3.1/D-3：按 mode 分组
              rep = max(mrecs, key=written_at)         # 同 mode 当日最后一条（多轮取最后，防污染）
              if rep.change_rate is None: continue     # unknown 记录不参与
              samples.append({date:D, mode:mode, est:rep.change_rate, real:real,
                              err=abs(est-real), dir_ok: sign(est)==sign(real) if real!=0 else None})
      for (mode, code) in group samples by mode: # ★口径：按 mode|code 归键（首档即评分档）
          window = samples of this mode within last 40 pairable days  # 滚动窗
          n = len(window)
          if n >= 5:  # n<5 → 不写统计（confidence=unknown + conf_reason=no_samples）
              write accuracy[mode|code] = {mae_rate, dir_hit_rate, n_test:n,
                                           window_days:40, updated_at:now, matched_days:[D...]}
  save_accuracy_atomic()                         # 整文件原子替换（可重建缓存）
```
- **评分对象固化（v3.1/D-3 修订）**：每个 `(date, code, mode)` 取当日最后一条（同 mode 同日多轮取最后、防污染；不同 mode 各自成样本——防 holdings/proxy 样本饥饿）。口径写入 `Valuation` tooltip 文案（R2-20）。
- `confidence` 分档沿用 v8 阈值（≤0.008 high / ≤0.012 mid / else low）；`conf_reason` **五值穷举 + 按序命中即停**由读取层生成（§3.1.1，v3.1/R-4）。
- 触发：`maintain_nav_history` 任务内（nav 就绪后）+ 启动 warmup；目标"净值回补接通后 24h 内产生当日误差记录"。
- 源码路径：`valuation.py#build_accuracy`（重写为 v2；保留函数名，不新增接口）。

##### 3.1.1 `conf_reason` 生成规则（读取层，v3.1/R-4：**按序命中即停**，五值穷举）
| 序 | 情形 | 值 |
|---|---|---|
| 1 | `mode=unknown`（全链无来源） | `mode_unknown` |
| 2 | 无当日记录且预算跳过 | `budget_exceeded` |
| 3 | 无当日记录（其他） | `valuation_missing` |
| 4 | 有当日记录但净值对缺 | `nav_missing` |
| 5 | 有记录但 `n_test<5` | `no_samples` |

> v3.1/R-4：`pending_backfill` 已移除（等待回填语义归 `reconcile_result=pending`，不混入徽章枚举）。

##### 3.1b 代理质量重建证据道（v3.1/D-2(a)；R2-04 首选证据）
```
build_proxy_quality(hold_list):
  # v1 公式（bars × nav 史，40 日窗）——重建式，不依赖展示通道逐日积累
  for h in hold_list where proxy_code:
      bars = get_bars(proxy); nav = nav_store(h.code)
      对每个可配对日 D：est = bars[D].close/bars[D-1].close - 1；real = nav(D)/nav(D-1) - 1
      entry = {code, proxy_code, mae_rate, dir_hit_rate, n_test, window_days:40,
               matched_days, updated_at}
  save data/snapshot/proxy_quality.json   # 原子替换；可重建
```
- **用途**：R2-04 9 只复核与换代理候选筛选的**首选证据**（判断代理质量）；`方向命中率≥60%` / MAE 超标判据取自本文件，**不取自展示通道**（`accuracy.json`）。
- **两通道分离（D-2）**：展示通道（§3.1，量"展示精度"、逐日积累）与质量通道（本节，量"代理质量"、可重建）分键分文件，禁止互相引用充当判据。
- 复核结论（含所用证据数字）落 `tier_reviews.jsonl`（INSERT-ONLY）；换代理事件同时记映射变更时点（供 R-1 复算追溯）。

#### 3.2 重仓加权升级（R2-02；含 T-05 合一）
- **F10 解析器合一（T-05）**：`proxy_map.parse_f10_holdings` 退役，`proxy_map.fetch_f10_holdings` 改为复用 `estimator.parse_top_holdings`（后者已支持 5/6 位代码、`topn` 参数）；两处口径只此一份。
- `estimator.eastmoney_top_holdings` 增 `topline` 参数（默认 10，R2 启用 20）；缓存文件记录 `top_n`，若缓存 `top_n<请求值` 且缓存过期 → 重抓；重抓失败按可得旧缓存 + 如实标注 `top_n`。
- 实时报价扩容：`tencent_symbol` 增港股分支（5 位数字码 → `hk` 前缀）；`tencent_rt_quotes` 支持混合 A/HK 批量；美股标的不解析（字母代码，parser 不产出）→ 计入 `excluded_count` 与覆盖缺口（**不编造**）。
- `valuation._weighted_holdings`：`detail` 增 `top_n` / `included_markets` / `excluded_count`（契约 §3.3）；缺报价标的保持 `used=false` 剔除。
- 工具提示口径：`report_date`（披露截止日）+ `covered_weight_pct`（前 10/20 覆盖权重）由 `trace[holdings].detail` 直出（R2-20 tooltip 第 7 项）。

#### 3.3 QDII 双段校正（R2-03；ISSUE-ZL-R2-01 裁定落地）
```
qdii_estimate(h, date_T, as_of_ts):
  dom = 最近已收盘 A 股交易日的代理 ETF 段：
        bars = get_bars(proxy); i = index of last bar with date <= date_T
        r_dom = bars[i].close/bars[i-1].close - 1 ; dom = {value: r_dom, as_of: bars[i].date}
  ovs = estimator.overseas_ref_quote(market_of(h))     # US→纳指参照 / HK→恒生参照
        → {value, ref_code, trade_date, close_ts} 或 None
  if ovs is None:
        return (r_dom, correction(applied=False, fallback_reason="overseas_unavailable"))
  if not aligned(ovs.close_ts > dom.as_of 15:00 Asia/Shanghai):
        return (r_dom, correction(applied=False, fallback_reason="alignment_conflict"))
  return (r_dom + ovs.value, correction(applied=True,
          domestic={value:r_dom, as_of:dom.as_of},
          overseas={value:ovs.value, ref_code, trade_date, source}))
```
- **拼接口径（架构冻结）**：加法拼接、两段**时间互补**（`alignment` 校验保证不双计）；**不引入学习权重**（防小样本过拟合）。
- **回退矩阵（穷举）**：
  1. 隔夜源不可得（探测/解析/超时）→ 单段 + `overseas_unavailable`（tooltip 标注"单段（隔夜数据缺失）"）；
  2. 时间对齐失败 → 单段 + `alignment_conflict`；
  3. 代理 bar 不足 → 不产出校正，落回既有 proxy 链（`qdii_correction=null`）；
  4. 首测不达标（§4.4）→ 产线回退单段 + `first_test_failed`；双段代码保留研究开关（复评暂态，见下）。
- **开关与裁决（v3.1/R-5 暂态化）**：`data/qdii_correction.json` `{enabled:bool, decided_at, reason, next_review_date, last_review:{dual_mae, single_mae, gap_pp, n_matched_days}}`；默认 `enabled=true` 待首测；**首测判定门槛 = 40 个可配对日窗且 n_test≥20**（未达门槛挂档观察，不得宣布首测失败）；回退为**暂态**——预注册 `next_review_date`（每 20 可配对日复评 + 隔夜源变更即复评）；回退结论必须带数字（单段实测 MAE + 与 1.50%/1.00% 目标差距）；首测/复评与 `alignment_conflict` 事件落 `data/review/qdii_review.jsonl`（INSERT-ONLY）。
- **对齐误杀统计（v3.1）**：`alignment_conflict` 触发即向 `qdii_review.jsonl` 追加事件行（`kind:"alignment_conflict"`，含 code / domestic_date / overseas_trade_date）；40 日窗内 ≥5 次 → 人工复核参照源是否误杀（参照可得却被对齐拒绝）。
- **参照指数**：`estimator.overseas_ref_quote(market)` 为新增适配器；market ∈ {`US_NDX`,`HK_HSI`}；符号映射由后端实测确认（腾讯行情），探测失败即回退——**不得编造行情**。
- 范围限定：024239/016665/012922（纳指系）、457001/021662（恒生系）、163208（油气，参照可得则做）；其余基金零变更。

#### 3.4 估值历史跨日留存（R2-05）
```
archive_daily(date):
  if exists(daily/valuation-{date}.jsonl): return   # 幂等：一文件一快照日
  rows = for each holding: 当日最终记录（收敛为每基金 1 行）
         {date, code, valuation_mode, change_rate, estimated_nav, nav_date, written_at}
  write_jsonl_once(daily/valuation-{date}.jsonl)    # 写完只读；不重写
```
- 触发：收盘后（`trade_session ∈ {closed, non_trading_day}`）由 `maintain_nav_history` 与 `refresh_valuation` 双触发（幂等）；盘中不写。
- 保留策略：全量保留（22 行/日，≤10KB/日，量级可忽略）；**≥40 交易日为可查询下限**由读取侧保证（不足按实给 `window_filled_days`）；文件不可写 → 启动告警（health note），不阻塞估值链。
- 跨日 MAE 序列可复算：`daily/*.jsonl` + `nav_store` → §3.1 的同一公式，QA 可逐日核对。

#### 3.5 预算实现（T-01 处置：**实现**，删死代码）
- `refresh_all`：`t0` 起算，超过 `TOTAL_BUDGET_SEC(20s)` 且非 force → **停止**继续估值；已入账记录保留；跳过持仓读取回退旧缓存，无缓存者 `unknown + conf_reason=budget_exceeded`；snapshot 附 `budget:{exceeded, processed, skipped}`；`record_source`/server 日志记一条 warn。
- force 刷新（启动/手动任务）不受限，保持"打开即有数据"。

### 4. 覆盖扩容（R2-06/07/08；R2-04 复核并入 §4.4）

#### 4.1 C→B 验证批次（`verify_tiers` 任务，R2-06）
```
verify_tiers(targets=默认 C 档 7 只, batch_id):
  for code in targets:
      bars = get_bars(proxy_of(code))              # 既有缓存，零新数据
      sc = factor_engine.evaluate_production({code: bars}, frozen_params())
      verdict:
        indep = sc.independent_trigger_days
        if indep < 20:            → 挂档观察（维持 C + 复查日 = 证据就绪日 +30 交易日；v3.1/D-4 统一口径）
        elif lift_full>=1.0 and delta_full>=0: → 升 B
        else:                     → 降 D（附原因，verify_status=validation_failed）
      write tier_reviews.jsonl（INSERT-ONLY：证据含六窗 lift/Δ/独立触发日/样本）
  holdings.apply_tier_reviews()                    # tier/tier_reason/verify_* 幂等更新
  coverage.prediction_coverage_note 随新档位刷新（(15+k)/22 按实计）
```
- 判据以 **full 窗** 为主（六窗证据全量落盘供复核）；低样本保护 `独立触发日<20` 优先于数值判据（防小样本翻盘，pre-mortem P3）。
- **防稀释闸（v3.1/D-4）**：>3 只同时处于挂档 → 触发架构×PM 复审并落 10-r2 纪要（视为验证批次设计异常）；挂档行不得计入「已验证/预测覆盖增长」，不进 universe；复查日在行内 tooltip 与覆盖面板「待结论清单」（`pending_verification_names`）展示。
- 验收：7/7 出结论（硬指标）；升 B 者进入预测 universe（`fund_predict.run_predictions` 的 tier 过滤自动生效）；60 交易日观察开口。

#### 4.2 影子盘按现档位重算（R2-07）
```
recompute_shadow_window():
  window, records = compute_shadow_window()        # 现有走前引擎，按"现档位"筛资产（自动）
  with lock:
      existing = read_signals_raw()
      archive_all(existing, reason="recompute_by_current_tier")   # 旧记录全量归档（先归档）
      # created_at 继承：对 (date,code) 在 existing 中者复用其 created_at（幂等稳定）
      _write_all_signals(records_with_inherited_created_at)
```
- 幂等断言：重复执行后行的 `(date,code,gate,p_up,ddsm_state,veto_crowd,veto_klow2,signal,opened,created_at)` 集合不变；`_manifest.jsonl` 追加每次重算记录（v3.1/N-4：含**差异摘要**——新增/移除条数、最早/最晚日期）。
- 一致性断言：重算后「台账档位 vs 现持仓档位」0 冲突（C/D 记录清出；升 B 记录按 B 重生成）。
- 触发：`POST /tasks {type:"backfill_ledger", params:{"mode":"recompute"}}`；建议顺序在 `verify_tiers` 之后执行（§7.4）。

#### 4.3 开口低频口径（R2-08）
- `fund_predict.signal_state` 增：`rolling_open_assets`（滚动 **60** 交易日触发 E1/E3 的资产去重数，v3.2 随窗更新）、`rolling_window_days=60`、`low_frequency_note`（文案与基线由 PM 按 60 日重定；原「约 11 资产/20 交易日」不再适用）。
- 数据源：台账合并集（含归档）；窗口按监控资产代理 K 线日期并集。

#### 4.4 R2-04 代理复核批次 + 首测不达标边界（ISSUE-ZL-R2-04 裁定落地）
- **复核批次**：`verify_tiers(targets=9 只超标清单)`，逐只出结论：**保留 / 换代理 / 明示降档**；换代理=更新 `PROXY_MAP` 后重跑本批次该只；025857/163208/014320 若换代理后方向命中率 ≥60% 且 Δ≥0 → 保留（B 或 C→B）；否则降档（见下）且 `tier_reason` 回填、覆盖面板可见。**证据来源（v3.1/D-2(a)）**：方向命中率 / MAE 判据取自**代理质量重建证据道**（§3.1b，`proxy_quality.json`），**不取自展示通道**（`accuracy.json`）。
- **挂档 vs 降档边界（冻结）**：见 10-arch-review-r2 v2 §2.4 的三段表（样本门槛 → 回退口径 → 降档），后端按该表实现判定函数 `review_verdict(evidence, samples)`；一票否决项（代理断供/映射失效）直接回退或降档，不等样本；挂档复查日统一 **+30 交易日（自证据就绪日起算）**，到期强制进入升/降判定。

### 5. 准确率出数（R2-11/12/13/14）

#### 5.1 `/review/scores` 真实化（R2-11；新模块 `review.py`）
- `review.py` 深模块：`scores(data_kind) -> {scores[], hero, note}`（唯一对外函数）。
  - `backtest`：读 `data/snapshot/review_scores.json` 缓存；缓存由 `factor_engine.evaluate_production`（全部 A/B 代理 bars）生成，写入时机 = warmup + `run_backtest` 任务；**同一 bars + frozen_config + seed → 结果可复现**。
  - `shadow_live`：从台账合并集算 T1 命中率 vs **实测基线**；T1 有数据、T3/T15 未回填则 `pending`。
  - `hero` = T1 窗（出数时）：`{window,hit_rate,baseline_rate,delta_pp,open_count,sample_period,data_kind,label}`。
- 未接通窗口 `baseline_status=pending` + 数值 null（**禁止估计值**）；回测/实盘由 `data_kind` 区分。
- 实现落点：`app.py#h_review_scores` 改薄（调 review.py）；`factor_engine.production_definition()` 内置因子 id `production`（`_builtin` 机制扩展）。

#### 5.2 t1_real 自动回填（R2-12；口径 = 代理日线）
```
backfill_due(today):
  merged = read_signals_raw()
  for e in merged where 未齐备(t1/t3/t15):
      bars = get_bars(proxy_of(e.code))
      i = index_of(bars, e.date); if i is None: continue        # 标的日线缺失 → 保持"数据缺失待补"
      for H in (1,3,15):
          if e.t{H}_real 缺 and i+H < len(bars):
              t{H}_real = bars[i+H].close / bars[i].close - 1    # ★代理涨跌口径（ADR-0008）
  write_backfill(entries, method="proxy_bar", proxy_code=proxy)   # 独立文件、只写 t*_real、INSERT-ONLY；v3.1/R-1 记复算锚
```
- 幂等：已存在的 `t*_real` 不再写（避免重复行）；无对应 signal 拒绝写入（沿用 E_VALIDATION）。
- **复算锚（v3.1/R-1）**：每行回填记 `proxy_code`（回填时映射）；换代理事件写 `tier_reviews.jsonl`——换代理后以「回填时映射」复算，避免按新映射复算得出不同结果。
- 触发：启动 warmup + 每日收盘后（`maintain_nav_history` 内）+ `backfill_ledger` 任务；失败只影响自身批次，已写不回滚。
- 验收复算：`t1_real` 必须等于代理日线可复现值；口径文案由 `backfill_method_note` 直出。

#### 5.3 20/60 矛盾解除（R2-13；归档合并）
- `shadow_progress`：`consecutive_days`/`gap_days` 数据集 = 主文件 ∪ `archive/shadow_signals_archive.jsonl`（去重）；`history_days` = 合并日数；`archive_merged` = 归档可读且非空；归档缺失 → 降级为主文件计算 + `note` 标注（不伪造天数）。
- 阈值不变：60 日门槛；`qualified` 在合并口径下可达（v3.2：窗口=60 后**启动回填满即达**；文案须按走前回算口径诚实表述，见 10-r2 §13.3——`qualified`= 记录窗完整度，非上线资格）。

#### 5.4 基线实测化（R2-14）
- 删除 `ledger_api.BASELINE_RATE`；新增 `measured_baseline(rows)`：`baseline = max(Σ[t1_real>0]/N, Σ[t1_real<0]/N)`，N=全部有 t1_real 的行；N=0 → null（**不填 0.5830**）。
- `shadow_progress` / `shadow_ledger.summary` / `shadow_audit` 全改实测值 + `baseline_source="measured"`；`engine.frozen_params` 增 `baseline_method`；`FROZEN_PARAM_KEYS` 黑名单增 `baseline_method`（app.py）。
- 断言：产线代码与运行数据 `0.5830` 零引用（grep）；`deviation_pp` 可复算。

#### 5.5 影子盘窗口 60 设计核验（v3.2 追加 · 2026-09-13；用户指令）
- **常量与引用**：`ledger_api.SHADOW_WINDOW_DAYS=60`（唯一源）；`app.py` 三处引用（271/284/1374）统一走常量；`fund_predict.py:376/390` 默认回退改 60（建议引用常量，消灭第二真相源）。
- **回填与滚动**：启动 warmup 回填 **60 交易日**（走前 `bars[:t-1]` 逐点）；此后每日滚动：新增最新 1 日 + 裁剪最旧 1 日（15 资产量级 → `written≈15 / trimmed≈15`/日）；更早记录由归档承接（`first_of_day_immutable_full_archive` 不变）。
- **计算量（评估）**：≈900 次走前单点训练 ≈**15–17s CPU**（启动首跑一次性；线性外推自 20 日窗 300 次/5.5s，`14-api-impl-report-r2` §10.2）；主文件 ≈900 行（≤~0.3MB，量级可忽略）。每日滚动若全量重算同量级 → 建议保留存在性快路径，必要时评估**增量模式**（仅算新增日，≈15 次/0.3s）——增量不改变走前口径与幂等断言。
- **幂等与审计**：`(date,code)` 唯一跳过、`created_at` 继承、先归档后重写、`recompute` reason 不变；空表也不得写示例数字（沿用）。
- **冷启动复验**：S3 探针（`ready+1s/+6s` 的 `/holdings` 时延 + warmup 时间戳）在 60 日窗下**复测**；若首跑拉长阻塞窗，按实测决定 chunk/增量。

### 6. 数据源治理（R2-15/16/17/18）

#### 6.1 nav_history 维护（R2-16）
```
maintain_nav_history(hold_list):
  for h in hold_list:                       # 只维护持仓 universe（PRD 不做清单 13）
      points = estimator.lsjz_history(code) # 分页（pageIndex 递增，止于空页/250 点）
      upsert nav_store[code].points         # 按 date 去重；既有日期不覆盖（首值冻结）；新增追加
      save nav_store atomic
  build_accuracy_v2(hold_list)              # §3.1（净值就绪后重算）
  archive_daily(yesterday_or_today)         # §3.4
```
- 幂等：重复执行 points 集不变；接口失败保留已有 + 标注滞后（不编造净值）。
- `/runtime.staleness` 与 `nav_of` 已读实时缓存（R1 v5 已做），R2 把 **历史全量**补至最新；`build_accuracy` 样本从 n_test=7 → ≥40。

#### 6.2 持仓主源切换（R2-15）
- `holdings.ensure_holdings`：`data/holdings.json` 存在即主源（既有行为成文）；缺失且外部导入源不可用 → 返回空态（可读提示），**不再抛 E_IO 堆栈**。
- `import_from_source`：保留 CSV/手工 CRUD 能力；`/settings/holdings-data` 输出主源/导入源双口径（§3.11 契约）；导入按钮禁用逻辑由 `import_available` 驱动（前端）。
- `holdings.json` 字段保持向后兼容；`nav_history` 标记为 legacy（权威源 = §6.1 nav_store）。

#### 6.3 新浪源定案（R2-17；ISSUE-ZL-R2-03 裁定：**(a) 启用，限缩为兜底**）
- 接线两处：① 档4 proxy 实时：腾讯 `tencent_rt_quote` 失败 → `sina_rt_quote(proxy)` 兜底；② 重仓个股批量：`tencent_rt_quotes` 失败 → `sina_rt_quotes` 批量兜底（仅 6 位 A 股）。
- 纪律：不做主源、不替换腾讯；单请求 5s 超时、重试 0（防双重超时拖垮预算）；每次调用 `record_source("sina_rt", ...)` 留痕（健康页三态 + 时间戳自然满足）。
- 失败回退静默（不阻塞估值链）：新浪也失败 → 落既有降级（日线/Gray）。
- 若 sina 实测长期不可用 → 按 (b) 标注降级（健康页 note"仅探测·非主链"）——由后端实测决定，结论回填健康页。

#### 6.4 fail_count 事件日志（R2-18）
- `record_source`：成功/失败均追加 `health-log.jsonl`（append-only）；`fail_window_7d` = 近 7 日中 `ok=false` 事件数；`recent_failures` = 最近 ≤10 条失败事件；成功不抹除窗口内历史（按时间窗自然滚动），`fail_count` 保留为累计（审计）。
- 启动时一次性迁移：旧 `health.json` 的 `fail_count` 保留显示为累计值（不得再作为当前状态）。

### 7. 任务与启动序列变更

#### 7.1 任务
- 新增 `maintain_nav_history`（§6.1）与 `verify_tiers`（§4.1/§4.4）。
- `backfill_ledger`：增 `mode=incremental|recompute`；`incremental` 内联 `backfill_due`（§5.2）。

#### 7.2 启动 warmup 序列（调整后，保持"打开即有数据"）
```
run_predictions → maintain_nav_history(净值史+accuracy v2+日留档)
→ refresh_fund_valuation(force) → refresh_official_nav → refresh_all(force)
→ backfill_ledger[incremental]（滚动窗口 + t*_real 回填）
→ refresh_penetrations → ensure_adopted_pan → review.scores 缓存生成
```

#### 7.3 依赖顺序与失败回退（T1 缓解；ISSUE-ZL-R2-02）
```
R2-16(nav) ─┬→ R2-05(留档，日积) ─→ R2-01(通道) ─┬→ R2-02(前20/HK) ─┐
            └─────────────────────────────────────┴→ R2-03(QDII 双段) ┴→ R2-04(9 只收口)
R2-12(回填) ─┬→ R2-22(UI 回填态) ─→ R2-19(成绩位)
             └→ R2-14(实测基线) ─→ R2-19
R2-06(C→B) ─→ R2-07(重算) ─→ R2-24(UI) ；R2-11 独立（R2-14 后口径一致）
```
- 失败回退：nav 断 → 通道保持 unknown + `nav_missing`（不静默）；回填断 → UI 保持"待回填"；**展示通道延迟 → 徽章保持 unknown+reason（不静默），R2-04 不受阻——其首选证据为 §3.1b 重建证据道（D-2）**。

#### 7.4 R2-04 排期（ISSUE-ZL-R2-02 裁定）
- **前置可提前**：证据模板、现有 proxy 档证据收集、六窗 lift 复跑可先做。
- **结论必须收口（v3.1/D-2 修订）**：R2-04 首选证据 = **代理质量重建证据道**（§3.1b：nav 史就绪后立即可重建，绕开展示通道 8 周积累）；展示通道（R2-01）只影响徽章成熟度，不影响代理能否被判；**收口硬约束：9/9 结论不晚于 G-PM-05 终验**，超窗须 PM×架构联合延期说明，未收口资产按 §4.4 层①挂档（带复查日与样本量），否则按未完成计。
- **G2-01 双时点（v3.1/D-2b）**：首判 = 满 5 个可配对日（`window_phase=first_verdict`）；终判 = 满 40 个可配对日（`window_phase=mature`）。

### 8. 冻结纪律与红线核对（R2 不触碰项）

| 红线 | R2 状态 |
|---|---|
| E2/E4 禁复活、禁 OR 合并 | 未实现、未提及（门仍 E1/E3） |
| DDSM 冻结参数 K=4/p=0.25/MIN_N=15/SHRINK=10 | 只读展示；`frozen_params` 未改值 |
| BAND=0.02（出口 0.52）、双否决分位 0.60/0.40 | 未改 |
| 永不做空 | 未触碰（无 down 分支） |
| INSERT-ONLY 台账 | 保持；(date,code) 唯一、回填独立文件；recompute=先归档后重生成 |
| 组合权重 = 可信市值 | 未触碰（weighting_basis 恒 market_value） |
| T+3/T+15 未验证不出 up | 未触碰 |
| `0.5830` | 退役（§5.4） |

### 9. 技术债处置

| # | 项 | R2 处置 | 落点 |
|---|---|---|---|
| T-01 | TOTAL_BUDGET_SEC 空转 | **实现**（删 `pass` 死代码） | §3.5 |
| T-05 | 两份 F10 解析器 | **合一**（estimator 版为唯一实现） | §3.2 |
| T-02 | bars 无主缓存清理 | 延后（R3 候选） | 不变 |
| T-03 | DDSM 重训缓存 | 延后（本地可容忍） | 不变 |
| T-04 | GATE_EFFECT 复算 | 延后（样本不足） | 不变 |
| 新增 | `valuation_history.jsonl` 增速 | 日留档分离（§3.4）+ 体积评估（≤10KB/日，R2 末复核） | §3.4 |

### 10. 测试要求（backend 新增用例，命名供 QA/契约测试）

| 测试文件（建议） | 断言要点 |
|---|---|
| `test_accuracy_channel.py` | 全档 `mode\|code`；**同 mode 当日最后一条**为评分对象（D-3）；n<5 → `no_samples`；官方档 nav_date<D 参与评分；`conf_reason` 按序命中即停（R-4） |
| `test_qdii_correction.py` | 加法拼接 = change_rate；对齐失败/隔夜缺失回退 + reason；`applied=true` 时 fallback null |
| `test_proxy_quality.py` | 证据道重建（bars×nav）；与展示通道分键分文件；MAE/方向命中率/n_test 可复算（D-2） |
| `test_qdii_review.py` | 首测门槛 n_test≥20 未达 → 挂档；复评日预注册与触发；alignment_conflict 计数及 ≥5 复核（R-5） |
| `test_nav_history_contract.py` | lsjz 分页幂等；既有日期不覆盖；失败保留旧值 |
| `test_backfill_real.py` | 到期写 `t*_real` + `method=proxy_bar` + `proxy_code`（R-1）；重复不重写；无 signal 仍 `E_VALIDATION` |
| `test_shadow_recompute.py` | 先归档后重生成；`created_at` 继承；重复执行集合不变；档位一致性 0 冲突 |
| `test_shadow_progress_archive.py` | 合并集 `consecutive_days` 可 ≥60（v3.2 窗=60；启动回填满即达）；归档缺失降级标注 `archive_merged=false` |
| `test_baseline_measured.py` | 实测公式；N=0 → null；`0.5830` 零引用 |
| `test_review_scores.py` | hero 出数结构；pending 窗口 null；`data_kind` 透出；缓存可重建 |
| `test_health_window.py` | `fail_window_7d` 窗滚动；成功不改窗口内计数；`recent_failures` ≤10 |
| `test_holdings_main_source.py` | `main_source` 口径；`import_available=false` 时禁用路径 |
| `test_sina_fallback.py` | 腾讯失败注入 → 新浪兜底调用；双失败 → 既有降级 |
| `test_tier_review.py` | 三种 verdict 判定；低样本挂档（复查日 +30 交易日、自证据就绪起算）；>3 只挂档复审触发；降档 `tier_reason` 回填；挂档行不进 universe（D-4） |
| `test_f10_top20.py` | `top_n=20`；5 位港股码解析；`excluded_count` 如实 |

## 自验收

- [x] 四目标数据流、模块级变更逐项落点（§1/§3/§4/§5/§6），未变部分声明沿用 R1 v5
- [x] 四项 open-issues 全部落实现口径：QDII 双段（§3.3）/ 排期（§7.3-7.4）/ 新浪（§6.3）/ 挂档降档（§4.4）
- [x] 模块接口为深模块风格：`review.scores` / `build_accuracy_v2` / `qdii_estimate` / `recompute_shadow_window` 单一对外入口
- [x] 不新增层、不引依赖、Python 3.8+ 安全（伪代码仅用标准库语义）
- [x] 冻结纪律逐条核对（§8）；E2/E4 未复活、永不做空、DDSM 参数未动、INSERT-ONLY 语义保持
- [x] `0.5830` 退役路径明确（§5.4 + 断言）；基线进冻结参数表（`baseline_method`）
- [x] 数值验收可复算（置信度/覆盖/Δ）与 09 §6 对齐；回填口径=代理日线成文（ADR-0008）
- [x] T-01 实现、T-05 合一、T-02/03/04 延后留痕（§9）
- [x] **v3.1 会签收敛**：D-2 证据道（§3.1b）/ D-3 评分对象（§3.1）/ R-5 门槛与复评（§3.3）/ D-4 复查日与防稀释闸（§4.1）/ N-4 差异摘要（§4.2）/ R-1 复算锚（§5.2）/ D-2(c) 收口约束（§7.4）逐条落文
- [x] **v3.2**：影子盘窗口 60 注记（§5.5）——常量/回填深度/每日滚动/计算量（≈15–17s）/幂等/冷启动复验逐条落文；§4.3/§5.3/§10 同步
- [x] 未写可运行代码；未修改 R1 既有工件；未触碰 `runtime/**`

## 下游交接

- **主消费方**：`backend-dev`。按 §3~§6 落模块；契约字段严格对齐 `09-api-contract-r2.md` **v9.1**（G-BE-02 红线：字段名不一致 FAIL）；冻结参数与 INSERT-ONLY 逐字保持。**建议实现顺序**：§6.1 nav → §3.1b 证据道 + §3.1 通道 → §5.2 回填（含 R-1 锚）→ §3.4 留档 → §3.2/§3.3 估值升级（含 QDII 门槛）→ §4/§5 `verify_tiers`/`review`。
- **次消费方**：`dev-lead`（G-BE-01 冒烟：起服 + 四目标各一条链路 + §10 用例跑通）、`qa`（§10 用例 + 负向断言）、`frontend-dev`（字段消费见 09 §7 消费点列）。
- **残留风险**（责任人 / 期限）：
  1. 隔夜参照指数符号未实测（腾讯美股/港股指数）→ 探测失败即回退单段（backend-dev，S3 首日）。
  2. `recompute` 的 `created_at` 继承规则依赖归档完整性 → 归档不可读时中止重算并告警，不半写（backend-dev，S3）。
  3. R2-06 verdict 阈值为架构口径（lift≥1.0 且 Δ≥0 且独立触发日≥20）→ 若首批实测显示误杀/误放，走 10-arch-review 复议（architect，S5 前）。
  4. 日留档与 `valuation_history.jsonl` 双写体积 → R2 末复核（backend-dev + architect，S5）。
- **未覆盖**：前端组件与交互（`07-frontend-arch-r2`）、系统五问（`06-system-arch-r2`）、产品能力视图（`05-product-arch-r2`）、会签问题（`10-arch-review-r2`）。
