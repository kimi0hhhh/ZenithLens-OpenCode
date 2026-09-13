# -*- coding: utf-8 -*-
"""C1b 断连修复 · RST 风暴探针（零 Traceback 断言 + 风暴后功能不受影响）。

模拟浏览器刷新/取消：发送请求后立即 SO_LINGER=0 关闭（RST）。
断言：stderr 无 Traceback / 无 ConnectionReset|Aborted|WinError 字样；
风暴后 /health ok；正常刷新场景（/、/runtime、/engine/status）不受影响。
"""
import io
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
HERE = os.path.dirname(os.path.abspath(__file__))
STORM_N = 24


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


def rst_get(port, path):
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    try:
        s.sendall(("GET %s HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                   "Connection: close\r\n\r\n" % path).encode("ascii"))
        time.sleep(0.004)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    finally:
        s.close()


def get(port, path, timeout=10):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path),
                                timeout=timeout) as r:
        return r.status, r.read()


def main():
    port = pick_port()
    err_path = os.path.join(HERE, "c1b_storm.err.log")
    out_path = os.path.join(HERE, "c1b_storm.out.log")
    proc = subprocess.Popen([sys.executable, "app.py", "--port", str(port)],
                            cwd=SRC,
                            stdout=io.open(out_path, "w", encoding="utf-8"),
                            stderr=io.open(err_path, "w", encoding="utf-8"))
    try:
        deadline = time.time() + 60
        ready = False
        while time.time() < deadline:
            try:
                st, body = get(port, "/api/v1/health", timeout=1)
                if json.loads(body.decode("utf-8")).get("ok"):
                    ready = True
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.15)
        print("ready:", ready)
        if not ready:
            return 2

        for _ in range(STORM_N):
            try:
                rst_get(port, "/api/v1/health")
            except Exception:  # noqa: BLE001
                pass
        for _ in range(STORM_N):
            try:
                rst_get(port, "/")
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2.0)

        err = io.open(err_path, encoding="utf-8", errors="replace").read()
        tb = err.count("Traceback")
        noise = sum(err.count(k) for k in ("ConnectionReset", "ConnectionAborted",
                                           "ConnectionRefused", "WinError", "10054", "10053"))
        print("after storm: Traceback=%d noise_hits=%d err_lines=%d" % (tb, noise, err.count("\n")))

        st_h, body_h = get(port, "/api/v1/health")
        health_ok = st_h == 200 and json.loads(body_h.decode("utf-8")).get("ok")
        refresh_ok = True
        for p in ("/", "/api/v1/runtime", "/api/v1/runtime", "/api/v1/engine/status"):
            try:
                st, _ = get(port, p)
                refresh_ok = refresh_ok and (st == 200)
            except Exception:  # noqa: BLE001
                refresh_ok = False
        time.sleep(0.5)
        err2 = io.open(err_path, encoding="utf-8", errors="replace").read()
        tb2 = err2.count("Traceback")
        report = {"port": port, "storm_requests": STORM_N * 2,
                  "traceback_after_storm": tb, "noise_hits": noise,
                  "traceback_after_normal_refresh": tb2,
                  "health_after_storm_ok": bool(health_ok),
                  "normal_refresh_ok": bool(refresh_ok),
                  "err_log_lines": err2.count("\n")}
        with io.open(os.path.join(HERE, "c1b_rst_probe.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=1))
        passed = (tb == 0 and tb2 == 0 and health_ok and refresh_ok)
        print("RST PROBE:", "PASS" if passed else "FAIL", json.dumps(report, ensure_ascii=False))
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
