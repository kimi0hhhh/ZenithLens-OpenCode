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
import re
import ssl
import time
from datetime import datetime

import errors
import settings

ROOT = os.path.dirname(os.path.abspath(__file__))
BARS_DIR = os.path.join(ROOT, "data", "cache", "bars")
HOLD_DIR = os.path.join(ROOT, "data", "cache", "holdings")
NAV_DIR = os.path.join(ROOT, "data", "cache", "nav")
FUNDVAL_PATH = os.path.join(NAV_DIR, "fund_valuation.json")
FUNDOFF_PATH = os.path.join(NAV_DIR, "fund_official.json")

HTTP_TIMEOUT = 5.0
HTTP_RETRIES = 1
USER_AGENT = "Mozilla/5.0 (ZenithLens local; +local backend)"

# 天天基金估值接口：旧 fundgz JSONP 于 2026-07-21 下线（301→notfound），
# 改用 H5 新接口 FundValuationLast（支持批量；字段 NAV/PDATE/GSZ/GSZZL/GZTIME）。
# 来源：leek-fund#677 与天天基金 H5 实测（2026-09-12）。
FUNDVAL_HOSTS = (
    "https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast",
    "https://fundcomapi.eastmoney.com/mm/newCore/FundValuationLast",
)
FUNDVAL_FIELDS = "FCODE,SHORTNAME,GSZZL,GZTIME,GSZ,NAV,PDATE"
LSJZ_URL = "https://api.fund.eastmoney.com/f10/lsjz"
PINGZHONG_URL = "https://fund.eastmoney.com/pingzhongdata/%s.js"
FUNDVAL_CACHE_TTL_SEC = 90      # 盘中估算需较新；批量接口单请求成本低
OFFICIAL_CACHE_TTL_SEC = 24 * 3600
# 前十持仓季度披露：缓存 30 天（来源：本任务「主动基金重仓加权」数据源口径）
HOLD_CACHE_TTL_SEC = 24 * 30 * 3600
# 天天基金 F10 前十持仓（HTML；需 UA+Referer，实测 200，UTF-8）；R2-02 起 topline 可为 20
F10_HOLD_URL = ("https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
                "?type=jjcc&code=%s&topline=%d")
F10_HOLD_REFERER = "https://fundf10.eastmoney.com/ccmx_%s.html"

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
    """代码 → 腾讯行情符号。

    - 6 位 A 股：5/6/9 开头或 11 开头 → sh，其余 → sz；
    - 5 位数字（港股）：hk 前缀（R2-02；来源：08-backend-arch-r2 §3.2）；
    - 字母代码（美股等）：不解析（parser 不产出）→ None，调用方计入 excluded_count（不编造）。
    """
    code = str(code).strip()
    if not code:
        return None
    if len(code) == 5 and code.isdigit():
        return "hk" + code
    if not code.isdigit():
        return None
    if code[0] in ("5", "6", "9") or code.startswith("11"):
        return "sh" + code
    return "sz" + code


def market_of_code(code):
    """代码 → 市场枚举（A/HK/US）。

    6 位数字 → A；5 位数字 → HK；其余（字母）→ US（不解析行情，如实计入缺口）。
    """
    c = str(code or "").strip()
    if len(c) == 6 and c.isdigit():
        return "A"
    if len(c) == 5 and c.isdigit():
        return "HK"
    return "US"


# ---------------- 基金类型分类（主动 / 指数联接 / QDII） ----------------

# 口径来源：本任务（2026-09-12）「主动基金不以 ETF 为估值锚，改用前十大重仓股加权」。
# 分类只据基金名称关键字判定（名称来自持仓源文件，只读，不臆造）。
FUND_TYPE_LABEL = {
    "active": "主动",
    "index_link": "指数联接",
    "qdii": "QDII",
    "other": "其他",
}
# QDII/海外优先（名称含 QDII 的主动混合基金归 QDII，不做重仓加权主估值）
_QDII_MARKERS = ("QDII", "全球", "亚洲", "海外", "纳指", "标普", "油气",
                 "美元", "欧元", "港股", "恒生")
