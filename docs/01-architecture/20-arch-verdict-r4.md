---
artifact: 20-arch-verdict-r4
owner: architect
version: v1
status: approved
supersedes: —
created: 2026-09-12
task_id: OC-COV-ARCH2
project: zenithlens-oc
reviewers: [backend-dev, frontend-dev, qa, dev-lead, orchestrator]
gate: G-AR-05
---

# 架构裁定书 R4 · 极境 ZenithLens（覆盖度档位补全与主动基金持仓穿透）

> 触发：`14-api-impl-report.md` **v8** §0f「覆盖度档位补全 + 主动基金持仓穿透」（task OC-COV-BE）、§7 **V14/V15/V16**（字段只加不改，请求架构师升契约版本）。
> 依据：用户 2026-09-12 明确诉求——**D「暴露待定」占约 12/22，要求补全 fund→proxy 映射并对真·主动全市场基金做持仓穿透**；诚实优先（映射不到仍留 D、禁编造代理、穿透结果标「待验证」）。
> 产出：契约升 **v8**（`docs/01-architecture/09-api-contract.md`，旧版备份 `docs/01-architecture/09-api-contract-v7.md`）。
> 边界：**不改后端 `*.py`、不改 `static/**`、不改 `runtime/**`、不派发子任务**；本次只做契约同步、枚举钉死与口径登记。

## 摘要

1. 裁定三条：**V14**（`HoldingRow.penetration_trace`）→ **采纳收编**；**V15**（`CoveragePanel.no_proxy_count`/`penetrated_count`）→ **采纳收编**；**V16**（A/B/C/D 分档判据 + C 档可带 `proxy_code`）→ **采纳收编并销 v2 偏差 D2**。
2. 契约 v8 **只加字段 / 只加共享对象 / 只加枚举 / 只加分档判定表**；**未改名、未删字段、未改类型、未改语义**；旧版 v7 备份留档 `09-api-contract-v7.md`。
3. V14 落点：§5.1 `HoldingRow.penetration_trace`（object/null，键恒在）+ 新增共享对象 §5.38 `PenetrationTrace`/`PenetrationTopHolding`/`PenetrationBasket`/`PenetrationUnmapped`（元素键名穷举）。
4. V15 落点：§5.19 `CoveragePanel` 增 `no_proxy_count`（无代理只数，实测 0）/ `penetrated_count`（穿透补全只数，实测 2）；计数口径 `no_proxy_count + penetrated_count ≤ total_count`。
5. V16 落点：§5.19 新增「`coverage_tier` 分档判定表」（A 行业 ETF 直接 / B 代理已映射且可取日线 / C 拟用·近似或穿透得出待验证 / D 无映射且未穿透，命中顺序唯一确定）+ §1.3 v8 枚举 `penetration_method`/`penetration_status`；`penetration_trace.confidence` 复用既有 `confidence`（穿透仅 `low`/`unknown`）。
6. 实现对齐项（**非字段改名**，写入 §13.5）：**A1** `penetration_trace.status` 当前为中文自由文本，契约定为 `penetration_status` 枚举 + 兄弟字段 `status_label`，待 backend-dev 下一轮对齐；**A2** `penetration_trace.*_pct` 系列为百分数，与 §1.2 `*_pct` 小数约定不同，已在 §5.38 **显式登记为 v8 口径例外**。
7. 边界：本轮只收编上述三项；`covered_count` 口径（V3）、否决层 hit 语义（V8）、候选端点同步返回（V10）等**不在本次范围**，见 §4。

## 正文

### 1. 裁定总表

