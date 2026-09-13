---
artifact: retro
owner: orchestrator
version: v1
status: final
supersedes: —
created: 2026-09-12
reviewers: [user]
gate: —
project: zenithlens-oc
---

# 迭代回顾 · 极境 ZenithLens（skill 驱动重跑轮）

> 方法：`retro` skill（Start / Stop / Continue + 优先行动项）。团队：1 主 Agent + 6 角色（general 子 agent 承载）。

## 一、Sprint 业绩

- 目标：OpenCode 独立实现「极境 ZenithLens」完整 S1–S6（零复用 FundLens/ZCode 代码）→ **达成（有条件）**。
- 结论签：dev-lead 方向不偏 / qa **PASS** / PM **CONCERN（有条件放行）**。
- 返工：S3 一轮（BLOCK 修复）、S4 一轮（2 BLOCK）、S5 一轮（1 P0）；均 1 轮内收敛。

## 二、三个主题

1. **skill 驱动的价值被证实**：子 agent 读 `SKILL.md` 后用出可辨识的差异——`pre-mortem` 让 PRD 带风险老虎/纸老虎；`tdd` 让后端 40 条断言先红后绿；`triage`/`code-review` 让 BLOCK 分流更准；`metrics-dashboard` 让 PM 用「North Star=Δ」而非组件数量收口。**方法改变了行为，不只是话术。**
2. **「契约正文引用」是当前唯一 100% 生效的 skill 通道**：`skill` 工具未暴露项目 94 个 skill，角色 agent 名也不可用（Unknown agent type）→ 全靠 `general` + 读取 `SKILL.md` 文本。能力地图 §8 的判断被本轮实测确认。
3. **核心价值仍未自证**：40 组件、53 接口、56 断言都齐，但 **T+1 Δ vs 基线 = 无值**（OBS-01）。过程指标漂亮，North Star 缺席——这是下一轮唯一真正该补的洞。

## 三、Start / Stop / Continue

- **Start**：把「North Star 指标（Δ vs 基线）是否产出」列为交付硬门禁——无值即 CONCERN，禁止用组件/接口数量充当价值证据。
- **Stop**：停止「skill 只写在能力地图、不写进派发 prompt」——每次派发必须点名 0~2 个 skill 的 SKILL.md 路径。
- **Continue**：文件交接 + 门禁不放水（本轮 S5 P0 确实拦下了 0.9% 的显示错误）；子 agent 回传列明所用 skill。

## 四、优先行动项（≤3）

| # | 行动 | 负责 | 期限 | 成功判据 |
|---|---|---|---|---|
| 1 | 产出 T+1 Δ vs 基线（回测 + 影子盘成绩），界面填实 | architect + backend-dev | 下一轮 | 复盘页 hero 出数、影子盘 ≥1 日真实回填、Δ 可复算 |
| 2 | 修 F-PM-01 覆盖口径（22/22 → 10/22） | backend-dev（或前端） | 下一轮 | 副标题覆盖数 < 总数，QA 补用例 |
| 3 | 派发模板固化「点名 skill」字段，并把常用 skill 路径写入 capability-map 派发示例 | orchestrator | 本轮即办 | 后续派发 prompt 均含 skill 行 |

## 五、Carry-over（承自 FundLens 轮）

- 「交互链 UI 用例设为 P0 门禁」——本轮 QA 已按 test-scenarios 强制正常/边界/异常三件套，**Done**。
- 看板固定 8790 / OpenCode 标识 / 登录自启——**Done**（本工作区）。
- FundLens 遗留（R-A6/A7、E9）——**Not started**（另一项目，另行排期）。
