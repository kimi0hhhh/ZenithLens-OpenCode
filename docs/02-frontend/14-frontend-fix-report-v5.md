---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v5
status: draft
supersedes: v4
created: 2026-09-12
reviewers: [dev-lead, qa, product-manager]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（OC-DATA-FE · 移除四态演示条与演示标签 · 契约 v5）

> 上游：用户实测反馈（信号页出现「四态演示条 R-UI-40」与「演示数据」标签，致用户误以为信号本身是演示数据）、
> v4 报告 `14-frontend-fix-report-v4.md`（状态矛盾 + 数据域标注）、`docs/01-architecture/09-api-contract.md`（v5）。
> **本轮范围（task OC-DATA-FE）**：① 从产品 UI 彻底移除「四态演示条 / 状态演示器 / 所有『演示数据』标签」
> 与 mock 注入的可见 UI；② 信号页只呈现真实数据，无信号时保留诚实空态四要素；③ 全站清除其它「演示/示例/mock」可见文案。
> **保留**：四态机制本身（真实请求触发的 空/加载/错误/成功）不变；mock 后端替身仍在 `js/mock/`、默认关闭、README 开发者说明保留。
> 约束：**只改 `static/**`**；未改后端 `*.py`、未改契约 `docs/01-architecture/**`、未改 `runtime/**`；未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`）+ Node 18.17.1（`node --check` ESM 副本）
> + Chrome for Testing（`chromium-1243`，`--headless=new --no-sandbox`，CDP 9333 直连）。证据逐条给出。

## 摘要

1. **演示条已从产品 UI 移除**：`index.html` 里整块 `.statebar`（「四态演示（R-UI-40）」+ 成功/空/加载/错误 4 个手动切换按钮）删除；
   `main.js` 的 `setDemoState()` 与 `#statebar-btns` 点击绑定删除；`app.css` 的 `.statebar*` 样式删除。
2. **「演示数据」文案清零**：`main.js` 移除 mock 可见徽章 `· MOCK` 与 toast「已启用 mock 演示数据（默认关闭）」；
   真浏览器全页 `innerText` 断言 **不含**「演示数据 / 四态演示 / 状态演示 / 演示」（17/17 PASS）。
3. **信号页只呈现真实数据**：`/signals/state` 实测 `state=no_open`（监控 10/22 只、上次开口 null、上次结果 pending），
   空态按真实字段渲染四要素「已在监控 / 距上次开口 / 上次开口 / 上次结果」，**无任何示意/演示数据**。
4. **四态机制保留且真实触发可用**：CDP 阻断 `/api/v1/signals/state` → `#view-signals[data-state=error]` + 重试按钮；
   解除阻断 + 刷新 → 恢复 `data-state=success`；mock 模式也无「演示/MOCK」可见文案（7/7 PASS）。
5. **回归全绿**：`node --check` 14/14；真浏览器断言合计 **24/24 PASS**；未改后端/契约/runtime。

## 正文

### C-01 ·【P0·产品 UI 混入调试件】四态演示条出现在信号页

- **位置**：`static/index.html:46-54`（旧 `.statebar` 整块）、`static/js/main.js:155-172`（旧 `setDemoState`）、
  `static/js/main.js:205-211`（旧 `#statebar-btns` 绑定）、`static/css/app.css:57-63`（旧 `.statebar` 样式）。
- **根因**：`.statebar` 是开发期手动切四态的调试件（文案「四态演示（R-UI-40）」），被留在产品外壳中，
  位于所有视图之上，用户看到即误判「页面展示的是演示数据」。
- **改法（删除清单）**：
  - `static/index.html`：删除 `<div class="statebar" id="statebar"> … </div>` 整块（含 4 个 `data-st` 按钮与「四态演示（R-UI-40）」文案）。
  - `static/js/main.js`：删除 `setDemoState(st)` 函数（含 `error:{code:'E_IO',message:'演示：本地文件不可读'}` 文案）；
    删除 `boot()` 内 `statebar-btns` 点击绑定；移除已无引用的 `mountState` 导入（改为 `import { toast, esc } from './components.js'`）。
  - `static/css/app.css`：删除 `.statebar`、`.statebar b`、`.statebar button`、`.statebar button.on` 四条规则。
- **保留（非回归）**：`components.js#mountState`（真实四态容器）、`index.html` 各视图 `[data-slot]`、
  CSS `.state-block`/`.view[data-state=…]` 规则不动 → 四态由真实请求状态驱动。
- **证据**：真浏览器（CDP 9333，`http://127.0.0.1:8791/#/signals`）：
  `document.getElementById('statebar')===null`、`querySelectorAll('.statebar').length===0`、
  `querySelectorAll('[data-st]').length===0`、`window.setDemoState===undefined`（均 PASS）。

### C-02 ·【P0·诚实空态】信号页无信号时展示真实四要素，不得出现演示字样

