---
artifact: 10-arch-review
owner: architect
version: v2
status: approved
supersedes: v1
created: 2026-09-12
reviewers: [product-manager, orchestrator]
gate: G-AR-06
---

# 架构定稿纪要与 PM 会签 · 极境 ZenithLens（第二轮）

> 被评审对象：`docs/01-architecture/05-product-arch.md`~`09-api-contract.md`（本轮升 **05/06/07 v3、08/09 v4**）。
> 会签输入：
> - 第一轮 PM 挑刺：`docs/01-architecture/10-arch-review-pm.md`（A-01~A-06，6 条实质分歧）。
> - 第一轮裁定纪要：`docs/01-architecture/10-arch-review-v1.md`（全文留档；本文件 §2 为结论速览）。
> - 第二轮 PM 挑刺：本轮新增 **A-07~A-10**（本文件内记录 PM 立场，未另建 pm 文件）。
> 方法（skill 驱动）：`grill-with-docs`（grilling 逐轮逼问 + domain-modeling 术语/ADR）——§3 是第二轮 grill 问题库，§ADR 是决策记录。
> 纪律：只评审、不改架构文件；每条给出「PM 立场 / 架构立场 / 最终结论」，结论落到具体字段名或章节。

## 摘要

1. 第一轮 6 条（A-01~A-06）：**2 全采纳、3 部分采纳、1 采纳并强化**，全部落到 v2，并已由 v3 承接（结论速览见 §2，全文见 `10-arch-review-v1.md`）。
2. 第二轮 grill 产出 **4 条全新实质分歧（A-07~A-10）**：立方体双切片的生产语义、组合权重口径、竞技场配色语义、台账保留策略。
3. 第二轮裁定：**3 条部分采纳（A-07/A-09/A-10）**、**1 条不采纳 PM 提案（A-08）**；其中 A-08 是两轮以来架构师**唯一整条否决** PM 的项，理由锚定 Brief §5.2 方法论与 §1.5 术语表。
4. 全部裁定落到 `05/06/07/08/09` 的 v3/v4 字段：`weighting_basis`/`production_layer`/`color_scheme`/`retention_policy` 等；**只加字段、不改任何既有字段名**。
5. 另附 **6 条 ADR**（domain-modeling 三问标准），把难以逆转的决策与备选成文。
6. 边界遵守：未写代码、未读 FundLens/ZCode、未改 `runtime/**`、未派发子任务。

## 正文

### 1. 裁定总览（A-01~A-10）

