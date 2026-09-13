# -*- coding: utf-8 -*-
"""设置与数据源健康。

- 设置结构：docs/01-architecture/09-api-contract.md §5.16（Settings）
- 数据源健康：§5.17（DataSourceHealth），枚举 data_source_id 固定 4 项
- API Key 只落本地、永不回传（契约 §6.10）；温度固定 0、输出格式固定 json、mode 固定 shadow
"""

import io
import json
import os
import time
from datetime import datetime

import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
HEALTH_PATH = os.path.join(DATA_DIR, "health.json")
KEY_PATH = os.path.join(DATA_DIR, "llm_key.txt")

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


def _key_is_set():
    return os.path.isfile(KEY_PATH) and os.path.getsize(KEY_PATH) > 0


def _load_raw():
    raw = _read_json(SETTINGS_PATH, None)
    if not isinstance(raw, dict):
        return dict(DEFAULT_SETTINGS), True
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


# ---------------- 数据源健康 ----------------

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


def get_health():
    raw = _read_json(HEALTH_PATH, {})
    out = []
    for sid in DATA_SOURCE_IDS:
        rec = dict(_DEFAULT_HEALTH[sid])
        if isinstance(raw, dict) and isinstance(raw.get(sid), dict):
            rec.update(raw[sid])
            rec["source_id"] = sid
            rec["label"] = DATA_SOURCE_LABELS[sid]
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
        rec["fail_count"] = int(rec.get("fail_count", 0)) + 1
        # 连续失败 >=3 记为 bad，否则 warn（三态判定，PRD F-16）
        rec["status"] = "bad" if rec["fail_count"] >= 3 else "warn"
        rec["latency_ms"] = int(latency_ms) if latency_ms is not None else rec.get("latency_ms")
        rec["note"] = note or ""
    rec["source_id"] = source_id
    rec["label"] = DATA_SOURCE_LABELS[source_id]
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
