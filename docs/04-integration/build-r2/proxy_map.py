# -*- coding: utf-8 -*-
"""代理映射表 + 主动基金持仓穿透（D 档压缩）。

来源与口径
- 代理映射（产品领域数据，非代码）：主 Agent 派发 OC-COV-BE 参考映射（2026-09-12）。
  档位语义（09-api-contract v7 §5.19 `coverage_tier`）：
    A=行业 ETF 直接对应（引擎可直接产出）；B=代理 ETF 已映射且可取到日线；
    C=代理为拟用/近似或映射置信度低；D=无映射且未穿透。
- 持仓穿透数据源：天天基金 F10 前十持仓
  `https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=<code>&topline=10`
  （GBK HTML；需 UA+Referer，实测 200）。个股→行业 ETF 映射见 STOCK_ETF_MAP。
- 纯标准库：urllib / re / json / os / datetime；外部调用 5s 超时、重试 1。
- 诚实优先：穿透不到的仍留 D 并注明原因；禁止为提高覆盖率编造代理；穿透结果标注「待验证」。
"""

import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PROXY_CACHE_DIR = os.path.join(ROOT, "data", "cache", "proxy")
PENETRATION_PATH = os.path.join(PROXY_CACHE_DIR, "penetration.json")

HTTP_TIMEOUT = 5.0
HTTP_RETRIES = 1
F10_URL = ("https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
           "?type=jjcc&code=%s&topline=10")
F10_REFERER = "https://fundf10.eastmoney.com/ccmx_%s.html"

# 基金代码 -> (代理ETF, 代理名, 档位, 依据, 置信度)
# A：行业 ETF 直接对应；B：代理 ETF 已映射且可取到日线；C：拟用/近似/低置信。
PROXY_MAP = {
    # ---- A 行业 ETF 直接对应 ----
    "014320": ("512480", "半导体ETF国联安", "A",
               "主动基金重仓半导体（存储/设计），与半导体ETF同向", "high"),
    "013566": ("512660", "军工ETF国泰", "A",
               "主动基金军工安全暴露与军工ETF同向", "high"),
    # ---- B 代理 ETF 已映射且可取到日线 ----
    "000217": ("518880", "黄金ETF华安", "B",
               "黄金ETF联接，跟踪同一黄金现货合约", "high"),
    "002963": ("518880", "黄金ETF华安", "B",
               "黄金ETF联接，跟踪同一黄金现货合约", "high"),
    "012922": ("513100", "纳指ETF国泰", "B",
               "全球成长精选重仓美股科技，纳指ETF代理", "mid"),
    "016665": ("513100", "纳指ETF国泰", "B",
               "全球高端制造重仓美股科技制造，纳指ETF代理", "mid"),
    "024239": ("513100", "纳指ETF国泰", "B",
               "全球科技先锋(QDII)重仓美股科技，纳指ETF代理", "mid"),
    "017412": ("588300", "科创创业50ETF招商", "B",
               "中证科创创业50指数增强，对应ETF", "high"),
    "008087": ("515880", "通信ETF国泰", "B",
               "中证5G通信主题联接，通信ETF代理", "mid"),
    "025857": ("561560", "电力ETF华泰柏瑞", "B",
               "中证电网设备主题联接，电力/电网设备ETF代理", "mid"),
    "017193": ("512400", "有色金属ETF南方", "B",
               "中证工业有色金属主题联接，对应ETF", "high"),
    "014881": ("562500", "机器人ETF华夏", "B",
               "中证机器人指数联接，对应ETF", "high"),
    "011840": ("515070", "人工智能ETF华夏", "B",
               "中证人工智能主题联接，对应ETF", "high"),
    "018897": ("561600", "消费电子ETF平安", "B",
               "中证消费电子主题联接，对应ETF", "high"),
    "016786": ("512100", "中证1000ETF南方", "B",
               "中证1000指数增强，对应ETF", "high"),
    # ---- C 拟用/近似/低置信 ----
    "022485": ("159352", "A500ETF南方", "C",
               "中证A500指数增强，代理ETF（拟用，待走前验证）", "mid"),
    "021662": ("159920", "恒生ETF华夏", "C",
               "亚洲机会(QDII)，恒生ETF近似（拟用，跨市场近似）", "low"),
    "457001": ("159920", "恒生ETF华夏", "C",
               "亚洲机会(QDII)，恒生ETF近似（拟用，跨市场近似）", "low"),
    "163208": ("162411", "华宝油气LOF", "C",
               "油气能源(QDII-FOF-LOF)，华宝油气代理（拟用，待验证）", "low"),
    "018957": ("515880", "通信ETF国泰", "C",
               "CPO/光模块暴露，通信ETF近似（光模块在通信ETF内，待验证）", "low"),
}