# 指数/ETF/联接/黄金 → 指数联接（含商品 ETF 联接；维持 proxy ETF 主口径）
_INDEX_MARKERS = ("指数", "ETF", "联接", "LOF", "黄金")
# 主动权益
_ACTIVE_MARKERS = ("混合", "股票", "灵活")


def classify_fund_type(name):
    """按名称分类：active / index_link / qdii / other（判定失败归 other，保守走 proxy）。

    规则（本任务）：
    - 主动 = 名称含「混合/股票/灵活」且**非**「指数/ETF联接/联接/QDII」；
    - QDII 标记优先于主动（QDII 混合基金不做重仓加权主估值）；
    - 指数/ETF/联接/黄金 → index_link（维持 proxy ETF 口径）。
    """
    n = str(name or "")
    if any(k in n for k in _QDII_MARKERS):
        return "qdii"
    if any(k in n for k in _INDEX_MARKERS):
        return "index_link"
    if any(k in n for k in _ACTIVE_MARKERS):
        return "active"
    return "other"


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


def tencent_rt_quotes(codes):
    """批量实时报价（一次请求多个代码，供重仓加权取个股实时涨跌）。

    返回 {code: quote}；单请求 5s 超时，失败/缺失的代码不入表（调用方按 null 处理，不编造）。
    """
    syms = []
    sym2code = {}
    for c in codes or []:
        sym = tencent_symbol(c)
        if sym:
            syms.append(sym)
            sym2code[sym] = str(c)
    if not syms:
        return {}
    raw = http_get("https://qt.gtimg.cn/q=%s" % ",".join(syms))
    if raw is None:
        settings.record_source("tencent_rt", False, note="rt batch unreachable")
        return {}
    try:
        text = raw.decode("gbk", "replace")
    except Exception:  # noqa: BLE001
        text = raw.decode("utf-8", "replace")
    out = {}
    for line in text.split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        sym = line.split("=", 1)[0].strip()
        if sym.startswith("v_"):
            sym = sym[2:]
        payload = line.split("=", 1)[1].strip().strip('"')
        parts = payload.split("~")
        if len(parts) < 5:
            continue
        try:
            price = float(parts[3])
            prev = float(parts[4])
        except (IndexError, TypeError, ValueError):
            continue
        if prev <= 0:
            continue
        code = sym2code.get(sym)
        if not code:
            continue
        out[str(code)] = {
            "code": str(code),
            "symbol": sym,
            "name": parts[1] if len(parts) > 1 else "",
            "price": price,
            "prev_close": prev,
            "change_rate": price / prev - 1.0,
            "time": parts[30] if len(parts) > 30 else "",
        }
    settings.record_source("tencent_rt", bool(out), note="rt batch")
    return out


def sina_rt_quote(code):
    """新浪实时报价兜底。返回 {price, prev_close, change_rate, name, time} 或 None。

    字段口径（hq.sinajs.cn/list=shXXXXXX）：0 名称、1 今开、2 昨收、3 现价。
    """
    sym = tencent_symbol(code)
    if not sym:
        return None
    raw = http_get("https://hq.sinajs.cn/list=%s" % sym,
                   headers={"Referer": "https://finance.sina.com.cn"})
    if raw is None:
        settings.record_source("sina_rt", False, note="sina unreachable")
        return None
    try:
        text = raw.decode("gbk", "replace")
    except Exception:
        text = raw.decode("utf-8", "replace")
    if '"' not in text:
        settings.record_source("sina_rt", False, note="sina empty")
        return None
    payload = text.split('"', 1)[1].rsplit('"', 1)[0]
    parts = payload.split(",")
    try:
        name = parts[0]
        prev = float(parts[2])
        price = float(parts[3])
    except (IndexError, TypeError, ValueError):
        settings.record_source("sina_rt", False, note="sina parse error")
        return None
    if prev <= 0 or price <= 0:
        settings.record_source("sina_rt", False, note="sina zero prev")
        return None
    settings.record_source("sina_rt", True)
    return {
        "code": code,
        "symbol": sym,
        "name": name,
        "price": price,
        "prev_close": prev,
        "change_rate": price / prev - 1.0,
        "time": parts[31] if len(parts) > 31 else (parts[30] if len(parts) > 30 else ""),
    }


