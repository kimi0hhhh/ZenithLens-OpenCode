# -*- coding: utf-8 -*-
"""因子回测与治理引擎（深度模块）。

唯一对外接口（`21-factor-governance.md` §9.2）：

    evaluate(definition, assets_bars, frozen_config) -> Scorecard

本模块实现机制正文 `docs/01-architecture/21-factor-governance.md`：
- 因子定义 = 声明式纯表达式（AST），只依赖"截至某日"数据 → 防前视（§1）
- 六窗走前（purged walk-forward，禁随机切分），purge = H+2（§2/§3）
- 基线 = max(恒涨率, 恒跌率)，报 lift = 命中率 ÷ 基线（§3.3）
- 评分链：lift → k_lift 五档悬崖 → ×窗权重 8/22/15/10/30/15 → ×准入度 → 总分（§4）
- 准入三项 F1/F2/F3 + 牌照 + 盘位（§5/§7）
- 候选/记分卡账本 INSERT-ONLY（§8）

防前视铁律（§1.6）：L1 视图截断（本模块逐日求值，AST 无负 shift）；
L2 归一化只用训练段（每折重算）；L3 purge=H+2；L4 参数只在训练段；
L5 因果窗口；L6 placebo（bootstrap 零分布）；L7 holdout 60 日不参与搜索/评分。

纯标准库（math/hashlib/json/os/random/datetime）。
"""

import hashlib
import io
import json
import math
import os
import random
from datetime import datetime, timedelta

import engine
import errors

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER_DIR = os.path.join(ROOT, "ledger")
FACTOR_CACHE_DIR = os.path.join(ROOT, "data", "cache", "factor")
CANDIDATES_PATH = os.path.join(LEDGER_DIR, "factor_candidates.jsonl")
SCORECARDS_PATH = os.path.join(LEDGER_DIR, "scorecards.jsonl")
SCAN_HISTORY_PATH = os.path.join(LEDGER_DIR, "scan_history.jsonl")
ARENA_PATH = os.path.join(LEDGER_DIR, "factor_arena.jsonl")
ADOPTED_PATH = os.path.join(LEDGER_DIR, "adopted_factors.json")
SIGNALS_CACHE_PATH = os.path.join(FACTOR_CACHE_DIR, "signals.json")
# R2-06/R2-04：C→B 验证 / 9 只代理复核结论（INSERT-ONLY）
TIER_REVIEWS_PATH = os.path.join(ROOT, "data", "review", "tier_reviews.jsonl")

# 三层判定冻结口径（10-arch-review-r2 v2 §2.4；ADR-0011）
MIN_INDEP_DAYS = 20            # 独立触发日门槛（低样本保护，优先于数值判据）
DIR_HIT_FLOOR = 0.60           # 代理质量方向命中率下限（R2-04）
REVIEW_HOLD_DAYS = 30          # 挂档复查日：自证据就绪日 +30 交易日（D-4 统一口径）

# ---------------- 冻结参数（机制 §3.1 / §4.2 / §4.3 / §4.4） ----------------
WINDOWS = ["d15", "d30", "d60", "m6", "m24", "full"]
WINDOW_LABEL = {"d15": "15日", "d30": "30日", "d60": "60日",
                "m6": "6月", "m24": "24月", "full": "全样本"}
WINDOW_WEIGHTS = {"d15": 8, "d30": 22, "d60": 15,
                  "m6": 10, "m24": 30, "full": 15}
WINDOW_NW = {"d15": 5, "d30": 10, "d60": 15,
             "m6": 30, "m24": 60, "full": 120}
HOLDOUT_DAYS = 60
PLACEBO_MIN_PP = 0.02
BOOTSTRAP_RUNS = 500
F3_DELTA_MIN_PP = 0.005          # +0.5pp（比率口径）
F3_COLLAPSE_MIN = 0.50           # 开口不塌方 >50%
F2_MAX_COLLINEARITY = 0.70

# k_lift 五档悬崖（机制 §4.2；lift 越大分越高，弱势重罚）
K_LIFT_TABLE = [
    (1.30, 1.0000, "≥1.30"),
    (1.20, 0.8000, "≥1.20"),
    (1.10, 0.6500, "≥1.10"),
    (1.00, 0.5000, "≥1.00"),
    (0.84, -0.8000, "<1.00"),
    (0.00, -1.3000, "<0.84"),
]

KINDS = ("binary_signal", "score")
ORIENTATIONS = ("higher_bullish", "higher_bearish")
ROLE_HINTS = ("veto", "score")
NORMALIZATIONS = ("none", "zscore_train", "quantile_train")
HORIZONS = (1, 3, 15)

JUNCTION_OPS = ("and", "or", "not")
COMPARE_OPS = ("gt", "ge", "lt", "le", "eq")
ARITH_OPS = ("add", "sub", "mul", "div", "neg", "abs", "log")
SERIES_OPS = ("shift", "rolling_mean", "rolling_std", "rolling_min", "rolling_max",
              "rolling_quantile", "rank_causal", "zscore_causal", "corr_causal", "ewma")
ALL_OPS = JUNCTION_OPS + COMPARE_OPS + ARITH_OPS + SERIES_OPS

# 输入列闭集（机制 §1.3）
INPUT_COLUMNS = ("open", "high", "low", "close", "volume", "amount", "ret", "logret",
                 "r2", "om", "vr", "mom5", "dev", "vpcorr", "volat", "skew",
                 "bench_close", "bench_ret")


# ---------------- 基础 ----------------

def _now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _r4(v):
    return None if v is None else round(float(v), 4)


def _r3(v):
    return None if v is None else round(float(v), 3)


def _ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)


def _read_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def _write_json(path, obj):
    _ensure_dir(path)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


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
    _ensure_dir(path)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ---------------- 评分链纯函数（机制 §4） ----------------

def k_lift_of(lift):
    if lift is None:
        return 0.0
    for min_lift, k, _label in K_LIFT_TABLE:
        if lift >= min_lift:
            return k
    return K_LIFT_TABLE[-1][1]


def cliff_of(lift):
    if lift is None:
        return None
    for min_lift, _k, label in K_LIFT_TABLE:
        if lift >= min_lift:
            return label
    return K_LIFT_TABLE[-1][2]


def admission_of(independent_trigger_days, n_w):
    if not independent_trigger_days:
        return 0.0
    return min(1.0, independent_trigger_days / float(n_w))


def _is_hit(orientation, fwd):
    """命中 = H 到期上涨（机制 §2.4：本项目永不做空，方向恒为"涨"）。
    `orientation` 只决定"开口/触发"的方向（见 `_generic_fired`），不改变命中口径。"""
    if fwd is None:
        return None
    return fwd > 0


def _license_of(total_score, indep_days, windows):
    """牌照四线（机制 §5.2：总分线 50/60/70/80 + 样本下限并行）。"""
    kd = {w["window"]: w.get("k_lift") for w in windows}
    d = indep_days or 0
    if total_score is None or total_score < 50 or d < 50:
        return "none"
    if total_score >= 80 and d >= 80 and (kd.get("m24") or -9) >= 0.7:
        return "full_t3"
    if total_score >= 70 and d >= 70 and (kd.get("d60") or -9) >= 0.7:
        return "renew_t2"
    if total_score >= 60 and d >= 60 and (kd.get("d30") or -9) >= 0.5:
        return "probation"
    return "candidate"


def license_label(lic):
    return {"none": "未达线", "candidate": "候补", "probation": "试用",
            "renew_t2": "续聘 T2", "full_t3": "正式 T3"}.get(lic, "未达线")


def k_lift_bins():
    return [{"min_lift": m, "k_lift": k, "label": lb} for m, k, lb in K_LIFT_TABLE]


# ---------------- 定义校验（机制 §1.6 提交即拒） ----------------

