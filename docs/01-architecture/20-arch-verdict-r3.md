---
artifact: 20-arch-verdict-r3
owner: architect
version: v1
status: approved
supersedes: —
created: 2026-09-12
task_id: OC-SHADOW-ARCH
project: zenithlens-oc
reviewers: [backend-dev, frontend-dev, qa, dev-lead, orchestrator]
gate: G-AR-05
---

# 架构裁定书 R3 · 极境 ZenithLens（影子盘滚动窗口 + 因子上限口径同步）

> 触发：`14-api-impl-report.md` **v6** §0d/§7 V5/V6（task OC-SHADOW-BE）、`12-interface-request.md` **v3** §10 缺口 10（task OC-SHADOW-FE）、`14-frontend-fix-report.md` §C-01/C-02 请求契约收录 `caps`。
> 依据：用户 2026-09-12 明确两条业务口径——① 影子台账「先抓过去 20 个交易日，每过一天替换一天」；② 因子正式盘真实上限为**否决位 ≤4 · 打分位 ≤3**（旧「上限 3」有误）。
> 产出：契约升 **v6**（`09-api-contract.md`，旧版备份 `09-api-contract-v5.md`）。
> 边界：**不改后端 `*.py`、不改 `static/**`、不改 `runtime/**`、不派发子任务**；本次只做契约同步与废弃登记。

## 摘要

1. 裁定两条：**V5**（台账 `opened` + 滚动窗口语义）→ **采纳收编**；**V6**（`FactorPan.caps` + `factor_cap` 废弃）→ **采纳收编 + 登记废弃**。
2. 契约 v6 **只加字段 / 只加对象键 / 登记一处既有键废弃（`factor_cap` 取值改 `null`）**；**未改名、未删字段、未改类型**；旧版 v5 备份留档 `09-api-contract-v5.md`。
3. V5 落点：§5.9 `LedgerEntry.opened`（boolean，= `signal=="up"`）+ §5.9 滚动窗口口径 + §6.7 `/ledger` 口径 + §5.28 `ShadowLedger.field_list` 补 `opened`（§5.13 `shadow_signals.schema_fields` 随 `FIELD_LIST` 同步）。
4. V6 落点：§5.11 `FactorPan.caps`（`{veto_max, score_max}`，正式盘 `{4,3}`、其余 `null` 键恒在）+ `factor_cap` **deprecated 且所有盘恒 `null`** + §6.8 `/factors/pans` 口径。
5. 后端与前端均已完成实现（后端 task OC-SHADOW-BE、前端 task OC-SHADOW-FE），本裁定**不产生代码修改单**，只产生契约与门禁核对依据。
6. 边界：本轮只收编上述两项，其余 v6 报告残留（六窗 lift 空、`covered_count` 口径等）**不在本次范围**，见 §4。

## 正文

### 1. 裁定总表

| 项 | 定性 | 裁定 | 契约落点 | 后端动作 | 前端动作 |
|---|---|---|---|---|---|
| V5 台账缺 `opened` + 滚动窗口未入契约 | 契约缺口 | **采纳收编** | §5.9 + §6.7 + §5.28 + §5.13 | 无（已实现） | 无（已消费） |
| V6 `caps` 未入契约 + `factor_cap` 误导 | 契约缺口 + 一处既有键废弃 | **采纳收编 + 登记 deprecated** | §5.11 + §6.8 | 无（已实现） | 无（已改读 `caps`） |

---

### 2. 裁定 1 · V5 —— 影子台账 `opened` 与滚动窗口语义：**采纳收编**

#### 2.1 问题

`14-api-impl-report` v6 §0d：`backfill_ledger` 实装为**最近 20 交易日滚动影子台账**（真实引擎走前计算、INSERT-ONLY、每日追加 + 裁剪最旧、幂等、裁剪归档），台账行新增 `opened`(bool)；实测 `GET /ledger` **200 条 / 20 交易日 / 2026-08-17~2026-09-11**，`opened=true` 4 条（其余 196 条如实 `false`）。但契约 v5 §5.9 `LedgerEntry` 无 `opened`，§6.7 `/ledger` 仅描述「读取左连接回填」，**未定义滚动窗口保留语义**；§5.28 `ShadowLedger.field_list` 仍为无 `opened` 的 12 键旧清单。若不同步，契约与唯一法律出现双份真相（G-BE-02 红线），且三方（前端/后端/QA）对「台账到底保留几天」无共同依据。

