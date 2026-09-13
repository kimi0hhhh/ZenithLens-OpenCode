# -*- coding: utf-8 -*-
"""S4 复验 · 冷启动探针 + /review/scores 逐条对账（独立复验，不依赖后端脚本）。

覆盖：
- 起服 → /health ready → ready+1s /holdings 计时（S3 验收口径）→ ready+6s 复测；
- /review/scores：backtest / shadow_live 两口径（B1-1/3/4/5/6）；formula ↔ 定义（B1-2）；
- review_verdict n_test 支路直调（B1-8）；
- /data-sources/health 新浪 (b) 标注（S2）。
输出：coldstart_s4.json + 控制台。
"""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8791
BASE = "http://127.0.0.1:%d/api/v1" % PORT

results = []


def check(name, ok, detail=""):
    results.append({"check": name, "pass": bool(ok), "detail": str(detail)[:300]})
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         (" | " + str(detail)[:160]) if detail else ""))


def get(path, timeout=30):
    t0 = time.perf_counter()
    status, env = 0, None
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            status, env = r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            env = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            env = None
    except Exception as e:  # noqa: BLE001
        env = {"ok": False, "error": {"code": "E_CONNECT", "message": str(e)}}
    return status, env, int((time.perf_counter() - t0) * 1000)


def port_in_use(port):
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        s.close()


