---
artifact: 18-test-report-r2
owner: qa
version: v2
status: draft
supersedes: v1（本文件 S5 首轮执行）
created: 2026-09-13
reviewers: [dev-lead, orchestrator]
gate: G-QA-02
---

# 测试报告 · 极境 ZenithLens（R2 升级轮 · S5 执行 · build-r2）

> **v2（S5 回归复审轮 · 2026-09-13）**：对修复轮刷新后的 `build-r2`（**137 文件**，README-START v3）独立副本全量重跑——167 条自动化检查 + 213 条构建单测**全绿**；原 2 条 P0 失败转 PASS；R2-D1/D2/D3/D4 全关闭；**G-QA-02 自判 = PASS**（详见 §10，v1 判定存档于 §8）。
> 对象：`docs/04-integration/build-r2/`（v1=136 文件 R2-S4b；v2=137 文件 R2-S5）的**只读副本**（起服于临时目录 `%TEMP%\opencode\zl-r2-qa-build`，端口 **8796**；build-r2 原目录零写入）。
> 依据：`17-test-plan-r2.md`（224 用例）、`09-api-contract-r2.md`（v9.2 + v9.3/v9.4 注记）、`10-arch-review-r2.md §10`、`03-ui-design-v3.md §4`、`15-code-review-r2.md v5 §9`、`16-fake-feature-audit-r2.md`。
> 方法：`test-scenarios`（用例执行）；HTTP 断言 + CDP/DOM 断言 + 文件级复算 + 构建单测；数据类断言全部以 API 原值复算，禁止「看着对」。
> 缺陷：见 `04-defects-r2.md`（**只提 dev-lead**）。证据：`docs/05-qa/evidence-r2/`。

## 摘要

1. **v2 回归复审（修复轮后）**：build-r2 刷新 137 文件；**167 条自动化检查（API 71 / 修复断言 25 / 任务 6 / UI 53 / CRUD+补充 12）+ 213 条构建单测全部通过，0 FAIL**。
2. 通过率：**P0 159/159（100%）· P1 63/63（100%）· P2 1/2**（T2-F2-10-N 研究报告未落盘 → 审计挂账 R3，非回归项；勘正 v1 误计）。
3. 原 2 条 P0 失败转 PASS：**U2-03-成**（分析页空态唯一条件=无预测记录，`rows=15/open=0 → success`；四态矩阵 7/7）与 **T2-F2-21-C**（触发条件与 `03-ui §4` 一致）。
4. 修复项/审计断言逐条过：R2-D2（path 字面）/ D3（同型 409 可读 + 完成后可再提交）/ D4（历史后缀联动）；A1（零出站+去谎言）/ S1~S4（隐私双开关+水合+不改数字）/ A-3·C1~C4（链同源重算、p_up 对账、零写）与 `chain_source` 三态（recomputed 现场 ×12；stored/null 单测）。
5. **G-QA-02 自判 = PASS（建议放行）**：无未关闭致命/严重缺陷；负向断言 20/20 复跑通过；残留挂账（R2-04 复核 / R2-01 双时点 / R2-10 研究项）均非本轮门禁项。

## 正文

### 1. 环境与构建

| 项 | 值 |
|---|---|
| 构建 | v1：`build-r2/` 136 文件（R2-S4b）；**v2：137 文件（R2-S5 修复轮，README-START v3）**；均拷副本运行（原目录未动） |
| 运行 | `python app.py --port 8796`（Python 3.8.6）；`/api/v1/health` 200；预热后台完成 |
| 浏览器 | Chrome 153 headless + 自建 CDP（stdlib），真实数据 success + fetch 桩四态 + 键盘交互 |
| 服务就绪证据 | `/health` 200（`ep2_health.json`）；起服日志未落盘（如实，以接口原文与截图为准） |
| 注意 | QA 在副本上执行了任务（recompute 等）→ 副本数据自然演进（台账 320→300、归档 320 行生成）；对测试结论无影响，原 build 零写入 |

### 2. 执行总览（检查条目）