def sina_rt_quotes(codes):
    """新浪批量实时报价兜底（仅 6 位 A 股；R2-17 限定兜底，不做主源）。

    - 单请求 5s 超时、重试 0（防双重超时拖垮估值预算；08-backend-arch-r2 §6.3）；
    - 非 A 股（5 位港股/字母美股）不解析、不入表（调用方按 null 处理，不编造）；
    - 每次调用 record_source("sina_rt", ...) 留痕（成功/失败均记，F2-17/F2-18）。
    """
    a_codes = [str(c) for c in (codes or [])
               if len(str(c)) == 6 and str(c).isdigit()]
    if not a_codes:
        return {}
    syms = []
    sym2code = {}
    for c in a_codes:
        sym = tencent_symbol(c)
        if sym:
            syms.append(sym)
            sym2code[sym] = c
    if not syms:
        return {}
    raw = http_get("https://hq.sinajs.cn/list=%s" % ",".join(syms),
                   headers={"Referer": "https://finance.sina.com.cn"}, retries=0)
    if raw is None:
        settings.record_source("sina_rt", False, note="sina batch unreachable")
        return {}
    try:
        text = raw.decode("gbk", "replace")
    except Exception:  # noqa: BLE001
        text = raw.decode("utf-8", "replace")
    out = {}
    for line in text.split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        head, _, payload = line.partition("=")
        sym = head.strip()
        if sym.startswith("var hq_str_"):
            sym = sym[len("var hq_str_"):]
        code = sym2code.get(sym)
        if not code:
            continue
        payload = payload.strip().strip('"')
        parts = payload.split(",")
        try:
            prev = float(parts[2])
            price = float(parts[3])
        except (IndexError, TypeError, ValueError):
            continue
        if prev <= 0 or price <= 0:
            continue
        out[str(code)] = {
            "code": str(code),
            "symbol": sym,
            "name": parts[0],
            "price": price,
            "prev_close": prev,
            "change_rate": price / prev - 1.0,
            "time": parts[31] if len(parts) > 31 else (parts[30] if len(parts) > 30 else ""),
        }
    settings.record_source("sina_rt", bool(out), note="sina batch")
    return out


