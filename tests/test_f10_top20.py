# -*- coding: utf-8 -*-
"""R2 契约测试 · F10 top20 + 港股 + excluded_count（08-r2 §3.2；R2-02；N-2）。

断言要点：
- `topline=20` 抓取档位；5 位港股代码解析；缓存记录 `top_n`；
- 重抓失败按旧缓存 + 如实标注 `top_n`（禁止静默降档）；
- `_weighted_holdings` detail：top_n / included_markets / excluded_count 如实。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estimator
import valuation


def _f10_html(n=12):
    rows = []
    for i in range(n):
        code = "60000%d" % i if i < 10 else "0134%d" % (i - 10) if i >= 10 else ""
        rows.append("<tr><td>%d</td><td><a href='//x'>%s</a></td>"
                    "<td class='tol'><a>股票%d</a></td><td class='tor'>%d.50%%</td>"
                    "<td class='tor'>10.0</td></tr>" % (i + 1, code, i, i + 1))
    return ('var apidata={ content:"<table><tbody>' + "".join(rows) +
            '</tbody></table>",arryear:[2026],curyear:2026};')


class F10Top20Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_f10_")
        self._saved = (estimator.HOLD_DIR, estimator.tencent_rt_quotes,
                       estimator.sina_rt_quotes, estimator.fetch_top_holdings)
        estimator.HOLD_DIR = self.tmp

    def tearDown(self):
        (estimator.HOLD_DIR, estimator.tencent_rt_quotes, estimator.sina_rt_quotes,
         estimator.fetch_top_holdings) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_top20_and_hk(self):
        rows20 = estimator.parse_top_holdings(_f10_html(12), topn=20)
        self.assertEqual(len(rows20), 12)
        self.assertEqual(rows20[-1]["stock_code"], "01341")   # 5 位港股
        rows10 = estimator.parse_top_holdings(_f10_html(12), topn=10)
        self.assertEqual(len(rows10), 10)

    def test_topline_request_and_cache_top_n(self):
        calls = {}

        def fake_fetch(code, allow_network=True, topn=10):
            calls["topn"] = topn
            rows = estimator.parse_top_holdings(_f10_html(12), topn=topn)
            return rows, "2026-06-30", "http://x"

        estimator.fetch_top_holdings = fake_fetch
        estimator.tencent_rt_quotes = lambda codes: {
            c: {"change_rate": 0.01, "price": 1.0, "prev_close": 1.0} for c in codes}
        rep = estimator.eastmoney_top_holdings("025500", allow_network=True, topline=20)
        self.assertEqual(calls["topn"], 20)
        self.assertEqual(rep["top_n"], 20)
        self.assertEqual(len(rep["holdings"]), 12)
        with io.open(os.path.join(self.tmp, "025500.json"), encoding="utf-8") as f:
            cached = json.load(f)
        self.assertEqual(cached["top_n"], 20)

    def test_refetch_failure_keeps_old_cache_with_truthful_top_n(self):
        cache = {"code": "025500", "report_date": "2026-03-31", "source": "old",
                 "fetched_at": "2020-01-01T00:00:00+08:00", "top_n": 10,
                 "holdings": [{"rank": 1, "stock_code": "603986",
                               "stock_name": "兆易创新", "weight_pct": 8.0}]}
        with io.open(os.path.join(self.tmp, "025500.json"), "w", encoding="utf-8") as f:
            json.dump(cache, f)
        estimator.fetch_top_holdings = lambda code, allow_network=True, topn=10: (
            [], None, "http://x")
        estimator.tencent_rt_quotes = lambda codes: {}
        estimator.sina_rt_quotes = lambda codes: {}
        rep = estimator.eastmoney_top_holdings("025500", allow_network=True, topline=20)
        self.assertEqual(rep["top_n"], 10)   # 如实标注旧档位，不静默称 20
        self.assertEqual(len(rep["holdings"]), 1)


class WeightedDetailTest(unittest.TestCase):
    def test_detail_top_n_markets_excluded(self):
        holdings = [
            {"rank": 1, "stock_code": "603986", "stock_name": "A", "weight": 6.0,
             "day_change": 0.02},
            {"rank": 2, "stock_code": "01347", "stock_name": "HK缺报价", "weight": 4.0,
             "day_change": None},
            {"rank": 3, "stock_code": "AAPL", "stock_name": "US不支持", "weight": 3.0,
             "day_change": None},
        ]
        ch, detail = valuation._weighted_holdings(holdings, top_n=20)
        self.assertAlmostEqual(ch, 0.02, places=6)
        self.assertEqual(detail["top_n"], 20)
        self.assertEqual(detail["included_markets"], ["A"])
        self.assertEqual(detail["excluded_count"], 2)
        self.assertFalse(detail["top10"][1]["used"])
        self.assertFalse(detail["top10"][2]["used"])

    def test_f6_method_frozen_and_top_n_enum(self):
        # F-6 确认（09-r2 v9.4 §12）：method 名恒定（历史标识）；档位以 top_n 如实（10/20）
        holdings = [{"rank": 1, "stock_code": "603986", "stock_name": "A",
                     "weight": 6.0, "day_change": 0.02}]
        for top_n in (10, 20):
            _ch, detail = valuation._weighted_holdings(holdings, top_n=top_n)
            self.assertEqual(detail["method"], "eastmoney_f10_top10_weighted")
            self.assertIn(detail["top_n"], (10, 20))
            self.assertEqual(detail["top_n"], top_n)


if __name__ == "__main__":
    unittest.main()
