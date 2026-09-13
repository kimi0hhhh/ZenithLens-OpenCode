# -*- coding: utf-8 -*-
"""审计台账：INSERT-ONLY（signals.jsonl + 独立 backfill.jsonl）。

- 契约 §5.9 / §5.10 / §5.28 / §5.29 / §5.34、08 §6
- 唯一性 (date, code)；写后不改；回填只写 t*_real；读取时左连接合并
- created_at 与 written_at 同刻恒等（v3 追加，二者都保留）
"""

import io
import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta
from decimal import Decimal

import engine
import errors
import estimator
import holdings as holdings_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_DIR = os.path.join(ROOT, "ledger")
SIGNALS_PATH = os.path.join(LEDGER_DIR, "shadow_signals.jsonl")
BACKFILL_PATH = os.path.join(LEDGER_DIR, "backfill.jsonl")
ARCHIVE_DIR = os.path.join(LEDGER_DIR, "archive")
ARCHIVE_SIGNALS_PATH = os.path.join(ARCHIVE_DIR, "shadow_signals_archive.jsonl")
ARCHIVE_MANIFEST_PATH = os.path.join(ARCHIVE_DIR, "_manifest.jsonl")

_LOCK = threading.Lock()
TARGET_DAYS = 60
DEVIATION_THRESHOLD = 0.02
# v4 A-10：首次口径永久 + 全量归档（单值枚举，冻结）
RETENTION_POLICY = "first_of_day_immutable_full_archive"
# 影子盘滚动窗口（唯一常量源；2026-09-13 用户指令「直接补满 60 天，来一天换一天」）：
# 窗口 = 最近 60 个交易日；启动即回填满 60 日，此后每日追加新一天并裁剪最旧一天。
# 契约：09-api-contract-r2 v9.5 §13（`ShadowProgress.window_days` / `SignalState.rolling_window_days` = 60）；
# 纪要与计算量评估：10-arch-review-r2 v7 §13。
SHADOW_WINDOW_DAYS = 60
# 训练/预测走前净化间隔（契约 §6.6 purge_gap=H+2）；H=1 → 训练标签不得晚于 t-2。
PURGE_GAP = 2
# R2-14：旧硬编码基线已退役（ADR-0013）；基线一律实测 max(恒涨率,恒跌率)，禁止再引入常量。

FIELD_LIST = ["date", "code", "gate", "p_up", "ddsm_state", "veto_crowd",
              "veto_klow2", "signal", "opened", "t1_real", "t3_real", "t15_real",
              "t1_real_method", "backfill_proxy_code", "created_at"]

INSERT_ONLY_NOTE = ("收盘时点固定写盘：同一 (date, code) 仅允许一条，写入即冻结；"
                    "事后不可编辑/删除；到期实际涨跌由独立 backfill.jsonl 回填，"
                    "只写 t1_real/t3_real/t15_real，不改原行。")

BACKFILL_METHODS = ("proxy_bar",)
BACKFILL_METHOD_NOTE = ("命中判定=代理 ETF 日线涨跌方向（t*_real = proxy_close(T+H)/"
                        "proxy_close(T) − 1，与预测锚点同源，ADR-0008）；"
                        "净值口径见估值误差通道。")


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


def write_backfill(entries, default_method="proxy_bar"):
    """人工/任务回填写入（独立 backfill.jsonl；INSERT-ONLY，只写 t*_real）。

    - B7：entries[] 允许可选 `method`（enum backfill_method，缺省 `proxy_bar`）；
    - R-1：允许可选 `proxy_code`（缺省取该基金当前映射）并随行落盘（复算锚）；
    - 无对应 signal → 拒绝写入（E_VALIDATION 沿用）。
    """
    if not isinstance(entries, list):
        raise errors.ApiError(errors.E_VALIDATION, "entries 必须是数组", {"entries": "not list"})
    signals = {(e.get("date"), e.get("code")) for e in read_signals_raw()}
    proxies = None
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
            method = it.get("method") or default_method
            if method not in BACKFILL_METHODS:
                raise errors.ApiError(errors.E_VALIDATION, "未知回填口径",
                                      {"method": "must be one of %s" % (list(BACKFILL_METHODS),)})
            proxy_code = it.get("proxy_code")
            if proxy_code is not None and not re.match(r"^\d{6}$", str(proxy_code)):
                raise errors.ApiError(errors.E_VALIDATION, "proxy_code 必须为 6 位数字或省略",
                                      {"proxy_code": str(proxy_code)})
            if proxy_code is None:
                if proxies is None:
                    proxies = current_proxy_map()
                proxy_code = proxies.get(key[1])
            rec = {"date": key[0], "code": key[1], "backfilled_at": _now_iso(),
                   "method": method}
            if proxy_code:
                rec["proxy_code"] = str(proxy_code)
            for f in ("t1_real", "t3_real", "t15_real"):
                if it.get(f) is not None:
                    rec[f] = float(it[f])
            _append_jsonl(BACKFILL_PATH, rec)
            backfilled += 1
    return {"backfilled_count": backfilled, "skipped": skipped}


