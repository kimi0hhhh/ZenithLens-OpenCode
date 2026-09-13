// ② 分析页 —— R-UI-10/11/12/13（R2：U-03 双源真实空态 + U-08 QDII 标注 + U-11 口径）
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, forecastCard, chainHTML, weightingNote, tag, toast, esc, showModal, tipAttr } from '../components.js';
import { prob, cls, isNum, int, amt, FACTOR_WINDOW_LABEL } from '../format.js';
import { METRIC_TIP } from '../copy.js';

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
    // S5/R2-D1：portfolio 片不参与空态判定（open_count=0 不得使页面进 empty；仅作展示）
    loadSlice('portfolio', '/portfolio/forecast'),
    loadSlice('predictions', '/predictions', null, function (d) {
      return !((d && d.rows || []).length);
    }),
    loadSlice('holdings', '/holdings?with=valuation,nav,prediction')
  ]);
  render();
}

// S5/R2-D1：页面空态唯一数据条件 = /predictions.rows.length === 0（03-ui-design-v3 §4「监控集合为空或全部资产无预测记录」）
// rows>0（即使全窗 open_count=0）→ success，表与三窗口卡照常渲染。
function viewState() {
  const pf = getSlice('portfolio');
  const pr = getSlice('predictions');
  if (pf.status === 'error') return { status: 'error', error: pf.error };
  if (pr.status === 'error') return { status: 'error', error: pr.error };
  if (pf.status === 'loading' || pf.status === 'idle' || pr.status === 'loading' || pr.status === 'idle') return { status: 'loading' };
  if (pr.status === 'empty') return { status: 'empty', variant: emptyVariant() };
  return { status: 'success' };
}

// 「为什么空」按触发因素如实二分支（由数据判定，不编造）：
// 监控集合为空（holdings 无 A/B 档行）→ no_monitor；否则 = 无预测记录 → no_prediction
function emptyVariant() {
  const hp = getSlice('holdings');
  if (hp.status === 'success') {
    const rows = (hp.data && hp.data.rows) || [];
    const monitored = rows.filter(function (r) { return r.tier === 'A' || r.tier === 'B'; }).length;
    if (!monitored) return 'no_monitor';
  }
  return 'no_prediction';
}

// 空态事实卡：数字只取接口字段，不本地推算
function analyzeFacts() {
  const pf = getSlice('portfolio');
  const pr = getSlice('predictions');
  const t1 = ((pf.data && pf.data.windows) || []).find(function (w) { return w.window === 'T1'; }) || {};
  const n = ((pr.data && pr.data.rows) || []).length;
  return [
    ['今日开口', int(t1.open_count != null ? t1.open_count : n) + ' 只'],
    ['覆盖市值', isNum(t1.coverage_ratio) ? (t1.coverage_ratio * 100).toFixed(1) + '%' : '—'],
    ['触发条件', 'E1/E3 触发 → DDSM → 双否决'],
    ['下一步', '等待下次触发；可到「信号」页看台账']
  ];
}

export function render() {
  const root = document.getElementById('view-analyze');
  const st = viewState();
  const mount = root.querySelector('[data-slot]');
  if (st.status !== 'success') mountState(mount, 'analyze', st, activate, st.status === 'empty' ? analyzeFacts() : null);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = st.status;
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

/* ---------- R-UI-11 三窗口（A-08：加权口径由后端 weighting_basis/policy 驱动） ---------- */
function renderForecast() {
  const el = document.getElementById('an-forecast');
  const noteEl = document.getElementById('an-weighting');
  const sl = getSlice('portfolio');
  if (!sl.data || (sl.status !== 'success' && sl.status !== 'empty')) {
    el.innerHTML = '<div class="card mini">' + (sl.status === 'error' ? '预测服务暂不可用' : '正在计算三窗口预测…') + '</div>';
    if (noteEl) noteEl.innerHTML = '<b>加权口径：</b>预测服务暂不可用。';
    return;
  }
  el.innerHTML = (sl.data.windows || []).map(forecastCard).join('');
  if (noteEl) {
    const t1 = (sl.data.windows || []).find(function (w) { return w.window === 'T1'; }) || (sl.data.windows || [])[0] || {};
    noteEl.innerHTML = weightingNote(t1)
      + '加权规则（三条缺一不可）：① 只有开口仓位计入（分子分母同时剔除灰）· ② C/D 档不参与 · ③ 必须显示覆盖市值占比。'
      + '组合方向需同时满足出口阈值 0.52 与最小覆盖门槛（覆盖 ≥' + (isNum(t1.min_coverage_ratio) ? (t1.min_coverage_ratio * 100).toFixed(0) : 30)
      + '%、开口 ≥' + (t1.min_open_count != null ? t1.min_open_count : 3) + ' 只）。';
  }
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
  const nameMap = {};
  ((hp.data && hp.data.rows) || []).forEach(function (r) { nameMap[r.code] = r.name; });
  tbody.innerHTML = rows.slice().sort(function (a, b) {
    return (b.market_value || 0) - (a.market_value || 0);
  }).map(function (r) {
    const nm = nameMap[r.code] || r.code;
    const veto = vetoTag(r);
    const w = r.windows || {};
    // U-08：QDII 领先口径标注（PredictionSummary.qdii_lead_note，文案后端产出）
    const qdii = r.qdii_lead_note
      ? ' <span class="tag blue" title="' + esc(r.qdii_lead_note) + '">' + esc(r.qdii_lead_note) + '</span>' : '';
    return '<tr data-code="' + esc(r.code) + '" style="cursor:pointer">'
      + '<td><div class="fname">' + esc(nm) + qdii + '</div><div class="fcode">' + esc(r.code) + ' · ' + esc(r.gate_label || r.gate) + '</div></td>'
      + '<td style="color:inherit">' + esc(r.tier || '—') + '</td>'
      + '<td class="mini">' + esc(r.gate_label || r.gate) + '</td>'
      + '<td class="num"' + tipAttr(METRIC_TIP.weighted_p) + '>' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</td>'
      + '<td>' + veto + '</td>'
      + '<td>' + winTag(w.T1) + '</td><td>' + winTag(w.T3) + '</td><td>' + winTag(w.T15) + '</td>'
      + '<td class="num amt">' + (r.market_value == null ? '—' : amt(r.market_value)) + '</td></tr>';
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
