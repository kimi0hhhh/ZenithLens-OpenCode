---
artifact: 20-arch-verdict-r2
owner: architect
version: v1
status: approved
supersedes: —
created: 2026-09-12
task_id: OC-R4-ARCH
project: zenithlens-oc
reviewers: [dev-lead, backend-dev, frontend-dev, orchestrator]
gate: G-AR-05
---

# 架构裁定书 R2 · 极境 ZenithLens（S4 评审销项 · BLOCK-2 + SHOULD-1/4/5 + 缺口4）

> 触发：`docs/04-integration/15-code-review.md` v2 §4/§5、§下游交接「架构师：终裁 BLOCK-2 + SHOULD-1/4/5 + 缺口4，契约版本 +1」。
> 依据：`09-api-contract.md` v4、`12-interface-request.md` v2 §10、`14-api-impl-report.md` v2 §7、`15-code-review.md` v2 §3 实地抽验（V1~V10）。
> 产出：契约升 **v5**（`09-api-contract.md`，旧版备份 `09-api-contract-v4.md`）；同步 08→v5（备份 `08-backend-arch-v4.md`）、07→v4（备份 `07-frontend-arch-v3.md`）。
> 边界：本裁定只做 BLOCK-2 与契约缺口/歧义，**不改后端 `*.py`、不改 `static/**`、不改 `runtime/**`、未派发子任务**。

## 摘要

1. 逐条裁定 5 项：**BLOCK-2**（`llm.base_url` 缺失）→ **采纳补字段**；**SHOULD-1**（§5.14 三数组键名漂移）→ **accept-as-is + 冻结为后端形态**；**SHOULD-4**（§5.4 缺 `tier/market_value`）→ **采纳补字段**；**SHOULD-5**（§5.25 `naive_p` 语义）→ **以契约为准、实现去除 MIN_N 门控 + 新增低样本标注**；**缺口4**（precision `groups` 缺 `label`）→ **采纳补字段**。
2. 契约 v5 **只加字段 / 冻结歧义键名 / 补口径**，**未改名、未删字段、未改类型**；老契约 v4 备份留档。
3. 每条裁定落到**后端可直接执行**的位置+字段+测试断言（§2~§6 的「对后端最小可执行规格」）。
4. 复核结论：BLOCK-2 与三条缺口均属**契约侧**（架构师责任），前端已按预期写/读，后端的偏差均为「实现未对齐契约」，按 G-BE-02 归 backend-dev。
5. 明确边界：后端 14-report §7 的 **D2/D3/D5/D7** 本次**未纳入**（另需单独裁定的配置/口径项），见 §7。

## 正文

### 1. 裁定总表

| 项 | 定性 | 裁定 | 契约落点 | 后端动作 | 前端动作 |
|---|---|---|---|---|---|
| BLOCK-2 `llm.base_url` 缺失 | 契约缺口 | **采纳补字段** | §5.16 + §6.10 | GET 回传 / PUT 落盘 / URL 校验 | 直读直写 |
| SHOULD-1 §5.14 键名漂移 | 契约歧义 | **accept-as-is + 冻结** | §5.14 尾注 + §10.2 | 保持现实现 + 补断言 | 删旧形态兜底 |
| SHOULD-4 §5.4 缺 `tier/market_value` | 契约缺口 | **采纳补字段** | §5.4 + §6.4 | 行构造补两键 | 改直读、删拼装 |
| SHOULD-5 §5.25 `naive_p` 语义 | 契约/实现分歧 | **以契约为准：去 MIN_N 门控 + 补标注** | §5.25 + §6.11.7 + §10.3 | `build_cube` 改 naive_p + 补 `naive_low_sample` | 低样本角标 |
| 缺口4 precision `groups` 缺 `label` | 契约缺口 | **采纳补字段** | §6.3 | `precision_summary` 补 `label` | 读 `label` |

### 2. BLOCK-2 · `Settings.llm.base_url` 静默不持久化

- **问题**：`09 v4 §5.16 Settings.llm` 无 `base_url`；`settings.py#get_settings`（输出白名单）与 `#update_settings`（`llm` 分支）均忽略该键且不报错；设置页 9.7-33「Base URL」输入提交后刷新即丢（15-code-review §3 实测 `/settings.llm` 无 `base_url`）。
- **立场**：契约缺口（架构师责任），非前端 bug；后端**静默丢弃请求字段**违反「不假成功」，按 G-BE-02 红线拦截。
- **结论**：**采纳**。契约 v5 §5.16 增 `llm.base_url`，§6.10 明确 GET 回传 / PUT 可写。
- **对后端最小可执行规格（`settings.py`）**：
  1. `get_settings`：`llm` 对象输出键集合 = `{enabled, provider, base_url, model, api_key_set, temperature, output_format, mode}`；`base_url` 读 `settings.json` 的 `llm.base_url`，缺失回 `""`（**空串，非 null**）。
  2. `update_settings`：`llm` 分支处理 `base_url` 并落盘（原子写）；不得静默忽略未知/已知键。
  3. 校验：`base_url` 非空时须匹配 `^https?://.+`，否则返回 `E_VALIDATION`（`error.detail.base_url`）。
  4. 测试断言（`tests/`）：`PUT {llm:{base_url:"https://api.deepseek.com/v1"}}` → `GET.llm.base_url` 回读一致；非法值 → `E_VALIDATION`；未配置 → `""`。