# 无静态映射、需持仓穿透的主动全市场基金（穿透成功→C，失败→D）
PENETRATION_TARGETS = ("025500", "021528")

# 个股代码 -> (ETF代码, ETF名, 主题)  仅覆盖需穿透基金前十主要标的（可扩充）
STOCK_ETF_MAP = {
    # 半导体/存储（025500 前十）
    "603986": ("512480", "半导体ETF国联安", "半导体（兆易创新）"),
    "300475": ("512480", "半导体ETF国联安", "半导体（香农芯创）"),
    "301308": ("512480", "半导体ETF国联安", "半导体（江波龙）"),
    "300223": ("512480", "半导体ETF国联安", "半导体（北京君正）"),
    "688525": ("512480", "半导体ETF国联安", "半导体（佰维存储）"),
    "001309": ("512480", "半导体ETF国联安", "半导体（德明利）"),
    "688766": ("512480", "半导体ETF国联安", "半导体（普冉股份）"),
    "688008": ("512480", "半导体ETF国联安", "半导体（澜起科技）"),
    "688110": ("512480", "半导体ETF国联安", "半导体（东芯股份）"),
    "688123": ("512480", "半导体ETF国联安", "半导体（聚辰股份）"),
    # CPO/光模块/PCB（021528 前十）
    "300502": ("515880", "通信ETF国泰", "光模块/CPO（新易盛）"),
    "688498": ("515880", "通信ETF国泰", "光芯片（源杰科技）"),
    "688519": ("515880", "通信ETF国泰", "覆铜板/PCB（南亚新材）"),
    "301511": ("515880", "通信ETF国泰", "铜箔/PCB（德福科技）"),
    "301377": ("515880", "通信ETF国泰", "PCB钻针（鼎泰高科）"),
    "301200": ("515880", "通信ETF国泰", "PCB设备（大族数控）"),
    "603186": ("515880", "通信ETF国泰", "覆铜板（华正新材）"),
    # 电子元件 -> 消费电子
    "300408": ("561600", "消费电子ETF平安", "电子陶瓷（三环集团）"),
    "000636": ("561600", "消费电子ETF平安", "MLCC（风华高科）"),
    # 金属粉体 -> 有色（近似）
    "605376": ("512400", "有色金属ETF南方", "金属粉体（博迁新材，近似）"),
}

COVERAGE_TIERS = ("A", "B", "C", "D")


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


# ---------------- F10 抓取与解析 ----------------

