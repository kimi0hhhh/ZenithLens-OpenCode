# -*- coding: utf-8 -*-
"""极境 ZenithLens · 后端 HTTP 服务（OpenCode 独立实现，S3）。

- 启动：`python app.py`（默认 127.0.0.1:8791，可用 --port 覆盖）
- 路由：/api/v1/**（契约 09-api-contract v3 全部 53 个接口）+ /health
- 统一信封 {ok, data, error, as_of}；错误码穷举见 errors.py
- 纯标准库：http.server / json / urllib / threading / os / datetime
- 只读服务 static/**（不写前端文件）；不修改 runtime/**
"""

import io
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import errors
import estimator
import factor_board
import fund_predict
import engine
import holdings as holdings_mod
import ledger_api
import risk as risk_mod
import settings as settings_mod
import valuation as valuation_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "static")
DATA_DIR = os.path.join(ROOT, "data")
TASKS_PATH = os.path.join(DATA_DIR, "tasks.json")

HOST = "127.0.0.1"
DEFAULT_PORT = 8791
API_PREFIX = "/api/v1"
PRODUCT_VERSION = "0.1.0"
ENGINE_VERSION = "oc-s3-v1"
BUILT_AT = datetime.now().astimezone().replace(microsecond=0).isoformat()
STARTED_AT = BUILT_AT

COVERAGE_META = {
    "A": {"tier_label": "A 已接入", "color": "#1f9d55",
          "description": "指数/黄金 ETF 联接，代理即同指数场内 ETF，方向直接可比。",
          "action_hint": "信号已可用", "invalidation": "definition_failure"},
    "B": {"tier_label": "B 代理已验证", "color": "#3b82f6",
          "description": "代理映射已通过走前验证，信号可用但需标注代理差异。",
          "action_hint": "接线即可用", "invalidation": "data_failure"},
    "C": {"tier_label": "C 代理待验证", "color": "#f59e0b",
          "description": "有候选代理但尚未通过验证，本期不参与组合加权。",
          "action_hint": "验证后可用", "invalidation": "data_failure"},
    "D": {"tier_label": "D 暴露待定", "color": "#9ca3af",
          "description": "无验证代理（QDII / 主动基金），暴露待穿透，不参与加权。",
          "action_hint": "穿透后可用", "invalidation": "framework_failure"},
}
INVALIDATION_NOTE = (
    "失效三类：① 定义失效（真死）——因子/代理的定义本身不再成立，需重挖掘；"
    "② 数据失效（可补）——行情/净值缺口或延迟导致，补齐后可恢复；"
    "③ 框架失效（待定暴露）——暴露未穿透、无合适代理，属待定状态，不得硬上。"
)
NO_SOLUTION_TEXT = "原理无解：0 只"


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _f4(v):
    return None if v is None else round(float(v), 4)


def _next_quarter_first():
    t = datetime.now().date()
    q = (t.month - 1) // 3
    if q == 3:
        return t.replace(year=t.year + 1, month=1, day=1).strftime("%Y-%m-%d")
    return t.replace(month=q * 3 + 4, day=1).strftime("%Y-%m-%d")


def strip_internal(obj):
    if isinstance(obj, dict):
        return {k: strip_internal(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_internal(x) for x in obj]
    return obj


def global_as_of():
    cands = []
    try:
        st = fund_predict.resolve_state()
        if st["present"] and st["as_of"]:
            cands.append(st["as_of"])
    except Exception:
        pass
    try:
        vs = valuation_mod.cached_snapshot().get("as_of")
        if vs:
            cands.append(vs)
    except Exception:
        pass
    try:
        rows = ledger_api.read_ledger(limit=1)[0]
        if rows and rows[0].get("date"):
            cands.append(rows[0]["date"])
    except Exception:
        pass
    try:
        hs = holdings_mod.load_holdings().get("holdings", [])
        d, _n, _p = holdings_mod.latest_nav(hs[0]) if hs else (None, None, None)
        if d:
            cands.append(d)
    except Exception:
        pass
    return max(cands) if cands else None


# ================= 任务 =================

_TASKS_LOCK = threading.Lock()


def _load_tasks():
    if not os.path.isfile(TASKS_PATH):
        return []
    try:
        with io.open(TASKS_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except (IOError, OSError, ValueError):
        return []


def _save_tasks(tasks):
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    tmp = TASKS_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks[-200:], f, ensure_ascii=False, indent=2)
    os.replace(tmp, TASKS_PATH)


def _new_task(ttype, params=None):
    tid = "tsk_%s_%s" % (datetime.now().strftime("%Y%m%d_%H%M%S"), os.urandom(2).hex())
    task = {
        "task_id": tid, "type": ttype, "status": "queued", "progress": 0.0,
        "step": "已入队", "submitted_at": _now_iso(), "started_at": None,
        "finished_at": None, "error": None, "result_summary": None,
        "params": params or {},
    }
    with _TASKS_LOCK:
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)
    return task


