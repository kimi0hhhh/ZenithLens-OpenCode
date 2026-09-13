---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v7
status: draft
supersedes: v6
created: 2026-09-12
reviewers: [dev-lead, qa, product-manager]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（task OC-SHADOWSTAT-FE · 影子盘 HUD 进度语义 · 契约 §6.9）

> 上游：用户实测反馈「影子盘记了最近 20 日还是不启动」、后端 task（OC-SHADOWSTAT-BE）已把
> `/engine/status.shadow_status` 从偏差审查枚举改为**记录进度语义**（`not_started/recording/qualified/gap`），
> 并新增保留独立字段 `shadow_audit_status`（`idle/ok/bad`）；接口需求 `12-interface-request.md` §10 缺口 11。
> **本轮范围**：仅修「引擎页 HUD（R-UI-20）影子盘卡」的枚举错配与进度呈现，并核查信号页/引擎页
> 「影子盘未启动」类误导文案。**不改后端/契约/runtime、不派发子任务。**
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`，真后端已在跑，pid 31144）
> + Node 18.17.1（`node --check`，ESM 副本）+ Chrome for Testing（CDP 9333 直连）。

## 摘要

1. **「记了 20 日还不启动」根因已除**：HUD 仍用旧审查映射 `SHADOW_STATUS_TAG[idle/ok/bad]` 查后端已改成
   进度语义的 `shadow_status`（值 `recording`），查不到 → 回落 `['—','gray']`，卡片恒显「—」。
2. **改法**：`static/js/views/engine.js` 拆成两张互不相交的映射表——`PROGRESS_TAG`（`shadow_status`）与
   `AUDIT_TAG`（`shadow_audit_status`）；HUD 影子盘卡值 = 进度标签，副文案 = `N / 60 日` + 进度条，
   偏差审查以独立小标签「偏差审查 未评估/达标/降级」表达，**不再把 idle 当「未启动」**。
3. **枚举文案**：`not_started→未启动`、`recording→记录中`、`qualified→已达标`、`gap→有缺口`；
   台账进度条同表（`gap` 由「中断」改为「有缺口」）。
4. **实测（真后端）**：`GET /api/v1/engine/status` → `shadow_status="recording"`、`shadow_audit_status="idle"`、
   `shadow_consecutive_days=20`、`shadow_target_days=60`；CDP 读 HUD 卡 innerText =
   `影子盘 / 记录中 / 20 / 60 日 / 偏差审查 未评估`。
5. **回归全绿**：`node --check` **14/14**；真浏览器 CDP 断言 **21/21 PASS**；未改后端/契约/runtime。

## 正文

### C-01 ·【P0·枚举错配】HUD 影子盘状态字因查错映射表而恒「—/未启动」

- **位置**：`static/js/views/engine.js`（改前 `renderHud`）：`const ptag = SHADOW_STATUS_TAG[d.shadow_status] || ['—', 'gray']`，
  其中 `SHADOW_STATUS_TAG = { idle:['未启动'], ok:['达标'], bad:['降级'] }`。
- **根因**：后端 task OC-SHADOWSTAT-BE 已把 `/engine/status.shadow_status` 改为**记录进度**枚举
  （`not_started/recording/qualified/gap`），偏差审查另立 `shadow_audit_status`（`idle/ok/bad`）。
  前端仍按旧审查枚举取键，`recording` 不在表中 → 命中兜底 `—`；用户看到的就是「记录了 20 日却仍不启动」。
- **复现（改前）**：真后端 `shadow_status=recording`、`shadow_consecutive_days=20` → HUD 卡值「—」。
- **改法**（`engine.js:13-18`）：删除 `SHADOW_STATUS_TAG`，新增
  ```js
  const PROGRESS_TAG = { not_started: ['未启动','gray'], recording: ['记录中','warn'], qualified: ['已达标','ok'], gap: ['有缺口','red'] };
  const AUDIT_TAG    = { idle: ['未评估','gray'], ok: ['达标','ok'], bad: ['降级','red'] };
  ```
  两表各管一段、值域不相交，禁止混用（与契约 §6.9 字段一一对应）。

### C-02 ·【P0·进度呈现】HUD 显示「记录中 N / 60」+ 进度条，偏差审查独立表达

- **位置**：`static/js/views/engine.js:118-130`（`renderHud`）。
- **改法**：影子盘卡——
  ```js
  const ptag = PROGRESS_TAG[d.shadow_status] || ['未启动','gray'];
  const atag = AUDIT_TAG[d.shadow_audit_status] || ['未评估','gray'];
  const ratio = (isNum(d.shadow_consecutive_days) && isNum(d.shadow_target_days) && d.shadow_target_days > 0)
    ? d.shadow_consecutive_days / d.shadow_target_days : 0;
  const pstate = d.shadow_status === 'qualified' ? 'on' : (d.shadow_status === 'gap' ? 'bad' : 'warn');
  hudCard('影子盘', esc(ptag[0]), cdays + ' / ' + tdays + ' 日' + progressBar(ratio)
    + '<div style="margin-top:5px">偏差审查 ' + tag(atag[0], atag[1]) + '</div>', pstate)
  ```
  主状态取进度语义（`qualified`→绿、`gap`→红、其余→黄），副行独立显示 `N / 60 日`、进度条与偏差审查标签。
- **证据（真后端，非桩）**：CDP 读 `#eg-hud .hud-c` innerText =
  `影子盘\n记录中\n20 / 60 日\n偏差审查 未评估`；`#eg-hud .hud-c .prg` 计数 = 1（进度条在）；
  后端存档 `evidence/api_engine_status.json`；截图 `evidence/zl_shadow_progress_engine.png`。

