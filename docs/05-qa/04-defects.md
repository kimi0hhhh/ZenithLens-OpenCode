---
artifact: 04-defects
owner: qa
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [dev-lead, orchestrator]
gate: G-QA-02
---

# 缺陷单 · 极境 ZenithLens（S5 定向回归销项 · 契约 v5 · task OC-R5-QA2）

> 方法依据 `diagnosing-bugs`：每单先复现（可稳定重跑）、再最小化、后定位根因，**禁止"疑似"**。
> 定性分流纪律（`revision-loop.md §1`）：缺陷**只提给 `dev-lead`**，不直接找前后端。
> 严重度定义见 qa 契约：**数据错误一律 P0**。
> 证据目录：`docs/05-qa/evidence/`；回归基线：`docs/05-qa/evidence/baseline-v1/`。代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。
> **本版（v2）**：基于前端修复（`14-frontend-fix-report` v3）+ 真浏览器定向回归，**D-01/D-02/D-03/D-04 全部 closed**。

## 摘要

1. v1 登记的 **4 条缺陷（P0 ×1 / P1 ×1 / P2 ×2）经修复后全部关闭**：P0 D-01、P1 D-02、P2 D-03/D-04 → `closed`。
2. **关闭依据**（真浏览器 CDP 9222 实测，见 `evidence/regress_ui_checks.json`）：D-01 对比卡 `92.00%→100.00%` 且无 `0.9%`；
   D-02 `low_sample_marks=23`（`.low-mark=23`）；D-03 `meta=v5` + 两处 footer v5；D-04 分析页 10/10 档位列直读、市值零 mismatch。
3. 回归未引出**新 P0/P1**：`tests/` 56/56、33 只读端点语义一致、数值口径 24/24、组件/交互仅预期差异。
4. **G-QA-02 = PASS**（无未关闭致命/严重缺陷），详见 `18-test-report.md` v2。

## 正文

### 缺陷状态总表（v2）

| 编号 | 严重度 | 摘要 | v1 状态 | v2 状态 | 回归证据 |
|---|---|---|---|---|---|
| D-01 | **P0** | 立方体对比卡「有效覆盖」少乘 100 | open | **closed** | `regress_ui_checks.json:D-01-a/b/c`；`shot_engine_regress.png` |
| D-02 | P1 | 研究口径 naive 缺「低样本·仅供审计」角标 | open | **closed** | `regress_ui_checks.json:D-02-a/b`；`ui_interactions.json:engine_naive.low_sample_marks=23` |
| D-03 | P2 | 契约版本标识停留 v4 | open | **closed** | `regress_ui_checks.json:D-03-a/b/c` |
| D-04 | P2 | 分析页跨接口拼 `tier/market_value` | open | **closed** | `regress_ui_checks.json:D-04-a/b`；`shot_analyze_regress.png` |

### D-01 ·【P0·数据/口径错误】125 格立方体对比卡「有效覆盖」少乘 100 → **closed**

| 项 | 内容 |
|---|---|
| **现象（v1）** | 引擎页对比卡显示 `有效覆盖 0.9% → 1.0%`，比后端原值小 100 倍。 |
| **根因** | `static/js/views/engine.js:348` 用 `num(ratio,1)+'%'` 直接拼 `%`，未走全站唯一格式化出口 `format.js#rateU`（`v*100`）。 |
| **修复** | `14-frontend-fix-report` v3：`engine.js:348` 改 `rateU(cmp.valid_coverage_naive_pct)` / `rateU(cmp.valid_coverage_ddsm_pct)`；全仓同类 `num(ratio)+'%'` 自查无第二处。 |
| **回归（v2）** | 真浏览器 `#/engine` 读 `#eg-cmp`：`有效覆盖 92.00% → 100.00%`；引擎页全文 `0.9%` 命中数 **0**。后端 `valid_coverage_naive_pct=0.92`、`valid_coverage_ddsm_pct=1.0`（N-20 PASS）。 |
| **证据** | `evidence/regress_ui_checks.json`（D-01-a/b/c 全 PASS）；`evidence/shot_engine_regress.png`；`evidence/numeric_checks.json:N-20`；`ep_engine_ddsm_cube_017193.json`。 |
| **关闭判定** | **closed**（前端已改，实测数值口径正确；无同类残留） |

### D-02 ·【P1·契约要求未落地】研究口径 naive 缺「低样本·仅供审计」角标 → **closed**

