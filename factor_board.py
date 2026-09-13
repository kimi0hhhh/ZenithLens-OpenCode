# -*- coding: utf-8 -*-
"""因子治理与竞技场（只读派生视图）。

- 契约 §5.11~§5.13 / §5.23 / §5.24 / §5.30~§5.32、§6.8、§6.11.9~§6.11.14
- 六本账本未产出数据时返回空集/null，**禁止用 legacy 示例数字冒充实测**（残留风险 9）
- 盘面 rule / 评分链 / 生命周期文本来源：legacy v2 壳 + PRD F-14；后端声明，前端不硬编码
"""

import io
import json
import os
from datetime import datetime, timedelta

import engine
import errors
import ledger_api

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_DIR = os.path.join(ROOT, "ledger")

PANS_ORDER = ["adopted", "shadow_retired", "shadow_effective", "frozen"]
PAN_META = {
    "adopted": {
        "role_label": "正式盘", "flow_kind": "promotion",
        "description": "当前生产因子（否决位 ≤4、打分位 ≤3）",
        "factor_cap": None, "nomination_limit": None, "pan_status": "on",
        # 真实上限口径（用户 2026-09-12 更正）：否决位 ≤4、打分位 ≤3。
        # factor_cap 单值（旧 3）会误导前端显示为「上限 3」，置 null 并改由 caps 承载。
        "caps": {"veto_max": 4, "score_max": 3},
        "rule_text": ("正式盘：仅收已过准入三项（F1 有效性 / F2 独立性 / F3 增量）AND 的因子；"
                      "上限：否决位 ≤4 · 打分位 ≤3；每月 1 日月榜跑留一法，"
                      "移除后 Δ 升 ≥0.5pp 且持续 30 天 = 结构红线。"),
    },
    "shadow_retired": {
        "role_label": "淘汰影子盘", "flow_kind": "promotion",
        "description": "A/B 对照中的淘汰候选，等待 60 个交易日结论",
        "factor_cap": None, "nomination_limit": None, "pan_status": "on",
        "caps": None,
        "rule_text": ("淘汰影子盘：正式盘因子进入淘汰流程后先降级到此做 A/B 对照"
                      "（移除 vs 保留），60 个交易日内不得回生产；开口 <20 不出结论。"),
    },
    "shadow_effective": {
        "role_label": "有效影子盘", "flow_kind": "promotion",
        "description": "准入三项 AND 通过、尚未晋升生产的候选",
        "factor_cap": None, "nomination_limit": 3, "pan_status": "on",
        "caps": None,
        "rule_text": ("有效影子盘：候选因子须同时过 F1 有效性、F2 独立性（与现役最大共线 <0.7）、"
                      "F3 增量（加入后 Δ≥+0.5pp 且开口不塌方）；每周提名 ≤3，冷却 90 天；"
                      "只记账不参与生产，待牌照升级。"),
    },
    "frozen": {
        "role_label": "冷冻盘", "flow_kind": "revival",
        "description": "已退役/失守因子的冷冻区，禁止直接回生产",
        "factor_cap": None, "nomination_limit": None, "pan_status": "on",
        "caps": None,
        "rule_text": ("冷冻盘：淘汰五线触发后进入冷冻；复活须重新走准入三项与 A/B 对照，"
                      "**禁止直接回生产**；复活路径属机制变更，须重走六关。"),
    },
}

