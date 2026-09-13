# README-START · 极境 ZenithLens（OpenCode 独立实现 · S4 集成版 v2）

> 构建标识：`zenithlens-oc / S4 / 2026-09-12`｜引擎版本 `oc-s3-v1`｜产品版本 `0.1.0`
> 关联评审：`docs/04-integration/15-code-review.md`（v2，G-DL-01 = CONCERN，2 条 BLOCK 未关）
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`

## 环境要求（第 0 步 · 先看这个）

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows（本机单用户） | 路径含中文，须用引号包裹 |
| Python | **3.8+**（实测 3.8.6；3.8 以下启动即打印 `E_VERSION` 并退出） | `app.py` 启动时校验 `sys.version_info >= (3,8)` |
| 依赖 | **无第三方依赖**（纯 Python 标准库） | 不需要 pip / npm / 构建步骤 |
| 持仓数据 | `C:\Users\10719\Desktop\基金监控项目\app_data\funds_data.json`（**只读**，不改写） | 不存在也可启动，但持仓/估值页会走错误/空态 |
| 浏览器 | 现代浏览器（原生 ES module） | **必须**经 `http://127.0.0.1` 访问，禁用 `file://` |

## 三步启动

**第 1 步 · 起服**（在代码根执行，保持窗口不关）
```bat
cd /d C:\Users\10719\Documents\ZenithLens-OpenCode
python app.py
```
默认监听 `127.0.0.1:8791`；端口占用时可用 `python app.py --port 8792` 覆盖。
`app.py` 同时托管 `static/**` 与 `/api/v1/**`，**无需另起 `http.server`**。

**第 2 步 · 打开界面**
浏览器访问 **http://127.0.0.1:8791**
> 必须经 `http://127.0.0.1` 访问，**不要**双击 `static/index.html`（`file://` 下 ES module 被浏览器拦截，页面空白）。

**第 3 步 · 冒烟确认**
```bat
curl http://127.0.0.1:8791/api/v1/runtime
curl http://127.0.0.1:8791/api/v1/holdings
```
`/api/v1/runtime` 返回 200 且 `ok=true`、`port=8791`、`engine_status=online` 即起服成功。
后端自测（可选，40 条契约断言）：`python -m unittest discover -s tests -t .` → 期望 `Ran 40 tests ... OK`。

## 已知限制（本轮，务必知悉）

1. **2 条 BLOCK 未关**（`15-code-review.md §4`，未关不进可交付版）：
   - BLOCK-1（前端）：HUD「影子盘」卡状态字恒显示「—」——`engine.js:113` 用 `shadow_progress_status` 表去查 `shadow_status`（`idle/ok/bad`）。
   - BLOCK-2（契约→后端）：设置页「Base URL」不持久化——契约 §5.16 无 `llm.base_url`，后端 GET 不回传、PUT 静默忽略。
2. **数据快照滞后**：实测 `latest_date=2026-08-25`、`days_behind=18`；引擎按真实数据诚实上报，未伪造新鲜度。
3. **因子 / 竞技场 / 影子盘 / 台账为空是正常的**：引擎尚未产出，页面显示空态而非假数据（mock 默认关闭，仅 `?mock=1` 或 `localStorage.zl_mock='1'` 可开，开启后页头出现 `· MOCK` 徽章）。
4. **代理映射未验证**（前端 10 只按 A 档、12 只 QDII/主动记 D 档），待架构师复核后升级。
5. **T+3 / T+15 未验证**（`validation_status=pending_cv`），页面按「观察」灰显示，不表态。
6. **立方体研究口径（naive）默认折叠**且当前有效覆盖为 0（`naive_p` 受 `MIN_N` 门控），仅作审计对照，勿据此判结论。
7. 桌面 exe（pywebview）未打包；多用户 / 云端同步 / 实盘交易**明确不做**（Brief §7）。
8. 仅本地单用户、不联网部署；金额打码、数据不出本机。

## 目录速览
- 后端：`app.py`（HTTP + 53 接口 + `/health`）、`engine.py` / `fund_predict.py` / `valuation.py` / `holdings.py` / `factor_board.py` / `ledger_api.py` / `risk.py` / `settings.py` / `estimator.py` / `errors.py`；`tests/`（40 条契约断言）。
- 前端：`static/index.html` + `static/css/app.css` + `static/js/**`（ES module，7 视图；唯一 `fetch` 出口 `js/api.js`，mock 隔离在 `js/mock/`）。
- 数据/台账：`data/`（持仓、行情缓存、快照、健康、任务）、`ledger/`（INSERT-ONLY 台账），源文件只读。

## 本轮评审所用 skill
`code-review`（双轴：Standards 代码规范 + 冒烟/气味基线；Spec 对齐 PRD/契约/Brief §9）、
`triage`（缺口/偏差定性分流状态机）。
