# -*- coding: utf-8 -*-
"""设置与数据源健康。

- 设置结构：docs/01-architecture/09-api-contract.md §5.16（Settings）
- 数据源健康：§5.17（DataSourceHealth），枚举 data_source_id 固定 4 项
- API Key 只落本地、永不回传（契约 §6.10）；温度固定 0、输出格式固定 json、mode 固定 shadow
"""

import copy
import io
import json
import os
import re
import time
from datetime import datetime, timedelta

import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
HEALTH_PATH = os.path.join(DATA_DIR, "health.json")
# R2-18：数据源事件日志（append-only；成功/失败均记）{at, source_id, ok, latency_ms, note}
HEALTH_LOG_PATH = os.path.join(DATA_DIR, "health-log.jsonl")
KEY_PATH = os.path.join(DATA_DIR, "llm_key.txt")

FAIL_WINDOW_DAYS = 7        # 展示口径：近 7 个自然日（N-3）
RECENT_FAIL_LIMIT = 10      # recent_failures 最近 ≤10 条

DATA_SOURCE_IDS = ("tencent_kline", "tencent_rt", "eastmoney", "sina_rt")
DATA_SOURCE_LABELS = {
    "tencent_kline": "腾讯日K",
    "tencent_rt": "腾讯实时",
    "eastmoney": "天天基金",
    "sina_rt": "新浪实时",
}

# 固定值（契约 §5.16）
FIXED_TEMPERATURE = 0
FIXED_OUTPUT_FORMAT = "json"
FIXED_MODE = "shadow"
FIXED_THEME = "light"


def _now_iso():
    # Asia/Shanghai 本地时间，ISO 8601 带偏移，秒级
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _read_json(path, default):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def _write_json_atomic(path, obj):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


DEFAULT_SETTINGS = {
    "privacy": {"masked": False, "mask_holdings_only": False},
    "llm": {
        "enabled": False,
        "provider": "deepseek",
        # v5 BLOCK-2：base_url 为可编辑字段，缺省空串（非 null），GET 回传 / PUT 可写
        "base_url": "",
        "model": "",
        "temperature": FIXED_TEMPERATURE,
        "output_format": FIXED_OUTPUT_FORMAT,
        "mode": FIXED_MODE,
    },
    "port": 8791,
    "auto_refresh": True,
    "refresh_interval_sec": 300,
    "theme": FIXED_THEME,
}

LLM_PROVIDERS = ("deepseek", "qwen", "moonshot", "custom")

# v5 BLOCK-2：非空 base_url 须匹配 http(s):// + 主机名（契约 §5.16/§6.10）
BASE_URL_RE = re.compile(r"^https?://.+")


def _key_is_set():
    return os.path.isfile(KEY_PATH) and os.path.getsize(KEY_PATH) > 0


def _load_raw():
    raw = _read_json(SETTINGS_PATH, None)
    if not isinstance(raw, dict):
        # 深拷贝默认值，避免就地修改污染模块级 DEFAULT_SETTINGS（跨调用泄漏）
        return copy.deepcopy(DEFAULT_SETTINGS), True
    return raw, False


def get_settings():
    """返回可对外回传的 Settings（绝不含 api_key 明文）。"""
    raw, is_default = _load_raw()
    priv = raw.get("privacy", {}) if isinstance(raw.get("privacy"), dict) else {}
    llm = raw.get("llm", {}) if isinstance(raw.get("llm"), dict) else {}
    out = {
        "privacy": {
            "masked": bool(priv.get("masked", False)),
            "mask_holdings_only": bool(priv.get("mask_holdings_only", False)),
        },
        "llm": {
            "enabled": bool(llm.get("enabled", False)),
            "provider": llm.get("provider", "deepseek"),
            # v5 BLOCK-2：未配置回 ""（空串，非 null），不得静默丢弃
            "base_url": llm.get("base_url") if isinstance(llm.get("base_url"), str) else "",
            "model": llm.get("model", ""),
            "api_key_set": _key_is_set(),
            "temperature": FIXED_TEMPERATURE,
            "output_format": FIXED_OUTPUT_FORMAT,
            "mode": FIXED_MODE,
        },
        "port": int(raw.get("port", 8791)),
        "auto_refresh": bool(raw.get("auto_refresh", True)),
        "refresh_interval_sec": int(raw.get("refresh_interval_sec", 300)),
        "theme": FIXED_THEME,
        "is_default": bool(is_default),
    }
    return out


