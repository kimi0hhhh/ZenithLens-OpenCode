---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v2
status: draft
supersedes: v1
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（S4 重跑 · OC-R4-FE · 契约 v4）

> 上游：`docs/04-integration/15-code-review.md`（v2 · BLOCK/SHOULD 清单）、`docs/02-frontend/12-interface-request.md`（v2）、
> `docs/01-architecture/09-api-contract.md`（v4）。
> **本轮范围（task OC-R4-FE）**：只销 v2 评审的 **BLOCK-1**（HUD `shadow_status` 枚举错配）与 **SHOULD-3**（`emptyWhen` 未接线）。
> v1 报告（`14-frontend-fix-report-v1.md`）已闭环的上一轮 BLOCK-1/2（`effect_pp`、`window_min_days`）不在本轮重开。
> 约束：**只改 `static/**`**；未改后端 `*.py`、未改 `docs/01-architecture/**`、未改 `runtime/**`；未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`，实测 `/api/v1/*`）+ Node 18.17.1（ESM 断言）+ Edge headless（`--dump-dom`）。
> commit：无（本工作区非 git 仓库，以报告时间戳为本版标识）。

## 摘要

1. **BLOCK-1 已关**：HUD「影子盘」状态字不再恒「—」。根因是 `shadow_status`（§6.9/§5.29 审查枚举 `idle/ok/bad`）被误用台账 `progress.status` 的映射表；新增独立 `SHADOW_STATUS_TAG` 后，实测 `/engine/status.shadow_status=idle` → HUD 渲染「未启动」。
2. **SHOULD-3 已关**：`api.loadSlice` 的第 4 参 `emptyWhen` 从「全仓零调用」变为 **5 个真实调用点**（holdings / analyze / signals-ledger / factors / review），真实空集落 `status=empty`，`mountState` 的 empty 分支可由真数据触发。
3. **真实空集实测**：起服后 `/portfolio/forecast` 三窗口 `open_count=0 / reason=no_open` → 分析页 `data-state=empty` 且文案「今日没有触发开口的资产」；`/ledger` `rows=0` → 信号页台账区「近 60 天无信号」。均非演示条触发。
4. **两处显式不接线（附理由）**：`/engine/status`（对象，离线按 A-06 走 `success+陈旧` 或 `error`，**不得进 empty**）、`/signals/state`（页面级空态由 `renderEmpty` 四事实卡承载，接 `emptyWhen` 会与 `mountState` 空态重复且降级内容）。
5. **回归全绿**：`node --check` 14/14 JS 模块 `TOTAL_FAIL=0`；Node ESM `emptyWhen` 断言 5/5；Edge 真浏览器 5 页状态 + HUD 标签断言通过；后端只读接口实测无 5xx。

## 正文

### 1. BLOCK-1 · HUD「影子盘」状态枚举错配（恒显「—」）

- **位置**：`static/js/views/engine.js`（原 `:113`）。
- **根因（复现→定位）**：后端 `app.py:586` 返回 `shadow_status = ledger_api.shadow_audit().status`，取值域为
  `ledger_api.py:333-365` 的 **影子盘审查枚举** `idle / ok / bad`（契约 §5.29 `ShadowReviewStatus`）。
  前端却用 `PROGRESS_TAG` 查表，而该表键域是**台账进度枚举** `not_started / recording / qualified / gap`
  （对应 `/ledger/shadow.progress.status`，契约 §5.28）——两套枚举不相交，故 `PROGRESS_TAG[d.shadow_status]`
  对 `idle/ok/bad` 恒为 `undefined` → 兜底 `['—','gray']`，状态字永远「—」。
- **改法**：
  - `static/js/views/engine.js:16` 新增独立映射
    `const SHADOW_STATUS_TAG = { idle: ['未启动','gray'], ok: ['达标','ok'], bad: ['降级','red'] };`
    （注释标明两套枚举分属 §6.9/§5.29 与 §5.28，禁止混用）。
  - `static/js/views/engine.js:116` HUD 状态字改用 `SHADOW_STATUS_TAG[d.shadow_status] || ['—','gray']`。
  - 同卡第三参状态色（`:117`）原本已按 `ok/bad/其它` 判定，**未改**；仅修状态字查表，未发明字段、未改契约。
- **证据**：
  - 接口：`GET /api/v1/engine/status` → `shadow_status=idle`、`shadow_consecutive_days=0`、`shadow_target_days=60`、`status=online`。
  - 真浏览器（Edge headless `--virtual-time-budget=9000`，`#/engine`）DOM 断言：
    `#eg-hud` 首个卡 `影子盘` 的 `.v` = **未启动**，`IS_DASH=false`，`PASS_BLOCK1=true`（修复前该值必为 `—`）。
  - 卡片其余值同屏正常：贡献度 0 / 60 日、引擎版本 `oc-s3-v1` 在线、状态格覆盖 100.0%（125/125）。

### 2. SHOULD-3 · 四态「空态」未接线（`emptyWhen` 死参）

- **根因**：`static/js/api.js:95 loadSlice(name,path,opts,emptyWhen)` 定义了第 4 参，`:100-101` 也实现了
  `status = isEmpty ? 'empty' : 'success'`；但全仓 44 处 `loadSlice(` 调用**无一传入** `emptyWhen`，
  故真实空集一律落 `success`，`components.js#mountState` 的 `empty` 分支只能被 `setDemoState('empty')` 演示条触发，
  与 `12-interface-request` §2/§3/§4/§6「空数组=`empty`」相悖。
- **改法（接线 + 让二次渲染接受 empty，避免把空态误显示成「加载中…」）**：

  | 页面/切片 | 调用点 | `emptyWhen` 判据 | 配套渲染守卫（接受 `empty`，数据仍在） |
  |---|---|---|---|
  | 持仓 `/holdings` | `holdings.js:46` | `!d.rows.length`（H1 空数组=`empty`） | `render()` 原已同时处理 `success/empty`，无需改 |
  | 分析 `/portfolio/forecast` | `analyze.js:21` | 三窗口全 `open_count<=0`（H3 `no_open`=空态） | `renderForecast` `analyze.js:67` 接受 `empty`，按 `d.windows` 渲染 |
  | 信号台账 `/ledger` | `signals.js:30` | `!d.rows.length`（S2 空数组=`empty`） | `renderTimeline` `signals.js:109` 接受 `empty` → 「近 60 天无信号」 |
  | 因子四盘 `/factors/pans` | `factors.js:30` | `!d.pans.length`（F1 空盘） | `renderPans` `factors.js:61` 接受 `empty`，按 `d.pans` 渲染 |
  | 复盘成绩 `/review/scores` | `review.js:14` | `!d.scores.length`（R1 `scores=[]`） | `renderHero` `review.js:41` / `renderScores` `review.js:56` 接受 `empty` → 「尚无成绩记录 / 暂无回测」 |

  > 关键实现事实：`loadSlice` 在 `empty` 时**仍写入 `data`**（`api.js:101`），故守卫从
  > `sl.status !== 'success'` 放宽为 `(sl.status !== 'success' && sl.status !== 'empty')` 后，
  > 视图函数可继续用 `sl.data` 渲染，不会退化成「正在读取…」。
- **证据**：
  - 纯函数（Node 18 ESM，照抄 `api.js` 后打桩 `fetch`）：`emptyWhen=true+空集 → status=empty 且保留 data`、
    `非空 → success`、`不传 emptyWhen 的空集仍 success（修复前行为）`、`网络异常 → error`，**5/5 PASS**。
  - 真浏览器（起 `python app.py` 8791）：
    - `#/analyze`：`data-state="empty"`，空态文案「今日没有触发开口的资产」已渲染——由真实
      `/portfolio/forecast` 三窗口 `no_open` 驱动；
    - `#/signals`：台账区渲染「近 60 天无信号」，且因 `signalsState` 为 `success`，页面级仍为 `success`
      （`renderEmpty` 四事实卡不受影响）；
    - `#/holdings`（22 行）、`#/factors`（4 盘）、`#/review`（3 行成绩）均为 `data-state="success"`，
      证明 `emptyWhen` 判据对非空集**不误判**。

### 3. 显式不接线项（附理由，避免过度接线）

- **`/engine/status`（引擎页 mount 驱动切片）不接 `emptyWhen`**：`12-interface-request` §9 明示
  「引擎离线不得进 `empty`，A-06 走 `success+陈旧条` 或 `error`」；且该响应是对象、非空集合。维持 `mountState` 的 error/loading 分支。
- **`/signals/state` 不接 `emptyWhen`**：该页页面级空态（`state=no_open`）由 `signals.js#renderEmpty` 的
  **四事实卡**（在监控 N/M 只、距上次开口、上次开口、上次结果）承载；若再接 `mountState` empty，会与四事实卡重复且丢失事实卡，属降级。集合维度已改接 `/ledger`（见 §2）。

### 4. 回归汇总

- **语法**：`node --check` 全部 14 个 JS 模块（`api/components/copy/format/main/store/mock` + `views/*`）→ `TOTAL_FAIL=0`
  （Node 18 将 `.js` 按 CJS 解析，检查用 `.mjs` 副本，同 v1 方法）。
- **接口（`python app.py` 8791，只读）**：`/engine/status`、`/portfolio/forecast`、`/predictions`、`/ledger`、
  `/review/scores`、`/factors/pans`、`/holdings` 均 200；无 5xx。
- **真浏览器（Edge headless）**：`#/engine` HUD 影子盘=`未启动`；`#/holdings`/`#/signals`/`#/factors`/`#/review`=`success`；
  `#/analyze`=`empty`（真实 no_open）。
- **纯函数断言**：`emptyWhen` 四态路径 5/5（见 §2）。
- **未覆盖**：真实后端当前处于 `no_open`/空台账态，故「分析页非空时 `success`」与「信号台账非空时渲染行」仅由
  `emptyWhen` 判据逻辑与 v1 既有渲染证据间接保证，未在本轮构造非空数据端到端复现（不改数据文件）。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（本轮补齐真实空集→`empty`；演示条仍可用）
- [x] 所有请求走统一封装层，页面层无裸 fetch（未新增 `fetch`；全仓仍唯一出口 `api.js`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`（本轮未动 mock）
- [x] 数字格式化走统一工具函数 `format.js`（本轮未新增数值格式化）
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可 `python app.py`（8791）启动，控制台无致命报错；HUD/空态均实测
- [x] BLOCK-1、SHOULD-3 逐条给根因/改法/证据；不接线项给理由
- [x] 只改 `static/**`；未动后端 `*.py` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `dev-lead`（G-DL-01 销项）**：复核 BLOCK-1、SHOULD-3 是否关闭。复核命令：
  `python app.py`（8791）→ `curl /api/v1/engine/status`（应 `shadow_status∈{idle,ok,bad}`）→ 浏览器
  `http://127.0.0.1:8791/#/engine` HUD 影子盘状态字（应「未启动/达标/降级」，不得「—」）；
  `#/analyze` 在 `no_open` 时应显示空态文案。
- **次消费方 `qa`（负向用例）**：
  - `shadow_status` 取 `idle/ok/bad` 三值分别断言 HUD 文案 = 未启动/达标/降级，**不得**出现「—」；
  - 造空集合（或删数据）验证 holdings/analyze/ledger/pans/scores 五处落 `empty` 并显示对应空文案；
  - 反向：非空集合**不得**落 `empty`（本轮实测 holdings/factors/review 为 `success`）。
- **架构师**：BLOCK-2（`llm.base_url`）、SHOULD-1/4/5 等契约缺口仍待裁定，非本轮前端可闭合。
- **残留风险**：
  1. 分析页在 `no_open` 时按契约进入页面级空态（`view-main` 隐藏，含预测表）；若 PM/架构师认为「无开口仍应展示参与预测的灰行」，属四态与信息架构口径问题，需裁定后由前端调整（责任人 architect/PM，期限：S4）。
  2. `emptyWhen` 未覆盖 `/predictions`、`/valuations/precision` 等二级切片（其空集当前由各卡片内文案兜底，非页面级空态）；如需全量收紧，另起接线轮次（责任人 frontend-dev，期限：S4）。
  3. 本轮无法构造非空数据端到端复现（后端当前 `no_open`/空台账），非空分支由逻辑与 v1 证据保证。