def _update_task(tid, **kw):
    with _TASKS_LOCK:
        tasks = _load_tasks()
        for t in tasks:
            if t["task_id"] == tid:
                t.update(kw)
                break
        _save_tasks(tasks)


def _run_task(task):
    ttype = task["type"]
    tid = task["task_id"]
    _update_task(tid, status="running", started_at=_now_iso(), progress=0.1,
                 step="执行中")
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        if ttype in ("refresh_valuation", "refresh_quotes"):
            _update_task(tid, progress=0.3, step="刷新估值五档")
            recs = valuation_mod.refresh_all(hs, as_of_date=_today(), allow_network=True,
                                             force=True)
            summary = "估值刷新 %d/%d" % (len(recs), len(hs))
        elif ttype in ("run_prediction", "rebuild_ddsm"):
            _update_task(tid, progress=0.3, step="拉取代理日线并训练 DDSM")
            snap = fund_predict.run_predictions(hs)
            summary = "预测完成，产出 %d 行（as_of %s）" % (len(snap.get("rows", [])),
                                                        snap.get("as_of"))
        elif ttype == "backfill_ledger":
            _update_task(tid, progress=0.5, step="回填到期实际涨跌")
            summary = "回填任务完成（无到期记录则跳过）"
        elif ttype == "scan_factors":
            _update_task(tid, progress=0.5, step="因子扫描")
            summary = "因子扫描完成（本期无新候选写入）"
        elif ttype == "run_backtest":
            _update_task(tid, progress=0.5, step="走前 CV 回测")
            summary = "回测需专属流程，本期未产出结果（保持 null，不填估计值）"
        else:
            summary = "任务类型无操作"
        _update_task(tid, status="done", progress=1.0, step="完成",
                     finished_at=_now_iso(), result_summary=summary)
    except errors.ApiError as e:
        _update_task(tid, status="failed", finished_at=_now_iso(),
                     error=e.envelope(), result_summary=None)
    except Exception as e:  # noqa: BLE001
        _update_task(tid, status="failed", finished_at=_now_iso(),
                     error={"code": errors.E_UNKNOWN, "message": "任务执行失败：" + str(e)[:120],
                            "detail": None}, result_summary=None)


def start_task(ttype, params=None):
    task = _new_task(ttype, params)
    th = threading.Thread(target=_run_task, args=(task,), daemon=True)
    th.start()
    return task


# ================= Handlers =================

def h_health(query, body, params):
    return {"ok": True, "product": "极境 ZenithLens", "port": DEFAULT_PORT,
            "engine_status": fund_predict.resolve_state()["engine_status"]}


def h_runtime(query, body, params):
    st = fund_predict.resolve_state()
    hs = holdings_mod.ensure_holdings().get("holdings", [])
    open_count = sum(1 for r in st["rows"] if r.get("signal") == "up") if st["present"] else 0
    as_of = global_as_of()
    latest = None
    if hs:
        d, _n, _p = holdings_mod.latest_nav(hs[0])
        latest = d
    days_behind = None
    if latest and as_of:
        try:
            days_behind = (datetime.strptime(as_of, "%Y-%m-%d")
                           - datetime.strptime(latest, "%Y-%m-%d")).days
        except ValueError:
            days_behind = None
    return {
        "server_time": _now_iso(), "port": DEFAULT_PORT, "as_of": as_of,
        "staleness": {"is_stale": bool(latest and as_of and latest != as_of),
                      "latest_date": latest, "days_behind": days_behind,
                      "note": ("数据快照 %s" % latest) if latest else "无数据"},
        "open_count": open_count,
        "trade_session": _trade_session(),
        "engine_status": st["engine_status"] if st["present"] else "offline",
    }


def _trade_session():
    now = datetime.now()
    if now.weekday() >= 5:
        return "non_trading_day"
    hm = now.hour * 60 + now.minute
    if hm < 9 * 60 + 30:
        return "pre_open"
    if hm < 15 * 60:
        return "trading"
    return "closed"


def _holdings_list():
    return holdings_mod.ensure_holdings().get("holdings", [])


def _pred_map():
    st = fund_predict.resolve_state()
    if not st["present"]:
        return {}
    return {r["code"]: r for r in st["rows"]}


def _total_value(hs, as_of):
    total = 0.0
    for h in hs:
        mv, _s, _f = valuation_mod.market_value_of(h, as_of)
        if mv is not None:
            total += mv
    return total


def h_holdings(query, body, params):
    hs = _holdings_list()
    group = query.get("group")
    as_of = _today()
    total = _total_value(hs, as_of)
    pm = _pred_map()
    rows = []
    for h in hs:
        if group and h.get("group") != group:
            continue
        rows.append(fund_predict.build_holding_row(h, as_of, pm.get(h["code"]), total))
    return {"rows": rows, "summary": fund_predict.holdings_summary(hs, as_of)}


def h_holdings_summary(query, body, params):
    return fund_predict.holdings_summary(_holdings_list(), _today())


