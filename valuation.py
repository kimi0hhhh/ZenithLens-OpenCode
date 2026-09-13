# -*- coding: utf-8 -*-
"""估值五档降级链：official → intraday → holdings → proxy → unknown。

- 顺序与 trace 穷举：08-backend-arch.md §3.1；硬规则 §3.2
- v10（本任务）：主动基金估值锚点 = 前十大重仓股加权（holdings，优先于 proxy），
  按 `fund_type`（active/index_link/qdii/other，estimator.classify_fund_type）分流；
  指数联接/QDII 维持 proxy/intraday。预测锚点仍为代理 ETF 日线（估值锚点 ≠ 预测代理）。
- 当日 INSERT-ONLY：valuation_history.jsonl 为审计源；valuation.json 仅缓存（A-01）
- 未知口径：unknown 必 change_rate=null；禁止 +0.00% 冒充（契约 §1.2/§5.2）
- 置信度：mae <=0.008 high / <=0.012 mid / >0.012 low；无回测 unknown
  对照行业基准 0.008（契约 §5.2；基准来源见残留风险）
"""

import io
import json
import os
import re
import sys
import threading
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
# R2 新增存储（08-backend-arch-r2 §2）
NAV_STORE_DIR = os.path.join(DATA_DIR, "cache", "nav")          # data/cache/nav/<code>.json
DAILY_DIR = os.path.join(SNAP_DIR, "daily")                      # valuation-YYYYMMDD.jsonl
PROXY_QUALITY_PATH = os.path.join(SNAP_DIR, "proxy_quality.json")  # 代理质量证据道（D-2）
REVIEW_DIR = os.path.join(DATA_DIR, "review")
QDII_REVIEW_PATH = os.path.join(REVIEW_DIR, "qdii_review.jsonl")   # INSERT-ONLY（R-5）
QDII_CONFIG_PATH = os.path.join(DATA_DIR, "qdii_correction.json")  # 开关与复评预注册

INDUSTRY_BASELINE_MAE = 0.008
ACCURACY_WINDOW_DAYS = 40
TOTAL_BUDGET_SEC = 20.0
# 盘中估算需较实时：缓存复用窗口从 300s 收窄到 60s（来源：本任务「真实、实时」目标）
REUSE_AGE_SEC = 60

MODE_LABEL = {
    "official": "官方净值",
    "intraday": "盘中估算",
    "holdings": "重仓加权",
    "proxy": "代理近似",
    "unknown": "未知",
}
CONF_LABEL = {"high": "误差达标", "mid": "误差中等", "low": "误差偏大", "unknown": "无可信估算"}
# v5 缺口4：/valuations/precision.groups[].label 短标签（高/中/低/无），与 confidence 同映射轴
CONF_GROUP_LABEL = {"high": "高", "mid": "中", "low": "低", "unknown": "无"}
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


def trade_session(now=None):
    """A 股交易时段判定（契约 §1.3 trade_session）。

    pre_open <09:30 / trading 09:30-15:00 / closed ≥15:00 / non_trading_day 周末。
    口径来源：本任务「仅交易日盘中才允许 intraday；周末/收盘后用最新官方净值」。
    """
    now = now or datetime.now()
    if now.weekday() >= 5:
        return "non_trading_day"
    hm = now.hour * 60 + now.minute
    if hm < 9 * 60 + 30:
        return "pre_open"
    if hm < 15 * 60:
        return "trading"
    return "closed"


def _mode_reusable(mode, session):
    """当日缓存复用闸：非盘中时段不得复用 intraday（否则周末会拿旧盘中估算冒充实时）。"""
    return not (mode == "intraday" and session != "trading")


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
    for d in (SNAP_DIR, os.path.join(DATA_DIR, "cache"), NAV_STORE_DIR, DAILY_DIR):
        if not os.path.isdir(d):
            os.makedirs(d)


# ---------------- 历史读写（INSERT-ONLY） ----------------

# S3 冷启动：valuation_history 是全量 JSONL（MB 级），/holdings 单请求会按 (code,date)
# 多次全文件扫描；按 (path, mtime_ns, size) 缓存解析结果，写后失效（append 同步追加）。
_HISTORY_CACHE = {"path": None, "sig": None, "rows": []}
_HISTORY_LOCK = threading.Lock()


def _parse_history_file(path):
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


def _history_rows():
    """按文件签名缓存的历史记录（只读共享；写后由 append_history/签名失配失效）。"""
    path = HISTORY_PATH
    try:
        st = os.stat(path)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        with _HISTORY_LOCK:
            _HISTORY_CACHE.update({"path": path, "sig": None, "rows": []})
        return []
    with _HISTORY_LOCK:
        if _HISTORY_CACHE.get("path") == path and _HISTORY_CACHE.get("sig") == sig:
            return _HISTORY_CACHE["rows"]
    rows = _parse_history_file(path)
    with _HISTORY_LOCK:
        _HISTORY_CACHE.update({"path": path, "sig": sig, "rows": rows})
    return rows


def read_history(code=None, date=None):
    rows = _history_rows()
    if code is None and date is None:
        return list(rows)
    return [r for r in rows
            if (code is None or r.get("code") == code)
            and (date is None or r.get("date") == date)]


def append_history(rec):
    _ensure_dirs()
    with io.open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # 缓存热时同步追加，避免随后读取触发整文件重解析
    with _HISTORY_LOCK:
        if _HISTORY_CACHE.get("path") == HISTORY_PATH and _HISTORY_CACHE.get("rows"):
            _HISTORY_CACHE["rows"].append(rec)
            try:
                st = os.stat(HISTORY_PATH)
                _HISTORY_CACHE["sig"] = (st.st_mtime_ns, st.st_size)
            except OSError:
                _HISTORY_CACHE["sig"] = None


def latest_for(code, date):
    recs = read_history(code=code, date=date)
    if not recs:
        return None
    recs.sort(key=lambda r: r.get("written_at") or "")
    return recs[-1]


def history_available(code):
    return len(read_history(code=code)) > 0


# ---------------- 置信度 / 精度（通道 v2：全档 mode|code，R2-01） ----------------

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
    """按 `mode|code` 全档归键读取统计（v9 结构）；兼容 `mode|*` 旧键。"""
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


# ---------------- 维护版净值史 data/cache/nav/<code>.json（R2-16 / §6.1） ----------------

