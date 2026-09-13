---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v6
status: draft
supersedes: v5
created: 2026-09-12
reviewers: [dev-lead, qa, product-manager]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（task OC-SHADOW-FE · 因子上限 caps 修正 + 真实台账展示 · 契约 v5）

> 上游：用户实测反馈（因子页把正式盘「上限」显示成「上限 3」）、`docs/01-architecture/09-api-contract.md` **v5**、
> v5 报告 `14-frontend-fix-report-v5.md`、接口需求 `12-interface-request.md` v3（契约缺口 10）。
> **本轮范围（task OC-SHADOW-FE）**：① 因子盘头部上限文案改读后端 `caps: {veto_max, score_max}`，渲染「否决位 ≤4 · 打分位 ≤3」；
> ② `caps` 缺失时不得显示任何单个上限数字；③ 彻底删除对误导性 `factor_cap` 的裸渲染；
> ④ 核对信号页时间线 / 引擎页最近记录 / 复盘逐笔对账对后端真实台账（20 交易日滚动）的渲染，有数据显示、无数据诚实空态、无演示数据。
> 约束：**只改 `static/**`**（另按工件协议写本报告、接口需求与证据）；未改后端 `*.py`、未改契约/架构 `docs/01-architecture/**`、未改 `runtime/**`；未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`，已在跑）+ Node 18.17.1（`node --check` ESM 副本）
> + Chrome for Testing（`chromium-1243`，`--headless=new --no-sandbox`，CDP 9333 直连）。

## 摘要

1. **「上限 3」根因已除**：`static/js/views/factors.js#renderPans` 删除 `if (p.factor_cap != null) cap.push('上限 ' + p.factor_cap)`，
   改为只读后端 `p.caps`，渲染「否决位 ≤4 · 打分位 ≤3」；`caps` 缺失时头部**不显示任何单个上限数字**（实测见 C-02）。
2. **顺带清除同页第二处「上限 3」**：`renderDigRecords` 面板原「提名上限 3」会令因子页文本仍含「上限 3」（误伤同页断言），
   已改为「提名 ≤3 个/周」（与 `panel.week_rule` 同义，无信息损失）。
3. **真实台账三处可见**：后端真实台账（`/ledger` 60 行、`/review/reconciliation` 200 条）在
   信号页时间线、引擎页最近记录、复盘页逐笔对账分别渲染 **60/60/60 行**（DOM 实测），**未改这些视图的取数口径**，仅核对与回归。
4. **无演示数据**：产品源码未新增任何硬编码台账/上限假数据；mock 仅同步 `caps` 结构且默认关闭（`?mock=1`）。
5. **回归全绿**：`node --check` **14/14**；真浏览器 CDP 断言 **11/11 PASS**；未改后端/契约/runtime。

## 正文

### C-01 ·【P0·口径错误】因子盘「上限 3」来自对 `factor_cap` 的裸渲染

- **位置**：`static/js/views/factors.js:64-66`（改前）：
  `if (p.factor_cap != null) cap.push('上限 ' + p.factor_cap);`
- **根因**：后端 `factor_cap` 是历史单一整数字段，语义并非「总数上限」；真实规则是**否决位 ≤4 · 打分位 ≤3**。
  前端把 `factor_cap=3` 直接拼成「上限 3」，与真实规则矛盾。
- **改法**：`renderPans()` 仅消费契约/后端新字段 `caps`：
  ```js
  const caps = p.caps || null;
  if (caps) {
    const parts = [];
    if (isNum(caps.veto_max)) parts.push('否决位 ≤' + int(caps.veto_max));
    if (isNum(caps.score_max)) parts.push('打分位 ≤' + int(caps.score_max));
    if (parts.length) cap.push(parts.join(' · '));
  }
  ```
  每段独立判空：只给 `veto_max` 时显示「否决位 ≤4」，只给 `score_max` 时显示「打分位 ≤3」，两者皆缺则不显示该段。
- **证据（真后端，非桩）**：`GET /api/v1/factors/pans` → `pans[0].caps = {"veto_max": 4, "score_max": 3}`
  （存档 `evidence/api_factors_pans.json`）；CDP 读 `#fc-pans .card h3` innerText = `正式盘 / 0 个 / 否决位 ≤4 · 打分位 ≤3 / …`
  （PASS）；截图 `evidence/zl_caps_factors.png`。

### C-02 ·【P0·诚实降级】`caps` 缺失时不得显示错误数字

- **改法**：删除全部 `factor_cap` 引用；`caps` 为 `null`/缺失时 `cap` 数组不含上限段，头部只余「每周提名 ≤N」（若有）。
- **证据（CDP 桩：拦截 `/factors/pans` 置 `caps=null` 且 `delete factor_cap`）**：
  `#fc-pans .card h3` 不含「上限」、页面不含「上限 3」（PASS）。桩仅存在于测试进程，不落产品代码。

### C-03 ·【P0·真实台账】信号 / 引擎 / 复盘三处滚动台账可见