def update_settings(patch):
    """全量覆盖式保存（未传字段保持原值）。校验固定值。"""
    if not isinstance(patch, dict):
        raise errors.ApiError(errors.E_VALIDATION, "请求体必须是对象",
                              {"body": "not an object"})
    raw, _ = _load_raw()
    detail = {}

    if "privacy" in patch:
        p = patch["privacy"]
        if not isinstance(p, dict):
            detail["privacy"] = "must be object"
        else:
            raw.setdefault("privacy", {})
            if "masked" in p:
                raw["privacy"]["masked"] = bool(p["masked"])
            if "mask_holdings_only" in p:
                raw["privacy"]["mask_holdings_only"] = bool(p["mask_holdings_only"])

    if "llm" in patch:
        llm = patch["llm"]
        if not isinstance(llm, dict):
            detail["llm"] = "must be object"
        else:
            raw.setdefault("llm", {})
            if "enabled" in llm:
                raw["llm"]["enabled"] = bool(llm["enabled"])
            if "provider" in llm:
                if llm["provider"] not in LLM_PROVIDERS:
                    detail["llm.provider"] = "must be one of %s" % (list(LLM_PROVIDERS),)
                else:
                    raw["llm"]["provider"] = llm["provider"]
            # v5 BLOCK-2：base_url 落盘（空串合法=清除）；非空必须是合法 URL，否则 E_VALIDATION
            if "base_url" in llm:
                bu = llm["base_url"]
                if bu is None or bu == "":
                    raw["llm"]["base_url"] = ""
                elif not isinstance(bu, str) or not BASE_URL_RE.match(bu):
                    detail["llm.base_url"] = "must match ^https?://.+ when non-empty"
                else:
                    raw["llm"]["base_url"] = bu
            if "model" in llm:
                raw["llm"]["model"] = str(llm["model"])
            if "temperature" in llm and llm["temperature"] != FIXED_TEMPERATURE:
                detail["llm.temperature"] = "fixed at 0"
            if "output_format" in llm and llm["output_format"] != FIXED_OUTPUT_FORMAT:
                detail["llm.output_format"] = "fixed at json"
            if "mode" in llm and llm["mode"] != FIXED_MODE:
                detail["llm.mode"] = "readonly shadow"
            # api_key 只落本地，永不回传
            if llm.get("api_key"):
                d = os.path.dirname(KEY_PATH)
                if not os.path.isdir(d):
                    os.makedirs(d)
                with io.open(KEY_PATH, "w", encoding="utf-8") as f:
                    f.write(str(llm["api_key"]))

    if detail:
        raise errors.ApiError(errors.E_VALIDATION, "部分字段校验失败", detail)

    if "port" in patch:
        try:
            raw["port"] = int(patch["port"])
        except (TypeError, ValueError):
            raise errors.ApiError(errors.E_VALIDATION, "port 必须为整数",
                                  {"port": "not int"})
    if "auto_refresh" in patch:
        raw["auto_refresh"] = bool(patch["auto_refresh"])
    if "refresh_interval_sec" in patch:
        try:
            raw["refresh_interval_sec"] = int(patch["refresh_interval_sec"])
        except (TypeError, ValueError):
            raise errors.ApiError(errors.E_VALIDATION, "refresh_interval_sec 必须为整数",
                                  {"refresh_interval_sec": "not int"})

    _write_json_atomic(SETTINGS_PATH, raw)
    return get_settings()


# ---------------- 数据源健康（R2-18：事件日志 + 失败窗口口径） ----------------

_DEFAULT_HEALTH = {
    sid: {
        "source_id": sid,
        "label": DATA_SOURCE_LABELS[sid],
        "status": "unchecked",
        "last_ok_at": None,
        "fail_count": 0,
        "latency_ms": None,
        "note": "",
    }
    for sid in DATA_SOURCE_IDS
}


