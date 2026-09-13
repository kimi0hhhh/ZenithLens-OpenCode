# -*- coding: utf-8 -*-
"""Shape probe: print top-level keys / sample structures of key R2 endpoints."""
import json, os, urllib.request, urllib.error

BASE = "http://127.0.0.1:8796/api/v1"
EV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch(path, method="GET", body=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def show(name, path, sampler=None):
    st, pl = fetch(path)
    d = pl.get("data") if isinstance(pl, dict) else None
    print("=" * 20, name, "status", st)
    if isinstance(d, dict):
        print("keys:", sorted(d.keys()))
        for k in sorted(d.keys()):
            v = d[k]
            if sampler and k in sampler:
                sampler[k](v)
            elif isinstance(v, list):
                print("  [%s] list len=%d" % (k, len(v)))
                if v and isinstance(v[0], dict):
                    print("    row0 keys:", sorted(v[0].keys()))
            elif isinstance(v, dict):
                print("  [%s] dict keys:" % k, sorted(v.keys()))
            else:
                print("  [%s] =" % k, repr(v)[:120])
    elif isinstance(d, list):
        print("list len=", len(d))
        if d and isinstance(d[0], dict):
            print("row0 keys:", sorted(d[0].keys()))
    else:
        print("data type:", type(d).__name__, repr(d)[:200])

show("health", "/health")
show("holdings", "/holdings?with=valuation,nav,prediction")
show("precision", "/valuations/precision")
show("coverage", "/holdings/coverage")
show("signals", "/signals/state")
show("engine_status", "/engine/status")
show("frozen", "/engine/frozen-params")
show("review_backtest", "/review/scores")
show("ledger_shadow", "/ledger/shadow")

# samp: print one holdings row and one ledger shadow record fully
st, pl = fetch("/holdings?with=valuation,nav,prediction")
d = pl.get("data")
rows = d.get("rows") if isinstance(d, dict) else d
if rows:
    print("=" * 20, "holdings row0")
    print(json.dumps(rows[0], ensure_ascii=False, indent=1)[:2500])
st, pl = fetch("/ledger/shadow")
d = pl.get("data")
recs = d.get("records") if isinstance(d, dict) else None
if recs:
    print("=" * 20, "ledger shadow record0")
    print(json.dumps(recs[0], ensure_ascii=False, indent=1)[:1500])
else:
    print("ledger shadow keys:", sorted(d.keys()) if isinstance(d, dict) else type(d))

# review scores full (small)
st, pl = fetch("/review/scores")
print("=" * 20, "review scores full")
print(json.dumps(pl, ensure_ascii=False, indent=1)[:3000])
