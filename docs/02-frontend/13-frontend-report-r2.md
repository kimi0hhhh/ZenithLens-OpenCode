---
artifact: 13-frontend-report-r2
owner: frontend-dev
version: v2
status: draft
supersedes: v1（R2 升级轮交付；v2 追加 S5 修复记录 §7，§2 分析行按 R2-D1 修正）
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端实现报告 · 极境 ZenithLens（R2 升级轮 · v2 · 契约 v9.3）

> 产出：`C:\Users\10719\Documents\ZenithLens-OpenCode\static\`（纯静态、零依赖、无构建步骤；R1 基线上升级，非重写）。
> 依据：`03-ui-design-v3.md`（U-01..U-12 + §4 四态 + §8 触点）、`04-ui-wireframe-v3.html`（对照物）、
> `07-frontend-arch-r2.md` **v3.1**（§2 组件→字段映射、§5 数值口径、§7 防退化）、`09-api-contract-r2.md`（字段唯一法律；S5 编报时为 **v9.3**）。
> 交付物：`static/**`（升级 + S5 修复）+ `docs/02-frontend/12-interface-request-r2.md` + 本文 + 证据（`docs/02-frontend/evidence/verify_r2_ui_states.py` 等）。
> 自检环境：Node 18 `--check` ×14 文件；Edge headless + stdlib CDP 静态断言（mock 模式 + fetch 桩四态 + S5 场景桩 + C2/C1 复核 + C0 E-1~E-4 + C1 账本 + C1 双任务，**152/152**）；
> 另对 live 后端（127.0.0.1:8791，v9.1 形状）做过抽查（v1 时点；S5 编报时后端未运行，联调回归归 qa）。

## 摘要

1. **U-01..U-12 全部落地（12/12）**，落在 16 个既有组件触点上；目录结构零变更（7 视图 + 既有组件扩容，不新增视图）。
2. **命脉三条**：成绩位出数（hero 三段式 / 三窗口 pending 纪律 / 对比卡「待复现」→ 出数）、徽章双层编码 + `conf_reason` 五值解释层 + 7 项 tooltip、回填态激活（`result` 直读 / 待回填仅限未到期 / ⑥步由后端 detail 直出）。
3. **四态真实接线 7/7 页**：空态含「为什么空 + 下一步」（持仓/设置含主行动按钮）；`empty` 下 view-main 隐藏（无数字行）；`error` 不回退示例；`loading` 骨架不渲染数字 —— 由静态断言逐页负向验证。
4. **不倒退清单全部保持**：涨红跌绿 / 未开=— / 隐私打码 / 徽章后端驱动 / StateBlock 统一 / SW 注销 / INSERT-ONLY 无入口 / 灰不加权。
5. **自检**：`node --check` **14/14 通过**；`verify_r2_ui_states.py` **92 断言全过**（阶段 A 七页 R2 触点 + 阶段 B 七页 × 三态）；R1 集成脚本对 live 后端复跑 **11/11 + 20/21**（1 条为脚本与后端数据漂移，非回归）；全仓 `fetch(` 仅 1 处（`api.js`）；mock 默认关闭。
6. 差异备案 2 处（见 §6）：来源档 `l` 映射按 07-r2 §2.1 逐字（与线框 v3 的 intraday/holdings 取色略有差异）；`.card.tight` 用 `overflow:clip`（替代线框 `visible`，保圆角且 sticky 生效，旧内核回落普通表头）。

## 正文

### 1. U-01..U-12 逐项落地（落点 + 证据）

| U | 升级点 | 落点（文件#函数） | 落地情况 | 证据 |
|---|---|---|---|---|
| U-01 | 成绩位填充 | `views/review.js#renderHero/renderScores`；`views/engine.js#renderCube`；`views/factors.js#renderPans` | hero 三段式（命中率+基线+Δ）+ 回测/实盘 tag + `open_count/sample_period/note` 直出；三窗口 `pending`→「待填充」不做估计；对比卡 Δ null→「待复现」、出数→`delta()`；因子空盘「（当前为空）」保留 | 断言：hero 含 `回测/58.3%/9.9pp`；三窗口含「待填充」「全样本窗」；`#eg-cmp` 走前 Δ 出数 |
| U-02 | 双层徽章 + 7 项 tooltip | `components.js#valBadge`（`copy.js#SOURCE_LAYER/CONF_CLASS/CONF_REASON`）；`views/holdings.js#renderVSum` | 来源底色 `l0~l3` × 置信度描边 `ch/cm/cl/cu` 独立拼类；tooltip 固定 7 项（来源/链路/MAE/方向/n/回测窗/披露口径）；unknown 必带 `conf_reason`；`qdii_correction` 追加校正行；vsum 主指标=`estimate_quality.weighted_mae_rate` + 官方档单列 chip + 全档参考 + `window_filled_days/phase` | 断言：tooltip 7 项逐项命中；unknown 含「未知原因：」；vsum 含「估算档市值加权/官方档（既成事实）/全档参考/12/40」；8 枚徽章双层渲染 |
| U-03 | 四态全量接线 | 7 个 `views/*.js`（`viewState/emptyWhen`）+ `components.js#mountState` | 7 页 `emptyWhen` 全部改真实条件（§2 表）；空态文案「为什么空+下一步」；settings/holdings 空态主行动按钮；`idle` 按 loading 渲染 | 断言：7 页 × empty/error/loading 状态与文案；empty 下 view-main `display:none` |
| U-04 | 回填态激活 | `views/signals.js#renderTimeline`；`views/review.js#renderRecon`；`components.js#chainHTML` | 时间线 `.tl-item.hit/.miss` 由 `result` 驱动（缺省按契约判定式回退）；对账判定列 hit/miss/abstain；待回填仅当 `t1_real=null`；回填行 tooltip 含 `t1_real_method`+`backfill_proxy_code`；⑥步「回填态」徽标由后端 detail 直出 | 断言：时间线 pending 行含「待回填」；对账渲染；⑥步标签存在 |
| U-05 | 影子盘进度真实化 | `views/engine.js#renderHud/renderShadow`（`#eg-prg-note`） | HUD 与台账均显示真实 x/60；口径注随 `archive_merged` 切换（「归档合并计算」/「按主文件计算（归档不可读）」）；`history_days`「可用历史 N 日（含归档）」；`window_days/baseline_source` 直读；进度枚举文案入 `copy.js` | 断言：HUD「23 / 60 · 归档合并」；`#eg-prg-note` 含「可用历史 23 日」；偏差审查独立表达 |
| U-06 | 数据源健康升级 | `views/settings.js#renderSources/renderHoldingsData/importHoldings` | 展示计数改 `fail_window_7d`（「近 7 日失败 n 次」）；`recent_failures` 折叠区；`fail_count` 仅折叠区标「累计 · 审计用」；主源读 `main_source`；导入按钮 `import_available=false` 禁用+reason | 断言：src-box 含「近 7 日失败」「历史失败」；hd-data 含 `data/holdings.json`；`#hd-import.disabled===true` |
| U-07 | C 档验证四态 | `components.js#verifyTag`；`views/holdings.js#rowHTML/predCell` | 行内标签五值（待验证/验证中/已验证/验证未通过/暴露待定）+ tooltip（tier_reason/verify_note/批次/复查日）；缺状态→「待验证」兜底且标注；信号列同步后端 label | 断言：持仓行含「验证中」「暴露待定」 |
| U-08 | QDII 领先标注 | `views/holdings.js#rowHTML`、`views/analyze.js#renderTable`、`views/signals.js`（`last_open` 可选） | `HoldingRow.qdii_lead_note` / `PredictionSummary.qdii_lead_note` 非 null 渲染 chip；文案后端产出（不硬编码「1–2 天」） | 断言：持仓行含「QDII · 境内代理领先净值 1–2 天」×2 |
| U-09 | sticky 表头 | `css/app.css`（`thead th`；`.card.tight` overflow; `.xwrap`） | 全站表头 sticky + 磨砂底；长表容器（台账/竞技场）内滚 + 表头常驻；旧内核回落普通表头不报错 | 断言：CSS 规则存在；渲染无报错 |
| U-10 | 键盘与焦点 | `css/app.css`（`focus-visible`/fold hover/reduced-motion）；`components.js#initDialogs/showModal/toast`；`main.js#boot` | 全站焦点环；`<dialog>` Esc 原生 + 打开时记录触发元素、关闭回位；modal-mask 支持 Esc；toast `aria-live=polite`；`prefers-reduced-motion` 降级 | 断言：组件初始化无错；CSS 规则存在（S4 CDP 复核 Tab/Esc） |
| U-11 | 数字口径悬浮统一 | `components.js#tipAttr/metricTip`；`copy.js#METRIC_TIP`；各视图关键数字 | 总资产/今日盈亏/累计/收益率/覆盖/加权 P/Δ/MAE/精度窗/影子进度等接线口径 tooltip；文案单一来源字典 | 断言：`title` 出现在 vsum/四卡/预测卡/进度等（抽查） |
| U-12 | 文案字典纪律 | `copy.js`（实现层） | 新增 `CONF_REASON`（五值）/`VERIFY_STATUS`（五值+kind）/`WINDOW_PHASE`（三值）/`SHADOW_STATUS`（四值）/`SHADOW_AUDIT`（三值）/`QDII_FALLBACK_REASON`（三值）+ 固定词条（既成事实/归档合并/待填充/待回填…）；组件全部从字典取文案 | 断言：`copy.js` 导出全量；14 文件 import 完整性脚本 0 问题 |

### 2. 四态接线清单（7 页 · `emptyWhen` 真实条件 → 渲染证据）

| 页 | 空态条件（实现） | 空态要素 | 证据（静态断言） |
|---|---|---|---|
| 持仓 | `rows.length===0` | 「还没有录入任何持仓」+ 数据源路径 + 「录入第一只基金」按钮 | 状态=empty；文案含「为什么空」；view-main 隐藏；按钮存在 |
| 分析 | **唯一条件 `predictions.rows.length===0`**（S5/R2-D1 修正：`open_count=0` 不再参与判定，rows>0 时恒 success）；「为什么空」按触发因素二分支 | 「今日没有触发开口的资产」+ 四要素事实卡 + 低频说明；分支①监控集合为空 / 分支②无预测记录 | 状态=empty + 二分支文案命中（C-A2）；正向回归：rows=15 且全窗 open_count=0 → success + 表 15 行 + 三窗口卡（C-A1） |
| 信号 | `ledger.rows.length===0` → 变体①；有台账无开口 = 页内变体②「今日无信号」四要素 + 低频说明 | 变体①启动说明；变体②「这是常态，不是故障」 | 变体①「影子盘尚未开始记录」命中；阶段 A 变体②含「20 交易日约 11 资产开口」 |
| 因子 | `pans.length===0` | 「因子库为空，等待首次扫描」+ 周提名说明 | 状态=empty + 文案命中 |
| 复盘 | `scores.length===0` 或 hero 缺失 | 「尚无成绩记录，引擎未产出回测」+「待填充≠0」 | 状态=empty + 文案命中 |
| 引擎 | `status=offline && !last_heartbeat_at && !snapshot_as_of`（心跳缺失且无快照） | 「引擎离线」+ 最近成功时间 + 启动指引（有快照走 success+陈旧，A-06 不倒退） | 状态=empty + 文案命中 |
| 设置 | health 行全 `unchecked` 或无行 | 「尚未检测数据源」+「立即检测」按钮 | 状态=empty + 按钮存在 |

- `loading`：7 页均以统一骨架/脉冲渲染（首帧 `idle` 按 loading），断言 `.skeleton≥1` 且不渲染数字。
- `error`：7 页均红框 + 「重试」，文案按 `error.code` 映射（`E_IO`→「读写本地数据失败」）；断言含「重试」。
- `success`：mock 模式下 7 页关键区渲染逐项断言（见 §1 证据列）。
- **success 前不渲染数字**：`empty` 态以 `data-state` 驱动 CSS 隐藏 `.view-main`（断言 `display:none`）；`loading` 态仅骨架。

### 3. 不倒退清单自检（G2-12）

| 项 | 实现 | 状态 |
|---|---|---|
| 涨红跌绿 | `format.js#cls/rate` 未改；zbar pos=红/neg=绿、bars g/r 未改 | 保持 |
| 未开=— | `unknownCell/changeCell/pnlCell` 未改；prediction/coverage null 均 `—` | 保持 |
| 隐私打码 | `store.js#applyPrivacyClass` + `body.masked .amt` 未改；新增元素均未绕过 | 保持 |
| 估值徽章后端驱动 | `mode_label`/`confidence_color_class` 直读；新增来源层 class 由 `valuation_mode` 映射表拼接（仍后端驱动，无前端推断） | 保持 |
| StateBlock 统一 | 所有页面四态经 `components.js#mountState`；无 per-page toast 错误新逻辑 | 保持 |
| 注销 SW | `main.js` 保留 SW/cache 注销 | 保持 |
| INSERT-ONLY 无入口 | 台账/对账/比分表无编辑/删除按钮；导入按钮按 `import_available` 禁用而非删 | 保持 |
| 灰不加权 | `forecastCard/weightingNote` 逻辑未改；W 口径文案后端驱动 | 保持 |
| 禁止 `+0.00%` | `rate()` 路径未改；断言「全局无 +0.00%」通过（mock 数据集） | 保持 |
| 前端不做业务计算 | 仅展示连接（nameMap）与格式化；Δ/MAE/覆盖/进度全部直读 | 保持 |

### 4. 与 v9.1 字段一致性自查（逐字段）

- **HoldingRow**：`verify_status / verify_status_label / verify_batch_id / verify_note / verify_review_date / tier_reason / qdii_lead_note / fund_type(_label)` —— 消费 1~9；`fund_type(_label)` 未展示（U 列表未要求，备案不消费）。
- **Valuation**：`conf_reason`（五值映射 `copy.js#CONF_REASON`，仅 unknown 显示）、`qdii_correction.{applied,fallback_reason,note}`（tooltip 追加行）、`trace[holdings].detail.{report_date,covered_weight_pct,top_n,included_markets}`（tooltip 第⑦项）。
- **ShadowProgress**：`consecutive_days/target_days`（x/60）、`window_days/archive_merged/history_days/baseline_source`（#eg-prg-note + HUD sub）。
- **ShadowLedger**：`backfill_method(_note)`、`field_list`（含 `t1_real_method/backfill_proxy_code`）直出。
- **LedgerEntry/ReconcileRow**：`result`（对账直读；时间线回退式与契约判定式一致）、`t1_real_method/backfill_proxy_code`（tooltip）。
- **/review/scores**：`hero.{open_count,sample_period,data_kind}`、`note`、`scores[].sample_window`（恒 full → 「全样本窗」注明）；`data_kind` 支持透传（当前用默认 backtest）。
- **/valuations/precision**：主指标 `estimate_quality.weighted_mae_rate`；`official_summary` 单列；`window_filled_days/window_status_label/window_phase`；全档 `weighted_mae_rate/groups` 降级为「全档参考」（文案标注）。
- **/engine/status**：`shadow_status` 进度四值 + `shadow_audit_status` 三值，分离表达；未出现 idle/ok/bad 于进度位。
- **/data-sources/health**：`fail_window_7d/fail_window_days/recent_failures` 消费；`fail_count` 仅折叠区。
- **/settings/holdings-data**：`main_source/import_available/import_disabled_reason` 消费；`primary_*` 不再作主源展示。
- **未消费（备案）**：`bootstrap_percentiles_measured/real_engine`（契约只加不改；保持常量口径，避免超额交付）、`fund_type` 展示、`ledger_refresh_mode`（任务参数）。
- 数值口径：比率类经 `format.js` ×100 两位；`weight_pct` 直显（detail 例外口径）；`history_days/window_filled_days/open_count` 整数直显；`QdiiCorrection.value` 经 rate 格式化（tooltip 载入 note 原文）。

