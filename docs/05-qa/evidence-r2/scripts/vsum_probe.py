# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP  # noqa: E402

CHROME = r"C:\Users\10719\.agent-browser\browsers\chrome-153.0.8010.36\chrome.exe"
P = 9342
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                         "--remote-debugging-port=%d" % P,
                         "--user-data-dir=" + r"C:\Users\10719\AppData\Local\Temp\opencode\chrome_qa_extra3",
                         "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time()
while time.time() - t0 < 30:
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % P, timeout=2)
        break
    except Exception:
        time.sleep(0.5)
c = CDP(P)
c.navigate("http://127.0.0.1:8796/#/holdings", settle=3.2)
h = c.eval("(document.getElementById('val-sum')||{}).innerHTML||''")
print(h[:2200])
c.close()
proc.terminate()
