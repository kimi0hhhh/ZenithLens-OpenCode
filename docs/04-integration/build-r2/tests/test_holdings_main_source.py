# -*- coding: utf-8 -*-
"""R2 契约测试 · 持仓主源切换（09-r2 §3.11/§4.4；08-r2 §6.2；R2-15）。

断言要点：
- `data/holdings.json` 存在即主源；缺失且外部导入源不可用 → 空态（可读提示），不抛 E_IO；
- `main_source` 口径（path/exists/modified_at/count/readonly=false）；
- `import_available=false` + 可读 `import_disabled_reason`（按钮禁用路径）。
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

import app
import holdings


class HoldingsMainSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_main_")
        self._saved = (holdings.HOLDINGS_PATH, holdings.PRIMARY_PATH,
                       holdings.LEGACY_PATH)
        holdings.HOLDINGS_PATH = os.path.join(self.tmp, "holdings.json")
        holdings.PRIMARY_PATH = os.path.join(self.tmp, "no_such_source.json")
        holdings.LEGACY_PATH = os.path.join(self.tmp, "no_such_source.json.bak")

    def tearDown(self):
        (holdings.HOLDINGS_PATH, holdings.PRIMARY_PATH,
         holdings.LEGACY_PATH) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_all_returns_empty_state(self):
        obj = holdings.ensure_holdings()          # 不抛 E_IO
        self.assertEqual(obj.get("holdings"), [])
        self.assertIn("hint", obj)
        self.assertTrue(os.path.isfile(holdings.HOLDINGS_PATH))

    def test_main_source_status(self):
        holdings.ensure_holdings()
        st = holdings.main_source_status()
        self.assertTrue(st["exists"])
        self.assertEqual(st["count"], 0)
        self.assertFalse(st["readonly"])
        # R2-D2：path 为契约字面相对标识（无盘符/反斜杠）
        self.assertEqual(st["path"], "data/holdings.json")
        self.assertNotIn(":", st["path"])
        self.assertNotIn("\\", st["path"])
        self.assertIsNotNone(st["modified_at"])

    def test_import_unavailable_reason(self):
        ok, reason = holdings.import_source_status()
        self.assertFalse(ok)
        self.assertIn("源文件不存在", reason)

    def test_settings_handler_exposes_main_source_fields(self):
        holdings.ensure_holdings()
        data = app.h_settings_holdings_data({}, None, {})
        self.assertIn("main_source", data)
        self.assertEqual(data["main_source"]["exists"], True)
        self.assertIn("import_available", data)
        self.assertFalse(data["import_available"])
        self.assertIsNotNone(data["import_disabled_reason"])
        # 向后兼容：primary_* 键保留（语义=可选外部导入源）
        self.assertIn("primary_exists", data)


if __name__ == "__main__":
    unittest.main()