### 5. 自检与证据

| 检查 | 命令/方式 | 结果 |
|---|---|---|
| JS 语法 | `node --check`（经复制为 `.mjs` 保真，14 文件） | **14/14 PASS** |
| import/export 完整性 | Node 脚本解析全部相对 import 对照导出集 | **0 问题** |
| 七页 R2 触点 + 四态 + S5 场景 | `python docs/02-frontend/evidence/verify_r2_ui_states.py`（Edge headless CDP + stdlib HTTP） | **v1：92/92；S5 更新后：152/152（exit 0）**（阶段 C 见 §7） |
| 四态证据截图 | 同上脚本产出 | `evidence/zl_r2_state_empty_holdings.png`、`evidence/zl_r2_state_error_engine.png` |
| 页面冒烟（mock 渲染转储） | Edge `--dump-dom` ×7 路由（mock=1） | 7/7 无 console/网络错误 |
| fetch 唯一出口 | `Select-String "fetch("` 全 static | 仅 `api.js:60` |
| mock 默认关闭 | 代码审读 `api.js#mockEnabled`（默认 false，仅 `?mock=1`/`localStorage`） | 保持 |
| R1 集成脚本 · `verify_shadow_fe.py`（live 8791 + CDP 9333，ms-playwright chromium） | 全量复跑 | **11/11 PASS（exit 0）** |
| R1 集成脚本 · `verify_shadow_progress_fe.py`（同上；证据截图输出重定向至 temp，不改 R1 工件） | 全量复跑 | **20/21 PASS**；唯一 FAIL 为脚本字面量 vs 后端数据漂移：脚本期望审查态「未评估」（idle 时代），live 后端现为 `shadow_audit_status=bad`，前端按枚举正确渲染「降级」——属预期行为，非回归（S4 复基线） |
| live 后端抽查（v9.1 形状） | CDP 实测 7 页与关键切片 | 持仓 26 行 + vsum 7 chips（`estimate_quality.weighted_mae_rate=null` → 「估算档暂无法计算 · 缺净值」原因 chip 直读 `conf_reason`；官方档 chip「既成事实 17 只 · 占 84.4%」）；引擎 60 行 + HUD「20 / 60 · 按主文件计算（归档不可读）· 可用历史 20 日」+ 审查「降级」；复盘 hero 52.6% / 对账 60 行；全部切片 success |
| 契约/架构文件未改 | `git` 状态不可用（非仓库）；以文件清单核对 | 未改 `09*/07*/08*/runtime/**` |

