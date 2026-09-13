---
artifact: 06-system-arch-r2
owner: architect
version: v3.2
status: draft
supersedes: 06-system-arch.md（R1 基线 v3）
created: 2026-09-12
reviewers: [product-manager]
gate: G-AR-02
---

# 项目开发架构（系统架构）· 极境 ZenithLens（R2 升级轮增量）

> 本文是 `06-system-arch.md`（R1 v3）的**增量版本**：只回答 R2 变更对五问的影响，未变部分（本地单用户 web + pywebview、JSON/JSONL 存储选型、REST+轮询、零依赖、失败降级基线）**沿用 R1 v3，不重抄**。
> 上游：`05-product-arch-r2.md`、`09-api-contract-r2.md`（**v9.1**）、`08-backend-arch-r2.md`（v3.1）。
> 五问 = **数据从哪来/多久更新 · 状态存在哪 · 前后端怎么通信 · 失败会怎样 · 边界在哪**。
> **v3.1（2026-09-12 · 会签收敛）**：存储新增 2 处（`proxy_quality.json` / `qdii_review.jsonl`，见 §3）；失败矩阵 B 行更新挂档口径（D-4）。
> **v3.2（2026-09-13 · 用户指令轮）**：影子盘窗口 20→60（§6 边界行、§7.3 数据流行、ADR-0009 索引更新；设计核验见 08-r2 §5.5、契约 09 v9.5 §13）。

## 摘要

1. **五问一句话（R2 后）**：数据新增两路——`lsjz 净值史维护`（T+1，持仓 22 只）与 `隔夜参照行情`（QDII 校正用，盘前/盘中按需）；状态新增 5 个文件（净值史 / 日留档 / 源事件日志 / 复核结论 / 成绩缓存）并修正 2 处口径；通信仍 REST+JSON+轮询，新增 2 个任务类型；失败表现新增"四目标各自失败矩阵"（§5）；边界新增 4 条（§6）。
2. **四目标数据流各一条**（§7）：A 估值链 → 误差通道回算；B 台账 → 验证批次 → 按现档位重算；C 代理日线 → t*_real 回填 → 成绩出数；D lsjz → nav 史 / 主源声明 / 源事件日志。
3. **回填任务失败的 UI 表现**（重点答复）：已写记录不回滚；未到期行保持「待回填」；失败批次写任务 `error`，页面不出现任何 hit/miss 假值；覆盖/进度照实不涨。
4. 冻结与边界未变：单用户、无并发写、不联网部署、不交易、无 WebSocket、无数据库。
5. ADR-0007~0012 记于 `10-arch-review-r2.md §ADR`；本文只列索引（§9）。

## 正文

### 1. 五问增量总表

| 问题 | R1 答案（v3） | R2 变更 |
|---|---|---|
| 数据从哪来/多久更新 | 腾讯日K/实时、天天基金、新浪（未接线）、桌面源文件 | **+lsjz 净值史维护（T+1）**；**+隔夜参照指数（QDII）**；新浪**限定接线**为兜底；桌面源降级为可选导入源 |
| 状态存在哪 | JSON/JSONL + 原子写 + 文件锁 | **+5 个文件**（§3），`accuracy.json` 结构 v2，`health.json` 追加事件日志 |
| 怎么通信 | REST+JSON，12s/2s 轮询 | 不变；任务类型 +2（`maintain_nav_history` / `verify_tiers`），`backfill_ledger` 增 `mode` |
| 失败会怎样 | 降级矩阵（§4 R1） | 新增四目标失败矩阵（§5）；回填/重算/双段/健康各自的显式降级 |
| 边界在哪 | 单用户/无并发/不部署/不交易 | +4 条：净值史仅持仓 universe、QDII 校正仅限 3~4 只、归档合并只读、日留档 ≤10KB/日（§6） |

### 2. 五问之一：数据从哪来、多久更新（变更清单）

| 数据 | 来源 | 更新时机（R2） | 历史上限 | 落盘位置 |
|---|---|---|---|---|
| 基金净值史（新增权威源） | 天天基金 lsjz 分页（`api.fund.eastmoney.com/f10/lsjz`） | 每交易日 T+1（`maintain_nav_history`；启动 warmup 触发一次） | 250 点/只（只维护持仓 universe，见 §6） | `data/cache/nav/<code>.json`（按 date 去重、既有不覆盖） |
| 隔夜参照指数（新增） | 腾讯行情（美股/港股指数，符号实测确认） | QDII 估值时按需（5s 超时，不缓存或短 TTL） | 仅最近一个已完结时段 | 不落盘（估值记录内 `qdii_correction`） |
| F10 前二十持仓（升级） | 天天基金 F10 `topline=20` | 季报披露后；缓存 30 天（缓存失效才重抓） | 前 20 大 | `data/cache/holdings/<code>.json`（记录 `top_n`） |
| 港股个股实时（升级） | 腾讯 `qt.gtimg.cn`（`hk` 前缀） | 重仓加权估值时按需批量 | — | 不落盘 |
| 新浪实时（定案） | `hq.sinajs.cn` | **仅腾讯失败时兜底**（proxy 档 + 个股批量两处） | — | 不落盘；事件进 `health-log.jsonl` |
| 桌面 `funds_data.json` | 用户桌面（断链） | 降级为**可选导入源**；源缺失时禁用导入按钮 | — | 只读；主源 = `data/holdings.json` |

