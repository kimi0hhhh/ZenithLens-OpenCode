# -*- coding: utf-8 -*-
"""外部取数适配层 + 五档降级链取数原语。

- 行情主通道：腾讯日K（不复权 + 自修除权：>25% 跳变缩放历史），来源 PROJECT_BRIEF §5.3
- 实时估值：腾讯实时 / 天天基金（盘中估算+官方净值）/ 新浪（仅探测，主链未用）
- 所有外部调用有超时（单源 5s、最多重试 1 次；五档总预算由 valuation.py 控制）
- 纯标准库：urllib.request / json / ssl，禁用第三方
"""

import io
import json
import os
import ssl
import time
from datetime import datetime

import errors
import settings

ROOT = os.path.dirname(os.path.abspath(__file__))
BARS_DIR = os.path.join(ROOT, "data", "cache", "bars")
HOLD_DIR = os.path.join(ROOT, "data", "cache", "holdings")

HTTP_TIMEOUT = 5.0
HTTP_RETRIES = 1
USER_AGENT = "Mozilla/5.0 (ZenithLens local; +local backend)"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _now_ts():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def http_get(url, timeout=HTTP_TIMEOUT, headers=None, retries=HTTP_RETRIES):
    """带超时/重试的 GET，返回 bytes；失败返回 None（不抛给调用方）。"""
    import urllib.request
    import urllib.error
    last = None
    hdr = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    for _ in range(retries + 1):
        req = urllib.request.Request(url, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - 适配层统一兜住
            last = e
            time.sleep(0.15)
    _ = last
    return None


# ---------------- 交易所前缀 ----------------

def tencent_symbol(code):
    code = str(code).strip()
    if not code:
        return None
    if code[0] in ("5", "6", "9") or code.startswith("11"):
        return "sh" + code
    return "sz" + code


# ---------------- 腾讯日K ----------------

def _fetch_kline_raw(code, count=320):
    sym = tencent_symbol(code)
    if not sym:
        return None
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,"
           % (sym, int(count)))
    raw = http_get(url)
    if raw is None:
        settings.record_source("tencent_kline", False, note="kline unreachable")
        return None
    try:
        obj = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        settings.record_source("tencent_kline", False, note="kline parse error")
        return None
    data = (obj or {}).get("data") or {}
    node = data.get(sym) or {}
    rows = node.get("day") or node.get("qfqday") or []
    out = []
    for r in rows:
        try:
            out.append({
                "date": r[0],
                "open": float(r[1]),
                "close": float(r[2]),
                "high": float(r[3]),
                "low": float(r[4]),
                "volume": float(r[5]),
            })
        except (IndexError, TypeError, ValueError):
            continue
    settings.record_source("tencent_kline", True)
    return out


def self_adjust(bars, threshold=0.25):
    """自修除权：>25% 单日跳变视为分红/拆分，按比例缩放之前全部历史。

    口径来源：PROJECT_BRIEF §5.3（不复权 + 自修除权：>25% 跳变缩放历史）。
    仅缩放 OHLC，不改 volume（近似，见 14-api-impl-report 残留风险）。
    """
    if not bars:
        return bars
    out = [dict(b) for b in bars]
    cum = 1.0
    # 从后往前走，累计缩放因子，避免修改已处理段
    for i in range(1, len(out)):
        prev_close = bars[i - 1]["close"]
        cur_close = bars[i]["close"]
        if prev_close <= 0 or cur_close <= 0:
            continue
        ratio = cur_close / prev_close
        if ratio > 1 + threshold or ratio < 1 - threshold:
            # 历史段（含 i-1）整体乘以 ratio，使 i-1 与 i 连续
            for j in range(0, i):
                out[j]["open"] *= ratio
                out[j]["high"] *= ratio
                out[j]["low"] *= ratio
                out[j]["close"] *= ratio
    _ = cum
    return out


def _bars_cache_path(code):
    return os.path.join(BARS_DIR, "%s.json" % code)


def _cache_age_hours(fetched_at):
    if not fetched_at:
        return 1e9
    try:
        t = datetime.fromisoformat(fetched_at)
        now = datetime.now(t.tzinfo) if t.tzinfo else datetime.now()
        return (now - t).total_seconds() / 3600.0
    except ValueError:
        return 1e9


def get_bars(code, allow_network=True, force=False, count=320):
    """返回 (bars, meta)。优先本地缓存，过期或 force 时拉腾讯。无数据返回 ([], meta)。"""
    if not os.path.isdir(BARS_DIR):
        os.makedirs(BARS_DIR)
    path = _bars_cache_path(code)
    cached = None
    if os.path.isfile(path):
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except (IOError, OSError, ValueError):
            cached = None
    need = force or cached is None or _cache_age_hours(cached.get("fetched_at")) > 6
    if need and allow_network:
        bars = _fetch_kline_raw(code, count=count)
        if bars:
            bars = self_adjust(bars)
            meta = {
                "code": code,
                "symbol": tencent_symbol(code),
                "source": "tencent_kline",
                "fetched_at": _now_ts(),
                "adjusted": True,
                "rows": bars,
            }
            try:
                tmp = path + ".tmp"
                with io.open(tmp, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False)
                os.replace(tmp, path)
            except (IOError, OSError):
                pass
            return bars, meta
    if cached is not None:
        return cached.get("rows", []), cached
    return [], {"code": code, "symbol": tencent_symbol(code), "source": "tencent_kline",
                "fetched_at": None, "adjusted": True, "rows": []}