BOOK_META = {
    "adopted_factors": {
        "book_label": "采纳登记表", "filename": "adopted_factors.json",
        "record_kind": "adopted_record",
        "purpose": "记录已采纳因子的角色、死亡条件与牌照",
        "schema_fields": ["factor_id", "name", "role", "license", "death_condition",
                          "adopted_at", "note"],
    },
    "scan_history": {
        "book_label": "挖掘台账", "filename": "scan_history.jsonl",
        "record_kind": "scan_record",
        "purpose": "记录每周挖掘扫描的 F1/F2/F3 判定",
        "schema_fields": ["record_id", "scan_date", "candidate", "f1_result", "f1_detail",
                          "f2_result", "f2_detail", "f3_result", "f3_detail", "verdict",
                          "nomination_week", "cooldown_until", "created_at"],
    },
    "factor_health": {
        "book_label": "体检台账", "filename": "factor_health.jsonl",
        "record_kind": "health_record",
        "purpose": "记录因子周期性体检与分数失守告警",
        "schema_fields": ["factor_id", "check_date", "license", "total_score",
                          "independent_trigger_days", "status", "alert", "created_at"],
    },
    "retired_log": {
        "book_label": "淘汰台账", "filename": "retired_log.jsonl",
        "record_kind": "retired_record",
        "purpose": "记录淘汰原因与冷冻/复活路径",
        "schema_fields": ["factor_id", "retired_at", "reason_line", "ab_delta_after_removal_pp",
                          "conclusion", "revive_eligible_at", "created_at"],
    },
    "shadow_signals": {
        "book_label": "影子信号", "filename": "shadow_signals.jsonl",
        "record_kind": "signal_record",
        "purpose": "开盘时点冻结的预测台账（INSERT-ONLY）",
        "schema_fields": ledger_api.FIELD_LIST,
    },
    "factor_arena": {
        "book_label": "因子竞技场", "filename": "factor_arena.jsonl",
        "record_kind": "arena_record",
        "purpose": "同数据同门同模型、只换一个因子的六窗对照矩阵",
        "schema_fields": ["config_id", "config_name", "config_kind", "is_leave_one_out",
                          "window", "open_count", "hit_rate", "paired_delta_pp", "created_at"],
    },
}


def _now_date():
    return datetime.now().strftime("%Y-%m-%d")


def _read_records(filename):
    path = os.path.join(LEDGER_DIR, filename)
    if not os.path.isfile(path):
        return []
    try:
        if filename.endswith(".json"):
            with io.open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return obj if isinstance(obj, list) else [obj]
        out = []
        with io.open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        return out
    except (IOError, OSError, ValueError):
        return []


def _last_record_at(recs):
    if not recs:
        return None
    def key(r):
        return r.get("created_at") or r.get("adopted_at") or r.get("scan_date") or r.get("date") or ""
    recs = sorted(recs, key=key)
    return key(recs[-1]) or None


def _future_days(func, today):
    t = datetime.strptime(today, "%Y-%m-%d").date()
    return func(t).strftime("%Y-%m-%d")


def _next_saturday(t):
    d = t
    while d.weekday() != 5:
        d += timedelta(days=1)
    return d


def _next_sunday(t):
    d = t
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d


def _next_month_first(t):
    if t.month == 12:
        return t.replace(year=t.year + 1, month=1, day=1)
    return t.replace(month=t.month + 1, day=1)


def _next_quarter_first(t):
    q = (t.month - 1) // 3
    if q == 3:
        return t.replace(year=t.year + 1, month=1, day=1)
    return t.replace(month=q * 3 + 4, day=1)


# ---------------- 四盘 ----------------

def pans():
    adopted = _read_records(BOOK_META["adopted_factors"]["filename"])
    out = []
    for role in PANS_ORDER:
        members = [f for f in adopted if f.get("role") == role]
        meta = PAN_META[role]
        out.append({
            "role": role,
            "role_label": meta["role_label"],
            "description": meta["description"],
            "factor_count": len(members),
            "factors": [_factor_item(f, role) for f in members],
            "rule_text": meta["rule_text"],
            "pan_status": meta["pan_status"],
            "flow_kind": meta["flow_kind"],
            "updated_at": _last_record_at(members),
            "factor_cap": meta["factor_cap"],
            "caps": meta.get("caps"),
            "nomination_limit": meta["nomination_limit"],
        })
    return out


def _factor_item(f, role):
    lift_bars = []
    windows = f.get("windows") or {}
    for w in ["d15", "d30", "d60", "m6", "m24", "full"]:
        lift_bars.append({"window": w, "window_label": _wlabel(w),
                          "lift": (windows.get(w) or {}).get("lift")})
    total = f.get("total_score")
    return {
        "factor_id": f.get("factor_id"),
        "name": f.get("name", ""),
        "role": role,
        "role_label": f.get("role_label", PAN_META.get(role, {}).get("role_label", "")),
        "score": total,
        "total_score": total,
        "status": f.get("status", "active"),
        "license": f.get("license", "none"),
        "license_label": _license_label(f.get("license", "none")),
        "lift_bars": lift_bars,
        "independent_trigger_days": f.get("independent_trigger_days"),
        "death_condition": f.get("death_condition"),
        "note": f.get("note", ""),
        "ab_progress": f.get("ab_progress"),
        "added_at": f.get("added_at"),
    }


