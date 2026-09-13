// ④ 因子页 —— R-UI-14/15/16/17/18/19（S5：S-a bootstrap 实测/兼容标注 + F-3 judges 值缺失标注）
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, tag, toast, esc, showModal } from '../components.js';
import { num, score as fscore, lift as flift, int, isNum, delta, dateTimeShort } from '../format.js';
import {
  BOOTSTRAP_MEASURED_LABEL, BOOTSTRAP_FALLBACK_LABEL, NOT_WIRED_LABEL,
  BOOK_FIELD_LABEL, DIG_RESULT_LABEL, DIG_VERDICT_LABEL, FACTOR_STATUS_LABEL, FACTOR_LICENSE_LABEL,
  RED_LINE_ON, RED_LINE_OFF, BOOK_BACKTEST_LABEL, BOOK_WRITE_PENDING, BOOK_RAW_TOGGLE_ON, BOOK_RAW_TOGGLE_OFF, BOOK_READONLY_NOTE
} from '../copy.js';

const PAN_STATUS = { on: 'ok', warn: 'warn', bad: 'red' };
const STATUS_TAG = { active: ['现役', 'ok'], probation: ['观察', 'warn'], cooling: ['冷却', 'warn'], frozen: ['冻结', 'gray'], retired: ['退役', 'gray'] };

export function init() {
  const pans = document.getElementById('fc-pans');
  if (pans) {
    pans.addEventListener('click', function (e) {
      const row = e.target.closest('.frow[data-fid]');
      if (row) toggleScoreDetail(row);
    });
  }
  const books = document.getElementById('fc-books');
  if (books) {
    books.addEventListener('click', function (e) {
      const btn = e.target.closest('[data-book]');
      if (btn) openBook(btn.dataset.book);
    });
  }
}

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('pans', '/factors/pans', null, function (d) {
      return !((d && d.pans || []).length);
    }),
    loadSlice('books', '/factors/books'),
    loadSlice('scoreChain', '/factors/score-chain'),
    loadSlice('lifecycle', '/factors/lifecycle'),
    loadSlice('governance', '/factors/governance-cycle'),
    loadSlice('digRecords', '/factors/dig-records')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-factors');
  const sl = getSlice('pans');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'factors', sl, activate);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  // idle 归 loading（首帧 slice 尚未发起请求），保证四态可真实触发（U-03）
  root.dataset.state = sl.status === 'success' ? 'success' : (sl.status === 'idle' ? 'loading' : sl.status);
  renderPans();
  renderBooks();
  renderScoreChain();
  renderGovernance();
  renderDigRecords();
  renderLifecycle();
}

/* ---------- R-UI-14 因子四盘 ---------- */
function renderPans() {
  const el = document.getElementById('fc-pans');
  const sl = getSlice('pans');
  if (!sl.data || (sl.status !== 'success' && sl.status !== 'empty')) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '因子账本读取失败' : '—') + '</div>'; return; }
  el.innerHTML = (sl.data.pans || []).map(function (p) {
    const rows = (p.factors || []).map(function (f) { return factorRow(f); }).join('');
    const cap = [];
    const caps = p.caps || null;
    if (caps) {
      const parts = [];
      if (isNum(caps.veto_max)) parts.push('否决位 ≤' + int(caps.veto_max));
      if (isNum(caps.score_max)) parts.push('打分位 ≤' + int(caps.score_max));
      if (parts.length) cap.push(parts.join(' · '));
    }
    if (p.nomination_limit != null) cap.push('每周提名 ≤' + p.nomination_limit);
    return '<div class="card" style="margin-bottom:12px">'
      + '<h3 style="font-size:13px;font-weight:600;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
      + esc(p.role_label) + ' ' + tag(int(p.factor_count) + ' 个', PAN_STATUS[p.pan_status] || 'gray')
      + (cap.length ? '<span class="mini" style="font-weight:400">' + esc(cap.join(' · ')) + '</span>' : '')
      + '<span class="mini" style="margin-left:auto;font-weight:400">' + esc(p.description || '') + '</span></h3>'
      + (rows
        ? '<div class="frow hd"><span>因子</span><span>总分</span><span>六窗 lift</span><span>牌照</span><span>角色</span><span>状态</span></div>' + rows
        : '<div class="mini" style="padding:8px 0">（当前为空）</div>')
      + '<div class="mini" style="margin-top:10px;padding-top:10px;border-top:1px dashed rgba(24,32,25,.12);line-height:1.8">' + esc(p.rule_text || '') + '</div>'
      + '</div>';
  }).join('');
}

