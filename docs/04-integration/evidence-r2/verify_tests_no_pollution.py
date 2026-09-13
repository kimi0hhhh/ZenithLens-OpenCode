# -*- coding: utf-8 -*-
"""S4 复验 · BLOCK-2 独立复验：全量测试双跑 + 产线数据 sha256 前后不变。

判定：
- run1/run2 均 `Ran N tests ... OK`；
- 每轮前后、以及 run1_after 与 run2_before 之间，监控集 sha256 全一致；
- 输出 verify_tests_no_pollution.json。
运行：python verify_tests_no_pollution.py
"""
import hashlib
import io
import json
import os
import subprocess
import sys

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = [
    "data/snapshot/proxy_quality.json",
    "data/snapshot/review_scores.json",
    "data/snapshot/accuracy.json",
    "data/snapshot/valuation_history.jsonl",
    "data/health.json",
    "data/health-log.jsonl",
    "data/holdings.json",
    "data/qdii_correction.json",
    "data/review/tier_reviews.jsonl",
    "data/review/qdii_review.jsonl",
    "ledger/shadow_signals.jsonl",
    "ledger/backfill.jsonl",
]


def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def snap():
    out = {}
    for rel in WATCH:
        p = os.path.join(SRC, rel.replace("/", os.sep))
        out[rel] = sha(p) if os.path.isfile(p) else None
    return out


def run_suite(tag):
    log = os.path.join(HERE, "backend-tests-%s.log" % tag)
    with io.open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                            "-s", "tests", "-p", "test_*.py"],
                           cwd=SRC, stdout=f, stderr=subprocess.STDOUT)
    text = io.open(log, encoding="utf-8", errors="replace").read()
    ok = (r.returncode == 0 and "OK" in text.splitlines()[-1] if text else False)
    ran = None
    for line in text.splitlines():
        if line.startswith("Ran ") and " tests" in line:
            ran = int(line.split()[1])
    if not ok:  # 更稳的判定：末段含 OK
        ok = r.returncode == 0 and ("\nOK" in text or text.rstrip().endswith("OK"))
    return {"tag": tag, "rc": r.returncode, "ran": ran, "ok": bool(ok), "log": log}


def eq(a, b):
    return all(a.get(k) == b.get(k) for k in WATCH)


def main():
    before1 = snap()
    r1 = run_suite("run1")
    after1 = snap()
    before2 = snap()
    r2 = run_suite("run2")
    after2 = snap()

    report = {
        "watch": WATCH,
        "run1": r1, "run2": r2,
        "guard": {
            "run1_before_eq_after": eq(before1, after1),
            "run1_after_eq_run2_before": eq(after1, before2),
            "run2_before_eq_after": eq(before2, after2),
        },
        "hashes": {"before1": before1, "after1": after1, "after2": after2},
        "diffs": [rel for rel in WATCH
                  if not (before1.get(rel) == after1.get(rel) == after2.get(rel))],
    }
    with io.open(os.path.join(HERE, "verify_tests_no_pollution.json"), "w",
                 encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1))
    print("run1: rc=%s ran=%s ok=%s" % (r1["rc"], r1["ran"], r1["ok"]))
    print("run2: rc=%s ran=%s ok=%s" % (r2["rc"], r2["ran"], r2["ok"]))
    print("guard:", json.dumps(report["guard"], ensure_ascii=False))
    print("diffs:", report["diffs"])
    print("proxy_sha256:", after2.get("data/snapshot/proxy_quality.json"))
    allok = (r1["ok"] and r2["ok"] and all(report["guard"].values())
             and not report["diffs"])
    print("NO-POLLUTION:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
