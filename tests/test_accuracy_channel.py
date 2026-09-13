# -*- coding: utf-8 -*-
"""R2 契约测试 · 误差通道 v2（09-r2 §3.2；08-r2 §3.1/D-3/R-4）。

断言要点：
- 全档 `mode|code` 归键；官方档与 holdings 档同日各自成样本（防饥饿）；
- 评分对象 = 每个 (date, code, mode) 当日最后一条（D-3，取 written_at 最大）；
- n_test<5 → 统计值 null（confidence=unknown + conf_reason=no_samples）；
- 官方档 stale-anchor（nav_date<D）照常参与误差统计；
- conf_reason 五值 + 按序命中即停（R-4）。
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

import settings
import valuation


class AccuracyChannelV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_acc_")
        self._saved = (valuation.HISTORY_PATH, valuation.ACCURACY_PATH,
                       valuation.NAV_STORE_DIR, valuation.SNAPSHOT_PATH,
                       settings.record_source)
        valuation.HISTORY_PATH = os.path.join(self.tmp, "history.jsonl")
        valuation.ACCURACY_PATH = os.path.join(self.tmp, "accuracy.json")
        valuation.NAV_STORE_DIR = os.path.join(self.tmp, "nav")
        valuation.SNAPSHOT_PATH = os.path.join(self.tmp, "valuation.json")
        settings.record_source = lambda *a, **k: None
        os.makedirs(valuation.NAV_STORE_DIR)

    def tearDown(self):
        (valuation.HISTORY_PATH, valuation.ACCURACY_PATH, valuation.NAV_STORE_DIR,
         valuation.SNAPSHOT_PATH, settings.record_source) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _nav_store(self, code, points):
        path = os.path.join(valuation.NAV_STORE_DIR, "%s.json" % code)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump({"code": code, "updated_at": "2026-09-12T00:00:00+08:00",
                       "points": [{"date": d, "nav": v} for d, v in points]}, f)

    def _rec(self, date, mode, est, written, code="000001", nav_date=None):
        return {"date": date, "code": code, "name": "x", "valuation_mode": mode,
                "change_rate": est, "estimated_nav": None, "written_at": written,
                "nav_date": nav_date, "confidence": "unknown", "trace": [{"mode": mode}],
                "run_id": "r"}

    def test_full_grade_keys_and_last_of_mode_same_day(self):
        code = "000001"
        dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-05"]
        navs = [1.00, 1.01, 1.02, 1.03, 1.04, 1.05]
        self._nav_store(code, list(zip(["2026-08-31"] + dates, navs)))
        for i, d in enumerate(dates):
            real = navs[i + 1] / navs[i] - 1.0
            # 同 mode 同日先写一条错值、后写一条对值（D-3 应只取最后一条）
            valuation.append_history(self._rec(d, "holdings", 0.5,
                                               "%sT01:00:00+08:00" % d, code=code))
            valuation.append_history(self._rec(d, "holdings", real,
                                               "%sT02:00:00+08:00" % d, code=code))
            # 另一 mode 同日各自成样本（防饥饿）
            valuation.append_history(self._rec(d, "official", real,
                                               "%sT03:00:00+08:00" % d, code=code))
        acc = valuation.build_accuracy([{"code": code}])
        self.assertIn("holdings|000001", acc)
        self.assertIn("official|000001", acc)
        h = acc["holdings|000001"]
        self.assertEqual(h["n_test"], 5)
        self.assertLessEqual(h["mae_rate"], 0.0001)  # 只取最后一条 → 误差≈0
        self.assertEqual(h["matched_days"], dates)
        self.assertEqual(h["window_days"], 40)
        self.assertIn("updated_at", h)
        self.assertIn(h["source"], ("nav_store", "legacy_nav_history"))

    def test_low_sample_keeps_stats_null(self):
        code = "000002"
        self._nav_store(code, [("2026-09-01", 1.0), ("2026-09-02", 1.01)])
        valuation.append_history(self._rec("2026-09-02", "proxy", 0.01,
                                           "2026-09-02T15:30:00+08:00", code=code))
        acc = valuation.build_accuracy([{"code": code}])
        entry = acc["proxy|000002"]
        self.assertEqual(entry["n_test"], 1)
        self.assertIsNone(entry["mae_rate"])
        self.assertIsNone(entry["dir_hit_rate"])
        conf, mae, _dh, _n = valuation._confidence_of("proxy", code)
        self.assertEqual(conf, "unknown")
        self.assertIsNone(mae)

    def test_official_stale_anchor_participates(self):
        code = "000003"
        self._nav_store(code, [("2026-09-01", 1.0), ("2026-09-02", 1.05),
                               ("2026-09-03", 1.10), ("2026-09-04", 1.155),
                               ("2026-09-05", 1.21275), ("2026-09-06", 1.2734)])
        # 官方档 nav_date < D（未发布、以最近一期净值为锚）→ 照常参与
        for i, d in enumerate(["2026-09-02", "2026-09-03", "2026-09-04",
                               "2026-09-05", "2026-09-06"]):
            valuation.append_history(self._rec(d, "official", 0.05,
                                               "%sT10:00:00+08:00" % d, code=code,
                                               nav_date="2026-09-01"))
        acc = valuation.build_accuracy([{"code": code}])
        self.assertEqual(acc["official|000003"]["n_test"], 5)
        self.assertGreater(acc["official|000003"]["mae_rate"], 0.0)

    def test_conf_reason_ordered_stop(self):
        code = "000004"
        # 序 1：mode=unknown（全链无来源）
        rec = self._rec("2026-09-12", "unknown", None, "2026-09-12T15:00:00+08:00",
                        code=code)
        self.assertEqual(valuation.conf_reason_of(rec), "mode_unknown")
        # 序 2：无当日记录 + 预算跳过
        with io.open(valuation.SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump({"as_of": valuation._today(), "records": [],
                       "budget": {"exceeded": True, "skipped": [code]}}, f)
        valuation._SNAP_CACHE["mtime"] = None
        valuation._SNAP_CACHE["obj"] = {}
        self.assertEqual(valuation.conf_reason_of(None, code=code,
                                                  as_of_date=valuation._today()),
                         "budget_exceeded")
        # 序 3：无当日记录（其他）→ valuation_missing
        self.assertEqual(valuation.conf_reason_of(None, code="000099",
                                                  as_of_date=valuation._today()),
                         "valuation_missing")
        # 序 4：有记录但净值对缺 → nav_missing
        rec = self._rec("2026-01-01", "proxy", 0.02, "2026-01-01T15:00:00+08:00",
                        code="000098")
        self.assertEqual(valuation.conf_reason_of(rec), "nav_missing")
        # 序 5：有净值对但 n_test<5 → no_samples
        self._nav_store("000097", [("2026-09-01", 1.0), ("2026-09-02", 1.01)])
        valuation.append_history(self._rec("2026-09-02", "proxy", 0.01,
                                           "2026-09-02T15:00:00+08:00", code="000097"))
        valuation.build_accuracy([{"code": "000097"}])
        rec = self._rec("2026-09-02", "proxy", 0.01, "2026-09-02T15:00:00+08:00",
                        code="000097")
        self.assertEqual(valuation.conf_reason_of(rec), "no_samples")

    def test_conf_reason_null_when_conf_known(self):
        rec = self._rec("2026-09-12", "proxy", 0.01, "2026-09-12T15:00:00+08:00")
        rec["confidence"] = "high"
        self.assertIsNone(valuation.conf_reason_of(rec))


class ConfReasonInPublicValuationTest(unittest.TestCase):
    def test_public_valuation_exposes_conf_reason_and_qdii(self):
        pub = valuation.public_valuation(valuation.unknown_skeleton("000001", "x"))
        self.assertIn("conf_reason", pub)
        self.assertIn("qdii_correction", pub)
        self.assertIsNone(pub["qdii_correction"])


if __name__ == "__main__":
    unittest.main()
