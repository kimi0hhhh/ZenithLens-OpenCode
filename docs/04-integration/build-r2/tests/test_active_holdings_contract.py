# -*- coding: utf-8 -*-
"""主动基金重仓加权估值测试（task OC-HOLDVAL-BE）。

覆盖点：
- 基金类型分类 active / index_link / qdii / other；
- F10 前十持仓 HTML 解析（含 5 位港股代码）；
- 重仓加权公式 Σ(w_i×chg_i)/Σw_i（剔除缺报价标的，不编造）；
- 主动基金 → valuation_mode=holdings（官方未出当日时），trace 含前十加权明细；
- 前十不可得 → 回退 proxy；
- 指数联接/QDII 不做重仓加权，仍走 official/intraday/proxy；
- HoldingRow 暴露 fund_type/fund_type_label。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estimator  # noqa: E402
import fund_predict  # noqa: E402
import valuation  # noqa: E402

F10_SNIPPET = (
    'var apidata={ content:"'
    "<table class='w782 comm tzxq'><tbody>"
    "<tr><td>1</td><td><a href='//x'>603986</a></td><td class='tol'><a>兆易创新</a></td>"
    "<td class='tor'>6.84%</td><td class='tor'>42.26</td></tr>"
    "<tr><td>2</td><td><a href='//x'>01347</a></td><td class='tol'><a>华虹半导体</a></td>"
    "<td class='tor'>4.79%</td><td class='tor'>129.00</td></tr>"
    "</tbody></table>"
    '",arryear:[2026,2025],curyear:2026};'
)


class ClassifyFundTypeTest(unittest.TestCase):
    def test_active(self):
        for n in ("东方阿尔法科技智选混合发起C", "华夏军工安全混合C", "中航机遇领航混合发起C"):
            self.assertEqual(estimator.classify_fund_type(n), "active", n)

    def test_qdii_beats_active(self):
        self.assertEqual(estimator.classify_fund_type("华夏全球科技先锋混合(QDII)C"), "qdii")
        self.assertEqual(estimator.classify_fund_type("诺安油气能源(QDII-FOF-LOF)"), "qdii")

    def test_index_link(self):
        self.assertEqual(
            estimator.classify_fund_type("华夏中证电网设备主题ETF发起式联接C"), "index_link")
        self.assertEqual(estimator.classify_fund_type("华安黄金ETF联接C"), "index_link")
        self.assertEqual(estimator.classify_fund_type("华夏中证1000指数增强C"), "index_link")

    def test_other(self):
        self.assertEqual(estimator.classify_fund_type(""), "other")
        self.assertEqual(estimator.FUND_TYPE_LABEL["active"], "主动")


class ParseTopHoldingsTest(unittest.TestCase):
    def test_parse_including_hk_code(self):
        rows = estimator.parse_top_holdings(F10_SNIPPET)
        self.assertEqual([r["stock_code"] for r in rows], ["603986", "01347"])
        self.assertAlmostEqual(rows[0]["weight_pct"], 6.84, places=2)
        self.assertAlmostEqual(rows[1]["weight_pct"], 4.79, places=2)

    def test_parse_empty(self):
        self.assertEqual(estimator.parse_top_holdings(""), [])


class WeightedHoldingsTest(unittest.TestCase):
    def test_formula_and_exclusion(self):
        holdings = [
            {"rank": 1, "stock_code": "600000", "stock_name": "A", "weight": 6.0, "day_change": 0.02},
            {"rank": 2, "stock_code": "000001", "stock_name": "B", "weight": 4.0, "day_change": -0.01},
            {"rank": 3, "stock_code": "01347", "stock_name": "HK", "weight": 5.0, "day_change": None},
        ]
        ch, detail = valuation._weighted_holdings(holdings)
        # (6*0.02 + 4*(-0.01)) / (6+4) = 0.08/10 = 0.008
        self.assertAlmostEqual(ch, 0.008, places=6)
        self.assertAlmostEqual(detail["weighted_change"], 0.008, places=4)
        self.assertAlmostEqual(detail["covered_weight_pct"], 10.0, places=2)
        self.assertAlmostEqual(detail["total_weight_pct"], 15.0, places=2)
        used = [r["used"] for r in detail["top10"]]
        self.assertEqual(used, [True, True, False])

    def test_no_quotes_returns_none(self):
        ch, detail = valuation._weighted_holdings(
            [{"rank": 1, "stock_code": "01347", "weight": 5.0, "day_change": None}])
        self.assertIsNone(ch)
        self.assertIsNone(detail["weighted_change"])


class _Patch(object):
    def __init__(self, **kw):
        self.kw = kw
        self.orig = {}

    def __enter__(self):
        for name, val in self.kw.items():
            self.orig[name] = getattr(valuation.estimator, name)
            setattr(valuation.estimator, name, val)

    def __exit__(self, *a):
        for name, val in self.orig.items():
            setattr(valuation.estimator, name, val)


def _off(nav, date, gsz=None, gszzl=None):
    return {"code": "x", "name": "x", "nav": nav, "nav_date": date,
            "change_rate": None, "prev_nav": nav / 1.01 if nav else None,
            "gsz": gsz, "estimate_change_rate": gszzl, "gztime": None, "source": "lsjz"}


def _rep(weighted_rows):
    return {"code": "x", "report_date": "2026-06-30", "source": "f10",
            "holdings": weighted_rows}


class ActiveHoldingsValuationTest(unittest.TestCase):
    def _active(self):
        return {"code": "014320", "name": "东方阿尔法产业混合C", "fund_type": "active",
                "proxy_code": "512480", "nav_history": {"2026-08-25": 2.0}}

    def test_active_uses_holdings_not_proxy(self):
        holdings = [
            {"rank": 1, "stock_code": "603986", "stock_name": "兆易创新",
             "weight": 6.0, "day_change": 0.02},
            {"rank": 2, "stock_code": "000001", "stock_name": "平安银行",
             "weight": 4.0, "day_change": -0.01},
        ]
        def fake_proxy(_code):
            raise AssertionError("主动基金不得调用 proxy 实时")
        with _Patch(get_official_nav=lambda code, allow_network=True: _off(2.0, "2026-09-11"),
                    eastmoney_top_holdings=lambda code, allow_network=True, force=False: _rep(holdings),
                    tencent_rt_quote=fake_proxy):
            rec = valuation.value_fund(self._active(), "2026-09-12",
                                       allow_network=True, session="non_trading_day")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "holdings")
        self.assertEqual(pub["mode_label"], "重仓加权")
        self.assertAlmostEqual(pub["change_rate"], 0.008, places=4)
        # estimated_nav = 最新官方净值 2.0 × (1 + 0.008)
        self.assertAlmostEqual(pub["estimated_nav"], 2.0 * 1.008, places=4)
        hit = [t for t in pub["trace"] if t["mode"] == "holdings" and t["hit"]]
        self.assertEqual(len(hit), 1)
        detail = hit[0]["detail"]
        self.assertEqual(detail["method"], "eastmoney_f10_top10_weighted")
        self.assertEqual(len(detail["top10"]), 2)
        self.assertEqual([t["mode"] for t in pub["trace"]], ["official", "intraday", "holdings"])
        self.assertEqual(pub["fund_type"], "active")

    def test_active_falls_back_to_proxy(self):
        with _Patch(get_official_nav=lambda code, allow_network=True: _off(2.0, "2026-09-11"),
                    eastmoney_top_holdings=lambda code, allow_network=True, force=False: None,
                    tencent_rt_quote=lambda code: {"change_rate": 0.03, "price": 1.1, "prev_close": 1.0}):
            rec = valuation.value_fund(self._active(), "2026-09-12",
                                       allow_network=True, session="non_trading_day")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "proxy")
        self.assertAlmostEqual(pub["change_rate"], 0.03, places=4)
        hols = [t for t in pub["trace"] if t["mode"] == "holdings"]
        self.assertTrue(hols and hols[0]["tried"] and not hols[0]["hit"])

    def test_active_today_official_wins(self):
        with _Patch(get_official_nav=lambda code, allow_network=True: _off(2.0, "2026-09-12"),
                    eastmoney_top_holdings=lambda code, allow_network=True, force=False: _rep([])):
            rec = valuation.value_fund(self._active(), "2026-09-12", allow_network=True)
        self.assertEqual(valuation.public_valuation(rec)["valuation_mode"], "official")

    def test_index_link_skips_holdings_and_uses_proxy(self):
        h = {"code": "025857", "name": "华夏中证电网设备主题ETF发起式联接C",
             "fund_type": "index_link", "proxy_code": "561560",
             "nav_history": {"2026-08-25": 2.0}}
        def no_holdings(_code, allow_network=True, force=False):
            raise AssertionError("指数联接不得调用重仓加权")
        with _Patch(get_official_nav=lambda code, allow_network=True: _off(2.0, "2026-09-11", gsz=None, gszzl=None),
                    eastmoney_top_holdings=no_holdings,
                    tencent_rt_quote=lambda code: {"change_rate": -0.005, "price": 1.0, "prev_close": 1.0}):
            rec = valuation.value_fund(h, "2026-09-14", allow_network=True, session="trading")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "proxy")
        hols = [t for t in pub["trace"] if t["mode"] == "holdings"]
        self.assertTrue(hols and not hols[0]["tried"])


class HoldingRowFundTypeTest(unittest.TestCase):
    def test_build_holding_row_exposes_fund_type(self):
        h = {"code": "014320", "name": "东方阿尔法产业混合C", "group": "active",
             "tier": "A", "shares": 1.0, "cost_amount": 1.0, "proxy_code": "512480"}
        row = fund_predict.build_holding_row(h, "2026-09-12", None, 1.0)
        self.assertEqual(row["fund_type"], "active")
        self.assertEqual(row["fund_type_label"], "主动")


if __name__ == "__main__":
    unittest.main()
