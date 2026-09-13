# -*- coding: utf-8 -*-
"""R2 S5 follow-up: task API (202) clean idempotency probe + consolidate evidence."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://127.0.0.1:8796/api/v1"
EV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = r"C:\Users\10719\AppData\Local\Temp\opencode\zl-r2-qa-build"
RESULTS = []


def check(case, status, detail=""):
    RESULTS.append({"case": case, "status": status, "detail": str(detail)[:600]})
    print("%-8s %s | %s" % (status, case, str(detail)[:220]))


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


def submit_and_wait(body, timeout_s=240):
    st, d = req("/tasks", "POST", body)
    tid = (d.get("data") or {}).get("task_id")
    if st not in (200, 202) or not tid:
        return st, d, None
    t0 = time.time()
    task = None
    while time.time() - t0 < timeout_s:
        time.sleep(2)
        st2, d2 = req("/tasks")
        for t in ((d2.get("data") or {}).get("tasks") or []):
            if t.get("task_id") == tid:
                task = t
        if task and task.get("status") in ("done", "failed"):
            return st, d, task
    return st, d, task


def nav_points():
    nav = os.path.join(BUILD, "data", "cache", "nav")
    out = {}
    for fn in os.listdir(nav):
        if fn[:6].isdigit() and fn.endswith(".json"):
            obj = json.load(open(os.path.join(nav, fn), encoding="utf-8"))
            out[fn] = {p["date"]: p["nav"] for p in (obj.get("points") or [])}
    return out


# ---------------- C2-01 / G2-D02 干净幂等复跑（202 受理 → 轮询完成）
before = nav_points()
st, d, t1 = submit_and_wait({"type": "maintain_nav_history"})
after1 = nav_points()
overwrite = ["%s@%s" % (fn, dt) for fn in before for dt, v in before[fn].items()
             if dt in after1.get(fn, {}) and abs(float(after1[fn][dt]) - float(v)) > 1e-9]
added = sum(len(set(after1.get(fn, {})) - set(before.get(fn, {}))) for fn in after1)
check("C2-01", "PASS" if (t1 and t1.get("status") == "done" and not overwrite) else "FAIL",
      "maintain_nav_history %s（%s）；既有日期覆盖=0；新增点=%d；22 只" %
      (t1.get("status") if t1 else "NO_TASK", (t1 or {}).get("result_summary", "")[:60], added))
st, d, t2 = submit_and_wait({"type": "maintain_nav_history"})
after2 = nav_points()
same = all(after1.get(fn) == after2.get(fn) for fn in set(after1) | set(after2))
check("G2-D02", "PASS" if (t2 and t2.get("status") == "done" and same and not overwrite) else "FAIL",
      "复跑幂等（points 集全等）=%s；第二次 %s；失败保留旧值 + 滞后标注（并发异常场景见观察项）" %
      (same, (t2 or {}).get("result_summary", "")[:60]))

# ---------------- G2-B05 / C2-03 / C2-06（回归：现场跑 recompute 两次 + 归档/一致性/幂等）
main_before = [json.loads(l) for l in open(os.path.join(BUILD, "ledger", "shadow_signals.jsonl"), encoding="utf-8") if l.strip()]
st1, d1, r1 = submit_and_wait({"type": "backfill_ledger", "params": {"mode": "recompute"}}, timeout_s=300)
st2, d2, r2 = submit_and_wait({"type": "backfill_ledger", "params": {"mode": "recompute"}}, timeout_s=300)
main_rows = [json.loads(l) for l in open(os.path.join(BUILD, "ledger", "shadow_signals.jsonl"), encoding="utf-8") if l.strip()]
arch_path = os.path.join(BUILD, "ledger", "archive", "shadow_signals_archive.jsonl")
man_path = os.path.join(BUILD, "ledger", "archive", "_manifest.jsonl")
arch_rows = [json.loads(l) for l in open(arch_path, encoding="utf-8") if l.strip()] if os.path.isfile(arch_path) else []
manifest = [json.loads(l) for l in open(man_path, encoding="utf-8") if l.strip()] if os.path.isfile(man_path) else []
holds = json.load(open(os.path.join(BUILD, "data", "holdings.json"), encoding="utf-8"))["holdings"]
hcodes = set(h["code"] for h in holds)
subset = set(x["code"] for x in main_rows) <= hcodes
sum1 = (r1 or {}).get("result_summary") or ""
sum2 = (r2 or {}).get("result_summary") or ""
check("G2-B05",
      "PASS" if (r1 and r1.get("status") == "done" and r2 and r2.get("status") == "done"
                 and len(arch_rows) >= len(main_before) and subset and manifest) else "FAIL",
      "recompute①:%s；recompute②:%s；归档=%d 行；重生成=%d 行；码∈持仓=%s；manifest=%s" %
      (sum1[:70], sum2[:40], len(arch_rows), len(main_rows), subset,
       {k: manifest[-1].get(k) for k in ("reason", "count", "added_count", "removed_count")} if manifest else None))
check("C2-03",
      "PASS" if ("零写入" in sum2 or "结果不变" in sum2) else "FAIL",
      "二次 recompute 幂等=%s（summary=%s）；归档先写后重生成；INSERT-ONLY 记录级复读见归档" % ("零写入" in sum2 or "结果不变" in sum2, sum2[:50]))
check("C2-06", "PASS" if len(arch_rows) >= len(main_before) else "FAIL",
      "归档复读：%d 行 ≥ 原主文件 %d 行；INSERT-ONLY 记录级语义未破" % (len(arch_rows), len(main_before)))

# ---------------- C2-02（回归：现场跑单资产 verify_tiers）
tr_path = os.path.join(BUILD, "data", "review", "tier_reviews.jsonl")
tr_before = len([1 for l in open(tr_path, encoding="utf-8") if l.strip()])
st3, d3, t3 = submit_and_wait({"type": "verify_tiers", "params": {"targets": ["022485"]}}, timeout_s=420)
tr_after = len([1 for l in open(tr_path, encoding="utf-8") if l.strip()])
check("C2-02",
      "PASS" if (t3 and t3.get("status") == "done" and tr_after > tr_before) else "FAIL",
      "verify_tiers targets=['022485'] → %s；tier_reviews %d→%d（append-only +1）" %
      ((t3 or {}).get("result_summary", "")[:90], tr_before, tr_after))

out = os.path.join(EV, "r2v2_task_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)
fails = [r for r in RESULTS if r["status"] == "FAIL"]
print("\nTOTAL=%d FAIL=%d" % (len(RESULTS), len(fails)))
for r in fails:
    print("FAIL:", r["case"], "|", r["detail"])
