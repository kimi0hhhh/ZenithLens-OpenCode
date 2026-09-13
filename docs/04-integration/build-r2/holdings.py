# -*- coding: utf-8 -*-
"""持仓读写、导入、CRUD、市值/收益计算。

- 源文件：C:\\Users\\10719\\Desktop\\基金监控项目\\app_data\\funds_data.json（只读，PROJECT_BRIEF §5.3）
- 产品自持：data/holdings.json（原子替换；不改写源文件）
- 字段口径：09-api-contract.md §5.1 / §6.2（金额 2 位、份额 4 位、snake_case）
- 覆盖档位 A/B/C/D 与代理映射见 proxy_map（完整 22 只映射 + 主动基金持仓穿透；
  来源见 14-api-impl-report §0f）。本模块只做读写与持久化，映射/穿透逻辑在 proxy_map.py。
"""

import io
import json
import os
import re
import shutil
from decimal import Decimal, InvalidOperation
from datetime import datetime

import errors
import estimator
import proxy_map

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

# R2-06/R2-24：验证状态四态 + not_applicable（v9.1/R-3）；中文文案由后端产出
VERIFY_STATUS_LABEL = {
    "pending_validation": "待验证",
    "validating": "验证中",
    "validated": "已验证",
    "validation_failed": "验证未通过",
    "not_applicable": "暴露待定",
}
# C→B 验证 / 9 只代理复核结论（INSERT-ONLY；factor_engine.verify_tiers 写入）
TIER_REVIEWS_PATH = os.path.join(DATA_DIR, "review", "tier_reviews.jsonl")
# QDII 领先口径标注（R2-09；仅 QDII 且跨市场代理，其余 null——不显示，不编造）
QDII_LEAD_NOTE = "QDII · 境内代理领先净值 1–2 天"

CODE_RE = re.compile(r"^\d{6}$")

# 代理映射：完整表在 proxy_map.PROXY_MAP（基金代码 -> (代理ETF, 代理名, 档位, 依据, 置信度)）。
# 本模块保留同名只读引用以兼容既有调用；映射/穿透口径见 proxy_map.py 顶部注释。
PROXY_MAP = proxy_map.PROXY_MAP


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
    return proxy_map.derive_tier(code, name)


def _default_verify_status(h):
    """按档位给验证状态默认值（v9.1/R-3）：A/B→validated；C→pending_validation；
    D①（无映射且未穿透）→ not_applicable；D②（降级）→ validation_failed（已有则保留）。"""
    tier = h.get("tier")
    if tier in ("A", "B"):
        return "validated"
    if tier == "C":
        cur = h.get("verify_status")
        return cur if cur in ("pending_validation", "validating") else "pending_validation"
    # D
    if h.get("verify_status") == "validation_failed":
        return "validation_failed"
    return "not_applicable"


def sync_proxy_fields(obj):
    """用 proxy_map（静态映射 + 穿透缓存，不联网）重算全部持仓的 tier/代理字段。

    返回是否有变更。幂等；供 ensure_holdings/导入后调用，把旧 D 档存量数据补齐。
    同时回填 fund_type（主动/指数联接/QDII/其他）与 verify_status（R2-24 四态）。
    - 验证锁定（R2-06/R2-24）：`validation_failed`（降档）与挂档观察行
      （`pending_validation/validating` 且带复查日）不被静态映射覆盖，保证降档/挂档持续生效。
    """
    changed = False
    for h in obj.get("holdings", []):
        locked = (h.get("verify_status") == "validation_failed"
                  or (h.get("verify_status") in ("pending_validation", "validating")
                      and h.get("verify_review_date")))
        if not locked:
            if proxy_map.apply_to_holding(h):
                changed = True
        ft = estimator.classify_fund_type(h.get("name"))
        if h.get("fund_type") != ft:
            h["fund_type"] = ft
            changed = True
        want = _default_verify_status(h)
        if h.get("verify_status") != want:
            h["verify_status"] = want
            changed = True
    return changed


