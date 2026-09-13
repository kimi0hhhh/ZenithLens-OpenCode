# -*- coding: utf-8 -*-
"""S6 PM 终验 · 真实浏览器实操（CDP 直连 Chrome）：
遍历 7 Tab、采集 40 组件 DOM 证据、核心口径交互（隐私/四态/推导链/立方体层/竞技场）。
agent-browser 若握手失败则沿用 CDP 直连（与 S5 一致，如实登记）。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP

BASE = "http://127.0.0.1:8791/"
OUT = os.path.abspath(os.path.join(HERE, ".."))

HELPERS = r"""
function q(s){return document.querySelector(s);}
function qa(s){return Array.prototype.slice.call(document.querySelectorAll(s));}
function txt(s){var e=q(s);return e?e.innerText.trim():null;}
function n(s){return document.querySelectorAll(s).length;}
function clsOf(s){var e=q(s);return e?e.className:null;}
"""

PROBES = {
    "holdings": r"""
    {
      route: location.hash,
      pa_total: txt('#pa-total'), pa_today: txt('#pa-today'),
      pa_pnl: txt('#pa-pnl'), pa_ret: txt('#pa-ret'),
      pa_today_sub: txt('#pa-today-sub'),
      livebar: txt('#livebar'), live_src: txt('#live-src'),
      vsum_text: (txt('#val-sum')||'').slice(0,600),
      vsum_badges: qa('#val-sum .vb').map(function(e){return e.innerText.trim();}),
      forecast_cards: n('#pf-forecast .win'),
      forecast_text: (txt('#pf-forecast')||'').slice(0,700),
      cov_tiers: n('#cov-bar .cov'), cov_text: (txt('#cov-bar')||'').slice(0,400),
      cov_note_len: (txt('#cov-note')||'').length,
      rows: n('#hd-body tr'), group_rows: n('#hd-body tr.grp'),
      valbadges: n('#hd-body .vb'),
      badge_pairs: qa('#hd-body .vb').map(function(e){return e.className.replace('vb ','')+'='+e.innerText.trim();}),
      unknown_cells: n('#hd-body .unk'),
      plus_zero_zero: (document.body.innerText.match(/\+0\.00%/g)||[]).length,
      masked: document.body.classList.contains('masked'),
      fold_risk: !!q('#fold-risk'), pop: !!q('#pop'), toast: !!q('#toast'),
      dialogs: n('dialog'),
      sw_regs: 0
    }
    """,
    "analyze": r"""
    {
      route: location.hash,
      defs_len: (txt('#an-defs')||'').length,
      defs_text: (txt('#an-defs')||'').slice(0,600),
      forecast_cards: n('#an-forecast .win'),
      forecast_text: (txt('#an-forecast')||'').slice(0,600),
      weighting_len: (txt('#an-weighting')||'').length,
      weighting_text: (txt('#an-weighting')||'').slice(0,400),
      body_rows: n('#an-body tr'),
      an_body_text: (txt('#an-body')||'').slice(0,500)
    }
    """,
    "signals": r"""
    {
      route: location.hash,
      empty_text: (txt('#sg-empty')||'').slice(0,700),
      empty_facts: n('#sg-empty .fact'),
      gates: n('#sg-gates > *'), gates_text: (txt('#sg-gates')||'').slice(0,600),
      excl_len: (txt('#sg-excl')||'').length,
      excl_text: (txt('#sg-excl')||'').slice(0,500),
      excl_pp: /pp/.test(txt('#sg-excl')||''),
      tl_items: n('#tl-list .tl-item'), tl_text: (txt('#tl-list')||'').slice(0,300),
      sigcards: n('#tl-list .sigcard')
    }
    """,
    "factors": r"""
    {
      route: location.hash,
      pans: n('#fc-pans .pan'), pan_roles: qa('#fc-pans .pan').map(function(e){return e.getAttribute('data-role')||e.className;}).slice(0,8),
      pans_text: (txt('#fc-pans')||'').slice(0,700),
      frows: n('#fc-pans .frow'),
      books: n('#fc-books .book') || n('#fc-books .bcard') || n('#fc-books > *'),
      books_text: (txt('#fc-books')||'').slice(0,600),
      score_len: (txt('#fc-score')||'').length, score_text: (txt('#fc-score')||'').slice(0,500),
      cycle: n('#fc-cycle > *'), cycle_text: (txt('#fc-cycle')||'').slice(0,400),
      scan_rows: n('#fc-scan tr'),
      life_len: (txt('#fc-life')||'').length, life_text: (txt('#fc-life')||'').slice(0,400)
    }
    """,
    "review": r"""
    {
      route: location.hash,
      hero_len: (txt('#rv-hero')||'').length, hero_text: (txt('#rv-hero')||'').slice(0,400),
      scores_rows: n('#rv-scores tr'), scores_text: (txt('#rv-scores')||'').slice(0,600),
      score_note_len: (txt('#rv-score-note')||'').length,
      degrade_text: (txt('#rv-degrade')||''), degrade_class: clsOf('#rv-degrade'),
      recon_rows: n('#rv-body tr'), recon_text: (txt('#rv-body')||'').slice(0,300)
    }
    """,
    "engine": r"""
    {
      route: location.hash,
      hud: n('#eg-hud .hud-c'), hud_text: (txt('#eg-hud')||'').slice(0,600),
      ledger_state: txt('#eg-ledger-state'),
      ledger_rows: n('#eg-ledger-rows tr'),
      prg_width: (q('#eg-prg .prg i')||{}).style ? q('#eg-prg .prg i').style.width : null,
      arena_head: n('#eg-arena-head th'), arena_rows: n('#eg-arena tr'),
      arena_legend: n('#eg-arena-legend span'), arena_text: (txt('#eg-arena')||'').slice(0,300),
      train_len: (txt('#eg-train')||'').length, train_text: (txt('#eg-train')||'').slice(0,500),
      frozen_rows: n('#eg-frozen .kv') || n('#eg-frozen tr') || n('#eg-frozen > *'),
      frozen_text: (txt('#eg-frozen')||'').slice(0,600),
      d3_bars: n('#dim-d3 .zbar'), d6_bars: n('#dim-d6 .zbar'),
      dims_text: (txt('#dim-d3')||'').slice(0,300) + ' || ' + (txt('#dim-d6')||'').slice(0,400),
      dim_asset_opts: n('#dim-asset option'),
      cube_prod_cells: n('#cube-prod .cc'), cube_prod_filled: n('#cube-prod .cc:not(.empty)'),
      cube_research_cells: n('#cube-research-grid .cc'),
      cube_legend: n('#eg-cube-legend span'), cube_legend_text: (txt('#eg-cube-legend')||'').slice(0,300),
      cmp_len: (txt('#eg-cmp')||'').length, cmp_text: (txt('#eg-cmp')||'').slice(0,400),
      dualnote_len: (txt('#cube-dualnote')||'').length,
      registry_rows: n('#eg-registry tr'),
      low_marks: n('#cube-prod .low, #cube-prod .low-mark, #cube-research-grid .low')
    }
    """,
    "settings": r"""
    {
      route: location.hash,
      sw_hide: !!q('#sw-hide'), sw_hide_holdings: !!q('#sw-hide-holdings'),
      llm_provider: !!q('#llm-provider'), llm_url: !!q('#llm-url'), llm_key: !!q('#llm-key'), llm_model: !!q('#llm-model'),
      llm_status_len: (txt('#llm-status')||'').length,
      src_rows: n('#src-box tr') || n('#src-box .kv') || n('#src-box > *'),
      src_text: (txt('#src-box')||'').slice(0,500),
      hd_data_len: (txt('#hd-data')||'').length, hd_data_text: (txt('#hd-data')||'').slice(0,400),
      hd_diff_len: (txt('#hd-diff')||'').length, hd_diff_text: (txt('#hd-diff')||'').slice(0,500),
      st_registry_rows: n('#st-registry tr'),
      about_len: (txt('#about-card')||'').length, about_text: (txt('#about-card')||'').slice(0,400)
    }
    """
}


def wait_for(c, expr, timeout=30.0, interval=0.6):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if c.eval(expr):
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def main():
    c = CDP(9222)
    c.call("Emulation.setDeviceMetricsOverride",
           {"width": 1720, "height": 3000, "deviceScaleFactor": 1, "mobile": False})
    res = {"routes": {}, "interactions": {}}
    for route in ["holdings", "analyze", "signals", "factors", "review", "engine", "settings"]:
        c.navigate(BASE + "#/" + route, settle=1.0)
        wait_for(c, "(function(){var v=document.getElementById('view-%s');"
                   "return v && v.classList.contains('active');})()" % route, timeout=25)
        time.sleep(6.0)
        try:
            raw = c.eval(HELPERS + "JSON.stringify(" + PROBES[route] + ")")
            res["routes"][route] = {"ok": True, "data": json.loads(raw)}
        except Exception as e:
            res["routes"][route] = {"ok": False, "error": str(e)}
        try:
            c.screenshot(os.path.join(OUT, "shot_%s.png" % route))
        except Exception as e:
            res["routes"][route]["shot_error"] = str(e)

    it = res["interactions"]

    # ---- R-UI-13 推导链弹窗六步 ----
    c.navigate(BASE + "#/analyze", settle=1.0)
    time.sleep(6)
    try:
        c.eval("document.querySelector('#an-body tr[data-code]').click()")
        time.sleep(2.5)
        it["chain"] = json.loads(c.eval(r"""JSON.stringify({
            modal: !!document.querySelector('#zl-modal.show'),
            items: document.querySelectorAll('#zl-modal .chain-item').length,
            on_items: document.querySelectorAll('#zl-modal .chain-item.on').length,
            steps_text: ((document.querySelector('#zl-modal')||{}).innerText||'').slice(0,700)
        })"""))
        c.screenshot(os.path.join(OUT, "shot_chain.png"))
        c.eval("(document.querySelector('#zl-modal [data-close]')||{click:function(){}}).click()")
    except Exception as e:
        it["chain"] = {"error": str(e)}

    # ---- R-UI-09 信号时间线 sigcard 展开事件链（若有） ----
    c.navigate(BASE + "#/signals", settle=1.0)
    time.sleep(5)
    try:
        it["signal_tl"] = json.loads(c.eval(r"""JSON.stringify({
            sigcards: document.querySelectorAll('#tl-list .sigcard').length,
            tl_items: document.querySelectorAll('#tl-list .tl-item').length,
            empty_facts: document.querySelectorAll('#sg-empty .fact').length,
            empty_text: ((document.querySelector('#sg-empty')||{}).innerText||'').slice(0,400)
        })"""))
    except Exception as e:
        it["signal_tl"] = {"error": str(e)}

    # ---- R-UI-22/25/26 引擎：vr 层切换 + naive 折叠 + 六维 ----
    c.navigate(BASE + "#/engine", settle=1.0)
    time.sleep(6)
    try:
        c.eval("document.querySelector('#eg-layers button[data-lay=\"3\"]').click()")
        time.sleep(1.2)
        it["engine_layer3"] = json.loads(c.eval(r"""JSON.stringify({
            prod_filled: document.querySelectorAll('#cube-prod .cc:not(.empty)').length,
            cs_prod: ((document.querySelector('#cs-prod')||{}).innerText||'')
        })"""))
        c.eval("document.querySelector('#cube-research').open = true")
        time.sleep(1.0)
        it["engine_naive"] = json.loads(c.eval(r"""JSON.stringify({
            research_open: !!(document.querySelector('#cube-research')||{}).open,
            research_filled: document.querySelectorAll('#cube-research-grid .cc:not(.empty)').length,
            low_marks: document.querySelectorAll('#cube-research-grid .low, #cube-research-grid [data-low-sample], #cube-prod .low').length
        })"""))
        c.screenshot(os.path.join(OUT, "shot_engine_full.png"))
    except Exception as e:
        it["engine_layer3"] = {"error": str(e)}

    # ---- R-UI-37 行菜单 popover + dialog ----
    c.navigate(BASE + "#/holdings", settle=1.0)
    time.sleep(5)
    try:
        c.eval("(document.querySelector('#hd-body tr[data-code] .rowmenu, #hd-body tr[data-code] [data-menu]')||{click:function(){}}).click()")
        time.sleep(0.8)
        it["rowmenu"] = json.loads(c.eval(r"""JSON.stringify({
            pop_visible: (function(){var p=document.querySelector('#pop');return !!(p && p.classList.contains('show'))})(),
            dialogs: document.querySelectorAll('dialog').length,
            has_add_dialog: !!document.querySelector('#dlg-fund'),
            has_amt_dialog: !!document.querySelector('#dlg-amt'),
            has_del_dialog: !!document.querySelector('#dlg-del')
        })"""))
    except Exception as e:
        it["rowmenu"] = {"error": str(e)}

    # ---- R-UI-32 隐私打码 ----
    try:
        before = c.eval("(document.querySelector('#pa-total')||{}).innerText")
        c.eval("document.querySelector('#eye-btn').click()")
        time.sleep(1.2)
        it["privacy_on"] = json.loads(c.eval(r"""JSON.stringify({
            masked: document.body.classList.contains('masked'),
            total: ((document.querySelector('#pa-total')||{}).innerText||''),
            ret: ((document.querySelector('#pa-ret')||{}).innerText||''),
            masked_amounts: document.querySelectorAll('.masked .amt').length
        })"""))
        c.screenshot(os.path.join(OUT, "shot_privacy.png"))
        c.eval("document.querySelector('#eye-btn').click()")
        time.sleep(1.2)
        it["privacy_off"] = json.loads(c.eval(r"""JSON.stringify({
            masked: document.body.classList.contains('masked'),
            total: ((document.querySelector('#pa-total')||{}).innerText||'')
        })"""))
        it["privacy_before_total"] = before
    except Exception as e:
        it["privacy_on"] = {"error": str(e)}

    # ---- R-UI-40 四态 ----
    states = {}
    try:
        for st in ["empty", "loading", "error", "success"]:
            c.eval("document.querySelector('#statebar-btns button[data-st=\"%s\"]').click()" % st)
            time.sleep(0.7)
            states[st] = json.loads(c.eval(r"""JSON.stringify({
                cls: ((document.querySelector('#view-holdings .state-block')||{}).className||''),
                text: (((document.querySelector('#view-holdings .state-block')||{}).innerText)||'').slice(0,120),
                has_retry: !!document.querySelector('#view-holdings .state-block [data-retry]')
            })"""))
            if st in ("empty", "loading", "error"):
                c.screenshot(os.path.join(OUT, "shot_state_%s.png" % st))
        c.eval("document.querySelector('#statebar-btns button[data-st=\"success\"]').click()")
        time.sleep(1.5)
    except Exception as e:
        states["error"] = str(e)
    it["states"] = states

    # ---- R-UI-38 Service Worker 注销 ----
    try:
        it["sw"] = json.loads(c.eval(r"""JSON.stringify({
            supported: ('serviceWorker' in navigator),
            regs: 0
        })"""))
        it["sw"]["regs"] = c.eval("(function(){try{return navigator.serviceWorker.getRegistrations().then(function(r){return r.length;}); }catch(e){return -1;}})()", await_promise=True)
    except Exception as e:
        it["sw"] = {"error": str(e)}

    with open(os.path.join(OUT, "ui_components.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("routes ok:", sum(1 for r in res["routes"].values() if r.get("ok")), "/7")
    print(json.dumps(it, ensure_ascii=False, indent=1)[:5000])
    c.close()


if __name__ == "__main__":
    main()
