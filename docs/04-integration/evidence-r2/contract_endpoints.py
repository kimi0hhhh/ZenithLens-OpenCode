# -*- coding: utf-8 -*-
import io
import re

t = io.open(r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\01-architecture\09-api-contract.md",
            encoding="utf-8").read()
rows = re.findall(r'^\|\s*(\d+)\s*\|\s*(GET|POST|PUT|DELETE)\s*\|\s*`([^`]+)`',
                  t, re.M)
print("contract enumerated endpoints:", len(rows))
pairs = [("%s %s" % (m, p)) for _n, m, p in rows]
for n, m, p in rows:
    if n in ("19", "20", "21", "54", "55"):
        print(n, m, p)
# also count distinct paths
print("distinct:", len(set(pairs)))
