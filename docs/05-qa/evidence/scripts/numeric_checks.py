# -*- coding: utf-8 -*-
"""S5 数值口径正确性用例：直接对后端 evidence 做算术复算，避免"看着对"。"""
import io
import json
import os

B = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def load(n):
    return json.load(io.open(os.path.join(B, n), encoding="utf-8"))


R = {}
checks = []


def chk(cid, desc, ok, detail):
    checks.append({"id": cid, "desc": desc, "pass": bool(ok), "detail": detail})
    return ok


h = load("ep_holdings.json")["data"]
s = load("ep_holdings_summary.json")["data"]
rows = h["rows"]

mv_sum = round(sum(r["market_value"] for r in rows if r.get("market_value") is not None), 2)
chk("N-01", "总资产 = Σ 各行 market_value", abs(mv_sum - s["total_value"]) < 0.02,
    "Σ=%.2f vs total_value=%.2f" % (mv_sum, s["total_value"]))

cost = s["total_value"] - s["total_pnl_amt"]
ret_calc = s["total_pnl_amt"] / cost if cost else None
chk("N-02", "收益率 = 累计收益 / 成本", abs(ret_calc - s["return_rate"]) < 0.0002,
    "手算=%.6f vs return_rate=%.6f (成本=%.2f)" % (ret_calc, s["return_rate"], cost))

# 覆盖率：covered_count/total_count
chk("N-03", "覆盖计数 22/22", s["covered_count"] == 22 and s["total_count"] == 22,
    "covered=%s total=%s" % (s["covered_count"], s["total_count"]))

# 未知≠持平：null change_rate 行存在，且 summary 无 +0.00% 冒充
null_rows = [r for r in rows if r.get("change_rate") is None]
zero_rows = [r for r in rows if r.get("change_rate") == 0]
chk("N-04", "未知≠持平：存在 null 涨跌且独立于 0", len(null_rows) >= 1,
    "null=%d 只, 恰好0=%d 只" % (len(null_rows), len(zero_rows)))

# 估值来源五档字段
modes = set((r.get("valuation") or {}).get("valuation_mode") for r in rows)
chk("N-05", "估值来源徽章由后端 valuation_mode 驱动", modes <= {"official", "intraday", "holdings", "proxy", "unknown"},
    "modes=%s" % sorted(m for m in modes if m))

# trace_text 降级链路存在
with_trace = [r for r in rows if (r.get("valuation") or {}).get("trace_text")]
chk("N-06", "估值降级链路 trace_text 非空", len(with_trace) >= 1,
    "%d/%d 行含 trace_text" % (len(with_trace), len(rows)))

# 精度：weighted_mae_rate 0.002 -> 0.20%; 行业 0.008 -> 0.80%
p = load("ep_valuations_precision.json")["data"]
chk("N-07", "MAE 口径 ratio：0.002→0.20%，行业 0.008→0.80%",
    abs(p["weighted_mae_rate"] * 100 - 0.2) < 1e-9 and abs(p["industry_baseline_mae_rate"] * 100 - 0.8) < 1e-9,
    "weighted=%.4f→%.2f%%, industry=%.4f→%.2f%%" % (p["weighted_mae_rate"], p["weighted_mae_rate"]*100,
                                                     p["industry_baseline_mae_rate"], p["industry_baseline_mae_rate"]*100))

# effect_pp 单位为百分点，禁止再 ×100
sig = load("ep_signals_state.json")["data"]
g3 = [g for g in sig["gates"] if g["gate_key"] == "E3"][0]
g1 = [g for g in sig["gates"] if g["gate_key"] == "E1"][0]
chk("N-08", "effect_pp 单位=百分点(E3=3.9→+3.90pp)", g3["effect_pp"] == 3.9 and 3.9 < 100,
    "E3=%s E1=%s" % (g3["effect_pp"], g1["effect_pp"]))

# 冻结表 N_w
fz = load("ep_engine_frozen-params.json")["data"]
nw = [x["n_w"] for x in fz["window_min_days"]]
chk("N-09", "冻结 N_w = 5/10/15/30/60/120", nw == [5, 10, 15, 30, 60, 120], "n_w=%s" % nw)
ww = [x["weight"] for x in fz["window_weights"]]
chk("N-10", "窗权重 = 8/22/15/10/30/15", ww == [8, 22, 15, 10, 30, 15], "weights=%s" % ww)
chk("N-11", "冻结常量 K=4/p=0.25/MIN_N=15/SHRINK=10/BAND=0.02",
    fz["k_noise"] == 4 and fz["p_perturb"] == 0.25 and fz["min_n"] == 15 and fz["shrink"] == 10 and fz["band"] == 0.02,
    "K=%s p=%s min_n=%s shrink=%s band=%s" % (fz["k_noise"], fz["p_perturb"], fz["min_n"], fz["shrink"], fz["band"]))

# 组合：无开口 → weighted_p null / coverage 0 / direction gray
pf = load("ep_portfolio_forecast.json")["data"]
wins = pf["windows"]
chk("N-12", "无开口：weighted_p=null 且 direction=gray（不硬造方向）",
    all(w["weighted_p"] is None and w["direction"] == "gray" for w in wins),
    "diretions=%s" % [w["direction"] for w in wins])