def main():
    if port_in_use(PORT):
        print("port %d already in use; abort" % PORT)
        return 2
    out_log = io.open(os.path.join(HERE, "coldstart_s4.out.log"), "w",
                      encoding="utf-8")
    err_log = io.open(os.path.join(HERE, "coldstart_s4.err.log"), "w",
                      encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=SRC,
                            stdout=out_log, stderr=err_log)
    t_start = time.perf_counter()
    ready = None
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(BASE + "/health", timeout=1) as r:
                    if json.loads(r.read().decode("utf-8")).get("ok"):
                        ready = time.perf_counter() - t_start
                        break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
        check("ready（/health ok）", ready is not None,
              "%.2fs" % ready if ready else "timeout")
        if ready is None:
            return 2

        time.sleep(max(0.0, 1.0 - (time.perf_counter() - t_start - ready)))
        st, env, ms1 = get("/holdings?with=valuation,nav,prediction", timeout=30)
        rows = ((env or {}).get("data") or {}).get("rows") or []
        check("ready+1s /holdings 200", st == 200 and (env or {}).get("ok"), "st=%s" % st)
        check("ready+1s /holdings <1s", ms1 < 1000, "%dms rows=%d" % (ms1, len(rows)))

        time.sleep(max(0.0, 6.0 - (time.perf_counter() - t_start - ready)))
        st2, env2, ms2 = get("/holdings?with=valuation,nav,prediction", timeout=30)
        rows2 = ((env2 or {}).get("data") or {}).get("rows") or []
        check("ready+6s /holdings 200 且 <1s",
              st2 == 200 and ms2 < 1000, "%dms rows=%d" % (ms2, len(rows2)))

        # ---- /review/scores backtest ----
        st3, env3, ms3 = get("/review/scores?data_kind=backtest")
        d3 = (env3 or {}).get("data") or {}
        sc = d3.get("scores") or []
        raw3 = json.dumps(d3, ensure_ascii=False)
        check("backtest 3 行", len(sc) == 3, [r.get("window") for r in sc])
        t1, t3, t15 = (sc + [{}, {}, {}])[:3]
        check("T1 非空（filled）", t1.get("baseline_status") == "filled"
              and t1.get("hit_rate") is not None,
              {k: t1.get(k) for k in ("hit_rate", "baseline_rate", "delta_pp", "open_count", "baseline_status")})
        for row, label in ((t3, "T3"), (t15, "T15")):
            check("%s pending + null + open_count=0" % label,
                  row.get("baseline_status") == "pending"
                  and row.get("hit_rate") is None and row.get("baseline_rate") is None
                  and row.get("delta_pp") is None and row.get("open_count") == 0,
                  {k: row.get(k) for k in ("hit_rate", "baseline_rate", "open_count")})
        check("全文 baseline_status ∈ {filled,pending}（无 ok）",
              '"baseline_status": "ok"' not in raw3 and '"baseline_status": "filled"' in raw3
              and '"baseline_status": "pending"' in raw3)
        check("sample_window 恒 full", all(r.get("sample_window") == "full" for r in sc))
        hero = d3.get("hero") or {}
        check("hero == T1 值/状态", hero.get("hit_rate") == t1.get("hit_rate")
              and hero.get("baseline_rate") == t1.get("baseline_rate")
              and hero.get("delta_pp") == t1.get("delta_pp")
              and hero.get("open_count") == t1.get("open_count")
              and hero.get("data_kind") == "backtest")
        check("note 含 pending_cv + 待验证",
              "pending_cv" in (d3.get("note") or "") and "待验证" in (d3.get("note") or ""),
              d3.get("note", "")[:80])
        check("T3/T15 formula 保留定式标签",
              t3.get("formula") == "gate_only" and t15.get("formula") == "gate+ddsm",
              [t3.get("formula"), t15.get("formula")])

        # ---- B1-2 formula ↔ 定义 ----
        sys.path.insert(0, SRC)
        import factor_engine  # noqa: E402
        defn = factor_engine.production_definition(1)
        check("production_definition.formula = gate+ddsm+veto",
              defn.get("formula") == "gate+ddsm+veto", defn.get("formula"))
        check("T1 row formula == 计算定义 formula",
              t1.get("formula") == defn.get("formula"),
              "%s vs %s" % (t1.get("formula"), defn.get("formula")))

        # ---- B1-8 review_verdict n_test 支路 ----
        ev = {"has_data": True, "independent_trigger_days": 30, "lift_full": 1.2,
              "delta_full": 0.02}
        v_hold = factor_engine.review_verdict(dict(ev, n_test=15))
        v_pass = factor_engine.review_verdict(dict(ev, n_test=20))
        v_none = factor_engine.review_verdict(dict(ev))
        check("B1-8 n_test<20 → hold / n_test=20 → pass / 缺省兼容",
              v_hold == "hold" and v_pass == "pass" and v_none == "pass",
              (v_hold, v_pass, v_none))
        check("B1-8 samples 死参已移除",
              list(factor_engine.review_verdict.__code__.co_varnames
                   [:factor_engine.review_verdict.__code__.co_argcount]) == ["evidence"])

        # ---- shadow_live ----
        st4, env4, ms4 = get("/review/scores?data_kind=shadow_live")
        d4 = (env4 or {}).get("data") or {}
        sc4 = d4.get("scores") or []
        raw4 = json.dumps(d4, ensure_ascii=False)
        check("shadow_live 3 行 / T3/T15 pending",
              len(sc4) == 3 and sc4[1].get("baseline_status") == "pending"
              and sc4[2].get("baseline_status") == "pending"
              and '"baseline_status": "ok"' not in raw4,
              [(r.get("window"), r.get("baseline_status")) for r in sc4])

        # ---- S2 新浪标注 ----
        st5, env5, _ = get("/data-sources/health", timeout=10)
        srcs = ((env5 or {}).get("data") or {}).get("sources") or []
        sina = next((s for s in srcs if s.get("source_id") == "sina_rt"), {})
        check("S2 sina note 含「仅探测·非主链」",
              "仅探测·非主链" in (sina.get("note") or ""),
              "%s | %s" % (sina.get("status"), sina.get("note")))

        report = {
            "ready_sec": round(ready, 2), "holdings_1s_ms": ms1, "holdings_6s_ms": ms2,
            "holdings_rows": [len(rows), len(rows2)],
            "review_backtest": {"t1_status": t1.get("baseline_status"),
                                "t1_values": {k: t1.get(k) for k in
                                              ("hit_rate", "baseline_rate", "delta_pp", "open_count")},
                                "t3": {k: t3.get(k) for k in ("baseline_status", "formula")},
                                "t15": {k: t15.get(k) for k in ("baseline_status", "formula")},
                                "hero": hero},
            "review_shadow_live": [(r.get("window"), r.get("baseline_status")) for r in sc4],
            "sina": {"status": sina.get("status"), "note": sina.get("note")},
            "checks": results,
        }
        with io.open(os.path.join(HERE, "coldstart_s4.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=1))
        with io.open(os.path.join(HERE, "ep_review_scores_v2.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(env3, ensure_ascii=False, indent=1))
        with io.open(os.path.join(HERE, "ep_review_scores_shadow_v2.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(env4, ensure_ascii=False, indent=1))
        with io.open(os.path.join(HERE, "ep_sources_health_v2.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(env5, ensure_ascii=False, indent=1))
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        out_log.close()
        err_log.close()
        time.sleep(1.0)
        check("端口释放", not port_in_use(PORT), PORT)
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    print("PROBE %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
