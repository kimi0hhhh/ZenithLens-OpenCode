// ② 分析页 —— R-UI-10/11/12/13
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, forecastCard, chainHTML, tag, toast, esc, showModal } from '../components.js';
import { prob, cls, isNum, int, amt, FACTOR_WINDOW_LABEL } from '../format.js';

export function init() {
  const body = document.getElementById('an-body');
  if (body) {
    body.addEventListener('click', function (e) {
      const tr = e.target.closest('tr[data-code]');
      if (tr) openChain(tr.dataset.code);
    });
  }
}

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('defs', '/meta/definitions'),
    loadSlice('portfolio', '/portfolio/forecast'),
    loadSlice('predictions', '/predictions'),
    loadSlice('holdings', '/holdings?with=valuation,nav,prediction')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-analyze');
  const sl = getSlice('portfolio');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'analyze', sl, activate);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
  renderDefs();
  renderForecast();
  renderTable();
}

/* ---------- R-UI-10 T+1 口径 + 三执行路径 ---------- */
function renderDefs() {
  const el = document.getElementById('an-defs');
  const sl = getSlice('defs');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '口径定义读取失败' : '—') + '</div>';
    return;
  }
  const d = sl.data;
  el.innerHTML = '<div class="mono" style="font-size:14px;margin-bottom:8px">' + esc(d.formula) + '</div>'
    + '<div class="mini" style="line-height:1.9">' + esc(d.timing_note || '')
    + '<br>信号生成时点：<b>' + esc(d.signal_time || '—') + '</b></div>'
    + '<div class="grid3" style="margin-top:14px">' + (d.paths || []).map(function (p) {
      return '<div class="factor"><div class="k">' + esc(p.label) + (p.executable ? ' ' + tag('可执行', 'ok') : '') + '</div>'
        + '<div class="mini" style="margin-top:6px">' + esc(p.steps || '') + '<br><span class="' + (p.executable ? 'up' : 'flat') + '">' + esc(p.caveat || '') + '</span></div></div>';
    }).join('') + '</div>'
    + '<div class="mini" style="margin-top:14px;padding-top:12px;border-top:1px dashed rgba(24,32,25,.12)"><b>' + esc(d.conclusion || '') + '</b></div>';
}

/* ---------- R-UI-11 三窗口 ---------- */
function renderForecast() {
  const el = document.getElementById('an-forecast');
  const sl = getSlice('portfolio');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="card mini">' + (sl.status === 'error' ? '预测服务暂不可用' : '正在计算三窗口预测…') + '</div>';
    return;
  }
  el.innerHTML = (sl.data.windows || []).map(forecastCard).join('');
}

/* ---------- R-UI-12 参与预测持仓表 ---------- */
function renderTable() {
  const sl = getSlice('predictions');
  const hp = getSlice('holdings');
  const tbody = document.getElementById('an-body');
  if (sl.status !== 'success' || !sl.data) {
    tbody.innerHTML = '<tr><td colspan="9" class="mini">' + (sl.status === 'error' ? '预测明细读取失败' : '—') + '</td></tr>';
    return;
  }
  const rows = sl.data.rows || [];
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="9" class="mini">今日无资产开口</td></tr>'; return; }
  const hMap = {};
  ((hp.data && hp.data.rows) || []).forEach(function (r) { hMap[r.code] = r; });
  tbody.innerHTML = rows.slice().sort(function (a, b) {
    const ma = hMap[a.code] ? (hMap[a.code].market_value || 0) : 0;
    const mb = hMap[b.code] ? (hMap[b.code].market_value || 0) : 0;
    return mb - ma;
  }).map(function (r) {
    const h = hMap[r.code] || {};
    const veto = vetoTag(r);
    const w = r.windows || {};
    return '<tr data-code="' + esc(r.code) + '" style="cursor:pointer">'
      + '<td><div class="fname">' + esc(h.name || r.code) + '</div><div class="fcode">' + esc(r.code) + ' · ' + esc(r.gate_label || r.gate) + '</div></td>'
      + '<td style="color:inherit">' + esc(h.tier || '—') + '</td>'
      + '<td class="mini">' + esc(r.gate_label || r.gate) + '</td>'
      + '<td class="num">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</td>'
      + '<td>' + veto + '</td>'
      + '<td>' + winTag(w.T1) + '</td><td>' + winTag(w.T3) + '</td><td>' + winTag(w.T15) + '</td>'
      + '<td class="num amt">' + (h.market_value == null ? '—' : amt(h.market_value)) + '</td></tr>';
  }).join('');
}

function vetoTag(r) {
  if (r.veto_crowd_status === 'missing' || r.veto_klow2_status === 'missing') return tag('数据缺失', 'gray', '否决层数据缺失 → 强制弃权（A-05）');
  if (r.veto_crowd) return tag('拥挤度', 'warn');
  if (r.veto_klow2) return tag('KLOW2', 'warn');
  return tag('未亮灯', 'ok');
}
function winTag(w) {
  if (!w) return tag('—', 'gray');
  if (w.validation_status === 'pending_cv') return tag('观察', 'gray', '该窗口未验证');
  const map = { up: ['涨', 'red'], gray: ['灰', 'blue'], down: ['跌', 'down'] };
  const m = map[w.direction] || ['—', 'gray'];
  return tag(m[0], m[1], w.formula || '');
}

/* ---------- R-UI-13 六步推导链 ---------- */
export function openChain(code) {
  get('/predictions/' + code).then(function (env) {
    showModal('推导链 · ' + code, chainHTML(env.data && env.data.chain));
  }).catch(function (e) { toast('读取推导链失败：' + e.message); });
}
