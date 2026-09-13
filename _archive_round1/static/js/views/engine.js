// ⑥ 引擎页 —— R-UI-20/21/22/23/24/25/26/27
import { loadSlice, get } from '../api.js';
import { getSlice, setSlice } from '../store.js';
import { mountState, hudCard, tag, progressBar, zbar, cubeSliceHTML, cubeLegendHTML, toast, esc, showModal } from '../components.js';
import { prob, rate, delta, num, int, isNum, lift as flift, timeHM, md } from '../format.js';

let cubeLayer = 0;
let dimCode = null;
let pollTimer = null;

const PROGRESS_TAG = { not_started: ['未启动', 'gray'], recording: ['记录中', 'warn'], qualified: ['已达标', 'ok'], gap: ['中断', 'red'] };

export function init() {
  const sel = document.getElementById('dim-asset');
  if (sel) sel.addEventListener('change', function () {
    dimCode = sel.value;
    loadInputs();
    loadCube();
  });
  const layers = document.getElementById('eg-layers');
  if (layers) layers.addEventListener('click', function (e) {
    const b = e.target.closest('button[data-lay]');
    if (b) { cubeLayer = parseInt(b.dataset.lay, 10); renderCube(); }
  });
}

export async function activate() {
  render();
  await refresh();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(function () {
    if (getState$('engineStatus').status === 'loading') return;
    loadSlice('engineStatus', '/engine/status').then(renderHud).catch(function () { });
  }, 12000);
}

export function deactivate() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

function getState$(n) { return getSlice(n); }

export async function refresh() {
  await Promise.allSettled([
    loadSlice('engineStatus', '/engine/status'),
    loadSlice('shadow', '/ledger/shadow?limit=60'),
    loadSlice('arena', '/engine/arena'),
    loadSlice('training', '/engine/training-status'),
    loadSlice('frozen', '/engine/frozen-params'),
    loadSlice('registry', '/engine/registry')
  ]);
  ensureDimOptions();
  loadInputs();
  loadCube();
  render();
}

function ensureDimOptions() {
  const sel = document.getElementById('dim-asset');
  if (!sel || sel.options.length) return;
  const hp = getSlice('holdings');
  let rows = (hp.data && hp.data.rows) || [];
  if (!rows.length) return;
  rows = rows.filter(function (r) { return r.tier === 'A' || r.tier === 'B'; });
  if (!rows.length) rows = (hp.data.rows || []);
  sel.innerHTML = rows.map(function (r) { return '<option value="' + esc(r.code) + '">' + esc(r.code) + ' · ' + esc(r.name) + '</option>'; }).join('');
  dimCode = rows[0].code;
}

async function loadInputs() {
  if (!dimCode) { setSlice('engineInputs', { status: 'empty', data: null }); renderDims(); return; }
  try { await loadSlice('engineInputs', '/engine/inputs?code=' + encodeURIComponent(dimCode)); }
  catch (e) { /* keep error slice */ }
  renderDims();
}

async function loadCube() {
  if (!dimCode) { setSlice('cube', { status: 'empty', data: null }); renderCube(); return; }
  try { await loadSlice('cube', '/engine/ddsm/cube?code=' + encodeURIComponent(dimCode)); }
  catch (e) { /* keep error slice */ }
  renderCube();
}

export function render() {
  const root = document.getElementById('view-engine');
  const sl = getSlice('engineStatus');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'engine', sl, refresh);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
  renderHud();
  renderShadow();
  renderArena();
  renderTraining();
  renderFrozen();
  renderDims();
  renderCube();
  renderRegistry();
}

