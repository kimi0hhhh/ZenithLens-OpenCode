# -*- coding: utf-8 -*-
"""S6 PM 终验 · 交互与 CRUD 实操（真实浏览器 CDP）：
隐私打码（计算样式）/ 行菜单 popover / 三 dialog / 浏览器端录入-编辑-加仓-删除并还原。
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP

BASE = "http://127.0.0.1:8791/"
OUT = os.path.abspath(os.path.join(HERE, ".."))
DATA = r"C:\Users\10719\Documents\ZenithLens-OpenCode\data\holdings.json"
BK = os.path.join(OUT, "holdings.backup.json")


def ev(c, expr, await_promise=False):
    return c.eval(expr, await_promise=await_promise)


def main():
    shutil.copy2(DATA, BK)
    c = CDP(9222)
    c.call("Emulation.setDeviceMetricsOverride",
           {"width": 1720, "height": 3000, "deviceScaleFactor": 1, "mobile": False})
    res = {}

    # ---- 隐私打码：计算样式验证 ----
    c.navigate(BASE + "#/holdings", settle=1.0)
    time.sleep(6)
    res["privacy_unmasked"] = json.loads(ev(c, r"""JSON.stringify({
        masked: document.body.classList.contains('masked'),
        total_text: (document.getElementById('pa-total')||{}).innerText,
        color: getComputedStyle(document.getElementById('pa-total')).color
    })"""))
    ev(c, "document.querySelector('#eye-btn').click()")
    time.sleep(1.2)
    res["privacy_masked"] = json.loads(ev(c, r"""JSON.stringify({
        masked: document.body.classList.contains('masked'),
        total_text: (document.getElementById('pa-total')||{}).innerText,
        color: getComputedStyle(document.getElementById('pa-total')).color,
        after: getComputedStyle(document.getElementById('pa-total'),'::after').content,
        ret_visible: (document.getElementById('pa-ret')||{}).innerText,
        ret_color: getComputedStyle(document.getElementById('pa-ret')).color
    })"""))
    c.screenshot(os.path.join(OUT, "shot_privacy.png"))
    ev(c, "document.querySelector('#eye-btn').click()")
    time.sleep(1.2)
    res["privacy_restored"] = json.loads(ev(c, r"""JSON.stringify({
        masked: document.body.classList.contains('masked')
    })"""))

    # ---- 行菜单 popover + 三 dialog 存在性 ----
    ev(c, "document.querySelector('#hd-body [data-menu]').click()")
    time.sleep(0.8)
    res["popover"] = json.loads(ev(c, r"""JSON.stringify({
        pop_show: (document.getElementById('pop')||{}).classList ? document.getElementById('pop').classList.contains('show') : false,
        acts: Array.prototype.map.call(document.querySelectorAll('#pop [data-act]'), function(b){return b.dataset.act;}),
        dlg_fund: !!document.getElementById('dlg-fund'),
        dlg_amt: !!document.getElementById('dlg-amt'),
        dlg_del: !!document.getElementById('dlg-del'),
        toast: !!document.getElementById('toast')
    })"""))
    c.screenshot(os.path.join(OUT, "shot_popover.png"))
    ev(c, "document.body.click()")
    time.sleep(0.4)

    # ---- CRUD：录入（浏览器 dialog）----
    crud = {}
    n0 = ev(c, "document.querySelectorAll('#hd-body tr:not(.grp)').length")
    crud["rows_before"] = n0
    try:
        ev(c, "document.getElementById('btn-add-fund').click()")
        time.sleep(0.8)
        crud["dlg_open"] = ev(c, "document.getElementById('dlg-fund').open")
        ev(c, "document.getElementById('fd-code').value='999997'")
        ev(c, "document.getElementById('fd-name').value='PM终验临时基金'")
        ev(c, "document.getElementById('fd-shares').value='1'")
        ev(c, "document.getElementById('fd-cost').value='1'")
        ev(c, "document.getElementById('fd-save').click()")
        time.sleep(3.5)
        crud["rows_after_create"] = ev(c, "document.querySelectorAll('#hd-body tr:not(.grp)').length")
        crud["created_exists"] = ev(c, "!!document.querySelector('#hd-body [data-menu=\"999997\"]')")
        crud["toast_after_create"] = ev(c, "(document.getElementById('toast')||{}).innerText")
    except Exception as e:
        crud["create_error"] = str(e)

    # ---- CRUD：编辑 ----
    try:
        ev(c, "document.querySelector('#hd-body [data-menu=\"999997\"]').click()")
        time.sleep(0.6)
        ev(c, "document.querySelector('#pop [data-act=\"edit\"]').click()")
        time.sleep(0.8)
        crud["edit_title"] = ev(c, "document.getElementById('fd-title').innerText")
        ev(c, "document.getElementById('fd-name').value='PM终验临时基金-已编辑'")
        ev(c, "document.getElementById('fd-save').click()")
        time.sleep(3.5)
        row = ev(c, r"""JSON.stringify((function(){var b=document.querySelector('#hd-body [data-menu="999997"]');return b?b.closest('tr').innerText:null;})())""")
        crud["edited_row_text"] = row
    except Exception as e:
        crud["edit_error"] = str(e)

    # ---- CRUD：加仓 ----
    try:
        ev(c, "document.querySelector('#hd-body [data-menu=\"999997\"]').click()")
        time.sleep(0.6)
        ev(c, "document.querySelector('#pop [data-act=\"buy\"]').click()")
        time.sleep(0.8)
        crud["amt_title"] = ev(c, "document.getElementById('am-title').innerText")
        ev(c, "document.getElementById('am-shares').value='2'")
        ev(c, "document.getElementById('am-price').value='1.0'")
        ev(c, "document.getElementById('am-save').click()")
        time.sleep(3.5)
        crud["toast_after_buy"] = ev(c, "(document.getElementById('toast')||{}).innerText")
    except Exception as e:
        crud["amt_error"] = str(e)

    # ---- CRUD：删除（二次确认 dialog）----
    try:
        ev(c, "document.querySelector('#hd-body [data-menu=\"999997\"]').click()")
        time.sleep(0.6)
        ev(c, "document.querySelector('#pop [data-act=\"delete\"]').click()")
        time.sleep(0.8)
        crud["del_dlg_open"] = ev(c, "document.getElementById('dlg-del').open")
        c.screenshot(os.path.join(OUT, "shot_dialog_delete.png"))
        ev(c, "document.getElementById('dl-save').click()")
        time.sleep(3.5)
        crud["rows_after_delete"] = ev(c, "document.querySelectorAll('#hd-body tr:not(.grp)').length")
        crud["deleted_gone"] = ev(c, "!document.querySelector('#hd-body [data-menu=\"999997\"]')")
        crud["toast_after_delete"] = ev(c, "(document.getElementById('toast')||{}).innerText")
    except Exception as e:
        crud["delete_error"] = str(e)

    res["crud"] = crud

    # 还原数据文件（保证字节级还原）
    shutil.copy2(BK, DATA)

    with open(os.path.join(OUT, "ui_interactions_crud.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("done")
    c.close()


if __name__ == "__main__":
    main()
