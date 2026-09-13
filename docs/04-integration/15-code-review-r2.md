---
artifact: 15-code-review-r2
owner: dev-lead
version: v9
status: draft
supersedes: v8（断连修复单笔）→ v9（F2 伪影修复单笔）；R1 基线 `15-code-review.md` v2 原样保留
created: 2026-09-12
reviewers: [frontend-dev, backend-dev, architect, qa, orchestrator]
gate: G-DL-01
---

# 代码评审与方向纠偏 · 极境 ZenithLens（R2 升级轮 · S4 集成评审）

> 上游：`docs/02-frontend/13-frontend-report-r2.md`(v1)、`12-interface-request-r2.md`(v1)、
> `docs/03-backend/14-api-impl-report-r2.md`(v1，含 §7 偏差 9 条 / §8 缺陷留痕)、
> `docs/01-architecture/09-api-contract-r2.md`(**v9.1**，字段唯一法律)、`08-backend-arch-r2.md` / `07-frontend-arch-r2.md`(v3.1)、
> `docs/01-architecture/10-arch-review-r2.md`(v2 裁定/会签/契约变更)、`docs/00-charter/02-prd-v3.md`、`01-requirements-v3.md`(R2 需求 25 条)、
> `docs/05-qa/17-test-plan-r2.md`（S5 测试计划）。
> **v2 复验输入**：`10-arch-review-r2.md` §10（BLOCK-1 终审 + B1-1..B1-8 修复清单）、`14-api-impl-report-r2.md` §9/§10（修复记录）、`09-api-contract-r2.md` **v9.2 §10**（口径注记）。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`（只读源码/数据；未改产品代码）。
> **本轮 skill**：`code-review`（双轴：Standards——契约 v9.1/08-r2 口径 + Fowler 气味基线；Spec——PRD F2-01..25 / U-01..U-12 / A-01..A-10）、
> `triage`（缺陷定性分流状态机）。按 `capability-map §5` 纪律：skill 只供方法与检查项，不改变本工件结构与门禁判据。
> **实测方法**：`python app.py`（8791，Python 3.8.6）起服 → 22 端点真抓取 + 40 条字段断言 + 前端 CDP 断言 + 后端 184 测试 + build-r2 独立启动实测。
> 证据目录：`docs/04-integration/evidence-r2/`（smoke_*、ep_*.json、日志、build_manifest.json）。

## 摘要

1. **G-DL-01 = CONCERN（v1 初评）→ v2 复验轮：BLOCK 清零、建议 PASS（§7）**；头号红线「前端假数据填满界面」**未触发**（不判 FAIL）：mock 默认关闭且生产路径不加载，全仓 `fetch(` 唯一出口 `api.js`。
2. **2 条 BLOCK（v1 记录；v2 均已复验清零，见 §7）**：① `/review/scores` T3/T15 行 `formula`（gate_only/gate+ddsm）与实际计算（生产配置全档 H=3/15）**不一致**，且与 UI v3 U-01、QA 计划 T2-F2-11-B/G2-C02 的「未接通保持待填充」预期冲突——已按架构 §10.1 裁定「接通范围=T1、T3/T15 待填充」修复（B1-1..B1-8）；② **测试套件污染生产数据**：`test_nav_history_contract` 未隔离 `PROXY_QUALITY_PATH`，复跑复现清空 `data/snapshot/proxy_quality.json`——已修复并双跑 sha256 复验无污染。
3. **方向偏差六项**：契约对齐/职责/假数据/四态 4 项 PASS；需求对齐与契约漂移各带 1 条 CONCERN（即 BLOCK-1），无第二处漂移（字段级 44+9+B1~B9 抽核一致；`field_list` 15 键逐字；`shadow_status` 取值域已切换且无双重输出）。
4. **集成冒烟实测**：22 端点正路径 + 1 负向；21/22 首过（唯一超时为**预热期** `/holdings`，预热完成后 **0.29s** 复测 200——已登记 SHOULD-3）；字段断言 **40/40**；关键值：持仓 22 行（5 holdings + 17 official）、覆盖 15/22（+7 待结论）、开口 11/20、MVP 数字 T1 52.63%/基线 54.15%/Δ −1.52pp（open 61）等全部如实出数。
5. **测试计数**：后端 `unittest` **184/184 OK**（13.4s）；前端 `node --check` **14/14**；`verify_r2_ui_states.py` **92/92**；R1 集成脚本 11/11 与 20/21（1 FAIL 为脚本字面量 vs 实盘数据漂移，非回归）。
6. **build-r2**：`docs/04-integration/build-r2/` 完整可启动副本（134 文件 = 内容 131 + 构建者新增 3）；**MD5 逐文件对齐 131/131（0 不符）**；临时副本 `python app.py --port 8792` 独立启动实测通过（health/review/engine 均 200，自身 data 正常写入）。
7. 全部缺陷经 `triage` 分流：BLOCK-1 → 架构裁定 + 后端；BLOCK-2/SHOULD-1/2/3 → 后端（S3 见 open-issues）；无一条「直接转发前端」或「把需求缺陷当 bug」。
8. **v4（审计併轨）**：审计 3 BLOCK 收口修复项（A-1 测试连接→诚实降级 + C1；A-2 隐私→两开关+启动水合；A-3 事件链→读时重算 + 前端分支）；6 SHOULD = 本轮修 3 / 架构裁定 1 / 挂账 2；NIT 10 = 顺手修 5 / 挂账 5（§8.7~8.11）。
9. **v5（S5 修复轮终验）**：§8.10 全项销项（前端 7/7 · 后端 6/6 · 架构 4/4 · PM 补注 1/1，跟踪项入 §9.3）；独立复验 = 后端 **213/213**（无污染）+ live 探针 **8/8**（chain_source recomputed 对账 / top_n=20 / D2 字面 / S-c 诚实）+ 前端 **133/133**；build-r2 刷新 137 文件 / **MD5 134/134**；**建议放行 QA 回归**（§9）。
10. **v7（C1 delta-pass 三笔）**：四本账本人话记录 / 影子盘窗口 60（v9.5，走前回算口径诚实标注）/ 复盘筛选排序——单点复查 **PASS**（后端 **217/217** 无污染 + 滚动专项 9/9 + 前端 **152/152** + 旧 20 残留零）；build-r2 同步 **137 文件 / MD5 134/134**（§10）。
11. **v8（断连噪声修复单笔）**：客户端断连族四处静默 + 非断连照抛——单点复查 **PASS**（全量 **226/226** 无污染 + 断连专项 9/9 + 独立 RST 风暴 48 请求 **Traceback 0**、风暴后功能/刷新正常）；build-r2 同步 **138 文件 / MD5 135/135**（§10.5）。
12. **v9（F2 自碰撞伪影修复单笔）**：`_candidate_identity_ids` 身份集合 + `_incumbent_series`/`_f2_independence` 双侧排除自比对（真共线仍 fail）——单点复验 **PASS**（全量 **234/234** 无污染 + F2 专项 8/8 + crowd6 `correction` 块完整/klow2 未动/漂移披露）；build-r2 同步 **139 文件 / MD5 136/136**（§10.6）。

## 正文

### 0. 门禁判定

| 门禁 | 判定（v2 复验轮） | 依据 |
|---|---|---|
| **G-DL-01 · 组长评审** | **PASS（建议）** | v1 的 2 条 BLOCK 已逐条独立复验清零（§7.1/§7.2）；假数据红线未触发；S1/S2/S3 关闭（§7.3）；终判权在 orchestrator |
| **G-DL-02 · 开发版构建** | **PASS（建议）** | build-r2 刷新：MD5 133/133 + 独立启动实测（8795，`[T1 filled, T3 pending, T15 pending]`）；README-START 三步同步（§7.4） |

> v1 判定存档：G-DL-01 = CONCERN（2 条 BLOCK 未关）；G-DL-02 = CONCERN（联调/评审版）。v2 复验结论见 §7。

### 1. 方向偏差六项检查（逐项、带证据）

| # | 检查项 | 结论 | 证据（实测/源码） |
|---|---|---|---|
| 1 | **需求对齐** | ⚠️ CONCERN（1 处口径，BLOCK-1） | P0 全落地：F2-01 误差通道 v2（D-3 同 mode 末条）、F2-05 日留档、F2-06 批次 7/7 出结论（挂档带复查日 2026-10-23）、F2-11 回测出数、F2-12 回填（backfill 行含 method+proxy_code）、F2-13 归档合并、F2-14 实测基线、F2-16 净值史；U-01..U-12 12/12（前端报告 §1，92/92 断言复核）。**未发现 PRD 外功能**；唯一缺口=T3/T15 行口径（见 BLOCK-1，非方向级打回） |
| 2 | **范围蔓延** | ✅ PASS | P2 F2-10 未做（合规：只研究项）；P1 R2-04 的 9 只复核未跑，已列为 S5 前事项（报告中显式残留，非静默）；未见「为以后可能」的抽象层（`review.py` 为契约指定新深模块） |
| 3 | **职责越界** | ✅ PASS | 前端：数字全直读 + `format.js` 格式化；唯一换算式为视觉映射（`factors.js:90` lift→条宽）与 tooltip 文本直出，**无业务计算**（Δ/MAE/覆盖/进度全部后端字段）。后端：文案类（`*_label`/`note`）按契约由后端产出；未管展示格式 |
| 4 | **假数据残留（红线）** | ✅ PASS（不判 FAIL） | `index.html` 仅加载 `js/main.js`（module）；mock 仅 `?mock=1`/`localStorage` 时动态 import（`main.js:165-168`）；全仓 `grep "fetch("` 仅 `api.js:60`；`0.583` 仅存在于 `mock/mock.js` 与 `format.js` 注释、`engine.frozen_params.baseline_method` 固定文本（契约要求）；empty/error/loading 断言 92/92（empty 下 `.view-main` 隐藏、error 不回退示例、loading 不渲染数字） |
| 5 | **契约漂移** | ⚠️ CONCERN（1 处未申报漂移，BLOCK-1） | 字段级 44+9 抽核一致（40/40 冒烟断言：`conf_reason` 双向、`verify_*` 9 键、`estimated/official` 拆分、`window_phase`、`fail_window_7d`、`main_source/import_*`、`sample_window`、`progress` 合并字段、`field_list` 15 键逐字、B1 取值域 `recording/not_started/qualified/gap` 无 idle/ok/bad）。**漂移点**：T3/T15 `formula` 标签 vs 实际计算（BLOCK-1）。端点计数复核：56 路由 = 契约 55（53 UI + 2 内部）+ `/health`（基础设施，沿用 R1 记账惯例，不计入——非漂移） |
| 6 | **四态缺失** | ✅ PASS | `verify_r2_ui_states.py` **92/92**（7 页 × empty/error/loading 真实触发，走真实 `api.js`→`loadSlice`→`emptyWhen`）；证据截图（`zl_r2_state_empty_holdings.png` / `zl_r2_state_error_engine.png`）；`empty` 文案含「为什么空 + 下一步」；settings/holdings 空态带主行动按钮 |

### 2. 代码设计评审（Standards 轴）

#### 2.1 重复逻辑 / 过度设计 / 命名 / 硬编码

| 观察 | 判定 |
|---|---|
| F10 解析器合一（`proxy_map.parse_f10_holdings` 委托 `estimator.parse_top_holdings`）——架构债 D-R2-1 销项 | ✅ |
| `reconcile_result`（ledger_api:260）与 `fund_predict._reconcile`（:435）为同一 6 行逻辑的两份实现（历史遗留） | NIT-5（登记） |
| `review_verdict(evidence, samples=None)` 的 `samples` 参数全链未用 | NIT-1（与 SHOULD-1 同根） |
| `review.py` 深模块：唯一对外 `scores()`，缓存整文件原子替换，失败窗口 pending+null | ✅ 无过度设计 |
| 命名：`snake_case` 全项目（契约 §2.3）；字段名与 v9.1 逐字（抽核 40/40） | ✅ |
| 硬编码：`0.5830` 产线零计算引用（仅冻结表文本）；7 码清单/C 名单/行业基准为契约/架构文本明列；冻结参数集中 `engine.py` 顶部 | ✅ |
| 错误处理：缺口一律 null + 原因（`conf_reason` 五值）；网络/解析失败显式降级（新浪→单段/保留旧值）；`except Exception` 仅出现在「单资产失败不阻塞整体」的边界层且有降级语义 | ✅（BLOCK-2 属测试隔离，非运行时错误处理） |

#### 2.2 冻结纪律红线（逐项实测）

| 红线 | R2 状态（实测） |
|---|---|
| K=4 / p=0.25 / MIN_N=15 / SHRINK=10 / BAND=0.02 / 双否决分位 0.60/0.40 | ✅ `/engine/frozen-params` 实测值一致；`FROZEN_PARAM_KEYS` 追加 `baseline_method`（B8，测试覆盖 E_VALIDATION） |
| E2/E4 禁复活、禁 OR 合并 | ✅ `engine.GATE_LABEL` 无 E2/E4（测试断言）；仅 `excluded_gates` 信息位呈现「已证伪，禁止并入」（R1 语义保持） |
| 永不做空 | ✅ 无 short 分支；`direction=up/gray/abstain` |
| INSERT-ONLY | ✅ `write_entry` 同日同码 `E_CONFLICT`；回填独立 `backfill.jsonl` 只写 `t*_real`+method+proxy_code；`recompute` **先归档（`recompute_by_current_tier`）后重生成**；tier 修正行只追加（§8 留痕） |
| 组合权重 = 可信市值 | ✅ `weighting_basis=market_value` 恒 |
| 0.5830 退役 | ✅ 产线 `.py` 仅 `engine.py:686` 契约固定文本；R1 归档目录命中为历史痕迹（允许） |

#### 2.3 证据道与展示通道分离（ADR-0015 / D-R2-9）

- `accuracy.json`（展示精度，键 `mode|code`，逐日积累）与 `proxy_quality.json`（代理质量，`bars×nav` 史重建，40 日窗）**分键分文件**：`build_accuracy` 不读 proxy_quality；`build_proxy_quality` 不读 accuracy（源码核对）。
- `_tier_review_evidence` 以 `production_backtest`（full 窗）为主证据并补 `proxy_quality`（方向命中率）；`dir_hit_rate` 取后者（R2-04 判据方向）。实测证据道 22 条、7 只 C 档 `n_test=40`（0.625~0.9）。
- **注**：S4 复跑测试曾清空该文件（BLOCK-2）；已用产物自带 `build_proxy_quality` 恢复并同步 build。

### 3. 问题清单（BLOCK / SHOULD / NIT · 含分流）

> 分流纪律（`triage`）：做错了→开发；做对了但定义不对→PM；做对了但结构撑不住→架构；话岔了→架构改契约。**无一条直接转发前端**。

#### BLOCK（必须关闭，未关不进 S5）

**BLOCK-1 · `/review/scores` T3/T15 行口径不一致（未申报漂移）** —— 分流：**架构（裁定）→ 后端（实现对齐）**
- 现象：响应行 `formula` 标 `gate_only`（T3）/`gate+ddsm`（T15），但计算路径 `review.build_review_scores → factor_engine.evaluate_production(horizon=H) → production_definition(horizon=H) → _base_fired(bars, H)` 对三个 H **一律使用生产配置（gate+ddsm>0.52+双否决）**（源码 `factor_engine.py:647/723/1481`；`engine.predict_at` 无按 H 分支）。
- 冲突面：契约 v9.1 §4.2「`scores[]` 行 = 持有期 horizon（T1/T3/T15，**各自定式**）」与 v8 `ReviewScore.formula=定式`；`03-ui-design-v3.md` U-01「三窗口表分行标注接通状态（T+1 出数 / **T+3、T+15 未接通保持「待填充」**）」；QA 计划 `T2-F2-11-B` / `G2-C02`（未接通→`pending`+null）。三方口径互斥，当前实现选了「全部出数（生产配置）」且 `formula` 标签沿旧值。
- 实测证据：`ep_review_scores.json` T1 0.5263/0.5415/−0.0152、T3 0.6857/0.5824/+0.1033、T15 0.5517/0.6422/−0.0904，`sample_window=full` 三行；`test_review_scores.py` 仅断结构（mock `evaluate_production`，不断定式）。
- 处置建议（不代改）：架构在 `09-r2`/`10-r2` 收口「各自定式」的含义与 T3/T15 是否出数（若定义变更→契约版本 +1 并同步 UI/QA）；后端按裁定二选一对齐：① T3/T15 用各自定式（gate_only / gate+ddsm）计算；或 ② 统一为生产配置并修正 `formula` 文案 + 更新 UI v3/QA 相应预期。后端改后重生成 `review_scores.json` 缓存并补测试断言（formula ↔ 计算一致）。
- 影响：R2-11 验收③「口径同页一致」、PM 终验「数字可信」；不涉及数据伪造，不判 FAIL。

**BLOCK-2 · 测试套件污染生产数据（证据道被清空）** —— 分流：**后端**
- 现象：`tests/test_nav_history_contract.py` 的 setUp 隔离了 NAV_STORE/ACCURACY/DAILY/ledger 等路径，但**未隔离 `valuation.PROXY_QUALITY_PATH`**；其 `maintain_nav_history([{"code":"000001"}])`（5 处调用）透传 `build_proxy_quality`，以 `entries={}` 覆写**真实** `data/snapshot/proxy_quality.json`。
- 实测证据：S4 复跑 `python -m unittest discover -s tests -p "test_*.py"`（184/184，13.4s；日志 mtime 23:47:45）期间该文件 mtime=23:47:41、体积 67B（空表）；对 `data/**`+`ledger/**` 全量 mtime 审计，仅此一文件落于测试窗（其余均 <23:45 或未变）。已用产物自带 `valuation.build_proxy_quality()` 恢复 22 条（含 7 只 C 档 `n_test=40`）并同步 build-r2。
- 风险：QA 在 S5 跑测试后再取 R2-04 证据 → 证据道为空被误读为「无证据」；README 内「可选自测」也会触发。
- 处置建议（不代改）：`test_nav_history_contract` 补 `PROXY_QUALITY_PATH` 隔离（照 `test_proxy_quality.py:36-40` 模式）；建议加一条「测试套件运行前后产线数据文件 mtime/内容不变」的守卫断言（防同类再生）。

#### SHOULD（建议改，可排下轮；登记 open-issues）

- **SHOULD-1 · `review_verdict` 层①缺 `n_test<20` 支路**（`10-arch-review-r2 §2.4` 冻结判定表：「独立触发日 <20 **或 n_test<20** → 挂档」；实现仅查 `independent_trigger_days`，`samples` 参数未用）。当前 7 只批次（indep 0/4/2/2/3/3/6）与证据道 `n_test=40` 均不受影响；对未来「indep≥20 且 n_test<20」批次存在误升/误降风险。归后端（随 BLOCK-1 一并评估）。
- **SHOULD-2 · 新浪 (b) 切换标注未实现**（08-r2 §6.3 + 会签加严②：连续 ≥3 次探测失败或 4xx 达 7 天 → 转「仅探测·非主链」并同步健康页文案）。实测本机 `sina_rt` `fail_window_7d=5`、`status=bad`，但文案仍为原始 note（无降级标注回写）。归后端；若 PM 认为该失败是环境性而非长期不可用，则由 R2 末三数字复盘（触发次数/成功率/原因分布）裁定后处置。
- **SHOULD-3 · 冷启动预热期 `/holdings` 阻塞**：起服 6s 后首测 `/holdings` 30s 超时（客户端），预热完成后同一端点 **0.29s/200**。前端该端点超时 8s → 用户在预热期打开首屏会命中 error+重试。建议后端预热期快速返回缓存/加就绪信号，或前端对首屏失败做「预热中」文案+自动重试。归后端+前端联合（S5 前实测定位）。

#### NIT（吹毛求疵，可不改）

- **NIT-1**：`review_verdict` 死参数 `samples`（与 SHOULD-1 同根，修复时一并处理）。
- **NIT-2**：`archive_merged=false` 的 note 文案「归档缺失或不可读」二合一；当前尚无裁剪（归档未生成），文案可区分「未生成/不可读」。
- **NIT-3**：`data/cache/nav/` 目录混合 `fund_official.json`/`fund_valuation.json`/`<code>.json`（后端 D9 已自登记，R3 清理）。
- **NIT-4**：R1 集成脚本 `verify_shadow_progress_fe.py` 断言语义依赖旧数据（「未评估」vs 现「降级」）→ 20/21；S5 复基线时更新脚本字面量或改动态断言。
- **NIT-5**：`reconcile_result` 双实现（ledger_api / fund_predict），可归并。

### 4. 后端偏差 9 条逐条裁定（§7 申报 · 是否有方向性偏差）

| # | 内容 | 裁定 |
|---|---|---|
| D1 | `163208` 油气 QDII 双段未启用（参照指数不在 {US_NDX, HK_HSI} 枚举） | **接受**：契约 §3.4 原文「163208 ← 162411 **视参照可得性**」，未启用=合规保守；如 PM 需补 US_OIL 类参照 → 架构版本 +1（残留风险已列） |
| D2 | 首轮 `verify_tiers` 形状缺陷（已修复 + 回归 + INSERT-ONLY 修正行 + 数据修复） | **接受**：根因/修复/留痕完整（§8），修正行只追加，读端 last-wins；符合 INSERT-ONLY |
| D3 | accuracy 条目 n≥1 即写（统计值 n≥5） | **接受**：为保留 `matched_days`（`window_filled_days`/`no_samples` 依赖）；与「n<5 不产出统计」一致 |
| D4 | 挂档 `verify_status=validating` | **接受**：契约 §3.1 允许 `pending_validation/validating` 且带复查日（挂档语义成文） |
| D5 | `budget_exceeded` 依赖当日 snapshot.budget | **接受**：序内行为（跨日自然落 `valuation_missing`），已注释 |
| D6 | `eastmoney_top_holdings` 默认 topline 10→20 | **接受**：R2-02 启用前 20（08-r2 §3.2）；需要 10 的场景显式传参 |
| D7 | `verify_tiers` 默认 targets = 当前 C 档（空→空批次） | **接受**：与契约「缺省 = C 档 7 只」在批内等价（当时 C 档=7 只清单）；R2-04 显式传 9 只 |
| D8 | daily 留档首日仅 `20260912` | **接受**：收盘后写、幂等；依赖每日维护任务（残留风险已列） |
| D9 | `data/cache/nav/` 混合文件名 | **接受**：不冲突；R3 目录细分（NIT-3 备案） |

> **结论：无方向性偏差需打回**；但 §7 未申报的 BLOCK-1 属新增发现（非 9 条内），按 BLOCK 处置。

### 5. 集成冒烟证据（S4 实测 · 8791）

**起服**：`python app.py`（Python 3.8.6，PID 受控重启）；预热（净值史/回填/回测缓存）后台执行，进程立即可服务。
**端点巡检**（`evidence-r2/smoke_fetch.py`：22 正 + 1 负）：

- 正路径 **21/22 首过**；唯一未过为 `/holdings?with=valuation,nav,prediction`（预热并发期 30s 客户端超时）→ 预热完成后复测 **200 / 0.29s**（已登记 SHOULD-3）。
- 负向：`/review/scores?data_kind=bogus` → **400 / E_VALIDATION**（PASS）。

**字段断言**（`smoke_checks.py`）：**40/40 PASS**，含：

| 面 | 实测值（证据文件） |
|---|---|
| 持仓 | 22 行；`verify_status`：15 `validated` + 7 `validating`；`qdii_lead_note` 6 只（024239/457001/163208/016665/012922/021662）；`unknown` 22 只全部带 `conf_reason=nav_missing`（首日无配对日，如实）；`trace[holdings].detail` 有结构明细 |
| 估值精度 | `estimate_quality`（count=5）/`official_summary`（17 只 · 84.44%）拆分；`window_filled_days=0`、`window_phase=warming`、`window_status_label=「累计 0/40 日」`；全档参考保留 |
| 覆盖 | `prediction_universe_count=15` == A+B 行数；`pending=7`；note=「预测覆盖 15/22（+7 待结论）」；待结论名单 7 只 |
| 信号 | `rolling_open_assets=11`、`rolling_window_days=20`、低频文案在 |
| 引擎 | `shadow_status=recording`、`shadow_audit_status=bad`（小样本偏差，如实）、`consecutive=20/60` == `/ledger/shadow.progress` |
| 冻结表 | K/p/MIN_N/BAND 全对；`baseline_method` 文本含「实测 + 0.5830 已退役」；`weighting_basis=market_value` |
| 台账 | 行含 `t1_real_method/backfill_proxy_code`；已回填恒 `proxy_bar`；`field_list` 15 键逐字；`progress` 4 新字段齐 |
| 复盘 | `hero.data_kind=backtest`；T1 0.5263/0.5415/−0.0152（61 开口，2025-05-26..2026-06-22）；`shadow_live` 可读（T1 1.0/0.5559/+0.4441） |
| 数据源 | 四源齐 `fail_window_7d`；eastmoney `fail_count=544` 仅累计；sina `bad`/5 |
| 设置 | `main_source.path=data/holdings.json`（count=22）；`import_available=false` + 可读原因 |
| 因子 | `bootstrap_percentiles_measured`+`real_engine` 兄弟并存（V11） |

### 6. 测试与 build 校验

#### 6.1 测试计数（S4 复跑）

| 项 | 命令/方式 | 结果 |
|---|---|---|
| 后端契约测试 | `python -m unittest discover -s tests -p "test_*.py"` | **Ran 184 tests … OK**（13.4s；R1 117 + R2 67）；日志 `evidence-r2/backend-tests.log` |
| 前端语法 | 全 14 JS（复制 `.mjs`）`node --check`（Node v18.17.1） | **14/14 PASS** |
| 前端四态+R2 触点 | `python docs/02-frontend/evidence/verify_r2_ui_states.py` | **TOTAL 92 PASS 92 FAIL 0**（exit 0） |
| R1 集成脚本 A | `verify_shadow_fe.py`（live 8791 + CDP 9333） | **11/11**（exit 0） |
| R1 集成脚本 B | `verify_shadow_progress_fe.py` | **20/21**；1 FAIL=脚本字面量（期望 idle 时代「未评估」）vs 实盘 `shadow_audit_status=bad` 渲染「降级」→ 数据漂移非回归（NIT-4） |

> BLOCK-2 注：本次复跑触发 `proxy_quality.json` 清空并已恢复；修复前「跑测试→取证据」顺序会互相破坏（QA 注意）。

#### 6.2 build-r2 校验（`docs/04-integration/build-r2/`）

- 组成：**134 文件** = 源码 14 py + `static/**` 17 + `tests/**` 29 + `data/**` 64 + `ledger/**` 7（内容 131） + 构建者新增 3（`README-START.md` / `start.cmd` / `start.ps1`）。
- **MD5 逐文件对齐：131/131 matched，0 mismatched**（`evidence-r2/build_manifest.json`；脚本 `verify_build_alignment.py` 可复跑）。**v2 复验轮刷新后为 133/133、136 文件——见 §7.4。**
- **独立启动实测**：临时副本 `python app.py --port 8792` → `health/review/scores/engine/status` 均 200/ok；预热写入副本自身 `data/**`（净值史/快照/证据道）——证明 build 自包含可跑。
- README-START：三步内启动（cd → `python app.py` → 浏览器 127.0.0.1:8791）；含 R2 已知限制 9 条（v2 已同步为「BLOCK 清零」版，见 §7.4）。

### 7. 复验轮记录（v2 · 2026-09-13 · BLOCK 销项）

> 输入：`10-arch-review-r2.md` §10（BLOCK-1 终审 + B1-1..B1-8 修复清单）、`14-api-impl-report-r2.md` §9（B1/B2/S1）与 §10（S2/S3）、`09-api-contract-r2.md` v9.2 §10。
> 方法：**独立复验**（源码走查 + 双跑测试 + 实测冒烟 + 冷启动探针 + build 重建与启动实测），不采信报告转述。
> 证据目录：`docs/04-integration/evidence-r2/`（`verify_tests_no_pollution.json`、`coldstart_s4.json`、`backend-tests-run1/2.log`、`ep_review_scores_v2.json`、`build_boot_v2.json`、`build_manifest.json`）。

#### 7.1 BLOCK-1 逐条对账（裁定清单 B1-1..B1-8）

| # | 裁定要求（10-r2 §10.4） | 复验结论 | 独立证据 |
|---|---|---|---|
| B1-1 | 仅 H=1 评估；T3/T15 一律 `_pending_row`（不得输出 H=3/15 数字） | ✅ 关闭 | `review.py:136-170`（仅 `production_definition(1)` 评估；T3/T15 走 `_pending_row`）；实测 T3/T15 `pending` + 三值 null + `open_count=0`（`ep_review_scores_v2.json`） |
| B1-2 | `formula` 与计算定义绑定（可注入变体判别） | ✅ 关闭 | `production_definition.formula="gate+ddsm+veto"`（factor_engine）；`review._formula_of(defn)`；探针断言「T1 row formula == 定义 formula」 |
| B1-3 | `baseline_status` 枚举 `filled/pending`（禁 `ok`） | ✅ 关闭 | 响应全文无 `"baseline_status": "ok"`（backtest + shadow_live 双口径断言） |
| B1-4 | 响应 `note` 含 `pending_cv` + 「待验证」 | ✅ 关闭 | backtest / shadow_live note 断言 PASS |
| B1-5 | `review_scores.json` 重生成（T3/T15 去数字） | ✅ 关闭 | 缓存 `generated_at=2026-09-13T00:32:46+08:00`；T1 `filled`(61) / T3/T15 `pending` |
| B1-6 | hero 与 T1 值/状态双一致 | ✅ 关闭 | hero = 0.5263 / 0.5415 / −0.0152 / open 61 / data_kind=backtest，与 T1 行全等 |
| B1-7 | 回归增补 + 全量证据 | ✅ 关闭 | 全量 **199/199 ×2**（`verify_tests_no_pollution.json`）；`test_review_scores.py` 8 条含 B1-1/B1-3 断言 |
| B1-8 | 层①补 `n_test<20` 支路 + 移除死参数 `samples` | ✅ 关闭 | 直调：`n_test=15→hold`、`n_test=20→pass`、缺省兼容；签名 `co_varnames[:argcount] == ["evidence"]` |
| 附加 | T3/T15 `formula` 保留定式标签 | ✅ | `gate_only` / `gate+ddsm`（探针断言） |

#### 7.2 BLOCK-2 复验（测试套件无产线污染）

- **双跑**：`run1 rc=0 Ran 199 tests OK`；`run2 rc=0 Ran 199 tests OK`。
- **sha256 守卫（12 个产线文件）**：`proxy_quality / review_scores / accuracy / valuation_history / health / health-log / holdings / qdii_correction / tier_reviews / qdii_review / shadow_signals / backfill` —— 三向断言（run1 前后 / run1_after↔run2_before / run2 前后）**全真**，`diffs=[]`。
- `proxy_quality.json` sha256 `d430c8c9043682c2…`（与后端 §10.3 报告一致；v1 事故时曾为 67B 空表）。
- **防再生**：`test_nav_history_contract.test_suite_guard_real_data_paths_untouched` 保持通过（套件内守卫）。

#### 7.3 SHOULD 关闭（S1/S2/S3）

| # | 复验结论 | 独立证据 |
|---|---|---|
| S1（`n_test` 支路 / 死参数） | ✅ 关闭 | §7.1-B1-8；`test_tier_review.py` 10 条含 `n_test` 用例 |
| S2（新浪 (b) 标注） | ✅ 关闭 | 实测 `/data-sources/health`：sina `note="仅探测·非主链（近 7 日失败 6 次）…"`；`test_health_window.SinaDegradeAnnotationTest` 3 条 |
| S3（冷启动 `/holdings` 阻塞） | ✅ 关闭 | 独立探针：ready 1.15s；**ready+1s `/holdings` 256ms / 22 行**；+6s 339ms（v1 复现为 30s 超时）；`[warmup] +N.NNs` 阶段日志在位 |

#### 7.4 复验轮集成与 build 证据

- 冒烟探针 **20/20 PASS**（`coldstart_s4_probe.py`）：覆盖 T1/T3/T15、hero、note、formula 绑定、`n_test` 直调、shadow_live、S2 标注、端口释放。
- 前端抽跑：`node --check` **14/14**；`verify_r2_ui_states.py` **92/92**（后端改动未破坏前端契约面：`baseline_status` `ok→filled` 不影响前端 `=== 'pending'` 判定）。
- **build-r2 刷新**：**136 文件** = 内容 133（14 py + 17 static + 30 tests + 64 data + 8 ledger）+ 构建者新增 3（README/start.cmd/start.ps1）；**MD5 逐文件对齐 133/133，0 不符**（`build_manifest.json` 已重生成）。
- **build 独立启动实测**：临时副本 `python app.py --port 8795` → health ok；`/review/scores` = `[T1 filled, T3 pending, T15 pending]`（`build_boot_v2.json`）；端口释放 True。
- README-START 已同步（v2「本版变更」6 条 + 已知限制 9 条）。

#### 7.5 剩余 NIT 挂账（非阻塞）

| # | 状态 |
|---|---|
| NIT-1（`samples` 死参） | ✅ 已随 B1-8 关闭 |
| NIT-2（归档文案「缺失/不可读」二合一） | 挂账（R3 文案细化；当前语义不误导） |
| NIT-3（`data/cache/nav/` 目录混名） | 挂账（R3 清理，D9） |
| NIT-4（R1 脚本旧字面量） | 挂账（S5 复基线随手更新；架构 §10.3 已列） |
| NIT-5（`reconcile_result` 双实现） | 挂账（低优先，可归并） |

#### 7.6 收口结论

- **BLOCK-1 ✅ 关闭**（B1-1..B1-8 逐条独立复验通过）；**BLOCK-2 ✅ 关闭**（199×2 + 12 文件 sha256 三向一致 + 守卫用例）。
- **S1 / S2 / S3 ✅ 关闭**；NIT 挂账 4 条（非阻塞，见 §7.5）。
- **G-DL-01 建议 = PASS**：方向偏差六项无新增 CONCERN；契约面已对齐 v9.2 §10 注记；假数据红线未触发。
- **G-DL-02 建议 = PASS**：build-r2 可独立启动 + README 三步 + MD5 全对齐；终判权在 orchestrator。
- 建议：orchestrator 判 PASS 后进 **S5**（qa 按 `17-test-plan-r2.md` 执行；上手即跑全量测试不再污染数据）。

### 8. S5 缺陷分流 + 审计併轨 · 统一修复指令（v3 QA 分流 → v4 审计併轨）

> 输入：`docs/05-qa/04-defects-r2.md`（R2-D1 P1 + R2-D2/D3/D4 P3）、`docs/05-qa/18-test-report-r2.md`（P0 157/159 · P1 63/63 · P2 2/2；G-QA-02 自判 FAIL，两 P0 失败同源 R2-D1）；**v4 增补输入**：`docs/04-integration/16-fake-feature-audit-r2.md`（假功能审计：BLOCK×3 + SHOULD×6 + NIT×10，见 §8.6~8.11）。
> 分流纪律（triage 四象限）：「做错了」→ 前端/后端；「做对了但定义不清」→ PM；「结构撑不住」→ 架构；「话岔了」→ 架构改契约。
> **结论速览**：R2-D1 = **前端做错**（实现偏离 UI v3 §4 触发条件 + 遮蔽主内容）；R2-D2 = **后端做错**（契约字面偏差）；R2-D3 = **后端做错**（健壮性；最小修 + 余项挂账 R3）；R2-D4 = **前端做错**（文案未联动）；**审计 3 BLOCK**：A-1 前端做错（谎言呈现，选诚实降级 + C1 真探测架构裁定）/ A-2 前端做错（开关无行为 + 刷新水合缺口）/ A-3 后端做错（写链缺失，选读时重算）。**无一条需 PM 先行裁定**（PM 仅文案类备注；架构裁定 2 项 C1/C2）。

#### 8.1 R2-D1（P1）· 分析页空态触发条件不符 → **前端做错**（本轮修）

- **裁定依据**：① `03-ui-design-v3 §4` 分析行空态触发 =「**监控集合为空，或全部资产无预测记录**」；② `02-prd-v3` F2-21「emptyWhen 全量接线；空态文案按 §4 逐页定义」；③ R1 `T-UI-12` 边界（无开口行仍应展示「参与预测持仓表」）。实现以「全窗 `open_count==0`」参与空态且与 predictions 片 **OR 合并**（`analyze.js:22-25` portfolio `emptyWhen` + `:41`），使「有 15 条预测记录、当日 0 开口」被误判整页 `empty`：预测表/三窗口卡被隐藏，「为什么空」文案与实际矛盾——**偏离规格，属代码缺陷**（实现注释自称「= 监控集合为空 或 全部资产无预测记录」，与代码条件亦不一致）。**不需 PM 先行裁定**；PM 侧仅可选文案备注（§8.5）。
- **责任方**：`frontend-dev`。
- **修复指令**（可直接转交）：
  1. `static/js/views/analyze.js`：拿掉 portfolio 片的 empty 判定（删除其 `emptyWhen` 或恒 `false`）；**页面空态唯一数据条件 = `/predictions.rows.length === 0`**（等价覆盖 §4 两种表述；**不得使用 `open_count`**）。
  2. `viewState()`：保留 loading/error 合并；`empty` 仅在 predictions 空时成立。**`rows>0` 且全窗 `open_count=0` → `success`**：三窗口卡与预测表照常渲染（`open_count=0` 按既有灰/零口径展示，新增文案前先入 `copy.js`）。
  3. 空态卡「为什么空」按触发因素**如实二分支**（由数据判定，不编造）：监控集合为空 →「当前没有纳入监控（A/B 档）的资产」；无预测记录 →「今日没有可展示的预测记录（`/predictions` 行为 0）」。主标题保留 §4 文案「今日没有触发开口的资产」+ 四要素事实卡（数字直读）+ 低频说明。
  4. 同步更新 `docs/02-frontend/13-frontend-report-r2.md` §2 空态条件表（移除「组合全窗 open_count=0」表述）与 `docs/02-frontend/evidence/verify_r2_ui_states.py` 分析页断言；**新增正向回归用例**：「rows=15 且全窗 open_count=0 → success」（即 R2-D1 场景）。
  5. 若产品希望「无开口日」给用户提示：只能以**页内信息条**（非四态空态、不隐藏 `.view-main`）呈现，且文案先入字典——**不得由实现者擅改空态触发口径**。
- **验收断言（qa 回归用）**：
  - **A1（正向·R2-D1 场景）**：rows=15、全窗 `open_count=0` → `#view-analyze` `dataset.state=success`；`.view-main` 可见；`#an-body tr`=15；三窗口卡渲染。
  - **A2（空态可触发）**：stub `rows=0` → `state=empty`、`.view-main` 隐藏、无数字行（X2-02 维持）、「为什么空」文案与实际分支一致。
  - **A3（负向）**：rows>0 时页面不得出现「无预测记录/监控集合为空」文案；`open_count=0` 不得使页面进入 empty。
  - **A4（回归）**：`U2-03-成`、`T2-F2-21-C` 转 **PASS**；其余 6 页 success 不回退；`verify_r2_ui_states.py` 更新后全过。

#### 8.2 R2-D2（P3）· `main_source.path` 绝对路径 → **后端做错**（本轮修）

- **裁定**：契约 §3.11 字面 `path: "data/holdings.json"`（展示标识）；实现直出文件系统绝对路径（`holdings.py:312 main_source_status()` 返回 `HOLDINGS_PATH`）。字段名/类型正确、**值格式**偏离契约 → **按契约字面修实现**（不改契约：该字段是展示化标识，非内部路径；无版本变更必要）。
- **责任方**：`backend-dev`。
- **修复指令**：`main_source_status()` 的 `path` 返回 **`"data/holdings.json"`**（正斜杠相对标识）；内部文件操作仍用绝对路径；`exists/count/modified_at/readonly` 语义不变；`primary_path/legacy_path`（可选导入源语义）本轮不动。
- **验收断言**：`/settings/holdings-data.main_source.path == "data/holdings.json"` 且不含盘符/反斜杠；`exists=true`、`count=22` 不变；`test_holdings_main_source` 增断言；前端无需改。

#### 8.3 R2-D3（P3）· 同型任务并发失败（`E_UNKNOWN`） → **后端最小修 + 余项挂账 R3**

- **裁定**：任务调度健壮性缺陷——同型任务无互斥，两任务对同一批 nav/accuracy 原子写产生竞态，`E_UNKNOWN` 直透原生 `WinError 5/2` 文案（违反错误可读纪律）。**数据无损、单用户串行不受影响**（QA 异常注入复现）→ **本轮修最小版**；队列化/自动合并/跨型加固 → **挂账 R3**（理由：涉及任务调度设计评审，非本轮验收面）。
- **责任方**：`backend-dev`。
- **修复指令**：
  1. **同型互斥**：`POST /tasks` 提交时若存在同 `type` 的 `queued/running` 任务 → 拒绝（建议 `E_CONFLICT` 409，message「同型任务进行中：<task_id>；可 GET /tasks 查询」）；不落 failed 记录、不启动第二线程。
  2. **错误可读化**：`_run_task` 捕获 `OSError` → `E_IO` + 中文可读 message（不含 `WinError` 原文；诊断细节走 stderr 日志）；其余异常 message 收敛为一句可读文案。
  3. 若实现中确认**跨型**任务也竞态同一文件 → 升级为全局任务串行并回报 `dev-lead`（不自行扩大范围）。
- **验收断言**：快速连发同型×2 → 第二个返回 4xx 可读错误，最终同型任务仅 1 个 `done`；`GET /tasks` 全表无 `WinError` 子串；串行提交仍 `done`；`data/cache/nav/*` 点数与 `accuracy.json` 内容前后不变（数据保全）；`test_app_contract` 增同型互斥用例。
- **挂账（R3）**：任务队列串行化/去重自动合并 + 原生错误统一映射（范围与理由已入 `open-issues`）。

#### 8.4 R2-D4（P3）· 降级分支 `histNote` 文案矛盾 → **前端做错**（本轮修）

- **裁定**：U-05 口径（归档缺失 → 按主文件计算 + 口径降级标注）下，`engine.js:147` 的 `histNote` 恒拼「（含归档）」，与 `ARCHIVE_FALLBACK_NOTE` 自相矛盾（归档不可读分支）。属**文案联动缺陷**；一行修正，07-r2 §2.5 示例句建议由前端在报告中注明「`archive_merged=true` 时」即可，**不涉契约/架构版本**。
- **责任方**：`frontend-dev`。
- **修复指令**：`histNote` 按 `prg.archive_merged` 联动：`true` → `可用历史 N 日（含归档）`；`false` → `可用历史 N 日（主文件）`（文案入 `copy.js` 字典）；副文案拼接不变。
- **验收断言**：stub `archive_merged=false` → HUD 副文案不含「含归档」且与 `ARCHIVE_FALLBACK_NOTE` 同口径；`true` → 含「含归档」；`U2-05` 记录同步；负向：任一分支不得同屏出现「（含归档）」×「按主文件计算」矛盾组合。

#### 8.5 汇总表（一页分流）

| 缺陷 | 严重度 | 定性（四象限） | 责任方 | 处置 | 验收 |
|---|---|---|---|---|---|
| R2-D1 分析页空态 | P1 | **做错了**（偏离 UI v3 §4 + 遮蔽主内容） | 前端 | **本轮修**（§8.1） | A1~A4（U2-03-成 / T2-F2-21-C 转 PASS） |
| R2-D2 主源路径 | P3 | **做错了**（契约字面偏差） | 后端 | **本轮修**（§8.2） | `path=="data/holdings.json"` + 回归 |
| R2-D3 同型并发 | P3 | **做错了**（健壮性；数据无损） | 后端 | **本轮修最小版**；队列化挂账 R3（§8.3） | 409 可读 + 无 WinError + 数据不变 |
| R2-D4 降级文案 | P3 | **做错了**（文案未联动） | 前端 | **本轮修**（§8.4） | 分支断言（含/不含「含归档」） |

- **PM 备注（不阻塞修复）**：① UI v3 §4 分析行「触发条件」与「文案」存在字面张力（触发=无预测记录；文案=无开口）——建议 PM 在文案增补中一句话明确「无开口日是否需要页内提示」（可选）；② `18-test-report-r2` §7 观察项 1/2（`+0.00%` 语义、五源/四源）建议 PM 备注入文档修订。
- **流程**：修复完成 → 前端/后端各自跑所属测试（前端 `node --check` + `verify_r2_ui_states.py`；后端 `unittest` 全量）→ 主 Agent 安排 **dev-lead 复验（本文件 +1、build-r2 刷新）** → **qa 回归**：`U2-03-成` + `T2-F2-21-C` + D2/D3/D4 断言 → G-QA-02 复审。

#### 8.6 审计併轨（已併入 · 2026-09-13）

- 输入：`docs/04-integration/16-fake-feature-audit-r2.md`（v1，165 行；方法 = `intended-vs-implemented` + `diagnosing-bugs`；只读审计）。**原「待併入」标记撤销**：本 §8.7~8.11 为併轨成果。
- 审计统计：**假功能 BLOCK×3（A-1/A-2/A-3）+ SHOULD×6 + NIT×10**；同时确认「无系统性假数据」（唯一 fetch 出口 / mock 默认关 / 数字全来自 API / 关键链路实算抽查一致）。
- 併轨口径：审计编号直接引用（A-1…F-8 / D-6 / D-7 / E-2），与 QA 缺陷（R2-D1..D4）合并为统一清单（§8.10）。

#### 8.7 审计 BLOCK 三条裁定（四象限 + 修复指令 + 验收断言）

**BLOCK-A1 ·「测试连接」按钮空转且谎称已发起（`settings.js:150-152`）** —— 定性：**前端做错（呈现谎言）**；需求侧**无「真连通性测试」实装承诺**（R-UI-33 验收仅①标注②硬约束长文③Key 本地存储；线框/legacy 基准均明确「未发起真实请求」原型）。→ **选定方案 B：诚实降级（本轮修）**；**方案 A（真探测）列入架构裁定 C1**（需新增端点、契约 +1；LLM 能力本身处「shadow 观察区/不做最终预测」，孤立连通性端点宜随 LLM 编码一并立项）。
- 责任方：`frontend-dev`（本轮）；`architect`（C1，见 §8.11）。
- 修复指令（本轮）：`probe('llm')` 改**本地校验**并如实呈现——读取 provider/base_url/model/key（或 `api_key_set`）：① 未配置 → toast「请先填写 Base URL / 模型 / Key（未发起网络请求）」；② 配置齐全 → toast「本地校验通过（格式有效）；连通性测试未接入，不会发起网络请求」；③ 删除「已发起连接测试（异步任务）」措辞；按钮 title/副文案标「本地校验」。文案入 `copy.js`。
- 修复指令（C1 若获批，非本轮前置）：后端加 `POST /settings/llm-test`（stdlib urllib、超时可配、返回可读结果），契约版本 +1 后前端接线为真实三态。
- 验收断言：① 点击前后无任何出站网络请求（CDP Network 计数为 0 / fetch 桩计数不变）；② toast 不含「已发起」「异步任务」；③ 两分支文案与配置状态一致；④（C1 落地后）真探测可读成功/失败且不回显 Key。

**BLOCK-A2 ·「隐藏持仓金额」开关无消费（`store.js:32-35` / `app.css:151-156` 零行为）** —— 定性：**前端做错**（R-UI-32 为 P0 承诺：全站金额打码 + **刷新后状态保持**）。**併轨加注**：核实现时发现**主开关同样缺「启动水合」**——boot 不拉 `/settings`，刷新后 `store.privacy` 归零 → R-UI-32 验收②（刷新保持）对**两个开关**均未满足（QA 未覆盖此点）。
- 责任方：`frontend-dev`。
- 修复指令：
  1. `store.applyPrivacyClass`：同时 toggle `body.masked` 与 `body.mask-holdings-only`；
  2. `app.css` 增 `body.mask-holdings-only` 规则：仅打码**明细行**（`#hd-body .amt` 与 `#an-body .amt`，含 pnlCell 所在 `td.amt`）；汇总位（见消费点清单）**保留**；
  3. **启动水合**：`main.js#boot` 增 `get('/settings')` → `setPrivacy(privacy)`（失败静默，不影响计算）；
  4. `settings.js#savePrivacy` 的 toast 按本次开关分支给文案；
  5. （顺手）主/副开关打码机制统一——当前均为「透明隐藏」；如需对齐 R-UI-32 字面 `••••`，两开关统一补 `::after`（一次 CSS 改动，登记即可）。
- **消费点清单（全量 12 处 `.amt` 渲染点）**：**汇总保留 7 处**——`holdings.js:92/94/96`（四卡三项）、`:105`（未知行成本提示）、`:139`（分组汇总）、`:190`（覆盖开口市值）、`:206`（档位市值）；**明细打码 5 处**——`holdings.js:283/284/285/287`（明细行市值/成本/今日盈亏/累计盈亏）＋`analyze.js:139`（预测表市值）；另 `components.js:161 pnlCell` 为明细辅助。
- 验收断言：**S1** 开副开关 → 明细行金额不可读（隐藏/`••••`）、四卡与汇总金额仍可见、占比/涨跌不变；**S2** 开主开关 → 全站 `.amt` 打码且顶栏按钮联动；**S3** **刷新后两开关状态与打码效果保持**（水合生效）；**S4** 打码不改任何计算数字（API 原值/DOM 数据不变）。

**BLOCK-A3 · 事件链恒空（`ledger_api.py:866-881` + 写入侧无 `_chain`）** —— 定性：**后端做错（写入缺链）** + 前端需按可复现性分支。契约依据：v8 §5.34 `LedgerChain.chain`「固定 6 步」+ `chain_available`「是否能取到六步推导链（true 时前端可调 `/ledger/chain` 展开）」——字段承诺存在，历史 320 行 `_chain` 命中 0。
- 责任方：`backend-dev`（主）；`frontend-dev`（分支小修）。
- 修复指令（选定：**读时按行走前重算**，INSERT-ONLY 零改动；次选「诚实降级」）：
  1. 后端：`ledger_chain(date, code)` 在 `_chain` 缺失时按**与写入同源口径**重算六步链——定位 bar t → `bars[:t-1]` 训练（H=1）→ `engine.predict_at` → 构建 6 步（建议抽取/复用 `fund_predict.build_chain` 的步骤构造，避免双份实现）；出口步必返 `exit_threshold=0.5200`；否决 missing 语义同 A-05；**禁止编造步骤数值**（不可复现即空链）。
  2. `/ledger` 行 `chain_available`：改为「可重算性」判定（该 code 有离线 bars 且含该 date → true；轻量判定不训练）；字段名/类型不变（**不新增字段、不改枚举**）。
  3. 前端：按 `chain_available` 分支——false → 「该行链路不可复现（代理日线缺失/超窗）」；空链沿用现文案；真链正常渲染（含 ⑥步回填值）。
  4. （可选优化，不强制）新写入行缓存 `_chain`（`_` 前缀已被 `strip_internal` 剥离，不破坏 API 面）。
- 验收断言：**C1** 任取历史行 → `chain` 长度 6、`key` 顺序 `gate/ddsm/veto_crowd/veto_klow2/exit/output`、`exit_threshold=0.5200`、`metrics` 与行内 `p_up/ddsm_state/signal` 对账一致；**C2** 前端点击时间线卡展开六步链（不再恒「无链路数据」）；**C3** `chain_available=true ⇔ 返回 6 步`（false 行前端明示不可复现）；**C4** INSERT-ONLY 不破（`shadow_signals.jsonl` sha256 前后一致）。

#### 8.8 审计 SHOULD 六条处置

| # | 事项 | 定性 | 处置 | 指令 / 明示 |
|---|---|---|---|---|
| S-a | F-1 bootstrap 静态常量冒充「500 校准」（`factors.js:141/200` 仅读常量；后端 measured 已就绪） | 前端做错（呈现口径） | **本轮修（前端）** | 改读 `bootstrap_percentiles_measured`（非空 → 标「bootstrap 500 实测」）；为 null → 回退常量并标「兼容常量（未实测）」；score-detail 无 measured 字段（契约未定义）→ 标注「兼容常量」或隐藏该行 |
| S-b | D-7/F-2 注册表三态单行常量（`app.py:859`） | 定义不清（三态机制是否存在 / 是否 R2 承诺） | **架构裁定 C2**；UI 文案随裁定 | 裁定前不得新增「三态已运作」表述；若判定无机制 → 改单版本现实文案（「当前单版本运行；shadow/retired 机制未接入」） |
| S-c | D-6 `scan_factors` 空转成功回执（`app.py:293-295`） | 后端做错（成功回执冒充已执行） | **本轮修（后端，诚实化）**；真扫描器 → 挂账 R3 | summary/step 不得出现「扫描完成」；改「因子扫描未接入（无扫描器实现）；未产出候选」；保留成功状态须配同等明示 |
| S-d | E-2 R2-04 仅 7/9 出结论 | 排期缺口（非代码缺陷） | **挂账（S5 内收口）** | 责任 `backend-dev`+PM；收口 ≤ G-PM-05；终验报告如实标注「未出结论清单」；到期未收口 → 联合延期说明 |
| S-e | E-2 R2-02 top_n=10 快照未生效 | 缓存/证据缺口 | **本轮修（后端）** | force 重抓 F10 缓存（topline=20）并留证据（新记录 `top_n=20`）；源不可得 → 按验收「或出不可得结论」如实标注，禁止静默 |
| S-f | E-2 R2-01 warming（accuracy 空 / 22 unknown） | 数据窗口（非缺陷） | **挂账（自然日）** | 首判=满 5 可配对日、终判=40 日；README/终验标注「未到期」；随每日 `maintain_nav_history` 推进 |

#### 8.9 审计 NIT 十条归纳

- **顺手修（本轮，低风险）**：F-5 版本标识 `v9.1→v9.2`（`index.html:8/31/336`、`static/README.md`）；F-6 `method="eastmoney_f10_top10_weighted"` 去数字或随 `top_n` 生成；D-8 `_warmup`/`global_as_of` 静默 `except` 至少写 stderr 摘要；B-5a `NO_SOLUTION_TEXT` 死常量清理（`no_solution_count` 改实测或保留注释）；F-3 `score_detail.judges[].value` 恒空——前端不渲染空 value 或标「待接入」。
- **挂账（不阻塞）**：A-4「建议」列恒 `—`（R1 契约缺口，已在 `12-interface-request` 挂账）；B-5b `index_only_assets=0` 硬编码（0 属实，待统计实现）；B-5c `GATE_EFFECT/GATE_T` 研究常量复算（R3）；B-5d `CUBE_LEGEND_FALLBACK` 前端死备份（R3 随分档统一清理）；C-3 warming（同 S-f）；F-4 `review.js` shadow_live 死分支（UI 入口为 R2 后项，前端报告已备案）；F-7 `last_retrain_at` 恒 None（诚实空格，待重训机制）；R2-10 出口灵敏度研究项（P2，R3）。

#### 8.10 统一修复清单（合并 QA 缺陷 + 审计发现 · 按责任方）

| 责任方 | 本轮修 | 挂账 / 裁定 |
|---|---|---|
| `frontend-dev` | R2-D1（§8.1）· R2-D4（§8.4）· **BLOCK-A1** 诚实降级（§8.7）· **BLOCK-A2** 两开关+水合（§8.7）· **BLOCK-A3** 前端分支（§8.7）· S-a（§8.8）· NIT 顺手（F-5/F-3） | F-4 shadow_live 入口 |
| `backend-dev` | R2-D2（§8.2）· R2-D3 最小版（§8.3）· **BLOCK-A3** 读时重算链（§8.7）· S-c·S-e（§8.8）· NIT 顺手（F-6/D-8/B-5a） | D-6 真扫描器（R3）· R2-04 9 只（S5 收口）· R2-01 窗口（自然日） |
| `architect` | — | **C1** R-UI-33 真探测端点（契约 +1）· **C2** 注册表三态机制定义 ·（可选 C3）`/ledger/chain` 重算来源标注 |
| `product-manager` | — | §8.5 备注 + R2-04/R2-01/R2-10 明示跟踪 |

#### 8.11 併轨结论

- 审计 **3 BLOCK 全部收口为本轮修复项**（无需 PM 先行裁定；其中 1 条建议 C1 架构增强、1 条 C2 架构定义）；**6 SHOULD = 本轮修 3 / 架构裁定 1 / 挂账 2**；**NIT 10 = 顺手修 5 / 挂账 5**。
- 「不虚报」纪律执行：一切「实测/完成」措辞要么有真数据（A-1 去谎言、F-1 改实测、D-6 去伪完成、S-e 补证据），要么明示未接入/未到期；`chain_available=false` 场景前端必须明示不可复现而非空壳。
- 修复完成后：前端/后端各自跑测试 → 主 Agent 安排 dev-lead 复验（本文件 +1、build-r2 刷新）→ qa 回归（QA 2 条 P0 + P3 断言 + 审计 3 BLOCK 断言 + NIT 抽查）。

### 9. S5 修复轮复验记录（v5 · 2026-09-13 · §8.10 逐项销项）

> 方法：**独立复验**（全量单测单跑 + 数据面抽查 + live 探针 8/8 + 前端脚本抽跑 + build 重建与独立启动实测），不采信报告转述。
> 证据：`evidence-r2/s5_backend_tests.json`、`s5_live_probe.json`、`s5-chain-tests.log`、`frontend-verify-v3.log`、`build_boot_v3.json`、`build_manifest.json`。

#### 9.1 §8.10 销项核对（逐项）

| 栏 | 项 | 状态 | 独立证据 |
|---|---|---|---|
| 前端 | R2-D1 分析页空态 | ✅ 关闭 | `analyze.js` 空态唯一条件 `rows=0` + 二分支文案；**133/133** 含「rows=15/open=0 → success」正向用例（A1~A4） |
| 前端 | R2-D4 histNote 联动 | ✅ 关闭 | `copy.js#HISTORY_SUFFIX_MERGED/MAIN` + `engine.js` 两处；脚本「含/不含（含归档）」双向断言 |
| 前端 | BLOCK-A1 本地校验 | ✅ 关闭 | `settings.js#probe` 三分支 + `index.html:309/312` 标注；脚本断言 `__fetchCalls` 点击前后相等（零出站） |
| 前端 | BLOCK-A2 隐私两开关+水合 | ✅ 关闭 | `store.js:37` 双 class、`app.css:159-164`（明细规则含 `••••`）、`main.js:157/179` 水合；脚本 S1~S4 |
| 前端 | BLOCK-A3 前端分支 | ✅ 关闭 | `signals.js:21` + `copy.js#CHAIN_UNAVAILABLE`；脚本 A-3；live C2 = 6 步可展开 |
| 前端 | S-a bootstrap 实测优先 | ✅ 关闭 | `factors.js:200-202` 读 `bootstrap_percentiles_measured` + 双标签；脚本 S-a 两例 |
| 前端 | NIT 顺手（F-5/F-3） | ✅ | 版本标识 = **v9.3**（`index.html:8/31/339`、`static/README.md`）；`factors.js:138` 空值 → 「待接入」 |
| 后端 | R2-D2 main_source.path | ✅ 关闭 | live：`"data/holdings.json"`（无盘符/反斜杠） |
| 后端 | R2-D3 最小版 | ✅ 关闭 | `app.py:357/371` 同型 409 互斥 + `_TASK_EXEC_LOCK` 全局串行 + OSError 可读；单测 5 条 |
| 后端 | BLOCK-A3 读时重算 | ✅ 关闭 | live：`012922/013566` → 6 步、key 顺序、`exit=0.52`、`p_up` 与行对账一致、`chain_source=recomputed`；专项单测 **5/5**（stored/null/C1/C3/C4） |
| 后端 | S-c scan_factors | ✅ 关闭 | live 任务回执「未接入…未执行扫描、未产出候选」；无「扫描完成」子串 |
| 后端 | S-e top20 证据 | ✅ 关闭 | 缓存 5 只 × 20 行（`top_n=20`）；live holdings detail `top_n=20`×5、`included_markets` 含 HK |
| 后端 | NIT 顺手（F-6/D-8/B-5a） | ✅ | F-6 依裁定维持（契约 v9.4，测试断言 `method` 恒定 + `top_n∈{10,20}`）；`_swallow` 21 处 stderr 摘要；`NO_SOLUTION_TEXT` 已删 + `no_solution_count` 实测 |
| 架构 | C1 真探测 | ✅ 裁定 | `10-r2 §11.1`（R2=本地校验收口；R3 端点草案备）+ `UI v3 §9` PM 补注；前端已按收口落地 |
| 架构 | C2 注册表三态 | ✅ 裁定+落地 | `10-r2 §11.2`；UI 注 + `REGISTRY_PROVISIONAL_NOTE` 两处注入（`engine.js:411`/`settings.js:219`）；`/engine/registry` 字段未动 |
| 架构 | C3 chain_source | ✅ 裁定+落地 | `09 v9.3 §11` + `ledger_api.py:947-973`；live `recomputed` + 单测 `stored`/`null` |
| 架构 | F-6 方法名 | ✅ 裁定 | `09 v9.4 §12`（历史标识冻结）；实现零改动，测试断言维持 |
| PM | R-UI-33/27 口径补注 | ✅ | `03-ui-design-v3 §9`（两组件补注；与 R1 §7.5/§7.7 冲突处以 §9 为准） |

**未闭合阻塞项：无。** 挂账见 §9.3。

#### 9.2 独立复验证据（命令级）

- **后端全量**：`Ran 213 tests … OK`（单跑，rc=0）；12 产线文件 sha256 前后零差异（`proxy_quality 98b94d43dec81a67…`，与报告 §12.3 一致）。
- **chain 专项**：`tests.test_ledger_chain_recompute` **5/5 ok**（stored/recomputed/null + C1/C3/C4）。
- **live 探针 8/8**：/ledger 60 行 `chain_available=true` 全量；六步 + `exit=0.52` + `p_up` 对账；`top_n=20`×5（HK 并入）；D2 字面；S-c 诚实回执；端口释放。
- **前端**：`node --check` **14/14**；`verify_r2_ui_states.py` **TOTAL 133 PASS 133 FAIL 0**（exit 0）。
- **build-r2 刷新**：**137 文件**（内容 134 = 14 py + 17 static + 31 tests + 65 data + 7 ledger；构建者新增 3）；**MD5 逐文件对齐 134/134，0 不符**；临时副本独立启动实测 PASS（health ok；`[T1 filled, T3 pending, T15 pending]`；端口释放）。
- 数据侧备注：源 `data/cache/nav/*.tmp` 2 个残留（原子写中断物）——构建按设计排除（`.tmp`），R3 顺手清理（入 §9.3）。

#### 9.3 残留挂账（非阻塞）

| 项 | 类型 | 去向 |
|---|---|---|
| R2-04 9 只复核（S-d） | 排期（S5 内收口 ≤ G-PM-05） | backend + PM |
| R2-01 首判/终判（S-f） | 数据窗口（自然日双时点） | backend 随每日任务 |
| R2-10 出口灵敏度研究项 | P2 研究 | R3 |
| D-6 真扫描器 | 功能（honesly 标注中） | R3 |
| D-3 队列化/自动合并 + 原生错误统一映射 | 健壮性设计 | R3（已回报） |
| C1 真探测端点（草案已备） | 增强（与 F-17 合并立项） | R3 |
| C2 版本化重训/回滚机制 | 机制（关联 T-03 / F-7） | R3 评估 |
| NIT：A-4 建议列 · B-5b/c/d · F-4 shadow_live 入口 · F-7 `last_retrain_at` · nav `.tmp` 残留 | 清理 | R3/随手 |
| NIT-2/3/4/5（S4 轮挂账） | 清理 | R3/随手 |

#### 9.4 放行建议

- **§8.10 统一清单：前端 7/7 · 后端 6/6 · 架构 4/4 · PM 补注 1/1（R2-04 / R2-01 / R2-10 跟踪项入 §9.3）全部销项**；独立复验未见新增阻塞。
- **建议 = 可放行 QA 回归**：回归范围 `U2-03-成` / `T2-F2-21-C` + D2/D3/D4 断言 + 审计 BLOCK 断言（A1 零出站 / S1~S4 隐私 / C1~C4 链）+ `chain_source` 三态（available ∈ {stored,recomputed}；unavailable null + 空链）。
- R2-D1 与 A-1/A-2/A-3 关闭后，G-QA-02 的 2 条 P0 失败同源项应转 PASS（预期 P0 159/159）；若 QA 发现 BLOCK 级回归 → 本文件版本 +1 再评。

#### 9.5 C0 快审（PM 终验 E-1~E-4 · 2026-09-13 · 只追加）

- **判定：PASS**（单点快审范围内；4 处均为体验/措辞微修，未触契约字段、未改口径计算）。
- **E-1 顶栏日期 UTC 偏差 → 本地日期**：`format.js#localDate` 新增 + `main.js#renderRuntime` 弃用 `toISOString().slice(0,10)`。**live 抽查（headless Edge）PASS**：`local=2026-09-13（周日）/ utc=2026-09-12` 处于 UTC 偏窗（00:00–08:00）内，页面 `#top-date` = 「2026-09-13 周日」（旧实现将显示 09-12）——证据 `evidence-r2/c0_e1_probe.json`。
- **E-2 口径词「可信估值覆盖」→「估值覆盖」**：`holdings.js#renderOverview` 改由字典 `copy.js#COVERAGE_VALUATION_LABEL` + `covered_count/total_count` 组装（字段未动、后端未改）；精度窗说明保留。
- **E-3 vsum 未知组标签「无」→「无可信估算」**：`holdings.js#renderVSum` 对 `confidence==='unknown'` 改显 `CONF_LABEL.unknown`；其余分组仍直读后端 label（mock 镜像后端以保真测试）。
- **E-4 降级条补样本数**：`review.js#activate` 增只读切片 `scoresLive`（`/review/scores?data_kind=shadow_live`，仅取 `hero.open_count`，非实盘切换入口）+ `renderDegrade` 显示「样本 n 笔」与「样本不足（<20 笔），偏差仅供参考」（仅展示、不参与计算；不可得不显示）。
- **计数与同步**：`node --check` **14/14**；`verify_r2_ui_states.py` **TOTAL 137 PASS 137 FAIL 0**（`frontend-verify-c0.log`）；**build-r2 同步刷新**：137 文件（内容 134）/ **MD5 逐文件 134/134，0 不符**（`build_manifest.json`）。
- **残留（R3，非本轮扩围）**：`holdings.js:486` 同类 `toISOString`（加/减仓默认日期）；`12-interface-request-r2 §2` 相关表述随 R3 同步。

### 10. C1 delta-pass 三笔复查记录（v7 · 2026-09-13 · 单点复查）

> 方法：**只核三笔增量**（不重读全量）；证据 = 源码抽查 + 脚本实跑 + 数据/文案残留扫描 + 专项单测。
> 证据文件：`evidence-r2/c1_backend_tests.json`、`c1-rolling-tests.log`、`frontend-verify-c1.log`、`build_manifest.json`。

#### 10.1 四本账本人话记录渲染（用户反馈；前端 §7.2）

- **判定：PASS**。`views/factors.js#bookRecordSummary`（导出）按账本类型输出人话摘要；卡片采样区最新一条与弹窗默认均走人话；**原始 JSON 视图可切换保留**（审计不丢）；字段缺失留白不编造；枚举文案入 `copy.js#BOOK_FIELD_LABEL/DIG_*/FACTOR_*/RED_LINE_*`。
- **独立证据**：`verify_r2_ui_states.py` 断言 4/4 过——「账本摘要人话渲染（无 JSON）」「弹窗默认人话记录列表」「弹窗默认隐藏原始」「原始切换保留（审计视图）」；日志含 scan_history 人话样例（「候选 RESI30 · F1 通过 · F3 未过 · 判定：未过 F3」等）。

#### 10.2 影子盘窗口 60（用户指令；契约 v9.5 §13 / 后端 §13 / 前端 §7.3）

- **判定：PASS**。
- **常量唯一源与残留**：`ledger_api.py:40 SHADOW_WINDOW_DAYS = 60`（唯一常量）；`app.py:271/283/285/1375` 与 `fund_predict.py:377-393` 全部引用该常量；产线 `.py` 无 `days=20` / `"rolling_window_days": 20` / 「20 交易日约 11 资产」；**前端全仓旧文案（滚动 20 / 20 交易日 / 自然积累 / 窗口 20 / 已达标 / 归档合并计算 / 上线门槛）零命中**，且 `verify` 脚本内含旧口径零残留断言（PASS）。
- **滚动增量（来一天换一天）与幂等**：专项单测 `tests.test_shadow_backfill_contract` **9/9 ok**——含「『来一天换一天』：追加一天、裁剪一天（written=2 / trimmed=2，资产不重叠）」「重复执行幂等（`test_rerun_is_idempotent`）」「常量 60」「调用链无 20 残留」「`signal_state` 引用常量窗」；后端全量 **217/217 OK**（单跑 + 12 产线文件 sha256 守卫零差异）。
- **诚实性口径（PM 会签要求）**：① UI 统一标注 `copy.js#SHADOW_WINDOW_NOTE='滚动 60 日 · 回算口径（启动回填）'`（HUD 子文案 + 进度注 + `index.html` 进度标签，实跑日志逐处命中）；② `qualified` 文案 = 「60 日回算覆盖达成（启动回填口径）」（`copy.js#SHADOW_QUALIFIED_TEXT`），**无上线资格暗示**；`shadow_audit` 行挂「回算口径（启动回填）· 与前向/实盘语义分离」注（复盘中同款，实跑命中）；③ 契约 v9.5 §13 已明示「走前回算、非自然前向积累」。
- **数据面**：产线未动（PM/用户预期：下次启动自动补满，首启约 +5s 一次性 CPU 窗——已入 README 首启提示与 §10.4 残留风险）。

#### 10.3 复盘页筛选排序（用户反馈；前端 §7.4）

- **判定：PASS**。纯视图层（不改计算与数据）：`review.js` 模块级 `reconFilter{veto,signal,fund,sort}` + `reconMeta{loaded,total}`；控件 = 否决层 5 项 / 信号 4 项 / 基金输入 + datalist / P(涨) 三态表头 / 清除。
- **独立证据（`verify_r2_ui_states.py` 实跑逐条）**：「筛选控件齐全（5/4/输入/清除/排序）」；「拥挤度 → 2 行」；「信号=涨 → 3 行」；「基金 `014320` → 2 行（模糊匹配）」；「P(涨) 三态：0.5300▲ → 0.6100▼ → 取消」；「清除复位 + 计数复位」。
- **诚实性**：计数提示 `RECON_LOADED_NOTE='作用于已载入 {n} 条'`（实测「已筛选 2 / 共 5 条 · 作用于已载入 5 条」）；`total > loaded` 时追加 `RECON_LIMITED_NOTE='接口限载（共 {total} 条，筛选仅作用已载入部分）'`；`index.html` 区标题同注「筛选与排序仅作用于已载入记录」。

#### 10.4 汇总与残留

- **三笔连续判定：PASS/PASS/PASS**；未见新增阻塞；`/review/reconciliation` 接口默认 `limit=60`（`total` 为全量计数） → 限载提示文案与后端语义一致。
- **build-r2 同步**：137 文件（内容 134）/ **MD5 逐文件 134/134，0 不符**；副本内 `SHADOW_WINDOW_DAYS = 60` 抽查命中；README-START 更新（v5：新增 C1 三笔变更 + 首启回填提示 + 已知限制 #5 走前回算口径）。
- **残留（非阻塞）**：① 首启一次性 ~5s `/holdings` 瞬时时延（迁移成本，已登记 README；稳态 ≤0.45s 不劣化）；② 契约 v9.1 §4.1 前端映射文字「qualified=已达标」与 v9.5 §13 建议文案（「记录窗已满 60 交易日（走前回算）」）并存——前端已按 PM 最终文案落地，建议 architect 随手同步 §4.1 映射行（契约注记级，不阻塞）；③ 筛选器作用于已载入 60 条（接口限载，已在 UI 明示）。
- 建议：三笔 delta-pass 可随 QA 回归一并抽查（账本人话 / 60 文案 / 筛选计数），无需单独回归轮。

#### 10.5 断连噪声零堆栈修复（单笔 · 2026-09-13 · 用户反馈）

- **判定：PASS**。问题：浏览器刷新/切页/取消请求 → 客户端先断开 → 服务端写响应抛 `ConnectionAborted/Reset/BrokenPipe`，原实现全量堆栈刷屏（复现探针 36 行 Traceback）；**契约/业务语义零变更**。
- **代码走查（四处兜底 + 不误吞）**：① `app.py:1198-1215` `DISCONNECT_ERRORS=(ConnectionAbortedError, ConnectionResetError, BrokenPipeError)`（3.8 兼容）+ `DISCONNECT_SUPPRESSED` 进程内计数 + `_is_disconnect/_note_disconnect`；② `_send`：`end_headers()+write` 包 try/except，连族 → 计数后静默 return，**其他异常继续抛**；③ `_serve_static` 主 write 同款；④ `_handle`：`except Exception` 先判连族 → return（不打栈、不发二次信封），**非断连保持 `traceback.print_exc()` + `E_UNKNOWN` 信封**（app.py:1326-1335）；⑤ `QuietThreadingHTTPServer.handle_error`：连族静默 + 计数，其他走默认堆栈（`main()` 已改用该类）。
- **实跑证据**：全量 **226/226 OK**（单跑 + 12 产线文件 sha256 守卫零差异）；断连专项 `tests.test_disconnect_quiet` **9/9**（含 `ValueError`/`RuntimeError` 照抛、`E_UNKNOWN` 信封保留、真起服 RST 风暴用例）；**独立 RST 风暴探针**（`c1b_rst_probe.py`：24 API + 24 静态 RST）→ stderr **Traceback=0**（修复前 36），风暴后 `/health` ok、正常刷新场景（`/`、`/api/v1/runtime`×2、`/api/v1/engine/status`）全 200、端口释放——`evidence-r2/c1b_rst_probe.json`。
- **观察（非阻塞）**：探针期间 stderr 出现 1 行 `[warn] warmup.run_predictions: PermissionError（WinError 5）…predictions.json.tmp → predictions.json`（D-8 可读摘要，**非 Traceback**）——系测试急停后 `.tmp` 残留锁的瞬时环境问题（探针前刚跑完起服型单测）；随后健康/刷新均正常。源 `data/snapshot/predictions.json.tmp` 残留 1 个（构建按 `.tmp` 排除；R3 顺手清理）。
- **build-r2 同步**：**138 文件**（内容 **135** = 14 py + 17 static + 32 tests + 65 data + 7 ledger；构建者 3）/ **MD5 逐文件 135/135，0 不符**；副本内 `DISCONNECT_ERRORS`/`QuietThreadingHTTPServer`/`test_disconnect_quiet.py` 抽查命中；README-START（v6）增「断连噪声零堆栈」条目。
- **残留**：无新增（`.tmp` 清理与首启回填瞬时时延为既有登记项）。

#### 10.6 F2 自碰撞伪影修复（单笔 · 2026-09-13 · 后端）

- **判定：PASS**。问题：F2 独立性检验把候选与**自身别名**比对（crowd6 的 `_builtin=crowd` 与现役 `crowd` 同源）→ `max_collinearity=1.0 / collinear_with="crowd"` → 记录 `rejected_f2`，属**假失败**；原排除逻辑仅 `name == factor_id`。
- **代码走查**：① `factor_engine.py:1149 _candidate_identity_ids`——身份集合 = `factor_id` / `name` / `_builtin` 键 / 同一内置实现的全部 `BUILTINS` 键名与实现名（crowd6↔crowd 均可识别）；② `_incumbent_series`（:1172）按集合排除自比对（crowd6 → 仅比对 `klow2`；klow2 → 仅比对 `crowd`）；③ `_f2_independence`（:1190）同集合**二次过滤**（即使调用方直传 `inc_series` 也不会自比）；④ 比对逻辑/阈值（`F2_MAX_COLLINEARITY=0.70`）与窗口口径**未动**；`_f3_increment` 等其余链路未触；冻结参数按 §16 红线表保持。
- **实跑**：全量 **234/234 OK**（单跑 + 12 产线文件 sha256 守卫零差异）；F2 专项 `tests.test_f2_selfcollision` **8/8 ok**——含**负向**「真共线（不同身份、同信号）仍 `fail` + 1.0 不被误放」与**正向**「仅自身别名 → 全排除 → `pass` + null（不再 1.0 fail）」「混有真因子 → `collinear_with="klow2"` 且 <1」「crowd6 全栈 evaluate 不再出现 vs `"crowd"`」「klow2 重评仍比对 `crowd` 且 <1（不回归）」。
- **记录抽查（`ledger/adopted_factors.json`）**：crowd6 `correction` 块**完整**——`at=2026-09-13T17:08:25+08:00` / `kind=f2_self_collision_artifact` / `from{1.0, "crowd", rejected_f2}` → `to{0.0127, "klow2", rejected_f1}` / `reason`（伪影成因）/ `rescore_note`（行情刷新漂移 + 报告 §15 索引）；`note` 追加「【2026-09-13 修正】…」；`added_at` 保留 `2026-09-12`；`backtest.verdict=rejected_f1`、`max_collinearity=0.0127`、`collinear_with=klow2`。**klow2 记录未被改动**（无 `correction` 块；`total_score=61.05`、`0.0398 vs crowd`、`added_at=2026-09-12`）。
- **语义变化披露**：`rejected_f2→rejected_f1` 属重评实值（F2 修复后通过；F1/总分因 2026-09-13 15:26 行情缓存刷新同步漂移，`total 21.4→−80.0`）——§15.3 注 + `correction.rescore_note` + `note` 三处一致披露，**非静默**。
- **build-r2 同步**：**139 文件**（内容 **136** = 14 py + 17 static + 33 tests + 65 data + 7 ledger；构建者 3）/ **MD5 逐文件 136/136，0 不符**；副本内 `_candidate_identity_ids`、crowd6 `correction`+`rejected_f1`、`test_f2_selfcollision.py` 抽查命中；README-START（v7）增「R3 · F2 伪影修复」条目与限制 #9（klow2 漂移登记）。
- **残留**：klow2 记录的行情刷新漂移（61.05→51.2）登记为**后续全盘重评候选**（本轮未改记录，符合「只更正确证伪影 + 一并披露」边界）；无其他新增。

## 自验收

- [x] 方向偏差六项全部过审，结论逐项落盘（§1）
- [x] 代码评审问题全部标注 BLOCK/SHOULD/NIT（2/3/5），含分流与处置建议（§3）
- [x] 缺陷全部完成定性分流，无「直接转发前端」；BLOCK-1 走架构裁定、其余归后端（§3）
- [x] 所有 BLOCK 已登记 `open-issues.md`（ISSUE-ZL-R2-S4-B1/B2；SHOULD S1~S3 同登记）
- [x] 集成冒烟实际起服（8791）走关键路径：持仓估值/信号/分析/引擎/数据源健康 + 负向；证据落盘（§5）
- [x] 测试计数：后端 184/184；前端 node 14/14 + 静态断言 92/92（§6.1）
- [x] build-r2 可独立启动（8792 实测）+ README-START 三步 + MD5 131/131（§6.2）
- [x] 已知限制清单已写（README-START §已知限制；含 2 BLOCK）
- [x] 未替开发改产品代码（仅评审意见；对测试污染物仅用产物自带 rebuild 恢复数据并留痕）
- [x] 未改契约/架构/需求工件；未触 `runtime/**`；未动 R1 既有工件（新增均 `-r2`/`evidence-r2`）
- [x] 结论（v1）：**BLOCK 2 条未清零 → 不建议进 S5**，待处置后本文件版本 +1 复验
- [x] **v2 复验轮**：BLOCK-1（B1-1..B1-8）与 BLOCK-2 逐条独立复验销项（§7.1/§7.2）；S1/S2/S3 关闭（§7.3）
- [x] **v2**：build-r2 刷新（136 文件 / MD5 133/133）+ 独立启动实测（8795）+ README-START 同步（§7.4）
- [x] **v2**：G-DL-01 / G-DL-02 建议 PASS（终判权在 orchestrator；§7.6）
- [x] **v3（S5 分流）**：R2-D1（P1）定性「前端做错」+ 可执行修复指令与 A1~A4 验收断言（§8.1）；R2-D2/D3/D4 逐条定性、责任方、修复指令、验收断言（§8.2~8.4）
- [x] **v3**：分流四象限逐条落表（无一条需 PM/架构先行裁定；PM 仅 1 条可选备注）；汇总表一页可转交（§8.5）
- [x] **v3**：审计併轨状态标注「待併入」（`16-fake-feature-audit-r2.md` 未见落盘；§8.6）；`open-issues` 已同步为「分流完成·待修复」
- [x] **v4（审计併轨）**：3 BLOCK 逐条裁定（A-1 诚实降级 + C1 / A-2 两开关+水合 / A-3 读时重算；§8.7）；6 SHOULD 处置分布（本轮修 3 / 架构 1 / 挂账 2；§8.8）；NIT 10 归纳（顺手 5 / 挂账 5；§8.9）
- [x] **v4**：统一修复清单按责任方一页收敛（§8.10）；「不虚报」纪律逐条落实；「待併入」标记移除（§8.6 改「已併入」）
- [x] **v5（S5 终验）**：§8.10 逐项销项（前端 7/7 · 后端 6/6 · 架构 4/4 · PM 补注 1/1）；**未闭合阻塞项：无**（§9.1）
- [x] **v5**：独立复验证据——后端 **213/213**（无污染）+ chain 专项 5/5 + live **8/8** + 前端 **133/133** + node 14/14（§9.2）
- [x] **v5**：build-r2 刷新（137 文件 / **MD5 134/134**）+ 独立启动实测；README-START 同步（v3 已知限制 10 条）
- [x] **v5**：放行建议 = **可放行 QA 回归**（§9.4）；残留挂账明列（§9.3）
- [x] **v6（C0 快审）**：E-1~E-4 单点快审 **PASS**（diff 可读 + `node` 14/14 + 断言 137/137 + E-1 live 本地日期）；build-r2 同步（137 文件 / MD5 134/134）
- [x] **v7（C1 delta-pass）**：三笔单点复查 **PASS**（账本人话 / 影子盘 60 走前回算口径 / 复盘筛选排序）；后端 **217/217** + 滚动专项 9/9 + 前端 **152/152** + 旧 20 零残留；build-r2 同步（137 文件 / MD5 134/134）
- [x] **v8（断连单笔）**：**PASS**（四处兜底 + 非断连照抛；全量 **226/226** + 专项 9/9 + 独立 RST 风暴 Traceback 0）；build-r2 同步（138 文件 / MD5 135/135）
- [x] **v9（F2 伪影单笔）**：**PASS**（身份集合双侧排除 + 真共线负向锁定；全量 **234/234** + F2 专项 8/8 + correction 完整/klow2 未动/漂移披露）；build-r2 同步（139 文件 / MD5 136/136）

## 下游交接

- **主消费方：`orchestrator`**。v5（S5 终验）建议执行顺序：
  1. **派 `qa` 执行回归**（范围见 §9.4）：`U2-03-成` / `T2-F2-21-C` + D2/D3/D4 断言 + 审计 BLOCK 断言（A1 零出站 / S1~S4 / C1~C4）+ `chain_source` 三态 → **G-QA-02 复审**（预期 P0 159/159）；
  2. 复审通过后：`PM` 终验（19；口径 = v9.2 §10 + v9.3/v9.4 注记 + UI §9 补注）；`architect` R3 立项输入（C1 端点草案 / C2 机制 / D-6 扫描器）；
  3. 长期挂账跟踪（§9.3）：R2-04 9 只复核（≤G-PM-05）· R2-01 双时点（自然日）· NIT 清理（含 nav `.tmp`）。
- **次消费方**：`qa`（§9.4 回归 + G-QA-02 复审）、`product-manager`（终验 + R2-04/R2-01/R2-10 明示跟踪）、`architect`（R3 立项）、`frontend-dev`/`backend-dev`（§9.3 清理项随手）。
- **残留风险（责任人/期限）**：
  1. G2-01 ≥21/22 依赖至少 1~2 个净值公布周期补齐配对（首判=满 5 可配对日；终判 40 日）——backend-dev 随每日任务；O1；
  2. QDII 首测样本（40 日窗 + n_test≥20，约 4–8 周）与 7 只挂档复审（>3 只，架构×PM）——architect+PM，S5 前；
  3. R2-04 的 9 只复核未执行（收口 ≤ G-PM-05）——backend-dev，S5；
  4. 冷却项：`_global_model` 每请求重训（D-R2-3）与 `nav_history` 双源（D-R2-5）留 R3。
- **未覆盖**：S5 测试执行（qa）、PM 终验（19）与交付说明（07-delivery）、因子机制 V7~V13 文档修订（21，R2 后）。