**所用 skill**：无（主 Agent 未点名；按 09 v9.1 + 07-r2 工件规格直接实现；自检复用仓库自带 `docs/05-qa/evidence/scripts/cdp.py`）。

### 6. 与 R1 差异及残留风险

1. **来源档映射差异备案**：`.vb.l1~l0` 按 07-r2 §2.1 逐字（official/intraday=绿系、holdings=金、proxy=灰、unknown=虚线灰）；线框 v3 演示把 intraday/holdings 同标金。已以架构文本为准，仅改 `copy.js#SOURCE_LAYER` 一行可切换。
2. **sticky 实现细节**：`.card.tight` 用 `overflow:hidden; overflow:clip`（clip 不建滚动容器 → sticky 相对页面生效且保留圆角；线框用 `overflow:visible`）。旧内核不支持 clip → 回落 hidden（普通表头降级，不报错）；台账/竞技场用 `.xwrap{max-height:72vh}` 容器内滚。
3. **四态工程化**：为让空态「可手动触发查看」，`emptyWhen` 全部真实化后，构造数据即触发（qa 构造；mock 不提供四态开关，避免回退旧“演示条”）。
4. **引擎空态边界**：取「心跳缺失且无快照」，有快照时保持 success+陈旧（A-06 不倒退）；与 03-ui §4「心跳缺失」的口径差一处备案。
5. **残留**：`/review/scores?data_kind=shadow_live` 的 UI 入口未加（维持默认 backtest；透传能力已留）；立方体对比卡 Δ 依赖后端延伸产出（未出数显示「待复现」）；R1 §10 缺口（建议列等）继续挂账。
6. **删除项**：无。R1 既有组件/文案/交互全部保留（U 触达组件为增量改）。

