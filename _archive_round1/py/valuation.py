# -*- coding: utf-8 -*-
"""估值五档降级链：official → intraday → holdings → proxy → unknown。

- 顺序与 trace 穷举：08-backend-arch.md §3.1；硬规则 §3.2
- 当日 INSERT-ONLY：valuation_history.jsonl 为审计源；valuation.json 仅缓存（A-01）
- 未知口径：unknown 必 change_rate=null；禁止 +0.00% 冒充（契约 §1.2/§5.2）
- 置信度：mae <=0.008 high / <=0.012 mid / >0.012 low；无回测 unknown
  对照行业基准 0.008（契约 §5.2；基准来源见残留风险）
"""

import io
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import errors
import estimator
import holdings as holdings_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SNAP_DIR = os.path.join(DATA_DIR, "snapshot")
HISTORY_PATH = os.path.join(SNAP_DIR, "valuation_history.jsonl")
SNAPSHOT_PATH = os.path.join(SNAP_DIR, "valuation.json")
ACCURACY_PATH = os.path.join(SNAP_DIR, "accuracy.json")

INDUSTRY_BASELINE_MAE = 0.008
ACCURACY_WINDOW_DAYS = 40
TOTAL_BUDGET_SEC = 20.0
REUSE_AGE_SEC = 300

MODE_LABEL = {
    "official": "官方净值",
    "intraday": "盘中估算",
    "holdings": "重仓加权",
    "proxy": "代理近似",
    "unknown": "未知",
}
CONF_LABEL = {"high": "误差达标", "mid": "误差中等", "low": "误差偏大", "unknown": "无可信估算"}
CONF_CLASS = {"high": "ch", "mid": "cm", "low": "cl", "unknown": "cu"}
REASON_TEXT = {
    "not_published": "未出", "missing": "缺失", "timeout": "超时",
    "parse_error": "解析失败", "hit": "命中", "no_mapping": "无映射",
    "no_report": "无持仓报告",
}


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _f4(v):
    if v is None:
        return None
    try:
        return float(Decimal(str(v)).quantize(Decimal("0.0001")))
    except Exception:
        return None


def _f2(v):
    if v is None:
        return None
    try:
        return float(Decimal(str(v)).quantize(Decimal("0.01")))
    except Exception:
        return None


def _ensure_dirs():
    for d in (SNAP_DIR, os.path.join(DATA_DIR, "cache")):
        if not os.path.isdir(d):
            os.makedirs(d)


# ---------------- 历史读写（INSERT-ONLY） ----------------

