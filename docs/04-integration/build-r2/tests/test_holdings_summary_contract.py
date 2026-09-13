# -*- coding: utf-8 -*-
"""契约 v5 关键路径测试 · 持仓汇总覆盖口径（09 §6.2.1 / PRD F-01 验收②）。

覆盖点：`covered_count` 按“可信估值”计数（`change_rate != null`），
存在 unknown 行（`change_rate=null`）时必须 `covered_count < total_count`；
`coverage_note` 与 `today_pnl_amt` 聚合口径与之保持一致。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fund_predict


def _hold(code, cost_amount=100.0):
    return {"code": code, "name": code, "shares": 100.0, "cost_amount": cost_amount}


class HoldingsSummaryCoverageTest(unittest.TestCase):
    def setUp(self):
        self._orig_mv = fund_predict.valuation_mod.market_value_of
        self._orig_get = fund_predict.valuation_mod.get_cached
        self._recs = {}
        fund_predict.valuation_mod.get_cached = \
            lambda code, as_of=None: self._recs.get(code)
        fund_predict.valuation_mod.market_value_of = \
            lambda h, as_of=None: (100.0, "valuation", 0.0)

    def tearDown(self):
        fund_predict.valuation_mod.market_value_of = self._orig_mv
        fund_predict.valuation_mod.get_cached = self._orig_get

    def test_unknown_rows_lower_covered_count(self):
        self._recs = {
            "000001": {"change_rate": 0.01},
            "000002": {"change_rate": None},
        }
        s = fund_predict.holdings_summary(
            [_hold("000001"), _hold("000002")], "2026-09-12")
        self.assertEqual(s["covered_count"], 1)
        self.assertEqual(s["total_count"], 2)
        self.assertLess(s["covered_count"], s["total_count"])
        self.assertIn("1/2", s["coverage_note"])
        # today_pnl_amt 只聚合可信行：100 - 100/1.01 = 0.99
        self.assertAlmostEqual(s["today_pnl_amt"], 0.99, places=2)

    def test_missing_rec_counts_as_unknown(self):
        self._recs = {"000001": {"change_rate": None}}
        s = fund_predict.holdings_summary(
            [_hold("000001"), _hold("000002")], "2026-09-12")
        self.assertEqual(s["covered_count"], 0)
        self.assertEqual(s["total_count"], 2)
        self.assertIn("0/2", s["coverage_note"])

    def test_full_coverage_note_when_all_trusted(self):
        self._recs = {
            "000001": {"change_rate": 0.01},
            "000002": {"change_rate": -0.01},
        }
        s = fund_predict.holdings_summary(
            [_hold("000001"), _hold("000002")], "2026-09-12")
        self.assertEqual(s["covered_count"], 2)
        self.assertEqual(s["total_count"], 2)
        self.assertIn("全部覆盖", s["coverage_note"])


if __name__ == "__main__":
    unittest.main()
