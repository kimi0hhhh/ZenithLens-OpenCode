# -*- coding: utf-8 -*-
"""DOM probe for ambiguous UI areas (real data)."""
import json
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import CDP  # noqa: E402

CHROME = r"C:\Users\10719\.agent-browser\browsers\chrome-153.0.8010.36\chrome.exe"
CDP_PORT = 9337
PROFILE = r"C:\Users\10719\AppData\Local\Temp\opencode\chrome_qa_probe"
BASE = "http://127.0.0.1:8796/"


def launch():
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                             "--remote-debugging-port=%d" % CDP_PORT,
                             "--user-data-dir=" + PROFILE, "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("chrome not ready")


def main():
    proc = launch()
    try:
        c = CDP(CDP_PORT)
        # holdings
        c.navigate(BASE + "#/holdings", settle=3.2)
        d = c.eval("""(function(){
          var out={};
          out.hd=document.getElementById('hd-body').innerText.slice(0,1800);
          out.badges=Array.from(document.querySelectorAll('[data-vb-code]')).slice(0,8).map(function(e){return {code:e.getAttribute('data-vb-code'),cls:e.className,title:(e.title||'').slice(0,300)}});
          out.vt=Array.from(document.querySelectorAll('.vt,.tag')).slice(0,10).map(function(e){return {cls:e.className,txt:(e.innerText||'').slice(0,30),title:(e.title||'').slice(0,150)}});
          return out})()""")
        print("== holdings.hd =="); print(d.get("hd"))
        print("== badges ==")
        for b in (d.get("badges") or []):
            print(b["code"], "|", b["cls"], "|", b["title"][:200])
        print("== vt/tags ==")
        for b in (d.get("vt") or []):
            print(b["cls"], "|", b["txt"], "|", b["title"][:100])
        # analyze
        c.navigate(BASE + "#/analyze", settle=3.2)
        d = c.eval("""(function(){return {
          state:(document.getElementById('view-analyze')||{}).dataset?document.getElementById('view-analyze').dataset.state:null,
          block:(document.querySelector('#view-analyze .state-block')||{}).innerText||'',
          rows:document.querySelectorAll('#an-body tr').length,
          main:document.querySelector('#view-analyze .view-main')?getComputedStyle(document.querySelector('#view-analyze .view-main')).display:null
        }})()""")
        print("== analyze ==", json.dumps(d, ensure_ascii=False)[:600])
        # signals
        c.navigate(BASE + "#/signals", settle=3.0)
        d = c.eval("""(function(){
          var items=Array.from(document.querySelectorAll('#tl-list .tl-item'));
          var hist={};items.forEach(function(e){var k=e.className.replace('tl-item','').trim()||'(none)';hist[k]=(hist[k]||0)+1});
          return {items:items.length,hist:hist,txt:(document.getElementById('tl-list')||{}).innerText.slice(0,600),sg:(document.getElementById('sg-empty')||{}).innerText.slice(0,300)}})()""")
        print("== signals ==", json.dumps(d, ensure_ascii=False)[:900])
        # review
        c.navigate(BASE + "#/review", settle=3.0)
        d = c.eval("""(function(){
          var rows=Array.from(document.querySelectorAll('#rv-body tr')).slice(0,6).map(function(r){return r.innerText.replace(/\\n/g,' | ').slice(0,200)});
          var pending=Array.from(document.querySelectorAll('#rv-body tr')).filter(function(r){return r.innerText.indexOf('待回填')>=0}).length;
          var hit=Array.from(document.querySelectorAll('#rv-body tr')).filter(function(r){return r.innerText.indexOf('命中')>=0}).length;
          return {hero:(document.getElementById('rv-hero')||{}).innerText,rows:rows,pending:pending,hit:hit,total:document.querySelectorAll('#rv-body tr').length}})()""")
        print("== review ==", json.dumps(d, ensure_ascii=False)[:1400])
        # engine
        c.navigate(BASE + "#/engine", settle=3.5)
        d = c.eval("""(function(){return {
          hud:(document.getElementById('eg-hud')||{}).innerText,
          prg:(document.getElementById('eg-prg-note')||{}).innerText,
          shadow:(document.querySelector('#eg-hud .hud-c')||{}).innerText||''}})()""")
        print("== engine ==", json.dumps(d, ensure_ascii=False)[:800])
        # settings
        c.navigate(BASE + "#/settings", settle=3.2)
        d = c.eval("""(function(){
          var hits=Array.from(document.querySelectorAll('#src-box *')).filter(function(e){return e.children.length===0 && (e.innerText||'').indexOf('544')>=0}).map(function(e){return {tag:e.tagName,cls:e.className,text:(e.innerText||'').slice(0,120),fold:(function(){var p=e;while(p&&p!==document.body){if(p.tagName==='DETAILS')return true;p=p.parentElement}return false})()}});
          return {hits:hits,src:(document.getElementById('src-box')||{}).innerText.slice(0,700),ft:(document.querySelector('#src-box details')||{}).innerText||''}})()""")
        print("== settings ==", json.dumps(d, ensure_ascii=False)[:1400])
        c.close()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