def _wlabel(w):
    return {"d15": "15日", "d30": "30日", "d60": "60日",
            "m6": "6月", "m24": "24月", "full": "全样本"}.get(w, w)


def _license_label(lic):
    return {"none": "未达线", "candidate": "候补", "probation": "试用",
            "renew_t2": "续聘 T2", "full_t3": "正式 T3"}.get(lic, "未达线")


# ---------------- 账本 ----------------

def books():
    out = []
    for book in ("adopted_factors", "scan_history", "factor_health",
                 "retired_log", "shadow_signals", "factor_arena"):
        meta = BOOK_META[book]
        recs = _read_records(meta["filename"])
        out.append({
            "book": book,
            "book_label": meta["book_label"],
            "filename": meta["filename"],
            "purpose": meta["purpose"],
            "record_kind": meta["record_kind"],
            "schema_fields": meta["schema_fields"],
            "record_count": len(recs),
            "last_record_at": _last_record_at(recs),
            "sample": recs[-3:] if recs else None,
        })
    return out


def book_detail(book, limit=20, offset=0):
    if book not in BOOK_META:
        raise errors.ApiError(errors.E_NOT_FOUND, "未知账本", {"book": book})
    meta = BOOK_META[book]
    recs = _read_records(meta["filename"])
    total = len(recs)
    page = recs[offset:offset + limit]
    fields = meta["schema_fields"]
    norm = []
    for r in page:
        norm.append({k: r.get(k) for k in fields})
    return {
        "book": book, "book_label": meta["book_label"],
        "record_kind": meta["record_kind"], "schema_fields": fields,
        "records": norm, "total": total, "last_record_at": _last_record_at(recs),
    }


# ---------------- 评分链 ----------------

LIFT_BINS = [
    {"min_lift": 1.30, "k_lift": 1.0, "label": "≥1.30"},
    {"min_lift": 1.20, "k_lift": 0.80, "label": "≥1.20"},
    {"min_lift": 1.10, "k_lift": 0.65, "label": "≥1.10"},
    {"min_lift": 1.00, "k_lift": 0.50, "label": "≥1.00"},
    {"min_lift": 0.84, "k_lift": -0.80, "label": "<1.00"},
    {"min_lift": 0.0, "k_lift": -1.3, "label": "<0.84"},
]
BOOTSTRAP_PERCENTILES = {"p50": -10.8, "p90": 38.7, "p95": 48.4, "p99": 61.7, "p995": 64.1}


def k_lift_of(lift):
    if lift is None:
        return 0.0
    if lift >= 1.30:
        return 1.0
    if lift >= 1.20:
        return 0.80
    if lift >= 1.10:
        return 0.65
    if lift >= 1.00:
        return 0.50
    if lift >= 0.84:
        return -0.80
    return -1.3


def score_chain():
    try:
        import factor_engine
        measured = factor_engine.measured_bootstrap()
    except Exception:  # noqa: BLE001 - 实测零分布缺失不阻塞评分链读取
        measured = None
    return {
        "lift_bins": LIFT_BINS,
        "window_weights": [dict(x, window_label=_wlabel(x["window"]))
                           for x in engine.frozen_params()["window_weights"]],
        "formula_text": ("每窗 lift = 命中率 ÷ 基线；k_lift 查悬崖表；得分 = k_lift × 窗权重 × 准入度；"
                         "总分 = 六窗得分之和。准入度 = min(1, 独立触发日 / N_w)，"
                         "N_w = 5/10/15/30/60/120。绩效与 t 一律按独立触发日聚合（不用条口径）。"),
        "bootstrap_percentiles": BOOTSTRAP_PERCENTILES,
        "bootstrap_percentiles_measured": measured,
        "real_engine": True,
        "judges": [
            {"judge": "lift", "scope": "分数裁判", "metric": "lift → k_lift 悬崖",
             "note": "决定每窗得分，越强正分越高、无效重罚"},
            {"judge": "t", "scope": "闸门裁判", "metric": "t 值", "note": "显著性未过则不放行"},
            {"judge": "admission", "scope": "折扣裁判", "metric": "独立触发日 / N_w",
             "note": "样本不足按比例打折"},
            {"judge": "backtest", "scope": "晋升裁判", "metric": "实测 Δ 与 A/B",
             "note": "最终晋升以走前回测 + A/B 为准"},
        ],
        "floor_note": ("地板说明：k_lift <1.00 → −0.80 天花板，<0.84 → −1.3；"
                       "不对称惩罚即噪声抑制器，宁可错杀弱势因子。"),
        "rule_source": "docs/00-charter/00-design-reference-legacy-v2.html §评分链",
    }


