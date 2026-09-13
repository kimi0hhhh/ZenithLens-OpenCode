# -*- coding: utf-8 -*-
"""OC-SHADOWSTAT-FE 前端断言：HUD 影子盘进度语义（真后端 8791 + CDP 9333）。

阶段 A（真后端）：/engine/status 进度语义 + HUD「记录中 20/60」+ 偏差审查单独表达。
阶段 B（桩，逐枚举）：not_started/recording/qualified/gap × idle/ok/bad 各自文案正确。
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\05-qa\evidence\scripts")
from cdp import CDP

PORT = 9333
BASE = "http://127.0.0.1:8791"
EV = r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\02-frontend\evidence"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" | " + str(detail)) if detail else ""))


def api(path):
    return json.load(urllib.request.urlopen(BASE + "/api/v1" + path, timeout=30))


c = CDP(PORT)
c.call("Network.enable")
c.call("Network.setCacheDisabled", {"cacheDisabled": True})

# ---- 后端真实形状（证据锚点） ----
st = api("/engine/status")["data"]
check("后端 shadow_status 为进度语义", st.get("shadow_status") in ("not_started", "recording", "qualified", "gap"), st.get("shadow_status"))
check("后端保留 shadow_audit_status（idle/ok/bad）", st.get("shadow_audit_status") in ("idle", "ok", "bad"), st.get("shadow_audit_status"))
check("后端 consecutive/target = 20/60", st.get("shadow_consecutive_days") == 20 and st.get("shadow_target_days") == 60,
      (st.get("shadow_consecutive_days"), st.get("shadow_target_days")))

# ============ 阶段 A：真后端 ============
c.navigate(BASE + "/?v=SP#/engine", settle=6.0)
time.sleep(5.0)
hud = c.eval("(document.getElementById('eg-hud')||{}).innerText||''")
card = c.eval("(document.querySelector('#eg-hud .hud-c')||{}).innerText||''")
check("A HUD 影子盘卡显示「记录中」", "记录中" in card, json.dumps(card, ensure_ascii=True))
check("A HUD 显示 20 / 60", "20 / 60" in card, json.dumps(card, ensure_ascii=True))
check("A 偏差审查单独表达（未评估），不混入进度", "偏差" in card and "未评估" in card, json.dumps(card, ensure_ascii=True))
check("A 引擎页不含「影子盘未启动」", "影子盘未启动" not in hud)
check("A HUD 进度条存在", c.eval("document.querySelectorAll('#eg-hud .hud-c .prg').length") >= 1,
      c.eval("document.querySelectorAll('#eg-hud .hud-c .prg').length"))
c.screenshot(EV + r"\zl_shadow_progress_engine.png")

# ============ 阶段 B：桩，逐枚举 ============
STUB = r"""
(function () {
  var real = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : ((input && input.url) || '');
    var m = /[?&]sstatus=([a-z_]+)/.exec(location.search);
    if (url.indexOf('/api/v1/engine/status') >= 0 && m) {
      var a = /[?&]saudit=([a-z]+)/.exec(location.search);
      return real(input, init).then(function (res) {
        return res.clone().json().then(function (env) {
          env.data.shadow_status = m[1];
          if (a) env.data.shadow_audit_status = a[1];
          return new Response(JSON.stringify(env), { status: res.status, headers: { 'Content-Type': 'application/json' } });
        });
      });
    }
    return real(input, init);
  };
})();
"""
c.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})

CASES = [
    ("recording", "ok", ["记录中", "20 / 60", "达标"]),
    ("qualified", "bad", ["已达标", "降级"]),
    ("not_started", "idle", ["未启动", "未评估"]),
    ("gap", "ok", ["有缺口", "达标"]),
]
for i, (ps, au, wants) in enumerate(CASES):
    c.navigate(BASE + "/?v=SPB%d&sstatus=%s&saudit=%s#/engine" % (i, ps, au), settle=6.0)
    time.sleep(4.5)
    card = c.eval("(document.querySelector('#eg-hud .hud-c')||{}).innerText||''")
    for w in wants:
        check("B %s/%s -> 含「%s」" % (ps, au, w), w in card, json.dumps(card, ensure_ascii=True))
    check("B %s/%s 无「—」占位" % (ps, au), "—" not in card.split("偏差")[0], json.dumps(card, ensure_ascii=True))

fails = [r for r in results if not r[1]]
print("TOTAL %d PASS %d FAIL %d" % (len(results), len(results) - len(fails), len(fails)))
c.close()
sys.exit(1 if fails else 0)
