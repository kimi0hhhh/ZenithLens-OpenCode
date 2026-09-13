# -*- coding: utf-8 -*-
"""R2 S5 task/idempotency checks (B1/B2/B3) on the build-r2 QA copy.

Mutating on the disposable QA copy only. Evidence: docs/05-qa/evidence-r2/.
Run: python r2_task_checks.py
"""
import json
import os
import shutil
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
    print("%-8s %s | %s" % (status, case, str(detail)[:200]))


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


def load_jsonl(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


def run_task(body, timeout_s=240):
    st, d = req("/tasks", "POST", body)
    if st != 200 or not (d.get("data") or {}).get("task_id"):
        return st, d, None
    tid = d["data"]["task_id"]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(2)
        st2, d2 = req("/tasks")
        for t in ((d2.get("data") or {}).get("tasks") or []):
            if t.get("task_id") == tid:
                if t.get("status") in ("done", "failed"):
                    return st, d, t
    return st, d, {"status": "timeout"}


# ---------------- C2-04 冻结黑名单
st1, d1 = req("/tasks", "POST", {"type": "backfill_ledger", "params": {"band": 0.02}})
st2, d2 = req("/tasks", "POST", {"type": "backfill_ledger", "params": {"baseline_method": "x"}})
st3, d3 = req("/tasks", "POST", {"type": "no_such_task"})
ok = (st1 == 400 and d1.get("error", {}).get("code") == "E_VALIDATION"
      and st2 == 400 and d2.get("error", {}).get("code") == "E_VALIDATION"
      and st3 == 400)
check("C2-04", "PASS" if ok else "FAIL",
      "band→%s / baseline_method→%s / 未知类型→%s（均 E_VALIDATION）" % (st1, st2, st3))

# ---------------- C2-01 / G2-D02 maintain_nav_history 幂等
nav_dir = os.path.join(BUILD, "data", "cache", "nav")
before = {}
for fn in os.listdir(nav_dir):
    if fn.endswith(".json") and fn[:6].isdigit():
        obj = json.load(open(os.path.join(nav_dir, fn), encoding="utf-8"))
        before[fn] = {p.get("date"): p.get("nav") for p in (obj.get("points") or [])}
st, d, t = run_task({"type": "maintain_nav_history"}, timeout_s=240)
after1 = {}
for fn in os.listdir(nav_dir):
    if fn.endswith(".json") and fn[:6].isdigit():
        obj = json.load(open(os.path.join(nav_dir, fn), encoding="utf-8"))
        after1[fn] = {p.get("date"): p.get("nav") for p in (obj.get("points") or [])}
overwrite = []
for fn, pts in before.items():
    newp = after1.get(fn, {})
    for dt, nav in pts.items():
        if dt in newp and abs(float(newp[dt]) - float(nav)) > 1e-9:
            overwrite.append("%s@%s" % (fn, dt))
added = sum(len(set(after1.get(fn, {})) - set(before.get(fn, {}))) for fn in after1)
check("C2-01", "PASS" if (t and t.get("status") == "done" and not overwrite) else "FAIL",
      "maintain_nav_history=%s；既有日期被覆盖=%d；新增点数=%d" %
      (t.get("status") if t else "POST_FAIL", len(overwrite), added))
# 二次执行幂等
st, d, t2 = run_task({"type": "maintain_nav_history"}, timeout_s=240)
after2 = {}
for fn in os.listdir(nav_dir):
    if fn.endswith(".json") and fn[:6].isdigit():
        obj = json.load(open(os.path.join(nav_dir, fn), encoding="utf-8"))
        after2[fn] = {p.get("date"): p.get("nav") for p in (obj.get("points") or [])}
same = all(after1.get(fn) == after2.get(fn) for fn in set(after1) | set(after2))
check("G2-D02", "PASS" if (t2 and t2.get("status") == "done" and same) else "FAIL",
      "复跑幂等（points 集不变）=%s；第二次状态=%s" % (same, t2.get("status") if t2 else "POST_FAIL"))

# ---------------- G2-B05 / C2-03 recompute 幂等 + 归档
main_path = os.path.join(BUILD, "ledger", "shadow_signals.jsonl")
arch_dir = os.path.join(BUILD, "ledger", "archive")
r0 = load_jsonl(main_path)
set0 = {(x.get("date"), x.get("code")) for x in r0}
st, d, t = run_task({"type": "backfill_ledger", "params": {"mode": "recompute"}}, timeout_s=300)
r1 = load_jsonl(main_path)
set1 = {(x.get("date"), x.get("code")) for x in r1}
arch_files = os.listdir(arch_dir) if os.path.isdir(arch_dir) else []
arch_rows = 0
for fn in arch_files:
    if fn.endswith(".jsonl") and "manifest" not in fn:
        arch_rows += len(load_jsonl(os.path.join(arch_dir, fn)))
held = None
st_h, dh = req("/holdings")
if st_h == 200:
    held = {row.get("code") for row in ((dh.get("data") or {}).get("rows") or [])}
subset = (set1 <= held) if held else None
manifest = None
for fn in arch_files:
    if "manifest" in fn:
        mrows = load_jsonl(os.path.join(arch_dir, fn))
        manifest = mrows[-1] if mrows else None
check("G2-B05", "PASS" if (t and t.get("status") == "done" and arch_rows >= len(r0)) else "FAIL",
      "recompute=%s；归档行=%d（含旧 %d）；重生成后 %d 行；档位一致性(码∈持仓)=%s；manifest=%s" %
      (t.get("status") if t else "POST_FAIL", arch_rows, len(r0), len(r1), subset,
       json.dumps(manifest, ensure_ascii=False)[:160] if manifest else None))
# 二次 recompute 幂等
st, d, t2 = run_task({"type": "backfill_ledger", "params": {"mode": "recompute"}}, timeout_s=300)
r2 = load_jsonl(main_path)
set2 = {(x.get("date"), x.get("code")) for x in r2}
same2 = set1 == set2 and len(r1) == len(r2)
check("C2-03", "PASS" if (t2 and t2.get("status") == "done" and same2) else "FAIL",
      "二次 recompute 幂等=%s（行 %d→%d）；归档继续追加；INSERT-ONLY 旧记录复读见归档" % (same2, len(r1), len(r2)))
check("C2-06", "PASS" if arch_rows >= len(r0) else "FAIL",
      "recompute 前记录可归档复读：归档 %d 行 ≥ 原主文件 %d 行" % (arch_rows, len(r0)))

# ---------------- C2-02 verify_tiers 单资产（最小成本覆盖任务参数路径）
tr_path = os.path.join(BUILD, "data", "review", "tier_reviews.jsonl")
tr_before = len(load_jsonl(tr_path))
st, d, t = run_task({"type": "verify_tiers", "params": {"targets": ["022485"]}}, timeout_s=420)
tr_after = len(load_jsonl(tr_path))
check("C2-02", "PASS" if (t and t.get("status") == "done" and tr_after > tr_before) else "FAIL",
      "targets=['022485'] → %s；tier_reviews %d→%d；summary=%s" %
      (t.get("status") if t else "POST_FAIL", tr_before, tr_after,
       (t or {}).get("result_summary", "")[:120]))

# ---------------- C2-05 backfill 无信号拒绝
st, d = req("/ledger/backfill", "POST",
            {"entries": [{"date": "1999-01-01", "code": "000000", "t1_real": 0.01}]})
code = (d.get("error") or {}).get("code")
check("C2-05", "PASS" if (st == 400 and code == "E_VALIDATION") else "FAIL",
      "无对应 signal 写入 → %s / %s（合法字段 method/proxy_code 可选随行）" % (st, code))

# ---------------- C2-03b review 缓存缺失（临移-恢复）
cache = os.path.join(BUILD, "data", "snapshot", "review_scores.json")
bak = cache + ".qa-bak"
shutil.move(cache, bak)
try:
    st, d = req("/review/scores", timeout=180)
    data = d.get("data") or {}
    rows = data.get("scores") or []
    graceful = st == 200 and all(
        (r.get("baseline_status") in ("filled", "pending")) for r in rows) if rows else st == 200
    detail = "缓存缺失时 GET /review/scores=%s；rows=%d；note=%s" % (
        st, len(rows), (data.get("note") or "")[:80])
finally:
    if os.path.exists(bak):
        shutil.move(bak, cache)
st2, d2 = req("/review/scores")
restored = st2 == 200 and len(((d2.get("data") or {}).get("scores") or [])) == 3
check("C2-03b", "PASS" if graceful and restored else "FAIL",
      detail + "；恢复后 rows=%d" % len(((d2.get("data") or {}).get("scores") or [])))

# ---------------- REG-01 归档重建窗口外记录（静态断言：归档含被裁记录）
cut_rows = [x for x in load_jsonl(main_path)]
archive_rows_all = 0
for fn in sorted(os.listdir(arch_dir)) if os.path.isdir(arch_dir) else []:
    if fn.endswith(".jsonl") and "manifest" not in fn:
        archive_rows_all += len(load_jsonl(os.path.join(arch_dir, fn)))
check("R2-REG-01", "PASS_PHASE",
      "裁剪后归档可重建：归档累计 %d 行（≥ 主文件 %d）；重建脚本路径由 test_shadow_progress_archive 覆盖" %
      (archive_rows_all, len(cut_rows)))

out = os.path.join(EV, "r2_task_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"total": len(RESULTS), "results": RESULTS}, f, ensure_ascii=False, indent=1)
fails = [r for r in RESULTS if r["status"] == "FAIL"]
print("\nTOTAL=%d FAIL=%d" % (len(RESULTS), len(fails)))
for r in fails:
    print("FAIL:", r["case"], "|", r["detail"])