> 结论口径：净值史**不是**全市场回补（不做清单 13）——只维护 22 只持仓；外部源只决定"今天能不能取到"，不决定"历史有没有"（历史落盘即自持）。

### 3. 五问之二：状态存在哪（新增 7 / 修改 2）

```
data/
  cache/nav/<code>.json                 # 新增：净值史（权威）；写入=按 date 去重追加
  snapshot/daily/valuation-YYYYMMDD.jsonl  # 新增：每日估值留档（每基金 1 行；写完只读）
  health-log.jsonl                      # 新增：源事件日志（append-only）
  review/tier_reviews.jsonl             # 新增：验证/复核结论（INSERT-ONLY）
  snapshot/review_scores.json           # 新增：成绩缓存（可重建，整文件原子替换）
  snapshot/proxy_quality.json            # 新增(v3.1)：代理质量重建证据道（bars×nav 史；R2-04 首选证据，D-2）
  review/qdii_review.jsonl              # 新增(v3.1)：QDII 首测/复评与 alignment 计数（INSERT-ONLY，R-5）
  snapshot/accuracy.json                # 修改：v2 结构（键 mode|code + updated_at/matched_days）
  ledger/backfill.jsonl                 # 修改：行内追加 method + proxy_code（v3.1/R-1）
```

写入规则（沿用 R1 v3 §2.3：原子替换 / 追加写 / 文件锁 / 单写者），R2 补充：
- **日留档一文件一快照日**：存在即跳过（幂等）；不重写已写文件。
- **净值史首值冻结**：同一 date 已存在即保留原值（官方对账差异记 `health-log` note，不覆盖）。
- **recompute 顺序**：先全量归档旧记录 → 再原子重写主文件（任何一步失败保持原状，不半写）。
- **成绩缓存**：可重建（删文件后由任务重算），不得作为审计源（审计源 = 台账 + 净值史 + 日留档）。

### 4. 五问之三：前后端怎么通信（不变 + 增量）

- REST + JSON over `127.0.0.1:8791`（绑定、端口策略、轮询间隔沿用 R1 v3 §3）。**无 WebSocket/SSE 的理由不变**（数据 T+1）。
- 新增任务：`POST /tasks {type:"maintain_nav_history"}`（净值史+误差通道+日留档）；`POST /tasks {type:"verify_tiers", params:{targets:[...]}}`（C→B 批次 / 代理复核）。
- `POST /tasks {type:"backfill_ledger", params:{"mode":"recompute"}}`：影子盘重算（缺省 `incremental`）。
- 任务仍为异步（202 + `GET /tasks/{id}` 2s 轮询）；长任务超过 90s 的进度步骤照常写 `step`。

### 5. 五问之四：失败会怎样（R2 四目标失败矩阵）

| 目标 | 失败场景 | 系统表现 | 用户可见 | 阻塞 |
|---|---|---|---|---|
| A 估值 | 净值史维护失败 | 保留已有净值；`accuracy` 不增长；源记 `warn/bad`（事件日志） | 设置页源状态 + 滞后提示照实；徽章 `unknown + conf_reason=nav_missing` | 否 |
| A | 误差样本不足（n<5） | `confidence=unknown + no_samples` | 徽章 tooltip 原因文案；vsum 无该组样本 | 否 |
| A | 隔夜参照不可得 | QDII 回退单段 + `fallback_reason=overseas_unavailable` | tooltip「单段（隔夜数据缺失）」 | 否 |
| A | 估值预算用尽 | 停止继续估值；跳过持仓回退旧缓存/unknown+`budget_exceeded` | 行内未知原因；任务日志 warn | 否 |
| B 覆盖 | 验证批次单只数据不足 | 挂档观察（复查日 = 证据就绪 +30 交易日；>3 只同时挂档触发架构×PM 复审；v3.1/D-4） | 行内「验证中·观察」+ 复查日，不得显示"已验证"；不计覆盖增长 | 否 |
| B | 重算中断/归档不可写 | **中止重算并告警**；主文件保持原状（不半写） | 任务 `error`；台账/进度照旧 | 是（该任务） |
| C 准确率 | 回填任务失败/部分成功 | 已写不回滚；未到期行保持「待回填」；失败写任务 `error` | 对账页无新 hit/miss；进度不涨；**无假值** | 否 |
| C | 回测未跑通 | `/review/scores` 保持 `pending` + `note` | hero「待填充」（不得估计值） | 否 |
| C | 基线样本 N=0 | `baseline_rate=null`、`deviation_pp=null` | 「待填充」；**不得回退 0.5830** | 否 |
| D 来源 | 外部源断链（腾讯/东财/新浪） | 逐档降级 → 缓存 → `unknown`；源事件留痕 | 健康页三态 + 时间戳；估值行 reason | 否 |
| D | 导入源不存在 | `import_available=false` + `import_disabled_reason` | 按钮禁用 + 可读说明（**不出现 E_IO 堆栈**） | 否 |