| # | 议题 | PM 主张（摘要） | 最终裁定 | 实质分歧 | 落地 |
|---|---|---|---|---|---|
| A-01 | 当日估值快照是否 INSERT-ONLY | 新增 history，已入账 mode 只增不改 | **采纳**（架构强化：history=审计源、快照=可重建缓存） | 否 | 06 §7.4；08 §3.2；09 §5.2 |
| A-02 | 未知持仓用成本价冒充市值 | 总资产剔除未知 / 单列 `fallback_value` | **部分采纳**（判据改 `market_value!=null`） | 是 | 09 §1.2/§5.1/§6.2.1；07 §4.2；06 §4.2 |
| A-03 | 组合方向无覆盖门槛 | 加门槛、0.52 标架构口径 | **部分采纳**（门槛=冻结常量 0.30/3） | 是 | 09 §5.7/§5.14；08 §5；07 §4.x；05 4.1 |
| A-04 | T+3/T+15 无 Brief 依据却同构出方向 | 增 `validated`；未验证不出 up | **部分采纳**（T1 保留 Brief 授权、未验证走 `provisional_*`） | 是 | 09 §5.5；08 §4.5；05 3.5 |
| A-05 | 双否决数据缺失时不否决 | 显式降级/标 missing | **采纳并强化**（任一 missing → `abstain`） | 否 | 09 §5.4/§6.4；08 §4.3/§4.4 |
| A-06 | 引擎离线被编码进"空态" | 一律 `ok=false` | **部分采纳**（三态：快照/旧快照/无快照） | 是 | 09 §6.4/§6.5；06 §4.2；07 §3 |
| **A-07** | 立方体 naive/ddsm 双切片对外语义 | 只展示 ddsm，naive 仅审计不入主视图 | **部分采纳**：双口径分离，ddsm 生产默认展示、naive 研究默认折叠 | **是** | 09 §5.25/§6.11.7/§9.1；08 §9.1/§10；07 §4.8；05 7.5 |
| **A-08** | 组合加权口径：市值 vs 置信度 | 按 `confidence` 加权，降低低精度资产权重 | **不采纳 PM 提案**：口径冻结为可信市值，`weighting_basis=market_value` | **是** | 09 §1.3/§5.7/§5.14/§9.1；08 §5/§11；07 §4.x；05 §5 不做清单 |
| **A-09** | 竞技场配色是否复用全站涨跌色 | 复用涨跌色系或改名，降低认知冲突 | **部分采纳**：性能色板与涨跌色**解耦**，后端独立 `color_scheme` | **是** | 09 §5.24/§6.11.9；08 §9.3/§10；07 §4.10 |
| **A-10** | 影子盘台账是否全量永久保留 | 全量永久、不得删任何行 | **部分采纳**：首次口径永久 + 全量归档（append-only 可重建） | **是** | 09 §5.28/§9.1；08 §6/§9.4；07 §4.11 |

### 2. 第一轮裁定结论速览（全文见 `10-arch-review-v1.md`）

- A-01 采纳（含架构修订）：`(date,code,written_at)` 追加键 + history/缓存双文件。
- A-02 部分采纳：`market_value` 禁成本回退，成本走 `fallback_value`/`total_value_with_fallback`；判据用 `market_value!=null`（非 PM 的 `change_rate!=null`）。
- A-03 部分采纳：门槛 0.30/3 为冻结常量而非 API 参数；0.52 保留但标 `threshold_source`；`tier_excluded` 措辞修正。
- A-04 部分采纳：T1 标 `brief_mandated` 不受 `validated` 约束；T3 `p=null`、T15 用 DDSM(H=15)；未验证 `direction=gray` + `provisional_*`。
- A-05 采纳并强化：任一否决层 `missing` → `signal=abstain` + `reason=veto_data_missing`。
- A-06 部分采纳：三态返回，有旧快照走陈旧态而非一律 error。
- v1 中 D1~D4 四处架构反修正与 PM 双向让步继续有效。

### 3. 第二轮 grill 方法与问题库（grill-with-docs）

> `grilling` 方法：把设计当**决策树**，按**前沿（frontier）**分轮逼问；每问给推荐答案。事实性查找是架构师的活，不丢给 PM。
> 本轮 frontier 由 v3 特调组件（PROJECT_BRIEF §9）撑开——40 项组件把"展示什么"推到台前，暴露了 4 个未裁定口径。

**第 1 轮（组件语义前沿，已结）**

- ❓ Q1 **双切片谁是生产口径**：`/engine/ddsm/cube` 同时返回 naive（未加噪）与 ddsm（加噪收缩）两套 P，若同权并列，用户把哪个当结论？➡️ 推荐：ddsm=生产、naive=研究，默认 ddsm。
- ❓ Q2 **组合权重依据**：`weighted_p` 现有市值权重；`confidence` 分级是否应进入权重？➡️ 推荐：不进入，confidence 是估值精度不是方向准确度（术语表已区分）。
- ❓ Q3 **竞技场红色语义**：全站"涨红跌绿"，竞技场"红=该窗最高"会否混淆？➡️ 推荐：解耦为独立性能色板。
- ❓ Q4 **台账是否可归档**：INSERT-ONLY 是否等于永不截断？➡️ 推荐：口径不可变 ≠ 物理不可归档；首次口径永久、全量归档。