### 7. S5 修复记录（15-code-review-r2 v4 §8.10 前端栏 · 2026-09-13）

> 输入：`15-code-review-r2.md` §8.1（R2-D1）/§8.4（R2-D4）/§8.7（审计 BLOCK-A1/A2/A3）/§8.8（S-a）/§8.9（NIT F-5/F-3）；
> `10-arch-review-r2.md` v5 §11.1（C1）/§11.2（C2）/§11.3（C3）。
> 边界：只改 `static/**` 与本报告；未改契约/架构/后端/QA 工件；未触 `runtime/**`；§8.10 以外未做重构。
> 新增文案一律先入 `copy.js` 字典（U-12 纪律）；断言脚本 `docs/02-frontend/evidence/verify_r2_ui_states.py` 已同步升级。

| 项 | 改动（文件#函数） | 证据 / 断言（全过） |
|---|---|---|
| **R2-D1** 分析页空态 | `views/analyze.js`：`activate` 删除 portfolio `emptyWhen`；`viewState` 空态唯一条件 `pr.status==='empty'`（加载/错误仍合并）；`emptyVariant()` 二分支（holdings 无 A/B 档 → `no_monitor`，否则 `no_prediction`）；`copy.js#STATE_COPY.analyze.empty{,_no_monitor,_no_prediction}` 文案 | **A1**：rows=15 且全窗 `open_count=0` → `state=success`、`.view-main` 可见、`#an-body tr`=15、三窗口卡 3 张；**A2**：rows=0 → empty，分支①「当前没有纳入监控（A/B 档）的资产」/ 分支②「今日没有可展示的预测记录（/predictions 行为 0）」；**A3**：A1 页无「无预测记录/监控集合为空」文案；**A4**：其余 6 页断言不回退（阶段 A/B 全绿） |
| **R2-D4** histNote 联动 | `views/engine.js#renderHud` + `#renderShadow`（两处）：`可用历史 N 日` 后缀按 `archive_merged` 取 `copy.js#HISTORY_SUFFIX_MERGED（含归档）`/`HISTORY_SUFFIX_MAIN（主文件）` | `arch=false`：HUD 与 `#eg-prg-note` 均「可用历史 20 日（主文件）」+「按主文件计算（归档不可读）」，且无「（含归档）」；`arch=true`：「（含归档）」+「归档合并计算」；负向：不同屏出现矛盾组合 |
| **BLOCK-A1** 测试连接诚实降级 | `views/settings.js#probe` 改本地校验（未配置 / URL 非法 / 通过 三分支，全部不发请求）；`init` 设按钮 `title`；`index.html` 按钮 `title` + 副文案「本地校验…不发起网络请求」；`copy.js#LLM_CHECK_*` | 未配置 → toast「请先填写 Base URL / 模型 / Key（未发起网络请求）」；配置齐全 → 「本地校验通过（格式有效）；连通性测试未接入，不会发起网络请求」；toast 无「已发起/异步任务」；两分支 `window.__fetchCalls` 前后相等（无出站请求）；按钮 title 含「本地校验」 |
| **BLOCK-A2** 隐私两开关 + 水合 | `store.js#applyPrivacyClass` 同时 toggle `masked`/`mask-holdings-only`；`app.css` 增 `body.mask-holdings-only #hd-body td.amt, #an-body td.amt`（透明 + `••••`，明细 5 处；汇总 7 处不受影响）；`main.js#boot` 增 `hydratePrivacy()`（`get('/settings')` → `setPrivacy`，失败静默）；`views/settings.js#savePrivacy` toast 按开关分支（`copy.js#PRIVACY_SUB_*`）；`mock.js` settings 改可变替身（PUT 合并回传，供 S1~S4 断言） | **S1** 副开关：`body.mask-holdings-only`；明细行 `color=transparent`、四卡/占比列不变；toast「已隐藏明细行金额（汇总保留）」；**S2** 主开关：`body.masked` + 四卡打码 + 顶栏按钮「显示金额」；**S3** 启动水合：`?stub=privacy` 全新导航后两 class 就位、设置页两开关回显勾选（刷新保持）；**S4** 打码不改数字：DOM 文本仍 `¥4,867.50`（明细）/ `¥22,762.21`（四卡） |
| **BLOCK-A3** 前端分支 | `views/signals.js`：时间线卡片增 `data-chain`（`chain_available===false→'0'`）；点击展开时 `'0'` 分支直接明示 `copy.js#CHAIN_UNAVAILABLE`（不请求、不空壳），`true` 正常拉 6 步链 | `chain=0` → `.ev` 含「该行链路不可复现（代理日线缺失/超窗）」；`chain=1` → `.chain-item`=6、含「回填态」/「⑥ 输出」（后端读时重算链属 backend-dev；QA 回归 C2/C3 随其后） |
| **S-a** bootstrap 实测 | `views/factors.js#renderScoreChain` 优先读 `bootstrap_percentiles_measured`（非空 → 「bootstrap 500 实测」）；`#scoreDetailHTML`（契约未定义 measured）标注「兼容常量（未实测）」；`copy.js#BOOTSTRAP_*` | measured 非空 → `#fc-score` 含「bootstrap 500 实测：P50 -12.4 …」；null → 「兼容常量（未实测）：P50 -10.8 …」 |
| **NIT F-5** 版本标识 | `index.html`（meta `api-contract` / 侧栏 / 页脚）+ `static/README.md`：v9.1 → **v9.3** | 契约实际版本为 **v9.3**（§11 新增 `LedgerChain.chain_source`，可选前端标注，未消费不改兼容）；审计时点为 v9.2，按「标识不虚报」取编报时点法律版本，见 §4 备案 |
| **NIT F-3** judges 空值 | `views/factors.js#scoreDetailHTML`：`j.value==null` → 标 `copy.js#NOT_WIRED_LABEL`「待接入」（不渲染空 value） | 展开跑分表（stub judges value=null）→ 详情含「待接入」 |
| **C2** 注册表三态诚实标注降级（§11.2） | `copy.js#REGISTRY_PROVISIONAL_NOTE`（字典单一来源）；`views/engine.js#renderRegistry` 与 `views/settings.js#renderRegistry` 注入 `#eg-registry-note`/`#st-registry-note`；`index.html` 两处占位槽 | 引擎页与设置页注册表下均显示「当前单版本运行；shadow/retired 为预留态（版本过渡机制未接入）」；组件与升级协议长文保留、未新增「三态已运作」表述；`/engine/registry` 字段未动（单条 active/metrics=null/can_rollback=false） |
| **C1** R-UI-33 复核（§11.1） | 复核上轮 BLOCK-A1 落地：`views/settings.js#probe`=本地校验三分支（未配置 / URL 非法 / 通过），全部不发请求；按钮 `title`+`index.html` 副文案标「本地校验」 | 设置页无「已发起/异步任务」文案（grep+断言零命中）；两分支 toast 不含谎言措辞；`window.__fetchCalls` 点击前后相等（无出站）；**真探测列 R3**（契约不动，v9.3 §11.1）；C1 立项后前端按端点接线为真实三态（测试中/成功/失败/未配置禁用） |
| 挂账（本轮不修） | F-4 `review.js` shadow_live UI 入口（§8.10 列挂账） | 维持现状 |