def _http_get(url, referer=None, timeout=HTTP_TIMEOUT, retries=HTTP_RETRIES):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
               "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    last = None
    for _ in range(retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - 适配层统一兜住
            last = e
            time.sleep(0.15)
    _ = last
    return None


def _text(fragment):
    s = re.sub(r"<[^>]+>", "", fragment or "")
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&lt;", "<").replace("&gt;", ">").
         replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_f10_holdings(html_text, topn=10):
    """[T-05 合一·R2] F10 持仓解析唯一实现 = `estimator.parse_top_holdings`。

    本函数保留为兼容别名（既有调用不破），内部委托 estimator 版；
    禁止在此恢复第二份解析实现（08-backend-arch-r2 §3.2 / T-05）。
    """
    import estimator
    return estimator.parse_top_holdings(html_text, topn=topn)


def fetch_f10_holdings(code, allow_network=True):
    """抓取并解析单只基金 F10 前十持仓。返回 (rows, report_date, source_url)。

    失败返回 ([], None, url)，由调用方决定留 D。
    """
    url = F10_URL % code
    if not allow_network:
        return [], None, url
    raw = _http_get(url, referer=F10_REFERER % code)
    if raw is None:
        return [], None, url
    # 天天基金 F10 实测为 UTF-8；兼容历史 GBK 页面回退。
    text = raw.decode("utf-8", "replace")
    if "股票代码" not in text:
        text = raw.decode("gbk", "replace")
    rows = parse_f10_holdings(text)
    dm = re.search(r"截止至：<font[^>]*>(\d{4}-\d{2}-\d{2})</font>", text)
    report_date = dm.group(1) if dm else None
    return rows, report_date, url


# ---------------- 穿透计算 ----------------

def penetrate_rows(code, rows, report_date=None, source_url=None):
    """把前十持仓按权重映射到行业 ETF，返回穿透记录（tier=C 或 D）。

    主代理 = 已映射标的中权重合计最高的 ETF；同时给出加权篮子与明细。
    """
    if not rows:
        return _no_proxy(code, "主动全市场基金：F10 前十持仓未取得（未缓存或抓取失败），暴露待定")
    buckets = {}
    mapped = 0.0
    top10 = []
    unmapped = []
    for r in rows:
        etf = STOCK_ETF_MAP.get(r["stock_code"])
        w = r.get("weight_pct") or 0.0
        item = dict(r)
        if etf:
            item["etf_code"] = etf[0]
            item["etf_name"] = etf[1]
            item["theme"] = etf[2]
            mapped += w
            b = buckets.setdefault(etf[0], {"etf_code": etf[0], "etf_name": etf[1],
                                            "weight_pct": 0.0, "stocks": []})
            b["weight_pct"] += w
            b["stocks"].append(r["stock_code"])
        else:
            item["etf_code"] = None
            item["etf_name"] = None
            item["theme"] = None
            unmapped.append({"stock_code": r["stock_code"],
                             "stock_name": r["stock_name"], "weight_pct": w})
        top10.append(item)
    if not buckets:
        # 前十有数据但无标的命中「个股→ETF」映射：仍留 D，但保留明细供审计。
        return {
            "code": code, "tier": "D", "proxy_code": None, "proxy_name": None,
            "tier_reason": "主动全市场基金：前十持仓无标的命中「个股→ETF」映射，暴露待定",
            "confidence": "unknown",
            "penetration_trace": {
                "method": "eastmoney_f10_top10_weighted",
                "source": source_url or (F10_URL % code),
                "report_date": report_date,
                "fetched_at": _now_iso(),
                "top10": top10,
                "basket": [],
                "mapped_weight_pct": 0.0,
                "unmapped": unmapped,
                "proxy": None,
                "proxy_basis": "无标的中「个股→ETF」映射，不构造代理",
                "confidence": "unknown",
                "status": "无映射（待补充个股→ETF 映射）",
            },
        }
    basket = sorted(buckets.values(), key=lambda b: b["weight_pct"], reverse=True)
    for b in basket:
        b["weight_pct"] = round(b["weight_pct"], 2)
    main = basket[0]
    trace = {
        "method": "eastmoney_f10_top10_weighted",
        "source": source_url or (F10_URL % code),
        "report_date": report_date,
        "fetched_at": _now_iso(),
        "top10": top10,
        "basket": basket,
        "mapped_weight_pct": round(mapped, 2),
        "unmapped": unmapped,
        "proxy": main["etf_code"],
        "proxy_basis": "主代理=前十已映射标的中权重合计最高的 ETF（加权篮子见 basket）",
        "confidence": "low",
        "status": "待验证",
    }
    return {
        "code": code,
        "tier": "C",
        "proxy_code": main["etf_code"],
        "proxy_name": main["etf_name"],
        "tier_reason": ("持仓穿透：前十映射权重 %.2f%% → 主代理 %s(%s)（待验证）"
                        % (trace["mapped_weight_pct"], main["etf_name"], main["etf_code"])),
        "confidence": "low",
        "penetration_trace": trace,
    }


def _no_proxy(code, reason):
    return {"code": code, "tier": "D", "proxy_code": None, "proxy_name": None,
            "tier_reason": reason, "confidence": "unknown",
            "penetration_trace": None}


def refresh_penetrations(codes=None, allow_network=True, force=False):
    """抓取并缓存需穿透基金的 F10 记录；返回 {code: record}。网络失败时保留旧缓存。"""
    codes = tuple(codes or PENETRATION_TARGETS)
    cache = load_penetration_cache()
    changed = False
    for code in codes:
        if not force and _cache_fresh(cache.get(code)):
            continue
        rows, rdate, url = fetch_f10_holdings(code, allow_network=allow_network)
        if not rows:
            continue
        rec = penetrate_rows(code, rows, report_date=rdate, source_url=url)
        rec["penetration_trace"]["fetched_at"] = _now_iso()
        cache[code] = rec
        changed = True
    if changed:
        save_penetration_cache(cache)
    return cache


def load_penetration_cache():
    if not os.path.isfile(PENETRATION_PATH):
        return {}
    try:
        with io.open(PENETRATION_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def save_penetration_cache(cache):
    if not os.path.isdir(PROXY_CACHE_DIR):
        os.makedirs(PROXY_CACHE_DIR)
    tmp = PENETRATION_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PENETRATION_PATH)


def _cache_fresh(rec):
    if not rec:
        return False
    ts = (rec.get("penetration_trace") or {}).get("fetched_at")
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts)
        now = datetime.now(t.tzinfo) if t.tzinfo else datetime.now()
        return (now - t).total_seconds() < 24 * 3600
    except (ValueError, TypeError):
        return False


