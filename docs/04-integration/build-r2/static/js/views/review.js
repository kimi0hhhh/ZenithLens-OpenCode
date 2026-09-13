// ⑤ 复盘页 —— R-UI-28/29/30/31（R2：U-01 成绩位出数 + U-04 回填态激活 + U-11 口径；C1+：对账筛选/排序）
import { loadSlice } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, tag, esc, tipAttr } from '../components.js';
import { prob, rate, delta, isNum, int, cls } from '../format.js';
import {
  METRIC_TIP, PENDING_FILL, BACKFILL_PENDING, SAMPLE_COUNT_LABEL, SAMPLE_INSUFFICIENT_NOTE,
  SHADOW_AUDIT_NOTE,
  RECON_FILTER_CLEAR, RECON_FUND_PLACEHOLDER, RECON_VETO_OPTIONS, RECON_SIGNAL_OPTIONS,
  RECON_LOADED_NOTE, RECON_LIMITED_NOTE, RECON_EMPTY_MATCH, RECON_SORT_MARK
} from '../copy.js';

const WIN_LABEL = { T1: 'T+1', T3: 'T+3', T15: 'T+15' };

// /review/scores 默认 data_kind=backtest（回测）；shadow_live（实盘）由调用方透传，不在前端推导
let dataKind = null;

// C1+ · 对账筛选/排序状态（纯视图层；数据刷新重渲染后保持，不持久化）
const reconFilter = { veto: 'all', signal: 'all', fund: '', sort: null };
const reconMeta = { loaded: 0, total: 0 };

export function init() {
  // C1+ · P 列排序：点击切换 升序 / 降序 / 取消（默认原序 = 时间倒序）
  const sp = document.getElementById('rv-sort-p');
  if (sp) sp.addEventListener('click', function () {
    reconFilter.sort = reconFilter.sort === 'asc' ? 'desc' : (reconFilter.sort === 'desc' ? null : 'asc');
    updateReconView();
  });
}

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('scores', '/review/scores' + (dataKind ? '?data_kind=' + encodeURIComponent(dataKind) : ''), null, function (d) {
      return !((d && d.scores || []).length);
    }),
    loadSlice('recon', '/review/reconciliation?limit=60'),
    loadSlice('shadowReview', '/engine/shadow-review'),
    // C0/E-4：降级条样本数来源（shadow_live hero.open_count；失败静默，不显示样本数）
    loadSlice('scoresLive', '/review/scores?data_kind=shadow_live'),
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
  // idle 归 loading（首帧 slice 尚未发起请求），保证四态可真实触发（U-03）
  root.dataset.state = sl.status === 'success' ? 'success' : (sl.status === 'idle' ? 'loading' : sl.status);
  renderHero();
  renderScores();
  renderDegrade();
  renderRecon();
}

/* ---------- R-UI-28 hero（U-01：命中率 + 基线 + Δ 三段式；data_kind 区分回测/实盘） ---------- */
function renderHero() {
  const el = document.getElementById('rv-hero');
  const sl = getSlice('scores');
  if (!sl.data || (sl.status !== 'success' && sl.status !== 'empty')) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '读取成绩失败' : '正在汇总历史成绩…') + '</div>'; return; }
  const d = sl.data;
  const h = d.hero;
  if (!h) { el.innerHTML = '<div class="mini">' + PENDING_FILL + '：尚无成绩记录</div>'; return; }
  const dt = h.delta_pp;
  const kind = h.data_kind === 'shadow_live' ? '实盘' : '回测';
  const kindCls = h.data_kind === 'shadow_live' ? 'blue' : 'gray';
  el.innerHTML = '<div class="hero"><div class="num"' + tipAttr(METRIC_TIP.hit_rate) + '>'
    + (isNum(h.hit_rate) ? (h.hit_rate * 100).toFixed(1) + '%' : '—') + '</div>'
    + '<div class="unit">' + esc(WIN_LABEL[h.window] || h.window || '') + ' ' + tag(kind, kindCls, '回测 ≠ 今日预测：由 data_kind 区分') + ' ' + esc(h.label || '命中率')
    + '<br><span class="mini">这是<b>' + esc(kind) + '</b>成绩，不是今日预测。基线 '
    + (isNum(h.baseline_rate) ? (h.baseline_rate * 100).toFixed(1) + '%' : '—')
    + '，Δ <span class="' + (isNum(dt) ? cls(dt) : 'flat') + '"' + tipAttr(METRIC_TIP.delta_pp) + '>' + delta(dt) + '</span>'
    + '<br>开口 ' + int(h.open_count) + ' 笔 · 样本期 ' + esc(h.sample_period || '—')
    + '</span></div></div>'
    + (d.note ? '<div class="mini" style="margin-top:10px;padding-top:8px;border-top:1px dashed rgba(24,32,25,.12)">' + esc(d.note) + '</div>' : '');
}

