# -*- coding: utf-8 -*-
"""预测核心引擎：E1/E3 门 → DDSM(125 格/K=4/p=0.25/MIN_N=15/收缩 10) → 双否决(拥挤度/KLOW2) → 出口 P>0.52。

严格依据：
- PROJECT_BRIEF §5.1（核心逻辑）
- docs/01-architecture/08-backend-arch.md §4（特征/门/DDSM/双否决/出口）、§9.1/§9.2（立方体/六维快照）
冻结参数不得改动（改动须重走六关）。纯标准库：math / statistics / random。
标签定义：up = 1 若 close[T+H] > close[T]（H=1/3/15）。
"""

import math
import random

# ---- 冻结参数（契约 §5.14） ----
K_NOISE = 4
P_PERTURB = 0.25
MIN_N = 15
SHRINK = 10
BAND = 0.02
EXIT_THRESHOLD = 0.5 + BAND  # 0.52
VETO_CROWD_QUANTILE = 0.60
VETO_KLOW2_QUANTILE = 0.40
SEED = 20260912
FEATURE_WARMUP = 25  # 至少需要的预热 bar 数（vr 需 t-20，约 25 安全）

DIMS = ["r2", "om", "vr"]
CROWD_DIMS = ["mom5", "vr", "dev", "vpcorr", "volat", "skew"]
FEATURE_LABELS = {
    "r2": "趋势线性度 R²", "om": "隔夜动量", "vr": "量比",
    "mom5": "5 日动量", "dev": "乖离率", "vpcorr": "量价相关",
    "volat": "波动率", "skew": "偏度",
}
FEATURE_FORMULA = {
    "r2": "近 L=5 个交易日对数收益对时间线性回归的 R²",
    "om": "open[t]/close[t-1] − 1",
    "vr": "volume[t] / mean(volume[t-20..t-1])",
    "mom5": "close[t]/close[t-5] − 1",
    "dev": "close[t]/MA20(close) − 1",
    "vpcorr": "近 20 日 return 与 volume_change 相关系数",
    "volat": "近 20 日日收益标准差",
    "skew": "近 20 日日收益偏度",
}
RAW_UNIT = {
    "r2": "比率", "om": "比率", "vr": "倍数", "mom5": "比率",
    "dev": "比率", "vpcorr": "相关系数", "volat": "比率", "skew": "比率",
}

# ---- 枚举（契约 §1.3） ----
GATE_LABEL = {"E1": "跳空", "E3": "无量急跌", "none": "未触发"}
SIGNAL_LABEL = {"up": "涨", "gray": "灰", "abstain": "弃权"}
WINDOW_FORMULA = {"T1": "gate+ddsm+veto", "T3": "gate_only", "T15": "gate+ddsm"}
WINDOW_SOURCE = {"T1": "brief_5.1", "T3": "arch_baseline_v1", "T15": "arch_baseline_v1"}


# ---------------- 基础统计 ----------------

def _mean(xs):
    return sum(xs) / float(len(xs)) if xs else 0.0


def _pstdev(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(len(xs)))


def _stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(len(xs) - 1))


