# -*- coding: utf-8 -*-
"""R2 契约测试 · QDII 双段校正（09-r2 §3.4；08-r2 §3.3；v9.1/R-5）。

断言要点：
- 加法拼接：change_rate = domestic + overseas（applied=true 时 fallback_reason 恒 null）；
- 隔夜源不可得 → 单段 + `overseas_unavailable`（overseas null）；
- 时间对齐失败 → 单段 + `alignment_conflict`（overseas 保留）并落 qdii_review 事件；
- 代理 bar 不足 → 不产出校正（qdii_correction=null）；
- 首测不达标回退（first_test_failed）为暂态且带数字。
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

import valuation

BARS = [
    {"date": "2026-09-10", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
     "volume": 1.0},
    {"date": "2026-09-11", "open": 1.0, "high": 1.02, "low": 1.0, "close": 1.02,
     "volume": 1.0},
]


def _ovs(value=0.03, trade_date="2026-09-12", close_ts="2026-09-12 04:00:00"):
    return {"value": value, "ref_code": "usNDX", "ref_name": "纳斯达克100",
            "trade_date": trade_date, "close_ts": close_ts,
            "source": "tencent_us_ndx"}


class QdiiCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_qdii_")
        self._saved = (valuation.QDII_CONFIG_PATH, valuation.QDII_REVIEW_PATH)
        valuation.QDII_CONFIG_PATH = os.path.join(self.tmp, "qdii_correction.json")
        valuation.QDII_REVIEW_PATH = os.path.join(self.tmp, "qdii_review.jsonl")
        self.h = {"code": "024239", "name": "全球科技先锋(QDII)", "proxy_code": "513100",
                  "fund_type": "qdii"}

    def tearDown(self):
        valuation.QDII_CONFIG_PATH, valuation.QDII_REVIEW_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _estimate(self, ovs, bars=None):
        with mock.patch.object(valuation.estimator, "get_bars",
                               return_value=(bars if bars is not None else BARS, {})), \
                mock.patch.object(valuation.estimator, "overseas_ref_quote",
                                  return_value=ovs):
            return valuation.qdii_estimate(self.h, "2026-09-11", session="closed")

    def test_additive_concat_and_applied(self):
        ch, corr = self._estimate(_ovs())
        self.assertAlmostEqual(ch, 0.02 + 0.03, places=6)
        self.assertTrue(corr["applied"])
        self.assertIsNone(corr["fallback_reason"])
        self.assertEqual(corr["method"], "etf_close_plus_overnight")
        self.assertAlmostEqual(corr["domestic"]["value"], 0.02, places=4)
        self.assertEqual(corr["domestic"]["as_of"], "2026-09-11")
        self.assertAlmostEqual(corr["overseas"]["value"], 0.03, places=4)
        self.assertEqual(corr["overseas"]["ref_code"], "usNDX")
        self.assertIn("不构成投资建议", corr["note"])

    def test_overseas_unavailable_falls_back_single(self):
        ch, corr = self._estimate(None)
        self.assertAlmostEqual(ch, 0.02, places=6)
        self.assertFalse(corr["applied"])
        self.assertEqual(corr["fallback_reason"], "overseas_unavailable")
        self.assertIsNone(corr["overseas"])
        self.assertIn("单段", corr["note"])

    def test_alignment_conflict_logs_event(self):
        ch, corr = self._estimate(_ovs(trade_date="2026-09-10"))
        self.assertAlmostEqual(ch, 0.02, places=6)
        self.assertFalse(corr["applied"])
        self.assertEqual(corr["fallback_reason"], "alignment_conflict")
        self.assertIsNotNone(corr["overseas"])
        rows = valuation._read_qdii_review()
        kinds = [r.get("kind") for r in rows]
        self.assertIn("alignment_conflict", kinds)
        self.assertEqual(rows[0]["domestic_date"], "2026-09-11")
        self.assertEqual(rows[0]["overseas_trade_date"], "2026-09-10")

    def test_same_day_time_check(self):
        ch, corr = self._estimate(_ovs(trade_date="2026-09-11",
                                       close_ts="2026-09-11 16:00:00"))
        self.assertTrue(corr["applied"])
        ch2, corr2 = self._estimate(_ovs(trade_date="2026-09-11",
                                         close_ts="2026-09-11 14:00:00"))
        self.assertFalse(corr2["applied"])
        self.assertEqual(corr2["fallback_reason"], "alignment_conflict")

    def test_bars_insufficient_returns_null_correction(self):
        ch, corr = self._estimate(_ovs(), bars=[BARS[0]])
        self.assertIsNone(ch)
        self.assertIsNone(corr)

    def test_first_test_failed_is_transient_with_numbers(self):
        with io.open(valuation.QDII_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"enabled": False, "reason": "首测不达标",
                       "last_review": {"single_mae": 0.018, "target_mae": 0.015,
                                       "gap_pp": 0.4, "n_matched_days": 22}}, f)
        ch, corr = self._estimate(_ovs())
        self.assertAlmostEqual(ch, 0.02, places=6)
        self.assertFalse(corr["applied"])
        self.assertEqual(corr["fallback_reason"], "first_test_failed")
        self.assertIn("0.018", corr["note"])
        self.assertIn("复评", corr["note"])

    def test_market_of_enum(self):
        self.assertEqual(valuation.market_of(self.h), "US_NDX")
        self.assertEqual(valuation.market_of({"code": "457001", "proxy_code": "159920"}),
                         "HK_HSI")
        self.assertIsNone(valuation.market_of({"code": "163208", "proxy_code": "162411"}))
        self.assertIsNone(valuation.market_of({"code": "000217", "proxy_code": "518880"}))


class PredictionQdiiLeadNoteTest(unittest.TestCase):
    """contract §3.7：PredictionSummary.qdii_lead_note 仅 QDII 行非 null。"""

    def test_prediction_summary_lead_note(self):
        import app
        import holdings
        h = {"code": "024239", "fund_type": "qdii", "proxy_code": "513100",
             "name": "全球科技先锋混合(QDII)C"}
        out = app._prediction_public({"code": "024239"}, {"024239": h}, "2026-09-12")
        self.assertEqual(out["qdii_lead_note"], holdings.QDII_LEAD_NOTE)
        h2 = {"code": "000217", "fund_type": "index_link", "proxy_code": "518880",
              "name": "华安黄金ETF联接C"}
        out2 = app._prediction_public({"code": "000217"}, {"000217": h2}, "2026-09-12")
        self.assertIsNone(out2["qdii_lead_note"])


if __name__ == "__main__":
    unittest.main()