def current_proxy_map():
    """{code: 当前代理 ETF 代码}：持仓映射优先，静态代理表兜底（R-1 复算锚）。"""
    out = {}
    try:
        import proxy_map
        for code, p in proxy_map.PROXY_MAP.items():
            out[str(code)] = p[0]
    except Exception:  # noqa: BLE001
        pass
    try:
        for h in holdings_mod.load_holdings().get("holdings", []):
            if h.get("code") and h.get("proxy_code"):
                out[str(h["code"])] = str(h["proxy_code"])
    except Exception:  # noqa: BLE001
        pass
    return out


def _merged_raw():
    """signals LEFT JOIN backfill（同 (date,code) 取最后一条回填值，含方法/复算锚）。"""
    back = {}
    for b in read_backfill_raw():
        back[(b.get("date"), b.get("code"))] = b
    out = []
    for s in read_signals_raw():
        r = dict(s)
        out.append(_apply_backfill(r, back.get((s.get("date"), s.get("code")))))
    return out


def _name_map():
    m = {}
    try:
        for h in holdings_mod.load_holdings().get("holdings", []):
            m[h["code"]] = h.get("name", "")
    except Exception:
        pass
    return m


# ---------------- 事件链可复现性 / 读时重算（BLOCK-A3 · 08.7） ----------------

_CHAIN_BARS_CACHE = {}


def _bars_index_for_chain(code, date, bars_cache=None, proxies=None):
    """定位 (proxy, bars, t)：代理离线日线中含该 date 时返回索引，否则 (None, [], None)。

    只读 `get_bars(allow_network=False)`（离线缓存；无写、无网络）——复现性判定的前提。
    """
    code = str(code or "")
    if not code or not date:
        return None, [], None
    pm = proxies if proxies is not None else current_proxy_map()
    proxy = pm.get(code)
    if not proxy:
        return None, [], None
    cache = bars_cache if bars_cache is not None else _CHAIN_BARS_CACHE
    bars = cache.get(proxy)
    if bars is None:
        try:
            bars, _m = estimator.get_bars(proxy, allow_network=False)
        except Exception:  # noqa: BLE001 - 取数失败按不可复现
            bars = []
        cache[proxy] = bars
    return proxy, bars, _date_index(bars, date)


def _chain_recomputable(r, bars_cache=None, proxies=None):
    """`chain_available` 判定 = 可重算性（轻量、零训练）：

    代理离线日线存在该 date，且训练段长度足以产出 DDSM 样本
    （`len(train) >= MIN_N*2 + FEATURE_WARMUP + 1`，与 `train_model` 门控同源）。
    """
    _proxy, bars, t = _bars_index_for_chain(r.get("code"), r.get("date"),
                                            bars_cache, proxies)
    if not bars or t is None:
        return False
    train_len = len(bars[:max(0, t - 1)])
    return train_len >= engine.MIN_N * 2 + engine.FEATURE_WARMUP + 1


def _recompute_chain(e):
    """与写入同源口径重算六步链（读时不改台账；INSERT-ONLY 零改动）。

    口径：定位 bar t → `bars[:t-1]` 训练（H=1）→ `engine.predict_at` →
    复用 `fund_predict.build_chain` 构造步骤（避免双份实现）。
    不可复现 → (None, None)（不编造步骤数值）。
    """
    _proxy, bars, t = _bars_index_for_chain(e.get("code"), e.get("date"))
    if not bars or t is None or t < 1:
        return None, None
    train = bars[:t - 1]
    if len(train) < engine.MIN_N * 2 + engine.FEATURE_WARMUP + 1:
        return None, None
    model = engine.train_model(train, H=1)
    if model is None:
        return None, None
    try:
        r = engine.predict_at(model, bars, t, 1)
    except Exception:  # noqa: BLE001 - 单点异常按不可复现
        return None, None
    import fund_predict  # 复用六步构造（同源口径）
    row = {"signal": r.get("signal"), "reason": r.get("reason")}
    chain = fund_predict.build_chain(row, r, bars)
    if not isinstance(chain, list) or len(chain) != 6:
        return None, None
    return chain, r.get("metrics")