**S5/S6 自检计数**：`node --check` **14/14 PASS**（含本轮全部改动文件）；import/export 完整性 0 问题；
`verify_r2_ui_states.py` 更新后 **152/152 PASS（exit 0）** —— 阶段 A 62 条（R2 触点 + C2/C1 三条 + C0 E-1~E-4 四条 + C1 账本四条 + C1 双任务十一条）+ 阶段 B 52 条（四态 ×7 页）
+ 阶段 C 38 条（A1 6 / A2 3 / D4 5 / A-1 6 / S1 5 / S2 3 / S3 2 / S4 2 / A-3 3 / S-a 2 / F-3 1），逐条见脚本控制台与
`%TEMP%\opencode\r2_verify_report.txt`；截图 `evidence/zl_r2_state_empty_holdings.png` / `zl_r2_state_error_engine.png`。

#### 7.1 C0 微修（PM 终验 E-1~E-4 · 2026-09-13）

> 输入：`19-pm-acceptance-r2.md` §7.1（体验 4 条）；纪律：C0 最小修改、不动契约字段名/口径、不做清单外重构，文案入 `copy.js` 字典。

| # | 问题（终验） | 改动（文件#函数） | 证据 / 断言（全过） |
|---|---|---|---|
| **E-1** | 顶栏日期 UTC 偏差（本地 00:00–08:00 早一天，与本地星期错配） | `format.js#localDate()` 新增本地时区日期 helper；`main.js#renderRuntime` 弃用 `toISOString().slice(0,10)` | `#top-date`=本地日期且非 UTC 日期；断言在 UTC 偏窗内实测：`local=2026-09-13 / utc=2026-09-12`，页面显示 2026-09-13 ✅（原缺陷可捕获） |
| **E-2** | 副标题「可信估值覆盖 22/22 只」与 R2-25 四层口径冲突 | `holdings.js#renderOverview`：口径词改由字典 `copy.js#COVERAGE_VALUATION_LABEL`（「估值覆盖」）+ `covered_count/total_count` 组装；不再直出后端 `coverage_note` 口径词（字段未动、未改后端）；「未知行按成本计」保留 | `#pa-today-sub` 含「估值覆盖 X/Y 只」且无「可信估值覆盖」✅；精度窗说明（vsum `window_*` chip）未动 |
| **E-3** | vsum 估算档未知组标签「无」（易误读为零/无样本） | `holdings.js#renderVSum` chips：`confidence==='unknown'` 时改显字典 `CONF_LABEL.unknown`（「无可信估算」）；其余分组标签仍直读后端 | vsum 含「无可信估算」且无裸「无 N 只」✅；mock `groups[].label` 同步镜像后端「高/中/低/无」以保真测试 |
| **E-4** | 影子盘降级条缺样本数（100.0% vs 55.6% · +44.4pp，实际 n=4） | `review.js#activate` 增只读切片 `scoresLive`（`/review/scores?data_kind=shadow_live`——仅取样本数，非 F-4 的实盘切换入口）；`#renderDegrade` 由 `hero.open_count` 显示「样本 n 笔」，`n<20` 附「样本不足（<20 笔），偏差仅供参考」（`copy.js#SAMPLE_*`）；数据不可得则不显示（不编造） | 降级条含「样本 4 笔」「样本不足」✅（mock 镜像终验 live 形态 n=4 / 100.0% / 55.6%） |
| 备注 | ① E-4 阈值 `<20` 沿用项目层①判定口径（`15-code-review-r2` §7.1-B1-8：独立触发日/n_test<20 挂档），**仅展示提示、不参与任何计算**；② E-1 同类 `toISOString` 残留仅 `holdings.js:486`（加/减仓默认日期，非清单项）——登记 R3，本轮不扩围；③ `12-interface-request-r2.md` §2 H1 原「副标题用 `coverage_note`」表述已被本条修订，遵 C0 边界未改该文档（R3 同步） | | |