/* ---------- R-UI-20 HUD ---------- */
function renderHud() {
  const el = document.getElementById('eg-hud');
  const sl = getSlice('engineStatus');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '引擎无响应' : '正在连接本地引擎…') + '</div>'; return; }
  const d = sl.data;
  const live = d.status === 'online' || d.status === 'running';
  const ptag = PROGRESS_TAG[d.shadow_status] || ['—', 'gray'];
  el.innerHTML = hudCard('影子盘', ptag[0], int(d.shadow_consecutive_days) + ' / ' + int(d.shadow_target_days) + ' 日', d.shadow_status === 'ok' ? 'on' : (d.shadow_status === 'bad' ? 'bad' : 'warn'))
    + hudCard('引擎版本', esc(d.active_engine_version || d.version || '—'), live ? '在线' : '离线', live ? 'on' : 'bad')
    + hudCard('训练资产', int(d.training_assets), '仅作特征 ' + int(d.index_only_assets) + ' 只', '')
    + hudCard('状态格覆盖', (isNum(d.state_grid_coverage_pct) ? (d.state_grid_coverage_pct * 100).toFixed(1) + '%' : '—'),
      int(d.state_grid_filled_cells) + ' / ' + int(d.state_grid_total_cells) + ' 有样本', isNum(d.state_grid_coverage_pct) && d.state_grid_coverage_pct >= 0.8 ? 'on' : 'warn')
    + hudCard('上次重训', esc(d.last_retrain_at || '—'), d.next_retrain_at ? '下次 ' + esc(d.next_retrain_at) : '', 'warn')
    + hudCard('数据新鲜度', (d.data_freshness_days_behind != null ? '滞后 ' + int(d.data_freshness_days_behind) + ' 日' : '—'),
      esc(d.data_freshness_snapshot_date || ''), 'warn');
}

/* ---------- R-UI-21 影子盘台账 ---------- */
function renderShadow() {
  const el = document.getElementById('eg-ledger');
  const tbody = document.getElementById('eg-ledger-rows');
  const sl = getSlice('shadow');
  const stateEl = document.getElementById('eg-ledger-state');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '台账不可读' : '—') + '</div>';
    tbody.innerHTML = '';
    return;
  }
  const d = sl.data;
  const s = d.summary || {};
  stateEl.innerHTML = d.progress ? tag((PROGRESS_TAG[d.progress.status] || ['—'])[0], (PROGRESS_TAG[d.progress.status] || ['', 'gray'])[1])
    + ' <span class="mini">' + esc(d.progress.note || '') + '</span>' : '';
  el.innerHTML = '<div class="hud" style="margin:0">'
    + hudCard('总记录', int(s.total_records), 'INSERT-ONLY')
    + hudCard('开口信号', int(s.open_signals), '输出「涨」', 'on')
    + hudCard('否决弃权', int(s.veto_abstains), '否决层拦下', '')
    + hudCard('已回填', int(s.backfilled_count), 'T+1 到期回填', '')
    + hudCard('命中率', isNum(s.hit_rate) ? (s.hit_rate * 100).toFixed(1) + '%' : '—', '基准 ' + (isNum(s.baseline_rate) ? (s.baseline_rate * 100).toFixed(1) + '%' : '—'), isNum(s.hit_rate) && isNum(s.baseline_rate) && s.hit_rate >= s.baseline_rate ? 'on' : 'warn')
    + '</div>';
  tbody.innerHTML = (d.rows || []).map(function (r) {
    return '<tr><td class="mono">' + esc(r.date) + '</td><td class="mono">' + esc(r.code) + '</td><td class="mini">' + esc(r.gate) + '</td>'
      + '<td class="num">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</td>'
      + '<td class="mono mini">' + esc((r.ddsm_state || []).join(',')) + '</td>'
      + '<td>' + (r.veto_crowd ? tag('亮', 'warn') : '<span class="mini">—</span>') + '</td>'
      + '<td>' + (r.veto_klow2 ? tag('亮', 'warn') : '<span class="mini">—</span>') + '</td>'
      + '<td>' + (r.signal === 'up' ? tag('涨', 'red') : tag('弃权', 'gray')) + '</td>'
      + '<td class="num">' + (isNum(r.t1_real) ? rate(r.t1_real) : '—') + '</td>'
      + '<td>' + (isNum(r.t1_real) ? (r.t1_real > 0 ? tag('命中', 'ok') : tag('未命中', 'red')) : '<span class="mini">待回填</span>') + '</td></tr>';
  }).join('');
  const prg = document.getElementById('eg-prg');
  const prgTxt = document.getElementById('eg-prg-txt');
  if (prg && d.progress) {
    prg.innerHTML = progressBar(d.progress.progress_ratio);
    prgTxt.textContent = int(d.progress.consecutive_days) + ' / ' + int(d.progress.target_days) + ' 日';
  }
  const fields = document.getElementById('eg-ledger-fields');
  if (fields) fields.innerHTML = '字段：<span class="mono">' + esc((d.field_list || []).join(' / ')) + '</span><br>'
    + esc(d.insert_only_note || '');
}