def read_history(code=None, date=None):
    out = []
    if not os.path.isfile(HISTORY_PATH):
        return out
    try:
        with io.open(HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if code is not None and rec.get("code") != code:
                    continue
                if date is not None and rec.get("date") != date:
                    continue
                out.append(rec)
    except (IOError, OSError):
        return []
    return out


def append_history(rec):
    _ensure_dirs()
    with io.open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def latest_for(code, date):
    recs = read_history(code=code, date=date)
    if not recs:
        return None
    recs.sort(key=lambda r: r.get("written_at") or "")
    return recs[-1]


def history_available(code):
    return len(read_history(code=code)) > 0


# ---------------- 置信度 / 精度 ----------------

def load_accuracy():
    if not os.path.isfile(ACCURACY_PATH):
        return {}
    try:
        with io.open(ACCURACY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_accuracy(obj):
    _ensure_dirs()
    tmp = ACCURACY_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ACCURACY_PATH)


def accuracy_for(mode, code):
    acc = load_accuracy()
    return acc.get("%s|%s" % (mode, code)) or acc.get("%s|*" % mode) or {}


def _confidence_of(mode, code):
    if mode == "unknown":
        return "unknown", None, None, None
    a = accuracy_for(mode, code)
    mae = a.get("mae_rate")
    if mae is None:
        return "unknown", None, a.get("dir_hit_rate"), a.get("n_test")
    if mae <= 0.008:
        conf = "high"
    elif mae <= 0.012:
        conf = "mid"
    else:
        conf = "low"
    return conf, _f4(mae), a.get("dir_hit_rate"), a.get("n_test")


def build_accuracy(hold_list, allow_network=True):
    """按 (valuation_mode × code) 回测方向命中率/MAE。仅 proxy 档本期可算（代理日线可追溯）。

    官方净值历史取自持仓 nav_history；代理日线取自腾讯缓存。样本不足则记 null。
    """
    acc = {}
    for h in hold_list:
        code = h["code"]
        proxy = h.get("proxy_code")
        if not proxy:
            continue
        bars, _meta = estimator.get_bars(proxy, allow_network=allow_network)
        if not bars:
            continue
        by_date = {b["date"]: b for b in bars}
        dates = sorted(by_date.keys())
        nh = h.get("nav_history") or {}
        nav_dates = sorted(nh.keys())
        errs = []
        hits = 0
        n = 0
        for i in range(1, len(nav_dates)):
            d = nav_dates[i]
            dp = nav_dates[i - 1]
            if d not in by_date:
                continue
            idx = dates.index(d)
            if idx <= 0:
                continue
            real = nh[d] / nh[dp] - 1.0
            # 代理上一交易日涨跌近似估算当日
            prev_bar = by_date[dates[idx - 1]]
            cur_bar = by_date[d]
            est = cur_bar["close"] / prev_bar["close"] - 1.0
            errs.append(abs(est - real))
            if (est > 0) == (real > 0):
                hits += 1
            n += 1
        if n >= 3:
            mae = sum(errs) / len(errs)
            acc["proxy|%s" % code] = {
                "mode": "proxy", "code": code, "mae_rate": _f4(mae),
                "dir_hit_rate": _f4(hits / float(n)), "n_test": n,
                "window_days": ACCURACY_WINDOW_DAYS,
            }
    if acc:
        save_accuracy(acc)
    return acc


# ---------------- 五档降级链 ----------------

def _make_trace_step(mode, tried, hit, reason):
    return {"mode": mode, "tried": bool(tried), "hit": bool(hit), "reason": reason}


def _finalize(rec):
    # v3 追加字段
    rec["mode_label"] = MODE_LABEL.get(rec["valuation_mode"], "未知")
    conf = rec.get("confidence", "unknown")
    rec["confidence_label"] = CONF_LABEL.get(conf, "无可信估算")
    rec["confidence_color_class"] = CONF_CLASS.get(conf, "cu")
    rec["industry_baseline_mae_rate"] = INDUSTRY_BASELINE_MAE
    rec["accuracy_window_days"] = ACCURACY_WINDOW_DAYS
    rec["trace_text"] = _trace_text(rec.get("trace") or [])
    return rec


def _trace_text(trace):
    if not trace:
        return None
    parts = []
    for st in trace:
        reason = REASON_TEXT.get(st.get("reason"), st.get("reason") or "")
        parts.append("%s %s" % (st.get("mode"), reason))
    return " → ".join(parts)


def value_fund(h, as_of_date, allow_network=True, run_id=None):
    """执行五档降级链，返回完整 Valuation 记录（不落盘）。"""
    code = h.get("code")
    name = h.get("name", "")
    trace = []
    official_nav = None
    official_date = None
    official_change = None
    prev_nav = None
    nav_date_last, nav_last, nav_prev = holdings_mod.latest_nav(h)

    est = None
    if allow_network:
        est = estimator.eastmoney_fund_estimate(code)
    if est and est.get("official_nav") is not None:
        official_nav = _f4(est["official_nav"])
        official_date = est.get("official_nav_date")
        if official_date and official_date != nav_date_last:
            prev_nav = nav_last
        else:
            prev_nav = nav_prev
    else:
        official_nav = nav_last
        official_date = nav_date_last
        prev_nav = nav_prev
    if official_nav is not None and prev_nav:
        official_change = _f4(official_nav / prev_nav - 1.0)

    result = None

    # 档1 official
    hit1 = bool(official_date) and official_date == as_of_date
    trace.append(_make_trace_step("official", True, hit1,
                                  "hit" if hit1 else "not_published"))
    if hit1:
        result = {
            "valuation_mode": "official",
            "change_rate": official_change,
            "estimated_nav": official_nav,
            "source_label": "官方净值",
            "nav_date": official_date,
        }

    # 档2 intraday
    if result is None:
        hit2 = bool(est and est.get("estimate_change_rate") is not None
                    and est.get("estimate_nav") is not None)
        reason2 = "hit" if hit2 else ("missing" if est is None else "not_published")
        trace.append(_make_trace_step("intraday", True, hit2, reason2))
        if hit2:
            result = {
                "valuation_mode": "intraday",
                "change_rate": _f4(est["estimate_change_rate"]),
                "estimated_nav": _f4(est["estimate_nav"]),
                "source_label": "天天基金盘中估算",
                "nav_date": est.get("official_nav_date") or official_date,
            }

    # 档3 holdings
    if result is None:
        rep = estimator.eastmoney_top_holdings(code) if allow_network else None
        if rep and rep.get("holdings"):
            tot_w = 0.0
            acc = 0.0
            for item in rep["holdings"]:
                w = float(item.get("weight") or 0)
                ch = item.get("day_change")
                if ch is None:
                    continue
                tot_w += w
                acc += w * float(ch)
            hit3 = tot_w > 0
            trace.append(_make_trace_step("holdings", True, hit3,
                                          "hit" if hit3 else "no_report"))
            if hit3:
                ch = acc / tot_w
                result = {
                    "valuation_mode": "holdings",
                    "change_rate": _f4(ch),
                    "estimated_nav": _f4((nav_last or 0) * (1 + ch)) if nav_last else None,
                    "source_label": "前十大重仓加权",
                    "nav_date": nav_date_last,
                }
        else:
            trace.append(_make_trace_step("holdings", True, False, "no_report"))

    # 档4 proxy
    if result is None:
        proxy = h.get("proxy_code")
        hit4 = False
        reason4 = "no_mapping"
        ch = None
        if proxy:
            if allow_network:
                q = estimator.tencent_rt_quote(proxy)
                if q is not None:
                    ch = q["change_rate"]
                    hit4 = True
                    reason4 = "hit"
                else:
                    reason4 = "missing"
            if not hit4:
                bars, _m = estimator.get_bars(proxy, allow_network=allow_network)
                if len(bars) >= 2 and bars[-1]["date"] == as_of_date:
                    ch = bars[-1]["close"] / bars[-2]["close"] - 1.0
                    hit4 = True
                    reason4 = "hit"
                elif not allow_network:
                    reason4 = "missing"
        trace.append(_make_trace_step("proxy", bool(proxy), hit4, reason4))
        if hit4 and ch is not None:
            base_nav = nav_last
            result = {
                "valuation_mode": "proxy",
                "change_rate": _f4(ch),
                "estimated_nav": _f4(base_nav * (1 + ch)) if base_nav else None,
                "source_label": "代理ETF %s 实时" % proxy,
                "nav_date": nav_date_last,
            }

    # 档5 unknown
    if result is None:
        trace.append(_make_trace_step("unknown", True, True, "missing"))
        result = {
            "valuation_mode": "unknown",
            "change_rate": None,
            "estimated_nav": None,
            "source_label": "未知",
            "nav_date": nav_date_last,
        }

    conf, mae, dirhit, ntest = _confidence_of(result["valuation_mode"], code)
    rec = {
        "date": as_of_date,
        "code": code,
        "name": name,
        "valuation_mode": result["valuation_mode"],
        "change_rate": result["change_rate"],
        "estimated_nav": result["estimated_nav"],
        "source_label": result["source_label"],
        "confidence": conf,
        "mae_rate": mae,
        "dir_hit_rate": _f4(dirhit) if dirhit is not None else None,
        "n_test": ntest,
        "nav_date": result["nav_date"],
        "trace": trace,
        "written_at": _now_iso(),
        "run_id": run_id or ("run_" + uuid.uuid4().hex[:8]),
    }
    return _finalize(rec)


def refresh_all(hold_list, as_of_date=None, allow_network=True, run_id=None,
                max_age_sec=REUSE_AGE_SEC, force=False):
    """对全部持仓执行五档链并追加审计记录；返回本日最新记录列表。"""
    _ensure_dirs()
    as_of_date = as_of_date or _today()
    run_id = run_id or ("run_" + uuid.uuid4().hex[:8])
    records = []
    t0 = time.time()
    for h in hold_list:
        if time.time() - t0 > TOTAL_BUDGET_SEC and not force:
            pass
        code = h["code"]
        existing = latest_for(code, as_of_date)
        if (not force) and existing is not None and existing.get("valuation_mode") != "unknown":
            written = existing.get("written_at")
            age = 1e9
            if written:
                try:
                    dt = datetime.fromisoformat(written)
                    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                    age = (now - dt).total_seconds()
                except ValueError:
                    age = 1e9
            if age <= max_age_sec:
                records.append(existing)
                continue
        rec = value_fund(h, as_of_date, allow_network=allow_network, run_id=run_id)
        prior = read_history(code=code, date=as_of_date)
        rec["is_first_of_day"] = len(prior) == 0
        rec["history_available"] = history_available(code)
        append_history(rec)
        records.append(rec)
    _write_snapshot(records, as_of_date)
    return records


def _write_snapshot(records, as_of_date):
    obj = {"as_of": as_of_date, "written_at": _now_iso(), "records": records}
    tmp = SNAPSHOT_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SNAPSHOT_PATH)


