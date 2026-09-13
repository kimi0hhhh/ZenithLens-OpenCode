# -*- coding: utf-8 -*-
"""预测编排：训练 → 单资产三窗口 → 快照 → 组合加权 → 六步链 → 空态/口径。

- 快照三态（A-06）：当日快照 / 旧快照(offline) / 无快照(E_ENGINE_OFFLINE)
- 组合三窗口加权（08 §5）：只算开口 + C/D 排除 + 覆盖市值占比 + 门槛 0.30/3
- 契约：09-api-contract §5.4/§5.5/§5.7/§6.4/§6.5/§6.11.3/§6.11.4
"""

import io
import json
import os
import uuid
from datetime import datetime, timedelta

import engine
import errors
import estimator
import holdings as holdings_mod
import ledger_api
import valuation as valuation_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(ROOT, "data", "snapshot")
PRED_PATH = os.path.join(SNAP_DIR, "predictions.json")

MIN_COVERAGE_RATIO = 0.30
MIN_OPEN_COUNT = 3
WEIGHTED_P_THRESHOLD = 0.52
# v4 A-08：组合权重口径冻结为可信市值；显式拒绝置信度加权（未过方法论）
WEIGHTING_BASIS = "market_value"
WEIGHTING_POLICY_NOTE = ("按可信市值加权；灰（未开口）从分子分母同剔；"
                         "未采用置信度加权（未经方法论验证，ADR-0005 拒绝）。")

GATE_EFFECT = {"E1": 0.88, "E3": 3.90, "E4": -2.72, "E2": -3.09}
GATE_T = {"E3": 2.33}
GATE_LABEL = {"E1": "跳空", "E3": "无量急跌", "E2": "放量上涨", "E4": "点火"}


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _f4(v):
    return None if v is None else round(float(v), 4)


# ---------------- 训练与快照 ----------------

def build_prediction_row(h, as_of):
    """返回 (PredictionSummary dict 或 None 表示档位不支持, chain list)。"""
    code = h["code"]
    proxy = h.get("proxy_code")
    if not proxy:
        return None, None
    bars, _meta = estimator.get_bars(proxy, allow_network=True)
    if len(bars) < engine.FEATURE_WARMUP + 2:
        return {
            "code": code, "gate": "none", "gate_label": "未触发", "p_up": None,
            "ddsm_state": None, "veto_crowd": False, "veto_crowd_status": "missing",
            "veto_klow2": False, "veto_klow2_status": "missing",
            "signal": "gray", "signal_label": "灰", "reason": "insufficient_data",
            "windows": _empty_windows("insufficient_data"), "as_of": as_of,
            "_chain": None, "_proxy": proxy,
        }, None
    t = len(bars) - 1
    m1 = engine.train_model(bars, H=1)
    m15 = engine.train_model(bars, H=15)
    if m1 is None:
        return {
            "code": code, "gate": "none", "gate_label": "未触发", "p_up": None,
            "ddsm_state": None, "veto_crowd": False, "veto_crowd_status": "missing",
            "veto_klow2": False, "veto_klow2_status": "missing",
            "signal": "gray", "signal_label": "灰", "reason": "insufficient_data",
            "windows": _empty_windows("insufficient_data"), "as_of": as_of,
            "_chain": None, "_proxy": proxy,
        }, None

    r1 = engine.predict_at(m1, bars, t, 1)
    r15 = engine.predict_at(m15, bars, t, 15) if m15 else None
    gate = r1["gate"]
    veto = r1["veto"] or {}
    windows = _build_windows(r1, r15, bars, as_of)

    row = {
        "code": code,
        "gate": gate,
        "gate_label": engine.GATE_LABEL.get(gate, "未触发"),
        "p_up": _f4(r1["p_up"]),
        "ddsm_state": r1["ddsm_state"],
        "veto_crowd": bool(veto.get("crowd_veto")),
        "veto_crowd_status": veto.get("crowd_status", "missing"),
        "veto_klow2": bool(veto.get("klow2_veto")),
        "veto_klow2_status": veto.get("klow2_status", "missing"),
        "signal": r1["signal"],
        "signal_label": engine.SIGNAL_LABEL.get(r1["signal"], "灰"),
        "reason": r1["reason"],
        "windows": windows,
        "as_of": as_of,
        "_proxy": proxy,
    }
    chain = build_chain(row, r1, bars)
    row["_chain"] = chain
    return row, chain


