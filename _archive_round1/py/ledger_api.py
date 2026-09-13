# -*- coding: utf-8 -*-
"""审计台账：INSERT-ONLY（signals.jsonl + 独立 backfill.jsonl）。

- 契约 §5.9 / §5.10 / §5.28 / §5.29 / §5.34、08 §6
- 唯一性 (date, code)；写后不改；回填只写 t*_real；读取时左连接合并
- created_at 与 written_at 同刻恒等（v3 追加，二者都保留）
"""

import io
import json
import os
import threading
from datetime import datetime, timedelta
from decimal import Decimal

import errors
import holdings as holdings_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_DIR = os.path.join(ROOT, "ledger")
SIGNALS_PATH = os.path.join(LEDGER_DIR, "shadow_signals.jsonl")
BACKFILL_PATH = os.path.join(LEDGER_DIR, "backfill.jsonl")

_LOCK = threading.Lock()
BASELINE_RATE = 0.5830
TARGET_DAYS = 60
DEVIATION_THRESHOLD = 0.02

FIELD_LIST = ["date", "code", "gate", "p_up", "ddsm_state", "veto_crowd",
              "veto_klow2", "signal", "t1_real", "t3_real", "t15_real", "created_at"]

INSERT_ONLY_NOTE = ("收盘时点固定写盘：同一 (date, code) 仅允许一条，写入即冻结；"
                    "事后不可编辑/删除；到期实际涨跌由独立 backfill.jsonl 回填，"
                    "只写 t1_real/t3_real/t15_real，不改原行。")


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _ensure_dir():
    if not os.path.isdir(LEDGER_DIR):
        os.makedirs(LEDGER_DIR)


def _read_jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except (IOError, OSError):
        return []
    return out


def _append_jsonl(path, obj):
    _ensure_dir()
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_signals_raw():
    return _read_jsonl(SIGNALS_PATH)


def read_backfill_raw():
    return _read_jsonl(BACKFILL_PATH)


def write_entry(payload):
    if not isinstance(payload, dict):
        raise errors.ApiError(errors.E_VALIDATION, "请求体必须是对象", {"body": "not object"})
    detail = {}
    for k in ("date", "code", "gate", "p_up", "ddsm_state", "veto_crowd",
              "veto_klow2", "signal", "market_value", "cost_est"):
        if k not in payload:
            detail[k] = "required"
    if detail:
        raise errors.ApiError(errors.E_VALIDATION, "缺少字段", detail)
    d, c = str(payload["date"]), str(payload["code"])
    with _LOCK:
        for e in read_signals_raw():
            if e.get("date") == d and e.get("code") == c:
                raise errors.ApiError(errors.E_CONFLICT, "同日同代码台账已存在",
                                      {"date": d, "code": c})
        now = _now_iso()
        rec = dict(payload)
        rec["date"] = d
        rec["code"] = c
        rec["written_at"] = now
        rec["created_at"] = now
        _append_jsonl(SIGNALS_PATH, rec)
    return {"written": True, "date": d, "code": c}


def write_backfill(entries):
    if not isinstance(entries, list):
        raise errors.ApiError(errors.E_VALIDATION, "entries 必须是数组", {"entries": "not list"})
    signals = {(e.get("date"), e.get("code")) for e in read_signals_raw()}
    backfilled = 0
    skipped = 0
    with _LOCK:
        for it in entries:
            if not isinstance(it, dict):
                skipped += 1
                continue
            key = (str(it.get("date")), str(it.get("code")))
            if key not in signals:
                raise errors.ApiError(errors.E_VALIDATION, "回填无对应 signal",
                                      {"date": key[0], "code": key[1]})
            rec = {"date": key[0], "code": key[1], "backfilled_at": _now_iso()}
            for f in ("t1_real", "t3_real", "t15_real"):
                if it.get(f) is not None:
                    rec[f] = float(it[f])
            _append_jsonl(BACKFILL_PATH, rec)
            backfilled += 1
    return {"backfilled_count": backfilled, "skipped": skipped}


def _merged_raw():
    """signals LEFT JOIN backfill（同 (date,code) 取最后一条回填值）。"""
    back = {}
    for b in read_backfill_raw():
        back[(b.get("date"), b.get("code"))] = b
    out = []
    for s in read_signals_raw():
        r = dict(s)
        b = back.get((s.get("date"), s.get("code")))
        if b:
            for f in ("t1_real", "t3_real", "t15_real"):
                if f in b:
                    r[f] = b[f]
        out.append(r)
    return out


