---
artifact: 17-test-plan-r2
owner: qa
version: v2
status: draft
supersedes: 17-test-plan.md（R1 基线 v1）
created: 2026-09-12
reviewers: [dev-lead, product-manager, orchestrator]
gate: G-QA-01
---

# R2 升级轮测试计划与用例 · 极境 ZenithLens（契约 v9.1 · 前置起草）

> 上游依据（只读）：`docs/01-architecture/09-api-contract-r2.md`（v9.1，字段/枚举/口径 = 断言的**法律依据**）、
> `docs/00-charter/01-requirements-v3.md`（R2-01..25 与 25 条定量验收）、`docs/00-charter/02-prd-v3.md`（F2-01..25 / G2-01..15 / §0 四层覆盖口径 / 不做清单）、
> `docs/00-charter/03-ui-design-v3.md`（U-01..U-12 + §4 四态真实触发表 + §8 升级触点表）、`docs/01-architecture/08-backend-arch-r2.md`（v3.1，§10 测试接缝 / §8 红线核对）、
> `docs/05-qa/17-test-plan.md`（R1 基线，编号沿用引用）。
> **本文件只写计划不执行**（S3 前后端并行开发中；v4.1 关键路径重叠机制下，用例只依赖契约与 PRD、不依赖实现代码）。执行结果与缺陷见 S5 的 `18-test-report-r2` / `04-defects-r2`。
> skill：`test-scenarios`（六段法推场景，强制正常/边界/异常三件套；只取方法，不改 G-QA-01/02 判据与四块结构）。执行期拟用 `dummy-dataset`（四态/降级夹具）与 `diagnosing-bugs`（缺陷必附根因）。

## 摘要

1. 范围 = R2 25 功能点（F2-01..25；P0 12 / P1 12 / P2 1）+ 四目标 P0 脊柱（估值/覆盖/准确率/来源）+ U-01..U-12 四态 + 数值口径 + 负向断言；R1 的 124 条用例全部沿用回归。
2. 用例总量 **224 条**：P0 159 / P1 63 / P2 2 —— 四目标 26、功能点 89、数值口径 N2 30、UI 四态 48、负向断言 X2 20、任务接口 C2 6、回归 R2-REG 5。
3. 数值红线逐条成用例：vsum 主指标=估算档（官方档单列）、Δ 可复算、覆盖 (15+k)/22 按实计、挂档不计覆盖、conf_reason 五值按序命中、QDII 首测门槛 40 可配对日且 n≥20（N2-01..30）。
4. 负向断言 20 条：伪造数字 / 假兜底 / 静默失败零容忍（X2-01..20）；数据错误一律 P0。
5. 判分按「先结论率、后数值目标」分段；未接通一律「待填充」；执行按依赖顺序分 6 批（B1 nav/通道 → … → B6 R1 回归）。

## 正文

### 0. 依据与纪律

| 项 | 内容 |
|---|---|
| 断言依据优先级 | 契约 v9.1 字段/枚举/口径 > PRD v3 G2-01..15 > 需求 v3 定量验收 > UI v3 U-01..12 / §4 |
| 只读边界 | 不修改产品代码/契约/架构文件/R1 工件（本文件为 `-r2` 新文件）；不触碰 `runtime/**` |
| 执行时机 | 本任务只编写计划；执行在 S5（构建产物就绪后）；缺陷只提 `dev-lead`（六项必填，数据错误一律 P0） |
| 契约漂移 | 实现期若契约出 v9.2+，按变更分诊 C1 增量修订本文件对应行，不重写全表 |
| skill | `test-scenarios`（本文件）；`dummy-dataset`、`diagnosing-bugs`（S5 执行期调用） |

### 1. 范围、方法与统计口径

#### 1.1 用例分组与编号

| 组 | 编号 | 内容 | 条数 |
|---|---|---|---|
| 四目标 P0 脊柱 | `G2-A/B/C/D-xx` | 每目标正常/边界/异常/口径全维度 | 26 |
| 功能点 | `T2-F2-01..25-{N/B/E/C}` | N=正常，B=边界，E=异常，C=口径 | 89 |
| 数值口径 | `N2-01..30` | 复算式/判据逐条（金融生命线） | 30 |
| UI 四态 | `U2-01..12-{空/载/错/成}` | 12 个升级点 × 四态 | 48 |
| 负向断言 | `X2-01..20` | 不得伪造数字 / 假兜底 / 静默失败 | 20 |
| 任务与接口 | `C2-01..06` | `/tasks` `/ledger/backfill` 口径 | 6 |
| R2 回归新增 | `R2-REG-01..05` | 归档重建 / INSERT-ONLY / 口径回归 | 5 |
| R1 沿用（不重复计数） | 见 §2 | 124 条（B6 批重跑） | (124) |

#### 1.2 优先级与优先级来源

| 分组 | 条数 | P0 | P1 | P2 | 优先级来源 |
|---|---|---|---|---|---|
| G2 四目标 | 26 | 26 | 0 | 0 | 四目标 = P0 验收脊柱 |
| T2 功能点 | 89 | 48 | 39 | 2 | 继承 F2-01..25：P0 12/P1 12/P2 1 各自成套 |
| N2 数值口径 | 30 | 30 | 0 | 0 | 数据错误一律 P0（qa 契约） |
| U2 UI 四态 | 48 | 24 | 24 | 0 | U-01..06 P0（随 R2-19..22/13/16）、U-07..12 P1 |
| X2 负向断言 | 20 | 20 | 0 | 0 | 红线 |
| C2 任务接口 | 6 | 6 | 0 | 0 | 均落 P0 任务契约（R2-07/12/14/16） |
| R2-REG 回归 | 5 | 5 | 0 | 0 | 红线 |
| **合计** | **224** | **159** | **63** | **2** | — |

#### 1.3 环境与数据（沿用 R1 §1，标注 R2 差异）

| 项 | 值 |
|---|---|
| 应用 | `python app.py`（R1 实测端口 8791）；纯标准库；构建产物与启动见 16-build `README-START.md` |
| 数据根 | 主源 `data/holdings.json`（R2-15 主源化，22 只）；执行前打版本化快照对照 |
| 构造夹具 | 四态/降级/失败注入夹具由 `dummy-dataset` 生成，落 `docs/05-qa/evidence-r2/fixtures/`；**不改产品数据**；CRUD 用临时代码测后还原 |
| 浏览器 | Chrome for Testing + 自建 CDP（R1 已验证路径） |
| 证据目录 | `docs/05-qa/evidence-r2/`（执行期新建）；接口 JSON 原文、逐页截图、复算脚本日志 |
| 脚本复用 | R1 `evidence/scripts/{numeric_checks,crud_checks,run_ui_checks,cdp}.py` 沿用；R2 新增通道/回填/复盘/四态专项脚本（执行期） |
| 错误注入 | nav 断供 / 源超时 / 归档不可写 / 样本不足 / 预算超限（文件级 fixture 或任务参数，不经产品代码修改） |

