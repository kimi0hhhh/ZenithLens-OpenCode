---
artifact: 06-system-arch
owner: architect
version: v3
status: approved
supersedes: v2
created: 2026-09-12
reviewers: [dev-lead, backend-dev, frontend-dev, product-manager]
gate: G-AR-02
---

# 项目开发架构（系统架构）· 极境 ZenithLens

> 上游：`docs/01-architecture/05-product-arch.md`、`docs/PROJECT_BRIEF.md` §5.3、`docs/00-charter/02-prd.md` F-11。
> 本文回答五个必答问题：**数据从哪来/多久更新 · 状态存在哪 · 前后端怎么通信 · 失败会怎样 · 边界在哪**。
> 不写代码；关键机制用伪代码或流程说明。
>
> **v3 重跑方法（skill 驱动）**：
> - `codebase-design`：§6 系统分层改用**深模块词汇**（Module / Interface / Seam / Adapter / Depth）描述，§6.1 给出**接缝地图**与删除测试。
> - `domain-modeling`：§8 附 **ADR 索引**（决策记录正文见 `10-arch-review §ADR`），存储/通信/审计等"难以逆转"的选择首次成文。
> - `grill-with-docs`：失败矩阵（§4）与边界（§5）承接第二轮 A-07~A-10 的裁定。

## 摘要

1. **形态**：本地单用户 web（`http://127.0.0.1:<port>`）+ pywebview 桌面 exe；引擎纯 Python 标准库，Python 3.8+ 直接 `python app.py` 起服，零第三方依赖。
2. **五问一句话**：数据来自腾讯日 K + 三源实时估值 + 本地 `funds_data.json`（按需拉取/盘后回填/本地缓存累积）；状态存本地 JSON/JSONL 文件（台账 append-only）；通信是 127.0.0.1 上的 REST+JSON，长任务用轮询（无 WebSocket）；失败时逐档降级到 `unknown` 并保留缓存与陈旧提示；边界是单机单用户无并发，不联网部署、不交易。
3. **存储不用数据库**（评测过 Python 自带 `sqlite3`）：改用 JSON/JSONL + 原子写 + 文件锁，理由是数据量小（22 基金 × ≤250 日）、依赖为零、台账可人工审计；代价见 §4.6。
4. **通信不用 WebSocket**：数据 T+1 更新，无实时推送需求；任务进度用 12 秒内轮询，成本可忽略。
5. **深模块原则（codebase-design）**：`value_fund`（五档降级）、`predict_one`（E1/E3→DDSM→双否决→出口）、`build_forecast`（组合加权）是三个**深模块**——小接口（分别返回 `ValResult` / `Prediction` / `PortfolioForecast`）背后藏着最复杂的逻辑；外部数据源集中在**接缝** `core/adapters/`，删除测试见 §6.1。
6. **v2 裁定延续（G-AR-06）**：当日估值 INSERT-ONLY（`valuation_history.jsonl` 审计源，A-01）；未知持仓成本不计入 `total_value`（A-02）；组合方向加最小覆盖门槛（A-03）；T+3/T+15 未验证不出方向（A-04）；否决层缺失即弃权（A-05）；引擎离线区分快照/旧快照/无快照（A-06）。
7. **v3 第二轮裁定（G-AR-06 v2）**：立方体 `naive` 为**研究口径**（默认折叠）、`ddsm` 为**生产口径**（默认展开），并新增 `cube/` 缓存（A-07）；组合加权口径冻结为**可信市值**，`weighting_basis` 随响应返回（A-08）；竞技场性能色板独立于涨跌色（A-09）；影子盘台账"当日首次口径永久 + 全量归档"（A-10）。
8. 失败降级矩阵（§4）与边界（§5）是本文最硬的约束，任何实现若绕过即触发 G-AR-02 退回。

## 正文

### 1. 五问之一：数据从哪来、多久更新

