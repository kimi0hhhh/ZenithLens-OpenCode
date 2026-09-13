---
artifact: 07-frontend-arch
owner: architect
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [frontend-dev, dev-lead]
gate: G-AR-03
---

# 前端架构 · 极境 ZenithLens

> 上游：`docs/00-charter/03-ui-design.md`、`docs/00-charter/04-ui-wireframe.html`、`docs/01-architecture/06-system-arch.md`。
> 约束（Brief §5.3）：**零第三方依赖、无构建步骤**——原生 HTML/CSS/ES2019 JS，由 `server/` 静态托管。
> 本文落地 UI 设计的四态与三个命脉组件；字段口径以 `09-api-contract.md` 为唯一法律。

## 摘要

1. 前端 = **一个壳（app shell）+ 7 视图 + 3 命脉组件 + 1 四态容器**；无框架、无打包、无 npm，浏览器原生 ES module 直接加载。
2. 状态管理采用**单一全局 store + 订阅重渲染**（约 60 行原生实现），不引入 Redux/Vuex；所有数据只来自 `api.js`，**禁止任何 mock/假数据进生产路径**。
3. 统一四态 `StateBlock`（empty/loading/error/success）与统一错误码映射是本文两条硬约束，直接对应 PRD 铁律 1「不造假」。
4. 三个命脉组件：`ValBadge`（读后端 `valuation_mode`）、`UnknownCell`（阻断 `+0.00%`）、`PrivacyMask`（金额打码）。
5. 加载策略：首屏并行 3 请求、切片渲染；引擎状态 12s 轮询；长任务 2s 轮询；任一接口失败只影响所属 StateBlock。

## 正文

### 1. 目录结构

```
web/
  index.html                 # 单页外壳（唯一 HTML）
  css/
    tokens.css               # 设计 token：颜色/圆角/玻璃/等宽
    base.css                 # reset + 排版 + blob 背景
    layout.css               # sidebar/topbar/main + 响应式断点
    components.css           # Card/StatCard/ValBadge/DataTable/Timeline/StateBlock...
    views.css                # 各视图局部样式
  js/
    main.js                  # 入口：初始化 store、注册路由、首屏拉取
    api.js                   # ★ 唯一 fetch 出口（含错误码映射、超时）
    store.js                 # 全局状态 + subscribe/dispatch
    router.js                # 7 Tab 切换（hash 路由，无整页跳转）
    format.js                # 数字/百分比/金额/日期格式化（decimal → 显示）
    components/
      state-block.js         # 四态容器（empty/loading/error/success）
      val-badge.js           # 估值来源徽章（命脉）
      unknown-cell.js        # 未知态单元格（命脉）
      privacy-mask.js        # 金额打码（命脉）
      data-table.js          # 等宽数字表（分组/折叠/显示列）
      stat-card.js           # 汇总卡
      timeline.js            # 信号时间线
      dialog.js / popover.js / toast.js
      switch.js
    views/
      holdings.js            # ① 持仓
      analyze.js             # ② 分析
      signals.js             # ③ 信号
      factors.js             # ④ 因子
      review.js              # ⑤ 复盘
      engine.js              # ⑥ 引擎
      settings.js            # ⑦ 设置
    state/
      copy.js                # 四态文案（与 UI 设计 §4 逐条对齐）
```

### 2. 模块划分与职责

| 模块 | 职责 | 硬规则 |
|---|---|---|
| `api.js` | 封装 `fetch`、超时（默认 8s / 长任务接口 30s）、统一解析信封、抛 `ApiError{code,message}` | **唯一**发起网络请求的地方；组件不得直接 `fetch` |
| `store.js` | 持有全局状态；`getState/setState/subscribe` | 视图只读 state、只通过 action 改；不缓存派生真值（如 total 由后端给） |
| `format.js` | 把后端数值转成展示串 | 概率 ×100→`xx.x%`；比率 ×100→`±x.xx%`；金额 2 位千分位；（见 §6 口径） |
| `router.js` | hash ↔ 视图；切换不重拉已加载数据 | 无二级页面跳转，下钻用展开/弹窗 |
| `components/*` | 无状态优先，输入 props 输出 DOM | `ValBadge`/`UnknownCell`/`PrivacyMask` 为命脉，单独单测 |
| `views/*` | 组合组件 + 调 api + 管理本视图四态 | 每个视图必须显式声明当前 `state` |

### 3. 状态管理方案

**方案：单一 store + 订阅重渲染（自制，约 60 行）。**