function factorRow(f) {
  const st = STATUS_TAG[f.status] || ['—', 'gray'];
  const bars = '<div class="bars">' + (f.lift_bars || []).map(function (b) {
    const h = isNum(b.lift) ? Math.max(12, Math.min(100, (b.lift - 0.85) / 0.60 * 100)) : 12;
    const c = isNum(b.lift) && b.lift >= 1 ? 'g' : 'r';
    return '<i class="' + c + '" style="height:' + h + '%" title="' + esc(b.window_label || b.window) + ' lift ' + flift(b.lift) + '"></i>';
  }).join('') + '</div>';
  const extra = f.ab_progress
    ? '<div class="mini" style="color:var(--up)">A/B ' + int(f.ab_progress.day) + '/' + int(f.ab_progress.total_days) + ' 日 · ' + esc(f.ab_progress.conclusion || '') + '</div>'
    : (f.death_condition ? '<div class="mini">死亡条件：' + esc(f.death_condition) + '</div>' : '');
  return '<div class="frow" data-fid="' + esc(f.factor_id) + '">'
    + '<div><div class="fname2">' + esc(f.name) + ' <span class="mini">▾ 展开跑分</span></div><div class="mini">' + esc(f.note || '') + '</div>' + extra + '</div>'
    + '<div class="fscore ' + (isNum(f.total_score) && f.total_score >= 50 ? 'up' : (isNum(f.total_score) && f.total_score < 0 ? 'down' : 'flat')) + '">' + fscore(f.total_score) + '</div>'
    + '<div>' + bars + '</div>'
    + '<div>' + tag(f.license_label || f.license || '—', 'blue') + '</div>'
    + '<div class="mini">' + esc(f.role_label || f.role || '') + '</div>'
    + '<div>' + tag(st[0], st[1]) + '</div>'
    + '</div>';
}

function toggleScoreDetail(row) {
  const fid = row.dataset.fid;
  let det = document.getElementById('fdet-' + fid);
  if (det) { det.style.display = det.style.display === 'none' ? 'block' : 'none'; return; }
  det = document.createElement('div');
  det.className = 'fdet';
  det.id = 'fdet-' + fid;
  det.innerHTML = '<div class="mini">加载中…</div>';
  row.insertAdjacentElement('afterend', det);
  get('/factors/score-detail?factor_id=' + encodeURIComponent(fid)).then(function (env) {
    const d = env.data;
    det.innerHTML = scoreDetailHTML(d);
  }).catch(function (e) {
    det.innerHTML = '<div class="mini">跑分表读取失败：' + esc(e.message) + '</div>';
  });
}

function scoreDetailHTML(d) {
  if (!d) return '<div class="mini">无数据</div>';
  const body = (d.windows || []).map(function (w) {
    return '<tr><td>' + esc(w.window_label) + '</td><td class="num">' + flift(w.lift) + '</td>'
      + '<td class="num ' + (isNum(w.k_lift) && w.k_lift < 0 ? 'down' : '') + '">' + num(w.k_lift, 2) + '</td>'
      + '<td class="num mini">' + int(w.weight) + '</td>'
      + '<td class="num mini">' + int(w.independent_trigger_days) + ' / ' + int(w.n_w) + '</td>'
      + '<td class="num mini">' + num(w.admission, 2) + '</td>'
      + '<td class="num"><b>' + num(w.score, 2) + '</b></td></tr>';
  }).join('');
  const bp = d.bootstrap_percentiles || {};
  // S5/S-a：judges 值缺失不渲染空 value（标「待接入」）
  const judges = (d.judges || []).map(function (j) {
    const val = (j.value == null) ? '<span class="flat">' + NOT_WIRED_LABEL + '</span>' : esc(String(j.value));
    return '<div class="mini">· ' + esc(j.judge) + '（' + esc(j.scope || '') + '）：' + esc(j.metric || '') + ' ' + val + ' ' + esc(j.note || '') + '</div>';
  }).join('');
  return '<table><thead><tr><th>窗</th><th class="r">lift</th><th class="r">k_lift</th><th class="r">权重</th><th class="r">独立触发日</th><th class="r">准入度</th><th class="r">得分</th></tr></thead>'
    + '<tbody>' + body + '<tr><td colspan="6" style="text-align:right"><b>总分</b></td><td class="num"><b style="font-size:14px">' + fscore(d.total_score) + '</b></td></tr></tbody></table>'
    + '<div class="mini" style="margin-top:8px;line-height:1.75">' + esc(d.formula_text || '')
    // S5/S-a：score-detail 无 measured 字段（契约未定义）→ 明示「兼容常量」
    + '<br>' + BOOTSTRAP_FALLBACK_LABEL + '：P50 ' + num(bp.p50, 1) + ' / P90 ' + num(bp.p90, 1) + ' / P95 ' + num(bp.p95, 1) + ' / P99 ' + num(bp.p99, 1) + ' / P99.5 ' + num(bp.p995, 1) + '</div>'
    + (judges ? '<div class="mini" style="margin-top:6px">' + judges + '</div>' : '');
}

