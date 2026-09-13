// ④ 因子页 —— R-UI-14/15/16/17/18/19
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, tag, toast, esc, showModal } from '../components.js';
import { num, score as fscore, lift as flift, int, isNum, dateTimeShort } from '../format.js';

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
    loadSlice('pans', '/factors/pans'),
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
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
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
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '因子账本读取失败' : '—') + '</div>'; return; }
  el.innerHTML = (sl.data.pans || []).map(function (p) {
    const rows = (p.factors || []).map(function (f) { return factorRow(f); }).join('');
    const cap = [];
    if (p.factor_cap != null) cap.push('上限 ' + p.factor_cap);
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
  const judges = (d.judges || []).map(function (j) {
    return '<div class="mini">· ' + esc(j.judge) + '（' + esc(j.scope || '') + '）：' + esc(j.metric || '') + ' ' + esc(String(j.value == null ? '' : j.value)) + ' ' + esc(j.note || '') + '</div>';
  }).join('');
  return '<table><thead><tr><th>窗</th><th class="r">lift</th><th class="r">k_lift</th><th class="r">权重</th><th class="r">独立触发日</th><th class="r">准入度</th><th class="r">得分</th></tr></thead>'
    + '<tbody>' + body + '<tr><td colspan="6" style="text-align:right"><b>总分</b></td><td class="num"><b style="font-size:14px">' + fscore(d.total_score) + '</b></td></tr></tbody></table>'
    + '<div class="mini" style="margin-top:8px;line-height:1.75">' + esc(d.formula_text || '')
    + '<br>bootstrap 500 校准分位：P50 ' + num(bp.p50, 1) + ' / P90 ' + num(bp.p90, 1) + ' / P95 ' + num(bp.p95, 1) + ' / P99 ' + num(bp.p99, 1) + ' / P99.5 ' + num(bp.p995, 1) + '</div>'
    + (judges ? '<div class="mini" style="margin-top:6px">' + judges + '</div>' : '');
}

/* ---------- R-UI-15 四本账本 ---------- */
function renderBooks() {
  const el = document.getElementById('fc-books');
  const sl = getSlice('books');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '账本读取失败' : '—') + '</div>'; return; }
  const show = (sl.data.books || []).filter(function (b) {
    return ['adopted_factors', 'scan_history', 'factor_health', 'retired_log'].indexOf(b.book) >= 0;
  });
  el.innerHTML = show.map(function (b) {
    const sample = (b.sample || []).slice(0, 1).map(function (s) { return esc(JSON.stringify(s)); }).join('');
    return '<div class="card" style="margin-bottom:12px">'
      + '<h3 style="font-size:13px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
      + '<span class="mono" style="font-size:12px">' + esc(b.filename) + '</span>' + tag(b.book_label, 'blue')
      + '<span class="mini" style="margin-left:auto;font-weight:400">' + int(b.record_count) + ' 条</span>'
      + '<button class="btn sm" data-book="' + esc(b.book) + '">展开最近记录</button></h3>'
      + '<div class="mini" style="margin-bottom:8px">' + esc(b.purpose || '') + '</div>'
      + '<div class="mono" style="font-size:11px;color:var(--ink2);background:rgba(24,32,25,.04);border-radius:8px;padding:8px 11px;line-height:1.7;word-break:break-all">'
      + (sample || '待写入') + '</div></div>';
  }).join('');
}

function openBook(book) {
  get('/factors/books/' + book + '?limit=20').then(function (env) {
    const d = env.data || {};
    const recs = d.records || [];
    let html;
    if (!recs.length) html = '<div class="mini">待写入</div>';
    else {
      const fields = d.schema_fields || Object.keys(recs[0]);
      html = '<div style="overflow-x:auto"><table><thead><tr>' + fields.map(function (f) { return '<th>' + esc(f) + '</th>'; }).join('') + '</tr></thead><tbody>'
        + recs.map(function (r) { return '<tr>' + fields.map(function (f) { return '<td class="mini">' + esc(r[f] == null ? '—' : r[f]) + '</td>'; }).join('') + '</tr>'; }).join('')
        + '</tbody></table></div>';
    }
    showModal(d.book_label || book, html + '<div class="mini" style="margin-top:8px">只读台账 · 无编辑/删除入口</div>');
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
  el.innerHTML = '<div class="mini" style="line-height:1.9">' + esc(d.formula_text || '')
    + '<br><b>k_lift 悬崖：</b>' + bins
    + '<br><b>窗权重：</b><code>' + esc(ww) + '</code>'
    + (d.floor_note ? '<br><b style="color:var(--gold)">' + esc(d.floor_note) + '</b>' : '')
    + '<br><b>bootstrap 500 校准：</b>P50 ' + num(bp.p50, 1) + ' / P90 ' + num(bp.p90, 1) + ' / P95 ' + num(bp.p95, 1) + ' / P99 ' + num(bp.p99, 1) + ' / P99.5 ' + num(bp.p995, 1)
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
  if (panel && d.panel) panel.textContent = (d.panel.week_rule || '') + ' · 冷却 ' + int(d.panel.cooldown_days) + ' 天 · 提名上限 ' + int(d.panel.nomination_limit);
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
