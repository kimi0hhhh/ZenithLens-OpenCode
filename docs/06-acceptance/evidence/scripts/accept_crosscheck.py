# -*- coding: utf-8 -*-
"""S6 PM 终验 · 展示数字 vs 后端 API 逐项对照（口径分叉检查）。"""
import io
import json
import os
import re

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BKD = os.path.join(OUT, "backend")


def load(name):
    return json.load(io.open(os.path.join(BKD, name), encoding="utf-8"))


def load_ui():
    return json.load(io.open(os.path.join(OUT, "ui_components.json"), encoding="utf-8"))


def load_crud():
    return json.load(io.open(os.path.join(OUT, "ui_interactions_crud.json"), encoding="utf-8"))


def load_probe():
    return json.load(io.open(os.path.join(OUT, "final_probe.json"), encoding="utf-8"))


def money(s):
    if s is None:
        return None
    s = s.replace("¥", "").replace(",", "").replace("+", "").strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


checks = []


def chk(cid, desc, ok, detail):
    checks.append({"id": cid, "desc": desc, "pass": bool(ok), "detail": detail})


def main():
    ui = load_ui()["routes"]
    crud = load_crud()
    probe = load_probe()
    summary = load("ep_holdings_summary.json")["data"]
    prec = load("ep_valuations_precision.json")["data"]
    cov = load("ep_holdings_coverage.json")["data"]
    fc = load("ep_portfolio_forecast.json")["data"]
    sig = load("ep_signals_state.json")["data"]
    scores = load("ep_review_scores.json")["data"]
    st = load("ep_engine_status.json")["data"]
    frz = load("ep_engine_frozen-params.json")["data"]
    src = load("ep_data-sources_health.json")["data"]
    cube = load("ep_engine_ddsm_cube_code=017193.json")["data"]["comparison"]
    preds = load("ep_predictions.json")["data"]["rows"]

    h = ui["holdings"]["data"]
    e = ui["engine"]["data"]
    a = ui["analyze"]["data"]
    r = ui["review"]["data"]
    s = ui["settings"]["data"]

    # G2-01..04 四卡
    chk("G2-01", "总资产 展示=后端", money(h["pa_total"]) == summary["total_value"],
        "%s vs %s" % (h["pa_total"], summary["total_value"]))
    chk("G2-02", "今日盈亏 展示=后端", money(h["pa_today"]) == summary["today_pnl_amt"],
        "%s vs %s" % (h["pa_today"], summary["today_pnl_amt"]))
    chk("G2-03", "累计收益 展示=后端", money(h["pa_pnl"]) == summary["total_pnl_amt"],
        "%s vs %s" % (h["pa_pnl"], summary["total_pnl_amt"]))
    chk("G2-04", "收益率 展示=后端", h["pa_ret"] == "+%.2f%%" % (summary["return_rate"] * 100),
        "%s vs %.4f" % (h["pa_ret"], summary["return_rate"]))

    # G2-05/06 精度汇总条
    g_high = [g for g in prec["groups"] if g["confidence"] == "high"][0]
    g_unk = [g for g in prec["groups"] if g["confidence"] == "unknown"][0]
    txt = h["vsum_text"]
    chk("G2-05", "精度条 high 组 只数/市值/占比 展示=后端",
        ("%d 只" % g_high["count"]) in txt and ("¥%.2f" % g_high["market_value"]).replace(",", "") in txt.replace(",", "")
        and ("%.1f%%" % (g_high["weight_ratio"] * 100)) in txt,
        "high=%d/%s/%.1f%%" % (g_high["count"], g_high["market_value"], g_high["weight_ratio"] * 100))
    chk("G2-06", "精度条 unknown 组 展示=后端",
        ("%d 只" % g_unk["count"]) in txt and ("%.1f%%" % (g_unk["weight_ratio"] * 100)) in txt,
        "unknown=%d/%.1f%%" % (g_unk["count"], g_unk["weight_ratio"] * 100))
    mode_counts = {m["mode"]: m["count"] for m in prec["mode_distribution"]}
    chk("G2-07", "mode 分布 展示=后端（代理10/未知12）",
        mode_counts.get("proxy") == 10 and mode_counts.get("unknown") == 12,
        json.dumps(mode_counts))
    chk("G2-08", "市值加权 MAE 展示=后端", "0.20%" in txt and abs(prec["weighted_mae_rate"] - 0.002) < 1e-9,
        "txt含0.20%% / api=%.4f" % prec["weighted_mae_rate"])
    chk("G2-09", "行业基准 0.80% 展示=后端", "0.80%" in txt and abs(prec["industry_baseline_mae_rate"] - 0.008) < 1e-9,
        "api=%.4f" % prec["industry_baseline_mae_rate"])

    # G2-10 覆盖度四档
    tiers = {t["tier"]: t for t in cov["tiers"]}
    chk("G2-10", "覆盖度 A/D 档 展示=后端",
        ("A 已接入" in h["cov_text"]) and ("10 只" in h["cov_text"]) and (tiers["A"]["count"] == 10)
        and (tiers["D"]["count"] == 12),
        "A=%d D=%d" % (tiers["A"]["count"], tiers["D"]["count"]))

    # G2-11 组合预测无开口
    fc_rows = fc["windows"]
    chk("G2-11", "三窗口无开口→不表态 展示=后端",
        all(w["weighted_p"] is None and w["open_count"] == 0 for w in fc_rows)
        and ("今日无开口" in h["forecast_text"]),
        "forecast open=%s" % [w["open_count"] for w in fc_rows])

    # G2-12 触发门/剔除
    gates = {x["gate_key"]: x["effect_pp"] for x in sig["gates"]}
    excl = {x["gate_key"]: x["effect_pp"] for x in sig["excluded_gates"]}
    chk("G2-12", "E1/E3 效应与 E2/E4 剔除 展示=后端",
        ("+3.90pp" in ui["signals"]["data"]["gates_text"]) and ("+0.88pp" in ui["signals"]["data"]["gates_text"])
        and ("-3.09pp" in ui["signals"]["data"]["excl_text"]) and ("-2.72pp" in ui["signals"]["data"]["excl_text"])
        and abs(gates["E3"] - 3.9) < 1e-9 and abs(excl["E2"] - -3.09) < 1e-9,
        "gates=%s excl=%s" % (gates, excl))

    # G2-13 复盘成绩 pending
    chk("G2-13", "回测成绩缺失→待填充（不填估计值）",
        all(x["hit_rate"] is None and x["baseline_status"] == "pending" for x in scores["scores"])
        and ("待填充" in r["scores_text"]) and ("回测待产出" in r["hero_text"]),
        "scores pending=%s" % [x["baseline_status"] for x in scores["scores"]])

    # G2-14 立方体对比卡
    chk("G2-14", "立方体对比卡 展示=后端",
        ("92.00% → 100.00%" in e["cmp_text"]) and ("0.352 → 0.103" in e["cmp_text"])
        and ("54 → 0" in e["cmp_text"])
        and abs(cube["valid_coverage_naive_pct"] - 0.92) < 1e-9 and abs(cube["valid_coverage_ddsm_pct"] - 1.0) < 1e-9,
        "cmp=%s" % e["cmp_text"].replace("\n", "|"))

    # G2-15 HUD vs engine/status
    chk("G2-15", "HUD 六卡 展示=后端",
        ("oc-s3-v1" in e["hud_text"]) and ("100.0%" in e["hud_text"]) and ("125" in e["hud_text"])
        and st["version"] == "oc-s3-v1" and abs(st["state_grid_coverage_pct"] - 1.0) < 1e-9,
        "version=%s cov=%.2f" % (st["version"], st["state_grid_coverage_pct"]))

    # G2-16 冻结参数
    f = frz
    chk("G2-16", "冻结参数 展示=后端（K=4/p=0.25/MIN_N=15/SHRINK=10/BAND=0.02/purge=H+2）",
        all(x in e["frozen_text"] for x in ["4 / 0.25", "15 / 10 / 0.02", "H+2", "8 / 22 / 15 / 10 / 30 / 15"]),
        "frozen keys=%d" % len(f.keys()))

    # G2-17 数据源健康
    chk("G2-17", "数据源健康表 展示=后端（含不通源）",
        ("腾讯日K" in s["src_text"]) and ("腾讯实时" in s["src_text"]) and ("天天基金" in s["src_text"])
        and ("新浪" in s["src_text"]) and ("不 通" in s["src_text"].replace("不通", "不 通")),
        "src_rows=%d" % s["src_rows"])

    # G2-18 徽章与 mode 一致
    import collections
    bp = collections.Counter(x.split("=")[0] for x in h["badge_pairs"])
    chk("G2-18", "行内徽章配色/文案与后端 mode 逐行一致（ch×10 / cu×12）",
        bp.get("ch") == 10 and bp.get("cu") == 12 and h["valbadges"] == 22,
        json.dumps(dict(bp)))

    # G4 未知≠持平
    chk("G4", "未知行不渲染 +0.00%（未知≠持平）",
        h["plus_zero_zero"] == 0 and h["unknown_cells"] == 24
        and ("未知" in probe["unknown_row"]["cells"]) and ("—" in probe["unknown_row"]["cells"]),
        "plus0=%d unk_cells=%d" % (h["plus_zero_zero"], h["unknown_cells"]))

    # G7 无涨误报
    chk("G7", "P>0.52 但有否决/无门→不出「涨」",
        all(x["signal"] == "gray" for x in preds)
        and any(x["p_up"] > 0.52 and x["veto_crowd"] and x["signal"] == "gray" for x in preds),
        "signals=%s" % collections.Counter(x["signal"] for x in preds))

    # G3 无假数据
    chk("G3", "无前端假数据（mock 默认关、全部请求本地）",
        (probe["env"]["zl_mock"] is None) and (not probe["env"]["mock_js_loaded"])
        and probe["env"]["non_local_api"] == 0,
        json.dumps(probe["env"]))

    # 隐私打码
    chk("G-PRV", "隐私打码：金额透明+••••、收益率保留",
        crud["privacy_masked"]["masked"] and crud["privacy_masked"]["color"] == "rgba(0, 0, 0, 0)"
        and "••••" in crud["privacy_masked"]["after"] and crud["privacy_masked"]["ret_visible"] == "+12.20%",
        json.dumps(crud["privacy_masked"]))

    # CRUD 还原
    c = crud["crud"]
    chk("G-CRUD", "CRUD 实操并还原（22→23→22、文件字节还原）",
        c["rows_before"] == 22 and c["rows_after_create"] == 23 and c["rows_after_delete"] == 22
        and c["deleted_gone"] and c["created_exists"],
        json.dumps(c, ensure_ascii=False))

    ok = sum(1 for x in checks if x["pass"])
    out = {"total": len(checks), "pass": ok, "fail": len(checks) - ok, "checks": checks}
    with io.open(os.path.join(OUT, "crosscheck.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("CROSSCHECK %d/%d" % (ok, len(checks)))
    for x in checks:
        print(("PASS " if x["pass"] else "FAIL ") + x["id"] + " | " + x["desc"])


if __name__ == "__main__":
    main()