_SNAP_CACHE = {"mtime": None, "obj": {}}


def cached_snapshot():
    if not os.path.isfile(SNAPSHOT_PATH):
        return {}
    try:
        mt = os.path.getmtime(SNAPSHOT_PATH)
    except OSError:
        return _SNAP_CACHE["obj"] or {}
    if _SNAP_CACHE["mtime"] == mt:
        return _SNAP_CACHE["obj"]
    try:
        with io.open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (IOError, OSError, ValueError):
        obj = {}
    _SNAP_CACHE["mtime"] = mt
    _SNAP_CACHE["obj"] = obj
    return obj


def get_cached(code, as_of_date):
    snap = cached_snapshot()
    if snap.get("as_of") == as_of_date:
        for rec in snap.get("records", []):
            if rec.get("code") == code:
                return rec
    # 回退到历史最新一条（含旧日）
    recs = read_history(code=code)
    if recs:
        recs.sort(key=lambda r: r.get("written_at") or "")
        return recs[-1]
    return None


def unknown_skeleton(code, name):
    """未估值时的诚实空记录：change_rate=null，trace 为空（不编造链路）。"""
    return _finalize({
        "date": _today(), "code": code, "name": name,
        "valuation_mode": "unknown", "change_rate": None, "estimated_nav": None,
        "source_label": "未知", "confidence": "unknown", "mae_rate": None,
        "dir_hit_rate": None, "n_test": None, "nav_date": None, "trace": [],
        "written_at": None, "run_id": None, "is_first_of_day": False,
        "history_available": history_available(code),
    })


