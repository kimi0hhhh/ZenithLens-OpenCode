---
artifact: 04-defects
owner: qa
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [dev-lead, orchestrator]
gate: G-QA-02
---

# 缺陷单 · 极境 ZenithLens（S5 重跑 · 契约 v5 · task OC-R5-QA）

> 方法依据 `diagnosing-bugs`：每单先复现（可稳定重跑）、再最小化、后定位根因，**禁止"疑似"**。
> 定性分流纪律（`revision-loop.md §1`）：缺陷**只提给 `dev-lead`**，不直接找前后端。
> 严重度定义见 qa 契约：**数据错误一律 P0**。
> 证据目录：`docs/05-qa/evidence/`。代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。

## 摘要

1. 本轮实起 `python app.py`(8791) + 真实浏览器遍历 7 Tab，共登记 **4 条缺陷：P0 ×1 / P1 ×1 / P2 ×2**。
2. **D-01（P0）** 立方体对比卡「有效覆盖」少乘 100（0.92 显示成 0.9%），属「展示数字与后端不一致（口径分叉）」→ Brief §4 直接失败定义。
3. **D-02（P1）** 研究口径 naive 缺「低样本·仅供审计」角标（契约 §5.25 明令「UI 须叠加」），存在极端 P（n=1→100%）误读风险。
4. **D-03/D-04（P2）** 契约版本标识停留 v4；分析页仍跨接口拼 `tier/market_value`（SHOULD-4 未闭环，数值一致无显示错误）。
5. 无「前端假数据」红线（mock 默认关闭、生产 fetch 唯一出口）；数值口径 24/24、CRUD 16/16 通过（见 `18-test-report.md`）。

## 正文

### D-01 ·【P0·数据/口径错误】125 格立方体对比卡「有效覆盖」少乘 100

| 项 | 内容 |
|---|---|
| **现象** | 引擎页「125 格状态立方体 → 对比卡」显示 `有效覆盖 0.9% → 1.0%`，数值比后端原值小 100 倍。 |
| **复现路径** | ① `python app.py` → 浏览器 `http://127.0.0.1:8791/#/engine` → 滚到「125 格状态立方体」对比卡；② 或直接 `GET /api/v1/engine/ddsm/cube?code=017193`，读 `data.comparison.valid_coverage_naive_pct`。 |
| **期望** | 后端字段为**比率**（`0.92 = 115/125`、`1.0 = 125/125`），按契约 §1.2「比率展示层 ×100」与 §5.25「比率 4 位」应显示 **`92.0% → 100.0%`**。 |
| **实际** | 显示 **`0.9% → 1.0%`**（后端 `valid_coverage_naive_pct=0.92`、`valid_coverage_ddsm_pct=1.0`）。 |
| **定性** | **前端实现缺陷**（契约无误，数值来源无误）。分流：`dev-lead → frontend-dev`。 |
| **根因** | `static/js/views/engine.js:348` 用 `(num(cmp.valid_coverage_naive_pct, 1)) + '%'`，把 ratio 直接当百分数拼 `%`，未走全站唯一格式化出口 `format.js` 的 `rateU()`（`format.js:33-36`，`v*100`）。最小复现：`num(0.92,1)+'%'` → `"0.9%"`；`rateU(0.92)` → `"92.00%"`。 |
| **证据** | `evidence/ep_engine_ddsm_cube_017193.json`（`valid_coverage_naive_pct:0.92`）；`evidence/shot_engine_full.png`（对比卡 `0.9% → 1.0%`）；`evidence/ui_components.json`→`engine.cmp_text`；`evidence/numeric_checks.json`→N-20。 |
| **修复建议** | `engine.js:348` 改用 `rateU(...)`（或 `prob(...)`）；同类 `num(...)+'%'` 模式一并排查。 |

### D-02 ·【P1·契约要求未落地】研究口径 naive 缺「低样本·仅供审计」角标