#### 2.2 两种立场与代价

| 立场 | 主张 | 收益 | 代价 |
|---|---|---|---|
| **A · 不改契约，`opened` 作为实现细节** | 台账保持「全量 INSERT-ONLY」旧描述，20 日窗口仅是任务实现 | 契约零改动 | ① 与「INSERT-ONLY=永不删行」的旧口径直接矛盾（滚动裁剪会删行）——审计语义被静默改变；② 前端无法据契约判断 `opened` 是否存在；③ QA 无依据断言「窗口 ≤20 日 / 幂等」，G-BE-02 无法核对 |
| **B · 采纳收编（推荐）** | §5.9 增 `opened`、§6.7 钉死 20 交易日滚动语义与归档，§5.28 `field_list` 补键 | ① 契约与实现继续单一真相；② 「裁剪≠丢审计」明确（裁剪行全量归档，`first_of_day_immutable` 语义延续 A-10）；③ QA 获得可断言口径 | 契约版本 +1（已执行）；需澄清滚动窗口与 A-10 归档的关系 |

#### 2.3 结论

**选 B · 采纳收编。** 依据：
1. **业务口径由用户拍板**（2026-09-12）：「先抓过去 20 个交易日，每过一天替换一天」——不是实现自选，属需求级口径，必须进唯一法律。
2. **与既有 INSERT-ONLY/归档语义自洽**：v4 A-10 已定义 `retention_policy=first_of_day_immutable_full_archive`（首次口径永久 + 全量归档），滚动裁剪**正是该保留策略的执行形态**；裁剪行写入 `ledger/archive/shadow_signals_archive.jsonl` + `_manifest.jsonl`，审计不丢。
3. **`opened` 是派生事实、非新决策**：`opened == (signal=="up")`，与 §1.3 `signal` 枚举同源。显式落键优于让每个消费方各自推导（消除前端/后端/QA 三处口径漂移），且旧行读取时按 `signal` 派生，向旧数据兼容。
4. **诚实性**：无开口日如实 `false`（实测 196/200），无代理行情时保持为空、不写示例数字——符合「缺失一律显式表达」铁律。

#### 2.4 对后端/前端的最小可执行规格

- **契约动作（本裁定书已执行，`09-api-contract.md` v6）**：
  1. §5.9 `LedgerEntry` 增 `opened`（boolean，`signal=="up"`；无开口日 `false`；键恒在）；
  2. §5.9 增「滚动窗口口径」注：交易历 = 监控 A/B 档代理 K 线日期并集；窗口 = 最近 20 交易日；每日追加 + 裁剪最旧；裁剪全量归档（`reason=rolling_window_trim`）；窗口内 `(date,code)` INSERT-ONLY、重复触发幂等；
  3. §6.7 `GET /ledger` 口径补滚动窗口与 `opened`；`POST /ledger/entries` 明确 `opened` 不入请求体、由后端按 `signal` 派生；
  4. §5.28 `ShadowLedger.field_list` 补 `opened`；§5.13 `shadow_signals.schema_fields` 随 `FIELD_LIST` 同步。
- **代码动作**：**无**（后端 `ledger_api.FIELD_LIST` 已含 `opened`，`rolling_shadow_backfill`/`compute_shadow_window` 已实现；前端已消费）。本裁定不新增修改单。
- **回归义务**：backend-dev 重跑 `python -m unittest discover -s tests -t .`（v6 基线 **70/70**，含 `test_shadow_backfill_contract.py` 5 条）；qa 按 §3.4 负向断言复核。

---

### 3. 裁定 2 · V6 —— 因子盘 `caps` 与 `factor_cap` 废弃：**采纳收编 + 登记 deprecated**

