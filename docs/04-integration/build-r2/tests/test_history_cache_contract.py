# -*- coding: utf-8 -*-
"""S3 契约测试 · 历史读取缓存（冷启动 /holdings 提速的内部机制）。

断言要点：
- 重复读取不重复解析（按文件签名缓存；`_parse_history_file` 调用计数）；
- append_history 热缓存同步追加（不触发重解析）；
- 绕过 append 的外部修改 → 签名失配 → 重新解析（不返回陈旧数据）；
- 筛选参数正确；返回副本（调用方排序/清空不污染缓存）。
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


class HistoryCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_hcache_")
        self._saved = valuation.HISTORY_PATH
        valuation.HISTORY_PATH = os.path.join(self.tmp, "history.jsonl")
        valuation._HISTORY_CACHE.update({"path": None, "sig": None, "rows": []})
        self._orig_parse = valuation._parse_history_file
        self.parse_calls = {"n": 0}

        def counting(path):
            self.parse_calls["n"] += 1
            return self._orig_parse(path)

        valuation._parse_history_file = counting

    def tearDown(self):
        valuation._parse_history_file = self._orig_parse
        valuation.HISTORY_PATH = self._saved
        valuation._HISTORY_CACHE.update({"path": None, "sig": None, "rows": []})
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rec(self, date, code="000001", est=0.01):
        return {"date": date, "code": code, "valuation_mode": "proxy",
                "change_rate": est, "written_at": "%sT15:00:00+08:00" % date}

    def test_repeated_reads_parse_once(self):
        valuation.append_history(self._rec("2026-09-01"))
        valuation.append_history(self._rec("2026-09-02"))
        rows1 = valuation.read_history()
        rows2 = valuation.read_history()
        self.assertEqual(len(rows1), 2)
        self.assertEqual(len(rows2), 2)
        self.assertEqual(self.parse_calls["n"], 1)

    def test_append_updates_warm_cache_without_reparse(self):
        valuation.append_history(self._rec("2026-09-01"))
        valuation.read_history()                       # 预热缓存
        valuation.append_history(self._rec("2026-09-02"))
        rows = valuation.read_history()
        self.assertEqual(len(rows), 2)                 # 热追加可见
        self.assertEqual(self.parse_calls["n"], 1)     # 未重解析

    def test_external_write_invalidates(self):
        valuation.append_history(self._rec("2026-09-01"))
        valuation.read_history()
        # 绕过 append 直接改文件（模拟另一进程/手工）→ 签名失配 → 重解析
        with io.open(valuation.HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._rec("2026-09-03", est=0.02)) + "\n")
        rows = valuation.read_history()
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.parse_calls["n"], 2)

    def test_filters_and_copy_semantics(self):
        valuation.append_history(self._rec("2026-09-01", code="000001"))
        valuation.append_history(self._rec("2026-09-01", code="000002"))
        valuation.append_history(self._rec("2026-09-02", code="000001"))
        self.assertEqual(len(valuation.read_history(code="000001")), 2)
        self.assertEqual(len(valuation.read_history(date="2026-09-01")), 2)
        mixed = valuation.read_history(code="000001", date="2026-09-01")
        self.assertEqual(len(mixed), 1)
        # 返回副本：清空返回值不影响缓存
        got = valuation.read_history(code="000001")
        got.clear()
        self.assertEqual(len(valuation.read_history(code="000001")), 2)


if __name__ == "__main__":
    unittest.main()
