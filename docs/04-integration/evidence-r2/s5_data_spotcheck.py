# -*- coding: utf-8 -*-
"""S5 终验 · 数据面抽查：method/top_n、缓存顶格、chain 单测调用。"""
import io
import json
import os
import subprocess
import sys

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))

# 1) 最近 valuation_history 中 holdings 档记录的 method / top_n
path = os.path.join(SRC, "data", "snapshot", "valuation_history.jsonl")
seen = {}
if os.path.isfile(path):
    with io.open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        tr = r.get("trace") or []
        det = None
        for step in tr:
            if isinstance(step, dict) and step.get("step") == "holdings" \
                    and isinstance(step.get("detail"), dict):
                det = step["detail"]
        if det and det.get("used", True) is not False:
            code = r.get("code")
            if code not in seen:
                seen[code] = {
                    "date": r.get("date"),
                    "method": det.get("method"),
                    "top_n": det.get("top_n"),
                    "covered_weight_pct": det.get("covered_weight_pct"),
                    "included_markets": det.get("included_markets"),
                }
            if len(seen) >= 8:
                break
print("holdings-detail samples:")
for k, v in seen.items():
    print(" ", k, json.dumps(v, ensure_ascii=False))

# 2) F10 缓存行数（active 5 只）
cache = {}
for code in ("025500", "018957", "021528", "013566", "014320"):
    p = os.path.join(SRC, "data", "cache", "holdings", "%s.json" % code)
    if os.path.isfile(p):
        obj = json.load(io.open(p, encoding="utf-8"))
        rows = obj.get("rows") or obj.get("holdings") or obj.get("top") or []
        cache[code] = {"rows": len(rows), "top_n": obj.get("top_n"),
                       "keys": sorted(obj.keys())[:8]}
print("f10 cache:", json.dumps(cache, ensure_ascii=False))

# 3) chain 三态单测（stored / recomputed / null）
log = os.path.join(HERE, "s5-chain-tests.log")
with io.open(log, "w", encoding="utf-8") as f:
    r = subprocess.run([sys.executable, "-m", "unittest",
                        "tests.test_ledger_chain_recompute", "-v"],
                       cwd=SRC, stdout=f, stderr=subprocess.STDOUT)
text = io.open(log, encoding="utf-8", errors="replace").read()
ran, ok = None, "OK" in text
for line in text.splitlines():
    if line.startswith("Ran "):
        ran = int(line.split()[1])
names = [line for line in text.splitlines() if " ... ok" in line or " ... FAIL" in line]
print("chain tests: rc=%s ran=%s ok=%s names=%d" % (r.returncode, ran, ok, len(names)))
for n in names:
    print("  ", n.strip()[:120])