#### 1.4 执行批次（依赖顺序，对齐 08-r2 §7.3）

| 批 | 内容 | 主要用例 | 前置 |
|---|---|---|---|
| B1 | nav 维护 → 日留档 → 置信度通道 | G2-A、T2-F2-16/05/01、N2-03..10/18/28 | R2-16 先行（T1 缓解） |
| B2 | t1_real 回填 → 基线实测 → /review/scores | G2-C、T2-F2-12/14/11、N2-14..16/22/23 | B1（nav 就绪） |
| B3 | C→B 验证 / 9 只复核 / recompute | G2-B、T2-F2-06/04/07、N2-11..13/24 | B1；复核用质量证据道（不依赖展示通道成熟） |
| B4 | 来源治理（主源 / sina / 计数） | G2-D、T2-F2-15/17/18、N2-17 | 独立 |
| B5 | UI 全量（U-01..12） | U2、T2-F2-19..25、X2 全量走查 | B1..B4 数据就绪 |
| B6 | R1 套件回归 + R2-REG | §2 全部 124 条 + R2-REG-01..05 | 全部 |

### 2. R1 沿用与预期修订清单（引用 `17-test-plan.md` 编号）

> 沿用 = R1 编号原样进入 B6 回归重跑、不重抄；预期修订 = R2 行为变更使原期望升级，执行时以本文件对应行（U2/N2/T2）为准。

| R1 编号段 | 内容 | 条数 | 处置 | 预期修订点 |
|---|---|---|---|---|
| §3 `N-01..N-24` | 数值口径（生命线） | 24 | 全部沿用重跑 | N-03 覆盖计数保持 `change_rate≠null` 口径；其余原样（R2 新口径见 N2-*） |
| §4 `T-F01..F11` | P0 功能点（各 N/B/E/C） | 44 | 全部沿用重跑 | T-F09 台账（回填激活→T2-F2-12/22）、T-F10 复盘（真实出数→T2-F2-11/19）、T-F11 健康（滞后/计数→T2-F2-16/18） |
| §5 `T-UI-01..40` | 40 组件逐项 | 40 | 全部沿用重跑 | 16 行按升级触点修订：T-UI-02/03/06/09/13/20/21/24/26/28/29/30/31/34/35/40（对应 §6 U2；触点表见 03-ui-design-v3 §8） |
| §6 `C-01..C-16` | 交互 / CRUD / 还原 | 16 | 全部沿用重跑 | 无（C-11..13 llm 往返不变） |
| **合计** | — | **124** | — | **19 条/组**标注预期修订（16 T-UI + 3 T-F） |

### 3. 四目标用例（P0 脊柱 · 26 条）

> 判读：每目标均含 正常 / 边界 / 异常（+口径）维度；数值复算式引用 §5 N2。

#### 3.1 A 估值更准 · G2-A（8 条）

| 用例ID | 类型 | 前置 / 步骤 | 期望（断言口径 · 契约 v9.1） |
|---|---|---|---|
| G2-A01 | 正常 | nav 回补接通 24h 后查 `/holdings` + `/valuations/precision` | 置信度非 unknown 只数 **≥21/22**（基线 0/22）；`conf_reason` 全 null；vsum `estimate_quality.weighted_mae_rate` 非 null 且可复算（N2-02） |
| G2-A02 | 边界 | 样本不足 / 窗口未满时查精度窗 | `n_test<5` → `unknown + no_samples`；`window_filled_days` 不足按实显「累计 X/40」；`window_phase`：<5 可配对日 `warming`、≥5 `first_verdict`、≥40 `mature` |
| G2-A03 | 异常 | 逐情形注入：净值对缺 / 预算跳过 / 全链无来源 | 分别得 `conf_reason = nav_missing / budget_exceeded / mode_unknown`（按序命中即停，N2-04）；unknown 必须带原因，**不得静默** |
| G2-A04 | 口径 | 抽样复算误差与归键 | 误差 = `|est − real|`，`real = nav(D)/nav(D−1)−1`；键 = `mode|code`；评分对象 = 每 `(date,code,mode)` 当日最后一条；不可配对日不入样本（不填 0） |
| G2-A05 | 正常 | 主动 5 只（025500/018957/021528/013566/014320）holdings 档 tooltip | 含 `report_date` + `covered_weight_pct` + `top_n∈{10,20}`；`included_markets ⊆ {A,HK,US}`；覆盖权重提升目标 ≥+10pp 或出「不可得原因」结论（不编造） |
| G2-A06 | 边界/异常 | QDII 行（024239/457001/021662）双段校正 | `applied=true` → `change_rate = domestic.value + overseas.value` 且 `fallback_reason=null`；隔夜缺 → `overseas_unavailable`；对齐失败 → `alignment_conflict`；首测失败判定需 40 可配对日且 n≥20（N2-20） |
| G2-A07 | 口径 | 抽查 `trace[holdings].detail` 重算 | `weighted_change = Σ(w×chg)/Σw`；`used=false` 标的剔除；`excluded_count` 如实；缓存 `top_n` 低于请求且过期 → 重抓，失败按旧缓存 + 如实标注 |
| G2-A08 | 边界/口径 | 连续两交易日触发日留档 | 每交易日 1 文件 `daily/valuation-YYYYMMDD.jsonl`（≤22 行）；重复调用不重写（幂等）；`window_filled_days` 逐日 +1 且 X/40 可查 |

#### 3.2 B 覆盖更多 · G2-B（6 条）

| 用例ID | 类型 | 前置 / 步骤 | 期望（断言口径） |
|---|---|---|---|
| G2-B01 | 正常 | 跑 `POST /tasks {type:"verify_tiers"}`（缺省 C 档 7 只）后查 `/holdings/coverage` | **7/7 出结论**（tier_reviews.jsonl）；升 B 者 `tier∈{A,B}` 且 `verify_status=validated`；`prediction_coverage_note` 显示 `(15+k)/22` 按实计 |
| G2-B02 | 边界 | 独立触发日 <20 的资产 | 挂档观察：`verify_status∈{pending_validation,validating}` + `verify_review_date` = 证据就绪日 +30 交易日；挂档行**不计入**覆盖增长、不进 universe；>3 只挂档 → 触发架构×PM 复审 |
| G2-B03 | 异常 | 样本足但不达标（构造 lift<1.0 或 Δ<0） | 降 D：`verify_status=validation_failed` + `tier_reason`/`verify_note` 原因；从 universe 移出；**禁止**「挂着 C 档不给结论」 |
| G2-B04 | 口径 | 复算覆盖率 | `prediction_universe_count == /holdings 中 tier∈{A,B} 行数`；k = 原 C 档名单{022485,025500,018957,021528,457001,021662,163208} ∩ 升 B ∩ `validated`；批次中显示 `15/22（+7 待结论）`（N2-11/12/13） |
| G2-B05 | 口径 | `backfill_ledger mode=recompute` 重跑两次 | 「台账档位 vs 现持仓档位」**0 冲突**；重复执行行集合不变（幂等）；旧记录先归档且可复读；`_manifest.jsonl` 含差异摘要（新增/移除条数、最早/最晚日期） |
| G2-B06 | 边界/口径 | 查 `/signals/state` 空态与滚动口径 | `rolling_open_assets ≥11`（滚动 20 交易日资产去重）；空态四要素（监控中 N/M、距上次开口、上次开口、上次结果）+ `low_frequency_note`；口径 = 资产数非日开口数 |