def _canon(obj):
    return json.dumps(_norm_numbers(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _norm_numbers(o):
    """哈希前把数值规范化（0.0 ≡ 0），保证同一定义不同序列化得到同一 definition_hash。"""
    if isinstance(o, bool):
        return o
    if isinstance(o, float):
        if o == int(o) and abs(o) < 1e15:
            return int(o)
        return o
    if isinstance(o, dict):
        return {k: _norm_numbers(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm_numbers(v) for v in o]
    return o


def definition_hash(definition):
    payload = {
        "kind": definition.get("kind"),
        "orientation": definition.get("orientation"),
        "role_hint": definition.get("role_hint"),
        "horizon": definition.get("horizon"),
        "inputs": definition.get("inputs"),
        "expression": definition.get("expression"),
        "normalization": definition.get("normalization"),
        "params": definition.get("params") or [],
        "veto_threshold": definition.get("veto_threshold"),
    }
    return hashlib.sha1(_canon(payload).encode("utf-8")).hexdigest()[:16]


def _validate_node(node, declared, detail, path="$"):
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return
    if not isinstance(node, dict):
        detail[path] = "node must be leaf/op object or number"
        return
    if "column" in node:
        col = node.get("column")
        if col not in INPUT_COLUMNS:
            detail[path + ".column"] = "undeclared column: %s" % col
        if declared is not None and col not in declared:
            detail[path + ".column"] = "column not in inputs: %s" % col
        lag = node.get("lag", 0)
        if not isinstance(lag, int) or lag < 0:
            detail[path + ".lag"] = "lag must be integer >= 0"
        return
    op = node.get("op")
    if op not in ALL_OPS:
        detail[path + ".op"] = "unknown op: %s" % op
        return
    args = node.get("args")
    if not isinstance(args, list):
        detail[path + ".args"] = "args must be array"
        return
    n = len(args)
    if op in ("and", "or") and n < 2:
        detail[path + ".args"] = "%s needs >=2 args" % op
    elif op == "not" and n != 1:
        detail[path + ".args"] = "not needs exactly 1 arg"
    elif op in COMPARE_OPS and n != 2:
        detail[path + ".args"] = "%s needs exactly 2 args" % op
    elif op in ("add", "sub") and n < 2:
        detail[path + ".args"] = "%s needs >=2 args" % op
    elif op == "mul" and n < 2:
        detail[path + ".args"] = "mul needs >=2 args"
    elif op in ("neg", "abs", "log") and n != 1:
        detail[path + ".args"] = "%s needs exactly 1 arg" % op
    elif op == "shift":
        if n != 2 or not isinstance(args[1], int) or args[1] < 0:
            detail[path + ".args"] = "shift(node, k>=0)"
    elif op in ("rolling_mean", "rolling_std", "rolling_min", "rolling_max",
                "rank_causal", "zscore_causal", "ewma"):
        if n != 2 or not isinstance(args[1], int) or args[1] < 1:
            detail[path + ".args"] = "%s(node, w>=1)" % op
    elif op == "rolling_quantile":
        if n != 3 or not isinstance(args[1], int) or args[1] < 1:
            detail[path + ".args"] = "rolling_quantile(node, w>=1, q)"
    elif op == "corr_causal":
        if n != 3 or not isinstance(args[2], int) or args[2] < 1:
            detail[path + ".args"] = "corr_causal(a, b, w>=1)"
    for i, a in enumerate(args):
        if op in ("shift",) and i == 1:
            continue
        if op in ("rolling_mean", "rolling_std", "rolling_min", "rolling_max",
                  "rank_causal", "zscore_causal", "ewma") and i == 1:
            continue
        if op == "rolling_quantile" and i in (1, 2):
            continue
        if op == "corr_causal" and i == 2:
            continue
        _validate_node(a, declared, detail, "%s.args[%d]" % (path, i))


def validate_definition(definition):
    """L0/L1：AST 提交即拒；违规抛 E_VALIDATION（detail 字段级）。"""
    if not isinstance(definition, dict):
        raise errors.ApiError(errors.E_VALIDATION, "请求体必须是对象",
                              {"body": "not object"})
    detail = {}
    name = definition.get("name")
    if not isinstance(name, str) or not name.strip():
        detail["name"] = "required non-empty string"
    if definition.get("kind") not in KINDS:
        detail["kind"] = "must be one of %s" % list(KINDS)
    if definition.get("orientation") not in ORIENTATIONS:
        detail["orientation"] = "must be one of %s" % list(ORIENTATIONS)
    if definition.get("role_hint") not in ROLE_HINTS:
        detail["role_hint"] = "must be one of %s" % list(ROLE_HINTS)
    if definition.get("horizon") not in HORIZONS:
        detail["horizon"] = "must be one of %s" % list(HORIZONS)
    inputs = definition.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        detail["inputs"] = "required non-empty array"
        declared = None
    else:
        declared = set()
        for c in inputs:
            if c not in INPUT_COLUMNS:
                detail["inputs"] = "column not in vocabulary: %s" % c
            else:
                declared.add(c)
    if definition.get("normalization") not in NORMALIZATIONS:
        detail["normalization"] = "must be one of %s" % list(NORMALIZATIONS)
    fid = definition.get("factor_id")
    if fid is not None and not (isinstance(fid, str) and
                                8 <= len(fid) <= 32 and all(
                                    ch.islower() or ch.isdigit() or ch == "_" for ch in fid)):
        detail["factor_id"] = "8~32 [a-z0-9_]"
    expr = definition.get("expression")
    if not isinstance(expr, dict):
        detail["expression"] = "required AST object"
    else:
        _validate_node(expr, declared, detail, "expression")
        if definition.get("kind") == "binary_signal":
            root_op = expr.get("op")
            if root_op not in (JUNCTION_OPS + COMPARE_OPS):
                detail["expression"] = "binary_signal root must be boolean compare/junction"
    params = definition.get("params") or []
    if params:
        if not isinstance(params, list):
            detail["params"] = "must be array"
        else:
            for i, p in enumerate(params):
                if not isinstance(p, dict) or not p.get("name") or \
                        p.get("type") not in ("int", "float", "bool"):
                    detail["params[%d]" % i] = "needs {name,type(default/int/float/bool),default,grid}"
                elif not isinstance(p.get("grid"), list) or not p.get("grid"):
                    detail["params[%d].grid" % i] = "grid must be non-empty"
    # veto_threshold：score 型否决位必填；binary_signal 由布尔表达式承载阈值
    if definition.get("role_hint") == "veto" and definition.get("kind") == "score":
        if definition.get("veto_threshold") is None:
            detail["veto_threshold"] = "required when role_hint=veto and kind=score"
    if detail:
        raise errors.ApiError(errors.E_VALIDATION, "因子定义校验失败", detail)
    return True


# ---------------- 列装配（机制 §1.3） ----------------

def _columns(bars):
    n = len(bars)
    cols = {c: [None] * n for c in INPUT_COLUMNS}
    for i, b in enumerate(bars):
        cols["open"][i] = b.get("open")
        cols["high"][i] = b.get("high")
        cols["low"][i] = b.get("low")
        cols["close"][i] = b.get("close")
        cols["volume"][i] = b.get("volume")
    for i in range(n):
        if i >= 1:
            c0 = bars[i - 1].get("close")
            c1 = bars[i].get("close")
            if c0 and c0 > 0 and c1 is not None:
                cols["ret"][i] = c1 / c0 - 1.0
                if c1 > 0:
                    cols["logret"][i] = math.log(c1 / c0)
        f = engine.features_at(bars, i)
        if f:
            for c in ("r2", "om", "vr", "mom5", "dev", "vpcorr", "volat", "skew"):
                cols[c][i] = f.get(c)
        cols["bench_close"][i] = cols["close"][i]
        cols["bench_ret"][i] = cols["ret"][i]
    return cols


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def eval_node(node, cols, t):
    """逐日求值（L1/L5：只用 date<=t 的数据；None 传播）。"""
    if isinstance(node, bool):
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if "column" in node:
        lag = node.get("lag", 0)
        i = t - lag
        arr = cols.get(node.get("column"))
        if arr is None or i < 0 or i >= len(arr):
            return None
        return arr[i]
    op = node.get("op")
    args = node.get("args") or []
    if op in ("and", "or"):
        vals = [eval_node(a, cols, t) for a in args]
        if any(v is None for v in vals):
            return None
        return all(vals) if op == "and" else any(vals)
    if op == "not":
        v = eval_node(args[0], cols, t)
        return None if v is None else (not bool(v))
    if op in COMPARE_OPS:
        a, b = eval_node(args[0], cols, t), eval_node(args[1], cols, t)
        if a is None or b is None:
            return None
        return {"gt": a > b, "ge": a >= b, "lt": a < b,
                "le": a <= b, "eq": a == b}[op]
    if op in ARITH_OPS:
        vals = [eval_node(a, cols, t) for a in args]
        if any(v is None for v in vals):
            return None
        if op == "add":
            return sum(vals)
        if op == "sub":
            acc = vals[0]
            for v in vals[1:]:
                acc -= v
            return acc
        if op == "mul":
            acc = 1.0
            for v in vals:
                acc *= v
            return acc
        if op == "div":
            acc = vals[0]
            for v in vals[1:]:
                if v == 0:
                    return None
                acc /= v
            return acc
        if op == "neg":
            return -vals[0]
        if op == "abs":
            return abs(vals[0])
        if op == "log":
            return math.log(vals[0]) if vals[0] > 0 else None
    if op == "shift":
        return eval_node(args[0], cols, t - int(args[1]))
    if op in ("rolling_mean", "rolling_std", "rolling_min", "rolling_max",
              "rank_causal", "zscore_causal", "ewma", "rolling_quantile"):
        w = int(args[1])
        lo = t - w + 1
        if lo < 0:
            return None
        seq = [eval_node(args[0], cols, i) for i in range(lo, t + 1)]
        if any(v is None for v in seq):
            return None
        if op == "rolling_mean":
            return engine._mean(seq)
        if op == "rolling_std":
            return engine._pstdev(seq)
        if op == "rolling_min":
            return min(seq)
        if op == "rolling_max":
            return max(seq)
        if op == "rolling_quantile":
            q = float(args[2])
            return engine.quantile(sorted(seq), q)
        if op == "rank_causal":
            cur = seq[-1]
            return sum(1 for v in seq if v <= cur) / float(len(seq))
        if op == "zscore_causal":
            sd = engine._pstdev(seq)
            return None if sd == 0 else (seq[-1] - engine._mean(seq)) / sd
        if op == "ewma":
            alpha = 2.0 / (w + 1.0)
            e = seq[0]
            for v in seq[1:]:
                e = alpha * v + (1 - alpha) * e
            return e
    if op == "corr_causal":
        w = int(args[2])
        lo = t - w + 1
        if lo < 0:
            return None
        xs = [eval_node(args[0], cols, i) for i in range(lo, t + 1)]
        ys = [eval_node(args[1], cols, i) for i in range(lo, t + 1)]
        if any(v is None for v in xs) or any(v is None for v in ys):
            return None
        return engine._corr(xs, ys)
    return None


# ---------------- 信号生成（防前视：归一化只用训练段） ----------------

def _generic_fired(definition, bars):
    """通用 AST 因子逐日信号；normalization 每折只用 [0, t-(H+2)] 训练段。"""
    n = len(bars)
    H = int(definition.get("horizon") or 1)
    cols = _columns(bars)
    raw = [eval_node(definition["expression"], cols, t) for t in range(n)]
    kind = definition.get("kind")
    norm = definition.get("normalization") or "none"
    thr = definition.get("veto_threshold")
    out = [None] * n
    if kind == "binary_signal":
        for t in range(n):
            out[t] = None if raw[t] is None else bool(raw[t])
        return out
    # score：训练段标准化后按阈值转布尔；higher_bearish 取负（机制 §1.2：回测取负）
    bearish = (definition.get("orientation") == "higher_bearish")
    for t in range(n):
        v = raw[t]
        if v is None:
            continue
        tr_end = t - (H + 2)
        if tr_end < 0:
            continue
        train = [raw[i] for i in range(0, tr_end + 1) if raw[i] is not None]
        if len(train) < 5:
            continue
        if norm == "zscore_train":
            sd = engine._pstdev(train)
            if sd == 0:
                continue
            val = (v - engine._mean(train)) / sd
            thr_v = 0.0 if thr is None else thr
        elif norm == "quantile_train":
            val = sum(1 for x in train if x <= v) / float(len(train))
            thr_v = 0.5 if thr is None else thr
        else:
            val = v
            thr_v = 0.0 if thr is None else thr
        out[t] = (val <= thr_v) if bearish else (val >= thr_v)
    return out


def _features_list(bars):
    return [engine.features_at(bars, i) for i in range(len(bars))]


def _klow2_fired(bars, feats, H):
    n = len(bars)
    kl = [(feats[i].get("klow2") if feats[i] else None) for i in range(n)]
    out = [None] * n
    for t in range(n):
        te = t - (H + 2)
        if te < 0:
            continue
        train = sorted(v for v in kl[:te + 1] if v is not None)
        if len(train) < 5:
            continue
        q = engine.quantile(train, engine.VETO_KLOW2_QUANTILE)
        cur = kl[t]
        out[t] = None if (cur is None or q is None) else bool(cur <= q)
    return out


def _crowd_fired(bars, feats, H):
    n = len(bars)
    dims = engine.CROWD_DIMS
    vals = {d: [(feats[i].get(d) if feats[i] else None) for i in range(n)] for d in dims}
    fwd = [None] * n
    for i in range(n - H):
        c0 = bars[i].get("close")
        c1 = bars[i + H].get("close")
        if c0 and c0 > 0 and c1 is not None:
            fwd[i] = c1 / c0 - 1.0
    out = [None] * n
    for t in range(n):
        te = t - (H + 2)
        if te < 0:
            continue
        means, stds, ics = {}, {}, {}
        ok = True
        for d in dims:
            pv = [vals[d][i] for i in range(te + 1) if vals[d][i] is not None]
            if len(pv) < 5:
                ok = False
                break
            means[d] = engine._mean(pv)
            stds[d] = engine._pstdev(pv) or 1.0
            xs, ys = [], []
            for i in range(te + 1):
                if vals[d][i] is not None and fwd[i] is not None:
                    xs.append(vals[d][i])
                    ys.append(fwd[i])
            c = engine._corr(xs, ys) if len(xs) >= 3 else 0.0
            ics[d] = 0 if abs(c) < 1e-9 else (1 if c > 0 else -1)
        if not ok:
            continue
        comps = []
        for i in range(te + 1):
            zs, bad = [], False
            for d in dims:
                if vals[d][i] is None:
                    bad = True
                    break
                zs.append((vals[d][i] - means[d]) / stds[d] * ics[d])
            if not bad:
                comps.append(engine._mean(zs))
        if len(comps) < 5:
            continue
        q = engine.quantile(sorted(comps), engine.VETO_CROWD_QUANTILE)
        f = feats[t]
        if f is None or q is None:
            continue
        zs, bad = [], False
        for d in dims:
            if f.get(d) is None:
                bad = True
                break
            zs.append((f.get(d) - means[d]) / stds[d] * ics[d])
        if bad:
            continue
        out[t] = bool(engine._mean(zs) >= q)
    return out


def _base_fired(bars, H):
    """现生产配置信号（gate+ddsm>0.52+双否决），走前逐日（purge=H+2）。"""
    n = len(bars)
    out = [None] * n
    for t in range(n):
        te = t - (H + 2)
        if te < 0:
            continue
        train = bars[:te + 1]
        model = engine.train_model(train, H=H) if len(train) > engine.FEATURE_WARMUP else None
        if model is None:
            continue
        try:
            r = engine.predict_at(model, bars, t, H)
        except Exception:  # noqa: BLE001 - 单点异常按无信号处理
            continue
        out[t] = (r.get("signal") == "up")
    return out


def _fingerprint(assets_bars, H):
    h = hashlib.sha1()
    h.update(("H=%d|" % H).encode())
    for aid, bars in sorted(assets_bars, key=lambda x: str(x[0])):
        h.update(("%s|%d|" % (aid, len(bars))).encode())
        if bars:
            h.update(("%s|%s|%.4f|" % (bars[0]["date"], bars[-1]["date"],
                                       bars[-1].get("close") or 0)).encode())
    return h.hexdigest()[:16]


def _all_signals(assets_bars, H, use_cache=True):
    """一次性计算三套复用信号（klow2/crowd/base），带缓存（R4：ledger/ 与 data/cache）。"""
    fp = _fingerprint(assets_bars, H)
    if use_cache:
        cached = _read_json(SIGNALS_CACHE_PATH)
        if cached and cached.get("fingerprint") == fp and cached.get("h") == H:
            return cached["assets"]
    out = {}
    for aid, bars in assets_bars:
        feats = _features_list(bars)
        out[str(aid)] = {
            "klow2": _klow2_fired(bars, feats, H),
            "crowd": _crowd_fired(bars, feats, H),
            "base": _base_fired(bars, H),
        }
    _write_json(SIGNALS_CACHE_PATH, {"fingerprint": fp, "h": H, "assets": out})
    return out


# ---------------- 内置因子定义（引擎在用；机制 §9.3 复用原语） ----------------

def klow2_definition():
    return {
        "factor_id": "klow2", "name": "KLOW2 下影线否决",
        "kind": "binary_signal", "orientation": "higher_bearish", "role_hint": "veto",
        "horizon": 1, "inputs": ["low", "open", "close", "high"],
        "normalization": "quantile_train", "params": [],
        "veto_threshold": engine.VETO_KLOW2_QUANTILE,
        "note": "下影线占振幅比处于训练段最不利 40% 时亮灯否决（复用 engine.veto_status）",
        "requested_by": "architect", "_builtin": "klow2",
    }


def crowd_definition():
    return {
        "factor_id": "crowd6", "name": "拥挤度六维复合否决",
        "kind": "binary_signal", "orientation": "higher_bearish", "role_hint": "veto",
        "horizon": 1, "inputs": ["mom5", "vr", "dev", "vpcorr", "volat", "skew"],
        "normalization": "zscore_train", "params": [],
        "veto_threshold": engine.VETO_CROWD_QUANTILE,
        "note": "六维（mom5/vr/dev/vpcorr/volat/skew）按训练段 IC 符号复合 z，最拥挤 40% 亮灯否决",
        "requested_by": "architect", "_builtin": "crowd",
    }


def production_definition(horizon=1):
    """内置因子 `production`：现生产配置（E1/E3→DDSM→双否决→出口）六窗走前。

    R2-11 / 08-backend-arch-r2 §5.1：`/review/scores` data_kind=backtest 的评估口径。
    `formula` = 定式标识，**随计算定义绑定**（09-r2 v9.2 §10.3：禁止标签与计算路径分叉；
    BLOCK-1 修复）。R2 实际接通范围 = T1（H=1）。
    """
    return {
        "factor_id": "production", "name": "生产配置（E1/E3→DDSM→双否决→出口）",
        "formula": "gate+ddsm+veto",
        "kind": "binary_signal", "orientation": "higher_bullish", "role_hint": "score",
        "horizon": int(horizon), "inputs": ["open", "high", "low", "close", "volume"],
        "normalization": "none", "params": [], "veto_threshold": None,
        "note": "现生产信号：gate+ddsm>0.52+双否决（走前 purge=H+2；ADR-0006）",
        "requested_by": "architect", "_builtin": "production",
    }


BUILTINS = {"klow2": klow2_definition, "crowd": crowd_definition,
            "crowd6": crowd_definition, "production": production_definition}


# ---------------- 数据加载 ----------------

def load_monitored_bars(allow_network=False):
    """监控资产代理日线（A/B 档）；失败回退 data/cache/bars/*.json（离线可复现）。"""
    out = []
    try:
        import holdings as holdings_mod
        import estimator
        hs = holdings_mod.ensure_holdings().get("holdings", [])
        for h in hs:
            if h.get("tier") in ("A", "B") and h.get("proxy_code"):
                bars, _m = estimator.get_bars(h["proxy_code"], allow_network=allow_network)
                if bars:
                    out.append((h["proxy_code"], bars))
    except Exception:  # noqa: BLE001
        out = []
    if out:
        return out
    import glob
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "cache", "bars", "*.json"))):
        try:
            with io.open(p, "r", encoding="utf-8") as f:
                o = json.load(f)
            rows = o.get("rows") or []
            if rows:
                out.append((o.get("code") or os.path.basename(p)[:-5], rows))
        except (IOError, OSError, ValueError):
            continue
    return out


