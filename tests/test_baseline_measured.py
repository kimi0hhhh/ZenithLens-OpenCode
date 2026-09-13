# -*- coding: utf-8 -*-
"""R2 契约测试 · 基线实测化（09-r2 §6.3；08-r2 §5.4；R2-14；ADR-0013）。

断言要点：
- `measured_baseline = max(Σ[t1_real>0]/N, Σ[t1_real<0]/N)`；N=0 → null；
- 旧常量彻底退役（无模块级 BASELINE_RATE；空台账不返回旧值）；
- 影子盘进度/审计 baseline_source 恒 measured。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ledger_api


class BaselineMeasuredTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_base_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
                       ledger_api.ARCHIVE_SIGNALS_PATH,
                       ledger_api.ARCHIVE_MANIFEST_PATH)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        # 读隔离：baseline 合并集不得引入真实 ledger/archive（BLOCK-2 审计项）
        ledger_api.ARCHIVE_DIR = os.path.join(self.tmp, "archive")
        ledger_api.ARCHIVE_SIGNALS_PATH = os.path.join(
            self.tmp, "archive", "shadow_signals_archive.jsonl")
        ledger_api.ARCHIVE_MANIFEST_PATH = os.path.join(
            self.tmp, "archive", "_manifest.jsonl")

    def tearDown(self):
        (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
         ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
         ledger_api.ARCHIVE_SIGNALS_PATH,
         ledger_api.ARCHIVE_MANIFEST_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_formula(self):
        rows = [{"t1_real": 0.02}, {"t1_real": 0.03}, {"t1_real": -0.01},
                {"t1_real": None}]
        # up=2/3, down=1/3 → max=2/3
        self.assertAlmostEqual(ledger_api.measured_baseline(rows), 2.0 / 3.0, places=6)

    def test_empty_is_null(self):
        self.assertIsNone(ledger_api.measured_baseline([]))
        self.assertIsNone(ledger_api.measured_baseline([{"t1_real": None}]))

    def test_legacy_constant_retired(self):
        self.assertFalse(hasattr(ledger_api, "BASELINE_RATE"))
        p = ledger_api.shadow_progress()
        self.assertIsNone(p["baseline_rate"])          # 不填 0.5830
        self.assertEqual(p["baseline_source"], "measured")
        a = ledger_api.shadow_audit()
        self.assertIsNone(a["baseline_rate"])
        self.assertEqual(a["baseline_source"], "measured")

    def test_deviation_recomputable(self):
        ledger_api.write_entry({"date": "2026-09-01", "code": "000001", "gate": "E1",
                                "p_up": 0.66, "ddsm_state": [1, 2, 3],
                                "veto_crowd": False, "veto_klow2": False,
                                "signal": "up", "market_value": 1.0, "cost_est": 1.0})
        ledger_api.write_backfill([{"date": "2026-09-01", "code": "000001",
                                    "t1_real": 0.01}])
        a = ledger_api.shadow_audit()
        self.assertAlmostEqual(a["baseline_rate"], 1.0, places=4)   # 唯一行上涨
        self.assertAlmostEqual(a["hit_rate"], 1.0, places=4)
        self.assertAlmostEqual(a["deviation_pp"], 0.0, places=4)


if __name__ == "__main__":
    unittest.main()