| 项 | 定性 | 裁定 | 契约落点 | 后端动作 | 前端动作 |
|---|---|---|---|---|---|
| V14 `HoldingRow` 缺 `penetration_trace` | 契约缺口 | **采纳收编** | §5.1 + §5.38（新增对象） | 无（已实现）；按 A1 补 `status` 枚举/`status_label` | 新增穿透行详情（带待验证角标） |
| V15 `CoveragePanel` 缺两计数 | 契约缺口 | **采纳收编** | §5.19 | 无（已实现） | 覆盖度头部可读两计数 |
| V16 分档判据 + C 档带代理未入契约 | 契约缺口（销 v2 D2） | **采纳收编** | §5.19 判定表 + §1.3 枚举 | 无（口径已实现） | 不改渲染（`tier` 语义不变） |

---

### 2. 裁定 1 · V14 —— `HoldingRow.penetration_trace`：**采纳收编**

#### 2.1 问题

`14-api-impl-report` v8 §0f：为压缩 D 档，新增深度模块 `proxy_map.py`，对**无静态代理的主动全市场基金**抓天天基金 F10 前十持仓，按「个股→行业 ETF」映射加权归集、取权重最高 ETF 为主代理；`fund_predict.build_holding_row` 逐行输出 `penetration_trace`（object/null）。实测 `025500` 前十映射权重 62.34% → 主代理 **半导体ETF `512480`**；`021528` 前十映射权重 72.31% → 主代理 **通信ETF `515880`**，均标「待验证」。但契约 v7 §5.1 `HoldingRow` 无该字段、亦无对应共享对象，若不同步则契约与唯一法律出现双份真相（G-BE-02 红线），且前端/后端/QA 对穿透结果的**待验证语义**无共同依据。

#### 2.2 两种立场与代价

| 立场 | 主张 | 收益 | 代价 |
|---|---|---|---|
| **A · 不改契约，穿透作实现细节** | 契约不收录，前端按需读原始 JSON | 契约零改动 | ① 穿透是**产品级覆盖度能力**（用户明确诉求），非实现细节；② 「待验证」是安全红线，不进契约则可能被下游当已验证代理消费；③ QA 无可断言口径 |
| **B · 采纳收编，新增共享对象 + 钉死待验证纪律（推荐）** | §5.1 增字段、§5.38 定义对象与元素键名、§1.3 增枚举 | ① 单一真相；② 待验证纪律成为法律；③ 元素键名穷举，前端不拼装、后端不自造 | 契约版本 +1（已执行）；需补一处后端对齐（`status` 枚举化，见 §5 A1） |

#### 2.3 结论

**选 B · 采纳收编。** 依据：
1. **属用户诉求级能力**（2026-09-12）：「补全 fund→proxy 映射 + 对真·主动全市场基金做持仓穿透」，必须进唯一法律。
2. **诚实性可被契约约束**：穿透主代理 `confidence` 仅 `low`/`unknown`、`status=pending_validation`，与 §1.5「覆盖度档/置信度」术语一致；把「未验证」写死，防止下游误用。
3. **元素键名穷举优于放任**：`top10[]`/`basket[]`/`unmapped[]` 元素若不入契约，前端各自解析必漂移；本次按后端实测形态（`rank/stock_code/stock_name/weight_pct/etf_code/etf_name/theme` 等）一次冻结。
4. **结构与 v5「冻结元素键名」先例一致**（§10.2 `FrozenParams`）：新增对象一次定义清楚，避免下一轮返工。

#### 2.4 对后端/前端的最小可执行规格

- **契约动作（本裁定书已执行，`09-api-contract.md` v8）**：
  1. §5.1 `HoldingRow` 增 `penetration_trace`（`PenetrationTrace`/null，键恒在；无穿透为 `null`）；
  2. 新增 §5.38 `PenetrationTrace` + `PenetrationTopHolding`/`PenetrationBasket`/`PenetrationUnmapped`，逐字段给类型/单位/精度/口径；
  3. §1.5 术语表增「持仓穿透 `penetration`」「主代理 `proxy`（穿透语境）」（含 Avoid）。