# ---------------- 净值缓存工具 ----------------

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _read_cache(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def _write_cache(path, obj):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    tmp = path + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except (IOError, OSError):
        pass


def _age_sec(fetched_at):
    if not fetched_at:
        return 1e9
    try:
        t = datetime.fromisoformat(fetched_at)
        now = datetime.now(t.tzinfo) if t.tzinfo else datetime.now()
        return (now - t).total_seconds()
    except ValueError:
        return 1e9


# ---------------- 天天基金：官方净值 + 盘中估算（FundValuationLast） ----------------

def fetch_fund_valuation(codes, allow_network=True):
    """批量抓取最新官方净值 + 盘中估算（天天基金 FundValuationLast）。

    字段映射：NAV→官方最新单位净值、PDATE→净值日期(jzrq)、GSZ→盘中估算净值、
    GSZZL→估算涨跌幅(%)、GZTIME→估值时间、SHORTNAME→名称。
    返回 {code: record}；结果落 `data/cache/nav/fund_valuation.json`（带 fetched_at）。
    失败不抛，`settings.record_source("eastmoney", False, ...)` 如实留痕并回退缓存。
    """
    codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
    cache = _read_cache(FUNDVAL_PATH)
    if not allow_network or not codes:
        return {c: cache[c] for c in codes if c in cache}
    fresh = {}
    for i in range(0, len(codes), 50):
        chunk = codes[i:i + 50]
        raw = None
        for host in FUNDVAL_HOSTS:
            url = "%s?FCODES=%s&FIELDS=%s" % (host, ",".join(chunk), FUNDVAL_FIELDS)
            raw = http_get(url, headers={"Referer": "https://h5.1234567.com.cn/"})
            if raw is not None:
                break
        if raw is None:
            settings.record_source("eastmoney", False, note="fundvaluation unreachable")
            continue
        try:
            obj = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            settings.record_source("eastmoney", False, note="fundvaluation parse error")
            continue
        for row in (obj or {}).get("data") or []:
            code = str(row.get("FCODE") or "")
            if not code:
                continue
            gszzl = _num(row.get("GSZZL"))
            rec = {
                "code": code,
                "name": row.get("SHORTNAME") or "",
                "nav": _num(row.get("NAV")),
                "nav_date": row.get("PDATE"),
                "gsz": _num(row.get("GSZ")),
                "gszzl": gszzl,
                "estimate_change_rate": (gszzl / 100.0) if gszzl is not None else None,
                "gztime": row.get("GZTIME"),
                "source": "fundcomapi",
                "fetched_at": _now_ts(),
            }
            cache[code] = rec
            fresh[code] = rec
        settings.record_source("eastmoney", True, note="fundvaluation")
    _write_cache(FUNDVAL_PATH, cache)
    for c in codes:
        if c not in fresh and c in cache:
            fresh[c] = cache[c]
    return fresh


def cached_fund_valuation(code):
    return _read_cache(FUNDVAL_PATH).get(str(code))


def get_fund_valuation(code, allow_network=True, max_age_sec=FUNDVAL_CACHE_TTL_SEC,
                      force=False):
    """缓存优先；过期且允许联网时按单代码补抓，失败回退缓存（不编造）。"""
    code = str(code)
    rec = _read_cache(FUNDVAL_PATH).get(code)
    if rec is not None and not force and _age_sec(rec.get("fetched_at")) <= max_age_sec:
        return rec
    if not allow_network:
        return rec
    return fetch_fund_valuation([code], allow_network=True).get(code) or rec


def refresh_fund_valuation(hold_list, allow_network=True,
                           max_age_sec=FUNDVAL_CACHE_TTL_SEC, force=False):
    """对持仓批量刷新净值/估算缓存；未过期不重复联网。

    force=True 时忽略缓存年龄强制批量抓取（启动与 refresh_valuation 任务用）。
    """
    codes = [str(h.get("code")) for h in (hold_list or []) if h.get("code")]
    cache = _read_cache(FUNDVAL_PATH)
    need = codes if force else [
        c for c in codes if c not in cache
        or _age_sec(cache[c].get("fetched_at")) > max_age_sec]
    if need and allow_network:
        fetch_fund_valuation(need, allow_network=True)
        cache = _read_cache(FUNDVAL_PATH)
    return {c: cache[c] for c in codes if c in cache}


def eastmoney_official_nav(code, allow_network=True, force=False):
    """官方已公布净值（含上一日与日涨跌）：天天基金 lsjz（pageSize=2）。

    返回 {nav, nav_date, change_rate, prev_nav, source, fetched_at} 或 None。
    用于补齐 FundValuationLast 缺失的上一日净值/官方涨跌；24h 缓存。
    """
    code = str(code)
    cache = _read_cache(FUNDOFF_PATH)
    rec = cache.get(code)
    if rec is not None and not force and _age_sec(rec.get("fetched_at")) <= OFFICIAL_CACHE_TTL_SEC:
        return rec
    if not allow_network:
        return rec
    url = "%s?fundCode=%s&pageIndex=1&pageSize=2" % (LSJZ_URL, code)
    raw = http_get(url, headers={"Referer": "https://fund.eastmoney.com/"})
    if raw is None:
        settings.record_source("eastmoney", False, note="lsjz unreachable")
        return rec
    try:
        obj = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        settings.record_source("eastmoney", False, note="lsjz parse error")
        return rec
    rows = ((obj or {}).get("Data") or {}).get("LSJZList") or []
    if not rows:
        settings.record_source("eastmoney", False, note="lsjz empty")
        return rec
    nav = _num(rows[0].get("DWJZ"))
    jzzzl = _num(rows[0].get("JZZZL"))
    prev_nav = _num(rows[1].get("DWJZ")) if len(rows) > 1 else None
    if prev_nav is None and nav is not None and jzzzl is not None and (1 + jzzzl / 100.0) != 0:
        prev_nav = nav / (1 + jzzzl / 100.0)
    out = {
        "code": code, "nav": nav, "nav_date": rows[0].get("FSRQ"),
        "change_rate": (jzzzl / 100.0) if jzzzl is not None else None,
        "prev_nav": prev_nav, "source": "lsjz", "fetched_at": _now_ts(),
    }
    if nav is not None:
        cache[code] = out
        _write_cache(FUNDOFF_PATH, cache)
    settings.record_source("eastmoney", True, note="lsjz")
    return out


def cached_official_nav(code):
    return _read_cache(FUNDOFF_PATH).get(str(code))


LSJZ_PAGE_SIZE = 20          # 实测接口单页上限 20 行（pageSize>20 被截断）
LSJZ_MAX_POINTS = 250        # 维护版净值史点数上限（08-backend-arch-r2 §6.1）
LSJZ_MAX_PAGES = 15


def lsjz_history(code, allow_network=True, max_points=LSJZ_MAX_POINTS,
                 existing_dates=None):
    """维护版净值史取数：天天基金 lsjz 分页（pageIndex 递增，止于空页/满点数）。

    口径来源：08-backend-arch-r2 §6.1（R2-16）。返回按日期升序的
    [{date, nav, change_rate}]；失败返回 None（调用方保留已有数据 + 标注滞后，不编造净值）。
    `existing_dates`：已存日期集合；当新抓页完全落在已存区间（增量已接上历史）即停，
    避免每次全量 13 页（首轮全量、之后 1~2 页增量）。
    """
    code = str(code)
    if not allow_network:
        return None
    out = []
    for page in range(1, LSJZ_MAX_PAGES + 1):
        url = "%s?fundCode=%s&pageIndex=%d&pageSize=%d" % (
            LSJZ_URL, code, page, LSJZ_PAGE_SIZE)
        raw = http_get(url, headers={"Referer": "https://fund.eastmoney.com/"})
        if raw is None:
            settings.record_source("eastmoney", False, note="lsjz history unreachable")
            return out if out else None
        try:
            obj = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            settings.record_source("eastmoney", False, note="lsjz history parse error")
            return out if out else None
        rows = ((obj or {}).get("Data") or {}).get("LSJZList") or []
        if not rows:
            break
        page_dates = []
        for r in rows:
            d = r.get("FSRQ")
            nav = _num(r.get("DWJZ"))
            if not d or nav is None:
                continue
            jz = _num(r.get("JZZZL"))
            out.append({"date": d, "nav": nav,
                        "change_rate": (jz / 100.0) if jz is not None else None})
            page_dates.append(d)
        if len(out) >= max_points:
            break
        # 增量已接上既有历史：本页所有日期都已存过 → 更早的页无需再抓
        if existing_dates and page_dates and all(d in existing_dates for d in page_dates):
            break
    settings.record_source("eastmoney", True, note="lsjz history")
    out.sort(key=lambda x: x.get("date") or "")
    return out[:max_points] if len(out) > max_points else out


def refresh_official_nav(hold_list, allow_network=True):
    for h in hold_list or []:
        code = h.get("code")
        if not code:
            continue
        try:
            eastmoney_official_nav(code, allow_network=allow_network)
        except Exception:  # noqa: BLE001 - 单只失败不拖垮整批
            continue


def eastmoney_pingzhong_nav(code, allow_network=True):
    """末位回退：从 pingzhongdata 解析 Data_netWorthTrend 最近两期官方净值。

    仅在 FundValuationLast 与 lsjz 均无数据时使用；返回 {nav, nav_date,
    prev_nav, change_rate} 或 None。
    """
    if not allow_network:
        return None
    raw = http_get(PINGZHONG_URL % code)
    if raw is None:
        settings.record_source("eastmoney", False, note="pingzhongdata unreachable")
        return None
    text = raw.decode("utf-8", "replace")
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\])\s*;", text, re.S)
    if not m:
        settings.record_source("eastmoney", False, note="pingzhongdata no netWorthTrend")
        return None
    try:
        rows = json.loads(m.group(1))
    except ValueError:
        settings.record_source("eastmoney", False, note="pingzhongdata parse error")
        return None
    if not rows:
        return None
    last = rows[-1]
    nav = _num(last.get("y"))
    ts = last.get("x")
    nav_date = None
    if ts is not None:
        try:
            nav_date = datetime.fromtimestamp(float(ts) / 1000.0).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            nav_date = None
    prev_nav = _num(rows[-2].get("y")) if len(rows) > 1 else None
    change = None
    if nav is not None and prev_nav:
        change = nav / prev_nav - 1.0
    settings.record_source("eastmoney", True, note="pingzhongdata")
    return {"code": str(code), "nav": nav, "nav_date": nav_date,
            "prev_nav": prev_nav, "change_rate": change, "source": "pingzhongdata"}


