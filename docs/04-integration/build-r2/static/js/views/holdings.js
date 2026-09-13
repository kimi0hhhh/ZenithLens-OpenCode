// ① 持仓页 —— R-UI-01/02/03/04/05/06（R2：U-02 vsum 主指标 + U-06 主源口径 + U-07 验证四态 + U-08 QDII 标注 + U-11/U-12）
import { loadSlice, get, post, put, del } from '../api.js';
import { getSlice, setSlice, getState } from '../store.js';
import { mountState, valBadge, unknownCell, changeCell, pnlCell, tag, progressBar, forecastCard, weightingNote, toast, esc, statCard, showModal, verifyTag, tipAttr } from '../components.js';
import { amt, prob, rate, cls, isNum, shares as fShares, nav as fNav, int, md, FACTOR_WINDOW_LABEL } from '../format.js';
import { CONF_LABEL, confReasonText, WINDOW_PHASE, OFFICIAL_FACT_NOTE, METRIC_TIP, COVERAGE_VALUATION_LABEL } from '../copy.js';

const COLS = { cost: true, pnl: true, val: true, sig: true, adv: true };

export function init() {
  const colBtn = document.getElementById('btn-colset');
  if (colBtn) colBtn.addEventListener('click', function (e) { colMenu(e); });
  const addBtn = document.getElementById('btn-add-fund');
  if (addBtn) addBtn.addEventListener('click', function () { openFund(''); });

  bind('fd-code', 'input', onCodeInput);
  bind('fd-save', 'click', saveFund);
  bind('am-save', 'click', saveAmt);
  bind('dl-save', 'click', doDelete);
  bind('dl-cancel', 'click', function () { close('dlg-del'); });
  bind('fd-cancel', 'click', function () { close('dlg-fund'); });
  bind('am-cancel', 'click', function () { close('dlg-amt'); });

  const fold = document.getElementById('fold-risk');
  if (fold) fold.addEventListener('toggle', function () {
    if (this.open) loadRisk();
  });
}

function bind(id, ev, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(ev, fn);
}
function close(id) { const d = document.getElementById(id); if (d) d.close(); }

export async function activate() {
  render();
  await refresh();
}

export async function refresh() {
  const root = document.getElementById('view-holdings');
  root.dataset.state = 'loading';
  mountState(root.querySelector('[data-slot]'), 'holdings', { status: 'loading' }, stateRetry);
  await Promise.allSettled([
    loadSlice('holdings', '/holdings?with=valuation,nav,prediction', null, function (d) {
      return !((d && d.rows || []).length);
    }),
    loadSlice('precision', '/valuations/precision'),
    loadSlice('portfolio', '/portfolio/forecast'),
    loadSlice('coverage', '/holdings/coverage'),
    loadSlice('predictions', '/predictions')
  ]);
  render();
}

// 四态重试：empty 走「录入第一只基金」，其余重发请求
function stateRetry(reason) {
  if (reason === 'empty') { openFund(''); return; }
  refresh();
}

export function render() {
  const root = document.getElementById('view-holdings');
  const hp = getSlice('holdings');
  mountState(root.querySelector('[data-slot]'), 'holdings', hp, stateRetry);
  // U-03：empty/loading/error 一律让四态容器接管（view-main 由 CSS 隐藏，不渲染数字行）
  root.dataset.state = hp.status === 'success' ? 'success' : hp.status;
  if (hp.status === 'success') {
    renderOverview();
    renderVSum();
    renderForecast();
    renderCoverage();
    renderTable();
  }
}

/* ---------- R-UI-01 资产总览四卡（U-11：关键数字口径 tooltip） ---------- */
function setTip(id, tip) {
  const el = document.getElementById(id);
  if (el) { if (tip) el.setAttribute('title', tip); else el.removeAttribute('title'); }
}