/* ---------- R-UI-15 四本账本（C1：人话记录视图；原始数据切换保留审计能力） ---------- */
// C1 · 账本记录 → 人话摘要（按账本类型；字段缺失优雅降级、不编造；未知账本走「字段名：值」兜底）
// 说明：枚举/字段中文一律取 copy.js 字典；原始数据始终可在弹窗内切换查看（INSERT-ONLY 审计精神）
export function bookRecordSummary(book, r) {
  if (!r || typeof r !== 'object') return '<span class="mini">' + esc(BOOK_WRITE_PENDING) + '</span>';
  if (book === 'adopted_factors') return adoptedSummary(r);
  if (book === 'scan_history') return scanSummary(r);
  if (book === 'factor_health') return healthSummary(r);
  if (book === 'retired_log') return retiredSummary(r);
  return genericSummary(r);
}

function adoptedSummary(r) {
  const title = '<b>' + esc(r.name || r.factor_id || '—') + '</b>'
    + (r.name && r.factor_id ? '（' + esc(r.factor_id) + '）' : '');
  const meta = [];
  const role = r.role_label || r.role;
  const st = r.status ? (FACTOR_STATUS_LABEL[r.status] || r.status) : '';
  const lic = r.license_label || (r.license ? (FACTOR_LICENSE_LABEL[r.license] || r.license) : '');
  if (role) meta.push('角色 ' + esc(role));
  if (st) meta.push('状态 ' + esc(st));
  if (lic) meta.push('牌照 ' + esc(lic));
  if (isNum(r.total_score)) meta.push('总分 ' + fscore(r.total_score));
  if (isNum(r.independent_trigger_days)) meta.push('独立触发 ' + int(r.independent_trigger_days) + ' 日');
  if (isNum(r.open_count)) meta.push('开口 ' + int(r.open_count) + ' 次');
  const lines = [title + (meta.length ? ' · ' + meta.join(' · ') : '')];
  if (r.death_condition) lines.push(esc(BOOK_FIELD_LABEL.death_condition) + '：' + esc(r.death_condition));
  const tail = [];
  const added = r.added_at || r.adopted_at;
  if (added) tail.push('采纳 ' + esc(added));
  const bt = (r.backtest && typeof r.backtest === 'object') ? r.backtest : null;
  if (bt) {
    const ps = [];
    if (bt.mode) ps.push(esc(bt.mode));
    if (bt.purge_gap) ps.push('purge=' + esc(bt.purge_gap));
    if (isNum(bt.holdout_days)) ps.push('holdout ' + int(bt.holdout_days) + ' 日');
    if (bt.sample_period) ps.push('样本期 ' + esc(bt.sample_period));
    const bp = bt.bootstrap_percentiles || {};
    if (isNum(bp.p50) || isNum(bp.p90)) ps.push('bootstrap P50 ' + num(bp.p50, 1) + ' / P90 ' + num(bp.p90, 1));
    const vd = bt.verdict ? (DIG_VERDICT_LABEL[bt.verdict] || String(bt.verdict)) : '';
    if (vd) ps.push('判定 ' + esc(vd));
    if (ps.length) tail.push(BOOK_BACKTEST_LABEL + '：' + ps.join(' · '));
  }
  if (tail.length) lines.push(tail.join(' · '));
  return (meta.length || r.death_condition || tail.length) ? lines.join('<br>') : genericSummary(r);
}