def get_official_nav(code, allow_network=True):
    """官方净值统一入口：FundValuationLast → lsjz → pingzhongdata。

    allow_network=False 时只读缓存（不联网）。返回含 gsz/estimate_change_rate/
    gztime 的合并快照；全链路无数据时各字段为 None（不编造）。
    """
    fv = get_fund_valuation(code, allow_network=allow_network)
    off = eastmoney_official_nav(code, allow_network=allow_network)
    nav = fv.get("nav") if fv else None
    nav_date = fv.get("nav_date") if fv else None
    name = fv.get("name") if fv else None
    change = None
    prev = None
    source = "fundcomapi" if nav is not None else None
    if off and off.get("nav") is not None:
        if nav is None or (off.get("nav_date") or "") > (nav_date or ""):
            nav = off["nav"]
            nav_date = off.get("nav_date")
            source = "lsjz"
        change = off.get("change_rate")
        prev = off.get("prev_nav")
    if nav is None and allow_network:
        pz = eastmoney_pingzhong_nav(code, allow_network=True)
        if pz and pz.get("nav") is not None:
            nav = pz["nav"]
            nav_date = pz.get("nav_date")
            prev = pz.get("prev_nav")
            change = pz.get("change_rate")
            source = "pingzhongdata"
    if change is None and nav is not None and prev:
        change = nav / prev - 1.0
    return {
        "code": str(code), "name": name or "",
        "nav": nav, "nav_date": nav_date,
        "change_rate": change, "prev_nav": prev,
        "gsz": fv.get("gsz") if fv else None,
        "estimate_change_rate": fv.get("estimate_change_rate") if fv else None,
        "gztime": fv.get("gztime") if fv else None,
        "source": source,
    }


