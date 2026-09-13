# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 组合加权（09 §5.7 / §6.5 · A-08）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fund_predict


def _rows():
    return [
        {"code": "000001", "windows": {
            "T1": {"open": True, "p": 0.80},
            "T3": {"open": True, "p": None},
            "T15": {"open": True, "p": 0.70},
        }},
        {"code": "000002", "windows": {
            "T1": {"open": True, "p": 0.60},
            "T3": {"open": True, "p": None},
            "T15": {"open": True, "p": 0.55},
        }},
    ]


def _holds():
    return [
        {"code": "000001", "tier": "A", "shares": 100.0, "cost_amount": 100.0},
        {"code": "000002", "tier": "A", "shares": 100.0, "cost_amount": 100.0},
        {"code": "000003", "tier": "C", "shares": 100.0, "cost_amount": 100.0},
    ]


class PortfolioV4Test(unittest.TestCase):
    def setUp(self):
        self._orig = fund_predict.valuation_mod.market_value_of
        fund_predict.valuation_mod.market_value_of = \
            lambda h, as_of=None: (100.0, "valuation", 0.0)

    def tearDown(self):
        fund_predict.valuation_mod.market_value_of = self._orig

    def _forecast(self):
        return fund_predict.portfolio_forecast(_rows(), _holds(), "online", "2026-09-12")

    def test_weighting_basis_frozen(self):
        wins = {w["window"]: w for w in self._forecast()}
        self.assertEqual(wins["T1"]["weighting_basis"], "market_value")
        self.assertTrue(wins["T1"]["weighting_policy_note"])
        self.assertIn("置信度", wins["T1"]["weighting_policy_note"])

    def test_threshold_constants(self):
        w = {x["window"]: x for x in self._forecast()}["T1"]
        self.assertEqual(w["min_coverage_ratio"], 0.30)
        self.assertEqual(w["min_open_count"], 3)
        self.assertEqual(round(w["weighted_p_threshold"], 4), 0.52)

    def test_t3_has_no_probability(self):
        w = {x["window"]: x for x in self._forecast()}["T3"]
        self.assertIsNone(w["weighted_p"])
        self.assertEqual(w["direction"], "gray")
        self.assertEqual(w["direction_reason"], "window_unvalidated")

    def test_t15_unvalidated_forces_gray(self):
        w = {x["window"]: x for x in self._forecast()}["T15"]
        self.assertEqual(w["direction"], "gray")
        self.assertFalse(w["coverage_threshold_met"] or w["direction"] == "up")

    def test_tier_excluded_lists_present_cd(self):
        w = {x["window"]: x for x in self._forecast()}["T1"]
        self.assertEqual(w["tier_excluded"], ["C"])

    def test_excluded_ratio_complements_coverage(self):
        for w in self._forecast():
            self.assertAlmostEqual(w["excluded_ratio"], 1.0 - w["coverage_ratio"], places=4)


if __name__ == "__main__":
    unittest.main()
