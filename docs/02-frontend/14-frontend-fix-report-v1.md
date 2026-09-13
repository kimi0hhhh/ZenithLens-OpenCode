---
artifact: 14-frontend-fix-report
owner: frontend-dev
version: v1
status: draft
supersedes: —
created: 2026-09-12
reviewers: [dev-lead, qa, architect]
gate: G-FE-01
---

# 前端缺陷修复报告 · 极境 ZenithLens（S4 · OC-S4-FE）

> 上游：`docs/04-integration/15-code-review.md`（BLOCK 清单）、`docs/02-frontend/13-frontend-report.md`、`docs/01-architecture/09-api-contract.md`（v3）。
> 范围：**只改 `static/**`**；未改后端 `*.py`、未改 `09-api-contract`、未改 `runtime/**`、未派发子任务。
> 回归环境：`python app.py`（Python 3.8.6，`DEFAULT_PORT=8791`）+ Edge headless `--dump-dom`；纯函数断言用 Node 18 ESM。
> commit：无（本工作区非 git 仓库，以文件时间为准，修复报告时间戳为本次唯一版本标识）。

## 摘要

1. **BLOCK-1 已关**：`effect_pp` 不再二次 ×100。新增统一出口 `format.js#pp()`（单位=百分点，按契约 §5.21），`signals.js:93/97` 改走 `pp()`。真浏览器实测渲染 `+3.90pp` / `+0.88pp` / `-3.09pp` / `-2.72pp`，无 `390.00pp`。
2. **BLOCK-2 已关**：`engine.js` 冻结参数表「准入度分母 N_w」改读 `window.n_w`（`nwOf()`），实测显示 `5 / 10 / 15 / 30 / 60 / 120`，不再吐窗口名。
3. **连带修复**：`mock.js` 的 `effect_pp` 由小数（0.039）改为百分点（3.9）、`window_min_days` 由 `{d15:5}` 改为 `{window,n_w}`，使替身与契约/后端同构（否则 mock 路径回归会反向出错）。
4. **SHOULD 3 条（1/4/5）+ NIT 3 条（1/2/3）已处理**；SHOULD-2/3 因依赖契约裁定或属打包层，**显式延后**并说明理由（见 §4）。
5. 回归全绿：`node --check` 14/14 JS 模块；Node ESM 断言 11/11；两处真浏览器复验通过。

## 正文

### 1. BLOCK-1 · `effect_pp` 二次 ×100

- **根因**：后端 `fund_predict.py:29` `GATE_EFFECT = {E1:0.88, E3:3.90, E4:-2.72, E2:-3.09}`，单位已是**百分点**（契约 §5.21 `effect_pp` 精度 4 位、单位=百分点）。前端误把它当 `*_rate`（小数比率）处理，再 `* 100`。
- **改法**：
  - `static/js/format.js:45` 新增统一出口 `pp(v,d)` → `(v>=0?'+':'')+v.toFixed(d??2)+'pp'`；与 `delta()`（小数比率、需 ×100）显式区分，避免口径混淆。
  - `static/js/views/signals.js:5` 引入 `pp`；`:93`（触发门卡）与 `:97`（剔除卡）由 `(g.effect_pp*100).toFixed(2)+'pp'` 改为 `pp(g.effect_pp)`。
  - `static/js/mock/mock.js:359-364` 替身同步为 `0.88 / 3.9 / -2.72 / -3.09`（原 `0.0088/0.039/...` 与单位不符）。
- **证据（真浏览器，`http://127.0.0.1:8791/#/signals`）**：`sg-gates` 实测 `纯事件效应 +3.90pp（t=+2.33）`、`纯事件效应 +0.88pp`；`sg-excl` 实测 `放量上涨（…，-3.09pp）；点火（…，-2.72pp）`；全 DOM 无 `390.00pp`/`309.00pp`。mock 路径（`?mock=1#/signals`）同样为 `+0.88pp`/`+3.90pp`。

### 2. BLOCK-2 · `window_min_days` 结构漂移

