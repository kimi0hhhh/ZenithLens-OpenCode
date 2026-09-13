# -*- coding: utf-8 -*-
"""S5 交互实测：推导链弹窗 / 四态 / 隐私打码 / 立方体 vr 层与 naive 折叠 / 竞技场空集。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP

OUT = os.path.abspath(os.path.join(HERE, ".."))
BASE = "http://127.0.0.1:8791/"


def ev(c, expr):
    return c.eval(expr)


def main():
    c = CDP(9222)
    c.call("Emulation.setDeviceMetricsOverride",
           {"width": 1720, "height": 2600, "deviceScaleFactor": 1, "mobile": False})
    res = {}

    # ---- R-UI-13 推导链（弹窗） ----
    c.navigate(BASE + "#/analyze", settle=1.0)
    time.sleep(6)
    ev(c, "document.querySelector('#an-body tr[data-code]').click()")
    time.sleep(2.5)
    res["chain"] = json.loads(ev(c, r"""JSON.stringify({
        modal: !!document.querySelector('#zl-modal.show'),
        items: document.querySelectorAll('#zl-modal .chain-item').length,
        on_items: document.querySelectorAll('#zl-modal .chain-item.on').length,
        steps_text: (document.querySelector('#zl-modal')||{}).innerText ? document.querySelector('#zl-modal').innerText.slice(0,500) : null
    })"""))
    c.screenshot(os.path.join(OUT, "shot_chain.png"))
    ev(c, "(document.querySelector('#zl-modal [data-close]')||{click:function(){}}).click()")

    # ---- R-UI-40 四态 ----
    c.navigate(BASE + "#/holdings", settle=1.0)
    time.sleep(6)
    states = {}
    for st in ["empty", "loading", "error", "success"]:
        ev(c, "document.querySelector('#statebar-btns button[data-st=\"%s\"]').click()" % st)
        time.sleep(0.7)
        states[st] = json.loads(ev(c, r"""JSON.stringify({
            cls: (document.querySelector('#view-holdings .state-block')||{}).className,
            text: ((document.querySelector('#view-holdings .state-block')||{}).innerText||'').slice(0,110),
            has_retry: !!document.querySelector('#view-holdings .state-block [data-retry]')
        })"""))
        if st == "empty":
            c.screenshot(os.path.join(OUT, "shot_state_empty.png"))
        if st == "error":
            c.screenshot(os.path.join(OUT, "shot_state_error.png"))
    ev(c, "document.querySelector('#statebar-btns button[data-st=\"success\"]').click()")
    time.sleep(1.5)
    res["states"] = states

    # ---- R-UI-32 隐私打码 ----
    ev(c, "document.querySelector('#eye-btn').click()")
    time.sleep(1.2)
    res["privacy_on"] = json.loads(ev(c, r"""JSON.stringify({
        masked: document.body.classList.contains('masked'),
        total: (document.querySelector('#pa-total')||{}).innerText,
        ret: (document.querySelector('#pa-ret')||{}).innerText,
        eye: (document.querySelector('#eye-btn')||{}).innerText,
        masked_amounts: document.querySelectorAll('.masked .amt').length
    })"""))
    c.screenshot(os.path.join(OUT, "shot_privacy.png"))
    ev(c, "document.querySelector('#eye-btn').click()")
    time.sleep(1.2)
    res["privacy_off"] = json.loads(ev(c, r"""JSON.stringify({
        masked: document.body.classList.contains('masked'),
        total: (document.querySelector('#pa-total')||{}).innerText,
        eye: (document.querySelector('#eye-btn')||{}).innerText
    })"""))

    # ---- R-UI-14 因子四盘 ----
    c.navigate(BASE + "#/factors", settle=1.0)
    time.sleep(6)
    res["factors"] = json.loads(ev(c, r"""JSON.stringify({
        pans_children: document.querySelectorAll('#fc-pans > *').length,
        child_classes: Array.prototype.map.call(document.querySelectorAll('#fc-pans > *'), function(e){return e.className;}),
        pan_count_badges: document.querySelectorAll('#fc-pans .pb, #fc-pans .pan-count').length,
        factor_rows: document.querySelectorAll('#fc-pans .frow').length,
        books: document.querySelectorAll('#fc-books > *').length,
        lifecycle_class: (document.querySelector('#fc-life')||{}).className
    })"""))

    # ---- R-UI-22 / 26 引擎：竞技场 + 立方体 ----
    c.navigate(BASE + "#/engine", settle=1.0)
    time.sleep(6)
    res["engine_default"] = json.loads(ev(c, r"""JSON.stringify({
        prod_cells: document.querySelectorAll('#cube-prod .cc').length,
        prod_filled: document.querySelectorAll('#cube-prod .cc:not(.empty)').length,
        research_cells: document.querySelectorAll('#cube-research-grid .cc').length,
        arena_head: Array.prototype.map.call(document.querySelectorAll('#eg-arena-head th'), function(e){return e.innerText;}).join('|'),
        arena_body: (document.querySelector('#eg-arena')||{}).innerText,
        arena_legend: Array.prototype.map.call(document.querySelectorAll('#eg-arena-legend span'), function(e){return e.innerText;}).join('|'),
        cmp: (document.querySelector('#eg-cmp')||{}).innerText
    })"""))
    # switch vr layer 4
    ev(c, "document.querySelector('#eg-layers button[data-lay=\"3\"]').click()")
    time.sleep(1.2)
    res["engine_layer4"] = json.loads(ev(c, r"""JSON.stringify({
        prod_filled: document.querySelectorAll('#cube-prod .cc:not(.empty)').length,
        cs_prod: (document.querySelector('#cs-prod')||{}).innerText,
        first_cell_title: (document.querySelector('#cube-prod .cc')||{}).getAttribute ? document.querySelector('#cube-prod .cc').getAttribute('title') : null
    })"""))
    # open research naive
    ev(c, "document.querySelector('#cube-research').open = true")
    time.sleep(0.8)
    res["engine_naive"] = json.loads(ev(c, r"""JSON.stringify({
        research_visible: !!(document.querySelector('#cube-research').open),
        research_filled: document.querySelectorAll('#cube-research-grid .cc:not(.empty)').length,
        low_sample_marks: document.querySelectorAll('#cube-research-grid .low, #cube-research-grid [data-low-sample], #cube-prod .low').length,
        research_text_head: (document.querySelector('#cube-research')||{}).innerText.slice(0,200)
    })"""))
    c.screenshot(os.path.join(OUT, "shot_engine_full.png"))

    # ---- R-UI-33 LLM base_url ----
    c.navigate(BASE + "#/settings", settle=1.0)
    time.sleep(5)
    res["settings"] = json.loads(ev(c, r"""JSON.stringify({
        base_url_input: !!document.querySelector('#llm-url'),
        base_url_value: (document.querySelector('#llm-url')||{}).value,
        sw_hide_checked: (document.querySelector('#sw-hide')||{}).checked,
        st_registry_rows: document.querySelectorAll('#st-registry tr').length
    })"""))

    with open(os.path.join(OUT, "ui_interactions.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    c.close()


if __name__ == "__main__":
    main()
