# -*- coding: utf-8 -*-
"""R2 契约测试 · 维护版净值史（08-r2 §6.1；R2-16）。

断言要点：
- lsjz 分页（pageIndex 递增，止于空页）；增量停页（已存日期全覆盖即停）；
- 幂等：既有日期不覆盖（首值冻结）、重复执行 points 集不变；
- 接口失败 → 保留已有 + 失败清单（不编造净值）。
"""

import hashlib
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
import ledger_api
import settings
import valuation


def _page(rows):
    body = {"Data": {"LSJZList": [
        {"FSRQ": d, "DWJZ": str(v), "JZZZL": "1.00"} for d, v in rows]},
        "TotalCount": 100}
    return json.dumps(body).encode("utf-8")


class NavHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_nav_")
        # 先记录真实产线路径（守卫断言用），再全部改指临时目录（BLOCK-2 修复）
        self._real_paths = {name: getattr(valuation, name) for name in
                            ("PROXY_QUALITY_PATH", "HISTORY_PATH", "ACCURACY_PATH",
                             "SNAPSHOT_PATH", "DAILY_DIR", "NAV_STORE_DIR")}
        self._real_paths["LEDGER_DIR"] = ledger_api.LEDGER_DIR
        self._saved = (valuation.NAV_STORE_DIR, valuation.HISTORY_PATH,
                       valuation.ACCURACY_PATH, valuation.SNAPSHOT_PATH,
                       valuation.DAILY_DIR, valuation.PROXY_QUALITY_PATH,
                       ledger_api.SIGNALS_PATH, ledger_api.BACKFILL_PATH,
                       ledger_api.LEDGER_DIR, settings.record_source,
                       estimator.http_get)
        valuation.NAV_STORE_DIR = os.path.join(self.tmp, "nav")
        valuation.HISTORY_PATH = os.path.join(self.tmp, "history.jsonl")
        valuation.ACCURACY_PATH = os.path.join(self.tmp, "accuracy.json")
        valuation.SNAPSHOT_PATH = os.path.join(self.tmp, "valuation.json")
        valuation.DAILY_DIR = os.path.join(self.tmp, "daily")
        valuation.PROXY_QUALITY_PATH = os.path.join(self.tmp, "proxy_quality.json")
        ledger_api.LEDGER_DIR = os.path.join(self.tmp, "ledger")
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "ledger", "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "ledger", "backfill.jsonl")
        os.makedirs(valuation.NAV_STORE_DIR)
        settings.record_source = lambda *a, **k: None

    def tearDown(self):
        (valuation.NAV_STORE_DIR, valuation.HISTORY_PATH, valuation.ACCURACY_PATH,
         valuation.SNAPSHOT_PATH, valuation.DAILY_DIR, valuation.PROXY_QUALITY_PATH,
         ledger_api.SIGNALS_PATH, ledger_api.BACKFILL_PATH,
         ledger_api.LEDGER_DIR, settings.record_source,
         estimator.http_get) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _snapshot(path):
        if os.path.isdir(path):
            return ("dir", sorted(os.listdir(path)))
        if os.path.isfile(path):
            with io.open(path, "rb") as f:
                return ("file", hashlib.sha1(f.read()).hexdigest())
        return ("none", None)

    def test_suite_guard_real_data_paths_untouched(self):
        """BLOCK-2 防再生：maintain 全链在隔离路径下执行，真实产线数据文件零变化."""
        before = {name: self._snapshot(p) for name, p in self._real_paths.items()}
        estimator.http_get = lambda url, **kw: _page([])   # 空页：最小执行
        valuation.maintain_nav_history([{"code": "000003"}])
        after = {name: self._snapshot(p) for name, p in self._real_paths.items()}
        self.assertEqual(before, after)

    def _http(self, pages):
        calls = {"n": 0}

        def fake_get(url, **kw):
            i = calls["n"]
            calls["n"] += 1
            if i < len(pages):
                return _page(pages[i])
            return _page([])

        return fake_get, calls

    def test_paging_and_frozen_existing_dates(self):
        store_path = os.path.join(valuation.NAV_STORE_DIR, "000001.json")
        with io.open(store_path, "w", encoding="utf-8") as f:
            json.dump({"code": "000001", "updated_at": "x",
                       "points": [{"date": "2026-09-10", "nav": 1.0}]}, f)
        pages = [[("2026-09-10", 9.9), ("2026-09-09", 1.1)],
                 [("2026-09-08", 1.2)]]
        fake_get, calls = self._http(pages)
        estimator.http_get = fake_get
        result = valuation.maintain_nav_history([{"code": "000001"}])
        self.assertEqual(result["updated"], 1)
        with io.open(store_path, encoding="utf-8") as f:
            obj = json.load(f)
        points = {p["date"]: p["nav"] for p in obj["points"]}
        self.assertEqual(points["2026-09-10"], 1.0)   # 首值冻结：不被 9.9 覆盖
        self.assertEqual(points["2026-09-09"], 1.1)
        self.assertEqual(points["2026-09-08"], 1.2)
        self.assertEqual(len(points), 3)

    def test_rerun_idempotent_and_early_stop(self):
        pages = [[("2026-09-10", 1.0), ("2026-09-09", 1.1)],
                 [("2026-09-08", 1.2)]]
        estimator.http_get, calls = self._http(pages)
        valuation.maintain_nav_history([{"code": "000001"}])
        first_calls = calls["n"]
        estimator.http_get, calls = self._http(pages)
        result = valuation.maintain_nav_history([{"code": "000001"}])
        self.assertEqual(result["added_points"], 0)
        # 增量停页：第 1 页日期已全部在库 → 不抓第 2 页
        self.assertEqual(calls["n"], 1)
        self.assertGreaterEqual(first_calls, 2)

    def test_failure_keeps_existing(self):
        estimator.http_get = lambda url, **kw: _page([])   # 首次：空页（建空文件）
        valuation.maintain_nav_history([{"code": "000002"}])
        store_path = os.path.join(valuation.NAV_STORE_DIR, "000002.json")
        with io.open(store_path, encoding="utf-8") as f:
            before = f.read()
        estimator.http_get = lambda url, **kw: None
        result = valuation.maintain_nav_history([{"code": "000002"}])
        self.assertIn("000002", result["failed"])
        with io.open(store_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)


if __name__ == "__main__":
    unittest.main()
