---
artifact: 10-arch-review-pm
owner: product-manager
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [architect, orchestrator]
gate: G-AR-06
---

# 架构会签 · PM 挑刺意见 · 极境 ZenithLens

> 被评审对象：`docs/01-architecture/05-product-arch.md`、`06-system-arch.md`、`07-frontend-arch.md`、`08-backend-arch.md`、`09-api-contract.md`（v1，均 draft）。
> PM 依据：`docs/PROJECT_BRIEF.md`、`docs/00-charter/01-requirements.md`、`02-prd.md`、`03-ui-design.md`。
> 纪律：只评审、不改架构文件；每条给出「问题 / 依据 / PM 立场 / 建议结论」，结论落到具体字段名或章节。

## 摘要

1. 架构草案整体骨架可信（能力域分层、五档降级、组合三规则、INSERT-ONLY 均有落地），**但不是橡皮图章**：本报告提出 **6 条实质分歧**，其中 2 条触碰 Brief §4 失败定义。
2. 最严重的两条：**A-01 当日估值快照非 INSERT-ONLY**（同日刷新会覆盖已入账 mode，R-03 的"可追溯"落空）；**A-06 引擎离线被编码进"空态"**（故障被伪装成"今日无信号"）。
3. 其余四条分别指向：**未知持仓用成本价冒充市值**（A-02）、**低覆盖下组合输出"看涨"且 0.52 组合阈值无 Brief 依据**（A-03）、**T+3/T+15 弱定式与 T+1 同构呈现**（A-04）、**双否决数据缺失时不否决（放松保护）**（A-05）。
4. 结论倾向：A-01 / A-03 / A-06 应在 S2 定稿前修订契约，否则 G-AR-06 判 **CONCERN**（有条件放行）而非 PASS。
5. 已核查为"落实"的项也在 §7 列出，避免只吵架不给背书。

## 正文

### 1. A-01 ·「估值≠净值」字段分离做到了，但「当日来源不可改」没做到

- **问题**：契约用 `valuation.*`（今日预估）与 `nav.*`（官方已公布）两组独立字段，确实实现了"估值≠净值"的字段分离；但**没有实现"当日已入账的估值来源不可被后续刷新覆盖"**。`/valuations` 是实时计算并返回当前 mode，`06-system-arch §1` 的当日快照是**单文件** `data/snapshot/valuation-YYYYMMDD.json`。同一天内 14:00 返回 `intraday`、20:00 官方净值公布后同一接口返回 `official`，若快照按整文件覆盖写入，14:00 的 `mode` 与 `trace` 即丢失。
- **依据**：
  - `01-requirements.md` R-03 验收：「对同日同一基金，官方净值回填后不得改写当日已入账的估值记录来源」。
  - `09-api-contract.md §5.2`：`Valuation` 无 `updated_at`/版本字段，`trace` 每次请求实时返回。
  - `06-system-arch.md §1`、`§2.2`：估值快照为"当日快照 `valuation-YYYYMMDD.json`"单文件，无历史追加文件。
  - `08-backend-arch.md §3.2`：只声明"官方回填不改当日估值 mode"，未声明"同日多次刷新不覆盖已入账快照"。
- **PM 立场**：R-03 的卖点是"事后可追溯当时用的是哪一档"，不是"字段名不一样"。当前设计只在"官方回填"这一个动作上守住了，却挡不住盘中→盘后、或两次盘中刷新之间的覆盖。这落在 Brief §4「展示数字与后端不一致 / 不可追溯 → 失败」上。
- **建议结论**：契约与后端补充 **当日估值历史 INSERT-ONLY**——新增 `data/snapshot/valuation_history.jsonl`（或快照内加 `valuation_as_of_ts` 并按 `(date, code, mode)` 追加），并明确"当日已入账 mode 只增不改，读取默认取最新一条、徽章详情可回溯全部历史"。修订前此项挂 CONCERN。

### 2. A-02 · 未知持仓用成本价冒充市值，与 R-01「总资产=Σ(份额×最新估值)」冲突