function renderOverview() {
  const hp = getSlice('holdings');
  const s = hp.data && hp.data.summary;
  const rows = (hp.data && hp.data.rows) || [];
  const covered = s ? s.covered_count : 0;
  const total = s ? s.total_count : rows.length;
  const fallback = s ? s.fallback_value : 0;
  document.getElementById('pa-total').innerHTML = s ? amt(s.total_value) : '—';
  document.getElementById('pa-today').innerHTML = s && isNum(s.today_pnl_amt)
    ? '<span class="' + cls(s.today_pnl_amt) + '">' + amt(s.today_pnl_amt) + '</span>' : '—';
  document.getElementById('pa-pnl').innerHTML = s
    ? '<span class="' + cls(s.total_pnl_amt) + '">' + amt(s.total_pnl_amt) + '</span>' : '—';
  document.getElementById('pa-ret').innerHTML = s && isNum(s.return_rate)
    ? '<span class="' + cls(s.return_rate) + '">' + rate(s.return_rate) + '</span>' : '—';
  setTip('pa-total', METRIC_TIP.total_value);
  setTip('pa-today', METRIC_TIP.today_pnl);
  setTip('pa-pnl', METRIC_TIP.total_pnl);
  setTip('pa-ret', METRIC_TIP.return_rate);
  const sub = document.getElementById('pa-today-sub');
  // C0/E-2：口径词由字典统一——「估值覆盖」= change_rate ≠ null 只数（不再直出「可信估值覆盖」）
  sub.innerHTML = esc(COVERAGE_VALUATION_LABEL + ' ' + covered + '/' + total + ' 只')
    + (isNum(fallback) && fallback > 0
      ? ' · <span class="cov-warn">未知行按成本计 ' + amt(fallback) + '</span>' : '');
  sub.setAttribute('title', METRIC_TIP.covered_count);
}

/* ---------- R-UI-02 估值精度汇总条（R2 · U-02/D-1：主指标=估算档 estimate_quality；官方档单列 chip） ---------- */
const CONF_CLS = { high: 'ch', mid: 'cm', low: 'cl', unknown: 'cu' };

// 主指标 null 时的原因 chip：只用后端已给数据归因（holdings 行 conf_reason / estimate_quality.note），前端不推断口径
function estimateBlockReason(eq) {
  const seen = [];
  const hp = getSlice('holdings');
  ((hp.data && hp.data.rows) || []).forEach(function (r) {
    const v = r.valuation || {};
    if (v.confidence === 'unknown' && v.conf_reason && seen.indexOf(v.conf_reason) < 0) seen.push(v.conf_reason);
  });
  const labels = seen.map(confReasonText).filter(Boolean);
  if (labels.length) return labels.join(' / ');
  return (eq && eq.note) ? String(eq.note) : '';
}