| 执行件 | 条目 | 结果 | 结果文件 |
|---|---|---|---|
| API 断言套件（契约/口径/负向） | 71 | PASS 46 + PASS(阶段) 21 + NA 4（转任务/UI 脚本）· **FAIL 0** | `r2_api_results.json` |
| 任务/幂等套件（首轮） | 10 | 6 条为**脚本误读（HTTP 202 未受理）/窗口口径误算**，由复跑脚本取代 | `r2_task_results.json` |
| 任务/幂等套件（复跑定稿） | 6 | **PASS 6**（maintain 幂等 ×2、recompute 幂等、归档、verify 单资产、targets 传参） | `r2_task_results2.json` |
| UI 套件（真实数据 + 四态矩阵 + 键盘） | 53 | PASS 20 + PASS(阶段) 32 + **FAIL 1**（U2-03-成 → 缺陷 R2-D1） | `r2_ui_results.json` |
| CRUD 冒烟 + 补充断言 | 12 | **PASS 12**（含 C-01..C-10 与还原） | `r2_crud_results.json` / `r2_extra_results.json` |
| 构建单测（回归） | 199 | **199/199 OK**（25.4s；R1 117 + R2 82） | `backend_tests_qa.log` |

**计划 224 条映射判定**：

| 组 | 计划 | 通过 | 失败 | 判定来源 |
|---|---|---|---|---|
| G2 四目标 | 26 | 26 | 0 | API 断言（含阶段判定 6 条，见 §3） |
| T2 功能点 | 89 | 88 | 1（F2-21-C） | API + UI + 任务 + 单测三层映射 |
| N2 数值口径 | 30 | 30 | 0 | API + 文件复算 |
| U2 UI 四态 | 48 | 47 | 1（U2-03-成） | UI 套件（四态矩阵 7 页 × 空/载/错 + 成功） |
| X2 负向断言 | 20 | 20 | 0 | API + UI + grep |
| C2 任务接口 | 6 | 6 | 0 | 任务套件 |
| R2-REG 回归 | 5 | 5 | 0 | API + UI + 单测 + 文件 |
| **合计** | **224** | **222** | **2** | 两条失败**同源**（缺陷 R2-D1） |

**S5 回归复审（v2 · 2026-09-13）全量重跑**：

> 对象：刷新后 build-r2（137 文件）只读副本；修复轮基础：`15-code-review-r2.md` v5 §9（前端 7/7 · 后端 6/6 · 架构 4/4 销项）。

| 执行件 | 条目 | 结果 | 结果文件 |
|---|---|---|---|
| 构建单测 | 213 | **213/213 OK**（15.9s） | `r2v2_backend_tests_qa.log` |
| 修复断言套件（D2/D3/D4 · A1/S1~S4 · A-3/C1~C4 · S-c/S-e · F-1/F-5/F-6） | 25 | **PASS 25 / FAIL 0** | `r2v2_fix_results.json` |
| API 断言套件（全量重跑） | 71 | **FAIL 0**（G2-D05 严格字面转 PASS） | `r2v2_api_results.json` |
| 任务/幂等套件（全量重跑） | 6 | **PASS 6**（含现场 recompute ×2 幂等 + verify 单资产） | `r2v2_task_results.json` |
| UI 套件（含四态矩阵 + 键盘） | 53 | **PASS 53 / FAIL 0**（U2-03-成 转 PASS） | `r2v2_ui_results.json` |
| CRUD + 补充断言 | 12 | **PASS 12** | `r2v2_crud_results.json` / `r2v2_extra_results.json` |
| **合计** | **167 检查 + 213 单测** | **全绿 · 0 FAIL** | — |

### 3. 关键结果（四目标 · 契约 v9.2 口径）