- **代码动作**：**无**（后端已输出该字段；前端按需消费）。**唯一对齐项见 §5 A1**（`status` 枚举化），属只加字段。
- **回归义务**：backend-dev 保持 `tests/test_proxy_map_contract.py` 12 条绿（v8 基线 **100/100**）；qa 按 §6 负向断言复核。

---

### 3. 裁定 2 · V15 —— `CoveragePanel` 两计数：**采纳收编**

#### 3.1 问题

`14-api-impl-report` v8 §0f：`app.h_holdings_coverage` 新增 `no_proxy_count`（`proxy_code` 为空只数，实测 0）/ `penetrated_count`（`penetration_trace != null` 只数，实测 2），供前端展示 D 档压缩进度。契约 v7 §5.19 `CoveragePanel` 无此两键，前端无法据契约读取 D 档是否真正压到 0。

#### 3.2 两种立场与代价

| 立场 | 主张 | 收益 | 代价 |
|---|---|---|---|
| **A · 不加，前端自行遍历 `/holdings` 统计** | 覆盖度接口保持精简 | 契约零改动 | ① 前端重复实现统计逻辑（双份真相）；② 「无代理 vs 穿透补全」语义无权威定义；③ 覆盖度接口自身无法自证 D 压缩 |
| **B · 收录两计数（推荐）** | §5.19 增两键并定义口径 | ① 覆盖度接口自洽自证；② 前端零拼装；③ QA 可断言 | 契约版本 +1（已执行） |

#### 3.3 结论

**选 B · 采纳收编。** 依据：两计数是**覆盖度能力的直接度量**，与 V14 同源；口径 `no_proxy_count + penetrated_count ≤ total_count`（穿透补全的持仓已带 `proxy_code`，不重复计）钉死，避免歧义；本期实测 `0 / 2` 与 `A2/B13/C7/D0` 一致，可交叉验证。

#### 3.4 对后端/前端的最小可执行规格

- **契约动作（已执行）**：§5.19 `CoveragePanel` 增 `no_proxy_count`（integer，只）/ `penetrated_count`（integer，只），含口径与本期实测值。
- **代码动作**：**无**（已实现）。
- **回归义务**：qa 按 §6 断言「两计数与逐行推导一致」。

---

### 4. 裁定 3 · V16 —— A/B/C/D 分档判据与 C 档可带代理：**采纳收编 + 销 v2 D2**

#### 4.1 问题

`14-api-impl-report` v8 §7 V16：本次把映射表从 10 只扩到 **20 只静态 + 2 只穿透**，`tier` 由 `A10/D12` 重分为 `A2/B13/C7/D0`；其中 **C 档 `proxy_code` 非 null**（拟用/近似或穿透主代理），仅 D 档为 null。契约 v7 §5.19 只有四档标签与 `action_hint` 文案，**未给出唯一判定条件**；v2 偏差 D2（代理映射未冻结）仍未销。若判据不入契约，同一持仓可能被不同实现落不同档（A 与 B 的边界、C 与 D 的边界）。

#### 4.2 两种立场与代价

| 立场 | 主张 | 收益 | 代价 |
|---|---|---|---|
| **A · 把 `PROXY_MAP` 逐条写进契约** | 契约冻结每只基金的代理与档位 | 「最精确」 | ① 映射表是**产品领域配置**、随行情/基金持仓变化，逐条进契约会高频改版；② 与「契约冻结结构、不冻结数据」原则冲突 |
| **B · 只冻结档位判据与纪律，映射表留在产品配置（推荐）** | §5.19 新增分档判定表 + `confidence` 纪律；映射表由 `proxy_map` 承载 | ① 判据唯一，实现/配置解耦；② 销 D2（映射口径已入契约，数据不进）；③ 未来增删映射不触发契约改版 | 需明确「映射表不在契约」的边界（已写入 §13.4/下游残留 17） |

#### 4.3 结论

