# -*- coding: utf-8 -*-
"""R2 契约测试 · t*_real 自动回填（08-r2 §5.2；R2-12；R-1 复算锚；ADR-0008）。

断言要点：
- 到期写 `t*_real = proxy_close(T+H)/proxy_close(T) − 1` + `method=proxy_bar` + `proxy_code`；
- 幂等：已存在值重复执行不再写（避免重复行）；
- 无对应 signal 仍拒绝写入（E_VALIDATION）；未知 method 拒绝。
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import errors
import ledger_api


def _bars(n=30):
    out = []
    price = 1.0
    for i in range(n):
        price = price * (1 + (0.001 if i % 3 else -0.0005))
        out.append({"date": "2026-09-%02d" % (1 + i), "open": price, "high": price,
                    "low": price, "close": price, "volume": 1.0})
    return out


class BackfillRealTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_bf_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.current_proxy_map,
                       ledger_api.estimator.get_bars)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        ledger_api.current_proxy_map = lambda: {"000001": "512480"}
        self.bars = _bars(30)

    def tearDown(self):
        (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH, ledger_api.BACKFILL_PATH,
         ledger_api.current_proxy_map, ledger_api.estimator.get_bars) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, date="2026-09-01"):
        ledger_api.write_entry({
            "date": date, "code": "000001", "gate": "E1", "p_up": 0.66,
            "ddsm_state": [1, 2, 3], "veto_crowd": False, "veto_klow2": False,
            "signal": "up", "market_value": 1000.0, "cost_est": 900.0})

    def test_due_writes_values_method_and_anchor(self):
        self._seed()
        with mock.patch.object(ledger_api.estimator, "get_bars",
                               return_value=(self.bars, {})):
            info = ledger_api.backfill_due(allow_network=True)
        self.assertEqual(info["written"], 1)
        i = next(j for j, b in enumerate(self.bars) if b["date"] == "2026-09-01")
        rows = ledger_api.read_ledger(limit=10)[0]
        r = rows[0]
        expect1 = self.bars[i + 1]["close"] / self.bars[i]["close"] - 1.0
        expect3 = self.bars[i + 3]["close"] / self.bars[i]["close"] - 1.0
        self.assertAlmostEqual(r["t1_real"], expect1, places=6)
        self.assertAlmostEqual(r["t3_real"], expect3, places=6)
        self.assertEqual(r["t1_real_method"], "proxy_bar")
        self.assertEqual(r["backfill_proxy_code"], "512480")
        raw = ledger_api.read_backfill_raw()
        self.assertEqual(raw[0]["method"], "proxy_bar")
        self.assertEqual(raw[0]["proxy_code"], "512480")

    def test_rerun_writes_nothing(self):
        self._seed()
        with mock.patch.object(ledger_api.estimator, "get_bars",
                               return_value=(self.bars, {})):
            ledger_api.backfill_due(allow_network=True)
            info = ledger_api.backfill_due(allow_network=True)
        self.assertEqual(info["written"], 0)
        self.assertEqual(len(ledger_api.read_backfill_raw()), 1)
        # 但 t15 若因 bar 不足未回填，重复运行仍不重写已有值
        self.assertEqual(info["due"], 0)

    def test_no_signal_still_rejected(self):
        with self.assertRaises(errors.ApiError) as cm:
            ledger_api.write_backfill([{"date": "2099-01-01", "code": "999999",
                                        "t1_real": 0.01}])
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_unknown_method_rejected(self):
        self._seed()
        with self.assertRaises(errors.ApiError) as cm:
            ledger_api.write_backfill([{"date": "2026-09-01", "code": "000001",
                                        "t1_real": 0.01, "method": "nav_bar"}])
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)


if __name__ == "__main__":
    unittest.main()