# ---------------- 对外解析 ----------------

def resolve(code, name=None, allow_network=False):
    """返回单只基金的代理解析结果（不触发网络，除非 allow_network）。

    dict: {code, tier, proxy_code, proxy_name, tier_reason, confidence, penetration_trace}
    """
    code = str(code)
    if code in PROXY_MAP:
        p = PROXY_MAP[code]
        return {"code": code, "tier": p[2], "proxy_code": p[0], "proxy_name": p[1],
                "tier_reason": p[3], "confidence": p[4], "penetration_trace": None}
    if code in PENETRATION_TARGETS:
        if allow_network:
            refresh_penetrations([code], allow_network=True)
        rec = load_penetration_cache().get(code)
        if rec:
            return {k: rec.get(k) for k in
                    ("code", "tier", "proxy_code", "proxy_name", "tier_reason",
                     "confidence", "penetration_trace")}
        return _no_proxy(code, "主动全市场基金：F10 持仓穿透未缓存或抓取失败，暴露待定")
    return _no_proxy(code, "无验证代理，暴露待定")


def derive_tier(code, name=None):
    return resolve(code, name)["tier"]


def apply_to_holding(h):
    """就地把解析结果写回持仓 dict（tier/proxy/tier_reason/penetration_trace）。"""
    r = resolve(h.get("code"), h.get("name"))
    changed = False
    for k in ("tier", "proxy_code", "proxy_name", "tier_reason"):
        if h.get(k) != r[k]:
            h[k] = r[k]
            changed = True
    if h.get("penetration_trace") != r["penetration_trace"]:
        h["penetration_trace"] = r["penetration_trace"]
        changed = True
    return changed


def tier_counts(holdings):
    """按档位统计（含占比），用于覆盖度核对。"""
    counts = {t: 0 for t in COVERAGE_TIERS}
    for h in holdings or []:
        t = h.get("tier")
        if t in counts:
            counts[t] += 1
    total = sum(counts.values()) or 0
    ratios = {t: (round(counts[t] / total, 4) if total else None) for t in COVERAGE_TIERS}
    return {"counts": counts, "ratios": ratios, "total": total}
