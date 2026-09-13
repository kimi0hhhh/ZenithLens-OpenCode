# -*- coding: utf-8 -*-
"""契约 v7 · 因子回测引擎测试（21-factor-governance / 09-api-contract §5.35~§5.37、§6.8）。

覆盖：防前视、六窗口径、baseline=max(恒涨,恒跌)、k_lift 悬崖边界、
候选提交流程、不可算→null、bootstrap、F1/F2/F3/盘位。
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import errors
import factor_engine as fe
from _fixtures import make_bars

WINDOWS = ["d15", "d30", "d60", "m6", "m24", "full"]


def mom5_defn():
    return {
        "name": "mom5 五日动量",
        "kind": "binary_signal", "orientation": "higher_bullish", "role_hint": "score",
        "horizon": 1, "inputs": ["mom5"],
        "expression": {"op": "gt", "args": [{"column": "mom5", "lag": 0}, 0.0]},
        "normalization": "none", "params": [],
    }


class K_LiftBoundaryTest(unittest.TestCase):
    def test_five_cliff_boundaries(self):
        self.assertEqual(fe.k_lift_of(None), 0.0)
        self.assertEqual(fe.k_lift_of(1.30), 1.0)
        self.assertEqual(fe.k_lift_of(1.29), 0.80)
        self.assertEqual(fe.k_lift_of(1.20), 0.80)
        self.assertEqual(fe.k_lift_of(1.19), 0.65)
        self.assertEqual(fe.k_lift_of(1.10), 0.65)
        self.assertEqual(fe.k_lift_of(1.09), 0.50)
        self.assertEqual(fe.k_lift_of(1.00), 0.50)
        self.assertEqual(fe.k_lift_of(0.99), -0.80)
        self.assertEqual(fe.k_lift_of(0.84), -0.80)
        self.assertEqual(fe.k_lift_of(0.83), -1.30)

    def test_cliff_labels(self):
        self.assertEqual(fe.cliff_of(None), None)
        self.assertEqual(fe.cliff_of(1.31), "≥1.30")
        self.assertEqual(fe.cliff_of(1.05), "≥1.00")
        self.assertEqual(fe.cliff_of(0.90), "<1.00")
        self.assertEqual(fe.cliff_of(0.50), "<0.84")


class LookaheadTest(unittest.TestCase):
    def test_negative_shift_rejected(self):
        d = mom5_defn()
        d["expression"] = {"op": "shift", "args": [{"column": "mom5", "lag": 0}, -1]}
        with self.assertRaises(errors.ApiError) as cm:
            fe.validate_definition(d)
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)
        self.assertIn("expression", cm.exception.detail)

    def test_negative_leaf_lag_rejected(self):
        d = mom5_defn()
        d["expression"] = {"op": "gt", "args": [{"column": "mom5", "lag": -2}, 0.0]}
        with self.assertRaises(errors.ApiError):
            fe.validate_definition(d)

    def test_undeclared_column_rejected(self):
        d = mom5_defn()
        d["inputs"] = ["vr"]
        d["expression"] = {"op": "gt", "args": [{"column": "mom5", "lag": 0}, 0.0]}
        with self.assertRaises(errors.ApiError) as cm:
            fe.validate_definition(d)
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_future_bars_do_not_change_past_signal(self):
        bars = make_bars(n=160, seed=3)
        d = mom5_defn()
        cols = fe._columns(bars)
        before_raw = [fe.eval_node(d["expression"], cols, t) for t in range(160)]
        before_fired = fe._generic_fired(d, bars)
        bars2 = [dict(b) for b in bars]
        for b in bars2[-40:]:
            for k in ("open", "high", "low", "close"):
                b[k] = b[k] * 1.5
            b["volume"] = b["volume"] * 3.0
        cols2 = fe._columns(bars2)
        after_fired = fe._generic_fired(d, bars2)
        for t in range(160 - 40):
            self.assertEqual(before_raw[t], fe.eval_node(d["expression"], cols2, t))
            self.assertEqual(before_fired[t], after_fired[t])

    def test_rolling_window_insufficient_history_is_null(self):
        bars = make_bars(n=80, seed=5)
        cols = fe._columns(bars)
        node = {"op": "rolling_mean", "args": [{"column": "close", "lag": 0}, 5]}
        self.assertIsNone(fe.eval_node(node, cols, 2))


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.assets = [("A", make_bars(200, seed=7)), ("B", make_bars(200, seed=11))]
        self.card = fe.evaluate(mom5_defn(), self.assets, do_bootstrap=False,
                                use_cache=False)

    def test_six_windows_in_order(self):
        self.assertEqual([w["window"] for w in self.card["windows"]], WINDOWS)
        for w in self.card["windows"]:
            self.assertEqual(w["weight"], fe.WINDOW_WEIGHTS[w["window"]])
            self.assertEqual(w["n_w"], fe.WINDOW_NW[w["window"]])
            self.assertEqual(w["k_lift"], fe.k_lift_of(w["lift"]))
            self.assertEqual(w["cliff_hit"], fe.cliff_of(w["lift"]))

    def test_score_is_chain_product(self):
        for w in self.card["windows"]:
            if w["lift"] is None:
                self.assertEqual(w["k_lift"], 0.0)
                self.assertEqual(w["admission"], 0.0)
                self.assertEqual(w["score"], 0.0)
            else:
                adm = fe.admission_of(w["independent_trigger_days"], w["n_w"])
                expect = w["k_lift"] * w["weight"] * adm
                self.assertAlmostEqual(w["score"], expect, places=4)

    def test_zero_when_uncomputable(self):
        d = mom5_defn()
        d["inputs"] = ["amount"]
        d["expression"] = {"op": "gt", "args": [{"column": "amount", "lag": 0}, 0.0]}
        card = fe.evaluate(d, self.assets, do_bootstrap=False, use_cache=False)
        self.assertIsNone(card["total_score"])
        for w in card["windows"]:
            self.assertIsNone(w["lift"])
            self.assertIsNone(w["hit_rate"])
            self.assertEqual(w["score"], 0.0)
            self.assertEqual(w["k_lift"], 0.0)
        self.assertEqual(card["verdict"], "insufficient_data")
        self.assertIsNone(card["pan"])


class BaselineTest(unittest.TestCase):
    def test_baseline_is_max_of_up_and_down(self):
        assets = [("A", make_bars(220, seed=9)), ("B", make_bars(220, seed=13))]
        d = mom5_defn()
        card = fe.evaluate(d, assets, do_bootstrap=False, use_cache=False)
        calendar = fe._union_calendar(assets)
        bounds, holdout_start = fe._window_bounds(calendar)
        fired = {aid: fe._generic_fired(d, bars) for aid, bars in assets}
        for w in card["windows"]:
            start, end = bounds[w["window"]]
            recs = fe._collect(assets, fired, set(calendar[start:end]), holdout_start, 1)
            universe = [(a, t, f) for (a, t, _fired, f) in recs if f is not None]
            ind = fe._independent([(a, t) for a, t, _f in universe], 1)
            um = {(a, t): f for a, t, f in universe}
            ups = sum(1 for (a, t) in ind if um[(a, t)] > 0)
            always_up = ups / float(len(ind)) if ind else None
            expect = None if always_up is None else max(always_up, 1.0 - always_up)
            self.assertEqual(w["baseline_rate"], fe._r4(expect))
            if w["baseline_rate"] is not None:
                self.assertGreaterEqual(w["baseline_rate"], 0.5)


class BootstrapTest(unittest.TestCase):
    def test_percentiles_and_percentile(self):
        assets = [("A", make_bars(220, seed=7)), ("B", make_bars(220, seed=17))]
        card = fe.evaluate(mom5_defn(), assets, do_bootstrap=True, use_cache=False)
        if card["total_score"] is None:
            self.skipTest("无可算窗口")
        p = card["bootstrap_percentiles"]
        self.assertIsNotNone(p)
        for k in ("p50", "p90", "p95", "p99", "p995"):
            self.assertIn(k, p)
        self.assertTrue(0.0 <= card["total_score_percentile"] <= 1.0)


class CandidateFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_fe_")
        self._saved = {}
        for attr in ("LEDGER_DIR", "CANDIDATES_PATH", "SCORECARDS_PATH",
                     "SCAN_HISTORY_PATH", "ARENA_PATH", "ADOPTED_PATH",
                     "SIGNALS_CACHE_PATH"):
            self._saved[attr] = getattr(fe, attr)
        fe.LEDGER_DIR = self.tmp
        fe.CANDIDATES_PATH = os.path.join(self.tmp, "factor_candidates.jsonl")
        fe.SCORECARDS_PATH = os.path.join(self.tmp, "scorecards.jsonl")
        fe.SCAN_HISTORY_PATH = os.path.join(self.tmp, "scan_history.jsonl")
        fe.ARENA_PATH = os.path.join(self.tmp, "factor_arena.jsonl")
        fe.ADOPTED_PATH = os.path.join(self.tmp, "adopted_factors.json")
        fe.SIGNALS_CACHE_PATH = os.path.join(self.tmp, "signals.json")
        self.assets = [("A", make_bars(200, seed=7)), ("B", make_bars(200, seed=21))]

    def tearDown(self):
        for attr, val in self._saved.items():
            setattr(fe, attr, val)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_submit_then_get(self):
        res = fe.submit_candidate(mom5_defn(), assets_bars=self.assets)
        for k in ("candidate_id", "factor_id", "definition_hash", "status",
                  "task_id", "submitted_at", "scorecard"):
            self.assertIn(k, res)
        self.assertTrue(res["candidate_id"].startswith("cand_"))
        card = res["scorecard"]
        for k in ("f1_validity", "f2_independence", "f3_increment", "verdict",
                  "license", "pan", "windows", "total_score"):
            self.assertIn(k, card)
        self.assertIn(card["verdict"], ("admitted_to_arena", "rejected_f1",
                                        "rejected_f2", "rejected_f3", "insufficient_data"))
        self.assertEqual(len(card["windows"]), 6)
        got = fe.get_scorecard(res["candidate_id"])
        self.assertEqual(got["candidate_id"], res["candidate_id"])
        self.assertEqual(got["status"], "done")
        no_win = fe.get_scorecard(res["candidate_id"], include_windows=False)
        self.assertIsNone(no_win["windows"])

    def test_duplicate_is_idempotent(self):
        r1 = fe.submit_candidate(mom5_defn(), assets_bars=self.assets)
        r2 = fe.submit_candidate(mom5_defn(), assets_bars=self.assets)
        self.assertTrue(r2.get("duplicate"))
        self.assertEqual(r1["candidate_id"], r2["candidate_id"])
        self.assertEqual(r1["definition_hash"], r2["definition_hash"])

    def test_invalid_definition_raises_validation(self):
        bad = mom5_defn()
        bad["inputs"] = ["nope"]
        bad["expression"] = {"op": "gt", "args": [{"column": "zzz", "lag": 0}, 0.0]}
        with self.assertRaises(errors.ApiError) as cm:
            fe.submit_candidate(bad, assets_bars=self.assets)
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_unknown_candidate_not_found(self):
        with self.assertRaises(errors.ApiError) as cm:
            fe.get_scorecard("cand_nope")
        self.assertEqual(cm.exception.code, errors.E_NOT_FOUND)

    def test_ledger_scan_and_arena_written(self):
        fe.submit_candidate(mom5_defn(), assets_bars=self.assets)
        self.assertTrue(os.path.isfile(fe.SCAN_HISTORY_PATH))
        self.assertTrue(os.path.isfile(fe.ARENA_PATH))
        with open(fe.SCAN_HISTORY_PATH, "r", encoding="utf-8") as f:
            self.assertIn("f1_result", f.read())


class BuiltinAdoptedTest(unittest.TestCase):
    def setUp(self):
        self.assets = [("A", make_bars(220, seed=7)), ("B", make_bars(220, seed=31))]
        self.tmp = tempfile.mkdtemp(prefix="zl_adopt_")
        self._sig = fe.SIGNALS_CACHE_PATH
        self._adp = fe.ADOPTED_PATH
        fe.SIGNALS_CACHE_PATH = os.path.join(self.tmp, "signals.json")
        fe.ADOPTED_PATH = os.path.join(self.tmp, "adopted.json")

    def tearDown(self):
        fe.SIGNALS_CACHE_PATH = self._sig
        fe.ADOPTED_PATH = self._adp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builtin_klow2_and_crowd_backtest(self):
        recs = fe.build_adopted_pan(assets_bars=self.assets, write=False, use_cache=True)
        ids = [r["factor_id"] for r in recs]
        self.assertIn("klow2", ids)
        self.assertIn("crowd6", ids)
        for r in recs:
            self.assertEqual(r["role"], "adopted")
            self.assertEqual(set(r["windows"].keys()), set(WINDOWS))
            for w in WINDOWS:
                self.assertIn("lift", r["windows"][w])
                self.assertIn("independent_trigger_days", r["windows"][w])


if __name__ == "__main__":
    unittest.main()