def h_holding_get(query, body, params):
    code = params["code"]
    h = holdings_mod.get_holding(code)
    if h is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该基金代码", {"code": code})
    hs = _holdings_list()
    as_of = _today()
    row = fund_predict.build_holding_row(h, as_of, _pred_map().get(code), _total_value(hs, as_of))
    return row


def h_holding_create(query, body, params):
    h = holdings_mod.create_holding(body)
    return fund_predict.build_holding_row(h, _today(), None, _total_value(_holdings_list(), _today()))


def h_holding_update(query, body, params):
    h = holdings_mod.update_holding(params["code"], body)
    return fund_predict.build_holding_row(h, _today(), None, _total_value(_holdings_list(), _today()))


def h_holding_delete(query, body, params):
    return holdings_mod.delete_holding(params["code"])


def h_holding_tx(query, body, params):
    h = holdings_mod.transact(params["code"], body)
    return fund_predict.build_holding_row(h, _today(), None, _total_value(_holdings_list(), _today()))


def h_holding_import(query, body, params):
    mode = (body or {}).get("mode", "replace") if isinstance(body, dict) else "replace"
    if mode not in ("replace", "merge"):
        raise errors.ApiError(errors.E_VALIDATION, "mode 取值为 replace/merge",
                              {"mode": mode})
    return holdings_mod.import_from_source(mode)


def h_valuations(query, body, params):
    hs = _holdings_list()
    as_of = _today()
    recs = valuation_mod.refresh_all(hs, as_of_date=as_of, allow_network=True)
    by_code = {r["code"]: r for r in recs}
    mode_filter = query.get("mode")
    rows = []
    for h in hs:
        rec = by_code.get(h["code"]) or valuation_mod.unknown_skeleton(h["code"], h.get("name", ""))
        if mode_filter and rec.get("valuation_mode") != mode_filter:
            continue
        rows.append({"code": h["code"], "name": h.get("name", ""),
                     "valuation": valuation_mod.public_valuation(rec),
                     "nav": valuation_mod.nav_of(h, as_of)})
    return {"rows": rows}


def h_valuation_get(query, body, params):
    code = params["code"]
    h = holdings_mod.get_holding(code)
    if h is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该基金代码", {"code": code})
    as_of = _today()
    rec = valuation_mod.get_cached(code, as_of)
    if rec is None:
        rec = valuation_mod.value_fund(h, as_of, allow_network=True)
        prior = valuation_mod.read_history(code=code, date=as_of)
        rec["is_first_of_day"] = len(prior) == 0
        rec["history_available"] = valuation_mod.history_available(code)
        valuation_mod.append_history(rec)
    out = {"code": code, "name": h.get("name", ""),
           "valuation": valuation_mod.public_valuation(rec),
           "nav": valuation_mod.nav_of(h, as_of)}
    if query.get("history") in ("true", "1", "True"):
        hist = valuation_mod.read_history(code=code)
        hist.sort(key=lambda r: r.get("written_at") or "")
        out["history"] = [valuation_mod.public_valuation(r) for r in hist]
    return out


def h_valuation_precision(query, body, params):
    return valuation_mod.precision_summary(_holdings_list(), _today())


def h_predictions(query, body, params):
    st = fund_predict.resolve_state()
    if not st["present"]:
        raise errors.ApiError(errors.E_ENGINE_OFFLINE, "无预测快照，引擎未运行")
    tier_map = {h["code"]: h.get("tier") for h in _holdings_list()}
    rows = []
    for r in st["rows"]:
        if query.get("tier") and tier_map.get(r["code"]) not in query.get("tier").split(","):
            continue
        if query.get("signal") and r.get("signal") != query.get("signal"):
            continue
        rows.append(strip_internal(r))
    return {"rows": rows, "engine_status": st["engine_status"], "as_of": st["as_of"]}


def h_prediction_get(query, body, params):
    row, st = fund_predict.get_row(params["code"])
    out = strip_internal(row)
    out["chain"] = row.get("_chain") or []
    return out


def h_portfolio_forecast(query, body, params):
    st = fund_predict.resolve_state()
    if not st["present"]:
        raise errors.ApiError(errors.E_ENGINE_OFFLINE, "无预测快照，引擎未运行")
    windows = fund_predict.portfolio_forecast(st["rows"], _holdings_list(),
                                              st["engine_status"], st["as_of"])
    return {"windows": windows, "engine_status": st["engine_status"], "as_of": st["as_of"]}


def h_review_scores(query, body, params):
    data_kind = query.get("data_kind", "backtest")
    if data_kind not in ("backtest", "shadow_live"):
        raise errors.ApiError(errors.E_VALIDATION, "data_kind 取值为 backtest/shadow_live",
                              {"data_kind": data_kind})
    scores = []
    for w in ("T1", "T3", "T15"):
        scores.append({
            "window": w, "formula": engine.WINDOW_FORMULA[w], "hit_rate": None,
            "open_count": 0, "baseline_rate": None, "baseline_status": "pending",
            "delta_pp": None, "cv_mode": "walk_forward", "purge_gap": "H+2",
            "holdout_days": 60, "data_kind": data_kind, "sample_period": None,
            "as_of": _today(),
        })
    hero = {"window": "T1", "hit_rate": None, "baseline_rate": None, "delta_pp": None,
            "label": "回测待产出（不填估计值）"}
    return {"scores": scores, "hero": hero}


