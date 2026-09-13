# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 台账（09 §5.9/§5.28 · A-10 · INSERT-ONLY）。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import errors
import ledger_api


class LedgerV4Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_ledger_")
        self._dir = ledger_api.LEDGER_DIR
        self._sig = ledger_api.SIGNALS_PATH
        self._back = ledger_api.BACKFILL_PATH
        self._arch = (ledger_api.ARCHIVE_DIR, ledger_api.ARCHIVE_SIGNALS_PATH,
                      ledger_api.ARCHIVE_MANIFEST_PATH)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        # 读隔离：归档合并集不得引入真实 ledger/archive（BLOCK-2 审计项）
        ledger_api.ARCHIVE_DIR = os.path.join(self.tmp, "archive")
        ledger_api.ARCHIVE_SIGNALS_PATH = os.path.join(
            self.tmp, "archive", "shadow_signals_archive.jsonl")
        ledger_api.ARCHIVE_MANIFEST_PATH = os.path.join(
            self.tmp, "archive", "_manifest.jsonl")

    def tearDown(self):
        ledger_api.LEDGER_DIR = self._dir
        ledger_api.SIGNALS_PATH = self._sig
        ledger_api.BACKFILL_PATH = self._back
        (ledger_api.ARCHIVE_DIR, ledger_api.ARCHIVE_SIGNALS_PATH,
         ledger_api.ARCHIVE_MANIFEST_PATH) = self._arch
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _entry(self, date="2026-09-12", code="000001"):
        return {"date": date, "code": code, "gate": "E1", "p_up": 0.66,
                "ddsm_state": [1, 2, 3], "veto_crowd": False, "veto_klow2": False,
                "signal": "up", "market_value": 1000.0, "cost_est": 900.0}

    def test_insert_only_conflict(self):
        ledger_api.write_entry(self._entry())
        with self.assertRaises(errors.ApiError) as cm:
            ledger_api.write_entry(self._entry())
        self.assertEqual(cm.exception.code, errors.E_CONFLICT)

    def test_created_at_equals_written_at(self):
        ledger_api.write_entry(self._entry())
        rec = ledger_api.read_signals_raw()[0]
        self.assertEqual(rec["created_at"], rec["written_at"])

    def test_backfill_is_separate_file(self):
        ledger_api.write_entry(self._entry())
        with open(ledger_api.SIGNALS_PATH, "r", encoding="utf-8") as f:
            before = f.read()
        ledger_api.write_backfill([{"date": "2026-09-12", "code": "000001",
                                    "t1_real": 0.012}])
        with open(ledger_api.SIGNALS_PATH, "r", encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)  # 原行不可改
        rows, _total = ledger_api.read_ledger()
        self.assertEqual(rows[0]["t1_real"], 0.012)

    def test_backfill_without_signal_rejected(self):
        with self.assertRaises(errors.ApiError) as cm:
            ledger_api.write_backfill([{"date": "2099-01-01", "code": "999999",
                                        "t1_real": 0.01}])
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_ledger_entry_v3_fields(self):
        ledger_api.write_entry(self._entry())
        rows, total = ledger_api.read_ledger()
        self.assertEqual(total, 1)
        r = rows[0]
        for k in ("created_at", "record_seq", "source_file", "chain_available"):
            self.assertIn(k, r)
        self.assertEqual(r["source_file"], "shadow_signals.jsonl")

    def test_shadow_ledger_v4_retention(self):
        ledger_api.write_entry(self._entry())
        data = ledger_api.shadow_ledger()
        self.assertEqual(data["retention_policy"], "first_of_day_immutable_full_archive")
        self.assertTrue(data["first_of_day_immutable"])
        self.assertIn("archive_manifest_at", data)

    def test_shadow_ledger_empty_retention(self):
        data = ledger_api.shadow_ledger()
        self.assertEqual(data["retention_policy"], "first_of_day_immutable_full_archive")
        self.assertIn("rows", data)


if __name__ == "__main__":
    unittest.main()
