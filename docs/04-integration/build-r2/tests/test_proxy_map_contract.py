# -*- coding: utf-8 -*-
"""契约 v7 覆盖度档位 + 主动基金持仓穿透测试（task OC-COV-BE）。

覆盖点：
- 全部 22 只基金（静态映射 20 + 穿透 2）均能算出 A/B/C/D 档（无遗漏）；
- 静态映射分档计数 A=2 / B=13 / C=5；
- F10 前十 HTML 解析 + 个股→行业 ETF 映射 + 加权主代理；
- 穿透不到 / 未映射 → 诚实留 D（proxy_code=null）；
- sync_proxy_fields 把存量 D 补齐（真实穿透缓存存在时 D=0）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fund_predict  # noqa: E402
import proxy_map  # noqa: E402

# 22 只持仓代码（来自 data/holdings.json）
ALL22 = [
    "025500", "018957", "024239", "025857", "021528", "017193", "016786", "457001",
    "013566", "014881", "163208", "018897", "022485", "014320", "011840", "008087",
    "017412", "016665", "012922", "021662", "000217", "002963",
]

F10_SNIPPET = (
    'var apidata={ content:"'
    "<table class='w782 comm tzxq'><tbody>"
    "<tr><td>1</td><td><a href='//x'>300502</a></td><td class='tol'><a>新易盛</a></td>"
    "<td class='tor'>9.47%</td><td class='tor'>197,399.01</td></tr>"
    "<tr><td>2</td><td><a href='//x'>688519</a></td><td class='tol'><a>南亚新材</a></td>"
    "<td class='tor'>8.75%</td><td class='tor'>182,514.25</td></tr>"
    "</tbody></table>"
    '",arryear:[2026,2025],curyear:2026};'
)


class TierMappingTest(unittest.TestCase):
    def test_all_22_resolve_to_valid_tier(self):
        for code in ALL22:
            r = proxy_map.resolve(code)
            self.assertIn(r["tier"], ("A", "B", "C", "D"), code)
            if r["tier"] != "D":
                self.assertRegex(str(r["proxy_code"]), r"^\d{6}$",
                                 "%s proxy_code" % code)
            else:
                self.assertIsNone(r["proxy_code"], code)

    def test_static_map_covers_20_no_duplicate(self):
        static = [c for c in ALL22 if c not in proxy_map.PENETRATION_TARGETS]
        self.assertEqual(len(static), 20)
        self.assertTrue(all(c in proxy_map.PROXY_MAP for c in static))

    def test_static_tier_counts_a2_b13_c5(self):
        static = [c for c in ALL22 if c not in proxy_map.PENETRATION_TARGETS]
        counts = {t: 0 for t in proxy_map.COVERAGE_TIERS}
        for c in static:
            counts[proxy_map.resolve(c)["tier"]] += 1
        self.assertEqual(counts, {"A": 2, "B": 13, "C": 5, "D": 0})

    def test_unknown_code_is_d(self):
        r = proxy_map.resolve("999999")
        self.assertEqual(r["tier"], "D")
        self.assertIsNone(r["proxy_code"])
        self.assertIn("待定", r["tier_reason"])


class PenetrationTest(unittest.TestCase):
    def test_parse_f10_top10(self):
        rows = proxy_map.parse_f10_holdings(F10_SNIPPET)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["stock_code"], "300502")
        self.assertEqual(rows[0]["stock_name"], "新易盛")
        self.assertAlmostEqual(rows[0]["weight_pct"], 9.47, places=2)
        self.assertEqual(rows[1]["stock_code"], "688519")

    def test_penetrate_maps_to_dominant_etf(self):
        rows = proxy_map.parse_f10_holdings(F10_SNIPPET)
        rec = proxy_map.penetrate_rows("021528", rows, report_date="2026-06-30")
        self.assertEqual(rec["tier"], "C")
        self.assertEqual(rec["proxy_code"], "515880")
        trace = rec["penetration_trace"]
        self.assertEqual(trace["report_date"], "2026-06-30")
        self.assertEqual(trace["proxy"], "515880")
        self.assertEqual(len(trace["top10"]), 2)
        self.assertTrue(all(x["etf_code"] == "515880" for x in trace["top10"]))
        self.assertIn("待验证", trace["status"])

    def test_unmapped_stock_leaves_d_or_ignored(self):
        rows = [{"rank": 1, "stock_code": "000000", "stock_name": "未知",
                 "weight_pct": 5.0}]
        rec = proxy_map.penetrate_rows("025500", rows, report_date="2026-06-30")
        self.assertEqual(rec["tier"], "D")
        self.assertIsNone(rec["proxy_code"])
        self.assertEqual(rec["penetration_trace"]["unmapped"][0]["stock_code"], "000000")

    def test_empty_rows_is_d(self):
        rec = proxy_map.penetrate_rows("025500", [])
        self.assertEqual(rec["tier"], "D")
        self.assertIsNone(rec["proxy_code"])

    def test_real_cache_penetration_has_trace(self):
        cache = proxy_map.load_penetration_cache()
        if not cache:
            self.skipTest("穿透缓存不存在（需联网生成 data/cache/proxy/penetration.json）")
        for code in proxy_map.PENETRATION_TARGETS:
            rec = cache.get(code)
            self.assertIsNotNone(rec, code)
            self.assertEqual(rec["tier"], "C")
            self.assertTrue(rec["penetration_trace"]["top10"])
            self.assertTrue(rec["penetration_trace"]["basket"])


class SyncProxyFieldsTest(unittest.TestCase):
    def test_sync_upgrades_legacy_d_rows(self):
        import holdings
        cache = proxy_map.load_penetration_cache()
        if not cache:
            self.skipTest("穿透缓存不存在")
        raw = [{"code": c, "name": c, "tier": "D", "proxy_code": None,
                "proxy_name": None, "tier_reason": "无验证代理，暴露待定"}
               for c in ALL22]
        obj = {"holdings": raw}
        self.assertTrue(holdings.sync_proxy_fields(obj))
        counts = {t: 0 for t in proxy_map.COVERAGE_TIERS}
        for h in obj["holdings"]:
            counts[h["tier"]] += 1
        self.assertEqual(counts, {"A": 2, "B": 13, "C": 7, "D": 0})
        # 幂等：再同步不再变更
        self.assertFalse(holdings.sync_proxy_fields(obj))


class HoldingRowTraceTest(unittest.TestCase):
    def test_build_holding_row_exposes_penetration_trace(self):
        h = {"code": "025500", "name": "东方阿尔法科技智选混合发起C", "group": "active",
             "tier": "C", "shares": 1.0, "cost_amount": 1.0, "proxy_code": "512480",
             "proxy_name": "半导体ETF国联安", "penetration_trace": {"proxy": "512480"}}
        row = fund_predict.build_holding_row(h, "2026-09-12", None, 1.0)
        self.assertEqual(row["penetration_trace"]["proxy"], "512480")

    def test_build_holding_row_trace_null_without_penetration(self):
        h = {"code": "000217", "name": "x", "tier": "B", "shares": 1.0,
             "cost_amount": 1.0, "proxy_code": "518880"}
        row = fund_predict.build_holding_row(h, "2026-09-12", None, 1.0)
        self.assertIsNone(row["penetration_trace"])


if __name__ == "__main__":
    unittest.main()