function renderVSum() {
  const el = document.getElementById('val-sum');
  const sl = getSlice('precision');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<span class="mini">' + (sl.status === 'error' ? '估值精度读取失败' : '—') + '</span>';
    return;
  }
  const d = sl.data;
  const eq = d.estimate_quality || null;      // v9.1/D-1 估算档（intraday/holdings/proxy）
  const off = d.official_summary || null;     // v9.1/D-1 官方档单列
  const groups = (eq && Array.isArray(eq.groups)) ? eq.groups : (d.groups || []);
  const chips = groups.map(function (g) {
    // C0/E-3：未知组标签走字典（后端 label「无」易被误读为零/无样本；统一显示「无可信估算」）
    const glabel = g.confidence === 'unknown'
      ? (CONF_LABEL.unknown || g.label)
      : (g.label || CONF_LABEL[g.confidence] || g.confidence);
    return '<span class="chip"' + tipAttr('估算档分组（对象 = intraday/holdings/proxy）') + '><span class="vb ' + (CONF_CLS[g.confidence] || 'cu') + '" style="margin-right:5px">' + esc(glabel) + '</span>'
      + int(g.count) + ' 只 · ' + amt(g.market_value) + ' · 占 ' + (isNum(g.weight_ratio) ? (g.weight_ratio * 100).toFixed(1) + '%' : '—') + '</span>';
  }).join('');
  const modeChips = (d.mode_distribution || []).map(function (m) {
    return '<span class="chip">' + esc(m.mode_label) + ' ' + int(m.count) + ' 只</span>';
  }).join('');
  const base = isNum(eq && eq.industry_baseline_mae_rate) ? eq.industry_baseline_mae_rate
    : (isNum(d.industry_baseline_mae_rate) ? d.industry_baseline_mae_rate : 0.008);
  // 主指标：估算档 weighted_mae_rate（官方档不混入）；null → 「暂无法计算」+ 原因 chip
  let mainChip;
  if (isNum(eq && eq.weighted_mae_rate)) {
    mainChip = '<span class="chip"' + tipAttr(METRIC_TIP.weighted_mae_est) + '>估算档市值加权 MAE <b style="color:'
      + (eq.weighted_mae_rate <= base ? 'var(--down)' : 'var(--gold)') + '">' + (eq.weighted_mae_rate * 100).toFixed(2)
      + '%</b> ／ 行业基准 ' + (base * 100).toFixed(2) + '%</span>';
  } else {
    const why = estimateBlockReason(eq);
    mainChip = '<span class="chip" style="border-style:dashed"' + tipAttr('主指标 = estimate_quality.weighted_mae_rate；未出数原因取后端数据') + '>估算档暂无法计算'
      + (why ? ' · ' + esc(why) : '') + '</span>';
  }
  // 官方档单列（既成事实，不参与主指标）
  const offChip = off
    ? '<span class="chip"' + tipAttr(OFFICIAL_FACT_NOTE + (off.note ? '；' + off.note : '')) + '>官方档（既成事实）' + int(off.count) + ' 只 · 占 '
      + (isNum(off.weight_ratio) ? (off.weight_ratio * 100).toFixed(1) + '%' : '—') + '</span>'
    : '';
  // 全档 weighted_mae_rate 仅作参考展示（v9.1/M3：语义登记为「全档参考」）
  const allRef = isNum(d.weighted_mae_rate)
    ? '<span class="chip" style="border-style:dashed"' + tipAttr('全档（含官方）仅作参考口径，不得再作主指标展示') + '>全档参考 MAE '
      + (d.weighted_mae_rate * 100).toFixed(2) + '%</span>'
    : '';
  // 精度窗累计（v9.1/D-2：window_phase 双时点文案）
  const filled = isNum(d.window_filled_days) ? int(d.window_filled_days) : '—';
  const phase = d.window_phase && WINDOW_PHASE[d.window_phase] ? ' · ' + WINDOW_PHASE[d.window_phase] : '';
  const winChip = '<span class="chip"' + tipAttr(METRIC_TIP.window_filled) + '>精度窗 ' + filled + '/40 日'
    + (d.window_status_label ? ' · ' + esc(d.window_status_label) : '') + esc(phase) + '</span>';
  const wd = isNum(eq && eq.window_days) ? eq.window_days : d.window_days;
  el.innerHTML = mainChip + offChip + chips + modeChips + allRef + winChip
    + '<span class="chip" style="border-style:dashed">口径：近 ' + int(wd) + ' 个交易日回测 · 估算涨跌 vs 官方净值涨跌</span>';
}

/* ---------- R-UI-11 组合预测 ---------- */
function renderForecast() {
  const el = document.getElementById('pf-forecast');
  const sl = getSlice('portfolio');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="card mini">' + (sl.status === 'error' ? '预测服务暂不可用' : '正在计算三窗口预测…') + '</div>';
    return;
  }
  const ws = sl.data.windows || [];
  el.innerHTML = ws.map(forecastCard).join('');
  const win = ws.find(function (w) { return w.window === 'T1'; }) || {};
  const note = document.getElementById('pf-note');
  if (note) note.innerHTML = weightingNote(win)
    + '<b>开口 ' + int(win.open_count) + ' 只，覆盖市值 ' + amt(win.coverage_value) + '，仅占组合 '
    + (isNum(win.coverage_ratio) ? (win.coverage_ratio * 100).toFixed(1) + '%' : '—') + '。</b>'
    + '<b style="color:var(--gold)">其余 ' + (isNum(win.excluded_ratio) ? (win.excluded_ratio * 100).toFixed(1) : '—') + '% 的仓位今日不开口</b> —— 灰不是"看平"，是从分子分母同时剔除。';
}