def score_detail(factor_id):
    adopted = _read_records(BOOK_META["adopted_factors"]["filename"])
    target = None
    for f in adopted:
        if f.get("factor_id") == factor_id:
            target = f
            break
    if target is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该因子", {"factor_id": factor_id})
    fp = engine.frozen_params()
    weights = {x["window"]: x["weight"] for x in fp["window_weights"]}
    nws = {x["window"]: x["n_w"] for x in fp["window_min_days"]}
    windows = target.get("windows") or {}
    out_windows = []
    total = 0.0
    any_val = False
    for w in ["d15", "d30", "d60", "m6", "m24", "full"]:
        rec = windows.get(w) or {}
        lift = rec.get("lift")
        k = k_lift_of(lift)
        itd = rec.get("independent_trigger_days")
        n_w = nws[w]
        admission = min(1.0, (itd or 0) / float(n_w)) if itd is not None else 0.0
        score = k * weights[w] * admission
        if lift is not None:
            any_val = True
            total += score
        out_windows.append({
            "window": w, "window_label": _wlabel(w), "lift": lift,
            "k_lift": round(k, 4), "weight": weights[w],
            "independent_trigger_days": itd, "n_w": n_w,
            "admission": round(admission, 4), "score": round(score, 4),
            "cliff_hit": (LIFT_BINS[[b["min_lift"] for b in LIFT_BINS].index(
                next((b["min_lift"] for b in LIFT_BINS if lift >= b["min_lift"]), 0.0))]["label"]
                if lift is not None else None),
        })
    full = windows.get("full") or {}
    # NIT F-3：judges.value 不再恒空——可从已采纳记录导出的就填实测值
    # （lift=total_score / admission=full 窗准入度 / backtest=Δpp）；
    # t 值未存于 adopted 记录（重算代价高），保持 None 由前端按「待接入」呈现。
    judge_values = {
        "lift": target.get("total_score"),
        "t": None,
        "admission": full.get("admission"),
        "backtest": target.get("delta_pp"),
    }
    judges = []
    for j in score_chain()["judges"]:
        jj = dict(j)
        jj["value"] = judge_values.get(j.get("judge"))
        judges.append(jj)
    return {
        "factor_id": factor_id, "name": target.get("name", ""),
        "total_score": round(total, 4) if any_val else None,
        "windows": out_windows,
        "bootstrap_percentiles": BOOTSTRAP_PERCENTILES,
        "judges": judges,
        "formula_text": score_chain()["formula_text"],
    }


# ---------------- 生命周期 ----------------

def lifecycle():
    return {
        "admission_rules": [
            "F1 有效性：近 6 月或近 60 日任一窗口命中率超基线",
            "F2 独立性：与现役因子最大共线 <0.7",
            "F3 增量：加入后 Δ≥+0.5pp 且开口不塌方",
            "准入 = F1 AND F2 AND F3（三项同时成立）",
        ],
        "license_lines": [
            {"license": "candidate", "threshold": "独立触发日 ≥50", "condition": "只记账不参与生产"},
            {"license": "probation", "threshold": "独立触发日 ≥60 且 30日窗 k≥0.5", "condition": "试用观察"},
            {"license": "renew_t2", "threshold": "≥70 且 60日窗 k≥0.7 且持牌满一季", "condition": "续聘 T2"},
            {"license": "full_t3", "threshold": "≥80 且 24月窗 k≥0.7", "condition": "正式 T3"},
        ],
        "retire_rules": [
            "急性熔断：单次重大失效立即停用",
            "缓性衰减：连续多窗 lift 下滑至悬崖下",
            "结构红线：留一法移除后 Δ 升 ≥0.5pp 持续 30 天",
            "分数失守：总分跌破牌照线",
            "开口塌方：加入因子后开口数显著下降",
        ],
        "dual_exit": [
            "软出口：沿降级梯 probation → cooling → frozen 逐级降级",
            "硬出口：进入 A/B 对照 60 个交易日，到期按实测 Δ 结论",
        ],
        "false_kill_guards": [
            "条件绩效口径：按独立触发日聚合，不用条口径",
            "开口 <20 不出结论",
            "A/B 期牌照冻结，不因短期波动淘汰",
        ],
        "revive_rules": [
            "冷冻因子复活须重新走准入三项 AND",
            "复活须再做 A/B 对照 60 日",
            "禁止直接回生产；复活属机制变更，须重走六关",
        ],
        "source": ("docs/00-charter/00-design-reference-legacy-v2.html §四盘/生命周期 + "
                   "docs/00-charter/02-prd.md F-14"),
        "freeze_note": "规则文本冻结；任何改动须重走六关。",
    }