def _decorate(r, names, seq, bars_cache=None, proxies=None):
    r = dict(r)
    r.setdefault("t1_real", None)
    r.setdefault("t3_real", None)
    r.setdefault("t15_real", None)
    # R2-12/R-1：回填口径与复算锚（未回填 null）
    r.setdefault("t1_real_method", None)
    r.setdefault("backfill_proxy_code", None)
    r["name"] = names.get(r.get("code"), r.get("name", ""))
    for k in ("ddsm_state", "veto_crowd", "veto_klow2", "signal", "gate", "p_up",
              "market_value", "cost_est"):
        r.setdefault(k, None)
    r["is_backfilled"] = all(r.get(f) is not None for f in ("t1_real", "t3_real", "t15_real"))
    r["created_at"] = r.get("created_at") or r.get("written_at")
    r["written_at"] = r.get("written_at") or r.get("created_at")
    # opened = T1 是否开口（涨）；旧行无该字段时按 signal 派生，不编造
    r["opened"] = bool(r.get("opened", r.get("signal") == "up"))
    r["record_seq"] = seq
    r["source_file"] = "shadow_signals.jsonl"
    # BLOCK-A3：`chain_available` = **可重算性**判定（有离线 bars 且含该 date、训练段足；
    # 轻量零训练）；写入侧有 `_chain` 时恒 true。字段名/类型不变。
    r["chain_available"] = bool(r.get("_chain")) or _chain_recomputable(r, bars_cache, proxies)
    return r


def read_ledger(limit=60, offset=0, code=None, frm=None, to=None):
    rows = _merged_raw()
    names = _name_map()
    bars_cache = {}
    proxies = current_proxy_map()
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
    return [_decorate(r, names, r.get("_seq"), bars_cache, proxies) for r in page], total


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


# ---------------- 影子盘回填引擎（真实引擎计算，禁止示例数字） ----------------

def _proxy_assets():
    """监控中有代理映射的资产（A 档 + 少数 B 档；无代理的 C/D 不产信号）。"""
    try:
        hs = holdings_mod.ensure_holdings().get("holdings", [])
    except Exception:  # noqa: BLE001 - 持仓读取失败即无资产可回填
        return []
    return [h for h in hs
            if h.get("tier") in ("A", "B") and h.get("proxy_code") and h.get("code")]


def _load_proxy_bars(allow_network=True):
    """返回 [(holding, bars)]；仅含有行情（缓存或实时）的代理资产。"""
    out = []
    for h in _proxy_assets():
        try:
            bars, _meta = estimator.get_bars(h["proxy_code"], allow_network=allow_network)
        except Exception:  # noqa: BLE001 - 单资产取数失败不阻塞其他资产
            bars = []
        if bars:
            out.append((h, bars))
    return out


def _date_index(bars, date):
    for i in range(len(bars) - 1, -1, -1):
        if bars[i].get("date") == date:
            return i
    return None


def _predict_historical(bars, t):
    """对 bar[t] 做走前（purged walk-forward）单点预测，返回台账字段子集。

    口径：模型只用 bar[:t-1] 训练（H=1，purge_gap=H+2=3，标签最晚 t-2 且不越界到 t+1），
    再用同一真实引擎 `engine.predict_at` 在 t 点出 gate/cell/p_up/双否决/signal。
    数据不足（模型 None）时如实给 gray + null，不编造 P。
    """
    train_bars = bars[:max(0, t - 1)] if t > 1 else []
    model = engine.train_model(train_bars, H=1) if train_bars else None
    if model is None:
        gate = engine.gate_of(bars, t) if t >= 1 else None
        return {"gate": gate or "none", "p_up": None, "ddsm_state": None,
                "veto_crowd": False, "veto_klow2": False, "signal": "gray"}
    r = engine.predict_at(model, bars, t, 1)
    veto = r.get("veto") or {}
    return {
        "gate": r.get("gate") or "none",
        "p_up": r.get("p_up"),
        "ddsm_state": r.get("ddsm_state"),
        "veto_crowd": bool(veto.get("crowd_veto")),
        "veto_klow2": bool(veto.get("klow2_veto")),
        "signal": r.get("signal", "gray"),
    }