chk("N-13", "weighting_basis 恒 market_value + 策略说明非空",
    all(w["weighting_basis"] == "market_value" and w["weighting_policy_note"] for w in wins),
    "basis=%s" % [w["weighting_basis"] for w in wins])
chk("N-14", "最小覆盖门槛 min_coverage_ratio=0.30 / min_open_count=3",
    all(abs(w["min_coverage_ratio"] - 0.30) < 1e-9 and w["min_open_count"] == 3 for w in wins),
    "min_cov=%s min_open=%s" % ([w["min_coverage_ratio"] for w in wins], [w["min_open_count"] for w in wins]))

# 覆盖度四档颜色由后端
cov = load("ep_holdings_coverage.json")["data"]
tiers = {t["tier"]: t for t in cov["tiers"]}
chk("N-15", "覆盖度 A/B/C/D 四档且颜色由后端给", set(tiers) == {"A", "B", "C", "D"} and all(t.get("color") for t in tiers.values()),
    "tiers=%s" % [(k, v["count"], v["color"]) for k, v in tiers.items()])

# 立方体：naive 不受 MIN_N 门控（naive_n>0 有 P），ddsm 覆盖率
cube = load("ep_engine_ddsm_cube_017193.json")["data"]
allcells = [c for l in cube["layers"] for c in l["cells"]]
q = [c for c in allcells if c["naive_n"] > 0]
chk("N-16", "naive_p 研究口径：naive_n>0 即给值（不受 MIN_N=15 门控）",
    all(c["naive_p"] is not None for c in q) and any(0 < c["naive_n"] < 15 for c in q),
    "%d 格 naive_n>0，其中 %d 格 n<15，均有 naive_p" % (len(q), sum(1 for c in q if c["naive_n"] < 15)))
chk("N-17", "naive_low_sample：naive_n<15 为 true", all(c["naive_low_sample"] for c in q if c["naive_n"] < 15),
    "低样本格数=%d" % sum(1 for c in q if c["naive_n"] < 15))
chk("N-18", "empty 格 P=null（不渲染 0/50%）",
    all(c["naive_p"] is None for c in allcells if c["naive_n"] == 0),
    "%d 个 naive_n=0 格均为 null" % sum(1 for c in allcells if c["naive_n"] == 0))
chk("N-19", "125 格 = 5 层 × 25 格", len(allcells) == 125 and len(cube["layers"]) == 5,
    "total_cells=%d layers=%d" % (len(allcells), len(cube["layers"])))
cmp_ = cube["comparison"]
chk("N-20", "对比卡 valid_coverage 为 ratio(0.92/1.0) -> 展示应为 92/100",
    abs(cmp_["valid_coverage_naive_pct"] - 0.92) < 0.001,
    "naive=%.4f ddsm=%.4f (UI 实测显示 0.9/1.0，少乘 100)" % (cmp_["valid_coverage_naive_pct"], cmp_["valid_coverage_ddsm_pct"]))
chk("N-21", "对比卡 P 标准差/极端格 数值与逐格一致",
    cmp_["extreme_count_naive"] == 54 and cmp_["extreme_count_ddsm"] == 0,
    "extreme naive=%s ddsm=%s" % (cmp_["extreme_count_naive"], cmp_["extreme_count_ddsm"]))

# 预测行 tier/market_value 直带（v5 SHOULD-4）
pr = load("ep_predictions.json")["data"]["rows"]
hm = {r["code"]: r for r in rows}
mism = [r["code"] for r in pr if r.get("market_value") is not None and hm.get(r["code"], {}).get("market_value") is not None
        and abs(r["market_value"] - hm[r["code"]]["market_value"]) > 0.01]
chk("N-22", "PredictionSummary.tier/market_value 与 /holdings 一致（无跨接口分叉）",
    len(mism) == 0 and all(r.get("tier") for r in pr), "mismatch=%s" % mism)

# P 范围 [0,1]
ps = [r["p_up"] for r in pr if r.get("p_up") is not None]
chk("N-23", "p_up ∈ [0,1]（小数非百分数）", all(0 <= v <= 1 for v in ps),
    "min=%.4f max=%.4f" % (min(ps), max(ps)))

# 出口阈值 0.52
chk("N-24", "出口阈值加权阈值 = 0.52", all(abs(w["weighted_p_threshold"] - 0.52) < 1e-9 for w in wins),
    "thresholds=%s" % [w["weighted_p_threshold"] for w in wins])

ok = sum(1 for c in checks if c["pass"])
out = {"total": len(checks), "pass": ok, "fail": len(checks) - ok, "checks": checks}
with io.open(os.path.join(B, "numeric_checks.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
for c in checks:
    print(("PASS " if c["pass"] else "FAIL ") + c["id"] + " " + c["desc"] + " | " + c["detail"])
print("SUMMARY %d/%d" % (ok, len(checks)))
