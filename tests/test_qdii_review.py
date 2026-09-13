# -*- coding: utf-8 -*-
"""R2 契约测试 · QDII 首测门槛 / 复评 / 对齐误杀计数（09-r2 §9.3-G1；08-r2 §3.3；R-5）。

断言要点：
- 门槛：40 可配对日窗且 n_test≥20 才可判 `first_test_failed`；未达门槛挂档观察；
- 不达标 → 回退单段（暂态）+ 预注册 `next_review_date` + 结论带数字；
- 达标 → 双段保留；
- `alignment_conflict` 40 日窗 ≥5 次 → 追加人工复核事件。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import valuation


class QdiiReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_qr_")
        self._saved = (valuation.NAV_STORE_DIR, valuation.HISTORY_PATH,
                       valuation.QDII_CONFIG_PATH, valuation.QDII_REVIEW_PATH)
        valuation.NAV_STORE_DIR = os.path.join(self.tmp, "nav")
        valuation.HISTORY_PATH = os.path.join(self.tmp, "history.jsonl")
        valuation.QDII_CONFIG_PATH = os.path.join(self.tmp, "qdii_correction.json")
        valuation.QDII_REVIEW_PATH = os.path.join(self.tmp, "qdii_review.jsonl")
        os.makedirs(valuation.NAV_STORE_DIR)

    def tearDown(self):
        (valuation.NAV_STORE_DIR, valuation.HISTORY_PATH, valuation.QDII_CONFIG_PATH,
         valuation.QDII_REVIEW_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, code, n, dual_bias, single_bias=-0.02):
        """nav 序列 + n 条双段记录；real=0.01，dual=real+dual_bias，single=real+single_bias。"""
        dates = ["2026-%02d-%02d" % (1 + (i // 28), 1 + (i % 28)) for i in range(n + 1)]
        vals = [1.0]
        for _i in range(n):
            vals.append(vals[-1] * 1.01)
        path = os.path.join(valuation.NAV_STORE_DIR, "%s.json" % code)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump({"code": code, "updated_at": "2026-09-12T00:00:00+08:00",
                       "points": [{"date": d, "nav": v}
                                  for d, v in zip(dates, vals)]}, f)
        with io.open(valuation.HISTORY_PATH, "a", encoding="utf-8") as f:
            for i in range(1, n + 1):
                real = 0.01
                rec = {
                    "date": dates[i], "code": code, "name": code,
                    "valuation_mode": "proxy", "change_rate": real + dual_bias,
                    "written_at": "%sT15:30:00+08:00" % dates[i],
                    "qdii_correction": {"applied": True, "method": "etf_close_plus_overnight",
                                        "domestic": {"value": real + single_bias,
                                                     "as_of": dates[i - 1]},
                                        "overseas": {"value": 0.0, "ref_code": "x",
                                                     "trade_date": dates[i],
                                                     "source": "tencent_us_ndx"},
                                        "fallback_reason": None, "note": ""},
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def test_hold_below_threshold(self):
        self._seed("021662", 5, dual_bias=0.0)
        out = valuation.evaluate_qdii_review(
            [{"code": "021662", "proxy_code": "159920"}])
        self.assertEqual(out["decisions"][0]["verdict"], "hold")
        rows = valuation._read_qdii_review()
        self.assertEqual(rows[0]["kind"], "qdii_review")
        self.assertEqual(rows[0]["verdict"], "hold")
        cfg = valuation.load_qdii_config()
        self.assertTrue(cfg["enabled"])  # 未达门槛不得宣布首测失败

    def test_first_test_failed_transient(self):
        self._seed("457001", 20, dual_bias=0.02)
        out = valuation.evaluate_qdii_review(
            [{"code": "457001", "proxy_code": "159920"}])
        self.assertEqual(out["decisions"][0]["verdict"], "first_test_failed")
        cfg = valuation.load_qdii_config()
        self.assertFalse(cfg["enabled"])
        self.assertIsNotNone(cfg["next_review_date"])
        self.assertIn("0.0", cfg["reason"])  # 结论带数字
        row = [r for r in valuation._read_qdii_review()
               if r.get("kind") == "qdii_review"][-1]
        self.assertAlmostEqual(row["dual_mae"], 0.02, places=4)
        self.assertIsNotNone(row["single_mae"])
        self.assertEqual(row["target_mae"], 0.01)

    def test_pass_keeps_dual(self):
        self._seed("024239", 20, dual_bias=0.0)
        out = valuation.evaluate_qdii_review(
            [{"code": "024239", "proxy_code": "513100"}])
        self.assertEqual(out["decisions"][0]["verdict"], "pass")
        cfg = valuation.load_qdii_config()
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["next_review_date"] is not None, True)

    def test_alignment_conflict_review_threshold(self):
        for i in range(5):
            valuation.append_qdii_review({"kind": "alignment_conflict", "code": "457001",
                                          "domestic_date": "2026-09-%02d" % (1 + i),
                                          "overseas_trade_date": "2026-09-%02d" % i})
        valuation.evaluate_qdii_review([])
        rows = valuation._read_qdii_review()
        reviews = [r for r in rows if r.get("kind") == "alignment_conflict_review"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["count"], 5)


if __name__ == "__main__":
    unittest.main()