| 项 | 内容 |
|---|---|
| **现象（v1）** | 125 格立方体「研究口径（naive）」低样本格无标注，naive P 直接呈现极端值。 |
| **根因** | `static/js/components.js#cubeSliceHTML` 未读取 v5 字段 `naive_low_sample`（契约 §5.25 要求 UI 叠加角标）。 |
| **修复** | `14-frontend-fix-report` v3：`components.js:249-251` 新增 `low = key==='naive_p' && c.naive_low_sample===true`，低样本格渲染 `.low` + `data-low-sample="1"` + `<sup class="low-mark">低</sup>`；`app.css` 增金线描边与角标样式。 |
| **回归（v2）** | 真浏览器展开 `#cube-research`：`.low` 格 **23**、`.low-mark` 角标 **23**（`low_sample_marks=46` 含重复选择器命中）；刷新 `ui_interactions.json` `engine_naive.low_sample_marks = 23`（v1 基线 = 0）。生产层 `ddsm_p` 不加角标（正确）。 |
| **证据** | `evidence/regress_ui_checks.json`（D-02-a/b PASS）；`evidence/shot_engine_regress.png`；`evidence/ui_interactions.json`；`ep_engine_ddsm_cube_017193.json`（每格 `naive_low_sample`）。 |
| **关闭判定** | **closed**（契约 §5.25 要求已落地，角标实测出现） |

### D-03 ·【P2·展示陈旧】契约版本标识停留 v4 → **closed**

| 项 | 内容 |
|---|---|
| **现象（v1）** | 页面多处标注「字段口径 = 09-api-contract v4」，与 v5 契约不符。 |
| **修复** | `14-frontend-fix-report` v3：`index.html` 3 处 + `api.js/format.js/main.js/components.js/engine.js` 头注 `v4 → v5`。 |
| **回归（v2）** | `meta[name=api-contract].content = "v5"`；侧栏 `.side-foot` 含 `09-api-contract v5` 且无 `v4`；设置页脚 `#view-settings .foot` 含 `v5` 且无 `v4`。 |
| **证据** | `evidence/regress_ui_checks.json`（D-03-a/b/c PASS）。 |
| **关闭判定** | **closed**（展示标注与 v5 契约一致） |

### D-04 ·【P2·契约对齐残留】分析页预测表跨接口拼 `tier/market_value` → **closed**

| 项 | 内容 |
|---|---|
| **现象（v1）** | 分析页从 `/holdings` 拼 `tier/market_value`，未用 v5 `PredictionSummary` 直带字段（SHOULD-4）。 |
| **修复** | `14-frontend-fix-report` v3：`analyze.js#renderTable` 改 `nameMap`（仅 `code→name`），排序与档位/市值列直读 `r.tier`/`r.market_value`；仅 `name` 取持仓行（契约预测对象无 `name`，非 `tier/market_value` 拼装）。 |
| **回归（v2）** | 真浏览器 `#/analyze`：10 行，档位列与 `/predictions.rows[].tier` 零 mismatch（全 `A`），市值列解析值与 `market_value` 逐只零 mismatch。 |
| **证据** | `evidence/regress_ui_checks.json`（D-04-a/b PASS）；`evidence/shot_analyze_regress.png`；`ep_predictions.json`、`numeric_checks.json:N-22`。 |
| **关闭判定** | **closed**（已按 v5 SHOULD-4 直读，无显示错误） |

## 自验收

- [x] 缺陷单六项必填齐全（现象/复现路径/期望/实际/定性/根因，见 v1 快照 `04-defects-v1.md`）
- [x] 严重度按定义判定（数据/口径错误 P0；契约未落地 P1；展示/对齐残留 P2）
- [x] 每条关闭均附**回归证据**（真浏览器断言 JSON / 截图 / 数值复算）
- [x] 回归未引出新 P0/P1，且相关模块（tests/端点/数值/组件/交互）差异逐项核对
- [x] 未修改产品代码 / 契约 / `runtime/**`；未派发子任务；未直接找前后端

## 下游交接

- **主消费方 `dev-lead`**：按本表销项（D-01/D-02/D-03/D-04 全 `closed`）；G-QA-02 = **PASS**。
- **次消费方 `architect`**：D-04 已按 v5 SHOULD-4 纯前端切换，无需改契约；若后续要求「预测对象补 `name`」属新增字段，另起版本。
- **残留风险**：
  1. 同类 `num(ratio)+'%'` 模式本次全仓自查未发现第二处（前端 v3 报告 §D-01），建议后续评审保持抽查。
  2. D-01/D-02 的回归基于当前真实数据（22 只）；空/极端数据集未复测（详见 `18-test-report.md` §9）。
