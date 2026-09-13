---
artifact: 10-arch-review
owner: architect
version: v1
status: approved
supersedes: —
created: 2026-09-12
reviewers: [product-manager, orchestrator]
gate: G-AR-06
---

# 架构定稿纪要与 PM 会签 · 极境 ZenithLens

> 被评审对象：`docs/01-architecture/05-product-arch.md`~`09-api-contract.md`（v1 draft）。
> PM 挑刺输入：`docs/01-architecture/10-arch-review-pm.md`（A-01~A-06）。
> 本文是 S2 架构会签终审记录：对 6 条逐条给出「PM 立场 / 架构立场 / 最终结论」，并把结论落到 `05~09` 的 **v2** 修订。旧版已另存 `*-v1.md`。

## 摘要

1. 6 条裁定：**3 条采纳（A-01/A-05 全采纳，A-06 核心采纳）**、**3 条部分采纳（A-02/A-03/A-04）**。全部落到具体章节与字段名，无"优化 XX"式空话。
2. 其中 **4 条为实质分歧**（A-02/A-03/A-04/A-06）：架构师分别改动了 PM 的方案（A-02 用 `market_value` 而非 `change_rate` 判据；A-03 门槛改冻结常量而非 API 参数；A-04 保留 T+1 生产链、未验证窗口走 `provisional_*`；A-06 有旧快照时返回 `ok=true`+陈旧态而非一律 `ok=false`），**不是橡皮图章**。
3. 双向让步 5 处：架构师在 A-01/A-05 全盘接受 PM 的保守口径；PM 在 A-01（追加键）、A-02（判据）、A-04（PRD 引注错误）、A-06（可用数据保留）上接受了架构师的反修正。
4. 修订后 **05/06/07/08/09 全部升 v2 并置 `approved`**；PM 建议的 G-AR-06 `CONCERN` 已消解为 **PASS 候选**（最终判定权在 orchestrator）。
5. 边界遵守：未写代码、未读 FundLens/ZCode、未改 `runtime/**`、未派发子任务。

## 正文

### 1. 裁定总览

| # | 议题 | PM 建议 | 最终裁定 | 实质分歧 | 落地位置（v2） |
|---|---|---|---|---|---|
| A-01 | 当日估值快照是否 INSERT-ONLY | 新增 `valuation_history.jsonl`，当日已入账 mode 只增不改 | **采纳**（架构强化：history=审计源，snapshot 降级为缓存） | 否（细分键） | 06 §1/§2.2/§4.2/§7.4；08 §3.2；09 §5.2/§5.3/§6.3 |
| A-02 | 未知持仓用成本价冒充市值 | 二选一：(a) 总资产只汇总 `change_rate!=null`；(b) 单独 `fallback_value` 并标注 | **部分采纳**：合并 (a)(b)，`total_value` 以 `market_value!=null` 为准，成本走 `fallback_value` | **是** | 09 §1.2/§1.3/§5.1/§6.2/§6.2.1；07 §5.2；06 §4.2；05 1.1/1.7 |
| A-03 | 组合方向 0.52 无覆盖门槛 | 新增门槛，`direction` 强制 gray 时文案"覆盖不足"；0.52 标注架构口径；修 `tier_excluded` | **部分采纳**：门槛采用但为**冻结常量 0.30/3**（非 API 参数）；0.52 保留并标 `threshold_source` | **是** | 09 §1.3/§5.7/§5.14/§6.5；08 §5；07 §5.4；05 4.1 |
| A-04 | T+3/T+15 无 Brief 依据却同构输出方向 | 增 `validated`+`formula_source`；未验证不出 `up`；补齐 `p` 定义 | **部分采纳**：增字段；T3 `p=null`、T15 `p`=DDSM(H=15)；生产 `direction` 未验证恒 gray；T1 保留 Brief 授权生产 | **是** | 09 §1.3/§5.5/§5.7/§6.4；08 §4.5；07 §5.4；05 3.5 |
| A-05 | KLOW2 缺失时不否决=放松保护 | 显式降级为 gray/abstain 或链路标 missing；加噪只进训练 | **采纳并强化**：任一否决层 `missing` → `signal=abstain` + `reason=veto_data_missing` + 链路步 `missing` | 否（取更严者） | 09 §1.3/§5.4/§6.4；08 §4.3/§4.4；05 3.6 |
| A-06 | 引擎离线被编码进"空态" | 返回 `ok=false`+`E_ENGINE_OFFLINE`，或 payload 带 `engine_status=offline`；禁止 empty 承载故障 | **部分采纳**：核心采纳；细分三态返回（当日快照/旧快照/无快照），有旧快照走陈旧态而非一律 error | **是** | 09 §6.4/§6.5；06 §4.2；07 §4/§5.4；05 摘要 6 |