### 3. SHOULD-1 · §5.14 三数组元素键名漂移

- **问题**：契约示例 `window_weights:[{d15:8}…]`、`window_min_days:{d15:5,…}`、`license_lines:[{candidate:50}…]`；后端实测统一为 `window_weights:[{window,weight}]`、`window_min_days:[{window,n_w}]`、`license_lines:[{license,min_independent_days,window_k}]`（15-code-review §3 V6）。前端已双向兼容、无显示错误，但构成双份真相。
- **立场**：**契约歧义**（示例只给形状、未定义元素键名），非后端实现缺陷；不引入新的事实源。
- **结论**：**accept-as-is + 冻结为后端形态**（与 §5.23 `FactorScoreWindow.n_w` 同义；**不采纳**前端 §10-6 提议的别名 `min_days`）。契约 v5 §5.14 尾注钉死元素结构，**旧示例形态作废**；`FrozenParams.license_lines`（数值线）与 `LifecycleRules.license_lines`（文本规则，§5.32）明确为**两个对象两套元素**，不得混用。
- **对后端最小可执行规格**：
  1. `engine.frozen_params()` **保持现实现**（无需改代码），仅确认元素键恰为：
     `window_weights`：`{window,weight}`；`window_min_days`：`{window,n_w}`；`license_lines`：`{license,min_independent_days,window_k}`（`window_k` 无 k 线要求时 `null`）。
  2. 测试断言：三数组每元素 **键集合恒等**于已冻结集合（多余/缺失键即 FAIL）；`window/mode` 取值 ∈ `factor_window`，`license` ∈ `factor_license`。
- **前端**：删除 `engine.js#nwOf/licenseName/licenseDays` 对 `{d15:...}`/`{candidate:...}` 旧形态的兜底分支。

### 4. SHOULD-4 · `PredictionSummary` 缺 `tier`/`market_value`

- **问题**：`§5.4 PredictionSummary` 无 `tier`、`market_value`；前端 `analyze.js:90-107` 用 `/holdings` 按 `code` 拼装预测表两列（跨接口展示连接，非业务计算）。
- **立场**：**契约缺口**（架构师责任）；前端跨接口拼装违反 §1.6「接口唯一性纪律」，数据切换时会产生双份真相。
- **结论**：**采纳**。契约 v5 §5.4 增 `tier`（enum `coverage_tier`）与 `market_value`（元 2 位，可为 null，口径同 §6.2.1，A-02）。
- **对后端最小可执行规格（`app.py` `h_predictions` / `h_prediction_get` 的行构造）**：
  1. 每个 `PredictionSummary` 元素补：`tier` = 关联 `HoldingRow.tier`；`market_value` = 关联 `HoldingRow.market_value`（估值→净值，两者皆无则 `null`，**禁止成本回退**）。
  2. `/predictions/{code}` 同字段（继承 `PredictionSummary`）。
  3. 测试断言：`GET /predictions` 的 `rows[].tier ∈ {A,B,C,D}`、`rows[].market_value` 与 `GET /holdings` 同 `code` 行一致（含 null 一致）。
- **前端**：`analyze.js` 改直读 `rows[].tier/market_value`，删除对 `/holdings` 的拼装。

### 5. SHOULD-5 · §5.25 `naive_p` 是否受 MIN_N 门控

- **问题**：契约 §5.25 仅规定 `status=empty` 时 `naive_p=null`；后端 `engine.build_cube` 实际按 `n>=MIN_N(15)` 门控 → 实测 017193 `naive_p` 大量为 null（`valid_coverage_naive_pct=0.0`），研究层整片「无样本」，组件 9.5-26「naive/DDSM 对照」名存实亡（15-code-review SHOULD-5）。
- **立场**：**契约与实现分歧**。研究口径（`naive`）是「未加噪真实档位」的**原始频率披露**，非决策估计，**不应**套用生产口径的 `MIN_N` 最小样本门；但低样本不得被读成中性估计，须**显式标注**（呼应「未知≠0/50%」铁律）。
- **结论**：**以契约为准，实现对齐契约**——① `naive_p = naive_up/naive_n`（`naive_n>0` 即给，`naive_n=0` 为 null）；② `MIN_N` **只**门控生产口径 `ddsm_p`/`ddsm_state`；③ 新增 `naive_low_sample = (naive_n < min_n)`；④ `status="filled" ⟺ naive_n>0`、`empty ⟺ naive_n=0`。
- **对后端最小可执行规格（`engine.py#build_cube`）**：
  1. 计算 `naive_p`：`None if naive_n==0 else round(naive_up/naive_n, 4)`——**删除** `if n>=MIN_N` 门。
  2. 每格新增 `naive_low_sample: bool = (naive_n < min_n)`（`empty` 格为 `true`）。
  3. `ddsm_p` / 收缩公式 / 加噪计数 / `status` 的 filled-empty 判定（改为 `naive_n>0`）**保持生产口径原样**；`empty` 格仍 `naive_p=ddsm_p=null`、`color_band="no_sample"`。
  4. 测试断言（`tests/test_engine_contract.py`）：构造 `0<naive_n<15` → `naive_p` 非 null 且 `naive_low_sample=true`；`naive_n=0` → 两 P 均 null、`status=empty`。
