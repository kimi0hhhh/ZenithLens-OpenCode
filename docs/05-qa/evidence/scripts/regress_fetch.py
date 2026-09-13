# -*- coding: utf-8 -*-
"""S5 定向回归：重拉关键只读端点，覆盖 evidence/ep_*.json（基线已备份到 evidence/baseline-v1/）。"""
import io
import json
import os
import sys
import urllib.request

B = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BASE = "http://127.0.0.1:8791/api/v1"

ENDPOINTS = [
    ("/runtime", "ep_runtime.json"),
    ("/holdings", "ep_holdings.json"),
    ("/holdings/summary", "ep_holdings_summary.json"),
    ("/holdings/coverage", "ep_holdings_coverage.json"),
    ("/valuations/precision", "ep_valuations_precision.json"),
    ("/signals/state", "ep_signals_state.json"),
    ("/engine/frozen-params", "ep_engine_frozen-params.json"),
    ("/engine/ddsm", "ep_engine_ddsm.json"),
    ("/engine/ddsm/cube?code=017193", "ep_engine_ddsm_cube_017193.json"),
    ("/engine/status", "ep_engine_status.json"),
    ("/engine/registry", "ep_engine_registry.json"),
    ("/engine/training-status", "ep_engine_training-status.json"),
    ("/engine/shadow-review", "ep_engine_shadow-review.json"),
    ("/engine/inputs?code=017193", "ep_engine_inputs_017193.json"),
    ("/engine/arena", "ep_engine_arena.json"),
    ("/predictions", "ep_predictions.json"),
    ("/predictions/017193", "ep_predictions_017193.json"),
    ("/portfolio/forecast", "ep_portfolio_forecast.json"),
    ("/ledger/shadow", "ep_ledger_shadow.json"),
    ("/meta/definitions", "ep_meta_definitions.json"),
    ("/factors/pans", "ep_factors_pans.json"),
    ("/factors/books", "ep_factors_books.json"),
    ("/factors/score-chain", "ep_factors_score-chain.json"),
    ("/factors/governance-cycle", "ep_factors_governance-cycle.json"),
    ("/factors/dig-records", "ep_factors_dig-records.json"),
    ("/factors/lifecycle", "ep_factors_lifecycle.json"),
    ("/review/scores", "ep_review_scores.json"),
    ("/review/reconciliation", "ep_review_reconciliation.json"),
    ("/review/cv-config", "ep_review_cv-config.json"),
    ("/data-sources/health", "ep_data-sources_health.json"),
    ("/settings", "ep_settings.json"),
    ("/settings/holdings-data", "ep_settings_holdings-data.json"),
    ("/about", "ep_about.json"),
]


def main():
    results = []
    fail = 0
    for path, name in ENDPOINTS:
        url = BASE + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                code = resp.getcode()
            data = json.loads(raw)
            with io.open(os.path.join(B, name), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            results.append({"path": path, "file": name, "http": code, "ok": bool(data.get("ok"))})
        except Exception as e:  # noqa
            fail += 1
            results.append({"path": path, "file": name, "http": None, "ok": False, "error": str(e)})
        print(("PASS " if results[-1]["ok"] else "FAIL ") + path + " -> " + name)
    out = {"total": len(ENDPOINTS), "fail": fail, "results": results}
    with io.open(os.path.join(B, "regress_fetch.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("SUMMARY fetched=%d fail=%d" % (len(ENDPOINTS) - fail, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
