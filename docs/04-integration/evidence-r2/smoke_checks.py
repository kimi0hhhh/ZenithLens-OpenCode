# -*- coding: utf-8 -*-
"""S4 集成冒烟断言：对 smoke_fetch.py 抓取的 ep_*.json 做逐条检查。

输出 smoke_checks.json（明细）+ 控制台摘要。退出码 0=全过。
运行：python smoke_checks.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FIELDS_8 = ["fund_type", "fund_type_label", "tier_reason", "verify_status",
            "verify_status_label", "verify_batch_id", "verify_note",
            "verify_review_date", "qdii_lead_note"]
FIELD_LIST_EXPECTED = ["date", "code", "gate", "p_up", "ddsm_state", "veto_crowd",
                       "veto_klow2", "signal", "opened", "t1_real", "t3_real",
                       "t15_real", "t1_real_method", "backfill_proxy_code", "created_at"]

results = []


def load(name):
    with io.open(os.path.join(HERE, "ep_%s.json" % name), "r", encoding="utf-8") as f:
        return json.load(f)


def check(group, name, cond, detail=""):
    results.append({"group": group, "check": name, "pass": bool(cond),
                    "detail": None if cond else str(detail)[:400]})
    print("[%s] %-58s %s" % ("PASS" if cond else "FAIL", group + " · " + name,
                             "" if cond else "-> " + str(detail)[:160]))


def main():
    # ---- holdings ----
    h = load("holdings").get("data") or {}
    rows = h.get("rows") or []
    check("holdings", "rows 非空（22 只）", len(rows) == 22, "len=%d" % len(rows))
    missing = []
    for r in rows:
        for k in FIELDS_8:
            if k not in r:
                missing.append("%s.%s" % (r.get("code"), k))
    check("holdings", "HoldingRow 9 个 v9.1 字段键恒在", not missing, missing[:8])
    bad_reason = [r["code"] for r in rows
                  if (r.get("valuation") or {}).get("conf_reason") is not None
                  and (r.get("valuation") or {}).get("confidence") != "unknown"]
    check("holdings", "conf_reason 仅 confidence=unknown 时非 null", not bad_reason, bad_reason)
    unknown_without = [r["code"] for r in rows
                       if (r.get("valuation") or {}).get("confidence") == "unknown"
                       and not r.get("valuation", {}).get("conf_reason")
                       and r.get("valuation", {}).get("recorded") is not False]
    check("holdings", "unknown 行带 conf_reason（读取层）", len(unknown_without) == 0, unknown_without)
    bad_qdii = [r["code"] for r in rows
                if r.get("qdii_lead_note") and r.get("fund_type") != "qdii"]
    check("holdings", "qdii_lead_note 仅 QDII 行非 null", not bad_qdii, bad_qdii)
    qdii_n = sum(1 for r in rows if r.get("qdii_lead_note"))
    details = [r["code"] for r in rows
               if any(step.get("detail") is not None
                      for step in ((r.get("valuation") or {}).get("trace") or [])) ]
    check("holdings", "trace[holdings].detail 至少一条有结构明细", len(details) > 0,
          "none; qdii_note=%d" % qdii_n)
    mv_nonnull = sum(1 for r in rows if r.get("market_value") is not None)

    # ---- holdings_summary 交叉 ----
    s = load("holdings_summary").get("data") or {}
    cr_nonnull = sum(1 for r in rows
                     if (r.get("valuation") or {}).get("change_rate") is not None)
    check("holdings_summary", "covered_count == change_rate != null 行数",
          s.get("covered_count") == cr_nonnull,
          "covered=%s vs cr_nonnull=%d" % (s.get("covered_count"), cr_nonnull))

    # ---- precision ----
    p = load("valuations_precision").get("data") or {}
    eq = p.get("estimate_quality") or {}
    off = p.get("official_summary") or {}
    check("precision", "estimate_quality 结构键齐", all(k in eq for k in
          ("groups", "weighted_mae_rate", "count", "market_value", "weight_ratio",
           "industry_baseline_mae_rate", "window_days", "window_filled_days", "note")),
          sorted(eq.keys()))
    check("precision", "official_summary 结构键齐", all(k in off for k in
          ("count", "market_value", "weight_ratio", "weighted_mae_rate", "note")),
          sorted(off.keys()))
    check("precision", "window_phase ∈ warming/first_verdict/mature",
          p.get("window_phase") in ("warming", "first_verdict", "mature"),
          p.get("window_phase"))
    check("precision", "全档参考字段保留（M3）", "weighted_mae_rate" in p and "groups" in p)
    check("precision", "官方档 note 含「既成事实」", "既成事实" in (off.get("note") or ""),
          off.get("note"))

    # ---- coverage ----
    c = load("holdings_coverage").get("data") or {}
    ab = sum(1 for r in rows if r.get("tier") in ("A", "B"))
    check("coverage", "prediction_universe_count == A+B 行数",
          c.get("prediction_universe_count") == ab,
          "universe=%s vs AB=%d" % (c.get("prediction_universe_count"), ab))
    pending_c = sum(1 for r in rows if r.get("tier") == "C"
                    and r.get("verify_status") in ("pending_validation", "validating"))
    check("coverage", "pending_verification_count == C 挂档行数",
          c.get("pending_verification_count") == pending_c,
          "pending=%s vs %d" % (c.get("pending_verification_count"), pending_c))
    check("coverage", "pending_verification_names ≤10 且非空",
          0 < len(c.get("pending_verification_names") or []) <= 10,
          c.get("pending_verification_names"))
    check("coverage", "prediction_coverage_note 非空", bool(c.get("prediction_coverage_note")),
          c.get("prediction_coverage_note"))

    # ---- signals ----
    sg = load("signals_state").get("data") or {}
    check("signals", "rolling_window_days == 20", sg.get("rolling_window_days") == 20,
          sg.get("rolling_window_days"))
    check("signals", "low_frequency_note 非空", bool(sg.get("low_frequency_note")),
          sg.get("low_frequency_note"))
    check("signals", "rolling_open_assets 为 int", isinstance(sg.get("rolling_open_assets"), int),
          sg.get("rolling_open_assets"))

    # ---- engine status ----
    e = load("engine_status").get("data") or {}
    check("engine", "shadow_status ∈ 进度枚举", e.get("shadow_status") in
          ("not_started", "recording", "qualified", "gap"), e.get("shadow_status"))
    check("engine", "shadow_audit_status ∈ idle/ok/bad", e.get("shadow_audit_status") in
          ("idle", "ok", "bad"), e.get("shadow_audit_status"))
    ls = load("ledger_shadow").get("data") or {}
    check("engine", "HUD consecutive == /ledger/shadow progress.consecutive_days",
          e.get("shadow_consecutive_days") == (ls.get("progress") or {}).get("consecutive_days"),
          "%s vs %s" % (e.get("shadow_consecutive_days"),
                        (ls.get("progress") or {}).get("consecutive_days")))

    # ---- frozen ----
    fr = load("engine_frozen").get("data") or {}
    check("frozen", "K=4 / p=0.25 / MIN_N=15 / BAND=0.02",
          fr.get("k_noise") == 4 and fr.get("p_perturb") == 0.25
          and fr.get("min_n") == 15 and fr.get("band") == 0.02,
          {k: fr.get(k) for k in ("k_noise", "p_perturb", "min_n", "band")})
    check("frozen", "baseline_method 含实测口径 + 0.5830 已退役",
          "max(恒涨率,恒跌率)" in (fr.get("baseline_method") or "")
          and "0.5830 已退役" in (fr.get("baseline_method") or ""),
          fr.get("baseline_method"))
    check("frozen", "weighting_basis == market_value", fr.get("weighting_basis") == "market_value",
          fr.get("weighting_basis"))

    # ---- ledger ----
    lg = load("ledger").get("data") or {}
    lrows = lg.get("rows") or []
    check("ledger", "行含 t1_real_method / backfill_proxy_code 键",
          all(("t1_real_method" in r and "backfill_proxy_code" in r) for r in lrows),
          "n=%d" % len(lrows))
    bf_rows = [r for r in lrows if r.get("t1_real_method")]
    check("ledger", "已回填行 method 恒 proxy_bar",
          all(r.get("t1_real_method") == "proxy_bar" for r in bf_rows),
          [r.get("t1_real_method") for r in bf_rows[:5]])
    check("ledger_shadow", "field_list 与契约 15 键逐字一致",
          ls.get("field_list") == FIELD_LIST_EXPECTED, ls.get("field_list"))
    check("ledger_shadow", "backfill_method == proxy_bar（单值）",
          ls.get("backfill_method") == "proxy_bar", ls.get("backfill_method"))
    prg = ls.get("progress") or {}
    check("ledger_shadow", "progress 含 window_days/archive_merged/history_days/baseline_source",
          prg.get("window_days") == 20 and isinstance(prg.get("archive_merged"), bool)
          and isinstance(prg.get("history_days"), int)
          and prg.get("baseline_source") == "measured", prg)

    # ---- review scores ----
    rs = load("review_scores").get("data") or {}
    hero = rs.get("hero") or {}
    check("review", "hero.data_kind == backtest", hero.get("data_kind") == "backtest",
          hero.get("data_kind"))
    check("review", "scores 3 行且 sample_window 恒 full",
          len(rs.get("scores") or []) == 3
          and all(r.get("sample_window") == "full" for r in (rs.get("scores") or [])),
          [(r.get("window"), r.get("sample_window")) for r in (rs.get("scores") or [])])
    t1 = (rs.get("scores") or [{}])[0]
    check("review", "T1 hit_rate 非 null（B5 真实出数）", t1.get("hit_rate") is not None, t1)
    delta_ok = all((r.get("delta_pp") is None) == (r.get("baseline_rate") is None)
                   for r in (rs.get("scores") or []))
    check("review", "delta 与 baseline 同 null/同有值（不填估计值）", delta_ok,
          [(r.get("window"), r.get("baseline_status")) for r in (rs.get("scores") or [])])
    rss = load("review_scores_shadow").get("data") or {}
    check("review", "shadow_live 口径可读", rss.get("data_kind") == "shadow_live",
          rss.get("data_kind"))

    # ---- sources ----
    sh = load("sources_health").get("data") or {}
    srcs = sh.get("sources") or []
    check("sources", "四源均有 fail_window_7d/fail_window_days",
          len(srcs) >= 4 and all(isinstance(s.get("fail_window_7d"), int)
                                 and s.get("fail_window_days") == 7 for s in srcs),
          [(s.get("source_id"), s.get("fail_window_7d")) for s in srcs])

    # ---- settings holdings-data ----
    shd = load("settings_holdings_data").get("data") or {}
    ms = shd.get("main_source") or {}
    check("settings", "main_source.path == data/holdings.json",
          str(ms.get("path") or "").replace("\\", "/").endswith("data/holdings.json"),
          ms.get("path"))
    check("settings", "import_available=false 且有可读原因",
          shd.get("import_available") is False and bool(shd.get("import_disabled_reason")),
          {"avail": shd.get("import_available"), "reason": shd.get("import_disabled_reason")})

    # ---- score chain ----
    sc = load("score_chain").get("data") or {}
    check("score-chain", "V11 兄弟字段并存",
          "bootstrap_percentiles_measured" in sc and "real_engine" in sc, sorted(sc.keys()))

    # ---- negative ----
    neg = load("neg_review_bad_kind")
    check("negative", "非法 data_kind → E_VALIDATION",
          neg.get("ok") is False and (neg.get("error") or {}).get("code") == "E_VALIDATION",
          neg.get("error"))

    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    with io.open(os.path.join(HERE, "smoke_checks.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"total": total, "passed": passed, "results": results},
                           ensure_ascii=False, indent=1))
    print("CHECKS %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
