# -*- coding: utf-8 -*-
"""R2 契约测试 · /review/scores 真实化（09-r2 §4.2 / §10 v9.2；R2-11；BLOCK-1 修复）。

断言要点：
- R2 接通范围 = T1（H=1 全链）；T3/T15 一律 pending + null + open_count=0（B1-1）；
- 非 pending 行 `formula` 来自计算定义（可注入变体判别；B1-2）；
- `baseline_status ∈ {filled, pending}`，`"ok"` 零出现（B1-3）；
- 响应 note 含 pending_cv / 待验证（B1-4）；缓存重生成后一致（B1-5）；
- hero 与 T1 行值/状态双一致（B1-6）；缓存可重建；shadow_live 同口径。
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

import errors
import factor_engine
import ledger_api
import review

VARIANT_FORMULA = "gate+ddsm+veto+test_variant"


def _fake_card():
    return {
        "windows": [{"window": "full", "hit_rate": 0.6, "open_count": 7,
                     "baseline_rate": 0.58, "delta_pp": 0.02,
                     "independent_trigger_days": 33}],
        "cv_mode": "walk_forward", "purge_gap": "H+2", "holdout_days": 60,
        "sample_period": "2025-01-01..2026-06-01",
    }


class ReviewScoresTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_scores_")
        self._saved = (review.CACHE_PATH, ledger_api.LEDGER_DIR,
                       ledger_api.SIGNALS_PATH, ledger_api.BACKFILL_PATH,
                       ledger_api.ARCHIVE_DIR, ledger_api.ARCHIVE_SIGNALS_PATH,
                       ledger_api.ARCHIVE_MANIFEST_PATH)
        review.CACHE_PATH = os.path.join(self.tmp, "review_scores.json")
        ledger_api.LEDGER_DIR = self.tmp
        ledger_api.SIGNALS_PATH = os.path.join(self.tmp, "shadow_signals.jsonl")
        ledger_api.BACKFILL_PATH = os.path.join(self.tmp, "backfill.jsonl")
        ledger_api.ARCHIVE_DIR = os.path.join(self.tmp, "archive")
        ledger_api.ARCHIVE_SIGNALS_PATH = os.path.join(
            self.tmp, "archive", "shadow_signals_archive.jsonl")
        ledger_api.ARCHIVE_MANIFEST_PATH = os.path.join(
            self.tmp, "archive", "_manifest.jsonl")

    def tearDown(self):
        (review.CACHE_PATH, ledger_api.LEDGER_DIR, ledger_api.SIGNALS_PATH,
         ledger_api.BACKFILL_PATH, ledger_api.ARCHIVE_DIR,
         ledger_api.ARCHIVE_SIGNALS_PATH,
         ledger_api.ARCHIVE_MANIFEST_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, formula="gate+ddsm+veto"):
        defn = {"factor_id": "production", "name": "生产配置", "formula": formula,
                "kind": "binary_signal", "orientation": "higher_bullish",
                "role_hint": "score", "horizon": 1,
                "inputs": ["open", "high", "low", "close", "volume"],
                "normalization": "none", "params": [], "_builtin": "production"}
        with mock.patch.object(factor_engine, "production_definition",
                               return_value=dict(defn)), \
                mock.patch.object(factor_engine, "evaluate",
                                  return_value=_fake_card()):
            return review.build_review_scores(
                assets_bars=[("x", [{"date": "2026-01-01"}])])

    def test_t1_filled_and_t3_t15_pending(self):
        payload = self._build()
        self.assertTrue(os.path.isfile(review.CACHE_PATH))
        self.assertEqual(len(payload["scores"]), 3)
        t1, t3, t15 = payload["scores"]
        # B1-1：T1 出数
        self.assertEqual(t1["window"], "T1")
        self.assertEqual(t1["baseline_status"], "filled")
        self.assertIsNotNone(t1["hit_rate"])
        self.assertEqual(t1["open_count"], 7)
        # B1-1/B1-5：T3/T15 待填充（null + open_count=0）
        for row in (t3, t15):
            self.assertEqual(row["baseline_status"], "pending")
            self.assertIsNone(row["hit_rate"])
            self.assertIsNone(row["baseline_rate"])
            self.assertIsNone(row["delta_pp"])
            self.assertEqual(row["open_count"], 0)
            self.assertEqual(row["data_kind"], "backtest")
            self.assertEqual(row["sample_window"], "full")
        # formula 标签保留各自定式（v9.2）
        self.assertEqual(t3["formula"], "gate_only")
        self.assertEqual(t15["formula"], "gate+ddsm")

    def test_formula_binds_to_computing_definition(self):
        # B1-2：注入变体定义 → T1 行 formula 必须随定义变化（不是固定映射）
        payload = self._build(formula=VARIANT_FORMULA)
        self.assertEqual(payload["scores"][0]["formula"], VARIANT_FORMULA)
        # 默认定义
        payload2 = self._build()
        self.assertEqual(payload2["scores"][0]["formula"], "gate+ddsm+veto")

    def test_baseline_status_enum_no_ok(self):
        # B1-3：枚举 {filled, pending}；"ok" 零出现
        for payload in (self._build(), review.scores("backtest"),
                        review.scores("shadow_live")):
            raw = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn('"baseline_status": "ok"', raw)
            for row in payload["scores"]:
                self.assertIn(row["baseline_status"], ("filled", "pending"))

    def test_note_mentions_pending_cv_and_transition(self):
        # B1-4：note 含「pending_cv」「待验证」
        payload = self._build()
        self.assertIn("pending_cv", payload["note"])
        self.assertIn("待验证", payload["note"])
        resp = review.scores("shadow_live")
        self.assertIn("pending_cv", resp["note"])

    def test_hero_consistent_with_t1(self):
        # B1-6：hero 与 T1 行值/状态双一致
        payload = self._build()
        t1, hero = payload["scores"][0], payload["hero"]
        self.assertEqual(hero["window"], "T1")
        for k in ("hit_rate", "baseline_rate", "delta_pp", "open_count",
                  "sample_period", "data_kind"):
            self.assertEqual(hero[k], t1[k], k)
        self.assertEqual(hero["data_kind"], "backtest")
        # 无缓存时 hero 走 pending 文案（不填估计值）
        os.remove(review.CACHE_PATH)
        resp = review.scores("backtest")
        self.assertIsNone(resp["hero"]["hit_rate"])
        self.assertIsNone(resp["scores"][0]["baseline_rate"])
        self.assertIn("不填估计值", resp["hero"]["label"])

    def test_cache_rebuildable_and_consistent(self):
        first = self._build()
        self.assertEqual(review.scores("backtest")["scores"][0]["hit_rate"],
                         first["scores"][0]["hit_rate"])
        os.remove(review.CACHE_PATH)
        self.assertEqual(review.scores("backtest")["scores"][0]["baseline_status"],
                         "pending")
        second = self._build()
        self.assertEqual(len(second["scores"]), 3)
        # 缓存内 T3/T15 同为 pending（B1-5）
        with io.open(review.CACHE_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        self.assertEqual([r["baseline_status"] for r in cached["scores"][1:]],
                         ["pending", "pending"])

    def test_cache_fresh_for_startup_reuse(self):
        # S3：warmup 复用时判断缓存是否当日生成（run_backtest 不受此影响）
        self.assertFalse(review.cache_fresh())
        self._build()
        self.assertTrue(review.cache_fresh())
        self.assertTrue(review.cache_fresh(as_of=review._today()))
        self.assertFalse(review.cache_fresh(as_of="2000-01-01"))

    def test_invalid_kind(self):
        with self.assertRaises(errors.ApiError) as cm:
            review.scores("paper")
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_shadow_live_t1_filled_t3_t15_pending(self):
        ledger_api.write_entry({"date": "2026-09-01", "code": "000001", "gate": "E1",
                                "p_up": 0.66, "ddsm_state": [1, 2, 3],
                                "veto_crowd": False, "veto_klow2": False,
                                "signal": "up", "market_value": 1.0, "cost_est": 1.0})
        ledger_api.write_backfill([{"date": "2026-09-01", "code": "000001",
                                    "t1_real": 0.01, "t3_real": -0.02,
                                    "method": "proxy_bar", "proxy_code": "512480"}])
        resp = review.scores("shadow_live")
        t1, t3, t15 = resp["scores"]
        self.assertEqual(t1["baseline_status"], "filled")
        self.assertEqual(t1["hit_rate"], 1.0)
        self.assertEqual(t1["baseline_rate"], 1.0)      # 实测 max(恒涨,恒跌)
        self.assertIsNotNone(t1["sample_period"])
        # 即便 t3_real 已回填，T3/T15 仍待填充（v9.2：接通范围 = T1）
        for row in (t3, t15):
            self.assertEqual(row["baseline_status"], "pending")
            self.assertIsNone(row["hit_rate"])
            self.assertEqual(row["open_count"], 0)


if __name__ == "__main__":
    unittest.main()