- **问题**：`market_value` 在估值与官方净值都为 null 时**回退用成本价**并标 `mv_source=fallback`，而 `HoldingsSummary.total_value = Σ market_value`。于是"总资产"这个数字在无估值日会悄悄变成"成本合计"，却不进入 F-04 的未知态声明。
- **依据**：
  - `09-api-contract.md §5.1`：`market_value = shares × (valuation.estimated_nav ?? nav.official_nav)`；「两者皆无时用成本价并标 `mv_source=fallback`」。
  - `09-api-contract.md §6.2.1`：`total_value = Σ market_value`。
  - `01-requirements.md` R-01 验收：总资产 = `Σ(份额 × 最新估值)`，与逐行明细误差为 0。
  - `PROJECT_BRIEF.md` §4：「数字错误（收益率 / 市值 / 估值口径算错）→ 直接失败」。
- **PM 立场**：unknown 行按成本价进总资产，等于用一个**口径不同的数**填进"市值"列，且用户看不到这个切换。R-01 定义的是"最新估值"，没定义"估不出来就用成本"。
- **建议结论**：unknown 行**不得以成本价计入 `total_value`**。二选一请架构师定并写进契约：(a) 总资产只汇总 `change_rate != null` 的行，并同屏声明"仅覆盖 N/M 只"；或 (b) 单独返回 `fallback_value` 并在 UI 明确标注口径。当前写法应改。

### 3. A-03 · 组合层 `direction` 用 0.52 阈值且无最小覆盖门槛，低覆盖会输出"看涨"

- **问题**：组合 `PortfolioForecast.direction = weighted_p > 0.52 → up`，但契约**没有任何最小覆盖市值占比 / 最小开口数门槛**。当 22 只里仅 1 只开口、`coverage_ratio≈0.04` 时，只要该只 P 高，组合卡就显示"方向：涨"。
- **依据**：
  - `09-api-contract.md §5.7`：`direction`「`weighted_p > 0.52` → up，否则 gray」；`coverage_ratio` 仅作展示字段，未参与方向判定。
  - `01-requirements.md` R-09 验收：只要求"覆盖 <100% 时显式写其余 X% 不表态"，**未授权低覆盖下出方向**。
  - `PROJECT_BRIEF.md` §8：「宁可只覆盖少数资产但每个数字都 trustworthy，不要覆盖 100% 但一半是猜的」；§4「把看起来能预测其实不能的标为可信 → 比不做更糟」。
  - 口径存疑：Brief §5.1 的 `P > 0.52` 是**单资产出口阈值**，Brief 从未定义组合层的方向阈值，0.52 直接被搬到组合层属架构自定口径（`05-product-arch §4.1` 却标"确定"）。
- **PM 立场**：把 1 只的信号按市值加权后当"组合方向"发布，是把单只结论包装成组合结论，正是 Brief §4 定义的头号失败。覆盖占比写在一旁不等于免责。
- **建议结论**：契约新增组合门槛（如 `min_coverage_ratio` / `min_open_count`，做接口参数或冻结常量）；未达门槛时 `direction` 强制 `gray` 且文案"覆盖不足，不构成组合结论"。同时把组合 0.52 阈值标注为**架构口径**而非 Brief 口径。另 `§5.7 tier_excluded`「固定含 C/D」措辞有误，应为"含组合中实际存在的 C/D"。

### 4. A-04 · T+3「仅触发做多」/ T+15「门+DDSM」无 Brief 依据，却与 T+1 同构输出方向

- **问题**：三窗口用了三套不同定式（T+1 完整链 / T+3 仅触发 / T+15 门+DDSM），但契约对三窗口**返回同构的 `direction`(up/gray)**，且在 `PortfolioForecast.direction` 里同样以 0.52 输出 up，未标注验证强度差异。
- **依据**：
  - `PROJECT_BRIEF.md` §5.1：只定义完整出口链（E1/E3→DDSM→双否决→`P>0.52`），**未定义 T+3/T+15 的差异化定式**。
  - `08-backend-arch.md §4.5`：T+3「仅触发做多」、T+15「门 + DDSM」；`02-prd.md` F-06 第 5 条自称"按 Brief §5.1 与设计基准定式"，但 Brief §5.1 无此内容。
  - `09-api-contract.md §5.5`：`direction` 三窗口同构；`p` 对 T+3/T+15 只说"各自定式下 P"，**未给 T+3「仅触发」如何得出概率的定义**。
  - `PROJECT_BRIEF.md` §5.2：任何新结论必过走前 CV + placebo；§4「把不能预测的标为可信 → 更糟」。