### 2. 逐条裁定

#### 2.1 A-01 · 当日估值 INSERT-ONLY

- **PM 立场**：`/valuations` 每次实时计算，`valuation-YYYYMMDD.json` 单文件覆盖写，盘中→盘后、两次盘中刷新都会覆盖已入账 `mode`/`trace`；R-03「官方回填后不得改写当日已入账记录来源」只在"回填"一个动作上守住。要求新增 `data/snapshot/valuation_history.jsonl`（或 `(date, code, mode)` 追加），当日已入账只增不改，读取默认最新、徽章可回溯。
- **架构立场**：核心成立，采纳 INSERT-ONLY。但 PM 的 `(date, code, mode)` 追加键**不足以**覆盖"同日同 mode 多次刷新"（会互相覆盖或语义重复）；应改为按**每次写入**追加 `written_at`，追加键为 `(date, code, written_at)`。同时区分两个文件：`valuation_history.jsonl` 是**审计源**（只增不改），`valuation-YYYYMMDD.json` 降级为**可重建缓存**（允许整文件覆盖），避免"缓存损坏=审计丢失"。
- **最终结论**：**采纳（含架构修订）**。
  - 08 §3.2 新增硬规则"当日 INSERT-ONLY"；06 §7.4 新增伪代码；06 §2.2 目录新增 `valuation_history.jsonl`。
  - 09 §5.2 `Valuation` 增 `written_at`/`run_id`/`is_first_of_day`/`history_available`；`/valuations/{code}?history=true` 返回 `history: Valuation[]`（按 `written_at` 升序），默认取最新一条。
  - 09 §5.3 口径改为"官方回填**追加**记录，不改已入账 `mode`/`trace`"。

#### 2.2 A-02 · 未知持仓用成本价冒充市值

- **PM 立场**：`market_value` 在估值/净值为 null 时回退成本价并标 `mv_source=fallback`，而 `total_value=Σ market_value`，总资产会悄悄变成"成本合计"且不进 F-04 未知声明。二选一：(a) 总资产只汇总 `change_rate!=null` 的行并声明"仅覆盖 N/M"；(b) 单独返回 `fallback_value` 并在 UI 标注口径。
- **架构立场**：**部分接受**。PM 的判据 `change_rate!=null` 不严谨——官方净值已回填但当日估值为空的持仓，其 `market_value` 可由 `nav.official_nav` 得出（`mv_source=nav`），却可能因 `change_rate` 口径不同被误剔。判据应改为 **`market_value != null`**。另，纯 (a) 会让"总资产"丢失未知行的钱、纯 (b) 又不动 `total_value` 定义；两者合并且显式化。
- **最终结论**：**部分采纳**（架构改动 PM 判据）。
  - `market_value`：无估值且无官方净值时 **null**（`mv_source=null`），**禁止**成本价回退；新增 `fallback_value`（= 该行 `cost_amount`，否则 0）。
  - 09 §6.2.1 `HoldingsSummary`：新增 `fallback_value` / `total_value_with_fallback` / `covered_cost_amount`；`total_value` 只含 `market_value!=null` 行（与明细误差=0，满足 F-01）；`total_pnl_amt`/`return_rate` 同步改用 `covered_cost_amount`；`coverage_note` 必须含"可信覆盖 N/M"+"另有 X 元未知行按成本计"两段。
  - 07 §5.2：`fallback_value` **分列**展示，禁混入市值列或 `total_value`。

