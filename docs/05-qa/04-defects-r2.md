---
artifact: 04-defects-r2
owner: qa
version: v2
status: draft
supersedes: v1（S5 首轮执行）
created: 2026-09-13
reviewers: [dev-lead, orchestrator]
gate: G-QA-02
---

# 缺陷单 · 极境 ZenithLens（R2 升级轮 · S5 · build-r2）

> 方法依据 `diagnosing-bugs`：每单先复现（可稳定重跑）、再最小化、后定位根因。
> 定性分流纪律：缺陷**只提给 `dev-lead`**，不直接找前后端。
> 严重度定义（qa 契约）：**P0 致命**=核心功能不可用/数据严重错误/无法启动；**P1 严重**=主要功能受影响且有绕过；**P2 一般**=体验问题；**P3 轻微**=优化建议。**数据错误一律 P0**。
> 本轮合计：**P0 0 / P1 1 / P2 0 / P3 3**。证据目录：`docs/05-qa/evidence-r2/`。

## 摘要

1. **v2（S5 回归复审轮）**：R2-D1/D2/D3/D4 **全部 closed** —— 修复经 dev-lead 独立复验（`15-code-review-r2.md` v5 §9：前端 7/7 · 后端 6/6 · 架构 4/4）后，QA 回归复审逐条断言通过（结果见 `18-test-report-r2.md` v2 §10）。
2. R2-D1（P1）修复后：分析页空态唯一条件=「无预测记录/无监控资产」，`rows=15/open=0 → success`；原失败 2 条 P0 用例转 PASS。
3. R2-D2（P3）`main_source.path` 已回契约字面；R2-D3（P3）同型 409 可读互斥 + 全局串行 + OSError 可读；R2-D4（P3）历史后缀随 `archive_merged` 联动。
4. 数据面零缺陷；本轮（回归）**无新增缺陷**。

## 正文

### 缺陷状态总表

| 编号 | 严重度 | 摘要 | v1 状态 | v2 状态（回归复审） | 关闭依据 |
|---|---|---|---|---|---|
| R2-D1 | **P1** | 分析页空态触发条件用「全窗 open_count=0」，与 §4「监控集合为空/无预测记录」不符；遮蔽预测表 + 原因文案失真 | open | **closed** | `analyze.js` 空态唯一条件=无预测记录；7/7 页真实 success；`r2v2_ui_results.json` |
| R2-D2 | P3 | `main_source.path` 返回绝对路径（契约 §3.11 字面 `data/holdings.json`） | open | **closed** | 真机 `path=='data/holdings.json'`；`r2v2_fix_results.json:R2-D2` |
| R2-D3 | P3 | 同型任务并发提交 → 任务失败 `E_UNKNOWN`（WinError 5/2） | open | **closed** | 同型 409 可读 + 完成后可再提交 + 全局串行；`R2-D3a/b/c`（队列化增强挂账 R3） |
| R2-D4 | P3 | 进度降级分支 `histNote` 硬编码「（含归档）」与 fallback 口径矛盾（潜在） | open | **closed** | 后缀随 `archive_merged` 联动实测（false→「（主文件）」）；`R2-D4` |

### R2-D1 ·【P1·行为/口径不符】分析页空态触发条件不符规格 → **closed（v2 · 回归复审通过）**

- **现象**：打开「分析」页（`#/analyze`），当日 0 开口但存在 15 条预测记录时，整页进入 `empty` 态：`view-main` 隐藏（参与预测持仓表不可见），仅显示空态卡；卡内「为什么空：监控集合为空，或全部资产无预测记录」与事实不符（实测监控 15/22 只、`/predictions` 15 行）。
- **复现路径**：① 起服 build-r2 副本（8796）→ 浏览器打开 `http://127.0.0.1:8796/#/analyze`；② DOM：`#view-analyze dataset.state = 'empty'`、`#an-body tr` 实为 15 行但 `.view-main display:none`、空态块含「今日没有触发开口的资产 / 监控集合为空，或全部资产无预测记录」；③ 对照 `/api/v1/predictions`（rows=15）与 `/portfolio/forecast`（三窗 `open_count=0`）。稳定复现（UI 套件 `U2-03-成` 条；`zl_r2_real_signals.png` 同批次可对照）。
- **期望**（`03-ui-design-v3 §4` 分析行）：空态触发 =「监控集合为空，**或**全部资产无预测记录」；有 15 条预测记录时应为 `success`，渲染三窗口组合卡 + 参与预测表（R1 `T-UI-12` 边界「无开口行」亦要求表仍展示）。空态卡「为什么空」文案必须与实际触发条件一致。
- **实际**：`analyze.js` 的 portfolio 片 `emptyWhen` 把「三窗口全部 `open_count==0`」判为空，且 `viewState()` 以 **OR** 合并两片 → 无开口日一律 `empty`（实测本日即命中）。
- **定性**：实现条件与设计文档不符（实现方注释自称「= 监控集合为空 或 全部资产无预测记录」，与代码条件也不一致）→ 若 PM 认可「无开口即空态」为新口径，则应改为**文档修订**（`03-ui §4` + `13-frontend-report-r2 §2`）；否则为**代码缺陷**。请 dev-lead 结合 PM 裁定分流。
- **根因**：`static/js/views/analyze.js:24`（portfolio `emptyWhen` 用 `open_count>0` 判断）+ `:41`（`pf.status==='empty' || pr.status==='empty'` OR 合并）；正确性应以「监控集合为空（monitored_count==0）/ `predictions.rows=0`」为条件，或独立分节展示「今日无开口」而不得隐藏整页主内容。
- **影响**：分析页主内容（预测表/三窗口卡）在无开口日（按产品自述为多数交易日）不可见；空态原因文案失真。影响 R2-21 验收①（触发条件逐页一致）与用户对「参与预测」的可见性。
- **证据**：`evidence-r2/r2_ui_results.json:U2-03-成`（7 页 success=6/7，偏差 `analyze:empty`）；`ep2_holdings.json` / `ep2_signals.json`（预测与开口口径）；源码 `analyze.js:24,34,41`；截图 `zl_r2_state_empty_holdings.png` 同法可复现。
- **分流建议**：dev-lead（开发修正 / 或转 PM×架构做口径裁定）。修复后回归 `U2-03-成` + `T2-F2-21-C` + 分析页 smoke 即可。

