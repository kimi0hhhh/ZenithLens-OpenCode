# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 估值（09 §5.2/§5.3 · A-01/A-02）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import valuation


class UnknownContractTest(unittest.TestCase):
    def test_unknown_change_rate_null(self):
        rec = valuation.unknown_skeleton("000001", "测试基金")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "unknown")
        self.assertIsNone(pub["change_rate"])
        self.assertEqual(pub["confidence"], "unknown")
        self.assertEqual(pub["confidence_color_class"], "cu")
        self.assertIsNone(pub["trace_text"])

    def test_v3_accuracy_fields_present(self):
        pub = valuation.public_valuation(valuation.unknown_skeleton("000001", "x"))
        for k in ("dir_hit_rate", "n_test", "accuracy_window_days",
                  "industry_baseline_mae_rate", "confidence_label",
                  "confidence_color_class", "trace_text"):
            self.assertIn(k, pub)
        self.assertEqual(pub["accuracy_window_days"], 40)
        self.assertEqual(pub["industry_baseline_mae_rate"], 0.008)


class ConfidenceMappingTest(unittest.TestCase):
    def test_thresholds(self):
        orig = valuation.accuracy_for
        try:
            valuation.accuracy_for = lambda mode, code: {"mae_rate": 0.005}
            self.assertEqual(valuation._confidence_of("proxy", "1")[0], "high")
            valuation.accuracy_for = lambda mode, code: {"mae_rate": 0.011}
            self.assertEqual(valuation._confidence_of("proxy", "1")[0], "mid")
            valuation.accuracy_for = lambda mode, code: {"mae_rate": 0.02}
            self.assertEqual(valuation._confidence_of("proxy", "1")[0], "low")
        finally:
            valuation.accuracy_for = orig


class TraceTest(unittest.TestCase):
    def test_trace_not_fabricated_when_missing(self):
        self.assertIsNone(valuation._trace_text([]))


class NavIndependenceTest(unittest.TestCase):
    def test_nav_fields(self):
        h = {"code": "000001", "name": "x",
             "nav_history": {"2026-09-10": 1.0, "2026-09-11": 1.01}}
        nav = valuation.nav_of(h, "2026-09-12")
        for k in ("official_nav", "official_nav_date", "official_change_rate",
                  "previous_nav", "is_today_official"):
            self.assertIn(k, nav)
        self.assertFalse(nav["is_today_official"])
        self.assertAlmostEqual(nav["official_change_rate"], 0.01, places=4)


class TradeSessionTest(unittest.TestCase):
    def test_sessions(self):
        import datetime
        self.assertEqual(valuation.trade_session(datetime.datetime(2026, 9, 12, 10, 0)),
                         "non_trading_day")
        self.assertEqual(valuation.trade_session(datetime.datetime(2026, 9, 11, 9, 0)),
                         "pre_open")
        self.assertEqual(valuation.trade_session(datetime.datetime(2026, 9, 11, 10, 0)),
                         "trading")
        self.assertEqual(valuation.trade_session(datetime.datetime(2026, 9, 11, 16, 0)),
                         "closed")