- **根因**：后端 `engine.py:679-682` 返回 `[{window:"d15",n_w:5},…]`；契约 §5.14 原注仅 `array[object]`（缺口 6）。前端用 `w[Object.keys(w)[0]]` 取「首键」，拿到 `"d15"`（窗口名）而非分母 `5`。
- **改法**：
  - `static/js/views/engine.js:209-217` 新增 `nwOf(w)`：优先 `w.n_w`（与后端及评审 §4 BLOCK-2 冻结结构一致），仅在缺 `n_w` 时回退首键值，以兼容契约字面形态 `{d15:5}`；无有效值返回 `—`。
  - `static/js/views/engine.js:232` 冻结表行改为 `(d.window_min_days||[]).map(nwOf)`。
  - `static/js/mock/mock.js:411` 替身改为 `[{window:'d15',n_w:5},…]`。
  - **未改后端/契约**：`nwOf` 是纯前端读取对齐，不发明新字段。
- **证据（真浏览器 `#/engine`）**：`准入度分母 N_w` 行实测 `<span class="mono">5 / 10 / 15 / 30 / 60 / 120</span>`；断言「`d15 / d30 / …`」窗口名串不存在。

### 3. SHOULD / NIT · 在 `static/**` 内的处理

| 编号 | 处理 | 改动位置 | 证据 |
|---|---|---|---|
| SHOULD-1 立方体颜色/图例未消费后端 | ✅ | `components.js:171-230` 新增 `cubeLegendHTML(legend)` 与 `cubeBandIndex(cell,p,legend)`；`cubeSliceHTML(slice,key,legend)` 优先按 `cell.color_band` 命中 `legend[].label` 定色，阈值仅由后端 `legend.min_p/max_p` 提供；不再自算 `CUBE_BANDS`。`index.html:265` 图例容器改为 `#eg-cube-legend`，由 `engine.js:288` 用 `d.legend` 渲染 | Node 断言：green/strongred band 命中 true、legend 5 项；`#/engine` DOM 图例由后端 5 项生成 |
| SHOULD-4 DDSM 对比列硬编码「全部 N 格有值」 | ✅ | `engine.js:294` 改为 `'DDSM '+int(cmp.empty_count_ddsm)+' 格无样本 · …'`，与 naive 列同构 | 全 DOM 无 `全部 N 格有值`；断言空样本格渲染 `—` 非 `0` |
| SHOULD-5 精度分组显示原始枚举 | ✅ | `copy.js:84` 新增 `CONF_LABEL`；`holdings.js:104` 渲染 `g.label || CONF_LABEL[g.confidence] || g.confidence` | 待契约缺口 4 补 `label` 后自动直读，无 `label` 时已中文 |
| NIT-1 `index.html:64` 硬编码 `0.80%` | ✅ | 副标题改为「行业基准 MAE 见后端字段（契约 §5.2 固定 0.80%）」，去除重复真相 | 实际值仍由 `val-sum` 后端字段渲染 |
| NIT-2 `DIRECTION_REASON` 重复 | ✅ | `components.js:3` 改为从 `copy.js` 导入 `DIRECTION_REASON`，删除本地 `DIR_REASON`；`:253` 改引用 | `grep DIR_REASON` 仅 `copy.js` 定义 + `components.js` 引用 |
| NIT-3 `cube` 取两次 slice | ✅ | `engine.js:273-279` 合并为单个 `sl`（`sl2 = sl`） | `node --check` 通过；`eg-layers` 与立方体正常渲染 |

### 4. 显式延后项（未改，理由）

- **SHOULD-2**（`analyze.js:82-98` 跨接口拼预测表 `tier/market_value`）：依赖契约缺口 2 裁定。契约未给 `PredictionSummary.tier/market_value` 前，改直读必然要发明字段（触硬性约束 #1/#3）。**保持现状**，待架构师裁定后由本轮下游或下一轮改。
- **SHOULD-3**（`mock.js` 随静态目录发布）：属**打包/交付层**（`16-build`）问题，非 `static/js` 源码缺陷；且 `main.js:144` 已在 mock 开启时给 `flavor-badge` 追加 `· MOCK` 徽章。建议 dev-lead 在交付包剔除 `static/js/mock/` 或在 `README-START` 标注，前端不越界处置。

