# -*- coding: utf-8 -*-
"""持仓读写、导入、CRUD、市值/收益计算。

- 源文件：C:\\Users\\10719\\Desktop\\基金监控项目\\app_data\\funds_data.json（只读，PROJECT_BRIEF §5.3）
- 产品自持：data/holdings.json（原子替换；不改写源文件）
- 字段口径：09-api-contract.md §5.1 / §6.2（金额 2 位、份额 4 位、snake_case）
- 覆盖档位 A/B/C/D 与代理映射见 PROXY_MAP / derive_tier（来源见 14-api-impl-report）
"""

import io
import json
import os
import re
import shutil
from decimal import Decimal, InvalidOperation
from datetime import datetime

import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
HOLDINGS_PATH = os.path.join(DATA_DIR, "holdings.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

PRIMARY_PATH = os.path.join(r"C:\Users\10719\Desktop\基金监控项目\app_data", "funds_data.json")
LEGACY_PATH = os.path.join(r"C:\Users\10719\Desktop\基金监控项目\app_data", "funds_data.json.bak")

HOLDING_GROUPS = {
    "domestic_index": "境内指数",
    "active": "主动",
    "qdii": "QDII",
    "gold": "黄金",
    "other": "其他",
}
COVERAGE_TIERS = ("A", "B", "C", "D")

CODE_RE = re.compile(r"^\d{6}$")

# 代理映射：基金代码 -> (代理ETF代码, 代理名, 档位, 依据)
# 依据：场内同指数/同主题 ETF；QDII 与主动基金本期无验证代理 → D。
# 说明：代理为预测所需的场内日线载体，映射本身为配置（来源 PROJECT_BRIEF §5.1 / 08 §2），
#      未做走前验证，故档位语义为 A=已接入（同指数 ETF 代理）、D=暴露待定。
PROXY_MAP = {
    "000217": ("518880", "黄金ETF", "A", "黄金ETF联接，跟踪同一黄金现货合约"),
    "002963": ("518880", "黄金ETF", "A", "黄金ETF联接，跟踪同一黄金现货合约"),
    "008087": ("515050", "通信ETF", "A", "中证5G通信主题指数对应ETF"),
    "011840": ("515070", "人工智能ETF", "A", "中证人工智能主题指数对应ETF"),
    "014881": ("562500", "机器人ETF", "A", "中证机器人指数对应ETF"),
    "016786": ("512100", "中证1000ETF", "A", "中证1000指数对应ETF"),
    "017193": ("512400", "有色金属ETF", "A", "中证工业有色金属主题指数对应ETF"),
    "017412": ("159781", "科创创业50ETF", "A", "中证科创创业50指数对应ETF"),
    "018897": ("561600", "消费电子ETF", "A", "中证消费电子主题指数对应ETF"),
    "022485": ("512050", "A500ETF", "A", "中证A500指数对应ETF"),
    # 025857 电网设备主题：代理 ETF 代码未确认 → D（暴露待定）
}


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _now_date():
    return datetime.now().strftime("%Y-%m-%d")


def derive_group(name):
    n = name or ""
    if "QDII" in n or "全球" in n or "亚洲" in n or "海外" in n or "油气" in n or "纳指" in n or "标普" in n:
        return "qdii"
    if "黄金" in n:
        return "gold"
    if "ETF" in n or "指数" in n:
        return "domestic_index"
    if "混合" in n or "股票" in n:
        return "active"
    return "other"


def derive_tier(code, name):
    if code in PROXY_MAP:
        return PROXY_MAP[code][2]
    return "D"


def _read_json(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_atomic(path, obj):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _to_dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _f2(v):
    if v is None:
        return None
    return float(Decimal(v).quantize(Decimal("0.01")))


def _f4(v):
    if v is None:
        return None
    return float(Decimal(v).quantize(Decimal("0.0001")))


# ---------------- 导入 ----------------

def import_from_source(mode="replace"):
    if not os.path.isfile(PRIMARY_PATH):
        raise errors.ApiError(errors.E_IO, "源文件不存在或不可读",
                              {"primary_path": PRIMARY_PATH})
    try:
        src = _read_json(PRIMARY_PATH)
    except ValueError:
        raise errors.ApiError(errors.E_PARSE, "源文件不是合法 JSON",
                              {"primary_path": PRIMARY_PATH})
    except (IOError, OSError):
        raise errors.ApiError(errors.E_IO, "读取源文件失败",
                              {"primary_path": PRIMARY_PATH})

    warnings = []
    imported = []
    for code, rec in src.items():
        if not CODE_RE.match(str(code)):
            warnings.append("跳过非 6 位代码：%s" % code)
            continue
        name = rec.get("name", "")
        group = derive_group(name)
        tier = derive_tier(code, name)
        proxy = PROXY_MAP.get(code)
        bought = _to_dec(rec.get("bought", 0)) or Decimal(0)
        sold = _to_dec(rec.get("sold", 0)) or Decimal(0)
        cost_amount = bought - sold
        if cost_amount < 0:
            cost_amount = Decimal(0)
        shares = _to_dec(rec.get("shares", 0)) or Decimal(0)
        navmap = rec.get("navmap") or {}
        imported.append({
            "code": str(code),
            "name": name,
            "group": group,
            "tier": tier,
            "shares": float(shares.quantize(Decimal("0.0001"))),
            "cost_amount": _f2(cost_amount),
            "confirm_days": int(rec.get("confirm_days", 1) or 1),
            "proxy_code": proxy[0] if proxy else None,
            "proxy_name": proxy[1] if proxy else None,
            "tier_reason": proxy[3] if proxy else "无验证代理，暴露待定",
            "nav_history": {d: float(v) for d, v in navmap.items()},
            "source_file": "funds_data.json",
        })

    if mode == "merge":
        existing = {h["code"]: h for h in load_holdings().get("holdings", [])}
        merged = dict(existing)
        for h in imported:
            merged[h["code"]] = h
        final = list(merged.values())
    else:  # replace
        final = imported

    # 导入前备份自持文件
    if os.path.isfile(HOLDINGS_PATH):
        if not os.path.isdir(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy2(HOLDINGS_PATH, os.path.join(BACKUP_DIR, "holdings-%s.json" % stamp))
        except (IOError, OSError):
            warnings.append("备份自持持仓失败（不阻塞导入）")

    _write_atomic(HOLDINGS_PATH, {"as_of": _now_date(), "source": PRIMARY_PATH,
                                  "imported_at": _now_iso(), "holdings": final})
    return {
        "imported_count": len(imported),
        "source": "app_data/funds_data.json",
        "imported_at": _now_iso(),
        "warnings": warnings,
    }


def ensure_holdings():
    if not os.path.isfile(HOLDINGS_PATH):
        import_from_source("replace")
    return load_holdings()


def load_holdings():
    if not os.path.isfile(HOLDINGS_PATH):
        return {"as_of": None, "source": PRIMARY_PATH, "holdings": []}
    try:
        obj = _read_json(HOLDINGS_PATH)
    except (IOError, OSError):
        raise errors.ApiError(errors.E_IO, "读取自持持仓失败", {"path": HOLDINGS_PATH})
    except ValueError:
        raise errors.ApiError(errors.E_PARSE, "自持持仓不是合法 JSON", {"path": HOLDINGS_PATH})
    if not isinstance(obj, dict) or not isinstance(obj.get("holdings"), list):
        return {"as_of": None, "source": PRIMARY_PATH, "holdings": []}
    return obj


def save_holdings(obj):
    _write_atomic(HOLDINGS_PATH, obj)


def get_holding(code):
    for h in load_holdings().get("holdings", []):
        if h["code"] == code:
            return h
    return None


# ---------------- CRUD ----------------

def _validate_payload(payload, code_locked=False):
    detail = {}
    p = payload
    if not isinstance(p, dict):
        raise errors.ApiError(errors.E_VALIDATION, "请求体必须是对象", {"body": "not object"})
    if not code_locked:
        c = str(p.get("code", ""))
        if not CODE_RE.match(c):
            detail["code"] = "must be 6 digits"
    if "name" in p and not str(p.get("name", "")).strip():
        detail["name"] = "must be nonempty"
    if "group" in p and p.get("group") not in HOLDING_GROUPS:
        detail["group"] = "must be one of %s" % (list(HOLDING_GROUPS),)
    if "tier" in p and p.get("tier") not in COVERAGE_TIERS:
        detail["tier"] = "must be one of %s" % (list(COVERAGE_TIERS),)
    if "confirm_days" in p and p.get("confirm_days") not in (1, 2, 3):
        detail["confirm_days"] = "must be 1/2/3"
    for k in ("shares", "cost_amount", "avg_cost"):
        if k in p and p[k] is not None:
            d = _to_dec(p[k])
            if d is None or d < 0:
                detail[k] = "must be >= 0"
    if "proxy_code" in p and p["proxy_code"] is not None:
        if not CODE_RE.match(str(p["proxy_code"])):
            detail["proxy_code"] = "must be 6 digits or null"
    if detail:
        raise errors.ApiError(errors.E_VALIDATION, "部分字段校验失败", detail)
    return detail


def create_holding(payload):
    _validate_payload(payload)
    code = str(payload["code"])
    if get_holding(code) is not None:
        raise errors.ApiError(errors.E_CONFLICT, "该基金代码已存在", {"code": code})
    name = str(payload.get("name", ""))
    shares = _to_dec(payload.get("shares") or 0) or Decimal(0)
    if payload.get("avg_cost") is not None and not payload.get("cost_amount"):
        cost = (_to_dec(payload["avg_cost"]) or Decimal(0)) * shares
    else:
        cost = _to_dec(payload.get("cost_amount") or 0) or Decimal(0)
    group = payload.get("group") or derive_group(name)
    tier = payload.get("tier") or derive_tier(code, name)
    proxy = PROXY_MAP.get(code)
    h = {
        "code": code,
        "name": name,
        "group": group,
        "tier": tier,
        "shares": float(shares.quantize(Decimal("0.0001"))),
        "cost_amount": _f2(cost),
        "confirm_days": int(payload.get("confirm_days", 1)),
        "proxy_code": payload.get("proxy_code", proxy[0] if proxy else None),
        "proxy_name": proxy[1] if proxy else None,
        "tier_reason": proxy[3] if proxy else "手工录入，暴露待定",
        "nav_history": {},
        "source_file": "manual",
    }
    obj = load_holdings()
    obj.setdefault("holdings", []).append(h)
    obj["as_of"] = _now_date()
    save_holdings(obj)
    return h


def update_holding(code, payload):
    _validate_payload(payload, code_locked=True)
    obj = load_holdings()
    target = None
    for h in obj.get("holdings", []):
        if h["code"] == code:
            target = h
            break
    if target is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该基金代码", {"code": code})
    if "name" in payload:
        target["name"] = str(payload["name"])
    if "group" in payload:
        target["group"] = payload["group"]
    if "tier" in payload:
        target["tier"] = payload["tier"]
    if "confirm_days" in payload:
        target["confirm_days"] = int(payload["confirm_days"])
    if "proxy_code" in payload:
        target["proxy_code"] = payload["proxy_code"]
    if "shares" in payload and payload["shares"] is not None:
        target["shares"] = float((_to_dec(payload["shares"]) or Decimal(0)).quantize(Decimal("0.0001")))
    if "avg_cost" in payload and payload["avg_cost"] is not None and not payload.get("cost_amount"):
        shares = _to_dec(target.get("shares") or 0) or Decimal(0)
        target["cost_amount"] = _f2((_to_dec(payload["avg_cost"]) or Decimal(0)) * shares)
    elif "cost_amount" in payload and payload["cost_amount"] is not None:
        target["cost_amount"] = _f2(_to_dec(payload["cost_amount"]) or Decimal(0))
    obj["as_of"] = _now_date()
    save_holdings(obj)
    return target


def delete_holding(code):
    obj = load_holdings()
    before = obj.get("holdings", [])
    after = [h for h in before if h["code"] != code]
    if len(after) == len(before):
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该基金代码", {"code": code})
    obj["holdings"] = after
    save_holdings(obj)
    return {"deleted_code": code}


def transact(code, payload):
    if not isinstance(payload, dict):
        raise errors.ApiError(errors.E_VALIDATION, "请求体必须是对象", {"body": "not object"})
    tx_type = payload.get("tx_type")
    detail = {}
    if tx_type not in ("buy", "sell"):
        detail["tx_type"] = "must be buy/sell"
    shares = _to_dec(payload.get("shares"))
    if shares is None or shares <= 0:
        detail["shares"] = "must be > 0"
    price = _to_dec(payload.get("price"))
    if price is None or price <= 0:
        detail["price"] = "must be > 0"
    if not payload.get("date"):
        detail["date"] = "required"
    fee = _to_dec(payload.get("fee_amount", 0)) or Decimal(0)
    if detail:
        raise errors.ApiError(errors.E_VALIDATION, "部分字段校验失败", detail)

    obj = load_holdings()
    target = None
    for h in obj.get("holdings", []):
        if h["code"] == code:
            target = h
            break
    if target is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该基金代码", {"code": code})

    cur_shares = _to_dec(target.get("shares") or 0) or Decimal(0)
    cur_cost = _to_dec(target.get("cost_amount") or 0) or Decimal(0)
    avg = (cur_cost / cur_shares) if cur_shares > 0 else Decimal(0)

    if tx_type == "buy":
        new_shares = cur_shares + shares
        new_cost = cur_cost + shares * price + fee
    else:  # sell 摊薄成本口径（契约 §6.2）；不含在途申赎
        if shares > cur_shares:
            raise errors.ApiError(errors.E_VALIDATION, "减仓份额超过当前持有份额",
                                  {"shares": "exceeds current"})
        new_shares = cur_shares - shares
        new_cost = cur_cost - shares * avg
        if new_cost < 0:
            new_cost = Decimal(0)

    target["shares"] = float(new_shares.quantize(Decimal("0.0001")))
    target["cost_amount"] = _f2(new_cost)
    obj["as_of"] = _now_date()
    save_holdings(obj)
    return target


# ---------------- 计算辅助 ----------------

def avg_cost_of(h):
    shares = _to_dec(h.get("shares") or 0) or Decimal(0)
    if shares == 0:
        return None
    cost = _to_dec(h.get("cost_amount") or 0) or Decimal(0)
    return cost / shares


def latest_nav(h):
    """从 nav_history 取最新官方净值与上一日净值。返回 (date, nav, prev_nav)。"""
    nh = h.get("nav_history") or {}
    if not nh:
        return None, None, None
    dates = sorted(nh.keys())
    last = dates[-1]
    prev = dates[-2] if len(dates) >= 2 else None
    return last, nh[last], (nh[prev] if prev else None)