**A 估值更准**
- `/holdings` 22 行：`confidence` 22/22 `unknown` 且**全部带 `conf_reason=nav_missing`**（首日无可配对日，如实；非 unknown 行 `conf_reason` 全 null，双向断言通过）；`window_filled_days=0`、`window_phase=warming`、`累计 0/40 日`（首判=5 日 / 终判=40 日，双时点符合 §6.1）。
- vsum：主指标=`estimate_quality.weighted_mae_rate`（估算档，未出数带原因「缺净值」chip）；`official_summary` 17 只 · 84.4% **单列（既成事实）**；全档参考字段保留且未作主指标（未出数时 chip 条件隐藏）。
- holdings 档 5 只：`trace[holdings].detail` 键齐（top_n=10、covered_weight_pct 50.36~76.13%、included_markets⊆{A,HK}、excluded_count 如实）；`weighted_change` 逐只复算一致（±0.0005）。
- QDII 6 只：回退矩阵零违规（`applied=false` 必带 `fallback_reason`，当前首测期无 applied=true）；`qdii_correction.json` 预注册 `enabled/next_review_date`；门槛「40 可配对日且 n_test≥20」未达 → **不宣布失败**（正确）。
- 日留档：`valuation-20260912/20260913.jsonl` 各 22 行；重复触发不重写（幂等）。

**B 覆盖更多**
- 覆盖面板：`prediction_universe_count=15` == A+B 行数；`pending=7` + 名单 7（≤10）；note=`预测覆盖 15/22（+7 待结论）`；C 档 7 只全挂档（`verify_review_date=2026-10-23`，+30 交易日），**挂档不计入增长/不进 universe**；`tier_reviews.jsonl` 22 行（首轮修正行 + 7×hold + 防稀释闸记录），读端 last-wins 结论 7/7 **hold**。
- recompute：先归档 320 行（manifest 含 `reason/count/added 0/removed 20/first-last_date`）→ 重生成 300 行，码集合 ⊆ 现持仓（档位一致性 0 冲突）；**二次 recompute「结果不变，零写入」**（幂等）。
- 信号口径：`rolling_open_assets=11` / 20 交易日；低频说明在页。

**C 准确率更高**
- `/review/scores`（backtest）：hero=T1=**0.5263/0.5415/−0.0152，open 61**，样本期 2025-05-26..2026-06-22；`sample_window=full`；Δ 复算一致；T+3/T+15 `baseline_status=pending` + 三值 null + open 0（**设计**，v9.2 §10）；`formula` 与计算定义绑定（T1=gate+ddsm+veto；T3/T15 保留定式标签）；`baseline_status` 枚举仅 `filled/pending`（无 `ok`）；`note` 含 `pending_cv`；`data_kind` 区分回测/实盘（shadow_live 可读）。
- 回填：`backfill.jsonl` 304 行 t1_real，`method=proxy_bar` + `proxy_code` 100% 合规；**已到期 up 信号 4/4 回填（100%）**；未回填行 method/proxy 恒 null；无 signal 写入 → `E_VALIDATION`。
- 影子盘：`consecutive_days=20 == /engine/status`；`archive_merged=true`（recompute 后）并注「归档合并计算」；实测基线复算 `max(129/169, …)/304 = 0.5559` == 接口（影子审计 hit 0.8 / 偏差 +24.41pp 如实）。

**D 来源更可靠**
- nav store 22 只 / 5636 点 / 最新净值日 **2026-09-11**（≤1 交易日）；`maintain_nav_history` 幂等（复跑 0 新增、既有日期零覆盖）；`accuracy.json={}`（首日无可配对日，空载如实）。
- 数据源健康：4 源均 `fail_window_7d/fail_window_days=7/recent_failures≤10`；eastmoney `fail_count=544` 仅累计、**不入当前状态**（页面仅在「历史失败（累计 544 次·审计用）」折叠）；sina 行注「仅探测·非主链（近 7 日失败 6 次）」。
- 持仓主源：`main_source` count=22；`import_available=false` + 可读原因（无 E_IO 堆栈）；`primary_exists=false` 不再作误导展示（UI 读 main_source）。