/* ---------- R-UI-29 三窗口 vs 基线（待填充纪律：baseline_status=pending 不留估计值） ---------- */
function renderScores() {
  const tbody = document.getElementById('rv-scores');
  const sl = getSlice('scores');
  if (!sl.data || (sl.status !== 'success' && sl.status !== 'empty')) { tbody.innerHTML = '<tr><td colspan="6" class="mini">' + (sl.status === 'error' ? '成绩文件不可读' : '—') + '</td></tr>'; return; }
  const rows = sl.data.scores || [];
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="mini">' + PENDING_FILL + '：暂无回测</td></tr>'; return; }
  tbody.innerHTML = rows.map(function (r) {
    const pending = r.baseline_status === 'pending';
    // v9.1/R-2：scores 行 = 持有期 horizon；sample_window 恒 full（全样本窗），不得与因子页六样本窗混用
    const sw = r.sample_window ? (r.sample_window === 'full' ? '全样本窗' : String(r.sample_window)) : '';
    return '<tr><td><b>' + esc(WIN_LABEL[r.window] || r.window) + '</b></td>'
      + '<td class="mini">' + esc(r.formula || '') + (r.data_kind === 'shadow_live' ? ' ' + tag('实盘', 'blue') : ' ' + tag('回测', 'gray'))
      + (sw ? ' · ' + esc(sw) : '') + '</td>'
      + '<td class="num ' + (isNum(r.hit_rate) ? 'up' : '') + '"' + tipAttr(METRIC_TIP.hit_rate) + '>' + (isNum(r.hit_rate) ? (r.hit_rate * 100).toFixed(1) + '%' : '—') + '</td>'
      + '<td class="num">' + int(r.open_count) + '</td>'
      + '<td class="num ' + (pending ? 'flat' : '') + '"' + tipAttr(METRIC_TIP.baseline_rate) + '>' + (pending ? PENDING_FILL : (isNum(r.baseline_rate) ? (r.baseline_rate * 100).toFixed(1) + '%' : '—')) + '</td>'
      + '<td class="num ' + (pending ? 'flat' : cls(r.delta_pp)) + '"' + tipAttr(METRIC_TIP.delta_pp) + '>' + (pending ? '—' : delta(r.delta_pp)) + '</td></tr>';
  }).join('');
  const cv = getSlice('cvConfig');
  const note = document.getElementById('rv-score-note');
  if (note) note.innerHTML = '<b>口径：</b>T+3/T+15 同期匹配基线未接通时保持「待填充」，此处留空而非填估计值；行主值取该持有期的全样本窗。'
    + (sl.data.note ? ' ' + esc(sl.data.note) : '')
    + (cv.status === 'success' && cv.data ? '（走前 CV · purge=' + esc(cv.data.purge_gap) + ' · placebo ≥' + (isNum(cv.data.placebo_min_pp) ? (cv.data.placebo_min_pp * 100).toFixed(1) + 'pp' : '—') + ' · holdout ' + int(cv.data.holdout_days) + ' 日）' : '');
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
    // C0/E-4：补样本数（shadow_live hero.open_count；不可得则不显示，不编造；<20 笔按项目门槛提示样本不足）
    const live = getSlice('scoresLive');
    const lh = (live.status === 'success' && live.data) ? live.data.hero : null;
    const n = (lh && isNum(lh.open_count)) ? lh.open_count : null;
    const sampleTxt = (n == null) ? ''
      : ' · ' + SAMPLE_COUNT_LABEL + ' ' + int(n) + ' 笔' + (n < 20 ? SAMPLE_INSUFFICIENT_NOTE : '');
    html += '<span style="margin-left:auto" class="mono">滚动 ' + int(d.rolling_days) + ' 日 ' + (isNum(d.hit_rate) ? (d.hit_rate * 100).toFixed(1) + '%' : '—')
      + ' vs ' + (isNum(d.baseline_rate) ? (d.baseline_rate * 100).toFixed(1) + '%' : '—') + ' · 偏差 ' + delta(d.deviation_pp) + sampleTxt + '</span>';
  }
  el.innerHTML = html;
  const note = document.getElementById('rv-degrade-note');
  // v9.5/PM：偏差审查（shadow_audit）同挂回算口径标签，与前向/实盘语义分离
  if (note) note.innerHTML = esc(SHADOW_AUDIT_NOTE) + (d.note ? '<br>' + esc(d.note) : '');
}