/* ---------- R-UI-22 因子竞技场 ---------- */
const ARENA_CELL_COLOR = { red: 'var(--up)', green: 'var(--down)', blue: 'var(--ink2)', yellow: 'var(--gold)', base: 'var(--ink3)' };
function renderArena() {
  const head = document.getElementById('eg-arena-head');
  const tbody = document.getElementById('eg-arena');
  const legend = document.getElementById('eg-arena-legend');
  const note = document.getElementById('eg-arena-note');
  const sl = getSlice('arena');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = ''; head.innerHTML = ''; return; }
  const d = sl.data;
  head.innerHTML = '<tr><th>配置</th>' + (d.windows || []).map(function (w) { return '<th class="r">' + esc(w.window_label) + '</th>'; }).join('') + '</tr>';
  if (!(d.rows || []).length) tbody.innerHTML = '<tr><td colspan="7" class="mini">竞技场暂无配置</td></tr>';
  else tbody.innerHTML = d.rows.map(function (r) {
    const rowStyle = r.is_highlight ? ' style="background:rgba(24,32,25,.045)"' : '';
    const badge = r.is_highlight ? ' ' + tag('生产', 'ok') : (r.config_kind === 'naive_baseline' ? ' ' + tag('基准', 'gray') : (r.is_leave_one_out ? ' ' + tag('留一', 'gray') : ''));
    const cells = (r.cells || []).map(function (c) {
      const col = ARENA_CELL_COLOR[c.color] || 'var(--ink2)';
      const marker = c.warning ? ' <span style="color:var(--gold)">▲</span>' : '';
      return '<td class="num"><span class="mono" style="color:var(--ink3);font-size:11px">' + int(c.open_count) + '</span> · '
        + '<b style="color:' + col + '">' + (isNum(c.hit_rate) ? (c.hit_rate * 100).toFixed(1) + '%' : '—') + '</b> '
        + '<span class="mini" style="color:' + col + '">' + (isNum(c.paired_delta_pp) ? delta(c.paired_delta_pp) : '—') + '</span>' + marker + '</td>';
    }).join('');
    return '<tr' + rowStyle + '><td class="mini">' + esc(r.config_name) + badge + '</td>' + cells + '</tr>';
  }).join('');
  legend.innerHTML = (d.legend || []).map(function (l) {
    return '<span><b style="color:' + (ARENA_CELL_COLOR[l.color] || 'var(--ink2)') + '">■</b> ' + esc(l.label) + '</span>';
  }).join('') + '<span style="margin-left:auto">格内三个数 = 开口数 · 命中率 · 相对基线 Δ</span>';
  note.textContent = d.naive_method_note || '';
}

/* ---------- R-UI-23 训练状态 ---------- */
function renderTraining() {
  const el = document.getElementById('eg-train');
  const sl = getSlice('training');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '训练状态不可读' : '—') + '</div>'; return; }
  const d = sl.data;
  el.innerHTML = '<div class="hud" style="margin:0">'
    + hudCard('状态格总数', int(d.total_cells), '5 × 5 × 5')
    + hudCard('有样本格', int(d.filled_cells), isNum(d.coverage_pct) ? (d.coverage_pct * 100).toFixed(1) + '%' : '—', 'on')
    + hudCard('平均样本/格', num(d.avg_samples_per_cell, 1), '加噪后 ×' + int((d.noise || {}).k_noise), '')
    + hudCard('最少样本格', int(d.min_samples_cell), '低于 MIN_N=' + int(d.min_n) + ' 强收缩', 'warn')
    + '</div>'
    + '<div class="mini" style="margin-top:12px;line-height:1.9"><b>训练方式：</b>' + esc(d.train_mode || '') + '<br>'
    + '<b>加噪增强：</b>' + esc(d.noise_text || '') + '<br>'
    + '<b style="color:var(--gold)">已证伪的死路（勿重试）：</b>' + esc((d.dead_ends || []).join('、')) + '</div>';
}

/* ---------- R-UI-24 冻结参数 ---------- */
// 契约 §5.14 window_min_days 冻结结构 [{window,n_w}]；兼容历史 {d15:5,...} 首键形态
function nwOf(w) {
  if (w && isNum(w.n_w)) return w.n_w;
  if (w && typeof w === 'object') {
    const keys = Object.keys(w);
    if (keys.length) return w[keys[0]];
  }
  return '—';
}

