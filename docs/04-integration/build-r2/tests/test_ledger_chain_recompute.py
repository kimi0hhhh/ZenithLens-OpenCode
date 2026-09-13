# -*- coding: utf-8 -*-
"""S5 / BLOCK-A3 契约测试 · `/ledger/chain` 读时重算六步链（15-r2 §8.7）。

断言（C1/C3/C4）：
- C1：可复现历史行 → chain 长度 6、key 顺序固定（gate/ddsm/veto_crowd/veto_klow2/
  exit/output）、`exit_threshold=0.5200`、`metrics` 与行内 p_up/ddsm_state/signal 对账一致；
- C3：`chain_available=true ⇔ 返回 6 步`（不可复现行 → flag false + 空链，不编造数值）；
- C4：INSERT-ONLY 不破（调用前后 `shadow_signals.jsonl` sha256 一致）。
"""

import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import errors
import ledger_api

CHAIN_KEYS = ["gate", "ddsm", "veto_crowd", "veto_klow2", "exit", "output"]


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


def _sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class LedgerChainRecomputeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_chain_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
                       ledger_api.ARCHIVE_SIGNALS_PATH,
                       ledger_api.ARCHIVE_MANIFEST_PATH,
                       ledger_api.current_proxy_map)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        ledger_api.ARCHIVE_DIR = os.path.join(self.tmp, "archive")
        ledger_api.ARCHIVE_SIGNALS_PATH = os.path.join(
            self.tmp, "archive", "shadow_signals_archive.jsonl")
        ledger_api.ARCHIVE_MANIFEST_PATH = os.path.join(
            self.tmp, "archive", "_manifest.jsonl")
        self.bars = _seq_bars(160, seed=11)
        ledger_api.current_proxy_map = lambda: {"000001": "512480",
                                                "000002": "159352"}
        self._patch_bars = mock.patch.object(
            ledger_api.estimator, "get_bars",
            side_effect=lambda code, allow_network=False, **kw: (
                self.bars if str(code) in ("512480", "159352") else [], {}))
        self._patch_bars.start()

    def tearDown(self):
        self._patch_bars.stop()
        (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
         ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
         ledger_api.ARCHIVE_SIGNALS_PATH, ledger_api.ARCHIVE_MANIFEST_PATH,
         ledger_api.current_proxy_map) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_entry(self, code="000001", t=120):
        d = self.bars[t]["date"]
        pred = ledger_api._predict_historical(self.bars, t)
        ledger_api.write_entry({
            "date": d, "code": code, "gate": pred["gate"],
            "p_up": (None if pred["p_up"] is None else round(float(pred["p_up"]), 4)),
            "ddsm_state": pred["ddsm_state"],
            "veto_crowd": pred["veto_crowd"], "veto_klow2": pred["veto_klow2"],
            "signal": pred["signal"], "market_value": 1000.0, "cost_est": 900.0})
        return d

    def test_c1_six_steps_and_metrics_consistency(self):
        d = self._seed_entry()
        row = ledger_api.read_ledger(limit=10)[0][0]
        data = ledger_api.ledger_chain(d, "000001")
        chain = data["chain"]
        # C1：6 步 + 顺序 + 出口阈值
        self.assertEqual(len(chain), 6)
        self.assertEqual([s["key"] for s in chain], CHAIN_KEYS)
        self.assertEqual([s["step"] for s in chain], [1, 2, 3, 4, 5, 6])
        exit_step = next(s for s in chain if s["key"] == "exit")
        self.assertEqual(exit_step["metrics"]["exit_threshold"], 0.52)
        # C1：metrics 与行内对账一致（同源重算）
        self.assertEqual(data["chain_source"], "recomputed")   # v9.3
        self.assertEqual(data["gate"], row["gate"])
        self.assertEqual(data["p_up"], row["p_up"])
        self.assertEqual(data["metrics"]["p_up"], row["p_up"])
        self.assertEqual(data["metrics"]["ddsm_state"], row["ddsm_state"])
        output_step = next(s for s in chain if s["key"] == "output")
        self.assertEqual(output_step["metrics"]["signal"], row["signal"])

    def test_chain_source_stored(self):
        # v9.3：写入侧已缓存 `_chain` → `stored`（原样返回，不重算）
        d = self._seed_entry(code="000001")
        stored_chain = [{"step": i + 1, "key": k, "title": k, "status": "off",
                         "detail": "", "metrics": {}} for i, k in enumerate(CHAIN_KEYS)]
        ledger_api.write_entry({
            "date": d, "code": "000003", "gate": "none", "p_up": None,
            "ddsm_state": None, "veto_crowd": False, "veto_klow2": False,
            "signal": "gray", "market_value": 1.0, "cost_est": 1.0,
            "_chain": stored_chain, "_metrics": {"p_up": 0.5}})
        data = ledger_api.ledger_chain(d, "000003")
        self.assertEqual(data["chain_source"], "stored")
        self.assertEqual(data["chain"], stored_chain)
        row = next(r for r in ledger_api.read_ledger(limit=10)[0]
                   if r["code"] == "000003")
        self.assertTrue(row["chain_available"])

    def test_c3_available_iff_six_steps(self):
        d = self._seed_entry(code="000001")
        rows, _total = ledger_api.read_ledger(limit=10)
        row = next(r for r in rows if r["code"] == "000001")
        self.assertTrue(row["chain_available"])
        data = ledger_api.ledger_chain(d, "000001")
        self.assertEqual(len(data["chain"]), 6)
        # v9.3 一致性：available=true ⇔ chain_source ∈ {stored, recomputed}
        self.assertIn(data["chain_source"], ("stored", "recomputed"))

        # 无代理映射 → 不可复现：flag false + 空链 + chain_source=null（不编造）
        ledger_api.write_entry({
            "date": d, "code": "000009", "gate": "none", "p_up": None,
            "ddsm_state": None, "veto_crowd": False, "veto_klow2": False,
            "signal": "gray", "market_value": 1.0, "cost_est": 1.0})
        rows2, _t = ledger_api.read_ledger(limit=10)
        row9 = next(r for r in rows2 if r["code"] == "000009")
        self.assertFalse(row9["chain_available"])
        data9 = ledger_api.ledger_chain(d, "000009")
        self.assertEqual(data9["chain"], [])
        self.assertIsNone(data9["chain_source"])

        # 有代理但 date 不在 bars → 不可复现
        ledger_api.write_entry({
            "date": "2099-01-01", "code": "000001", "gate": "none", "p_up": None,
            "ddsm_state": None, "veto_crowd": False, "veto_klow2": False,
            "signal": "gray", "market_value": 1.0, "cost_est": 1.0})
        rows3, _t = ledger_api.read_ledger(limit=10)
        row_far = next(r for r in rows3 if r["date"] == "2099-01-01")
        self.assertFalse(row_far["chain_available"])
        data_far = ledger_api.ledger_chain("2099-01-01", "000001")
        self.assertEqual(data_far["chain"], [])
        self.assertIsNone(data_far["chain_source"])

    def test_c4_insert_only_untouched(self):
        d = self._seed_entry()
        before = _sha256(ledger_api.SIGNALS_PATH)
        ledger_api.ledger_chain(d, "000001")
        ledger_api.read_ledger(limit=50)
        self.assertEqual(_sha256(ledger_api.SIGNALS_PATH), before)

    def test_missing_entry_still_not_found(self):
        with self.assertRaises(errors.ApiError) as cm:
            ledger_api.ledger_chain("2099-01-01", "999999")
        self.assertEqual(cm.exception.code, errors.E_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