def _empty_windows(reason):
    out = {}
    for w in ("T1", "T3", "T15"):
        out[w] = {
            "window": w, "formula": engine.WINDOW_FORMULA[w],
            "formula_source": engine.WINDOW_SOURCE[w],
            "validation_status": "brief_mandated" if w == "T1" else "pending_cv",
            "validated": w == "T1",
            "direction": "gray", "provisional_direction": "gray",
            "p": None, "provisional_p": None, "open": False,
            "hit_rate": None, "baseline_rate": None, "delta_pp": None,
        }
    return out


def _build_windows(r1, r15, bars, as_of):
    p1 = r1["p_up"]
    gate = r1["gate"] != "none"
    veto = r1["veto"] or {}
    veto_block = (r1["signal"] == "abstain")
    t1_open = r1["signal"] == "up"
    t3_open = gate
    p15 = r15["p_up"] if r15 else None
    t15_open = bool(gate and p15 is not None and not veto_block)
    prov15 = "up" if (t15_open and p15 is not None and p15 > engine.EXIT_THRESHOLD) else "gray"

    return {
        "T1": {
            "window": "T1", "formula": "gate+ddsm+veto", "formula_source": "brief_5.1",
            "validation_status": "brief_mandated", "validated": True,
            "direction": "up" if t1_open else "gray",
            "provisional_direction": "up" if t1_open else "gray",
            "p": _f4(p1), "provisional_p": None, "open": bool(t1_open),
            "hit_rate": None, "baseline_rate": None, "delta_pp": None,
        },
        "T3": {
            "window": "T3", "formula": "gate_only", "formula_source": "arch_baseline_v1",
            "validation_status": "pending_cv", "validated": False,
            "direction": "gray", "provisional_direction": "up" if gate else "gray",
            "p": None, "provisional_p": None, "open": bool(t3_open),
            "hit_rate": None, "baseline_rate": None, "delta_pp": None,
        },
        "T15": {
            "window": "T15", "formula": "gate+ddsm", "formula_source": "arch_baseline_v1",
            "validation_status": "pending_cv", "validated": False,
            "direction": "gray", "provisional_direction": prov15,
            "p": _f4(p15), "provisional_p": _f4(p15), "open": bool(t15_open),
            "hit_rate": None, "baseline_rate": None, "delta_pp": None,
        },
    }


def build_chain(row, r1, bars):
    """六步推导链（§6.4 ChainStep / §6.11.5）。"""
    veto = r1["veto"] or {}
    m = r1["metrics"]
    gate = r1["gate"]
    gate_status = "on" if gate != "none" else "off"
    chain = [
        {"step": 1, "key": "gate", "title": "①触发门", "status": gate_status,
         "detail": ("触发 %s（%s）" % (gate, engine.GATE_LABEL.get(gate, ""))) if gate != "none"
                   else "未触发 E1/E3（E2/E4 已证伪、禁止 OR 合并）",
         "metrics": {"ret_rate": m.get("ret_rate"), "vr": m.get("vr")}},
        {"step": 2, "key": "ddsm", "title": "②DDSM 档位",
         "status": "on" if r1.get("ddsm_state") is not None else "missing",
         "detail": "真实档位 [r2,om,vr] = %s，P=%.4f" % (r1.get("ddsm_state"), m.get("p_up") or 0.0),
         "metrics": {"r2": m.get("r2"), "om": m.get("om"), "ddsm_state": m.get("ddsm_state"),
                     "p_up": m.get("p_up")}},
        {"step": 3, "key": "veto_crowd", "title": "③拥挤度否决",
         "status": ("missing" if veto.get("crowd_status") == "missing"
                    else ("on" if veto.get("crowd_veto") else "off")),
         "detail": "六维复合 z=%s，分位=%s（阈值 0.60，最拥挤 40%% 否决）"
                   % (m.get("crowd_z"), m.get("crowd_quantile")),
         "metrics": {"crowd_z": m.get("crowd_z"), "crowd_quantile": m.get("crowd_quantile"),
                     "veto_crowd_status": veto.get("crowd_status")}},
        {"step": 4, "key": "veto_klow2", "title": "④KLOW2 否决",
         "status": ("missing" if veto.get("klow2_status") == "missing"
                    else ("on" if veto.get("klow2_veto") else "off")),
         "detail": "下影线比=%s（阈值 0.40，最不利 40%% 否决）" % m.get("klow2"),
         "metrics": {"klow2": m.get("klow2"), "klow2_quantile": m.get("klow2_quantile"),
                     "veto_klow2_status": veto.get("klow2_status")}},
        {"step": 5, "key": "exit", "title": "⑤出口判定",
         "status": "on" if (m.get("p_up") is not None and m.get("p_up") > engine.EXIT_THRESHOLD) else "off",
         "detail": "P=%s vs 阈值 0.5200（单向做多，永不做空）" % m.get("p_up"),
         "metrics": {"p_up": m.get("p_up"), "band": m.get("band"),
                     "exit_threshold": m.get("exit_threshold")}},
        {"step": 6, "key": "output", "title": "⑥输出/入台账",
         "status": ("on" if row.get("signal") == "up"
                    else ("missing" if row.get("signal") == "abstain" else "off")),
         "detail": "signal=%s，reason=%s" % (row.get("signal"), row.get("reason")),
         "metrics": {"signal": row.get("signal"), "reason": row.get("reason")}},
    ]
    return chain