### R2-D2 ·【P3·契约字面偏差】`main_source.path` 为绝对路径 → **closed（v2）**

- **现象**：`GET /settings/holdings-data` 的 `main_source.path` 返回安装绝对路径（如 `…\data\holdings.json`），契约 §3.11 字面为 `"data/holdings.json"`。
- **复现路径**：`curl http://127.0.0.1:8796/api/v1/settings/holdings-data` → `data.main_source.path`；S4 证据同态（`evidence-r2/ep_settings_holdings_data.json` 亦为绝对路径）。
- **期望**：按契约字面返回相对主源标识 `data/holdings.json`（或由架构版本 +1 明确「绝对路径」并同步前端展示）。
- **实际**：`holdings.py:312 main_source_status()` 直接返回 `HOLDINGS_PATH`（由 `DATA_DIR` 拼出的绝对路径）。
- **定性**：字段名/类型正确，仅**值格式**与契约字面不一致（显示层；不影响功能，前端展示为该绝对路径）。
- **根因**：实现以文件系统路径直出，未按契约做展示化相对路径。
- **证据**：`evidence-r2/ep2_holdings_data.json`；`build-r2/holdings.py:312`；S4 `ep_settings_holdings_data.json`。
- **分流建议**：dev-lead 快审（改 `relpath` 或架构修订契约文字；二选一即可关闭）。

### R2-D3 ·【P3·健壮性】同型任务并发提交失败（`E_UNKNOWN`） → **closed（v2 · 最小版）**

- **现象**：QA 误并发提交 2 个 `maintain_nav_history`（同期还有一个 `backfill_ledger recompute`）→ 2 个任务 `failed`，error = `[WinError 5] 拒绝访问` / `[WinError 2] 系统找不到指定的文件`（`E_UNKNOWN`，直接暴露原生异常文案）。随后**串行重跑 `done`**（22 只 / 新增 0 点），数据无损（nav points 5636 不变）。
- **复现路径**：① 快速连续 `POST /api/v1/tasks {"type":"maintain_nav_history"}` ×2（间隔数秒）；② 查 `GET /api/v1/tasks`，可见 `tsk_20260913_010421_6c36` / `tsk_20260913_010421_05ec` `failed`（error 字段含 WinError 原文）；③ 再串行提交一次同任务 → `done`，`data/cache/nav/*.json` 与 `data/snapshot/accuracy.json` 内容不变。
- **期望**：同型任务应串行化/去重（或至少降级为可读失败原因并自动重试）；任务失败不得影响数据完整性（该点已满足）。
- **实际**：队列允许同型任务并行执行，两任务对同一批 nav/accuracy 原子写产生文件竞态 → WinError 被包装为 `E_UNKNOWN` 直接透出。
- **定性**：任务调度健壮性（边缘场景：单用户正常串行操作不受影响；QA 异常注入复现）。非数据缺陷（数据保全、重试可恢复）。
- **根因**：任务队列缺少同型互斥/去重；原子替换在并发同进程内无锁（基于任务记录与文件时点推定，待后端复核）。
- **证据**：任务记录（`/tasks` 两单 error 字段，见 `r2_task_results.json` 首轮记录）；串行复跑 `r2_task_results2.json:C2-01/G2-D02`（done + 幂等）。
- **分流建议**：dev-lead（可归 R3 健壮性；建议加「同型任务排队/去重」与错误文案可读化）。

