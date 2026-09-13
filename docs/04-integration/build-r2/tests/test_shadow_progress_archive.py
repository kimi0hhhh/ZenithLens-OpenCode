# -*- coding: utf-8 -*-
"""R2 契约测试 · 影子盘进度 20/60 归档合并（08-r2 §5.3；R2-13；B2/B3）。

断言要点：
- consecutive_days / history_days 按「主文件 ∪ 归档」合并计算，可达 ≥60；
- 归档缺失 → 降级为主文件 + archive_merged=false + note 标注（不伪造天数）；
- baseline_source 恒 measured；N=0 → baseline_rate null。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ledger_api


def _weekdays(start, n):
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


class ShadowProgressArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_mrg_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
                       ledger_api.ARCHIVE_SIGNALS_PATH,
                       ledger_api.ARCHIVE_MANIFEST_PATH)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        ledger_api.ARCHIVE_DIR = os.path.join(self.tmp, "archive")
        ledger_api.ARCHIVE_SIGNALS_PATH = os.path.join(
            self.tmp, "archive", "shadow_signals_archive.jsonl")
        ledger_api.ARCHIVE_MANIFEST_PATH = os.path.join(
            self.tmp, "archive", "_manifest.jsonl")

    def tearDown(self):
        (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH, ledger_api.BACKFILL_PATH,
         ledger_api.ARCHIVE_DIR, ledger_api.ARCHIVE_SIGNALS_PATH,
         ledger_api.ARCHIVE_MANIFEST_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _row(self, d, code="000001"):
        return {"date": d, "code": code, "gate": "none", "p_up": None,
                "ddsm_state": None, "veto_crowd": False, "veto_klow2": False,
                "signal": "gray", "opened": False, "created_at": "x"}

    def test_merge_reaches_beyond_20(self):
        all_days = _weekdays("2026-05-01", 65)   # 65 个连续工作日
        main_days = all_days[-60:]                # v9.5：主文件滚动窗 60
        arch_days = all_days[:-60]
        for d in main_days:
            ledger_api._append_jsonl(ledger_api.SIGNALS_PATH, self._row(d))
        os.makedirs(ledger_api.ARCHIVE_DIR)
        for d in arch_days:
            ledger_api._append_jsonl(ledger_api.ARCHIVE_SIGNALS_PATH, self._row(d))
        p = ledger_api.shadow_progress()
        self.assertEqual(p["consecutive_days"], 65)
        self.assertEqual(p["history_days"], 65)
        self.assertTrue(p["archive_merged"])
        self.assertEqual(p["baseline_source"], "measured")
        self.assertIsNone(p["baseline_rate"])   # 无 t1_real → null（不填旧常量）
        self.assertEqual(p["window_days"], 60)  # v9.5 §13：主文件滚动窗口 60

    def test_missing_archive_degrades(self):
        main_days = _weekdays("2026-06-22", 60)   # v9.5：60 日量级样本
        for d in main_days:
            ledger_api._append_jsonl(ledger_api.SIGNALS_PATH, self._row(d))
        p = ledger_api.shadow_progress()
        self.assertEqual(p["consecutive_days"], 60)
        self.assertEqual(p["window_days"], 60)
        self.assertFalse(p["archive_merged"])
        self.assertIn("降级", p["note"])

    def test_window_60_qualified_reachable_with_disclosure(self):
        # v9.5 §13.3：满 60 交易日窗后 qualified 可达；note 必须带「走前口径」诚实披露
        main_days = _weekdays("2026-06-22", 60)
        for d in main_days:
            ledger_api._append_jsonl(ledger_api.SIGNALS_PATH, self._row(d))
        p = ledger_api.shadow_progress()
        self.assertEqual(p["window_days"], 60)
        self.assertEqual(p["consecutive_days"], 60)
        self.assertEqual(p["status"], "qualified")
        self.assertEqual(p["progress_ratio"], 1.0)
        self.assertIn("走前口径", p["note"])
        self.assertIn("非自然积累", p["note"])

    def test_measured_baseline(self):
        rows = [{"t1_real": 0.01}] * 3 + [{"t1_real": -0.01}]
        self.assertEqual(ledger_api.measured_baseline(rows), 0.75)
        self.assertIsNone(ledger_api.measured_baseline([]))
        self.assertIsNone(ledger_api.measured_baseline([{"t1_real": None}]))


if __name__ == "__main__":
    unittest.main()
