# -*- coding: utf-8 -*-
"""S4b 审计併轨用素材提取：契约 chain 定义 + 隐私金额消费点。"""
import glob
import io
import os
import re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"

# 1) 契约中 ledger/chain 相关段
t = io.open(os.path.join(SRC, "docs", "01-architecture", "09-api-contract-r2.md"),
            encoding="utf-8").read()
w = io.open(os.path.join(OUT, "contract-chain.txt"), "w", encoding="utf-8")
for kw in ("ledger/chain", "chain_available", "ChainStep"):
    idx = 0
    while True:
        i = t.find(kw, idx)
        if i < 0:
            break
        w.write("=== %s @%d ===\n%s\n\n" % (kw, i, t[max(0, i - 260):i + 560]))
        idx = i + 1
w.close()

# 2) 前端金额渲染消费点（amt( 调用与 .amt class）
rows = []
for p in glob.glob(os.path.join(SRC, "static", "js", "**", "*.js"), recursive=True):
    if "mock" in p.replace("/", os.sep):
        continue
    src = io.open(p, encoding="utf-8").read()
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r"\bamt\(|['\"]amt['\"]|\.amt\b|mask-holdings", line):
            rel = os.path.relpath(p, SRC).replace(os.sep, "/")
            rows.append("%s:%d  %s" % (rel, i, line.strip()[:170]))
io.open(os.path.join(OUT, "amt-consumers.txt"), "w", encoding="utf-8").write("\n".join(rows))
print("amt lines:", len(rows))
print("contract-chain written")