#### 7.2 C1 增量 · 四本账本人话记录（用户反馈修复 · 2026-09-13）

> 反馈：用户在因子页「四本账本」看到原始 JSON 文本（「这里应该是挖到什么的记录，而不是 json」）。
> 纪律：人话是**展示层**——原始数据与字段表不删除（INSERT-ONLY 审计精神），弹窗内可切换；文案/枚举翻译一律入 `copy.js` 字典。

| 项 | 改动（文件#函数） | 证据 |
|---|---|---|
| `bookRecordSummary(book, r)` | `views/factors.js` 新增（导出）：按账本类型输出人话摘要；`adopted_factors` 含因子名+id · 角色 · 状态 · 牌照 · 总分 · 独立触发日/开口数 · 死亡条件 · 采纳日期 · 回测摘要（mode / purge / holdout / 样本期 / bootstrap P50·P90 / verdict）；`scan_history` 含扫描日期（周次）· 候选 · F1/F2/F3「通过/未过 + 细节」· 判定（verdict_text 优先）· 冷却期；`factor_health`（留一法 Δ / 红线 / regime）与 `retired_log`（移除后 Δ / 结论 / 环境）按真实字段渲染；未知账本/无已知字段走「字段名：值」通用兜底；字段缺失一律留白不编造 | 实测（mock 镜像真实形状）：采纳「klow2 · 角色 否决位 · 牌照 正式 T3 ／ 死亡条件：… ／ 采纳 2026-09-01」；挖掘「2026-08-30 · 候选 RESI30 ／ F1 有效性：通过 · F2 独立性：通过 · F3 增量：未过 ／ 判定：未过 F3（增量）」；体检「待写入」；淘汰「2026-08-24 · vpcorr ／ 移除后组合 Δ +0.3pp · 结论：淘汰正确 → 冷冻盘 · 环境 短窗高波动」 |
| 卡片采样区 | `#renderBooks`：最新 1 条改 `bookRecordSummary` 人话预览（`.bookrec` 样式）；空账本维持「待写入」 | 断言：`#fc-books` 含 `klow2`/`RESI30` 且无 `{"`、无 `factor_id` 字样 |
| 弹窗 | `#openBook`：默认渲染人话记录列表（每条一 `.bookrec`）；右上「查看原始数据/返回人话视图」按钮切换原字段×行表格（审计视图保留）；只读脚注更新为「只读台账 · 无编辑/删除入口；原始数据视图仅供审计」 | 断言：弹窗默认 `.bookrec`≥1、原始视图 `display:none`；切换后原始表格可见（审计不丢） |
| 字典 | `copy.js` 新增 `BOOK_FIELD_LABEL`（字段→中文）、`DIG_RESULT_LABEL`（pass→通过 / fail→未过 / not_run→未执行 / na→不适用）、`DIG_VERDICT_LABEL`、`FACTOR_STATUS_LABEL`、`FACTOR_LICENSE_LABEL`、`RED_LINE_ON/OFF`、`BOOK_*`（回测/待写入/切换按钮/只读脚注）；组件不再散落硬编码枚举文案 | 断言计数：C1 四条（摘要人话渲染 / 弹窗默认人话 / 默认隐藏原始 / 原始切换保留）全过 |
| 边界 | 未改契约字段名与后端；四态与只读语义不变（无编辑/删除入口）；`bookRecordSummary` 对缺字段留白（`—`/跳过），不编造 | `node --check` 通过；import 完整性 0 问题 |