function renderFrozen() {
  const el = document.getElementById('eg-frozen');
  const sl = getSlice('frozen');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '冻结参数不可读' : '—') + '</div>'; return; }
  const d = sl.data;
  const rows = [
    ['加噪 K / p', d.k_noise + ' / ' + num(d.p_perturb, 2)],
    ['MIN_N / SHRINK / BAND', d.min_n + ' / ' + d.shrink + ' / ' + num(d.band, 2)],
    ['双否决阈值', '拥挤 ' + num(d.veto_crowd_quantile, 2) + ' / KLOW2 ' + num(d.veto_klow2_quantile, 2)],
    ['最小覆盖门槛', '覆盖 ≥' + num(d.min_coverage_ratio, 2) + ' · 开口 ≥' + int(d.min_open_count)],
    ['E1 跳空', d.gate_e1 || '—'],
    ['E3 无量急跌', d.gate_e3 || '—'],
    ['purge gap', d.purge_gap || '—'],
    ['窗权重', (d.window_weights || []).map(function (w) { return w.weight; }).join(' / ')],
    ['准入度分母 N_w', (d.window_min_days || []).map(nwOf).join(' / ')]
  ];
  (d.license_lines || []).forEach(function (l) {
    rows.push(['牌照线 · ' + l.license, '≥' + l.min_independent_days + (l.window_k != null ? ' · k≥' + l.window_k : '')]);
  });
  el.innerHTML = rows.map(function (p) {
    return '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:7px 0;border-bottom:1px solid rgba(24,32,25,.04);font-size:12px">'
      + '<span style="color:var(--ink2)">' + esc(p[0]) + '</span><span class="mono">' + esc(String(p[1])) + '</span></div>';
  }).join('') + '<div class="mini" style="margin-top:8px;color:var(--gold)">' + esc(d.change_policy || '改任何一项必须重走六关') + '</div>';
}

/* ---------- R-UI-25 六维输入 ---------- */
function renderDims() {
  const el3 = document.getElementById('dim-d3');
  const el6 = document.getElementById('dim-d6');
  const sum = document.getElementById('dim-sum');
  const sl = getSlice('engineInputs');
  if (sl.status !== 'success' || !sl.data) {
    el3.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '特征不可读' : '暂无特征快照') + '</div>';
    el6.innerHTML = ''; sum.textContent = ''; return;
  }
  const d = sl.data;
  const row = function (x) {
    const icText = x.ic_sign === '+' ? 'IC +' : (x.ic_sign === '-' ? 'IC −' : 'IC 0');
    return '<div class="dim"><div><div class="dn">' + esc(x.label || x.feature) + '</div><div class="df">' + esc(x.formula || icText) + '</div></div>'
      + zbar(x.z, x.level)
      + '<div style="text-align:right"><span class="mono">' + (isNum(x.raw) ? num(x.raw, 4) : '—') + ' ' + esc(x.raw_unit || '') + '</span>'
      + '<div class="df">z ' + (isNum(x.z) ? (x.z >= 0 ? '+' : '') + x.z.toFixed(2) : '—') + ' · 档 ' + (x.level == null ? '—' : x.level) + '</div></div></div>';
  };
  el3.innerHTML = (d.ddsm_3d || []).map(row).join('') || '<div class="mini">—</div>';
  el6.innerHTML = (d.crowd_6d || []).map(row).join('') || '<div class="mini">—</div>';
  const c = d.crowd;
  if (c) {
    sum.innerHTML = '复合拥挤度 <span class="mono" style="color:' + (c.is_veto ? 'var(--gold)' : 'var(--down)') + '">z=' + (isNum(c.composite_z) ? (c.composite_z >= 0 ? '+' : '') + c.composite_z.toFixed(2) : '—') + '</span>'
      + ' 分位 ' + int(c.quantile_level) + '/5 ' + (c.is_veto ? tag('最挤 · 否决', 'warn') : tag('未亮灯', 'ok'))
      + ' · KLOW2 <span class="mono">' + (isNum(c.klow2) ? num(c.klow2, 4) : '—') + '</span> 分位 ' + (c.klow2_level == null ? '—' : int(c.klow2_level)) + '/5 '
      + (c.klow2_is_veto ? tag('最不利 · 否决', 'warn') : tag('未亮灯', 'ok'));
  } else sum.textContent = '';
}

