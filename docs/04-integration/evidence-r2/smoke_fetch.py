# -*- coding: utf-8 -*-
"""S4 集成冒烟：dev-lead 对 R2 后端（8791）关键路径实测抓取。

只读；输出证据到本目录 ep_*.json + smoke_summary.json。
运行：python smoke_fetch.py [port]
"""
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
BASE = "http://127.0.0.1:%d/api/v1" % PORT
HERE = os.path.dirname(os.path.abspath(__file__))

ENDPOINTS = [
    ("runtime", "/runtime", 8000),
    ("holdings", "/holdings?with=valuation,nav,prediction", 30000),
    ("holdings_summary", "/holdings/summary", 8000),
    ("valuations_precision", "/valuations/precision", 8000),
    ("holdings_coverage", "/holdings/coverage", 8000),
    ("signals_state", "/signals/state", 8000),
    ("ledger", "/ledger?limit=60", 30000),
    ("ledger_shadow", "/ledger/shadow?limit=60", 30000),
    ("engine_status", "/engine/status", 30000),
    ("engine_frozen", "/engine/frozen-params", 8000),
    ("engine_shadow_review", "/engine/shadow-review", 8000),
    ("review_scores", "/review/scores", 30000),
    ("review_scores_shadow", "/review/scores?data_kind=shadow_live", 30000),
    ("review_recon", "/review/reconciliation?limit=60", 30000),
    ("review_cv", "/review/cv-config", 8000),
    ("portfolio_forecast", "/portfolio/forecast", 30000),
    ("predictions", "/predictions", 30000),
    ("sources_health", "/data-sources/health", 8000),
    ("settings_holdings_data", "/settings/holdings-data", 8000),
    ("factors_pans", "/factors/pans", 30000),
    ("score_chain", "/factors/score-chain", 30000),
    ("engine_cube", "/engine/ddsm/cube?code=017193", 30000),
]

NEGATIVE = [
    ("neg_review_bad_kind", "/review/scores?data_kind=bogus", 8000),
]


def fetch(path, timeout_ms):
    url = BASE + path
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout_ms / 1000.0) as r:
            body = r.read().decode("utf-8")
            status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:  # noqa: BLE001
        body = json.dumps({"ok": False, "error": {"code": "E_CONNECT", "message": str(e)}})
        status = 0
    ms = int((time.time() - t0) * 1000)
    try:
        env = json.loads(body)
    except ValueError:
        env = {"ok": False, "error": {"code": "E_PARSE_CLIENT", "message": body[:200]}}
    return status, ms, env


def main():
    results = []
    for name, path, timeout in ENDPOINTS:
        status, ms, env = fetch(path, timeout)
        with io.open(os.path.join(HERE, "ep_%s.json" % name), "w", encoding="utf-8") as f:
            f.write(json.dumps(env, ensure_ascii=False, indent=1))
        ok = bool(env.get("ok"))
        results.append({"name": name, "path": path, "http": status, "ok": ok, "ms": ms,
                        "err": (env.get("error") or {}).get("code") if not ok else None})
        print("[%s] %-24s http=%s ok=%s %dms %s" % (
            "PASS" if ok else "FAIL", name, status, ok, ms,
            "" if ok else str(env.get("error"))))
    for name, path, timeout in NEGATIVE:
        status, ms, env = fetch(path, timeout)
        with io.open(os.path.join(HERE, "ep_%s.json" % name), "w", encoding="utf-8") as f:
            f.write(json.dumps(env, ensure_ascii=False, indent=1))
        ok = (env.get("ok") is False and (env.get("error") or {}).get("code") == "E_VALIDATION")
        results.append({"name": name, "path": path, "http": status, "ok": ok, "ms": ms,
                        "err": (env.get("error") or {}).get("code")})
        print("[%s] %-24s http=%s expect=E_VALIDATION got=%s" % (
            "PASS" if ok else "FAIL", name, status,
            (env.get("error") or {}).get("code")))
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    with io.open(os.path.join(HERE, "smoke_summary.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"base": BASE, "total": total, "passed": passed,
                            "results": results}, ensure_ascii=False, indent=1))
    print("SMOKE %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