function scanSummary(r) {
  const head = [];
  if (r.scan_date) head.push(esc(r.scan_date) + (r.nomination_week ? '（' + esc(r.nomination_week) + '）' : ''));
  if (r.candidate) head.push('候选 <b>' + esc(r.candidate) + '</b>');
  const digs = [['f1_result', 'f1_detail'], ['f2_result', 'f2_detail'], ['f3_result', 'f3_detail']].map(function (p) {
    const res = r[p[0]];
    if (res == null) return '';
    const lbl = DIG_RESULT_LABEL[res] || String(res);
    const det = r[p[1]] ? '（' + esc(r[p[1]]) + '）' : '';
    return esc(BOOK_FIELD_LABEL[p[0]]) + '：' + esc(lbl) + det;
  }).filter(Boolean).join(' · ');
  const tail = [];
  const verdict = r.verdict_text || (r.verdict ? (DIG_VERDICT_LABEL[r.verdict] || String(r.verdict)) : '');
  if (verdict) tail.push('判定：' + esc(verdict));
  if (r.cooldown_until) tail.push('冷却至 ' + esc(r.cooldown_until));
  const lines = [head.join(' · '), digs, tail.join(' · ')].filter(Boolean);
  return lines.length ? lines.join('<br>') : genericSummary(r);
}

function healthSummary(r) {
  const head = [r.date, r.factor_id].filter(Boolean).map(esc).join(' · ');
  const parts = [];
  if (isNum(r.loo_delta_pp)) parts.push('留一法 Δ ' + delta(r.loo_delta_pp));
  if (r.red_line === true) parts.push(RED_LINE_ON);
  else if (r.red_line === false) parts.push(RED_LINE_OFF);
  if (r.regime) parts.push('环境 ' + esc(r.regime));
  const lines = [head, parts.join(' · ')].filter(Boolean);
  return lines.length ? lines.join('<br>') : genericSummary(r);
}

function retiredSummary(r) {
  const head = [r.date, r.factor_id].filter(Boolean).map(esc).join(' · ');
  const parts = [];
  if (isNum(r.delta_after_removal_pp)) parts.push('移除后组合 Δ ' + delta(r.delta_after_removal_pp));
  if (r.conclusion) parts.push('结论：' + esc(r.conclusion));
  if (r.regime) parts.push('环境 ' + esc(r.regime));
  const lines = [head, parts.join(' · ')].filter(Boolean);
  return lines.length ? lines.join('<br>') : genericSummary(r);
}

// 兜底：未知账本/无已知字段 →「字段名：值」可读列表（嵌套对象压缩展示，不丢审计信息）
function genericSummary(r) {
  const keys = Object.keys(r || {});
  if (!keys.length) return '<span class="mini">' + esc(BOOK_WRITE_PENDING) + '</span>';
  return keys.map(function (k) {
    let v = r[k];
    if (v == null || v === '') v = '—';
    else if (typeof v === 'object') v = JSON.stringify(v);
    else v = String(v);
    return '<span style="display:inline-block;margin-right:12px">' + esc(BOOK_FIELD_LABEL[k] || k) + '：<span class="mono">' + esc(v) + '</span></span>';
  }).join('');
}

function renderBooks() {
  const el = document.getElementById('fc-books');
  const sl = getSlice('books');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '账本读取失败' : '—') + '</div>'; return; }
  const show = (sl.data.books || []).filter(function (b) {
    return ['adopted_factors', 'scan_history', 'factor_health', 'retired_log'].indexOf(b.book) >= 0;
  });
  el.innerHTML = show.map(function (b) {
    const first = (b.sample || [])[0] || null;
    const preview = first ? bookRecordSummary(b.book, first) : '<span class="mini">' + esc(BOOK_WRITE_PENDING) + '</span>';
    return '<div class="card" style="margin-bottom:12px">'
      + '<h3 style="font-size:13px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
      + '<span class="mono" style="font-size:12px">' + esc(b.filename) + '</span>' + tag(b.book_label, 'blue')
      + '<span class="mini" style="margin-left:auto;font-weight:400">' + int(b.record_count) + ' 条</span>'
      + '<button class="btn sm" data-book="' + esc(b.book) + '">展开最近记录</button></h3>'
      + '<div class="mini" style="margin-bottom:8px">' + esc(b.purpose || '') + '</div>'
      + '<div class="bookrec">' + preview + '</div></div>';
  }).join('');
}

