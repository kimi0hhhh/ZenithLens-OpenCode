# -*- coding: utf-8 -*-
"""C0 快审 · E-1 顶栏日期 live 抽查（headless Edge dump-dom）。"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def free(port):
    s = socket.socket()
    s.settimeout(0.2)
    try:
        s.connect(("127.0.0.1", port))
        return False
    except Exception:  # noqa: BLE001
        return True
    finally:
        s.close()


def pick_port():
    for p in range(8799, 8820):
        if free(p):
            return p
    raise SystemExit("no free port")


def main():
    port = pick_port()
    proc = subprocess.Popen([sys.executable, "app.py", "--port", str(port)],
                            cwd=SRC,
                            stdout=io.open(os.path.join(HERE, "c0_e1.out.log"), "w", encoding="utf-8"),
                            stderr=io.open(os.path.join(HERE, "c0_e1.err.log"), "w", encoding="utf-8"))
    try:
        deadline = time.time() + 60
        ok = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/api/v1/health" % port, timeout=1) as r:
                    if json.loads(r.read().decode("utf-8")).get("ok"):
                        ok = True
                        break
            except Exception:  # noqa: BLE001
                time.sleep(0.15)
        local = datetime.now().strftime("%Y-%m-%d")
        utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_local = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]
        print("local=%s (%s) | utc=%s | in-utc-skew-window=%s" % (
            local, week_local, utc, local != utc))
        dump = subprocess.run(
            [EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
             "--virtual-time-budget=8000", "--dump-dom",
             "http://127.0.0.1:%d/" % port],
            capture_output=True, timeout=90)
        html = dump.stdout.decode("utf-8", "replace")
        m = re.search(r'id="top-date"[^>]*>([^<]*)<', html)
        shown = m.group(1).strip() if m else None
        print("top-date shows:", repr(shown))
        passed = bool(shown) and shown.startswith(local) and week_local in shown \
            and (local == utc or not shown.startswith(utc))
        report = {"local": local, "utc": utc, "week_local": week_local,
                  "top_date": shown, "passed": passed, "port": port}
        with io.open(os.path.join(HERE, "c0_e1_probe.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=1))
        print("E-1 LIVE:", "PASS" if passed else "FAIL")
        return 0 if passed else 1
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.8)
        print("port released:", free(port))


if __name__ == "__main__":
    raise SystemExit(main())