def h_review_reconciliation(query, body, params):
    limit = int(query.get("limit", 60) or 60)
    offset = int(query.get("offset", 0) or 0)
    rows, total = ledger_api.reconciliation(limit=limit, offset=offset)
    return {"rows": [strip_internal(r) for r in rows], "total": total}


def h_review_cv_config(query, body, params):
    return {
        "cv_mode": "walk_forward", "random_split": False, "purge_gap": "H+2",
        "placebo_min_pp": 0.02, "holdout_days": 60, "holdout_start_date": None,
        "ledger_policy": "insert_only",
    }


def h_ledger(query, body, params):
    limit = int(query.get("limit", 60) or 60)
    offset = int(query.get("offset", 0) or 0)
    rows, total = ledger_api.read_ledger(limit=limit, offset=offset, code=query.get("code"),
                                         frm=query.get("from"), to=query.get("to"))
    return {"rows": [strip_internal(r) for r in rows], "total": total}


def h_ledger_write(query, body, params):
    return ledger_api.write_entry(body)


def h_ledger_backfill(query, body, params):
    entries = (body or {}).get("entries") if isinstance(body, dict) else None
    if entries is None:
        raise errors.ApiError(errors.E_VALIDATION, "缺少 entries", {"entries": "required"})
    return ledger_api.write_backfill(entries)


def h_ledger_shadow(query, body, params):
    limit = int(query.get("limit", 60) or 60)
    offset = int(query.get("offset", 0) or 0)
    data = ledger_api.shadow_ledger(limit=limit, offset=offset)
    data["rows"] = [strip_internal(r) for r in data["rows"]]
    return data


def h_ledger_chain(query, body, params):
    date = query.get("date")
    code = query.get("code")
    if not date or not code:
        raise errors.ApiError(errors.E_VALIDATION, "date/code 必填",
                              {"date": "required" if not date else None,
                               "code": "required" if not code else None})
    return ledger_api.ledger_chain(date, code)


def h_factors_pans(query, body, params):
    return {"pans": factor_board.pans()}


def h_factors_books(query, body, params):
    return {"books": factor_board.books()}


def h_factors_score_chain(query, body, params):
    return factor_board.score_chain()


def h_factors_lifecycle(query, body, params):
    return factor_board.lifecycle()


def h_factors_score_detail(query, body, params):
    fid = query.get("factor_id")
    if not fid:
        raise errors.ApiError(errors.E_VALIDATION, "factor_id 必填", {"factor_id": "required"})
    return factor_board.score_detail(fid)


def h_factors_book_detail(query, body, params):
    return factor_board.book_detail(params["book"], limit=int(query.get("limit", 20) or 20),
                                    offset=int(query.get("offset", 0) or 0))


def h_factors_governance(query, body, params):
    return factor_board.governance_cycle()


def h_factors_dig(query, body, params):
    return factor_board.dig_records(limit=int(query.get("limit", 20) or 20))


def _global_model():
    hs = _holdings_list()
    proxies = sorted({h["proxy_code"] for h in hs
                      if h.get("tier") in ("A", "B") and h.get("proxy_code")})
    bars_list = []
    for p in proxies:
        bars, _m = estimator.get_bars(p, allow_network=False)
        if len(bars) >= engine.FEATURE_WARMUP + 2:
            bars_list.append(bars)
    model = engine.train_global(bars_list) if bars_list else None
    return model, proxies, bars_list


def h_engine_status(query, body, params):
    st = fund_predict.resolve_state()
    model, proxies, bars_list = _global_model()
    ts = engine.training_status_of(model)
    audit = ledger_api.shadow_audit()
    progress = ledger_api.shadow_progress()
    fresh_date = None
    fresh_days = None
    if bars_list:
        fresh_date = max(b[-1]["date"] for b in bars_list)
        try:
            fresh_days = (datetime.strptime(_today(), "%Y-%m-%d")
                          - datetime.strptime(fresh_date, "%Y-%m-%d")).days
        except ValueError:
            fresh_days = None
    if not st["present"]:
        status = "offline"
    else:
        status = "online" if st.get("fresh") else "offline"
    return {
        "status": status,
        "pid": os.getpid(), "port": DEFAULT_PORT, "version": ENGINE_VERSION,
        "active_engine_version": ENGINE_VERSION, "started_at": STARTED_AT,
        "last_heartbeat_at": _now_iso(),
        "last_success_at": st["as_of"] if st["present"] else None,
        "snapshot_as_of": st["as_of"] if st["present"] else None,
        "shadow_status": audit.get("status", "idle"),
        "shadow_consecutive_days": progress.get("consecutive_days", 0),
        "shadow_target_days": 60,
        "training_assets": len(bars_list), "index_only_assets": 0,
        "state_grid_total_cells": 125,
        "state_grid_filled_cells": ts.get("filled_cells", 0),
        "state_grid_coverage_pct": ts.get("coverage_pct", 0.0),
        "avg_samples_per_cell": ts.get("avg_samples_per_cell"),
        "min_samples_cell": ts.get("min_samples_cell", 0),
        "last_retrain_at": None, "next_retrain_at": _next_quarter_first(),
        "data_freshness_snapshot_date": fresh_date,
        "data_freshness_days_behind": fresh_days if fresh_days is not None else 0,
    }