#### 3.3 C 准确率更高 · G2-C（6 条）

| 用例ID | 类型 | 前置 / 步骤 | 期望（断言口径） |
|---|---|---|---|
| G2-C01 | 正常 | 查 `/review/scores?data_kind=backtest` 与复盘页 | hero 三段式出数（hit_rate / baseline_rate / delta_pp / open_count / sample_period / data_kind）；`scores[]` ≥T+1 行非 null；`sample_window` 恒 `full`；口径同页（走前 CV / purge=H+2 / placebo≥2pp / holdout 60） |
| G2-C02 | 边界 | T+3/T+15 未接通；shadow_live 样本不足 | 未接通窗口 `baseline_status=pending` + 数值 null（**不得填估计值**）；shadow_live 可 `scores[]` 空 + `note`；`data_kind` 透传请求值；六样本窗**不得**混入本页充当「三窗口」 |
| G2-C03 | 异常 | 成绩缓存缺失 / 回测任务失败 | 复盘页空态「尚无成绩记录，引擎未产出回测」；不白屏；不拿回测冒充 `shadow_live`（`data_kind` 区分） |
| G2-C04 | 口径 | 同 bars + frozen_config + seed 重复回测 | `delta_pp = hit_rate − baseline_rate` 结果一致（幂等复算）；`baseline_rate` = 实测 `max(恒涨率,恒跌率)`（同窗去重叠全测试日集）；`baseline_source=measured`；`0.5830` 零引用（N2-08/09/10） |
| G2-C05 | 正常/口径 | 到期信号回填 | `backfill.jsonl ≥1` 条真实回填；已到期 up 覆盖率 **100%（≥4/4）**；`t1_real = bars[i+H]/bars[i]−1`、`method=proxy_bar` + `proxy_code`；给定日线可复现 hit/miss |
| G2-C06 | 边界/口径 | 归档 + 主文件合并计算（构造 ≥60 日） | `consecutive_days` 可达 **≥60**（不再封顶 20）；`history_days` = 合并且去重日数；归档缺失 → `archive_merged=false` + note 口径降级（不伪造天数） |

#### 3.4 D 来源更可靠 · G2-D（6 条）

| 用例ID | 类型 | 前置 / 步骤 | 期望（断言口径） |
|---|---|---|---|
| G2-D01 | 正常 | 跑 `maintain_nav_history` 后查侧栏与 accuracy | nav_history 滞后 **≤1 交易日**（基线 18 天）；`n_test ≥40`（基线 7）；侧栏滞后显示与实际一致 |
| G2-D02 | 边界 | 重复执行任务；接口失败注入 | 幂等：points 集不变、既有日期不覆盖（首值冻结）；失败 → 保留已有数据 + 标注滞后（不编造净值） |
| G2-D03 | 异常 | 腾讯实时失败注入 → 新浪；再到双失败 | 单源失败走新浪兜底（5s 超时、重试 0）且留痕；双失败落既有降级（日线/Gray）不阻塞估值链；健康页新浪行有三态 + 时间戳 |
| G2-D04 | 口径 | 查 `/data-sources/health` | `fail_window_7d` = 近 7 自然日失败数（成功不抹历史、自然滚动）；`recent_failures ≤10`；`fail_count=544` **不得作为当前状态**出现（deprecated 仅审计） |
| G2-D05 | 边界/异常 | 设置页持仓卡：主源存在 / 缺失两态 | `main_source` 口径正确；缺失时 `import_available=false` → 导入按钮禁用 + `import_disabled_reason` 说明；**不出现** E_IO 堆栈与 `primary_exists=false` 误导展示；重启 22 只完整 |
| G2-D06 | 正常 | 查健康表全部源 | 各源（含新浪）均有状态 + 时间戳；nav 滞后 ≤1 日显示正常态；断链/降级说明可读 |

### 4. 功能点用例（F2-01..25 · 89 条）

> P0 功能每个 4 条（正常 N / 边界 B / 异常 E / 口径 C）；P1 功能 3~4 条；P2 2 条。与 §3 的分工：§3 是目标级验收，本节是功能点级拆解。

#### 4.1 A 组 · F2-01..05（估值）

| 用例ID | 类型 | 步骤 / 输入 | 期望 |
|---|---|---|---|
| T2-F2-01-N | 正常 | 净值就绪后查 `/holdings` valuation | 当日误差记录按 `mode|code` 产生；至少某档 confidence 非 unknown 且 `n_test` 展示 |
| T2-F2-01-B | 边界 | n_test=4 → 5 两态 | 4 → `unknown + no_samples`；5 → 出统计（n≥5 才产出） |
| T2-F2-01-E | 异常 | 净值接口失败 / 无当日记录 / mode=unknown / 预算跳过 | 对应 `nav_missing / valuation_missing / mode_unknown / budget_exceeded`，按序命中即停 |
| T2-F2-01-C | 口径 | 逐只复算 MAE/方向命中率/窗 | 与 `/valuations/precision` 一致（±0.0002）；滚动 40 可配对日；n 逐日累计 |
| T2-F2-02-N | 正常 | holdings 档行 tooltip | `report_date` + `covered_weight_pct` + `top_n=20`（启用后）；`included_markets` 含 HK |
| T2-F2-02-B | 边界 | 缓存 top_n=10 且过期 / 美股代码 | 重抓或如实标 10（不虚报）；美股 → `excluded_count` +1 |
| T2-F2-02-E | 异常 | F10 不可得 | 回退 proxy 链并保留 no_report 语义；缺报价标的 `used=false` 剔除 |
| T2-F2-02-C | 口径 | 复算 `weighted_change` | `Σw×chg/Σw`；覆盖权重 = 参与加权合计；±0.0002 |
| T2-F2-03-N | 正常 | QDII 行估值 | `qdii_correction.applied=true`；`change_rate` = 两段和；tooltip 显示校正口径 |
| T2-F2-03-B | 边界 | 隔夜源缺 / 时间对齐失败 | `applied=false` + `overseas_unavailable` / `alignment_conflict`（不静默） |
| T2-F2-03-E | 异常 | 代理 bar 不足 | 不产出校正（`qdii_correction=null`），落既有 proxy 链 |
| T2-F2-03-C | 口径 | first_test_failed 门槛 | 仅 40 可配对日且 n≥20 可判；未达 → 挂档观察（`next_review_date` 预注册）；回退结论带数字 |
| T2-F2-04-N | 正常 | 跑 `verify_tiers`（9 只超标清单） | 9/9 结论落盘（含六窗 lift/MAE/方向命中率/样本证据） |
| T2-F2-04-B | 边界 | 3 只方向命中率 <60%（025857/163208/014320） | 换代理后 ≥60% 且 Δ≥0 → 保留；否则降档；**不得「超标且无结论」** |
| T2-F2-04-E | 异常 | 证据缺失 / 代理候选缺失 | 结论标「无候选，明示降档」；不得留白 |
| T2-F2-04-C | 口径 | 证据来源分键 | MAE/方向命中率读数取自 `proxy_quality.json`（质量通道），不得取 `accuracy.json`（展示通道） |
| T2-F2-05-N | 正常 | 收盘后触发留档 | 每交易日 `daily/valuation-YYYYMMDD.jsonl` 生成；每基金 1 行 |
| T2-F2-05-B | 边界 | <40 日 / 满 40 日 | `window_filled_days`：「累计 X/40」/「已满 40 日」；MAE 序列可复算 |
| T2-F2-05-E | 异常 | 归档目录不可写 | 启动告警（health note），不阻塞估值链 |
| T2-F2-05-C | 口径 | INSERT-ONLY 语义 | 追加写、重复调用不重写、可归档不可改（R2-REG-02） |