function openBook(book) {
  get('/factors/books/' + book + '?limit=20').then(function (env) {
    const d = env.data || {};
    const recs = d.records || [];
    if (!recs.length) {
      showModal(d.book_label || book, '<div class="mini">' + esc(BOOK_WRITE_PENDING) + '</div>');
      return;
    }
    // 人话视图（默认）：每条一段摘要
    const human = recs.map(function (r) { return '<div class="bookrec">' + bookRecordSummary(book, r) + '</div>'; }).join('');
    // 原始数据视图（审计保留）：字段 × 行 裸表格
    const fields = d.schema_fields || Object.keys(recs[0]);
    const raw = '<div style="overflow-x:auto"><table><thead><tr>' + fields.map(function (f) { return '<th>' + esc(f) + '</th>'; }).join('') + '</tr></thead><tbody>'
      + recs.map(function (r) { return '<tr>' + fields.map(function (f) { return '<td class="mini">' + esc(r[f] == null ? '—' : r[f]) + '</td>'; }).join('') + '</tr>'; }).join('')
      + '</tbody></table></div>';
    const html = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
      + '<span class="mini">共 ' + int(recs.length) + ' 条 · 人话视图</span><span style="flex:1"></span>'
      + '<button class="btn sm" data-bk-toggle>' + esc(BOOK_RAW_TOGGLE_ON) + '</button></div>'
      + '<div data-bk-view="human">' + human + '</div>'
      + '<div data-bk-view="raw" style="display:none">' + raw + '</div>';
    showModal(d.book_label || book, html + '<div class="mini" style="margin-top:8px">' + esc(BOOK_READONLY_NOTE) + '</div>');
    const btn = document.querySelector('#zl-modal [data-bk-toggle]');
    if (btn) btn.addEventListener('click', function () {
      const humanEl = document.querySelector('#zl-modal [data-bk-view="human"]');
      const rawEl = document.querySelector('#zl-modal [data-bk-view="raw"]');
      const showingRaw = rawEl.style.display !== 'none';
      humanEl.style.display = showingRaw ? '' : 'none';
      rawEl.style.display = showingRaw ? 'none' : '';
      btn.textContent = showingRaw ? BOOK_RAW_TOGGLE_ON : BOOK_RAW_TOGGLE_OFF;
    });
  }).catch(function (e) { toast('账本读取失败：' + e.message); });
}

/* ---------- R-UI-16 评分链 ---------- */
function renderScoreChain() {
  const el = document.getElementById('fc-score');
  const sl = getSlice('scoreChain');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '评分链读取失败' : '—') + '</div>'; return; }
  const d = sl.data;
  const bins = (d.lift_bins || []).map(function (b) {
    return '≥' + flift(b.min_lift) + '→<b>' + num(b.k_lift, 2) + '</b>';
  }).join(' / ');
  const ww = (d.window_weights || []).map(function (w) { return w.weight; }).join('/');
  const judges = (d.judges || []).map(function (j) {
    return '<b>' + esc(j.judge) + '</b> 管' + esc(j.scope || '') + (j.metric ? '（' + esc(j.metric) + '）' : '');
  }).join(' · ');
  const bp = d.bootstrap_percentiles || {};
  // S5/S-a：优先读实测分位 bootstrap_percentiles_measured（v9 销项 V11）；为 null 回退常量并明示「兼容常量」
  const measured = (d.bootstrap_percentiles_measured && typeof d.bootstrap_percentiles_measured === 'object')
    ? d.bootstrap_percentiles_measured : null;
  const bpShow = measured || bp;
  const bpLabel = measured ? BOOTSTRAP_MEASURED_LABEL : BOOTSTRAP_FALLBACK_LABEL;
  el.innerHTML = '<div class="mini" style="line-height:1.9">' + esc(d.formula_text || '')
    + '<br><b>k_lift 悬崖：</b>' + bins
    + '<br><b>窗权重：</b><code>' + esc(ww) + '</code>'
    + (d.floor_note ? '<br><b style="color:var(--gold)">' + esc(d.floor_note) + '</b>' : '')
    + '<br><b>' + bpLabel + '：</b>P50 ' + num(bpShow.p50, 1) + ' / P90 ' + num(bpShow.p90, 1) + ' / P95 ' + num(bpShow.p95, 1) + ' / P99 ' + num(bpShow.p99, 1) + ' / P99.5 ' + num(bpShow.p995, 1)
    + (judges ? '<br><b>四个裁判：</b>' + judges : '')
    + (d.rule_source ? '<br><span style="color:var(--ink3)">来源：' + esc(d.rule_source) + '</span>' : '') + '</div>';
}