# ---------------- 治理周期 / 挖掘记录 ----------------

def governance_cycle():
    today = _now_date()
    phases = [
        {"phase": "dig_scan", "label": "下次挖掘扫描", "cadence": "周六",
         "status": "scheduled", "last_run_at": None,
         "next_run_at": _future_days(_next_saturday, today),
         "rule_text": "每周六扫描候选因子；每周提名 ≤3，冷却 90 天。",
         "human_retained": "紧急停机权"},
        {"phase": "scorecard", "label": "下次评分卡", "cadence": "周日",
         "status": "scheduled", "last_run_at": None,
         "next_run_at": _future_days(_next_sunday, today),
         "rule_text": "每周日按评分链（悬崖 × 窗权重 × 准入度）出评分卡。",
         "human_retained": "机制变更权"},
        {"phase": "monthly_rank", "label": "下次月榜·牌照", "cadence": "每月 1 日",
         "status": "scheduled", "last_run_at": None,
         "next_run_at": _future_days(_next_month_first, today),
         "rule_text": "每月 1 日月榜只产生提名与牌照变更建议，不直接变更生产。",
         "human_retained": "机制变更权"},
        {"phase": "quarterly_review", "label": "下次季复查", "cadence": "每季首月",
         "status": "scheduled", "last_run_at": None,
         "next_run_at": _future_days(_next_quarter_first, today),
         "rule_text": "每季首月复查在册因子体检与 A/B 结论。",
         "human_retained": "机制变更权"},
        {"phase": "ddsm_retrain", "label": "下次 DDSM 重训", "cadence": "每季",
         "status": "scheduled", "last_run_at": None,
         "next_run_at": _future_days(_next_quarter_first, today),
         "rule_text": "每季重训 DDSM；参数变更须重走六关（待验证）。",
         "human_retained": "机制变更权"},
    ]
    return {
        "phases": phases,
        "note": "机器自动裁判，人只留机制变更权与紧急停机权。",
    }


def dig_records(limit=20):
    recs = _read_records(BOOK_META["scan_history"]["filename"])
    recs = recs[-limit:]
    out = []
    for r in recs:
        out.append({
            "record_id": r.get("record_id"),
            "scan_date": r.get("scan_date"),
            "candidate": r.get("candidate"),
            "f1_result": r.get("f1_result", "not_run"),
            "f1_detail": r.get("f1_detail", ""),
            "f2_result": r.get("f2_result", "not_run"),
            "f2_detail": r.get("f2_detail", ""),
            "f3_result": r.get("f3_result", "not_run"),
            "f3_detail": r.get("f3_detail", ""),
            "verdict": r.get("verdict", "candidate_pool"),
            "verdict_text": r.get("verdict_text", ""),
            "nomination_week": r.get("nomination_week"),
            "cooldown_until": r.get("cooldown_until"),
            "created_at": r.get("created_at"),
        })
    return {
        "records": out,
        "panel": {"nomination_limit": 3, "cooldown_days": 90, "week_rule": "每周提名 ≤3"},
    }


# ---------------- 竞技场 ----------------

ARENA_WINDOWS = ["d15", "d30", "d60", "m6", "m24", "full"]
# v4 A-09：竞技场采用独立性能色板，与全站涨跌色（--up/--down）解耦
ARENA_COLOR_SCHEME = "performance_rank"
ARENA_COLOR_PREFIX = "--arena-"
ARENA_LEGEND = [
    {"color": "red", "label": "该窗最高"},
    {"color": "green", "label": "该窗最低"},
    {"color": "blue", "label": "居中"},
    {"color": "yellow", "label": "▲ 警示（Δ 低于裸算法基准）"},
    {"color": "base", "label": "基准行不着色"},
]