def bars_as_of(code, allow_network=True):
    bars, meta = get_bars(code, allow_network=allow_network)
    return bars


# ---------------- 腾讯实时报价 ----------------

def tencent_rt_quote(code):
    """返回 {price, prev_close, change_rate, name, time} 或 None。"""
    sym = tencent_symbol(code)
    if not sym:
        return None
    raw = http_get("https://qt.gtimg.cn/q=%s" % sym)
    if raw is None:
        settings.record_source("tencent_rt", False, note="rt unreachable")
        return None
    try:
        text = raw.decode("gbk", "replace")
    except Exception:
        text = raw.decode("utf-8", "replace")
    if "=" not in text:
        settings.record_source("tencent_rt", False, note="rt empty")
        return None
    payload = text.split("=", 1)[1].strip().strip('";')
    parts = payload.split("~")
    try:
        price = float(parts[3])
        prev = float(parts[4])
    except (IndexError, TypeError, ValueError):
        settings.record_source("tencent_rt", False, note="rt parse error")
        return None
    if prev <= 0:
        settings.record_source("tencent_rt", False, note="rt zero prev")
        return None
    settings.record_source("tencent_rt", True)
    return {
        "code": code,
        "symbol": sym,
        "name": parts[1] if len(parts) > 1 else "",
        "price": price,
        "prev_close": prev,
        "change_rate": price / prev - 1.0,
        "time": parts[30] if len(parts) > 30 else "",
    }


# ---------------- 天天基金：官方净值 + 盘中估算 ----------------

def eastmoney_fund_estimate(code):
    """解析 fundgz。返回 {official_nav, official_nav_date, estimate_nav,
    estimate_change_rate, estimate_time, name} 或 None。"""
    url = "https://fundgz.1234567.com.cn/js/%s.js?rt=%d" % (code, int(time.time() * 1000))
    raw = http_get(url)
    if raw is None:
        settings.record_source("eastmoney", False, note="fundgz unreachable")
        return None
    text = raw.decode("utf-8", "replace")
    if "jsonpgz(" not in text:
        settings.record_source("eastmoney", False, note="no jsonpgz")
        return None
    try:
        body = text[text.index("jsonpgz(") + len("jsonpgz("):]
        body = body[:body.rindex(")")]
        obj = json.loads(body)
    except (ValueError, IndexError):
        settings.record_source("eastmoney", False, note="fundgz parse error")
        return None

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    est_pct = _num(obj.get("gszzl"))
    out = {
        "code": code,
        "name": obj.get("name", ""),
        "official_nav": _num(obj.get("dwjz")),
        "official_nav_date": obj.get("jzrq"),
        "estimate_nav": _num(obj.get("gsz")),
        "estimate_change_rate": (est_pct / 100.0) if est_pct is not None else None,
        "estimate_time": obj.get("gztime"),
    }
    settings.record_source("eastmoney", True)
    return out


def eastmoney_top_holdings(code):
    """前十大重仓（30 天缓存）。无缓存且未抓取时返回 None（不编造）。

    本期不实现重仓页抓取（HTML 结构脆弱），若本地已有缓存则使用；
    否则该档 trace 记 tried=true/hit=false/reason=no_report（诚实降级）。
    """
    if not os.path.isdir(HOLD_DIR):
        os.makedirs(HOLD_DIR)
    path = os.path.join(HOLD_DIR, "%s.json" % code)
    if os.path.isfile(path):
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if _cache_age_hours(obj.get("fetched_at")) <= 24 * 30:
                return obj
        except (IOError, OSError, ValueError):
            return None
    return None


# ---------------- 探测 ----------------

def probe_source(source_id):
    if source_id == "tencent_kline":
        bars = _fetch_kline_raw("000001", count=3)
        return bool(bars)
    if source_id == "tencent_rt":
        return tencent_rt_quote("000001") is not None
    if source_id == "eastmoney":
        return eastmoney_fund_estimate("000217") is not None
    if source_id == "sina_rt":
        raw = http_get("https://hq.sinajs.cn/list=sh000001",
                       headers={"Referer": "https://finance.sina.com.cn"})
        if raw is None:
            return False
        try:
            text = raw.decode("gbk", "replace")
        except Exception:
            text = raw.decode("utf-8", "replace")
        ok = "sh000001" in text and "=" in text
        settings.record_source("sina_rt", ok)
        return ok
    raise errors.ApiError(errors.E_VALIDATION, "未知数据源", {"source_id": source_id})