#### 7.3 C1 双任务 · 影子盘 60 天文案与字段（v9.5 F-1..F-3 + PM 补记 · 2026-09-13）

> 输入：`10-arch-review-r2.md` §13（滚动窗口 20→60 + 启动回填；F-1 文案扫描 / F-2 字段直读 / F-3 qualified 文案）+
> `19-pm-acceptance-r2.md` 补记（统一标注「滚动 60 日 · 回算口径（启动回填）」；达成文案；shadow_audit 分离；旧表述零残留）。
> 纪律：字段直读后端（不硬编码）；文案入 `copy.js` 字典；不改计算与数据。

| 项 | 改动（文件#函数） | 证据 / 断言 |
|---|---|---|
| 统一口径标注 | `copy.js#SHADOW_WINDOW_NOTE='滚动 60 日 · 回算口径（启动回填）'`；`engine.js#renderHud` 影子盘子文案 + `#renderShadow` `#eg-prg-note` 与 `index.html` 进度标签同步 | HUD 含「滚动 60 日 · 回算口径（启动回填）」；进度注含同标注 ✅ |
| 达成文案 | `copy.js#SHADOW_QUALIFIED_TEXT='60 日回算覆盖达成（启动回填口径）'`；`SHADOW_STATUS.qualified` 标签「已达标」→「60 日回算覆盖达成」；qualified 时进度注追加完整达成文案 | 断言：HUD/页面含「60 日回算覆盖达成」与「（启动回填口径）」；**无上线资格暗示** ✅ |
| 审计分离 | `copy.js#SHADOW_AUDIT_NOTE='回算口径（启动回填）· 与前向/实盘语义分离'`；HUD 偏差审查行与 `review.js#renderDegrade` 注均挂该标签；`index.html` 「实盘对照」标题 → 「影子盘对照」（副标注「与前向/实盘语义分离」） | 断言：偏差审查行/复盘条含「回算口径（启动回填）」「与前向/实盘语义分离」✅ |
| 字段直读 | `consecutive_days/target_days`（60/60）、`window_days`、`rolling_window_days`、`history_days` 全部直读后端；无硬编码 | 断言：HUD「60 / 60」；mock/stub 镜像 v9.5（progress 60/60 qualified、signals rolling_window_days=60）✅ |
| 旧表述清理 | `copy.js` 移除 `ARCHIVE_MERGED_NOTE`（改用统一标注；保留 `ARCHIVE_FALLBACK_NOTE` 降级分支）；`engine.js`/`static/README.md`/mock 注释与文案同步；`METRIC_TIP.progress_shadow` 重写 | **全仓扫描「滚动 20 / 20 交易日 / 窗口 20 / 自然积累 / 上线门槛 / 已达标 / 归档合并计算」零命中**；断言：引擎页旧口径零残留 ✅ |
| 边界 | 不改契约/后端；四态与只读语义不变；`archive_merged=false` 时仍附「按主文件计算（归档不可读）」降级注（D4 分支不回退） | D4 断言 arch=false/true 双分支通过 ✅ |

#### 7.4 C1 双任务 · 复盘逐笔对账筛选与排序（用户反馈 · 纯视图层）

> 用户反馈（2026-09-13）：否决层加筛选、概率加排序、信号加筛选、基金也加筛选。纪律：纯视图层（不改任何计算与数据）；
> 文案入 `copy.js`；四态与只读（无编辑/删除入口）保持；限量诚实提示。