#### 3.1 问题

`14-api-impl-report` v6 §0d/§7 V6 与前端 `14-frontend-fix-report` §C-01：契约 v5 §5.11 `FactorPan.factor_cap`（`integer/null`）在正式盘返回单值 `3`，前端裸渲染为「上限 3」，与用户更正的**真实规则「否决位 ≤4 · 打分位 ≤3」**矛盾（P0 口径错误）。后端已改：新增 `caps={"veto_max":4,"score_max":3}`（正式盘）、其余盘 `caps=null`，并把 `factor_cap` 置 `null`；前端 `factors.js` 已删除全部 `factor_cap` 引用、改读 `caps`（`caps` 缺失时不显示任何单一上限数字）。`12-interface-request` v3 §10 缺口 10 正式请求契约收录 `caps` 并标注 `factor_cap` deprecated。

#### 3.2 两种立场与代价

| 立场 | 主张 | 收益 | 代价 |
|---|---|---|---|
| **A · 保留 `factor_cap` 旧语义，仅前端不再读** | 契约不动，前端自律 | 契约零改动 | ① 「上限」是**两个维度**（否决位/打分位），单值字段无法承载，保留即留误导源；② 契约与实现分叉（实现已返回 `null`），G-BE-02 反而判后端「字段口径不符」；③ 未来新消费方仍可能踩「上限 3」 |
| **B · 增 `caps` 承载真实上限 + 登记 `factor_cap` deprecated（推荐）** | §5.11 增 `caps`，`factor_cap` 名称/类型保留但恒 `null` 并标注废弃 | ① 真实上限（双维度）有唯一载体；② 向后兼容（不删字段，旧壳不报错）；③ 明确删除路径（版本 +1） | 契约版本 +1（已执行）；短期两键并存（可接受，前端已不读旧键） |

#### 3.3 结论

**选 B · 采纳收编 + 登记 deprecated。** 依据：
1. **真实业务规则是双维度**（否决位 ≤4 · 打分位 ≤3），任何单值字段（`factor_cap`）在语义上都无法表达，属**结构性契约缺口**。
2. **「只加不改」纪律下最优解**：新增 `caps` 对象承载真实语义；`factor_cap` 不删名/不改类型（避免破坏旧壳），但**取值恒 `null`** 并在契约标注 `deprecated`——既消误导，又保兼容。
3. **前端已零引用**：`14-frontend-fix-report` §C-01/C-02 实测删除全部 `factor_cap` 裸渲染、`caps=null` 时不显示单一上限数字；契约收录后前后端回到单一真相。
4. **删除路径明确**：后端当前 `caps`/`factor_cap` 并存以兼容旧壳；删除 `factor_cap` 须版本 +1 并通知双边（写入 §5.11 口径）。

#### 3.4 对后端/前端的最小可执行规格

- **契约动作（本裁定书已执行，`09-api-contract.md` v6）**：
  1. §5.11 `FactorPan` 增 `caps`（object/null；`{veto_max:int, score_max:int}`；正式盘 `{4,3}`、其余 `null`、**键恒在**）+ 元素字段穷举表；
  2. §5.11 `factor_cap` 口径改为 **deprecated + 所有盘恒 `null`** + 明确「不得再据此展示上限、删除须版本 +1」；
  3. §6.8 `GET /factors/pans` 增 v6 口径（上限以 `caps` 为准，`factor_cap` 恒 `null`）；
  4. §1.5 术语表增「因子上限 `caps`」（Avoid：`factor_cap`）。
- **代码动作**：**无**（后端 `factor_board.PAN_META`/`pans()` 已实现；前端已改读）。本裁定不新增修改单。
- **回归义务**：backend-dev 保持 `tests/test_shadow_backfill_contract.py::FactorPansCapsTest` 2 条绿；前端保持「因子页不含『上限 3』、无裸 `factor_cap`」断言（`evidence/verify_shadow_fe.py`）；qa 按 §3.4 负向断言复核。

---

### 4. 本次未纳入 / 边界（防范围蔓延）