/* ---------- R-UI-04 覆盖度四档 ---------- */
function renderCoverage() {
  const el = document.getElementById('cov-bar');
  const sl = getSlice('coverage');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '档位读取失败' : '—') + '</div>';
    return;
  }
  const d = sl.data;
  el.innerHTML = (d.tiers || []).map(function (t) {
    return '<div class="cov" title="' + esc(t.action_hint || '') + '"><div class="h"><span class="dot" style="background:' + esc(t.color) + '"></span>'
      + esc(t.tier_label) + '</div><div class="v">' + int(t.count) + ' 只 · ' + amt(t.market_value) + '</div>'
      + '<div class="s">占市值 ' + (isNum(t.weight_ratio) ? (t.weight_ratio * 100).toFixed(1) + '%' : '—') + ' —— ' + esc(t.description || '') + '</div>'
      + (t.member_names && t.member_names.length ? '<div class="cs">' + esc(t.member_names.join('、')) + '</div>' : '') + '</div>';
  }).join('');
  const note = document.getElementById('cov-note');
  if (note) {
    const covNote = d.prediction_coverage_note;
    const uni = d.prediction_universe_count;
    const pend = d.pending_verification_count;
    const names = d.pending_verification_names;
    note.innerHTML = esc(d.invalidation_note || '')
      + '<br><b style="color:var(--down)">原理无解：' + int(d.no_solution_count) + ' 只。</b>'
      + ((covNote || isNum(uni)) ? '<br><b>预测覆盖：' + esc(covNote || (int(uni) + ' 只')) + '</b>'
        + (isNum(pend) ? '（待结论 ' + int(pend) + ' 只，不计入覆盖增长）' : '') : '')
      + (names && names.length ? '<br><span style="color:var(--ink3)">待结论清单：' + esc(names.join('、')) + '</span>' : '');
  }
}

/* ---------- R-UI-05 持仓明细表 ---------- */
function renderTable() {
  const hp = getSlice('holdings');
  const rows = (hp.data && hp.data.rows) || [];
  const tbody = document.getElementById('hd-body');
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="11" class="mini">暂无持仓行</td></tr>'; return; }
  const ORDER = ['境内指数', '主动', 'QDII', '黄金', '其他'];
  const groups = {};
  rows.forEach(function (r) {
    const g = r.group_label || '其他';
    (groups[g] = groups[g] || []).push(r);
  });
  const names = Object.keys(groups).sort(function (a, b) {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  let html = '';
  names.forEach(function (g) {
    // 仅按后端 market_value 排序用于展示；**不在前端做分组金额求和**（业务数据归后端）
    const list = groups[g].slice().sort(function (a, b) { return (b.market_value || 0) - (a.market_value || 0); });
    html += '<tr class="grp" data-g="' + esc(g) + '"><td colspan="11"><span class="caret">▼</span>' + esc(g) + ' · ' + list.length + ' 只</td></tr>';
    list.forEach(function (r) { html += rowHTML(r, g); });
  });
  tbody.innerHTML = html;
  applyCols();
  Array.prototype.forEach.call(tbody.querySelectorAll('tr.grp'), function (t) {
    t.addEventListener('click', function () {
      const g = t.dataset.g;
      const caret = t.querySelector('.caret');
      const on = caret.textContent === '▼';
      caret.textContent = on ? '▶' : '▼';
      Array.prototype.forEach.call(tbody.querySelectorAll('tr[data-g="' + g + '"]:not(.grp)'), function (row) {
        row.style.display = on ? 'none' : '';
      });
    });
  });
  Array.prototype.forEach.call(tbody.querySelectorAll('[data-menu]'), function (b) {
    b.addEventListener('click', function (e) { openPop(e, b.dataset.menu); });
  });
  bindBadges();
}

function rowHTML(r, g) {
  const v = r.valuation || {};
  const mv = r.market_value;
  const cost = r.cost_amount;
  const today = r.today_pnl_amt;
  const pnl = r.pnl_amt;
  const pct = v.change_rate;
  const w = r.weight_ratio;
  // U-07：C/D 档与「验证中/未通过」行内可见四态标签（直读后端 verify_status，不推测）
  const showVerify = r.verify_status && (r.tier === 'C' || r.tier === 'D'
    || r.verify_status === 'validating' || r.verify_status === 'validation_failed');
  // U-08：QDII 领先口径标注（文案后端产出，非 null 才显示，不硬编码「1–2 天」）
  const qdii = r.qdii_lead_note
    ? '<span class="tag blue" style="margin-left:5px" title="' + esc(r.qdii_lead_note) + '">' + esc(r.qdii_lead_note) + '</span>' : '';
  return '<tr data-g="' + esc(g) + '">'
    + '<td><div class="fname">' + esc(r.name) + (r.confirm_days === 2 ? '<span class="tag warn" style="margin-left:5px">T+2</span>' : (r.confirm_days === 3 ? '<span class="tag warn" style="margin-left:5px">T+3</span>' : '')) + qdii
    + '</div><div class="fcode">' + esc(r.code) + ' · ' + esc(r.tier) + ' ' + esc(r.proxy_name || r.proxy_code || '') + (showVerify ? ' · ' + verifyTag(r) : '') + '</div></td>'
    + '<td class="num amt' + (mv == null ? ' unk' : '') + '"' + tipAttr(METRIC_TIP.total_value) + '>' + (mv == null ? '—' : amt(mv)) + (r.mv_source === null && r.fallback_value ? '<div class="fcode">成本 ' + amt(r.fallback_value) + '</div>' : '') + '</td>'
    + '<td class="num mini amt" data-col="cost">' + amt(cost) + '</td>'
    + '<td class="num amt">' + pnlCell(today) + '</td>'
    + '<td class="num">' + changeCell(pct) + '</td>'
    + '<td class="num amt ' + cls(pnl) + '" data-col="pnl">' + amt(pnl) + '</td>'
    + '<td class="num mini">' + (isNum(w) ? (w * 100).toFixed(1) + '%' : '—') + '</td>'
    + '<td data-col="val">' + valBadge(v, { code: r.code }) + '</td>'
    + '<td data-col="sig">' + predCell(r) + '</td>'
    + '<td data-col="adv"><span class="tag gray" title="契约缺失建议字段，见 12-interface-request">—</span></td>'
    + '<td class="num"><button class="btn sm" data-menu="' + esc(r.code) + '">···</button></td></tr>';
}

function predCell(r) {
  const p = r.prediction;
  if (!p) {
    if (r.tier === 'C') {
      // U-07 ③：信号列同步后端验证状态（升 B 后由 tier 数据刷新自然切换）
      return verifyTag(r);
    }
    if (r.tier === 'D') return tag('暴露待定', 'gray', '暴露待定，需先做穿透');
    return tag('灰', 'blue', '能算但无边际，按纪律不开口');
  }
  if (p.signal === 'up') return tag('涨 ' + prob(p.p_up), 'red', (p.gate_label || '') + ' · ' + (p.reason || ''));
  if (p.signal === 'abstain') return tag('弃权 ' + prob(p.p_up), 'gray', (p.signal_label || '') + ' · ' + (p.reason || ''));
  return tag('灰 ' + prob(p.p_up), 'blue', (p.signal_label || '') + ' · ' + (p.reason || ''));
}

function applyCols() {
  Object.keys(COLS).forEach(function (k) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-col="' + k + '"]'), function (e) {
      e.style.display = COLS[k] ? '' : 'none';
    });
  });
}

