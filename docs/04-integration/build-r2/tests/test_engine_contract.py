# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 引擎核（08 §4 / 09 §5.14/§5.25 / Brief §5.1）。

红-绿：本文件先在 round1 代码上跑红（缺 v4 字段），实现后再跑绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine
from tests._fixtures import make_bars


class GateTest(unittest.TestCase):
    def test_e1_gap_up(self):
        bars = make_bars(40)
        bars[-1]["low"] = bars[-2]["high"] * 1.001
        self.assertEqual(engine.gate_of(bars, len(bars) - 1), "E1")

    def test_e3_volume_dry_drop(self):
        bars = make_bars(40)
        bars[-1]["close"] = bars[-2]["close"] * 0.95
        bars[-1]["low"] = min(bars[-1]["open"], bars[-1]["close"]) * 0.999
        bars[-1]["volume"] = 1.0
        self.assertEqual(engine.gate_of(bars, len(bars) - 1), "E3")

    def test_no_or_merge_e2_e4_absent(self):
        self.assertNotIn("E2", engine.GATE_LABEL or {})
        self.assertNotIn("E4", engine.GATE_LABEL or {})


class DdsmTest(unittest.TestCase):
    def test_frozen_params(self):
        self.assertEqual(engine.K_NOISE, 4)
        self.assertEqual(engine.P_PERTURB, 0.25)
        self.assertEqual(engine.MIN_N, 15)
        self.assertEqual(engine.SHRINK, 10)
        self.assertEqual(round(engine.EXIT_THRESHOLD, 4), 0.52)

    def test_model_cells_in_range(self):
        model = engine.train_model(make_bars(), H=1)
        self.assertIsNotNone(model)
        f = engine.features_at(make_bars(), 179)
        cell = engine.cell_of(model, f)
        self.assertEqual(len(cell), 3)
        for k in cell:
            self.assertIn(k, (0, 1, 2, 3, 4))
        p = engine.ddsm_p(model, cell)
        self.assertTrue(0.0 <= p <= 1.0)

    def test_naive_p_raw_frequency_no_min_n_gate(self):
        # v5 SHOULD-5：0<naive_n<MIN_N 的格仍给原始频率，不再被 MIN_N 门控
        model = engine.train_model(make_bars(), H=1)
        low = [(c, r) for c, r in model["naive"].items() if 0 < r[0] < engine.MIN_N]
        self.assertTrue(low)
        for cell, r in low:
            p = engine.naive_p(model, cell)
            self.assertIsNotNone(p)
            self.assertAlmostEqual(p, r[1] / float(r[0]), places=6)

    def test_naive_p_null_when_no_sample(self):
        model = engine.train_model(make_bars(), H=1)
        empty = None
        for r2 in range(5):
            for om in range(5):
                for vr in range(5):
                    if (r2, om, vr) not in model["naive"]:
                        empty = (r2, om, vr)
                        break
                if empty:
                    break
            if empty:
                break
        self.assertIsNotNone(empty)
        self.assertIsNone(engine.naive_p(model, empty))


class VetoTest(unittest.TestCase):
    def test_crowd_missing_when_dim_none(self):
        model = engine.train_model(make_bars(), H=1)
        f = engine.features_at(make_bars(), 179)
        f["volat"] = None
        comp, status = engine.crowd_composite(model, f)
        self.assertIsNone(comp)
        self.assertEqual(status, "missing")

    def test_veto_missing_forces_abstain(self):
        bars = make_bars()
        model = engine.train_model(bars, H=1)
        model = dict(model)
        model["klow_q40"] = None
        bars[-1]["low"] = bars[-2]["high"] * 1.001  # 确保门触发
        r = engine.predict_at(model, bars, len(bars) - 1, 1)
        self.assertEqual(r["signal"], "abstain")
        self.assertEqual(r["reason"], "veto_data_missing")

    def test_signal_never_down(self):
        bars = make_bars()
        model = engine.train_model(bars, H=1)
        for t in range(engine.FEATURE_WARMUP, len(bars)):
            r = engine.predict_at(model, bars, t, 1)
            self.assertIn(r["signal"], ("up", "gray", "abstain"))


class FrozenParamsV4Test(unittest.TestCase):
    def test_weighting_basis_frozen(self):
        fp = engine.frozen_params()
        self.assertEqual(fp.get("weighting_basis"), "market_value")
        self.assertEqual(fp["min_coverage_ratio"], 0.30)
        self.assertEqual(fp["min_open_count"], 3)