def compute_shadow_window(days=SHADOW_WINDOW_DAYS, allow_network=True,
                          only_dates=None, assets=None):
    """计算最近 `days` 个交易日的影子台账记录。

    交易日历 = 监控资产代理 K 线日期的并集（真实盘中日历，不用工作日近似）。
    返回 (window_dates, records)；records 为 [(date, code) 唯一] 的 INSERT-ONLY 字典。

    v9.5 §13.4 增量模式（实现优化，口径不变）：`only_dates` 限定只计算指定日期
    （每日滚动通常仅新增 1 日 × 资产数）；`assets` 允许复用已加载代理行情。
    """
    if assets is None:
        assets = _load_proxy_bars(allow_network=allow_network)
    if not assets:
        return [], []
    if only_dates is not None:
        window = sorted({d for d in only_dates if d})
    else:
        all_dates = sorted({b["date"] for _h, bars in assets for b in bars
                            if b.get("date")})
        window = all_dates[-days:] if len(all_dates) > days else all_dates
    if not window:
        return [], []
    now = _now_iso()
    records = []
    for h, bars in assets:
        for d in window:
            t = _date_index(bars, d)
            if t is None:
                continue
            pred = _predict_historical(bars, t)
            records.append({
                "date": d, "code": h["code"], "gate": pred["gate"],
                "p_up": (None if pred["p_up"] is None else round(float(pred["p_up"]), 4)),
                "ddsm_state": pred["ddsm_state"],
                "veto_crowd": pred["veto_crowd"], "veto_klow2": pred["veto_klow2"],
                "signal": pred["signal"], "opened": pred["signal"] == "up",
                "created_at": now,
            })
    return window, records


def _write_all_signals(records):
    """整文件重写（仅用于滚动裁剪；记录内容保持冻结不变）。"""
    _ensure_dir()
    tmp = SIGNALS_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, SIGNALS_PATH)