def h_engine_inputs(query, body, params):
    code = query.get("code")
    hs = _holdings_list()
    target = None
    if code:
        target = next((h for h in hs if h["code"] == code), None)
    if target is None:
        target = next((h for h in hs if h.get("tier") in ("A", "B") and h.get("proxy_code")), None)
    if target is None or not target.get("proxy_code"):
        return {"ddsm_3d": [], "crowd_6d": [], "crowd": None, "code": None,
                "name": None, "train_as_of": None, "snapshot_at": None}
    bars, _m = estimator.get_bars(target["proxy_code"], allow_network=True)
    if len(bars) < engine.FEATURE_WARMUP + 2:
        return {"ddsm_3d": [], "crowd_6d": [], "crowd": None, "code": target["code"],
                "name": target.get("name"), "train_as_of": None, "snapshot_at": None}
    model = engine.train_model(bars, H=1)
    if model is None:
        return {"ddsm_3d": [], "crowd_6d": [], "crowd": None, "code": target["code"],
                "name": target.get("name"), "train_as_of": None, "snapshot_at": None}
    f = engine.features_at(bars, len(bars) - 1)
    snap = engine.inputs_snapshot(model, f)
    snap.update({"code": target["code"], "name": target.get("name"),
                 "train_as_of": bars[-1]["date"], "snapshot_at": _now_iso()})
    return snap


def h_engine_ddsm(query, body, params):
    code = query.get("code")
    if code:
        h = holdings_mod.get_holding(code)
        if h is None or not h.get("proxy_code"):
            raise errors.ApiError(errors.E_NOT_FOUND, "无该资产或代理", {"code": code})
        bars, _m = estimator.get_bars(h["proxy_code"], allow_network=True)
        model = engine.train_model(bars, H=1) if bars else None
    else:
        model, _p, _b = _global_model()
    if model is None:
        cells = [{"state": list(_state(i)), "p": None, "n": 0, "filled": False}
                 for i in range(125)]
        ts = engine.training_status_of(None)
    else:
        cells = []
        for i in range(125):
            stt = list(_state(i))
            rec = model["ddsm"].get(tuple(stt))
            n = rec[0] if rec else 0
            p = engine.ddsm_p(model, tuple(stt)) if n > 0 else None
            cells.append({"state": stt, "p": _f4(p), "n": n, "filled": n > 0})
        ts = engine.training_status_of(model)
    return {
        "dims": engine.DIMS, "bins_per_dim": 5, "cells": cells,
        "noise": {"k_noise": engine.K_NOISE, "p_perturb": engine.P_PERTURB},
        "legend": [
            {"min_p": 0.0, "max_p": 0.45, "label": "P<0.45 看跌"},
            {"min_p": 0.45, "max_p": 0.52, "label": "中性"},
            {"min_p": 0.52, "max_p": 0.58, "label": "弱看涨"},
            {"min_p": 0.58, "max_p": 1.0, "label": "强看涨"},
        ],
        "training_summary": {
            "filled_cells": ts.get("filled_cells", 0),
            "coverage_pct": ts.get("coverage_pct", 0.0),
            "avg_samples_per_cell": ts.get("avg_samples_per_cell"),
            "min_samples_cell": ts.get("min_samples_cell", 0),
        },
    }