```js
// store.js 形状（伪代码）
state = {
  route: "holdings",
  privacy: { masked: false },           // 来自 settings
  runtime: { as_of: null, stale: false, open_count: 0 },
  holdings: { status: "idle", data: null, error: null },      // 四态
  valuations: { status: "idle", data: null, error: null },
  forecast: { status: "idle", data: null, error: null },
  review: { status: "idle", data: null, error: null },
  ledger: { status: "idle", data: null, error: null },
  factors: { status: "idle", data: null, error: null },
  engine: { status: "idle", data: null, error: null },
  settings: { status: "idle", data: null, error: null },
  task: { id: null, status: "idle", progress: 0, step: "" },
}
```

- **每个数据切片自带四态**（`status: idle|loading|success|empty|error` + `data` + `error`）。视图渲染时读自己的切片，互不牵连。
- **订阅机制**：`subscribe(viewFn)`；`setState(patch)` 后对变更切片触发对应视图重渲染（按 `route` 定向，不整页重绘）。
- **不引入框架的理由**：视图仅 7 个、状态扁平、无复杂列表 diff；引框架需构建步骤，违反零依赖底线。代价：需手工管理重渲染范围；在 7 视图规模可控。
- **禁止项**：store 中不得存放由其他字段可推出的"真值"（例如 total 由后端返回，不在前端 Σ 之后再当事实源）；前端可做求和**仅用于自检展示一致性**，不一致必须报错而非静默以自己为准。

### 4. 四态统一处理公约（与产品经理 UI §5.4 对齐）

所有数据视图必须经 `StateBlock` 渲染，禁止自行拼凑空/错态。

| 状态 | 触发 | 渲染 | 铁律 |
|---|---|---|---|
| `loading` | 请求发出、未返回 | 脉冲点/骨架 + 文案（`copy.js` 按视图取） | 骨架**不得**显示任何数字 |
| `empty` | 请求成功但集合为空（如无开口、无持仓、无信号） | 居中标题 + 副文案 + 事实卡 + 行动按钮（视视图而定） | 区分"空"与"错"：无信号是**常态**，文案须写明"不是故障" |
| `error` | 请求失败或 `ok=false` | 红框 + 可读原因（来自 `error.message`）+ 重试按钮 | **不得**回退示例数据；不得静默空白 |
| `success` | 有数据 | 真实内容 | 只显示后端返回值；未知用命脉组件 |

**关键实现约定**：

- `STATE_COPY` 文案与 UI 设计 §4.1~§4.7 的表格逐条对应（`state/copy.js`）。
- 同一页可有多个 StateBlock（如持仓页的总览卡、明细表分别成态）；一个接口失败不使其他块进入 error。
- 重试按钮重新调用该切片的加载 action，不刷新整页。

### 5. 命脉组件细规

#### 5.1 `ValBadge`（估值来源徽章）

- 输入：`valuation_mode`、`confidence`、`source_label`、`trace`、`nav_date`、`mae`。
- 文案映射（**来自后端 `valuation_mode`，禁止前端硬编码映射以外的推断**）：
  `official→官方净值 / intraday→盘中估算 / holdings→重仓加权 / proxy→代理近似 / unknown→未知`。
- 配色：按 `confidence`（high→绿 / mid→金 / low→红 / unknown→虚线灰），**来源名与置信度分离**，置信度优先着色（UI §5.1）。
- 悬浮/展开：`source_label` + 降级链路（由 `trace` 拼接，如 `official 未出 → intraday 命中`）+ 历史 MAE + 方向命中率 + 样本日数。
- 硬规则：`trace` 缺失时**只显示 mode 文案，不编造链路**；`nav_date` 缺失显示"净值截止日未知"。

#### 5.2 `UnknownCell`（未知态）

- 判定：`change_rate === null || change_rate === undefined || typeof !== "number" || Number.isNaN(...)` → 未知。
- 渲染：涨跌列 `<span class="unk">未知</span>`（斜体灰）；今日盈亏 `—`。
- 汇总：若存在未知持仓，副标题必须出现"仅覆盖 N/M 只，其余未知不计入"（N/M 来自后端 `coverage` 字段，不由前端数）。
- **禁止**：`Number(null)`、`Number("")`、`parseFloat` 后当 0；`change_rate === 0` 才渲染 `+0.00%`。

#### 5.3 `PrivacyMask`（隐私打码）

- 开关来自 `settings.privacy.masked`，切换时 `PUT /api/v1/settings` 持久化。
- 实现：给所有金额节点加类 `amt`；`masked` 时用 CSS 模糊 + `••••` 覆盖（样式参照线框）。
- 只作用于展示，**不改变 store 中的数值**，也不影响任何计算/导出。

### 6. 数值展示口径（与 09-api-contract §1 一致）