- **PM 立场**：T+3 去掉双否决保护、T+15 去掉否决，都是**降低审计门槛**的弱规则，且 `p` 的计算口径在契约里是空的（后端只能自造）。用与 T+1 相同的方向色呈现，用户会以为三窗口同等可信。
- **建议结论**：契约对三窗口增加 `validated: bool` + `formula_source` 字段；T+3/T+15 在未过走前 CV 与 `placebo ≥ 2pp` 前，`direction` 不得显示 `up`，只显示"未验证/观察"；并补齐 T+3/T+15 的 `p` 计算定义，否则字段留空由后端自造即违规。

### 5. A-05 · 双否决「数据缺失时不否决」= 放松保护，与「未知≠持平」的诚实口径冲突

- **问题**：KLOW2 在 `high==low` 时"视为缺失 → 不否决并记数据缺失"；同时 `ddsm_state` 要求返回**未加噪真实档位**，但 08 §4.3 的训练伪代码把加噪副本 `add cell` 与出值 `obs[target_cell]` 混在同一段，未钉死"加噪只进训练、出值/台账用真实档位"。
- **依据**：
  - `08-backend-arch.md §4.4`：「`high==low` 时视为缺失→**不否决**并记数据缺失」。
  - `PROJECT_BRIEF.md` §5.1：KLOW2 为"下影线比，最不利 40% 否决"——缺失时本应无法判断"是否最不利"。
  - `09-api-contract.md §5.4`：`ddsm_state`「真实档位 `[r2档, om档, vr档]`」；`03-ui-design.md §4.2`、R-08 验收要求每步数值缺失显示"数据缺失"而非留空。
  - `01-requirements.md` R-04「未知≠持平」的精神：无数据不得沿默认方向解读。
- **PM 立场**：一只否决项"读不到"时默认放行，等于在最该保守的地方乐观。这与产品反复强调的诚实审计相悖；用户看到"弃权/开口"却不知道有一层否决因缺数据被跳过。
- **建议结论**：KLOW2 缺失时应**显式降级**——要么 `signal=gray/abstain` 并标注"某否决层数据缺失，未保护"，要么在链路第④步以 `missing` 状态明示且不视为通过。另请 08 §4.3 用文字钉死：`ddsm_state` 与 `p_up` 的 target 均为**真实档位**，加噪副本仅用于训练计数。

### 6. A-06 · 引擎离线被编码进「空态」，前端无法区分"今日无信号（常态）"与"引擎没跑（故障）"

- **问题**：`/predictions` 与 `/portfolio/forecast` 在 `E_ENGINE_OFFLINE` 时都"返回 `rows: []` / 空窗口 + `weighted_p=null`，**不报 500**"。前端据此把结果渲染成 `empty`（"今日无信号 / 今日无开口"），而真实原因是引擎未运行。
- **依据**：
  - `09-api-contract.md §6.4`：「`E_ENGINE_OFFLINE`（无当日快照且引擎未运行 → 返回 `rows: []` 并附 `as_of` 为空，不报 500）」。
  - `09-api-contract.md §6.5`：「`E_ENGINE_OFFLINE`（返回空窗口 + `weighted_p=null`，不报 500）」。
  - `03-ui-design.md §4.3`：信号页空态文案必须写明"今日无信号……**这是常态，不是故障**"。
  - `07-frontend-arch.md §4`：四态硬规则区分 `empty`（成功但集合空）与 `error`（请求失败）。
  - `PROJECT_BRIEF.md` §4：前端混淆/误导 → 失败。
- **PM 立场**：把"故障"折进"常态的 0"，用户会以为系统一切正常，实际预测根本没算。这正是产品要对抗的"伪装"。
- **建议结论**：引擎离线时 `/predictions`、`/portfolio/forecast` 应返回 `ok=false, error.code=E_ENGINE_OFFLINE`，或至少在 payload 携带 `engine_status=offline` 供前端区分并渲染 `error` 态"引擎未运行"；禁止用 `empty` 承载故障。修订前挂 CONCERN。