| 项 | 内容 |
|---|---|
| **现象** | 125 格立方体「研究口径（naive）」展开后，低样本格无任何标注；naive P 以彩色数字直接呈现极端值（如 n=1 → 100 / 0，n=5 → 75）。 |
| **复现路径** | `#/engine` → 展开「研究口径（未加噪真实档位 naive）· 默认折叠」；观察网格无「低样本」角标。对照 `GET /api/v1/engine/ddsm/cube?code=017193`：115/115 个有值格 `naive_low_sample=true`。 |
| **期望** | 契约 §5.25 明确「UI 须叠加『低样本·仅供审计』角标，不得据此判结论」；§10.3 列为 SHOULD-5 前端交付项。 |
| **实际** | `grep -r naive_low_sample static/` 无任何命中（字段未接线）；实测 `low_sample_marks = 0`。 |
| **定性** | **前端实现缺陷**（字段已由后端 v5 返回，前端未消费）。分流：`dev-lead → frontend-dev`。 |
| **根因** | `static/js/components.js#cubeSliceHTML`（`:233-253`）仅分支 `is_empty/status=empty/!isNum(p)`，未读取 `c.naive_low_sample`；研究层与生产层视觉等同，弱化了「稀疏格 P 不稳」的提示。 |
| **证据** | `evidence/ui_interactions.json`→`engine_naive.low_sample_marks:0`；`evidence/shot_engine_full.png` 研究层切片；`evidence/ep_engine_ddsm_cube_017193.json`（每格 `naive_low_sample:true`）。 |
| **影响面** | 仅研究/审计层（默认折叠，`dual_view_note` 已提示仅供审计），故非 P0；但契约要求为硬性，缺标注有误导风险。 |

### D-03 ·【P2·展示陈旧】契约版本标识停留 v4（实际 v5）

| 项 | 内容 |
|---|---|
| **现象** | 页面多处标注「字段口径 = 09-api-contract **v4**」，而本轮契约为 **v5**。 |
| **复现路径** | `http://127.0.0.1:8791/` 左下角（`index.html:29`）；设置页 footer（`index.html:343`）；页面 `<meta name="api-contract" content="v4">`（`index.html:8`）；`api.js:1`、`components.js:2`、`main.js:1` 注释。 |
| **期望** | 标注 v5，与 `09-api-contract.md`（v5）及 §10 v5 销项一致。 |
| **实际** | 显示 v4。 |
| **定性** | **前端展示/注释陈旧**（非数据错误、不影响功能）。分流：`dev-lead → frontend-dev`。 |
| **根因** | 契约由 v4→v5 升级时未同步前端版本标识与注释（`index.html` 3 处 + 3 个 JS 头注）。 |
| **证据** | 见上；`evidence/shot_home.png` 左下角。 |

### D-04 ·【P2·契约对齐残留】分析页预测表仍跨接口拼 `tier/market_value`

| 项 | 内容 |
|---|---|
| **现象** | 分析页「参与本次预测的持仓」表从 `/holdings` 拼 `tier/market_value`，未改用 v5 起 `PredictionSummary` 已直带的两字段。 |
| **复现路径** | `#/analyze`；源码 `static/js/views/analyze.js:93-110`（建 `hMap`，读 `h.tier`/`h.market_value`）。对照 `GET /api/v1/predictions` 每行已含 `tier/market_value`。 |
| **期望** | 按 v5 SHOULD-4 直读预测行字段，消除跨接口展示连接（`15-code-review` §5 SHOULD-4）。 |
| **实际** | 仍跨接口拼接；**实测两来源逐只一致（N-22 mismatch=0）**，故无数字错误。 |
| **定性** | **前端实现（契约对齐残留）**。分流：`dev-lead → frontend-dev`。 |
| **根因** | `analyze.js#renderTable` 未随 v5 契约切换到直读 `r.tier/r.market_value`。 |
| **证据** | `evidence/numeric_checks.json`→N-22；`analyze.js:93-110`。 |

## 自验收

- [x] 缺陷单六项必填齐全（现象/复现路径/期望/实际/定性/根因）
- [x] 严重度按定义判定：数据/口径错误判 P0（D-01）；契约要求未落地判 P1（D-02）；展示陈旧/对齐残留判 P2（D-03/D-04）
- [x] 每单附证据（接口原文 / 截图 / 断言 JSON）
- [x] 全部经 `diagnosing-bugs` 诊断循环定位根因（含最小复现），无"疑似"
- [x] 缺陷只提给 `dev-lead`，未直接找前后端；未派发子任务
- [x] 未修改产品代码 / 契约 / `runtime/**`

## 下游交接

- **主消费方 `dev-lead`**：按 `triage` 分流——D-01/D-02/D-04 → `frontend-dev`（D-03 亦前端）；修复后由 qa 回归（N-20、`low_sample_marks`、`0.9%` 消失、v5 标注）。
- **次消费方 `architect`**：D-04 若认为 v5 需进一步约束「禁止前端跨接口拼装」，请在契约补纪律；否则纯前端切换即可。
- **残留风险**：
  1. 同类 `num(ratio)+'%'` 模式可能不止 D-01 一处（本次仅引擎页命中），建议前端全仓自查（责任人 frontend-dev）。
  2. D-03 仅前端标注，非契约实现缺陷，但会误导下游以为实现基于 v4。