| 项 | 改动（文件#函数） | 证据 / 断言 |
|---|---|---|
| 状态与控件 | `review.js` 模块级 `reconFilter{veto,signal,fund,sort}` + `reconMeta{loaded,total}`（数据刷新重渲染后保持）；`index.html` 新增 `#rv-filters` 筛选栏；`app.css` 增 `.fbar`/`.thbtn` | 控件断言：否决层 5 项 / 信号 4 项 / 基金输入+datalist / 清除按钮 / 可排序表头 ✅ |
| 否决层筛选 | 全部 / 拥挤度 / KLOW2 / 双灯未亮 / 数据缺失（`vetoCat` 与行内判定口径一致） | 断言：选「拥挤度」→ 2 行且不含「双灯未亮」✅ |
| 信号筛选 | 全部 / 涨 / 灰 / 弃权 | 断言：选「涨」→ 3 行 ✅ |
| 基金筛选 | 文本模糊匹配（代码或名称；datalist 提供现有代码→名称） | 断言：输入 `014320` → 命中 2 行（名称显示「德邦…」，不含「华夏…」）✅ |
| 概率排序 | 「P(涨)」表头点击三态：升序 ▲ → 降序 ▼ → 取消（默认原序=时间倒序）；null 恒置末尾 | 断言：0.5300▲ → 0.6100▼ → 0.6100 无指示符 ✅ |
| 清除与计数 | 「清除筛选」复位四类状态与控件；计数提示 `已筛选 N / 共 M 条 · 作用于已载入 M 条`；当 `total > loaded` 追加「接口限载（共 total 条，筛选仅作用已载入部分）」 | 断言：清除后 5 行 + 计数复位；初始计数含「作用于已载入 5 条」✅（接口上限：`/review/reconciliation` 默认 `limit=60`，`total` 为全量计数——已读后端 `app.py#h_review_reconciliation` / `ledger_api.reconciliation` 确认） |
| 边界 | 筛选/排序不改计算与数据；行 `result`/待回填纪律不变；只读无入口 | 152/152 全过；四态 Stage B 不回退 ✅ |

## 自验收

- [x] U-01..U-12 逐项落地并给出证据（12/12）
- [x] 四态（空/加载/错误/成功）逐页真实可触发；空态含「为什么空 + 下一步」；success 前不渲染数字；error 不回退示例
- [x] 不倒退清单 10 项全部保持（§3）
- [x] 数字全部直读 API 字段（无本地推算；缺失一律 `—`/留白；`+0.00%` 负向断言通过）
- [x] 新增文案先入 `copy.js` 字典再进组件；口径 tooltip 走统一 `METRIC_TIP`/`tipAttr`
- [x] mock 仅测试隔离、默认关闭、形状同步 v9.1
- [x] 未修改 `09` 契约与架构文件；未改任何根目录 `.py`；未改 R1 既有工件（新文件 `-r2` 后缀）；未触 `runtime/**`
- [x] `node --check` 14/14；静态断言 92/92；7 路由冒烟无 console 错误
- [x] 与 v9.1 字段一致性自查完成（§4），未消费字段显式备案
- [x] **S5 修复轮（§7）**：R2-D1（A1~A3）/ R2-D4 / BLOCK-A1 / BLOCK-A2（S1~S4）/ BLOCK-A3 前端分支 / S-a / F-5 / F-3 / **C2 文案 + C1 复核 + C0 微修（E-1~E-4）+ C1 账本人话 + C1 双任务（影子盘 60 文案 / 对账筛选排序）** 全部落地；断言 **152/152 PASS**；F-4 按清单挂账
- [x] S5 边界：只改 `static/**` 与本报告；未改契约/架构/后端/QA 工件；未触 `runtime/**`

## 下游交接

- **`dev-lead`（评审 · G-FE-01）**：核对 03-ui-v3 §8 触点表 × 本报告 §1 双向清单；重点审差异备案 §6-1/§6-4（来源档映射、引擎空态边界）、§4 未消费字段备案与 **§7 S5 修复记录**（F-5 版本标识取 v9.3 的说明）。
- **`qa`（S4/S5 用例）**：以 `verify_r2_ui_states.py`（已含 A1~A3 / D4 / A-1 / S1~S4 / A-3 / S-a / F-3 场景桩）为基础扩真后端用例：四态构造触发、`conf_reason` 五值、徽章 7 项 tooltip、vsum 主指标/官方 chip、hit/miss 与 `t1_real` 一致、待回填仅未到期、sticky/focus/Esc、`import_available=false` 禁用、`+0.00%` 负向；S5 回归重点：U2-03-成 / T2-F2-21-C、D2/D3/D4 断言、审计 A1/S1~S4/C2~C3 断言；R1 集成脚本（8791+CDP）可复用。
- **`backend-dev`（S4 联调）**：按 `12-interface-request-r2.md` §7/§9 字段交付；B1 `shadow_status` 不得双输出；`conf_reason` 按序命中即停；`estimate_quality`/`official_summary` 按 v9.1 §9.1；`progress` 合并口径。
- **`architect`**：两处差异备案（来源档映射、引擎空态边界）若与裁定不符，请版本 +1 明确；R1 挂账缺口（建议列 `advice`）未在本轮扩围。
- **残留风险**：① 契约暂缺 `estimate_quality` 时 vsum 显示「暂无法计算」+ 原因（不阻塞）；② `trace[holdings].detail` 缺失时第⑦项留白；③ 旧内核 sticky/focus 降级路径已在 CSS 兜底（S4 复核）。