**回填任务失败的 UI 表现（逐条）**：① 对账/时间线行维持「待回填」（`result=pending`）；② 不出现任何 hit/miss 或 `t1_real` 假值；③ 任务列表该任务 `failed` + `error.message`；④ 页面**不弹全局错误**（该任务失败不使整页进 error 态）；⑤ 下次任务自动重试到期项（幂等）。

### 6. 五问之五：边界在哪（R2 新增 4 条）

| 边界 | 明确取值 |
|---|---|
| 净值史范围 | 仅持仓 universe（22 只）；不做全市场历史回补（PRD 不做清单 13） |
| QDII 校正范围 | 仅 `fund_type=qdii` 且代理为跨市场 ETF（024239/016665/012922/457001/021662/163208 中的可得者）；其余基金零校正 |
| 日留档规模 | 22 行/日 ≤10KB/日（全量保留，R2 末复核）；盘中不写 |
| 归档合并 | 只读计算（主文件滚动 **60** 交易日不变，v3.2 用户指令）；归档不可写/不可读时降级为主文件口径并标注 |
| 延续 R1 | 单用户 / 无并发写 / 127.0.0.1 / 不联网部署 / 不交易 / 无日期主题切换 |

### 7. 四目标数据流变更（每目标：流程 → 失败 → 边界）

#### 7.1 A · 估值更准
```
[变更前] 五档链 → valuation_history（当日多轮） → 徽章（confidence 仅 proxy 档有键 → 22/22 unknown）
[变更后] 五档链 → valuation_history（审计源）
              └→ 每日收盘 archive_daily → daily/valuation-YYYYMMDD.jsonl（≥40 日）
         净值史（lsjz 维护）→ build_accuracy v2：逐日配对 → accuracy[mode|code]（滚动 40 日）
              └→ 徽章 confidence / vsum weighted_mae / precision.window_filled_days
         重仓加权：F10 top20 + A/HK 实时 → trace[holdings].detail（披露日/覆盖权重）
         QDII：境内段 + 隔夜段（对齐校验）→ qdii_correction（回退单段）
```
- 失败：见 §5 前 4 行；样本不足/源缺全部给 `conf_reason`，**无估计值**。
- 边界：误差样本只认"可配对日"；官方档在未发布时段的非零误差**照实计**（口径见 09 §3.2）。

#### 7.2 B · 覆盖更多
```
[变更前] C 档 7 只无结论 → 预测 universe 15/22；影子盘按旧档位留 022485 遗留
[变更后] verify_tiers（C 7 只，生产配置单资产六窗走前）→ tier_reviews.jsonl（INSERT-ONLY）
              └→ holdings 更新（升 B / 维持 C+复查日 / 降 D）→ universe (15+k)/22 按实计
         recompute（按现档位）→ 归档旧台账 → 重生成滚动窗（created_at 继承）
         signal_state.rolling_open_assets（滚动 60 日资产数（v3.2）；口径替代"日开口数"）
```
- 失败：批次单只数据不足 → 维持 C + 复查日；重算中断 → 中止告警（§5）。
- 边界：门仍 E1/E3（E2/E4 禁复活）；低频是常态（文案口径）。

#### 7.3 C · 准确率更高
```
[变更前] backfill 0 行；/review/scores 硬编码 null；基线 0.5830 硬编码；影子盘进度封顶 20
[变更后] 到期信号 → 代理日线 → backfill.jsonl（t1/t3/t15_real + method=proxy_bar）
              └→ 对账 hit/miss、时间线、事件链第⑥步
         factor_engine.evaluate_production（全部 A/B 代理）→ review_scores.json → /review/scores（hero+三窗）
         实测基线 = max(恒涨率,恒跌率)（台账 universe）→ shadow 三处 + frozen_params.baseline_method
         20/60：shadow_progress 读「主文件 ∪ 归档」→ consecutive_days 可达 ≥60
```
- 失败：回填失败 UI 表现见 §5；成绩 pending 不填估计值；N=0 → null。
- 边界：回填口径 = 代理日线（ADR-0008）；Δ 复算 = 同 bars + frozen_config + seed 幂等。