#### 4.2 B 组 · F2-06..10（覆盖）

| 用例ID | 类型 | 步骤 / 输入 | 期望 |
|---|---|---|---|
| T2-F2-06-N | 正常 | `verify_tiers` 跑 C 档 7 只 | 7/7 结论；升 B 入 universe；`prediction_coverage_note` 按实计 |
| T2-F2-06-B | 边界 | 独立触发日 <20 | 维持 C + 复查日（+30 交易日）；挂档可见且不计增长 |
| T2-F2-06-E | 异常 | 验证不通过 | 降 D + `tier_reason` + `validation_failed`；从 universe 移出 |
| T2-F2-06-C | 口径 | 复算 `(15+k)/22` | k 口径见 N2-11；批次中 `15/22（+7 待结论）` |
| T2-F2-07-N | 正常 | `mode=recompute` 重算 | 按现档位重生成；0 档位冲突 |
| T2-F2-07-B | 边界 | 中断后重跑 | 事务性保护：不半写；重跑幂等覆盖 |
| T2-F2-07-E | 异常 | 归档不可写 | 中止并告警（不半写、不静默） |
| T2-F2-08-N | 正常 | 信号页空态 | 四要素 + 低频说明 + `rolling_open_assets ≥11` |
| T2-F2-08-B | 边界 | 台账空 / 监控集合空 | 要素显「无记录」/「0/0」；变体①「影子盘尚未开始记录」 |
| T2-F2-08-E | 异常 | 台账读取失败 | 错误态「读取信号台账失败」+ 原因 + 重试（不回退示例） |
| T2-F2-09-N | 正常 | 信号卡 + 持仓行 | QDII 标注出现，文案与 Brief §5.3 一致 |
| T2-F2-09-B | 边界 | 非 QDII / 字段缺失 | `qdii_lead_note=null` 不显示（不编造） |
| T2-F2-09-E | 异常 | 标注前后信号 diff | 信号字段零变更（断言不改变任何信号逻辑） |
| T2-F2-10-N | 正常 | 研究报告落盘 | 六窗 + placebo 报告存在（进 21-factor-governance） |
| T2-F2-10-B | 边界 | `frozen_params` diff | 无 diff（R2 内不改参）；如建议改参须附六关提案 |

#### 4.3 C 组 · F2-11..14（准确率）

| 用例ID | 类型 | 步骤 / 输入 | 期望 |
|---|---|---|---|
| T2-F2-11-N | 正常 | 复盘页 + `/review/scores` | hero 出数；scores T1 行完整（命中/基线/Δ/开口数） |
| T2-F2-11-B | 边界 | T3/T15 未接通 | 显示「待填充」；数值 null；不得估计值 |
| T2-F2-11-E | 异常 | 无成绩文件 / 服务失败 | 空态/错误态可读；不白屏、不回退示例 |
| T2-F2-11-C | 口径 | grep 硬编码 + 复算 | 代码 0 处硬编码 null 出口；Δ 可复算；口径与 cv-config 一致 |
| T2-F2-12-N | 正常 | 到期 up 信号回填 | `backfill ≥1`；覆盖率 100%；只写 `t*_real` |
| T2-F2-12-B | 边界 | 未到期 / 无对应 signal | 未到期不写；无 signal → `E_VALIDATION` |
| T2-F2-12-E | 异常 | 日线缺失 | 标「数据缺失待补」，不移除记录、不回滚已写 |
| T2-F2-12-C | 口径 | 复算 | `t1_real` = bars 比值；`method=proxy_bar`；`proxy_code` 落盘（复算锚） |
| T2-F2-13-N | 正常 | 引擎页进度条 | `x/60` 与后端 `shadow_progress` 一致；标注「归档合并计算」 |
| T2-F2-13-B | 边界 | 合并集 ≥60 可达 | `consecutive_days ≥60` 可证；不封顶、不伪造 |
| T2-F2-13-E | 异常 | 归档缺失 | `archive_merged=false` + note 口径降级 |
| T2-F2-13-C | 口径 | 窗口外记录重建 | 裁剪后可由归档完整重建（R2-REG-01） |
| T2-F2-14-N | 正常 | 复盘页 / 影子盘基线显示 | `baseline_source=measured`；`baseline_method` 非空；显示口径与 universe |
| T2-F2-14-B | 边界 | N=0（无 t1_real 行） | baseline `null`（**不得回退 0.5830**） |
| T2-F2-14-E | 异常 | 改参注入（`baseline_method`） | `POST /tasks` 黑名单 → `E_VALIDATION`；产线 grep `0.5830` 0 引用 |
| T2-F2-14-C | 口径 | Δ 复算 | `delta_pp = hit − measured baseline`；同数据同结果 |

#### 4.4 D 组 · F2-15..18（来源）

