# -*- coding: utf-8 -*-
"""Minimal Chrome DevTools Protocol client (stdlib only).

Used because agent-browser daemon handshake failed on this host; we drive the
already-running Chrome for Testing (ms-playwright chromium) over CDP directly.
"""
import base64
import json
import os
import socket
import struct
import time
import urllib.request


class WS(object):
    def __init__(self, url):
        # ws://127.0.0.1:9222/devtools/page/<id>
        assert url.startswith("ws://")
        rest = url[5:]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET /%s HTTP/1.1\r\n"
            "Host: %s:%s\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (path, host, port, key)
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        if b"101" not in buf.split(b"\r\n")[0]:
            raise RuntimeError("websocket upgrade failed: %r" % buf[:200])
        self._rbuf = b""

    def _recv_exact(self, n):
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise RuntimeError("socket closed")
            out += chunk
        return out

    def send(self, text):
        data = text.encode("utf-8")
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv(self):
        while True:
            b1, b2 = self._recv_exact(2)
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            payload = self._recv_exact(length) if length else b""
            if opcode == 0x8:
                raise RuntimeError("websocket closed by peer")
            if opcode == 0x9:  # ping -> pong
                self.sock.sendall(b"\x8a\x80" + os.urandom(4))
                continue
            if opcode in (0x1, 0x2, 0x0):
                return payload.decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class CDP(object):
    def __init__(self, port=9222):
        self.port = port
        targets = json.load(urllib.request.urlopen(
            "http://127.0.0.1:%d/json/list" % port, timeout=15))
        pages = [t for t in targets if t.get("type") == "page"]
        if not pages:
            raise RuntimeError("no page target")
        self.target = pages[0]
        self.ws = WS(self.target["webSocketDebuggerUrl"])
        self.mid = 0
        self.call("Runtime.enable")
        self.call("Page.enable")

    def call(self, method, params=None, timeout=60):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method,
                                 "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})
        raise RuntimeError("timeout waiting %s" % method)

    def eval(self, expr, await_promise=False):
        r = self.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        })
        if "exceptionDetails" in r:
            raise RuntimeError("JS error: %s" % json.dumps(
                r["exceptionDetails"], ensure_ascii=False)[:400])
        return r.get("result", {}).get("value")

    def navigate(self, url, settle=3.0):
        self.call("Page.navigate", {"url": url})
        deadline = time.time() + 40
        while time.time() < deadline:
            state = self.eval("document.readyState")
            if state == "complete":
                break
            time.sleep(0.3)
        time.sleep(settle)

    def screenshot(self, path, full=True):
        params = {"format": "png"}
        if full:
            params["captureBeyondViewport"] = True
        r = self.call("Page.captureScreenshot", params)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path

    def close(self):
        self.ws.close()