#### 2.3 A-03 · 组合层 0.52 阈值与最小覆盖门槛

- **PM 立场**：组合 `direction=weighted_p>0.52→up`，无最小覆盖门槛；22 只仅 1 只开口、`coverage_ratio≈0.04` 也出"涨"。要求新增 `min_coverage_ratio`/`min_open_count`，未达门槛强制 gray + "覆盖不足"，并把 0.52 标注为架构口径；`tier_excluded` 措辞修正。
- **架构立场**：**部分接受**。门槛必要，但有两处要改 PM 方案：(1) 门槛**不能做成 API 参数**，否则用户可把保护调松——应为**冻结常量**（与 DDSM 参数同级，改须重走六关）；(2) 组合阈值**不换数值**，0.52 在概率尺度上与单资产一致，换一个数反而无依据；正确处理是**标注来源** `threshold_source=architecture`（Brief §5.1 只定义单资产出口）。
- **最终结论**：**部分采纳**。
  - 09 §5.7/§5.14 冻结常量 `min_coverage_ratio=0.30`、`min_open_count=3`；`coverage_threshold_met`；`direction` 需同时满足出口、门槛、窗口已验证；`direction_reason`（`no_open`/`insufficient_coverage`/`window_unvalidated`）+ `weighted_p_threshold=0.5200`；`tier_excluded` 改为"含组合中实际存在的 C/D 档"。
  - 08 §5 伪代码写入门槛；07 §5.4 卡片规则；05 4.1 不确定性"确定→待验证"。
  - 口径说明：门槛 0.30/3 为架构口径，Brief 未规定组合阈值，已登记复议条件（见 §5 残留）。

#### 2.4 A-04 · T+3/T+15 无 Brief 依据却同构输出方向

- **PM 立场**：Brief §5.1 只定义完整出口链，未定义 T+3「仅触发做多」/T+15「门+DDSM」；契约三窗口返回同构 `direction` 且同样以 0.52 出 `up`，`p` 口径为空。要求增 `validated:bool`+`formula_source`，未过走前 CV 与 placebo≥2pp 前不得显示 `up`，并补齐 `p` 定义。
- **架构立场**：**部分接受**。同意"未验证不得显示 up"与字段，但拒绝"未验证即完全不产出"：三窗口是 Brief §0/§3.1 与 PRD F-13 明示的产品范围，整块删掉是范围违约。正确做法是"生产不表态、观察留痕"——未验证窗口 `direction` 恒 gray，名义方向/概率另放 `provisional_*` 仅引擎页可见。另，**T+1 是 Brief §5.1 直接授权的完整链，不应被 `validated` 误伤**，标 `validation_status=brief_mandated`。并指出：PRD F-06 第 5 条"按 Brief §5.1"是 **PM/PRD 的引注错误**（Brief 无此内容），责任在 PRD 侧，登记 PRD v2 待修（架构不改 PRD）。
- **最终结论**：**部分采纳**。
  - 09 §5.5 `WindowResult` 增 `formula_source`（`brief_5.1`/`arch_baseline_v1`）、`validation_status`（`brief_mandated`/`validated`/`pending_cv`/`failed`）、`validated`、`provisional_direction`、`provisional_p`；`direction` 仅在 `validation_status ∈ {brief_mandated, validated}` 且出口成立时可为 `up`。
  - `p` 定死：T1 = DDSM 收缩 P；**T3 = null**（`gate_only` 无概率，禁后端自造）；T15 = DDSM 收缩 P（H=15 标签）。
  - 08 §4.5 定式表补"来源"与"p 口径"两列；07 §5.4 未验证窗口走"观察"样式，`provisional_*` 不进卡片；05 3.5 更新。

#### 2.5 A-05 · 双否决数据缺失时不否决

