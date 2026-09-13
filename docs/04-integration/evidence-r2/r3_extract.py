# -*- coding: utf-8 -*-
"""R3 F2 伪影修复 · 代码与记录抽查提取。"""
import io
import json

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
OUT = SRC + r"\docs\04-integration\evidence-r2\r3-code-records.txt"
w = io.open(OUT, "w", encoding="utf-8")

t = io.open(SRC + r"\factor_engine.py", encoding="utf-8").read()
for kw in ("def _candidate_identity_ids", "def _incumbent_series", "def _f2_independence"):
    i = t.find(kw)
    w.write("=== %s @line %d ===\n%s\n\n" % (kw, t[:i].count("\n") + 1, t[i:i + 1600]))

d = json.load(io.open(SRC + r"\ledger\adopted_factors.json", encoding="utf-8"))
w.write("adopted records: %s\n\n" % [r.get("factor_id") for r in d])
for r in d:
    fid = r.get("factor_id")
    if fid in ("crowd6", "klow2"):
        w.write("===== %s =====\n" % fid)
        w.write(json.dumps({k: r.get(k) for k in
                            ("factor_id", "total_score", "verdict", "max_collinearity",
                             "collinear_with", "added_at", "note")},
                           ensure_ascii=False, indent=1)[:1000] + "\n")
        if r.get("correction"):
            w.write("CORRECTION:\n" + json.dumps(r["correction"], ensure_ascii=False,
                                                 indent=1)[:1600] + "\n")
        w.write("\n")
w.close()
print("written")
