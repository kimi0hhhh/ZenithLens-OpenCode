# -*- coding: utf-8 -*-
"""S5 CRUD / 设置往返实测：实起 8791 上真调 HTTP，测完还原数据。"""
import io
import json
import os
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8791/api/v1"
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
checks = []


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def chk(cid, desc, ok, detail):
    checks.append({"id": cid, "desc": desc, "pass": bool(ok), "detail": detail})


# 基线
_, env = call("GET", "/holdings")
n0 = len(env["data"]["rows"])
_, s0 = call("GET", "/holdings/summary")
t0 = s0["data"]["total_value"]
chk("C-00", "基线持仓 22 只", n0 == 22, "rows=%d total=%.2f" % (n0, t0))

# Create
st, env = call("POST", "/holdings", {"code": "999998", "name": "QA临时测试基金",
                                     "shares": 1.0, "cost_amount": 1.0,
                                     "group": "other", "tier": "D", "confirm_days": 1})
chk("C-01", "POST /holdings 建档返回 201", st == 201 and env["ok"], "status=%s code=%s" % (st, env.get("data", {}).get("code")))
_, env = call("GET", "/holdings")
n1 = len(env["data"]["rows"])
chk("C-02", "建档后 22→23", n1 == 23, "rows=%d" % n1)

# 重复建档 -> 冲突
st, env = call("POST", "/holdings", {"code": "999998", "name": "dup"})
chk("C-03", "重复代码冲突 E_CONFLICT", st == 409 and env["error"]["code"] == "E_CONFLICT",
    "status=%s code=%s" % (st, env["error"]["code"] if env.get("error") else None))

# 非法代码 -> 校验失败
st, env = call("POST", "/holdings", {"code": "abc", "name": "x"})
chk("C-04", "非法代码 E_VALIDATION", st == 400 and env["error"]["code"] == "E_VALIDATION",
    "status=%s code=%s" % (st, env["error"]["code"] if env.get("error") else None))

# Update
st, env = call("PUT", "/holdings/999998", {"name": "QA临时测试基金-改", "shares": 2.0, "cost_amount": 2.0})
chk("C-05", "PUT 更新名称/份额", st == 200 and env["data"]["name"] == "QA临时测试基金-改",
    "name=%s" % env.get("data", {}).get("name"))
_, env = call("GET", "/holdings/999998")
chk("C-06", "GET 单条回读更新后值", env["data"]["name"] == "QA临时测试基金-改" and abs(env["data"]["shares"] - 2.0) < 1e-9,
    "name=%s shares=%s" % (env["data"]["name"], env["data"]["shares"]))

# 不存在
st, env = call("GET", "/holdings/999999")
chk("C-07", "不存在代码 E_NOT_FOUND", st == 404 and env["error"]["code"] == "E_NOT_FOUND",
    "status=%s" % st)

# Delete
st, env = call("DELETE", "/holdings/999998")
chk("C-08", "DELETE 返回 deleted_code", st == 200 and env["data"]["deleted_code"] == "999998",
    "data=%s" % env.get("data"))

# 还原核对
_, env = call("GET", "/holdings")
n2 = len(env["data"]["rows"])
_, s2 = call("GET", "/holdings/summary")
t2 = s2["data"]["total_value"]
chk("C-09", "删除后还原 22 只且总额一致", n2 == 22 and abs(t2 - t0) < 0.01, "rows=%d total=%.2f" % (n2, t2))
st, env = call("DELETE", "/holdings/999998")
chk("C-10", "重复删除 E_NOT_FOUND", st == 404, "status=%s" % st)

# ---- 设置 base_url 往返（v5 BLOCK-2）----
_, env = call("GET", "/settings")
b0 = env["data"]["llm"]["base_url"]
st, env = call("PUT", "/settings", {"llm": {"base_url": "https://api.deepseek.com/v1"}})
_, env = call("GET", "/settings")
b1 = env["data"]["llm"]["base_url"]
chk("C-11", "llm.base_url PUT→GET 往返持久化", b1 == "https://api.deepseek.com/v1", "b1=%s" % b1)
st, env = call("PUT", "/settings", {"llm": {"base_url": "api.deepseek.com"}})
chk("C-12", "非法 base_url E_VALIDATION", st == 400 and env["error"]["code"] == "E_VALIDATION",
    "status=%s detail=%s" % (st, env["error"].get("detail")))
# 还原
call("PUT", "/settings", {"llm": {"base_url": b0 or ""}})
_, env = call("GET", "/settings")
chk("C-13", "base_url 已还原为初值", env["data"]["llm"]["base_url"] == (b0 or ""), "now=%r init=%r" % (env["data"]["llm"]["base_url"], b0))

# 台账 INSERT-ONLY：无 PUT/DELETE 路由
for m in ("PUT", "DELETE"):
    st, env = call(m, "/ledger/entries")
    chk("C-14%s" % m, "%s /ledger/entries 应无编辑路由" % m, st in (404, 405),
        "status=%s" % st)

ok = sum(1 for c in checks if c["pass"])
with io.open(os.path.join(OUT, "crud_checks.json"), "w", encoding="utf-8") as f:
    json.dump({"total": len(checks), "pass": ok, "fail": len(checks) - ok, "checks": checks}, f, ensure_ascii=False, indent=2)
for c in checks:
    print(("PASS " if c["pass"] else "FAIL ") + c["id"] + " " + c["desc"] + " | " + c["detail"])
print("SUMMARY %d/%d" % (ok, len(checks)))
