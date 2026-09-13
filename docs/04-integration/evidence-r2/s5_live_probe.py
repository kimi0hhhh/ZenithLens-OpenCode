# -*- coding: utf-8 -*-
"""S5 终验 · live 探针：chain_source / 重算一致性 / top_n / D2 / S-c。"""
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
PORT = 8797
BASE = "http://127.0.0.1:%d/api/v1" % PORT

results = []


def check(name, ok, detail=""):
    results.append({"check": name, "pass": bool(ok), "detail": str(detail)[:400]})
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         (" | " + str(detail)[:180]) if detail else ""))


def req(path, method="GET", body=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return e.code, None


def free(port):
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        return False
    except Exception:  # noqa: BLE001
        return True
    finally:
        s.close()


def main():
    if not free(PORT):
        print("port busy", PORT)
        return 2
    out = io.open(os.path.join(HERE, "s5_probe.out.log"), "w", encoding="utf-8")
    err = io.open(os.path.join(HERE, "s5_probe.err.log"), "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "app.py", "--port", str(PORT)],
                            cwd=SRC, stdout=out, stderr=err)
    try:
        deadline = time.time() + 60
        ready = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(BASE + "/health", timeout=1) as r:
                    if json.loads(r.read().decode("utf-8")).get("ok"):
                        ready = True
                        break
            except Exception:  # noqa: BLE001
                time.sleep(0.15)
        check("ready", ready)
        if not ready:
            return 2

        # 1) ledger rows + chain_available
        st, env = req("/ledger?limit=60")
        rows = ((env or {}).get("data") or {}).get("rows") or []
        avail = [r for r in rows if r.get("chain_available")]
        check("/ledger rows=60 且 chain_available=true 存在",
              st == 200 and len(rows) > 0 and len(avail) > 0,
              "rows=%d avail=%d" % (len(rows), len(avail)))

        # 2) chain recomputed + 一致性（取 2 行）
        okc = 0
        for row in avail[:2]:
            st2, env2 = req("/ledger/chain?date=%s&code=%s" % (row["date"], row["code"]))
            d = (env2 or {}).get("data") or {}
            chain = d.get("chain") or []
            keys = [s.get("key") for s in chain]
            exit_step = next((s for s in chain if s.get("key") == "exit"), {}) or {}
            met = exit_step.get("metrics") or {}
            row_p = row.get("p_up")
            same_p = (met.get("p_up") is None and row_p is None) or (
                met.get("p_up") is not None and row_p is not None
                and abs(float(met["p_up"]) - float(row_p)) < 1e-3)
            st_ok = (st2 == 200 and len(chain) == 6
                     and keys == ["gate", "ddsm", "veto_crowd", "veto_klow2", "exit", "output"]
                     and str(met.get("exit_threshold")) in ("0.52", "0.5200")
                     and d.get("chain_source") == "recomputed" and same_p)
            if st_ok:
                okc += 1
            check("chain(%s/%s) 六步+recomputed+对账" % (row["date"], row["code"]), st_ok,
                  "source=%s keys=%s exit=%s p=%s vs %s" % (
                      d.get("chain_source"), ",".join(keys[:6]), met.get("exit_threshold"),
                      met.get("p_up"), row_p))

        # 3) holdings detail method/top_n（active 5 只）
        st3, env3 = req("/holdings?with=valuation,nav,prediction")
        hrows = ((env3 or {}).get("data") or {}).get("rows") or []
        details = []
        for r in hrows:
            v = r.get("valuation") or {}
            if v.get("valuation_mode") != "holdings":
                continue
            det = None
            for s in (v.get("trace") or []):
                d = s.get("detail") if isinstance(s, dict) else None
                if isinstance(d, dict) and d.get("method"):
                    det = d
            if det:
                details.append({"code": r["code"], "method": det.get("method"),
                                "top_n": det.get("top_n"),
                                "markets": det.get("included_markets")})
        method_ok = bool(details) and all(
            d["method"] == "eastmoney_f10_top10_weighted" and d["top_n"] in (10, 20)
            for d in details)
        top20 = sum(1 for d in details if d["top_n"] == 20)
        hk = sum(1 for d in details if "HK" in (d.get("markets") or []))
        check("holdings detail method 恒定 + top_n∈{10,20}（top20=%d，HK=%d）" % (top20, hk),
              method_ok and top20 >= 1, details)

        # 4) D2 主源路径
        st4, env4 = req("/settings/holdings-data")
        mpath = ((env4 or {}).get("data") or {}).get("main_source", {}).get("path")
        check("main_source.path == data/holdings.json", mpath == "data/holdings.json", mpath)

        # 5) S-c scan_factors 诚实回执
        st5, env5 = req("/tasks", method="POST", body={"type": "scan_factors"})
        tid = ((env5 or {}).get("data") or {}).get("task_id")
        summary = ""
        for _ in range(30):
            time.sleep(0.5)
            st6, env6 = req("/tasks/%s" % tid)
            d = (env6 or {}).get("data") or {}
            if d.get("status") in ("done", "failed"):
                summary = d.get("result_summary") or ""
                break
        ok5 = ("未接入" in summary) and ("扫描完成" not in summary)
        check("scan_factors 回执诚实（含「未接入」、无「扫描完成」）", ok5, summary[:120])

        report = {"checks": results, "detail_samples": details}
        with io.open(os.path.join(HERE, "s5_live_probe.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=1))
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        out.close()
        err.close()
        time.sleep(0.8)
        check("端口释放", free(PORT), PORT)
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    print("PROBE %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
