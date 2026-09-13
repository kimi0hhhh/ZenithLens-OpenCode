---
artifact: 18-test-report
owner: qa
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [dev-lead, product-manager, orchestrator]
gate: G-QA-02
---

# 测试报告 · 极境 ZenithLens（S5 重跑 · 契约 v5 · task OC-R5-QA）

> 上游：`docs/05-qa/17-test-plan.md`（v1）、`PROJECT_BRIEF.md`（§4/§9）、`docs/00-charter/02-prd.md`（v3）、
> `docs/01-architecture/09-api-contract.md`（v5）、`docs/04-integration/15-code-review.md`（v2）。
> 代码根：`C:\Users\10719\Documents\ZenithLens-OpenCode\`。**实起 `python app.py`(8791) + 真实浏览器实测**，非只读报告。
> 证据：`docs/05-qa/evidence/`（接口 JSON×32、逐 Tab 截图×10、`ui_components.json`、`ui_interactions.json`、
> `numeric_checks.json`、`crud_checks.json`、驱动脚本 `scripts/*.py`）。
> **本轮 skill**：`test-scenarios`（推场景）、`diagnosing-bugs`（缺陷根因）。

## 摘要

1. **执行 113 条 P0 用例 + 11 条专项**：**通过 112 / 113，失败 1（R-UI-26）**；后端数值口径 **24/24**、CRUD **16/16**、40 组件 **39/40**。
2. **G-QA-02 判定 = FAIL**（P0 未 100% 通过）：**D-01（P0·口径错误）**——立方体对比卡「有效覆盖」少乘 100（0.92 显示成 0.9%），属 Brief §4「展示数字与后端不一致」失败定义，整轮退回。
3. 另登记 **D-02（P1）** 研究口径 naive 缺「低样本·仅供审计」角标（契约 §5.25 明令）、**D-03/D-04（P2）** 契约版本标注停留 v4、分析页跨接口拼装残留。全部见 `04-defects.md`。
4. **红线未触发**：无前端假数据（mock 默认关闭、生产 fetch 唯一出口、104 次真实 `/api/v1/*` 调用）；未知≠持平成立；隐私打码、四态、推导链、五档 trace、无开口不表态均通过。
5. **BLOCK-1 复核关闭**：HUD 影子盘状态显示「未启动」（`idle` 映射已修）；**BLOCK-2 复核关闭**：`llm.base_url` GET/PUT 往返持久化（实测+契约测试）。
6. 方法偏差登记：`agent-browser` daemon 握手失败（`Chrome exited early exit 3`），按派发约束改 **CDP 直连 Chrome for Testing**（自建 stdlib WebSocket 客户端），已如实记录。

## 正文

### 1. 执行总览（通过率统计）

| 维度 | 用例数 | 通过 | 失败 | 通过率 |
|---|---|---|---|---|
| 数值口径 N-01..N-24 | 24 | 24 | 0 | 100% |
| P0 功能 F-01..F-11（正常/边界/异常） | 33 | 33 | 0 | 100% |
| R-UI-01..40 组件 | 40 | 39 | 1 | 97.5% |
| 交互 / CRUD C-01..C-16 | 16 | 16 | 0 | 100% |
| 专项 X-01..X-11 | 11 | 11 | 0 | 100% |
| **合计** | **124** | **123** | **1** | **99.2%** |

- **P0 用例**（N + F + R-UI + C）= 113，通过 112，未通过 1 → **P0 通过率 99.1% ≠ 100%**。
- **G-QA-02 判定 = FAIL**（红线：存在 P0 未通过 → 整轮退回，`gate-rules.md` G-QA-02）。

### 2. 环境与实测方法（如实登记）

| 项 | 实测值 |
|---|---|
| 应用 | `python app.py`，端口 **8791**（`app.py:38`），Python **3.8.6**，纯标准库 |
| 路由 | `app.ROUTES` 长度 **54**（53 契约接口 + `/health`），独立复核 `tests` 通过 |
| 浏览器 | Chrome for Testing `...\ms-playwright\chromium-1243\chrome-win64\chrome.exe`（`--headless=new --remote-debugging-port=9222`，视口 1720×2600） |
| 驱动 | `agent-browser.cmd` **握手失败**（`Auto-launch failed: Chrome exited early (exit code: 3) without writing DevToolsActivePort`）→ 改 **CDP 直连**（`evidence/scripts/cdp.py` 自建 stdlib WebSocket） |
| 复现命令 | `python app.py` → `python docs/05-qa/evidence/scripts/run_ui_checks.py` / `run_ui_interactions.py` / `numeric_checks.py` / `crud_checks.py` |
| 数据 | 真实持仓 22 只；CRUD 用临时代码 `999998`，测后删除并核对还原 |

### 3. 数值口径执行结果（N-01..N-24 · 全过）

断言脚本 `evidence/scripts/numeric_checks.py`，输出 `evidence/numeric_checks.json`：**SUMMARY 24/24**。

关键实值：`total_value=53092.77 == Σmarket_value`；`return_rate=0.122`（手算 0.121969，成本 47321.07）；
`weighted_mae_rate=0.002→0.20%` / 行业 `0.008→0.80%`；`effect_pp E3=3.9→+3.90pp`（非 390pp）；
冻结 `N_w=[5,10,15,30,60,120]`、窗权重 `[8,22,15,10,30,15]`、`K=4/p=0.25/MIN_N=15/SHRINK=10/BAND=0.02`；
无开口 `weighted_p=null/direction=gray`、`min_coverage_ratio=0.30/min_open_count=3`；
立方体 125=5×25、`naive_n>0` 即给 `naive_p`（115/115，其中 115 格 n<15）、`naive_n=0` 格 P=null；
`p_up∈[0.3460,0.7381]`；出口阈值 0.52。

**唯一被本组标记的风险值：N-20** `valid_coverage_naive_pct=0.92` 为 **ratio**，UI 实显 `0.9%`（应为 92%）→ 建 D-01。

### 4. R-UI-01..40 组件逐项结果（39/40）

> 采集：`evidence/scripts/run_ui_checks.py`（7 Tab 遍历）→ `evidence/ui_components.json` + `shot_<tab>.png`；
> 交互：`run_ui_interactions.py` → `evidence/ui_interactions.json`。

| 用例ID | 组件 | 实际（实测摘要） | 结果 | 证据 |
|---|---|---|---|---|
| R-UI-01 | 资产总览四卡 | 总资产 ¥53,092.77 / 今日 ¥-290.25 / 累计 ¥5,771.70 / 收益率 +12.20%，口径副标题可见 | PASS | `ui_components.json:holdings.pa_*` |
| R-UI-02 | 估值精度 `.vsum` | 高 10 只占 48.1% + 未知(短标签「无」) 12 只占 51.9%；加权 MAE 0.20% / 行业 0.80% | PASS | `vsum_text` |
| R-UI-03 | 估值徽章 `.vb` 五档+`.ch/.cm/.cl/.cu` | 22 徽章（ch×10 / cu×12）；title 含五档降级链 trace + MAE + 命中率 + 样本 | PASS | `valbadges=22`，`ep_holdings.json` |
| R-UI-04 | 覆盖度 `.covbar`+失效三类 | A 10/¥25,531.90、B 0、C 0、D 12/¥27,560.87；失效三类长文 116 字 | PASS | `cov_tiers=4` |
| R-UI-05 | 持仓明细表 | 26 行（22 持仓+4 分组）；`.vb` 22；未知格 24；**`+0.00%` 计数 0** | PASS | `rows=26`、`plus_zero_zero=0` |
| R-UI-06 | 风险指标折叠区 | `#fold-risk` 存在，展开才请求 | PASS | DOM |
| R-UI-07 | 信号空态四要素 | 监控中 10/22、距上次开口 —、上次开口 —、上次结果 待填充 | PASS | `signals.empty_text` |
| R-UI-08 | 触发门 E1/E3 + E2/E4 剔除 | E3 `+3.90pp`、E1 `+0.88pp`；E2 `-3.09pp`、E4 `-2.72pp`；禁 OR 合并 | PASS | `signals.gates_text` |
| R-UI-09 | 信号时间线 `.tl` | 空数据显占位（近 60 天无信号），无伪造 | PASS | `tl_items=0` |
| R-UI-10 | T+1 口径+三执行路径 | 279 字长文（A/B/C 路径，B 可执行） | PASS | `analyze.defs_len=279` |
| R-UI-11 | 三窗口组合卡+加权口径 | 3 卡；`weighting_basis=market_value` + 策略说明 | PASS | `forecast_cards=3` |
| R-UI-12 | 参与预测持仓表 | 10 行（档/触发/P/否决/三窗口/市值） | PASS | `body_rows=10` |
| R-UI-13 | 推导链 `.chain/.chain-item` 六步 | 弹窗 6×`.chain-item`，逐步带指标（触发门→DDSM→拥挤度→KLOW2→出口→入账） | PASS | `ui_interactions.chain.items=6`、`shot_chain.png` |
| R-UI-14 | 因子四盘+跑分表 | 4 盘 rule 长文（正式/淘汰影子/有效影子/冷冻），空盘诚实 | PASS | `factors.pans_children=4` |
| R-UI-15 | 四本账本 | 4 账本（用途+字段+写入说明） | PASS | `books=4` |
| R-UI-16 | 评分链长文 | k_lift 悬崖 + bootstrap 500 + 四裁判 | PASS | `score_len=556` |
| R-UI-17 | 治理周期卡 | 6 卡 | PASS | `cycle=6` |
| R-UI-18 | 最近挖掘记录 F1/F2/F3 | 表头齐，空集 | PASS | `scan_rows=1` |
| R-UI-19 | 生命周期规则长文 | 693 字（准入/牌照/淘汰/双出口/防误杀/冷冻） | PASS | `life_len=693` |
| R-UI-20 | HUD 六卡 | 6 卡；影子盘「未启动」（**BLOCK-1 已修**） | PASS | `hud=6` |
| R-UI-21 | 影子盘台账+进度 | 表+0/60 进度+字段说明；空台账 `not_started` | PASS | `prg_width=0%` |
| R-UI-22 | 因子竞技场矩阵 | 表头 7 列（配置+六窗）+6 legend；空集诚实 | PASS | `arena_head=7` |
| R-UI-23 | 训练状态卡 | 125 格/有样本/平均样本 21.2/加噪说明/5 条死路 | PASS | `train_len=267` |
| R-UI-24 | 冻结参数表 | 15 组参数只读 | PASS | `frozen_rows=15` |
| R-UI-25 | 六维输入 z-bar | DDSM 3 bar + 拥挤度 6 bar；资产下拉 10 项 | PASS | `d3_bars=3,d6_bars=6` |
| **R-UI-26** | **125 格立方体 naive/DDSM** | 生产 ddsm 默认/研究 naive 折叠/vr 5 层/图例/悬停均正常；**但对比卡「有效覆盖」=0.9%→1.0%（应 92%→100%）【D-01】；研究层缺「低样本」角标【D-02】** | **FAIL** | `cmp_text`、`low_sample_marks=0` |
| R-UI-27 | 引擎注册表三态 | active 版本 oc-s3-v1；设置页复用 | PASS | `registry_rows=1` |
| R-UI-28 | 历史成绩 hero | 「回测待产出（不填估计值）」 | PASS | `hero_text` |
| R-UI-29 | 三窗口 vs 基线 | 3 行，`baseline_status=pending` 留空 | PASS | `scores_rows=3` |
| R-UI-30 | 影子盘降级审查条 | `degrade idle` 三态样式 | PASS | `degrade_class` |
| R-UI-31 | 逐笔对账表 | 表头齐，空集 | PASS | `recon_rows=1` |
| R-UI-32 | 隐私开关 | 打码后金额 `••••`（101 处 `.amt`），涨跌/占比/收益率保留 | PASS | `ui_interactions.privacy_on`、`shot_privacy.png` |
| R-UI-33 | LLM 接口+三硬约束+温度0 | 服务商/Base/模型/Key 全在；Base 往返持久化（**BLOCK-2 已修**） | PASS | `base_url_input=true`，C-11 |
| R-UI-34 | 数据源健康表 | 4 源：腾讯K ok、腾讯实时 ok、天天基金 bad(失败315)、新浪 unchecked | PASS | `src_rows=4` |
| R-UI-35 | 持仓数据卡+不一致长文 | 源路径/只数/一致性 + 偏差 ~0.73% 实证 | PASS | `hd_diff_text` |
| R-UI-36 | 关于卡 | 版本/引擎/存储/审计/免责 | PASS | `about_text` |
| R-UI-37 | 三 dialog+popover+toast | 3 dialog + popover + toast；CRUD 实测通过 | PASS | `dialogs=3`，C-01..C-10 |
| R-UI-38 | 注销 Service Worker | `main.js:18-23` try/catch | PASS | 源码 |
| R-UI-39 | livebar 真实数据接入条 | 「已接入本地引擎 · 持仓/预测真实数据 · 快照 2026-09-12」+源不通提示 | PASS | `shot_home.png` |
| R-UI-40 | 四态覆盖各页 | empty/loading/error/success 四态可切且文案各异 | PASS | `ui_interactions.states`、`shot_state_*.png` |

### 5. P0 功能点执行结果（F-01..F-11 · 全过）

| 功能 | 正常 | 边界 | 异常 | 口径 | 结果 |
|---|---|---|---|---|---|
| F-01 资产总览 | 四卡真实值 | 空集→空态（演示）、成本0→— | 接口失败→错误态+重试 | N-01/N-02 | PASS |
| F-02 估值五档 | 五档枚举由 mode 驱动 | 仅 proxy/unknown 不补假档 | 三源失败→unknown | trace 语义一致 | PASS |
| F-03 徽章+降级链 | `.vb` title 含 trace/MAE/命中/样本 | trace 缺失退化未知 | nav_date 缺失显 — | `.ch/.cm/.cl/.cu` 由后端 | PASS |
| F-04 未知态 | null→未知/— | 0→`+0.00%` 区分 | 全未知无冒充 | `+0.00%` 计数 0 | PASS |
| F-05 覆盖度 A/B/C/D | 四档只数/市值/占比 | B/C=0 显 0 | 档未知→D | 占比和≈1 | PASS |
| F-06 单只方向预测 | `p_up∈[0,1]` 字段齐 | `gate=none` 仍算不开口 | 缺失→abstain(A-05) | E1/E3 公式、P>0.52 | PASS |
| F-07 信号链路 6 步 | 弹窗 6 步 | 某步 missing 标注 | 无链路提示 | 每步带指标 | PASS |
| F-08 组合加权预测 | 三窗口+口径长文 | 无开口→gray/覆盖0 | 离线走 stale/error | 门槛 30%/3、market_value | PASS |
| F-09 台账 INSERT-ONLY | 行+进度+字段 | 空台账 not_started | 无 PUT/DELETE(404) | backfill 仅回填 real | PASS |
| F-10 回测 vs 基线 | hero+三窗口表 | 待填充留空 | 无成绩空态 | baseline=max(恒涨,恒跌) | PASS |
| F-11 数据/可靠性 | livebar+源健康 | 源 bad 提示 | 离线/滞后如实 | 快照日期一致 | PASS |

### 6. 交互 / CRUD 执行结果（C-01..C-16 · 全过）

`evidence/scripts/crud_checks.py` → `evidence/crud_checks.json`：**SUMMARY 16/16**。
建档 201→23 只；重复 409；非法代码 400；更新/回读一致；不存在 404；删除→**还原 22 只、总额 53092.77 不变**；
`llm.base_url` PUT→GET 往返持久化、非法值 400、已还原；`/ledger/entries` 无 PUT/DELETE（404）。

### 7. 关键专项验证（X-01..X-11）

| 用例ID | 专项 | 实测 | 结果 |
|---|---|---|---|
| X-01..04 | 四态（空/加载/错误/成功） | `state-block empty/loading/error` + 成功态清空；文案各异、重试按钮在 | PASS |
| X-05 | 隐私打码 | `body.masked`，101 处 `.amt` 打码；`+12.20%`、占比保留；刷新持久化 | PASS |
| X-06 | 推导链 | 6×`.chain-item`，含 on/off 态与指标 | PASS |
| X-07 | 无假数据 | `?mock` 未开、`localStorage.zl_mock=null`、mock 脚本 0、104 次真实 API | PASS |
| X-08 | 立方体 vr 层切换 | 切 vr4 后切片/统计更新，无样本格斜纹 | PASS |
| X-09 | 竞技场空集 | 「当前无开口配置」+ legend，无伪造行 | PASS |
| X-10 | BLOCK-1 复核 | HUD 影子盘显示「未启动」（idle 映射已修） | PASS |
| X-11 | 空态接线复核 | `holdings/analyze/factors/review/signals` 均已传 `emptyWhen` 回调 | PASS |

### 8. 缺陷汇总（详见 `04-defects.md`）

| 编号 | 严重度 | 摘要 | 定性/分流 |
|---|---|---|---|
| D-01 | **P0** | 立方体对比卡「有效覆盖」少乘 100（0.9% vs 92%） | 前端（`engine.js:348`） |
| D-02 | P1 | 研究口径 naive 缺「低样本·仅供审计」角标（契约 §5.25） | 前端（`components.js:233`） |
| D-03 | P2 | 契约版本标注停留 v4（实际 v5） | 前端展示 |
| D-04 | P2 | 分析页跨接口拼 `tier/market_value`（SHOULD-4 残留，数值一致） | 前端 |

**门禁判定：G-QA-02 = FAIL**。理由：存在 P0 未通过（D-01），按红线整轮退回；修复后 qa 回归 N-20、`low_sample_marks`、`0.9%` 消失。

## 自验收

- [x] P0 功能每个 ≥3 条用例（正常/边界/异常）已执行并记录实际（§5）
- [x] 含口径正确性用例（§3，24 条，实算复现）
- [x] 每条用例的「实际」已写实（含与期望一致的也写明），非只打勾
- [x] 所有失败用例附证据（接口原文/截图/断言 JSON，§4 R-UI-26 与 04-defects）
- [x] 缺陷严重度按定义判定，数据错误一律 P0（D-01）
- [x] 缺陷单六项必填齐全（见 `04-defects.md`）
- [x] 报告含通过率统计（§1）与未关闭缺陷清单（§8）
- [x] 使用并回传 skill：`test-scenarios`、`diagnosing-bugs`
- [x] 未修改产品代码 / 契约 / `runtime/**`；未派发子任务
- [x] 真浏览器优先；`agent-browser` 失败改 CDP 已如实登记（§2）

## 下游交接

- **主消费方 `dev-lead`**：按 `04-defects.md` 分流（D-01/D-02/D-04 → frontend-dev；D-03 前端）；修复后安排 qa 回归：`numeric_checks.py` N-20、`ui_interactions.json` `low_sample_marks`、对比卡不再出现 `0.9%`。
- **次消费方 `product-manager`**：`17-test-plan.md` §3/§5 可作 G-PM-05 终验走查清单；注意 R-UI-26 未闭合。
- **残留风险**：
  1. D-01 同类 `num(ratio)+'%'` 模式可能另有他处，建议前端全仓自查（责任人 frontend-dev）。
  2. 数据快照滞后（`latest_date=2026-08-25`，18 自然日）影响官方净值回填，属数据管线新鲜度（责任人 backend-dev），非本轮算错。
  3. 桌面 exe 打包、性能压测、多用户（Brief §7 不做）未覆盖。
- **未覆盖**：真实空数据集下 `emptyWhen` 的端到端触发（当前数据非空，仅演示条覆盖）；SPA 长时间运行的性能。