| 后端字段类型 | 含义 | 前端展示 |
|---|---|---|
| `*_p`（如 `p_up`） | 概率，小数 [0,1] | ×100，保留 1 位，如 `0.583 → 58.3%` |
| `*_rate` / `*_ratio` / `pct` | 比率，小数非百分数 | ×100，保留 2 位，带 +/−，如 `0.0124 → +1.24%` |
| `delta_pp` | 增量，小数（0.099=9.9pp） | ×100，保留 1 位，如 `+9.9pp` |
| `*_amt` / `*_value` | 金额，元 | 2 位 + 千分位，`¥53,243.28`；masked → `••••` |
| `shares` | 份额，份 | 4 位小数 |
| `nav` / `price` | 净值，元/份 | 4 位小数 |
| `z` | z 值 | 3 位小数 |
| 日期 | `YYYY-MM-DD` | 原样 + 可选"周x" |
| 时间戳 | ISO 8601 带时区 | 本地 `HH:mm`（时区 `Asia/Shanghai`） |

**硬规则**：格式化只发生在 `format.js`；组件不得各自实现百分比逻辑，避免"12.42% vs 0.1242"分叉（PRD 失败定义）。

### 7. 错误处理统一口径

```js
// api.js 伪代码
async function request(path, opts) {
  try {
    const res = await fetchWithTimeout(BASE + path, opts, timeoutFor(path));
    const body = await res.json().catch(() => { throw new ApiError("E_PARSE", "返回不是合法 JSON"); });
    if (!body.ok) throw new ApiError(body.error.code, body.error.message);
    return body;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e.name === "AbortError") throw new ApiError("E_TIMEOUT", "请求超时");
    throw new ApiError("E_NETWORK", "无法连接本地服务");
  }
}
```

- 视图捕获后：`store.setState({ [slice]: {status:"error", error:{code,message}} })` → `StateBlock` 渲染。
- `error.code` 显示文案映射集中在 `copy.js`；未知 code 统一显示"发生未知错误：<message>"，不吞掉 message。
- 控制台可 `console.error` 便于排查，但**不得**把密钥/持仓金额打进日志（隐私）。

### 8. 日志与可观测性

- 前端无自建日志服务；仅：
  1. `console.error` 记录失败接口与错误码（不含金额/密钥）；
  2. Topbar 的 `LiveBar` 展示 `runtime` 状态（正常/波动/不通/陈旧）；
  3. 引擎页轮询 `GET /engine/status`，展示心跳与最近成功时间。
- 真实日志在**后端**（`server/`），前端只负责展示后端给的 `runtime`/`data_sources`。

### 9. 路由与交互

- hash 路由：`#/holdings`、`#/analyze`…；默认 `#/holdings`。
- 无二级页面：所有下钻用 `details`/弹窗/气囊，关闭回原位（UI IA §1）。
- 危险操作（删除持仓）走二次确认对话框；台账页**无**任何编辑/删除入口。
- 响应式断点：≥1100 侧栏常驻；900~1100 卡片两列；≤900 侧栏转底部栏、表格单列。

## 自验收

- [x] 给出目录结构与模块划分
- [x] 状态管理方案（单一 store + 订阅）并说明不引框架的理由与代价
- [x] 前端架构写明「加载/错误/空态/成功」统一约定，与 UI 设计四态对齐
- [x] 三个命脉组件单独细规（ValBadge / UnknownCell / PrivacyMask）
- [x] 错误处理统一口径（ApiError + code 映射 + 不回退假数据）
- [x] 日志与可观测性口径（前端只展示后端状态，不回传隐私）
- [x] 数值展示口径唯一入口 `format.js`，避免口径分叉
- [x] 未写实现代码（仅伪代码/形状说明）

## 下游交接

- **主消费方**：`frontend-dev`。需其执行：按本目录落 7 视图与 3 命脉组件；`ValBadge` 读 `valuation_mode`、`UnknownCell` 阻断 `+0.00%`、`PrivacyMask` 只作用展示；所有请求经 `api.js`。
- **次消费方**：`qa`。需其执行：按四态与命脉组件建负向用例（G3/G4/G5/G2），重点断言"无假数据""未知不含 `+0.00%`""徽章=mode"。
- **残留风险**：
  1. **引擎页 125 格热力图**信息密度高，窄屏需折叠/横滚（责任人：frontend-dev，期限：S4）。
  2. **顺序加载导致的口径时间差**：首屏三请求并行，若估值与组合预测的 `as_of` 不同，需在 Topbar 分别标注时间，避免用户以为同一时点（责任人：frontend-dev，期限：S4）。
  3. **ES module 的 file:// 限制**：必须经 `http://127.0.0.1` 访问，与 AGENTS「不要双击 HTML」同因；README 需写明（责任人：dev-lead，期限：S5）。
- **未覆盖**：接口逐字段（`09-api-contract`）、后端模块（`08-backend-arch`）。
