# -*- coding: utf-8 -*-
"""S6 PM 终验 · 收尾核验：mock 未加载 / 无 JS 错误 / livebar / 未知行渲染。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP

OUT = os.path.abspath(os.path.join(HERE, ".."))
BASE = "http://127.0.0.1:8791/"


def main():
    c = CDP(9222)
    c.call("Emulation.setDeviceMetricsOverride",
           {"width": 1720, "height": 3000, "deviceScaleFactor": 1, "mobile": False})
    res = {}
    c.navigate(BASE + "#/holdings", settle=1.0)
    time.sleep(6)
    res["env"] = json.loads(c.eval(r"""JSON.stringify({
        zl_mock: (function(){try{return localStorage.getItem('zl_mock');}catch(e){return 'ERR';}})(),
        mock_js_loaded: performance.getEntriesByType('resource').some(function(r){return /mock\.js/.test(r.name);}),
        api_calls: performance.getEntriesByType('resource').filter(function(r){return /\/api\/v1\//.test(r.name);}).length,
        non_local_api: performance.getEntriesByType('resource').filter(function(r){return /\/api\/v1\//.test(r.name) && !/127\.0\.0\.1/.test(r.name);}).length,
        livebar: (document.getElementById('livebar')||{}).innerText,
        livebar_class: (document.getElementById('livebar')||{}).className,
        masked: document.body.classList.contains('masked')
    })"""))
    # 未知行渲染：找一行 valuation_mode=unknown 的涨跌/盈亏格
    res["unknown_row"] = json.loads(c.eval(r"""JSON.stringify((function(){
        var rows=document.querySelectorAll('#hd-body tr:not(.grp)');
        for (var i=0;i<rows.length;i++){
            var t=rows[i].innerText;
            if (t.indexOf('未知')>=0){
                var tds=rows[i].querySelectorAll('td');
                return {text:t.slice(0,160), cells:[].map.call(tds,function(d){return d.innerText.trim();})};
            }
        }
        return null;
    })())"""))
    with open(os.path.join(OUT, "final_probe.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("final probe done")
    c.close()


if __name__ == "__main__":
    main()