| 用例ID | 类型 | 步骤 / 输入 | 期望 |
|---|---|---|---|
| T2-F2-15-N | 正常 | 设置页持仓卡 | `main_source` 正常态；重启 22 只完整加载 |
| T2-F2-15-B | 边界 | `holdings.json` 缺失 | 空态引导导入；按钮禁用 + 说明；无 E_IO |
| T2-F2-15-E | 异常 | 写盘失败 | 原文件不破坏（原子写） |
| T2-F2-16-N | 正常 | `maintain_nav_history` | 滞后 ≤1 交易日；`n_test ≥40` |
| T2-F2-16-B | 边界 | 重复补全 | 幂等；既有日期不覆盖 |
| T2-F2-16-E | 异常 | 接口失败 | 保留旧值 + 滞后标注（不编造净值） |
| T2-F2-16-C | 口径 | 复算滞后与样本 | `staleness` = 最新交易日 − 最新净值日 ≤1 交易日；`n_test ≥40` 且与 `accuracy` 键逐项一致（±0） |
| T2-F2-17-N | 正常 | 健康页新浪行 | 三态 + 时间戳；回退路径可证（腾讯失败 → 新浪） |
| T2-F2-17-B | 边界 | 双失败 | 落既有降级；不阻塞估值链 |
| T2-F2-17-E | 异常 | 新浪长期不可用 | 按 (b) 标「仅探测·非主链」且无死代码残留 |
| T2-F2-18-N | 正常 | 健康页计数 | `fail_window_7d` 近 7 日；544 不出现为当前状态 |
| T2-F2-18-B | 边界 | 成功 ≥1 次后 | 计数按窗自然滚动（不抹历史、不回归 544） |
| T2-F2-18-E | 异常 | 无记录 / 时钟异常 | 「未检测」；以服务时间戳为准 |

#### 4.5 E 组 · F2-19..25（前端升级）

| 用例ID | 类型 | 步骤 / 输入 | 期望 |
|---|---|---|---|
| T2-F2-19-N | 正常 | 复盘 hero / 三窗口 / 对比卡 / 因子盘 | hero 出数；T1 行完整；对比卡 Δ 出数（或等待标注） |
| T2-F2-19-B | 边界 | 部分接通 | 分窗口独立标注；待填充样式（灰 + 虚线下划线） |
| T2-F2-19-E | 异常 | 数据未接通 | 「待填充」；不得示例数 / 估计值 |
| T2-F2-19-C | 口径 | 数字与后端一致 | hero 数字 == `/review/scores` 字段（0 差异） |
| T2-F2-20-N | 正常 | 徽章 hover | 双层编码（来源底色 × 置信度描边）；≥6 项 tooltip（来源/trace/MAE/方向/n/窗/披露） |
| T2-F2-20-B | 边界 | unknown / 字段缺失 | unknown 带 `conf_reason` 文案；缺数据留白不编造 |
| T2-F2-20-E | 异常 | trace 缺失 / 来源不可用 | 不显示链路；虚线「来源不可用」 |
| T2-F2-20-C | 口径 | 五档 × 四级同屏 | 颜色类由契约字段驱动，无硬编码 |
| T2-F2-21-N | 正常 | 7 页四态构造 | 空/加载/错误/成功均可真实触发（详见 U2-03） |
| T2-F2-21-B | 边界 | empty 条件 | 空态含「为什么空 + 下一步」；不渲染数字行 |
| T2-F2-21-E | 异常 | error 条件 | 可读原因 + 重试；不回退示例数据 |
| T2-F2-21-C | 口径 | 触发条件对照 | 与 03-ui-design-v3 §4 表逐页一致（7/7） |
| T2-F2-22-N | 正常 | 时间线 / 对账 / 事件链 | hit/miss 激活；第⑥步出值 |
| T2-F2-22-B | 边界 | 未到期 | 「待回填」仅未到期；数据缺失 → 「数据缺失待补」 |
| T2-F2-22-E | 异常 | 回填失败 | 状态如实；不伪造 hit |
| T2-F2-22-C | 口径 | 刷新一致性 | hit/miss 与 `t1_real` 符号一致；刷新后一致（非缓存假象） |
| T2-F2-23-N | 正常 | 长表滚动 | 表头 sticky 生效（Chrome/Edge）；半透明背景不穿透 |
| T2-F2-23-B | 边界 | 旧内核 / 窄屏 | 降级普通表头不报错；横向滚动保底 |
| T2-F2-23-E | 异常 | dialog 键盘操作 | Esc 关闭 + 焦点回位；Tab 可达且焦点可见 |
| T2-F2-24-N | 正常 | C 档 7 只行内 | 四态可见；与 `tier_reason` 一致 |
| T2-F2-24-B | 边界 | 状态缺失 | 「待验证」兜底 + 标注（不推测） |
| T2-F2-24-E | 异常 | 升 B / 降级 | 升 B 后信号列同步；降级有原因 |
| T2-F2-25-N | 正常 | 文案字典与线框 | 字典落盘；抽查 3 页 0 混用（未知 ≠ 0.00%、— ≠ 待填充） |
| T2-F2-25-B | 边界 | 新文案引入 | 未入字典不得上线（review 清单项） |
| T2-F2-25-E | 异常 | 全站混用扫描 | 字典外文案 0 处；口径错误文案 0 处 |

### 5. 数值口径正确性用例（N2-01..30 · 全 P0）

> 全部以**后端 API 原值与复算脚本**核对，禁止「看着对」；断言脚本执行期落 `evidence-r2/`。