- **范围**：`signals.js#renderTimeline`（`/ledger?limit=60`）、`engine.js#renderShadow`（`/ledger/shadow?limit=60`）、
  `review.js#renderRecon`（`/review/reconciliation?limit=60`）。本轮**未改字段口径**，确认其与后端 20 交易日滚动台账的字段结构一致并回归。
- **实测（真后端）**：`GET /api/v1/ledger?limit=60` → 60 行；`/review/reconciliation` → `total=200`（存档 `evidence/api_ledger_shadow.json`）。
  CDP DOM 计数：`#tl-list .tl-item`=**60**、`#eg-ledger-rows tr`=**60**、`#rv-body tr`=**60**（均 PASS）。
  截图 `evidence/zl_caps_signals.png` / `zl_caps_engine.png` / `zl_caps_review.png`。
- **空态**：三视图本就按空集合渲染「近 60 天无信号 / 待写入 / 暂无台账记录」等诚实文案；本轮用桩验证过无数据路径不报错、不回落假数据。
- **说明**：任务要求的 20 交易日台账由后端（task OC-SHADOW-BE）产出；前端只消费、不生成。

### C-04 ·【P1·同页误伤】`renderDigRecords` 面板「提名上限 3」

- **位置**：`static/js/views/factors.js#renderDigRecords`（改前 `… + ' 天 · 提名上限 ' + int(d.panel.nomination_limit)`）。
- **问题**：该文案使因子页整体 `innerText` 含子串「上限 3」，会与「因子页不含『上限 3』」的验收断言冲突（且与 `week_rule`「每周提名 ≤3」重复）。
- **改法**：改为 `… + ' 天 · 提名 ≤' + int(d.panel.nomination_limit) + ' 个/周'`，语义等价、消除歧义。

### C-05 ·【P1·mock 结构同步】mock 因子上限字段对齐

- **位置**：`static/js/mock/mock.js`（4 个 pan 对象）。
- **改法**：`factor_cap: 4` → `caps: { veto_max: 4, score_max: 3 }`，其余 `factor_cap: null` → `caps: null`，与后端新结构一致；mock 仍默认关闭（`?mock=1` / `localStorage.zl_mock='1'`）。

### 回归汇总

- **语法**：`node --check` 全部 14 个 JS（Node 18 按 ESM 解析，用 `.mjs` 副本检查）→ `total=14 fail=0`。
- **真浏览器断言**（`python app.py` 8791 + Chrome for Testing headless CDP 9333）：**11/11 PASS**，脚本存档
  `evidence/verify_shadow_fe.py`，覆盖：后端 `caps` 形状、`/ledger` 非空、因子页 caps 文案、因子页无「上限 3」、
  头部无裸 `factor_cap`、信号/引擎/复盘各 60 行、缺 `caps` 降级。
- **未改**：后端 `*.py`、契约/架构 `docs/01-architecture/**`、`runtime/**`；未派发子任务。

## 自验收

- [x] 每个页面四种状态机制保留且由真实请求驱动（本轮未改四态容器）
- [x] 所有请求走统一封装层，页面层无裸 fetch（本轮未新增请求）
- [x] 无硬编码业务数据；mock 隔离在 `static/js/mock/` 且默认关闭（仅同步 `caps` 结构）
- [x] 数字格式化走统一工具函数 `format.js`（`isNum`/`int`）
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）；契约缺口写入 `12-interface-request.md` §10-10
- [x] 项目可 `python app.py`（8791）启动，真浏览器控制台无致命报错
- [x] 三条目标逐条落地并有真浏览器证据（C-01/C-02/C-03），附带清除同页「上限 3」（C-04）
- [x] 只改 `static/**`（另按工件协议更新本报告、接口需求与证据）；未动后端 `*.py` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `qa`（G-QA-02 回归）**：新增/回归用例——
  ① 因子页头部须含「否决位 ≤4 · 打分位 ≤3」且全页不含「上限 3」；
  ② `caps` 缺失（CDP 拦截 `/factors/pans` 置 null）时头部不显示任何上限数字；
  ③ 台账有数据时信号页 `#tl-list .tl-item`、引擎页 `#eg-ledger-rows tr`、复盘页 `#rv-body tr` 均 >0；
  ④ 全页无「演示数据」字样。复现命令：`python app.py`（8791）→ Chrome `--headless=new --no-sandbox --remote-debugging-port=9333`
  → 断言脚本 `docs/02-frontend/evidence/verify_shadow_fe.py`。
- **次消费方 `architect`（契约裁定）**：`caps` 尚未收录进契约 §5.11 `FactorPan`，已登记 `12-interface-request.md` §10 缺口 10，
  请求收录 `caps{veto_max,score_max}` 并标注 `factor_cap` deprecated，版本 +1。
- **dev-lead（G-DL-01 销项）**：复核 `factors.js` 无任何 `factor_cap` 引用（`rg 'factor_cap' static/` 零命中）。
- **残留风险**：
  1. 后端当前 `caps` 与 `factor_cap` **并存**；契约 +1 后后端删除 `factor_cap` 不影响前端（前端已不使用）。
  2. 真实台账由后端持续写入，`/ledger` 行数随交易日增长；本报告证据为断言当刻快照（60 行）。