def _read_arena():
    """factor_arena.jsonl 记录可为长表（每行一个窗）或宽表（cells）。"""
    recs = _read_records(BOOK_META["factor_arena"]["filename"])
    configs = {}
    for r in recs:
        cid = r.get("config_id")
        if cid is None:
            continue
        cfg = configs.setdefault(cid, {
            "config_id": cid, "config_name": r.get("config_name", cid),
            "config_kind": r.get("config_kind", "candidate"),
            "is_leave_one_out": bool(r.get("is_leave_one_out", False)),
            "cells": {},
        })
        if "window" in r:
            cfg["cells"][r["window"]] = {
                "open_count": r.get("open_count"),
                "hit_rate": r.get("hit_rate"),
                "paired_delta_pp": r.get("paired_delta_pp"),
            }
        elif isinstance(r.get("cells"), dict):
            cfg["cells"].update(r["cells"])
    return list(configs.values())


def arena():
    raw = _read_arena()
    if not raw:
        return {
            "windows": [{"window": w, "window_label": _wlabel(w)} for w in ARENA_WINDOWS],
            "rows": [],
            "color_scheme": ARENA_COLOR_SCHEME,
            "color_token_prefix": ARENA_COLOR_PREFIX,
            "legend": ARENA_LEGEND,
            "naive_method_note": ("留一法（C − eᵢ）：同一份数据、同一个门、同一个模型，"
                                  "只移除一个因子，观察 Δ 变化；移除后 Δ 升 ≥0.5pp 持续 30 天 = 结构红线。"),
            "as_of": None,
        }
    # 每个窗口的裸算法基准 Δ
    base = {}
    for cfg in raw:
        if cfg["config_kind"] == "naive_baseline":
            for w in ARENA_WINDOWS:
                c = cfg["cells"].get(w)
                if c:
                    base[w] = c.get("paired_delta_pp")
    maxima, minima = {}, {}
    for w in ARENA_WINDOWS:
        vals = [cfg["cells"].get(w, {}).get("paired_delta_pp") for cfg in raw
                if cfg["config_kind"] != "naive_baseline"
                and cfg["cells"].get(w, {}).get("paired_delta_pp") is not None]
        if vals:
            maxima[w] = max(vals)
            minima[w] = min(vals)
    rows = []
    for cfg in raw:
        is_base = cfg["config_kind"] == "naive_baseline"
        cells = []
        warn_row = False
        for w in ARENA_WINDOWS:
            c = cfg["cells"].get(w, {})
            pd_ = c.get("paired_delta_pp")
            warning = bool((not is_base) and base.get(w) is not None and pd_ is not None
                           and pd_ < base[w])
            warn_row = warn_row or warning
            if is_base:
                color = "base"
            elif warning:
                color = "yellow"
            elif pd_ is not None and maxima.get(w) == pd_:
                color = "red"
            elif pd_ is not None and minima.get(w) == pd_:
                color = "green"
            else:
                color = "blue"
            cells.append({
                "window": w, "open_count": c.get("open_count"),
                "hit_rate": c.get("hit_rate"), "paired_delta_pp": pd_,
                "is_leave_one_out": cfg["is_leave_one_out"],
                "warning": warning, "color": color,
                "is_window_max": bool(pd_ is not None and maxima.get(w) == pd_),
                "is_window_min": bool(pd_ is not None and minima.get(w) == pd_),
            })
        rows.append({
            "config_id": cfg["config_id"], "config_name": cfg["config_name"],
            "config_kind": cfg["config_kind"],
            "is_leave_one_out": cfg["is_leave_one_out"],
            "is_highlight": cfg["config_kind"] == "production",
            "warning": warn_row, "cells": cells,
        })
    return {
        "windows": [{"window": w, "window_label": _wlabel(w)} for w in ARENA_WINDOWS],
        "rows": rows,
        "color_scheme": ARENA_COLOR_SCHEME,
        "color_token_prefix": ARENA_COLOR_PREFIX,
        "legend": ARENA_LEGEND,
        "naive_method_note": ("留一法（C − eᵢ）：同一份数据、同一个门、同一个模型，"
                              "只移除一个因子，观察 Δ 变化；移除后 Δ 升 ≥0.5pp 持续 30 天 = 结构红线。"),
        "as_of": None,
    }
