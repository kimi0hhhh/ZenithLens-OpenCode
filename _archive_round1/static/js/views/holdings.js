// ① 持仓页 —— R-UI-01/02/03/04/05/06
import { loadSlice, get, post, put, del } from '../api.js';
import { getSlice, setSlice, getState } from '../store.js';
import { mountState, valBadge, unknownCell, changeCell, pnlCell, tag, progressBar, forecastCard, toast, esc, statCard, showModal } from '../components.js';
import { amt, prob, rate, cls, isNum, shares as fShares, nav as fNav, int, md, FACTOR_WINDOW_LABEL } from '../format.js';
import { CONF_LABEL } from '../copy.js';

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
  mountState(root.querySelector('[data-slot]'), 'holdings', { status: 'loading' }, refresh);
  await Promise.allSettled([
    loadSlice('holdings', '/holdings?with=valuation,nav,prediction'),
    loadSlice('precision', '/valuations/precision'),
    loadSlice('portfolio', '/portfolio/forecast'),
    loadSlice('coverage', '/holdings/coverage'),
    loadSlice('predictions', '/predictions')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-holdings');
  const hp = getSlice('holdings');
  mountState(root.querySelector('[data-slot]'), 'holdings', hp, refresh);
  if (hp.status === 'success' || hp.status === 'empty') {
    root.dataset.state = 'success';
    renderOverview();
    renderVSum();
    renderForecast();
    renderCoverage();
    renderTable();
  } else {
    root.dataset.state = hp.status;
  }
}

/* ---------- R-UI-01 资产总览四卡 ---------- */
function renderOverview() {
  const hp = getSlice('holdings');
  const s = hp.data && hp.data.summary;
  const rows = (hp.data && hp.data.rows) || [];
  const covered = s ? s.covered_count : 0;
  const total = s ? s.total_count : rows.length;
  const fallback = s ? s.fallback_value : 0;
  const note = s && s.coverage_note ? s.coverage_note : '';
  document.getElementById('pa-total').innerHTML = s ? amt(s.total_value) : '—';
  document.getElementById('pa-today').innerHTML = s && isNum(s.today_pnl_amt)
    ? '<span class="' + cls(s.today_pnl_amt) + '">' + amt(s.today_pnl_amt) + '</span>' : '—';
  document.getElementById('pa-pnl').innerHTML = s
    ? '<span class="' + cls(s.total_pnl_amt) + '">' + amt(s.total_pnl_amt) + '</span>' : '—';
  document.getElementById('pa-ret').innerHTML = s && isNum(s.return_rate)
    ? '<span class="' + cls(s.return_rate) + '">' + rate(s.return_rate) + '</span>' : '—';
  const sub = document.getElementById('pa-today-sub');
  sub.innerHTML = esc(note || '') + (isNum(fallback) && fallback > 0
    ? ' · <span class="cov-warn">未知行按成本计 ' + amt(fallback) + '</span>' : '')
    + ' · 覆盖 ' + covered + '/' + total + ' 只';
}

/* ---------- R-UI-02 估值精度汇总条 ---------- */
function renderVSum() {
  const el = document.getElementById('val-sum');
  const sl = getSlice('precision');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<span class="mini">' + (sl.status === 'error' ? '估值精度读取失败' : '—') + '</span>';
    return;
  }
  const d = sl.data;
  const chips = (d.groups || []).map(function (g) {
    const clsMap = { high: 'ch', mid: 'cm', low: 'cl', unknown: 'cu' };
    return '<span class="chip"><span class="vb ' + (clsMap[g.confidence] || 'cu') + '" style="margin-right:5px">' + esc(g.label || CONF_LABEL[g.confidence] || g.confidence) + '</span>'
      + int(g.count) + ' 只 · ' + amt(g.market_value) + ' · 占 ' + (isNum(g.weight_ratio) ? (g.weight_ratio * 100).toFixed(1) + '%' : '—') + '</span>';
  }).join('');
  const modeChips = (d.mode_distribution || []).map(function (m) {
    return '<span class="chip">' + esc(m.mode_label) + ' ' + int(m.count) + ' 只</span>';
  }).join('');
  const base = isNum(d.industry_baseline_mae_rate) ? d.industry_baseline_mae_rate : 0.008;
  const wmae = d.weighted_mae_rate;
  el.innerHTML = chips + modeChips
    + (isNum(wmae) ? '<span class="chip">市值加权平均误差 <b style="color:' + (wmae <= base ? 'var(--down)' : 'var(--gold)') + '">'
      + (wmae * 100).toFixed(2) + '%</b> ／ 行业基准 ' + (base * 100).toFixed(2) + '%</span>' : '')
    + '<span class="chip" style="border-style:dashed">口径：近 ' + int(d.window_days) + ' 个交易日回测 · 估算涨跌 vs 官方净值涨跌</span>';
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
  if (note) note.innerHTML = '<b>开口 ' + int(win.open_count) + ' 只，覆盖市值 ' + amt(win.coverage_value) + '，仅占组合 '
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
  if (note) note.innerHTML = esc(d.invalidation_note || '')
    + '<br><b style="color:var(--down)">原理无解：' + int(d.no_solution_count) + ' 只。</b>';
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
    const list = groups[g].slice().sort(function (a, b) { return (b.market_value || 0) - (a.market_value || 0); });
    const mv = list.reduce(function (s, r) { return s + (r.market_value || 0); }, 0);
    html += '<tr class="grp" data-g="' + esc(g) + '"><td colspan="11"><span class="caret">▼</span>' + esc(g) + ' · ' + list.length + ' 只 · ' + amt(mv) + '</td></tr>';
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
  return '<tr data-g="' + esc(g) + '">'
    + '<td><div class="fname">' + esc(r.name) + (r.confirm_days === 2 ? '<span class="tag warn" style="margin-left:5px">T+2</span>' : (r.confirm_days === 3 ? '<span class="tag warn" style="margin-left:5px">T+3</span>' : ''))
    + '</div><div class="fcode">' + esc(r.code) + ' · ' + esc(r.tier) + ' ' + esc(r.proxy_name || r.proxy_code || '') + '</div></td>'
    + '<td class="num amt' + (mv == null ? ' unk' : '') + '">' + (mv == null ? '—' : amt(mv)) + (r.mv_source === null && r.fallback_value ? '<div class="fcode">成本 ' + amt(r.fallback_value) + '</div>' : '') + '</td>'
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
    if (r.tier === 'C') return tag('待验证', 'warn', 'C 档待过六关，仅供参考');
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


