# -*- coding: utf-8 -*-
"""风险指标（慢接口，展开才计算）。

契约 §5.20 RiskMetrics：Sharpe / VaR95 / 下行风险 / 最大回撤。
口径：用 A/B 档可信持仓的代理 ETF 日线，按市值加权合成组合日收益；
样本不足返回 null（禁止用 0 冒充）。
"""

import math
from datetime import datetime

import estimator
import valuation as valuation_mod

SAMPLE_DAYS = 250


def _mean(xs):
    return sum(xs) / float(len(xs)) if xs else 0.0


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(len(xs) - 1))


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _f4(v):
    return None if v is None else round(float(v), 4)


def portfolio_returns(hold_list, days=SAMPLE_DAYS):
    """按市值加权合成组合日收益；返回 (dates, returns, weights_used)。"""
    series = {}
    weights = {}
    for h in hold_list:
        if h.get("tier") not in ("A", "B"):
            continue
        proxy = h.get("proxy_code")
        if not proxy:
            continue
        bars, _meta = estimator.get_bars(proxy, allow_network=False)
        if len(bars) < 3:
            continue
        rets = {}
        for i in range(1, len(bars)):
            prev = bars[i - 1]["close"]
            if prev > 0:
                rets[bars[i]["date"]] = bars[i]["close"] / prev - 1.0
        series[proxy] = rets
        mv, _src, _fb = valuation_mod.market_value_of(h)
        weights[proxy] = weights.get(proxy, 0.0) + (mv or 0.0)
    if not series:
        return [], []
    # 以数据最多的代理为日期骨架
    spine = max(series.values(), key=lambda d: len(d))
    dates = sorted(spine.keys())[-days:]
    out = []
    for d in dates:
        num = 0.0
        den = 0.0
        for proxy, rets in series.items():
            if d in rets:
                w = weights.get(proxy, 0.0)
                num += w * rets[d]
                den += w
        if den > 0:
            out.append((d, num / den))
    return [x[0] for x in out], [x[1] for x in out]


def risk_metrics(hold_list, days=SAMPLE_DAYS):
    dates, rets = portfolio_returns(hold_list, days=days)
    if len(rets) < 20:
        return {
            "sharpe": None, "var95_rate": None, "downside_vol_rate": None,
            "max_drawdown_rate": None, "sample_days": SAMPLE_DAYS,
            "stale": _stale(dates),
            "computed_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "note": "代理日线样本不足，风险指标不可计算（—）。",
        }
    mean = _mean(rets)
    std = _std(rets)
    sharpe = (mean / std * math.sqrt(252)) if std > 0 else None
    sorted_rets = sorted(rets)
    var95 = -_percentile(sorted_rets, 0.05)
    downside = [r for r in rets if r < 0]
    dvol = (_std(downside) * math.sqrt(252)) if len(downside) >= 2 else None
    # 最大回撤
    cum = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        cum *= (1 + r)
        if cum > peak:
            peak = cum
        dd = (peak - cum) / peak if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return {
        "sharpe": _f4(sharpe),
        "var95_rate": _f4(max(0.0, var95)),
        "downside_vol_rate": _f4(dvol),
        "max_drawdown_rate": _f4(max(0.0, mdd)),
        "sample_days": SAMPLE_DAYS,
        "stale": _stale(dates),
        "computed_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "note": ("历史模拟法；VaR95 与回撤以正数表示损失幅度；年化按 √252；"
                 "无风险利率取 0。慢接口，展开才计算。"),
    }


def _stale(dates):
    if not dates:
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    return dates[-1] != today