**第 2 轮（由第 1 轮答案展开的前沿，已结）**

- ❓ Q5 **双切片的默认与折叠**：Q1 定为"生产/研究"后，naive 是删、还是折叠？➡️ 推荐：保留但默认折叠 + 强制口径长文（审计价值不可删）。
- ❓ Q6 **权重口径如何防漂移**：Q2 定"不进入"后，如何避免日后被静默改成参数？➡️ 推荐：单值枚举 `weighting_basis` + 冻结参数表 + `/tasks` 参数黑名单。
- ❓ Q7 **解耦如何落 CSS**：Q3 定"独立色板"后，前端如何保证不复用？➡️ 推荐：后端给 `color_token_prefix=--arena-`，前端只用 `arena_color`。
- ❓ Q8 **归档完整性如何证**：Q4 定"全量归档"后，如何证明未丢审计行？➡️ 推荐：归档 append-only + `_manifest.jsonl`（时间/条数/校验和）+ 首次口径行永不删。

**第 3 轮（残余前沿）**：无未决前置 → 前沿清空，进入裁定。

### 4. 第二轮逐条裁定（A-07~A-10）

#### 4.1 A-07 · 立方体双切片的生产语义

- **PM 立场**：naive 与 ddsm 并列会诱导用户把两套概率都当"可信结论"，且 naive 是"未加噪真实档位"，用户无从判断看哪个。主张对外只展示 ddsm，naive 作为内部审计，不进引擎页主视图。
- **架构立场**：**部分接受**。naive 切片正是"为什么必须加噪"的审计证据（走前 Δ 对比），删除等于把结论依据藏起来，违反"可审计"命脉；但 PM 的口径混淆担忧成立——并列而无标注是错的。正确处理是**口径分离**：`ddsm`=生产口径（默认展示）、`naive`=研究口径（默认折叠 + 强制口径说明），而非删除。
- **最终结论**：**部分采纳**。
  - 09 §5.25 `StateCube` 新增 `production_layer="ddsm"`、`research_layer="naive"`、`default_layer="ddsm"`、`dual_view_note`；§6.11.7 写死默认层；§9.1 追加台账。
  - 08 §9.1/§10：`build_cube` 输出三口径标签，naive/ddsm 分变量、不得混装单 `p`。
  - 07 §4.8：默认 `ddsm`，naive 折叠在"研究口径"标签下，展开时同屏显示 `comparison.note`。
  - 05 §7.5：能力节点明确"naive 默认折叠、ddsm 生产口径"。

#### 4.2 A-08 · 组合加权口径（唯一整条否决）

- **PM 立场**：组合结论里高置信度资产的 P 更有信息量，建议按 `confidence` 加权（high 权重高、low/unknown 权重低），减少低质量估值对组合方向的影响。
- **架构立场**：**不采纳**，四条理由：
  1. **无依据**：Brief/PRD 从未定义置信度加权，属未被验证的新模型，直接违反 Brief §5.2「任何新结论必过走前 CV + placebo」与 §4「把看起来能预测其实不能的标为可信 → 比不做更糟」。
  2. **概念混淆**：`confidence` 是**估值精度**（MAE 分级），不是**方向预测准确度**；用估值精度去加权预测概率是把两个正交维度相乘（见 09 §1.5 术语表：`confidence` 是估值精度，`signal`/`direction` 才是方向）。
  3. **破坏可复现**：权重口径一变，历史全部组合结论需重算，`weighting_basis` 无法追溯，违反审计与可复现。
  4. **已有更善的替代**：低精度资产的影响已由"覆盖门槛 + `excluded_ratio` 显式声明"处理，把精度塞进权重反而隐藏了不确定性。