以下项在 v6 报告/前端报告中被提及，但**均不属于**本轮 OC-SHADOW-ARCH「契约同步 caps/opened」派发范围，本次**不裁定**：

- **v6 报告残留 16「六窗 lift 如实为空」**：`adopted_factors.json` 无记录导致 `FactorLiftBar.lift=null`，属**因子引擎产出后回填**，非本契约结构问题；已登记为 v6 残留风险 12（责任人 backend-dev + architect）。
- **v6 报告 §0b V3「`covered_count` 口径」（契约 v5 §6.2.1 写 `market_value != null`，实现按 `change_rate != null`）**：终验 P1 修复已落地代码，但契约文字同步属**另一次裁定**（`covered_count` 口径反转需单独比较两立场与代价），本次不夹带。
- **v6 报告 §0c V4「官方净值数据源替换 fundgz→FundValuationLast/lsjz」**：数据源替换，非契约字段变更，另轮知悉。
- **`factor_cap` 的最终删除**：本轮只登记 deprecated 与恒 `null`；删除须版本 +1（§5.11），另行排期。

## 自验收

- [x] 两条裁定均四段齐全（问题 / 两种立场与代价 / 结论 / 最小可执行规格：契约落点 + 代码动作 + 回归义务）——§2、§3
- [x] V5 明确滚动窗口与 INSERT-ONLY/归档（A-10）的关系，未与旧口径矛盾——§2.2/§2.3
- [x] V6 明确 `caps` 双维度语义与 `factor_cap` 废弃/删除路径——§3.2/§3.3
- [x] 契约升版走 +1（09 v6，supersedes v5），旧版另存 `09-api-contract-v5.md`——已执行
- [x] 字段类型/单位/精度/口径齐全（`opened` boolean、`caps` 元素 integer）；枚举不新增（布尔与整数不涉枚举）
- [x] **只加不改**：未改任何既有字段名/类型；仅登记 `factor_cap` 取值废弃（`null`）——§1 总表、契约 §11.4
- [x] 未修改任何 `.py`、未改 `static/**`、未改 `runtime/**`、未派发子任务——是
- [x] 数字带来源（200 条/20 日/4 条、caps 4/3、70/70）均注 `14-api-impl-report` v6 出处

## 下游交接

- **主消费方 `backend-dev`（经主 Agent 转派）**：**无代码动作**。确认 `FIELD_LIST` 含 `opened`、`factor_cap=null`、`caps` 结构稳定与 `shadow_signals.schema_fields` 同步；重跑 `python -m unittest discover -s tests -t .`（v6 基线 70/70）并回报。
- **次消费方 `frontend-dev`**：无代码动作（已按 `caps`/`opened` 消费）。保持负向断言：因子页无「上限 3」、无裸 `factor_cap`；`caps=null` 不显示单一上限数字。
- **次消费方 `qa`**：按本裁定书 §2.4/§3.4 负向断言执行——`/ledger` 行含 `opened` 且与 `signal=="up"` 一致、无开口日 `false`；`backfill_ledger` 两次 `total` 不翻倍、窗口 ≤20 交易日；`/factors/pans` 正式盘 `caps={veto_max:4,score_max:3}`、`factor_cap=null`、其余盘 `caps=null` 键恒在。
- **`dev-lead`**：G-BE-02 自本版起以 **`09-api-contract.md` v6** 为唯一法律复核；销项以本裁定书 §1 总表 + 契约 §11 为核对清单。
- **残留风险**：
  1. `factor_cap` 目前与 `caps` 并存（兼容旧壳），存在被未来新消费方误读的余量 → 删除须版本 +1 并通知双边（责任人：architect + backend-dev，期限：下一轮触达）。
  2. 滚动窗口「20 交易日」为当前冻结值；若用户调整窗口长度，须契约版本 +1（`SHADOW_WINDOW_DAYS` 属口径常量，责任人：architect，触发人：product-manager/orchestrator）。
  3. 无可用代理行情时台账保持为空（诚实空态）；若长期为空致影子盘 60 日进度不动，属数据源可用性问题，另走 08 残留风险（责任人：backend-dev）。
