# -*- coding: utf-8 -*-
import json
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://127.0.0.1:8796/api/v1"


def get(p):
    try:
        with urllib.request.urlopen(BASE + p, timeout=90) as f:
            return f.status, json.loads(f.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


st, d = get("/ledger/chain?date=2026-09-11&code=012922")
print("status", st)
print(json.dumps(d, ensure_ascii=False)[:1600])
print("=== try alt params ===")
st, d = get("/ledger/chain?date=2026-09-11&code=013566")
print("status", st, json.dumps(d, ensure_ascii=False)[:600])
st, d = get("/ledger/chain?date=2026-09-10&code=012922")
print("status", st, json.dumps(d, ensure_ascii=False)[:600])
