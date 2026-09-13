# -*- coding: utf-8 -*-
"""S4b · 刷新后 build-r2 独立启动实测（临时副本 + 空闲端口 8795）。"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\04-integration\build-r2"
TMP = r"C:\Users\10719\AppData\Local\Temp\opencode\zl-build-test-v2"


def _pick_port():
    for cand in range(8799, 8820):
        s = socket.socket()
        s.settimeout(0.2)
        busy = True
        try:
            s.connect(("127.0.0.1", cand))
        except Exception:  # noqa: BLE001
            busy = False
        finally:
            s.close()
        if not busy:
            return cand
    raise SystemExit("no free port")


PORT = _pick_port()


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
    assert free(PORT), "port %d busy" % PORT
    shutil.rmtree(TMP, ignore_errors=True)
    shutil.copytree(BUILD, TMP)
    out = io.open(os.path.join(HERE, "build_boot_v3.out.log"), "w", encoding="utf-8")
    err = io.open(os.path.join(HERE, "build_boot_v3.err.log"), "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "app.py", "--port", str(PORT)],
                            cwd=TMP, stdout=out, stderr=err)
    ok = False
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/api/v1/health" % PORT, timeout=1) as r:
                    env = json.loads(r.read().decode("utf-8"))
                    if env.get("ok"):
                        ok = True
                        break
            except Exception:  # noqa: BLE001
                time.sleep(0.15)
        if ok:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/v1/review/scores" % PORT, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8")).get("data") or {}
            marks = [(s.get("window"), s.get("baseline_status")) for s in d.get("scores", [])]
            ok2 = marks == [("T1", "filled"), ("T3", "pending"), ("T15", "pending")]
            print("BUILD BOOT: health=ok review=%s %s" % (marks, "PASS" if ok2 else "FAIL"))
            report = {"ok": True, "review_status": marks, "review_ok": ok2, "tmp": TMP}
        else:
            print("BUILD BOOT: health timeout FAIL")
            report = {"ok": False}
        with io.open(os.path.join(HERE, "build_boot_v3.json"), "w", encoding="utf-8") as f:
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
        print("port released:", free(PORT))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