#### 7.4 D · 来源更可靠
```
[变更前] 桌面源断链（导入报 E_IO）；nav_history 滞后 18 天；fail_count 544；sina 从未实测
[变更后] holdings.json 主源 + 导入源状态字段（禁用说明）→ 设置页不再误导
         lsjz 分页 → nav 史（T+1）→ n_test 7→≥40、/runtime.staleness 同步
         新浪：腾讯失败兜底（proxy + 个股批量）→ 健康页三态
         record_source 事件日志 → fail_window_7d + recent_failures（累计值仅审计）
```
- 失败：源断 → 降级 + 留痕；不编造。
- 边界：新浪不做主源；净值史仅持仓；QDII 参照探测失败即回退。

### 8. 安全 / 隐私 / 离线（不变声明确认）

- 数据不出本机（除出站行情/净值与可选 LLM）；无入站、无上传；API Key 只落本地不回传；隐私打码仅展示层。R2 新增字段均不含隐私敏感值（`recent_failures.note` 须脱敏，不得含金额/路径外泄信息——路径为产品本地路径，允许）。

### 9. ADR 索引增量（正文见 `10-arch-review-r2.md §ADR`）

| ADR | 决策 | 关联 |
|---|---|---|
| ADR-0007 | 估值误差通道评分对象 = 当日最终展示记录（含官方档零误差语义） | §7.1 / 09 §3.2 |
| ADR-0008 | t*_real 回填口径 = 代理日线涨跌（与预测锚点同源） | §7.3 |
| ADR-0009 | 20/60 修复 = 归档合并（合并口径不变；窗口 v3.2 起 20→60，用户指令） | §7.3 |
| ADR-0010 | QDII 双段 = 时间互补加法（无学习权重），不达标回退单段 | §7.1 |
| ADR-0011 | 首测不达标处置分层（样本门槛 → 回退口径 → 降档） | §5 / 10 §2.4 |
| ADR-0012 | 新浪源 = 限定兜底接入（不做主源） | §7.4 |

### 10. 本期不做（技术项增量）

| 不做 | 理由 |
|---|---|
| 交易日历（法定节假日）完整校准 | `trade_session` 仍按周末+时段（R1 风险 14 延续）；QDII 校正以时段对齐校验自兜底 |
| 全市场净值史 / 全市场 bars 回补 | PRD 不做清单 13 |
| 净值史冲突自动纠错 | 首值冻结 + 差异留痕（人工审计）；自动改历史违反审计纪律 |
| 日留档冷热分层/压缩 | 体积可忽略（R2 末复核再议） |

## 自验收

- [x] 五问全部回答 R2 增量（§1~§6），未变部分明确沿用 R1 v3
- [x] 数据来源给出域名/接口、更新时机、上限与落盘位置（§2）
- [x] 存储新增 5 / 修改 2 全部给出路径、写入时机与幂等规则（§3）
- [x] 通信说明不变理由 + 任务增量（§4）
- [x] **四目标失败矩阵 + 回填任务失败 UI 表现逐条**（§5）
- [x] 四目标数据流"变更前 → 变更后 → 失败 → 边界"逐目标成文（§7）
- [x] 边界新增 4 条明确取值（§6）
- [x] 冻结/红线未触碰（无 E2/E4、无做空、INSERT-ONLY、无 WebSocket/数据库）
- [x] 未写代码；ADR 仅索引（正文在 10）；未修改 R1 工件；未触碰 `runtime/**`

## 下游交接

- **主消费方**：`backend-dev`（存储与任务落点）、`frontend-dev`（状态字段与失败表现的 UI 映射）。需其执行：按 §3 文件语义实现；§5 失败矩阵逐行可构造（QA 配合）。
- **次消费方**：`dev-lead`（G-DL-02 构建核验：零依赖 + Python 3.8 + 端口自适配 + 新存储幂等）、`qa`（失败矩阵与回填失败 UI 用例）。
- **残留风险**：
  1. 隔夜参照指数符号/可用性未实测 → 探测失败回退单段（backend-dev，S3 首日）。
  2. 净值史 250 点上限对长样本的影响 → 40 日窗远小于上限，无影响；R2 末复核（backend-dev，S5）。
  3. `trade_session` 节假日误判延续 → 若 QDII 校正因此误开，靠对齐校验兜底（architect，S5 评估）。
- **未覆盖**：契约逐字段（`09-api-contract-r2`）、后端模块（`08-backend-arch-r2`）、前端组件（`07-frontend-arch-r2`）、产品能力（`05-product-arch-r2`）。
