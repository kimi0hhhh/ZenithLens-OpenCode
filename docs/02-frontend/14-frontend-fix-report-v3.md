---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v3
status: draft
supersedes: v2
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（S5 重跑 · OC-R5-FE · 契约 v5）

> 上游：`docs/05-qa/04-defects.md`（v1 · D-01..D-04）、`docs/05-qa/18-test-report.md`（v1）、
> `docs/01-architecture/09-api-contract.md`（v5 · §1.2 数值口径 / §5.4 PredictionSummary / §5.25 StateCube）。
> **本轮范围（task OC-R5-FE）**：销 S5 测试判 FAIL 的 **P0 D-01**（比率显示少乘 100）与 **P1 D-02**（naive 低样本角标缺失），
> 并顺带销 **P2 D-03**（契约版本标注陈旧 v4）、**P2 D-04**（分析页跨接口拼 `tier/market_value`）。
> 约束：**只改 `static/**`**；未改后端 `*.py`、未改 `docs/01-architecture/**`、未改 `runtime/**`；未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`）+ Node 18.17.1（`node --check` ESM 副本）
> + Chrome for Testing（`chromium-1243`，`--headless=new --no-sandbox`，CDP 9222 直连）。证据在文内逐条给出。

## 摘要

1. **D-01（P0）已修**：`engine.js:348` 把后端比率 `0.92` 当百分数拼 `%`，实显 `0.9%`。改用全站唯一格式化出口
   `format.js#rateU`（`v*100`，契约 §1.2「`*_pct` 为比率，展示层 ×100」）后，实测 `#eg-cmp` = **`有效覆盖 92.00% → 100.00%`**，`0.9%` 消失。
2. **D-02（P1）已修**：`components.js#cubeSliceHTML` 新增读取 v5 字段 `naive_low_sample`，对研究口径（`naive_p`）低样本格叠加
   `.low` 类 + `data-low-sample` + 「低样本·仅供审计」角标（契约 §5.25 明令）；真浏览器实测 `low_sample_marks = 23`（修复前 0）。
3. **D-03（P2）已修**：`index.html` 3 处 + `api.js/format.js/main.js/components.js/engine.js` 头注由 `v4` 同步为 `v5`；实测 `meta[name=api-contract]=v5`、侧栏与设置页脚均为 v5。
4. **D-04（P2）已修**：`analyze.js#renderTable` 改为直读 `predictions` 行自带字段 `r.tier`/`r.market_value`（契约 §5.4 SHOULD-4），
   排序亦按 `r.market_value`；仅 `name` 仍取持仓行（预测对象契约无 `name` 字段，非跨接口拼装 tier/market_value）。
5. **回归全绿**：`node --check` 14/14；真浏览器断言 D-01/D-02/D-03/D-04 全 PASS（详见 §5）；后端只读接口无 5xx。

## 正文

### D-01 ·【P0·数据/口径错误】125 格立方体对比卡「有效覆盖」少乘 100

- **位置**：`static/js/views/engine.js:348`（`renderCube` → 对比卡 `#eg-cmp`）。
- **根因（复现→定位）**：后端 `comparison.valid_coverage_naive_pct=0.92` 是**比率**（契约 §1.2：`*_pct` 语义同 `*_ratio`，
  展示层 ×100）。旧代码 `num(cmp.valid_coverage_naive_pct, 1) + '%'` 直接把比率拼 `%`，未乘 100，故 `0.92 → "0.9%"`；
  最小复现：`num(0.92,1)+'%'` = `"0.9%"`，而 `rateU(0.92)` = `"92.00%"`。
- **改法**：
  - `engine.js:7` 从 `format.js` 增补导入 `rateU`（唯一格式化出口；禁止本页自行 `*100`）。
  - `engine.js:348` 改为 `cmpHtml('有效覆盖', rateU(cmp.valid_coverage_naive_pct), rateU(cmp.valid_coverage_ddsm_pct))`，
    即 `92.00% → 100.00%`。
  - **同类模式全仓自查**：`grep` 全 `static/js` 中所有 `+'%'` 用法，除本处外均为 `(v*100).toFixed(...) + '%'` 的正确写法
    （holdings/engine/review/components 等），无第二处少乘 100（回应缺陷单残留风险 1）。
- **证据**：
  - 接口：`GET /api/v1/engine/ddsm/cube?code=017193` → `valid_coverage_naive_pct=0.92`、`valid_coverage_ddsm_pct=1.0`（实测）。
  - 真浏览器（CDP 9222，`#/engine`）`#eg-cmp` 内文：`有效覆盖\n92.00% → 100.00%\nP 标准差\n0.352 → 0.103\n…`；
    断言 `d01_shows_92/shows_100/no_bad_0_9` 全 `pass`（见 §5）。

### D-02 ·【P1·契约要求未落地】研究口径 naive 缺「低样本·仅供审计」角标

- **位置**：`static/js/components.js:239-253`（`cubeSliceHTML`）+ `static/css/app.css:271-279`。
- **根因**：函数仅分支 `is_empty/status=empty/!isNum(p)`，未读取 v5 新增字段 `c.naive_low_sample`（契约 §5.25：
  `naive_n < min_n(15)` 为 true，UI 须叠加角标，不得据此判结论），研究层与生产层视觉等同，弱化稀疏格 P 不稳的提示。