def _name_map():
    m = {}
    try:
        for h in holdings_mod.load_holdings().get("holdings", []):
            m[h["code"]] = h.get("name", "")
    except Exception:
        pass
    return m


def _decorate(r, names, seq):
    r = dict(r)
    r.setdefault("t1_real", None)
    r.setdefault("t3_real", None)
    r.setdefault("t15_real", None)
    r["name"] = names.get(r.get("code"), r.get("name", ""))
    for k in ("ddsm_state", "veto_crowd", "veto_klow2", "signal", "gate", "p_up",
              "market_value", "cost_est"):
        r.setdefault(k, None)
    r["is_backfilled"] = all(r.get(f) is not None for f in ("t1_real", "t3_real", "t15_real"))
    r["created_at"] = r.get("created_at") or r.get("written_at")
    r["written_at"] = r.get("written_at") or r.get("created_at")
    r["record_seq"] = seq
    r["source_file"] = "shadow_signals.jsonl"
    r["chain_available"] = bool(r.get("_chain"))
    return r


def read_ledger(limit=60, offset=0, code=None, frm=None, to=None):
    rows = _merged_raw()
    names = _name_map()
    # 按 (created_at, code) 生成序号（升序）
    rows.sort(key=lambda r: (r.get("created_at") or r.get("written_at") or "", r.get("code") or ""))
    for i, r in enumerate(rows):
        r["_seq"] = i + 1
    if code:
        rows = [r for r in rows if r.get("code") == code]
    if frm:
        rows = [r for r in rows if (r.get("date") or "") >= frm]
    if to:
        rows = [r for r in rows if (r.get("date") or "") <= to]
    total = len(rows)
    rows.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    page = rows[offset:offset + limit] if limit is not None else rows[offset:]
    return [_decorate(r, names, r.get("_seq")) for r in page], total


def get_entry(date, code):
    for r in _merged_raw():
        if r.get("date") == date and r.get("code") == code:
            return r
    return None


def reconcile_result(e):
    t1 = e.get("t1_real")
    if t1 is None:
        return "pending"
    if e.get("signal") == "abstain":
        return "abstain"
    return "hit" if t1 > 0 else "miss"


def reconciliation(limit=60, offset=0):
    rows, total = read_ledger(limit=limit, offset=offset)
    out = []
    for r in rows:
        r = dict(r)
        r["result"] = reconcile_result(r)
        out.append(r)
    return out, total


# ---------------- 影子盘 ----------------