**选 B · 采纳收编。** 依据：
1. **契约冻结「怎么分档」，不冻结「哪只基金融哪个 ETF」**：判据（A 行业 ETF 直接 / B 已映射且可取日线 / C 拟用·近似或穿透待验证 / D 无映射且未穿透）是结构，映射表是数据。
2. **销 v2 D2**：D2 的本质是「代理映射未在契约冻结」导致 A/B/C/D 无判据；本次以**判据 + 置信度纪律**收口，映射表作为产品配置由 `proxy_map` 维护，D2 可销。
3. **诚实性**：C 档「验证后可用」、D 档「穿透后可用」，与 `action_hint` 既有文案一致；禁止为提高覆盖率编造代理写入铁律。
4. **`confidence` 复用而非新增**：§1.3 已有 `confidence`（`high/mid/low/unknown`），穿透语境直接复用；仅对 `method`/`status` 新增 2 组枚举（穷举）。

#### 4.4 对后端/前端的最小可执行规格

- **契约动作（已执行）**：
  1. §5.19 新增「`coverage_tier` 分档判定表」+ 口径铁律 5 条（命中顺序唯一、禁编造代理、C 带代理、穿透必待验证、本期实测分档）；
  2. §1.3 增 v8 枚举 `penetration_method`（单值 `eastmoney_f10_top10_weighted`）/ `penetration_status`（`pending_validation`/`no_mapping`/`no_report`）；
  3. §1.5 术语表补两条；
  4. §13.4 明确「映射表 `PROXY_MAP`/`STOCK_ETF_MAP` 属产品领域配置，不逐条进契约」。
- **代码动作**：**无**（`tier` 语义与 `proxy_code` 规则已实现）。**唯一对齐项见 §5 A1**。
- **回归义务**：backend-dev 保持 `tests/test_proxy_map_contract.py` 12 条绿；qa 按 §6 断言分档边界（尤其未知码→D、穿透→C 待验证）。

---

### 5. 登记的实现对齐项与口径例外（写入契约 §13.5/§5.38）

| # | 契约形态 | v8 后端实测 | 定性 | 动作 |
|---|---|---|---|---|
| A1 | `penetration_trace.status` = enum `penetration_status`（snake_case）+ 兄弟 `status_label`（中文） | `status` 返回中文自由文本（`"待验证"` / `"无映射（待补充个股→ETF 映射）"`） | **枚举纪律不对齐**（§1.1 命名/§1.3 穷举） | backend-dev 下轮改为输出 enum token + `status_label`；**只加字段、不改** `top10`/`basket`/`proxy` 等既有键 |
| A2 | `penetration_trace.*.weight_pct`、`mapped_weight_pct` 单位 = 百分数（`8.31`=8.31%） | 已为百分数（`62.34`/`8.31`） | 与 §1.2 `*_pct`「小数 ×100」约定不同 | **契约侧显式登记为 v8 例外**（§5.38 尾注）；统一为 `*_ratio` 须版本 +1 并通知双边 |

> A1 不阻塞本轮放行：字段已存在、语义清晰（中文文案）；契约已给出目标形态与兄弟字段，属**只加字段**的对齐，不构成字段改名。

---

### 6. 本次未纳入 / 边界（防范围蔓延）

以下项在 v8 报告中提及，但**不属于**本轮 OC-COV-ARCH2「覆盖度穿透契约同步」范围，本次**不裁定**：

- **V3 `covered_count` 口径**（契约 §6.2.1 写 `market_value != null`，实现按 `change_rate != null`）：终验 P1 已改代码，契约文字同步属**另一次裁定**，本次不夹带（残留风险见契约 v8 下游 12）。
- **否决层 hit 语义（V8）/ 基线测试日集（V7）/ 候选端点同步返回（V10）/ 内置因子 id（V12）/ 因子账本路径（V13）**：均属因子治理轮（`20-arch-verdict-r3` 之后待收口项），与覆盖度穿透无关。
- **穿透主代理的走前验证**：本轮只登记「待验证」；是否把某只穿透代理升为 B（已验证）须另立验证裁定与版本 +1。
- **`STOCK_ETF_MAP` 的扩充**：属产品领域配置，不由契约逐条冻结。