# ---------------- 六窗走前回测（机制 §2/§3） ----------------

def _union_calendar(assets_bars):
    return sorted({b["date"] for _a, bars in assets_bars for b in bars if b.get("date")})


def _window_bounds(calendar):
    n = len(calendar)
    if n == 0:
        return {}, None
    hold_idx = max(0, n - HOLDOUT_DAYS)
    holdout_start = calendar[hold_idx]
    end_idx = hold_idx
    bounds = {}
    bounds["d15"] = (max(0, end_idx - 15), end_idx)
    bounds["d30"] = (max(0, end_idx - 30), end_idx)
    bounds["d60"] = (max(0, end_idx - 60), end_idx)
    try:
        hd = datetime.strptime(holdout_start, "%Y-%m-%d").date()
    except ValueError:
        hd = None
    for w, months in (("m6", 6), ("m24", 24)):
        start_idx = 0
        if hd is not None:
            y = hd.year
            m = hd.month - months
            while m <= 0:
                m += 12
                y -= 1
            cutoff = "%04d-%02d-%02d" % (y, m, hd.day)
            for i, d in enumerate(calendar):
                if d >= cutoff:
                    start_idx = i
                    break
        bounds[w] = (start_idx, end_idx)
    bounds["full"] = (0, end_idx)
    return bounds, holdout_start