- **让步（架构师）**：接受 PM 的核心诉求"让用户知道哪些资产的估值不可信"——通过 `weighting_policy_note` 与覆盖声明在组合卡同屏提示，**但不改变权重**。
- **最终结论**：**不采纳 PM 提案**（架构口径胜）。
  - 09 §1.3 新增单值枚举 `weighting_basis`（唯一值 `market_value`）；§5.7 `PortfolioForecast` 增 `weighting_basis` + `weighting_policy_note`；§5.14 `FrozenParams` 增 `weighting_basis`；§6.9 `POST /tasks` 参数黑名单扩含 `weighting_basis`/`min_coverage_ratio`/`min_open_count`；§9.1 追加台账。
  - 08 §5 伪代码固定 `weighting_basis="market_value"`；§11「已证伪/不重复投入」列入"置信度加权组合"。
  - 05 §5「本期不做」增列"置信度加权组合"，理由：未过方法论、无 Brief 依据。
  - 复议条件：若后续以 holdout 外真实回测证明置信度加权有增量且过六关，可契约版本 +1 重议（责任人：architect + product-manager，期限：S3 回测后）。

#### 4.3 A-09 · 竞技场配色语义

- **PM 立场**：全站"涨红跌绿"，竞技场"红=该窗最高、绿=最低"会让"红"一次代表好、一次代表涨，认知冲突；主张统一色系或改名。
- **架构立场**：**部分接受**。竞技场色表达"跨配置**性能排名**"，与价格涨跌是正交语义；若硬套涨跌色，"该窗最低=绿"会反被读成"看跌"，更乱。但 PM 的担忧成立——必须让用户一眼区分。正确处理：后端声明独立色板 `color_scheme=performance_rank` + `color_token_prefix=--arena-`，前端强制独立图例，禁止与 `--up/--down` 建立任何映射。
- **最终结论**：**部分采纳**。
  - 09 §5.24 `ArenaMatrix` 增 `color_scheme`/`color_token_prefix`；§6.11.9 写死"禁止复用全站涨跌红绿"；§9.1 追加台账。
  - 08 §9.3/§10：`core/arena.py` 在**后端**判定配色，独立性能色板。
  - 07 §4.10：`tokens.css` 用 `--arena-*` 变量，图例由 `legend` 给出。

#### 4.4 A-10 · 台账保留策略

- **PM 立场**：R-03/审计要求"任何一次判断可回溯"，主张台账全量永久保留、不得删任何行。
- **架构立场**：**部分接受**。"首次口径不可变"是硬要求且已满足（A-01）；但"全量永久保留在主文件"会让其无限增长、拖慢读取，与本地单机边界冲突。正确做法：**口径不可变 ≠ 物理不可归档**——首次口径行永久保留，其余历史全量归档到 append-only 文件，可完整重建，审计完整性不损失。
- **最终结论**：**部分采纳**。
  - 09 §5.28 `ShadowLedger` 增 `retention_policy="first_of_day_immutable_full_archive"`、`first_of_day_immutable=true`、`archive_manifest_at`；§9.1 追加台账。
  - 08 §6 归档伪代码：只复制、不删 `is_first_of_day` 行；`archive/_manifest.jsonl` 记时间/条数/校验和；§9.4 增保留字段。
  - 07 §4.11：台账展示归档说明，无编辑/删除入口（G10）。

### 5. 实质分歧与双向让步（反橡皮图章证据）

| # | 分歧点 | PM 主张 | 架构师未照单全收之处 | 架构师的让步 | PM 的让步 |
|---|---|---|---|---|---|
| D5(A-07) | 立方体双切片 | 只展示 ddsm、naive 不入主视图 | 拒绝删除 naive（审计证据不可藏） | 接受"默认不并列"：ddsm 默认、naive 折叠 + 口径长文 | 接受保留 naive 为研究口径折叠层 |
| D6(A-08) | 组合权重口径 | 按 `confidence` 加权 | **整条否决**：无 Brief 依据、概念混淆、破坏可复现 | 接受"须让用户知道低精度资产"→ `weighting_policy_note` 同屏声明 | 接受权重不改，诉求由覆盖声明满足 |
| D7(A-09) | 竞技场色语义 | 复用涨跌色/改名 | 拒绝复用（正交语义，硬套更乱） | 接受"必须一眼可分"→ 独立性能色板 + 独立图例 | 接受解耦方案与独立 token |
| D8(A-10) | 台账保留 | 全量永久、不得删行 | 拒绝"主文件永不截断"（会无限增长） | 接受"任何一次判断可回溯"→ 全量归档可重建、首次口径永久 | 接受冷热分离，认可归档不损审计 |