def public_valuation(rec):
    """裁掉内部字段，返回契约 §5.2 的 Valuation。"""
    if rec is None:
        return None
    keys = ["valuation_mode", "mode_label", "change_rate", "estimated_nav", "source_label",
            "confidence", "mae_rate", "nav_date", "trace", "written_at", "run_id",
            "is_first_of_day", "history_available", "dir_hit_rate", "n_test",
            "accuracy_window_days", "industry_baseline_mae_rate", "confidence_label",
            "confidence_color_class", "trace_text", "as_of"]
    out = {k: rec.get(k) for k in keys}
    if out.get("as_of") is None:
        out["as_of"] = rec.get("date")
    return out


def precision_summary(hold_list, as_of_date=None):
    """GET /valuations/precision：置信度分组 + mode 分布（v3）。"""
    as_of_date = as_of_date or _today()
    groups = {}
    modes = {}
    weighted = 0.0
    weight_sum = 0.0
    total_value = 0.0
    detail = []
    for h in hold_list:
        rec = get_cached(h["code"], as_of_date) or unknown_skeleton(h["code"], h.get("name", ""))
        mv = _market_value_of(h, rec)
        if mv is not None:
            total_value += mv
        conf = rec.get("confidence", "unknown")
        g = groups.setdefault(conf, {"confidence": conf, "count": 0, "market_value": 0.0})
        g["count"] += 1
        if mv is not None:
            g["market_value"] += mv
        mode = rec.get("valuation_mode", "unknown")
        m = modes.setdefault(mode, {"mode": mode, "mode_label": MODE_LABEL.get(mode, "未知"),
                                    "count": 0, "market_value": 0.0})
        m["count"] += 1
        if mv is not None:
            m["market_value"] += mv
        mae = rec.get("mae_rate")
        if mae is not None and mv is not None:
            weighted += mae * mv
            weight_sum += mv
        detail.append((h["code"], mv))

    out_groups = []
    for conf in ("high", "mid", "low", "unknown"):
        if conf in groups:
            g = groups[conf]
            g["market_value"] = _f2(g["market_value"])
            g["weight_ratio"] = _f4(g["market_value"] / total_value) if total_value > 0 else None
            out_groups.append(g)
    out_modes = []
    for mode in ("official", "intraday", "holdings", "proxy", "unknown"):
        if mode in modes:
            m = modes[mode]
            m["market_value"] = _f2(m["market_value"])
            m["weight_ratio"] = _f4(m["market_value"] / total_value) if total_value > 0 else None
            out_modes.append(m)
    return {
        "groups": out_groups,
        "weighted_mae_rate": _f4(weighted / weight_sum) if weight_sum > 0 else None,
        "industry_baseline_mae_rate": INDUSTRY_BASELINE_MAE,
        "window_days": ACCURACY_WINDOW_DAYS,
        "mode_distribution": out_modes,
    }