def _archive_records(records, reason="rolling_window_trim", extra=None):
    """记录全量归档（保留策略：first_of_day_immutable_full_archive）。

    N-4：manifest 增差异摘要（新增/移除条数、最早/最晚日期）由 extra 传入。
    """
    if not records:
        return
    if not os.path.isdir(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    with io.open(ARCHIVE_SIGNALS_PATH, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    dates = sorted({r.get("date") for r in records if r.get("date")})
    manifest = {
        "created_at": _now_iso(), "reason": reason,
        "count": len(records), "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "window_days": SHADOW_WINDOW_DAYS,
    }
    if extra:
        manifest.update(extra)
    with io.open(ARCHIVE_MANIFEST_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(manifest, ensure_ascii=False) + "\n")


def _archive_rows_readable():
    """归档记录 + 可读标志（缺失/不可读 → ( [], False )，不伪造天数）。"""
    if not os.path.isfile(ARCHIVE_SIGNALS_PATH):
        return [], False
    rows = _read_jsonl(ARCHIVE_SIGNALS_PATH)
    return rows, True


def _apply_backfill(r, b):
    """把 backfill 行的 t*_real / method / proxy_code 左连接到信号行（B7/R-1）。"""
    if not b:
        return r
    for f in ("t1_real", "t3_real", "t15_real"):
        if f in b:
            r[f] = b[f]
    if b.get("method"):
        r["t1_real_method"] = b.get("method")
    if b.get("proxy_code"):
        r["backfill_proxy_code"] = str(b.get("proxy_code"))
    return r


def _merged_all():
    """主文件 ∪ 归档（(date,code) 去重，主文件优先）+ 回填左连接。

    返回 (rows, archive_merged)；归档缺失不可读 → ([主文件], False)，口径降级（R2-13）。
    """
    main = read_signals_raw()
    arch, readable = _archive_rows_readable()
    merged = {}
    for r in arch:
        merged[(r.get("date"), r.get("code"))] = r
    for r in main:
        merged[(r.get("date"), r.get("code"))] = r
    back = {}
    for b in read_backfill_raw():
        back[(b.get("date"), b.get("code"))] = b
    rows = []
    for r in merged.values():
        r = dict(r)
        _apply_backfill(r, back.get((r.get("date"), r.get("code"))))
        rows.append(r)
    return rows, bool(readable and arch)


def merged_all_rows():
    """对外只读入口：主文件 ∪ 归档合并集（供 /review/scores 实盘口径使用）。"""
    return _merged_all()


def _monitored_calendar():
    """监控资产代理 K 线日期并集（只读缓存，不联网）。"""
    dates = set()
    for h in _proxy_assets():
        try:
            bars, _m = estimator.get_bars(h["proxy_code"], allow_network=False)
        except Exception:  # noqa: BLE001
            bars = []
        for b in bars:
            if b.get("date"):
                dates.add(b["date"])
    return sorted(dates)


def measured_baseline(rows):
    """实测基线 = max(恒涨率, 恒跌率)（ADR-0013 / R2-14 / 契约 §6.3）。

    N = 全部 `t1_real` 非 null 的行；N=0 → null（不填旧常量）。
    """
    vals = [r.get("t1_real") for r in rows if r.get("t1_real") is not None]
    n = len(vals)
    if n == 0:
        return None
    up = sum(1 for v in vals if v > 0) / float(n)
    down = sum(1 for v in vals if v < 0) / float(n)
    return max(up, down)


def backfill_due(today=None, allow_network=True):
    """到期 t*_real 自动回填（R2-12 / ADR-0008；R-1 复算锚）。

    - 口径 = 代理日线：`t{H}_real = proxy_close(T+H)/proxy_close(T) − 1`；
    - 只写缺失值（已存在的 t*_real 不再写，避免重复行）；标的日线缺失 → 保持待补；
    - 独立 backfill.jsonl、INSERT-ONLY；行记 `method=proxy_bar` + `proxy_code`。
    """
    merged = _merged_raw()
    proxies = current_proxy_map()
    entries = []
    bar_missing = 0
    for e in merged:
        code = e.get("code")
        d = e.get("date")
        missing = [H for H in (1, 3, 15) if e.get("t%d_real" % H) is None]
        if not missing or not code or not d:
            continue
        proxy = proxies.get(str(code)) or e.get("backfill_proxy_code")
        if not proxy:
            continue  # 无代理映射：无法回填（不编造）
        try:
            bars, _m = estimator.get_bars(proxy, allow_network=allow_network)
        except Exception:  # noqa: BLE001
            bars = []
        i = _date_index(bars, d)
        if i is None:
            bar_missing += 1
            continue
        rec = {}
        for H in missing:
            if i + H < len(bars):
                c0 = bars[i].get("close")
                c1 = bars[i + H].get("close")
                if c0 and c1 is not None:
                    rec["t%d_real" % H] = round(c1 / c0 - 1.0, 6)
        if rec:
            rec.update({"date": d, "code": code, "method": "proxy_bar",
                        "proxy_code": str(proxy)})
            entries.append(rec)
    written = 0
    if entries:
        with _LOCK:
            for rec in entries:
                out = {"date": rec["date"], "code": rec["code"],
                       "backfilled_at": _now_iso(), "method": rec["method"],
                       "proxy_code": rec["proxy_code"]}
                for f in ("t1_real", "t3_real", "t15_real"):
                    if rec.get(f) is not None:
                        out[f] = rec[f]
                _append_jsonl(BACKFILL_PATH, out)
                written += 1
    return {"due": len(entries), "written": written, "bar_missing": bar_missing}


def recompute_shadow_window(days=SHADOW_WINDOW_DAYS, allow_network=True):
    """按现档位全量重生成滚动窗（R2-07）：旧记录先全量归档，再重生成。

    - INSERT-ONLY 记录级语义不破（旧记录可归档复读，首次口径行不丢）；
    - `created_at` 继承：对 (date,code) 在旧集中者复用其 created_at（幂等稳定）；
    - 幂等断言：重复执行后行的 FIELD_LIST 元组集合不变（不变则零写入）；
    - 归档不可读时不半写：直接中止并告警（08-r2 残留风险 2）。
    """
    window, records = compute_shadow_window(days=days, allow_network=allow_network)
    if not window:
        return {"changed": False, "reason": "no_market_data", "days": 0,
                "written": 0, "tier_conflicts": 0,
                "note": "无可用代理行情，未重算（保持原状，不用示例数字）。"}
    with _LOCK:
        existing = read_signals_raw()
        ex_map = {(e.get("date"), e.get("code")): e for e in existing}
        for r in records:
            old = ex_map.get((r.get("date"), r.get("code")))
            if old and old.get("created_at"):
                r["created_at"] = old["created_at"]

        def canon(rows):
            out = []
            for r in rows:
                out.append(tuple(json.dumps(r.get(k), ensure_ascii=False, sort_keys=True)
                                 for k in FIELD_LIST))
            return sorted(out)

        if canon(existing) == canon(records):
            return {"changed": False, "days": len(window), "written": 0,
                    "total_records": len(records), "tier_conflicts": 0,
                    "first_date": window[0], "last_date": window[-1],
                    "as_of": _now_iso()}
        old_keys = {(e.get("date"), e.get("code")) for e in existing}
        new_keys = {(r.get("date"), r.get("code")) for r in records}
        added = len(new_keys - old_keys)
        removed = len(old_keys - new_keys)
        if existing:
            _archive_records(existing, reason="recompute_by_current_tier",
                             extra={"added_count": added, "removed_count": removed,
                                    "window_days": days})
        _write_all_signals(records)
    # 一致性断言：重算后「台账档位 vs 现持仓档位」0 冲突（C/D 记录清出）
    tiers = {h["code"]: h.get("tier") for h in _proxy_assets()}
    conflicts = [r.get("code") for r in records
                 if tiers.get(r.get("code")) not in ("A", "B")]
    if conflicts:
        sys.stderr.write("[ledger] recompute 档位一致性冲突 %d 条\n" % len(conflicts))
    return {
        "changed": True, "days": len(window), "written": len(records),
        "archived": len(existing), "added_count": added, "removed_count": removed,
        "first_date": window[0], "last_date": window[-1],
        "total_records": len(records), "tier_conflicts": len(conflicts),
        "as_of": _now_iso(),
    }


def rolling_open_stats(days=SHADOW_WINDOW_DAYS):
    """滚动 60 交易日开口统计（R2-08 / v9.5 §13）：资产去重数（含归档合并集）。"""
    rows, archive_merged = _merged_all()
    cal = _monitored_calendar()
    if not cal:
        cal = sorted({r.get("date") for r in rows if r.get("date")})
    if not cal:
        return {"rolling_open_assets": 0, "rolling_window_days": days,
                "window_start": None, "window_end": None, "assets": [],
                "asset_days": 0, "archive_merged": archive_merged}
    window = cal[-days:] if len(cal) > days else cal
    wset = set(window)
    opens = [r for r in rows if r.get("date") in wset and r.get("gate") in ("E1", "E3")]
    codes = sorted({r.get("code") for r in opens})
    return {"rolling_open_assets": len(codes), "rolling_window_days": days,
            "window_start": window[0], "window_end": window[-1],
            "assets": codes, "asset_days": len(opens),
            "archive_merged": archive_merged}


def shadow_progress():
    rows, archive_merged = _merged_all()
    if not rows:
        return {
            "status": "not_started", "consecutive_days": 0, "target_days": TARGET_DAYS,
            "progress_ratio": 0.0, "start_date": None, "target_date": None,
            "gap_days": 0, "hit_rate": None, "baseline_rate": None,
            "baseline_source": "measured", "deviation_pp": None,
            "window_days": SHADOW_WINDOW_DAYS, "archive_merged": archive_merged,
            "history_days": 0,
            "note": ("窗口 60 交易日；台账尚未启动。记录按走前口径回算补全（非自然积累）；"
                     "上线资格建议结合实盘观察另行评估。"),
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
    # 连续无漏单（B2：数据集 = 主文件 ∪ 归档；自最新日期向前逐交易日回溯，可达 ≥60）
    consec = 0
    cur = datetime.strptime(last, "%Y-%m-%d").date()
    while cur.strftime("%Y-%m-%d") in present:
        consec += 1
        cur -= timedelta(days=1)
        while cur.weekday() >= 5:
            cur -= timedelta(days=1)
    # gap_days：监控资产代理 K 线日期并集（交易日历）中存在、合并集无记录的交易日数
    cal = _monitored_calendar()
    if cal:
        gap = sum(1 for d in cal if start <= d <= last and d not in present)
        calendar_source = "monitored_bar_union"
    else:
        gap = max(0, _business_days(start, last) + 1 - len(dates))
        calendar_source = "business_day_approx"
    hr = _hit_rate(rows)
    base = measured_baseline(rows)
    dev = (hr - base) if (hr is not None and base is not None) else None
    if gap > 0:
        status = "gap"
    elif consec >= TARGET_DAYS:
        status = "qualified"
    else:
        status = "recording"
    note = ("窗口 60 交易日；记录按走前口径回算补全（非自然积累）；"
            "上线资格建议结合实盘观察另行评估。连续天数按归档合并计算。")
    if not archive_merged:
        note += " 归档缺失或不可读，本值按主文件计算（口径降级）。"
    return {
        "status": status, "consecutive_days": consec, "target_days": TARGET_DAYS,
        "progress_ratio": round(min(1.0, consec / float(TARGET_DAYS)), 2),
        "start_date": start, "target_date": target_date, "gap_days": gap,
        "hit_rate": round(hr, 4) if hr is not None else None,
        "baseline_rate": round(base, 4) if base is not None else None,
        "baseline_source": "measured",
        "deviation_pp": round(dev, 4) if dev is not None else None,
        "window_days": SHADOW_WINDOW_DAYS, "archive_merged": archive_merged,
        "history_days": len(dates), "calendar_source": calendar_source,
        "note": note,
    }


def _shadow_window_fast_check(days, allow_network=True):
    """S3 冷启动快路径：仅做存在性对账（零训练），判断窗口是否已齐备无需重算。

    返回 (window, expected_keys, existing, trimmed) 或 None（无法快判/需重算）。
    - window/expected 仅用 bars 日期集合推导（记录存在性与预测内容无关）；
    - 若既有记录（窗口内）== expected 且无窗口外旧行 → 调用方可直接跳过重算。
    """
    assets = _load_proxy_bars(allow_network=allow_network)
    if not assets:
        return None
    all_dates = sorted({b["date"] for _h, bars in assets for b in bars if b.get("date")})
    if not all_dates:
        return None
    window = all_dates[-days:] if len(all_dates) > days else all_dates
    if not window:
        return None
    expected = set()
    for h, bars in assets:
        ds = {b.get("date") for b in bars if b.get("date")}
        for d in window:
            if d in ds:
                expected.add((d, h["code"]))
    existing = read_signals_raw()
    window_start = window[0]
    have = {(e.get("date"), e.get("code")) for e in existing
            if (e.get("date") or "") >= window_start}
    trimmed = [e for e in existing if (e.get("date") or "") < window_start]
    return window, expected, have, trimmed, assets


def rolling_shadow_backfill(days=SHADOW_WINDOW_DAYS, allow_network=True):
    """滚动回填：补齐最近 `days` 个交易日缺失记录 + 裁剪窗口外最旧记录。

    - INSERT-ONLY：同 (date, code) 已存在即跳过，不覆盖、不重复。
    - 滚动替换：窗口随最新交易日推进，窗口外旧记录归档后从主文件移除。
    - 幂等：同一交易日历下重复触发不新增、不裁剪、条数不变。
    - S3 快路径：窗口记录已齐备且无窗口外旧行时，**跳过重算**（零训练）。
    - v9.5 §13.4 增量模式（实现优化，口径/幂等不变）：仅对**缺键日期 × 资产**做
      走前单点计算（每日滚动通常 1 日 ≈15 次训练 ≈0.3s）；既有 (date,code) 行按
      INSERT-ONLY 原样保留（全量重算本就不覆盖它们，结果逐位等价）。
    """
    fast = _shadow_window_fast_check(days, allow_network=allow_network)
    if fast is not None:
        window, expected, have, trimmed, assets = fast
        # 快判等价于原逻辑的「fresh 空 且 trimmed 空」：
        # expected ⊆ have（窗口内应有记录齐备）+ 无窗口外旧行 → 原逻辑零写入，可跳过重算。
        # 窗口内多余行（如档位变更前冻结的旧码记录）按 INSERT-ONLY 原样保留。
        if have and not trimmed and expected <= have:
            return {
                "window_days": days, "days": len(window),
                "first_date": window[0], "last_date": window[-1],
                "written": 0, "trimmed": 0, "total_records": len(have),
                "codes": len({code for _d, code in expected}),
                "note": "窗口已齐备，跳过重算（幂等快路径，零训练）",
                "as_of": _now_iso(),
            }
        # 增量模式：只计算缺键日期（首填 = 全窗日期；每日滚动 = 新增 1 日）
        missing_dates = sorted({d for (d, _c) in expected if (d, _c) not in have})
        if missing_dates:
            _, records = compute_shadow_window(days=days, allow_network=allow_network,
                                               only_dates=missing_dates, assets=assets)
        else:
            records = []
    else:
        window, records = compute_shadow_window(days=days, allow_network=allow_network)
    if not window:
        return {"window_days": days, "days": 0, "first_date": None, "last_date": None,
                "written": 0, "trimmed": 0, "total_records": 0, "codes": 0,
                "note": "无可用代理行情，未产出影子台账（保持为空，不用示例数字）。"}
    window_start = window[0]
    with _LOCK:
        existing = read_signals_raw()
        have = {(e.get("date"), e.get("code")) for e in existing}
        fresh = [r for r in records if (r["date"], r["code"]) not in have]
        kept = [e for e in existing if (e.get("date") or "") >= window_start]
        trimmed = [e for e in existing if (e.get("date") or "") < window_start]
        if fresh or trimmed:
            if trimmed:
                _archive_records(trimmed)
            _write_all_signals(kept + fresh)
        total = len(kept) + len(fresh)
    return {
        "window_days": days, "days": len(window),
        "first_date": window[0], "last_date": window[-1],
        "written": len(fresh), "trimmed": len(trimmed), "total_records": total,
        "codes": len({r["code"] for r in records}),
        "as_of": _now_iso(),
    }


def shadow_ledger(limit=60, offset=0):
    rows, total = read_ledger(limit=limit, offset=offset)
    # 按 created_at 倒序
    rows.sort(key=lambda r: (r.get("created_at") or "", r.get("code") or ""), reverse=True)
    allrows, _archive_merged = _merged_all()
    opens = sum(1 for r in allrows if r.get("signal") == "up")
    abstains = sum(1 for r in allrows if r.get("signal") == "abstain")
    backfilled = sum(1 for r in allrows
                     if all(r.get(f) is not None for f in ("t1_real", "t3_real", "t15_real")))
    hr = _hit_rate(allrows)
    base = measured_baseline(allrows)
    summary = {
        "total_records": len(allrows),
        "open_signals": opens,
        "veto_abstains": abstains,
        "backfilled_count": backfilled,
        "hit_rate": round(hr, 4) if hr is not None else None,
        # R2-14/B3：实测基线 + 来源登记（旧常量不再参与计算）
        "baseline_rate": round(base, 4) if base is not None else None,
        "baseline_source": "measured",
    }
    return {
        "rows": rows, "total": total, "summary": summary,
        "progress": shadow_progress(), "field_list": FIELD_LIST,
        "retention_policy": RETENTION_POLICY,
        "first_of_day_immutable": True,
        "archive_manifest_at": _archive_manifest_at(),
        # R2-12：本盘回填口径（页面口径标注数据源）
        "backfill_method": "proxy_bar",
        "backfill_method_note": BACKFILL_METHOD_NOTE,
        "insert_only_note": INSERT_ONLY_NOTE, "as_of": _today(),
    }


def _archive_manifest_at():
    """最近一次归档清单时间（archive/_manifest.jsonl 末行 created_at）；未归档 null。"""
    path = os.path.join(LEDGER_DIR, "archive", "_manifest.jsonl")
    recs = _read_jsonl(path)
    if not recs:
        return None
    return recs[-1].get("created_at") or recs[-1].get("archived_at")


def shadow_audit():
    rows, _archive_merged = _merged_all()
    if not rows:
        return {
            "status": "idle", "rolling_days": 60, "hit_rate": None,
            "baseline_rate": None, "baseline_source": "measured", "deviation_pp": None,
            "threshold_pp": DEVIATION_THRESHOLD,
            "message": "影子盘尚未启动，先积累连续记录再评估上线资格。",
            "checked_at": _now_iso(),
            "note": "回测再漂亮也只是回测，最后保险是影子盘（本盘记录按走前口径回算，非自然积累）。",
        }
    dates = sorted(set(r.get("date") for r in rows if r.get("date")), reverse=True)
    window = set(dates[:60])
    subset = [r for r in rows if r.get("date") in window]
    hr = _hit_rate(subset)
    base = measured_baseline(subset)
    dev = (hr - base) if (hr is not None and base is not None) else None
    if dev is None:
        status = "idle"
    elif abs(dev) >= DEVIATION_THRESHOLD:
        status = "bad"
    else:
        status = "ok"
    return {
        "status": status, "rolling_days": 60,
        "hit_rate": round(hr, 4) if hr is not None else None,
        "baseline_rate": round(base, 4) if base is not None else None,
        "baseline_source": "measured",
        "deviation_pp": round(dev, 4) if dev is not None else None,
        "threshold_pp": DEVIATION_THRESHOLD,
        "message": ("影子盘达标（偏差 <2pp）" if status == "ok"
                    else ("影子盘降级：偏差 ≥2pp" if status == "bad" else "影子盘样本不足")),
        "checked_at": _now_iso(),
        "note": "回测再漂亮也只是回测，最后保险是影子盘（本盘记录按走前口径回算，非自然积累）。",
    }


def ledger_chain(date, code):
    """台账事件链（契约 v8 §5.34：固定 6 步）。

    BLOCK-A3（08.7）：写入侧无 `_chain` 时按**与写入同源口径**读时重算六步
    （离线 bars + 走前训练，不写台账、不改 INSERT-ONLY）；不可复现 → 空链
    （前端按 `chain_available` 明示不可复现，不编造步骤数值）。

    v9.3（C3 采纳）：响应追加 `chain_source`（enum `chain_source`/null）——
    `stored`=写入时缓存链 / `recomputed`=读时同源重算 / 不可用=null（不得编造）。
    """
    e = get_entry(date, code)
    if e is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该条台账",
                              {"date": date, "code": code})
    names = _name_map()
    chain = e.get("_chain")
    metrics = e.get("_metrics") or {}
    chain_source = None
    if chain:
        chain_source = "stored"
    else:
        chain, recomputed_metrics = _recompute_chain(e)
        if chain:
            chain_source = "recomputed"
            metrics = recomputed_metrics or metrics
        else:
            chain = []
    return {
        "date": e.get("date"), "code": e.get("code"),
        "name": names.get(e.get("code"), e.get("name", "")),
        "gate": e.get("gate"), "signal": e.get("signal"), "p_up": e.get("p_up"),
        "chain": chain,
        # v9.3：chain_available=false ⇔ 此处 null（同源一致）
        "chain_source": chain_source,
        "metrics": metrics,
        "source_ledger": "shadow_signals.jsonl",
        "created_at": e.get("created_at") or e.get("written_at"),
    }


def _today():
    return datetime.now().strftime("%Y-%m-%d")


# 兼容：供 factor_board 使用的 shadow_signals 账本原文
def shadow_signals_records():
    return read_signals_raw()
