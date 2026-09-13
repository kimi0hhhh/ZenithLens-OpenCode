# README-START · 极境 ZenithLens（R2 开发版构建 · OpenCode · S5 + C0 + C1b + R3 终验 v7）

> 构建标识：`zenithlens-oc / R2-S5-C1b-R3 / 2026-09-13`｜引擎版本 `oc-s3-v1`｜构建根：本目录（`docs/04-integration/build-r2/`）
> 关联评审：`docs/04-integration/15-code-review-r2.md`（**v9：§10.6 F2 自碰撞伪影修复单笔复查 PASS**；§10.5 断连修复；§10 三笔 C1 delta-pass；§9.5 C0 快审 PASS）
> 源码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`（本目录为其**完整可启动副本**：源码 + static + tests + data/ledger 快照 + 本文件 + start 脚本；与源逐文件 MD5 对齐，见 §校验记录）

## 环境要求（第 0 步 · 先看这个）

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows（本机单用户） | 路径含中文，命令行用引号包裹 |
| Python | **3.8+**（实测 3.8.6） | `app.py` 启动时校验 `sys.version_info >= (3,8)`，低于即打印 `E_VERSION` 退出 |
| 依赖 | **无第三方依赖**（纯 Python 标准库） | 不需要 pip / npm / 构建步骤 |
| 浏览器 | 现代浏览器（原生 ES module） | **必须**经 `http://127.0.0.1` 访问，禁用 `file://` |
| 数据 | 本目录自带 2026-09-13 数据快照 | `data/` + `ledger/`；运行期写入本目录内，不影响源码根 |

## 三步启动

**第 1 步 · 起服**（在**本目录**执行，保持窗口不关；或直接双击 `start.cmd`）
```bat
cd /d <本目录>
python app.py
```
默认监听 `127.0.0.1:8791`；端口占用可用 `python app.py --port 8792` 覆盖。
`app.py` 同时托管 `static/**` 与 `/api/v1/**`，**无需另起 http.server**。
> **首启提示（C1）**：影子盘窗口 20→60 后，**首次启动**会一次性回填补满 60 交易日（约 +5s CPU 窗，期间 `/holdings` 可能有一次性瞬时时延）；此后每日滚动为增量（「来一天换一天」，约 0.26s），稳态不受影响。

**第 2 步 · 打开界面**
浏览器访问 **http://127.0.0.1:8791**
> 必须经 `http://127.0.0.1` 访问，**不要**双击 `static/index.html`（`file://` 下 ES module 被拦截，页面空白）。

**第 3 步 · 冒烟确认**
```bat
curl http://127.0.0.1:8791/api/v1/health
curl "http://127.0.0.1:8791/api/v1/ledger?limit=5"
```
`/health` 返回 200 且 `ok=true`；`/ledger` 行含 `chain_available`（可复现行为 true，点开时间线可看六步链）。

## 本版变更

1. **R2-D1 分析页空态修复**：有预测记录（含 0 开口日）不再整页空态；空态只由「无预测记录/无监控资产」触发，文案按触发因素二分。
2. **R2-D4 影子盘历史文案**：`可用历史 N 日` 后缀随 `archive_merged` 联动（含归档/主文件）。
3. **审计 BLOCK-A1「测试连接」**：改为**本地校验**（仅检查配置格式，不发起任何网络请求）；真探测列 R3（架构 C1 裁定）。
4. **审计 BLOCK-A2 隐私开关**：主开关全站打码 + 副开关「只隐藏明细行（保留组合总额）」生效；**启动水合**（刷新后状态与打码保持）。
5. **审计 BLOCK-A3 事件链**：`/ledger/chain` 读时**同源重算六步链** + `chain_source ∈ {stored/recomputed/null}`（契约 v9.3）；不可复现行前端明示。
6. **审计 SHOULD/NIT**：bootstrap 改读**实测分位**；`scan_factors` 诚实回执；F10 前 20 重仓生效（`top_n=20`，含港股）；注册表「单版本运行/预留态」注（C2）；版本标识 v9.3；`warmup` 静默异常补 stderr 摘要。
7. 后端同步：`main_source.path` 回契约字面；同型任务 409 互斥 + 全局串行 + OSError 可读化。
8. **C0 微修（PM 终验 E-1~E-4）**：顶栏日期改**本地时区**；口径词「**估值覆盖**」；vsum 未知组「**无可信估算**」；影子盘降级条补「**样本 n 笔**」+ 不足提示。
9. **C1 增量三笔（用户反馈/指令）**：
   ① **四本账本人话记录**：卡片采样与弹窗默认渲染人话摘要，原始 JSON 视图可切换保留（审计不丢）；
   ② **影子盘窗口 60**（契约 v9.5）：`rolling_window_days`/`window_days` 固定 **60**、启动回填满、每日增量「来一天换一天」；口径统一标注「**滚动 60 日 · 回算口径（启动回填）**」，`qualified` 文案「**60 日回算覆盖达成**」（不暗示上线资格）；
   ③ **复盘页筛选排序**：否决层（5）/ 信号（4）/ 基金（模糊匹配）/ P(涨) 三态排序 + 清除；计数提示「已筛选 N / 共 M 条 · **作用于已载入 M 条**」+ 限载说明（纯视图层，不改计算）。