/* ---------- R-UI-31 逐笔对账（U-04：hit/miss 激活；待回填仅限未到期；C1+：筛选/排序 = 纯视图层） ---------- */
// result 为后端字段；/reconciliation 缺失时按契约同一判定式回退（t1_real>0 且 signal=up → hit）
function reconResult(r) {
  if (r.result != null) return r.result;
  if (r.signal === 'abstain') return 'abstain';
  if (!isNum(r.t1_real)) return 'pending';
  return (r.t1_real > 0 && r.signal === 'up') ? 'hit' : 'miss';
}

// 否决层分类（与行内判定口径一致；仅用于筛选，不重算业务）
function vetoCat(r) {
  if (r.veto_crowd_status === 'missing' || r.veto_klow2_status === 'missing') return 'missing';
  if (r.veto_crowd) return 'crowd';
  if (r.veto_klow2) return 'klow2';
  return 'none';
}

function reconAllRows() {
  const sl = getSlice('recon');
  return (sl.data && sl.data.rows) || [];
}

function reconActive() {
  return reconFilter.veto !== 'all' || reconFilter.signal !== 'all' || !!reconFilter.fund || !!reconFilter.sort;
}

// 筛选 + 排序（纯视图层；不改任何计算与数据；排序仅作用于已载入行）
function applyReconView(rows) {
  let list = rows.filter(function (r) {
    if (reconFilter.veto !== 'all' && vetoCat(r) !== reconFilter.veto) return false;
    if (reconFilter.signal !== 'all' && r.signal !== reconFilter.signal) return false;
    if (reconFilter.fund) {
      const q = reconFilter.fund.trim().toLowerCase();
      if (q) {
        const code = String(r.code || '').toLowerCase();
        const name = String(r.name || '').toLowerCase();
        if (code.indexOf(q) < 0 && name.indexOf(q) < 0) return false;
      }
    }
    return true;
  });
  if (reconFilter.sort) {
    const dir = (reconFilter.sort === 'asc') ? 1 : -1;
    list = list.slice().sort(function (a, b) {
      const av = isNum(a.p_up) ? a.p_up : null;
      const bv = isNum(b.p_up) ? b.p_up : null;
      if (av == null && bv == null) return 0;
      if (av == null) return 1;   // 缺失值恒置末尾（不参与排序语义）
      if (bv == null) return -1;
      return (av - bv) * dir;
    });
  }
  return list;
}

function reconRowHTML(r) {
  const veto = vetoCat(r) === 'missing' ? tag('数据缺失', 'gray')
    : (r.veto_crowd ? tag('拥挤度', 'warn') : (r.veto_klow2 ? tag('KLOW2', 'warn') : tag('双灯未亮', 'ok')));
  const sig = r.signal === 'up' ? tag('涨', 'red') : (r.signal === 'abstain' ? tag('弃权', 'gray') : tag('灰', 'blue'));
  const res = reconResult(r);
  // 待回填只允许出现在未到期记录（t1_real=null）；已到期必有 hit/miss/abstain
  const resTag = res === 'pending'
    ? (isNum(r.t1_real) ? '<span class="flat" title="状态与数据不一致，等待后端刷新">—</span>' : tag(BACKFILL_PENDING, 'gray', '未到期，t1_real 未产生'))
    : (res === 'hit' ? tag('命中', 'ok') : (res === 'miss' ? tag('未命中', 'red') : tag('弃权', 'gray')));
  const t1 = isNum(r.t1_real) ? '<span class="' + cls(r.t1_real) + '">' + rate(r.t1_real) + '</span>' : '<span class="flat">—</span>';
  const methodTip = (res !== 'pending' && (r.t1_real_method || r.backfill_proxy_code))
    ? '回填口径：' + (r.t1_real_method || '—') + (r.backfill_proxy_code ? ' · 代理 ' + r.backfill_proxy_code : '') : '';
  return '<tr data-recon-row="1"><td class="mono">' + esc(r.date) + '</td><td>' + esc(r.name || r.code) + '</td><td class="mini">' + esc(r.gate) + '</td>'
    + '<td class="num">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</td><td>' + veto + '</td><td>' + sig + '</td>'
    + '<td class="num">' + t1 + '</td><td' + (methodTip ? ' title="' + esc(methodTip) + '"' : '') + '>' + resTag + '</td></tr>';
}

