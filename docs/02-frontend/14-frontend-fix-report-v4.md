---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v4
status: draft
supersedes: v3
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（OC-BUG-FE · 状态矛盾 + 数据域标注 · 契约 v5）

> 上游：用户实测反馈（同屏矛盾：livebar「已接入本地引擎 · 快照 2026-09-12」 vs stale-banner「引擎未运行，展示 2026-08-25 快照」）、
> `docs/01-architecture/09-api-contract.md`（v5）。
> **本轮范围（task OC-BUG-FE）**：① 消除「引擎状态」与「数据陈旧」两个概念的互相冒充；
> ② 三个日期（服务日期 / 净值快照 / 行情快照）分别加数据域标签；③ 仅引擎真正离线时才出现「引擎未运行」。
> 约束：**只改 `static/**`**；未改后端 `*.py`、未改 `docs/01-architecture/**`、未改 `runtime/**`；未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`）+ Node 18.17.1（`node --check` ESM 副本）
> + Chrome for Testing（`chromium-1243`，`--headless=new --no-sandbox`，CDP 9222 直连）。证据逐条给出。

## 摘要

1. **现象根因已定位**：旧 `main.js` 只要 `staleness.is_stale` 就硬写「引擎未运行」；而 `is_stale` 只表示
   **基金净值停更**（`latest_date=2026-08-25`，滞后 18 天），与引擎在线与否无关。引擎在线由
   `engine_status=online` 表达（实测 `/runtime`：`engine_status=online` 且 `staleness.is_stale=true`），二者被混为一谈。
2. **矛盾已消除**：`engine_status=online` 时页面任何位置均**不含**「引擎未运行」（真浏览器全页 `innerText` 断言 PASS）；
   stale-banner 改为按数据域表达：**`净值快照 2026-08-25（滞后 18 天） · 行情快照 2026-09-11 · 引擎在线`**。
3. **三个数据域已分别标注**：顶部 chip = **服务日期 2026-09-12**（`runtime.as_of`）；侧栏 = **净值快照 2026-08-25**（`staleness.latest_date`）；
   侧栏另一行 = **行情快照 2026-09-11**（`/engine/status.data_freshness_snapshot_date`）；不再混称「数据快照」。
4. **离线分支已保留**：`engine_status≠online` 时才显示「引擎未运行」；mock 离线态实测 banner = `净值快照 2026-08-24（滞后 19 天） · 行情快照 2026-08-24 · 引擎未运行`，livebar 同步「引擎未运行（offline）」。
5. **回归全绿**：`node --check` 14/14；真浏览器在线断言 12/12、离线断言 5/5 全 PASS；未改后端/契约/runtime。

## 正文

### B-01 ·【P0·状态语义矛盾】stale-banner 把「净值停更」说成「引擎未运行」

- **位置**：`static/js/main.js:73-78`（旧 `renderRuntime` 的 stale-banner 分支）、`static/js/components.js:61-63`（旧 `staleBanner` 导出）。
- **根因（复现→定位）**：旧代码 `main.js:76` 为
  `if (d && d.staleness && d.staleness.is_stale) stale.innerHTML = '引擎未运行，展示 <latest_date> 快照'`。
  但 `staleness.is_stale`（契约口径，`app.py:268`）= 「最新净值日 ≠ 服务日」，即**净值数据陈旧**，与 `engine_status` 无关。
  实测 `/api/v1/runtime`：`engine_status="online"`、`staleness.is_stale=true`、`latest_date="2026-08-25"`、`days_behind=18`；
  同时 `main.js:97` 的 livebar 依据 `engine_status=online` 写「已接入本地引擎」→ 同屏自相矛盾，用户误判为打开静态文件。
  最小复现：同一 `/runtime` 响应内 `is_stale=true` 与 `engine_status=online` 并存。
- **改法**：
  - 新增 `isEngineOnline(status)`（`'online'|'running'`）作为引擎在线唯一判定，livebar 与 banner 共用，杜绝两处各自判断分叉。
  - `renderStaleBanner(d)` 改为：`is_stale` 时表达 **净值快照滞后**，并附 **行情快照**、**引擎状态**三段数据域；
    仅当 `!isEngineOnline` 时才输出「引擎未运行」。`engine_status=online` 时**结构上不可能**出现「引擎未运行」。
  - `components.js#staleBanner` 同步重写：默认「引擎在线」，仅 `opts.engineOnline===false` 才写「引擎未运行」；
    文案由「引擎未运行，展示 X 快照」改为「净值快照 X（滞后 N 天） · 行情快照 Y · 引擎在线」。
- **证据**：
  - 真浏览器（CDP 9222，`http://127.0.0.1:8791/`）全页 `innerText.indexOf('引擎未运行') = -1`（断言 A1 PASS）；
    livebar 实测 `已接入本地引擎 · 持仓/预测真实数据 · 服务日期 2026-09-12 · 1 个数据源不通`（A2/A3 PASS）。
  - stale-banner 实测 `净值快照 2026-08-25（滞后 18 天） · 行情快照 2026-09-11 · 引擎在线`（C1/C2/C3/C4 PASS），与 livebar 一致。

### B-02 ·【P1·数据域混淆】三个日期分属三域却统称「数据快照」

- **位置**：`static/index.html:28`（旧侧栏「数据快照」）、`:38`（旧顶部 chip「数据快照 —」）、
  `static/js/main.js:63-69`（旧 chip 文案）、`:97`（livebar 旧文案「快照 <as_of>」）。
