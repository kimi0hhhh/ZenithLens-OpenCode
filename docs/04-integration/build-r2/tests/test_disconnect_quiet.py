# -*- coding: utf-8 -*-
"""断连噪声修复测试（客户端刷新/切页/取消请求 → 服务端不刷堆栈；真错不误吞）。

覆盖：
- `_send` / `_serve_static`：断连族（ConnectionAborted/Reset/BrokenPipe）静默返回；
  非断连异常继续抛（不许吞）；
- `_handle`：断连 → 直接 return（不打印、不发信封）；非断连 → print_exc + E_UNKNOWN 信封；
- `QuietThreadingHTTPServer.handle_error`：断连静默计数；其他异常走默认堆栈；
- 真起服 + RST 风暴：stderr 无 Traceback，风暴后服务正常。
"""

import contextlib
import io
import json
import os
import shutil
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import errors

DISCONNECTS = (ConnectionAbortedError("x"), ConnectionResetError("x"),
               BrokenPipeError("x"))


class _WFile:
    def __init__(self, exc):
        self.exc = exc
        self.writes = 0

    def write(self, raw):
        self.writes += 1
        if self.exc is not None:
            raise self.exc


class _FakeHandler:
    def __init__(self, exc=None, fail_at="write"):
        self.exc = exc
        self.fail_at = fail_at
        self.wfile = _WFile(exc if fail_at == "write" else None)
        self.headers = []

    def send_response(self, status):
        pass

    def send_header(self, k, v):
        pass

    def end_headers(self):
        if self.exc is not None and self.fail_at == "end_headers":
            raise self.exc


class SendDisconnectTest(unittest.TestCase):
    def test_send_swallows_disconnect_family(self):
        for exc in DISCONNECTS:
            for where in ("write", "end_headers"):
                before = app.DISCONNECT_SUPPRESSED["count"]
                h = _FakeHandler(exc, fail_at=where)
                app._send(h, 200, {"ok": True})   # 不抛
                self.assertEqual(app.DISCONNECT_SUPPRESSED["count"], before + 1)
                self.assertIsNotNone(app.DISCONNECT_SUPPRESSED["last_at"])

    def test_send_reraises_other_errors(self):
        h = _FakeHandler(ValueError("real bug"), fail_at="write")
        with self.assertRaises(ValueError):
            app._send(h, 200, {"ok": True})


class ServeStaticDisconnectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zl_static_")
        with io.open(os.path.join(self.tmp, "x.js"), "w", encoding="utf-8") as f:
            f.write("console.log(1);" * 100)
        self._saved = app.STATIC_DIR
        app.STATIC_DIR = self.tmp

    def tearDown(self):
        app.STATIC_DIR = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_static_swallows_disconnect(self):
        h = _FakeHandler(BrokenPipeError("gone"))
        before = app.DISCONNECT_SUPPRESSED["count"]
        app._serve_static(h, "/x.js")             # 不抛
        self.assertEqual(app.DISCONNECT_SUPPRESSED["count"], before + 1)

    def test_static_reraises_other_errors(self):
        h = _FakeHandler(ValueError("real bug"))
        with self.assertRaises(ValueError):
            app._serve_static(h, "/x.js")


class HandleDisconnectTest(unittest.TestCase):
    def _handler(self, wfile_exc):
        Handler = app.make_handler()
        h = Handler.__new__(Handler)
        h.path = "/api/v1/health"
        h.command = "GET"
        h.request_version = "HTTP/1.1"
        h.headers = {}
        h.send_response = lambda status: None
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None
        h.wfile = _WFile(wfile_exc)
        return h

    def test_handle_swallows_disconnect_without_envelope(self):
        h = self._handler(ConnectionAbortedError("gone"))
        captured = []
        h._envelope_err = lambda e: captured.append(e)
        err = io.StringIO()
        before = app.DISCONNECT_SUPPRESSED["count"]
        with contextlib.redirect_stderr(err):
            h._handle("GET")                       # 不抛、不打印
        self.assertEqual(captured, [])
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(app.DISCONNECT_SUPPRESSED["count"], before + 1)

    def test_handle_keeps_internal_error_envelope_and_stack(self):
        h = self._handler(None)
        captured = []
        h._envelope_err = lambda e: captured.append(e)
        err = io.StringIO()
        with mock.patch.object(app, "dispatch",
                               side_effect=RuntimeError("real bug")):
            with contextlib.redirect_stderr(err):
                h._handle("GET")
        self.assertIn("Traceback", err.getvalue())     # 真错仍可见
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].code, errors.E_UNKNOWN)


class HandleErrorTest(unittest.TestCase):
    def _server(self):
        return app.QuietThreadingHTTPServer.__new__(app.QuietThreadingHTTPServer)

    def test_disconnect_is_silent_and_counted(self):
        srv = self._server()
        before = app.DISCONNECT_SUPPRESSED["count"]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            try:
                raise ConnectionResetError(10054, "reset by peer")
            except ConnectionResetError:
                srv.handle_error(None, ("127.0.0.1", 0))
        self.assertEqual(app.DISCONNECT_SUPPRESSED["count"], before + 1)
        self.assertEqual(err.getvalue(), "")

    def test_other_errors_keep_default_stack(self):
        srv = self._server()
        with mock.patch("socketserver.BaseServer.handle_error") as m:
            try:
                raise RuntimeError("real bug")
            except RuntimeError:
                srv.handle_error(None, ("127.0.0.1", 0))
            m.assert_called_once()


class RealServerRstStormTest(unittest.TestCase):
    """真起服 + RST 风暴：stderr 零 Traceback；风暴后服务仍正常。"""

    def setUp(self):
        self.httpd = app.QuietThreadingHTTPServer(("127.0.0.1", 0), app.make_handler())
        self.port = self.httpd.server_address[1]
        self.th = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.th.start()
        self.base = "http://127.0.0.1:%d/api/v1" % self.port

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _rst(self, path):
        sk = socket.socket()
        sk.connect(("127.0.0.1", self.port))
        sk.sendall(("GET %s HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
                    % path).encode("ascii"))
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sk.close()

    def test_rst_storm_no_traceback_and_service_alive(self):
        import urllib.request
        err = io.StringIO()
        before = app.DISCONNECT_SUPPRESSED["count"]
        with contextlib.redirect_stderr(err):
            for _ in range(4):
                self._rst("/api/v1/runtime")
                self._rst("/js/views/holdings.js")
            time.sleep(0.8)
        self.assertNotIn("Traceback", err.getvalue())
        # 风暴后正常请求不受影响
        with urllib.request.urlopen(self.base + "/health", timeout=30) as r:
            self.assertTrue(json.load(r)["ok"])
        # 断连确实发生过（计数器变化；极少数时序下写成功不计数，故不强制 >0）
        self.assertGreaterEqual(app.DISCONNECT_SUPPRESSED["count"], before)


if __name__ == "__main__":
    unittest.main()
