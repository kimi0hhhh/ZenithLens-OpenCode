# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP

c = CDP(9222)
c.call("Emulation.setDeviceMetricsOverride",
       {"width": 1680, "height": 2600, "deviceScaleFactor": 1, "mobile": False})
c.navigate("http://127.0.0.1:8791/", settle=6.0)
print("title:", c.eval("document.title"))
print("readyState:", c.eval("document.readyState"))
print("body_len:", c.eval("document.body.innerText.length"))
print("body_head:", repr(c.eval("document.body.innerText.slice(0,300)")))
print("views:", c.eval("JSON.stringify(Object.keys(window).filter(k=>/store|app|router/i.test(k)))"))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shot_home.png")
c.screenshot(os.path.abspath(out))
print("shot:", os.path.abspath(out))
c.close()
