# -*- coding: utf-8 -*-
"""R2 契约测试 · C→B 验证 / 9 只复核三层判定（10-r2 §2.4；08-r2 §4.1/§4.4；D-4）。

断言要点：
- `review_verdict` 三种 verdict：低样本挂档 / 达标 pass / 不达标 downgrade；
- 挂档复查日 = 自证据就绪日 +30 交易日；降档 `tier_reason` 回填；升 B 入 universe；
- 挂档行不计入已验证/预测覆盖增长（D-4）；>3 只挂档 → 防稀释闸触发。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import factor_engine
import holdings


def _next_weekdays(start, n):
    d = date.fromisoformat(start)
    out = []
    while len(out) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            out.append(d.isoformat())
    return out


class ReviewVerdictTest(unittest.TestCase):
    def test_low_sample_holds(self):
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 19, "lift_full": 1.5,
             "delta_full": 0.1}), "hold")

    def test_n_test_branch_holds(self):
        # SHOULD-1 / B1-8：indep≥20 但 n_test<20 → 挂档（不得升/降）
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "n_test": 15,
             "lift_full": 1.5, "delta_full": 0.1}), "hold")
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "n_test": 20,
             "lift_full": 1.1, "delta_full": 0.02}), "pass")
        # n_test 缺失（None）→ 仅按独立触发日判（向后兼容）
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30,
             "lift_full": 1.1, "delta_full": 0.02}), "pass")

    def test_dead_samples_param_removed(self):
        # NIT-1：死参数 samples 已移除（签名只剩 evidence）
        import inspect
        params = list(inspect.signature(factor_engine.review_verdict).parameters)
        self.assertEqual(params, ["evidence"])

    def test_pass_conditions(self):
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "lift_full": 1.1,
             "delta_full": 0.02, "dir_hit_rate": 0.7}), "pass")
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "lift_full": 1.0,
             "delta_full": 0.0}), "pass")

    def test_fail_conditions(self):
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "lift_full": 0.9,
             "delta_full": 0.02}), "downgrade")
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "lift_full": 1.2,
             "delta_full": -0.01}), "downgrade")
        self.assertEqual(factor_engine.review_verdict(
            {"has_data": True, "independent_trigger_days": 30, "lift_full": 1.2,
             "delta_full": 0.02, "dir_hit_rate": 0.5}), "downgrade")

    def test_no_data_one_vote_downgrade(self):
        self.assertEqual(factor_engine.review_verdict({"has_data": False}),
                         "downgrade")


class VerifyTiersIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_tier_")
        self._saved = (holdings.HOLDINGS_PATH, factor_engine.TIER_REVIEWS_PATH,
                       holdings.TIER_REVIEWS_PATH,
                       factor_engine._tier_review_evidence)
        holdings.HOLDINGS_PATH = os.path.join(self.tmp, "holdings.json")
        factor_engine.TIER_REVIEWS_PATH = os.path.join(self.tmp, "tier_reviews.jsonl")
        holdings.TIER_REVIEWS_PATH = factor_engine.TIER_REVIEWS_PATH
        self._evidence = {
            "000001": {"has_data": True, "independent_trigger_days": 30,
                       "lift_full": 1.1, "delta_full": 0.02, "dir_hit_rate": 0.7},
            "000002": {"has_data": True, "independent_trigger_days": 35,
                       "lift_full": 0.9, "delta_full": 0.01, "dir_hit_rate": 0.7},
            "000003": {"has_data": True, "independent_trigger_days": 8,
                       "lift_full": 1.4, "delta_full": 0.05},
        }
        factor_engine._tier_review_evidence = (
            lambda code, proxy, allow_network=True: (self._evidence.get(code,
                {"has_data": False}), None))
        obj = {"holdings": [
            {"code": c, "name": "基金%s" % c, "tier": "C", "proxy_code": "512480",
             "tier_reason": "原C依据", "verify_status": "pending_validation"}
            for c in ("000001", "000002", "000003")]}
        holdings.save_holdings(obj)

    def tearDown(self):
        (holdings.HOLDINGS_PATH, factor_engine.TIER_REVIEWS_PATH,
         holdings.TIER_REVIEWS_PATH,
         factor_engine._tier_review_evidence) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read_rows(self):
        with io.open(factor_engine.TIER_REVIEWS_PATH, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def _run(self):
        return factor_engine.verify_tiers(
            targets=["000001", "000002", "000003"], allow_network=False)

    def test_three_verdicts_and_apply(self):
        out = self._run()
        verdicts = {v["code"]: v for v in out["verdicts"]}
        self.assertEqual(verdicts["000001"]["verdict"], "pass")
        self.assertEqual(verdicts["000001"]["tier_after"], "B")
        self.assertEqual(verdicts["000001"]["verify_status"], "validated")
        self.assertEqual(verdicts["000002"]["verdict"], "downgrade")
        self.assertEqual(verdicts["000002"]["tier_after"], "D")
        self.assertEqual(verdicts["000002"]["verify_status"], "validation_failed")
        self.assertEqual(verdicts["000003"]["verdict"], "hold")
        self.assertEqual(verdicts["000003"]["tier_after"], "C")
        self.assertIsNotNone(verdicts["000003"]["review_date"])
        rows = self._read_rows()
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertIn("batch_id", r)
        # 应用结果（幂等更新 holdings）
        obj = holdings.load_holdings()
        by = {h["code"]: h for h in obj["holdings"]}
        self.assertEqual(by["000001"]["tier"], "B")
        self.assertEqual(by["000001"]["verify_status"], "validated")
        self.assertEqual(by["000002"]["tier"], "D")
        self.assertIn("降档", by["000002"]["tier_reason"])
        self.assertEqual(by["000003"]["tier"], "C")           # 挂档不进 universe
        self.assertEqual(by["000003"]["verify_status"], "validating")
        self.assertEqual(by["000003"]["verify_review_date"],
                         verdicts["000003"]["review_date"])
        # 复查日 = 证据就绪日 +30 交易日
        expect = _next_weekdays(factor_engine._today(), 30)
        self.assertEqual(verdicts["000003"]["review_date"], expect[29])
        # 幂等：重复应用不再变更
        self.assertEqual(holdings.apply_tier_reviews(), 0)

    def test_dilution_gate(self):
        self._evidence.update({
            "000004": {"has_data": True, "independent_trigger_days": 5},
            "000005": {"has_data": True, "independent_trigger_days": 6},
            "000006": {"has_data": True, "independent_trigger_days": 7},
        })
        obj = holdings.load_holdings()
        for c in ("000004", "000005", "000006"):
            obj["holdings"].append({"code": c, "name": "基金%s" % c, "tier": "C",
                                    "proxy_code": "512480", "tier_reason": "x",
                                    "verify_status": "pending_validation"})
        holdings.save_holdings(obj)
        out = factor_engine.verify_tiers(
            targets=["000001", "000002", "000003", "000004", "000005", "000006"],
            allow_network=False)
        self.assertEqual(out["hold_count"], 4)   # 000003~000006
        self.assertTrue(out["dilution_gate_triggered"])
        rows = self._read_rows()
        self.assertEqual(rows[-1]["kind"], "dilution_gate_alert")


class ProductionBacktestIntegrationTest(unittest.TestCase):
    """回归：verify_tiers 的证据收集必须能真正跑通单资产生产配置回测。

    （烟测曾发现 {code: bars} 形状错传 → 全量误降档；此用例守住该接缝。）
    """

    def _bars(self, n=140, seed=7):
        bars = []
        price = 1.0
        x = seed
        for i in range(n):
            x = (1103515245 * x + 12345) % 2147483648
            r = ((x / 2147483648.0) - 0.5) * 0.03
            o = price
            price = max(0.01, price * (1.0 + r))
            c = price
            bars.append({"date": "2026-%02d-%02d" % (1 + (i // 28) % 12, 1 + (i % 28)),
                         "open": o, "high": max(o, c) * 1.004, "low": min(o, c) * 0.996,
                         "close": c, "volume": float(1000 + (x % 500))})
        return bars

    def test_evaluate_production_shapes(self):
        bars = self._bars()
        for shape in ([("000001", bars)], {"000001": bars}):
            card = factor_engine.evaluate_production(
                shape, horizon=1, use_cache=False, do_bootstrap=False)
            self.assertGreater(card["sample_days"], 0)
            self.assertEqual(len(card["windows"]), 6)
            full = next(w for w in card["windows"] if w["window"] == "full")
            self.assertIn("independent_trigger_days", full)


class CoveragePendingTest(unittest.TestCase):
    def test_pending_excluded_from_universe(self):
        hs = [
            {"code": "000001", "name": "已升B", "tier": "B",
             "verify_status": "validated", "verify_review_date": None},
            {"code": "000002", "name": "挂档中", "tier": "C",
             "verify_status": "validating", "verify_review_date": "2026-11-01"},
            {"code": "000003", "name": "待验证", "tier": "C",
             "verify_status": "pending_validation", "verify_review_date": None},
            {"code": "000004", "name": "暴露待定", "tier": "D",
             "verify_status": "not_applicable", "verify_review_date": None},
        ]
        with mock.patch.object(app, "_holdings_list", return_value=hs), \
                mock.patch.object(app, "_total_value", return_value=0.0):
            data = app.h_holdings_coverage({}, None, {})
        self.assertEqual(data["prediction_universe_count"], 1)   # 挂档/待验证不计入
        self.assertEqual(data["pending_verification_count"], 2)
        self.assertEqual(data["pending_verification_names"],
                         ["挂档中", "待验证"])
        self.assertIn("待结论", data["prediction_coverage_note"])


if __name__ == "__main__":
    unittest.main()