function updateReconCount(listLen) {
  const el = document.getElementById('rv-count');
  if (!el) return;
  const loaded = reconMeta.loaded;
  const loadedNote = RECON_LOADED_NOTE.replace('{n}', String(loaded));
  const limited = reconMeta.total > loaded ? ' · ' + RECON_LIMITED_NOTE.replace('{total}', String(reconMeta.total)) : '';
  el.textContent = (reconActive() ? '已筛选 ' + listLen + ' / 共 ' + loaded + ' 条' : '共 ' + loaded + ' 条')
    + ' · ' + loadedNote + limited;
}

function updateReconSortMark() {
  const ind = document.getElementById('rv-p-ind');
  const btn = document.getElementById('rv-sort-p');
  if (ind) ind.textContent = RECON_SORT_MARK[reconFilter.sort || 'none'];
  if (btn) btn.classList.toggle('on', !!reconFilter.sort);
}

// 仅重绘表体与计数（筛选输入时不重建控件，避免丢失焦点）
function updateReconView() {
  const rows = reconAllRows();
  const list = applyReconView(rows);
  const tbody = document.getElementById('rv-body');
  if (rows.length && !list.length) tbody.innerHTML = '<tr><td colspan="8" class="mini">' + esc(RECON_EMPTY_MATCH) + '</td></tr>';
  else tbody.innerHTML = list.map(reconRowHTML).join('');
  updateReconCount(list.length);
  updateReconSortMark();
}

function renderReconFilters(rows) {
  const el = document.getElementById('rv-filters');
  if (!el) return;
  const vetoOpts = RECON_VETO_OPTIONS.map(function (o) {
    return '<option value="' + esc(o[0]) + '"' + (reconFilter.veto === o[0] ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
  }).join('');
  const sigOpts = RECON_SIGNAL_OPTIONS.map(function (o) {
    return '<option value="' + esc(o[0]) + '"' + (reconFilter.signal === o[0] ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
  }).join('');
  const funds = {};
  rows.forEach(function (r) { if (r.code) funds[r.code] = r.name || r.code; });
  const dl = Object.keys(funds).map(function (c) { return '<option value="' + esc(c) + '">' + esc(funds[c]) + '</option>'; }).join('');
  el.innerHTML = '<select id="rv-f-veto" title="否决层筛选">' + vetoOpts + '</select>'
    + '<select id="rv-f-signal" title="信号筛选">' + sigOpts + '</select>'
    + '<input id="rv-f-fund" list="rv-fund-list" placeholder="' + esc(RECON_FUND_PLACEHOLDER) + '" value="' + esc(reconFilter.fund) + '" style="width:150px">'
    + '<datalist id="rv-fund-list">' + dl + '</datalist>'
    + '<button class="btn sm" id="rv-f-clear" type="button">' + esc(RECON_FILTER_CLEAR) + '</button>'
    + '<span class="mini" id="rv-count" style="margin-left:auto"></span>';
  const vetoSel = document.getElementById('rv-f-veto');
  if (vetoSel) vetoSel.addEventListener('change', function () { reconFilter.veto = vetoSel.value; updateReconView(); });
  const sigSel = document.getElementById('rv-f-signal');
  if (sigSel) sigSel.addEventListener('change', function () { reconFilter.signal = sigSel.value; updateReconView(); });
  const fundInp = document.getElementById('rv-f-fund');
  if (fundInp) fundInp.addEventListener('input', function () { reconFilter.fund = fundInp.value; updateReconView(); });
  const clr = document.getElementById('rv-f-clear');
  if (clr) clr.addEventListener('click', function () {
    reconFilter.veto = 'all'; reconFilter.signal = 'all'; reconFilter.fund = ''; reconFilter.sort = null;
    renderReconFilters(rows);   // 复位控件显隐值
    updateReconView();
  });
}

function renderRecon() {
  const tbody = document.getElementById('rv-body');
  const sl = getSlice('recon');
  if (sl.status !== 'success' || !sl.data) {
    tbody.innerHTML = '<tr><td colspan="8" class="mini">' + (sl.status === 'error' ? '台账不可读' : '—') + '</td></tr>';
    const fb = document.getElementById('rv-filters');
    if (fb) fb.innerHTML = '';
    return;
  }
  const rows = sl.data.rows || [];
  reconMeta.loaded = rows.length;
  reconMeta.total = isNum(sl.data.total) ? sl.data.total : rows.length;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="mini">暂无台账记录</td></tr>';
    const fb = document.getElementById('rv-filters');
    if (fb) fb.innerHTML = '';
    return;
  }
  renderReconFilters(rows);
  updateReconView();
}
