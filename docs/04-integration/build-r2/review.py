# -*- coding: utf-8 -*-
"""复盘成绩组装（R2-11）：`/review/scores` 的深模块实现（唯一对外函数 `scores`）。

- `data_kind=backtest`（默认）：生产配置（E1/E3→DDSM→双否决→出口）作为内置因子
  `production` 经 `factor_engine.evaluate` 六窗走前；结果缓存 `data/snapshot/review_scores.json`
  （写入时机 = warmup + `run_backtest` 任务；同一 bars + frozen_config + seed 可复现）。
- `data_kind=shadow_live`：台账合并集（含归档）+ 实测基线（max(恒涨率,恒跌率)）。
- 未接通窗口 `baseline_status=pending` + 数值 null（**禁止估计值**）。
- v9.1/R-2：`scores[]` 行 = 持有期 horizon（T1/T3/T15，按 H=1/3/15 分别评估）；
  主值取该 horizon 的**全样本窗 full**（`sample_window` 恒 `full` 明示）；
  六样本窗（d15…full）归因子页，不得混入本页充当「三窗口」。

契约：09-api-contract-r2 §4.2（B5 / R2-11 / v9.1/R-2）。
"""

import io
import json
import os
from datetime import datetime

import engine
import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(ROOT, "data", "snapshot")
CACHE_PATH = os.path.join(SNAP_DIR, "review_scores.json")

HORIZONS = ((1, "T1"), (3, "T3"), (15, "T15"))

# BLOCK-1 终审（10-r2 v4 §10.1 / 09-r2 v9.2 §10）：R2 实际接通范围 = **T1**；
# T3/T15 定式（gate_only / gate+ddsm）validation_status=pending_cv（未过走前验证），
# 一律「待填充」——不得输出 H=3/15 数字；接通须各自定式过六关后由架构版本 +1 发布。
T3_T15_NOTE = ("T+3/T+15 定式（gate_only / gate+ddsm）验证状态 pending_cv（待验证："
               "未过走前 CV + placebo），R2 不填充成绩；"
               "接通须各自定式过六关后由架构版本 +1 发布。")


def _formula_of(definition):
    """公式标签必须来自**计算所用定义**（09-r2 v9.2 §10.3 / BLOCK-1）.

    禁止标签与计算路径分叉——不得用固定映射猜；定义无 formula 时回退 name。
    """
    return str((definition or {}).get("formula") or (definition or {}).get("name") or "")


def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _f4(v):
    return None if v is None else round(float(v), 4)


def load_cache():
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with io.open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def cache_fresh(as_of=None):
    """缓存是否为当日生成（S3：warmup 复用以降低启动 CPU 争抢；run_backtest 仍强制重生成）。

    判断依据：`generated_at` 的日期 == 目标日（默认今天）。缺缓存/跨日 → False（需重生成）。
    """
    cache = load_cache()
    if not cache or not cache.get("scores"):
        return False
    target = as_of or _today()
    return str(cache.get("generated_at") or "").startswith(target)


def _save_cache(obj):
    if not os.path.isdir(SNAP_DIR):
        os.makedirs(SNAP_DIR)
    tmp = CACHE_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_PATH)


def _pending_row(label, data_kind):
    return {
        "window": label,
        "formula": engine.WINDOW_FORMULA.get(label),
        "hit_rate": None,
        "open_count": 0,
        "baseline_rate": None,
        "baseline_status": "pending",
        "delta_pp": None,
        "cv_mode": "walk_forward",
        "purge_gap": "H+2",
        "holdout_days": 60,
        "data_kind": data_kind,
        "sample_window": "full",
        "sample_period": None,
        "as_of": _today(),
    }


def _hero_of(rows, data_kind, label_ok, label_pending):
    row = rows[0] if rows else None
    out = {
        "window": "T1",
        "hit_rate": (row or {}).get("hit_rate"),
        "baseline_rate": (row or {}).get("baseline_rate"),
        "delta_pp": (row or {}).get("delta_pp"),
        "open_count": (row or {}).get("open_count") or 0,
        "sample_period": (row or {}).get("sample_period"),
        "data_kind": data_kind,
        "label": label_ok if (row or {}).get("hit_rate") is not None else label_pending,
    }
    return out


