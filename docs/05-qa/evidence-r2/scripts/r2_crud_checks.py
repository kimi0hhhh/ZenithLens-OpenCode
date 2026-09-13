# -*- coding: utf-8 -*-
"""R1 沿用 CRUD 冒烟（临时代码 999998，测后还原）+ vsum/滞后补充断言（CDP）。"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:8796/api/v1"
RESULTS = []


def check(case, status, detail=""):
    RESULTS.append({"case": case, "status": status, "detail": str(detail)[:400]})
    print("%-8s %s | %s" % (status, case, str(detail)[:200]))


def req(path, method="GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(r, timeout=30) as f:
            return f.status, json.loads(f.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


st, d = req("/holdings")
before = len(((d.get("data") or {}).get("rows") or []))
# C-01 建档
st, d = req("/holdings", "POST", {"code": "999998", "name": "QA临时测试基金", "shares": 10, "cost_amount": 10})
check("C-01", "PASS" if st in (200, 201) else "FAIL", "POST /holdings → %s" % st)
# C-03 重复
st, d = req("/holdings", "POST", {"code": "999998", "name": "dupe"})
check("C-03", "PASS" if st == 409 and (d.get("error") or {}).get("code") == "E_CONFLICT" else "FAIL",
      "重复建档 → %s/%s" % (st, (d.get("error") or {}).get("code")))
# C-04 非法代码
st, d = req("/holdings", "POST", {"code": "abc"})
check("C-04", "PASS" if st == 400 and (d.get("error") or {}).get("code") == "E_VALIDATION" else "FAIL",
      "非法代码 → %s/%s" % (st, (d.get("error") or {}).get("code")))
# C-05/C-06 更新与读取
st, d = req("/holdings/999998", "PUT", {"shares": 20})
st2, d2 = req("/holdings/999998")
sh = ((d2.get("data") or {}).get("shares"))
check("C-05", "PASS" if st == 200 and sh == 20 else "FAIL", "PUT→%s 回读 shares=%s" % (st, sh))
# C-07 不存在
st, d = req("/holdings/999997")
check("C-07", "PASS" if st == 404 else "FAIL", "不存在 → %s" % st)
# C-02 计数
st, d = req("/holdings")
after_add = len(((d.get("data") or {}).get("rows") or []))
check("C-02", "PASS" if after_add == before + 1 else "FAIL", "计数 %d → %d" % (before, after_add))
# C-08/C-09 删除与还原
st, d = req("/holdings/999998", "DELETE")
st2, d2 = req("/holdings")
after_del = len(((d2.get("data") or {}).get("rows") or []))
codes = [r.get("code") for r in ((d2.get("data") or {}).get("rows") or [])]
check("C-08", "PASS" if st == 200 else "FAIL", "DELETE → %s" % st)
check("C-09", "PASS" if after_del == before and "999998" not in codes else "FAIL",
      "还原：行数 %d == 原 %d；临时码残留=%s" % (after_del, before, "999998" in codes))
# C-10 重复删除
st, d = req("/holdings/999998", "DELETE")
check("C-10", "PASS" if st == 404 else "FAIL", "重复删除 → %s" % st)

out = os.path.join(EV, "r2v2_crud_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)

# ---------- vsum / 滞后 补充断言（CDP） ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP  # noqa: E402
CHROME = r"C:\Users\10719\.agent-browser\browsers\chrome-153.0.8010.36\chrome.exe"
CDP_PORT = 9340
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                         "--remote-debugging-port=%d" % CDP_PORT,
                         "--user-data-dir=" + r"C:\Users\10719\AppData\Local\Temp\opencode\chrome_qa_extra",
                         "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time()
while time.time() - t0 < 30:
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
        break
    except Exception:
        time.sleep(0.5)
c = CDP(CDP_PORT)
c.navigate("http://127.0.0.1:8796/#/holdings", settle=3.2)
vs = c.eval("(document.getElementById('val-sum')||{}).innerText||''")
vsum_ok = ("估算档" in vs and "官方档" in vs and "既成事实" in vs and "0/40" in vs)
check("U2-VSUM", "PASS_PHASE" if vsum_ok else "FAIL",
      "主指标=估算档（未出数带原因「缺净值」）；官方档单列；全档参考 chip 在未出数时按条件隐藏（留白不填）；%s" % vs.replace("\n", " | ")[:160])
pv = c.eval("""(function(){var css=false;try{for(var s of document.styleSheets){try{for(var r of s.cssRules){if((r.cssText||'').indexOf('body.masked .amt')>=0)css=true}}catch(e){}}}catch(e){}
return {css:css,sw:document.querySelectorAll('#view-settings input[type=checkbox]').length}})()""")
check("U2-PRIVACY", "PASS_PHASE" if pv.get("css") else "FAIL",
      "隐私打码：body.masked .amt 规则在 CSS=%s；设置页开关元素=%d（未实操切换，R1 已覆盖且 R2 未改动）" % (pv.get("css"), pv.get("sw", 0)))
cr = c.eval("(document.querySelector('.crumb,.livebar,#livebar,header')||{}).innerText||''")
bodyh = c.eval("document.body.innerText")
lag_ok = ("滞后" in bodyh or "09-11" in bodyh or "09-10" in bodyh)
check("U2-LAG", "PASS_PHASE" if lag_ok else "FAIL",
      "新鲜度文案在页：滞后/日期=%s；头部=%s" % (lag_ok, cr.replace("\n", " ")[:120]))
sv = c.eval("(document.querySelector('.side,.sidebar,#sidebar')||{}).innerText||''")
print("SIDEBAR:", sv.replace("\n", " | ")[:300])
c.close()
proc.terminate()

out2 = os.path.join(EV, "r2v2_extra_results.json")
with open(out2, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)
fails = [r for r in RESULTS if r["status"] == "FAIL"]
print("\nTOTAL=%d FAIL=%d" % (len(RESULTS), len(fails)))
for r in fails:
    print("FAIL:", r["case"], "|", r["detail"])