| 用例ID | 类型 | 断言（复算式 / 判据） | 依据 |
|---|---|---|---|
| N2-01 | 口径 | vsum 主指标 = `/valuations/precision.estimate_quality.weighted_mae_rate`（估算档 intraday/holdings/proxy）；`official_summary` 单列 chip **不参与主指标**；全档 `weighted_mae_rate` 仅「全档参考」不得作主指标展示 | 09 v9.1 §4.5/D-1 |
| N2-02 | 口径 | 估算档加权 MAE 复算：`Σ(mae_rate_i×mv_i)/Σ(mv_i)`，与逐只 `mae_rate` 一致（±0.0002） | 09 §6.1、PRD G2-02 |
| N2-03 | 口径 | 非 unknown ≥21/22 复算式：`|{h : confidence(mode_h\|code_h) ≠ unknown}|`；unknown 须带 `conf_reason` | 09 §6.1 |
| N2-04 | 口径 | `conf_reason` 五值穷举 + **按序命中即停**：`mode_unknown → budget_exceeded → valuation_missing → nav_missing → no_samples`；仅当 `confidence=unknown` 时非 null | 09 §3.2/§3.1.1（v9.1/R-4） |
| N2-05 | 口径 | 误差 = `|est − real|`；`real = nav(D)/nav(D−1)−1`；不可配对日不入样本（不填 0） | 09 §3.2 |
| N2-06 | 口径 | 窗 = 最近 40 个可配对交易日；`n_test ≥5` 才产出统计、逐日累计；`window_filled_days` = 累计 X/40；`window_phase` ∈ warming/first_verdict/mature（5/40 双时点） | 09 §6.1/§9.1-3 |
| N2-07 | 口径 | 评分对象 = 每 `(date,code,mode)` 当日**最后一条**；按 `mode|code` 归键；不同 mode 各自成样本 | 09 §9.2-M1、08 §3.1 |
| N2-08 | 口径 | Δ = `hit_rate − baseline_rate`；baseline = `max(恒涨率,恒跌率)`（同测试窗去重叠全测试日集）；同 bars + frozen_config + seed 重复调用结果一致 | 09 §6.3 |
| N2-09 | 口径 | 影子盘实测基线 = `max(Σ[t1_real>0]/N, Σ[t1_real<0]/N)`；N=0 → null；`baseline_source` 恒 `measured` | 09 §6.3 |
| N2-10 | 口径 | grep `0.5830` 于产线代码/运行数据 **0 引用**（历史归档除外）；`FrozenParams.baseline_method` 非空 | 09 §6.3、PRD G2-07 |
| N2-11 | 口径 | 覆盖 = `(15+k)/22`；k = 原 C 档名单{022485,025500,018957,021528,457001,021662,163208} ∩ 升 B ∩ `validated`；`prediction_universe_count` == tier∈{A,B} 行数 | 09 §6.2 |
| N2-12 | 口径 | **挂档不计覆盖**：`verify_review_date` 非 null 的 pending/validating 行不进 universe、不计增长；>3 只挂档触发复审 | 09 §3.1、08 §4.1 |
| N2-13 | 口径 | `pending_verification_count`（C 档无结论）；`pending_verification_names ≤10`；`prediction_coverage_note` 两形态（批次中 / 结论后） | 09 §3.5 |
| N2-14 | 口径 | `t*_real = bars[i+H]/bars[i]−1`（H∈{1,3,15}）；`method=proxy_bar`；`proxy_code` 复算锚；幂等不重写 | 09 §4.8、08 §5.2 |
| N2-15 | 口径 | 已到期 up 回填覆盖率 100%（≥4/4）；缺 bars → 「数据缺失待补」不移除记录 | PRD G2-05、09 §4.8 |
| N2-16 | 口径 | `consecutive_days`/`gap_days` = 主文件 ∪ 归档（`(date,code)` 去重）；`history_days`；**≥60 可达**；`archive_merged` 布尔如实 | 09 §3.8 |
| N2-17 | 口径 | `fail_window_7d` = 近 7 自然日失败数（成功不抹历史、自然滚动）；`recent_failures ≤10`；544 不作当前状态 | 09 §3.10、C1 废弃登记 |
| N2-18 | 口径 | nav 滞后 ≤1 交易日；`n_test ≥40`；侧栏显示一致；补全幂等（既有日期不覆盖） | PRD G2-09 |
| N2-19 | 口径 | QDII：`change_rate = domestic.value + overseas.value`；`applied=true ⇒ fallback_reason=null`；对齐校验（overseas close_ts > domestic as_of 15:00） | 09 §3.4 |
| N2-20 | 口径 | `first_test_failed` 仅可在 **40 个可配对日窗且 n_test≥20** 时判定；未达门槛 → 挂档观察（`next_review_date` 预注册复评）；回退结论必须带数字（单段 MAE + 差距） | 09 §9.3-G1 |
| N2-21 | 口径 | `top_n∈{10,20}`；`weighted_change=Σw×chg/Σw`；`covered_weight_pct`；`included_markets ⊆ {A,HK,US}`；`excluded_count` 如实；`used=false` 剔除 | 09 §3.3 |
| N2-22 | 口径 | `scores[]` 行 = horizon T1/T3/T15，主值取全样本窗（`sample_window` 恒 `full`）；六个样本窗（d15…full）归因子页**不得混入**；未接通 `pending` + null | 09 §4.2/§9.1-7（R-2） |
| N2-23 | 口径 | `hero.{open_count, sample_period, data_kind}` 与请求/口径一致；响应 `note` 可读 | 09 §4.2 |
| N2-24 | 口径 | `verify_tiers` 判据：`lift≥1.0 且 Δ≥0 且独立触发日≥20 → 升 B`；`<20 → 挂档`；`else → 降 D` | 09 §4.8、10-r2 §2.4 |
| N2-25 | 口径 | `shadow_status ∈ {not_started,recording,qualified,gap}`（**不得 idle/ok/bad**）；`shadow_audit_status ∈ {idle,ok,bad}` | 09 §4.1/B1 |
| N2-26 | 口径 | 四层覆盖（估值 / 预测 / 开口 / 可信估值）分列声明、**禁止互替**（F-PM-01 教训回归） | PRD §0、需求 v3 §7 |
| N2-27 | 口径 | `qdii_lead_note` 仅 QDII 非 null；非 QDII 必须 null（不编造）；文案与 Brief §5.3 一致 | 09 §3.1 |
| N2-28 | 口径 | 日留档：一交易日一文件、≤22 行、收盘后写、重复调用不重写；不可写 → 告警不阻塞 | 08 §3.4 |
| N2-29 | 口径 | 预算：>20s 停继续估值；`budget_exceeded`；snapshot `budget{exceeded,processed,skipped}`；force 不受限 | 08 §3.5（T-01） |
| N2-30 | 口径 | 精度格式：比率 4 位 / `pp` 百分点 / 权重百分数 2 位；`effect_pp` 不再 ×100（沿用 R1 N-08 口径） | 09 §2.2、R1 `N-08` |

### 6. UI 四态用例（U-01..12 × 四态 · 48 条）

> 四态容器沿用 `StateBlock`（`data-state=empty|loading|error|success`）；触发条件与文案以 03-ui-design-v3 §4 表为准。
> 编号：`U2-XX-{空/载/错/成}`；U-01..06 为 P0，U-07..12 为 P1。