class OfficialOnNonTradingDayTest(unittest.TestCase):
    """本轮修复：周末/收盘后用最近一期官方净值（official + nav_date=jzrq），不产出 intraday。"""

    def setUp(self):
        self._orig = valuation.estimator.get_official_nav
        valuation.estimator.get_official_nav = lambda code, allow_network=True: {
            "code": "000217", "name": "黄金ETF联接C",
            "nav": 3.1588, "nav_date": "2026-09-11",
            "change_rate": -0.0143, "prev_nav": 3.2045,
            "gsz": 3.1593, "estimate_change_rate": -0.0141,
            "gztime": "2026-09-11 15:30", "source": "lsjz",
        }

    def tearDown(self):
        valuation.estimator.get_official_nav = self._orig

    def _holding(self):
        return {"code": "000217", "name": "黄金ETF联接C",
                "nav_history": {"2026-08-25": 3.0}}

    def test_non_trading_day_official(self):
        rec = valuation.value_fund(self._holding(), "2026-09-12",
                                   allow_network=True, session="non_trading_day")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "official")
        self.assertEqual(pub["nav_date"], "2026-09-11")
        self.assertNotEqual(pub["nav_date"], "2026-08-25")
        self.assertAlmostEqual(pub["change_rate"], -0.0143, places=4)
        self.assertAlmostEqual(pub["estimated_nav"], 3.1588, places=4)
        self.assertEqual([t for t in pub["trace"] if t["mode"] == "intraday" and t["hit"]], [])

    def test_weekend_and_after_close_use_official(self):
        for sess in ("non_trading_day", "closed", "pre_open"):
            rec = valuation.value_fund(self._holding(), "2026-09-12",
                                       allow_network=True, session=sess)
            pub = valuation.public_valuation(rec)
            self.assertEqual(pub["valuation_mode"], "official", sess)
            self.assertEqual(pub["nav_date"], "2026-09-11", sess)

    def test_trading_session_allows_intraday(self):
        rec = valuation.value_fund(self._holding(), "2026-09-14",
                                   allow_network=True, session="trading")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "intraday")
        self.assertAlmostEqual(pub["change_rate"], -0.0141, places=4)
        self.assertTrue(any(t["mode"] == "intraday" and t["hit"] for t in pub["trace"]))

    def test_no_intraday_reuse_when_not_trading(self):
        self.assertFalse(valuation._mode_reusable("intraday", "non_trading_day"))
        self.assertFalse(valuation._mode_reusable("intraday", "closed"))
        self.assertTrue(valuation._mode_reusable("intraday", "trading"))
        self.assertTrue(valuation._mode_reusable("official", "non_trading_day"))


class NavFreshnessTest(unittest.TestCase):
    """本轮修复：nav_of 优先最近一期官方净值缓存，不被源文件 08-25 滞后值污染。"""

    def test_nav_of_prefers_fresh_official(self):
        orig = valuation.estimator.get_official_nav
        valuation.estimator.get_official_nav = lambda code, allow_network=True: {
            "nav": 3.1588, "nav_date": "2026-09-11", "change_rate": -0.0143,
            "prev_nav": 3.2045, "gsz": None, "estimate_change_rate": None,
            "gztime": None, "source": "lsjz"}
        try:
            h = {"code": "000217", "name": "x", "nav_history": {"2026-08-25": 3.0}}
            nav = valuation.nav_of(h, "2026-09-12")
            self.assertEqual(nav["official_nav_date"], "2026-09-11")
            self.assertAlmostEqual(nav["official_nav"], 3.1588, places=4)
            self.assertFalse(nav["is_today_official"])
        finally:
            valuation.estimator.get_official_nav = orig


class PrecisionGroupLabelV5Test(unittest.TestCase):
    """缺口4：/valuations/precision.groups[] 每项含中文 label（高/中/低/无）。"""

    def test_groups_each_have_label(self):
        out = valuation.precision_summary(
            [{"code": "999999", "name": "无样本基金", "shares": 0.0, "cost_amount": 0.0}])
        self.assertTrue(out["groups"])
        for g in out["groups"]:
            self.assertIn("label", g)
            self.assertIn(g["label"], ("高", "中", "低", "无"))
            self.assertEqual(set(g.keys()),
                             {"confidence", "label", "count", "market_value", "weight_ratio"})

    def test_label_mapping(self):
        self.assertEqual(valuation.CONF_GROUP_LABEL["high"], "高")
        self.assertEqual(valuation.CONF_GROUP_LABEL["mid"], "中")
        self.assertEqual(valuation.CONF_GROUP_LABEL["low"], "低")
        self.assertEqual(valuation.CONF_GROUP_LABEL["unknown"], "无")


if __name__ == "__main__":
    unittest.main()