**E 前端升级（U-01..U-12 摘要）**
- U-01 复盘 hero 出数（52.6% / 54.1% / −1.5pp / 61 只，展示 1 位小数；底层值与 API 一致）、三窗口「待填充」「全样本窗」标注；U-02 徽章双层（l1×cu）+ tooltip 实测 6~7 项（来源/降级链路/回测窗/披露口径/未知原因/净值截止日/入账）、unknown 带原因；U-03 四态 7 页 × 空/载/错 **21/21 真实触发**（stub 经真实 `api.js`），success 6/7（分析页见 R2-D1）；U-04 时间线 hit×11 / miss×32 / 待回填×15（仅未回填项，且对账「待回填」日期=最新未到期 2026-09-11）；U-05 `20/60 天` + 归档合并口径 + 可用历史 20 日；U-06 窗口计数 + sina 标注 + 544 折叠；U-07 「验证中」×7 + tier_reason tooltip；U-08 QDII 领先标注（持仓行）；U-09 `thead th position=sticky`；U-10 `:focus-visible` + Tab 可达 + **Esc 关 dialog（焦点回位封装在码）** + reduced-motion；U-11 口径 tooltip（title 425 个、口径类 225）；U-12 文案字典 0 混用（见 §5）。

### 4. 失败清单与缺陷索引

| 用例 | v1 结果 | v2 结果（回归复审） | 说明 |
|---|---|---|---|
| `U2-03-成` | FAIL（R2-D1） | **PASS（已关闭）** | 分析页空态唯一条件=「无预测记录/无监控资产」；`rows=15/open=0 → success`；四态矩阵 7/7 success（`r2v2_ui_results.json`） |
| `T2-F2-21-C` | FAIL（R2-D1） | **PASS（已关闭）** | 触发条件与 `03-ui §4` 一致；空态文案二分支（无监控/无预测） |

缺陷单：`04-defects-r2.md`（v2：**R2-D1/D2/D3/D4 全部 closed**）。**本轮无未关闭缺陷；无 P0 缺陷**。

### 5. 负向断言结果（X2-01..20 · 20/20）

| 断言 | 结果 | 关键证据 |
|---|---|---|
| X2-01 未知不渲染 `+0.00%` | PASS | 全站唯一 1 处 `+0.00%` = 真实 0 值（013566@2026-09-09 `t1_real=0.0`）；`.cu/.gray`（unknown 态）零出现 |
| X2-02 empty 不渲染数字行 | PASS | 7/7 页 `view-main display:none` |
| X2-03 error 不回退示例 | PASS | 7/7 页错误态「原因+重试」，无示例数据 |
| X2-04 待填充无估计值 | PASS | T3/T15 三值 null + open 0；对比卡/基线同纪律 |
| X2-05 conf_reason 双向 | PASS | 仅 unknown 非 null；五值穷举合法 |
| X2-06 `0.5830` 零引用 | PASS | 产线代码仅 `engine.py:685/686` 契约固定文本；`baseline_source=measured` |
| X2-07 `shadow_status` 无 idle/ok/bad | PASS | `recording`（进度枚举）；审计三态独立 |
| X2-08 `t1_real` 无来源不写 | PASS | 回填文件 100% 带 method/proxy；未回填行恒 null |
| X2-09 QDII 回退不静默 | PASS | `applied=false ⇒ reason`；首测门槛未达不宣布失败 |
| X2-10 挂档不计覆盖 | PASS | 7 挂档不进 universe/不计增长 |
| X2-11 四层覆盖不互替 | PASS | 22/15/11/0 四值分列（§0 口径） |
| X2-12 前端不硬编码后端文案 | PASS | 扫描仅注释与「状态缺失→待验证兜底」；标签直读 `verify_status_label` |
| X2-13 缺数据不编造 | PASS | unknown tooltip 仅原因；无来源数字零出现 |
| X2-14 INSERT-ONLY | PASS | `PUT/DELETE /ledger/entries` 均 404；recompute 先归档后重生成 |
| X2-15 `544` 非当前状态 | PASS | 仅在历史折叠 summary「累计 544 次·审计用」 |
| X2-16 导入无 E_IO 堆栈 | PASS | `import_available=false` + 可读原因 |
| X2-17 冻结参数零 diff | PASS | K/p/MIN_N/BAND/双否决分位/0.30/3 全对；黑名单拒绝改参 |
| X2-18 nav 断链不静默 | PASS | unknown+`nav_missing` |
| X2-19 回测/实盘区分 | PASS | `data_kind` 透传；六样本窗未混入复盘页 |
| X2-20 预算不静默 | PASS | `budget_exceeded` 语义就绪；当前无超限（N2-29） |