| U | 空态（为什么空 + 下一步） | 加载态 | 错误态 | 成功态主断言 |
|---|---|---|---|---|
| U-01 成绩位 | `U2-01-空` 复盘无成绩 →「尚无成绩记录，引擎未产出回测」+「待填充≠0」；不渲染数字 | `U2-01-载` hero 脉冲骨架 + 动作文案；不闪示例数 | `U2-01-错`「读取成绩失败」+ 重试；不白屏 | `U2-01-成` hero 三段式出数；T1 行完整；对比卡 Δ 出数（或等待标注）；待填充样式正确 |
| U-02 置信度徽章 | `U2-02-空` 来源不可用 → 虚线灰「来源不可用」；不编造 | `U2-02-载` 置信度未就绪按 unknown 处理，不闪假色 | `U2-02-错` 字段缺失留白；trace 缺失不显示链路 | `U2-02-成` 双层编码可区分；hover ≥6 项；unknown 带原因 |
| U-03 四态全量接线 | `U2-03-空` **7/7 页**空态可真实触发；文案含「为什么空 + 下一步」 | `U2-03-载` 7/7 加载态（骨架/脉冲 + 具体动作） | `U2-03-错` 7/7 错误态（可读原因 + 重试） | `U2-03-成` success 前不渲染数字；error 不回退示例数据 |
| U-04 回填态 | `U2-04-空` 未到期仅「待回填」（已到期不得出现） | `U2-04-载` 回填计算中中性占位，不显示假 hit | `U2-04-错` 数据缺失 →「数据缺失待补」如实标注 | `U2-04-成` hit/miss 与 `t1_real` 符号一致；第⑥步出值；刷新一致 |
| U-05 影子盘进度 | `U2-05-空` 归档缺失 → 按主文件计算 + 口径降级标注 | `U2-05-载` 进度骨架不闪假天数 | `U2-05-错` 读取失败可读 + 重试 | `U2-05-成` `x/60` 与后端一致；「归档合并计算」标注；idle/ok/bad 文案正确 |
| U-06 数据源健康 | `U2-06-空` 从未检测 →「尚未检测数据源」+「立即检测」 | `U2-06-载` 行内「检测中…」 | `U2-06-错`「配置读写失败」+ 原因（不丢已填） | `U2-06-成` 各源状态 + 时间戳；近 7 日计数；nav 滞后正常态；历史折叠可查 |
| U-07 C 档验证四态 | `U2-07-空` 状态缺失 →「待验证」兜底 + 标注（不推测） | `U2-07-载`「验证中（批次号）」金色态 | `U2-07-错` 读取失败降级展示 + 原因 | `U2-07-成` 四态与 `tier_reason` 一致；升 B 后信号列同步；未通过有原因 |
| U-08 QDII 标注 | `U2-08-空` 非 QDII 不显示（不编造） | `U2-08-载` 加载不闪假文案 | `U2-08-错` 字段缺失不显示 | `U2-08-成` 信号卡 + 持仓行均出现；文案与 Brief §5.3 一致；逻辑零变更 |
| U-09 sticky 表头 | `U2-09-空` 空表无行时表头不悬挂异常 | `U2-09-载` 骨架期表头占位正常 | `U2-09-错` 错误态不残留悬挂表头 | `U2-09-成` 滚动表头常驻（Chrome/Edge）；半透明不穿透；旧内核降级不报错 |
| U-10 键盘与焦点 | `U2-10-空` 空态下 Tab 可达重试/导航 | `U2-10-载` 加载期焦点不丢失 | `U2-10-错` 错误态按钮焦点可见 | `U2-10-成` Tab 顺序可达；Esc 关 dialog + 焦点回位；reduced-motion 无强动画 |
| U-11 数字口径悬浮 | `U2-11-空` 无数据数字（—/未知）tooltip 给「无数据」说明 | `U2-11-载` 加载不显示数值 tooltip | `U2-11-错` 错误态数字不出现 | `U2-11-成` 抽查 10 个关键数字均有口径 tooltip；不含无来源数字 |
| U-12 文案字典 | `U2-12-空` 空态文案取自字典 | `U2-12-载` 加载文案取自字典 | `U2-12-错` 错误文案含原因（非裸「失败」） | `U2-12-成` 抽查 3 页 0 混用（未知 ≠ 0.00%、— ≠ 待填充、待回填仅未到期） |

### 7. 负向断言（X2-01..20 · 全 P0 · 伪造数字/假兜底/静默失败零容忍）

| 用例ID | 断言（**不得**出现的行为） | 检出方式 |
|---|---|---|
| X2-01 | 全站 `+0.00%` 计数 = 0（未知不得渲染持平；数据非空时） | 全页面 DOM 扫描 |
| X2-02 | empty 条件下任何页面不渲染数字行 | 构造夹具 + DOM 扫描 |
| X2-03 | error 态不回退示例数据 / 假数据、不白屏 | 失败注入 + 截图 |
| X2-04 | 「待填充」处不得出现估计值 / 示例值 / 0（复盘 T3/T15、对比卡、基线） | DOM 扫描 + 契约字段比对 |
| X2-05 | `conf_reason` 仅在 `confidence=unknown` 时非 null；unknown 必须带原因（双向断言） | 接口全量遍历 |
| X2-06 | `0.5830` 产线代码/运行数据零引用；`baseline_source` 恒 `measured` | grep + 接口遍历 |
| X2-07 | `shadow_status` 不得出现 `idle/ok/bad`（取值域切换后无双重输出） | 接口遍历 |
| X2-08 | `t1_real` 无来源不写（`E_VALIDATION`）；缺 bars 标「数据缺失待补」，不编造、不移除 | 注入 + 文件核对 |
| X2-09 | QDII 回退不得静默（`applied=false` 必带 `fallback_reason`）；未达门槛不得宣布 `first_test_failed` | 注入 + 接口核对 |
| X2-10 | 挂档行不进 universe / 不计覆盖增长；不得「挂着 C 档不给结论」 | 覆盖率复算 + 行状态核对 |
| X2-11 | 四层覆盖口径不得互替（估值 ≠ 预测 ≠ 开口 ≠ 可信估值） | 文案/字段扫描（N2-26） |
| X2-12 | 前端不得硬编码后端文案（`verify_status_label`/`low_frequency_note`/`backfill_method_note`/`qdii_lead_note`） | 代码走查 + 文案变更注入 |
| X2-13 | 徽章/字段缺数据留白不编造；无来源数字零出现 | DOM + 接口对照 |
| X2-14 | recompute 旧记录必须可归档复读；INSERT-ONLY 无编辑入口（无 PUT/DELETE 路由） | 归档核对 + 路由探测 |
| X2-15 | `fail_count=544` 不得作为当前状态展示（仅审计折叠区） | DOM 扫描 |
| X2-16 | 导入不得出 E_IO 堆栈；`primary_exists=false` 不得再作误导展示 | 缺失态构造 + DOM |
| X2-17 | `frozen_params` 值零 diff；研究项不得改参（E2/E4 未复活、永不做空） | 接口 diff + grep |
| X2-18 | nav/通道断链不得静默：保持 unknown + reason（不编造净值） | 断供注入 |
| X2-19 | 回测不得冒充实盘（`data_kind` 区分）；六样本窗不得混入复盘页充当「三窗口」 | 接口核对 + DOM |
| X2-20 | 预算跳过不得静默（`budget_exceeded` + `snapshot.budget` 字段） | 预算注入 + 接口核对 |

### 8. 任务与接口口径用例（C2-01..06 · 全 P0）

