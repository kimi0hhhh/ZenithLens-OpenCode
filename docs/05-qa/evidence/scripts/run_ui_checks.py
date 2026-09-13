# -*- coding: utf-8 -*-
"""S5 UI 组件实测：CDP 驱动真实 Chrome for Testing 遍历 7 Tab，采集 DOM 证据。

方法说明：agent-browser daemon 握手失败（Chrome exited early exit 3），
按派发约束改用 CDP 直连 Chrome for Testing（ms-playwright chromium-1243）。
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
      vsum_vb: n('#val-sum .vb'), vsum_text: (txt('#val-sum')||'').slice(0,300),
      forecast_cards: n('#pf-forecast .win'),
      forecast_text: (txt('#pf-forecast')||'').slice(0,700),
      cov_tiers: n('#cov-bar .cov'), cov_bar_html: (q('#cov-bar')||{}).innerHTML ? true : false,
      cov_note_len: (txt('#cov-note')||'').length,
      rows: n('#hd-body tr'), group_rows: n('#hd-body tr.grp'),
      valbadges: n('#hd-body .vb'), badge_classes: qa('#hd-body .vb').map(function(e){return e.className.replace('vb ','');}).slice(0,25),
      unknown_cells: n('#hd-body .unk'),
      plus_zero_zero: (document.body.innerText.match(/\+0\.00%/g)||[]).length,
      masked: document.body.classList.contains('masked'),
      fold_risk: !!q('#fold-risk'), pop: !!q('#pop'), toast: !!q('#toast'),
      dialogs: n('dialog')
    }
    """,
    "analyze": r"""
    {
      route: location.hash,
      defs_len: (txt('#an-defs')||'').length,
      defs_text: (txt('#an-defs')||'').slice(0,400),
      forecast_cards: n('#an-forecast .win'),
      weighting_len: (txt('#an-weighting')||'').length,
      weighting_text: (txt('#an-weighting')||'').slice(0,300),
      body_rows: n('#an-body tr')
    }
    """,
    "signals": r"""
    {
      route: location.hash,
      empty_text: (txt('#sg-empty')||'').slice(0,500),
      empty_facts: n('#sg-empty .fact'),
      empty_html_len: (q('#sg-empty')||{}).innerHTML ? q('#sg-empty').innerHTML.length : 0,
      gates: n('#sg-gates > *'), gates_text: (txt('#sg-gates')||'').slice(0,400),
      excl_len: (txt('#sg-excl')||'').length,
      excl_text: (txt('#sg-excl')||'').slice(0,300),
      excl_pp: /pp/.test(txt('#sg-excl')||''),
      tl_items: n('#tl-list .tl-item'), tl_text: (txt('#tl-list')||'').slice(0,200)
    }
    """,
    "factors": r"""
    {
      route: location.hash,
      pans: n('#fc-pans .pan'), pan_roles: qa('#fc-pans .pan').map(function(e){return e.getAttribute('data-role')||e.className;}).slice(0,6),
      pans_text: (txt('#fc-pans')||'').slice(0,500),
      books: n('#fc-books .book') || n('#fc-books .bcard') || n('#fc-books > *'),
      books_text: (txt('#fc-books')||'').slice(0,400),
      score_len: (txt('#fc-score')||'').length,
      cycle: n('#fc-cycle > *'),
      scan_rows: n('#fc-scan tr'),
      life_len: (txt('#fc-life')||'').length,
      scorechain_text: (txt('#fc-score')||'').slice(0,500)
    }
    """,
    "review": r"""
    {
      route: location.hash,
      hero_len: (txt('#rv-hero')||'').length, hero_text: (txt('#rv-hero')||'').slice(0,300),
      scores_rows: n('#rv-scores tr'), scores_text: (txt('#rv-scores')||'').slice(0,500),
      score_note_len: (txt('#rv-score-note')||'').length,
      degrade_text: (txt('#rv-degrade')||''), degrade_class: clsOf('#rv-degrade'),
      recon_rows: n('#rv-body tr')
    }
    """,
    "engine": r"""
    {
      route: location.hash,
      hud: n('#eg-hud .hud-c'), hud_text: (txt('#eg-hud')||'').slice(0,400),
      ledger_state: txt('#eg-ledger-state'),
      ledger_rows: n('#eg-ledger-rows tr'),
      prg_width: (q('#eg-prg .prg i')||{}).style ? q('#eg-prg .prg i').style.width : null,
      arena_head: n('#eg-arena-head th'), arena_rows: n('#eg-arena tr'),
      arena_legend: n('#eg-arena-legend span'),
      train_len: (txt('#eg-train')||'').length,
      frozen_rows: n('#eg-frozen .kv') || n('#eg-frozen tr') || n('#eg-frozen > *'),
      frozen_text: (txt('#eg-frozen')||'').slice(0,400),
      d3_bars: n('#dim-d3 .zbar'), d6_bars: n('#dim-d6 .zbar'),
      dim_asset_opts: n('#dim-asset option'),
      cube_prod_cells: n('#cube-prod .cc'), cube_prod_pct: n('#cube-prod .cc:not(.empty)'),
      cube_research_cells: n('#cube-research-grid .cc'),
      cube_layers: n('#eg-layers .laysel') || n('#eg-layers *'),
      cube_legend: n('#eg-cube-legend span'),
      cmp_len: (txt('#eg-cmp')||'').length, cmp_text: (txt('#eg-cmp')||'').slice(0,300),
      dualnote_len: (txt('#cube-dualnote')||'').length,
      registry_rows: n('#eg-registry tr')
    }
    """,
    "settings": r"""
    {
      route: location.hash,
      sw_hide: !!q('#sw-hide'), sw_hide_holdings: !!q('#sw-hide-holdings'),
      llm_provider: !!q('#llm-provider'), llm_url: !!q('#llm-url'), llm_key: !!q('#llm-key'), llm_model: !!q('#llm-model'),
      llm_status_len: (txt('#llm-status')||'').length,
      src_rows: n('#src-box tr') || n('#src-box .kv') || n('#src-box > *'),
      src_text: (txt('#src-box')||'').slice(0,300),
      hd_data_len: (txt('#hd-data')||'').length,
      hd_diff_len: (txt('#hd-diff')||'').length,
      hd_diff_text: (txt('#hd-diff')||'').slice(0,300),
      st_registry_rows: n('#st-registry tr'),
      about_len: (txt('#about-card')||'').length,
      about_text: (txt('#about-card')||'').slice(0,300)
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
    results = {}
    for route in ["holdings", "analyze", "signals", "factors", "review", "engine", "settings"]:
        c.navigate(BASE + "#/" + route, settle=1.0)
        # wait until the view is active and its slice settled
        ok = wait_for(c, "(function(){var v=document.getElementById('view-%s');"
                         "return v && v.classList.contains('active') && "
                         "(document.querySelector('#view-%s .state-block')?true:true);})()" % (route, route),
                      timeout=25)
        time.sleep(6.0)  # allow async slices
        try:
            raw = c.eval(HELPERS + "JSON.stringify(" + PROBES[route] + ")")
            results[route] = {"ok": True, "data": json.loads(raw)}
        except Exception as e:
            results[route] = {"ok": False, "error": str(e)}
        try:
            c.screenshot(os.path.join(OUT, "shot_%s.png" % route))
        except Exception as e:
            results[route]["shot_error"] = str(e)

    with open(os.path.join(OUT, "ui_components.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    c.close()


if __name__ == "__main__":
    main()
