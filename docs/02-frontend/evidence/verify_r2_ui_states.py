# -*- coding: utf-8 -*-
"""R2 前端升级 + S5 修复轮断言（静态托管 + Edge headless + stdlib CDP；无需真实后端）。

阶段 A（?mock=1 · mock 替身，默认关闭）：七页 success 渲染 R2 触点
  —— U-01 成绩位 / U-02 双层徽章+7 项 tooltip / U-04 回填态 / U-05 影子盘进度 /
     U-06 数据源与主源 / U-07 验证四态 / U-08 QDII 标注 / U-11 口径。
阶段 B（?stub=empty|error|loading，经 window.fetch 桩，真实走 api.js → loadSlice → emptyWhen）：
  —— U-03 四态真实触发：七页 empty 文案含「为什么空」、error 含「重试」、loading 有骨架。
阶段 C（S5 修复轮 §8.10 前端栏）：
  —— R2-D1 A1~A3（rows=15 且 open_count=0 → success；空态二分支；负向文案）；
     R2-D4 histNote 分支；BLOCK-A1 本地校验（无出站请求）；BLOCK-A2 S1~S4（含启动水合）；
     BLOCK-A3 chain_available 分支；S-a bootstrap 实测/兼容；F-3 judges 值缺失标注。

用法：python verify_r2_ui_states.py
产物：本目录 zl_r2_state_empty_holdings.png / zl_r2_state_error_engine.png
退出码：0 全过 / 1 有 FAIL。
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = r"C:\Users\10719\Documents\ZenithLens-OpenCode\static"
sys.path.insert(0, r"C:\Users\10719\Documents\ZenithLens-OpenCode\docs\05-qa\evidence\scripts")
from cdp import CDP  # noqa: E402

HTTP_PORT = 18796
CDP_PORT = 9334
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = r"C:\Users\10719\AppData\Local\Temp\opencode\edgeprof_r2_verify"

results = []
loglines = []
# 控制台可能为 GBK 无法编码 '¥' 等字符：结果全量另写 UTF-8 报告（不因打印失败中断）
REPORT_PATH = os.path.join(tempfile.gettempdir(), "opencode", "r2_verify_report.txt")


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    line = ("PASS " if ok else "FAIL ") + name
    if detail:
        line += " | " + str(detail)[:220]
    loglines.append(line)
    try:
        print(line)
    except Exception:
        try:
            print(line.encode("utf-8", "replace").decode("ascii", "replace"))
        except Exception:
            pass
    sys.stdout.flush()


# ---------------- 静态服务 ----------------
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def serve():
    handler = lambda *a, **kw: QuietHandler(*a, directory=STATIC, **kw)  # noqa: E731
    httpd = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


# ---------------- fetch 桩：驱动真实 emptyWhen / S5 断言场景 ----------------
STUB = r"""
(function () {
  var realFetch = window.fetch.bind(window);
  window.__fetchCalls = window.__fetchCalls || 0;
  function resp(env) {
    return new Response(JSON.stringify(env), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }
  function ok(data) { return resp({ ok: true, data: data, error: null, as_of: '2026-01-01' }); }
  function qq() { return new URLSearchParams(location.search); }
  function predRow(i) {
    var code = ('00000' + (100 + i)).slice(-6);
    return { code: code, gate: 'E3', gate_label: '无量急跌', tier: 'A', market_value: 1000 + i, p_up: 0.55,
      ddsm_state: [1, 2, 2], veto_crowd: false, veto_crowd_status: 'pass', veto_klow2: false, veto_klow2_status: 'pass',
      signal: 'gray', signal_label: '灰', reason: 'below_band', qdii_lead_note: null,
      windows: { T1: { window: 'T1', direction: 'gray', weighted_p: 0.55, validation_status: 'brief_mandated', formula: 'gate+ddsm+veto' },
                 T3: { window: 'T3', direction: 'gray', validation_status: 'pending_cv' },
                 T15: { window: 'T15', direction: 'gray', weighted_p: 0.597, validation_status: 'pending_cv' } } };
  }
  function abRow(j) {
    return { code: ('10000' + j).slice(-6), name: 'stub-' + j, group: 'active', group_label: '主动', tier: 'A',
      shares: 1, cost_amount: 100, confirm_days: 1, proxy_code: null, proxy_name: null,
      valuation: { valuation_mode: 'official', mode_label: '官方净值', change_rate: 0.01, confidence: 'high',
        confidence_label: '误差达标', confidence_color_class: 'ch', nav_date: '2026-01-01',
        written_at: '2026-01-01T15:30:00+08:00', mae_rate: null, dir_hit_rate: null, n_test: null, conf_reason: null },
      nav: null, prediction: null, market_value: 101, mv_source: 'nav', fallback_value: 0, weight_ratio: 0.5,
      today_pnl_amt: 1, pnl_amt: 1, return_rate: 0.01, verify_status: 'validated', verify_status_label: '已验证', tier_reason: null };
  }
  function panFixture() {
    return { role: 'adopted', role_label: '正式盘', description: '', factor_count: 1, pan_status: 'on',
      caps: { veto_max: 4, score_max: 3 }, nomination_limit: null, rule_text: '',
      factors: [{ factor_id: 'klow2', name: 'stub-factor', role: 'adopted', role_label: '否决位', score: 10,
        total_score: 10, status: 'active', license: 'full_t3', license_label: '正式',
        lift_bars: [{ window: 'd15', window_label: '15日', lift: 1.2 }], independent_trigger_days: 5,
        death_condition: null, note: '', ab_progress: null, added_at: '2026-01-01' }] };
  }
  function scoreChainFixture(hasMeasured) {
    return { lift_bins: [], window_weights: [], formula_text: '',
      bootstrap_percentiles: { p50: -10.8, p90: 38.7, p95: 48.4, p99: 61.7, p995: 64.1 },
      bootstrap_percentiles_measured: hasMeasured ? { p50: -12.4, p90: 40.1, p95: 50.2, p99: 63.5, p995: 66.0 } : null,
      real_engine: hasMeasured, judges: [], floor_note: '', rule_source: '' };
  }
  function scoreDetailFixture() {
    return { factor_id: 'klow2', name: 'stub', total_score: 10,
      windows: [{ window: 'd15', window_label: '15日', lift: 1.2, k_lift: 1, weight: 8, independent_trigger_days: 5, n_w: 5, admission: 1, score: 8, cliff_hit: '' }],
      bootstrap_percentiles: { p50: -10.8, p90: 38.7, p95: 48.4, p99: 61.7, p995: 64.1 },
      judges: [{ judge: 'lift', scope: '分数', metric: 'k_lift', value: null, note: '' }], formula_text: '' };
  }
  function ledgerFixture(ca) {
    return { date: '2026-09-10', code: '014320', name: 'stub-fund', tier: 'A', gate: 'E3', p_up: 0.55,
      ddsm_state: [1, 2, 2], veto_crowd: false, veto_klow2: false, signal: 'up', t1_real: 0.0124,
      t1_real_method: 'proxy_bar', backfill_proxy_code: '512480', result: 'hit',
      chain_available: ca, created_at: '2026-09-10T15:30:00+08:00', written_at: '2026-09-10T15:30:00+08:00' };
  }
  function chainSteps() {
    var keys = [['gate', '① 触发门'], ['ddsm', '② DDSM'], ['veto_crowd', '③ 拥挤度否决'], ['veto_klow2', '④ KLOW2 否决'], ['exit', '⑤ 出口'], ['output', '⑥ 输出']];
    return keys.map(function (k, i) { return { step: i + 1, key: k[0], title: k[1], status: 'on',
      detail: (i === 5 ? '命中 +1.24%' : ''), metrics: (i === 4 ? { exit_threshold: 0.52 } : {}) }; });
  }
  window.fetch = function (input, init) {
    try {
      var url = (typeof input === 'string') ? input : ((input && input.url) || '');
      if (url.indexOf('/api/v1/') < 0) return realFetch(input, init);
      var q = qq();
      var mode = q.get('stub');
      if (!mode) return realFetch(input, init);
      window.__fetchCalls += 1;
      if (mode === 'error') {
        return Promise.resolve(resp({ ok: false, data: null, error: { code: 'E_IO', message: 'stub failure' }, as_of: null }));
      }
      if (mode === 'loading') {
        return new Promise(function (resolve) {
          setTimeout(function () { resolve(ok({})); }, 60000);
        });
      }
      var p = '/' + url.split('/api/v1/')[1].split('?')[0];
      // ---- S5 参数化场景（默认走下方 empty 形状） ----
      var anpred = parseInt(q.get('anpred') || '0', 10);
      if (p === '/predictions' && anpred > 0) {
        var prows = []; for (var i = 0; i < anpred; i++) prows.push(predRow(i));
        return Promise.resolve(ok({ rows: prows, engine_status: 'offline', as_of: '2026-01-01' }));
      }
      var ab = parseInt(q.get('ab') || '0', 10);
      if (p === '/holdings' && ab > 0) {
        var hrows = []; for (var j = 0; j < ab; j++) hrows.push(abRow(j));
        return Promise.resolve(ok({ rows: hrows, summary: { total_value: 2000, total_count: ab, covered_count: ab, fallback_value: 0, coverage_note: '', as_of: '2026-01-01' } }));
      }
      var arch = q.get('arch');
      if (arch != null && p === '/engine/status') {
        return Promise.resolve(ok({ status: 'online', port: 8791, last_heartbeat_at: '2026-09-13T09:00:00+08:00',
          last_success_at: '2026-09-13T09:00:00+08:00', snapshot_as_of: '2026-09-13', shadow_status: 'qualified',
          shadow_audit_status: 'idle', shadow_consecutive_days: 60, shadow_target_days: 60, training_assets: 38,
          index_only_assets: 3, state_grid_total_cells: 125, state_grid_filled_cells: 118, state_grid_coverage_pct: 0.944,
          last_retrain_at: null, next_retrain_at: null, data_freshness_snapshot_date: '2026-09-13', data_freshness_days_behind: 1 }));
      }
      if (arch != null && p === '/ledger/shadow') {
        return Promise.resolve(ok({ rows: [], total: 0, summary: {},
          progress: { status: 'qualified', consecutive_days: 60, target_days: 60, progress_ratio: 1.0,
            window_days: 60, archive_merged: arch === '1', history_days: 60, baseline_source: 'measured',
            note: '窗口 60 交易日；记录按走前口径回算补全（启动回填）；上线资格建议结合实盘观察另行评估' },
          field_list: [], retention_policy: '', first_of_day_immutable: true, archive_manifest_at: null,
          insert_only_note: '', backfill_method: 'proxy_bar', backfill_method_note: '', as_of: '2026-01-01' }));
      }
      if (q.get('pan') === '1' && p === '/factors/pans') return Promise.resolve(ok({ pans: [panFixture()] }));
      var meas = q.get('meas');
      if (meas != null && p === '/factors/score-chain') return Promise.resolve(ok(scoreChainFixture(meas === '1')));
      if (q.get('detail') === '1' && p === '/factors/score-detail') return Promise.resolve(ok(scoreDetailFixture()));
      var ch = q.get('chain');
      if (ch != null && p === '/ledger') return Promise.resolve(ok({ rows: [ledgerFixture(ch === '1')], total: 1 }));
      if (ch != null && p === '/signals/state') {
        return Promise.resolve(ok({ state: 'no_open', monitored_count: 1, total_count: 1, days_since_last_open: 1,
          last_open: { date: '2026-09-10', code: '014320', name: 'stub', gate: 'E3', result: 'hit', t1_real: 0.01 },
          last_result: 'hit', empty_note: 'stub', gates: [], excluded_gates: [], or_merge_forbidden: true,
          rolling_open_assets: 33, rolling_window_days: 60, low_frequency_note: '60 交易日窗口内开口为低频事件，多数交易日不开口是常态' }));
      }
      if (ch != null && p === '/ledger/chain') {
        return Promise.resolve(ok({ date: '2026-09-10', code: '014320', name: 'stub', gate: 'E3', signal: 'up', p_up: 0.55,
          chain: chainSteps(), metrics: {}, source_ledger: 'shadow_signals.jsonl', created_at: '2026-09-10T15:30:00+08:00' }));
      }
      // ---- 默认 empty 形状（成功但集合为空） ----
      var data = {};
      if (p === '/holdings') data = { rows: [], summary: { total_value: 0, total_count: 0, covered_count: 0, fallback_value: 0, coverage_note: '', as_of: '2026-01-01' } };
      else if (p === '/predictions') data = { rows: [], engine_status: 'offline', as_of: '2026-01-01' };
      else if (p === '/portfolio/forecast') data = { windows: [
        { window: 'T1', open_count: 0, coverage_ratio: 0, weighted_p: null, direction: 'gray', direction_reason: 'no_open' },
        { window: 'T3', open_count: 0, coverage_ratio: 0, weighted_p: null, direction: 'gray', direction_reason: 'no_open' },
        { window: 'T15', open_count: 0, coverage_ratio: 0, weighted_p: null, direction: 'gray', direction_reason: 'no_open' }
      ], engine_status: 'offline', as_of: '2026-01-01' };
      else if (p === '/ledger') data = { rows: [], total: 0 };
      else if (p === '/signals/state') data = { state: 'no_open', monitored_count: 0, total_count: 0, days_since_last_open: null, last_open: null, last_result: 'pending', empty_note: 'stub', gates: [], excluded_gates: [], or_merge_forbidden: true };
      else if (p === '/factors/pans') data = { pans: [] };
      else if (p === '/review/scores') data = { scores: [], hero: null };
      else if (p === '/engine/status') data = { status: 'offline', last_heartbeat_at: null, last_success_at: null, snapshot_as_of: null, shadow_status: 'not_started', shadow_consecutive_days: 0, shadow_target_days: 60 };
      else if (p === '/data-sources/health') data = { sources: [] };
      else if (p === '/settings' && mode === 'privacy') data = { privacy: { masked: true, mask_holdings_only: true }, llm: { enabled: false, provider: 'deepseek', model: 'deepseek-chat', api_key_set: false, temperature: 0, output_format: 'json', mode: 'shadow' }, port: 8787, auto_refresh: true, refresh_interval_sec: 300, theme: 'light' };
      return Promise.resolve(ok(data));
    } catch (e) {
      return realFetch(input, init);
    }
  };
})();
"""


def launch_edge():
    if not os.path.exists(EDGE):
        raise RuntimeError("edge not found: " + EDGE)
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--remote-debugging-port=%d" % CDP_PORT,
        "--user-data-dir=" + PROFILE,
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/json/version" % CDP_PORT, timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("edge devtools not ready")


ROUTES = ["holdings", "analyze", "signals", "factors", "review", "engine", "settings"]

PAGE_CN = {
    "holdings": "持仓", "analyze": "分析", "signals": "信号", "factors": "因子",
    "review": "复盘", "engine": "引擎", "settings": "设置",
}


def main():
    httpd = serve()
    proc = launch_edge()
    try:
        c = CDP(CDP_PORT)
        c.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
        c.call("Network.enable")
        c.call("Network.setCacheDisabled", {"cacheDisabled": True})

        base = "http://127.0.0.1:%d/index.html" % HTTP_PORT

        # ============ 阶段 A：mock success + R2 触点 ============
        c.navigate(base + "?mock=1#/holdings", settle=2.6)
        check("A 持仓 success", c.eval("document.getElementById('view-holdings').dataset.state") == "success")
        vs = c.eval("(document.getElementById('val-sum')||{}).innerText||''")
        check("A vsum 主指标=估算档", "估算档市值加权" in vs)
        check("A vsum 官方档单列（既成事实）", "官方档" in vs and "既成事实" in vs)
        check("A vsum 全档参考（语义登记）", "全档参考" in vs)
        check("A vsum 精度窗累计 12/40", "12/40" in vs)
        hd = c.eval("(document.getElementById('hd-body')||{}).innerText||''")
        check("A 持仓行 QDII 领先标注", "QDII · 境内代理领先净值 1–2 天" in hd)
        check("A 持仓行 C 档验证四态（验证中）", "验证中" in hd)
        check("A 持仓行 D 档「暴露待定」", "暴露待定" in hd)
        nvb = c.eval("document.querySelectorAll('[data-vb-code]').length")
        check("A 徽章双层渲染（8 只）", nvb and nvb >= 8, nvb)
        tip_hold = c.eval("(document.querySelector('[data-vb-code=\"013566\"]')||{}).title||''")
        for kw in ["来源：", "降级链路", "MAE", "方向命中率", "样本", "回测窗", "披露口径"]:
            check("A 徽章 tooltip 7 项 · " + kw, kw in tip_hold)
        tip_unk = c.eval("(document.querySelector('[data-vb-code=\"025500\"]')||{}).title||''")
        check("A unknown 必带原因（conf_reason）", "未知原因：" in tip_unk, tip_unk[:60])
        check("A 全局无 +0.00%", c.eval("document.body.innerText.indexOf('+0.00%') === -1"))
        # C0/E-1：顶栏日期=本地时区（非 UTC；本地 00:00–08:00 时段该断言可捕获原 toISOString 缺陷）
        topd = c.eval("(document.getElementById('top-date')||{}).textContent||''")
        locald = c.eval("(function(){var d=new Date();var p=function(n){return String(n).padStart(2,'0');};return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());})()")
        utcd = c.eval("new Date().toISOString().slice(0,10)")
        check("E-1 顶栏日期=本地时区（非 UTC）",
              topd.startswith(locald) and (utcd == locald or not topd.startswith(utcd)),
              topd + " / local=" + locald + " / utc=" + utcd)
        # C0/E-2：持仓卡副标题口径词=「估值覆盖」（不再直出「可信估值覆盖」）
        subh = c.eval("(document.getElementById('pa-today-sub')||{}).innerText||''")
        check("E-2 副标题=「估值覆盖 X/Y 只」（无「可信估值覆盖」）",
              ("估值覆盖 " in subh) and ("可信估值覆盖" not in subh), subh[:80])
        # C0/E-3：未知组标签=字典「无可信估算」（不再显示裸「无」）
        check("E-3 未知组标签=「无可信估算」", ("无可信估算" in vs) and ("无 1 只" not in vs), vs[:120])

        c.navigate(base + "?mock=1#/analyze", settle=2.6)
        check("A 分析 success", c.eval("document.getElementById('view-analyze').dataset.state") == "success")
        check("A 分析预测表有行", c.eval("document.querySelectorAll('#an-body tr').length") > 0)

        c.navigate(base + "?mock=1#/signals", settle=2.6)
        check("A 信号 success", c.eval("document.getElementById('view-signals').dataset.state") == "success")
        check("A 时间线渲染台账行", c.eval("document.querySelectorAll('#tl-list .tl-item').length") > 0)
        stl = c.eval("(document.getElementById('tl-list')||{}).innerText||''")
        check("A 回填态：待回填仅未到期", "待回填" in stl, stl[:60])
        sge = c.eval("(document.getElementById('sg-empty')||{}).innerText||''")
        check("A 信号空态卡（变体②）四要素+低频（60 日口径）", "今日无信号" in sge and "近 60 交易日" in sge)

        c.navigate(base + "?mock=1#/factors", settle=2.6)
        check("A 因子 success", c.eval("document.getElementById('view-factors').dataset.state") == "success")
        check("A 因子四盘渲染", c.eval("document.querySelectorAll('#fc-pans .card').length") >= 4)
        # C1 · 四本账本人话记录（默认非裸 JSON）+ 原始数据切换保留（审计视图）
        books_txt = c.eval("(document.getElementById('fc-books')||{}).innerText||''")
        check("C1 账本摘要人话渲染（非 JSON）",
              ("klow2" in books_txt) and ("RESI30" in books_txt) and ('{"' not in books_txt) and ("factor_id" not in books_txt),
              books_txt[:120])
        c.eval("document.querySelector('#fc-books [data-book]').click()")
        time.sleep(0.9)
        nrec = c.eval("document.querySelectorAll('#zl-modal .bookrec').length")
        check("C1 弹窗默认人话记录列表", nrec and nrec > 0, nrec)
        raw_hidden = c.eval("getComputedStyle(document.querySelector('#zl-modal [data-bk-view=\"raw\"]')).display")
        check("C1 弹窗默认隐藏原始数据", raw_hidden == "none", raw_hidden)
        c.eval("document.querySelector('#zl-modal [data-bk-toggle]').click()")
        time.sleep(0.3)
        raw_shown = c.eval("getComputedStyle(document.querySelector('#zl-modal [data-bk-view=\"raw\"]')).display") != "none"
        raw_has_table = c.eval("document.querySelectorAll('#zl-modal [data-bk-view=\"raw\"] table').length") > 0
        check("C1 原始数据切换保留（审计视图）", raw_shown and raw_has_table, (raw_shown, raw_has_table))

        c.navigate(base + "?mock=1#/review", settle=2.6)
        rv = c.eval("(document.getElementById('rv-hero')||{}).innerText||''")
        check("A 复盘 hero 出数（回测 tag + Δ）", "回测" in rv and "58.3%" in rv and "9.9pp" in rv, rv[:80])
        rvs = c.eval("(document.getElementById('rv-scores')||{}).innerText||''")
        check("A 三窗口「待填充」纪律", "待填充" in rvs)
        check("A 三窗口注明全样本窗", "全样本窗" in rvs)
        check("A 逐笔对账渲染", c.eval("document.querySelectorAll('#rv-body tr').length") > 0)
        # C0/E-4：降级条补样本数（shadow_live hero.open_count）+ 样本不足提示
        deg = c.eval("(document.getElementById('rv-degrade')||{}).innerText||''")
        check("E-4 降级条含样本数（样本 4 笔）+ 样本不足提示",
              ("样本 4 笔" in deg) and ("样本不足" in deg), deg[:140])
        # v9.5/PM：偏差审查条同挂回算口径标签（与前向/实盘语义分离）
        dnote = c.eval("(document.getElementById('rv-degrade-note')||{}).innerText||''")
        check("A shadow_audit 回算标注（复盘条）", "回算口径（启动回填）" in dnote, dnote[:100])

        # -- C1+ · 逐笔对账：筛选 / 排序（纯视图层） --
        nv = c.eval("document.querySelectorAll('#rv-f-veto option').length")
        nsig = c.eval("document.querySelectorAll('#rv-f-signal option').length")
        has_ctrl = c.eval("!!document.getElementById('rv-f-fund') && !!document.getElementById('rv-f-clear') && !!document.getElementById('rv-sort-p')")
        cnt0 = c.eval("(document.getElementById('rv-count')||{}).textContent||''")
        check("B 筛选控件就位（否决层 5 / 信号 4 / 基金 / 清除 / 排序）", nv == 5 and nsig == 4 and has_ctrl, (nv, nsig))
        check("B 计数提示（共 M 条 · 作用于已载入 M 条）", ("共 5 条" in cnt0) and ("作用于已载入 5 条" in cnt0), cnt0)
        # 否决层筛选
        c.eval("(function(){var s=document.getElementById('rv-f-veto');s.value='crowd';s.dispatchEvent(new Event('change'));})()")
        time.sleep(0.3)
        n1 = c.eval("document.querySelectorAll('#rv-body tr[data-recon-row]').length")
        t1 = c.eval("(document.getElementById('rv-body')||{}).innerText||''")
        check("B 否决层筛选（拥挤度）", n1 == 2 and ("拥挤度" in t1) and ("双灯未亮" not in t1), (n1, t1[:60]))
        cnt1 = c.eval("(document.getElementById('rv-count')||{}).textContent||''")
        check("B 筛选计数（已筛选 N / 共 M 条）", "已筛选 2 / 共 5 条" in cnt1, cnt1)
        # 信号筛选
        c.eval("(function(){var s=document.getElementById('rv-f-veto');s.value='all';s.dispatchEvent(new Event('change'));var g=document.getElementById('rv-f-signal');g.value='up';g.dispatchEvent(new Event('change'));})()")
        time.sleep(0.3)
        n2 = c.eval("document.querySelectorAll('#rv-body tr[data-recon-row]').length")
        check("B 信号筛选（涨）", n2 == 3, n2)
        # 基金筛选（代码模糊）
        c.eval("(function(){var g=document.getElementById('rv-f-signal');g.value='all';g.dispatchEvent(new Event('change'));var f=document.getElementById('rv-f-fund');f.value='014320';f.dispatchEvent(new Event('input'));})()")
        time.sleep(0.3)
        n3 = c.eval("document.querySelectorAll('#rv-body tr[data-recon-row]').length")
        t3 = c.eval("(document.getElementById('rv-body')||{}).innerText||''")
        check("B 基金筛选（代码模糊匹配 → 命中名称行）", n3 == 2 and ("德邦" in t3) and ("华夏" not in t3), (n3, t3[:60]))
        # 清除筛选
        c.eval("document.getElementById('rv-f-clear').click()")
        time.sleep(0.3)
        n4 = c.eval("document.querySelectorAll('#rv-body tr[data-recon-row]').length")
        cnt4 = c.eval("(document.getElementById('rv-count')||{}).textContent||''")
        check("B 清除筛选（复位 5 条 + 计数复位）",
              n4 == 5 and ("共 5 条" in cnt4)
              and (c.eval("document.getElementById('rv-f-veto').value") == 'all')
              and (c.eval("document.getElementById('rv-f-fund').value") == ''), (n4, cnt4))
        # P 排序三态：升序 → 降序 → 取消（默认原序 = 时间倒序）
        firstp = "(function(){var tr=document.querySelector('#rv-body tr[data-recon-row]');return tr?tr.children[3].textContent.trim():'';})()"
        c.eval("document.getElementById('rv-sort-p').click()")
        time.sleep(0.25)
        pa = c.eval(firstp); ma = c.eval("(document.getElementById('rv-p-ind')||{}).textContent||''")
        c.eval("document.getElementById('rv-sort-p').click()")
        time.sleep(0.25)
        pd = c.eval(firstp); md = c.eval("(document.getElementById('rv-p-ind')||{}).textContent||''")
        c.eval("document.getElementById('rv-sort-p').click()")
        time.sleep(0.25)
        pn = c.eval(firstp); mn = c.eval("(document.getElementById('rv-p-ind')||{}).textContent||''")
        check("B 概率排序三态（升序→降序→取消）",
              pa == "0.5300" and ma == "▲" and pd == "0.6100" and md == "▼" and pn == "0.6100" and mn == "",
              (pa, ma, pd, md, pn, mn))

        c.navigate(base + "?mock=1#/engine", settle=3.0)
        check("A 引擎 success", c.eval("document.getElementById('view-engine').dataset.state") == "success")
        hud = c.eval("(document.querySelector('#eg-hud .hud-c')||{}).innerText||''")
        check("A HUD 影子盘 60/60 · 回算口径标注",
              ("60 / 60" in hud) and ("滚动 60 日 · 回算口径（启动回填）" in hud) and ("60 日回算覆盖达成" in hud), hud[:130])
        prgn = c.eval("(document.getElementById('eg-prg-note')||{}).innerText||''")
        check("A 进度口径注（60 日直读 + 达成文案）",
              ("可用历史 60 日" in prgn) and ("滚动 60 日 · 回算口径（启动回填）" in prgn)
              and ("60 日回算覆盖达成（启动回填口径）" in prgn), prgn[:130])
        eng_txt = c.eval("(document.getElementById('view-engine')||{}).innerText||''")
        check("A v9.5 旧口径零残留（滚动 20 / 20 交易日 / 自然积累）",
              ("滚动 20" not in eng_txt) and ("20 交易日" not in eng_txt) and ("自然积累" not in eng_txt))
        check("A v9.5 审计标签与前向/实盘语义分离", "与前向/实盘语义分离" in eng_txt)
        fz = c.eval("(document.getElementById('eg-frozen')||{}).innerText||''")
        check("A 冻结参数含 baseline_method", "baseline_method" in fz)
        cmp_ = c.eval("(document.getElementById('eg-cmp')||{}).innerText||''")
        check("A 立方体对比卡走前 Δ 出数", "走前" in cmp_ and "待复现" not in cmp_, cmp_[:80])
        # C2 裁定（§11.2）：注册表三态诚实标注降级（单版本现实 + 预留态）
        regnote = c.eval("(document.getElementById('eg-registry-note')||{}).innerText||''")
        check("A 注册表预留态标注（C2：单版本/预留态/机制未接入）",
              "当前单版本运行" in regnote and "预留态" in regnote and "机制未接入" in regnote, regnote[:80])

        c.navigate(base + "?mock=1#/settings", settle=2.6)
        check("A 设置 success", c.eval("document.getElementById('view-settings').dataset.state") == "success")
        src = c.eval("(document.getElementById('src-box')||{}).innerText||''")
        check("A 数据源健康时间窗计数", "近 7 日失败" in src)
        check("A 历史失败折叠（累计审计）", "历史失败" in src)
        hdd = c.eval("(document.getElementById('hd-data')||{}).innerText||''")
        check("A 持仓主源口径 data/holdings.json", "data/holdings.json" in hdd and "外部导入源" in hdd)
        check("A 导入按钮禁用（import_available=false）", c.eval("document.getElementById('hd-import').disabled") is True)
        # C2 裁定（§11.2）：设置页复用注册表的预留态标注；R-UI-33 复核（C1：本地校验，无谎言文案）
        stnote = c.eval("(document.getElementById('st-registry-note')||{}).innerText||''")
        check("A 设置页注册表预留态标注（C2）", "当前单版本运行" in stnote and "机制未接入" in stnote, stnote[:80])
        st_txt = c.eval("(document.getElementById('view-settings')||{}).innerText||''")
        check("A R-UI-33 复核：设置页无「已发起/异步任务」",
              "已发起" not in st_txt and "异步任务" not in st_txt)

        # ============ 阶段 B：四态（empty / error / loading） ============
        for mode, want_state, want_text in (
            ("empty", "empty", "为什么空"),
            ("error", "error", "重试"),
            ("loading", "loading", "skeleton"),
        ):
            for route in ROUTES:
                c.navigate(base + "?stub=%s#/%s" % (mode, route), settle=1.8)
                state = c.eval("document.getElementById('view-%s').dataset.state" % route)
                check("B %s %s state=%s" % (mode, PAGE_CN[route], want_state), state == want_state, state)
                slot = c.eval("(document.querySelector('#view-%s .state-block')||{}).innerText||''" % route)
                if mode == "loading":
                    nsk = c.eval("document.querySelectorAll('#view-%s .state-block .skeleton').length" % route)
                    check("B loading %s 骨架可见（不渲染数字）" % PAGE_CN[route], nsk and nsk > 0, nsk)
                else:
                    check("B %s %s 文案含「%s」" % (mode, PAGE_CN[route], want_text), want_text in slot, slot[:80])
                if mode == "empty":
                    # 空态下正文（含数字行）必须被 CSS 隐藏：view-main display=none
                    disp = c.eval("getComputedStyle(document.querySelector('#view-%s .view-main')).display" % route)
                    check("B empty %s 不渲染数字行（view-main 隐藏）" % PAGE_CN[route], disp == "none", disp)

        # 空态主行动按钮（为什么空 + 下一步）
        c.navigate(base + "?stub=empty#/holdings", settle=1.8)
        check("B empty 持仓含「录入第一只基金」", "录入第一只基金" in c.eval("(document.querySelector('#view-holdings .state-block')||{}).innerText||''"))
        c.navigate(base + "?stub=empty#/settings", settle=1.8)
        check("B empty 设置含「立即检测」", "立即检测" in c.eval("(document.querySelector('#view-settings .state-block')||{}).innerText||''"))
        c.navigate(base + "?stub=empty#/signals", settle=1.8)
        check("B empty 信号为变体①（尚未开始记录）", "影子盘尚未开始记录" in c.eval("(document.querySelector('#view-signals .state-block')||{}).innerText||''"))

        # ============ 阶段 C：S5 修复轮断言（§8.10 前端栏） ============
        # -- R2-D1 / A1：rows=15 且全窗 open_count=0 → success（正向回归） --
        c.navigate(base + "?stub=empty&anpred=15#/analyze", settle=2.2)
        check("C A1 分析 rows=15/open=0 state=success",
              c.eval("document.getElementById('view-analyze').dataset.state") == "success",
              c.eval("document.getElementById('view-analyze').dataset.state"))
        check("C A1 view-main 可见",
              c.eval("getComputedStyle(document.querySelector('#view-analyze .view-main')).display") != "none")
        check("C A1 预测表 15 行", c.eval("document.querySelectorAll('#an-body tr').length") == 15,
              c.eval("document.querySelectorAll('#an-body tr').length"))
        check("C A1 三窗口卡渲染", c.eval("document.querySelectorAll('#an-forecast .win').length") >= 3,
              c.eval("document.querySelectorAll('#an-forecast .win').length"))
        an_txt = c.eval("(document.getElementById('view-analyze')||{}).innerText||''")
        check("C A1/A3 负向：无「无预测记录」文案", "无预测记录" not in an_txt)
        check("C A1/A3 负向：无「监控集合为空」文案", "监控集合为空" not in an_txt)

        # -- R2-D1 / A2：空态二分支如实 --
        c.navigate(base + "?stub=empty#/analyze", settle=1.8)
        slot_a = c.eval("(document.querySelector('#view-analyze .state-block')||{}).innerText||''")
        check("C A2 空态 state=empty", c.eval("document.getElementById('view-analyze').dataset.state") == "empty")
        check("C A2 分支①（监控集合为空）文案", "当前没有纳入监控（A/B 档）的资产" in slot_a, slot_a[:100])
        c.navigate(base + "?stub=empty&ab=2#/analyze", settle=1.8)
        slot_b = c.eval("(document.querySelector('#view-analyze .state-block')||{}).innerText||''")
        check("C A2 分支②（无预测记录）文案", "今日没有可展示的预测记录（/predictions 行为 0）" in slot_b, slot_b[:100])

        # -- R2-D4：histNote 与 archive_merged 联动 --
        c.navigate(base + "?stub=empty&arch=0#/engine", settle=2.4)
        hud0 = c.eval("(document.querySelector('#eg-hud .hud-c')||{}).innerText||''")
        prg0 = c.eval("(document.getElementById('eg-prg-note')||{}).innerText||''")
        check("C D4 arch=false HUD（主文件后缀 + 回算口径）",
              ("可用历史 60 日（主文件）" in hud0) and ("（含归档）" not in hud0)
              and ("滚动 60 日 · 回算口径（启动回填）" in hud0), hud0[:130])
        check("C D4 arch=false 口径注=按主文件计算", "按主文件计算（归档不可读）" in hud0)
        check("C D4 arch=false 进度注（主文件后缀）", "可用历史 60 日（主文件）" in prg0 and "（含归档）" not in prg0, prg0[:130])
        check("C D4 负向：不同屏矛盾组合", not ("（含归档）" in hud0 and "按主文件计算" in hud0))
        c.navigate(base + "?stub=empty&arch=1#/engine", settle=2.4)
        hud1 = c.eval("(document.querySelector('#eg-hud .hud-c')||{}).innerText||''")
        check("C D4 arch=true HUD（含归档后缀 + 回算口径）",
              ("可用历史 60 日（含归档）" in hud1) and ("滚动 60 日 · 回算口径（启动回填）" in hud1)
              and ("按主文件计算" not in hud1), hud1[:130])

        # -- BLOCK-A1：测试连接=本地校验（不发起网络请求） --
        c.navigate(base + "?stub=empty#/settings", settle=2.0)
        check("C A-1 按钮 title 标本地校验", "本地校验" in c.eval("(document.getElementById('llm-test')||{}).title||''"))
        r1 = c.eval("""(function(){
          var c0 = window.__fetchCalls;
          document.getElementById('llm-test').click();
          return JSON.stringify({ c0: c0, toast: (document.getElementById('toast')||{}).textContent || '' });
        })()""")
        obj1 = json.loads(r1)
        check("C A-1 未配置分支文案", "请先填写" in obj1["toast"] and "未发起网络请求" in obj1["toast"], obj1["toast"])
        check("C A-1 toast 无「已发起/异步任务」", "已发起" not in obj1["toast"] and "异步任务" not in obj1["toast"])
        time.sleep(1.0)
        c1 = c.eval("window.__fetchCalls")
        check("C A-1 未配置分支无出站请求", c1 == obj1["c0"], (obj1["c0"], c1))
        r2 = c.eval("""(function(){
          document.getElementById('llm-model').value = 'deepseek-chat';
          document.getElementById('llm-url').value = 'https://api.deepseek.com/v1';
          document.getElementById('llm-key').value = 'sk-test-local';
          var c0 = window.__fetchCalls;
          document.getElementById('llm-test').click();
          return JSON.stringify({ c0: c0, toast: (document.getElementById('toast')||{}).textContent || '' });
        })()""")
        obj2 = json.loads(r2)
        check("C A-1 配置齐全分支文案（本地校验通过）", "本地校验通过" in obj2["toast"], obj2["toast"])
        time.sleep(1.0)
        c2 = c.eval("window.__fetchCalls")
        check("C A-1 配置齐全分支无出站请求", c2 == obj2["c0"], (obj2["c0"], c2))

        # -- BLOCK-A2：隐私两开关（S1~S4；mock 模式 PUT 回显） --
        c.navigate(base + "?mock=1#/holdings", settle=2.8)
        # S1 副开关：仅明细行打码，汇总保留
        c.eval("document.getElementById('sw-hide-holdings').click()")
        time.sleep(0.9)
        s1 = json.loads(c.eval("""(function(){
          var det = getComputedStyle(document.querySelector('#hd-body td.amt'));
          var sum = getComputedStyle(document.getElementById('pa-total'));
          var pct = getComputedStyle(document.querySelector('#hd-body tr:not(.grp) td:nth-child(7)'));
          return JSON.stringify({ cls: document.body.className, det: det.color, sum: sum.color, pct: pct.color,
            toast: (document.getElementById('toast')||{}).textContent || '' });
        })()"""))
        check("C S1 副开关 class=mask-holdings-only", "mask-holdings-only" in s1["cls"], s1["cls"])
        check("C S1 明细行金额被打码（color transparent）", s1["det"].replace(" ", "") == "rgba(0,0,0,0)", s1["det"])
        check("C S1 四卡汇总保留（颜色非透明）", s1["sum"].replace(" ", "") != "rgba(0,0,0,0)", s1["sum"])
        check("C S1 占比列不受影响", s1["pct"].replace(" ", "") != "rgba(0,0,0,0)", s1["pct"])
        check("C S1 副开关 toast 文案", "明细行" in s1["toast"], s1["toast"])
        # S2 主开关：全站
        c.eval("document.getElementById('sw-hide').click()")
        time.sleep(0.9)
        s2 = json.loads(c.eval("""(function(){
          var sum = getComputedStyle(document.getElementById('pa-total'));
          return JSON.stringify({ cls: document.body.className, sum: sum.color,
            eye: (document.getElementById('eye-btn')||{}).textContent || '' });
        })()"""))
        check("C S2 主开关 class=masked", "masked" in s2["cls"].split(), s2["cls"])
        check("C S2 全站金额打码（四卡透明）", s2["sum"].replace(" ", "") == "rgba(0,0,0,0)", s2["sum"])
        check("C S2 顶栏按钮联动「显示金额」", s2["eye"] == "显示金额", s2["eye"])
        # S4 打码不改数字口径（文本原值保留；纯展示层）
        s4 = json.loads(c.eval("""(function(){
          var cell = document.querySelector('#hd-body td.amt');
          return JSON.stringify({ text: cell.textContent, sum: document.getElementById('pa-total').textContent });
        })()"""))
        check("C S4 打码不改数字（明细单元格文本仍为原金额）", "¥" in s4["text"], s4["text"][:40])
        check("C S4 打码不改数字（四卡文本仍为原金额）", "¥" in s4["sum"], s4["sum"][:40])
        # S3 启动水合：刷新（重新导航）后两开关状态与打码效果保持
        c.navigate(base + "?stub=privacy#/holdings", settle=2.2)
        h1 = json.loads(c.eval("""(function(){
          return JSON.stringify({ cls: document.body.className,
            det: getComputedStyle(document.querySelector('#hd-body td.amt') || document.body).color });
        })()"""))
        check("C S3 水合：刷新后 body 两 class 就位", "masked" in h1["cls"] and "mask-holdings-only" in h1["cls"], h1["cls"])
        c.navigate(base + "?stub=privacy#/settings", settle=2.0)
        h2 = json.loads(c.eval("""(function(){
          return JSON.stringify({ sw: document.getElementById('sw-hide').checked,
            swh: document.getElementById('sw-hide-holdings').checked,
            cls: document.body.className });
        })()"""))
        check("C S3 水合：开关回显勾选", h2["sw"] is True and h2["swh"] is True, h2)

        # -- BLOCK-A3：chain_available 分支 --
        c.navigate(base + "?stub=empty&chain=0#/signals", settle=2.2)
        c.eval("document.querySelector('#tl-list .sigcard').click()")
        time.sleep(0.5)
        ev0 = c.eval("(document.querySelector('#tl-list .sigcard .ev')||{}).innerText||''")
        check("C A-3 chain_available=false 明示不可复现", "该行链路不可复现" in ev0, ev0[:80])
        c.navigate(base + "?stub=empty&chain=1#/signals", settle=2.2)
        c.eval("document.querySelector('#tl-list .sigcard').click()")
        time.sleep(0.8)
        nstep = c.eval("document.querySelectorAll('#tl-list .chain-item').length")
        ev1 = c.eval("(document.querySelector('#tl-list .sigcard .ev')||{}).innerText||''")
        check("C A-3 chain_available=true 六步链渲染", nstep and nstep >= 6, nstep)
        check("C A-3 ⑥步回填态标注", "回填态" in ev1 or "⑥ 输出" in ev1, ev1[:80])

        # -- S-a：bootstrap 分位来源标注 --
        c.navigate(base + "?stub=empty&pan=1&meas=1#/factors", settle=2.2)
        fsc = c.eval("(document.getElementById('fc-score')||{}).innerText||''")
        check("C S-a measured 非空→标「bootstrap 500 实测」", "bootstrap 500 实测" in fsc and "-12.4" in fsc, fsc[:100])
        c.navigate(base + "?stub=empty&pan=1&meas=0#/factors", settle=2.2)
        fsc0 = c.eval("(document.getElementById('fc-score')||{}).innerText||''")
        check("C S-a measured=null→标「兼容常量（未实测）」", "兼容常量（未实测）" in fsc0, fsc0[:100])

        # -- F-3：judges 值缺失不渲染空 value（标「待接入」） --
        c.navigate(base + "?stub=empty&pan=1&detail=1#/factors", settle=2.2)
        c.eval("document.querySelector('#fc-pans .frow[data-fid=\"klow2\"]').click()")
        time.sleep(0.8)
        fdet = c.eval("(document.querySelector('#fc-pans .fdet')||{}).innerText||''")
        check("C F-3 judges 值缺失标注「待接入」", "待接入" in fdet, fdet[:100])

        # 证据截图
        c.navigate(base + "?stub=empty#/holdings", settle=1.6)
        c.screenshot(os.path.join(HERE, "zl_r2_state_empty_holdings.png"), full=False)
        c.navigate(base + "?stub=error#/engine", settle=1.6)
        c.screenshot(os.path.join(HERE, "zl_r2_state_error_engine.png"), full=False)
        c.close()
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        httpd.shutdown()

    fails = [r for r in results if not r[1]]
    total = "TOTAL %d PASS %d FAIL %d" % (len(results), len(results) - len(fails), len(fails))
    loglines.append(total)
    try:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(loglines) + "\n")
    except Exception:
        pass
    try:
        print(total)
    except Exception:
        print(total.encode("ascii", "replace").decode("ascii"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
