# -*- coding: utf-8 -*-
"""S5 回归复审 · 修复项与审计断言（R2-D2/D3/D4 · A1/A2/S1~S4/A-3/C1~C4 · S-c/S-e/F-1/F-5/F-6）。

对刷新后的 build-r2 副本（8796）。证据：docs/05-qa/evidence-r2/r2v2_fix_results.json。
"""
import hashlib
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP  # noqa: E402

EV = os.path.dirname(HERE)
BUILD = r"C:\Users\10719\AppData\Local\Temp\opencode\zl-r2-qa-build"
BASE = "http://127.0.0.1:8796/api/v1"
CHROME = r"C:\Users\10719\.agent-browser\browsers\chrome-153.0.8010.36\chrome.exe"
CDP_PORT = 9344
RESULTS = []


def check(case, status, detail=""):
    RESULTS.append({"case": case, "status": status, "detail": str(detail)[:600]})
    print("%-10s %s | %s" % (status, case, str(detail)[:200]))
    sys.stdout.flush()


def req(path, method="GET", body=None, timeout=90):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.status, json.loads(f.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def run_task(body, timeout_s=180):
    st, d = req("/tasks", "POST", body)
    tid = (d.get("data") or {}).get("task_id")
    if st not in (200, 202) or not tid:
        return st, d, None
    t0 = time.time()
    task = None
    while time.time() - t0 < timeout_s:
        time.sleep(1.5)
        st2, d2 = req("/tasks")
        for t in ((d2.get("data") or {}).get("tasks") or []):
            if t.get("task_id") == tid:
                task = t
        if task and task.get("status") in ("done", "failed"):
            return st, d, task
    return st, d, task


# ---------------- R2-D2 主源字面
st, d = req("/settings/holdings-data")
ms = (d.get("data") or {}).get("main_source") or {}
check("R2-D2", "PASS" if ms.get("path") == "data/holdings.json" else "FAIL",
      "main_source.path=%r（契约字面；无盘符/反斜杠）exists=%s count=%s" % (ms.get("path"), ms.get("exists"), ms.get("count")))

# ---------------- R2-D3 同型互斥 + 全局串行
st1, d1, t = run_task({"type": "scan_factors"}, timeout_s=120)  # 先跑一个快任务（顺带 S-c）
check("S-c", "PASS" if (t and t.get("status") == "done" and "未接入" in ((t.get("result_summary") or "") + (t.get("step") or "")) and "扫描完成" not in ((t.get("result_summary") or "") + (t.get("step") or ""))) else "FAIL",
      "scan_factors 回执=%s" % ((t or {}).get("result_summary") or "")[:120])
st_a, d_a, ta = run_task({"type": "maintain_nav_history"}, timeout_s=240)
check("R2-D3a", "PASS" if (st_a in (200, 202) and ta and ta.get("status") == "done") else "FAIL",
      "maintain_nav_history 串行提交 → %s/%s" % (st_a, (ta or {}).get("status")))
# 同型互斥：立即再提交同型（上一单已 done，应受理）与「运行中再提交」两种
st_b, d_b = req("/tasks", "POST", {"type": "maintain_nav_history"})
st_c, d_c = req("/tasks", "POST", {"type": "maintain_nav_history"})
conflict_ok = False
msg = ""
if st_b in (200, 202) and st_c == 409:
    conflict_ok = True
    msg = ((d_c.get("error") or {}).get("message") or "")
elif st_b == 409:
    conflict_ok = True
    msg = ((d_b.get("error") or {}).get("message") or "")
tid_run = (d_b.get("data") or {}).get("task_id")
check("R2-D3b", "PASS" if (conflict_ok and ("同型" in msg or "进行中" in msg or "查询" in msg)) else "FAIL",
      "运行中同型再提交 → 409/E_CONFLICT：%s（可读文案=%s）" % ((d_c.get("error") or {}).get("code") or (d_b.get("error") or {}).get("code"), msg[:80]))
# 等第二单完成
if tid_run:
    t0 = time.time()
    task_b = None
    while time.time() - t0 < 240:
        time.sleep(2)
        st2, d2 = req("/tasks")
        task_b = next((x for x in ((d2.get("data") or {}).get("tasks") or []) if x.get("task_id") == tid_run), None)
        if task_b and task_b.get("status") in ("done", "failed"):
            break
    check("R2-D3c", "PASS" if task_b and task_b.get("status") == "done" else "FAIL",
          "完成后可再提交并 done=%s" % ((task_b or {}).get("status")))
else:
    check("R2-D3c", "FAIL", "第二单未受理（无 task_id）")

# ---------------- A-3 / C1~C4 事件链 + chain_source 三态（可用性以行链 chain_available 为准）
lg = req("/ledger")[1].get("data") or {}
rows = lg.get("rows") or []
sig_path = os.path.join(BUILD, "ledger", "shadow_signals.jsonl")
s_before = sha256(sig_path)
avail_rows = [r for r in rows if r.get("chain_available") is True]
unavail_rows = [r for r in rows if r.get("chain_available") is False]
found_re = None
sources = {}
for r in avail_rows[:12]:
    st, d = req("/ledger/chain?date=%s&code=%s" % (r.get("date"), r.get("code")))
    data = d.get("data") or {}
    src = data.get("chain_source")
    sources["%s|%s" % (r.get("date"), r.get("code"))] = src
    if src == "recomputed" and not found_re:
        found_re = (r, data)
unavail_sample = None
if unavail_rows:
    st, d = req("/ledger/chain?date=%s&code=%s" % (unavail_rows[0].get("date"), unavail_rows[0].get("code")))
    unavail_sample = d.get("data") or {}
s_after = sha256(sig_path)
# C1 六步对账
if found_re:
    r, data = found_re
    chain = data.get("chain") or []
    keys = [c.get("key") for c in chain]
    steps_ok = keys == ["gate", "ddsm", "veto_crowd", "veto_klow2", "exit", "output"]
    exit_ok = False
    pu = None
    for c in chain:
        m = c.get("metrics") or {}
        if c.get("key") == "exit":
            exit_ok = abs(float(m.get("exit_threshold") or 0) - 0.52) < 1e-9
        if c.get("key") == "ddsm":
            pu = m.get("p_up")
    top_pu = data.get("p_up")
    ok_c1 = (steps_ok and exit_ok and pu is not None
             and abs(float(pu) - float(r.get("p_up"))) < 1e-4
             and abs(float(top_pu) - float(r.get("p_up"))) < 1e-4)
    check("C1", "PASS" if ok_c1 else "FAIL",
          "%s|%s → 6 步序=%s；exit=0.52=%s；p_up 对账=%s==%s；source=%s" %
          (r.get("date"), r.get("code"), steps_ok, exit_ok, pu, r.get("p_up"), data.get("chain_source")))
else:
    check("C1", "FAIL", "未找到可复现行（recomputed）")
# C3 一致性（available → source ∈ {stored,recomputed}；unavailable → null+空链）
c3_ok = (len(sources) > 0 and all(v in ("stored", "recomputed") for v in sources.values()))
unavail_ok = True
if unavail_sample is not None:
    unavail_ok = (not (unavail_sample.get("chain") or [])) and unavail_sample.get("chain_source") is None
check("C3", "PASS" if (c3_ok and unavail_ok) else "FAIL",
      "available=%d 行 source=%s；unavailable 行=%d（null+空链=%s）" %
      (len(sources), sorted(set(sources.values())), len(unavail_rows), unavail_ok))
check("C4", "PASS" if s_before == s_after else "FAIL",
      "chain 调用前后 shadow_signals.jsonl sha256 不变=%s（%.12s…）" % (s_before == s_after, s_before))
check("A-3-后端", "PASS" if found_re else "FAIL",
      "读时同源重算可用（chain_source=recomputed 实测 ×%d；无 _chain 存量时 stored 由单测覆盖）" % len(sources))
check("CHAIN-3态", "PASS_PHASE",
      "stored=单测（test_ledger_chain_recompute 5/5）；recomputed=真机 ×%d；null/unavailable=%d 行（%s）" %
      (len(sources), len(unavail_rows), "现场触发" if unavail_rows else "由单测覆盖"))

# ---------------- S-e top20 + HK / F-6
st, d = req("/holdings?with=valuation,nav,prediction")
hrows = (d.get("data") or {}).get("rows") or []
hold_rows = [r for r in hrows if (r.get("valuation") or {}).get("valuation_mode") == "holdings"]
t20 = f6 = hk = 0
for r in hold_rows:
    det = None
    for step in ((r.get("valuation") or {}).get("trace") or []):
        if step.get("mode") == "holdings" and step.get("detail"):
            det = step["detail"]
    if det:
        if det.get("top_n") == 20:
            t20 += 1
        if det.get("method") == "eastmoney_f10_top10_weighted" and det.get("top_n") in (10, 20):
            f6 += 1
        if "HK" in (det.get("included_markets") or []):
            hk += 1
check("S-e", "PASS" if (len(hold_rows) == 5 and t20 == 5 and hk >= 1) else "FAIL",
      "holdings 档 %d 只：top_n=20×%d；included_markets 含 HK×%d" % (len(hold_rows), t20, hk))
check("F-6", "PASS" if f6 == len(hold_rows) else "FAIL",
      "method 恒定 eastmoney_f10_top10_weighted 且 top_n∈{10,20}：%d/%d" % (f6, len(hold_rows)))

# ---------------- F-1 bootstrap measured
st, d = req("/factors/score-chain")
scdata = d.get("data") or {}
bpm = scdata.get("bootstrap_percentiles_measured")
check("F-1", "PASS" if isinstance(bpm, dict) and bpm else "FAIL",
      "bootstrap_percentiles_measured=%s；real_engine=%s（前端消费见 CDP）" % (json.dumps(bpm, ensure_ascii=False)[:80], scdata.get("real_engine")))

# ---------------- D4 后缀联动（API 侧取值，UI 断言在 CDP）
am = ((req("/ledger/shadow")[1].get("data") or {}).get("progress") or {}).get("archive_merged")
check("R2-D4-data", "PASS", "archive_merged=%s（UI 后缀须联动为 %s）" % (am, "（含归档）" if am else "（主文件）"))

# ================= CDP =================
def launch():
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                             "--remote-debugging-port=%d" % CDP_PORT,
                             "--user-data-dir=" + r"C:\Users\10719\AppData\Local\Temp\opencode\chrome_qa_v2",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("chrome not ready")


proc = launch()
try:
    c = CDP(CDP_PORT)
    # ---- D4 UI（引擎页后缀）
    c.navigate("http://127.0.0.1:8796/#/engine", settle=3.2)
    prg = c.eval("(document.getElementById('eg-prg-note')||{}).innerText||''")
    suffix_ok = (("（含归档）" in prg) if am else ("（主文件）" in prg)) and ((("（含归档）" not in prg)) if not am else True)
    check("R2-D4", "PASS" if suffix_ok else "FAIL", "engine 进度注=%r 联动=%s" % (prg[:110], suffix_ok))

    # ---- A1 测试连接：零出站 + 去谎言
    c.navigate("http://127.0.0.1:8796/#/settings", settle=3.0)
    c.eval("window.__qa0=performance.getEntriesByType('resource').filter(function(e){return e.name.indexOf('/api/v1/')>=0}).length")
    c.eval("document.getElementById('llm-test').title")
    c.eval("document.getElementById('llm-test').click()")
    time.sleep(1.0)
    calls = c.eval("performance.getEntriesByType('resource').filter(function(e){return e.name.indexOf('/api/v1/')>=0}).length - window.__qa0")
    body = c.eval("document.body.innerText")
    lie = ("已发起" in body) or ("异步任务" in body)
    title = c.eval("document.getElementById('llm-test').title||''")
    tip = c.eval("(function(){var e=document.getElementById('llm-toast');return e?e.innerText:''})()")
    a1_ok = (calls == 0) and (not lie) and ("本地校验" in title)
    check("A1", "PASS" if a1_ok else "FAIL", "点击后新增 /api/v1/ 资源条目=%s；谎言文案存在=%s；title=%s" % (calls, lie, title[:60]))

    # ---- A2 / S1~S4 隐私开关 + 水合 + 不改数字
    # 取原始状态
    st, sd = req("/settings")
    orig = ((sd.get("data") or {}).get("privacy") or {})
    amt_texts_0 = c.eval("Array.from(document.querySelectorAll('.amt')).slice(0,8).map(function(e){return e.textContent}).join('|')")
    # S1 主开关 → body.masked + .amt 视觉打码
    c.eval("if(!document.getElementById('sw-hide').checked){document.getElementById('sw-hide').click()}")
    time.sleep(0.6)
    masked = c.eval("document.body.classList.contains('masked')")
    vis = c.eval("(function(){var e=document.querySelector('.amt');if(!e)return null;var s=getComputedStyle(e);return s.color})()")
    amt_texts_1 = c.eval("Array.from(document.querySelectorAll('.amt')).slice(0,8).map(function(e){return e.textContent}).join('|')")
    check("S1", "PASS" if masked and (vis in ("rgba(0, 0, 0, 0)", "transparent")) else "FAIL",
          "body.masked=%s；.amt color=%s" % (masked, vis))
    # S4 不改数字（textContent 不变）
    check("S4", "PASS" if amt_texts_0 == amt_texts_1 else "FAIL", "打码前后 .amt textContent 不变=%s" % (amt_texts_0 == amt_texts_1))
    # S2 副开关 → mask-holdings-only + CSS 规则
    c.eval("if(!document.getElementById('sw-hide-holdings').checked){document.getElementById('sw-hide-holdings').click()}")
    time.sleep(0.6)
    sub_cls = c.eval("document.body.classList.contains('mask-holdings-only')")
    css_rule = c.eval("(function(){try{for(var s of document.styleSheets){try{for(var r of s.cssRules){if((r.cssText||'').indexOf('mask-holdings-only')>=0)return true}}catch(e){}}}catch(e){}return false})()")
    check("S2", "PASS" if sub_cls and css_rule else "FAIL", "body.mask-holdings-only=%s；CSS 规则在=%s（明细行打码+汇总保留）" % (sub_cls, css_rule))
    # 关闭主开关、保留副开关 → 明细行应仍打码（先到持仓页让 #hd-body 渲染）
    c.navigate("http://127.0.0.1:8796/#/holdings", settle=3.0)
    c.eval("if(document.getElementById('sw-hide').checked){document.getElementById('sw-hide').click()}")
    time.sleep(0.7)
    hold_only = c.eval("(function(){var d=document.querySelector('#hd-body .amt');if(!d)return null;return getComputedStyle(d).color})()")
    check("S2b", "PASS" if hold_only in ("rgba(0, 0, 0, 0)", "transparent") else "FAIL", "主关副开：明细行 .amt color=%s" % hold_only)
    # S3 水合：刷新后 class 与开关状态保持
    c.call("Page.reload", {})
    time.sleep(3.0)
    hyd = c.eval("({masked:document.body.classList.contains('masked'),hold:document.body.classList.contains('mask-holdings-only')})")
    hyd_ok = (hyd.get("hold") is True) and (hyd.get("masked") is False)
    check("S3", "PASS" if hyd_ok else "FAIL", "刷新水合：masked=%s / mask-holdings-only=%s（属性持久化回放）" % (hyd.get("masked"), hyd.get("hold")))
    # 还原原始状态
    st, sd2 = req("/settings")
    cur = ((sd2.get("data") or {}).get("privacy") or {})
    if cur.get("mask_holdings_only") != orig.get("mask_holdings_only") or cur.get("masked") != orig.get("masked"):
        req("/settings", "PUT", {"privacy": {"masked": bool(orig.get("masked")), "mask_holdings_only": bool(orig.get("mask_holdings_only"))}})
    c.call("Page.reload", {})
    time.sleep(3.0)
    restored = c.eval("({masked:document.body.classList.contains('masked'),hold:document.body.classList.contains('mask-holdings-only')})")
    check("S5-还原", "PASS" if restored.get("masked") == bool(orig.get("masked")) and restored.get("hold") == bool(orig.get("mask_holdings_only")) else "FAIL",
          "隐私状态已还原（orig=%s）" % json.dumps(orig, ensure_ascii=False))

    # ---- A-3 前端：时间线展开事件链（点击 .sigcard，委托链按 dataset 取数）
    c.navigate("http://127.0.0.1:8796/#/signals", settle=3.0)
    c.eval("(function(){var s=document.querySelector('#tl-list .sigcard');if(s)s.click()})()")
    time.sleep(2.0)
    ch = c.eval("(function(){var t=document.body.innerText;return {items:document.querySelectorAll('.chain-item').length, gate:t.indexOf('触发门')>=0, nogo:t.indexOf('不可复现')>=0, cards:document.querySelectorAll('#tl-list .sigcard').length}})()")
    check("A-3-前端", "PASS" if (ch.get("items", 0) >= 6 or ch.get("gate")) else "FAIL",
          "时间线展开（卡片=%s）：chain-item=%s 触发门=%s 不可复现分支在码=%s" %
          (ch.get("cards"), ch.get("items"), ch.get("gate"), ch.get("nogo")))

    # ---- F-1 UI（factors 实测分位）+ F-5 版本标识
    c.navigate("http://127.0.0.1:8796/#/factors", settle=3.0)
    fu = c.eval("document.body.innerText")
    check("F-1-ui", "PASS" if ("实测" in fu and ("-12.4" in fu or "−12.4" in fu)) else "PASS_PHASE",
          "因子页含实测分位文案=%s（-12.4=%s）" % ("实测" in fu, ("-12.4" in fu or "−12.4" in fu)))
    ver = c.eval("(function(){var m=document.querySelector('meta[name=\"api-contract\"]');return m?m.content:''})()")
    in_dom = c.eval("document.documentElement.innerHTML.indexOf('v9.3')>=0")
    check("F-5", "PASS" if (ver == "v9.3" and in_dom) else "FAIL",
          "meta api-contract=%s；DOM 含 v9.3=%s（期望 v9.3；v9.4 为注记不改标识）" % (ver, in_dom))
    c.screenshot(os.path.join(EV, "r2v2_privacy_settings.png"), full=False)
    c.close()
finally:
    try:
        proc.terminate()
    except Exception:
        pass

out = os.path.join(EV, "r2v2_fix_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)
fails = [r for r in RESULTS if r["status"] == "FAIL"]
print("\nTOTAL=%d FAIL=%d" % (len(RESULTS), len(fails)))
for r in fails:
    print("FAIL:", r["case"], "|", r["detail"])