def _collect(assets_bars, fired_map, dates_set, holdout_start, H):
    """返回 records=[(asset, t, fired-or-None, fwd-or-None)]，仅含 fwd 可算的日。"""
    recs = []
    for aid, bars in assets_bars:
        fired = fired_map.get(str(aid)) or fired_map.get(aid)
        if fired is None:
            continue
        n = len(bars)
        for t in range(n):
            if bars[t].get("date") not in dates_set:
                continue
            if t + H >= n:
                continue
            if bars[t + H].get("date") >= holdout_start:
                continue
            c0 = bars[t].get("close")
            c1 = bars[t + H].get("close")
            fwd = (c1 / c0 - 1.0) if (c0 and c0 > 0 and c1 is not None) else None
            recs.append((str(aid), t, fired[t] if t < len(fired) else None, fwd))
    return recs


def _independent(items, H):
    """独立触发日去重叠（机制 §2.5：同资产内 t - last >= H）。"""
    out = []
    last = {}
    for aid, t in sorted(items, key=lambda x: (x[0], x[1])):
        if aid in last and (t - last[aid]) < H:
            continue
        last[aid] = t
        out.append((aid, t))
    return out


def _analyze_window(records, orientation, w, H):
    triggers = [(a, t, f) for (a, t, fired, f) in records if fired is True and f is not None]
    universe = [(a, t, f) for (a, t, _fired, f) in records if f is not None]
    ind_trig = _independent([(a, t) for a, t, _f in triggers], H)
    trig_map = {(a, t): f for a, t, f in triggers}
    ind_univ = _independent([(a, t) for a, t, _f in universe], H)
    univ_map = {(a, t): f for a, t, f in universe}
    n_ind = len(ind_trig)
    hits = sum(1 for (a, t) in ind_trig if _is_hit(orientation, trig_map[(a, t)]))
    hit_rate = (hits / float(n_ind)) if n_ind else None
    ups = sum(1 for (a, t) in ind_univ if (univ_map[(a, t)] or 0) > 0)
    always_up = (ups / float(len(ind_univ))) if ind_univ else None
    baseline = None
    if always_up is not None:
        baseline = max(always_up, 1.0 - always_up)
    lift = (hit_rate / baseline) if (hit_rate is not None and baseline) else None
    k = k_lift_of(lift)
    adm = admission_of(n_ind, WINDOW_NW[w])
    score = k * WINDOW_WEIGHTS[w] * adm
    delta_pp = (hit_rate - baseline) if (hit_rate is not None and baseline is not None) else None
    t_val = None
    if n_ind >= 2:
        xs = [1.0 if _is_hit(orientation, trig_map[(a, t)]) else 0.0 for (a, t) in ind_trig]
        sd = engine._stdev(xs)
        if sd > 0 and baseline is not None:
            t_val = (engine._mean(xs) - baseline) / (sd / math.sqrt(n_ind))
    return {
        "window": w, "window_label": WINDOW_LABEL[w],
        "lookback_days": (WINDOW_NW[w] if w.startswith("d") else None),
        "lift": _r4(lift), "hit_rate": _r4(hit_rate), "baseline_rate": _r4(baseline),
        "delta_pp": _r4(delta_pp), "open_count": len(triggers),
        "independent_trigger_days": n_ind, "n_w": WINDOW_NW[w],
        "admission": _r4(adm), "k_lift": _r4(k), "weight": WINDOW_WEIGHTS[w],
        "score": _r4(score), "cliff_hit": cliff_of(lift),
        "t_value": _r3(t_val), "low_sample": len(triggers) < 20,
    }, ind_trig, ind_univ, trig_map, univ_map


def _bootstrap_percentiles(win_data, orientation, seed):
    """bootstrap 校准零分布（打乱信号日期、保频率；机制 §4.6）。"""
    rng = random.Random(seed)
    totals = []
    for _ in range(BOOTSTRAP_RUNS):
        total = 0.0
        any_w = False
        for w in WINDOWS:
            d = win_data[w]
            n_ind = len(d["ind_trig"])
            univ = d["univ_map"]
            if n_ind == 0 or len(univ) == 0:
                continue
            keys = list(univ.keys())
            sample = rng.sample(keys, min(n_ind, len(keys)))
            hits = sum(1 for k in sample if _is_hit(orientation, univ[k]))
            hit_rate = hits / float(len(sample)) if sample else None
            baseline = d["baseline"]
            if hit_rate is None or not baseline:
                continue
            lift = hit_rate / baseline
            k = k_lift_of(lift)
            adm = admission_of(n_ind, WINDOW_NW[w])
            total += k * WINDOW_WEIGHTS[w] * adm
            any_w = True
        if any_w:
            totals.append(total)
    if len(totals) < 20:
        return None, None
    totals.sort()

    def pct(p):
        pos = p * (len(totals) - 1)
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        if lo == hi:
            return totals[lo]
        return totals[lo] * (hi - pos) + totals[hi] * (pos - lo)
    return {"p50": _r4(pct(0.50)), "p90": _r4(pct(0.90)), "p95": _r4(pct(0.95)),
            "p99": _r4(pct(0.99)), "p995": _r4(pct(0.995))}, totals


def _normalize_bars(assets_bars):
    """接受 [(id,bars)] / [bars] / {id: bars} 三种形态。"""
    if isinstance(assets_bars, dict):
        return [(str(k), v) for k, v in assets_bars.items()]
    out = []
    for i, item in enumerate(assets_bars):
        if isinstance(item, tuple) and len(item) == 2:
            out.append((str(item[0]), item[1]))
        else:
            out.append((str(i), item))
    return out


