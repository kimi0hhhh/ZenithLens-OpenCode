# -*- coding: utf-8 -*-
"""R2 契约测试 · 数据源失败窗口（09-r2 §3.10；08-r2 §6.4；R2-18）。

断言要点：
- fail_window_7d 按自然日窗口滚动；成功不抹除窗口内历史；
- recent_failures 最近 ≤10 条 {at, note}；fail_window_days=7；
- 旧 fail_count 保留为累计（审计），当前状态由窗口驱动（544 不再作当前状态）。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import settings


class HealthWindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_health_")
        self._saved = (settings.HEALTH_PATH, settings.HEALTH_LOG_PATH)
        settings.HEALTH_PATH = os.path.join(self.tmp, "health.json")
        settings.HEALTH_LOG_PATH = os.path.join(self.tmp, "health-log.jsonl")

    def tearDown(self):
        settings.HEALTH_PATH, settings.HEALTH_LOG_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _health(self, sid="eastmoney"):
        return next(r for r in settings.get_health() if r["source_id"] == sid)

    def test_window_rolls_and_success_keeps_history(self):
        settings.record_source("eastmoney", False, note="fail-1")
        settings.record_source("eastmoney", False, note="fail-2")
        h = self._health()
        self.assertEqual(h["fail_window_7d"], 2)
        self.assertEqual(h["fail_window_days"], 7)
        self.assertEqual(h["status"], "warn")
        settings.record_source("eastmoney", True, note="ok")
        h = self._health()
        self.assertEqual(h["fail_window_7d"], 2)     # 成功不抹除窗口内历史
        self.assertEqual(h["status"], "ok")

    def test_old_event_out_of_window(self):
        old = (datetime.now().astimezone() - timedelta(days=8)).replace(
            microsecond=0).isoformat()
        with io.open(settings.HEALTH_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(json.dumps({"at": old, "source_id": "eastmoney", "ok": False,
                                "note": "old"}) + "\n")
        h = self._health()
        self.assertEqual(h["fail_window_7d"], 0)

    def test_recent_failures_capped_at_10(self):
        for i in range(12):
            settings.record_source("eastmoney", False, note="f%d" % i)
        h = self._health()
        self.assertEqual(h["fail_window_7d"], 12)
        self.assertLessEqual(len(h["recent_failures"]), 10)
        self.assertIn("at", h["recent_failures"][0])
        self.assertIn("note", h["recent_failures"][0])
        self.assertEqual(h["status"], "bad")

    def test_cumulative_fail_count_preserved_not_current(self):
        with io.open(settings.HEALTH_PATH, "w", encoding="utf-8") as f:
            json.dump({"eastmoney": {"source_id": "eastmoney", "status": "bad",
                                     "fail_count": 544, "note": "历史累计"}}, f)
        h = self._health()
        self.assertEqual(h["fail_count"], 544)          # 累计值保留（审计）
        self.assertEqual(h["fail_window_7d"], 0)        # 当前状态不再由 544 驱动
        self.assertNotEqual(h["status"], "bad")


class SinaDegradeAnnotationTest(unittest.TestCase):
    """S2（b）路线：新浪长期不可用 → 既有 note 回填「仅探测·非主链」（不改契约字段）。

    依据：10-arch-review-r2 §2 裁定③ / 08-r2 §6.3 加严②。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_sina_hl_")
        self._saved = (settings.HEALTH_PATH, settings.HEALTH_LOG_PATH)
        settings.HEALTH_PATH = os.path.join(self.tmp, "health.json")
        settings.HEALTH_LOG_PATH = os.path.join(self.tmp, "health-log.jsonl")

    def tearDown(self):
        settings.HEALTH_PATH, settings.HEALTH_LOG_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _health(self, sid):
        return next(r for r in settings.get_health() if r["source_id"] == sid)

    def test_annotation_on_repeated_failures(self):
        for i in range(3):
            settings.record_source("sina_rt", False, note="sina f%d" % i)
        h = self._health("sina_rt")
        self.assertIn(settings.SINA_DEGRADE_MARK, h["note"])
        self.assertIn("失败", h["note"])
        # 回填落盘：health.json 既有 note 字段同步携带标注（非仅读取层）
        with io.open(settings.HEALTH_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertIn(settings.SINA_DEGRADE_MARK, raw["sina_rt"]["note"])
        # 其他源不受影响（标注只挂新浪）
        self.assertNotIn(settings.SINA_DEGRADE_MARK, self._health("eastmoney")["note"])

    def test_no_annotation_below_threshold(self):
        settings.record_source("sina_rt", False, note="f")
        settings.record_source("sina_rt", True, note="ok")
        self.assertNotIn(settings.SINA_DEGRADE_MARK, self._health("sina_rt")["note"])

    def test_annotation_when_long_unavailable_without_success(self):
        old = (datetime.now().astimezone() - timedelta(days=10)).replace(
            microsecond=0).isoformat()
        now = datetime.now().astimezone().replace(microsecond=0).isoformat()
        with io.open(settings.HEALTH_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(json.dumps({"at": old, "source_id": "sina_rt", "ok": False,
                                "note": "old fail"}) + "\n")
            f.write(json.dumps({"at": now, "source_id": "sina_rt", "ok": False,
                                "note": "fail"}) + "\n")
        h = self._health("sina_rt")
        self.assertIn(settings.SINA_DEGRADE_MARK, h["note"])
        self.assertIn("≥7 日", h["note"])


if __name__ == "__main__":
    unittest.main()