### 7. 已核查通过（作为会签背书，非橡皮图章）

- **覆盖市值占比字段已落实**：`09 §5.7` 同时返回 `weighted_p / coverage_ratio / coverage_value / excluded_ratio`，`08 §5` 加权分母取开口市值（灰从分子分母同剔，不以 0.5 计入），与 R-09 一致（唯门槛见 A-03）。
- **估值/净值字段分离与徽章由后端驱动**：`09 §5.2/§5.3` 两组字段独立，`valuation_mode` 唯一定义徽章文案，`trace` 只读不编造，与 R-02/R-03 字段面一致（唯快照见 A-01）。
- **DDSM/双否决主参数与 Brief §5.1 一致**：`[r2,om,vr]`×5 档=125、`K=4`、`p=0.25`、`SHRINK=10`、`MIN_N=15`、拥挤度 40% / KLOW2 40%、出口 `P>0.5+0.02`，逐项对齐（唯缺失处理见 A-05）。
- **T+3/T+15 基线 pending 处理诚实**：`baseline_status=pending` 时 `baseline_rate/delta_pp=null`，界面"待填充"且禁填估计值，`09 §5.8/§6.6` 与 R-10 一致（当心 A-04 的 direction 提前表态）。
- **未知≠持平在契约可判定**：`change_rate=null` / `today_pnl_amt=null` / `coverage_note` 齐备，`07 §5.2` 明确阻断 `Number(null)→0`，与 R-04 一致。

## 自验收

> 本工件为架构会签评审，非需求/PRD/UI 交付物；下表按角色契约 self-check 的**可适用性**勾选。

- [x] 与架构师完成至少一轮实质探讨，分歧记录落盘（本文件 6 条实质分歧，均含依据/立场/建议结论）
- [x] 所有分歧可追溯到具体文档章节或字段名（无"凭感觉"条目）
- [x] 未替架构师做技术选型（只提"要什么效果/字段口径"，未指定实现方式）
- [x] 引用事实均标注来源文件与章节
- [x] 未改架构文件、未写代码、未读 FundLens/ZCode、未改 runtime/**
- [x] 未派发子任务
- [x] 结论可执行（每条落到具体字段或章节修订动作）
- [x] 无"双方无分歧"式橡皮图章表述
- [—] 「每条需求含场景+痛点+需求+验收」「四态定义」等 PRD/UI 专属项：本工件不适用（N/A）

## 下游交接

- **主消费方**：`architect`。需其执行：对 A-01 / A-02 / A-03 / A-04 / A-05 / A-06 逐条给出「采纳 / 部分采纳 / 不采纳 + 理由」，落到 `05~09` 具体章节与字段修订，并将修订结果回写 `10-arch-review` 定稿纪要（会签结论）。
- **次消费方**：`frontend-dev` / `backend-dev`（契约一旦修订，按新版本实现，勿按未决口径开工）；`qa`（A-01/A-03/A-06 需转为负向用例）。
- **建议门禁判定**：G-AR-06 → **CONCERN（有条件放行）**。A-01、A-03、A-06 属 Brief §4 失败定义相邻项，建议 24h 内决策；A-02/A-04/A-05 可随 S2 定稿一并处理。
- **残留风险**：
  1. 若 A-01 不采纳，R-03「可追溯」无法通过 G-PM-05 终验，届时需回退契约，返工成本高于现在（责任人：architect，期限：S2 定稿前）。
  2. 若 A-04 的 T+3/T+15 `p` 口径不补齐，`09 §5.5 p` 字段将由后端自造，触发 PRD G3「前端/后端假数据」（责任人：architect，期限：S2 定稿前）。
  3. A-03 最小覆盖门槛若不定，`PortfolioForecast.direction` 存在把单只信号当组合结论的产品风险（责任人：architect + product-manager，期限：S2 定稿前）。
- **未覆盖**：`04-ui-wireframe.html` 未逐屏核对（本评审聚焦 05~09 契约口径与算法链）；测试用例设计留 `qa`。