### 6. R1 沿用回归（B6）

- **后端契约套件**：`python -m unittest discover -s tests -p "test_*.py"` → **Ran 199 tests OK**（含 R1 语义 117 条）；套件隔离（测试前后产线数据无污染，守卫用例在套内）。
- **R1 CRUD（C-01..C-10）实操复跑**：9/9 PASS（建档 201 / 重复 409 / 非法 400 / 更新回读 / 404 / 计数 / 删除 / **还原 22 只零残留** / 重复删 404）。
- **T-UI 组件面**：R2 升级触点 16 行（03-ui §8）全部经 DOM 断言/截图复核；其余 R1 组件行未逐条人工重走（残留风险 R-2）。
- 说明：R1 集成脚本存在已知字面量漂移（`15-code-review-r2 §7.5` NIT-4），未纳入本判定；不构成回归。

### 7. 观察项（非缺陷，供 dev-lead/PM 知悉）

1. **`+0.00%` 语义**：唯一出现为真实 0 值（proxy 收盘价持平）；未知态零冒充 —— 与 R1 `T-F04-B`（恰好 0 → `+0.00%`）一致；建议 UI v3 §2「绝不渲染 `+0.00%`」明确为「未知不得渲染为 `+0.00%`」。
2. **「五源」vs「四源」**：UI v3 U-06 文案写「五源」，PRD G2-10 与实测为 4 源（腾讯日K/腾讯实时/东财/新浪）→ 文档口径差异，建议 PM 备注。
3. **hero 展示 1 位小数**（52.6% / −1.5pp）：底层 0.5263 / −0.0152 由 API 复算一致，属展示舍入。
4. **全档参考 chip 条件渲染**：`weighted_mae_rate` 未出数时隐藏（留白不填，M3 语义未破坏）。
5. 首日 `warming`：置信度/覆盖数值目标（≥21/22、MAE≤0.8%）按双时点属**未到期**，本报告按「如实出值 + 原因」判定，终判时点=满 40 可配对日。

### 8. G-QA-02 自判（v2 · 最终）

| 判据 | v1（存档） | v2 回归复审（最终） | 判定 |
|---|---|---|---|
| P0 用例 100% 通过 | 157/159（98.7%） | **159/159（100%）** | ✅ |
| P1 通过率 ≥90% | 63/63 | **63/63（100%）** | ✅ |
| P2（尽力） | ~~2/2~~（误计） | **1/2**：`T2-F2-10-N` 研究报告未落盘 → 审计挂账 R3；`T2-F2-10-B` frozen 零 diff PASS | ◑ 非门禁项 |
| 无未关闭致命/严重缺陷 | R2-D1（P1）open | **0 未关闭**（R2-D1/D2/D3/D4 全 closed） | ✅ |

**结论：G-QA-02 = PASS（建议放行至 G-PM-05 终验）**。依据：P0 100%、P1 100%、无未关闭致命/严重缺陷；修复轮销项经独立复验（`15-code-review-r2.md` v5 §9）后由本轮全量重跑确认；审计断言（A1/S1~S4/A-3/C1~C4）与 `chain_source` 三态全过。
> v1 判定（FAIL，不建议通过）存档于本文件历史版本；两 P0 失败同源（R2-D1）已修复并独立复验。
> **勘误**：v1 报告将 P2 计为 2/2 系误计（T2-F2-10-N 从未执行）；v2 勘正为 1/2，该项为 R2 计划内 P2 研究项、已列 R3 挂账，不影响本轮门禁。

### 9. 证据索引（`docs/05-qa/evidence-r2/`）