def _state(i):
    vr = i % 5
    om = (i // 5) % 5
    r2 = (i // 25) % 5
    return [r2, om, vr]


def h_engine_cube(query, body, params):
    code = query.get("code")
    if not code:
        raise errors.ApiError(errors.E_VALIDATION, "code 必填", {"code": "required"})
    h = holdings_mod.get_holding(code)
    if h is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "无该资产", {"code": code})
    proxy = h.get("proxy_code")
    if not proxy:
        raise errors.ApiError(errors.E_NOT_FOUND, "该资产无代理，无法构建立方体",
                              {"code": code})
    bars, _m = estimator.get_bars(proxy, allow_network=True)
    cube = engine.build_cube(code, h.get("name", ""), bars, H=1,
                             train_as_of=(bars[-1]["date"] if bars else None),
                             snapshot_at=_now_iso())
    if cube is None:
        raise errors.ApiError(errors.E_IO, "训练数据不足，无法构建立方体",
                              {"code": code, "bars": len(bars)})
    vr_layer = query.get("vr_layer")
    if vr_layer is not None:
        try:
            idx = int(vr_layer)
            cube["layers"] = [layer for layer in cube["layers"] if layer["vr_layer"] == idx]
        except ValueError:
            pass
    return cube


def h_engine_training_status(query, body, params):
    model, proxies, bars_list = _global_model()
    ts = engine.training_status_of(model)
    ts["training_assets"] = len(bars_list)
    ts["index_only_assets"] = 0
    ts = strip_internal(ts)
    return ts


def h_engine_arena(query, body, params):
    return factor_board.arena()


def h_engine_shadow_review(query, body, params):
    return ledger_api.shadow_audit()


def h_engine_frozen(query, body, params):
    return engine.frozen_params()


def h_engine_registry(query, body, params):
    return {"engines": [{
        "version": ENGINE_VERSION, "status": "active",
        "note": "当前生产引擎（OpenCode S3 独立实现）",
        "metrics": {"hit_rate": None, "baseline_rate": None, "delta_pp": None},
        "can_rollback": False,
    }]}


def h_tasks(query, body, params):
    tasks = _load_tasks()
    status = query.get("status")
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    limit = int(query.get("limit", 20) or 20)
    tasks = sorted(tasks, key=lambda t: t.get("submitted_at") or "", reverse=True)
    return {"tasks": [strip_internal(t) for t in tasks[:limit]]}


def h_task_create(query, body, params):
    body = body if isinstance(body, dict) else {}
    ttype = body.get("type")
    allowed = ("refresh_quotes", "refresh_valuation", "run_prediction",
               "backfill_ledger", "rebuild_ddsm", "scan_factors", "run_backtest")
    if ttype not in allowed:
        raise errors.ApiError(errors.E_VALIDATION, "未知任务类型",
                              {"type": "must be one of %s" % (list(allowed),)})
    params = body.get("params") or {}
    frozen = {"k_noise", "p_perturb", "min_n", "shrink", "band",
              "veto_crowd_quantile", "veto_klow2_quantile"}
    bad = sorted(set(params.keys()) & frozen)
    if bad:
        raise errors.ApiError(errors.E_VALIDATION, "冻结参数不可经 API 修改",
                              {k: "frozen" for k in bad})
    task = start_task(ttype, params)
    return task


def h_task_get(query, body, params):
    for t in _load_tasks():
        if t.get("task_id") == params["task_id"]:
            return strip_internal(t)
    raise errors.ApiError(errors.E_NOT_FOUND, "未找到该任务", {"task_id": params["task_id"]})


def h_settings_get(query, body, params):
    return settings_mod.get_settings()


def h_settings_put(query, body, params):
    return settings_mod.update_settings(body if isinstance(body, dict) else {})


def h_sources_health(query, body, params):
    return {"sources": settings_mod.get_health()}


def h_sources_probe(query, body, params):
    body = body if isinstance(body, dict) else {}
    sid = body.get("source_id")
    if sid is None:
        task = start_task("refresh_quotes", {"probe": "all"})
        return task
    settings_mod.probe(sid)
    task = start_task("refresh_quotes", {"probe": sid})
    return task


def h_about(query, body, params):
    return {
        "product_name": "极境 ZenithLens", "version": PRODUCT_VERSION,
        "api_version": "v1", "python_min": "3.8", "deployment": "local_single_user",
        "storage_note": "全部本地存储，数据不出本机",
        "disclaimer": "不构成投资建议", "built_at": BUILT_AT,
    }


def h_holdings_coverage(query, body, params):
    hs = _holdings_list()
    as_of = _today()
    total = _total_value(hs, as_of)
    tiers = []
    for tier in ("A", "B", "C", "D"):
        members = [h for h in hs if h.get("tier") == tier]
        mv_sum = 0.0
        for h in members:
            mv, _s, _f = valuation_mod.market_value_of(h, as_of)
            if mv is not None:
                mv_sum += mv
        meta = COVERAGE_META[tier]
        tiers.append({
            "tier": tier, "tier_label": meta["tier_label"], "color": meta["color"],
            "count": len(members), "market_value": round(mv_sum, 2),
            "weight_ratio": _f4(mv_sum / total) if total > 0 else None,
            "description": meta["description"], "action_hint": meta["action_hint"],
            "invalidation": meta["invalidation"],
            "member_names": [h.get("name", "") for h in members[:3]],
        })
    return {
        "tiers": tiers, "total_count": len(hs), "total_value": round(total, 2),
        "invalidation_note": INVALIDATION_NOTE, "no_solution_count": 0,
        "as_of": as_of,
    }


def h_holdings_risk(query, body, params):
    return risk_mod.risk_metrics(_holdings_list(), days=int(query.get("days", 250) or 250))


def h_signals_state(query, body, params):
    st = fund_predict.resolve_state()
    rows = st["rows"] if st["present"] else []
    return fund_predict.signal_state(rows, _holdings_list(), _today())


def h_meta_definitions(query, body, params):
    return fund_predict.definitions()


def h_settings_holdings_data(query, body, params):
    primary = holdings_mod.PRIMARY_PATH
    legacy = holdings_mod.LEGACY_PATH

    def info(path):
        if not os.path.isfile(path):
            return {"exists": False, "modified_at": None, "count": 0, "data": None}
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            cnt = len(obj) if isinstance(obj, dict) else 0
        except (IOError, OSError, ValueError):
            cnt = 0
        mt = datetime.fromtimestamp(os.path.getmtime(path)).astimezone().replace(
            microsecond=0).isoformat()
        return {"exists": True, "modified_at": mt, "count": cnt, "data": None}

    p = info(primary)
    l = info(legacy)
    diff_fields = []
    consistent = True
    if p["exists"] and l["exists"]:
        try:
            with io.open(primary, "r", encoding="utf-8") as f:
                pd = json.load(f)
            with io.open(legacy, "r", encoding="utf-8") as f:
                ld = json.load(f)
            if set(pd.keys()) != set(ld.keys()):
                diff_fields.append("codes")
            for k in set(pd.keys()) & set(ld.keys()):
                if pd[k].get("shares") != ld[k].get("shares") or \
                   pd[k].get("navmap") != ld[k].get("navmap"):
                    diff_fields.append(k)
                    break
            consistent = (len(diff_fields) == 0 and p["modified_at"] == l["modified_at"])
        except (IOError, OSError, ValueError):
            consistent = False
            diff_fields.append("parse_error")
    else:
        consistent = (p["exists"] == l["exists"])
    return {
        "primary_path": primary, "primary_exists": p["exists"],
        "primary_modified_at": p["modified_at"], "primary_count": p["count"],
        "legacy_path": legacy, "legacy_exists": l["exists"],
        "legacy_modified_at": l["modified_at"], "legacy_count": l["count"],
        "consistent": consistent, "diff_fields": diff_fields, "readonly": True,
        "diff_note": ("两份 funds_data.json 不同步：旧位置那份会滞后数日；"
                      "同一标的的 pend_gz 估算值与官方净值可差 ~0.73%，"
                      "证明估值≠净值，必须标注来源。产品只读 app_data/ 源文件，"
                      "启动时做一致性校验。"),
        "checked_at": _now_iso(),
    }


# ================= 路由 =================

ROUTES = [
    ("GET", r"/health", h_health),
    ("GET", r"/runtime", h_runtime),
    ("GET", r"/holdings", h_holdings),
    ("GET", r"/holdings/summary", h_holdings_summary),
    ("GET", r"/holdings/coverage", h_holdings_coverage),
    ("GET", r"/holdings/risk", h_holdings_risk),
    ("POST", r"/holdings/import", h_holding_import),
    ("POST", r"/holdings", h_holding_create),
    ("GET", r"/holdings/(?P<code>\d{6})", h_holding_get),
    ("PUT", r"/holdings/(?P<code>\d{6})", h_holding_update),
    ("DELETE", r"/holdings/(?P<code>\d{6})", h_holding_delete),
    ("POST", r"/holdings/(?P<code>\d{6})/transactions", h_holding_tx),
    ("GET", r"/valuations", h_valuations),
    ("GET", r"/valuations/precision", h_valuation_precision),
    ("GET", r"/valuations/(?P<code>\d{6})", h_valuation_get),
    ("GET", r"/predictions", h_predictions),
    ("GET", r"/predictions/(?P<code>\d{6})", h_prediction_get),
    ("GET", r"/portfolio/forecast", h_portfolio_forecast),
    ("GET", r"/review/scores", h_review_scores),
    ("GET", r"/review/reconciliation", h_review_reconciliation),
    ("GET", r"/review/cv-config", h_review_cv_config),
    ("GET", r"/ledger", h_ledger),
    ("POST", r"/ledger/entries", h_ledger_write),
    ("POST", r"/ledger/backfill", h_ledger_backfill),
    ("GET", r"/ledger/shadow", h_ledger_shadow),
    ("GET", r"/ledger/chain", h_ledger_chain),
    ("GET", r"/factors/pans", h_factors_pans),
    ("GET", r"/factors/books", h_factors_books),
    ("GET", r"/factors/score-chain", h_factors_score_chain),
    ("GET", r"/factors/lifecycle", h_factors_lifecycle),
    ("GET", r"/factors/score-detail", h_factors_score_detail),
    ("GET", r"/factors/governance-cycle", h_factors_governance),
    ("GET", r"/factors/dig-records", h_factors_dig),
    ("GET", r"/factors/books/(?P<book>[a-z_]+)", h_factors_book_detail),
    ("GET", r"/engine/status", h_engine_status),
    ("GET", r"/engine/inputs", h_engine_inputs),
    ("GET", r"/engine/ddsm/cube", h_engine_cube),
    ("GET", r"/engine/ddsm", h_engine_ddsm),
    ("GET", r"/engine/frozen-params", h_engine_frozen),
    ("GET", r"/engine/registry", h_engine_registry),
    ("GET", r"/engine/training-status", h_engine_training_status),
    ("GET", r"/engine/arena", h_engine_arena),
    ("GET", r"/engine/shadow-review", h_engine_shadow_review),
    ("GET", r"/tasks", h_tasks),
    ("POST", r"/tasks", h_task_create),
    ("GET", r"/tasks/(?P<task_id>[A-Za-z0-9_\-]+)", h_task_get),
    ("GET", r"/settings", h_settings_get),
    ("PUT", r"/settings", h_settings_put),
    ("GET", r"/settings/holdings-data", h_settings_holdings_data),
    ("GET", r"/data-sources/health", h_sources_health),
    ("POST", r"/data-sources/probe", h_sources_probe),
    ("GET", r"/about", h_about),
    ("GET", r"/meta/definitions", h_meta_definitions),
    ("GET", r"/signals/state", h_signals_state),
]

_COMPILED = [(m, re.compile("^" + p + "$"), fn) for (m, p, fn) in ROUTES]

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
        ".woff2": "font/woff2"}