/* ---------- R-UI-26 125 格立方体 ---------- */
function renderCube() {
  const layers = document.getElementById('eg-layers');
  const sl = getSlice('cube');
  if (layers) layers.innerHTML = [0, 1, 2, 3, 4].map(function (i) {
    return '<button data-lay="' + i + '" class="' + (i === cubeLayer ? 'on' : '') + '">vr ' + (i + 1) + '</button>';
  }).join('');
  const sl2 = sl;
  const lgEl = document.getElementById('eg-cube-legend');
  if (sl2.status !== 'success' || !sl2.data) {
    if (lgEl) lgEl.innerHTML = cubeLegendHTML(null);
    document.getElementById('cube-naive').innerHTML = '<div class="mini">' + (sl2.status === 'error' ? '状态表不可读' : '立方体未训练') + '</div>';
    document.getElementById('cube-deno').innerHTML = '';
    return;
  }
  const d = sl2.data;
  if (lgEl) lgEl.innerHTML = cubeLegendHTML(d.legend);
  const slice = (d.layers || []).find(function (l) { return l.vr_layer === cubeLayer; });
  document.getElementById('cube-naive').innerHTML = cubeSliceHTML(slice, 'naive_p', d.legend);
  document.getElementById('cube-deno').innerHTML = cubeSliceHTML(slice, 'ddsm_p', d.legend);
  const cmp = d.comparison || {};
  document.getElementById('cs-naive').innerHTML = int(cmp.empty_count_naive) + ' 格无样本 · P 极差 ' + num(cmp.p_range_naive, 2) + ' · 标准差 ' + num(cmp.p_std_naive, 3);
  document.getElementById('cs-deno').innerHTML = 'DDSM ' + int(cmp.empty_count_ddsm) + ' 格无样本 · P 极差 ' + num(cmp.p_range_ddsm, 2) + ' · 标准差 ' + num(cmp.p_std_ddsm, 3);
  const cmpEl = document.getElementById('eg-cmp');
  const cmpHtml = function (k, a, b, unit) {
    return '<div class="cmp-c"><div class="k">' + esc(k) + '</div><div class="v"><span style="color:var(--ink2)">' + a + '</span> → <span style="color:var(--down)">' + b + '</span>' + (unit || '') + '</div></div>';
  };
  cmpEl.innerHTML = cmpHtml('有效覆盖', (num(cmp.valid_coverage_naive_pct, 1)) + '%', (num(cmp.valid_coverage_ddsm_pct, 1)) + '%')
    + cmpHtml('P 标准差', num(cmp.p_std_naive, 3), num(cmp.p_std_ddsm, 3))
    + cmpHtml('极端格数', int(cmp.extreme_count_naive), int(cmp.extreme_count_ddsm), ' 格')
    + cmpHtml('走前 Δ', isNum(cmp.walk_forward_delta_naive_pp) ? delta(cmp.walk_forward_delta_naive_pp) : '待复现',
      isNum(cmp.walk_forward_delta_ddsm_pp) ? delta(cmp.walk_forward_delta_ddsm_pp) : '待复现');
  const note = document.getElementById('cube-note');
  if (note) note.innerHTML = esc(cmp.note || '');
}

/* ---------- R-UI-27 引擎注册表 ---------- */
function renderRegistry() {
  const tbody = document.getElementById('eg-registry');
  const sl = getSlice('registry');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="3" class="mini">' + (sl.status === 'error' ? '注册表读取失败' : '—') + '</td></tr>'; return; }
  const rows = sl.data.engines || [];
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="3" class="mini">尚无注册版本</td></tr>'; return; }
  tbody.innerHTML = rows.map(function (r) {
    const t = r.status === 'active' ? tag('active', 'ok') : tag(r.status, 'gray');
    return '<tr><td class="mono">' + esc(r.version) + '</td><td>' + t + (r.can_rollback ? ' ' + tag('可回滚', 'blue') : '') + '</td>'
      + '<td class="mini">' + esc(r.note || '') + (r.metrics ? ' · 命中率 ' + prob(r.metrics.hit_rate) + ' / 基线 ' + prob(r.metrics.baseline_rate) + ' / Δ ' + delta(r.metrics.delta_pp) : '') + '</td></tr>';
  }).join('');
}
