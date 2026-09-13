# -*- coding: utf-8 -*-
"""R2 契约测试 · 代理质量重建证据道（08-r2 §3.1b；ADR-0015；D-2）。

断言要点：
- 证据道重建（bars × nav 史，40 日窗）；MAE/方向命中率/n_test 可复算；
- 与展示通道（accuracy.json）分键分文件，互不引用；
- 无代理 / 无 nav → 条目如实给 n_test=0（不编造）。
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

import valuation


def _series(start=1.0, n=6, step=0.01):
    out = []
    v = start
    for _i in range(n):
        v = v * (1 + step)
        out.append(v)
    return out


class ProxyQualityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_pq_")
        self._saved = (valuation.NAV_STORE_DIR, valuation.PROXY_QUALITY_PATH,
                       valuation.ACCURACY_PATH)
        valuation.NAV_STORE_DIR = os.path.join(self.tmp, "nav")
        valuation.PROXY_QUALITY_PATH = os.path.join(self.tmp, "proxy_quality.json")
        valuation.ACCURACY_PATH = os.path.join(self.tmp, "accuracy.json")
        os.makedirs(valuation.NAV_STORE_DIR)
        self.dates = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03",
                      "2026-09-04", "2026-09-05"]
        self.navs = _series(1.0, 6, 0.01)
        self.bar_closes = _series(1.0, 6, 0.01)
        # 第 4 个 bar 人为偏差 → 可复算 MAE
        self.bar_closes[3] = self.bar_closes[2] * (1 + 0.03)

    def tearDown(self):
        (valuation.NAV_STORE_DIR, valuation.PROXY_QUALITY_PATH,
         valuation.ACCURACY_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_nav(self, code):
        path = os.path.join(valuation.NAV_STORE_DIR, "%s.json" % code)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump({"code": code, "updated_at": "2026-09-12T00:00:00+08:00",
                       "points": [{"date": d, "nav": v}
                                  for d, v in zip(self.dates, self.navs)]}, f)

    def _bars(self, code):
        return [{"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 1.0}
                for d, c in zip(self.dates, self.bar_closes)]

    def test_rebuild_recomputable(self):
        self._write_nav("000001")
        with mock.patch.object(valuation.estimator, "get_bars",
                               return_value=(self._bars("512480"), {})):
            entries = valuation.build_proxy_quality(
                [{"code": "000001", "proxy_code": "512480"}])
        e = entries["000001"]
        self.assertEqual(e["n_test"], 5)
        self.assertEqual(e["matched_days"], self.dates[1:])
        self.assertEqual(e["window_days"], 40)
        self.assertEqual(e["proxy_code"], "512480")
        self.assertEqual(e["source"], "bars_x_nav")
        # 复算：逐样本 est=bar[i]/bar[i-1]-1 vs real=nav[i]/nav[i-1]-1
        errs, hits = [], 0
        for i in range(1, len(self.dates)):
            est = self.bar_closes[i] / self.bar_closes[i - 1] - 1.0
            real = self.navs[i] / self.navs[i - 1] - 1.0
            errs.append(abs(est - real))
            if real != 0 and (est > 0) == (real > 0):
                hits += 1
        self.assertAlmostEqual(e["mae_rate"], round(sum(errs) / len(errs), 4),
                               places=4)
        self.assertAlmostEqual(e["dir_hit_rate"], round(hits / float(len(errs)), 4),
                               places=4)
        # 落盘 + 分文件
        self.assertTrue(os.path.isfile(valuation.PROXY_QUALITY_PATH))
        self.assertFalse(os.path.isfile(valuation.ACCURACY_PATH))
        loaded = valuation.load_proxy_quality()
        self.assertIn("000001", loaded)

    def test_no_nav_entry_zero_samples(self):
        with mock.patch.object(valuation.estimator, "get_bars",
                               return_value=(self._bars("512480"), {})):
            entries = valuation.build_proxy_quality(
                [{"code": "000999", "proxy_code": "512480"}])
        self.assertEqual(entries["000999"]["n_test"], 0)
        self.assertIsNone(entries["000999"]["mae_rate"])

    def test_no_proxy_skipped(self):
        self._write_nav("000002")
        entries = valuation.build_proxy_quality([{"code": "000002"}])
        self.assertNotIn("000002", entries)


if __name__ == "__main__":
    unittest.main()
