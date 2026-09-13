---
artifact: 18-test-report
owner: qa
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [dev-lead, product-manager, orchestrator]
gate: G-QA-02
---

# 测试报告 · 极境 ZenithLens（S5 定向回归 · 契约 v5 · task OC-R5-QA2）

> 上游：`docs/05-qa/17-test-plan.md`（v1）、`docs/05-qa/18-test-report-v1.md`（v1 · 判 FAIL）、
> `docs/05-qa/04-defects.md`（v1）、`docs/02-frontend/14-frontend-fix-report.md`（v3）、
> `docs/01-architecture/09-api-contract.md`（v5）。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。**实起 `python app.py`(8791) + 真实浏览器（CDP 直连 Chrome for Testing）实测**，非只读报告。
> 证据：`docs/05-qa/evidence/`（`regress_fetch.json`、`regress_ui_checks.json`、`regress_tests.log`、`regress_numeric.log`、
> `shot_engine_regress.png`、`shot_analyze_regress.png`、`baseline-v1/` 及刷新后的接口/组件 JSON）。
> **本轮 skill**：`diagnosing-bugs`（回归定位与最小复现纪律）。
> **范围**：只做**定向回归**（D-01/P1 及其相关模块 + P2 逐条复核 + `tests/` + 关键只读端点），非全量重测。

## 摘要

1. **P0 D-01 已闭环**：真浏览器实测引擎页对比卡 `#eg-cmp` = **`有效覆盖 92.00% → 100.00%`**，引擎页全文**不再出现 `0.9%`**；后端比率仍 `0.92/1.0`（N-20 PASS）。少乘 100 已消除。
2. **P1 D-02 已闭环**：研究口径（naive）低样本角标现身，实测 `.low` 格 **23** + `.low-mark` 角标 **23**（`low_sample_marks > 0`）；`ui_interactions.json` 刷新为 **23**（v1 基线为 0）。
3. **P2 D-03 / D-04 逐条复核通过**：`meta[name=api-contract]=v5`、侧栏与设置页脚均 `v5` 且无 `v4`；分析页 10 行档位列**直读** `predictions.tier`（全 A、零 mismatch）、市值列与 `market_value` 逐只一致（零 mismatch）。
4. **回归全绿**：`tests/` **56/56 OK**；关键只读端点 **33/33 ok** 且与 v1 基线**语义一致**（仅时间戳/`run_id`/源探测计数等易变字段变化，未污染数值）；数值口径 **24/24**；7-Tab 组件与交互回归**仅出现 3~4 处预期差异**（cmp_text、low_sample_marks、research_text_head），无其他回归。
5. **门禁判定：G-QA-02 = PASS**——P0 用例 100% 通过、无未关闭 P0/P1（D-01/D-02 关闭，D-03/D-04 关闭），符合 `gate-rules.md` G-QA-02。

## 正文

### 1. 判定与范围

| 项 | 内容 |
|---|---|
| 激活缺陷 | D-01（P0）/ D-02（P1）/ D-03（P2）/ D-04（P2） |
| 本轮目标 | 验证前端修复（`14-frontend-fix-report` v3）使 D-01/D-02 闭环，复核 P2；确认未引出新 P0/P1 |
| 方法 | 实起服务 + 真浏览器断言（不读报告当结论）+ `tests/` + 只读端点重拉 + 数值复算 |
| **G-QA-02** | **PASS**（P0 100% 通过、无未关闭致命/严重缺陷） |

### 2. 环境与实测方法（如实登记）

| 项 | 实测值 |
|---|---|
| 应用 | `python app.py`，端口 **8791**（`app.py:38`），Python **3.8.6**，纯标准库；`/api/v1/runtime` HTTP 200 |
| 浏览器 | Chrome for Testing `...\ms-playwright\chromium-1243\chrome-win64\chrome.exe`，`--headless=new --no-sandbox --remote-debugging-port=9222`，视口 1720×2600 |
| 驱动 | **CDP 直连**（`evidence/scripts/cdp.py` 自建 stdlib WebSocket）；`agent-browser` 握手失败沿用 v1 处置，如实登记 |
| 回归脚本 | `evidence/scripts/regress_fetch.py`、`run_ui_regress.py`；复用 `numeric_checks.py`、`run_ui_checks.py`、`run_ui_interactions.py` |
| 基线 | `evidence/baseline-v1/`（36 个 v1 证据文件快照，用于逐项差异比对） |
| 数据 | 只读真实持仓 22 只；本轮**未执行** CRUD 写操作（后端未改动、范围限只读） |