### 5. 回归证据汇总

- **语法**：`node --check` 全部 14 个 JS 模块（`api/components/copy/format/main/store/mock` + `views/*`）→ `TOTAL_FAIL=0`。（Node 18 将 `.js` 按 CJS 解析，故以 `.mjs` 副本做 ESM 语法检查。）
- **接口实测（`python app.py` 8791，只读）**：`/signals/state` → E3=3.9、E1=0.88、E2=-3.09、E4=-2.72；`/engine/frozen-params` → `window_min_days=[{window,n_w}]`。
- **真浏览器（Edge headless）**：`#/signals` 与 `?mock=1#/signals` 的 `effect_pp` 均为 `±x.xxpp`；`#/engine` 的 N_w 行为 `5/10/15/30/60/120`。
- **纯函数断言（Node ESM）**：11/11 PASS（`pp()` 四值、`delta()` 未回归、立方体 3 格含 1 空、按 `color_band` 命中绿/深红 band、legend 5 项、空格不渲染 0/50%）。
- **未覆盖**：立方体真实数据路径（`#/engine` 直开时 `holdings` 切片为空 → `dimCode` 为 null，立方体显「立方体未训练」，此为**既有行为**，非本次引入）；改用 Node 合成切片覆盖了 `color_band` 渲染分支。

## 自验收

- [x] 每个页面四种状态全部实现并可手动触发查看（本次未改四态；仅复验 signals/engine 两页成功态）
- [x] 所有请求走统一封装层，页面层无裸 fetch（本次未新增 fetch；`grep fetch(` 仍仅 `api.js`）
- [x] 无硬编码业务数据；mock 默认关闭且隔离在 `static/js/mock/`（`effect_pp`/`window_min_days` 已与契约同构）
- [x] 数字格式化走统一工具函数 `format.js`（新增 `pp()`），涨跌配色正确
- [x] 未修改任何契约文件（`09-api-contract.md` / `docs/01-architecture/**` 只读）
- [x] 项目可直接以 `python app.py`（8791）启动，控制台无致命报错
- [x] BLOCK-1、BLOCK-2 逐条给根因/改法/证据；SHOULD/NIT 逐条给处理或延后理由
- [x] 只改 `static/**`；未动后端 `*.py` / `runtime/**`；未派发子任务

## 下游交接

- **主消费方 `dev-lead`（G-DL-01 销项）**：复核 BLOCK-1/2 是否关闭；如需回归可 `python app.py` 后访问 `http://127.0.0.1:8791/#/signals` 与 `#/engine`。
- **次消费方 `qa`（负向用例）**：
  - `effect_pp` 必须渲染 `±x.xxpp`（E3=+3.90pp），**不得**出现 `390pp`；
  - 冻结表 N_w 必须为 `5/10/15/30/60/120`，**不得**为窗口名；
  - 立方体空样本格必须渲染 `—`（不得 0/50%），图例须来自后端 `legend`（改后端阈值后前端应随之变化）。
- **架构师**：缺口 6（`window_min_days`）建议在契约 §5.14 正式冻结为 `[{window,n_w}]`（与后端及本报告读取一致）；缺口 2/4 裁定后转发前端闭合 SHOULD-2/5。
- **部分闭合的未决项**：
  1. `window_min_days` 契约字面仍为 `{d15:5,…}` 示例，与实现 `{window,n_w}` 未在契约层统一（契约缺口 6，责任人 architect，期限：S4 收口）；前端已双向兼容，不再显示错值。
  2. SHOULD-2（跨接口拼表）待契约缺口 2（责任人 architect）。
  3. SHOULD-3（交付包剔除 mock）待 `16-build`（责任人 dev-lead）。
- **残留风险**：
  1. 立方体全量真实数据路径未做端到端（`#/engine` 直开无 holdings 切片，属既有设计）；责任人 frontend-dev，期限：S4。
  2. `pp()` 仅用于 `effect_pp`；若后续新增其他已达百分点单位的字段，需继续走 `pp()` 而非 `delta()`/`rate()`，防口径再混。