function colMenu(e) {
  const p = document.getElementById('pop');
  const lab = { cost: '成本', pnl: '累计收益', val: '估值来源', sig: 'T+1 预测', adv: '建议' };
  p.innerHTML = Object.keys(COLS).map(function (k) {
    return '<button data-col-toggle="' + k + '">' + (COLS[k] ? '✓ ' : '　') + lab[k] + '</button>';
  }).join('');
  p.classList.add('show');
  const r = e.target.getBoundingClientRect();
  p.style.left = Math.min(r.left, window.innerWidth - 170) + 'px';
  p.style.top = (r.bottom + 6) + 'px';
  e.stopPropagation();
  Array.prototype.forEach.call(p.querySelectorAll('[data-col-toggle]'), function (b) {
    b.addEventListener('click', function () {
      const k = b.dataset.colToggle;
      COLS[k] = !COLS[k];
      applyCols();
      toast('已' + (COLS[k] ? '显示' : '隐藏') + '该列');
      p.classList.remove('show');
    });
  });
}

/* ---------- R-UI-03 · 徽章详情（估值可追溯） ---------- */
function bindBadges() {
  Array.prototype.forEach.call(document.querySelectorAll('[data-vb-code]'), function (badge) {
    badge.addEventListener('click', function () {
      const code = badge.dataset.vbCode;
      get('/valuations/' + code + '?history=true').then(function (env) {
        const d = env.data || {};
        const hist = (d.history || []).map(function (v) {
          return '<div class="mini">' + esc(v.written_at) + ' · ' + esc(v.mode_label || v.valuation_mode)
            + (v.is_first_of_day ? ' · 当日首次口径' : '') + '</div>';
        }).join('');
        showModal('估值来源 · ' + code, (d.valuation && d.valuation.trace_text ? '降级链路：' + d.valuation.trace_text + '<br>' : '')
          + (hist || '<div class="mini">无当日入账历史</div>'));
      }).catch(function (e) { toast('读取估值详情失败：' + e.message); });
    });
  });
}