def cached_nav_dates(codes):
    """返回 {code: 最新官方净值日期}，聚合两张缓存（供 /runtime staleness）。"""
    fv = _read_cache(FUNDVAL_PATH)
    off = _read_cache(FUNDOFF_PATH)
    out = {}
    for c in codes or []:
        c = str(c)
        d = None
        if c in fv:
            d = fv[c].get("nav_date")
        if c in off and off[c].get("nav_date") and (d is None or off[c]["nav_date"] > d):
            d = off[c]["nav_date"]
        if d:
            out[c] = d
    return out


def eastmoney_fund_estimate(code):
    """[兼容保留] 单代码估值快照，映射为旧 fundgz 形态。

    新接口 FundValuationLast；旧 fundgz JSONP 已下线。含 official_nav/
    official_nav_date/estimate_nav/estimate_change_rate/estimate_time/name。
    """
    fv = get_fund_valuation(code, allow_network=True)
    if fv is None:
        return None
    return {
        "code": str(code),
        "name": fv.get("name", ""),
        "official_nav": fv.get("nav"),
        "official_nav_date": fv.get("nav_date"),
        "estimate_nav": fv.get("gsz"),
        "estimate_change_rate": fv.get("estimate_change_rate"),
        "estimate_time": fv.get("gztime"),
    }


def _html_text(fragment):
    s = re.sub(r"<[^>]+>", "", fragment or "")
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_top_holdings(html_text, topn=10):
    """解析 F10 前十持仓 HTML → [{rank, stock_code, stock_name, weight_pct}]。

    只取第一个 <table>（当期季度），逐行取：序号/股票代码/股票名称/占净值比例%。
    解析失败或无有效行返回 []（不编造）。
    """
    if not html_text:
        return []
    m = re.search(r'content:"(.*?)",arryear', html_text, re.S)
    content = m.group(1) if m else html_text
    content = content.replace('\\"', '"')
    tm = re.search(r"<table[^>]*>(.*?)</table>", content, re.S)
    table = tm.group(1) if tm else content
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 4:
            continue
        try:
            rank = int(_html_text(tds[0]))
        except ValueError:
            continue
        cm = re.search(r"(\d{5,6})", _html_text(tds[1]))
        if not cm:
            continue
        name = _html_text(tds[2])
        weight = None
        for cell in tds[3:]:
            wm = re.match(r"^(\d+(?:\.\d+)?)%$", _html_text(cell))
            if wm:
                weight = float(wm.group(1))
                break
        if weight is None:
            continue
        rows.append({"rank": rank, "stock_code": cm.group(1),
                     "stock_name": name, "weight_pct": weight})
        if len(rows) >= topn:
            break
    return rows