- **改法**：
  - `components.js:247-253`：新增 `const low = key === 'naive_p' && c.naive_low_sample === true;`
    仅研究口径生效；低样本格渲染为 `<div class="cc low" data-low-sample="1" …>`，数字后附
    `<sup class="low-mark" title="低样本·仅供审计（naive_n<15），不得据此判结论">低</sup>`，并在 `title` 追加「低样本（仅供审计）」。
  - `app.css:271-279`：`.cube .cc{position:relative}`，新增 `.cube .cc.low{border-color:var(--gold)}` 与
    `.low-mark{position:absolute;top:0;right:2px;font-size:8px;color:var(--gold)}`（金线描边 + 右上角「低」标）。
  - 生产层（`ddsm_p`）不加角标，`naive_low_sample` 为空格的既有「无样本」渲染不受影响。
- **证据**：真浏览器展开 `#cube-research` 后，
  `document.querySelectorAll('#cube-research-grid .low, #cube-research-grid [data-low-sample], #cube-prod .low').length = 23`（修复前 0）。

### D-03 ·【P2·展示陈旧】契约版本标识停留 v4（实际 v5）

- **改法（同步标注，无逻辑改动）**：
  - `static/index.html:8` `<meta name="api-contract" content="v5">`；`:29` 侧栏「字段口径 = 09-api-contract v5」；
    `:343` 设置页脚「字段口径 09-api-contract v5」。
  - 头注同步：`api.js:1`、`main.js:1`、`format.js:2`、`components.js:2`、`engine.js:1` 的 `v4` → `v5`。
- **证据**：真浏览器 `meta[name=api-contract].content = "v5"`；`.side-foot` 与 `#view-settings .foot` 均含 `v5` 且不含 `v4`。

### D-04 ·【P2·契约对齐残留】分析页预测表改为直读 `PredictionSummary.tier/market_value`

- **位置**：`static/js/views/analyze.js:83-110`（`renderTable`）。
- **根因**：旧代码建 `hMap`（来自 `/holdings`），从持仓行取 `h.tier`/`h.market_value` 跨接口拼装；v5 起 `PredictionSummary`
  已直带 `tier`/`market_value`（契约 §5.4 SHOULD-4 明令前端直读、禁止再跨接口拼装）。
- **改法**：
  - `analyze.js:93-94`：`hMap` 收敛为 `nameMap`（仅存 `code → name`）；
  - `analyze.js:95-96`：排序改用 `(b.market_value || 0) - (a.market_value || 0)`（直读预测行）；
  - `analyze.js:103`：档位列 `esc(r.tier || '—')`（直读预测行）；
  - `analyze.js:108`：市值列 `r.market_value == null ? '—' : amt(r.market_value)`（直读预测行）。
  - `name` 仍取 `nameMap`：`PredictionSummary`（契约 §5.4）不含 `name` 字段，属契约既有边界，非 `tier/market_value` 拼装。
- **证据**：真浏览器 `#/analyze` 表档位列 10/10 直读得到 `["A",…,"A"]`（值来自 `/predictions.rows[].tier`，
  与缺陷单 `evidence/ep_predictions.json` 每行含 `tier`/`market_value` 一致）。

### 回归汇总（§5 详列）

- **语法**：`node --check` 全部 14 个 JS（Node 18 按 CJS 解析，用 `.mjs` 副本检查）→ `total=14 fail=0`。
- **真浏览器断言**（`python app.py` 8791 + Chrome CDP 9222）：D-01 `92.00%→100.00%` 且无 `0.9%`；
  D-02 `low_sample_marks=23`；D-03 `meta=v5` + 两处 footer v5；D-04 `tier` 列直读非空 → **全 PASS**。
- **未覆盖**：未构造额外非空/空数据集；本轮仅修显示与字段接线，未改任何后端/契约/数据。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（本轮未动四态；演示条与既有emptyWhen接线保持）
- [x] 所有请求走统一封装层，页面层无裸 fetch（未新增 `fetch`；仍唯一出口 `api.js`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`（本轮未动 mock）
- [x] 数字格式化走统一工具函数 `format.js`（D-01 改用 `rateU`，未在本页自行 ×100）
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可 `python app.py`（8791）启动，浏览器控制台无致命报错
- [x] D-01/D-02/D-03/D-04 逐条给根因/改法/证据
- [x] 只改 `static/**`；未动后端 `*.py` / `runtime/**`；未派发子任务
- [x] 字段口径按契约 v5：`*_pct`/`*_ratio` 比率展示 ×100 统一经 `format.js`；`naive_low_sample` 按 §5.25 消费

## 下游交接

- **主消费方 `qa`（G-QA-02 回归）**：复跑 N-20（有效覆盖应 `0.92 → 92%`、不再 `0.9%`）、`ui_interactions.json` 的
  `low_sample_marks`（应 > 0）、确认页面无 `0.9%`、标注为 v5。复用命令：
  `python app.py`（8791）→ `python docs/05-qa/evidence/scripts/numeric_checks.py` / `run_ui_interactions.py`
  （注：本机 Chrome 直启需 `--no-sandbox`，见 §5 环境）。
- **次消费方 `dev-lead`（G-DL-01 销项）**：复核 4 条缺陷关闭；确认无同类 `num(ratio)+'%'` 残留（已全仓自查）。
- **架构师**：D-04 已按 v5 SHOULD-4 纯前端切换，无需再改契约；若后续要求「预测对象补 `name`」以减少最后一次跨接口取名，属新增契约字段，另起版本。
- **残留风险**：
  1. 研究层低样本角标为视觉提示，`naive_p` 仍可能显示极端值（如 n=1→100），已由角标 + `dual_view_note` 双重提示，但不做数值门控（契约 §5.25 研究口径不设 MIN_N，正确）。
  2. 本机 Chrome for Testing 需 `--no-sandbox` 才能起 CDP（`exit code 3`），属环境限制，非代码问题；qa 复跑请沿用该 flag。
