# -*- coding: utf-8 -*-
"""极境 ZenithLens · 后端 HTTP 服务（OpenCode 独立实现，S3）。

- 启动：`python app.py`（默认 127.0.0.1:8791，可用 --port 覆盖）
- 路由：/api/v1/**（契约 09-api-contract v4 全部 53 个接口）+ /health
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
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import errors
import estimator
import factor_board
import factor_engine
import fund_predict
import engine
import holdings as holdings_mod
import ledger_api
import proxy_map
import review as review_mod
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
# 净值缓存保鲜窗：/runtime staleness 读取实时净值缓存时的最大容忍年龄（秒）
RV_NAV_CACHE_SEC = 300
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
# NIT B-5a：原死常量 NO_SOLUTION_TEXT 已清理；`no_solution_count` 改为**实测**
# （无代理且无穿透映射的资产数；契约 §5.19 文案由前端按 N 直出）。

# 冻结参数黑名单（契约 §6.9：POST /tasks.params 出现即 E_VALIDATION；v4 扩至含组合口径；v9.1/B8 增 baseline_method）
FROZEN_PARAM_KEYS = frozenset({
    "k_noise", "p_perturb", "min_n", "shrink", "band",
    "veto_crowd_quantile", "veto_klow2_quantile",
    "min_coverage_ratio", "min_open_count", "weighting_basis",
    "baseline_method",
})
TASK_TYPES = ("refresh_quotes", "refresh_valuation", "run_prediction",
              "backfill_ledger", "rebuild_ddsm", "scan_factors", "run_backtest",
              # R2-16 / R2-06：新增 2 类（contract §4.8）
              "maintain_nav_history", "verify_tiers")

LEDGER_REFRESH_MODES = ("incremental", "recompute")


def validate_task_payload(ttype, params):
    """校验任务类型与参数；冻结口径不可经 API 修改（契约 §6.9 / A-08 / B8）。"""
    if ttype not in TASK_TYPES:
        raise errors.ApiError(errors.E_VALIDATION, "未知任务类型",
                              {"type": "must be one of %s" % (list(TASK_TYPES),)})
    params = params if isinstance(params, dict) else {}
    bad = sorted(set(params.keys()) & FROZEN_PARAM_KEYS)
    if bad:
        raise errors.ApiError(errors.E_VALIDATION, "冻结参数不可经 API 修改",
                              {k: "frozen" for k in bad})
    if ttype == "backfill_ledger" and "mode" in params:
        if params["mode"] not in LEDGER_REFRESH_MODES:
            raise errors.ApiError(errors.E_VALIDATION, "mode 取值为 incremental/recompute",
                                  {"mode": "must be one of %s" % (list(LEDGER_REFRESH_MODES),)})
    if ttype == "verify_tiers" and "targets" in params:
        targets = params["targets"]
        if not isinstance(targets, list) or not targets or \
                not all(isinstance(t, str) and re.match(r"^\d{6}$", t) for t in targets):
            raise errors.ApiError(errors.E_VALIDATION, "targets 必须为 6 位基金代码数组",
                                  {"targets": "must be list of 6-digit codes"})
    return params


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


def _swallow(stage, e):
    """NIT D-8：静默吞错改为 stderr 摘要（诊断细节看服务日志；不回传用户面）。"""
    try:
        sys.stderr.write("[warn] %s: %s: %s\n"
                         % (stage, type(e).__name__, str(e)[:160]))
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass


def global_as_of():
    cands = []
    try:
        st = fund_predict.resolve_state()
        if st["present"] and st["as_of"]:
            cands.append(st["as_of"])
    except Exception as e:  # noqa: BLE001
        _swallow("global_as_of.resolve_state", e)
    try:
        vs = valuation_mod.cached_snapshot().get("as_of")
        if vs:
            cands.append(vs)
    except Exception as e:  # noqa: BLE001
        _swallow("global_as_of.valuation_snapshot", e)
    try:
        rows = ledger_api.read_ledger(limit=1)[0]
        if rows and rows[0].get("date"):
            cands.append(rows[0]["date"])
    except Exception as e:  # noqa: BLE001
        _swallow("global_as_of.ledger", e)
    try:
        hs = holdings_mod.load_holdings().get("holdings", [])
        d, _n, _p = holdings_mod.latest_nav(hs[0]) if hs else (None, None, None)
        if d:
            cands.append(d)
    except Exception as e:  # noqa: BLE001
        _swallow("global_as_of.holdings", e)
    return max(cands) if cands else None


# ================= 任务 =================

_TASKS_LOCK = threading.Lock()
# R2-D3：任务执行全局串行（跨型文件竞态兜底；同型互斥在 start_task 提交侧）
_TASK_EXEC_LOCK = threading.Lock()


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
    """任务执行入口（R2-D3）：

    - 同型互斥：提交侧 `start_task` 拒绝（409 可读）；
    - **全局串行锁**：兜住跨型任务竞态同一文件（已确认 `maintain_nav_history` ×
      `backfill_ledger` 同写 `backfill.jsonl`；见 14 报告 §11）——单用户下任务串行执行。
    """
    with _TASK_EXEC_LOCK:
        _run_task_impl(task)


def _run_task_impl(task):
    ttype = task["type"]
    tid = task["task_id"]
    final_step = "完成"
    _update_task(tid, status="running", started_at=_now_iso(), progress=0.1,
                 step="执行中")
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        if ttype in ("refresh_valuation", "refresh_quotes"):
            _update_task(tid, progress=0.25, step="抓取最新官方净值")
            try:
                estimator.refresh_fund_valuation(hs, allow_network=True, force=True)
                estimator.refresh_official_nav(hs, allow_network=True)
            except Exception:  # noqa: BLE001 - 抓取失败仍进入估值链（缺失显式 null）
                pass
            _update_task(tid, progress=0.4, step="刷新估值五档")
            recs = valuation_mod.refresh_all(hs, as_of_date=_today(), allow_network=True,
                                             force=True)
            summary = "估值刷新 %d/%d" % (len(recs), len(hs))
        elif ttype in ("run_prediction", "rebuild_ddsm"):
            _update_task(tid, progress=0.3, step="拉取代理日线并训练 DDSM")
            snap = fund_predict.run_predictions(hs)
            summary = "预测完成，产出 %d 行（as_of %s）" % (len(snap.get("rows", [])),
                                                        snap.get("as_of"))
        elif ttype == "backfill_ledger":
            mode = (task.get("params") or {}).get("mode", "incremental")
            if mode == "recompute":
                _update_task(tid, progress=0.3,
                             step="按现档位全量重生成影子台账（旧记录先归档）")
                info = ledger_api.recompute_shadow_window(
                    days=ledger_api.SHADOW_WINDOW_DAYS, allow_network=True)
                if info.get("changed"):
                    summary = ("影子台账重算：%d 条 / %s~%s（新增 %d，移除 %d，归档 %d）"
                               % (info.get("total_records", 0), info.get("first_date"),
                                  info.get("last_date"), info.get("added_count", 0),
                                  info.get("removed_count", 0), info.get("archived", 0)))
                else:
                    summary = ("影子台账重算：结果不变，零写入（%s）"
                               % (info.get("reason") or "幂等"))
            else:
                _update_task(tid, progress=0.3,
                             step="按最近 %d 交易日回填影子台账（走前）+ 到期 t*_real 回填"
                                  % ledger_api.SHADOW_WINDOW_DAYS)
                info = ledger_api.rolling_shadow_backfill(
                    days=ledger_api.SHADOW_WINDOW_DAYS, allow_network=True)
                bf = {"due": 0, "written": 0}
                try:
                    bf = ledger_api.backfill_due(allow_network=True)
                except Exception:  # noqa: BLE001 - 回填失败不影响台账窗口
                    pass
                if info.get("days"):
                    summary = ("影子台账回填：窗口 %d 日 / %d 条 / %s~%s（新增 %d，裁剪 %d）；"
                               "t*_real 回填 %d 条（method=proxy_bar）"
                               % (info["days"], info["total_records"], info["first_date"],
                                  info["last_date"], info["written"], info["trimmed"],
                                  bf.get("written", 0)))
                else:
                    summary = "影子台账回填：无可用代理行情，保持为空（未用示例数字）"
        elif ttype == "maintain_nav_history":
            _update_task(tid, progress=0.3, step="维护净值史（lsjz 分页增量）")
            info = valuation_mod.maintain_nav_history(hs, allow_network=True)
            summary = ("净值史维护：%d 只 / 新增 %d 点 / accuracy v2 %s 条"
                       % (info.get("updated", 0), info.get("added_points", 0),
                          info.get("accuracy_entries")))
        elif ttype == "verify_tiers":
            _update_task(tid, progress=0.3, step="单资产生产配置六窗走前验证")
            params = task.get("params") or {}
            info = factor_engine.verify_tiers(
                targets=params.get("targets"), allow_network=True)
            verdicts = info.get("verdicts") or []
            up = sum(1 for v in verdicts if v.get("verdict") == "pass"
                     and v.get("tier_before") == "C")
            hold = info.get("hold_count", 0)
            down = sum(1 for v in verdicts if v.get("verdict") == "downgrade")
            summary = ("验证批次 %s：%d 只（升 B %d / 挂档 %d / 降档 %d）"
                       % (info.get("batch_id"), len(verdicts), up, hold, down))
            if info.get("dilution_gate_triggered"):
                summary += "；防稀释闸触发（>3 只挂档 → 架构×PM 复审）"
        elif ttype == "scan_factors":
            # S5/S-c（D-6 去伪）：无扫描器实现 → 不得以「扫描完成」的成功回执冒充已执行
            _update_task(tid, progress=0.5, step="因子扫描未接入（无扫描器实现）")
            summary = "因子扫描未接入：无扫描器实现，本次未执行扫描、未产出候选"
            final_step = "因子扫描未接入（无扫描器实现）"
        elif ttype == "run_backtest":
            _update_task(tid, progress=0.5, step="走前 CV 回测 + 复盘成绩缓存")
            if not os.path.isfile(factor_engine.ADOPTED_PATH):
                recs = factor_engine.build_adopted_pan()
                summary = "因子盘真实回测：%d 个因子写入 adopted" % len(recs)
            else:
                summary = "因子盘已存在真实回测结果（INSERT-ONLY，不覆盖）"
            try:
                payload = review_mod.build_review_scores()
                summary += "；/review/scores 缓存生成（%d 窗口）" % len(payload.get("scores") or [])
            except Exception as e:  # noqa: BLE001 - 成绩缓存失败不拖垮因子盘
                summary += "；/review/scores 缓存失败：%s" % str(e)[:60]
        else:
            summary = "任务类型无操作"
        _update_task(tid, status="done", progress=1.0, step=final_step,
                     finished_at=_now_iso(), result_summary=summary)
    except errors.ApiError as e:
        _update_task(tid, status="failed", finished_at=_now_iso(),
                     error=e.envelope(), result_summary=None)
    except OSError as e:
        # R2-D3：原生 OSError（含 WinError）不直透 message；详情走 stderr 日志
        sys.stderr.write("[task] %s OSError: %r\n" % (tid, e))
        _update_task(tid, status="failed", finished_at=_now_iso(),
                     error={"code": errors.E_IO,
                            "message": "任务执行失败：本地数据文件被占用或不可用",
                            "detail": None}, result_summary=None)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write("[task] %s failed: %r\n" % (tid, e))
        _update_task(tid, status="failed", finished_at=_now_iso(),
                     error={"code": errors.E_UNKNOWN,
                            "message": "任务执行失败：内部错误（详见服务日志）",
                            "detail": None}, result_summary=None)


def _reject_running_same_type(ttype):
    """同型任务互斥（R2-D3）：存在 `queued/running` 的同类任务 → 409 可读拒绝。

    不落 failed 记录、不启动第二线程（拒绝发生在 `_new_task` 之前）。
    """
    for t in _load_tasks():
        if t.get("type") == ttype and t.get("status") in ("queued", "running"):
            raise errors.ApiError(
                errors.E_CONFLICT,
                "同型任务进行中：%s；可 GET /tasks 查询" % t.get("task_id"),
                {"type": ttype, "running_task_id": t.get("task_id")})


def start_task(ttype, params=None):
    _reject_running_same_type(ttype)
    task = _new_task(ttype, params)
    th = threading.Thread(target=_run_task, args=(task,), daemon=True)
    th.start()
    return task


# ================= Handlers =================

def h_health(query, body, params):
    return {"ok": True, "product": "极境 ZenithLens", "port": DEFAULT_PORT,
            "engine_status": fund_predict.resolve_state()["engine_status"]}


def _latest_nav_date(hs):
    """真实最新官方净值日：优先实时抓取缓存，回退源文件 nav_history。

    来源：本任务「净值快照必须实时抓、反映最近一期官方净值」。
    """
    codes = [h.get("code") for h in (hs or []) if h.get("code")]
    if not codes:
        return None
    try:
        estimator.refresh_fund_valuation(hs, allow_network=True, max_age_sec=RV_NAV_CACHE_SEC)
    except Exception:  # noqa: BLE001 - 缓存新鲜度读取失败不阻塞 /runtime
        pass
    try:
        nav_dates = estimator.cached_nav_dates(codes)
    except Exception:  # noqa: BLE001
        nav_dates = {}
    if nav_dates:
        return max(nav_dates.values())
    if hs:
        d, _n, _p = holdings_mod.latest_nav(hs[0])
        return d
    return None


def h_runtime(query, body, params):
    st = fund_predict.resolve_state()
    hs = holdings_mod.ensure_holdings().get("holdings", [])
    open_count = sum(1 for r in st["rows"] if r.get("signal") == "up") if st["present"] else 0
    as_of = global_as_of()
    # 最新净值日取实时抓取缓存（FundValuationLast/lsjz），源文件 nav_history 仅作回退；
    # 来源：本任务「staleness.latest_date 必须为真实最新净值日，不再是 08-25」。
    latest = _latest_nav_date(hs)
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
    return valuation_mod.trade_session()


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
    hs = _holdings_list()
    hold_map = {h["code"]: h for h in hs}
    tier_map = {h["code"]: h.get("tier") for h in hs}
    as_of = _today()
    rows = []
    for r in st["rows"]:
        if query.get("tier") and tier_map.get(r["code"]) not in query.get("tier").split(","):
            continue
        if query.get("signal") and r.get("signal") != query.get("signal"):
            continue
        rows.append(_prediction_public(r, hold_map, as_of))
    return {"rows": rows, "engine_status": st["engine_status"], "as_of": st["as_of"]}


def _prediction_public(row, hold_map, as_of):
    """PredictionSummary 输出前补 v5（SHOULD-4）字段 tier/market_value。

    口径同 HoldingRow（§5.1/§5.4）：tier 取关联持仓档位；market_value 走
    valuation.market_value_of（估值→净值，两者皆无则 null，禁止成本回退 A-02）。
    R2-09（contract §3.7）：qdii_lead_note 同 HoldingRow，仅 QDII 行非 null。
    """
    out = strip_internal(row)
    h = hold_map.get(row.get("code"))
    if h is None:
        out["tier"] = None
        out["market_value"] = None
        out["qdii_lead_note"] = None
    else:
        out["tier"] = h.get("tier")
        mv, _src, _fb = valuation_mod.market_value_of(h, as_of)
        out["market_value"] = mv
        ft = h.get("fund_type") or estimator.classify_fund_type(h.get("name"))
        out["qdii_lead_note"] = (holdings_mod.QDII_LEAD_NOTE
                                 if (ft == "qdii" and h.get("proxy_code")) else None)
    return out


def h_prediction_get(query, body, params):
    row, st = fund_predict.get_row(params["code"])
    hold_map = {h["code"]: h for h in _holdings_list()}
    out = _prediction_public(row, hold_map, _today())
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
    """R2-11：真实输出（backtest = 生产配置六窗走前缓存；shadow_live = 台账+实测基线）。

    未接通窗口 baseline_status=pending + null（禁止估计值）。来源：review.scores（深模块）。
    """
    data_kind = query.get("data_kind", "backtest")
    return review_mod.scores(data_kind)


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


def h_factors_candidate_submit(query, body, params):
    """v7 §6.8 POST /factors/candidates：提交定义并回测（INSERT-ONLY 账本）。"""
    body = body if isinstance(body, dict) else {}
    result = factor_engine.submit_candidate(body)
    result["_caller_status"] = 202
    return result


def h_factors_candidate_get(query, body, params):
    """v7 §6.8 GET /factors/candidates/{candidate_id}：取记分卡。"""
    include = str(query.get("include_windows", "true")).lower() not in ("false", "0", "no")
    return factor_engine.get_scorecard(params["candidate_id"], include_windows=include)


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
        # shadow_status 采用**进度语义**（not_started/recording/qualified/gap）：
        # 有台账记录即为 recording，不再被偏差评估的 idle 覆盖（用户曾反映连续记录多日仍显示未启动）。
        # 偏差评估独立保留为 shadow_audit_status（idle/ok/bad，契约 §5.29 语义）。
        "shadow_status": progress.get("status", "not_started"),
        "shadow_audit_status": audit.get("status", "idle"),
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
    params = validate_task_payload(ttype, body.get("params") or {})
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
    no_proxy_count = sum(1 for h in hs if not h.get("proxy_code"))
    penetrated_count = sum(1 for h in hs if h.get("penetration_trace"))
    # NIT B-5a：原理无解 = 无代理且无穿透映射（实测；契约 §5.19 当前恒 0）
    no_solution_count = sum(1 for h in hs
                            if not h.get("proxy_code")
                            and not h.get("penetration_trace"))
    # R2-06（contract §3.5）：预测 universe 计数 / 待结论 / 覆盖文案 / 待结论清单
    universe_count = sum(t["count"] for t in tiers if t["tier"] in ("A", "B"))
    pending = [h for h in hs if h.get("tier") == "C"
               and h.get("verify_status") in ("pending_validation", "validating")]
    pending_names = [h.get("name", "") for h in pending[:10]]
    # 原 C 档名单（R2-06）：升 B 者计入 k，覆盖 =（基数+k）/总数 按实计
    c_list = ("022485", "025500", "018957", "021528", "457001", "021662", "163208")
    by_code = {h.get("code"): h for h in hs}
    c_present = [c for c in c_list if c in by_code]
    k = sum(1 for c in c_present
            if by_code[c].get("tier") in ("A", "B")
            and by_code[c].get("verify_status") == "validated")
    base = len(hs) - len(c_present)
    if pending and k == 0:
        note = "预测覆盖 %d/%d（+%d 待结论）" % (base, len(hs), len(c_present))
    else:
        note = "预测覆盖 %d/%d" % (base + k, len(hs))
    return {
        "tiers": tiers, "total_count": len(hs), "total_value": round(total, 2),
        "invalidation_note": INVALIDATION_NOTE, "no_solution_count": no_solution_count,
        # v8 新增（只加不改）：无代理只数 / 经持仓穿透补全只数，便于前端展示 D 档压缩进度。
        "no_proxy_count": no_proxy_count, "penetrated_count": penetrated_count,
        # R2-06/R2-24 新增（只加不改）
        "prediction_universe_count": universe_count,
        "pending_verification_count": len(pending),
        "prediction_coverage_note": note,
        "pending_verification_names": pending_names,
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
    # R2-15（contract §3.11）：主源 = 产品自持 data/holdings.json；primary_* 语义降级为
    # 「可选外部导入源」；导入按钮禁用逻辑由 import_available 驱动。
    import_ok, import_reason = holdings_mod.import_source_status()
    return {
        "primary_path": primary, "primary_exists": p["exists"],
        "primary_modified_at": p["modified_at"], "primary_count": p["count"],
        "legacy_path": legacy, "legacy_exists": l["exists"],
        "legacy_modified_at": l["modified_at"], "legacy_count": l["count"],
        "consistent": consistent, "diff_fields": diff_fields, "readonly": True,
        "main_source": holdings_mod.main_source_status(),
        "import_available": bool(import_ok),
        "import_disabled_reason": import_reason,
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
    ("POST", r"/factors/candidates", h_factors_candidate_submit),
    ("GET", r"/factors/candidates/(?P<candidate_id>[A-Za-z0-9_\-]+)", h_factors_candidate_get),
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


# ---------------- 客户端断连静默（浏览器刷新/切页/取消请求的固有行为） ----------------

# `ConnectionAbortedError/ConnectionResetError/BrokenPipeError` 是客户端先断开时
# 服务端写响应的典型异常（WinError 10053/10054/109 等）；属正常客户端行为：
# 不打堆栈、不发二次响应；非断连异常一律照抛（真错可见，不许误吞）。
DISCONNECT_ERRORS = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)
DISCONNECT_SUPPRESSED = {"count": 0, "last_at": None}


def _is_disconnect(exc):
    return isinstance(exc, DISCONNECT_ERRORS)


def _note_disconnect():
    DISCONNECT_SUPPRESSED["count"] = int(DISCONNECT_SUPPRESSED["count"]) + 1
    DISCONNECT_SUPPRESSED["last_at"] = _now_iso()


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """断连族静默（客户端刷新/切页/取消）；其他异常保持默认堆栈（真错可见）。"""

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if _is_disconnect(exc):
            _note_disconnect()
            return
        ThreadingHTTPServer.handle_error(self, request, client_address)


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
    try:
        handler.end_headers()
        handler.wfile.write(raw)
    except DISCONNECT_ERRORS:
        # 客户端已断开：无接收方，静默返回；其他异常继续抛（不吞真错）
        _note_disconnect()
        return


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
    try:
        handler.end_headers()
        handler.wfile.write(data)
    except DISCONNECT_ERRORS:
        # 客户端已断开：静默；其他异常继续抛
        _note_disconnect()
        return


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
                if isinstance(data, dict):
                    _cs = data.pop("_caller_status", None)
                    if _cs:
                        status = _cs
                self._envelope_ok(data, status)
            except errors.ApiError as e:
                self._envelope_err(e)
            except Exception as e:  # noqa: BLE001
                # 断连族：客户端已走，直接返回（不打堆栈、不发二次响应）；其余照旧
                if _is_disconnect(e):
                    _note_disconnect()
                    return
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
    """启动预热（R2 调整序列；08-backend-arch-r2 §7.2；保持「打开即有数据」）。

    run_predictions → maintain_nav_history（净值史+accuracy v2+日留档+回填+QDII 复评）
    → refresh_fund_valuation(force) → refresh_official_nav → refresh_all(force)
    → backfill_ledger[incremental]（滚动窗口 + t*_real 回填）
    → refresh_penetrations → ensure_adopted_pan → review.scores 缓存生成

    S3：每阶段打点 stderr（`[warmup] +N.NNs <stage>`），便于冷启动时延定位与证据留存。
    """
    t0 = time.time()

    def _wt(stage):
        sys.stderr.write("[warmup] +%.2fs %s\n" % (time.time() - t0, stage))
        sys.stderr.flush()

    time.sleep(0.5)
    _wt("start")
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        # S3 冷启动预热：先落历史解析缓存 / 快照 / 预测快照，
        # 使首个 /holdings 不必付整文件解析与磁盘竞争开销（不阻塞就绪）。
        try:
            valuation_mod.read_history()
            valuation_mod.cached_snapshot()
            fund_predict.resolve_state()
        except Exception as e:  # noqa: BLE001
            _swallow("warmup.prewarm_caches", e)
        _wt("prewarm caches (history/snapshot)")
        if not hs:
            return
        fund_predict.run_predictions(hs)
        _wt("run_predictions")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.run_predictions", e)
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        # R2-16：净值史维护（含 accuracy v2 / 日留档 / t*_real 回填 / QDII 复评 / 证据道）
        valuation_mod.maintain_nav_history(hs, allow_network=True)
        _wt("maintain_nav_history")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.maintain_nav_history", e)
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        # 启动即批量抓最新官方净值/盘中估算（带超时/缓存），
        # 保证 /runtime staleness 与 /valuations 反映最近一期官方净值。
        estimator.refresh_fund_valuation(hs, allow_network=True, force=True)
        _wt("refresh_fund_valuation")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.refresh_fund_valuation", e)
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        estimator.refresh_official_nav(hs, allow_network=True)
        _wt("refresh_official_nav")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.refresh_official_nav", e)
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        valuation_mod.refresh_all(hs, as_of_date=_today(), allow_network=True, force=True)
        _wt("refresh_all")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.refresh_all", e)
    try:
        # 启动即滚动回填影子台账最近 60 个交易日（INSERT-ONLY；重复启动幂等）+ t*_real 回填。
        ledger_api.rolling_shadow_backfill(days=ledger_api.SHADOW_WINDOW_DAYS,
                                           allow_network=True)
        ledger_api.backfill_due(allow_network=True)
        _wt("rolling_shadow_backfill + backfill_due")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.rolling_shadow_backfill", e)
    try:
        # 主动全市场基金持仓穿透：F10 前十 → 行业 ETF，缓存 24h；成功后下次 ensure_holdings 升 C。
        proxy_map.refresh_penetrations(allow_network=True)
        holdings_mod.ensure_holdings()
        _wt("refresh_penetrations")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.refresh_penetrations", e)
    try:
        # 因子盘真实回测：正式盘账本缺失时用引擎在用的 KLOW2/拥挤度六维回测生成。
        factor_engine.ensure_adopted_pan()
        _wt("ensure_adopted_pan")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.ensure_adopted_pan", e)
    try:
        # R2-11：/review/scores 回测缓存生成（可重建；同 bars+冻结配置+seed 可复现）。
        # S3：当日缓存直接复用（warmup 不重复跑重 CPU 评估）；run_backtest 任务仍强制重生成。
        if not review_mod.cache_fresh():
            review_mod.build_review_scores()
            _wt("review.scores build")
        else:
            _wt("review.scores reuse (fresh)")
    except Exception as e:  # noqa: BLE001
        _swallow("warmup.review_scores", e)
    _wt("done")


def main():
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
    httpd = QuietThreadingHTTPServer((HOST, port), handler)
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
