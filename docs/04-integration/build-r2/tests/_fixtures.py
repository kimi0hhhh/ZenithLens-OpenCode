# -*- coding: utf-8 -*-
"""测试夹具：确定性合成 K 线（不联网、不使用第三方库）。"""


def make_bars(n=180, seed=7):
    """确定性伪随机游走 OHLCV（LCG，无 random 模块依赖），日期仅作标识。"""
    bars = []
    price = 1.0
    x = seed
    for i in range(n):
        x = (1103515245 * x + 12345) % 2147483648
        r = ((x / 2147483648.0) - 0.5) * 0.03
        o = price
        price = max(0.01, price * (1.0 + r))
        c = price
        hi = max(o, c) * (1.0 + 0.004)
        lo = min(o, c) * (1.0 - 0.004)
        vol = float(1000 + (x % 500))
        bars.append({
            "date": "2026-%02d-%02d" % (1 + (i // 28) % 12, 1 + (i % 28)),
            "open": o, "high": hi, "low": lo, "close": c, "volume": vol,
        })
    return bars