### 3. 定向回归矩阵（逐项）

| 用例 | 期望 | 实际 | 结果 | 证据 |
|---|---|---|---|---|
| D-01-a | 对比卡显示 92.00% | `#eg-cmp` = `有效覆盖 92.00% → 100.00%` | PASS | `regress_ui_checks.json:D-01-a` |
| D-01-b | 对比卡显示 100.00% | 同上 | PASS | `regress_ui_checks.json:D-01-b` |
| D-01-c | 不再出现 `0.9%` | 引擎页全文 `0.9%` 命中数 = 0 | PASS | `regress_ui_checks.json:D-01-c` |
| D-02-a | 低样本角标 >0 | `low_sample_marks = 46`（`.low` 格 23 + `.low-mark` 23；去重后 23 格） | PASS | `regress_ui_checks.json:D-02-a` |
| D-02-b | 存在「低样本·仅供审计」角标 | `.low-mark` = 23 | PASS | `regress_ui_checks.json:D-02-b`、`shot_engine_regress.png` |
| D-03-a | `meta[name=api-contract]=v5` | `v5` | PASS | `regress_ui_checks.json:D-03-a` |
| D-03-b | 侧栏口径标注 v5、无 v4 | `字段口径 = 09-api-contract v5`，无 `v4` | PASS | `regress_ui_checks.json:D-03-b` |
| D-03-c | 设置页脚 v5、无 v4 | `…字段口径 09-api-contract v5…`，无 `v4` | PASS | `regress_ui_checks.json:D-03-c` |
| D-04-a | 档位列直读 `predictions.tier` | 10/10 行，tier 全 `A`，与 `/predictions.rows[].tier` 零 mismatch | PASS | `regress_ui_checks.json:D-04-a`、`shot_analyze_regress.png` |
| D-04-b | 市值列与 `market_value` 一致 | 逐只解析比对零 mismatch | PASS | `regress_ui_checks.json:D-04-b` |
| **合计** | | | **10/10 PASS** | |

### 4. 关键只读端点基线一致性

- 重拉 **33 个只读端点**（`regress_fetch.json`）：**33/33 HTTP 200 且 `ok=true`**。
- 与 `baseline-v1/` 逐文件比对：**25 个字节相同**；8 个仅为**易变字段**差异，无非预期内容变化：
  - `ep_engine_ddsm_cube_017193.json` / `ep_engine_inputs_017193.json` / `ep_engine_status.json` / `ep_engine_shadow-review.json` / `ep_settings_holdings-data.json` / `ep_about.json`：仅 `snapshot_at/started_at/written_at/built_at/checked_at` 等时间戳；
  - `ep_holdings.json`：仅 `valuation.written_at`、`valuation.run_id`（同一快照重算）；
  - `ep_data-sources_health.json`：`last_ok_at` + 腾讯实时源重试计数 `315→359`（探测计数器自然增长，非回归）。
- 立方体 `valid_coverage_naive_pct=0.92`、`valid_coverage_ddsm_pct=1.0`、`extreme_count_naive=54`、`naive_low_sample` 等**关键数值与 v1 完全一致**。

### 5. 后端单测（`tests/`）

- 命令：`python -m unittest discover -s tests -v` → **Ran 56 tests … OK（56/56）**（`regress_tests.log`）。
- 覆盖：app 契约（54 路由 / 冻结参数黑名单 / `base_url` 往返）、engine（门禁/DDSM/坐标 v4/v5/冻结 v5）、factor 竞技场、ledger INSERT-ONLY、portfolio 加权、valuation 未知态与 v5 精度分组。

### 6. 数值口径复算（N-01..N-24）