/* ---------- R-UI-06 风险指标（展开才加载） ---------- */
let riskLoaded = false;
function loadRisk() {
  const ids = ['rk-sharpe', 'rk-var', 'rk-down', 'rk-dd'];
  if (riskLoaded) return;
  ids.forEach(function (id) { const el = document.getElementById(id); if (el) el.textContent = '…'; });
  loadSlice('risk', '/holdings/risk').catch(function () { toast('风险指标计算失败'); });
  const sl = getSlice('risk');
  const finish = function () {
    const s = getSlice('risk');
    if (s.status !== 'success' || !s.data) {
      ids.forEach(function (id) { const el = document.getElementById(id); if (el) el.textContent = '—'; });
      return;
    }
    const d = s.data;
    document.getElementById('rk-sharpe').textContent = isNum(d.sharpe) ? d.sharpe.toFixed(2) : '—';
    document.getElementById('rk-var').textContent = isNum(d.var95_rate) ? (d.var95_rate * 100).toFixed(2) + '%' : '—';
    document.getElementById('rk-var').className = 'v down';
    document.getElementById('rk-down').textContent = isNum(d.downside_vol_rate) ? (d.downside_vol_rate * 100).toFixed(2) + '%' : '—';
    document.getElementById('rk-dd').textContent = isNum(d.max_drawdown_rate) ? (d.max_drawdown_rate * 100).toFixed(2) + '%' : '—';
    document.getElementById('rk-dd').className = 'v down';
    riskLoaded = true;
  };
  const t = setInterval(function () {
    if (getSlice('risk').status !== 'loading' && getSlice('risk').status !== 'idle') { clearInterval(t); finish(); }
  }, 300);
  setTimeout(function () { clearInterval(t); finish(); }, 35000);
}

/* ---------- R-UI-37 交互层：dialog / popover / toast ---------- */
let curCode = '';

function openPop(e, code) {
  e.stopPropagation();
  curCode = code;
  const p = document.getElementById('pop');
  p.innerHTML = '<button data-act="buy">加仓</button><button data-act="sell">减仓</button>'
    + '<button data-act="edit">编辑</button><button class="danger" data-act="delete">删除</button>';
  const r = e.target.getBoundingClientRect();
  p.style.left = Math.min(r.left, window.innerWidth - 160) + 'px';
  p.style.top = (r.bottom + 6) + 'px';
  p.classList.add('show');
  Array.prototype.forEach.call(p.querySelectorAll('[data-act]'), function (b) {
    b.addEventListener('click', function () {
      const act = b.dataset.act;
      p.classList.remove('show');
      if (act === 'buy' || act === 'sell') openAmt(act);
      else if (act === 'edit') openFund(code);
      else if (act === 'delete') delAsk(code);
    });
  });
}

document.addEventListener('click', function (e) {
  const pop = document.getElementById('pop');
  if (!pop) return;
  if (!e.target.closest('#pop') && !e.target.closest('#btn-colset') && !e.target.closest('[data-menu]')) {
    pop.classList.remove('show');
  }
});

let editing = null;
function openFund(code) {
  editing = code || '';
  const dlg = document.getElementById('dlg-fund');
  document.getElementById('fd-title').textContent = editing ? '编辑 ' + editing : '录入基金';
  document.getElementById('fd-sub').textContent = editing ? '' : '输入 6 位代码后自动回填名称';
  document.getElementById('fd-code').value = editing;
  document.getElementById('fd-code').readOnly = !!editing;
  ['fd-name', 'fd-shares', 'fd-cost', 'fd-amount'].forEach(function (id) { document.getElementById(id).value = ''; });
  document.getElementById('fd-group').value = 'domestic_index';
  document.getElementById('fd-tier').value = 'B';
  document.getElementById('fd-t').value = '1';
  if (editing) {
    const hp = getSlice('holdings');
    const row = hp.data && (hp.data.rows || []).find(function (r) { return r.code === editing; });
    if (row) {
      document.getElementById('fd-name').value = row.name;
      document.getElementById('fd-shares').value = row.shares;
      document.getElementById('fd-cost').value = row.cost_amount;
      document.getElementById('fd-group').value = row.group;
      document.getElementById('fd-tier').value = row.tier;
      document.getElementById('fd-t').value = String(row.confirm_days || 1);
    }
  }
  dlg.showModal();
}

