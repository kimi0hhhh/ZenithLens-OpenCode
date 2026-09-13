# -*- coding: utf-8 -*-
import io
import re
import sys
import os

sys.path.insert(0, r"C:\Users\10719\Documents\ZenithLens-OpenCode")
os.chdir(r"C:\Users\10719\Documents\ZenithLens-OpenCode")
import app  # noqa: E402

t = io.open(r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\01-architecture\09-api-contract.md",
            encoding="utf-8").read()
rows = re.findall(r'^\|\s*(\d+)\s*\|\s*(GET|POST|PUT|DELETE)\s*\|\s*`([^`]+)`',
                  t, re.M)
contract = set()
for _n, m, p in rows:
    p = p.replace("/api/v1", "")
    p = re.sub(r"\{candidate_id\}", r"(?P<candidate_id>[A-Za-z0-9_\\-]+)", p)
    p = re.sub(r"\{book\}", r"(?P<book>[a-z_]+)", p)
    contract.add("%s %s" % (m, p))

actual = set("%s %s" % (m, p) for m, p, _fn in app.ROUTES)
print("contract:", len(contract), "actual:", len(actual))
print("actual - contract:")
for x in sorted(actual - contract):
    print("  +", x)
print("contract - actual:")
for x in sorted(contract - actual):
    print("  -", x)