def evaluate(definition, assets_bars, frozen_config=None, candidate_id=None,
             base_fired=None, incumbent_series=None, do_bootstrap=True,
             use_cache=True):
    """深度模块：definition + assets_bars + frozen_config -> Scorecard（契约 §5.37）。"""
    frozen = frozen_config or engine.frozen_params()
    H = int(definition.get("horizon") or 1)
    assets = _normalize_bars(assets_bars or [])
    if not assets:
        return _empty_card(definition, candidate_id)
    orientation = definition.get("orientation") or "higher_bullish"
    builtin = definition.get("_builtin")
    if builtin and builtin in BUILTINS:
        builtin = BUILTINS[builtin].__name__.replace("_definition", "")

    allsig = None
    if use_cache:
        try:
            allsig = _all_signals(assets, H, use_cache=True)
        except Exception:  # noqa: BLE001 - 缓存不可用则降级为直算
            allsig = None

    fired_map = {}
    for aid, bars in assets:
        if builtin == "klow2":
            if allsig:
                fired_map[aid] = allsig[str(aid)]["klow2"]
            else:
                fired_map[aid] = _klow2_fired(bars, _features_list(bars), H)
        elif builtin == "crowd":
            if allsig:
                fired_map[aid] = allsig[str(aid)]["crowd"]
            else:
                fired_map[aid] = _crowd_fired(bars, _features_list(bars), H)
        elif builtin == "production":
            # R2-11：生产配置 = gate+ddsm+双否决+出口，走前逐日（与台账引擎同源）
            fired_map[aid] = _base_fired(bars, H)
        else:
            fired_map[aid] = _generic_fired(definition, bars)

    calendar = _union_calendar(assets)
    bounds, holdout_start = _window_bounds(calendar)
    if holdout_start is None:
        return _empty_card(definition, candidate_id)

    windows = []
    win_data = {}
    for w in WINDOWS:
        start_idx, end_idx = bounds[w]
        dates_set = set(calendar[start_idx:end_idx])
        recs = _collect(assets, fired_map, dates_set, holdout_start, H)
        wd, ind_trig, ind_univ, trig_map, univ_map = _analyze_window(recs, orientation, w, H)
        windows.append(wd)
        win_data[w] = {"win": wd, "ind_trig": ind_trig, "ind_univ": ind_univ,
                       "trig_map": trig_map, "univ_map": univ_map,
                       "baseline": wd["baseline_rate"]}

    total_score = None
    if any(w["lift"] is not None for w in windows):
        total_score = _r4(sum((w["score"] or 0.0) for w in windows if w["lift"] is not None))

    # F2 独立性：与现役因子逐日信号 Pearson 相关（训练段/评分段逐日，非重叠）
    inc_series = incumbent_series
    if inc_series is None:
        inc_series = _incumbent_series(definition, assets, H, allsig)
    f2 = _f2_independence(definition, fired_map, inc_series, assets, holdout_start)

    # F1 有效性
    lm6, ld60 = _win_lift(windows, "m6"), _win_lift(windows, "d60")
    if lm6 is not None and lm6 > 1.0:
        f1 = {"result": "pass", "detail": "lift(m6)=%.4f > 1.00" % lm6,
              "lift_m6": lm6, "lift_d60": ld60}
    elif ld60 is not None and ld60 > 1.0:
        f1 = {"result": "pass", "detail": "lift(d60)=%.4f > 1.00" % ld60,
              "lift_m6": lm6, "lift_d60": ld60}
    else:
        f1 = {"result": "fail", "detail": "lift(m6)=%s / lift(d60)=%s 均 ≤ 1.00"
              % (lm6, ld60), "lift_m6": lm6, "lift_d60": ld60}

    # F3 增量（加入现生产配置）
    base_map = base_fired
    if base_map is None and allsig:
        base_map = {aid: allsig[str(aid)]["base"] for aid, _b in assets}
    f3 = _f3_increment(definition, assets, H, base_map, fired_map, holdout_start)

    indep_full = _win_field(windows, "full", "independent_trigger_days") or 0
    if indep_full < 20:
        verdict = "insufficient_data"
        admission_passed = False
    elif f1["result"] != "pass":
        verdict, admission_passed = "rejected_f1", False
    elif f2["result"] == "fail":
        verdict, admission_passed = "rejected_f2", False
    elif builtin is None and f3["result"] == "fail":
        verdict, admission_passed = "rejected_f3", False
    else:
        verdict, admission_passed = "admitted_to_arena", True

    license_ = _license_of(total_score, indep_full, windows)
    pan = "shadow_effective" if admission_passed else None

    boot = None
    boot_pct = None
    boot_seed = int(hashlib.sha1(_canon({
        "expr": definition.get("expression"), "inputs": definition.get("inputs"),
        "kind": definition.get("kind")}).encode()).hexdigest()[:8], 16)
    if do_bootstrap and total_score is not None:
        boot, _totals = _bootstrap_percentiles(win_data, orientation, boot_seed)
        if boot and _totals:
            below = sum(1 for x in _totals if x <= total_score)
            boot_pct = _r4(below / float(len(_totals)))

    open_count = sum(w["open_count"] for w in windows)
    sample_days = len(calendar)
    sample_period = "%s..%s" % (calendar[0], holdout_start) if calendar else None
    card = {
        "candidate_id": candidate_id, "factor_id": definition.get("factor_id"),
        "name": definition.get("name", ""),
        "status": "done", "verdict": verdict, "admission_passed": admission_passed,
        "windows": windows, "total_score": total_score,
        "bootstrap_percentiles": boot, "total_score_percentile": boot_pct,
        "f1_validity": f1, "f2_independence": f2, "f3_increment": f3,
        "license": license_, "license_label": license_label(license_),
        "pan": pan, "pan_label": _pan_label(pan),
        "max_collinearity": f2.get("max_collinearity"),
        "collinear_with": f2.get("collinear_with"),
        "delta_pp": f3.get("delta_pp"), "open_count": open_count,
        "independent_trigger_days": indep_full, "sample_days": sample_days,
        "placebo_delta_pp": None,
        "placebo_min_pp": PLACEBO_MIN_PP,
        "holdout": None, "chosen_params": definition.get("params") or None,
        "frozen_config_hash": _frozen_hash(frozen),
        "definition_hash": definition_hash(definition) if definition.get("expression") else None,
        "cv_mode": "walk_forward", "purge_gap": "H+2",
        "holdout_days": HOLDOUT_DAYS, "sample_period": sample_period,
        "judges": _judges(windows, total_score, f3),
        "scored_at": _now_iso(), "as_of": calendar[-1] if calendar else None,
        "_win_data": win_data,
    }
    return card


def _empty_card(definition, candidate_id):
    return {
        "candidate_id": candidate_id, "factor_id": definition.get("factor_id"),
        "name": definition.get("name", ""), "status": "failed",
        "verdict": "insufficient_data", "admission_passed": False,
        "windows": [_null_window(w) for w in WINDOWS], "total_score": None,
        "bootstrap_percentiles": None, "total_score_percentile": None,
        "f1_validity": {"result": "na", "detail": "无可用行情", "lift_m6": None, "lift_d60": None},
        "f2_independence": {"result": "na", "detail": "无可用行情", "max_collinearity": None,
                            "collinear_with": None},
        "f3_increment": {"result": "na", "detail": "无可用行情", "delta_pp": None,
                         "open_count_new": None, "open_count_base": None, "collapse_ratio": None},
        "license": "none", "license_label": "未达线", "pan": None, "pan_label": None,
        "max_collinearity": None, "collinear_with": None, "delta_pp": None,
        "open_count": 0, "independent_trigger_days": 0, "sample_days": 0,
        "placebo_delta_pp": None, "placebo_min_pp": PLACEBO_MIN_PP, "holdout": None,
        "chosen_params": None, "frozen_config_hash": _frozen_hash(engine.frozen_params()),
        "definition_hash": None, "cv_mode": "walk_forward", "purge_gap": "H+2",
        "holdout_days": HOLDOUT_DAYS, "sample_period": None, "judges": [],
        "scored_at": None, "as_of": None,
    }


def _null_window(w):
    return {"window": w, "window_label": WINDOW_LABEL[w], "lookback_days": None,
            "lift": None, "hit_rate": None, "baseline_rate": None, "delta_pp": None,
            "open_count": 0, "independent_trigger_days": 0, "n_w": WINDOW_NW[w],
            "admission": 0.0, "k_lift": 0.0, "weight": WINDOW_WEIGHTS[w], "score": 0.0,
            "cliff_hit": None, "t_value": None, "low_sample": True}


def _win_lift(windows, w):
    return _win_field(windows, w, "lift")


def _win_field(windows, w, field):
    for x in windows:
        if x["window"] == w:
            return x.get(field)
    return None