- 复用 `numeric_checks.py` 对刷新后端值复算 → **SUMMARY 24/24**（`regress_numeric.log`、`numeric_checks.json`）。
- 关键：`N-20` 对比卡字段为 ratio `0.92/1.0`（展示应 92%/100%）；`N-22` `tier/market_value` 跨接口 mismatch=0；`N-23` `p_up∈[0.3460,0.7381]`。

### 7. 相关模块无回归（组件 / 交互差异比对）

- **R-UI-01..40**（`ui_components.json` vs `baseline-v1`）：共 4 处差异，全部为预期或易变——
  `engine.data.cmp_text`(`0.9% → 1.0%` ⇒ `92.00% → 100.00%`，D-01 修复)、`engine.data.cmp_len`(65⇒70)、
  `settings.data.src_text`(源探测时间/失败数)、`settings.data.hd_diff_text`(时间戳)。**其余 36+ 组件无变化**。
- **交互套件**（`ui_interactions.json` vs `baseline-v1`）：共 3 处差异，全部为预期——
  `engine_default.cmp`(⇒92.00%/100.00%)、`engine_naive.low_sample_marks`(0⇒23)、`engine_naive.research_text_head`(新增低样本注记)。
  推导链 6 步、四态、隐私打码、因子四盘、设置页等**均保持通过**。

### 8. 缺陷状态（详见 `04-defects.md` v2）

| 编号 | 严重度 | 摘要 | 回归证据 | 状态 |
|---|---|---|---|---|
| D-01 | P0 | 立方体对比卡「有效覆盖」少乘 100 | `92.00%→100.00%`、无 `0.9%` | **closed** |
| D-02 | P1 | naive 缺「低样本·仅供审计」角标 | `low_sample_marks=23`、`.low-mark=23` | **closed** |
| D-03 | P2 | 契约版本标注停留 v4 | `meta=v5`、两处 footer v5 | **closed** |
| D-04 | P2 | 分析页跨接口拼 `tier/market_value` | 10/10 档位列直读、市值零 mismatch | **closed** |

### 9. 残留风险（不阻塞放行）

1. 研究层低样本角标仅视觉提示，`naive_p` 仍可能显示极端值（契约 §5.25 研究口径不设 MIN_N，正确）；已由角标 + `dual_view_note` 双重提示。
2. 快照滞后 `latest_date=2026-08-25`（18 自然日），属数据管线新鲜度（责任人 backend-dev），非本轮算错。
3. 桌面 exe 打包、性能压测、多用户（Brief §7 不做）未覆盖；真实空数据集端到端触发未复测。

## 自验收

- [x] 已实起 `python app.py`(8791) + 真实浏览器实测（非只读报告），方法/环境如实登记
- [x] D-01（P0）用真浏览器证据闭环（`92.00%→100.00%`、`0.9%` 消失）
- [x] D-02（P1）用真浏览器证据闭环（`low_sample_marks>0`）
- [x] P2 逐条复核（D-03 标注 v5、D-04 直读字段）
- [x] 回归相关模块：`tests/` 56/56 + 33 只读端点 + 24 数值口径 + 组件/交互差异比对
- [x] 每条结论附证据文件（`regress_ui_checks.json` / 截图 / `regress_*.log` / `baseline-v1`）
- [x] 缺陷状态更新为 closed 并附回归证据（`04-defects.md` v2）
- [x] 未修改产品代码 / 契约 / `runtime/**`；未派发子任务
- [x] 已回传 skill：`diagnosing-bugs`

## 下游交接

- **主消费方 `dev-lead`**：按 `04-defects.md` v2 销项（D-01/D-02/D-03/D-04 全 `closed`）；G-QA-02 判定 **PASS**，可进入 S7 交付就绪。
- **次消费方 `product-manager`**：`17-test-plan.md` §3/§5 仍可作 G-PM-05 终验走查清单；R-UI-26 已闭合。
- **残留风险**：见 §9（数据新鲜度、打包/性能/多用户未覆盖、空数据集端到端未复测）。
- **未覆盖**：CRUD 写路径本轮未重跑（后端未改动、定向回归限只读），如需可复用 `evidence/scripts/crud_checks.py`。
