# -*- coding: utf-8 -*-
"""S6 PM 终验 · 后端只读快照 + 口径对照值提取（不改产品数据）。"""
import io
import json
import os
import urllib.request

BASE = "http://127.0.0.1:8791/api/v1"
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BKD = os.path.join(OUT, "backend")

ENDPOINTS = [
    "runtime", "holdings", "holdings/summary", "holdings/coverage", "holdings/risk",
    "valuations", "valuations/precision", "predictions", "predictions/017193",
    "portfolio/forecast", "signals/state", "review/scores", "review/reconciliation",
    "review/cv-config", "ledger", "ledger/shadow", "ledger/chain",
    "factors/pans", "factors/books", "factors/score-chain", "factors/lifecycle",
    "factors/governance-cycle", "factors/dig-records",
    "engine/status", "engine/inputs?code=017193", "engine/ddsm/cube?code=017193",
    "engine/frozen-params", "engine/registry", "engine/training-status",
    "engine/arena", "engine/shadow-review",
    "settings", "settings/holdings-data", "data-sources/health", "about",
    "meta/definitions",
]


def fetch(path):
    url = BASE + "/" + path
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main():
    summary = {"endpoints": {}, "key": {}}
    for p in ENDPOINTS:
        try:
            st, env = fetch(p)
            name = p.replace("/", "_").replace("?", "_")
            with io.open(os.path.join(BKD, "ep_%s.json" % name), "w", encoding="utf-8") as f:
                json.dump(env, f, ensure_ascii=False, indent=2)
            ok = bool(env.get("ok"))
            summary["endpoints"][p] = {"status": st, "ok": ok}
            data = env.get("data")
            if p == "holdings":
                rows = data.get("rows", [])
                modes = {}
                null_pct = []
                for row in rows:
                    v = row.get("valuation") or {}
                    m = v.get("mode")
                    modes[m] = modes.get(m, 0) + 1
                    if v.get("pct") is None:
                        null_pct.append(row.get("code"))
                summary["key"]["holdings_modes"] = modes
                summary["key"]["holdings_null_pct"] = null_pct
                summary["key"]["holdings_count"] = len(rows)
            if p == "holdings/summary":
                summary["key"]["summary"] = data
            if p == "valuations/precision":
                summary["key"]["precision"] = data
            if p == "portfolios/forecast" or p == "portfolio/forecast":
                summary["key"]["forecast"] = data
            if p == "signals/state":
                summary["key"]["signals_state"] = {
                    "state": data.get("state"),
                    "gates": data.get("gates"),
                    "excluded_gates": data.get("excluded_gates"),
                }
            if p == "review/scores":
                summary["key"]["review_scores"] = data
            if p == "review/cv-config":
                summary["key"]["cv_config"] = data
            if p == "predictions/017193":
                d = data or {}
                summary["key"]["pred_017193"] = {
                    "gate": d.get("gate"), "p_up": d.get("p_up"),
                    "ddsm_state": d.get("ddsm_state"), "veto_crowd": d.get("veto_crowd"),
                    "veto_klow2": d.get("veto_klow2"), "signal": d.get("signal"),
                    "windows": d.get("windows"), "metrics": d.get("metrics"),
                }
            if p == "engine/frozen-params":
                summary["key"]["frozen"] = data
            if p == "engine/ddsm/cube?code=017193":
                summary["key"]["cube"] = {
                    "production_layer": data.get("production_layer"),
                    "research_layer": data.get("research_layer"),
                    "default_layer": data.get("default_layer"),
                    "valid_coverage_naive_pct": data.get("valid_coverage_naive_pct"),
                    "valid_coverage_ddsm_pct": data.get("valid_coverage_ddsm_pct"),
                    "p_std_ddsm": data.get("p_std_ddsm"),
                    "p_std_naive": data.get("p_std_naive"),
                    "extreme_count_ddsm": data.get("extreme_count_ddsm"),
                    "extreme_count_naive": data.get("extreme_count_naive"),
                    "walkforward_delta_pp": data.get("walkforward_delta_pp"),
                    "legend": data.get("legend"),
                }
            if p == "engine/arena":
                summary["key"]["arena"] = {
                    "color_scheme": data.get("color_scheme"),
                    "rows": len(data.get("rows", [])),
                    "legend": data.get("legend"),
                }
            if p == "engine/status":
                summary["key"]["engine_status"] = data
            if p == "engine/shadow-review":
                summary["key"]["shadow_review"] = data
            if p == "ledger/shadow":
                summary["key"]["ledger_shadow"] = data
            if p == "settings":
                summary["key"]["settings"] = data
            if p == "about":
                summary["key"]["about"] = data
            if p == "engine/inputs?code=017193":
                summary["key"]["inputs_017193"] = data
        except Exception as e:
            summary["endpoints"][p] = {"error": str(e)}
    with io.open(os.path.join(OUT, "backend_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    okc = sum(1 for v in summary["endpoints"].values() if v.get("ok"))
    print("endpoints ok %d/%d" % (okc, len(ENDPOINTS)))
    print(json.dumps(summary["key"], ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