def _pan_label(pan):
    return {"adopted": "正式盘", "shadow_retired": "淘汰影子盘",
            "shadow_effective": "有效影子盘", "frozen": "冷冻盘"}.get(pan)


def _frozen_hash(frozen):
    return hashlib.sha1(_canon(frozen).encode("utf-8")).hexdigest()[:16]


def _judges(windows, total_score, f3):
    return [
        {"judge": "lift", "scope": "分数裁判", "metric": "lift → k_lift 悬崖",
         "value": total_score, "note": "六窗 k_lift×权重×准入度之和"},
        {"judge": "t", "scope": "闸门裁判", "metric": "独立触发日 t 值",
         "value": _win_field(windows, "full", "t_value"),
         "note": "显著性未过不放行"},
        {"judge": "admission", "scope": "折扣裁判", "metric": "独立触发日 / N_w",
         "value": _win_field(windows, "full", "admission"),
         "note": "样本不足按比例打折"},
        {"judge": "backtest", "scope": "晋升裁判", "metric": "实测 Δ / open_count",
         "value": f3.get("delta_pp"), "note": "最终晋升以走前回测 + A/B 为准"},
    ]


def _candidate_identity_ids(definition):
    """候选信号身份集合（F2 自比对排除用；含别名，如 crowd6↔crowd）。

    来源：`factor_id` / `name` / `_builtin` 键 / 同一内置实现的全部键名与实现名。
    自比对 corr≡1.0 属伪影（候选 vs 自身别名），不得作为共线判据。
    """
    ids = set()
    for k in ("factor_id", "name"):
        v = definition.get(k)
        if v:
            ids.add(str(v))
    key = definition.get("_builtin")
    if key:
        ids.add(str(key))
        impl = BUILTINS.get(key)
        if impl is not None:
            ids.add(str(impl.__name__).replace("_definition", ""))
            for k, fn in BUILTINS.items():
                if fn is impl:
                    ids.add(str(k))
    return ids


def _incumbent_series(definition, assets, H, allsig):
    """现役因子逐日系列（klow2/crowd），排除候选自身（含别名；R3/F2 伪影修复）。"""
    exclude = _candidate_identity_ids(definition)
    out = {}
    for name in ("klow2", "crowd"):
        if name in exclude:
            continue
        out[name] = {}
        for aid, bars in assets:
            if allsig:
                out[name][aid] = allsig[str(aid)][name]
            elif name == "klow2":
                out[name][aid] = _klow2_fired(bars, _features_list(bars), H)
            else:
                out[name][aid] = _crowd_fired(bars, _features_list(bars), H)
    return out


def _f2_independence(definition, fired_map, inc_series, assets, holdout_start=None):
    exclude = _candidate_identity_ids(definition)   # 候选自身（含别名）不参与比对
    best = None
    best_id = None
    for name, series in (inc_series or {}).items():
        if name in exclude:
            continue
        xs, ys = [], []
        for aid, bars in assets:
            cand = fired_map.get(aid)
            inc = series.get(aid) or series.get(str(aid))
            if cand is None or inc is None:
                continue
            for i in range(min(len(cand), len(inc))):
                if holdout_start and bars[i].get("date") >= holdout_start:
                    break
                if cand[i] is None or inc[i] is None:
                    continue
                xs.append(1.0 if cand[i] else 0.0)
                ys.append(1.0 if inc[i] else 0.0)
        if len(xs) < 3:
            continue
        c = abs(engine._corr(xs, ys))
        if best is None or c > best:
            best, best_id = c, name
    if best is None:
        return {"result": "pass", "detail": "无现役因子或无共同样本，F2 视为不适用",
                "max_collinearity": None, "collinear_with": None}
    passed = best < F2_MAX_COLLINEARITY
    return {"result": "pass" if passed else "fail",
            "detail": "max|corr|=%.4f vs %s（阈值 <0.70）" % (best, best_id),
            "max_collinearity": _r4(best), "collinear_with": best_id}


def _f3_increment(definition, assets, H, base_map, fired_map, holdout_start):
    if not base_map:
        return {"result": "na", "detail": "现生产配置信号不可用",
                "delta_pp": None, "open_count_new": None, "open_count_base": None,
                "collapse_ratio": None}
    role = definition.get("role_hint")
    orientation = definition.get("orientation") or "higher_bullish"
    base_trig, new_trig = [], []
    for aid, bars in assets:
        base = base_map.get(aid) or base_map.get(str(aid))
        cand = fired_map.get(aid)
        if base is None:
            continue
        n = len(bars)
        for t in range(n):
            if t + H >= n:
                continue
            if bars[t + H].get("date") >= holdout_start:
                continue
            c0, c1 = bars[t].get("close"), bars[t + H].get("close")
            fwd = (c1 / c0 - 1.0) if (c0 and c0 > 0 and c1 is not None) else None
            if fwd is None:
                continue
            b = bool(base[t]) if t < len(base) else False
            c = cand[t] if (cand is not None and t < len(cand)) else None
            if b:
                base_trig.append((aid, t, fwd))
            if not b:
                continue
            if role == "veto":
                keep = (c is not True)      # veto 亮灯则过滤该日
            else:
                keep = (c is True)          # score 型：需与候选同向开口
            if keep:
                new_trig.append((aid, t, fwd))

    def rate(trigs):
        ind = _independent([(a, t) for a, t, _f in trigs], H)
        m = {(a, t): f for a, t, f in trigs}
        if not ind:
            return None, 0
        hits = sum(1 for (a, t) in ind if _is_hit(orientation, m[(a, t)]))
        return hits / float(len(ind)), len(trigs)
    base_rate, base_cnt = rate(base_trig)
    new_rate, new_cnt = rate(new_trig)
    delta = None if (base_rate is None or new_rate is None) else (new_rate - base_rate)
    collapse = (new_cnt / float(base_cnt)) if base_cnt > 0 else None
    if base_cnt == 0:
        result, detail = "na", "现生产配置无开口样本"
    elif delta is None:
        result, detail = "na", "增量不可算（样本不足）"
    else:
        ok = delta >= F3_DELTA_MIN_PP and collapse is not None and collapse >= F3_COLLAPSE_MIN
        result = "pass" if ok else "fail"
        detail = ("Δ=%+.4fpp, 开口 %d/%d(%.0f%%)"
                  % (delta * 100, new_cnt, base_cnt, (collapse or 0) * 100))
    return {"result": result, "detail": detail, "delta_pp": _r4(delta),
            "open_count_new": new_cnt, "open_count_base": base_cnt,
            "collapse_ratio": _r4(collapse), "base_hit_rate": _r4(base_rate)}


# ---------------- 账本与盘位 ----------------

def _gen_candidate_id():
    return "cand_%s_%s" % (datetime.now().strftime("%Y%m%d_%H%M%S"), os.urandom(2).hex())


def _gen_factor_id():
    seq = len(_read_jsonl(CANDIDATES_PATH)) + 1
    return "f_%04d" % seq


def _gen_task_id():
    return "tsk_%s_%s" % (datetime.now().strftime("%Y%m%d_%H%M%S"), os.urandom(2).hex())


def submit_candidate(body, assets_bars=None, run=True, use_cache=True):
    """L0/L1/L2：校验 → 落候选账本 → 回测 → 记分卡 INSERT-ONLY（机制 §2.1/§8.2）。"""
    definition = dict(body or {})
    validate_definition(definition)
    factor_id = definition.get("factor_id") or _gen_factor_id()
    definition["factor_id"] = factor_id
    # factor_id 冲突（已采纳/已提交）
    for f in read_adopted():
        if f.get("factor_id") == factor_id:
            raise errors.ApiError(errors.E_CONFLICT, "factor_id 已存在",
                                  {"factor_id": factor_id})
    dhash = definition_hash(definition)
    for c in _read_jsonl(CANDIDATES_PATH):
        if c.get("definition_hash") == dhash:
            card = get_scorecard(c["candidate_id"])
            card["verdict"] = "duplicate"
            return {"candidate_id": c["candidate_id"], "factor_id": c.get("factor_id"),
                    "definition_hash": dhash, "status": "done",
                    "task_id": c.get("task_id"), "submitted_at": c.get("submitted_at"),
                    "duplicate": True, "scorecard": card}

    candidate_id = _gen_candidate_id()
    submitted_at = _now_iso()
    task_id = _gen_task_id()
    _append_jsonl(CANDIDATES_PATH, {
        "candidate_id": candidate_id, "factor_id": factor_id,
        "definition_hash": dhash, "definition": definition,
        "requested_by": definition.get("requested_by") or "orchestrator",
        "submitted_at": submitted_at, "status": "submitted", "task_id": task_id,
    })
    if not run:
        return {"candidate_id": candidate_id, "factor_id": factor_id,
                "definition_hash": dhash, "status": "backtesting",
                "task_id": task_id, "submitted_at": submitted_at}
    if assets_bars is None:
        assets_bars = load_monitored_bars(allow_network=False)
    card = evaluate(definition, assets_bars, engine.frozen_params(),
                    candidate_id=candidate_id, use_cache=use_cache)
    card["candidate_id"] = candidate_id
    card["definition_hash"] = dhash
    card.pop("_win_data", None)
    _append_jsonl(SCORECARDS_PATH, card)
    _record_scan(definition, card)
    _record_arena(definition, card)
    return {"candidate_id": candidate_id, "factor_id": factor_id,
            "definition_hash": dhash, "status": card.get("status", "done"),
            "task_id": task_id, "submitted_at": submitted_at, "scorecard": card}


