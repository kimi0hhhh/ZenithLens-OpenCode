# -*- coding: utf-8 -*-
"""契约 v9.5 关键路径测试 · 影子盘 60 交易日滚动回填 + 因子上限口径。

v9.5 §13（用户指令「直接补满 60 天，来一天换一天」）：窗口 20→60；
启动即回填满 60 日，此后每日滚动（进一天、出一天）；INSERT-ONLY/幂等/归档语义不变。
不联网：以确定性合成 K 线替换 `_load_proxy_bars`，落盘到临时目录。
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import factor_board
import fund_predict
import ledger_api

WINDOW = ledger_api.SHADOW_WINDOW_DAYS          # 唯一常量源（本文件不写死 60）


def _seq_bars(n, seed=7, start="2026-01-05"):
    """确定性交易日 K 线（跳过周末），前 n 条与 n+1 条前缀严格一致。"""
    d = date.fromisoformat(start)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    out = []
    price = 1.0
    x = seed
    for _ in range(n):
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


REQUIRED_FIELDS = ("date", "code", "gate", "p_up", "ddsm_state", "veto_crowd",
                   "veto_klow2", "signal", "opened", "created_at")


class ShadowBackfill60Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_shadow_")
        self._saved = (ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
                       ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
                       ledger_api.ARCHIVE_SIGNALS_PATH, ledger_api.ARCHIVE_MANIFEST_PATH,
                       ledger_api._load_proxy_bars)
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
         ledger_api.ARCHIVE_MANIFEST_PATH, ledger_api._load_proxy_bars) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _patch_assets(self, bars_list):
        assets = [({"code": "T%05d" % (i + 1)}, b) for i, b in enumerate(bars_list)]
        ledger_api._load_proxy_bars = lambda allow_network=True: assets

    def test_window_is_last_60_trading_days_insert_only_fields(self):
        # B-5：启动回填深度 = 60（默认走常量，一次性补满）
        bars1 = _seq_bars(140, seed=11)
        bars2 = _seq_bars(140, seed=23)
        self._patch_assets([bars1, bars2])
        window, records = ledger_api.compute_shadow_window()
        self.assertEqual(len(window), WINDOW)
        self.assertEqual(WINDOW, 60)
        self.assertEqual(window, [b["date"] for b in bars1][-WINDOW:])
        self.assertEqual(len(records), 2 * WINDOW)  # 2 资产 × 60 日
        for r in records:
            for k in REQUIRED_FIELDS:
                self.assertIn(k, r)
            self.assertIsInstance(r["opened"], bool)
            self.assertEqual(r["opened"], r["signal"] == "up")
            self.assertIn(r["gate"], ("E1", "E3", "none"))
            self.assertIn(r["signal"], ("up", "abstain", "gray"))
        info = ledger_api.rolling_shadow_backfill()   # 默认深度 = 60
        self.assertEqual(info["written"], 2 * WINDOW)
        self.assertEqual(info["trimmed"], 0)
        self.assertEqual(info["total_records"], 2 * WINDOW)
        self.assertEqual(info["window_days"], WINDOW)
        self.assertEqual(info["first_date"], window[0])
        self.assertEqual(info["last_date"], window[-1])

    def test_rerun_is_idempotent(self):
        self._patch_assets([_seq_bars(140, seed=11), _seq_bars(140, seed=23)])
        ledger_api.rolling_shadow_backfill()
        info = ledger_api.rolling_shadow_backfill()
        self.assertEqual(info["written"], 0)
        self.assertEqual(info["trimmed"], 0)
        self.assertEqual(info["total_records"], 2 * WINDOW)
        _rows, total = ledger_api.read_ledger(limit=1000)
        self.assertEqual(total, 2 * WINDOW)

    def test_warm_start_fast_path_skips_recompute(self):
        """S3 冷启动：窗口齐备时跳过重算（零训练）——compute_shadow_window 不被调用。"""
        self._patch_assets([_seq_bars(140, seed=11), _seq_bars(140, seed=23)])
        ledger_api.rolling_shadow_backfill()        # 首次：全量计算 + 写入
        calls = {"n": 0}
        orig = ledger_api.compute_shadow_window

        def counting(days=WINDOW, allow_network=True, only_dates=None, assets=None):
            calls["n"] += 1
            return orig(days=days, allow_network=allow_network,
                        only_dates=only_dates, assets=assets)

        ledger_api.compute_shadow_window = counting
        try:
            info = ledger_api.rolling_shadow_backfill()
        finally:
            ledger_api.compute_shadow_window = orig
        self.assertEqual(calls["n"], 0)             # 快路径：未重算
        self.assertEqual(info["written"], 0)
        self.assertEqual(info["trimmed"], 0)
        self.assertEqual(info["total_records"], 2 * WINDOW)
        self.assertIn("快路径", info["note"])

    def test_daily_roll_one_in_one_out(self):
        """「来一天换一天」：追加一日 → written=2 / trimmed=2（按资产数），
        窗深保持 60，最旧一天进归档，重复执行零写；且走**增量模式**（only_dates=新增 1 日）。"""
        self._patch_assets([_seq_bars(140, seed=11), _seq_bars(140, seed=23)])
        ledger_api.rolling_shadow_backfill()
        old_window = [b["date"] for b in _seq_bars(140, seed=11)][-WINDOW:]
        # 交易日历右移一天：窗口滚动，最旧一天被裁掉
        self._patch_assets([_seq_bars(141, seed=11), _seq_bars(141, seed=23)])
        new_day = [b["date"] for b in _seq_bars(141, seed=11)][-1]
        seen = {"only_dates": None}
        orig = ledger_api.compute_shadow_window

        def spy(days=WINDOW, allow_network=True, only_dates=None, assets=None):
            seen["only_dates"] = list(only_dates) if only_dates is not None else None
            return orig(days=days, allow_network=allow_network,
                        only_dates=only_dates, assets=assets)

        ledger_api.compute_shadow_window = spy
        try:
            info = ledger_api.rolling_shadow_backfill()
        finally:
            ledger_api.compute_shadow_window = orig
        # v9.5 §13.4 增量：只算新增 1 日（而非整窗 60 日）
        self.assertEqual(seen["only_dates"], [new_day])
        new_window = [b["date"] for b in _seq_bars(141, seed=11)][-WINDOW:]
        self.assertEqual(info["written"], 2)
        self.assertEqual(info["trimmed"], 2)
        self.assertEqual(info["total_records"], 2 * WINDOW)
        self.assertEqual(info["window_days"], WINDOW)
        self.assertEqual(info["first_date"], new_window[0])
        self.assertNotEqual(old_window[0], new_window[0])
        rows, total = ledger_api.read_ledger(limit=1000)
        self.assertEqual(total, 2 * WINDOW)
        dates = sorted({r["date"] for r in rows})
        self.assertEqual(dates, new_window)
        self.assertNotIn(old_window[0], dates)
        self.assertTrue(os.path.isfile(ledger_api.ARCHIVE_SIGNALS_PATH))
        self.assertTrue(os.path.isfile(ledger_api.ARCHIVE_MANIFEST_PATH))
        self.assertEqual(ledger_api.shadow_ledger()["archive_manifest_at"] is not None, True)
        # B-7：manifest window_days 随 60；重复执行幂等
        manifests = ledger_api._read_jsonl(ledger_api.ARCHIVE_MANIFEST_PATH)
        self.assertEqual(manifests[-1]["window_days"], WINDOW)
        info2 = ledger_api.rolling_shadow_backfill()
        self.assertEqual(info2["written"], 0)
        self.assertEqual(info2["trimmed"], 0)


class WindowConstantTest(unittest.TestCase):
    """B-1/B-2/B-3：60 唯一常量源；旧 20 值零残留（含 signal_state 默认回退）。"""

    def test_constant_is_60(self):
        self.assertEqual(ledger_api.SHADOW_WINDOW_DAYS, 60)

    def test_signal_state_uses_constant_window(self):
        # fund_predict 默认回退改引用常量；low_frequency_note 为 60 日口径、无旧基线文案
        import inspect
        src = inspect.getsource(fund_predict.signal_state)
        self.assertIn("SHADOW_WINDOW_DAYS", src)
        self.assertNotIn("rolling_window_days\": 20", src)
        self.assertNotIn("20 交易日约 11 资产", src)

    def test_no_stale_20_in_shadow_call_chain(self):
        import io
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("app.py", "ledger_api.py", "fund_predict.py"):
            with io.open(os.path.join(root, name), encoding="utf-8") as f:
                src = f.read()
            for bad in ("days=20", "SHADOW_WINDOW_DAYS = 20", "rolling_window_days\": 20",
                        "DEFAULT_WINDOW_DAYS"):
                self.assertNotIn(bad, src, "%s 残留: %s" % (name, bad))


class FactorPansCapsTest(unittest.TestCase):
    def test_adopted_caps_and_rule_text(self):
        adopted = next(p for p in factor_board.pans() if p["role"] == "adopted")
        self.assertEqual(adopted["caps"], {"veto_max": 4, "score_max": 3})
        self.assertIn("否决位 ≤4", adopted["rule_text"])
        self.assertIn("打分位 ≤3", adopted["rule_text"])
        self.assertIsNone(adopted["factor_cap"])

    def test_all_pans_expose_caps_key(self):
        for p in factor_board.pans():
            self.assertIn("caps", p)


if __name__ == "__main__":
    unittest.main()