| 数据 | 来源 | 更新时机 | 历史/上限 | 落盘位置 |
|---|---|---|---|---|
| 持仓（22 只） | 用户本机 `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json` | 首次启动导入一次；用户手动"重新导入" | 以源文件当前内容为准 | `data/holdings.json`（产品自持，源文件只读） |
| ETF/标的日线 OHLCV | 腾讯 `web.ifzq.gtimg.cn` 日 K（**不复权** + 自修除权：单日跳变 >25% 时缩放该点之前历史） | 每个交易日收盘后刷新一次；用户可在引擎页手动触发 | 首次拉取近 **250 交易日**；此后增量追加到本地缓存，不依赖外部历史上限 | `data/cache/bars/<code>.json` |
| 基金官方净值 | 天天基金（官方净值接口） | 盘后按轮询回填；具体公布时点不确定 | 近 250 交易日 | `data/cache/nav/<code>.json` |
| 实时估值 | 腾讯实时 `qt.gtimg.cn` / 天天基金估算 / 新浪 `hq.sinajs.cn` | 盘中/盘后按需拉取；每次产出**追加**一条入账记录 | 不适用 | `data/snapshot/valuation_history.jsonl`（**INSERT-ONLY 审计源**）+ `data/snapshot/valuation-YYYYMMDD.json`（可重建缓存，A-01） |
| 重仓股列表 | 天天基金基金档案（前十大） | 季报披露后更新；缓存 30 天 | 前 10 大 | `data/cache/holdings_<code>.json` |
| 代理映射 | 产品内维护的 `fund → proxy ETF` 映射表 | 人工/导入维护 | — | `data/proxy_map.json` |
| 预测/台账 | 本地引擎计算 | 收盘时点开口写盘；到期回填 | INSERT-ONLY | `data/ledger/signals.jsonl` + `data/ledger/backfill.jsonl` |
| 因子账本 | 本地引擎 | 每次扫描/体检/淘汰追加 | 只增 | `data/factors/*.json(.jsonl)` |
| 状态立方体快照 | 本地引擎派生（只读） | 训练段更新或手动重建 | 按 `snapshot_as_of` 失效 | `data/cache/cube/<code>.json`（v3 新增，A-07） |
| 影子盘归档 | 本地引擎 | 每日归档 + 阈值触发冷存 | 首次口径永久 + 全量归档（A-10） | `data/ledger/archive/YYYYMM.jsonl` |

**结论（合格答案口径）**：**不做全市场历史回补**；首次建缓存拉近 250 交易日，之后靠本地累积。外部源只决定"今天能不能取到数"，不决定"历史有没有"——历史一旦落盘即自持，故单一数据源被墙不会让系统失忆。

### 2. 五问之二：状态存在哪

#### 2.1 存储选型决策（ADR-0001，见 §8）

| 候选 | 结论 | 理由 / 不用它的代价 |
|---|---|---|
| **JSON/JSONL 文件** | **采用** | 单用户、数据量 ≤ 数年 × 22 标；可人工审计；stdlib `json` 直接支持；append-only 台账天然防篡改 |
| Python 自带 `sqlite3` | 不用 | 会引入"二进制库文件不可读 + schema 迁移"成本；台账 INSERT-ONLY 用触发器/权限实现比文件难度更高；本规模下无性能收益 |

代价（显式承认）：全量扫描是 O(文件大小) 而不是 O(log N)；写入需自行做原子替换与并发保护（§2.3）。在 ≤10 万行台账、22 只持仓的规模下可接受。

#### 2.2 数据目录结构（产品自有数据根）

```
ZenithLens-OpenCode/
  app.py                     # 唯一入口：解析端口 → 起 HTTP 服务 → 可选拉起 pywebview
  core/                      # 纯逻辑（无 I/O 副作用，可单测）
  server/                    # HTTP 服务与 API 处理器
  web/                       # 前端静态资源（原生 HTML/CSS/JS）
  data/                      # ★ 运行期数据（不入版本库）
    holdings.json            # 产品自持持仓（CRUD 落这里）
    settings.json            # 隐私开关 / LLM / 端口等
    proxy_map.json           # fund → proxy ETF 映射
    runtime.json             # 本次运行端口、pid、启动时间
    cache/
      bars/<code>.json       # ETF/标的日线
      nav/<code>.json        # 基金官方净值历史
      holdings_<code>.json   # 前十大重仓（带 fetched_at）
      cube/<code>.json       # v3：状态立方体快照（按 snapshot_as_of 失效，A-07）
    snapshot/
      valuation_history.jsonl# ★ 估值入账历史（INSERT-ONLY 审计源，A-01）
      valuation-YYYYMMDD.json# 当日估值缓存（可整文件覆盖重建，非审计源）
      prediction-YYYYMMDD.json# 当日预测快照
    ledger/
      signals.jsonl          # INSERT-ONLY 台账（每行一条 JSON）
      backfill.jsonl         # INSERT-ONLY 回填补丁（不改原行）
      archive/YYYYMM.jsonl   # v3：台账全量归档（冷存，A-10）
    factors/
      adopted_factors.json
      scan_history.jsonl
      factor_health.jsonl
      retired_log.jsonl
      shadow_signals.jsonl
      factor_arena.jsonl
    runs/<task_id>.json      # 长任务进度与结果
    locks/                   # 进程/文件锁
```