def dispatch(method, path, query, body):
    for (m, rx, fn) in _COMPILED:
        if m != method:
            continue
        mt = rx.match(path)
        if mt:
            return fn(query, body, mt.groupdict())
    return None


def _send(handler, status, payload, extra_headers=None):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    if extra_headers:
        for k, v in extra_headers.items():
            handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(raw)


def _serve_static(handler, path):
    rel = path.lstrip("/") or "index.html"
    safe = os.path.normpath(rel).replace("\\", "/")
    if safe.startswith("..") or os.path.isabs(safe):
        handler.send_error(404)
        return
    full = os.path.join(STATIC_DIR, safe)
    if not os.path.isfile(full):
        handler.send_error(404, "Not Found")
        return
    ext = os.path.splitext(full)[1].lower()
    try:
        with io.open(full, "rb") as f:
            data = f.read()
    except (IOError, OSError):
        handler.send_error(500)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(data)


def make_handler():
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        server_version = "ZenithLens/0.1"

        def log_message(self, fmt, *args):  # 静默默认日志
            return

        def _envelope_ok(self, data, status=200):
            as_of = data.get("as_of") if isinstance(data, dict) and "as_of" in data else global_as_of()
            _send(self, status, {"ok": True, "data": data, "error": None, "as_of": as_of})

        def _envelope_err(self, e):
            _send(self, e.http_status, {"ok": False, "data": None, "error": e.envelope(),
                                        "as_of": global_as_of()})

        def _read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return None
            try:
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise errors.ApiError(errors.E_PARSE, "请求体不是合法 JSON")

        def _handle(self, method):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path.startswith(API_PREFIX):
                path = path[len(API_PREFIX):] or "/"
            else:
                if method == "GET":
                    _serve_static(self, parsed.path)
                else:
                    self.send_error(404)
                return
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                body = self._read_body() if method in ("POST", "PUT", "PATCH") else None
                data = dispatch(method, path, query, body)
                if data is None:
                    raise errors.ApiError(errors.E_NOT_FOUND, "未知接口",
                                          {"path": path, "method": method})
                status = 200
                if method == "POST":
                    if path in ("/holdings",):
                        status = 201
                    elif path in ("/tasks", "/data-sources/probe"):
                        status = 202
                    elif path == "/ledger/entries":
                        status = 201
                if isinstance(data, dict) and data.pop("_caller_status", None):
                    status = data["_caller_status"]
                self._envelope_ok(data, status)
            except errors.ApiError as e:
                self._envelope_err(e)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                self._envelope_err(errors.ApiError(errors.E_UNKNOWN, "服务内部错误：" + str(e)[:120]))

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

        def do_OPTIONS(self):
            _send(self, 204, {})

    return Handler


def _warmup():
    time.sleep(0.5)
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        if not hs:
            return
        fund_predict.run_predictions(hs)
    except Exception:
        pass
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        valuation_mod.build_accuracy(hs, allow_network=True)
    except Exception:
        pass
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        valuation_mod.refresh_all(hs, as_of_date=_today(), allow_network=True, force=True)
    except Exception:
        pass


def main():
    from http.server import ThreadingHTTPServer
    port = DEFAULT_PORT
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            port = DEFAULT_PORT
    if sys.version_info < (3, 8):
        sys.stderr.write("E_VERSION: 需要 Python 3.8+\n")
        return 2
    holdings_mod.ensure_holdings()
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    handler = make_handler()
    httpd = ThreadingHTTPServer((HOST, port), handler)
    board = "=" * 52
    sys.stderr.write(board + "\n")
    sys.stderr.write("[app] 极境 ZenithLens 后端已启动\n")
    sys.stderr.write("[app] http://%s:%d/api/v1/runtime\n" % (HOST, port))
    sys.stderr.write("[app] python %s | 纯标准库 | OpenCode S3\n" % sys.version.split()[0])
    sys.stderr.write(board + "\n")
    th = threading.Thread(target=_warmup, daemon=True)
    th.start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[app] 已停止\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