/* ---------- R-UI-17 治理周期 ---------- */
function renderGovernance() {
  const el = document.getElementById('fc-cycle');
  const sl = getSlice('governance');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '周期读取失败' : '—') + '</div>'; return; }
  const d = sl.data;
  el.innerHTML = (d.phases || []).map(function (p) {
    return '<div class="cyc-item" title="' + esc(p.rule_text || '') + '"><div class="k">' + esc(p.label) + '</div>'
      + '<div class="v">' + esc(p.cadence || '—') + '</div>'
      + '<div class="s">' + esc(p.status || '') + (p.next_run_at ? ' · 下次 ' + esc(p.next_run_at) : '') + '</div></div>';
  }).join('') + (d.note ? '<div class="mini" style="grid-column:1/-1;margin-top:4px">' + esc(d.note) + '</div>' : '');
}

/* ---------- R-UI-18 最近挖掘记录 ---------- */
function renderDigRecords() {
  const tbody = document.getElementById('fc-scan');
  const panel = document.getElementById('fc-scan-panel');
  const sl = getSlice('digRecords');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="6" class="mini">' + (sl.status === 'error' ? '读取失败' : '—') + '</td></tr>'; return; }
  const d = sl.data;
  const recs = d.records || [];
  if (!recs.length) { tbody.innerHTML = '<tr><td colspan="6" class="mini">尚无挖掘记录</td></tr>'; }
  else tbody.innerHTML = recs.map(function (r) {
    return '<tr><td class="mono">' + esc(r.scan_date) + '</td><td class="mono">' + esc(r.candidate) + '</td>'
      + '<td>' + digCell(r.f1_result, r.f1_detail) + '</td><td>' + digCell(r.f2_result, r.f2_detail) + '</td><td>' + digCell(r.f3_result, r.f3_detail) + '</td>'
      + '<td class="mini ' + (r.verdict === 'admitted_to_arena' ? 'up' : '') + '">' + esc(r.verdict_text || r.verdict) + '</td></tr>';
  }).join('');
  if (panel && d.panel) panel.textContent = (d.panel.week_rule || '') + ' · 冷却 ' + int(d.panel.cooldown_days) + ' 天 · 提名 ≤' + int(d.panel.nomination_limit) + ' 个/周';
}
function digCell(res, detail) {
  if (res === 'na' || res == null) return '<span class="flat">—</span>';
  if (res === 'not_run') return '<span class="flat">未执行</span>';
  const ok = res === 'pass';
  return '<span class="' + (ok ? 'down' : 'up') + '">' + (ok ? '✓' : '✗') + '</span>' + (detail ? ' <span class="mini">' + esc(detail) + '</span>' : '');
}

/* ---------- R-UI-19 生命周期规则 ---------- */
function renderLifecycle() {
  const el = document.getElementById('fc-life');
  const sl = getSlice('lifecycle');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '生命周期规则读取失败' : '—') + '</div>'; return; }
  const d = sl.data;
  const block = function (title, arr) {
    if (!arr || !arr.length) return '';
    return '<div style="margin-bottom:8px"><b>' + esc(title) + '：</b>' + arr.map(esc).join('｜') + '</div>';
  };
  const lines = (d.license_lines || []).map(function (l) {
    return esc(l.license) + ' ≥' + esc(String(l.threshold)) + (l.condition ? '（' + esc(l.condition) + '）' : '');
  }).join('；');
  el.innerHTML = block('准入（三项 AND）', d.admission_rules)
    + (lines ? '<div style="margin-bottom:8px"><b>牌照四线：</b>' + lines + '</div>' : '')
    + block('淘汰五线', d.retire_rules)
    + block('双出口', d.dual_exit)
    + block('防误杀三保险', d.false_kill_guards)
    + block('冷冻复活', d.revive_rules)
    + (d.source ? '<div class="mini" style="color:var(--ink3);margin-top:6px">文本来源：' + esc(d.source) + '</div>' : '')
    + (d.freeze_note ? '<div class="mini" style="color:var(--gold);margin-top:4px">' + esc(d.freeze_note) + '</div>' : '');
}
