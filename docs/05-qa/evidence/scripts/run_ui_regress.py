# -*- coding: utf-8 -*-
"""S5 定向回归 · 真浏览器断言（Chrome CDP 9222 直连）：
D-01 立方体对比卡 92.00%→100.00% 且无 0.9%；D-02 naive 低样本角标 >0；
D-03 契约版本标注 v5；D-04 分析页档位列/市值列直读 predictions 行字段。
输出 evidence/regress_ui_checks.json + shot_engine_regress.png / shot_analyze_regress.png。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP

OUT = os.path.abspath(os.path.join(HERE, ".."))
BASE = "http://127.0.0.1:8791/"


def load(n):
    return json.load(io.open(os.path.join(OUT, n), encoding="utf-8"))


def parse_amt(s):
    if not s:
        return None
    t = s.replace("¥", "").replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def main():
    c = CDP(9222)
    c.call("Emulation.setDeviceMetricsOverride",
           {"width": 1720, "height": 2600, "deviceScaleFactor": 1, "mobile": False})
    checks = []

    def chk(cid, desc, ok, detail):
        checks.append({"id": cid, "desc": desc, "pass": bool(ok), "detail": detail})

    # ---------- Engine: D-01 / D-02 / D-03 ----------
    c.navigate(BASE + "#/engine", settle=1.0)
    time.sleep(7)
    cmp_text = c.eval("(document.querySelector('#eg-cmp')||{}).innerText || ''") or ""
    page_text = c.eval("document.body.innerText") or ""
    cmp_cells = c.eval("Array.prototype.map.call(document.querySelectorAll('#eg-cmp *'),function(e){return e.innerText;}).join('|')") or ""

    chk("D-01-a", "#eg-cmp 显示 92.00%", "92.00%" in cmp_text, "cmp_text=%r" % cmp_text[:160])
    chk("D-01-b", "#eg-cmp 显示 100.00%", "100.00%" in cmp_text, "cmp_text=%r" % cmp_text[:160])
    chk("D-01-c", "引擎页不再出现 0.9%（少乘 100）", "0.9%" not in page_text and "0.9 %" not in page_text,
        "has_0.9=%.0f" % ("0.9%" in page_text))

    # expand research naive + count low-sample marks
    c.eval("document.querySelector('#cube-research').open = true")
    time.sleep(1.2)
    low_marks = c.eval("document.querySelectorAll('#cube-research-grid .low, #cube-research-grid [data-low-sample], #cube-research-grid .low-mark').length") or 0
    low_mark_sups = c.eval("document.querySelectorAll('#cube-research-grid .low-mark').length") or 0
    chk("D-02-a", "naive 低样本角标 low_sample_marks > 0", low_marks > 0, "low_sample_marks=%s" % low_marks)
    chk("D-02-b", "存在「低样本·仅供审计」角标元素", low_mark_sups > 0, "low-mark=%s" % low_mark_sups)
    c.screenshot(os.path.join(OUT, "shot_engine_regress.png"))

    meta_v = c.eval("(document.querySelector('meta[name=api-contract]')||{}).content") or ""
    side_foot = c.eval("(document.querySelector('.side-foot')||{}).innerText || ''") or ""
    chk("D-03-a", "meta[name=api-contract]=v5", meta_v.strip() == "v5", "meta=%r" % meta_v)
    chk("D-03-b", "侧栏字段口径标注 v5 且无 v4", "v5" in side_foot and "v4" not in side_foot, "side_foot=%r" % side_foot[:120])

    # ---------- Settings footer (D-03) ----------
    c.navigate(BASE + "#/settings", settle=1.0)
    time.sleep(5)
    set_foot = c.eval("(document.querySelector('#view-settings .foot')||{}).innerText || ''") or ""
    chk("D-03-c", "设置页脚标注 v5 且无 v4", "v5" in set_foot and "v4" not in set_foot, "set_foot=%r" % set_foot[:160])

    # ---------- Analyze: D-04 ----------
    c.navigate(BASE + "#/analyze", settle=1.0)
    time.sleep(7)
    dom_rows = c.eval(r"""JSON.stringify(Array.prototype.map.call(
        document.querySelectorAll('#an-body tr[data-code]'), function(tr){
            var tds = tr.querySelectorAll('td');
            return { code: tr.getAttribute('data-code'),
                     tier: (tds[1]||{}).innerText || '',
                     mv: (tds[8]||{}).innerText || '' };
        }))""")
    dom_rows = json.loads(dom_rows or "[]")
    preds = {r["code"]: r for r in load("ep_predictions.json")["data"]["rows"]}
    tier_mism = []
    mv_mism = []
    for r in dom_rows:
        p = preds.get(r["code"], {})
        if (p.get("tier") or "—") != (r.get("tier") or ""):
            tier_mism.append(r["code"])
        if p.get("market_value") is not None:
            got = parse_amt(r.get("mv"))
            if got is None or abs(got - p["market_value"]) > 0.01:
                mv_mism.append("%s:%s vs %s" % (r["code"], got, p["market_value"]))
    chk("D-04-a", "分析页预测表档位列直读 predictions.tier（10/10 且全部 A-D）",
        len(dom_rows) >= 10 and len(tier_mism) == 0 and all(r["tier"] in ("A", "B", "C", "D") for r in dom_rows),
        "rows=%d tier_mismatch=%s tiers=%s" % (len(dom_rows), tier_mism, [r["tier"] for r in dom_rows]))
    chk("D-04-b", "分析页市值列与 predictions.market_value 逐只一致",
        len(mv_mism) == 0, "mv_mismatch=%s" % mv_mism)
    c.screenshot(os.path.join(OUT, "shot_analyze_regress.png"))

    c.close()

    ok = sum(1 for x in checks if x["pass"])
    out = {"total": len(checks), "pass": ok, "fail": len(checks) - ok,
           "dom_rows": dom_rows, "checks": checks}
    with io.open(os.path.join(OUT, "regress_ui_checks.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for x in checks:
        print(("PASS " if x["pass"] else "FAIL ") + x["id"] + " " + x["desc"] + " | " + x["detail"])
    print("SUMMARY %d/%d" % (ok, len(checks)))
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