## 自验收

- [x] 三条裁定均四段齐全（问题 / 两种立场与代价 / 结论 / 最小可执行规格：契约落点 + 代码动作 + 回归义务）——§2、§3、§4
- [x] V14 明确「待验证」为红线，`confidence` 仅 `low`/`unknown`，与 §1.5 术语一致——§2.3、§5.38
- [x] V15 口径 `no_proxy_count + penetrated_count ≤ total_count` 钉死，实测 0/2——§3.3
- [x] V16 分档判据入契约、映射表留产品配置、销 v2 D2——§4.3、§13.4
- [x] 契约升版走 +1（09 v8，supersedes v7），旧版另存 `09-api-contract-v7.md`——已执行
- [x] 字段类型/单位/精度/口径齐全（`penetration_trace` 全字段；`no_proxy_count`/`penetrated_count` integer）；元素键名穷举（`top10`/`basket`/`unmapped`）——§5.38
- [x] 枚举穷举：新增 `penetration_method`（单值）+ `penetration_status`（3 值）；`confidence` 复用不新增——§1.3
- [x] **只加不改**：未改任何既有字段名/类型/语义；仅新增字段/对象/枚举/判定表 + 登记一处单位例外（A2）——契约 §13.6
- [x] 数字带来源（`A10/B0/C0/D12`→`A2/B13/C7/D0`、`no_proxy_count=0`、`penetrated_count=2`、`025500→512480`、`021528→515880`、100/100）均注 `14-api-impl-report` v8 出处
- [x] 未修改任何 `.py`、未改 `static/**`、未改 `runtime/**`、未派发子任务——是

## 下游交接

- **主消费方 `backend-dev`（经主 Agent 转派）**：**无需改既有键**；按 §5 **A1** 把 `penetration_trace.status` 改为 enum `penetration_status` token 并补 `status_label`（只加字段），保持 `confidence ∈ {low, unknown}`、`status=pending_validation`；重跑 `python -m unittest discover -s tests -t .`（v8 基线 **100/100**）并回报。
- **次消费方 `frontend-dev`**：持仓页穿透行可读 `HoldingRow.penetration_trace`（前十 + `basket` 加权篮子 + `proxy` 主代理 + `status_label`「待验证」），**必须带待验证角标**，不得渲染为已验证代理；覆盖度头部可读 `no_proxy_count`/`penetrated_count`；`status` 走 `status_label`，**禁止硬编码中文**；`tier` 语义未变，既有渲染无需改。
- **次消费方 `qa`**：负向断言——映射不到/穿透不到的未知码必须 `tier=D`、`proxy_code=null`、`penetration_trace=null`；穿透得出必为 `tier=C`、`confidence != high/mid`、`status=pending_validation`；`no_proxy_count`/`penetrated_count` 与逐行推导一致；禁止出现「无映射却带代理」的持仓。
- **`dev-lead`**：G-BE-02 自本版起以 **`09-api-contract.md` v8** 为唯一法律复核；销项以本裁定书 §1 总表 + 契约 §13 为核对清单。
- **残留风险**：
  1. **A1 `status` 枚举化未落**：后端当前返回中文自由文本；契约已给目标形态，待下一轮对齐（责任人：backend-dev，期限：S3 收口）。不阻塞读取。
  2. **A2 单位例外**：`penetration_trace.*_pct` 为百分数，与 §1.2 不同；统一为小数须版本 +1 并通知双边（责任人：architect + backend-dev，期限：下一轮触达）。
  3. **穿透主代理未经走前验证**：`512480`/`515880` 等为 F10 前十加权推断，属真实持仓但**非已验证代理**；在升为 B 档前不得进组合加权（责任人：architect + backend-dev，期限：验证产出后）。