def _business_days(a, b):
    """[a, b) 内的周一~周五数（交易日近似，无官方历）。"""
    try:
        d1 = datetime.strptime(a, "%Y-%m-%d").date()
        d2 = datetime.strptime(b, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0
    n = 0
    cur = d1
    while cur < d2:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def _hit_rate(rows):
    considered = [r for r in rows if r.get("signal") == "up" and r.get("t1_real") is not None]
    if not considered:
        return None
    hits = sum(1 for r in considered if r["t1_real"] > 0)
    return hits / float(len(considered))


def shadow_progress():
    rows = _merged_raw()
    if not rows:
        return {
            "status": "not_started", "consecutive_days": 0, "target_days": TARGET_DAYS,
            "progress_ratio": 0.0, "start_date": None, "target_date": None,
            "gap_days": 0, "hit_rate": None, "baseline_rate": BASELINE_RATE,
            "deviation_pp": None,
            "note": "连续 60 个交易日无漏单且偏差 <2pp 才具上线资格；台账尚未启动。",
        }
    dates = sorted(set(r.get("date") for r in rows if r.get("date")))
    start = dates[0]
    last = dates[-1]
    present = set(dates)
    target_ts = datetime.strptime(start, "%Y-%m-%d").date()
    added = 0
    while added < TARGET_DAYS:
        target_ts += timedelta(days=1)
        if target_ts.weekday() < 5:
            added += 1
    target_date = target_ts.strftime("%Y-%m-%d")
    # 连续无漏单：从 last 向前回溯连续交易日
    consec = 0
    cur = datetime.strptime(last, "%Y-%m-%d").date()
    while cur.strftime("%Y-%m-%d") in present:
        consec += 1
        cur -= timedelta(days=1)
        while cur.weekday() >= 5:
            cur -= timedelta(days=1)
    gap = max(0, _business_days(start, last) + 1 - len(dates))
    hr = _hit_rate(rows)
    dev = (hr - BASELINE_RATE) if hr is not None else None
    if gap > 0:
        status = "gap"
    elif consec >= TARGET_DAYS:
        status = "qualified"
    else:
        status = "recording"
    return {
        "status": status, "consecutive_days": consec, "target_days": TARGET_DAYS,
        "progress_ratio": round(min(1.0, consec / float(TARGET_DAYS)), 2),
        "start_date": start, "target_date": target_date, "gap_days": gap,
        "hit_rate": round(hr, 4) if hr is not None else None,
        "baseline_rate": BASELINE_RATE,
        "deviation_pp": round(dev, 4) if dev is not None else None,
        "note": "连续 60 个交易日无漏单且偏差 <2pp 才具上线资格。",
    }


def shadow_ledger(limit=60, offset=0):
    rows, total = read_ledger(limit=limit, offset=offset)
    # 按 created_at 倒序
    rows.sort(key=lambda r: (r.get("created_at") or "", r.get("code") or ""), reverse=True)
    allrows = _merged_raw()
    opens = sum(1 for r in allrows if r.get("signal") == "up")
    abstains = sum(1 for r in allrows if r.get("signal") == "abstain")
    backfilled = sum(1 for r in allrows
                     if all(r.get(f) is not None for f in ("t1_real", "t3_real", "t15_real")))
    hr = _hit_rate(allrows)
    summary = {
        "total_records": len(allrows),
        "open_signals": opens,
        "veto_abstains": abstains,
        "backfilled_count": backfilled,
        "hit_rate": round(hr, 4) if hr is not None else None,
        "baseline_rate": BASELINE_RATE,
    }
    return {
        "rows": rows, "total": total, "summary": summary,
        "progress": shadow_progress(), "field_list": FIELD_LIST,
        "insert_only_note": INSERT_ONLY_NOTE, "as_of": _today(),
    }


def shadow_audit():
    rows = _merged_raw()
    if not rows:
        return {
            "status": "idle", "rolling_days": 60, "hit_rate": None,
            "baseline_rate": BASELINE_RATE, "deviation_pp": None,
            "threshold_pp": DEVIATION_THRESHOLD,
            "message": "影子盘尚未启动，先积累连续记录再评估上线资格。",
            "checked_at": _now_iso(),
            "note": "回测再漂亮也只是回测，最后保险是影子盘。",
        }
    dates = sorted(set(r.get("date") for r in rows if r.get("date")), reverse=True)
    window = set(dates[:60])
    subset = [r for r in rows if r.get("date") in window]
    hr = _hit_rate(subset)
    dev = (hr - BASELINE_RATE) if hr is not None else None
    if dev is None:
        status = "idle"
    elif abs(dev) >= DEVIATION_THRESHOLD:
        status = "bad"
    else:
        status = "ok"
    return {
        "status": status, "rolling_days": 60,
        "hit_rate": round(hr, 4) if hr is not None else None,
        "baseline_rate": BASELINE_RATE,
        "deviation_pp": round(dev, 4) if dev is not None else None,
        "threshold_pp": DEVIATION_THRESHOLD,
        "message": ("影子盘达标（偏差 <2pp）" if status == "ok"
                    else ("影子盘降级：偏差 ≥2pp" if status == "bad" else "影子盘样本不足")),
        "checked_at": _now_iso(),
        "note": "回测再漂亮也只是回测，最后保险是影子盘。",
    }


def ledger_chain(date, code):
    e = get_entry(date, code)
    if e is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该条台账",
                              {"date": date, "code": code})
    names = _name_map()
    chain = e.get("_chain")
    return {
        "date": e.get("date"), "code": e.get("code"),
        "name": names.get(e.get("code"), e.get("name", "")),
        "gate": e.get("gate"), "signal": e.get("signal"), "p_up": e.get("p_up"),
        "chain": chain if chain is not None else [],
        "metrics": e.get("_metrics") or {},
        "source_ledger": "shadow_signals.jsonl",
        "created_at": e.get("created_at") or e.get("written_at"),
    }


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# 兼容：供 factor_board 使用的 shadow_signals 账本原文
def shadow_signals_records():
    return read_signals_raw()
