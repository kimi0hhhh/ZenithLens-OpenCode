# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 因子竞技场（09 §5.24 / §6.11.9 · A-09）。"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import factor_board

WINDOWS = ["d15", "d30", "d60", "m6", "m24", "full"]


class ArenaLegendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_arena_")
        self._dir = factor_board.LEDGER_DIR
        factor_board.LEDGER_DIR = self.tmp

    def tearDown(self):
        factor_board.LEDGER_DIR = self._dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_matrix_v4_fields(self):
        data = factor_board.arena()
        self.assertEqual(data["color_scheme"], "performance_rank")
        self.assertEqual(data["color_token_prefix"], "--arena-")
        self.assertEqual(data["rows"], [])

    def test_colors_disjoint_from_price_scheme(self):
        recs = []
        for kind, name, base in (("naive_baseline", "裸算法", 0.0),
                                 ("production", "生产", 1.0),
                                 ("leave_one_out", "留一 C-e1", -0.5)):
            for w in WINDOWS:
                recs.append({"config_id": kind, "config_name": name,
                             "config_kind": kind, "window": w,
                             "open_count": 10, "hit_rate": 0.6,
                             "paired_delta_pp": base})
        with io.open(os.path.join(self.tmp, "factor_arena.jsonl"), "w",
                     encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        data = factor_board.arena()
        self.assertEqual(data["color_scheme"], "performance_rank")
        allowed = {"red", "green", "blue", "yellow", "base"}
        for row in data["rows"]:
            for cell in row["cells"]:
                self.assertIn(cell["color"], allowed)
        # 裸算法行不着红绿
        base_row = [r for r in data["rows"] if r["config_kind"] == "naive_baseline"][0]
        for cell in base_row["cells"]:
            self.assertEqual(cell["color"], "base")


class BootstrapMeasuredTest(unittest.TestCase):
    """F-1（后端侧）：measured 实测分位可用、与常量兄弟并存（V11 / 09 §4.9）。"""

    def test_score_chain_exposes_measured_sibling(self):
        import factor_engine
        fake = {"p50": -12.4, "p90": 1.0, "p95": 2.0, "p99": 3.0, "p995": 4.0}
        orig = factor_engine.measured_bootstrap
        factor_engine.measured_bootstrap = lambda: fake
        try:
            data = factor_board.score_chain()
        finally:
            factor_engine.measured_bootstrap = orig
        self.assertEqual(data["bootstrap_percentiles_measured"], fake)
        self.assertTrue(data["real_engine"])
        # 常量兄弟字段保留（删除常量须版本 +1）
        self.assertIn("p50", data["bootstrap_percentiles"])

    def test_measured_null_when_unavailable(self):
        import factor_engine
        orig = factor_engine.measured_bootstrap
        factor_engine.measured_bootstrap = lambda: None
        try:
            data = factor_board.score_chain()
        finally:
            factor_engine.measured_bootstrap = orig
        self.assertIsNone(data["bootstrap_percentiles_measured"])


class ScoreDetailJudgesTest(unittest.TestCase):
    """F-3（后端侧）：judges.value 不再恒空——可从 adopted 记录导出的填实测值。"""

    def test_judge_values_filled(self):
        fake = {"factor_id": "klow2", "name": "KLOW2 下影线否决",
                "total_score": 61.05, "delta_pp": 0.012,
                "windows": {"full": {"admission": 0.55, "lift": 1.07}}}
        orig = factor_board._read_records
        factor_board._read_records = lambda name: [fake]
        try:
            data = factor_board.score_detail("klow2")
        finally:
            factor_board._read_records = orig
        judges = {j["judge"]: j["value"] for j in data["judges"]}
        self.assertEqual(judges["lift"], 61.05)
        self.assertEqual(judges["admission"], 0.55)
        self.assertEqual(judges["backtest"], 0.012)
        self.assertIsNone(judges["t"])   # adopted 记录未存 t 值 → 前端按「待接入」


if __name__ == "__main__":
    unittest.main()