def fetch_top_holdings(code, allow_network=True, topn=10):
    """抓取并解析单只基金 F10 前 N 大持仓。返回 (rows, report_date, source_url)。

    topn：默认 10；R2-02 起支持 20（topline 参数直传上游）。
    失败返回 ([], None, url) —— 由调用方按不可得处理（诚实降级，不编造）。
    """
    topn = int(topn or 10)
    url = F10_HOLD_URL % (code, topn)
    if not allow_network:
        return [], None, url
    raw = http_get(url, headers={"Referer": F10_HOLD_REFERER % code})
    if raw is None:
        settings.record_source("eastmoney", False, note="f10 unreachable")
        return [], None, url
    text = raw.decode("utf-8", "replace")
    if "股票代码" not in text:
        text = raw.decode("gbk", "replace")
    rows = parse_top_holdings(text, topn=topn)
    dm = re.search(r"截止至：<font[^>]*>(\d{4}-\d{2}-\d{2})</font>", text)
    report_date = dm.group(1) if dm else None
    if rows:
        settings.record_source("eastmoney", True, note="f10 jjcc top%d" % topn)
    else:
        settings.record_source("eastmoney", False, note="f10 parse empty")
    return rows, report_date, url


def eastmoney_top_holdings(code, allow_network=True, force=False, topline=20):
    """前 N 大重仓（F10 jjcc）+ 个股实时涨跌，供主动基金重仓加权估值。

    数据源：
    - 持仓：天天基金 F10 `FundArchivesDatas.aspx?type=jjcc&code=<code>&topline=<N>`
      （HTML，含股票代码/名称/占净值比例%；季度披露，30 天缓存）。
      R2-02：`topline` 参数默认启用 20；缓存文件记录 `top_n`，若缓存 `top_n` 低于请求值
      且缓存过期 → 重抓；重抓失败按可得旧缓存 + 如实标注 `top_n`（禁止静默降档，N-2）。
    - 个股实时：腾讯 `qt.gtimg.cn/q=<sh|sz|hk><code>` 批量一次请求（5s 超时）；
      腾讯失败 → 新浪批量兜底（仅 6 位 A 股，R2-17）；美股字母代码不解析，
      计入 `excluded_count` 与覆盖缺口（不编造）。
    返回 {code, report_date, fetched_at, source, top_n, holdings:[{rank, stock_code,
    stock_name, weight, weight_pct, price, prev_close, day_change}]}；持仓不可得返回 None。
    """
    code = str(code)
    topline = int(topline or 20)
    if not os.path.isdir(HOLD_DIR):
        os.makedirs(HOLD_DIR)
    path = os.path.join(HOLD_DIR, "%s.json" % code)
    cached = _read_cache(path)
    has_cache = bool(cached.get("holdings"))
    cached_top_n = int(cached.get("top_n") or len(cached.get("holdings") or []) or 0)
    expired = _age_sec(cached.get("fetched_at")) > HOLD_CACHE_TTL_SEC
    # 需重抓：无缓存/force/过期/缓存档位低于请求档位且已过期（N-2：不得静默降档）
    need = force or not has_cache or expired
    if need and allow_network:
        rows, rdate, url = fetch_top_holdings(code, allow_network=True, topn=topline)
        if rows:
            cached = {
                "code": code, "report_date": rdate, "source": url,
                "fetched_at": _now_ts(), "top_n": topline,
                "holdings": [{
                    "rank": r["rank"], "stock_code": r["stock_code"],
                    "stock_name": r["stock_name"], "weight_pct": r["weight_pct"],
                } for r in rows],
            }
            _write_cache(path, cached)
            has_cache = True
            cached_top_n = topline
    if not has_cache:
        return None
    holdings = cached.get("holdings") or []
    quotes = {}
    if allow_network:
        tradeable = [str(r.get("stock_code")) for r in holdings
                     if tencent_symbol(r.get("stock_code"))]
        if tradeable:
            try:
                quotes = tencent_rt_quotes(tradeable)
            except Exception:  # noqa: BLE001 - 报价失败按 null，不编造
                quotes = {}
            if not quotes:
                # R2-17：腾讯失败 → 新浪批量兜底（仅 6 位 A 股；双失败落既有降级）
                try:
                    quotes = sina_rt_quotes(tradeable)
                except Exception:  # noqa: BLE001
                    quotes = {}
    out_rows = []
    for r in holdings:
        q = quotes.get(str(r.get("stock_code"))) or {}
        out_rows.append({
            "rank": r.get("rank"),
            "stock_code": r.get("stock_code"),
            "stock_name": r.get("stock_name"),
            "weight": r.get("weight_pct"),
            "weight_pct": r.get("weight_pct"),
            "price": q.get("price"),
            "prev_close": q.get("prev_close"),
            "day_change": q.get("change_rate"),
        })
    return {
        "code": code,
        "report_date": cached.get("report_date"),
        "fetched_at": cached.get("fetched_at"),
        "source": cached.get("source"),
        # 实际抓取档位（回退旧缓存时如实给旧值；禁止静默降档 N-2）
        "top_n": cached_top_n or len(holdings),
        "holdings": out_rows,
    }