| 类 | 文件 |
|---|---|
| 套件结果 | `r2_api_results.json`(71) / `r2_task_results.json`(首轮) / `r2_task_results2.json`(6) / `r2_ui_results.json`(53) / `r2_crud_results.json`(9) / `r2_extra_results.json`(12) |
| 回归日志 | `backend_tests_qa.log`（199 OK）；server 运行日志未落盘 |
| 接口原文 | `ep2_*.json`（holdings/precision/coverage/signals/engine_status/frozen/review_backtest/review_shadow/ledger/ledger_shadow/health_sources/holdings_data/scorechain/recon 等） |
| 截图 | `zl_r2_real_{holdings,review,engine,settings,signals}.png`、`zl_r2_state_{empty_holdings,error_engine,loading_analyze}.png` |
| 脚本 | `scripts/r2_api_checks.py` / `r2_task_checks.py` / `r2_task_checks2.py` / `r2_ui_checks.py` / `r2_crud_checks.py` / `ui_probe.py` / `vsum_probe.py` / `cdp.py` / `probe_shape.py` |
| **回归批（v2）** | 结果：`r2v2_fix_results.json`(25) / `r2v2_api_results.json`(71) / `r2v2_task_results.json`(6) / `r2v2_ui_results.json`(53) / `r2v2_crud_results.json`(9) / `r2v2_extra_results.json`(12)；日志：`r2v2_backend_tests_qa.log`（213 OK）；截图：`r2v2_real_{holdings,review,engine,settings,signals,analyze}.png`、`r2v2_state_{empty_holdings,error_engine,loading_analyze}.png`、`r2v2_privacy_settings.png`；脚本：`r2v2_fix_checks.py` / `chain_probe.py` |

### 10. S5 回归复审 · 修复项与审计断言结果（v2）

**10.1 计划命中**：原失败两用例（`U2-03-成` / `T2-F2-21-C`）→ **PASS**；P0 159/159；四态矩阵 7 页 success 全绿。

**10.2 修复项断言（R2-D1..D4）**

| 项 | 断言 | 结果 | 证据 |
|---|---|---|---|
| R2-D1 | 分析页空态唯一条件=「无预测记录/无监控资产」；`rows=15/open=0 → success`；空态文案二分支 | PASS | `r2v2_ui_results.json`（7/7 success）；`15-code-review-r2 v5 §9.1`（前端 133/133） |
| R2-D2 | `main_source.path == "data/holdings.json"`（无盘符/反斜杠） | PASS | `r2v2_fix_results.json:R2-D2` |
| R2-D3 | 运行中同型再提交 → 409 `E_CONFLICT` 可读（含 tid + `GET /tasks` 指引）；完成后可再提交；全局串行 | PASS | `R2-D3a/b/c` |
| R2-D4 | `可用历史 N 日（主文件/含归档）` 随 `archive_merged` 联动 | PASS | `R2-D4`（archive_merged=false → 「（主文件）」；recompute 后含归档路径由代码双分支覆盖） |

**10.3 审计断言（`16-fake-feature-audit-r2.md`）**

| 断言 | 结果 | 证据 |
|---|---|---|
| A1 测试连接=本地校验（零出站 + 去谎言） | PASS | 点击后新增 `/api/v1/` 资源条目=0；title=「本地校验（仅检查配置格式，不会发起网络请求）」；页面无「已发起/异步任务」 |
| S1 主开关全站打码 | PASS | `body.masked` + `.amt` computed color=transparent |
| S2/S2b 副开关仅明细行（汇总保留） | PASS | `body.mask-holdings-only` + CSS 规则命中；主关副开时 `#hd-body .amt` 仍打码 |
| S3 启动水合 | PASS | 刷新后 class 与持久化设置一致（masked=false / hold=true） |
| S4 打码不改数字 | PASS | 打码前后 `.amt` textContent 完全一致 |
| A-3 / C1 读时同源重算六步 | PASS | `012922/2026-09-11`：6 步序、`exit=0.5200`、`p_up=0.5886` 与行对账一致 |
| C3 可用性一致性 | PASS | available 12 行 `chain_source=recomputed`；unavailable（null+空链）由单测覆盖 |
| C4 链调用零写 | PASS | 调用前后 `shadow_signals.jsonl` sha256 不变 |
| `chain_source` 三态 | PASS | recomputed=真机 ×12；stored/null=单测 `test_ledger_chain_recompute` 5/5 |

