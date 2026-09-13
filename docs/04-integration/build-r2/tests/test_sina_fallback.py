# -*- coding: utf-8 -*-
"""R2 契约测试 · 新浪源限定兜底（08-r2 §6.3；R2-17；ISSUE-ZL-R2-03(a)）。

断言要点：
- 档4 实时：腾讯失败 → 新浪兜底调用（5s 超时、重试 0 由 estimator 保证）；
- 双失败 → 落既有降级（unknown，不编造）；
- 新浪批量仅 6 位 A 股；重仓个股批量腾讯失败 → 新浪兜底。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estimator
import settings
import valuation

SINA_TEXT = ("var hq_str_sh600000=\"浦发银行,9.30,9.35,9.26,9.40,9.20,9.26,9.27,"
             "100000,930000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,"
             "2026-09-11,15:00:00,00\";")


class SinaFallbackValuationTest(unittest.TestCase):
    def _off(self):
        return {"code": "x", "name": "x", "nav": 2.0, "nav_date": "2026-09-11",
                "change_rate": None, "prev_nav": 2.0, "gsz": None,
                "estimate_change_rate": None, "gztime": None, "source": "lsjz"}

    def _fund(self):
        return {"code": "025857", "name": "华夏中证电网设备主题ETF发起式联接C",
                "fund_type": "index_link", "proxy_code": "561560",
                "nav_history": {"2026-09-10": 2.0}}

    def test_tencent_fail_sina_fallback(self):
        calls = {"sina": 0}

        def sina(_code):
            calls["sina"] += 1
            return {"change_rate": 0.012, "price": 1.012, "prev_close": 1.0,
                    "name": "x", "symbol": "sh561560", "time": ""}

        with mock.patch.object(valuation.estimator, "get_official_nav",
                               return_value=self._off()), \
                mock.patch.object(valuation.estimator, "tencent_rt_quote",
                                  return_value=None), \
                mock.patch.object(valuation.estimator, "sina_rt_quote",
                                  side_effect=sina), \
                mock.patch.object(valuation.estimator, "get_bars",
                                  return_value=([], {})):
            rec = valuation.value_fund(self._fund(), "2026-09-12",
                                       allow_network=True, session="trading")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "proxy")
        self.assertAlmostEqual(pub["change_rate"], 0.012, places=4)
        self.assertEqual(calls["sina"], 1)

    def test_double_fail_degrades_honestly(self):
        with mock.patch.object(valuation.estimator, "get_official_nav",
                               return_value=self._off()), \
                mock.patch.object(valuation.estimator, "tencent_rt_quote",
                                  return_value=None), \
                mock.patch.object(valuation.estimator, "sina_rt_quote",
                                  return_value=None), \
                mock.patch.object(valuation.estimator, "get_bars",
                                  return_value=([], {})):
            rec = valuation.value_fund(self._fund(), "2026-09-12",
                                       allow_network=True, session="trading")
        pub = valuation.public_valuation(rec)
        self.assertEqual(pub["valuation_mode"], "unknown")
        self.assertIsNone(pub["change_rate"])


class SinaBatchTest(unittest.TestCase):
    def setUp(self):
        self._saved = estimator.http_get
        # BLOCK-2：隔离源事件日志/健康文件（record_source 真实写入会污染产线数据）
        self._saved_record = settings.record_source
        settings.record_source = lambda *args, **kwargs: None
        self.calls = []

    def tearDown(self):
        estimator.http_get = self._saved
        settings.record_source = self._saved_record

    def test_batch_only_a_shares(self):
        def fake_get(url, **kw):
            self.calls.append(kw)
            return SINA_TEXT.encode("gbk", "replace")

        estimator.http_get = fake_get
        out = estimator.sina_rt_quotes(["600000", "01347", "AAPL"])
        self.assertEqual(list(out.keys()), ["600000"])
        self.assertAlmostEqual(out["600000"]["change_rate"],
                               9.26 / 9.35 - 1.0, places=4)
        self.assertEqual(self.calls[0].get("retries"), 0)   # 重试 0（R2-17）

    def test_batch_unreachable(self):
        estimator.http_get = lambda url, **kw: None
        self.assertEqual(estimator.sina_rt_quotes(["600000"]), {})


class TopHoldingsSinaFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_sina_")
        self._saved = (estimator.HOLD_DIR, estimator.tencent_rt_quotes,
                       estimator.sina_rt_quotes)
        estimator.HOLD_DIR = self.tmp

    def tearDown(self):
        (estimator.HOLD_DIR, estimator.tencent_rt_quotes,
         estimator.sina_rt_quotes) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_top_holdings_sina_fallback(self):
        cache = {"code": "025500", "report_date": "2026-06-30", "source": "f10",
                 "fetched_at": estimator._now_ts(), "top_n": 20,
                 "holdings": [{"rank": 1, "stock_code": "603986",
                               "stock_name": "兆易创新", "weight_pct": 8.0}]}
        with io.open(os.path.join(self.tmp, "025500.json"), "w", encoding="utf-8") as f:
            json.dump(cache, f)
        estimator.tencent_rt_quotes = lambda codes: {}
        estimator.sina_rt_quotes = lambda codes: {
            "603986": {"change_rate": 0.02, "price": 10.2, "prev_close": 10.0}}
        rep = estimator.eastmoney_top_holdings("025500", allow_network=True)
        self.assertEqual(rep["top_n"], 20)
        self.assertAlmostEqual(rep["holdings"][0]["day_change"], 0.02, places=4)


if __name__ == "__main__":
    unittest.main()
