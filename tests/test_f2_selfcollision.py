# -*- coding: utf-8 -*-
"""R3/F2 自碰撞伪影修复测试（候选自身/别名不参与独立性比对）。

背景：crowd6 的 `_builtin` 与现役因子 `crowd` 同源；`_incumbent_series` 仅按
`factor_id == name` 排除，导致候选与自身别名比对 → max_collinearity=1.0 /
collinear_with="crowd" → 假 `rejected_f2`。修复：按候选身份集合
（factor_id / name / `_builtin` 键 / 同实现别名）排除自比对。

断言：
- 身份集合包含别名（crowd6↔crowd）；
- 现役清单/相关性检验排除候选自身（含别名）；全被排除 → pass + null；
- 真共线因子仍被拒绝（负向）；
- crowd6 全栈 evaluate 不再出现 vs "crowd" 的 1.0；klow2 重评不回归（仍比对 crowd）。
"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine
import factor_engine as fe


def _bars(n=200, seed=7, start="2026-01-05"):
    d = date.fromisoformat(start)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    out = []
    price = 1.0
    x = seed
    for _i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        x = (1103515245 * x + 12345) % 2147483648
        r = ((x / 2147483648.0) - 0.5) * 0.03
        o = price
        price = max(0.01, price * (1.0 + r))
        c = price
        out.append({"date": d.strftime("%Y-%m-%d"), "open": o,
                    "high": max(o, c) * 1.004, "low": min(o, c) * 0.996,
                    "close": c, "volume": float(1000 + (x % 500))})
        d += timedelta(days=1)
    return out


def _pattern(n, period, offset=0):
    return [((i + offset) % period == 0) for i in range(n)]


class CandidateIdentityTest(unittest.TestCase):
    def test_alias_ids(self):
        ids = fe._candidate_identity_ids(fe.crowd_definition())
        self.assertIn("crowd6", ids)
        self.assertIn("crowd", ids)          # _builtin 别名
        self.assertIn("crowd6", fe._candidate_identity_ids(fe.crowd_definition()))

    def test_klow2_ids(self):
        ids = fe._candidate_identity_ids(fe.klow2_definition())
        self.assertIn("klow2", ids)

    def test_incumbent_series_excludes_alias(self):
        assets = [("A", _bars(120, seed=5))]
        series = fe._incumbent_series(fe.crowd_definition(), assets, 1, None)
        self.assertNotIn("crowd", series)           # 自身别名被排除
        self.assertEqual(set(series.keys()), {"klow2"})
        series2 = fe._incumbent_series(fe.klow2_definition(), assets, 1, None)
        self.assertEqual(set(series2.keys()), {"crowd"})


class F2SelfCollisionTest(unittest.TestCase):
    def setUp(self):
        self.assets = [("A", _bars(120, seed=11)), ("B", _bars(120, seed=23))]
        self.same = {"A": _pattern(120, 7), "B": _pattern(120, 5)}
        self.other = {"A": _pattern(120, 4, offset=1), "B": _pattern(120, 3, offset=1)}

    def test_only_alias_excluded_then_na_pass(self):
        # 现役清单里只有候选自身别名 → 全部排除 → pass + null（不是 1.0 fail）
        f2 = fe._f2_independence(fe.crowd_definition(), self.same,
                                 {"crowd": self.same}, self.assets, None)
        self.assertEqual(f2["result"], "pass")
        self.assertIsNone(f2["max_collinearity"])
        self.assertIsNone(f2["collinear_with"])

    def test_alias_skipped_but_real_peer_compared(self):
        f2 = fe._f2_independence(fe.crowd_definition(), self.same,
                                 {"crowd": self.same, "klow2": self.other},
                                 self.assets, None)
        self.assertEqual(f2["collinear_with"], "klow2")
        self.assertLess(f2["max_collinearity"], 1.0)

    def test_genuine_collinearity_still_rejected(self):
        # 负向：真实共线（不同身份、信号相同）仍应 fail
        clone = {"factor_id": "my_clone", "name": "clone", "_builtin": None}
        f2 = fe._f2_independence(clone, self.same, {"klow2": self.same},
                                 self.assets, None)
        self.assertEqual(f2["result"], "fail")
        self.assertEqual(f2["max_collinearity"], 1.0)
        self.assertEqual(f2["collinear_with"], "klow2")

    def test_evaluate_crowd6_no_self_comparison(self):
        card = fe.evaluate(fe.crowd_definition(), self.assets,
                           engine.frozen_params(), do_bootstrap=False,
                           use_cache=False)
        f2 = card["f2_independence"]
        self.assertNotEqual(card.get("collinear_with"), "crowd")
        self.assertNotEqual(f2.get("collinear_with"), "crowd")
        self.assertNotEqual(card.get("max_collinearity"), 1.0)

    def test_evaluate_klow2_still_compares_crowd(self):
        card = fe.evaluate(fe.klow2_definition(), self.assets,
                           engine.frozen_params(), do_bootstrap=False,
                           use_cache=False)
        # klow2 自身被排除，仅余 crowd 可比 → collinear_with 必为 crowd
        self.assertEqual(card.get("collinear_with"), "crowd")
        self.assertLess(card.get("max_collinearity") or 0.0, 1.0)


if __name__ == "__main__":
    unittest.main()
