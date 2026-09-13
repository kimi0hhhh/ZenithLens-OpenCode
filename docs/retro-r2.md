---
artifact: retro-r2
owner: orchestrator
version: v1
status: final
supersedes: —
created: 2026-09-13
reviewers: [user]
gate: —
project: zenithlens-oc
---

# 迭代回顾 · 极境 ZenithLens R2 升级轮

> 方法：ORCHESTRATOR §7 四问 + 运行指标。团队：1 主 Agent + 7 角色 + 2 外援（explorer/auditor）。
> 轮次：R2（升级轮，C2 级走完整 S1–S7，关键路径重叠 v4.1 首次全量实践）。

## 运行指标（§7 三行）

| 指标 | 本 R2 轮值 | 来源 |
|---|---|---|
| 总 token / 成本 | **6,815,646 tokens / $6.53**（真实值，OpenCode session DB） | `/api/state` → `tokens.actual` |
| 返工轮次 | S3→S4 修复 1 轮（2 BLOCK）· S5 缺陷 1 轮（R2-D1）· S5 审计 1 轮（3 假功能 BLOCK）——均在 1 轮内收敛 | 15-review v2/v4/v6 · 04-defects-r2 |
| 门禁拦截数 | FAIL×1（G-QA-02 v1：P0 157/159）· CONCERN×2（G-DL-01 v1 / G-PM-05）· BLOCK 拦截×5（S4×2 + 审计×3）+ 缺陷×4 | gate-log · open-issues |

**token 大头**：explorer $2.19（33%，GLM-5.3——首个 general 子 agent 未吃到模型钉扎，继承主模型）→ 其余全档 deepseek-v4.1-flash（PM $0.37 / 架构 $0.52 / 前端 $0.95 / 后端 $1.06 / 组长 $0.90 / QA $0.40 / 审计 $0.14）。**模型钉扎生效性存在「进程内滞后」**：钉 `kimi-k3`/`hy4-preview` 的两个角色实际仍以 deepseek 完成（结果合格、成本反而更低），需下一轮验证。

## 四问

1. **门禁拦住了什么真问题（4 个，均在交付前）**：
   - S4 BLOCK-1：`/review/scores` 的 formula 标签与实际计算不一致（且与 UI/QA 口径冲突）——差点交付「说了待填充、实际在算」的误导性成绩页；架构裁定 (b) 后端改实现后闭环。
   - S4 BLOCK-2：测试套件未隔离 `PROXY_QUALITY_PATH`，复跑 184 测试会**清空 R2-04 首选证据道**（22 条真实数据）——不可逆数据破坏被拦下，随后加了「真实数据零触碰」守卫用例（双跑 sha256 三向一致）。
   - S5 审计 BLOCK×3（用户追加要求直接命中）：「测试连接」按钮空转谎称已发起（0 出站）、隐私开关只持久化零消费、信号时间线事件链恒空（320/320 `_chain` 缺）——三个「静态壳假功能」全部修复并经 PM live 复核。
   - G-PM-05 CONCERN：负 Δ 事实（T+1 −1.52pp）被原样保留进交付，未用任何话术掩盖——北星指标「宁可少而诚实」在终验生效。
2. **哪些门禁/流程边际价值低（形式主义）**：`12-interface-request-r2` 在升级轮中属重复登记——09 契约 v9.1 已是逐字段完整规格，前端接口清单没有新增信息量。**下轮升级轮可将其降级为「契约覆盖核对表」（只核对不重写）**。
3. **token 大头**：见上，explorer 一人占 33%（GLM-5.3 单价 ≈ deepseek 的 14 倍）；方法类工作（解剖/审计）本应全走 deepseek，属钉扎滞后损耗，非任务本身成本。
4. **下一轮只改一条**：**子 agent 模型钉扎的生效性验证**——派发 prompt 首段要求子 agent 回报实际模型 ID（如本轮 PM/QA 的回传已带），发现继承贵模型立即中止重派；或在 OpenCode 进程重启后核对 `.opencode/agents/*.md` 的 model 字段确已加载。改完观察一轮再动其他。

## 本轮的可见改进（Start/Continue）

- **Continue**：关键路径重叠（契约后 qa 前置 17-r2，与 S3 三席并行占满 ≤3）、独立审计员路线（用户要求 → 3 假功能 BLOCK）、每步 sha256 零污染守卫、CONCERN 挂账进交付说明。
- **Start（下轮）**：模型钉扎验证（唯一行动项）；升级轮跳过 12-interface-request 重写。
- **Stop**：不再把「数据积累型缺口」（R2-04 剩 5 只 / 双时点）当缺陷追责——它们是口径内的等待态，只做监测点。

## 遗留（进交付说明与 R3 议题）

R2-04 剩 5 只复核（≤G-PM-05 后顺延，监测点 M1~M5）· R2-01/03/16 双时点未到期 · R3：C1 真探测端点 / C2 注册机制 / R2-10 研究项 / holdings.js:486 同类 toISOString / NIT×9。
