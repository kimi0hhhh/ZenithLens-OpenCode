# -*- coding: utf-8 -*-
import io
import re

def routes(path):
    t = io.open(path, encoding="utf-8").read()
    return set("%s %s" % (m, p) for m, p in
               re.findall(r'\("(GET|POST|PUT|DELETE)",\s*r"([^"]+)"', t))

r1 = routes(r"C:\Users\10719\Documents\ZenithLens-OpenCode\_archive_round1\py\app.py")
r2 = routes(r"C:\Users\10719\Documents\ZenithLens-OpenCode\app.py")
print("R1 archive routes:", len(r1))
print("R2 routes:", len(r2))
print("R2-R1:")
for x in sorted(r2 - r1):
    print("  +", x)
print("R1-R2:")
for x in sorted(r1 - r2):
    print("  -", x)