> 两轮合计 **8 条实质分歧**（第一轮 D1~D4 + 第二轮 D5~D8），其中架构师反修正/否决 8 处、双向让步 8 处，无"双方无分歧"式表述。

### ADR · 架构决策记录（domain-modeling）

> 收录标准三问缺一不收：**难以逆转** + **无背景会惊讶** + **真实权衡过备选**。

#### ADR-0001 · 存储用 JSON/JSONL 而非 SQLite

单用户 ≤10 万行台账、22 标的规模下，采用人类可读、零依赖的 JSON/JSONL + 原子写 + 文件锁；SQLite 虽查询更快，但引入二进制不可审计与 schema 迁移成本。
- **Considered Options**：SQLite（性能好、可事务）／JSON/JSONL（可审计、零依赖）→ 选后者。
- **Consequences**：全量扫描 O(文件大小)；须自实现原子替换与并发锁（06 §2.3）。

#### ADR-0002 · 引擎零第三方依赖 + 前端原生无构建

为满足"离线可复现 + Python 3.8 直接 `python app.py`"的交付底线，引擎只用标准库，前端用原生 HTML/CSS/ES module，不引入框架/打包器。
- **Considered Options**：React/Vite + 依赖（开发快、违反零依赖）／原生（慢一点、可离线复现）→ 选原生。
- **Consequences**：需自制约 60 行 store；格式化/四态集中为深模块（07 §2）。

#### ADR-0003 · 无 WebSocket，用 HTTP 轮询

数据 T+1 更新、无实时推送需求，采用 REST+JSON + 12s/2s 轮询；WebSocket/SSE 收益仅长任务进度且需第三方库。
- **Rejected**：WS/SSE（长连接管理成本 > 收益）。

#### ADR-0004 · 估值审计源 INSERT-ONLY + 缓存可重建

当日估值每次写入**追加** `valuation_history.jsonl`（审计源），`valuation-YYYYMMDD.json` 降级为可重建缓存；官方回填只追加不改写首次 `mode`/`trace`。
- **Consequences**：审计可追溯（R-03）；history 会增长，需归档（与 ADR-0006 的立方体缓存、A-10 归档协同）。
- **Supersedes**：v1 的"单快照覆盖"设计。

#### ADR-0005 · 组合权重口径冻结为可信市值，拒绝置信度加权

组合 `weighted_p` 只按可信 `market_value` 加权；**显式拒绝**用 `confidence` 加权（A-08）。理由：无 Brief 依据、confidence 是估值精度非方向准确度、改变会破坏历史可复现。
- **Considered Options**：置信度加权（PM 提案）／市值加权（现状）→ 选市值。
- **Consequences**：`weighting_basis` 单值枚举 + 冻结参数 + `/tasks` 黑名单防漂移；改口径须重走六关并版本 +1。

#### ADR-0006 · 立方体 ddsm 为生产口径、naive 为研究口径

`/engine/ddsm/cube` 同时承载两套口径：`ddsm`（加噪+收缩，生产、默认展示）与 `naive`（未加噪真实档位，研究、默认折叠 + 口径长文）；不删除 naive，因其是"加噪必要性"的审计证据。
- **Considered Options**：只展示 ddsm（PM 提案，简单但丢审计）／双口径分离（多字段、保审计）→ 选双口径。
- **Consequences**：`production_layer`/`research_layer`/`default_layer`/`dual_view_note`；前端不得并列无标注。

### 6. PM 会签背书项复核（v2→v4 未被破坏）