class FrozenParamsV5Test(unittest.TestCase):
    """SHOULD-1：三个 array[object] 元素键名冻结（键集合恒等，多余/缺失即 FAIL）。"""

    def test_window_weights_key_set(self):
        fp = engine.frozen_params()
        self.assertEqual(len(fp["window_weights"]), 6)
        for e in fp["window_weights"]:
            self.assertEqual(set(e.keys()), {"window", "weight"})
            self.assertIn(e["window"], ("d15", "d30", "d60", "m6", "m24", "full"))

    def test_window_min_days_key_set(self):
        fp = engine.frozen_params()
        self.assertEqual(len(fp["window_min_days"]), 6)
        for e in fp["window_min_days"]:
            self.assertEqual(set(e.keys()), {"window", "n_w"})
            self.assertIn(e["window"], ("d15", "d30", "d60", "m6", "m24", "full"))

    def test_license_lines_key_set(self):
        fp = engine.frozen_params()
        self.assertEqual(len(fp["license_lines"]), 4)
        for e in fp["license_lines"]:
            self.assertEqual(set(e.keys()),
                             {"license", "min_independent_days", "window_k"})
            self.assertIn(e["license"],
                          ("none", "candidate", "probation", "renew_t2", "full_t3"))
        cand = [e for e in fp["license_lines"] if e["license"] == "candidate"][0]
        self.assertIsNone(cand["window_k"])  # candidate 无 k 线要求 → null


class CubeV4Test(unittest.TestCase):
    def setUp(self):
        self.bars = make_bars()
        self.cube = engine.build_cube("512100", "中证1000ETF", self.bars, H=1,
                                      train_as_of=self.bars[-1]["date"],
                                      snapshot_at="2026-09-12T15:00:00+08:00")

    def test_dual_layer_labels(self):
        self.assertIsNotNone(self.cube)
        self.assertEqual(self.cube["production_layer"], "ddsm")
        self.assertEqual(self.cube["research_layer"], "naive")
        self.assertEqual(self.cube["default_layer"], "ddsm")
        self.assertTrue(self.cube["dual_view_note"])

    def test_five_layers_25_cells(self):
        self.assertEqual(len(self.cube["layers"]), 5)
        for layer in self.cube["layers"]:
            self.assertEqual(len(layer["cells"]), 25)

    def test_empty_cell_explicit_null_both_p(self):
        empties = [c for layer in self.cube["layers"] for c in layer["cells"]
                   if c["status"] == "empty"]
        self.assertTrue(empties)
        for c in empties:
            self.assertIsNone(c["naive_p"])
            self.assertIsNone(c["ddsm_p"])
            self.assertTrue(c["is_empty"])


class CubeV5Test(unittest.TestCase):
    """SHOULD-5：naive_p 研究口径原始频率 + naive_low_sample + status 判定式。"""

    def setUp(self):
        self.bars = make_bars()
        self.cube = engine.build_cube("512100", "中证1000ETF", self.bars, H=1,
                                      train_as_of=self.bars[-1]["date"],
                                      snapshot_at="2026-09-12T15:00:00+08:00")

    def test_status_iff_naive_n(self):
        for layer in self.cube["layers"]:
            for c in layer["cells"]:
                if c["naive_n"] > 0:
                    self.assertEqual(c["status"], "filled")
                else:
                    self.assertEqual(c["status"], "empty")

    def test_low_sample_naive_p_given_and_flagged(self):
        cells = [c for layer in self.cube["layers"] for c in layer["cells"]
                 if 0 < c["naive_n"] < engine.MIN_N]
        self.assertTrue(cells)
        for c in cells:
            self.assertIsNotNone(c["naive_p"])
            self.assertTrue(c["naive_low_sample"])
            self.assertEqual(c["status"], "filled")

    def test_empty_cell_low_sample_true_both_p_null(self):
        empties = [c for layer in self.cube["layers"] for c in layer["cells"]
                   if c["naive_n"] == 0]
        self.assertTrue(empties)
        for c in empties:
            self.assertTrue(c["naive_low_sample"])
            self.assertIsNone(c["naive_p"])
            self.assertIsNone(c["ddsm_p"])
            self.assertEqual(c["color_band"], "no_sample")


if __name__ == "__main__":
    unittest.main()
