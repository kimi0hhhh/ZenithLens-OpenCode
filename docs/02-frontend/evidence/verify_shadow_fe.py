# -*- coding: utf-8 -*-
"""OC-SHADOW-FE 前端断言（真后端 127.0.0.1:8791 + CDP 9333）。

阶段 A（真后端，无桩）：因子页 caps 文案、无「上限 3」、真实台账三处可见。
阶段 B（桩：caps/factor_cap 全缺）：头部不得显示任何上限数字（防回归）。
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\05-qa\evidence\scripts")
from cdp import CDP

PORT = 9333
BASE = "http://127.0.0.1:8791"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)) if detail else ""))


def api(path):
    return json.load(urllib.request.urlopen(BASE + "/api/v1" + path, timeout=20))


c = CDP(PORT)

# ---- 后端真实形状（证据锚点） ----
pans = api("/factors/pans")["data"]["pans"]
adopted = [p for p in pans if p["role"] == "adopted"][0]
check("后端 /factors/pans 返回 caps 对象", isinstance(adopted.get("caps"), dict), json.dumps(adopted.get("caps"), ensure_ascii=True))
led = api("/ledger?limit=60")["data"]
check("后端 /ledger 真实台账非空", len(led.get("rows") or []) > 0, len(led.get("rows") or []))

# ============ 阶段 A：真后端 ============
c.navigate(BASE + "/?v=A#/factors", settle=5.0)
time.sleep(3.5)
txt = c.eval("(document.getElementById('view-factors')||{}).innerText||''")
hdr = c.eval("(document.querySelector('#fc-pans .card h3')||{}).innerText||''")
check("A 因子页 data-state=success", c.eval("document.getElementById('view-factors').dataset.state") == "success")
check("A 因子盘头部显示「否决位 ≤4 · 打分位 ≤3」", "否决位 ≤4 · 打分位 ≤3" in hdr, json.dumps(hdr, ensure_ascii=True))
check("A 因子页不含「上限 3」", "上限 3" not in txt)
check("A 因子盘头部无裸 factor_cap 文案", "上限" not in hdr, json.dumps(hdr, ensure_ascii=True))
c.screenshot(r"C:\Users\10719\AppData\Local\Temp\opencode\zl_caps_factors.png")

c.navigate(BASE + "/?v=As#/signals", settle=5.0)
time.sleep(4.0)
tl = c.eval("document.querySelectorAll('#tl-list .tl-item').length")
check("A 信号页时间线渲染真实台账行（>0）", tl and tl > 0, tl)
c.screenshot(r"C:\Users\10719\AppData\Local\Temp\opencode\zl_caps_signals.png")

c.navigate(BASE + "/?v=Ae#/engine", settle=6.0)
time.sleep(5.0)
eg = c.eval("document.querySelectorAll('#eg-ledger-rows tr').length")
check("A 引擎页最近记录渲染真实台账行（>0）", eg and eg > 0, eg)
c.screenshot(r"C:\Users\10719\AppData\Local\Temp\opencode\zl_caps_engine.png")

c.navigate(BASE + "/?v=Ar#/review", settle=6.0)
time.sleep(5.0)
rv = c.eval("document.querySelectorAll('#rv-body tr').length")
check("A 复盘页逐笔对账渲染真实台账行（>0）", rv and rv > 0, rv)
c.screenshot(r"C:\Users\10719\AppData\Local\Temp\opencode\zl_caps_review.png")

# ============ 阶段 B：缺 caps 不显示错误数字 ============
STUB = r"""
(function () {
  var realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : ((input && input.url) || '');
    var p = realFetch(input, init);
    if (url.indexOf('/api/v1/factors/pans') >= 0) {
      return p.then(function (res) {
        return res.clone().json().then(function (env) {
          (env.data.pans || []).forEach(function (x) { x.caps = null; delete x.factor_cap; });
          return new Response(JSON.stringify(env), { status: res.status, headers: { 'Content-Type': 'application/json' } });
        });
      });
    }
    return p;
  };
})();
"""
c.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
c.navigate(BASE + "/?v=B#/factors", settle=5.0)
time.sleep(3.5)
hdrB = c.eval("(document.querySelector('#fc-pans .card h3')||{}).innerText||''")
txtB = c.eval("(document.getElementById('view-factors')||{}).innerText||''")
check("B caps/factor_cap 皆缺时头部不显示任何上限数字", "上限" not in hdrB, json.dumps(hdrB, ensure_ascii=True))
check("B caps 缺失时无「上限 3」", "上限 3" not in txtB)

fails = [r for r in results if not r[1]]
print("TOTAL %d PASS %d FAIL %d" % (len(results), len(results) - len(fails), len(fails)))
c.close()
sys.exit(1 if fails else 0)
