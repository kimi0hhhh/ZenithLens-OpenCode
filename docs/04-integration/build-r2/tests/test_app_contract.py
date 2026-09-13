# -*- coding: utf-8 -*-
"""契约 v4 关键路径测试 · 服务装配（09 §4/§6.9 · A-08 参数黑名单）。"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import errors
import settings


class AppContractTest(unittest.TestCase):
    def test_default_port_8791(self):
        self.assertEqual(app.DEFAULT_PORT, 8791)

    def test_routes_cover_55_interfaces_plus_health(self):
        # 55 契约接口（v7 增 2：POST/GET /factors/candidates）+ /health 运维端点
        self.assertEqual(len(app.ROUTES), 56)
        routes = {(m, p) for (m, p, _fn) in app.ROUTES}
        self.assertIn(("POST", "/factors/candidates"), routes)
        self.assertIn(("GET", "/factors/candidates/(?P<candidate_id>[A-Za-z0-9_\\-]+)"), routes)

    def test_no_ledger_edit_or_delete_route(self):
        for method, path, _fn in app.ROUTES:
            if path.startswith("/ledger"):
                self.assertNotIn(method, ("DELETE", "PUT", "PATCH"))

    def test_frozen_param_blacklist_v4(self):
        for k in ("min_coverage_ratio", "min_open_count", "weighting_basis",
                  "k_noise", "p_perturb", "min_n", "shrink", "band",
                  "veto_crowd_quantile", "veto_klow2_quantile"):
            self.assertIn(k, app.FROZEN_PARAM_KEYS)

    def test_task_payload_rejects_frozen_weighting_basis(self):
        with self.assertRaises(errors.ApiError) as cm:
            app.validate_task_payload("run_prediction", {"weighting_basis": "market_value"})
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)

    def test_task_payload_rejects_frozen_coverage(self):
        with self.assertRaises(errors.ApiError):
            app.validate_task_payload("run_prediction", {"min_coverage_ratio": 0.1})

    def test_task_payload_accepts_normal_params(self):
        app.validate_task_payload("run_backtest", {"window": "T1"})


class SettingsBaseUrlV5Test(unittest.TestCase):
    """BLOCK-2：llm.base_url GET 回传 / PUT 落盘往返 / 非法值 E_VALIDATION / 缺省空串。"""

    def setUp(self):
        self._orig = settings.SETTINGS_PATH
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)
        settings.SETTINGS_PATH = self.path

    def tearDown(self):
        settings.SETTINGS_PATH = self._orig
        if os.path.isfile(self.path):
            os.remove(self.path)

    def test_missing_returns_empty_string(self):
        self.assertEqual(settings.get_settings()["llm"]["base_url"], "")

    def test_put_then_get_roundtrip(self):
        url = "https://api.deepseek.com/v1"
        settings.update_settings({"llm": {"base_url": url}})
        # 重新从磁盘读（模拟刷新），值必须仍在
        self.assertEqual(settings.get_settings()["llm"]["base_url"], url)

    def test_invalid_url_rejected(self):
        with self.assertRaises(errors.ApiError) as cm:
            settings.update_settings({"llm": {"base_url": "api.deepseek.com"}})
        self.assertEqual(cm.exception.code, errors.E_VALIDATION)
        self.assertIn("llm.base_url", cm.exception.detail)

    def test_empty_string_clears(self):
        settings.update_settings({"llm": {"base_url": "https://x.example/v1"}})
        settings.update_settings({"llm": {"base_url": ""}})
        self.assertEqual(settings.get_settings()["llm"]["base_url"], "")


class PredictionSummaryV5Test(unittest.TestCase):
    """SHOULD-4：/predictions 行直带 tier/market_value，口径同 HoldingRow（禁成本回退）。"""

    def test_tier_and_market_value_from_holding(self):
        row = {"code": "TEST01", "signal": "gray", "_chain": [{"step": 1}]}
        h = {"code": "TEST01", "tier": "A", "shares": 100.0,
             "nav_history": {"2026-09-11": 2.0}}
        out = app._prediction_public(row, {"TEST01": h}, "2026-09-12")
        self.assertEqual(out["tier"], "A")
        self.assertAlmostEqual(out["market_value"], 200.0, places=2)
        self.assertNotIn("_chain", out)

    def test_market_value_null_without_nav_no_cost_fallback(self):
        row = {"code": "TEST02", "signal": "gray"}
        h = {"code": "TEST02", "tier": "D", "shares": 100.0,
             "cost_amount": 999.0, "nav_history": {}}
        out = app._prediction_public(row, {"TEST02": h}, "2026-09-12")
        self.assertEqual(out["tier"], "D")
        self.assertIsNone(out["market_value"])

    def test_orphan_row_tier_null(self):
        out = app._prediction_public({"code": "GONE01"}, {}, "2026-09-12")
        self.assertIsNone(out["tier"])
        self.assertIsNone(out["market_value"])


class TaskMutexD3Test(unittest.TestCase):
    """R2-D3（§8.3）：同型互斥 409 可读 + 全局串行 + 错误可读化（无 WinError 泄漏）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_task_")
        self._saved = (app.TASKS_PATH, app._run_task, app._run_task_impl)
        self._orig_run_task = app._run_task
        app.TASKS_PATH = os.path.join(self.tmp, "tasks.json")
        app._run_task = lambda task: None          # 线程 noop（专注提交侧互斥）
        self._events = []

    def tearDown(self):
        app.TASKS_PATH, app._run_task, app._run_task_impl = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _task(self, tid):
        return next(t for t in app._load_tasks() if t["task_id"] == tid)

    def test_same_type_conflict_readable(self):
        first = app.start_task("run_prediction")
        with self.assertRaises(errors.ApiError) as cm:
            app.start_task("run_prediction")
        self.assertEqual(cm.exception.code, errors.E_CONFLICT)
        self.assertEqual(cm.exception.http_status, 409)
        self.assertIn(first["task_id"], cm.exception.message)
        self.assertIn("同型任务进行中", cm.exception.message)
        tasks = app._load_tasks()
        self.assertEqual(len(tasks), 1)            # 不落 failed、不启动第二线程
        self.assertEqual(tasks[0]["status"], "queued")

    def test_sequential_after_done_allowed(self):
        first = app.start_task("run_prediction")
        app._update_task(first["task_id"], status="done")
        second = app.start_task("run_prediction")
        self.assertNotEqual(first["task_id"], second["task_id"])

    def test_global_serial_across_types(self):
        # 跨型也串行（确认 maintain × backfill 同写 backfill.jsonl 的竞态兜底）
        def slow(task):
            self._events.append(("start", task["type"]))
            time.sleep(0.15)
            self._events.append(("end", task["type"]))

        app._run_task_impl = slow
        app._run_task = self._orig_run_task     # 恢复带锁入口，验证全局串行
        app.start_task("run_prediction")
        app.start_task("scan_factors")
        time.sleep(0.8)
        self.assertEqual(len(self._events), 4)
        self.assertEqual(self._events[0][0], "start")
        self.assertEqual(self._events[1][0], "end")
        self.assertEqual(self._events[0][1], self._events[1][1])   # 无交叉
        self.assertEqual(self._events[2][0], "start")
        self.assertEqual(self._events[3][0], "end")

    def test_oserror_readable_no_winerror(self):
        task = app._new_task("scan_factors")
        orig = app.holdings_mod.ensure_holdings
        app.holdings_mod.ensure_holdings = lambda: (_ for _ in ()).throw(
            OSError(5, "Access is denied"))
        try:
            app._run_task_impl(task)
        finally:
            app.holdings_mod.ensure_holdings = orig
        t = self._task(task["task_id"])
        self.assertEqual(t["status"], "failed")
        self.assertEqual(t["error"]["code"], errors.E_IO)
        blob = json.dumps(t["error"], ensure_ascii=False)
        self.assertNotIn("WinError", blob)
        self.assertNotIn("Access is denied", blob)
        self.assertIn("本地数据文件", t["error"]["message"])


class ScanFactorsHonestTest(unittest.TestCase):
    """独立跑（不依赖互斥类的 noop patch）：scan_factors summary/step 诚实化。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_scan_")
        self._saved = app.TASKS_PATH
        app.TASKS_PATH = os.path.join(self.tmp, "tasks.json")

    def tearDown(self):
        app.TASKS_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_fake_completion(self):
        task = app._new_task("scan_factors")
        app._run_task_impl(task)
        t = next(x for x in app._load_tasks() if x["task_id"] == task["task_id"])
        blob = (t.get("result_summary") or "") + (t.get("step") or "")
        self.assertNotIn("扫描完成", blob)
        self.assertIn("未接入", t["result_summary"])
        self.assertIn("未接入", t["step"])


if __name__ == "__main__":
    unittest.main()