def run_predictions(hold_list, as_of=None, run_id=None):
    as_of = as_of or _today()
    run_id = run_id or ("run_" + uuid.uuid4().hex[:8])
    rows = []
    for h in hold_list:
        if h.get("tier") not in ("A", "B"):
            continue
        try:
            row, _chain = build_prediction_row(h, as_of)
        except Exception:
            row = None
        if row is not None:
            rows.append(row)
    snap = {
        "as_of": as_of, "run_id": run_id, "written_at": _now_iso(),
        "seed": engine.SEED, "engine_status": "online", "rows": rows,
    }
    if not os.path.isdir(SNAP_DIR):
        os.makedirs(SNAP_DIR)
    tmp = PRED_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PRED_PATH)
    return snap


def load_snapshot():
    if not os.path.isfile(PRED_PATH):
        return None
    try:
        with io.open(PRED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def resolve_state():
    """A-06 三态：{present, fresh, as_of, engine_status, rows}。无快照 present=False。"""
    snap = load_snapshot()
    if snap is None:
        return {"present": False, "fresh": False, "as_of": None,
                "engine_status": "offline", "rows": [], "run_id": None}
    fresh = snap.get("as_of") == _today()
    return {
        "present": True, "fresh": fresh, "as_of": snap.get("as_of"),
        "engine_status": "online" if fresh else "offline",
        "rows": snap.get("rows", []), "run_id": snap.get("run_id"),
    }


def require_state():
    st = resolve_state()
    if not st["present"]:
        raise errors.ApiError(errors.E_ENGINE_OFFLINE, "无预测快照，引擎未运行")
    return st


def get_row(code):
    st = require_state()
    for r in st["rows"]:
        if r.get("code") == code:
            return r, st
    raise errors.ApiError(errors.E_NOT_FOUND, "无该基金预测", {"code": code})


# ---------------- 组合三窗口加权 ----------------

def _window_validated(w):
    return w in ("T1",)


def portfolio_forecast(rows, hold_list, engine_status, as_of):
    by_code = {r["code"]: r for r in rows}
    total_value = 0.0
    tier_present = set()
    mv_map = {}
    for h in hold_list:
        mv, _src, _fb = valuation_mod.market_value_of(h, as_of)
        mv_map[h["code"]] = mv
        if h.get("tier") in ("C", "D"):
            tier_present.add(h.get("tier"))
        if mv is not None:
            total_value += mv

    windows = []
    for w in ("T1", "T3", "T15"):
        num = 0.0
        den = 0.0
        open_count = 0
        for h in hold_list:
            if h.get("tier") not in ("A", "B"):
                continue
            row = by_code.get(h["code"])
            if not row:
                continue
            wr = (row.get("windows") or {}).get(w)
            if not wr or not wr.get("open"):
                continue
            p = wr.get("p")
            mv = mv_map.get(h["code"])
            open_count += 1
            if p is not None and mv is not None:
                num += p * mv
                den += mv
        weighted_p = (num / den) if den > 0 else None
        coverage_value = den
        coverage_ratio = (coverage_value / total_value) if total_value > 0 else 0.0
        threshold_met = (coverage_ratio >= MIN_COVERAGE_RATIO and open_count >= MIN_OPEN_COUNT)
        validated = _window_validated(w)
        if open_count == 0:
            reason = "no_open"
        elif not validated:
            reason = "window_unvalidated"
        elif not threshold_met:
            reason = "insufficient_coverage"
        else:
            reason = "ok"
        direction = "up" if (weighted_p is not None and weighted_p > WEIGHTED_P_THRESHOLD
                             and threshold_met and validated) else "gray"
        windows.append({
            "window": w,
            "weighted_p": _f4(weighted_p),
            "weighting_basis": WEIGHTING_BASIS,
            "weighting_policy_note": WEIGHTING_POLICY_NOTE,
            "coverage_ratio": _f4(coverage_ratio),
            "coverage_value": round(coverage_value, 2),
            "open_value": round(coverage_value, 2),
            "total_value": round(total_value, 2),
            "open_count": open_count,
            "min_coverage_ratio": MIN_COVERAGE_RATIO,
            "min_open_count": MIN_OPEN_COUNT,
            "coverage_threshold_met": bool(threshold_met),
            "excluded_ratio": _f4(1.0 - coverage_ratio),
            "threshold_source": "brief_5.1" if w == "T1" else "architecture",
            "direction": direction,
            "direction_reason": reason,
            "weighted_p_threshold": WEIGHTED_P_THRESHOLD,
            "tier_excluded": sorted(tier_present),
            "engine_status": engine_status,
            "as_of": as_of,
        })
    return windows


# ---------------- 空态 / 口径 ----------------

def signal_state(rows, hold_list, as_of):
    monitored = [h for h in hold_list if h.get("tier") in ("A", "B")]
    total = len(hold_list)
    open_rows = [r for r in rows if r.get("signal") == "up"]
    state = "opened" if open_rows else ("no_open" if monitored else "watching")
    last = _last_open_from_ledger()
    gates = [
        {"gate": "E3", "gate_key": "E3", "label": "无量急跌",
         "formula": "ret < -0.02 且 vr < 0.8", "role": "primary",
         "effect_pp": GATE_EFFECT["E3"], "t_value": GATE_T.get("E3"), "note": "主力事件"},
        {"gate": "E1", "gate_key": "E1", "label": "跳空",
         "formula": "low[t] > high[t-1]", "role": "secondary",
         "effect_pp": GATE_EFFECT["E1"], "t_value": None, "note": "辅助事件"},
    ]
    excluded = [
        {"gate": "none", "gate_key": "E2", "label": "放量上涨",
         "formula": "—", "role": "excluded", "effect_pp": GATE_EFFECT["E2"],
         "t_value": None, "note": "已证伪，禁止并入"},
        {"gate": "none", "gate_key": "E4", "label": "点火",
         "formula": "—", "role": "excluded", "effect_pp": GATE_EFFECT["E4"],
         "t_value": None, "note": "已证伪，禁止并入"},
    ]
    days = None
    if last and last.get("date"):
        days = _business_days_between(last["date"], as_of)
    # R2-08 / v9.5：滚动 60 交易日开口资产数（台账合并集；去重资产数，非日开口数）
    # 窗口常量唯一来源 = ledger_api.SHADOW_WINDOW_DAYS（消灭第二真相源）
    rolling = {"rolling_open_assets": 0,
               "rolling_window_days": ledger_api.SHADOW_WINDOW_DAYS}
    try:
        rolling = ledger_api.rolling_open_stats()
    except Exception:  # noqa: BLE001 - 台账不可读时按 0（不编造）
        pass
    return {
        "state": state, "as_of": as_of,
        "monitored_count": len(monitored), "total_count": total,
        "days_since_last_open": days,
        "last_open": last,
        "last_result": _last_result(last),
        "empty_note": "这是常态，不是故障。多数交易日不会开口。",
        "rolling_open_assets": rolling.get("rolling_open_assets", 0),
        "rolling_window_days": rolling.get("rolling_window_days",
                                           ledger_api.SHADOW_WINDOW_DAYS),
        # v9.5 §13.4：60 日窗文案（旧低频基线不再适用，由 PM 重定；
        # 此处不含静态基线数字，窗口/数量直读字段——不编造、不派生）
        "low_frequency_note": ("滚动 60 交易日窗内开口资产数（去重）见 rolling_open_assets；"
                               "多数交易日不开口是常态，空态不等于故障。"),
        "gates": gates, "excluded_gates": excluded, "or_merge_forbidden": True,
    }


def _business_days_between(d1, d2):
    try:
        a = datetime.strptime(d1, "%Y-%m-%d").date()
        b = datetime.strptime(d2, "%Y-%m-%d").date()
    except ValueError:
        return None
    if b <= a:
        return 0
    n = 0
    cur = a
    while cur < b:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def _last_open_from_ledger():
    try:
        import ledger_api
        # limit=None：读取全量台账，避免开口落在默认分页之外时误报「无开口」（真实数据优先）
        rows = sorted(ledger_api.read_ledger(limit=None)[0], key=lambda r: r.get("date") or "")
    except Exception:
        return None
    if not rows:
        return None
    opens = [r for r in rows if r.get("signal") == "up"]
    if not opens:
        return None
    e = opens[-1]
    return {
        "date": e.get("date"), "code": e.get("code"), "name": e.get("name"),
        "gate": e.get("gate"),
        "result": _reconcile(e),
        "t1_real": e.get("t1_real"),
    }


def _reconcile(e):
    t1 = e.get("t1_real")
    if t1 is None:
        return "pending"
    if e.get("signal") == "abstain":
        return "abstain"
    return "hit" if t1 > 0 else "miss"


def _last_result(last):
    if not last:
        return "pending"
    return last.get("result", "pending")


def definitions():
    return {
        "formula": "up = 1 若 close[T+1] > close[T]",
        "signal_time": "T 日 15:30 收盘后",
        "timing_note": ("场外基金申购 15:00 截止，而信号 15:30 才生成：T 日信号最早只能用于 "
                        "T+1 日申购，无法当天买入。"),
        "paths": [
            {"path": "new_position", "label": "A 新建仓位",
             "steps": "T+1 开盘后申购；吃晚一拍的净值，非信号段",
             "executable": False, "caveat": "时序上错过 T 日 15:00 截止"},
            {"path": "hold_existing", "label": "B 已持有仓位",
             "steps": "T+1 日 15:00 前决定继续持有或赎回",
             "executable": True, "caveat": "与信号时点匹配，最现实的用法"},
            {"path": "onsite_etf", "label": "C 场内 ETF",
             "steps": "T+1 开盘买入 / 收盘卖出",
             "executable": False, "caveat": "open→close 口径与场外净值不同"},
        ],
        "conclusion": "对场外基金最现实的用法是 B（持有/赎回决策），本系统不暗示当天可买入。",
    }


# ---------------- HoldingRow 组装 ----------------

def build_holding_row(h, as_of, prediction_row, total_value):
    code = h["code"]
    rec = valuation_mod.get_cached(code, as_of)
    if rec is None:
        rec = valuation_mod.unknown_skeleton(code, h.get("name", ""))
    mv, mv_source, fallback = valuation_mod.market_value_of(h, as_of)
    cost = h.get("cost_amount") or 0.0
    shares = h.get("shares") or 0.0
    avg_cost = (cost / shares) if shares else None
    today_pnl = None
    cr = rec.get("change_rate")
    if cr is not None and mv is not None:
        today_pnl = round(mv - mv / (1 + cr), 2)
    pnl = round(mv - cost, 2) if mv is not None else None
    return_rate = (pnl / cost) if (pnl is not None and cost) else None
    weight = (mv / total_value) if (mv is not None and total_value and total_value > 0) else None
    fund_type = h.get("fund_type") or estimator.classify_fund_type(h.get("name"))
    return {
        "code": code,
        "name": h.get("name", ""),
        "group": h.get("group", "other"),
        "group_label": holdings_mod.HOLDING_GROUPS.get(h.get("group"), "其他"),
        # v10 新增（只加不改）：基金类型，决定估值锚点（主动→重仓加权；指数联接/QDII→proxy）。
        # 来源 estimator.classify_fund_type；契约同步项见 14-api-impl-report §7 V18。
        "fund_type": fund_type,
        "fund_type_label": estimator.FUND_TYPE_LABEL.get(fund_type, "其他"),
        "tier": h.get("tier", "D"),
        "shares": round(float(shares), 4),
        "cost_amount": round(float(cost), 2),
        "avg_cost": round(float(avg_cost), 4) if avg_cost is not None else None,
        "confirm_days": int(h.get("confirm_days", 1)),
        "proxy_code": h.get("proxy_code"),
        "proxy_name": h.get("proxy_name"),
        # v8 新增（只加不改）：D→C 的持仓穿透明细（前十持仓 + 个股→ETF 映射 + 加权篮子）。
        # 来源 proxy_map.penetrate_rows；无穿透时 null。契约同步项见 14-api-impl-report §7 V14。
        "penetration_trace": h.get("penetration_trace"),
        # R2-06/R2-24（contract §3.1）：档位依据 + 验证状态四态（中文文案后端产出）
        "tier_reason": h.get("tier_reason"),
        "verify_status": h.get("verify_status"),
        "verify_status_label": holdings_mod.VERIFY_STATUS_LABEL.get(h.get("verify_status")),
        "verify_batch_id": h.get("verify_batch_id"),
        "verify_note": h.get("verify_note"),
        "verify_review_date": h.get("verify_review_date"),
        # R2-09（contract §3.1）：QDII 领先口径标注；非 QDII 或非跨市场代理 null（不编造）
        "qdii_lead_note": (holdings_mod.QDII_LEAD_NOTE
                           if (fund_type == "qdii" and h.get("proxy_code")) else None),
        "valuation": valuation_mod.public_valuation(rec),
        "nav": valuation_mod.nav_of(h, as_of),
        "prediction": _public_prediction(prediction_row),
        "market_value": mv,
        "mv_source": mv_source,
        "fallback_value": fallback,
        "weight_ratio": _f4(weight),
        "today_pnl_amt": today_pnl,
        "pnl_amt": pnl,
        "return_rate": _f4(return_rate),
        "staleness": _staleness(h, as_of),
    }


def _public_prediction(row):
    if not row:
        return None
    keys = ["code", "gate", "gate_label", "p_up", "ddsm_state", "veto_crowd",
            "veto_crowd_status", "veto_klow2", "veto_klow2_status", "signal",
            "signal_label", "reason", "windows", "as_of"]
    return {k: row.get(k) for k in keys}


def _staleness(h, as_of):
    d, _nav, _p = holdings_mod.latest_nav(h)
    is_stale = bool(d and d != as_of)
    days = None
    if d:
        try:
            days = (datetime.strptime(as_of, "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days
        except ValueError:
            days = None
    return {"is_stale": is_stale, "latest_date": d, "days_behind": days,
            "note": ("数据快照 %s" % d) if d else "无官方净值数据"}


def holdings_summary(hold_list, as_of):
    total_value = 0.0
    fallback = 0.0
    covered_cost = 0.0
    today_pnl = 0.0
    today_any = False
    covered_count = 0
    for h in hold_list:
        mv, _src, fb = valuation_mod.market_value_of(h, as_of)
        rec = valuation_mod.get_cached(h["code"], as_of)
        cr = rec.get("change_rate") if rec else None
        # 可信估值口径：change_rate != null 才算“可信估值覆盖”（PRD F-01 验收②「仅覆盖 N/M 只」）。
        # 与 today_pnl_amt 聚合口径一致（仅 change_rate 非 null 行参与）。
        # total_value / covered_cost_amount 仍按 market_value != null 口径（09 §6.2.1 / A-02）。
        if cr is not None:
            covered_count += 1
            if mv is not None:
                today_pnl += mv - mv / (1 + cr)
                today_any = True
        if mv is not None:
            total_value += mv
            covered_cost += float(h.get("cost_amount") or 0.0)
        else:
            fallback += fb or 0.0
    total_pnl = total_value - covered_cost
    total_count = len(hold_list)
    return {
        "total_value": round(total_value, 2),
        "fallback_value": round(fallback, 2),
        "total_value_with_fallback": round(total_value + fallback, 2),
        "covered_cost_amount": round(covered_cost, 2),
        "today_pnl_amt": round(today_pnl, 2) if today_any else None,
        "total_pnl_amt": round(total_pnl, 2),
        "return_rate": _f4(total_pnl / covered_cost) if covered_cost else None,
        "covered_count": covered_count,
        "total_count": total_count,
        "coverage_note": _coverage_note(covered_count, total_count, total_value, fallback),
        "as_of": as_of,
    }


def _coverage_note(n, m, total_value, fallback):
    if n == m:
        first = "可信估值覆盖 %d/%d 只（全部覆盖）" % (n, m)
    else:
        first = "可信估值覆盖 %d/%d 只" % (n, m)
    if fallback > 0:
        second = "另有 %.2f 元未知行按成本计，合计 %.2f" % (fallback, total_value + fallback)
    else:
        second = "无未知行按成本计"
    return first + "；" + second
