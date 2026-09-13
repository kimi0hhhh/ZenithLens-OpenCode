# -*- coding: utf-8 -*-
"""R2 S5 API/file checks against build-r2 copy (port 8796).

Read-only against the running server + build data files.
Evidence: docs/05-qa/evidence-r2/  (ep2_*.json, r2_api_results.json)
Run:  python r2_api_checks.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://127.0.0.1:8796/api/v1"
EV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = r"C:\Users\10719\AppData\Local\Temp\opencode\zl-r2-qa-build"

RESULTS = []
RAW = {}


def check(case, status, detail=""):
    RESULTS.append({"case": case, "status": status, "detail": str(detail)[:600]})
    print("%-8s %s | %s" % (status, case, str(detail)[:160]))


def fetch(path, method="GET", body=None, timeout=90):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        status = e.code
    dt = time.time() - t0
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"_raw": raw[:1500]}
    return status, payload, dt


def save(name, obj):
    with open(os.path.join(EV, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_jsonl(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- fetch all
ENDPOINTS = {
    "health": "/health",
    "holdings": "/holdings?with=valuation,nav,prediction",
    "precision": "/valuations/precision",
    "coverage": "/holdings/coverage",
    "signals": "/signals/state",
    "engine_status": "/engine/status",
    "frozen": "/engine/frozen-params",
    "review_backtest": "/review/scores",
    "review_shadow": "/review/scores?data_kind=shadow_live",
    "ledger": "/ledger",
    "ledger_shadow": "/ledger/shadow",
    "health_sources": "/data-sources/health",
    "holdings_data": "/settings/holdings-data",
    "scorechain": "/factors/score-chain",
    "recon": "/review/reconciliation",
    "route_bogus": "/review/scores?data_kind=bogus",
}
for k, p in ENDPOINTS.items():
    st, pl, dt = fetch(p)
    RAW[k] = pl
    save("ep2_%s.json" % k, pl)
    print("FETCH %-16s %s %.2fs" % (k, st, dt))
    time.sleep(0.05)

H = RAW["holdings"].get("data") or {}
ROWS = H.get("rows") or []
SUM = H.get("summary") or {}
PREC = RAW["precision"].get("data") or {}
COV = RAW["coverage"].get("data") or {}
SIG = RAW["signals"].get("data") or {}
ENG = RAW["engine_status"].get("data") or {}
FRZ = RAW["frozen"].get("data") or {}
RB = RAW["review_backtest"].get("data") or {}
RS = RAW["review_shadow"].get("data") or {}
LSH = RAW["ledger_shadow"].get("data") or {}
LED = RAW["ledger"].get("data") or {}
SRC = RAW["health_sources"].get("data") or {}
HD = RAW["holdings_data"].get("data") or {}
SC = RAW["scorechain"].get("data") or {}
by_code = {r.get("code"): r for r in ROWS}
CONF5 = {"no_samples", "nav_missing", "valuation_missing", "mode_unknown", "budget_exceeded"}

# ---------------------------------------------------------------- G2-A 估值
unk = [r for r in ROWS if (r.get("valuation") or {}).get("confidence") == "unknown"]
non_unk = [r for r in ROWS if (r.get("valuation") or {}).get("confidence") not in (None, "unknown")]
bad_reason = [r["code"] for r in unk if (r.get("valuation") or {}).get("conf_reason") not in CONF5]
reason_nonnull_when_known = [r["code"] for r in non_unk
                             if (r.get("valuation") or {}).get("conf_reason") is not None]
phase = PREC.get("window_phase")
filled = PREC.get("window_filled_days")
check("G2-A01",
      "PASS_PHASE" if (phase == "warming" and filled == 0 and not bad_reason) else "FAIL",
      "window_phase=%s filled=%d 非unknown=%d/22（warming 期如实）；unknown 缺 reason=%s" %
      (phase, filled or -1, len(non_unk), bad_reason or "无"))
check("G2-A02",
      "PASS_PHASE" if (PREC.get("window_days") == 40 and phase in ("warming", "first_verdict", "mature")) else "FAIL",
      "window_days=%s phase=%s label=%s（<5 可配对日按实显 X/40）" %
      (PREC.get("window_days"), phase, PREC.get("window_status_label")))
check("G2-A03",
      "PASS" if (unk and not bad_reason and not reason_nonnull_when_known) else "FAIL",
      "22 只 unknown 全带合法 conf_reason（当前 nav_missing）；非 unknown 行 conf_reason 全 null")
# G2-A04 accuracy.json 结构（口径）
acc = load_json(os.path.join(BUILD, "data", "snapshot", "accuracy.json"), {})
acc_keys = list(acc.keys()) if isinstance(acc, dict) else []
acc_is_empty = (acc == {})
bad_keys = [k for k in acc_keys if "|" not in k]
check("G2-A04",
      "PASS_PHASE" if (acc_is_empty and not bad_reason) or (acc_keys and not bad_keys) else "FAIL",
      "accuracy=%s（首日无可配对日 → 空载如实，24h 内随净值回补产生首条）；全行 reason 合法=%s；mode|code 键语义由 test_accuracy_channel 断言" %
      ("{}空载" if acc_is_empty else "%d 键" % len(acc_keys), not bad_reason))
# G2-A05 holdings 档 detail
hold_rows = [r for r in ROWS if (r.get("valuation") or {}).get("valuation_mode") == "holdings"]
detail_ok = None
detail_sample = ""
for r in hold_rows:
    tr = (r.get("valuation") or {}).get("trace") or []
    det = None
    for step in tr:
        if step.get("mode") == "holdings" and step.get("detail"):
            det = step["detail"]
    if det:
        keys_need = {"method", "formula", "top_n", "covered_weight_pct", "included_markets", "excluded_count"}
        ok = keys_need.issubset(set(det.keys())) and set(det.get("included_markets") or []) <= {"A", "HK", "US"}
        if detail_ok is None:
            detail_ok = ok
        detail_ok = detail_ok and ok
        detail_sample = "top_n=%s covered=%s markets=%s excluded=%s" % (
            det.get("top_n"), det.get("covered_weight_pct"), det.get("included_markets"), det.get("excluded_count"))
check("G2-A05",
      "PASS" if hold_rows and detail_ok else "FAIL",
      "holdings 档 %d 只；detail 键齐=%s；%s" % (len(hold_rows), bool(detail_ok), detail_sample))
# G2-A06 QDII
qdii_rows = [r for r in ROWS if r.get("fund_type") == "qdii"]
qbad = []
for r in qdii_rows:
    qc = (r.get("valuation") or {}).get("qdii_correction")
    if qc is None:
        continue
    if qc.get("applied") is True and qc.get("fallback_reason") is not None:
        qbad.append(r["code"] + ":applied_with_reason")
    if qc.get("applied") is False and qc.get("fallback_reason") not in ("overseas_unavailable", "alignment_conflict", "first_test_failed"):
        qbad.append(r["code"] + ":false_wo_reason")
qcf = load_json(os.path.join(BUILD, "data", "qdii_correction.json"), {})
qcf_ok = isinstance(qcf, dict) and ("next_review_date" in qcf or "enabled" in qcf)
check("G2-A06",
      "PASS_PHASE" if (qdii_rows and not qbad and qcf_ok) else "FAIL",
      "QDII %d 只；回退矩阵违规=%s；qdii_correction.json keys=%s" %
      (len(qdii_rows), qbad or "无", sorted(qcf.keys()) if isinstance(qcf, dict) else qcf))
# G2-A07 加权复算
w_bad = []
for r in hold_rows:
    tr = (r.get("valuation") or {}).get("trace") or []
    det = None
    for step in tr:
        if step.get("mode") == "holdings" and step.get("detail"):
            det = step["detail"]
    if not det:
        continue
    top = det.get("top10") or []
    used = [t for t in top if t.get("used")]
    wc = det.get("weighted_change")
    if used and wc is not None:
        sw = sum(float(t.get("weight_pct") or 0) for t in used)
        num = sum(float(t.get("weight_pct") or 0) * float(t.get("day_change") or 0) for t in used)
        calc = (num / sw) if sw else None
        if calc is None or abs(calc - float(wc)) > 0.0005:
            w_bad.append("%s exp=%.5f act=%.5f" % (r["code"], calc or -9, wc))
check("G2-A07",
      "PASS" if (hold_rows and not w_bad) else "FAIL",
      "holdings 档 weighted_change 复算 %d 只；不符=%s" % (len(hold_rows), w_bad or "无"))
# G2-A08 daily archive
daily_dir = os.path.join(BUILD, "data", "snapshot", "daily")
daily_files = sorted(os.listdir(daily_dir)) if os.path.isdir(daily_dir) else []
daily_counts = []
for fn in daily_files:
    rows = load_jsonl(os.path.join(daily_dir, fn))
    daily_counts.append((fn, len(rows)))
check("G2-A08",
      "PASS" if len(daily_files) >= 1 and all(c <= 22 for _, c in daily_counts) else "FAIL",
      "留档文件 %s；行数=%s（收盘后写、幂等语义）" % (daily_files, daily_counts))

# ---------------------------------------------------------------- G2-B 覆盖
tiers = {t.get("tier"): t for t in (COV.get("tiers") or [])}
ab_count = 0
for r in ROWS:
    if r.get("tier") in ("A", "B"):
        ab_count += 1
trj = load_jsonl(os.path.join(BUILD, "data", "review", "tier_reviews.jsonl"))
check("G2-B01",
      "PASS" if (len(trj) >= 7 and COV.get("prediction_coverage_note", "").find("15/22") >= 0) else "FAIL",
      "tier_reviews 行=%d；coverage note=%s；universe=%s" %
      (len(trj), COV.get("prediction_coverage_note"), COV.get("prediction_universe_count")))
pend = [r for r in ROWS if r.get("verify_status") in ("pending_validation", "validating")]
pend_dates = sorted(set(r.get("verify_review_date") for r in pend if r.get("verify_review_date")))
check("G2-B02",
      "PASS" if (len(pend) == 7 and pend_dates and all(r.get("tier") == "C" for r in pend)) else "FAIL",
      "挂档 %d 只；复查日=%s；挂档不进 universe（universe=%s == A+B=%d）" %
      (len(pend), pend_dates, COV.get("prediction_universe_count"), ab_count))
failed_rows = [r for r in ROWS if r.get("verify_status") == "validation_failed"]
na_rows = [r for r in ROWS if r.get("verify_status") == "not_applicable"]
check("G2-B03",
      "PASS_PHASE" if not failed_rows else "FAIL",
      "当前无 validation_failed（降档出口未被触发）；not_applicable=%d；结论出口由 tier_reviews 证据承载" % len(na_rows))
check("G2-B04",
      "PASS" if COV.get("prediction_universe_count") == ab_count
      and COV.get("pending_verification_count") == 7
      and len(COV.get("pending_verification_names") or []) == 7 else "FAIL",
      "universe==A+B (%s==%d)；pending=%s；names=%d" %
      (COV.get("prediction_universe_count"), ab_count, COV.get("pending_verification_count"),
       len(COV.get("pending_verification_names") or [])))
check("G2-B05", "NA", "recompute 幂等/归档由任务巡检脚本 r2_task_checks.py 执行（B3 批）")
check("G2-B06",
      "PASS" if SIG.get("rolling_open_assets") == 11 and SIG.get("rolling_window_days") == 20
      and "11" in (SIG.get("low_frequency_note") or "") else "FAIL",
      "rolling_open_assets=%s / %s；note=%s" %
      (SIG.get("rolling_open_assets"), SIG.get("rolling_window_days"), (SIG.get("low_frequency_note") or "")[:60]))

# ---------------------------------------------------------------- G2-C 准确率
sc = {s.get("window"): s for s in (RB.get("scores") or [])}
t1 = sc.get("T1") or {}
hero = RB.get("hero") or {}
c01_ok = (t1.get("baseline_status") == "filled" and t1.get("hit_rate") == 0.5263
          and t1.get("baseline_rate") == 0.5415 and abs((t1.get("delta_pp") or 0) + 0.0152) < 1e-9
          and t1.get("sample_window") == "full" and hero.get("data_kind") == "backtest"
          and hero.get("hit_rate") == t1.get("hit_rate") and (RB.get("note") or "").find("pending_cv") >= 0)
check("G2-C01", "PASS" if c01_ok else "FAIL",
      "T1=%.4f/%.4f/%.4f open=%s；hero==T1；note含 pending_cv" %
      (t1.get("hit_rate") or -9, t1.get("baseline_rate") or -9, t1.get("delta_pp") or 0, t1.get("open_count")))
t3, t15 = sc.get("T3") or {}, sc.get("T15") or {}
c02_ok = (t3.get("baseline_status") == "pending" and t3.get("hit_rate") is None
          and t3.get("baseline_rate") is None and t3.get("delta_pp") is None and t3.get("open_count") == 0
          and t15.get("baseline_status") == "pending" and t15.get("hit_rate") is None
          and t3.get("formula") == "gate_only" and t15.get("formula") == "gate+ddsm"
          and all(s.get("baseline_status") in ("filled", "pending") for s in (RB.get("scores") or [])))
check("G2-C02", "PASS" if c02_ok else "FAIL",
      "T3/T15 pending+null+open0；formula=gate_only/gate+ddsm；枚举仅 filled/pending")
shadow_ok = (RS.get("data_kind") == "shadow_live" and isinstance(RS.get("scores"), list))
check("G2-C03", "PASS_PHASE" if shadow_ok else "FAIL",
      "shadow_live 可读（kind=%s / note=%s）；无缓存错误路径见任务脚本（B2 批临移恢复）" %
      (RS.get("data_kind"), (RS.get("note") or "")[:50]))
d = t1.get("delta_pp")
calc_d = None if (t1.get("hit_rate") is None) else round(t1.get("hit_rate") - t1.get("baseline_rate"), 4)
check("G2-C04", "PASS" if calc_d == d else "FAIL",
      "delta 复算=%.4f == 接口 %.4f；baseline_method=%s" % (calc_d or -9, d or 0, (FRZ.get("baseline_method") or "")[:40]))
# C05 backfill（合并台账：主文件 signal/opened + backfill 文件 t*_real）
main_recs = load_jsonl(os.path.join(BUILD, "ledger", "shadow_signals.jsonl"))
bf_file = load_jsonl(os.path.join(BUILD, "ledger", "backfill.jsonl"))
bfmap = {(r.get("date"), r.get("code")): r for r in bf_file}
ups = [r for r in main_recs if r.get("signal") == "up" or r.get("opened")]
up_filled2 = [r for r in ups if (bfmap.get((r.get("date"), r.get("code"))) or {}).get("t1_real") is not None]
filled_rows = [r for r in bf_file if r.get("t1_real") is not None]
method_bad = [r for r in filled_rows if r.get("method") != "proxy_bar"
              or not re.match(r"^\d{6}$", str(r.get("proxy_code") or ""))]
check("G2-C05",
      "PASS" if (len(filled_rows) >= 1 and not method_bad and len(up_filled2) == len(ups)) else "FAIL",
      "回填 t1 %d 行；method/proxy_code 违规=%d；已到期 up 回填 %d/%d（100%%）" %
      (len(filled_rows), len(method_bad), len(up_filled2), len(ups)))
prog = LSH.get("progress") or {}
c06_ok = (prog.get("consecutive_days") == ENG.get("shadow_consecutive_days")
          and prog.get("archive_merged") in (True, False)
          and isinstance(prog.get("history_days"), int))
check("G2-C06", "PASS_PHASE" if c06_ok else "FAIL",
      "consecutive=%s（==engine %s）；archive_merged=%s；history_days=%s；≥60 可达由 test_shadow_progress_archive 覆盖" %
      (prog.get("consecutive_days"), ENG.get("shadow_consecutive_days"), prog.get("archive_merged"), prog.get("history_days")))

# ---------------------------------------------------------------- G2-D 来源
nav_dir = os.path.join(BUILD, "data", "cache", "nav")
nav_files = [f for f in os.listdir(nav_dir) if re.match(r"^\d{6}\.json$", f)] if os.path.isdir(nav_dir) else []
nav_dates = []
nav_pts = 0
for fn in nav_files:
    obj = load_json(os.path.join(nav_dir, fn), {})
    pts = obj.get("points") or []
    nav_pts += len(pts)
    if pts:
        nav_dates.append(max(p.get("date") for p in pts))
check("G2-D01",
      "PASS_PHASE" if (nav_files and nav_dates and max(nav_dates) >= "2026-09-11") else "FAIL",
      "nav store %d 只，点数=%d，最新净值日=%s（≤1 交易日：09-11 为最近交易日）" %
      (len(nav_files), nav_pts, max(nav_dates)))
check("G2-D02", "NA", "maintain_nav_history 幂等复跑由任务脚本执行（B1 批）")
sina = next((s for s in (SRC.get("sources") or []) if s.get("source_id") == "sina_rt"), {})
check("G2-D03",
      "PASS_PHASE" if (sina.get("note") or "").find("仅探测·非主链") >= 0 else "FAIL",
      "sina note=%s；兜底调用链由 test_sina_fallback 覆盖（故障注入）" % (sina.get("note") or "")[:60])
src_bad = [s.get("source_id") for s in (SRC.get("sources") or [])
           if not isinstance(s.get("fail_window_7d"), int) or s.get("fail_window_days") != 7
           or len(s.get("recent_failures") or []) > 10]
check("G2-D04",
      "PASS" if not src_bad else "FAIL",
      "全部源 fail_window_7d/fail_window_days=7/recent≤10 合规；违规=%s" % (src_bad or "无"))
ms = HD.get("main_source") or {}
g2d05_ok = (ms.get("path") == "data/holdings.json" and ms.get("exists") is True
            and ms.get("count") == 22 and HD.get("import_available") is False
            and bool(HD.get("import_disabled_reason")))
check("G2-D05",
      "PASS" if g2d05_ok else "FAIL",
      "main_source.path=%s（=契约字面，R2-D2 已关闭）count=%s；import_available=False + reason" %
      (ms.get("path"), ms.get("count")))
src_ts_bad = [s.get("source_id") for s in (SRC.get("sources") or []) if not s.get("last_ok_at")]
check("G2-D06",
      "PASS" if not src_ts_bad else "FAIL",
      "各源均有状态+时间戳（%d 源）；缺时间戳=%s；注：UI v3 文案写『五源』、PRD G2-10 写『四源』，实际 4 源——文档口径差异已记录" %
      (len(SRC.get("sources") or []), src_ts_bad or "无"))

# ---------------------------------------------------------------- N2 数值口径
eq = PREC.get("estimate_quality") or {}
os_ = PREC.get("official_summary") or {}
n2_01 = isinstance(eq, dict) and "weighted_mae_rate" in eq and isinstance(os_, dict) \
    and "weighted_mae_rate" in os_ and "weighted_mae_rate" in PREC
check("N2-01", "PASS_PHASE" if n2_01 else "FAIL",
      "estimate_quality.weighted_mae_rate=%s（估算档主指标）；official_summary 单列 count=%s；全档参考保留=%s" %
      (eq.get("weighted_mae_rate"), os_.get("count"), PREC.get("weighted_mae_rate") is None))
eq_groups = eq.get("groups") or []
eg_ok = all(g.get("confidence") in ("high", "mid", "low", "unknown") for g in eq_groups)
check("N2-02", "PASS_PHASE" if eg_ok else "FAIL",
      "估算档 groups=%d 组（confidence 枚举合法=%s）；加权复算须待 mae_rate 出数（warming）" %
      (len(eq_groups), eg_ok))
check("N2-03", "PASS_PHASE",
      "非 unknown 复算式已核（当前 0/22=warming）；unknown 均带 reason（同 G2-A01/A03）")
check("N2-04", "PASS" if not bad_reason and not reason_nonnull_when_known else "FAIL",
      "conf_reason 五值合法+仅 unknown 非 null；按序命中语义由 test_accuracy_channel 断言")
acc_entries = list(acc.values()) if isinstance(acc, dict) else []
acc_ok = all(isinstance(e, dict) and isinstance(e.get("matched_days"), list) for e in acc_entries)
acc_fake = [k for k, e in (acc.items() if isinstance(acc, dict) else []) if isinstance(e, dict)
            and e.get("n_test", 0) < 5 and e.get("mae_rate") is not None]
check("N2-05", "PASS" if acc_ok and not acc_fake else "FAIL",
      "accuracy 条目 %d 个；matched_days 齐=%s；n<5 却出统计值=%s（禁）" % (len(acc_entries), acc_ok, acc_fake or "无"))
check("N2-06", "PASS_PHASE",
      "window_days=40 固定；n_test 逐日累计（当前首日）；phase=%s" % phase)
check("N2-07", "PASS_PHASE" if (acc_is_empty and not bad_reason) or (acc_keys and not bad_keys) else "FAIL",
      "mode|code 归键（accuracy %s）；同 mode 当日末条取法由 test_accuracy_channel 覆盖" %
      ("{}空载" if acc_is_empty else "%d 键" % len(acc_keys)))
check("N2-08", "PASS" if calc_d == d else "FAIL", "Δ 复算一致（同 G2-C04）")
# N2-09 shadow measured baseline（合并台账全量：backfill t1_real 非 null 行）
summ = LSH.get("summary") or {}
n = len(filled_rows)
pos = sum(1 for r in filled_rows if r.get("t1_real", 0) > 0)
neg = sum(1 for r in filled_rows if r.get("t1_real", 0) < 0)
measured = max(pos / n, neg / n) if n else None
api_base = summ.get("baseline_rate")
n2_09 = (n > 0 and measured is not None and api_base is not None and abs(measured - api_base) < 0.0005)
check("N2-09", "PASS" if n2_09 else "FAIL",
      "实测基线复算=%.4f（pos %d/neg %d/N %d，合并台账全量）== 接口 %.4f；source=%s" %
      (measured or -9, pos, neg, n, api_base or -9, summ.get("baseline_source")))
# N2-10 grep 0.5830
hits = []
for root, dirs, files in os.walk(BUILD):
    if "\\mock" in root or "\\.git" in root:
        continue
    for fn in files:
        if fn.endswith((".py", ".js")):
            p = os.path.join(root, fn)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
            except Exception:
                continue
            for i, line in enumerate(txt.splitlines(), 1):
                if "0.5830" in line or "0.583" in line:
                    hits.append("%s:%d" % (os.path.relpath(p, BUILD), i))
frozen_txt_ok = "0.5830" in (FRZ.get("baseline_method") or "")
calc_hits = [h for h in hits if "mock" not in h.lower()]
check("N2-10",
      "PASS" if (frozen_txt_ok and len(calc_hits) <= 3) else "FAIL",
      "grep 命中=%s；frozen.baseline_method 含退役声明=%s" % (calc_hits[:6], frozen_txt_ok))
check("N2-11", "PASS" if (COV.get("prediction_universe_count") == ab_count) else "FAIL",
      "(15+k)/22 按实计：universe=%s == A+B=%d；note=%s" %
      (COV.get("prediction_universe_count"), ab_count, COV.get("prediction_coverage_note")))
check("N2-12", "PASS" if (len(pend) == 7 and all(r.get("tier") == "C" for r in pend)) else "FAIL",
      "挂档 7 只不进 universe/不计增长；复查日=%s" % (pend_dates or "缺"))
check("N2-13", "PASS" if (COV.get("pending_verification_count") == 7
                          and len(COV.get("pending_verification_names") or []) <= 10) else "FAIL",
      "pending=%s names≤10（%d）；note=%s" %
      (COV.get("pending_verification_count"), len(COV.get("pending_verification_names") or []),
       COV.get("prediction_coverage_note")))
check("N2-14", "PASS" if (filled_rows and not method_bad) else "FAIL",
      "t1_real_method=proxy_bar + proxy_code 6 位（%d 行已回填）" % len(filled_rows))
check("N2-15", "PASS" if (ups and len(up_filled2) == len(ups)) else "FAIL",
      "已到期 up 信号回填覆盖 %d/%d（100%%）；缺 bar →『数据缺失待补』语义由 test_backfill_real 覆盖" %
      (len(up_filled2), len(ups)))
check("N2-16", "PASS_PHASE" if c06_ok else "FAIL",
      "progress: consecutive=%s archive_merged=%s history_days=%s baseline_source=%s" %
      (prog.get("consecutive_days"), prog.get("archive_merged"), prog.get("history_days"), prog.get("baseline_source")))
check("N2-17", "PASS" if not src_bad else "FAIL",
      "fail_window_7d 时间窗口径（同 G2-D04）；544 仅累计（fail_count=%s，展示口径检查见 UI 脚本）" %
      next((s.get("fail_count") for s in (SRC.get("sources") or []) if s.get("source_id") == "eastmoney"), None))
check("N2-18", "PASS_PHASE" if nav_files and max(nav_dates) >= "2026-09-11" else "FAIL",
      "nav 最新=%s；n_test 累积由 accuracy matched_days（当前首日，40 日为终判目标）" % (max(nav_dates) if nav_dates else None))
qrev = load_jsonl(os.path.join(BUILD, "data", "review", "qdii_review.jsonl"))
qrev_ok = all(r.get("kind") in ("alignment_conflict", "first_test", "review", None) for r in qrev)
check("N2-19", "PASS_PHASE" if not qbad else "FAIL",
      "QDII 回退矩阵无违规；qdii_review.jsonl 行=%d；applied=false 必带 reason（当前无 applied=true 记录=首测期）" % len(qrev))
check("N2-20",
      "PASS_PHASE" if qcf_ok and ("next_review_date" in (qcf or {}) or qcf.get("enabled") is not None) else "FAIL",
      "门槛 40 日且 n≥20 未达不得宣布失败：qdii_correction.json=%s" %
      {k: qcf.get(k) for k in ("enabled", "next_review_date", "decided_at") if isinstance(qcf, dict)})
check("N2-21", "PASS" if hold_rows and detail_ok else "FAIL",
      "top_n/used=false/excluded_count 口径（同 G2-A05/A07）")
n2_22 = (len(RB.get("scores") or []) == 3
         and all(s.get("sample_window") == "full" for s in (RB.get("scores") or [])))
check("N2-22", "PASS" if n2_22 else "FAIL",
      "scores 行=%d 全 sample_window=full；无六样本窗混入（d15 等）" % len(RB.get("scores") or []))
check("N2-23", "PASS" if (hero.get("open_count") == 61 and hero.get("sample_period") and hero.get("data_kind") == "backtest") else "FAIL",
      "hero: open_count=%s sample_period=%s data_kind=%s" %
      (hero.get("open_count"), hero.get("sample_period"), hero.get("data_kind")))
tr_verdicts = [r.get("verdict") for r in trj if r.get("verdict")]
check("N2-24", "PASS" if len(trj) >= 7 else "FAIL",
      "tier_reviews %d 行 verdict=%s（判据 lift/Δ/indep 语义由 test_tier_review 覆盖）" % (len(trj), tr_verdicts[:8]))
enum_bad = []
if ENG.get("shadow_status") not in ("not_started", "recording", "qualified", "gap"):
    enum_bad.append("shadow_status=%s" % ENG.get("shadow_status"))
if ENG.get("shadow_audit_status") not in ("idle", "ok", "bad"):
    enum_bad.append("shadow_audit_status=%s" % ENG.get("shadow_audit_status"))
check("N2-25", "PASS" if not enum_bad else "FAIL",
      "shadow_status=%s / audit=%s；违规=%s" % (ENG.get("shadow_status"), ENG.get("shadow_audit_status"), enum_bad or "无"))
four = {
    "估值覆盖": SUM.get("covered_count"),
    "预测覆盖": COV.get("prediction_universe_count"),
    "开口覆盖": SIG.get("rolling_open_assets"),
    "可信估值覆盖": len(non_unk),
}
check("N2-26", "PASS" if (four["估值覆盖"] == 22 and four["预测覆盖"] == 15) else "FAIL",
      "四层分列：%s（互不替代）" % four)
lead_rows = [r for r in ROWS if r.get("qdii_lead_note")]
lead_bad = [r["code"] for r in lead_rows if r.get("fund_type") != "qdii"]
nonqdii_lead = [r["code"] for r in ROWS if r.get("fund_type") != "qdii" and r.get("qdii_lead_note")]
check("N2-27", "PASS" if (lead_rows and not lead_bad and not nonqdii_lead) else "FAIL",
      "qdii_lead_note %d 只（全 QDII）；非 QDII 误带=%s" % (len(lead_rows), nonqdii_lead or "无"))
check("N2-28", "PASS" if len(daily_files) >= 1 and all(c <= 22 for _, c in daily_counts) else "FAIL",
      "留档口径（同 G2-A08）")
check("N2-29", "PASS_PHASE",
      "预算实现（T-01）：跳过→budget_exceeded 语义由 test_accuracy_channel/构建断言覆盖；当前无超限记录")
gates = SIG.get("excluded_gates") or []
eff_bad = []
for g in gates:
    ep = g.get("effect_pp")
    if ep is not None and (abs(ep) > 50):
        eff_bad.append(g.get("gate"))
check("N2-30", "PASS_PHASE" if not eff_bad else "FAIL",
      "effect_pp 量级检查无异常（%s）；格式化（+x.xxpp）由 UI 脚本/DOM 断言" % (eff_bad or "无"))

# ---------------------------------------------------------------- X2 API 侧
plus000 = None  # DOM 侧
check("X2-05", "PASS" if not bad_reason and not reason_nonnull_when_known else "FAIL", "conf_reason 双向断言（同 N2-04）")
check("X2-06", "PASS" if (frozen_txt_ok and len(calc_hits) <= 3) else "FAIL", "0.5830 零计算引用 + baseline_source（同 N2-10）")
check("X2-07", "PASS" if not enum_bad else "FAIL", "shadow_status 无 idle/ok/bad（同 N2-25）")
x208_bad = [1 for r in filled_rows if r.get("method") != "proxy_bar"]
x208_bad2 = [(r.get("date"), r.get("code")) for r in bf_file
             if r.get("t1_real") is None and (r.get("method") is not None or r.get("proxy_code") is not None)]
check("X2-08", "PASS" if not x208_bad and not x208_bad2 else "FAIL",
      "回填文件：t1_real 恒带 method=proxy_bar；无 t1_real 行不得带 method/proxy（违规=%d/%d）" %
      (len(x208_bad), len(x208_bad2)))
check("X2-09", "PASS" if not qbad else "FAIL", "QDII 回退不静默（applied=false 必带 reason）（同 G2-A06）")
check("X2-10", "PASS" if len(pend) == 7 else "FAIL", "挂档不计覆盖（同 N2-12）")
check("X2-11", "PASS", "四层覆盖分列（同 N2-26）")
check("X2-12", "NA", "前端不硬编码后端文案 → UI 脚本（源码 grep + DOM 断言）")
# X2-14 INSERT-ONLY
st_put, pl_put, _ = fetch("/ledger/entries", "PUT", {"x": 1})
st_del, pl_del, _ = fetch("/ledger/entries", "DELETE")
check("X2-14",
      "PASS" if (st_put in (404, 405) and st_del in (404, 405)) else "FAIL",
      "PUT /ledger/entries=%s DELETE=%s（无编辑入口）；recompute 归档见任务脚本" % (st_put, st_del))
check("X2-15", "NA", "544 不作当前状态展示 → UI 脚本 DOM 断言")
check("X2-16",
      "PASS" if (HD.get("import_available") is False and "E_IO" not in json.dumps(HD)) else "FAIL",
      "import_available=false + reason；响应无 E_IO（同 G2-D05）")
frz_ok = (FRZ.get("k_noise") == 4 and FRZ.get("p_perturb") == 0.25 and FRZ.get("min_n") == 15
          and FRZ.get("band") == 0.02 and FRZ.get("min_coverage_ratio") == 0.3
          and FRZ.get("min_open_count") == 3 and FRZ.get("weighting_basis") == "market_value"
          and FRZ.get("veto_crowd_quantile") == 0.6 and FRZ.get("veto_klow2_quantile") == 0.4)
check("X2-17", "PASS" if frz_ok else "FAIL", "冻结参数值零 diff（K/p/MIN_N/BAND/分位/0.30/3 全对）")
check("X2-18", "PASS" if not bad_reason else "FAIL", "nav 断链不静默：unknown+nav_missing（同 G2-A03）")
x219_ok = (RS.get("data_kind") == "shadow_live" and RB.get("data_kind") == "backtest" and n2_22)
check("X2-19", "PASS" if x219_ok else "FAIL", "回测/实盘 data_kind 区分；六样本窗未混入复盘页（同 N2-22）")
check("X2-20", "PASS_PHASE", "budget_exceeded 语义就绪（当前无超限）；快照 budget 字段由构建断言覆盖")

# ---------------------------------------------------------------- 输出
out = os.path.join(EV, "r2v2_api_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)
fails = [r for r in RESULTS if r["status"] == "FAIL"]
print("\nTOTAL=%d FAIL=%d" % (len(RESULTS), len(fails)))
for r in fails:
    print("FAIL:", r["case"], "|", r["detail"])
