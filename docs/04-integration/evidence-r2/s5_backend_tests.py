# -*- coding: utf-8 -*-
"""S5 终验 · 后端单跑 + 产线数据 sha256 守卫（≥213 预期）。"""
import hashlib
import io
import json
import os
import subprocess
import sys

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = [
    "data/snapshot/proxy_quality.json", "data/snapshot/review_scores.json",
    "data/snapshot/accuracy.json", "data/snapshot/valuation_history.jsonl",
    "data/health.json", "data/health-log.jsonl", "data/holdings.json",
    "data/qdii_correction.json", "data/review/tier_reviews.jsonl",
    "data/review/qdii_review.jsonl", "ledger/shadow_signals.jsonl",
    "ledger/backfill.jsonl",
]


def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def snap():
    return {rel: (sha(os.path.join(SRC, rel.replace("/", os.sep)))
                  if os.path.isfile(os.path.join(SRC, rel.replace("/", os.sep))) else None)
            for rel in WATCH}


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "s5"
    before = snap()
    log = os.path.join(HERE, "%s-backend-tests.log" % prefix)
    with io.open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                            "-s", "tests", "-p", "test_*.py"],
                           cwd=SRC, stdout=f, stderr=subprocess.STDOUT)
    text = io.open(log, encoding="utf-8", errors="replace").read()
    after = snap()
    ran, ok = None, False
    for line in text.splitlines():
        if line.startswith("Ran ") and " tests" in line:
            ran = int(line.split()[1])
        if line.strip() == "OK":
            ok = True
    diffs = [rel for rel in WATCH if before.get(rel) != after.get(rel)]
    out = {"rc": r.returncode, "ran": ran, "ok": ok, "diffs": diffs,
           "proxy_sha256": after.get("data/snapshot/proxy_quality.json")}
    with io.open(os.path.join(HERE, "%s_backend_tests.json" % prefix), "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False))
    return 0 if (r.returncode == 0 and ok and not diffs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