### R2-D4 ·【P3·潜在文案】降级分支 `histNote` 硬编码「（含归档）」 → **closed（v2）**

- **现象（潜在）**：影子盘进度在「归档不可读」降级分支下会同时出现相互矛盾的文案：`按主文件计算（归档不可读）` + `可用历史 N 日（含归档）`。
- **复现路径**：源码走查 `static/js/views/engine.js:146-147` —— 146 行按 `prg.archive_merged` 切换 `ARCHIVE_MERGED_NOTE` / `ARCHIVE_FALLBACK_NOTE`，但 147 行 `histNote` 恒定拼接 `'（含归档）'`；`copy.js:182-183` 两条口径注。当前 `archive_merged=true`（归档已生成）**不可现场触发**；若归档目录被删/不可读即显现。
- **期望**：降级分支 `histNote` 不宣称「含归档」（如「可用历史 N 日（主文件）」），与 `ARCHIVE_FALLBACK_NOTE` 一致（U-05「归档缺失→按主文件计算 + 口径降级标注」）。
- **实际**：fallback 分支下仍显示「（含归档）」。
- **定性**：文案一致性问题（潜在路径；当前不影响显示）。
- **根因**：`histNote` 未与 `archive_merged` 联动。
- **证据**：`build-r2/static/js/views/engine.js:146-147`、`copy.js:182-183`；UI 套件 `U2-05` 记录（当前分支正常）。
- **分流建议**：dev-lead（前端一行修正或并入 R3 清理）。

## v2 · 关闭记录（2026-09-13 · S5 回归复审）

> 关闭方法：修复轮（`15-code-review-r2.md` v5 §9 独立复验）后，QA 在刷新 build-r2（137 文件）副本上逐条重跑断言（`evidence-r2/r2v2_fix_results.json` + `r2v2_ui_results.json`）。

| 编号 | 关闭断言（QA 复跑） | 结果 |
|---|---|---|
| R2-D1 | 分析页空态唯一条件=「无预测记录/无监控资产」；`rows=15/open=0 → success`（7/7 页真实 success）；空态文案二分支 | ✅ closed |
| R2-D2 | `GET /settings/holdings-data.main_source.path == "data/holdings.json"`（无盘符/反斜杠）；count=22 | ✅ closed |
| R2-D3 | 运行中同型再提交 → `409/E_CONFLICT`，message 含任务号与 `GET /tasks` 查询指引；完成后可再提交并 `done`；全局串行（跨型无交叉由 5 条单测覆盖）| ✅ closed（最小版）；队列化/自动合并 + 原生错误统一映射挂账 R3 |
| R2-D4 | 引擎页历史后缀随 `archive_merged` 联动：false → 「可用历史 20 日（主文件）」；代码双分支（`HISTORY_SUFFIX_MERGED/MAIN`）覆盖 true 路径 | ✅ closed |

- 附加：审计 BLOCK 断言（A1 零出站 / S1~S4 隐私+水合+不改数字 / A-3·C1~C4 链）与 `chain_source` 三态同批通过（`r2v2_fix_results.json` 25/25）。
- 残留挂账（非缺陷）：R2-D3 的队列化增强、C1 真探测、C2 版本化机制等 → `15-code-review-r2.md §9.3`（R3）。

## 自验收

- [x] 每单六项必填（现象 / 复现路径 / 期望 / 实际 / 定性 / 根因）齐全，附严重度与证据索引
- [x] 严重度按定义判定：无数据错误（故无 P0）；R2-D1 按「主要功能受影响、有绕过」判 P1；其余为优化/潜在项 P3
- [x] 所有单据均可稳定复现或给出静态可查证据（R2-D4 已注明当前不可现场触发）
- [x] 缺陷只登记给 `dev-lead` 分流，未直接联系前后端；未修改任何产品代码
- [x] 证据均落 `docs/05-qa/evidence-r2/`，文件名可回溯
- [x] **v2**：R2-D1/D2/D3/D4 逐条关闭断言复跑通过（上表）；回归轮无新增缺陷

## 下游交接

- **主消费方 `dev-lead` / `orchestrator`**：**本单 v2 全部 closed，无需再分流**；`18-test-report-r2.md` v2 的 G-QA-02 自判 = PASS（159/159），可放行 G-PM-05 终验。
- **次消费方 `product-manager`**：终验可对照 v2 关闭记录逐条复核；分析页空态与隐私开关的实操路径见 `r2v2_*` 截图与 `r2v2_fix_results.json`。
- **残留挂账（非缺陷，R3）**：R2-D3 队列化/自动合并与原生错误统一映射；C1 真探测端点；C2 版本化重训/回滚机制；R2-04 9 只复核 ≤ G-PM-05 另行收口（`15-code-review-r2.md §9.3`）。