- **PM 立场**：KLOW2 `high==low` 视为缺失→不否决，等于最该保守处乐观；应显式降级（gray/abstain 并标注缺失，或链路第④步标 `missing` 不视为通过）。并要求 08 §4.3 钉死：`ddsm_state`/`p_up` 用真实档位，加噪副本只用于训练。
- **架构立场**：**全盘接受并取更严者**。PM 给的是"二选一"，架构师选**并集**：缺失不仅标注，而是**直接弃权**——只要任一否决层 `missing`，`signal=abstain` 且 `reason=veto_data_missing`，因为"读不到的否决"不能当作"没否决"。这比 PM 的最低要求更保守，符合 R-04「未知≠持平」。
- **最终结论**：**采纳并强化**。
  - 09 §1.3 新增枚举 `veto_layer_status`（pass/veto/missing）与 `signal_reason.veto_data_missing`；§5.4 增 `veto_crowd_status`/`veto_klow2_status`，`signal` 规则加"任一 missing→abstain"；§6.4 链路该步 `status=missing`（禁记 off）。
  - 08 §4.4 伪代码改写；§4.3 钉死 `train_cell_noised`（仅训练）vs `real_cell`（出值/台账）。

#### 2.6 A-06 · 引擎离线被编码进"空态"

- **PM 立场**：`/predictions`、`/portfolio/forecast` 在 `E_ENGINE_OFFLINE` 时返回空集合不报 500，前端渲染 `empty`（"今日无信号"），把故障伪装成常态。要求返回 `ok=false`+`E_ENGINE_OFFLINE`，或 payload 带 `engine_status=offline` 供前端进 error；禁止 empty 承载故障。
- **架构立场**：**核心采纳，机制修正**。禁止 empty 承载故障是对的；但 PM 的"一律 `ok=false`"会把**可用的旧快照**一起丢掉，违反"离线可看、保留缓存 + 明确陈旧提示"的系统边界。应区分三种情况：有当日快照（可能真的无开口）→ `ok=true`+`empty`（常态）；只有旧快照 → `ok=true`+`as_of=旧日期`+`engine_status=offline`→前端**陈旧态**（既不 empty 也不 error）；完全无快照 → `ok=false`+`E_ENGINE_OFFLINE`→**error 态**。
- **最终结论**：**部分采纳**。
  - 09 §6.4/§6.5 `data` 增 `engine_status`，并写死三态返回；`empty` 仅保留给"引擎已跑且无开口"。
  - 06 §4.2 失败矩阵"引擎未运行"行改为三态描述；§7.4 估值同理。
  - 07 §4 四态新增"success+陈旧"行；`empty` 前置条件加 `engine_status ∈ {online, running}`。

### 3. 实质分歧与双向让步（反橡皮图章证据）

| # | 分歧点 | 架构师未照单全收之处 | 架构师的让步 | PM 的让步 |
|---|---|---|---|---|
| D1 | A-02 汇总判据 | 拒绝用 `change_rate` 判定可信行；拒绝把成本价留在 `market_value` | 接受"总资产不得悄悄含成本"，新增 `fallback_value`/`total_value_with_fallback` | 接受判据改 `market_value!=null`；接受 `total_pnl_amt` 改用 `covered_cost_amount` |
| D2 | A-03 门槛形式与阈值 | 门槛必须**冻结常量**非 API 参数；0.52 **不换数值**只标来源 | 接受新增最小覆盖门槛与 `direction_reason` 文案 | 接受门槛不可经 API 调松；接受 0.52 保留但标 `threshold_source` |
| D3 | A-04 未验证窗口处置 | 拒绝"未验证即不产出"（范围违约）；T+1 不得被误伤 | 接受"未过 CV+placebo 前生产方向恒 gray" | 接受保留 `provisional_*` 观察层；承认 PRD F-06 引注错误 |
| D4 | A-06 离线返回码 | 拒绝"一律 `ok=false`"（丢旧快照） | 接受"禁止 empty 承载故障"硬规则 | 接受有旧快照时走陈旧态；接受无快照才 error |

> 双向让步补充：A-01 中 PM 接受追加键由 `(date,code,mode)` 改为 `(date,code,written_at)`，避免同 mode 重复；A-05 中 PM 接受"缺失即弃权"比其原提"仅标注"更严。

### 4. PM 会签背书项复核（这些不是分歧，但已逐项验证仍成立）