10. **C1 delta-pass · 断连噪声零堆栈（用户反馈）**：客户端刷新/切页/取消导致的 `ConnectionAborted/Reset/BrokenPipe` 在四处全链静默（`_send` / `_serve_static` / `_handle` / `QuietThreadingHTTPServer.handle_error`）并进程内计数；**非断连异常仍照常打栈 + `E_UNKNOWN` 信封**（真错可见）。实测 RST 风暴 48 次：Traceback **36 → 0**。
11. **R3 · F2 自碰撞伪影修复（后端）**：F2 独立性检验原按 `name==factor_id` 排除自身，漏掉别名（crowd6 的 `_builtin=crowd` 与现役 `crowd` 同源）→ 自比对 corr≡1.0 的**假失败**。修法：`_candidate_identity_ids`（factor_id/name/_builtin/同实现键）+ `_incumbent_series`/`_f2_independence` 双侧排除；**真共线仍 fail**（负向用例锁定）。crowd6 记录重评留痕（`correction` 块：1.0/crowd/rejected_f2 → 0.0127/klow2/rejected_f1 + 原因 + 行情刷新漂移说明）。
12. 测试规模：**234 条**（R1 117 + R2 117）；前端断言 `verify_r2_ui_states.py` **152/152**。

## 已知限制（R2 · 如实，务必知悉）

1. **T3/T15 恒「待填充」是设计而非缺陷**（契约 v9.2 §10 裁定）：`gate_only` / `gate+ddsm` 定式未过走前验证（`pending_cv`），接通须各自定式过六关后由架构版本 +1 发布。
2. **首日精度 warming**：`window_filled_days=0`、`window_phase=warming`；`conf_reason=nav_missing`——首判=满 5 个可配对日，终判=40 日。
3. **回测结果为真实值不修饰**：T1 52.63% / 基线 54.15% / Δ −1.52pp（open 61）；基线=实测 `max(恒涨率,恒跌率)`。
4. **C 档 7 只全挂档**（独立触发日 <20）：复查日 2026-10-23；9 只代理复核（R2-04）为 S5 内收口事项。
5. **影子盘**：窗口 60 交易日的记录为**走前回算口径（启动回填）**——`consecutive_days=60`/`qualified`=**记录窗完整度**，**非自然前向积累、不构成上线资格**；`shadow_audit_status` 偏差评估独立（小样本时 `bad` 如实展示）；归档仅在发生裁剪后产生（未裁剪时 `archive_merged=false` 按主文件计算为标注口径）。
6. **QDII 双段**：首测门槛=40 可配对日窗 + `n_test≥20`；当前 5 只 hold（暂态，复评日已预注册）。
7. **LLM「测试连接」= 本地校验**（不联网）；**真探测 R3**。**引擎注册表 = 单版本运行 + 三态预留注**（机制未接入，R3 评估）。
8. **`scan_factors` 未接入**（任务回执如实标注「未接入」）；`last_retrain_at` 无写入点恒 `—`（诚实空格）。
9. **因子盘记录**：crowd6 已完成 F2 伪影更正（含 `correction` 留痕）但重评为 `rejected_f1`（行情刷新后实值）；klow2 记录的行情刷新漂移（61.05→51.2）登记为后续全盘重评候选（未改记录）。
10. **mock 默认关闭**：仅 `?mock=1` 或 `localStorage.zl_mock='1'` 开启；生产路径零假数据（全仓唯一 `fetch` 出口 `js/api.js`）。
11. 不做清单保持：无多用户/云端/实盘交易/自动推送；台账 INSERT-ONLY（无编辑/删除入口）。

## 目录速览

- 后端：`app.py`（HTTP + 55 接口 + `/health`）、`engine.py` / `fund_predict.py` / `valuation.py` / `holdings.py` / `factor_engine.py` / `factor_board.py` / `ledger_api.py` / `review.py` / `estimator.py` / `proxy_map.py` / `risk.py` / `settings.py` / `errors.py`。
- 前端：`static/index.html` + `static/css/app.css` + `static/js/**`（ES module，7 视图；唯一 fetch 出口 `js/api.js`；mock 隔离 `js/mock/`，默认关闭）。
- 测试：`tests/`（标准库 unittest，**234 条**，零联网 mock；套件与产线数据完全隔离）。
- 数据/台账：`data/`（持仓、nav 史、bars 缓存、快照、健康、任务）、`ledger/`（INSERT-ONLY 台账、因子盘 `adopted_factors.json`）。
- 自测（可选）：`python -m unittest discover -s tests -p "test_*.py"` → 期望 `Ran 234 tests ... OK`（已实测无污染）。

## 校验记录

- 构建清单（逐文件 MD5 + 对齐计数）：`docs/04-integration/evidence-r2/build_manifest.json`
- 复验证据：`docs/04-integration/evidence-r2/`（`r3_backend_tests.json`、`r3-f2-tests.log`、`r3-code-records.txt`、`c1b_rst_probe.json`、`c1b-disconnect-tests.log`、`frontend-verify-c1.log`）