#### 2.3 写入规则（防损坏 / 防并发）

- **原子替换**：任何整文件 JSON 写入先写 `*.tmp`，`fsync` 后 `os.replace` 覆盖目标（同盘原子）。
- **追加写**：`.jsonl` 一律 `open(..., "a", encoding="utf-8")` 追加，不重写整文件；每行写完即 `flush`。
- **文件锁**：`data/locks/<name>.lock` 用 `os.open(..., O_CREAT|O_EXCL)` 实现；引擎与 API 进程对台账/因子账本的写操作互斥。锁过期阈值 120s，超时可强制接管并记日志。
- **单写者原则**：同一文件同一时刻只允许一个写者；读操作无锁（依赖原子替换保证读到的是完整旧版或完整新版）。
- **归档不改审计（A-10）**：归档只**复制**已落盘行到 `archive/`，不删除 `signals.jsonl` 中 `is_first_of_day` 记录对应的当日首次行；主文件可截断的仅是"非首次且已归档"的历史行，截断动作记录到 `archive/_manifest.jsonl`。

#### 2.4 各文件字段契约

文件字段与 API 字段同名同义，完整定义见 `09-api-contract.md`；文件只存原始值，不存派生展示值（如不打码、不千分位）。

### 3. 五问之三：前后端怎么通信

#### 3.1 协议与通道

- **REST + JSON over HTTP/1.1**，绑定 `127.0.0.1`（**不绑 0.0.0.0**，杜绝局域网访问）。
- 默认端口 **8787**（可用 `--port` 或 `settings.json` 覆盖）；端口占用时**自动向上探测**（8787→8788→…→+20），实际端口写入 `data/runtime.json` 并在启动日志打印。不采用固定端口保证"点启动必能起"。
- 所有接口前缀 `/api/v1/`；静态资源由同一服务提供。
- 响应统一信封（见 `09-api-contract §2`）：`{ "ok": bool, "data": ..., "error": null|{code,message,detail}, "as_of": "..." }`。

#### 3.2 为什么不用 WebSocket / SSE

| 候选 | 结论 | 理由 |
|---|---|---|
| WebSocket | 不用 | 数据 T+1 更新，无实时推送需求；websockets 需第三方库，违反零依赖；本地单用户无长连接收益 |
| SSE | 不用 | 需长连接管理，收益仅限长任务进度；轮询已足够 |
| **HTTP 轮询** | **采用** | 首屏一次拉取；引擎状态每 **12s** 轮询一次；长任务（估值刷新/预测/回测）触发后每 **2s** 轮询 `GET /tasks/{id}` 直到 `done/failed` |

#### 3.3 请求时序（关键路径）

```
[首屏]
前端 GET /api/v1/holdings?with=valuation,summary,tier  ──►  后端读 holdings.json + 估值缓存
前端 GET /api/v1/portfolio/forecast                    ──►  读当日预测快照（无则三态返回，不现算）
前端 GET /api/v1/review/scores                          ──►  读回测成绩文件
（三请求并行；任一失败只影响对应 StateBlock，不整页崩）

[刷新估值]
前端 POST /api/v1/tasks {type:"refresh_valuation"} ──► 返回 task_id
前端每 2s GET /api/v1/tasks/{id} 直到 done
完成后再拉 /api/v1/valuations

[收盘预测]
后端内置调度/手动 POST /api/v1/tasks {type:"run_prediction"}
逐标的走 E1/E3 → DDSM → 双否决 → 出口；开口写 ledger
```