def apply_tier_reviews():
    """把 tier_reviews.jsonl 的最新结论幂等应用到持仓（tier/tier_reason/verify_*）。

    R2-06/R2-24：升 B 后 tier 与信号列同步更新；降档回填 tier_reason；挂档带复查日。
    返回变更字段计数（幂等：重复应用同批结论不再变更）。
    """
    if not os.path.isfile(TIER_REVIEWS_PATH):
        return 0
    try:
        with io.open(TIER_REVIEWS_PATH, "r", encoding="utf-8") as f:
            latest = {}
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("kind") in ("tier_validation", "proxy_review"):
                    latest[str(row.get("code"))] = row
    except (IOError, OSError):
        return 0
    if not latest:
        return 0
    obj = load_holdings()
    changed = 0
    for h in obj.get("holdings", []):
        r = latest.get(str(h.get("code")))
        if not r:
            continue
        updates = {
            "tier": r.get("tier_after") or h.get("tier"),
            "verify_status": r.get("verify_status") or h.get("verify_status"),
            "verify_batch_id": r.get("batch_id"),
            "verify_note": r.get("note"),
            "verify_review_date": r.get("review_date"),
        }
        if r.get("verdict") in ("pass", "downgrade"):
            updates["tier_reason"] = r.get("reason") or h.get("tier_reason")
        for k, v in updates.items():
            if h.get(k) != v:
                h[k] = v
                changed += 1
    if changed:
        save_holdings(obj)
    return changed


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
        r = proxy_map.resolve(code, name)
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
            "fund_type": estimator.classify_fund_type(name),
            "tier": r["tier"],
            "shares": float(shares.quantize(Decimal("0.0001"))),
            "cost_amount": _f2(cost_amount),
            "confirm_days": int(rec.get("confirm_days", 1) or 1),
            "proxy_code": r["proxy_code"],
            "proxy_name": r["proxy_name"],
            "tier_reason": r["tier_reason"],
            "penetration_trace": r["penetration_trace"],
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
    """主源 = `data/holdings.json`（产品自持；R2-15）。

    缺失时尝试一次外部导入源；外部源也不可用 → 返回空态 + 可读提示（不再抛 E_IO 堆栈）。
    """
    if not os.path.isfile(HOLDINGS_PATH):
        try:
            import_from_source("replace")
        except errors.ApiError as e:
            if e.code != errors.E_IO:
                raise
            # R2-15：主源缺失且外部导入源不可用 → 空态（可读提示）
            save_holdings({
                "as_of": _now_date(), "source": None, "imported_at": _now_iso(),
                "holdings": [],
                "hint": "主源 data/holdings.json 缺失且外部导入源不可用；"
                        "请在设置页用 CSV/手工录入导入持仓。",
            })
    obj = load_holdings()
    # 存量数据补齐：旧 D 档按完整映射 + 穿透缓存重算（幂等、不联网）。
    if sync_proxy_fields(obj):
        save_holdings(obj)
    return obj


def main_source_status():
    """产品自持主源状态（R2-15；contract §3.11 main_source）。

    R2-D2（§8.2）：`path` 返回**契约字面相对标识** `data/holdings.json`
    （展示化标识；内部文件操作仍用绝对路径 HOLDINGS_PATH）。
    """
    info = {"path": "data/holdings.json", "exists": os.path.isfile(HOLDINGS_PATH),
            "modified_at": None, "count": 0, "readonly": False}
    if info["exists"]:
        info["modified_at"] = (datetime.fromtimestamp(os.path.getmtime(HOLDINGS_PATH))
                               .astimezone().replace(microsecond=0).isoformat())
        try:
            obj = _read_json(HOLDINGS_PATH)
            info["count"] = len(obj.get("holdings") or []) if isinstance(obj, dict) else 0
        except (IOError, OSError, ValueError):
            info["count"] = 0
    return info


def import_source_status():
    """可选外部导入源状态：(available, disabled_reason)（R2-15；contract §3.11）。"""
    path = PRIMARY_PATH
    if not os.path.isfile(path):
        return False, "源文件不存在：%s；可用 CSV/手工录入" % path
    try:
        _read_json(path)
    except (IOError, OSError, ValueError):
        return False, "源文件不可读或不是合法 JSON：%s；可用 CSV/手工录入" % path
    return True, None


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
    r = proxy_map.resolve(code, name)
    tier = payload.get("tier") or r["tier"]
    h = {
        "code": code,
        "name": name,
        "group": group,
        "fund_type": estimator.classify_fund_type(name),
        "tier": tier,
        "shares": float(shares.quantize(Decimal("0.0001"))),
        "cost_amount": _f2(cost),
        "confirm_days": int(payload.get("confirm_days", 1)),
        "proxy_code": payload.get("proxy_code", r["proxy_code"]),
        "proxy_name": r["proxy_name"] if payload.get("proxy_code") is None else None,
        "tier_reason": r["tier_reason"] if payload.get("tier") is None else "手工指定档位",
        "penetration_trace": r["penetration_trace"],
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