- **位置**：`static/js/views/signals.js#renderEmpty`（`#sg-empty`）。
- **改法**：本轮未改该逻辑（本就取真实字段），但把「无信号」路径纳入强制证据：
  实测 `/api/v1/signals/state` → `state=no_open`、`monitored_count=10`、`total_count=22`、`days_since_last_open=null`、`last_result=pending`；
  页面 `#sg-empty` 渲染四要素「已在监控 10/22 只 / 距上次开口 — / 上次开口 — / 上次结果 待回填」，
  `.grid4 .factor` 节点数 = 4；`#sg-empty` 文本 **不含**「演示」。
- **证据**：断言「空态四要素含 已在监控/距上次开口/上次开口/上次结果」「空态四要素均为真实值 4/4」「空态无演示字样」全 PASS；
  截图 `C:/Users/10719/AppData/Local/Temp/opencode/zl_signals_nodemo.png`。

### C-03 ·【P1·mock 可见入口清除】徽章与提示不再打标

- **位置**：`static/js/main.js:187-189`（旧 `boot()` 内追加 `badge.textContent += ' · MOCK'` 与
  `toast('已启用 mock 演示数据（默认关闭）')`）。
- **改法**：仅保留 `mockEnabled()` → `import('./mock/mock.js')` → `enableMock(m.mockRequest)` 的机制本体；
  删除可见徽章与 toast。`static/js/mock/mock.js` 保持隔离、默认关闭（`?mock=1` / `localStorage.zl_mock='1'` 才加载）。
- **证据**：真浏览器 `http://127.0.0.1:8791/?mock=1#/signals` 全页 `innerText` 不含「演示」「MOCK」「mock」；
  `#flavor-badge` 文本仍为「OpenCode 版」，未追加 `· MOCK`（3/3 PASS）。

### C-04 ·【P1·全站文案扫描】其它「演示/示例/mock」可见文案清理

- **扫描**：对 `static/**` 全量正则扫描 `演示|示意|假数据|mock|示例|demo|MOCK`（`rg` 口径）。
  命中仅剩：`README.md` 的「演示模式（mock，默认关闭）」开发者说明（按任务约定保留）、
  `api.js`/`mock.js` 源码注释（非 UI）。`README.md:48` 目录说明中的「四态演示」字样已改为「路由/顶栏/livebar/SW 注销/隐私」。
- **保留说明**：`README.md` 中「演示模式（mock，默认关闭）—— 假数据仅位于 `js/mock/`，生产路径不加载」
  属开发者文档（非产品 UI），按派发约定保留，用于说明 mock 默认关闭。

### 回归汇总

- **语法**：`node --check` 全部 14 个 JS（Node 18 按 CJS 解析，用 `.mjs` 副本检查）→ `total=14 fail=0`。
- **真浏览器断言**（`python app.py` 8791 + Chrome for Testing headless CDP 9333）：
  - 信号页在线态：**17/17 PASS**（无演示词、无演示条残留节点、空态四要素、data-state=success）；
  - 四态真实触发 + mock：**7/7 PASS**（error 态真实触发、重试按钮、解除后恢复 success、mock 无可见标签）。
  - 合计 **24/24 PASS**。
- **四态覆盖说明**：本轮验证了真实请求触发的 **成功态 / 空态 / 错误态**；加载态为同一 `mountState` 分支，
  由请求中切片 `status=loading` 驱动（C-01 保留机制、未改渲染路径），未单独构造慢响应快照。

## 自验收

- [x] 每个页面四种状态机制全部保留且由真实请求驱动（CDP 断言 error/success 可复现；演示条已移除）
- [x] 所有请求走统一封装层，页面层无裸 fetch（本轮未新增请求）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`（移除的是可见打标，非 mock 本体）
- [x] 数字格式化走统一工具函数 `format.js`（本轮无新增数值格式化）
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可 `python app.py`（8791）启动，真浏览器控制台无致命报错
- [x] 三条目标逐条落地并有真浏览器证据（C-01/C-02/C-03/C-04）
- [x] 只改 `static/**`（另按工件协议更新本报告及归档 `-v4.md`）；未动后端 `*.py` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `qa`（G-QA-02 回归）**：新增两条 P0 用例并回归——
  ① `http://127.0.0.1:8791/`（含 `#/signals`）全页文本不含「演示数据」且无 `#statebar/.statebar` 节点；
  ② `state=no_open` 时 `#sg-empty` 展示四要素（已在监控/距上次开口/上次开口/上次结果）且无演示字样。
  复现命令：`python app.py`（8791）→ Chrome `--headless=new --no-sandbox --remote-debugging-port=9333`
  → 打开 `http://127.0.0.1:8791/#/signals`；错误态用 CDP `Network.setBlockedURLs(["*/api/v1/signals/state*"])`。
- **次消费方 `product-manager`（G-PM-05 终验）**：以真实用户视角确认信号页不再出现「演示数据」，空态文案为诚实口径。
- **dev-lead（G-DL-01 销项）**：复核演示条相关 DOM/JS/CSS 全部删除，且四态容器 `mountState` 未被误删。
- **残留风险**：
  1. mock 模式下（`?mock=1`）现在无任何可见打标，仅适合开发者本地替身；生产入口不暴露该参数，风险可接受。
  2. `static/js/mock/mock.js:1` 源码注释仍含「mock 演示数据」字样，属代码注释非 UI；若要零残留可另起小改。