**10.4 附带销项抽查（S-c/S-e/F-1/F-5/F-6）**

| 项 | 结果 |
|---|---|
| S-c `scan_factors` 诚实回执 | PASS：summary=「因子扫描未接入：无扫描器实现，本次未执行扫描、未产出候选」（无「扫描完成」） |
| S-e top20+港美股 | PASS：holdings 档 5/5 `top_n=20`；`included_markets` 含 HK；covered_weight_pct 提升（如 025500 62.34→78.09） |
| F-1 bootstrap 实测优先 | PASS：接口 `bootstrap_percentiles_measured={p50:-12.4,…}`；因子页显示实测分位（−12.4） |
| F-5 版本标识 | PASS：`meta[name=api-contract]=v9.3` + DOM 含 v9.3（v9.4 为注记、不改标识） |
| F-6 method 冻结 | PASS：method 恒定 `eastmoney_f10_top10_weighted` + `top_n∈{10,20}`（契约 v9.4 §12） |

**10.5 环境（v2）**：build-r2 137 文件只读副本；8796；Python 3.8.6；Chrome 153 headless/CDP；测毕停服（8796 已释放）、无 QA 遗留进程。

## 自验收

- [x] 计划 224 条全量映射判定（222 通过 / 2 失败），失败项均附证据与缺陷编号
- [x] P0/P1/P2 通过率统计（157/159 · 63/63 · 2/2）；G-QA-02 判据逐条对照自判
- [x] 四目标关键值实测可复算（Δ、基线 0.5559、覆盖 15/22、n_test/窗口、nav 滞后）
- [x] UI 四态真实触发（7 页 × 空/载/错 21/21 + success 6/7）+ 截图证据
- [x] 负向断言 20/20 逐条核对（含 `+0.00%` 真实 0 值释义）
- [x] 缺陷六项必填（现象/复现/期望/实际/定性/根因 + 严重度）落 `04-defects-r2.md`，只提 dev-lead
- [x] 不改产品代码/契约/架构/前端/build 内文件；未触碰 `runtime/**`；测试脚本与证据均在 `docs/05-qa/evidence-r2/`
- [x] 测毕停服（8796 已释放）、QA 继承的 Chrome 实例已清理（无 QA 遗留进程）
- [x] **v2**：回归复审全量重跑（167 检查 + 213 单测全绿）；原 2 条 P0 失败转 PASS；R2-D1/D2/D3/D4 关闭
- [x] **v2**：审计断言逐条通过（A1 零出站+去谎言 / S1~S4 隐私双开关+水合+不改数字 / A-3 链可复现 / C1~C4 / `chain_source` 三态）
- [x] **v2**：勘正 v1 的 P2 计数（1/2，研究项挂账 R3）；G-QA-02 自判 = PASS

## 下游交接

- **主消费方 `dev-lead` / `orchestrator`**：**G-QA-02 自判 = PASS（建议放行至 G-PM-05 终验）**；本轮无需返修；`04-defects-r2.md` v2 全部 closed。
- **次消费方 `product-manager`**：G-PM-05 终验可复用本报告 §3/§10 与 `r2v2_*.json`；§7 观察项 1/2 文案备注仍建议顺手处理（非阻塞）。
- **残留挂账（非门禁）**：
  1. 数值目标（≥21/22 首判=5 可配对日 / 终判=40；MAE 目标；QDII 首测）**双时点未到期**，随每日任务自然推进（backend/qa 后续轮）。
  2. R2-04 的 9 只代理复核（≤ G-PM-05 收口）与 R2-10 出口研究项（R3）——见 `15-code-review-r2.md §9.3`。
  3. R1 40 组件中未升级的 24 行未逐条人工重走（构建单测 + 截图覆盖关键面）；如需全量走查可于下一轮补。
  4. 任务队列化/自动合并与真探测端点等已挂 R3（`15-code-review-r2.md §9.3`）。
