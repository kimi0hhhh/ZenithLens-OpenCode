# -*- coding: utf-8 -*-
"""open-issues 状态刷新（S5 终验）。"""
import io

p = r"C:\Users\10719\Documents\Default Project\.opencode\state\open-issues.md"
t = io.open(p, encoding="utf-8").read()
out = []
for ln in t.split("\n"):
    if "### R2 S5" in ln:
        ln = ln.replace("QA 缺陷分流完成·待修复", "QA 缺陷 + 审计 BLOCK：修复完成 · 待 QA 回归")
    if "ISSUE-ZL-R2-S5-A1" in ln:
        ln += " → ✅ 已修复（2026-09-13，15-code-review-r2 v5 §9 复验；live/133 断言）· 待 QA 回归"
    if "ISSUE-ZL-R2-S5-A2" in ln:
        ln += " → ✅ 已修复（§9 销项；S1~S4 断言）· 待 QA 回归"
    if "ISSUE-ZL-R2-S5-A3" in ln:
        ln += " → ✅ 已修复（§9 销项；live 六步对账 + chain_source）· 待 QA 回归"
    if "R2-D1 | P1" in ln:
        ln += " → ✅ 已修复（前端 §7；dev-lead §9 销项）· 待 QA 回归（U2-03-成 / T2-F2-21-C）"
    if "R2-D2 | P3" in ln:
        ln += " → ✅ 已修复（后端 §11；live 字面断言）· 待 QA 回归"
    if "R2-D3 | P3" in ln:
        ln += " → ✅ 已修复（最小版 §11；同型 409 + 全局串行）· 待 QA 回归"
    if "R2-D4 | P3" in ln:
        ln += " → ✅ 已修复（前端 §7；D4 断言）· 待 QA 回归"
    if "ZL-R2-S5-C1" in ln:
        ln += " → ✅ 已裁定（10-r2 §11.1：R2=本地校验收口；真探测 R3 立项）"
    if "ZL-R2-S5-C2" in ln:
        ln += " → ✅ 已裁定 + 文案落地（§11.2；单版本/预留态注）"
    if "ZL-R2-S5-C3" in ln:
        ln += " → ✅ 采纳并落码（§11.3；契约 v9.3；live/单测验证）"
    if "审计 SHOULD/NIT 挂账" in ln:
        ln = ln.rstrip() + "（另：源 data/cache/nav/*.tmp 残留 2 个，R3 顺手清理）"
    out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("updated, chars=", len("\n".join(out)))