### C-03 ·【P1·诚实降级】四枚举 × 三审查态逐档断言，杜绝「—」与误读

- **方法（CDP 桩）**：拦截 `/api/v1/engine/status`，按 URL `sstatus/saudit` 改写两字段后放行（不落产品代码）。
- **实测**：
  | `shadow_status` | `shadow_audit_status` | HUD 卡文本（断言含） |
  |---|---|---|
  | `recording` | `ok` | 记录中 · 20 / 60 日 · 达标 |
  | `qualified` | `bad` | 已达标 · 降级 |
  | `not_started` | `idle` | 未启动 · 未评估 |
  | `gap` | `ok` | 有缺口 · 达标 |
  四例主状态区均无「—」占位；`idle` 只渲染为「偏差审查 未评估」，**不与进度混用**。
- 说明：进度枚举走 `PROGRESS_TAG`、审查枚举走 `AUDIT_TAG`，任一字段缺失时分别回落「未启动 / 未评估」，不再交叉污染。

### C-04 ·【P1·文案核查】信号页 / 引擎页无「影子盘未启动」误导残留

- **核查**：`rg '影子盘未启动|未启动' static/` → 命中仅 `engine.js` 的 `PROGRESS_TAG.not_started`（进度语义，正确）。
  信号页空态文案来自后端 `/signals/state.empty_note`（「这是常态，不是故障…」），与影子盘进度无关；引擎台账进度条
  本就走 `PROGRESS_TAG`（同表），`gap` 文案由「中断」校正为「有缺口」。
- **mock 同步**：`static/js/mock/mock.js` `/engine/status` 补 `shadow_audit_status`，`shadow_status` 由 `not_started`
  改为 `recording`、`shadow_consecutive_days=20`；`/ledger/shadow.progress` 同步为 `recording/20/60`（mock 仍默认关闭）。

### 回归汇总

- **语法**：`node --check` 全部 14 个 JS（Node 18 按 ESM 解析，用 `.mjs` 副本检查）→ `total=14 fail=0`。
- **真浏览器断言**（`python app.py` 8791 + Chrome for Testing headless CDP 9333）：**21/21 PASS**，
  脚本存档 `evidence/verify_shadow_progress_fe.py`，覆盖：后端双枚举形状、HUD「记录中 20/60」、进度条存在、
  偏差审查独立、无「影子盘未启动」、4×2 枚举桩用例。
- **未改**：后端 `*.py`、契约/架构 `docs/01-architecture/**`、`runtime/**`；未派发子任务。

## 自验收

- [x] 每个页面四种状态机制保留且由真实请求驱动（本轮仅改 HUD 渲染）
- [x] 所有请求走统一封装层，页面层无裸 fetch（本轮未新增请求）
- [x] 无硬编码业务数据；mock 隔离在 `static/js/mock/` 且默认关闭（仅同步新字段结构）
- [x] 数字格式化走统一工具函数 `format.js`（`isNum`/`int`），进度条复用 `components.js#progressBar`
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）；契约缺口写入 `12-interface-request.md` §10 缺口 11
- [x] 项目可 `python app.py`（8791）启动，真浏览器控制台无致命报错
- [x] 目标逐条落地并有真浏览器证据（C-01/C-02/C-03），文案残留已核查（C-04）
- [x] 只改 `static/**`（另按工件协议更新本报告、接口需求与证据）；未动后端 `*.py` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `qa`（G-QA-02 回归）**：新增/回归用例——
  ① 真后端下 HUD 影子盘卡须含「记录中」与「20 / 60」，且**不得**含「影子盘未启动」；
  ② `recording/qualified/not_started/gap` 四进度 × `idle/ok/bad` 三审查各自文案正确、主状态区无「—」；
  ③ 存在 `#eg-hud .hud-c .prg` 进度条。复现命令：`python app.py`（8791）→ Chrome `--headless=new --no-sandbox --remote-debugging-port=9333`
  → 断言脚本 `docs/02-frontend/evidence/verify_shadow_progress_fe.py`。
- **次消费方 `architect`（契约裁定）**：契约 §6.9 仍注 `shadow_status = enum shadow_review_status`，与后端现状不符，
  已登记 `12-interface-request.md` §10 缺口 11，请求将 `shadow_status` 改为进度枚举并正式收录 `shadow_audit_status`，版本 +1。
- **dev-lead（G-DL-01 销项）**：复核 `engine.js` 无 `SHADOW_STATUS_TAG` 残留、无按 `idle/ok/bad` 查进度字段的代码。
- **残留风险**：
  1. 契约 v7 与后端 `shadow_status` 语义暂不一致（本报告登记缺口，待架构师 +1）；前端已按**后端实测**实现，不依赖契约旧注。
  2. 复盘页「影子盘降级审查（idle/ok/bad）」条读 `/engine/shadow-review`（审查语义，正确），其 idle 文案由后端给出，
     本轮未改；若后端把 idle 文案改成「未启动」将再次误导，已在上游提示（责任人：backend-dev，期限：下轮）。