#### 3.4 契约的"接缝"定位（codebase-design）

- 前后端之间的**唯一接缝** = `/api/v1/*` 的 JSON 信封；`09-api-contract` 是接缝两侧共同的 **Interface**（含字段、单位、精度、枚举、错误码、三态返回）。
- 前端只有 `api.js` 一个 **Adapter** 触碰该接缝；后端只有 `server/handlers/*` 一侧触碰。任何一侧绕过信封/字段口径（如前端自造 mock、后端自定义字段名）即破坏接缝。

### 4. 五问之四：失败会怎样

#### 4.1 统一错误模型

- API 永远返回 JSON 信封，不裸抛堆栈；`error.code` 为**穷举枚举**（见 `09-api-contract §3`）。
- 前端按 `error.code` 显示对应文案，并进入 `StateBlock` 的 `error` 态；**不得回退到示例数据**（PRD G3 / 铁律 1）。

#### 4.2 失败降级矩阵（硬约束）

| 失败场景 | 系统表现 | 用户可见 | 是否阻塞 |
|---|---|---|---|
| 单一估值源超时（如腾讯） | 该档记为 miss，进入下一档 | 徽章最终落点 + `trace` | 否 |
| 五档全部失败 | `valuation_mode=unknown`、`change_rate=null` | 涨跌列"未知"、盈亏"—"、汇总"仅覆盖 N/M" | 否 |
| ETF 日线拉取失败 | 用本地缓存最后一根；标记 `stale=true` | 顶部数据快照滞后提示条 | 否 |
| 官方净值未公布 | `nav.official_nav=null`，估值停留在估算档 | 徽章"盘中估算/重仓加权/代理近似" | 否 |
| 官方净值回填 | 写入 `nav.*` 并**追加**一条估值入账记录；**不改已入账记录的 `valuation_mode`/`trace`** | 可区分"既成事实 vs 估算"，且可回溯当日首次入账（A-01） | 否 |
| 引擎未运行（三态，A-06） | ① 有当日快照 → 正常返回；② 只有旧快照 → 返回旧数据 + `engine_status=offline`（陈旧态）；③ 无任何快照 → `E_ENGINE_OFFLINE`（error 态）；**禁止**用空态承载 | 引擎页 HUD"离线"+最近成功时间；预测页"引擎未运行，展示 <date> 快照"或"引擎未运行"错误态 | 否（①②）/ 是（③，该页 error 态） |
| 立方体/竞技场快照缺失 | 相关接口返回空集/`null` | 引擎页"待写入/—" | 否 |
| 台账写盘失败 | 预测仍可展示；记录到 `runs` 并重试一次 | 该条标"未入账"红色提示 | 部分 |
| 持仓源文件缺失/损坏 | 若 `data/holdings.json` 存在则用产品自持；否则空态引导 | 空态"还没有录入任何持仓"+重试 | 是（首屏空态） |
| 配置读写失败 | 不覆盖旧配置；返回 `E_IO` | 设置页"保存配置失败：<原因>"，已填内容不丢 | 部分 |
| 端口占用 | 自动换端口；20 个都占用则 `E_PORT` | exe 弹出可读错误，**不得静默** | 是（启动） |
| Python < 3.8 / 依赖缺失 | 启动前版本检查 → 打印可读原因并退出码非 0 | exe 显示错误弹窗 | 是（启动） |
| 网络完全断开 | 已缓存数据可看；估值降级 unknown | 首页降级提示条 + 数据源"不通" | 否（离线可看） |

#### 4.3 陈旧度（staleness）口径

- 每个数据集合带 `as_of`（数据日期，`YYYY-MM-DD`）。
- 当前交易日 > `as_of` 时，UI 顶部 chip 显示"数据快照 `<as_of>`"，且估值相关数字**必须**与该 chip 同屏（不允许只有数字没有时间）。
- `stale` 的判定与展示由后端给出 `staleness` 对象（见契约），前端不自行推算日期。
- 多切片并存时（估值 `as_of` 与预测 `as_of` 不同）**按切片各自标注**，不使用单一全局时间掩盖差异（A-06 衍生约束）。

### 5. 五问之五：边界在哪