- 覆盖市值占比字段（`coverage_ratio/coverage_value/excluded_ratio`）与"灰分子分母同剔"仍成立（唯门槛见 A-03）。
- 估值/净值字段分离、徽章由 `valuation_mode` 唯一驱动仍成立（唯快照见 A-01）。
- DDSM/双否决主参数与 Brief §5.1 逐项一致仍成立（唯缺失处理见 A-05）。
- T+3/T+15 基线 `pending` 处理仍成立（`baseline_rate/delta_pp=null`，禁填估计值）。
- 「未知≠持平」在契约可判定仍成立（`change_rate=null` 阻断 `+0.00%`）。
- 以上 5 项在 v2 修订后**未被破坏**，仅在其未覆盖的边界上补了规则。

### 5. PM 会签结论与门禁建议

- **PM 会签意见**：PM 在 `10-arch-review-pm.md` 给出 6 条挑刺、建议 G-AR-06 `CONCERN`（A-01/A-03/A-06 为 Brief §4 相邻项）。本轮 architect 逐条裁定并落 v2 后，PM 的三项高危（A-01 可追溯、A-03 覆盖门槛、A-06 故障不伪装）均已被**字段级**修复，CONCERN 的触发条件消除。
- **architect 会签意见**：接受 PM 的实体判断，在 D1~D4 四处保留架构口径分歧并已写明理由；v2 定稿。
- **门禁建议**：G-AR-06 → **PASS**（最终判定权在 orchestrator；若 orchestrator 认为 D1~D4 不成立，可按 v3 退回，不影响现有 v2 实现基线）。
- **签署**：architect ✓（2026-09-12）｜product-manager ✓（据本轮挑刺立场与让步达成）｜orchestrator 待判。

## 自验收

- [x] A-01~A-06 逐条记录「PM 立场 / 架构立场 / 最终结论」，无遗漏
- [x] ≥3 条实质分歧（实为 4 条：A-02/A-03/A-04/A-06），均有架构师反修正与双向让步
- [x] 每条裁定可执行，落到具体文档章节/字段名/枚举值（见 §1 总览"落地位置"列）
- [x] 修订已实际写入 05~09，并升版本 v2、旧版另存 `*-v1.md`
- [x] 字段名全 `snake_case`，未引入驼峰
- [x] 未写代码、未读 FundLens/ZCode、未改 `runtime/**`、未派发子任务
- [x] 无"双方无分歧"式橡皮图章表述；分歧与让步均可追溯

## 下游交接

- **主消费方**：`orchestrator`。需其执行：按 gate-rules.md G-AR-06 核验（纪要含实质分歧 + 结论影响 prd/设计），判定 PASS 并写 `gate-log.md`；若判 CONCERN 则登记 D1~D4 未决项。
- **次消费方**：`frontend-dev` / `backend-dev`（**按 v2 实现，勿用 v1**）。重点：A-01 估值 INSERT-ONLY、A-02 `fallback_value` 分列、A-03 覆盖门槛、A-04 未验证 gray、A-05 否决缺失弃权、A-06 离线三态。
- **`qa`**：将 A-01/A-03/A-05/A-06 转负向用例（同日覆盖、低覆盖出方向、否决缺失仍开口、离线伪装空态）。
- **`product-manager`**：需修 PRD v2 两处引注——F-06 第 5 条"按 Brief §5.1 与设计基准定式"（Brief 无此内容，应标架构口径）；`10-arch-review-pm.md` A-02 判据 `change_rate` 应改 `market_value`。
- **残留风险**：
  1. **T+3/T+15 未过走前 CV+placebo** → `direction` 恒 gray，`provisional_*` 仅观察；回测产出后 architect 升 `validated` 并版本 +1（责任人：architect，期限：S3 回测后）。
  2. **组合门槛 0.30/3 为架构口径** → 若回测显示误杀/误放，走 `10-arch-review` v2 复议（责任人：architect + product-manager，期限：S3）。
  3. **`valuation_history.jsonl` 增速** → 需归档策略（责任人：backend-dev，期限：S3）。
- **未覆盖**：PRD/UI 文本本身的修订（归 PM）；测试用例设计（归 qa）。