def _record_scan(definition, card):
    f1, f2, f3 = card.get("f1_validity", {}), card.get("f2_independence", {}), card.get("f3_increment", {})
    _append_jsonl(SCAN_HISTORY_PATH, {
        "record_id": "scan_%s" % card.get("candidate_id"),
        "scan_date": _today(),
        "candidate": definition.get("name", ""),
        "f1_result": f1.get("result", "not_run"), "f1_detail": f1.get("detail", ""),
        "f2_result": f2.get("result", "not_run"), "f2_detail": f2.get("detail", ""),
        "f3_result": f3.get("result", "not_run"), "f3_detail": f3.get("detail", ""),
        "verdict": card.get("verdict"), "verdict_text": _verdict_text(card.get("verdict")),
        "nomination_week": datetime.now().strftime("%G-W%V"),
        "cooldown_until": _cooldown_date(), "created_at": _now_iso(),
    })


def _record_arena(definition, card):
    cid = card.get("candidate_id")
    for w in card.get("windows") or []:
        _append_jsonl(ARENA_PATH, {
            "config_id": cid, "config_name": definition.get("name", ""),
            "config_kind": "candidate", "is_leave_one_out": False,
            "window": w["window"], "open_count": w.get("open_count"),
            "hit_rate": w.get("hit_rate"), "paired_delta_pp": w.get("delta_pp"),
            "created_at": _now_iso(),
        })


def _verdict_text(v):
    return {"admitted_to_arena": "进入有效影子盘", "rejected_f1": "未过 F1，回落候选池",
            "rejected_f2": "未过 F2（共线），回落候选池",
            "rejected_f3": "未过 F3（增量），回落候选池",
            "insufficient_data": "样本不足，不进 F2/F3", "duplicate": "同定义已回测"}.get(v, "")


