# -*- coding: utf-8 -*-
"""C1b 断连修复 · 代码走查提取。"""
import io

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
OUT = r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\04-integration\evidence-r2\c1b-code.txt"
t = io.open(SRC + r"\app.py", encoding="utf-8").read()
w = io.open(OUT, "w", encoding="utf-8")
for kw in ("DISCONNECT_ERRORS", "DISCONNECT_SUPPRESSED",
           "def _send", "def _serve_static", "def _handle",
           "class QuietThreadingHTTPServer", "def handle_error"):
    idx, n = 0, 0
    while True:
        i = t.find(kw, idx)
        if i < 0:
            break
        n += 1
        idx = i + 1
        if n <= 2:
            w.write("=== %s @line %d ===\n%s\n\n" % (
                kw, t[:i].count("\n") + 1, t[max(0, i - 260):i + 1000]))
w.close()
print("written")