- **数据域定义（读只读后端确认，未改）**：
  - **服务日期** = `runtime.as_of`（`app.py:267`，实测 `2026-09-12`）；
  - **净值快照** = `runtime.staleness.latest_date`（`app.py:269`，实测基金最新净值日 `2026-08-25`，滞后 18 天）；
  - **行情快照** = `/engine/status.data_freshness_snapshot_date`（`app.py:618`，实测 ETF/指数 bars 最新日 `2026-09-11`）。
- **改法**：
  - `index.html`：顶部 chip 默认 `服务日期 —`；侧栏改为三行「服务日期 / 净值快照（含滞后）/ 行情快照」，新增 `#side-svc`、`#side-market` 节点。
  - `main.js`：顶部 chip 只写 `服务日期 <as_of>`；新增 `marketSnapshotDate()`（读共享切片 `engineStatus.data.data_freshness_snapshot_date`）
    与 `renderDomains(d)` 统一填充侧栏三域；`renderLivebar` 在线文案由「快照 <as_of>」改为「**服务日期 <as_of>**」。
  - `boot()`：并行 `loadSlice('runtime','/runtime')` 与 `loadSlice('engineStatus','/engine/status')`，任一到达即重绘数据域
    （行情快照随 `/engine/status` 到达补齐，仍走统一封装层 `api.js`，无裸 fetch）。
- **证据**：真浏览器断言 B1–B4 全 PASS：`#top-snapshot="服务日期 2026-09-12"`、`#side-svc="2026-09-12"`、
  `#side-date="2026-08-25"`、`#side-lag="滞后 18 个自然日"`、`#side-market="2026-09-11"`；全页三域标签各至少一处（D1 PASS）。

### B-03 ·【P1·离线分支保留】仅引擎真正离线才显示「引擎未运行」

- **位置**：`static/js/main.js#renderStaleBanner` 与 `#renderLivebar`。
- **改法**：两处均以 `isEngineOnline(engine_status)` 为门；离线时 livebar 写「引擎未运行（offline）」，banner 写
  「净值快照 … · 行情快照 … · 引擎未运行」；在线时 banner 写「引擎在线」，永不出现「引擎未运行」。
- **证据**：mock 离线态（`http://127.0.0.1:8791/?mock=1`，`/runtime.engine_status=offline`）实测
  banner=`净值快照 2026-08-24（滞后 19 天） · 行情快照 2026-08-24 · 引擎未运行`、livebar=`引擎未运行（offline）…`；
  断言 O1–O5 全 PASS（含 O4「banner 不误写引擎在线」）。

### 回归汇总

- **语法**：`node --check` 全部 14 个 JS（Node 18 按 CJS 解析，用 `.mjs` 副本检查）→ `total=14 fail=0`。
- **真浏览器断言**（`python app.py` 8791 + Chrome CDP 9222）：
  - 在线态：A1–A3、B1–B4、C1–C4、D1 共 **12/12 PASS**；
  - 离线 mock 态：O1–O5 共 **5/5 PASS**。
- **未覆盖**：未构造 `engine_status='running'` 数据集（该值按 `isEngineOnline` 与 `online` 同分支处理，逻辑等价）。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（本轮未动四态；演示条与既有 emptyWhen 接线保持）
- [x] 所有请求走统一封装层，页面层无裸 fetch（新增行情快照走 `loadSlice` → `api.js`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`（本轮未动 mock）
- [x] 数字格式化走统一工具函数 `format.js`（本轮无新增数值格式化）
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可 `python app.py`（8791）启动，浏览器控制台无致命报错
- [x] 三条目标逐条落地并有真浏览器证据（B-01/B-02/B-03）
- [x] 只改 `static/**`；未动后端 `*.py` / `runtime/**`；未派发子任务
- [x] 数据域按契约口径对齐：`runtime.as_of`（服务日期）/ `staleness.latest_date`（净值快照）/ `engine/data_freshness_snapshot_date`（行情快照）

## 下游交接

- **主消费方 `qa`（G-QA-02 回归）**：新增两条 P0 用例并回归——
  ① 在线时页面不出现「引擎未运行」（全页文本断言）；② 三个日期各有域标签（服务日期/净值快照/行情快照）。
  复现命令：`python app.py`（8791）→ Chrome `--headless=new --no-sandbox --remote-debugging-port=9222`
  → 打开 `http://127.0.0.1:8791/`（离线分支用 `?mock=1`）。
- **次消费方 `dev-lead`（G-DL-01 销项）**：复核 B-01 根因关闭；确认 livebar 与 banner 共用 `isEngineOnline`，无第二处独立判断。
- **架构师**：本轮无需改契约。若后续希望「行情快照」不依赖 `/engine/status`（当前该接口会触发 `train_global`），
  可考虑在 `/runtime` 直接暴露 `market_snapshot_date`，属新增契约字段，另起版本。
- **残留风险**：
  1. `/engine/status` 较慢（内部 `_global_model()`→`train_global`），首屏行情快照可能延迟 1–3 秒才补齐，期间显示 `—`（不影响「服务日期/净值快照」即时可见），已用非阻塞并行加载规避白屏。
  2. mock 的 `staleness.note` 仍是旧文案「数据快照 X」；mock 默认关闭，仅为演示数据，未纳入本轮文案口径（如需可另起小改）。