def build_review_scores(assets_bars=None, use_cache=True):
    """生成生产配置回测缓存（可重建；整文件原子替换）。

    R2 接通范围 = **T1**（BLOCK-1 终审 · 10-r2 v4 §10.1 / 09-r2 v9.2 §10）：
    - 仅 H=1 评估（生产配置全链）；T3/T15 一律 `_pending_row`（不得调用
      `evaluate_production(horizon∈{3,15})` 出数字）；
    - `formula` 取自计算定义（`production_definition.formula`），禁止标签/计算分叉；
    - `baseline_status` 枚举 `filled` / `pending`（v8 §1.3；禁 `ok`）。
    """
    import factor_engine

    if assets_bars is None:
        assets_bars = factor_engine.load_monitored_bars(allow_network=False)
    defn = factor_engine.production_definition(1)
    card = None
    if assets_bars:
        try:
            card = factor_engine.evaluate(defn, assets_bars, candidate_id=None,
                                          do_bootstrap=False, use_cache=use_cache)
        except Exception:  # noqa: BLE001 - 评估失败按 pending（不编造）
            card = None
    win = None
    if card:
        win = next((w for w in (card.get("windows") or [])
                    if w.get("window") == "full"), None)
    win = win or {}
    t1 = {
        "window": "T1",
        # B1-2：标签随计算定义（可注入变体判别；不是固定映射）
        "formula": _formula_of(defn),
        "hit_rate": win.get("hit_rate"),
        "open_count": win.get("open_count") or 0,
        "baseline_rate": win.get("baseline_rate"),
        "baseline_status": ("filled" if win.get("baseline_rate") is not None
                            else "pending"),
        "delta_pp": win.get("delta_pp"),
        "cv_mode": (card or {}).get("cv_mode", "walk_forward"),
        "purge_gap": (card or {}).get("purge_gap", "H+2"),
        "holdout_days": (card or {}).get("holdout_days", 60),
        "data_kind": "backtest",
        "sample_window": "full",
        "sample_period": (card or {}).get("sample_period"),
        "as_of": _today(),
    }
    scores = [t1]
    # B1-1/B1-5：T3/T15 一律待填充（基线枚举 pending + null + open_count=0）
    for _H, label in HORIZONS[1:]:
        scores.append(_pending_row(label, "backtest"))
    payload = {
        "data_kind": "backtest",
        "generated_at": _now_iso(),
        "as_of": _today(),
        "scores": scores,
        "hero": _hero_of(scores, "backtest",
                         "生产配置走前回测 · T+1 · 全样本窗",
                         "回测待产出（不填估计值）"),
        "note": ("回测=生产配置全链（E1/E3→DDSM→双否决→出口）走前（purge=H+2 / "
                 "holdout 60）；T1 主值取 full 全样本窗（六样本窗归因子页）。"
                 + T3_T15_NOTE),
    }
    _save_cache(payload)
    return payload


def _measured(rows, field):
    vals = [r.get(field) for r in rows if r.get(field) is not None]
    if not vals:
        return None
    up = sum(1 for v in vals if v > 0) / float(len(vals))
    down = sum(1 for v in vals if v < 0) / float(len(vals))
    return max(up, down)


def _shadow_live():
    """实盘口径：台账合并集（含归档）+ 实测基线；样本不足 → pending + null。

    R2 接通范围 = T1（BLOCK-1）：T+3/T+15 行一律待填充（`pending` + null +
    open_count=0），`formula` 保留各自定式标签（gate_only / gate+ddsm）。
    """
    import ledger_api

    rows, _archive_merged = ledger_api.merged_all_rows()
    field = "t1_real"
    considered = [r for r in rows
                  if r.get("signal") == "up" and r.get(field) is not None]
    base = _measured(rows, field)
    if considered and base is not None:
        hr = sum(1 for r in considered if r[field] > 0) / float(len(considered))
        dates = sorted(r.get("date") for r in considered if r.get("date"))
        t1 = {
            "window": "T1",
            "formula": engine.WINDOW_FORMULA.get("T1"),
            "hit_rate": _f4(hr),
            "open_count": len(considered),
            "baseline_rate": _f4(base),
            "baseline_status": "filled",
            "delta_pp": _f4(hr - base),
            "cv_mode": "shadow_live",
            "purge_gap": None,
            "holdout_days": None,
            "data_kind": "shadow_live",
            "sample_window": "full",
            "sample_period": ("%s..%s" % (dates[0], dates[-1])) if dates else None,
            "as_of": _today(),
        }
    else:
        t1 = _pending_row("T1", "shadow_live")
        t1["cv_mode"] = "shadow_live"
        t1["purge_gap"] = None
        t1["holdout_days"] = None
    scores = [t1]
    for _H, label in HORIZONS[1:]:
        row = _pending_row(label, "shadow_live")
        row["cv_mode"] = "shadow_live"
        row["purge_gap"] = None
        row["holdout_days"] = None
        scores.append(row)
    return {
        "data_kind": "shadow_live",
        "generated_at": _now_iso(),
        "as_of": _today(),
        "scores": scores,
        "hero": _hero_of(scores, "shadow_live",
                         "影子盘实测 · T+1", "实盘样本待回填（不填估计值）"),
        "note": ("实盘=台账合并集（主文件 ∪ 归档）+ 实测基线 max(恒涨率,恒跌率)；"
                 "回填口径=代理 ETF 日线涨跌（proxy_bar）。" + T3_T15_NOTE),
    }


def scores(data_kind="backtest"):
    """`GET /review/scores` 组装（唯一对外入口）。"""
    if data_kind not in ("backtest", "shadow_live"):
        raise errors.ApiError(errors.E_VALIDATION,
                              "data_kind 取值为 backtest/shadow_live",
                              {"data_kind": data_kind})
    if data_kind == "backtest":
        cache = load_cache()
        if cache and cache.get("scores"):
            return cache
        pending = [_pending_row(label, "backtest") for _H, label in HORIZONS]
        return {
            "data_kind": "backtest",
            "generated_at": None,
            "as_of": _today(),
            "scores": pending,
            "hero": _hero_of(pending, "backtest",
                             "生产配置走前回测 · T+1 · 全样本窗",
                             "回测待产出（不填估计值）"),
            "note": ("回测缓存未生成：等待启动 warmup 或 POST /tasks "
                     "{type:'run_backtest'}（不填估计值）。" + T3_T15_NOTE),
        }
    return _shadow_live()