| 边界 | 明确取值 |
|---|---|
| 用户数 | **1**（单用户本机），无账号/权限/会话 |
| 并发 | 无并发写；HTTP 服务用 `ThreadingHTTPServer` 但所有写路径经文件锁串行化 |
| 部署 | Windows 本机；`127.0.0.1` 回环；不部署公网、不做反向代理 |
| 运行时 | Python **3.8+ 标准库**；桌面壳 pywebview（打包 exe 时依赖，开发态可不装） |
| 数据规模 | 持仓 ≤ 50 只；标的日线 ≤ 500 根/只；台账 ≤ 10 万行；单次预测 CPU ≤ 3 分钟 |
| 联网 | 仅出站拉行情/净值/估值/可选 LLM；**无入站、无上传**；无云同步 |
| 交易 | 只读判断依据，不下单、不接券商 |
| 主题 | 无深色主题、无多语言 |
| 数据写入 | 不改写用户桌面 `funds_data.json`；产品数据全在 `data/` |

### 6. 系统分层（codebase-design 深模块视角）

```
┌─ 展示层 web/（原生 HTML/CSS/JS，无构建步骤）
│   壳层 app shell（Sidebar/Topbar/StateBlock）+ 7 视图 + 组件
├─ 接口层 server/（stdlib http.server + 手写路由）
│   路由 → 参数校验 → 调 core → 统一信封序列化；错误码映射
├─ 领域层 core/（纯逻辑，零 I/O，可单测）
│   holdings / valuation(五档) / gates / ddsm / veto / portfolio
│   review / ledger / factors / governance / arena / cube / tasks
├─ 适配层 core/adapters（唯一允许外部 I/O 与网络）
│   腾讯日K / 腾讯实时 / 天天基金 / 新浪 / 本地文件读写 / 文件锁
└─ 存储层 data/（JSON/JSONL 文件，§2）
```

**依赖方向单向向下**：展示层只经接口层；领域层不 import server；适配层是唯一碰网络与文件系统的地方（便于把外部源替换成假实现做测试）。

#### 6.1 接缝地图与删除测试（codebase-design）

| 模块 | Interface（调用方必须知道的全部） | Seam | Adapter | 删除测试 |
|---|---|---|---|---|
| `core.valuation.value_fund` | `(holding, as_of_date) -> ValResult`；保证原子性（一个确定 mode 或 unknown）；`trace` 穷举；超时预算 20s | 每档数据源 | `tencent_rt` / `eastmoney` / `sina_rt` / `proxy bars`（≥2 个，故接缝为**真实接缝**） | 删掉它 → 五档链会在 holdings/predict/portfolio/precision 四处重现 → **在赚深度**，保留 |
| `core.predict.predict_one` | `(code, bars, train_stats) -> Prediction`；含 gate/ddsm_state/双否决/exit/三窗口；不改外部 | 特征/训练统计 | 内存统计（单适配器 → **假想接缝**，不为它加抽象） | 删掉它 → 触发门+DDSM+双否决+出口会在信号/分析/组合/引擎四处重现 → **在赚深度**，保留 |
| `core.portfolio.build_forecast` | `(predictions, holdings, window) -> PortfolioForecast`；纯函数、无副作用 | 无外部 | 纯内存 | 删掉它 → 加权/门槛/覆盖占比会在持仓/分析两处重现 → 保留（深度中等） |
| `core/cube.build_cube` | `(code) -> StateCube`；naive 用真实档位、ddsm 用加噪+收缩；空样本格显式返回 | 训练样本 | 纯内存 | 删掉它 → naive/ddsm 双计数会在竞技场/训练状态/对比卡三处重现 → 保留（v3 深模块） |
| `core.adapters.files` | 原子写 / jsonl 追加 / 文件锁；不泄漏路径细节 | 文件系统 | 真实文件系统 / 测试内存实现（≥2 → 真实接缝） | 删掉它 → 原子写与锁会在 ledger/valuation/factors 多文件重现 → 保留 |

> **深度纪律**：深模块内部可以有小而可 mock 的部件，但它们**不属于 Interface**。例：`value_fund` 内部把五档拆成 5 个私有步骤（可单测），对外仍只暴露一个函数。

### 7. 关键机制说明（伪代码级）

#### 7.1 启动序列

