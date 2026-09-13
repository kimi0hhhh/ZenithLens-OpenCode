# -*- coding: utf-8 -*-
"""R2 契约测试 · 影子盘档位重算（08-r2 §4.2；R2-07；N-4 差异摘要）。

断言要点：
- 先归档后重生成（旧记录全量归档，reason=recompute_by_current_tier）；
- created_at 继承（幂等稳定）；重复执行集合不变（零写入）；
- 档位一致性 0 冲突（C/D 记录清出）。
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ledger_api


def _seq_bars(n, seed=7, start="2026-01-05"):
    d = date.fromisoformat(start)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    out = []
    price = 1.0
    x = seed
    for _i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        x = (1103515245 * x + 12345) % 2147483648
        r = ((x / 2147483648.0) - 0.5) * 0.03
        o = price
        price = max(0.01, price * (1.0 + r))
        c = price
        out.append({"date": d.strftime("%Y-%m-%d"), "open": o,
                    "high": max(o, c) * 1.004, "low": min(o, c) * 0.996,
                    "close": c, "volume": float(1000 + (x % 500))})
        d += timedelta(days=1)
    return out


class ShadowRecomputeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_recompute_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
                       ledger_api.ARCHIVE_SIGNALS_PATH,
                       ledger_api.ARCHIVE_MANIFEST_PATH, ledger_api._load_proxy_bars,
                       ledger_api._proxy_assets)
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
         ledger_api.ARCHIVE_MANIFEST_PATH, ledger_api._load_proxy_bars,
         ledger_api._proxy_assets) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _patch_assets(self):
        assets = [({"code": "000001"}, _seq_bars(140, seed=11)),
                  ({"code": "000002"}, _seq_bars(140, seed=23))]
        ledger_api._load_proxy_bars = lambda allow_network=True: assets
        ledger_api._proxy_assets = lambda: [
            {"code": "000001", "tier": "A", "proxy_code": "512480"},
            {"code": "000002", "tier": "B", "proxy_code": "512100"}]
        return assets

    def test_archive_first_recompute_and_idempotent(self):
        self._patch_assets()
        # 旧记录：一天错档（C 码）记录 + 一条将被清出的记录
        ledger_api.write_entry({"date": "2020-01-02", "code": "999999", "gate": "none",
                                "p_up": None, "ddsm_state": None, "veto_crowd": False,
                                "veto_klow2": False, "signal": "gray",
                                "market_value": 1.0, "cost_est": 1.0})
        old = ledger_api.read_signals_raw()
        info = ledger_api.recompute_shadow_window()
        self.assertTrue(info["changed"])
        self.assertEqual(info["tier_conflicts"], 0)
        self.assertTrue(os.path.isfile(ledger_api.ARCHIVE_SIGNALS_PATH))
        arch = ledger_api._read_jsonl(ledger_api.ARCHIVE_SIGNALS_PATH)
        self.assertTrue(any(a["code"] == "999999" for a in arch))
        manifests = ledger_api._read_jsonl(ledger_api.ARCHIVE_MANIFEST_PATH)
        self.assertEqual(manifests[-1]["reason"], "recompute_by_current_tier")
        self.assertIn("added_count", manifests[-1])
        self.assertIn("removed_count", manifests[-1])
        # created_at 继承（同 (date,code) 复用旧值）
        new_rows = ledger_api.read_signals_raw()
        new_map = {(r["date"], r["code"]): r for r in new_rows}
        # 重复执行：集合不变 → 零写入
        info2 = ledger_api.recompute_shadow_window()
        self.assertFalse(info2["changed"])
        self.assertEqual(info2["written"], 0)
        rows2 = ledger_api.read_signals_raw()
        self.assertEqual(len(rows2), len(new_rows))
        _ = old, new_map

    def test_created_at_inherited(self):
        self._patch_assets()
        ledger_api.rolling_shadow_backfill()
        before = {(r["date"], r["code"]): r.get("created_at")
                  for r in ledger_api.read_signals_raw()}
        # 人为把磁盘上的 created_at 改成固定值 + 加一条将被清出的旧行，重算后必须继承
        rows = ledger_api.read_signals_raw()
        for r in rows:
            r["created_at"] = "2026-01-01T00:00:00+08:00"
        rows.append({"date": "2020-01-02", "code": "000009", "gate": "none",
                     "p_up": None, "ddsm_state": None, "veto_crowd": False,
                     "veto_klow2": False, "signal": "gray", "opened": False,
                     "created_at": "2026-01-01T00:00:00+08:00"})
        ledger_api._write_all_signals(rows)
        info = ledger_api.recompute_shadow_window()
        self.assertTrue(info["changed"])
        after = {(r["date"], r["code"]): r.get("created_at")
                 for r in ledger_api.read_signals_raw()}
        for k, v in after.items():
            if k in before:
                self.assertEqual(v, "2026-01-01T00:00:00+08:00", k)


if __name__ == "__main__":
    unittest.main()