# ---------------- 隔夜参照指数（QDII 双段第二段；R2-03 / ISSUE-ZL-R2-01） ----------------

# 符号映射由后端实测确认（2026-09-12 探测 qt.gtimg.cn：usNDX / usIXIC / hkHSI 均正常）。
# 探测失败即回退单段（overseas_unavailable）——不得编造行情（08-backend-arch-r2 §3.3）。
OVERSEAS_REF_SYMBOLS = {
    "US_NDX": (("usNDX", "纳斯达克100"), ("usIXIC", "纳斯达克")),
    "HK_HSI": (("hkHSI", "恒生指数"),),
}


def _parse_quote_time(t):
    """腾讯行情时间 → (trade_date, close_ts)。失败返回 (None, None)。"""
    t = str(t or "").strip()
    if not t:
        return None, None
    if re.match(r"^\d{14}$", t):
        return ("%s-%s-%s" % (t[0:4], t[4:6], t[6:8]),
                "%s-%s-%s %s:%s:%s" % (t[0:4], t[4:6], t[6:8], t[8:10], t[10:12], t[12:14]))
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{2}):(\d{2}):(\d{2})", t)
    if m:
        d = "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
        return d, "%s %s:%s:%s" % (d, m.group(4), m.group(5), m.group(6))
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})", t)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3)), None
    return None, None


def overseas_ref_quote(market):
    """隔夜参照指数报价（QDII 双段第二段；R2-03）。

    market ∈ {`US_NDX`, `HK_HSI`}（枚举穷举；其余返回 None → 回退单段，不编造）。
    返回 {value, ref_code, ref_name, trade_date, close_ts, source} 或 None。
    单请求 5s 超时、重试 0；成功/失败均 record_source 留痕。
    """
    if market not in OVERSEAS_REF_SYMBOLS:
        return None
    for sym, name in OVERSEAS_REF_SYMBOLS[market]:
        raw = http_get("https://qt.gtimg.cn/q=%s" % sym, retries=0)
        if raw is None:
            settings.record_source("tencent_rt", False, note="overseas ref unreachable")
            return None
        try:
            text = raw.decode("gbk", "replace")
        except Exception:  # noqa: BLE001
            text = raw.decode("utf-8", "replace")
        payload = text.split("=", 1)[1].strip().strip('";') if "=" in text else ""
        parts = payload.split("~")
        try:
            price = float(parts[3])
            prev = float(parts[4])
        except (IndexError, TypeError, ValueError):
            continue
        if prev <= 0:
            continue
        trade_date, close_ts = _parse_quote_time(parts[30] if len(parts) > 30 else "")
        settings.record_source("tencent_rt", True, note="overseas ref %s" % sym)
        return {
            "value": price / prev - 1.0,
            "ref_code": sym,
            "ref_name": name,
            "trade_date": trade_date,
            "close_ts": close_ts,
            "source": "tencent_%s" % market.lower(),
        }
    return None




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