| 用例ID | 步骤 / 输入 | 期望 |
|---|---|---|
| C2-01 | `POST /tasks {type:"maintain_nav_history"}` 连跑两次 | 幂等（points 集不变）；既有日期不覆盖；接口失败保留旧值；24h 内产生当日误差记录 |
| C2-02 | `verify_tiers`：缺省调用 / `params.targets` 传 9 只 | 缺省 = C 档 7 只；传参 = 清单逐只；两者结论均落 `tier_reviews.jsonl`（INSERT-ONLY） |
| C2-03 | `backfill_ledger {params:{mode:"recompute"}}` | 先全量归档（`reason=recompute_by_current_tier`）后重生成；`created_at` 继承；`_manifest.jsonl` 差异摘要（新增/移除条数、最早/最晚日期） |
| C2-04 | `POST /tasks` 注入冻结参数（`baseline_method` 与既有 9 键任一） | 全部 → `E_VALIDATION`（黑名单 B8） |
| C2-05 | `POST /ledger/backfill` `entries[]` 带可选 `method` / `proxy_code`；无对应 signal | 字段写入记录；无 signal → `E_VALIDATION`（沿用语义） |
| C2-06 | recompute 后读归档 | 旧记录可完整复读（INSERT-ONLY 记录级语义不破） |

### 9. R2 回归新增（R2-REG-01..05 · 全 P0）

| 用例ID | 步骤 | 期望 |
|---|---|---|
| R2-REG-01 | 裁剪窗口外记录后由归档重建（R2-13 验收④） | 归档可完整重建窗口外记录；重建集与归档原始集一致 |
| R2-REG-02 | INSERT-ONLY 纪律回归（E6-3 固化） | 台账/回填/留档均无编辑入口；回填只写 `t*_real`；重复执行不产生重复行 |
| R2-REG-03 | F-PM-01 覆盖口径回归（E5） | 四层覆盖分列、0 混用（与 N2-26 联动） |
| R2-REG-04 | 不倒退清单（PRD G2-12） | 涨红跌绿 / 未知 ≠ `+0.00%` / 隐私打码 / 徽章 mode 驱动 / 灰不加权 / INSERT-ONLY：0 违反 |
| R2-REG-05 | 冻结参数零 diff（PRD G2-12/08-r2 §8） | `frozen_params` 值不变；E2/E4 未复活；永不做空；研究项（F2-10）未改参 |

### 10. 判定标准与统计

**10.1 G-QA-01（本计划）自查映射**

| 判据 | 落点 |
|---|---|
| P0 功能每个 ≥3 条（正常/边界/异常） | §4：全部 P0 功能 4 条（N/B/E/C）+ §3 四目标 26 条 |
| 数值类含口径正确性用例 | §5 N2-01..30 + 各 `T2-*-C` |
| U-01..12 四态（v4.1 前置扩展要求） | §6：12 × 4 = 48 |
| 负向断言列明 | §7：20 条 |
| R1 沿用编号标注 | §2：124 条 + 19 条/组预期修订 |

**10.2 G-QA-02（执行后）判据**：P0 用例 100% 通过、P1 ≥90%、无未关闭致命/严重缺陷；数据错误一律 P0；失败必须稳定复现并附证据（截图/接口原文/日志），否则无效。

**10.3 缺陷纪律**：只提 `dev-lead`（六项必填：现象/复现路径/期望/实际/严重度/证据）；偶现问题单列并标注复现概率与环境，不阻塞主流程；本文件不产缺陷单（S5 产出 `04-defects-r2`）。

**10.4 分段判分（对齐 PRD T6）**：先判「全出值 + 全结论」（≥21/22、7/7、9/9、backfill ≥1、Δ 有值），后判数值目标（MAE / 覆盖增幅 / 开口量）；不达标按「明示降档、不虚报」收口，不以数值目标失守掩盖结论率完成。

## 自验收

- [x] 编码齐全：四目标 26 / 功能点 89 / 数值口径 30 / UI 四态 48 / 负向断言 20 / 任务接口 6 / 回归 5 = **224**（P0 159 / P1 63 / P2 2）
- [x] P0 功能每个 ≥3 条（正常/边界/异常/口径）——F2-01/05/06/11/12/13/14/16/19/20/21/22 各 4 条（§4）
- [x] 含口径正确性用例：N2-01..30 覆盖 vsum 主指标=估算档、官方档单列、Δ 复算、覆盖 (15+k)/22、挂档不计覆盖、conf_reason 五值按序命中、QDII 门槛 40 日且 n≥20
- [x] U-01..U-12 每个 ≥1 条四态用例（12 × 4 = 48，§6）
- [x] 负向断言逐条列出（20 条，§7）；「待填充/待回填」纪律、unknown 带原因、四态真实触发均有对应用例
- [x] R1 沿用用例已标注编号（§2 引用 `17-test-plan.md` §3/§4/§5/§6；124 条 + 19 条/组预期修订）
- [x] 每条用例只写「期望」；「实际结果」留待 S5 `18-test-report-r2`（本计划不执行、不产缺陷单）
- [x] 未修改产品代码/契约/架构文件/R1 工件（本文件为 `-r2` 新文件）；未触碰 `runtime/**`；未派发子任务
- [x] 使用 skill `test-scenarios`（只取方法：目标→条件→角色→步骤→期望→边界与异常）

## 下游交接

- **主消费方**：`qa`（S5 按 §1.4 批次执行本计划，产出 `18-test-report-r2` / `04-defects-r2`）；`dev-lead`（G-QA-02 分流与验收裁决）。
- **次消费方**：`frontend-dev` / `backend-dev`（开发自检对照：§4 E 组 + §6 U2 + §7 X2）；`product-manager`（复用 §3 四目标与 §5 N2 作为 G-PM-05 终验走查清单）。
- **消费方需执行**：backend 按 §4.1~4.4 与 §5/§8 自证口径；frontend 按 §6/§7 自证四态与负向断言；qa 在 S5 逐条填「实际结果 + 证据」。
- **残留风险**：
  1. 用例预期锚定契约 v9.1；实现期若契约出 v9.2+（如 QDII 参照源、`included_markets` 扩容），需 C1 增量同步本文件对应行（责任人：architect → qa，期限：S3 末）。
  2. QDII 隔夜参照指数符号未实测（09 §下游交接 残留风险 1）→ 用例预期以「探测失败即回退 + reason」为合法收口，不预设双段必然开通。
  3. 数值目标（MAE/覆盖增幅）首测不达标属预判风险（PRD T6）→ 按 10.4 分段判分与明示降档收口，不判本计划失效。
  4. 四态夹具依赖构造数据；若实现未暴露注入点，执行期以文件级 fixture + 停服替换实现并全量还原（责任人：qa，期限：S5 首周）。
  5. R2-04 复核依赖质量证据道（§3.1b）→ 证据道缺失时 B3 批用例阻塞，上报 `dev-lead` 定性（责任人：backend-dev，期限：B3 前）。