function onCodeInput() {
  const code = document.getElementById('fd-code').value.trim();
  if (!/^\d{6}$/.test(code) || editing) return;
  get('/holdings/' + code).then(function (env) {
    if (env.data && !document.getElementById('fd-name').value) document.getElementById('fd-name').value = env.data.name || '';
  }).catch(function () { /* 新代码，保持可手填 */ });
}

function saveFund() {
  const code = document.getElementById('fd-code').value.trim();
  if (!/^\d{6}$/.test(code)) return toast('基金代码必须是 6 位数字');
  const name = document.getElementById('fd-name').value.trim();
  if (!name) return toast('请填写基金名称');
  const shares = parseFloat(document.getElementById('fd-shares').value);
  const amtVal = parseFloat(document.getElementById('fd-amount').value);
  const cost = parseFloat(document.getElementById('fd-cost').value);
  const body = {
    name: name,
    group: document.getElementById('fd-group').value,
    tier: document.getElementById('fd-tier').value,
    confirm_days: parseInt(document.getElementById('fd-t').value, 10) || 1
  };
  if (!Number.isNaN(shares)) body.shares = shares;
  if (!Number.isNaN(amtVal)) body.cost_amount = amtVal;
  if (!Number.isNaN(cost)) body.cost_amount = cost;
  if (body.shares == null && body.cost_amount == null) return toast('份额与成本金额至少填一项');
  const p = editing ? put('/holdings/' + editing, body) : post('/holdings', Object.assign({ code: code }, body));
  p.then(function () {
    toast(editing ? '已保存' : '已录入');
    close('dlg-fund');
    refresh();
  }).catch(function (e) { toast('保存失败：' + e.message); });
}

function openAmt(act) {
  document.getElementById('am-title').textContent = act === 'buy' ? '加仓' : '减仓';
  const row = currentRow();
  document.getElementById('am-sub').textContent = row ? row.name + ' · ' + row.code : '';
  document.getElementById('am-shares').value = '';
  document.getElementById('am-price').value = row && row.nav && isNum(row.nav.official_nav) ? row.nav.official_nav : '';
  document.getElementById('am-date').value = new Date().toISOString().slice(0, 10);
  document.getElementById('am-fee').value = '';
  document.getElementById('dlg-amt').dataset.tx = act;
  document.getElementById('dlg-amt').showModal();
}

function currentRow() {
  const hp = getSlice('holdings');
  return hp.data && (hp.data.rows || []).find(function (r) { return r.code === curCode; });
}

function saveAmt() {
  const act = document.getElementById('dlg-amt').dataset.tx || 'buy';
  const sh = parseFloat(document.getElementById('am-shares').value);
  const price = parseFloat(document.getElementById('am-price').value);
  const date = document.getElementById('am-date').value;
  const fee = parseFloat(document.getElementById('am-fee').value);
  if (Number.isNaN(sh) || sh <= 0) return toast('请输入有效份额');
  if (Number.isNaN(price) || price <= 0) return toast('请输入有效成交净值');
  if (!date) return toast('请选择交易确认日');
  post('/holdings/' + curCode + '/transactions', {
    tx_type: act, shares: sh, price: price, date: date,
    fee_amount: Number.isNaN(fee) ? 0 : fee
  }).then(function () {
    toast(act === 'buy' ? '已加仓' : '已减仓');
    close('dlg-amt');
    refresh();
  }).catch(function (e) { toast('操作失败：' + e.message); });
}

function delAsk(code) {
  curCode = code;
  const row = currentRow();
  document.getElementById('dl-sub').textContent = row ? row.name + ' · ' + row.code : code;
  document.getElementById('dlg-del').showModal();
}

function doDelete() {
  del('/holdings/' + curCode).then(function () {
    toast('已删除');
    close('dlg-del');
    refresh();
  }).catch(function (e) { toast('删除失败：' + e.message); });
}


