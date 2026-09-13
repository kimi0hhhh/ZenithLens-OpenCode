---
artifact: 00-dissection-v3
owner: general-explorer
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [product-manager]
gate: —
note: R2 升级轮现状解剖（研究工件，不承担门禁，交产品经理吸收）；全部数字为 2026-09-12 只读实测，台账与数据零改动
---

# 极境 ZenithLens · R2 解剖报告（现状基线）

## 摘要

本报告对极境 ZenithLens R1 交付版（代码根 `C:\Users\10719\Documents\ZenithLens-OpenCode\`）做全面只读解剖，作为 R2 四大目标（实时预估值更准 / 预测开口日覆盖更多 / 分析准确率更高 / 来源更可靠）的需求输入件。

**一句话总结论**：工程骨架与诚实纪律优秀（117 契约测试全绿、55 接口、五档估值链、INSERT-ONLY 台账、D 档压到 0），但**四大 R2 目标在现状上各有一个明确的「堵点」**——估值不准的堵点是置信度体系与档位脱节（22/22 全 unknown）+ 9 只代理 MAE 超标；覆盖不足的堵点是 C 档 7 只未验证 + up 出口极低频（20 日仅 4 条）；准确率无值的堵点是影子盘零回填（backfill.jsonl 0 行）+ 复盘页硬编码 null + 回测机制齐备但未接通；来源可靠性的堵点是桌面数据根已断链（PRIMARY 不存在，靠 data/holdings.json 存量 + 东财实时缓存续命）。另发现一处**结构性矛盾**：影子盘滚动窗口 20 日封顶，而上线资格要求连续 60 日——按现状永远无法达标。

**四目标现状基线速览**（详据见正文）：

| R2 目标 | 现状基线值 | 主要堵点 |
|---|---|---|
| A 估值更准 | 盘后 22 只：official 17 / holdings 5 / intraday 0 / proxy 0 / unknown 0；proxy 口径 40 日窗 MAE 均值 0.80%（中位 0.49%）、9 只超行业基准 0.8%（max 2.40%）；**置信度 22/22 全 unknown** | accuracy.json 只有 `proxy|code` 键，official/holdings 档无误差通道 |
| B 覆盖更多 | 预测覆盖 15/22（A2+B13）；台账 16 资产/20 交易日；开口 11 资产/13 日/E1×25+E3×32 行次；up 出口 4 条（全部黄金 518880 代理） | C 档 7 只待验证；6 只 A/B 资产 20 日内零开口 |
| C 准确率 | **T+1 Δ vs 基线 = 无值（实测确认）**；backfill.jsonl 0 行、320 条台账零 t1_real；复盘页 hero 全「—」；若按代理 T+1 离线复算 4 条 up = 4 hit（样本不足） | 回填未接；复盘页硬编码 null；基线 0.5830 是拍脑袋常量非实测 |
| D 来源可靠 | 4 数据源（腾讯日K/腾讯实时/东财/新浪-仅探测）；**桌面 funds_data.json 不存在（实测）**；现读 data/holdings.json（09-12 01:45 导入）+ 东财实时缓存；nav_history 滞后至 08-25（18 天） | 源数据根单点断链；eastmoney 历史失败 544 次不衰减 |

## 正文

### A. 实时估值链：代码路径、档位分布、误差实测

#### A1. 五档降级链实现路径与触发条件（valuation.py:327 `value_fund`）

执行顺序 official → intraday → holdings → proxy → unknown，每步留 trace（`{mode, tried, hit, reason}`）：

| 档 | 数据路径 | 触发条件（代码口径） |
|---|---|---|
| 1 official | `estimator.get_official_nav`（天天基金 FundValuationLast → lsjz（pageSize=2，24h 缓存）→ pingzhongdata 末位回退） | **非主动基金**：官方净值非空且（非盘中 或 nav_date==今日）即命中；**主动基金**：仅 nav_date==今日才命中，否则让位重仓加权 |
| 2 intraday | FundValuationLast 的 GSZ/GSZZL（盘中估算净值，90s TTL 缓存） | 仅**非主动基金**且 `trade_session()=="trading"`（A 股 09:30–15:00，周末/收盘后一律不产出） |
| 3 holdings | `estimator.eastmoney_top_holdings`（F10 前十持仓 HTML，30 天缓存）+ `tencent_rt_quotes` 批量个股实时 → `_weighted_holdings`：Σ(wᵢ×chgᵢ)/Σwᵢ，weight 或 day_change 任一为 null 即剔除该股不编造 | 仅**主动基金**（`fund_type=active`，`classify_fund_type` 按名称关键字：混合/股票/灵活 且非指数/QDII）；前十不可得回退 proxy |
| 4 proxy | 代理 ETF 腾讯实时 `qt.gtimg.cn`；实时失败回退日线（`bars[-1].date==今日` 时用收盘比） | 有 `proxy_code` 即可（指数联接/QDII 主口径 + 主动基金兜底）；无映射 → no_mapping |
| 5 unknown | — | 全链无数据，`change_rate=null`（禁止 +0.00% 冒充，契约 §1.2） |

资金类型分流（estimator.py:110）：22 只实测 fund_type = active 5（025500/018957/021528/013566/014320）/ index_link 11 / qdii 6。估值锚点与预测锚点分离（估值用重仓加权，预测仍用代理 ETF 日线）。

#### A2. 22 只基金当前各走哪档（data/snapshot/valuation.json，2026-09-12 18:51 收盘后快照）

- **official 17 只**（盘后官方净值已出）：024239/025857/017193/016786/457001/014881/163208/018897/022485/011840/008087/017412/016665/012922/021662/000217/002963
- **holdings 5 只**（全部 active 主动基金）：025500（chg −2.73%）/ 018957（+1.25%）/ 021528（+2.47%）/ 013566（−1.67%）/ 014320（−2.29%）
- intraday 0 / proxy 0 / unknown 0（该时刻点全部有值）
- 当日 valuation_history.jsonl 累计 968 行（同日多轮刷新追加，INSERT-ONLY 允许）：official 354 / unknown 368 / proxy 204 / intraday 22 / holdings 20——盘中时段部分基金曾走 intraday/proxy/unknown，晚上官方净值齐后收敛到 official/holdings。**历史只有 2026-09-12 一天的估值记录，无跨日误差序列。**

#### A3. 估值误差实测（data/snapshot/accuracy.json）

`build_accuracy`（valuation.py:196）只对 **proxy 档**回测：代理 ETF 日线涨跌 vs nav_history 真实净值涨跌，40 日窗。22 只实测（每只 n_test=7 个可配对净值日——受 nav_history 滞后 18 天限制样本很短）：

- MAE：min 0.13% / max 2.40% / **mean 0.80%（恰压行业基准线）/ median 0.49%**
- **超行业基准 0.8% 共 9 只**：025500 / 024239 / 025857 / 457001 / 163208 / 014320 / 016665 / 012922 / 021662
- 方向命中率 mean 83.77%，**<60% 的 3 只：025857（42.86%）/ 163208（42.86%）/ 014320（57.14%）**——这三只代理连方向都常错
- n_test=7 意味着这是极小样本估计，置信区间宽

#### A4. 哪里不准、为什么不准

1. **置信度体系与档位脱节（全站失效）**：`_confidence_of(mode, code)` 按 `"{mode}|{code}"` 键查 accuracy.json，而 accuracy.json 只有 `proxy|code` 键。当前 22 只走 official/holdings 档 → 全部查不到 → **实测 22/22 confidence=unknown、mae_rate=null**，徽章全站显示灰色虚线「无可信估算」，估值精度汇总条（vsum）无市值加权 MAE 可显示（weighted_mae_rate=null）。估值误差数据存在（proxy 口径）但没有接进当前档位。
2. **主动基金重仓加权的固有误差**：F10 前十持仓是**季度披露**（30 天缓存，实际滞后 1 个季度），前十权重合计通常仅 40–60% 净值，剩余持仓贡献不可见；个股实时用腾讯 A 股行情，港股/美股标的剔除（day_change=null）进一步缩覆盖。
3. **QDII 跨市场代理误差**：024239（纳指代理）MAE 2.19%、457001/021662（恒生代理）MAE 1.23%——境内 ETF 与场外 QDII 净值有确认时滞与汇率差；brief §5.3 指出 QDII 境内价格领先净值 1–2 天（信息优势），但估值口径未利用该时差做校正。
4. **低方向命中代理**：025857（电力）、163208（油气）方向命中率 42.86%——比抛硬币还差，代理质量本身不合格，但仍以 C/B 档在用。

#### A5. R2 升级建议要点

1. **打通置信度**：为 official/holdings 档建立误差通道——当日估值落账后，T+1 官方净值公布时回算当日误差，按 `mode|code` 键日累计 MAE（holdings/official 档的估值历史已在 valuation_history.jsonl 逐日追加，只差回算器）。
2. **重仓加权升级**：前十大 → 前二十大（F10 topline=20），港股/美股纳入实时源（腾讯港股 qt.gtimg.cn 已支持，estimator 只过滤了非 6 位 A 股代码）；季报披露滞后在徽章 tooltip 明示。
3. **QDII 时差校正**：对 QDII 用「境内 ETF T 日收盘 + 隔夜美股 T−1→T 收益修正」双段估算，可显著降 024239 一类 2%+ 的 MAE。
4. **代理复核**：9 只 MAE 超标的代理逐一走前验证（尤其方向命中率 <60% 的 025857/163208），换代理或明示降档；025857 已是 B 档但误差不合格，验证不过应降 C。
5. **估值历史跨日积累**：valuation_history 目前仅 1 天，R2 起每日快照自动留档，支撑跨日 MAE 与「估值 vs 净值」偏差审计（设置页长文承诺的 0.73% 实证口径才能落地）。

---

### B. 预测开口日覆盖：台账实测与扩容路径

#### B1. shadow_signals.jsonl 实测（只读统计，2026-09-12）

- **总量**：320 行 / **16 资产** / **20 个交易日**（2026-08-17 ~ 2026-09-11，滚动窗口 20 日，ledger_api.SHADOW_WINDOW_DAYS=20；启动 warmup + backfill_ledger 任务自动生成，走前 purge：训练集截断 bars[:t-1]）
- **signal 分布**：gray 292 / abstain 24 / **up 4**
- **gate 分布**：E1 25 / E3 7 / none 288 → **开口（E1/E3 触发）32 行次，覆盖 11 资产、13 个交易日**（约 10% 的资产-日组合开口）
- **up 出口 4 条**：全部是黄金（000217/002963 华安/易方达黄金联接，同代理 518880），2026-08-17（p=0.5688）与 2026-08-20（p=0.6808）各 2 条——开口 32 次中仅 4 次过出口（12.5%），双否决 + P>0.52 门槛很严
- 逐资产开口次数：000217×6 / 002963×6 / 017193×4 / 024239×3 / 016665×3 / 012922×3 / 008087×2 / 014320×2 / 014881×1 / 018897×1 / 017412×1

#### B2. 哪些基金从未有信号、为什么

- **预测入口本身只放行 A/B 档**（fund_predict.py:209 `if h.get("tier") not in ("A","B"): continue`）→ 当前 A+B=15 只；ledger_api._proxy_assets 同口径。
- **从无台账记录的 6 只**：025500 / 018957 / 021528 / 457001 / 021662 / 163208——全部是 **C 档**（穿透成功待验证的 2 只主动 + 3 只 QDII + 1 只油气）。原因 = 代理映射置信度未验证，非行情缺失（457001/163208 的代理 159920/162411 日线缓存都有 320 根）。
- **有记录但 20 日零开口的 5 只 A/B**：011840（AI）/ 013566（军工）/ 014881（机器人）/ 016786（中证1000）/ 017412（科创创业50）——E1/E3 触发门在这些标的上 20 日未发生，属事件低频常态，非故障。
- 台账有一处**历史遗留**：022485（A500，现 C 档）有 20 行 gray 记录——生成时其档位与现值不同；说明台账口径随 holdings 档位漂移，未做一致性重算。
- retro 所称 F-PM-01「22/22 → 实际 10/22」的口径基线已演进：当前代码 `holdings_summary.covered_count` 已按 `change_rate != null` 统计（fund_predict.py:546，修法已落地），今日恰 22/22 全有可信估值、非虚报；但**预测覆盖仍是 15/22（A/B），估值覆盖 ≠ 预测覆盖**，两口径不能互替。

#### B3. 覆盖从 10/22 扩到更多的技术可行性路径

R1 期间已从「前端 10 只按 A 档、12 只记 D」扩到 A2/B13/C7/D0（proxy_map 22 只全映射 + 2 只主动穿透成功升 C，契约 v8）。剩余扩容路径按可行性排序：

1. **C 档 7 只走前验证 → 升 B**（零新数据需求）：022485/457001/021662/163208 的代理 ETF 日线已在 bars 缓存（320 根），025500/021528 穿透主代理 512480/515880 也有；用 factor_engine 的六窗走前回测即可出 lift/Δ 证据。验证通过 7 只全升 B → 预测覆盖 15→22（100%）。
2. **触发面不变、扩资产是主路径**：E1/E3 是低频事件门（brief §5.1 冻结，E2/E4 已证伪禁止 OR 合并），单资产开口率 ~10% 资产-日；扩 7 只 C 档后开口资产-日约 +70%。
3. **出口灵敏度**（须过方法论六关）：up/开口 = 4/32（12.5%），20 日仅黄金过出口。BAND=0.02 是冻结参数，R2 可评估 exit_threshold 或双否决分位的走前 sensitivity，但改动须重走六关（冻结纪律，engine.frozen_params change_policy）。
4. **QDII T+2 信息优势**（brief §5.3）：513100 已映射 3 只 QDII，开口时点领先净值 1–2 天——在信号页/分析页明示该口径即可提升「可用性感知」，不需新机制。
5. **台账一致性**：022485 遗留记录与当前档位矛盾；R2 重算影子盘时按现档位全量重生成（滚动窗口机制本身就是「最近 20 日重算」，天然支持）。

#### B4. R2 升级建议要点

1. **C→B 验证批次**：对 7 只 C 档代理跑六窗走前验证（lift≥1.0 + Δ≥0 即升 B），预测覆盖 15/22 → 22/22；验证不过的明示降 D 并回填 tier_reason。
2. **影子盘按现档位重算**：rolling_shadow_backfill 幂等重跑即可清理 022485 遗留口径。
3. **开口低频的期望管理**：11 资产/13 交易日开口基线写进 PRD 空态文案（「多数交易日不开口」已有），R2 验收口径用「月度开口资产数」而非「日开口数」。
4. **QDII 领先口径明示**：信号卡加「境内代理领先净值 1–2 天」标注（纯文案，无代码风险）。
5. **出口灵敏度研究项**：评估 BAND 0.02→0.01 与 KLOW2/CROWD 分位微调的走前 Δ（研究性质，产出进 21-factor-governance 机制，不动冻结参数）。

---

### C. 准确率：Δ 有无、回填现状、回测能力

#### C1. T+1 Δ vs 基线：实测确认无值（OBS-01 维持）

- `/review/scores` 后端**硬编码全 null**（app.py:498-514：hit_rate=None、baseline_rate=None、delta_pp=None、baseline_status="pending"，hero label「回测待产出（不填估计值）」）→ 复盘页历史成绩 hero 与三窗口表全部「—」。R1 retro 称无值，本轮从代码 + 界面双侧实测**确认属实**。
- **影子盘回填现状**：`ledger/backfill.jsonl` **0 行**；320 条台账无一条 t1_real（reconciliation 逐笔对账全部「待回填」）；`_hit_rate` 因无样本返回 null；`shadow_audit` 状态 idle（样本不足以评偏差）。
- **离线复算参考**（只读推演，非台账回填）：4 条 up 若按代理 518880 的 T+1 日涨跌回填——08-17→08-18 +0.11%、08-20→08-21 +1.67%，**4/4 hit**；但 4 条样本远不足以支撑 Δ 结论（基线 = max(恒涨,恒跌) 需同期全样本口径）。
- **影子盘进度矛盾（结构性缺陷）**：`SHADOW_WINDOW_DAYS=20`（滚动窗只保留最近 20 日）但 `TARGET_DAYS=60`（上线资格要求连续 60 日无漏单）——`shadow_progress.consecutive_days` 从台账日期回溯，**封顶 20，永远无法到 qualified**。引擎页「连续记录进度 0/60」按此机制不可能走满。

#### C2. 回测能力现状（机制齐备、出口未接）

- **已具备**：factor_engine.evaluate 提供完整六窗走前回测（purge=H+2、holdout 60、独立触发日去重叠、bootstrap 500 零分布、F1/F2/F3）；`_base_fired` 已实现「生产配置（gate+ddsm>0.52+双否决）」的走前逐日信号（供 F3 增量用）——**生产链路本身可作为一个因子送进 evaluate 出六窗 Δ**，能力闭环，只差把结果接回 /review/scores。
- **已产出的真实回测**（adopted_factors.json，2026-09-12 真实回测写入，非示例数字）：
  - KLOW2：六窗 lift 1.07~1.31，m24 窗 hit 59.10% vs 基线 55.13%（Δ +3.97pp），独立触发日 863，牌照 probation、总分 61.05
  - 拥挤度六维 crowd6：六窗 lift 1.00~1.07，m24 Δ +0.62pp，总分 21.40，牌照 none
  - 候选因子 1 条（mom5 突破）verdict=rejected_f3（增量不足，真实回测跑过 F1 pass/F2 pass/F3 fail）
- **口径缺陷**：`BASELINE_RATE = 0.5830` 是硬编码常量（ledger_api.py:30），shadow 偏差评估用它当基线——与 brief 定义的 `max(恒涨, 恒跌)` 实测口径不符；0.583 无实测来源标注。

#### C3. R2 升级建议要点

1. **接通回测 → 复盘页**：把生产配置作为 builtin 因子跑 evaluate（六窗 lift/Δ + bootstrap 置信），回填 /review/scores 的 hero 与三窗口行（data_kind=backtest）；这是 North Star 出数的最快路径，机制零新增。
2. **台账自动回填 t1_real**：rolling_shadow_backfill 对已到期信号从代理日线自动写 backfill.jsonl（INSERT-ONLY 独立文件，契约 §5.10 语义已定义）；上线后复盘页逐笔对账从「待回填」变 hit/miss，命中率自然出数。
3. **解开 20/60 矛盾**：连续记录天数改按「归档 + 主文件」合并计算（archive 已全量留痕，只差 shadow_progress 读 archive），或把窗口扩到 60 日；否则 qualified 永远 false。
4. **基线实测化**：BASELINE_RATE 改为按台账 universe（全部资产-日）的上涨率算 max(恒涨,恒跌)，替换硬编码 0.5830；影子盘偏差评估随之可信。
5. **placebo 与 holdout 纪律沿用**：复盘页 cv-config 已声明（walk_forward/purge=H+2/placebo≥2pp/holdout 60），R2 出数时必须同页展示这些口径，防「漂亮数字无出处」。

---

### D. 来源可靠性：数据源清单、断链实测、徽章驱动

#### D1. 行情/估值数据源清单与失效处理

| 源 | 用途 | 代码位置 | 失效处理 |
|---|---|---|---|
| 腾讯日K web.ifzq.gtimg.cn | 代理 ETF 日线（不复权 + >25% 跳变自修除权）；6h 缓存 | estimator.get_bars | 失败返回空 bars，预测/影子盘如实降级；record_source 留痕 |
| 腾讯实时 qt.gtimg.cn | 代理 ETF 实时（proxy 档）+ 重仓加权个股批量实时 | tencent_rt_quote(s) | 失败回退日线收盘比；缺失代码不入表按 null |
| 天天基金 fundcomapi FundValuationLast | 官方净值 + 盘中估算（批量，90s TTL）；**旧 fundgz JSONP 已于 2026-07-21 下线，已切 H5 新接口** | fetch_fund_valuation | 双 host 容灾（tiantianfunds/eastmoney）；失败回退缓存 |
| 天天基金 lsjz / pingzhongdata | 官方净值补充（24h 缓存）/ 末位回退 | eastmoney_official_nav / eastmoney_pingzhong_nav | 层层回退，全无则 null 不编造 |
| 天天基金 F10 jjcc | 前十持仓 HTML（30 天缓存，需 UA+Referer） | fetch_top_holdings | 失败返回 ([], None) → holdings 档 no_report 回退 proxy |
| 新浪 hq.sinajs.cn | **仅探测，主链未用**（sina_rt_quote 存在但估值链未调用） | sina_rt_quote / probe_source | 无实际消费方 |

健康监控：`settings.record_source` 三态（ok / warn / bad，连续失败 ≥3 → bad）落 data/health.json。实测当前：tencent_kline ok（09-12 18:50）、tencent_rt ok、eastmoney ok（09-12 19:06，**历史 fail_count=544**——fundgz 下线期间的失败累计，恢复后不衰减归零）；sina_rt 无记录（从未被主链使用）。

#### D2. 持仓数据源现状：R1 brief 的数据根已断链

- **实测**：`C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json` **不存在**（PRIMARY 与 .bak 均无）。
- **现在实际从哪读**：`data/holdings.json`（产品自持；2026-09-12 01:45:48 从源文件最后一次成功导入，22 只完整）。启动 `ensure_holdings` 逻辑：holdings.json 存在即直接用，不再依赖源文件；仅当 holdings.json 缺失才尝试 import（会抛 E_IO「源文件不存在」）。
- **断链表现**：①设置页「持仓数据」卡显示 primary_exists=false；②「重新导入」按钮会报错；③每只基金 nav_history 停在 2026-08-25（滞后 18 天）——nav_of 的官方净值走东财实时缓存（lsjz/FundValuationLast）补新，但 nav_history 本体不再更新；`build_accuracy` 的回测样本因此只有 7 个配对日。
- **估值链未受断链影响**（双源冗余生效）：官方净值/盘中估算全部来自东财实时接口与缓存，`staleness.latest_date` 由 `cached_nav_dates` 给真实最新净值日。

#### D3. 估值来源徽章：后端真实驱动（确认无硬编码）

`valBadge`（components.js:77-98）的文案/配色/悬浮 tip 全部消费后端字段：`mode_label`、`confidence_color_class`、`trace_text`、`mae_rate`、`dir_hit_rate`、`n_test`、`nav_date`、`written_at`——其中配色类与标签由后端 `_finalize`（valuation.py:252）生成；前端仅有 `{official:…unknown}` 与 `{high:ch…}` 两张**兜底枚举映射**（后端缺字段时兜底，不覆盖后端值）。点击徽章拉 `/valuations/{code}?history=true` 展示当日逐次入账历史与降级链路 trace。五档徽章 + `.ch/.cm/.cl/.cu` 置信度配色在 css/app.css:116-121 落地。**结论：徽章链路后端真实驱动，符合 brief「不得静态硬编码」。**

#### D4. R2 升级建议要点

1. **持仓主源切换**：data/holdings.json 升为正式主源（设置页文案与 import 按钮改口径），源文件断链从「隐患」变「已声明边界」；或提供新的外部持仓导入口径（CSV/手工 CRUD 已有）。
2. **nav_history 自动维护**：用 lsjz 历史净值接口（eastmoney lsjz 已在用，翻页可得全史）定期把 nav_history 补到最新，摆脱 18 天滞后——直接提升 accuracy 回测样本量（7 → 40）。
3. **新浪兜底接入**：sina_rt_quote 已实现未接线，把它接进 proxy 档与重仓加权的个股实时作第二源（腾讯实时失败时），多一条腿。
4. **fail_count 衰减**：health.json 失败计数加时间衰减或成功后重置，避免「恢复后仍挂 544 次失败」误导阅读。
5. **数据源健康页补 sina 实测**：sina_rt 从未被探测调用，数据源健康表四源齐全但 sina 永远 unchecked——要么接要么从枚举中降级说明。

---

### E. 业务优劣缺点：优势 / 劣势 / 风险 / 技术债 / 口径诚实性

#### E1. 优势（业务层）

1. **诚实纪律贯穿全栈**：unknown≠0%、不填估计值（复盘页宁可「—」）、C 档一律「待验证」不冒充可信、INSERT-ONLY 台账 + 归档、mock 默认关闭且开启显式留痕（页头 MOCK 徽章）。
2. **覆盖已完成 0→22 映射**：proxy_map 22 只全解析（A2/B13/C7/D0），2 只主动全市场基金 F10 穿透成功并留完整 trace（025500→512480、021528→515880），D 档 0。
3. **工程可移植性**：纯标准库零依赖、Python 3.8+（启动检查 sys.version_info、实测 117 测试全绿 13.8s）、原子写全覆盖（tmp+os.replace）。
4. **契约治理成熟**：09-api-contract 迭代到 v8，全程「只加不改」+ 追加台账 §8-§13；冻结参数黑名单堵 API 改参（FROZEN_PARAM_KEYS）。
5. **因子治理机制真实跑通**：六窗走前 + F1/F2/F3 + bootstrap + 牌照四线全部有代码有实测（klow2/crowd6 已真实回测入盘，候选 mom5 真实拒绝 rejected_f3）。

#### E2. 劣势 / 风险

1. **核心价值未自证**（OBS-01 维持）：Δ 无值、影子盘零回填——用户每天打开看到的是「机制」而非「成绩」。
2. **置信度体系失效**（新发现）：22/22 徽章 unknown，估值精度汇总条无加权 MAE 可显示——「误差达标/中等/偏大」分组永远空。
3. **影子盘 20/60 结构矛盾**（新发现）：qualified 不可达。
4. **估值误差两极**：median 0.49% 很好，但 9/22 超 0.8% 基准、3 只方向命中率 <60%——「覆盖 22/22」里藏着近半数精度不合格的代理。
5. **数据源历史脆弱**：fundgz 一夜下线导致 544 次失败（OBS-04）说明外部接口无常；当前东财双 host + 腾讯双源是有效冗余，但 sina 未接线、日K 单 host。

#### E3. 技术债清单

| # | 项 | 位置 | 性质 |
|---|---|---|---|
| 1 | TOTAL_BUDGET_SEC=20 预算检查空转（`if ... : pass`） | valuation.py:534-535 | 死代码/未实现承诺 |
| 2 | BASELINE_RATE=0.5830 硬编码非实测 | ledger_api.py:30 | 口径债 |
| 3 | /review/scores 硬编码 null | app.py:498-514 | 待接回测出口 |
| 4 | bars 缓存 18 个文件中 159781/512050 两只无主（不在当前代理映射） | data/cache/bars | 历史遗留 |
| 5 | 022485 台账 20 行与现 C 档口径矛盾 | shadow_signals.jsonl | 口径漂移 |
| 6 | GATE_EFFECT（E1 0.88/E3 3.90 等）硬编码研究值（FundLens 结论，R1 标注口径） | fund_predict.py:33 | 可接受但需复核来源 |
| 7 | eastmoney fail_count=544 永不衰减 | health.json | 监控误导 |
| 8 | h_engine_status / h_engine_ddsm 每请求全量重训 DDSM（无模型缓存） | app.py:632/703 | 性能债（本地单用户可容忍） |
| 9 | accuracy.json 样本窗仅 7 日（nav_history 滞后所致） | data/snapshot/accuracy.json | 数据债（D2 建议可解） |

#### E4. INSERT-ONLY 台账纪律：代码真执行（实测确认）

- `write_entry` 查重 (date,code) 冲突抛 E_CONFLICT（ledger_api.py:104-107）；`write_backfill` 只写 t1/t3/t15_real 到**独立 backfill.jsonl**，无对应 signal 拒绝（test_ledger_contract 全绿覆盖这两条）。
- 滚动裁剪：窗口外记录 `_archive_records` 全量归档（archive/shadow_signals_archive.jsonl + _manifest.jsonl）后主文件重写——主文件在**裁剪场景**整体重写，但记录内容逐字冻结；保留策略声明为 first_of_day_immutable_full_archive 且 UI 披露归档时间。实测当前尚未发生裁剪（归档目录不存在），320 条都在窗口内。
- valuation_history.jsonl 逐次追加（同日同码多条=多轮刷新，各自带 written_at/run_id，first_of_day 标记保留）——语义符合 INSERT-ONLY。
- 路由层无台账编辑/删除入口（test_no_ledger_edit_or_delete_route）。

#### E5. F-PM-01 覆盖口径现状

**代码已修**：`holdings_summary.covered_count` 按 `change_rate != null`（可信估值）统计（fund_predict.py:545-546 注释引用 PRD F-01 验收②），今日实测 covered=22/22 为真（全部有 change_rate）。该缺陷从「虚报」收敛为「真覆盖」，但**需 QA 用 unknown 行场景补回归用例**（当前 22 只恰好全可信，掩盖了部分未知时的表现）；test_holdings_summary_contract 已有 unknown 场景用例（test_unknown_rows_lower_covered_count），风险可控。

#### E6. R2 升级建议要点

1. **口径单页化**：把「估值覆盖 22/22、预测覆盖 15/22、开口覆盖 11/22、可信估值覆盖 N/22」四层口径收敛到一张口径表（PRD 术语表），杜绝再次出现覆盖口径混用的 F-PM-01 类缺陷。
2. **技术债三处小修**：TOTAL_BUDGET_SEC 空转（删或实现）、022485 台账口径重算、bars 无主缓存清理——半天量级，防债滚大。
3. **INSERT-ONLY 纪律回归用例固化**：QA 增补「裁剪后归档可完整重建窗口外记录」用例（当前归档机制从未在真实数据上触发过，仅测试覆盖）。
4. **fail_count 衰减与重训缓存**（与 D4-4 / G5-4 同源）：监控数字可信 + 响应性能，两处低成本改进。
5. **GATE_EFFECT 研究值复核**：E1 0.88 / E3 3.90 / E2 −3.09 / E4 −2.72 来自 FundLens 研究结论，R2 用自家台账（开口 32 次）独立复算一遍效应，替换或确认。

---

### F. 前端：40 组件现状、短板、与 legacy v2 基准差距

#### F1. 现状

- **结构**：7 页签（持仓/分析/信号/因子/复盘/引擎/设置）+ 顶栏（日期/交易时段 chip/开口数/隐私眼睛）+ livebar + stale 横幅 + 3 dialog（录入编辑/加减仓/删除确认）+ 行菜单 popover + toast；侧栏数据域三行（服务日期/净值快照+滞后/行情快照，三者互不冒充）。
- **PM 验收**：40 组件 36✅ + 4✅*（有条件）+ 1⚠；Brief §9 逐项目录全对齐（G-FE-01 过）。
- **命脉组件实测**：估值徽章 `.vb`（五档 + `.ch/.cm/.cl/.cu`）、`.vsum` 精度汇总、`.covbar` 覆盖四档、`.tl/.sigcard/.ev` 信号时间线（点击拉 /ledger/chain 展开六步事件链）、`.chain-item` 推导链（分析页行点击弹窗）、125 格立方体（ddsm 默认 + naive 折叠 + vr 层切换 + 低样本「低」角标）、六维 z-bar、竞技场矩阵（独立 `--arena-*` 色板与涨跌色解耦 A-09）、HUD 卡、冻结参数表、四态 mountState、隐私打码、玻璃拟态（backdrop-filter blur 26px）——均已在 css/app.css 与视图中落地。
- **唯一 fetch 出口**（api.js）+ 慢接口超时名单（8s/30s 分档）；mock 隔离在 js/mock/，默认关闭（?mock=1 或 localStorage.zl_mock）；SW 注销 + caches 清理（R-UI-38）；15s 轮询 /runtime。
- **两 BLOCK 均已销项**：BLOCK-1（影子盘 HUD 状态字）——engine.js:17-18 拆成 PROGRESS_TAG（not_started/recording/qualified/gap）与 AUDIT_TAG（idle/ok/bad）两套枚举各管一段；BLOCK-2（Base URL 不持久化）——settings.py v5 已支持 base_url 落盘回传，前端 llm-url 字段读写正常。

#### F2. 短板

1. **数字空态大面积存在**（OBS-01 的 UI 侧）：复盘页 hero/三窗口全「—」、逐笔对账「待回填」×320、因子页四盘仅 adopted 有 2 个因子其余空——结构对了但「成绩」缺席，观感是「半成品仪表盘」。
2. 四态「空态」仅演示条可触发（OBS-03 遗留，emptyWhen 未全量接线）。
3. 置信度徽章全站灰（E2 根因在后端，但 UI 无「为什么全灰」的解释层）。
4. 单主题 light（设计基准如此，深色不做）。

#### F3. 与 legacy v2 设计基准（00-design-reference-legacy-v2.html，112,629 字符）的差距

- 页签结构、命脉类名、40 特调组件清单**完全对齐**（基准的 data-v 7 页签与产品壳一致；vsum/vb/covbar/tl-item/sigcard/chain-item/cube/zbar/hud/frow/dim/degrade/dlg/livebar 全部存在）。
- 差距集中在**填充态**：基准壳里的长文 rule（四盘规则/评分链/生命周期/加权三规则）产品壳已由后端驱动（factor_board rule_text 等来源标注），这部分反而比基准更可审计；真正的差距是基准演示的「有数状态」（命中率/Δ/立方体对比卡走前 Δ）在产品里是「—」。
- R-UI-01 四卡今日盈亏副标题已带「覆盖 N/N 只」口径；「未知≠持平」在 changeCell/pnlCell 实现（null→未知/—）。

#### F4. R2 升级建议要点

1. **成绩位优先**：复盘 hero/三窗口 Δ 出数（C 节）是前端最大单点提升——所有组件骨架已备，纯填充。
2. **置信度全灰加解释**：徽章 tooltip 与 vsum 增加一行「误差通道建设中」的过渡文案，避免用户把 unknown 误读为「系统不可信」。
3. **emptyWhen 全量接线**（OBS-03）：七个视图的空判定补齐，让四态可在真实数据下触发。
4. **逐笔对账回填态**：t1_real 自动回填（C 节）后 UI 从「待回填」变 hit/miss 徽章，信号时间线的 hit/miss 色同步激活。
5. **立方体对比卡走前 Δ**：comparison.walk_forward_delta_* 当前恒 null（契约注明待回填）——C 节回测接通后此卡自然出数。

---

### G. 后端：53 接口、模块划分、代码质量、兼容性

#### G1. 接口清单与模块划分（契约 v8：55 接口 = 53 UI + 2 内部 + /health）

9 域划分（app.py ROUTES 53 条 + /health，实测 test_routes_cover_55_interfaces_plus_health 绿）：

| 域 | 接口 | 后端模块 |
|---|---|---|
| 元信息/runtime | /health /runtime /about /meta/definitions /signals/state | app.py |
| 持仓 CRUD | /holdings(+summary/coverage/risk/import) /holdings/{code}(GET/PUT/DELETE) /holdings/{code}/transactions | holdings.py + risk.py |
| 实时估值 | /valuations(+precision) /valuations/{code}?history | valuation.py + estimator.py |
| 预测/组合 | /predictions /predictions/{code} /portfolio/forecast | fund_predict.py + engine.py |
| 复盘 | /review/scores /review/reconciliation /review/cv-config | app.py + ledger_api.py |
| 台账 | /ledger /ledger/entries(内部) /ledger/backfill(内部) /ledger/shadow /ledger/chain | ledger_api.py |
| 因子 | /factors/{pans,books,score-chain,lifecycle,score-detail,governance-cycle,dig-records,book_detail} + v7 候选 2 个 | factor_board.py + factor_engine.py |
| 引擎 | /engine/{status,inputs,ddsm,ddsm/cube,frozen-params,registry,training-status,arena,shadow-review} | engine.py + ledger_api.py |
| 任务/设置/数据源 | /tasks(POST/GET/{id}) /settings(+/holdings-data) /data-sources/{health,probe} | app.py + settings.py |

启动 warmup 后台线程依次执行：run_predictions → build_accuracy → refresh_fund_valuation(force) → refresh_official_nav → valuation.refresh_all(force) → rolling_shadow_backfill(20) → refresh_penetrations → ensure_adopted_pan——「打开即有数据」的来源。

#### G2. 代码质量

- **优点**：模块边界清晰（取数 estimator / 决策 engine / 编排 fund_predict / 估值 valuation / 台账 ledger_api / 因子 factor_engine+board 六层）；docstring 全部带口径出处（契约条款/Brief 章节/任务裁定号）；原子写全站统一；异常统一兜 ApiError 10 码穷举；防前视铁律在 factor_engine 有 7 层实现（L1 视图截断-L7 holdout）。
- **坏味道**（除 E3 表外）：`_global_model` 在多个 handler 重复全量训练（无缓存层）；estimator/proxy_map 有两份几乎相同的 F10 解析器（parse_top_holdings vs parse_f10_holdings，重复实现）；`h_engine_registry` 的 can_rollback=False 硬编码「当前生产引擎」单条记录（三态注册表是演示态）。
- **硬编码盘点**：端口 8791/引擎版本 oc-s3-v1/BASELINE_RATE/窗口 20 日/目标 60 日/基准 MAE 0.008——多数有契约出处，唯 BASELINE_RATE 无实证出处（E3-2）。

#### G3. Python 3.8+ 兼容性

- 启动硬检查 `sys.version_info >= (3,8)`（app.py:1227）；代码风格全程 3.8 安全（% 格式化、无 walrus 滥用、无 3.9+ 语法如 dict |、str.removeprefix）；`datetime.fromisoformat` 只喂自身产出的 ISO 串（3.8 无 bug 风险面）。
- 实测：当前解释器 117 项测试 13.8s 全绿；README-START 记载 R1 曾在 3.8.6 实测通过。纯标准库（urllib/http.server/json/decimal/math/random/hashlib/threading），无 pip 依赖。

#### G4. 测试资产

12 个契约测试文件 / 117 断言全绿：INSERT-ONLY 冲突与独立回填文件、滚动窗口 20 日/幂等/裁剪归档、E1/E3 门与「永不做空」、冻结参数与黑名单、naive/ddsm 双口径、代理映射 22 只全解析与穿透 trace、估值档位分流（active→holdings 优先）、组合加权三规则、四盘 caps 口径。测试用临时目录 + 合成 K 线，不联网、不碰产品数据。

#### G5. R2 升级建议要点

1. **优先级即 C 节三件**：回测接 /review/scores、t1_real 自动回填、基线实测化——三处改动都在后端且体量小（估 1~2 天），North Star 直接出数。
2. **置信度通道**（A 节）按 `mode|code` 键落盘 accuracy，后端一处改动激活全站徽章。
3. **重构两份 F10 解析器合一**（estimator 复用 proxy_map 的或反之），防口径分叉。
4. **重训结果缓存**：engine 训练按 (code, as_of) 加进程内缓存，估值/引擎页响应从全量重训降到毫秒级。
5. **BASELINE_RATE 与窗口参数进 frozen_params**：20 日窗口、60 日门槛、0.583 基线全部纳入冻结参数表统一管理（当前散在常量），改口径必须重走六关的纪律才闭环。

## 自验收

1. **四块齐全**：摘要 ✅ / 正文 A–G ✅ / 自验收 ✅ / 下游交接 ✅。
2. **A–G 七节全覆盖且每节附 ≤5 条 R2 建议要点** ✅；「解剖必须回答」清单逐项有实测答案：
   - A：五档代码路径与触发条件表、22 只档位分布（17/5/0/0/0 + 当日历史 968 行）、MAE 实测（mean 0.80% / median 0.49% / 9 只超标 / max 2.40%）、置信度 22/22 unknown 的根因 ✅
   - B：台账 320 行/16 资产/20 交易日、开口 11 资产/13 日、up 4 条、无记录 6 只（全 C 档）与原因、10/22→22/22 扩容路径 ✅
   - C：Δ 无值实测确认（代码硬编码 null + backfill 0 行）、4/4 hit 离线复算参考、回测能力齐备未接通、20/60 矛盾新发现 ✅
   - D：4 源清单与失效处理表、桌面数据根断链实测、data/holdings.json 现状、徽章后端驱动确认（无硬编码）✅
   - E：优劣/风险/技术债 9 项表、F-PM-01 已修待回归、INSERT-ONLY 代码级确认 ✅
   - F：40 组件 36✅+4✅*+1⚠、两 BLOCK 销项确认、与 legacy v2 差距（结构齐、数字空）✅
   - G：53 UI + 2 内部接口 9 域表、坏味道与硬编码盘点、Py3.8+ 兼容实测、117 测试全绿 ✅
3. **只读纪律**：全程零改动产品代码/数据/台账/文档（统计脚本写入系统临时目录 `C:\Users\10719\AppData\Local\Temp\opencode\`）；台账与数据文件只做读取统计 ✅。
4. **限制说明**：accuracy 的 n_test=7 受 nav_history 滞后限制，误差数字为小样本估计；up 4 条的 T+1 复算是只读推演、未写入台账（写入即违反 INSERT-ONLY 归属）。

## 下游交接

- **接收角色**：product-manager（R2 PRD 输入）；副本参考：architect（D 节数据源口径、C 节回测接口改动）、backend-dev（A/C/G 节落地清单）。
- **R2 四大目标 → 现状堵点 → 建议主线的对应表**：

| R2 目标 | 最大堵点 | 首选动作（本报告建议） | 预期基线变化 |
|---|---|---|---|
| 估值更准 | 置信度体系脱节（22/22 unknown） | mode|code 误差通道 + 重仓加权升级 + QDII 时差校正 | 置信度可分档显示；MAE 超标 9 只复核 |
| 覆盖更多 | C 档 7 只未验证 | 六窗走前验证批次 C→B | 预测覆盖 15/22 → 22/22 |
| 准确率更高 | Δ 无值 + 零回填 + 20/60 矛盾 | 回测接复盘页 + t1_real 自动回填 + 基线实测化 + 解开窗口矛盾 | 复盘 hero 出数、影子盘可积累至 qualified |
| 来源更可靠 | 桌面数据根断链 + nav_history 停更 | holdings.json 主源化 + lsjz 补 nav_history + sina 兜底 | 滞后 18 天 → T+1；accuracy 样本 7→40 |

- **PRD 撰写注意**：①C 节三个后端改动是「价值出数」的最短路径，建议列为 R2 P0 首批；②A 节置信度通道依赖 C 节的净值回补（误差回算需要 T+1 官方净值），两目标有依赖顺序；③B 节 C→B 验证可复用 21-factor-governance 既有机制（成本最低）；④冻结参数（BAND/双否决分位/窗口）任何调整须按 brief §5.2 重走六关，PRD 不要直接承诺参数变更，只承诺「研究项产出」。
- **风险与未决项**（交接清单，非本报告可关闭）：
  1. 影子盘 20 日窗口 vs 60 日达标矛盾（结构性，R2 必改否则 qualified 永不可达）
  2. BASELINE_RATE=0.5830 无实证出处
  3. 置信度键口径（proxy-only）与当前档位脱节
  4. 桌面 funds_data.json 断链后「重新导入」按钮将报 E_IO（UI 侧未提示）
  5. 022485 台账遗留口径漂移；bars 无主缓存 2 只
  6. eastmoney fail_count 544 不衰减；sina_rt 从未实测
  7. accuracy n_test=7 小样本（依赖 nav_history 补新后才能扩大）
  8. up 出口 4/32（12.5%）极低频——若 R2 调出口阈值，须走前 CV + placebo + holdout 全套