def _read_health_events(source_id=None):
    rows = []
    if not os.path.isfile(HEALTH_LOG_PATH):
        return rows
    try:
        with io.open(HEALTH_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if source_id is not None and row.get("source_id") != source_id:
                    continue
                rows.append(row)
    except (IOError, OSError):
        return []
    return rows


def _parse_at(at, ref):
    try:
        t = datetime.fromisoformat(str(at))
    except (ValueError, TypeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=ref.tzinfo)
    return t


def _fail_window(events, days=FAIL_WINDOW_DAYS):
    """近 `days` 自然日内的失败事件（按时间窗滚动；成功不抹除窗口内历史）。"""
    now = datetime.now().astimezone()
    cutoff = now - timedelta(days=days)
    out = []
    for e in events:
        if e.get("ok"):
            continue
        t = _parse_at(e.get("at"), now)
        if t is not None and t >= cutoff:
            out.append(e)
    return out


def _window_status(events):
    """三态由失败窗口驱动（旧 fail_count 累计值不得再作当前状态）。"""
    if not events:
        return None
    fails = _fail_window(events)
    last = events[-1]
    if last.get("ok"):
        return "ok"
    return "bad" if len(fails) >= 3 else "warn"


# ---------------- 新浪源 (b) 降级标注（10-r2 §2 裁定③ / 08-r2 §6.3 加严②） ----------------

SINA_DEGRADE_MARK = "仅探测·非主链"
SINA_DEGRADE_MIN_FAILS = 3


def _sina_degraded(events, last_ok_at):
    """新浪 (b) 切换判定：长期不可用 → 转「仅探测·非主链」并回填健康页 note。

    触发（任一命中）：
    1. 连续失败 ≥3（事件尾部连续 `ok=false`）；
    2. 近 7 自然日失败 ≥3 次（聚合口径；适配层未捕获 HTTP 状态码，
       「4xx 持续 7 天」以本可测化聚合近似——不区分 4xx 与网络失败）；
    3. 最近事件失败，且距最近成功 ≥7 日（无成功记录时按首次失败起算）。
    返回 (degraded, reason)；恢复（条件均不满足）时自动摘除标注。
    """
    events = [e for e in (events or [])]
    if not events:
        return False, None
    streak = 0
    for e in reversed(events):
        if e.get("ok"):
            break
        streak += 1
    if streak >= SINA_DEGRADE_MIN_FAILS:
        return True, "连续失败 %d 次" % streak
    fails = _fail_window(events)
    if len(fails) >= SINA_DEGRADE_MIN_FAILS:
        return True, "近 %d 日失败 %d 次" % (FAIL_WINDOW_DAYS, len(fails))
    if not events[-1].get("ok"):
        now = datetime.now().astimezone()
        if last_ok_at:
            t = _parse_at(last_ok_at, now)
            if t is not None and (now - t).days >= FAIL_WINDOW_DAYS:
                return True, "自 %s 起无成功（≥%d 日）" % (
                    str(last_ok_at)[:10], FAIL_WINDOW_DAYS)
        else:
            t0 = _parse_at(events[0].get("at"), now)
            if t0 is not None and (now - t0).days >= FAIL_WINDOW_DAYS:
                return True, "无成功记录且失败持续 ≥%d 日" % FAIL_WINDOW_DAYS
    return False, None


def _strip_sina_mark(note):
    """去掉既有降级标注，返回原始 note（恢复/再标注时保证原因随实测刷新）。"""
    note = note or ""
    pos = note.find(SINA_DEGRADE_MARK)
    if pos < 0:
        return note
    tail = note[pos:]
    if "；" in tail:
        return tail.split("；", 1)[1]
    return ""


def _annotate_sina_note(rec, events):
    """把 (b) 标注回填到既有 `note` 字段（读写两层共用；不改契约字段）。

    - 标注随 7 日窗滚动自然衰减；条件不再满足时摘除（保留原始 note）；
    - 已带标注时按当前实测结果刷新原因文案。
    """
    orig = _strip_sina_mark(rec.get("note"))
    degraded, reason = _sina_degraded(events, rec.get("last_ok_at"))
    if not degraded:
        rec["note"] = orig
        return rec
    ann = "%s（%s）" % (SINA_DEGRADE_MARK, reason)
    rec["note"] = ("%s；%s" % (ann, orig)) if orig else ann
    return rec


def _append_health_event(source_id, ok, latency_ms=None, note=""):
    try:
        d = os.path.dirname(HEALTH_LOG_PATH)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        row = {"at": _now_iso(), "source_id": source_id, "ok": bool(ok),
               "latency_ms": int(latency_ms) if latency_ms is not None else None,
               "note": note or ""}
        with io.open(HEALTH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        pass


def get_health():
    raw = _read_json(HEALTH_PATH, {})
    out = []
    for sid in DATA_SOURCE_IDS:
        rec = dict(_DEFAULT_HEALTH[sid])
        if isinstance(raw, dict) and isinstance(raw.get(sid), dict):
            rec.update(raw[sid])
            rec["source_id"] = sid
            rec["label"] = DATA_SOURCE_LABELS[sid]
        events = _read_health_events(sid)
        fails = _fail_window(events)
        recent = list(reversed(fails))[:RECENT_FAIL_LIMIT]
        rec["fail_window_7d"] = len(fails)
        rec["fail_window_days"] = FAIL_WINDOW_DAYS
        rec["recent_failures"] = [{"at": e.get("at"), "note": e.get("note") or ""}
                                  for e in recent]
        status = _window_status(events)
        if status is not None:
            rec["status"] = status
        elif rec.get("last_ok_at"):
            # 迁移：无事件日志时以最近一次成功为准；旧 fail_count 累计值不作当前状态
            rec["status"] = "ok"
        else:
            rec["status"] = "unchecked"
        # S2（b）路线：新浪长期不可用 → 既有 `note` 字段回填「仅探测·非主链」标注
        # （不改契约字段；恢复/条件衰减后自动摘除，原因随实测刷新）
        if sid == "sina_rt":
            _annotate_sina_note(rec, events)
        out.append(rec)
    return out


def record_source(source_id, ok, latency_ms=None, note=""):
    if source_id not in DATA_SOURCE_IDS:
        return
    raw = _read_json(HEALTH_PATH, {})
    if not isinstance(raw, dict):
        raw = {}
    rec = raw.get(source_id) or dict(_DEFAULT_HEALTH[source_id])
    if ok:
        rec["status"] = "ok"
        rec["last_ok_at"] = _now_iso()
        rec["latency_ms"] = int(latency_ms) if latency_ms is not None else None
        rec["note"] = note or ""
    else:
        # fail_count 保留为累计（审计用；展示口径改读 fail_window_7d）
        rec["fail_count"] = int(rec.get("fail_count", 0)) + 1
        fails = _fail_window(_read_health_events(source_id))
        rec["status"] = "bad" if len(fails) + 1 >= 3 else "warn"
        rec["latency_ms"] = int(latency_ms) if latency_ms is not None else rec.get("latency_ms")
        rec["note"] = note or ""
    rec["source_id"] = source_id
    rec["label"] = DATA_SOURCE_LABELS[source_id]
    # R2-18：成功/失败均追加事件日志（append-only；成功不抹除窗口内历史）
    _append_health_event(source_id, ok, latency_ms, note)
    # S2：写盘前按含本次事件的实测结果回填 (b) 标注（随条件衰减自动摘除）
    if source_id == "sina_rt":
        _annotate_sina_note(rec, _read_health_events(source_id))
    raw[source_id] = rec
    try:
        _write_json_atomic(HEALTH_PATH, raw)
    except (IOError, OSError):
        pass


def probe(source_id):
    """立即探测一个源；返回更新后的 DataSourceHealth 记录。"""
    import estimator  # 延迟导入避免循环
    if source_id not in DATA_SOURCE_IDS:
        raise errors.ApiError(errors.E_VALIDATION, "未知数据源",
                              {"source_id": "must be one of %s" % (list(DATA_SOURCE_IDS),)})
    t0 = time.time()
    ok = False
    note = ""
    try:
        ok = estimator.probe_source(source_id)
    except Exception as e:  # 网络异常不裸抛
        note = str(e)[:120]
        ok = False
    latency = int((time.time() - t0) * 1000)
    record_source(source_id, ok, latency, note)
    for rec in get_health():
        if rec["source_id"] == source_id:
            return rec
    return dict(_DEFAULT_HEALTH[source_id])