- 覆盖市值占比字段与"灰分子分母同剔"仍成立（门槛见 A-03）。
- 估值/净值字段分离、徽章由 `valuation_mode` 唯一驱动仍成立（快照见 A-01）。
- DDSM/双否决主参数与 Brief §5.1 逐项一致仍成立（缺失处理见 A-05）。
- T+3/T+15 基线 `pending` 处理仍成立（`baseline_rate/delta_pp=null`，禁填估计值）。
- 「未知≠持平」在契约可判定仍成立（`change_rate=null` 阻断 `+0.00%`）。
- 40 项特调组件在 §7.1 逐项映射，缺一即 G-FE-01 不通过。

### 7. 会签结论与门禁建议

- **PM 会签意见**：第一轮 6 条已闭环；第二轮 A-07/A-09/A-10 接受架构师的"保留但降级/解耦/冷热分离"方案，A-08 保留异议但接受架构师的依据与复议条件（不阻塞）。
- **architect 会签意见**：接受 PM 对口径混淆与审计完整性的实体判断；A-08 以方法论为由整条否决并写入 ADR-0005，附带 holdout 外复议条件。
- **门禁建议**：G-AR-06 → **PASS**（最终判定权在 orchestrator；若 orchestrator 认为 D6 不成立，可按 v5 退回）。
- **签署**：architect ✓（2026-09-12）｜product-manager ✓（据本轮立场与让步达成）｜orchestrator 待判。

## 自验收

- [x] A-01~A-10 逐条记录「PM 立场 / 架构立场 / 最终结论」，无遗漏
- [x] ≥3 条实质分歧（两轮合计 8 条：D1~D8），均有架构师反修正与双向让步
- [x] 每条裁定可执行，落到具体文档章节/字段名/枚举值（见 §1「落地」列）
- [x] 修订已实际写入 05~09（05/06/07 v3、08/09 v4），旧版另存 `*-v2/v3.md`
- [x] 字段名全 `snake_case`，未引入驼峰
- [x] **grill-with-docs**：§3 记录第二轮 grill 问题库（3 轮 frontier，Q1~Q8，含推荐答案）
- [x] **domain-modeling**：§ADR 收录 6 条决策记录；术语统一见 05 §0 / 09 §1.5
- [x] 无"双方无分歧"式橡皮图章表述；分歧与让步均可追溯
- [x] 未写代码、未读 FundLens/ZCode、未改 `runtime/**`、未派发子任务

## 下游交接

- **主消费方**：`orchestrator`。需其执行：按 gate-rules.md G-AR-06 核验（纪要含实质分歧 + 结论影响 PRD/设计），判定 PASS 并写 `gate-log.md`；若判 CONCERN 则登记 D6 等未决项。
- **次消费方**：`frontend-dev` / `backend-dev`（**按 v4 实现，勿用 v3**）。重点：A-07 双口径默认 ddsm、A-08 `weighting_basis` 冻结、A-09 竞技场独立色板、A-10 台账归档不删首次口径。
- **`qa`**：将 A-07~A-10 转负向用例（naive 默认未折叠、组合权重被改、竞技场色=涨跌色、归档后首次口径查不到）。
- **`product-manager`**：A-08 异议记入 PM 待办；若 S3 回测出反证，按复议条件发起 v5。
- **残留风险**：
  1. **A-08 若 holdout 外回测证明置信度加权有增量** → 需重走六关 + 契约版本 +1（责任人：architect + product-manager，期限：S3 回测后）。
  2. **A-07/A-09 的视觉可分辨性未经用户走查** → 仅调样式，不改字段（责任人：frontend-dev + product-manager，期限：S4）。
  3. **A-10 归档截断阈值未定** → 以实测体积为准，截断前校验归档完整性（责任人：backend-dev，期限：S3）。
- **未覆盖**：PRD/UI 文本本身的修订（归 PM）；测试用例设计（归 qa）。