```
app.py:
  1. 版本检查：sys.version_info >= (3,8) 否则打印可读原因 → exit(2)
  2. 读 settings.json（缺失则用默认，写回）
  3. 解析端口：--port / settings / 默认 8787；逐个 bind 探测
  4. 数据自检：确保 data/ 子目录存在；holdings.json 缺失则从 funds_data.json 导入
  5. 起 ThreadingHTTPServer(127.0.0.1, port)
  6. 写 runtime.json（port/pid/started_at）
  7. 打印 "ZenithLens running at http://127.0.0.1:<port>"
  8. 桌面模式：pywebview.create_window(url).start()；失败则回退为只开浏览器/打印 URL
```

#### 7.2 收盘预测调度

```
每个交易日 15:30 后（或手动触发 run_prediction）：
  for each holding where tier in (A,B):
      bars ← bars_cache(code)            # 本地优先，缺失/过期则拉腾讯
      for window in (T1,T3,T15):
          按 08-backend-arch §4 定式计算
      若 T1 出口开口 → append ledger 一行（含 gate/p_up/ddsm_state/双否决/signal）
  写 snapshot/prediction-YYYYMMDD.json
  账本写入使用文件锁，逐行 flush
```

#### 7.3 台账回填

```
到期检查（每次启动 + 每日收盘后）：
  for each ledger line where t{n}_real is null and 已到期:
      取该 code 在 date+n 的实际涨跌
      append_jsonl("data/ledger/backfill.jsonl", {date, code, t{H}_real})
# 读取：signals LEFT JOIN backfill ON (date, code)；不改原行（INSERT-ONLY）
```

#### 7.4 估值入账（INSERT-ONLY，A-01）

```
每次刷新估值（手动/调度）：
  with file_lock("valuation"):
      for h in holdings:
          r = value_fund(h, today)                  # 五档降级链
          first = not exists_history(today, h.code)  # 当日首次？
          append_jsonl("data/snapshot/valuation_history.jsonl",
                       {**r, date:today, code:h.code, written_at:now,
                        run_id:task_id, is_first_of_day:first})
  write_json_atomic("data/snapshot/valuation-YYYYMMDD.json", latest_by_code())  # 仅缓存
读取：latest_by_code() ← 从 history 取 (date,code) 最大 written_at 一条；
      徽章详情可读全量 history（按 written_at 升序）。
```

> 硬规则：`valuation_history.jsonl` 只增不改；缓存文件损坏可由 history 完整重建；官方回填/二次刷新只追加，绝不改写已入账的 `mode`/`trace`。

#### 7.5 台账归档（A-10）

```
归档（每日收盘后）：
  with file_lock("ledger"):
      rows = read_jsonl(signals.jsonl)
      keep = rows where is_first_of_day 或未回填       # 首次口径永久保留
      archived = rows - keep
      append_jsonl(archive/YYYYMM.jsonl, archived)      # 复制，不删审计行
      append_jsonl(archive/_manifest.jsonl, {date, archived_count, kept_count, checksum})
# 硬规则：任何归档不得使"当日首次入账口径"不可读；归档文件同样 append-only
```

### 8. ADR 索引（domain-modeling；正文见 `10-arch-review §ADR`）

> 收录标准（skill 三问缺一不收）：**难以逆转** + **无背景会令人惊讶** + **真实权衡过备选**。

| ADR | 决策 | 为何难以逆转 / 真实备选 | 关联 |
|---|---|---|---|
| ADR-0001 | 存储用 JSON/JSONL 而非 SQLite | 一旦数据落地，换库需迁移；备选 SQLite 性能更好但破坏可审计与零依赖 | §2.1 |
| ADR-0002 | 引擎零第三方依赖 + 前端原生无构建 | 引入框架后全量重构；备选 React/Vite 开发快但违反离线复现底线 | §6 |
| ADR-0003 | 无 WebSocket，用轮询 | 通信范式一旦定，改造成本高；备选 WS/SSE 收益仅长任务进度 | §3.2 |
| ADR-0004 | 估值审计源 INSERT-ONLY + 缓存可重建 | 审计语义不可逆；备选"单快照覆盖"简单但丢可追溯（A-01） | §7.4 |
| ADR-0005 | 组合加权口径冻结为**可信市值**，拒绝置信度加权 | 权重口径改变会重写全部历史组合结论；备选置信度加权未过方法论（A-08） | §5 / 09 §5.7 |
| ADR-0006 | 立方体 `ddsm` 为生产口径、`naive` 为研究口径（默认折叠） | 双口径对外语义影响用户信任；备选并列展示易误读（A-07） | §4.2 / 09 §5.25 |