- **前端**：研究层低样本格叠加「低样本·仅供审计」角标；不得因 `naive_p` 有值而当作可信估计。
- **风险提示**：`naive` 仍默认折叠、仅供审计；`valid_coverage_naive_pct` 将随之上抬（覆盖率变高是研究口径披露的预期结果，非生产结论变好）。

### 6. 缺口4 · `/valuations/precision.groups[].label`

- **问题**：`groups` 元素仅 `{confidence,count,market_value,weight_ratio}`，无中文标签；前端以本地 `CONF_LABEL` 兜底（15-code-review V3/缺口4）。
- **立场**：**契约缺口**；展示文案应后端单源（与 `mode_distribution.mode_label` 同构），避免前后端各存一份。
- **结论**：**采纳**。契约 v5 §6.3 `groups[]` 增 `label`（中文）/ `count` / `market_value` / `weight_ratio`，`label` 映射与 `Valuation.confidence_label` 一致。
- **对后端最小可执行规格（`valuation.py#precision_summary`）**：`groups` 每项补 `label`（`high→高 / mid→中 / low→低 / unknown→无`），复用与 `confidence_label` 同一映射函数。
- **前端**：`H2`/`.vsum` 读 `groups[].label`，仅空值时回退本地常量。

### 7. 本次未纳入 / 边界（防范围蔓延）

以下项在 15-code-review §5 分流表中亦指向架构师，但**不属于**本轮 OC-R4-ARCH 派发范围，**本次不裁定**，避免超额交付：

- **后端 14-report §7 D2（代理映射 A/D 配置）、D3（`legacy_path` 定义）、D5（门优先 vs 否决 missing 优先级）、D7（`import.merge` 语义）**：均为配置/口径假设，需独立裁定轮次（建议下一轮 architect 触达 08/09 时逐条落字段）。
- **SHOULD-2/3（前端）**：SHOULD-2 与 BLOCK-1 同类（HUD 枚举映射）、SHOULD-3（`emptyWhen` 接线）——**前端实现**，与本裁定无关。
- **A-10 归档轮转阈值/定时器**：backend-dev 排期增强项，非契约缺口。

## 自验收

- [x] BLOCK-2 逐条裁定并落到字段级规格（问题/立场/结论/后端位置+字段+测试断言）
- [x] SHOULD-1 冻结三数组元素键名，旧示例作废，同名不同对象明确区分
- [x] SHOULD-4/缺口4 补齐字段并给出后端行构造/映射位置
- [x] SHOULD-5 明确以契约为准（去 MIN_N 门控）+ `naive_low_sample` + `status` 判定式
- [x] 契约升 v5（`version: v5` / `supersedes: v4`），只加/冻结/补口径，未改名
- [x] 备份 `09-api-contract-v4.md`、`08-backend-arch-v4.md`、`07-frontend-arch-v3.md`；07 升 v4、08 升 v5 同步
- [x] 未写实现代码/未改后端 `*.py`/`static/**`/`runtime/**`；未派发子任务
- [x] 明确边界：D2/D3/D5/D7 等未纳入，另轮裁定

## 下游交接

- **主消费方 `backend-dev`（经主 Agent 转派）**：执行 §2~§6 的五处最小改动 —— ① `settings.py` 补 `base_url`（BLOCK-2）；② `app.py` `/predictions` 补 `tier/market_value`（SHOULD-4）；③ `engine.py#build_cube` 改 `naive_p` + 补 `naive_low_sample`（SHOULD-5）；④ `valuation.py#precision_summary` 补 `label`（缺口4）；⑤ §5.14 三数组保持现状仅补断言。改后重跑 `python -m unittest discover -s tests -t .` 全绿，并把新断言回写 `14-api-impl-report`。
- **次消费方 `frontend-dev`**：按 `07 §4.14` 收口四处读取（LLM Base / 预测表直读 / 精度分组 label / 冻结表三数组键名），删除旧形态与跨接口兜底；不新增功能。
- **`dev-lead`**：G-BE-02 自 v5 起以 `09-api-contract.md` v5 为唯一法律复核；`15-code-review` 销项时以本裁定书 §1 总表为核对清单。
- **残留风险**：① 契约 `naive_p` 语义变更后，研究层 `valid_coverage_naive_pct` 上抬属预期，但需防止被误读为「模型变好」——由 `dual_view_note` + 低样本角标兜底（责任人：frontend-dev，期限：S4 收口）；② D2/D3/D5/D7 未裁定期间按 14-report「实现配置假设」运行，若与用户预期不符须重走裁定（责任人：architect，期限：S4 收口后首轮触达）。