def _read_json_file(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def _write_json_atomic(path, obj):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _nav_store_path(code):
    return os.path.join(NAV_STORE_DIR, "%s.json" % code)


def load_nav_history(hold_list=None):
    """净值史统一入口：nav_store（权威）→ holdings.nav_history（legacy 回退）。

    返回 {code: {"points": [{date, nav}], "source": "nav_store"|"legacy_nav_history",
    "updated_at": ...}}；缺数据不编造（缺者不入表）。
    """
    store = {}
    if os.path.isdir(NAV_STORE_DIR):
        for name in sorted(os.listdir(NAV_STORE_DIR)):
            if not re.match(r"^\d{6}\.json$", name):
                continue
            code = name[:-5]
            obj = _read_json_file(os.path.join(NAV_STORE_DIR, name))
            pts = obj.get("points") if isinstance(obj.get("points"), list) else []
            pts = [p for p in pts if p.get("date") and p.get("nav") is not None]
            if pts:
                store[code] = {"points": pts, "source": "nav_store",
                               "updated_at": obj.get("updated_at")}
    if hold_list is None:
        try:
            hold_list = holdings_mod.load_holdings().get("holdings", [])
        except Exception:  # noqa: BLE001 - 回退源不可读即跳过（不阻塞）
            hold_list = []
    for h in hold_list or []:
        code = str(h.get("code") or "")
        if not code or code in store:
            continue
        nh = h.get("nav_history") or {}
        pts = [{"date": d, "nav": nh[d]} for d in sorted(nh.keys())
               if nh.get(d) is not None]
        if pts:
            store[code] = {"points": pts, "source": "legacy_nav_history",
                           "updated_at": None}
    return store


def nav_pair(store, code, date):
    """返回 (nav(D), nav(D-1))；D 无净值或缺前一日 → None（不填 0）。"""
    entry = (store or {}).get(str(code))
    if not entry:
        return None
    pts = entry.get("points") or []
    dates = [p.get("date") for p in pts]
    if date not in dates:
        return None
    i = dates.index(date)
    if i < 1:
        return None
    nav = pts[i].get("nav")
    prev = pts[i - 1].get("nav")
    if nav is None or prev in (None, 0):
        return None
    return float(nav), float(prev)


def maintain_nav_history(hold_list, allow_network=True):
    """维护版净值史：lsjz 分页增量补全 + 重算估值误差通道 + 日留档 + t*_real 回填。

    幂等（按 date 去重、既有日期不覆盖）；接口失败保留已有 + 标注滞后（不编造净值）。
    口径来源：08-backend-arch-r2 §6.1（R2-16）/ §3.1（R2-01）/ §3.4（R2-05）。
    """
    if not os.path.isdir(NAV_STORE_DIR):
        os.makedirs(NAV_STORE_DIR)
    result = {"updated": 0, "failed": [], "added_points": 0}
    for h in hold_list or []:
        code = str(h.get("code") or "")
        if not code:
            continue
        path = _nav_store_path(code)
        existing = _read_json_file(path)
        pts = existing.get("points") if isinstance(existing.get("points"), list) else []
        known = {p.get("date") for p in pts if p.get("date")}
        hist = estimator.lsjz_history(code, allow_network=allow_network,
                                      existing_dates=known)
        if hist is None:
            result["failed"].append(code)
            continue
        added = 0
        for row in hist:
            d, nav = row.get("date"), row.get("nav")
            if d and nav is not None and d not in known:
                pts.append({"date": d, "nav": nav})
                known.add(d)
                added += 1
        pts.sort(key=lambda p: p.get("date") or "")
        _write_json_atomic(path, {"code": code, "updated_at": _now_iso(),
                                  "points": pts})
        result["updated"] += 1
        result["added_points"] += added
    # §3.1：净值就绪后重算误差通道
    try:
        result["accuracy_entries"] = len(build_accuracy(hold_list, allow_network=False))
    except Exception:  # noqa: BLE001 - 通道失败不阻塞净值维护
        result["accuracy_entries"] = None
    # §3.4：日留档（收盘后；盘中不写）
    try:
        result["archived"] = archive_daily(None)
    except Exception:  # noqa: BLE001
        result["archived"] = None
    # §5.2：到期 t*_real 自动回填（独立 backfill.jsonl）
    try:
        import ledger_api
        result["backfill"] = ledger_api.backfill_due(allow_network=allow_network)
    except Exception:  # noqa: BLE001
        result["backfill"] = None
    # §3.3：QDII 首测/复评（R-5）
    try:
        result["qdii_review"] = evaluate_qdii_review(hold_list, allow_network=allow_network)
    except Exception:  # noqa: BLE001
        result["qdii_review"] = None
    # D-2(a)：代理质量重建证据道（bars × nav 史）
    try:
        result["proxy_quality"] = len(build_proxy_quality(hold_list, allow_network=False))
    except Exception:  # noqa: BLE001
        result["proxy_quality"] = None
    return result


# ---------------- 误差通道 v2（R2-01；评分对象 D-3：同 mode 当日最后一条） ----------------

def build_accuracy(hold_list, allow_network=True):
    """全档 `mode|code` 误差统计：评分对象 = 每个 (date, code, mode) 当日最后一条。

    口径来源：09-api-contract-r2 §3.2（v9.1/D-3/M1）+ 08-backend-arch-r2 §3.1：
    - 估值样本来自 valuation_history（INSERT-ONLY）；官方净值来自 nav_store
      （回退 holdings.nav_history 并标注 source）；
    - 真值 = nav(D)/nav(D−1) − 1；不可配对日期跳过（不填 0）；
    - 滚动窗 = 最近 40 个可配对交易日；n_test ≥ 5 才产出统计值（否则 null + no_samples）。
    """
    store = load_nav_history(hold_list)
    acc = {}
    for h in hold_list or []:
        code = str(h.get("code") or "")
        if code not in store:
            continue
        recs = read_history(code=code)
        by_day = {}
        for r in recs:
            d = r.get("date")
            m = r.get("valuation_mode")
            if not d or not m:
                continue
            by_day.setdefault(d, {}).setdefault(m, []).append(r)
        samples_by_mode = {}
        for D in sorted(by_day.keys()):
            pair = nav_pair(store, code, D)
            if pair is None:
                continue
            real = pair[0] / pair[1] - 1.0
            for mode, mrecs in by_day[D].items():
                # D-3：同 mode 当日最后一条（同 mode 同日多轮取最后，防污染）
                rep = max(mrecs, key=lambda r: r.get("written_at") or "")
                est = rep.get("change_rate")
                if est is None:
                    continue  # unknown 记录不参与评分
                samples_by_mode.setdefault(mode, []).append({
                    "date": D, "est": float(est), "real": real,
                    "err": abs(float(est) - real),
                    "dir_ok": ((float(est) > 0) == (real > 0)) if real != 0 else None,
                })
        for mode, samples in samples_by_mode.items():
            samples.sort(key=lambda s: s.get("date") or "")
            window = samples[-ACCURACY_WINDOW_DAYS:]
            n = len(window)
            if n <= 0:
                continue
            entry = {
                "mode": mode, "code": code, "mae_rate": None, "dir_hit_rate": None,
                "n_test": n, "window_days": ACCURACY_WINDOW_DAYS,
                "updated_at": _now_iso(),
                "matched_days": [s["date"] for s in window],
                "source": store[code].get("source", "nav_store"),
            }
            if n >= 5:
                errs = [s["err"] for s in window]
                considered = [s for s in window if s["dir_ok"] is not None]
                hits = sum(1 for s in considered if s["dir_ok"])
                entry["mae_rate"] = _f4(sum(errs) / float(len(errs)))
                entry["dir_hit_rate"] = (_f4(hits / float(len(considered)))
                                         if considered else None)
            acc["%s|%s" % (mode, code)] = entry
    save_accuracy(acc)
    return acc


def window_filled_days(hold_list=None):
    """40 日精度窗内已积累的可配对交易日数（matched_days 并集，累计 X/40）。"""
    acc = load_accuracy()
    codes = None
    if hold_list:
        codes = {str(h.get("code")) for h in hold_list}
    dates = set()
    for key, entry in (acc or {}).items():
        if not isinstance(entry, dict):
            continue
        if codes is not None and str(entry.get("code")) not in codes:
            continue
        for d in entry.get("matched_days") or []:
            if d:
                dates.add(d)
    return min(ACCURACY_WINDOW_DAYS, len(sorted(dates)[-ACCURACY_WINDOW_DAYS:]))


def window_phase(window_filled):
    """双时点（v9.1/D-2(b)）：<5 warming / ≥5 且 <40 first_verdict / ≥40 mature。"""
    n = int(window_filled or 0)
    if n >= ACCURACY_WINDOW_DAYS:
        return "mature"
    if n >= 5:
        return "first_verdict"
    return "warming"


# ---------------- conf_reason（读取层生成；按序命中即停 R-4） ----------------

def _missing_conf_reason(code, as_of_date=None):
    """无当日记录：预算跳过 → budget_exceeded；否则 valuation_missing（序 2/3）。"""
    date = as_of_date or _today()
    snap = cached_snapshot()
    if snap.get("as_of") == date:
        b = snap.get("budget") or {}
        if code and code in (b.get("skipped") or []):
            return "budget_exceeded"
    return "valuation_missing"


def conf_reason_of(rec, code=None, as_of_date=None):
    """conf_reason 五值穷举 + 按序命中即停（08-backend-arch-r2 §3.1.1 / v9.1/R-4）。

    仅在 `confidence=unknown` 时非 null；confidence 非 unknown → null。
    """
    if rec is None:
        return _missing_conf_reason(code, as_of_date)
    if rec.get("confidence") != "unknown":
        return None
    wrote = rec.get("written_at") is not None
    if not wrote:
        return _missing_conf_reason(rec.get("code") or code,
                                    rec.get("date") or as_of_date)
    mode = rec.get("valuation_mode")
    if mode == "unknown":
        return "mode_unknown"                       # 序 1
    store = load_nav_history()
    c = rec.get("code") or code
    d = rec.get("date")
    if nav_pair(store, c, d) is None:
        return "nav_missing"                        # 序 4（有记录但净值对缺）
    a = accuracy_for(mode, c)
    n = a.get("n_test")
    if not n or int(n) < 5:
        return "no_samples"                         # 序 5
    return None


# ---------------- 日留档（R2-05；写入即只读、幂等） ----------------

def archive_daily(date=None):
    """每日估值留档 `data/snapshot/daily/valuation-YYYYMMDD.jsonl`（每基金 1 行）。

    - 幂等：一文件一快照日，已存在即返回 0；
    - 盘中不写（仅 closed / non_trading_day）；
    - 行字段穷举：{date, code, valuation_mode, change_rate, estimated_nav, nav_date, written_at}。
    来源：08-backend-arch-r2 §3.4（R2-05）。
    """
    date = date or cached_snapshot().get("as_of") or _today()
    if trade_session() == "trading":
        return 0
    path = os.path.join(DAILY_DIR, "valuation-%s.jsonl" % str(date).replace("-", ""))
    if os.path.isfile(path):
        return 0
    snap = cached_snapshot()
    if snap.get("as_of") == date:
        recs = snap.get("records") or []
    else:
        recs = read_history(date=date)
    by_code = {}
    for r in recs:
        c = r.get("code")
        if not c:
            continue
        prev = by_code.get(c)
        if prev is None or (r.get("written_at") or "") >= (prev.get("written_at") or ""):
            by_code[c] = r
    if not by_code:
        return 0
    if not os.path.isdir(DAILY_DIR):
        os.makedirs(DAILY_DIR)
    tmp = path + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as f:
            for c in sorted(by_code):
                r = by_code[c]
                f.write(json.dumps({
                    "date": date, "code": c,
                    "valuation_mode": r.get("valuation_mode"),
                    "change_rate": r.get("change_rate"),
                    "estimated_nav": r.get("estimated_nav"),
                    "nav_date": r.get("nav_date"),
                    "written_at": r.get("written_at"),
                }, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except (IOError, OSError):
        # 文件不可写 → 启动告警（health note），不阻塞估值链（§3.4）
        try:
            import settings as settings_mod
            settings_mod.record_source("eastmoney", True, note="daily archive write skipped")
        except Exception:  # noqa: BLE001
            pass
        return 0
    return len(by_code)


# ---------------- 代理质量重建证据道（D-2(a)；与展示通道分键分文件） ----------------

def load_proxy_quality():
    obj = _read_json_file(PROXY_QUALITY_PATH)
    return obj.get("entries") if isinstance(obj.get("entries"), dict) else {}


def build_proxy_quality(hold_list, allow_network=False):
    """代理质量证据道：bars × nav 史 40 日窗重建（R2-04 首选证据）。

    口径来源：08-backend-arch-r2 §3.1b（v3.1/D-2(a)）+ ADR-0015：
    - est = proxy_bars[D].close / proxy_bars[D-1].close − 1；
    - real = nav(D)/nav(D−1) − 1（nav 史维护版）；
    - 与展示通道（accuracy.json）**分键分文件**，禁止互相引用充当判据。
    落 `data/snapshot/proxy_quality.json`（整文件原子替换；可重建）。
    """
    store = load_nav_history(hold_list)
    entries = {}
    for h in hold_list or []:
        code = str(h.get("code") or "")
        proxy = h.get("proxy_code")
        if not proxy:
            continue
        try:
            bars, _meta = estimator.get_bars(proxy, allow_network=allow_network)
        except Exception:  # noqa: BLE001 - 单资产取数失败按无证据处理
            bars = []
        by_date = {b.get("date"): b for b in bars if b.get("date")}
        dates = sorted(by_date.keys())
        entry = {"code": code, "proxy_code": str(proxy), "mae_rate": None,
                 "dir_hit_rate": None, "n_test": 0,
                 "window_days": ACCURACY_WINDOW_DAYS, "matched_days": [],
                 "updated_at": _now_iso(), "source": "bars_x_nav"}
        if code in store:
            nav_dates = [p.get("date") for p in store[code].get("points", [])]
            samples = []
            for i, D in enumerate(nav_dates):
                if i < 1:
                    continue
                bar_idx = dates.index(D) if D in by_date else None
                if bar_idx is None or bar_idx < 1:
                    continue
                pair = nav_pair(store, code, D)
                if pair is None:
                    continue
                est = by_date[D]["close"] / by_date[dates[bar_idx - 1]]["close"] - 1.0
                real = pair[0] / pair[1] - 1.0
                samples.append((D, est, real))
            samples = samples[-ACCURACY_WINDOW_DAYS:]
            n = len(samples)
            entry["n_test"] = n
            entry["matched_days"] = [s[0] for s in samples]
            if n > 0:
                errs = [abs(e - r) for _d, e, r in samples]
                considered = [(e > 0) == (r > 0) for _d, e, r in samples if r != 0]
                entry["mae_rate"] = _f4(sum(errs) / float(n))
                entry["dir_hit_rate"] = (_f4(sum(1 for x in considered if x) /
                                             float(len(considered)))
                                         if considered else None)
        entries[code] = entry
    _write_json_atomic(PROXY_QUALITY_PATH, {"updated_at": _now_iso(), "entries": entries})
    return entries



# ---------------- QDII 双段校正（R2-03 / ISSUE-ZL-R2-01；v9.1/R-5 门槛与复评） ----------------

QDII_NOTE_BASE = ("双段=境内收盘+隔夜参照，时间互补加法拼接（不引入学习权重）；"
                  "不构成投资建议。")
QDII_TARGETS = {"024239": 0.0150, "016665": 0.0150, "012922": 0.0150,
                "457001": 0.0100, "021662": 0.0100}
QDII_REVIEW_STEP_DAYS = 20     # 复评：每 20 可配对日（R-5）
QDII_MIN_MATCHED = 20          # 首测门槛 n_test≥20（R-5；40 日窗内）


def market_of(h):
    """跨市场 QDII 的参照市场枚举（穷举 US_NDX/HK_HSI；其余 None → 不做双段）。"""
    code = str(h.get("code") or "")
    proxy = str(h.get("proxy_code") or "")
    if code in ("024239", "016665", "012922") or proxy == "513100":
        return "US_NDX"
    if code in ("457001", "021662") or proxy == "159920":
        return "HK_HSI"
    return None


def load_qdii_config():
    obj = _read_json_file(QDII_CONFIG_PATH)
    return {
        "enabled": bool(obj.get("enabled", True)),
        "decided_at": obj.get("decided_at"),
        "reason": obj.get("reason") or ("待首测：40 个可配对日窗且 n_test≥20 方可判定 "
                                        "（未达门槛挂档观察）"),
        "next_review_date": obj.get("next_review_date"),
        "last_review": obj.get("last_review"),
    }


def save_qdii_config(cfg):
    _write_json_atomic(QDII_CONFIG_PATH, cfg)
    return cfg


def append_qdii_review(row):
    if not os.path.isdir(REVIEW_DIR):
        os.makedirs(REVIEW_DIR)
    row = dict(row)
    row.setdefault("at", _now_iso())
    with io.open(QDII_REVIEW_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_qdii_review():
    rows = []
    if not os.path.isfile(QDII_REVIEW_PATH):
        return rows
    try:
        with io.open(QDII_REVIEW_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except (IOError, OSError):
        return []
    return rows


def _aligned(ovs, dom):
    """时间对齐校验：ovs 收盘时刻晚于 domestic 交易日 A 股收盘 15:00。

    - 隔夜交易日 > 境内段日 → 对齐（时间互补，防双计）；
    - 同日：用行情时间字段的钟点判断（>15:00）；无法验证 → False（不静默采用）。
    来源：08-backend-arch-r2 §3.3（架构冻结口径）。
    """
    ot = (ovs or {}).get("trade_date")
    dt = (dom or {}).get("as_of")
    if not ot or not dt:
        return False
    if ot > dt:
        return True
    if ot < dt:
        return False
    ts = (ovs or {}).get("close_ts") or ""
    m = re.match(r"^\d{4}-\d{2}-\d{2} (\d{2}):(\d{2})", str(ts))
    if not m:
        return False
    return int(m.group(1)) * 60 + int(m.group(2)) > 15 * 60


def _log_alignment_conflict(code, domestic_date, overseas_trade_date):
    """alignment_conflict 触发即落 qdii_review.jsonl（同键去重；R-5）。"""
    for row in _read_qdii_review():
        if (row.get("kind") == "alignment_conflict" and row.get("code") == code
                and row.get("domestic_date") == domestic_date
                and row.get("overseas_trade_date") == overseas_trade_date):
            return
    append_qdii_review({"kind": "alignment_conflict", "code": code,
                        "domestic_date": domestic_date,
                        "overseas_trade_date": overseas_trade_date})


def _correction_note(reason=None, cfg=None):
    if reason == "overseas_unavailable":
        return QDII_NOTE_BASE + "本次单段（隔夜数据缺失）。"
    if reason == "alignment_conflict":
        return QDII_NOTE_BASE + "本次单段（时间对齐校验失败）。"
    if reason == "first_test_failed":
        lr = (cfg or {}).get("last_review") or {}
        extra = ""
        if lr:
            extra = ("单段实测 MAE %s vs 目标 %s（差 %s pp）。"
                     % (lr.get("single_mae"), lr.get("target_mae"),
                        lr.get("gap_pp")))
        return QDII_NOTE_BASE + "首测不达标已回退单段（暂态，预注册复评日）。" + extra
    return QDII_NOTE_BASE


def qdii_estimate(h, date_T, session=None, allow_network=True):
    """QDII 双段估算：境内 ETF 收盘段 + 隔夜参照段。

    返回 `(change_rate, correction)`；代理 bar 不足 → `(None, None)`（落回既有 proxy 链，
    qdii_correction=null）。回退矩阵穷举（§3.3）：overseas_unavailable /
    alignment_conflict / first_test_failed（回退均为暂态、带数字）。
    """
    market = market_of(h)
    proxy = h.get("proxy_code")
    if not market or not proxy:
        return None, None
    try:
        bars, _meta = estimator.get_bars(proxy, allow_network=allow_network)
    except Exception:  # noqa: BLE001
        bars = []
    if len(bars) < 2:
        return None, None
    idx = len(bars) - 1
    session = session or trade_session()
    if session == "trading" and bars[idx].get("date") == date_T:
        idx -= 1  # 最近已收盘交易日（盘中不取未收盘 bar）
    if idx < 1:
        return None, None
    b, bp = bars[idx], bars[idx - 1]
    if not b.get("close") or not bp.get("close"):
        return None, None
    r_dom = b["close"] / bp["close"] - 1.0
    dom = {"value": _f4(r_dom), "as_of": b.get("date")}
    cfg = load_qdii_config()
    base = {"method": "etf_close_plus_overnight", "domestic": dom}
    if not cfg.get("enabled"):
        corr = dict(base, applied=False, overseas=None,
                    fallback_reason="first_test_failed",
                    note=_correction_note("first_test_failed", cfg))
        return r_dom, corr
    ovs = None
    try:
        ovs = estimator.overseas_ref_quote(market)
    except Exception:  # noqa: BLE001 - 探测失败按不可得（不编造）
        ovs = None
    if ovs is None:
        return r_dom, dict(base, applied=False, overseas=None,
                           fallback_reason="overseas_unavailable",
                           note=_correction_note("overseas_unavailable"))
    ovs_pub = {"value": _f4(ovs.get("value")), "ref_code": ovs.get("ref_code"),
               "trade_date": ovs.get("trade_date"), "source": ovs.get("source")}
    if not _aligned(ovs, dom):
        _log_alignment_conflict(h.get("code"), dom.get("as_of"),
                                ovs.get("trade_date"))
        return r_dom, dict(base, applied=False, overseas=ovs_pub,
                           fallback_reason="alignment_conflict",
                           note=_correction_note("alignment_conflict"))
    return (r_dom + float(ovs.get("value") or 0.0),
            dict(base, applied=True, overseas=ovs_pub, fallback_reason=None,
                 note=QDII_NOTE_BASE))


def _qdii_samples(records, store, code):
    """从估值记录构造双段评分样本（同 mode 同日最后一条；不可配对不填 0）。"""
    by_day = {}
    for r in records:
        d = r.get("date")
        if not d:
            continue
        prev = by_day.get(d)
        if prev is None or (r.get("written_at") or "") >= (prev.get("written_at") or ""):
            by_day[d] = r
    samples = []
    for D in sorted(by_day.keys()):
        rec = by_day[D]
        if rec.get("change_rate") is None:
            continue
        pair = nav_pair(store, code, D)
        if pair is None:
            continue
        corr = rec.get("qdii_correction")
        if not corr or not corr.get("domestic"):
            continue
        samples.append({
            "date": D,
            "real": pair[0] / pair[1] - 1.0,
            "dual": float(rec["change_rate"]) if corr.get("applied") else None,
            "single": corr["domestic"].get("value"),
        })
    return samples[-ACCURACY_WINDOW_DAYS:]


def next_trading_days(date_str, n):
    """date_str 之后的第 n 个交易日（周一~周五近似；无官方历）。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        d = datetime.now().date()
    added = 0
    while added < int(n):
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d.strftime("%Y-%m-%d")


def evaluate_qdii_review(hold_list, allow_network=False):
    """QDII 首测/复评（R-5）：门槛 40 可配对日窗且 n_test≥20，未达挂档观察。

    - 达标（双段 MAE ≤ 目标）→ 保持启用，写复评事件；
    - 不达标 → `first_test_failed`（暂态回退单段）预注册复评日；
    - alignment_conflict 40 日窗内 ≥5 次 → 追加人工复核事件。
    """
    store = load_nav_history(hold_list)
    cfg = load_qdii_config()
    decisions = []
    today = _today()
    for h in hold_list or []:
        code = str(h.get("code") or "")
        if market_of(h) is None:
            continue
        samples = _qdii_samples(read_history(code=code), store, code)
        applied = [s for s in samples if s["dual"] is not None]
        n_test = len(applied)
        target = QDII_TARGETS.get(code, 0.0100)
        if n_test < QDII_MIN_MATCHED:
            lr = cfg.get("last_review") or {}
            if lr.get("verdict") != "hold" or lr.get("code") != code:
                append_qdii_review({
                    "kind": "qdii_review", "code": code, "verdict": "hold",
                    "n_test": n_test, "n_matched_days": len(samples),
                    "threshold": {"min_matched_days": ACCURACY_WINDOW_DAYS,
                                  "min_n_test": QDII_MIN_MATCHED},
                    "target_mae": target,
                    "note": "未达首测门槛，挂档观察（不得宣布首测失败）",
                })
                cfg["last_review"] = {"code": code, "verdict": "hold",
                                      "n_matched_days": n_test, "at": _now_iso()}
                save_qdii_config(cfg)
            decisions.append({"code": code, "verdict": "hold", "n_test": n_test})
            continue
        dual_mae = sum(abs(s["dual"] - s["real"]) for s in applied) / float(n_test)
        single_vals = [s for s in applied if s["single"] is not None]
        single_mae = (sum(abs(s["single"] - s["real"]) for s in single_vals) /
                      float(len(single_vals))) if single_vals else None
        gap_pp = (dual_mae - target) * 100.0
        verdict = "pass" if dual_mae <= target else "first_test_failed"
        lr = cfg.get("last_review") or {}
        should_write = (lr.get("verdict") != verdict or lr.get("code") != code
                        or (n_test - int(lr.get("n_matched_days") or 0))
                        >= QDII_REVIEW_STEP_DAYS)
        if should_write:
            append_qdii_review({
                "kind": "qdii_review", "code": code, "verdict": verdict,
                "dual_mae": _f4(dual_mae),
                "single_mae": _f4(single_mae) if single_mae is not None else None,
                "gap_pp": round(gap_pp, 4), "target_mae": target,
                "n_test": n_test, "n_matched_days": len(samples),
                "note": ("首测达标（双段保留）" if verdict == "pass"
                         else "首测不达标：回退单段（暂态，预注册复评日）"),
            })
            if verdict == "first_test_failed":
                cfg["enabled"] = False
                cfg["decided_at"] = _now_iso()
                cfg["reason"] = ("首测不达标：双段 MAE %.4f > 目标 %.4f（单段 MAE %s）；"
                                 "回退单段，复评日 %s"
                                 % (dual_mae, target,
                                    ("%.4f" % single_mae) if single_mae is not None else "?",
                                    next_trading_days(today, QDII_REVIEW_STEP_DAYS)))
                cfg["next_review_date"] = next_trading_days(today, QDII_REVIEW_STEP_DAYS)
            else:
                cfg["enabled"] = True
                cfg["decided_at"] = _now_iso()
                cfg["reason"] = "首测达标：双段保留（目标 MAE %.4f）" % target
                cfg["next_review_date"] = next_trading_days(today, QDII_REVIEW_STEP_DAYS)
            cfg["last_review"] = {"code": code, "verdict": verdict,
                                  "dual_mae": _f4(dual_mae),
                                  "single_mae": _f4(single_mae) if single_mae is not None else None,
                                  "gap_pp": round(gap_pp, 4), "target_mae": target,
                                  "n_matched_days": n_test, "at": _now_iso()}
            save_qdii_config(cfg)
        decisions.append({"code": code, "verdict": verdict, "n_test": n_test,
                          "dual_mae": _f4(dual_mae)})
    # 对齐误杀统计：40 日窗内 ≥5 次 → 人工复核参照源是否误杀（R-5）
    cutoff = (datetime.now() - timedelta(days=ACCURACY_WINDOW_DAYS)).strftime("%Y-%m-%d")
    conflicts = [r for r in _read_qdii_review()
                 if r.get("kind") == "alignment_conflict"
                 and (r.get("at") or "")[:10] >= cutoff]
    if len(conflicts) >= 5:
        reviews = [r for r in _read_qdii_review()
                   if r.get("kind") == "alignment_conflict_review"
                   and (r.get("at") or "")[:10] >= cutoff]
        if not reviews:
            append_qdii_review({
                "kind": "alignment_conflict_review",
                "count": len(conflicts),
                "note": "40 日窗内对齐冲突 ≥5 次：人工复核参照源是否误杀（参照可得却被对齐拒绝）",
            })
    return {"decisions": decisions, "conflicts_40d": len(conflicts),
            "config": {"enabled": cfg.get("enabled"),
                       "next_review_date": cfg.get("next_review_date")}}




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


def _weighted_holdings(holdings, top_n=None):
    """前 N 大重仓股加权：weighted_change = Σ(w_i × chg_i) / Σ w_i。

    口径来源：本任务（2026-09-12）「主动基金估值锚点 = 前十大重仓股加权」；
    R2-02 升级为 top_n=20 并增 detail 字段（09-api-contract-r2 §3.3）。
    - w_i = 占净值比例(%)，chg_i = 个股当日实时涨跌（小数，来自腾讯/新浪实时）；
    - 仅 weight 与 day_change 均非 null 的标的参与；缺一即剔除，不编造补值；
    - 返回 (weighted_change 或 None, detail dict)；detail.top10 记录明细与逐只贡献。
    """
    tot_w = 0.0
    acc = 0.0
    expected_w = 0.0
    rows = []
    included_markets = set()
    excluded_count = 0
    for item in holdings or []:
        w = item.get("weight")
        if w is None:
            w = item.get("weight_pct")
        ch = item.get("day_change")
        try:
            wv = float(w) if w is not None else None
        except (TypeError, ValueError):
            wv = None
        if wv is not None:
            expected_w += wv
        used = wv is not None and ch is not None
        contrib = None
        if used:
            chv = float(ch)
            tot_w += wv
            acc += wv * chv
            contrib = _f4(wv * chv)
            included_markets.add(estimator.market_of_code(item.get("stock_code")))
        else:
            excluded_count += 1
        rows.append({
            "rank": item.get("rank"),
            "stock_code": item.get("stock_code"),
            "stock_name": item.get("stock_name"),
            "weight_pct": _f4(wv),
            "day_change": _f4(ch) if ch is not None else None,
            "contribution": contrib,
            "used": bool(used),
        })
    detail = {
        "method": "eastmoney_f10_top10_weighted",
        "formula": "weighted_change = sum(w_i * chg_i) / sum(w_i)",
        "top_n": int(top_n) if top_n else len(rows),
        "report_date": None,
        "top10": rows,
        "covered_weight_pct": _f4(tot_w),
        "total_weight_pct": _f4(expected_w),
        "weighted_change": _f4(acc / tot_w) if tot_w > 0 else None,
        # R2-02：included_markets ⊆ ["A","HK","US"]；excluded_count 如实计（不编造）
        "included_markets": sorted(included_markets),
        "excluded_count": excluded_count,
    }
    if tot_w <= 0:
        return None, detail
    return acc / tot_w, detail


def value_fund(h, as_of_date, allow_network=True, run_id=None, session=None):
    """执行五档降级链，返回完整 Valuation 记录（不落盘）。

    取数口径（本轮修复，来源：本任务「主动基金改重仓加权估值」）：
    - 基金类型 `fund_type`（estimator.classify_fund_type）：active / index_link / qdii / other。
    - 档1 official：通用——非盘中时段最近一期官方净值即当期估值；仅 A 股盘中且官方净值
      日期未到当日时才让位。**主动基金**例外——仅「当日官方已发布」（nav_date==as_of）才
      official，否则让位重仓加权（不再以 ETF proxy 为主动基金锚点，也不作盘中估算）。
    - 档2 intraday：仅**非主动**基金且 A 股盘中产出；周末/收盘后一律不产出。
    - 档3 holdings：**主动基金主估值 = 前十大重仓股加权**（Σ(w_i×chg_i)/Σw_i），优先于
      proxy；前十不可得才回退 proxy。非主动基金不做重仓加权（直接 proxy/intraday）。
    - 档4 proxy：代理 ETF 实时/日线（主动基金兜底 + 指数联接/QDII 主口径）。
    - 档5 unknown：全链无数据，change_rate=null。
    - **预测锚点 ≠ 估值锚点**：估值用重仓加权；预测（方向信号）仍用可交易代理 ETF 的
      价格序列（基金自身净值无日内历史），此点不变（见 14-api-impl-report）。
    """
    code = h.get("code")
    name = h.get("name", "")
    fund_type = h.get("fund_type") or estimator.classify_fund_type(name)
    trace = []
    session = session or trade_session()
    intraday_allowed = (session == "trading")
    nav_date_last, nav_last, nav_prev = holdings_mod.latest_nav(h)

    # 官方净值统一入口：FundValuationLast（NAV/PDATE）→ lsjz（DWJZ/FSRQ/JZZZL）→ pingzhongdata
    try:
        off = estimator.get_official_nav(code, allow_network=allow_network)
    except Exception:  # noqa: BLE001 - 取数适配层失败不拖垮估值
        off = None

    if off and off.get("nav") is not None:
        official_nav = _f4(off["nav"])
        official_date = off.get("nav_date")
        official_change = _f4(off.get("change_rate"))
        if official_change is None and official_nav is not None and off.get("prev_nav"):
            official_change = _f4(official_nav / float(off["prev_nav"]) - 1.0)
        est = {
            "estimate_nav": _f4(off.get("gsz")),
            "estimate_change_rate": _f4(off.get("estimate_change_rate")),
            "estimate_time": off.get("gztime"),
            "official_nav_date": official_date,
        }
    else:
        # 回退源文件 nav_history（可能滞后；此时 official 仅在净值日==as_of 时命中）
        official_nav = _f4(nav_last)
        official_date = nav_date_last
        if official_nav is not None and nav_prev:
            official_change = _f4(official_nav / nav_prev - 1.0)
        else:
            official_change = None
        est = None

    # 估算基准净值：优先实时官方净值（FundValuationLast/lsjz），回退源文件最新净值。
    base_nav = official_nav if official_nav is not None else nav_last
    base_date = official_date if official_nav is not None else nav_date_last

    result = None

    # 档1 official：最新一期官方净值。通用规则——非盘中时段不再要求 official_date==as_of_date，
    # 否则周末/收盘后会跳过官方净值而误落 intraday。
    # 主动基金规则——仅「当日官方已发布」才 official；否则让位重仓加权（本轮需求：
    # 主动基金不以 ETF proxy / 盘中估算为锚，改用前十大重仓股加权）。
    if fund_type == "active":
        hit1 = official_nav is not None and official_date == as_of_date
    else:
        hit1 = official_nav is not None and ((not intraday_allowed) or official_date == as_of_date)
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

    # 档2 intraday（仅非主动基金且 A 股盘中；非盘中/主动基金一律不产出）
    if result is None:
        if fund_type != "active" and intraday_allowed:
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
                    "nav_date": official_date,
                }
        else:
            trace.append(_make_trace_step("intraday", False, False, "not_published"))

    # 档3 holdings（仅主动基金：前十大重仓股加权，优先于 proxy）
    if result is None:
        if fund_type == "active":
            rep = None
            if allow_network:
                try:
                    rep = estimator.eastmoney_top_holdings(code, allow_network=True)
                except Exception:  # noqa: BLE001 - 取数失败按不可得处理
                    rep = None
            if rep and rep.get("holdings"):
                ch, detail = _weighted_holdings(rep["holdings"], top_n=rep.get("top_n"))
                hit3 = ch is not None
                detail["report_date"] = rep.get("report_date")
                detail["base_nav"] = _f4(base_nav)
                detail["base_nav_date"] = base_date
                step = _make_trace_step("holdings", True, hit3,
                                        "hit" if hit3 else "no_report")
                step["detail"] = detail
                trace.append(step)
                if hit3:
                    result = {
                        "valuation_mode": "holdings",
                        "change_rate": _f4(ch),
                        "estimated_nav": _f4(base_nav * (1 + ch)) if base_nav else None,
                        "source_label": "前十大重仓加权",
                        "nav_date": base_date,
                    }
                    detail["estimated_nav"] = result["estimated_nav"]
            else:
                trace.append(_make_trace_step("holdings", True, False, "no_report"))
        else:
            # 指数联接/QDII/其他：不做重仓加权，直接走 proxy（保持既有口径）
            trace.append(_make_trace_step("holdings", False, False, "no_report"))

    # 档4 proxy（R2-03：QDII 跨市场双段优先；R2-17：腾讯失败 → 新浪兜底）
    qdii_correction = None
    if result is None:
        proxy = h.get("proxy_code")
        hit4 = False
        reason4 = "no_mapping"
        ch = None
        source_label4 = None
        if proxy:
            if fund_type == "qdii" and market_of(h):
                ch, corr = qdii_estimate(h, as_of_date, session=session,
                                         allow_network=allow_network)
                if ch is not None:
                    qdii_correction = corr
                    hit4 = True
                    reason4 = "hit"
                    source_label4 = ("QDII 双段（%s + 隔夜参照）"
                                     if (corr or {}).get("applied")
                                     else "QDII 单段（%s）" % ((corr or {}).get("fallback_reason") or ""))
            if not hit4 and allow_network:
                q = estimator.tencent_rt_quote(proxy)
                if q is None and estimator.market_of_code(proxy) == "A":
                    # R2-17：新浪限定兜底（仅 A 股；5s 超时/重试 0；不阻塞估值链）
                    q = estimator.sina_rt_quote(proxy)
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
                "source_label": source_label4 or ("代理ETF %s 实时" % proxy),
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
        "fund_type": fund_type,
        "fund_type_label": estimator.FUND_TYPE_LABEL.get(fund_type, "其他"),
        "valuation_mode": result["valuation_mode"],
        "change_rate": result["change_rate"],
        "estimated_nav": result["estimated_nav"],
        "source_label": result["source_label"],
        # R2-03：QDII 双段校正记录（非 QDII 或未走双段为 null；contract §3.4）
        "qdii_correction": qdii_correction,
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
                max_age_sec=REUSE_AGE_SEC, force=False, session=None):
    """对全部持仓执行五档链并追加审计记录；返回本日最新记录列表。

    T-01 预算实现（08-backend-arch-r2 §3.5）：t0 起算超过 TOTAL_BUDGET_SEC 且非 force
    → 停止继续估值；已入账记录保留；跳过者回退旧缓存（若有当日缓存），无缓存者不产记录
    （读取层 conf_reason=budget_exceeded）；snapshot 附 budget:{exceeded,processed,skipped}。
    """
    _ensure_dirs()
    as_of_date = as_of_date or _today()
    run_id = run_id or ("run_" + uuid.uuid4().hex[:8])
    session = session or trade_session()
    records = []
    skipped = []
    processed = 0
    t0 = time.time()
    for h in hold_list:
        code = h["code"]
        if (not force) and (time.time() - t0 > TOTAL_BUDGET_SEC):
            skipped.append(code)
            existing = latest_for(code, as_of_date)
            if existing is not None:
                records.append(existing)
            continue
        existing = latest_for(code, as_of_date)
        if (not force) and existing is not None and existing.get("valuation_mode") != "unknown" \
                and _mode_reusable(existing.get("valuation_mode"), session):
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
        rec = value_fund(h, as_of_date, allow_network=allow_network, run_id=run_id,
                         session=session)
        prior = read_history(code=code, date=as_of_date)
        rec["is_first_of_day"] = len(prior) == 0
        rec["history_available"] = history_available(code)
        append_history(rec)
        records.append(rec)
        processed += 1
    budget = {"exceeded": bool(skipped), "processed": processed,
              "skipped": skipped, "budget_sec": TOTAL_BUDGET_SEC}
    if skipped:
        sys.stderr.write("[valuation] 预算超时：跳过 %d 只（conf_reason=budget_exceeded）\n"
                         % len(skipped))
    _write_snapshot(records, as_of_date, budget=budget)
    # R2-05 日留档双触发（幂等；盘中不写由 archive_daily 自检）
    if session != "trading":
        try:
            archive_daily(as_of_date)
        except Exception:  # noqa: BLE001 - 留档失败不阻塞估值链
            pass
    return records


def _write_snapshot(records, as_of_date, budget=None):
    obj = {"as_of": as_of_date, "written_at": _now_iso(), "records": records}
    if budget is not None:
        obj["budget"] = budget
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
    ft = estimator.classify_fund_type(name)
    return _finalize({
        "date": _today(), "code": code, "name": name,
        "fund_type": ft, "fund_type_label": estimator.FUND_TYPE_LABEL.get(ft, "其他"),
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
            "confidence_color_class", "trace_text", "as_of",
            "fund_type", "fund_type_label",
            # R2-01/R2-03（contract §3.2）：unknown 徽章原因 + QDII 双段校正记录
            "conf_reason", "qdii_correction"]
    out = {k: rec.get(k) for k in keys}
    if out.get("as_of") is None:
        out["as_of"] = rec.get("date")
    # conf_reason：仅 confidence=unknown 时非 null；读取层按序命中即停（R-4）
    if out.get("conf_reason") is None and out.get("confidence") == "unknown":
        out["conf_reason"] = conf_reason_of(rec)
    return out


def precision_summary(hold_list, as_of_date=None):
    """GET /valuations/precision：置信度分布 + 主指标拆分 + 双时点（v9.1 D-1/D-2）。

    - vsum 主指标 = `estimate_quality.weighted_mae_rate`（估算档 intraday/holdings/proxy）；
    - 官方档单列 chip `official_summary`（既成事实，不参与主指标）；
    - 既有 `weighted_mae_rate` / `groups`（全档）保留为「全档参考」（M3 语义登记）。
    来源：09-api-contract-r2 §4.5 + §9.1（ADR-0014）。
    """
    as_of_date = as_of_date or _today()
    groups = {}
    modes = {}
    weighted = 0.0
    weight_sum = 0.0
    total_value = 0.0
    est_groups = {}
    est_weighted = 0.0
    est_weight_sum = 0.0
    est_count = 0
    est_value = 0.0
    off_count = 0
    off_value = 0.0
    off_weighted = 0.0
    off_weight_sum = 0.0
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
        if mode in ("intraday", "holdings", "proxy"):
            eg = est_groups.setdefault(conf, {"confidence": conf, "count": 0,
                                              "market_value": 0.0})
            eg["count"] += 1
            est_count += 1
            if mv is not None:
                eg["market_value"] += mv
                est_value += mv
            if mae is not None and mv is not None:
                est_weighted += mae * mv
                est_weight_sum += mv
        elif mode == "official":
            off_count += 1
            if mv is not None:
                off_value += mv
            if mae is not None and mv is not None:
                off_weighted += mae * mv
                off_weight_sum += mv

    out_groups = _groups_out(groups, total_value)
    out_modes = []
    for mode in ("official", "intraday", "holdings", "proxy", "unknown"):
        if mode in modes:
            m = modes[mode]
            m["market_value"] = _f2(m["market_value"])
            m["weight_ratio"] = _f4(m["market_value"] / total_value) if total_value > 0 else None
            out_modes.append(m)
    filled = window_filled_days(hold_list)
    phase = window_phase(filled)
    if filled >= ACCURACY_WINDOW_DAYS:
        label = "已满 %d 日" % ACCURACY_WINDOW_DAYS
    else:
        label = "累计 %d/%d 日" % (filled, ACCURACY_WINDOW_DAYS)
    estimate_quality = {
        "groups": _groups_out(est_groups, total_value),
        "weighted_mae_rate": (_f4(est_weighted / est_weight_sum)
                              if est_weight_sum > 0 else None),
        "count": est_count,
        "market_value": _f2(est_value),
        "weight_ratio": _f4(est_value / total_value) if total_value > 0 else None,
        "industry_baseline_mae_rate": INDUSTRY_BASELINE_MAE,
        "window_days": ACCURACY_WINDOW_DAYS,
        "window_filled_days": filled,
        "note": ("估算档（intraday/holdings/proxy）质量为主指标；官方档为既成事实单列，"
                 "不参与本指标（ADR-0014 / v9.1 D-1）。"),
    }
    official_summary = {
        "count": off_count,
        "market_value": _f2(off_value),
        "weight_ratio": _f4(off_value / total_value) if total_value > 0 else None,
        "weighted_mae_rate": (_f4(off_weighted / off_weight_sum)
                              if off_weight_sum > 0 else None),
        "note": ("官方档 = 已发布净值的既成事实（未发布时段以最近一期净值为锚的记录"
                 "照常参与全档参考统计）；不参与主指标换算。"),
    }
    return {
        "groups": out_groups,
        # 全档参考（M3 语义登记：不得再作主指标展示）
        "weighted_mae_rate": _f4(weighted / weight_sum) if weight_sum > 0 else None,
        "industry_baseline_mae_rate": INDUSTRY_BASELINE_MAE,
        "window_days": ACCURACY_WINDOW_DAYS,
        "window_filled_days": filled,
        "window_status_label": label,
        "window_phase": phase,
        "estimate_quality": estimate_quality,
        "official_summary": official_summary,
        "mode_distribution": out_modes,
    }


def _groups_out(groups, total_value):
    out = []
    for conf in ("high", "mid", "low", "unknown"):
        if conf in groups:
            g = groups[conf]
            g["label"] = CONF_GROUP_LABEL.get(conf, "无")
            g["market_value"] = _f2(g["market_value"])
            g["weight_ratio"] = _f4(g["market_value"] / total_value) if total_value > 0 else None
            out.append(g)
    return out


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
    """契约 §5.3 Nav：官方已公布净值，独立于估值。

    优先最新官方净值缓存（FundValuationLast / lsjz），缺失回退源文件 nav_history。
    来源：本任务「净值快照必须反映最近一期官方净值」，避免源文件滞后（08-25）污染 nav.*。
    """
    as_of_date = as_of_date or _today()
    code = h.get("code")
    official_nav = None
    official_date = None
    change = None
    prev = None
    try:
        off = estimator.get_official_nav(code, allow_network=False)
    except Exception:  # noqa: BLE001
        off = None
    if off and off.get("nav") is not None:
        official_nav = _f4(off.get("nav"))
        official_date = off.get("nav_date")
        change = _f4(off.get("change_rate"))
        prev = off.get("prev_nav")
    if official_nav is None:
        d, nav_last, prev = holdings_mod.latest_nav(h)
        official_nav = _f4(nav_last)
        official_date = d
        if nav_last is not None and prev:
            change = _f4(nav_last / prev - 1.0)
    return {
        "official_nav": official_nav,
        "official_nav_date": official_date,
        "official_change_rate": change,
        "previous_nav": _f4(prev),
        "is_today_official": bool(official_date == as_of_date),
    }