def _market_value_of(h, rec):
    shares = h.get("shares") or 0
    nav = rec.get("estimated_nav")
    if nav is None:
        _d, nav_last, _p = holdings_mod.latest_nav(h)
        nav = nav_last
    if nav is None:
        return None
    return float(shares) * float(nav)


def market_value_of(h, as_of_date=None):
    """(market_value, mv_source, fallback_value)。

    A-02：market_value 优先估值 estimated_nav，其次官方净值；两者皆无 → null，
    并给 fallback_value = cost_amount（禁止成本价进入 market_value）。
    """
    rec = get_cached(h["code"], as_of_date or _today())
    nav = rec.get("estimated_nav") if rec else None
    src = "valuation" if nav is not None else None
    if nav is None:
        _d, nav_last, _p = holdings_mod.latest_nav(h)
        if nav_last is not None:
            nav = nav_last
            src = "nav"
    if nav is None:
        return None, None, _f2(h.get("cost_amount") or 0)
    mv = _f2(float(h.get("shares") or 0) * float(nav))
    return mv, src, 0.0


def nav_of(h, as_of_date=None):
    """契约 §5.3 Nav：官方已公布净值，独立于估值。"""
    as_of_date = as_of_date or _today()
    d, nav_last, prev = holdings_mod.latest_nav(h)
    change = None
    if nav_last is not None and prev:
        change = _f4(nav_last / prev - 1.0)
    return {
        "official_nav": _f4(nav_last),
        "official_nav_date": d,
        "official_change_rate": change,
        "previous_nav": _f4(prev),
        "is_today_official": bool(d == as_of_date),
    }