def _cooldown_date():
    return (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")


def get_scorecard(candidate_id, include_windows=True):
    """返回 Scorecard；未完成给 status=backtesting 骨架（契约 §6.8）。"""
    cand = None
    for c in _read_jsonl(CANDIDATES_PATH):
        if c.get("candidate_id") == candidate_id:
            cand = c
            break
    if cand is None:
        raise errors.ApiError(errors.E_NOT_FOUND, "未找到该候选",
                              {"candidate_id": candidate_id})
    card = None
    for s in _read_jsonl(SCORECARDS_PATH):
        if s.get("candidate_id") == candidate_id:
            card = s
    if card is None:
        card = {
            "candidate_id": candidate_id, "factor_id": cand.get("factor_id"),
            "name": (cand.get("definition") or {}).get("name", ""),
            "status": "backtesting", "verdict": None, "admission_passed": None,
            "windows": [_null_window(w) for w in WINDOWS], "total_score": None,
            "bootstrap_percentiles": None, "total_score_percentile": None,
            "f1_validity": {"result": "not_run", "detail": "回测中", "lift_m6": None, "lift_d60": None},
            "f2_independence": {"result": "not_run", "detail": "回测中", "max_collinearity": None,
                                "collinear_with": None},
            "f3_increment": {"result": "not_run", "detail": "回测中", "delta_pp": None,
                             "open_count_new": None, "open_count_base": None, "collapse_ratio": None},
            "license": "none", "license_label": "未达线", "pan": None, "pan_label": None,
            "max_collinearity": None, "collinear_with": None, "delta_pp": None,
            "open_count": 0, "independent_trigger_days": 0, "sample_days": 0,
            "placebo_delta_pp": None, "placebo_min_pp": PLACEBO_MIN_PP, "holdout": None,
            "chosen_params": None,
            "frozen_config_hash": _frozen_hash(engine.frozen_params()),
            "definition_hash": cand.get("definition_hash"), "cv_mode": "walk_forward",
            "purge_gap": "H+2", "holdout_days": HOLDOUT_DAYS, "sample_period": None,
            "judges": [], "scored_at": None, "as_of": None,
        }
    card = dict(card)
    card.pop("_win_data", None)
    if not include_windows:
        card["windows"] = None
    return card


# ---------------- 采纳盘（真实回测填盘） ----------------

def read_adopted():
    obj = _read_json(ADOPTED_PATH)
    if isinstance(obj, list):
        return obj
    return []


def build_adopted_pan(assets_bars=None, write=True, use_cache=True):
    """用真实回测跑 KLOW2 与拥挤度六维，写入因子盘 adopted（禁 legacy 数字）。"""
    if assets_bars is None:
        assets_bars = load_monitored_bars(allow_network=False)
    records = []
    for defn in (klow2_definition(), crowd_definition()):
        card = evaluate(defn, assets_bars, engine.frozen_params(),
                        candidate_id=None, do_bootstrap=True, use_cache=use_cache)
        records.append(_adopted_record(defn, card))
    if write:
        _write_json(ADOPTED_PATH, records)
    return records


def _adopted_record(defn, card):
    windows = {}
    for w in card.get("windows") or []:
        windows[w["window"]] = {
            "lift": w.get("lift"), "hit_rate": w.get("hit_rate"),
            "baseline_rate": w.get("baseline_rate"), "delta_pp": w.get("delta_pp"),
            "k_lift": w.get("k_lift"), "weight": w.get("weight"),
            "admission": w.get("admission"), "score": w.get("score"),
            "independent_trigger_days": w.get("independent_trigger_days"),
            "open_count": w.get("open_count"), "n_w": w.get("n_w"),
            "cliff_hit": w.get("cliff_hit"), "low_sample": w.get("low_sample"),
        }
    return {
        "factor_id": defn.get("factor_id"), "name": defn.get("name"),
        "role": "adopted", "role_label": "否决位", "status": "active",
        "license": card.get("license"), "license_label": card.get("license_label"),
        "total_score": card.get("total_score"), "windows": windows,
        "independent_trigger_days": card.get("independent_trigger_days"),
        "open_count": card.get("open_count"),
        "max_collinearity": card.get("max_collinearity"),
        "collinear_with": card.get("collinear_with"),
        "delta_pp": card.get("delta_pp"),
        "admission_passed": card.get("admission_passed"),
        "death_condition": "lift(m24) < 1.00 或留一法移除后 Δ 升 ≥0.5pp 持续 30 天",
        "note": defn.get("note", ""), "ab_progress": None,
        "added_at": _today(),
        "backtest": {
            "mode": "walk_forward", "purge_gap": card.get("purge_gap"),
            "holdout_days": card.get("holdout_days"),
            "sample_period": card.get("sample_period"),
            "scored_at": card.get("scored_at"),
            "bootstrap_percentiles": card.get("bootstrap_percentiles"),
            "total_score_percentile": card.get("total_score_percentile"),
            "verdict": card.get("verdict"),
        },
    }


def ensure_adopted_pan(assets_bars=None, use_cache=True):
    """启动预热：正式盘账本缺失时用真实回测生成（已存在则不覆盖，保持 INSERT-ONLY 语义）。"""
    if os.path.isfile(ADOPTED_PATH):
        return read_adopted()
    return build_adopted_pan(assets_bars=assets_bars, write=True, use_cache=use_cache)


def measured_bootstrap():
    """从已采纳因子回测中取一份实测零分布（供 score-chain 参考，缺失 null）。"""
    for f in read_adopted():
        bt = f.get("backtest") or {}
        if bt.get("bootstrap_percentiles"):
            return bt["bootstrap_percentiles"]
    return None


# ---------------- R2：生产配置回测 + C→B 验证 / 代理复核（R2-06 / R2-11 / R2-04） ----------------

def evaluate_production(assets_bars, horizon=1, frozen_config=None, use_cache=True,
                        do_bootstrap=False):
    """生产配置（内置因子 `production`）六窗走前回测 → Scorecard。

    口径：08-backend-arch-r2 §5.1（R2-11）；`/review/scores` 三 horizon 各自评估，
    主值取 full 全样本窗（v9.1/R-2）。
    """
    return evaluate(production_definition(horizon), assets_bars, frozen_config,
                    candidate_id=None, do_bootstrap=do_bootstrap, use_cache=use_cache)


def review_verdict(evidence):
    """三层顺序判定（冻结，落 10-arch-review-r2 v2 §2.4；ADR-0011；SHOULD-1 修订）。

    ① 样本门槛：独立触发日 <20 **或 n_test<20**（二者任一命中）→ `hold`（挂档观察；
       不得升档、不得降档）。`n_test` 来自代理质量证据道（`proxy_quality.json`），
       缺失（None）时仅按独立触发日判定；
    ② 口径回退（估值线）不在此函数裁决（双段/前 20 回退 tier 不动，另行登记）；
    ③ 样本足：lift(full)≥1.0 且 Δ≥0（R2-04 清单另加方向命中率≥0.60）→ `pass`，
       否则 `downgrade`（明示降档）。
    一票否决（不等样本）：代理断供/映射失效/数据不可得 → `downgrade` 并标原因。
    返回 "hold" / "pass" / "downgrade"。
    """
    ev = evidence or {}
    if not ev.get("has_data"):
        return "downgrade"
    indep = ev.get("independent_trigger_days") or 0
    try:
        indep = int(indep)
    except (TypeError, ValueError):
        indep = 0
    n_test = ev.get("n_test")
    try:
        n_test = int(n_test) if n_test is not None else None
    except (TypeError, ValueError):
        n_test = None
    if indep < MIN_INDEP_DAYS or (n_test is not None and n_test < MIN_INDEP_DAYS):
        return "hold"
    lift = ev.get("lift_full")
    delta = ev.get("delta_full")
    dir_hit = ev.get("dir_hit_rate")
    ok = (lift is not None and float(lift) >= 1.0
          and delta is not None and float(delta) >= 0.0)
    if dir_hit is not None and float(dir_hit) < DIR_HIT_FLOOR:
        ok = False
    return "pass" if ok else "downgrade"


def _tier_review_evidence(code, proxy, allow_network=True):
    """单资产证据收集：生产配置六窗（full 为主）+ 代理质量证据道（R2-04 首选证据）。"""
    import estimator
    import valuation

    evidence = {"has_data": False, "proxy_code": proxy,
                "evidence_source": "production_backtest"}
    card = None
    if proxy:
        try:
            bars, _meta = estimator.get_bars(proxy, allow_network=allow_network)
        except Exception:  # noqa: BLE001
            bars = []
        if bars:
            try:
                card = evaluate_production([(code, bars)], horizon=1, use_cache=True,
                                           do_bootstrap=False)
            except Exception:  # noqa: BLE001 - 单资产回测失败按无证据
                card = None
    if card and card.get("sample_days"):
        win = next((w for w in (card.get("windows") or [])
                    if w.get("window") == "full"), None) or {}
        evidence.update({
            "has_data": True,
            "independent_trigger_days": win.get("independent_trigger_days"),
            "lift_full": win.get("lift"),
            "delta_full": win.get("delta_pp"),
            "hit_rate_full": win.get("hit_rate"),
            "baseline_rate_full": win.get("baseline_rate"),
            "open_count_full": win.get("open_count"),
            "sample_days": card.get("sample_days"),
            "six_windows": [{k: w.get(k) for k in
                             ("window", "lift", "hit_rate", "baseline_rate", "delta_pp",
                              "independent_trigger_days", "open_count")}
                            for w in (card.get("windows") or [])],
        })
    # R2-04 首选证据：代理质量重建证据道（与展示通道分键分文件，ADR-0015）
    try:
        pq = valuation.load_proxy_quality().get(code) or {}
    except Exception:  # noqa: BLE001
        pq = {}
    if pq:
        evidence["proxy_quality"] = {
            "dir_hit_rate": pq.get("dir_hit_rate"), "mae_rate": pq.get("mae_rate"),
            "n_test": pq.get("n_test"), "proxy_code": pq.get("proxy_code"),
        }
        evidence["dir_hit_rate"] = pq.get("dir_hit_rate")
        # SHOULD-1：层① 的 n_test 门槛取代理质量证据道样本数（缺失 None → 仅按独立触发日判）
        evidence["n_test"] = pq.get("n_test")
        evidence["evidence_source"] = ("proxy_quality+production_backtest"
                                       if evidence.get("has_data") else "proxy_quality")
    return evidence, card


def verify_tiers(targets=None, batch_id=None, allow_network=True, kind="tier_validation"):
    """C→B 验证批次 / 9 只代理复核（R2-06 / R2-04；08-backend-arch-r2 §4.1/§4.4）。

    - 逐只跑单资产生产配置六窗走前；按 `review_verdict` 三层判定出结论；
    - 结论落 `data/review/tier_reviews.jsonl`（INSERT-ONLY：证据含六窗 lift/Δ/独立触发日/样本）；
    - `holdings.apply_tier_reviews()` 幂等更新 tier/verify_* 字段；
    - 防稀释闸（D-4）：>3 只同时挂档 → 追加复审事件（视为验证批次设计异常）。
    返回批次摘要；`targets` 缺省 = 当前 C 档全部。
    """
    import holdings as holdings_mod

    hs = holdings_mod.load_holdings().get("holdings", [])
    if targets is None:
        targets = [h.get("code") for h in hs if h.get("tier") == "C"]
    targets = [str(t) for t in (targets or [])]
    batch_id = batch_id or ("vb_%s" % datetime.now().strftime("%Y%m%d_%H%M"))
    today = _today()
    rows = []
    verdicts = []
    hold_count = 0
    for code in targets:
        h = next((x for x in hs if str(x.get("code")) == code), None)
        tier_before = (h or {}).get("tier")
        proxy = (h or {}).get("proxy_code")
        evidence, _card = _tier_review_evidence(code, proxy, allow_network=allow_network)
        verdict = review_verdict(evidence)
        if verdict == "hold":
            hold_count += 1
            import valuation
            review_date = valuation.next_trading_days(today, REVIEW_HOLD_DAYS)
            status = "validating"
            tier_after = tier_before
            reason = ("样本不足（独立触发日 %s、n_test %s；门槛均为 20）：挂档观察，"
                      "档位/口径不变；复查日 %s（自证据就绪日 +30 交易日）"
                      % (evidence.get("independent_trigger_days"),
                         evidence.get("n_test"), review_date))
            note = "低样本·观察"
        elif verdict == "pass":
            review_date = None
            status = "validated"
            tier_after = "B" if tier_before == "C" else tier_before
            note = "验证通过：升 B" if tier_before == "C" else "复核通过：保留"
            reason = ("生产配置六窗：lift(full)=%s Δ(full)=%s；代理质量方向命中率=%s"
                      % (evidence.get("lift_full"), evidence.get("delta_full"),
                         evidence.get("dir_hit_rate")))
        else:  # downgrade
            review_date = None
            status = "validation_failed"
            tier_after = "D"
            note = "验证未通过：明示降档"
            if not proxy or not evidence.get("has_data"):
                reason = "代理断供/映射失效/数据不可得（一票否决，不等样本）：明示降档"
            else:
                reason = ("不达标（lift(full)=%s 或 Δ(full)=%s 或方向命中率=%s <0.60）："
                          "明示降档，移出预测 universe"
                          % (evidence.get("lift_full"), evidence.get("delta_full"),
                             evidence.get("dir_hit_rate")))
        rows.append({
            "batch_id": batch_id, "at": _now_iso(), "kind": kind, "code": code,
            "tier_before": tier_before, "tier_after": tier_after,
            "verdict": verdict, "verify_status": status,
            "review_date": review_date, "reason": reason, "note": note,
            "evidence": evidence, "proxy_code": proxy,
        })
        verdicts.append({"code": code, "verdict": verdict, "tier_before": tier_before,
                         "tier_after": tier_after, "verify_status": status,
                         "review_date": review_date})
    for r in rows:
        _append_jsonl(TIER_REVIEWS_PATH, r)
    holdings_mod.apply_tier_reviews()
    dilution = hold_count > 3
    if dilution:
        _append_jsonl(TIER_REVIEWS_PATH, {
            "batch_id": batch_id, "at": _now_iso(), "kind": "dilution_gate_alert",
            "hold_count": hold_count,
            "note": "同时挂档 >3 只 → 视为验证批次设计异常，触发架构×PM 复审（D-4）",
        })
    return {"batch_id": batch_id, "targets": targets, "verdicts": verdicts,
            "hold_count": hold_count, "dilution_gate_triggered": dilution,
            "as_of": today}


def log_proxy_change(code, old_proxy_code, new_proxy_code, reason=""):
    """换代理事件写 tier_reviews.jsonl（映射变更时点，供回填复算追溯；R-1）。"""
    row = {
        "kind": "proxy_change", "at": _now_iso(), "code": str(code),
        "old_proxy_code": old_proxy_code, "new_proxy_code": new_proxy_code,
        "reason": reason or "代理映射变更",
        "note": "换代理事件：后续 t*_real 复算以回填时映射为准（backfill_proxy_code）",
    }
    _append_jsonl(TIER_REVIEWS_PATH, row)
    return row