## 自验收

- [x] 五问全部回答：数据来源/更新（§1）、存储（§2）、通信（§3）、失败（§4）、边界（§5）
- [x] 数据来源给出具体域名、更新时机、历史上限与落盘位置
- [x] 存储给出具体文件路径、写入时机、原子写/锁机制
- [x] 通信给出协议、端口策略、轮询间隔，并说明为何不用 WebSocket
- [x] 失败降级矩阵覆盖数据源/引擎/回填/启动/断网
- [x] 边界明确单用户无并发、不联网部署、不交易
- [x] 每项选型（无数据库/无 WebSocket/无框架）写明理由与代价
- [x] 明确写出「本期不做」技术项（§附）
- [x] A-01：估值 INSERT-ONLY 落盘方案（`valuation_history.jsonl`）与缓存重建路径写明
- [x] A-06：失败矩阵明确"引擎离线"三态（快照/旧快照/无快照），禁止空态承载故障
- [x] **codebase-design**：§6.1 接缝地图 + 删除测试覆盖 5 个关键模块（区分真实接缝 vs 假想接缝）
- [x] **domain-modeling**：§8 ADR 索引收录 6 条难以逆转的决策
- [x] **v3 A-07**：新增 `data/cache/cube/<code>.json` 立方体快照与失效口径
- [x] **v3 A-10**：新增 `data/ledger/archive/` 归档策略与"首次口径永久"硬规则

### 附：本期不做（技术项）

| 不做 | 理由 |
|---|---|
| 数据库（含 SQLite） | 规模不需要，破坏可审计性与零依赖 |
| WebSocket / SSE | 无实时推送需求 |
| 前端框架/打包器（React/Vue/Vite…） | 违反零第三方依赖与"原生静态资源"底线 |
| 多进程/多线程计算加速 | 单次预测 CPU 分钟级，串行可接受 |
| 容器化/云部署 | 本地单用户 |
| 自动参数寻优/在线学习 | 违反冻结 holdout 方法论（Brief §5.2） |

## 下游交接

- **主消费方**：`07-frontend-arch` / `08-backend-arch`。需其执行：分别按展示层/领域层边界落目录与模块；文件字段以 `09-api-contract` 为准；模块划分沿用 §6.1 深模块/接缝词汇。
- **次消费方**：`dev-lead`。需其执行：G-DL-02 构建时核验"零第三方依赖 + Python 3.8 + 端口自适配 + 台账 append-only 回填文件方案 + v3 立方体缓存/归档"。
- **残留风险**：
  1. **Python 3.8 与开发机版本差异**（如 `dict|dict` 语法、`str.removeprefix`）需构建阶段实测（责任人：dev-lead，期限：S5）。
  2. **腾讯日K 自修除权阈值 25%** 为经验值，需用真实除权案例回归验证；若误判会污染 r2/vr 特征（责任人：backend-dev，期限：S3）。
  3. **默认端口 8787 与编排看板端口（8790）不同**，但同机若有其他服务占用需依赖自增探测；极端情况 20 个端口全占用需给出可读错误（责任人：backend-dev，期限：S3）。
  4. **官方净值公布时点不确定** 导致"当日 official 是否命中"不稳定，`trace` 需如实记录（责任人：backend-dev，期限：S3）。
  5. **`valuation_history.jsonl` 体积管理**：按刷新频率线性增长，v3 的 `cube/` 与 `archive/` 策略需在 S3 评估实际增速（责任人：backend-dev，期限：S3）。
  6. **立方体快照按 `snapshot_as_of` 失效**：若训练段每日滚动，缓存命中率下降，需评估重建耗时（责任人：backend-dev，期限：S3）。
- **未覆盖**：前端目录与组件树（`07-frontend-arch`）、后端算法与模块（`08-backend-arch`）、接口逐字段（`09-api-contract`）、ADR 正文（`10-arch-review §ADR`）。