def _corr(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((xs[i] - mx) ** 2 for i in range(n))
    syy = sum((ys[i] - my) ** 2 for i in range(n))
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _skew(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = _mean(xs)
    sd = _pstdev(xs)
    if sd == 0:
        return 0.0
    return sum(((x - m) / sd) ** 3 for x in xs) * n / float((n - 1) * (n - 2))


def _r2(values):
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx, my = _mean(xs), _mean(values)
    sxy = sum((xs[i] - mx) * (values[i] - my) for i in range(n))
    sxx = sum((xs[i] - mx) ** 2 for i in range(n))
    syy = sum((values[i] - my) ** 2 for i in range(n))
    if sxx <= 0 or syy <= 0:
        return 0.0
    return (sxy * sxy) / (sxx * syy)


# ---------------- 特征 ----------------

def features_at(bars, t):
    """计算 bar[t] 的 3+6 维特征；数据不足返回 None。"""
    if t < FEATURE_WARMUP or t >= len(bars):
        return None
    cur = bars[t]
    prev = bars[t - 1]
    if cur["close"] <= 0 or prev["close"] <= 0:
        return None

    closes5 = [bars[i]["close"] for i in range(t - 4, t + 1)]
    logs = [math.log(closes5[i] / closes5[i - 1]) for i in range(1, 5)
            if closes5[i - 1] > 0 and closes5[i] > 0]
    r2 = _r2(logs) if len(logs) == 4 else 0.0

    om = cur["open"] / prev["close"] - 1.0 if prev["close"] > 0 else 0.0

    vols = [bars[i]["volume"] for i in range(t - 20, t)]
    mean_vol = _mean(vols)
    vr = (cur["volume"] / mean_vol) if mean_vol > 0 else None
    if vr is None:
        return None

    mom5 = cur["close"] / bars[t - 5]["close"] - 1.0
    ma20 = _mean([bars[i]["close"] for i in range(t - 19, t + 1)])
    dev = cur["close"] / ma20 - 1.0 if ma20 > 0 else 0.0

    rets = []
    vchg = []
    for i in range(t - 19, t + 1):
        if i == t - 19 and i == 0:
            continue
        c0, c1 = bars[i - 1]["close"], bars[i]["close"]
        rets.append(c1 / c0 - 1.0 if c0 > 0 else 0.0)
        v0, v1 = bars[i - 1]["volume"], bars[i]["volume"]
        vchg.append(v1 / v0 - 1.0 if v0 > 0 else 0.0)
    n = min(len(rets), len(vchg))
    rets, vchg = rets[-n:], vchg[-n:]
    vpcorr = _corr(rets, vchg)
    volat = _pstdev(rets)
    skew = _skew(rets)

    klow2 = None
    rng = cur["high"] - cur["low"]
    if rng > 0:
        klow2 = (min(cur["open"], cur["close"]) - cur["low"]) / rng

    return {
        "r2": r2, "om": om, "vr": vr,
        "mom5": mom5, "dev": dev, "vpcorr": vpcorr,
        "volat": volat, "skew": skew, "klow2": klow2,
        "close": cur["close"], "high": cur["high"], "low": cur["low"],
        "open": cur["open"],
    }


def gate_of(bars, t):
    """E1/E3 触发门；E2/E4 不实现、禁止 OR 合并。"""
    if t < 1:
        return None
    cur, prev = bars[t], bars[t - 1]
    ret = cur["close"] / prev["close"] - 1.0 if prev["close"] > 0 else 0.0
    if cur["low"] > prev["high"]:
        return "E1"
    f = features_at(bars, t)
    vr = f["vr"] if f else None
    if ret < -0.02 and vr is not None and vr < 0.8:
        return "E3"
    return None


# ---------------- DDSM 训练 ----------------

def _bin(value, bounds):
    if value is None:
        return 2
    k = 0
    for b in bounds:
        if value >= b:
            k += 1
    return min(4, max(0, k))


def _samples_from_bars(bars, H):
    """samples = [(t, features, label, fwd_return)]，只用可计算特征的样本。"""
    n = len(bars)
    out = []
    for t in range(FEATURE_WARMUP, n - H):
        f = features_at(bars, t)
        if f is None:
            continue
        c0, c1 = bars[t]["close"], bars[t + H]["close"]
        if c0 <= 0:
            continue
        fwd = c1 / c0 - 1.0
        label = 1 if c1 > c0 else 0
        out.append((t, f, fwd, label))
    return out


def train_model(bars, H=1, seed=SEED):
    """在单一 bars 上训练 DDSM+H 标签。返回 model 或 None。"""
    return train_from_samples(_samples_from_bars(bars, H), seed)


def train_global(bars_list, H=1, seed=SEED):
    """全样本聚合训练：各资产特征样本汇总后统一分档（用于 HUD 状态格覆盖）。"""
    samples = []
    for bars in bars_list:
        samples.extend(_samples_from_bars(bars, H))
    return train_from_samples(samples, seed)


def train_from_samples(samples_tuple, seed=SEED):
    samples = samples_tuple
    if len(samples) < MIN_N * 2:
        return None

    bounds = {}
    means = {}
    stds = {}
    ics = {}
    for d in DIMS + CROWD_DIMS:
        vals = [s[1][d] for s in samples if s[1].get(d) is not None]
        if len(vals) < 5:
            return None
        sv = sorted(vals)
        bounds[d] = [quantile(sv, q) for q in (0.2, 0.4, 0.6, 0.8)]
        means[d] = _mean(vals)
        stds[d] = _pstdev(vals) or 1.0
        fv = [s[1][d] for s in samples if s[1].get(d) is not None]
        fwd = [s[2] for s in samples if s[1].get(d) is not None]
        c = _corr(fv, fwd)
        ics[d] = 0 if abs(c) < 1e-9 else (1 if c > 0 else -1)

    train_rate = _mean([s[3] for s in samples])
    naive = {}
    ddsm = {}
    rng = random.Random(seed)
    for (_t, f, _fwd, label) in samples:
        cell = tuple(_bin(f[d], bounds[d]) for d in DIMS)
        _bump(naive, cell, label)
        for _k in range(K_NOISE):
            nc = []
            for di, d in enumerate(DIMS):
                v = cell[di]
                if rng.random() < P_PERTURB:
                    v = v + rng.choice((-1, 1))
                    v = min(4, max(0, v))
                nc.append(v)
            _bump(ddsm, tuple(nc), label)

    # 拥挤度训练分布
    crowd_vals = []
    for (_t, f, _fwd, _l) in samples:
        zs = []
        ok = True
        for d in CROWD_DIMS:
            if f.get(d) is None:
                ok = False
                break
            zs.append((f[d] - means[d]) / stds[d] * ics[d])
        if ok:
            crowd_vals.append(_mean(zs))
    crowd_sorted = sorted(crowd_vals)
    crowd_q60 = quantile(crowd_sorted, VETO_CROWD_QUANTILE)

    klow_vals = [f["klow2"] for (_t, f, _fwd, _l) in samples if f.get("klow2") is not None]
    klow_sorted = sorted(klow_vals)
    klow_q40 = quantile(klow_sorted, VETO_KLOW2_QUANTILE)

    return {
        "seed": seed,
        "bounds": bounds,
        "means": means,
        "stds": stds,
        "ics": ics,
        "train_rate": train_rate,
        "naive": naive,
        "ddsm": ddsm,
        "crowd_q60": crowd_q60,
        "crowd_n": len(crowd_vals),
        "crowd_mean": _mean(crowd_vals),
        "crowd_std": _pstdev(crowd_vals),
        "klow_q40": klow_q40,
        "klow_n": len(klow_vals),
        "n_samples": len(samples),
    }


def _bump(counts, cell, label):
    rec = counts.get(cell)
    if rec is None:
        rec = [0, 0]  # [n, up]
        counts[cell] = rec
    rec[0] += 1
    rec[1] += label


def cell_of(model, f):
    return tuple(_bin(f[d], model["bounds"][d]) for d in DIMS)


def naive_p(model, cell):
    # v5 SHOULD-5：研究口径原始频率 naive_up/naive_n；naive_n>0 即给，naive_n=0 → null。
    # 研究口径不设 MIN_N 门控（MIN_N 只门控生产口径 ddsm_p）；低样本由 naive_low_sample 标注。
    rec = model["naive"].get(cell)
    if not rec or rec[0] <= 0:
        return None
    return rec[1] / float(rec[0])


def ddsm_p(model, cell):
    rec = model["ddsm"].get(cell)
    if not rec:
        return model["train_rate"]
    return (rec[1] + SHRINK * model["train_rate"]) / (rec[0] + SHRINK)


# ---------------- 双否决 ----------------

def crowd_composite(model, f):
    """六维复合 z（按训练段 IC 符号等权）。任一维缺失 → (None, 'missing')。"""
    zs = []
    for d in CROWD_DIMS:
        if f.get(d) is None:
            return None, "missing"
        zs.append((f[d] - model["means"][d]) / model["stds"][d] * model["ics"][d])
    comp = _mean(zs)
    return comp, "ok"


def crowd_quantile_of(model, comp):
    if comp is None or not model.get("crowd_std"):
        return None
    # 近似分位：按正态近似（训练段分布），保持单调
    z = (comp - model["crowd_mean"]) / model["crowd_std"]
    # 标准正态 CDF 近似（Abramowitz-Stegun 7.1.26 的 erf 近似）
    q = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return min(1.0, max(0.0, q))


def veto_status(model, f):
    comp, cstat = crowd_composite(model, f)
    if cstat == "missing" or model.get("crowd_q60") is None or model.get("crowd_n", 0) < 5:
        crowd_status = "missing"
        crowd_veto = False
        crowd_q = None
    else:
        crowd_q = crowd_quantile_of(model, comp)
        if crowd_q is None:
            crowd_status = "missing"
            crowd_veto = False
        else:
            crowd_veto = comp >= model["crowd_q60"]
            crowd_status = "veto" if crowd_veto else "pass"

    klow2 = f.get("klow2")
    if klow2 is None or model.get("klow_q40") is None or model.get("klow_n", 0) < 5:
        klow_status = "missing"
        klow_veto = False
    else:
        klow_veto = klow2 <= model["klow_q40"]
        klow_status = "veto" if klow_veto else "pass"
    return {
        "composite_z": comp,
        "crowd_quantile": crowd_q,
        "crowd_veto": crowd_veto,
        "crowd_status": crowd_status,
        "klow2": klow2,
        "klow2_veto": klow_veto,
        "klow2_status": klow_status,
    }


# ---------------- 单点预测 ----------------

def predict_at(model, bars, t, H):
    """返回 dict：gate/cell/p/veto/signal/reason/metrics。"""
    f = features_at(bars, t)
    if f is None or model is None:
        return {"gate": "none", "signal": "gray", "reason": "insufficient_data",
                "p_up": None, "ddsm_state": None, "features": f, "veto": None,
                "metrics": {"insufficient": True}}
    gate = gate_of(bars, t)
    cell = cell_of(model, f)
    p = ddsm_p(model, cell)
    veto = veto_status(model, f)

    if gate is None:
        signal, reason = "gray", "gate_not_triggered"
    elif veto["crowd_status"] == "missing" or veto["klow2_status"] == "missing":
        signal, reason = "abstain", "veto_data_missing"
    elif veto["crowd_veto"]:
        signal, reason = "abstain", "veto_crowd"
    elif veto["klow2_veto"]:
        signal, reason = "abstain", "veto_klow2"
    elif p is not None and p > EXIT_THRESHOLD:
        signal, reason = "up", "ok"
    else:
        signal, reason = "gray", "below_band"

    prev = bars[t - 1]
    ret = bars[t]["close"] / prev["close"] - 1.0 if prev["close"] > 0 else 0.0
    metrics = {
        "ret_rate": round(ret, 4),
        "vr": round(f["vr"], 4) if f.get("vr") is not None else None,
        "r2": round(f["r2"], 4),
        "om": round(f["om"], 4),
        "ddsm_state": list(cell),
        "p_up": round(p, 4) if p is not None else None,
        "crowd_z": round(veto["composite_z"], 3) if veto["composite_z"] is not None else None,
        "crowd_quantile": round(veto["crowd_quantile"], 4) if veto["crowd_quantile"] is not None else None,
        "klow2": round(veto["klow2"], 4) if veto["klow2"] is not None else None,
        "klow2_quantile": None,
        "band": BAND,
        "exit_threshold": EXIT_THRESHOLD,
        "veto_crowd_status": veto["crowd_status"],
        "veto_klow2_status": veto["klow2_status"],
    }
    return {"gate": gate or "none", "signal": signal, "reason": reason,
            "p_up": p, "ddsm_state": list(cell), "features": f, "veto": veto,
            "metrics": metrics}


# ---------------- 六维输入快照（§9.2） ----------------

def inputs_snapshot(model, f):
    ddsm_3d = []
    for d in DIMS:
        raw = f.get(d)
        z = (raw - model["means"][d]) / model["stds"][d] if raw is not None else None
        lvl = _bin(raw, model["bounds"][d]) if raw is not None else None
        ic = model["ics"][d]
        ddsm_3d.append({
            "feature": d, "group": "ddsm_3d", "label": FEATURE_LABELS[d],
            "raw": round(raw, 4) if raw is not None else None,
            "raw_unit": RAW_UNIT[d],
            "z": round(z, 3) if z is not None else None,
            "level": lvl,
            "level_label": ("%d/5" % (lvl + 1)) if lvl is not None else None,
            "ic_sign": "+" if ic > 0 else ("-" if ic < 0 else "0"),
            "signed_z": round(z * ic, 3) if z is not None else None,
            "formula": FEATURE_FORMULA[d],
        })
    crowd_6d = []
    for d in CROWD_DIMS:
        raw = f.get(d)
        z = (raw - model["means"][d]) / model["stds"][d] if raw is not None else None
        ic = model["ics"][d]
        crowd_6d.append({
            "feature": d, "group": "crowd_6d", "label": FEATURE_LABELS[d],
            "raw": round(raw, 4) if raw is not None else None,
            "raw_unit": RAW_UNIT[d],
            "z": round(z, 3) if z is not None else None,
            "level": None, "level_label": None,
            "ic_sign": "+" if ic > 0 else ("-" if ic < 0 else "0"),
            "signed_z": round(z * ic, 3) if z is not None else None,
            "formula": FEATURE_FORMULA[d],
        })
    comp, _st = crowd_composite(model, f)
    cq = crowd_quantile_of(model, comp)
    crowd = {
        "composite_z": round(comp, 3) if comp is not None else None,
        "quantile": round(cq, 4) if cq is not None else None,
        "quantile_level": (min(5, max(1, int((cq or 0) * 5) + 1)) if cq is not None else None),
        "quantile_threshold": VETO_CROWD_QUANTILE,
        "is_veto": bool(cq is not None and cq >= VETO_CROWD_QUANTILE),
        "status": ("missing" if comp is None else ("veto" if cq is not None and cq >= VETO_CROWD_QUANTILE else "pass")),
        "klow2": round(f["klow2"], 4) if f.get("klow2") is not None else None,
        "klow2_quantile": None,
        "klow2_level": None,
        "klow2_threshold": VETO_KLOW2_QUANTILE,
        "klow2_is_veto": bool(model.get("klow_q40") is not None and f.get("klow2") is not None
                             and f["klow2"] <= model["klow_q40"]),
        "klow2_status": ("missing" if f.get("klow2") is None or model.get("klow_q40") is None
                         else ("veto" if f["klow2"] <= model["klow_q40"] else "pass")),
    }
    return {"ddsm_3d": ddsm_3d, "crowd_6d": crowd_6d, "crowd": crowd}


# ---------------- 状态立方体（§9.1） ----------------

VLABELS = ["≈0.55", "≈0.75", "≈0.95", "≈1.20", "≈1.55"]
CUBE_LEGEND = [
    {"min_p": 0.0, "max_p": 0.45, "label": "P<0.45 看跌"},
    {"min_p": 0.45, "max_p": 0.52, "label": "0.45–0.52 中性"},
    {"min_p": 0.52, "max_p": 0.58, "label": "0.52–0.58 弱看涨"},
    {"min_p": 0.58, "max_p": 1.0, "label": ">0.58 强看涨"},
    {"min_p": None, "max_p": None, "label": "无样本"},
]


def _color_band(p):
    if p is None:
        return "no_sample"
    if p < 0.45:
        return "P<0.45 看跌"
    if p < 0.52:
        return "0.45–0.52 中性"
    if p < 0.58:
        return "0.52–0.58 弱看涨"
    return ">0.58 强看涨"


def build_cube(code, name, bars, H=1, train_as_of=None, snapshot_at=None):
    """逐资产 125 格 naive/ddsm 双切片 + 对比卡。空样本格显式 empty。"""
    model = train_model(bars, H=H)
    if model is None:
        return None
    layers = []
    for vr_layer in range(5):
        cells = []
        filled = 0
        for r2 in range(5):
            for om in range(5):
                cell = (r2, om, vr_layer)
                nrec = model["naive"].get(cell)
                drec = model["ddsm"].get(cell)
                np_ = naive_p(model, cell)
                dp_ = ddsm_p(model, cell)
                n = nrec[0] if nrec else 0
                dn = drec[0] if drec else 0
                # v5 SHOULD-5/§10.3：filled ⟺ naive_n>0，empty ⟺ naive_n=0
                status = "filled" if n > 0 else "empty"
                # 契约 §5.25 / A-07：empty 格两 P 均 null（不得用收缩值/训练涨率冒充）
                dp_val = dp_ if status == "filled" else None
                if status == "filled":
                    filled += 1
                cells.append({
                    "state": [r2, om, vr_layer], "vr_layer": vr_layer,
                    "status": status, "is_empty": status == "empty",
                    "naive_n": n, "naive_p": round(np_, 4) if np_ is not None else None,
                    "naive_low_sample": bool(n < MIN_N),
                    "ddsm_n": dn, "ddsm_p": round(dp_val, 4) if dp_val is not None else None,
                    "color_band": _color_band(np_ if np_ is not None else dp_val),
                })
        layers.append({
            "vr_layer": vr_layer, "vr_label": VLABELS[vr_layer],
            "cell_axis": {"row": "r2", "col": "om"},
            "cells": cells, "filled_count": filled, "empty_count": 25 - filled,
        })

    # 对比卡
    def stats(key, pkey):
        vals = []
        empty = 0
        for cell, rec in model[key].items():
            p = None
            if key == "naive":
                p = naive_p(model, cell)
            else:
                p = ddsm_p(model, cell)
            if p is None:
                empty += 1
            else:
                vals.append(p)
        mean = _mean(vals) if vals else None
        std = _pstdev(vals) if len(vals) >= 2 else None
        rng = (max(vals) - min(vals)) if vals else None
        extreme = sum(1 for v in vals if v < 0.25 or v > 0.75)
        return {
            "coverage": len(vals) / 125.0,
            "mean": round(mean, 4) if mean is not None else None,
            "std": round(std, 4) if std is not None else None,
            "range": round(rng, 4) if rng is not None else None,
            "extreme": extreme, "empty": empty,
        }

    sn = stats("naive", "naive_p")
    sd = stats("ddsm", "ddsm_p")
    comparison = {
        "valid_coverage_naive_pct": round(sn["coverage"], 4),
        "valid_coverage_ddsm_pct": round(sd["coverage"], 4),
        "mean_naive": sn["mean"], "mean_ddsm": sd["mean"],
        "p_std_naive": sn["std"], "p_std_ddsm": sd["std"],
        "p_range_naive": sn["range"], "p_range_ddsm": sd["range"],
        "extreme_count_naive": sn["extreme"], "extreme_count_ddsm": sd["extreme"],
        "empty_count_naive": sn["empty"], "empty_count_ddsm": sd["empty"],
        # 走前 Δ 须真实回测产出；本期未产出 → null（契约 §6.11.7 残留风险 8）
        "walk_forward_delta_naive_pp": None,
        "walk_forward_delta_ddsm_pp": None,
        "walk_forward_delta_ddsm_lo_pp": None,
        "walk_forward_delta_ddsm_hi_pp": None,
        "note": ("左：未加噪的原始离散格（真实档位计数，样本稀疏时 P 不稳）；"
                 "右：K=4 加噪副本 + 向训练段涨率收缩后的还原离散格。"
                 "加噪只进训练计数、出值用真实档位（A-05）。走前 Δ 待真实回测回填。"),
    }
    return {
        "code": code, "name": name, "dims": DIMS, "bins_per_dim": 5,
        # v4 A-07：生产口径=ddsm（加噪+收缩，默认展示），研究口径=naive（真实档位，默认折叠）
        "production_layer": "ddsm",
        "research_layer": "naive",
        "default_layer": "ddsm",
        "dual_view_note": ("ddsm=生产口径（加噪 K=4 + 向训练段涨率收缩，对外结论用）；"
                           "naive=研究口径（未加噪真实档位，仅供审计对照，勿据此判结论）。"
                           "默认展示 ddsm 层，naive 层默认折叠。"),
        "vlabels": VLABELS, "layers": layers, "comparison": comparison,
        "legend": CUBE_LEGEND,
        "train_as_of": train_as_of, "snapshot_at": snapshot_at,
    }


# ---------------- 训练状态（§5.26） ----------------

DEAD_ENDS = [
    "接入第 4/5 维特征",
    "DDSM 用于 T+3",
    "逐资产路由",
    "loss-guided 加噪",
    "IC 自适应加噪",
]


def training_status(bars):
    return training_status_of(train_model(bars, H=1) if bars else None)


def training_status_of(model):
    if model is None:
        return {
            "total_cells": 125, "filled_cells": 0, "coverage_pct": 0.0,
            "avg_samples_per_cell": None, "min_samples_cell": 0,
            "min_n": MIN_N, "noise": {"k_noise": K_NOISE, "p_perturb": P_PERTURB},
            "train_mode": "逐资产、训练段统计；本期无逐资产调参",
            "noise_text": "加噪 K=4 / p=0.25：边缘格 n=3 经 5× 有效样本可达 n≈15，越过 MIN_N",
            "retrain_cycle": "quarterly", "last_retrain_at": None, "next_retrain_at": None,
            "retrain_note": "原年→季属参数变更，须重走六关（待验证）",
            "training_assets": 0, "index_only_assets": 0, "dead_ends": DEAD_ENDS,
        }
    filled = len([c for c, r in model["naive"].items() if r[0] > 0])
    ns = [r[0] for r in model["naive"].values() if r[0] > 0]
    filled_ddsm = len([c for c, r in model["ddsm"].items() if r[0] > 0])
    all_n = [r[0] for r in model["ddsm"].values() if r[0] > 0]
    return {
        "total_cells": 125, "filled_cells": filled,
        "coverage_pct": round(filled / 125.0, 4),
        "avg_samples_per_cell": round(_mean(ns), 4) if ns else None,
        "min_samples_cell": min(ns) if ns else 0,
        "min_n": MIN_N, "noise": {"k_noise": K_NOISE, "p_perturb": P_PERTURB},
        "train_mode": "逐资产、全样本训练段；季度滚动；无逐资产调参",
        "noise_text": ("加噪 K=4 / p=0.25：每维以 0.25 概率 ±1 档，副本仅进训练计数；"
                       "边缘格 n=3 → 有效样本 ×5 ≈ n=15，越过 MIN_N；ddsm 有效格 %d" % filled_ddsm),
        "retrain_cycle": "quarterly", "last_retrain_at": None, "next_retrain_at": None,
        "retrain_note": "原年→季属参数变更，须重走六关（待验证）",
        "training_assets": 0, "index_only_assets": 0, "dead_ends": DEAD_ENDS,
        "_ddsm_avg": round(_mean(all_n), 4) if all_n else None,
    }


def frozen_params():
    return {
        "k_noise": K_NOISE, "p_perturb": P_PERTURB, "min_n": MIN_N, "shrink": SHRINK,
        "band": BAND, "veto_crowd_quantile": VETO_CROWD_QUANTILE,
        "veto_klow2_quantile": VETO_KLOW2_QUANTILE,
        "min_coverage_ratio": 0.30, "min_open_count": 3,
        "weighting_basis": "market_value",  # v4 A-08：组合权重口径冻结，拒置信度加权
        # R2-14（contract §3.9）：基线口径固定文本；旧常量 0.5830 已退役（ADR-0013）
        "baseline_method": "max(恒涨率,恒跌率)，按台账 universe（全部资产-日）实测；0.5830 已退役",
        "gate_e1": "low[t] > high[t-1]",
        "gate_e3": "ret < -0.02 且 vr < 0.8",
        "purge_gap": "H+2",
        "window_weights": [
            {"window": "d15", "weight": 8}, {"window": "d30", "weight": 22},
            {"window": "d60", "weight": 15}, {"window": "m6", "weight": 10},
            {"window": "m24", "weight": 30}, {"window": "full", "weight": 15},
        ],
        "window_min_days": [
            {"window": "d15", "n_w": 5}, {"window": "d30", "n_w": 10},
            {"window": "d60", "n_w": 15}, {"window": "m6", "n_w": 30},
            {"window": "m24", "n_w": 60}, {"window": "full", "n_w": 120},
        ],
        "license_lines": [
            {"license": "candidate", "min_independent_days": 50, "window_k": None},
            {"license": "probation", "min_independent_days": 60, "window_k": 0.5},
            {"license": "renew_t2", "min_independent_days": 70, "window_k": 0.7},
            {"license": "full_t3", "min_independent_days": 80, "window_k": 0.7},
        ],
        "change_policy": "任何一项改动必须重走六关",
    }
