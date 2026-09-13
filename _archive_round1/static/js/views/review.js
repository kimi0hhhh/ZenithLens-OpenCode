// ⑤ 复盘页 —— R-UI-28/29/30/31
import { loadSlice } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, tag, esc } from '../components.js';
import { prob, rate, delta, isNum, int, cls } from '../format.js';

const WIN_LABEL = { T1: 'T+1', T3: 'T+3', T15: 'T+15' };

export function init() { }

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('scores', '/review/scores'),
    loadSlice('recon', '/review/reconciliation?limit=60'),
    loadSlice('shadowReview', '/engine/shadow-review'),
    loadSlice('cvConfig', '/review/cv-config')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-review');
  const sl = getSlice('scores');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'review', sl, activate);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
  renderHero();
  renderScores();
  renderDegrade();
  renderRecon();
}

/* ---------- R-UI-28 hero ---------- */
function renderHero() {
  const el = document.getElementById('rv-hero');
  const sl = getSlice('scores');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '读取成绩失败' : '正在汇总历史成绩…') + '</div>'; return; }
  const d = sl.data;
  const h = d.hero;
  if (!h) { el.innerHTML = '<div class="mini">尚无成绩记录</div>'; return; }
  const dt = h.delta_pp;
  el.innerHTML = '<div class="hero"><div class="num">' + (isNum(h.hit_rate) ? (h.hit_rate * 100).toFixed(1) + '%' : '—') + '</div>'
    + '<div class="unit">' + esc(WIN_LABEL[h.window] || h.window || '') + ' ' + esc(h.label || '命中率') + '<br>'
    + '<span class="mini">这是<b>回测/实盘</b>成绩，不是今日预测。基线 ' + (isNum(h.baseline_rate) ? (h.baseline_rate * 100).toFixed(1) + '%' : '—')
    + '，Δ <span class="' + cls(dt) + '">' + delta(dt) + '</span></span></div></div>';
}

/* ---------- R-UI-29 三窗口 vs 基线 ---------- */
function renderScores() {
  const tbody = document.getElementById('rv-scores');
  const sl = getSlice('scores');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="6" class="mini">' + (sl.status === 'error' ? '成绩文件不可读' : '—') + '</td></tr>'; return; }
  const rows = sl.data.scores || [];
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="mini">暂无回测</td></tr>'; return; }
  tbody.innerHTML = rows.map(function (r) {
    const pending = r.baseline_status === 'pending';
    return '<tr><td><b>' + esc(WIN_LABEL[r.window] || r.window) + '</b></td>'
      + '<td class="mini">' + esc(r.formula || '') + (r.data_kind === 'shadow_live' ? ' ' + tag('实盘', 'blue') : ' ' + tag('回测', 'gray')) + '</td>'
      + '<td class="num ' + (isNum(r.hit_rate) ? 'up' : '') + '">' + (isNum(r.hit_rate) ? (r.hit_rate * 100).toFixed(1) + '%' : '—') + '</td>'
      + '<td class="num">' + int(r.open_count) + '</td>'
      + '<td class="num ' + (pending ? 'flat' : '') + '">' + (pending ? '待填充' : (isNum(r.baseline_rate) ? (r.baseline_rate * 100).toFixed(1) + '%' : '—')) + '</td>'
      + '<td class="num ' + (pending ? 'flat' : cls(r.delta_pp)) + '">' + (pending ? '—' : delta(r.delta_pp)) + '</td></tr>';
  }).join('');
  const cv = getSlice('cvConfig');
  const note = document.getElementById('rv-score-note');
  if (note) note.innerHTML = '<b>已知缺口：</b>T+3/T+15 同期匹配基线尚未填充，此处留空而非填估计值。口径一步一定义。'
    + (cv.status === 'success' && cv.data ? '（走前 CV · purge=' + esc(cv.data.purge_gap) + ' · holdout ' + int(cv.data.holdout_days) + ' 日）' : '');
}

/* ---------- R-UI-30 影子盘降级审查条 ---------- */
function renderDegrade() {
  const el = document.getElementById('rv-degrade');
  const sl = getSlice('shadowReview');
  if (sl.status !== 'success' || !sl.data) { el.className = 'degrade idle'; el.textContent = sl.status === 'error' ? '影子盘审查读取失败' : '加载中…'; return; }
  const d = sl.data;
  el.className = 'degrade ' + (d.status === 'ok' ? 'ok' : (d.status === 'bad' ? 'bad' : 'idle'));
  let html = esc(d.message || '');
  if (d.status !== 'idle') {
    html += '<span style="margin-left:auto" class="mono">滚动 ' + int(d.rolling_days) + ' 日 ' + (isNum(d.hit_rate) ? (d.hit_rate * 100).toFixed(1) + '%' : '—')
      + ' vs ' + (d.baseline_rate * 100).toFixed(1) + '% · 偏差 ' + delta(d.deviation_pp) + '</span>';
  }
  el.innerHTML = html;
  const note = document.getElementById('rv-degrade-note');
  if (note && d.note) note.innerHTML = esc(d.note);
}

/* ---------- R-UI-31 逐笔对账 ---------- */
function renderRecon() {
  const tbody = document.getElementById('rv-body');
  const sl = getSlice('recon');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="8" class="mini">' + (sl.status === 'error' ? '台账不可读' : '—') + '</td></tr>'; return; }
  const rows = sl.data.rows || [];
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="8" class="mini">暂无台账记录</td></tr>'; return; }
  tbody.innerHTML = rows.map(function (r) {
    const veto = (r.veto_crowd_status === 'missing' || r.veto_klow2_status === 'missing') ? tag('数据缺失', 'gray')
      : (r.veto_crowd ? tag('拥挤度', 'warn') : (r.veto_klow2 ? tag('KLOW2', 'warn') : tag('双灯未亮', 'ok')));
    const sig = r.signal === 'up' ? tag('涨', 'red') : (r.signal === 'abstain' ? tag('弃权', 'gray') : tag('灰', 'blue'));
    const res = r.result === 'hit' ? tag('命中', 'ok') : (r.result === 'miss' ? tag('未命中', 'red') : (r.result === 'abstain' ? tag('弃权', 'gray') : tag('待回填', 'gray')));
    const t1 = isNum(r.t1_real) ? '<span class="' + cls(r.t1_real) + '">' + rate(r.t1_real) + '</span>' : '<span class="flat">—</span>';
    return '<tr><td class="mono">' + esc(r.date) + '</td><td>' + esc(r.name || r.code) + '</td><td class="mini">' + esc(r.gate) + '</td>'
      + '<td class="num">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</td><td>' + veto + '</td><td>' + sig + '</td>'
      + '<td class="num">' + t1 + '</td><td>' + res + '</td></tr>';
  }).join('');
}
