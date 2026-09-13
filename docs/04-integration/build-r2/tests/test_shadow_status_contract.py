# -*- coding: utf-8 -*-
"""影子盘状态语义测试（task OC-SHADOWSTAT-BE / v9.5 窗口 60）。

背景：`app.py` 的 `/api/v1/engine/status` 曾用 `shadow_audit()["status"]`（偏差评估：
窗口内无 "涨" 信号 → `idle`）当作 `shadow_status`，导致台账已记多日仍显示
「未启动」。修复后 `shadow_status` 取 `shadow_progress()["status"]`（进度语义
`not_started/recording/qualified/gap`），偏差评估独立为 `shadow_audit_status`。

v9.5 §13：主文件滚动窗 20→60；满 60 交易日窗后 `qualified` 可达
（记录为走前回算口径、非自然积累——`note` 必须带披露）。

断言：有台账→进度语义、无台账→not_started、audit 与 progress 分离、满窗→qualified。
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import ledger_api

# v9.5 真实窗口：2026-06-22(一) ~ 2026-09-11(五) 共 60 个交易日（60 交易日窗）。
REAL_DATES = ["2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26",
              "2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03",
              "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10",
              "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17",
              "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
              "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
              "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07",
              "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
              "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21",
              "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
              "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
              "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]


def _weekdays(start="2026-06-22", n=60):
    """从 start 起取 n 个连续工作日（与真实窗口同构，不依赖官方交易日历）。"""
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


class ShadowStatusSemanticsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_shadowstat_")
        self._dir = ledger_api.LEDGER_DIR
        self._sig = ledger_api.SIGNALS_PATH
        self._back = ledger_api.BACKFILL_PATH
        self._arch = (ledger_api.ARCHIVE_DIR, ledger_api.ARCHIVE_SIGNALS_PATH,
                      ledger_api.ARCHIVE_MANIFEST_PATH)
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        # 读隔离：进度/审查的合并集不得引入真实 ledger/archive（BLOCK-2 审计项）
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

    def _seed(self, dates, signal="gray"):
        for d in dates:
            ledger_api.write_entry({
                "date": d, "code": "000001", "gate": "none", "p_up": None,
                "ddsm_state": [1, 2, 3], "veto_crowd": False, "veto_klow2": False,
                "signal": signal, "market_value": 1000.0, "cost_est": 900.0,
            })

    def _engine_status(self):
        """离线调用 h_engine_status：绕开联网模型（返回空模型）。"""
        state = {"present": False, "fresh": False, "as_of": None}
        with mock.patch.object(app, "_global_model", return_value=(None, [], [])), \
                mock.patch.object(app.fund_predict, "resolve_state", return_value=state):
            return app.h_engine_status({}, None, {})

    # --- 满 60 交易日窗 → qualified（v9.5 §13.3 可达） ---
    def test_with_ledger_shadow_status_qualified_at_60(self):
        self._seed(REAL_DATES)
        data = self._engine_status()
        self.assertEqual(data["shadow_status"], "qualified")
        self.assertEqual(data["shadow_consecutive_days"], 60)
        self.assertEqual(data["shadow_target_days"], 60)
        p = ledger_api.shadow_progress()
        self.assertEqual(p["window_days"], 60)
        self.assertIn("走前口径", p["note"])     # 诚实披露：非自然积累

    # --- 无台账 → not_started ---
    def test_without_ledger_shadow_status_not_started(self):
        data = self._engine_status()
        self.assertEqual(data["shadow_status"], "not_started")
        self.assertEqual(data["shadow_consecutive_days"], 0)
        self.assertEqual(data["shadow_target_days"], 60)

    # --- audit 与 progress 分离：无 "涨" 信号时进度=qualified、audit=idle ---
    def test_audit_and_progress_are_separated(self):
        self._seed(REAL_DATES, signal="gray")
        progress = ledger_api.shadow_progress()
        audit = ledger_api.shadow_audit()
        self.assertEqual(progress["status"], "qualified")   # 满 60 日窗
        self.assertEqual(audit["status"], "idle")           # 无 up 信号可评估偏差

        data = self._engine_status()
        self.assertEqual(data["shadow_status"], progress["status"])
        self.assertEqual(data["shadow_audit_status"], audit["status"])
        self.assertIn(data["shadow_audit_status"], ("idle", "ok", "bad"))

    # --- 有 "涨" 信号并回填命中时 audit 可评估（ok/bad），仍不影响 shadow_status ---
    def test_audit_status_reports_when_evaluable(self):
        self._seed(REAL_DATES, signal="up")
        # 前 36 日 t1 上涨、后 24 日下跌 → hit_rate=0.6；实测基线 0.6 → 偏差 0pp → ok
        ledger_api.write_backfill([
            {"date": d, "code": "000001", "t1_real": (0.01 if i < 36 else -0.01)}
            for i, d in enumerate(REAL_DATES)
        ])
        audit = ledger_api.shadow_audit()
        self.assertEqual(audit["status"], "ok")
        data = self._engine_status()
        self.assertEqual(data["shadow_status"], "qualified")
        self.assertEqual(data["shadow_audit_status"], "ok")


if __name__ == "__main__":
    unittest.main()

