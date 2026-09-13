// ⑥ 引擎页 v3 —— R-UI-20/21/22/23/24/25/26/27（对齐 09-api-contract v9.1）
// R2：U-05 影子盘进度（x/60 · 滚动 60 日 · 回算口径（启动回填））+ history_days；U-01 对比卡走前 Δ；R-UI-24 基线口径入表；
//     枚举文案统一取 copy.js 字典（U-12），组件不硬编码。
import { loadSlice, get } from '../api.js';
import { getSlice, setSlice } from '../store.js';
import { mountState, hudCard, tag, progressBar, zbar, cubeSliceHTML, cubeLegendHTML, arenaColorVar, arenaClass, toast, esc, showModal } from '../components.js';
import { prob, rate, rateU, delta, num, int, isNum, lift as flift, timeHM, md } from '../format.js';
import { SHADOW_STATUS, SHADOW_AUDIT, ARCHIVE_FALLBACK_NOTE, METRIC_TIP, HISTORY_SUFFIX_MERGED, HISTORY_SUFFIX_MAIN, REGISTRY_PROVISIONAL_NOTE, SHADOW_WINDOW_NOTE, SHADOW_QUALIFIED_TEXT, SHADOW_AUDIT_NOTE } from '../copy.js';

let cubeLayer = 0;
let dimCode = null;
let pollTimer = null;

// 影子盘两套枚举各管一段，禁止混用同一张映射表（文案来源：copy.js）：
// · shadow_status = 记录进度（not_started/recording/qualified/gap）——「未启动/记录中/60 日回算覆盖达成/有缺口」；
// · shadow_audit_status = 偏差审查（idle/ok/bad）——idle 仅表示「样本尚不足以评偏差」，
//   绝不等于「影子盘未启动」；有台账记录时进度一律以 shadow_status 表达。
const PROGRESS_TAG = SHADOW_STATUS;
const AUDIT_TAG = SHADOW_AUDIT;

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
    // U-03：引擎页空态真实条件 = 心跳缺失且无快照（有快照走 success+陈旧，A-06 不倒退）
    loadSlice('engineStatus', '/engine/status', null, function (d) {
      return !!d && d.status === 'offline' && !d.last_heartbeat_at && !d.snapshot_as_of;
    }),
    loadSlice('shadow', '/ledger/shadow?limit=60'),
    loadSlice('arena', '/engine/arena'),
    loadSlice('training', '/engine/training-status'),
    loadSlice('frozen', '/engine/frozen-params'),
    loadSlice('registry', '/engine/registry')
  ]);
  // 深链直落引擎页时，持仓切片可能尚未加载 → 资产下拉/六维/立方体无 code；补拉一次（复用统一入口）。
  const hp = getSlice('holdings');
  if (!hp.data || !((hp.data.rows || []).length)) {
    await loadSlice('holdings', '/holdings?with=valuation,nav,prediction').catch(function () { });
  }
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
  if (sl.status !== 'success') {
    const d = sl.data || {};
    const facts = sl.status === 'empty' ? [
      ['最近成功', esc(d.last_success_at || '—')],
      ['服务端口', d.port ? '127.0.0.1:' + esc(d.port) : '—'],
      ['启动指引', 'python app.py'],
      ['下一步', '启动后本页自动刷新为只读面板']
    ] : null;
    mountState(mount, 'engine', sl, refresh, facts);
  } else { mount.className = 'state-block'; mount.innerHTML = ''; }
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

/* ---------- R-UI-20 HUD（U-05：进度真实化 + 归档口径 + history_days） ---------- */
function shadowProgressSlice() {
  const sl = getSlice('shadow');
  return (sl.status === 'success' && sl.data && sl.data.progress) ? sl.data.progress : null;
}

function renderHud() {
  const el = document.getElementById('eg-hud');
  const sl = getSlice('engineStatus');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '引擎无响应' : '正在连接本地引擎…') + '</div>'; return; }
  const d = sl.data;
  const live = d.status === 'online' || d.status === 'running';
  // 记录进度（shadow_status）与偏差审查（shadow_audit_status）分开表达：
  // 有记录时 HUD 必显示「记录中 N / 60」，不得因审查 idle 而回落「未启动」。
  const ptag = PROGRESS_TAG[d.shadow_status] || ['未启动', 'gray'];
  const atag = AUDIT_TAG[d.shadow_audit_status] || ['未评估', 'gray'];
  const cdays = int(d.shadow_consecutive_days);
  const tdays = int(d.shadow_target_days);
  const ratio = (isNum(d.shadow_consecutive_days) && isNum(d.shadow_target_days) && d.shadow_target_days > 0)
    ? d.shadow_consecutive_days / d.shadow_target_days : 0;
  const pstate = d.shadow_status === 'qualified' ? 'on' : (d.shadow_status === 'gap' ? 'bad' : 'warn');
  // U-05：口径注（v9.5：滚动 60 日 · 回算口径（启动回填）统一标注）+ 可用历史（history_days）
  // S5/R2-D4：history_days 后缀与 archive_merged 联动（含归档 / 主文件），不得与口径注自相矛盾
  const prg = shadowProgressSlice();
  const degradeNote = (prg && prg.archive_merged === false) ? ARCHIVE_FALLBACK_NOTE : '';
  const histNote = (prg && isNum(prg.history_days))
    ? '可用历史 ' + int(prg.history_days) + ' 日' + (prg.archive_merged ? HISTORY_SUFFIX_MERGED : HISTORY_SUFFIX_MAIN)
    : '';
  const subBits = [cdays + ' / ' + tdays + ' 日', SHADOW_WINDOW_NOTE, degradeNote, histNote].filter(Boolean);
  el.innerHTML = hudCard('影子盘', esc(ptag[0]), subBits.join(' · ')
    + progressBar(ratio, null, METRIC_TIP.progress_shadow)
    + '<div style="margin-top:5px">偏差审查 ' + tag(atag[0], atag[1]) + ' <span class="mini">' + esc(SHADOW_AUDIT_NOTE) + '</span></div>', pstate)
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
      + '<td>' + (isNum(r.t1_real) ? (r.t1_real > 0 ? tag('命中', 'ok') : tag('未命中', 'red')) : '<span class="mini">待回填</span>') + '</td>'
      + '<td class="mono mini">' + esc((r.created_at || r.written_at || '').slice(11, 16) || '—') + '</td></tr>';
  }).join('');
  const prg = document.getElementById('eg-prg');
  const prgTxt = document.getElementById('eg-prg-txt');
  if (prg && d.progress) {
    prg.innerHTML = progressBar(d.progress.progress_ratio, null, METRIC_TIP.progress_shadow);
    prgTxt.textContent = int(d.progress.consecutive_days) + ' / ' + int(d.progress.target_days) + ' 日';
  }
  // U-05：口径注（v9.5：滚动 60 日 · 回算口径（启动回填）统一标注）+ history_days + 字段直读
  const prgNote = document.getElementById('eg-prg-note');
  if (prgNote && d.progress) {
    const bits = [SHADOW_WINDOW_NOTE];
    if (d.progress.archive_merged === false) bits.push(ARCHIVE_FALLBACK_NOTE);
    if (d.progress.status === 'qualified') bits.push(SHADOW_QUALIFIED_TEXT);
    if (isNum(d.progress.history_days)) bits.push('可用历史 ' + int(d.progress.history_days) + ' 日'
      + (d.progress.archive_merged ? HISTORY_SUFFIX_MERGED : HISTORY_SUFFIX_MAIN));
    if (isNum(d.progress.window_days)) bits.push('滚动窗 ' + int(d.progress.window_days) + ' 日');
    if (d.progress.baseline_source) bits.push('基线口径 ' + esc(d.progress.baseline_source));
    prgNote.innerHTML = esc(bits.join(' · ')) + (d.progress.note ? '<br>' + esc(d.progress.note) : '');
  }
  const fields = document.getElementById('eg-ledger-fields');
  if (fields) fields.innerHTML = '字段：<span class="mono">' + esc((d.field_list || []).join(' / ')) + '</span><br>'
    + esc(d.insert_only_note || '')
    + (d.backfill_method_note ? '<br>' + esc(d.backfill_method_note) : (d.backfill_method ? '<br>回填口径：' + esc(d.backfill_method) : ''));
  const archive = document.getElementById('eg-ledger-archive');
  if (archive) {
    const at = d.archive_manifest_at ? ('最近归档 ' + esc(d.archive_manifest_at)) : '尚未归档';
    archive.innerHTML = '<b>归档策略 <code>' + esc(d.retention_policy || 'first_of_day_immutable_full_archive') + '</code></b>：'
      + (d.first_of_day_immutable ? '当日首次口径永久保留、不可改写；' : '')
      + '历史行全量归档、不删除；' + at + '。';
  }
}

/* ---------- R-UI-22 因子竞技场（A-09：只用后端 arena_color + --arena-*） ---------- */
function renderArena() {
  const head = document.getElementById('eg-arena-head');
  const tbody = document.getElementById('eg-arena');
  const legend = document.getElementById('eg-arena-legend');
  const note = document.getElementById('eg-arena-note');
  const sl = getSlice('arena');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = ''; head.innerHTML = ''; legend.innerHTML = ''; note.textContent = ''; return; }
  const d = sl.data;
  const prefix = d.color_token_prefix || '--arena-';
  head.innerHTML = '<tr><th>配置</th>' + (d.windows || []).map(function (w) { return '<th class="r">' + esc(w.window_label) + '</th>'; }).join('') + '</tr>';
  if (!(d.rows || []).length) tbody.innerHTML = '<tr><td colspan="7" class="mini">竞技场暂无配置</td></tr>';
  else tbody.innerHTML = d.rows.map(function (r) {
    const rowStyle = r.is_highlight ? ' style="background:rgba(24,32,25,.045)"' : '';
    const badge = r.is_highlight ? ' ' + tag('生产', 'ok') : (r.config_kind === 'naive_baseline' ? ' ' + tag('基准', 'gray') : (r.is_leave_one_out ? ' ' + tag('留一', 'gray') : ''));
    const cells = (r.cells || []).map(function (c) {
      const col = arenaColorVar(c.color, prefix);
      const marker = c.warning ? ' <span style="color:var(--arena-yellow)">▲</span>' : '';
      return '<td class="num"><span class="mono" style="color:var(--ink3);font-size:11px">' + int(c.open_count) + '</span> · '
        + '<b style="color:' + col + '">' + (isNum(c.hit_rate) ? (c.hit_rate * 100).toFixed(1) + '%' : '—') + '</b> '
        + '<span class="mini arena-cell ' + arenaClass(c.color) + '">' + (isNum(c.paired_delta_pp) ? delta(c.paired_delta_pp) : '—') + '</span>' + marker + '</td>';
    }).join('');
    return '<tr' + rowStyle + '><td class="mini">' + esc(r.config_name) + badge + '</td>' + cells + '</tr>';
  }).join('');
  legend.innerHTML = (d.legend || []).map(function (l) {
    return '<span><b class="arena-swatch ' + arenaClass(l.color) + '"></b>' + esc(l.label) + '</span>';
  }).join('') + '<span style="margin-left:auto">格内三个数 = 开口数 · 命中率 · 相对基线 Δ</span>';
  note.innerHTML = '<b>性能色板 <code>' + esc(d.color_scheme || 'performance_rank') + '</code>（独立于涨跌色，A-09）</b>'
    + (d.naive_method_note ? '<br>' + esc(d.naive_method_note) : '');
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

// 契约 §5.14 / §5.32 对 license_lines 元素给了两种形态，均兼容；只读展示，不重算。
function licenseName(l) {
  if (!l || typeof l !== 'object') return '—';
  if (l.license) return l.license;
  const keys = Object.keys(l).filter(function (k) { return k !== 'window_k'; });
  return keys.length ? keys[0] : '—';
}
function licenseDays(l) {
  if (!l || typeof l !== 'object') return '—';
  if (l.min_independent_days != null) return l.min_independent_days;
  if (l.threshold != null) return l.threshold;
  const name = licenseName(l);
  return l[name] != null ? l[name] : '—';
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
    ['准入度分母 N_w', (d.window_min_days || []).map(nwOf).join(' / ')],
    ['权重口径 weighting_basis', d.weighting_basis || '—'],
    ['基线口径 baseline_method', d.baseline_method || '—']
  ];
  (d.license_lines || []).forEach(function (l) {
    rows.push(['牌照线 · ' + licenseName(l), '≥' + licenseDays(l) + (l.window_k != null ? ' · k≥' + l.window_k : '')]);
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

/* ---------- R-UI-26 125 格立方体（A-07：ddsm 生产口径默认 / naive 研究口径折叠） ---------- */
function renderCube() {
  const layers = document.getElementById('eg-layers');
  const sl = getSlice('cube');
  if (layers) layers.innerHTML = [0, 1, 2, 3, 4].map(function (i) {
    return '<button data-lay="' + i + '" class="' + (i === cubeLayer ? 'on' : '') + '">vr ' + (i + 1) + '</button>';
  }).join('');
  const prodEl = document.getElementById('cube-prod');
  const resEl = document.getElementById('cube-research-grid');
  const lgEl = document.getElementById('eg-cube-legend');
  const modeEl = document.getElementById('eg-laymode');
  const dualEl = document.getElementById('cube-dualnote');
  if (sl.status !== 'success' || !sl.data) {
    if (lgEl) lgEl.innerHTML = cubeLegendHTML(null);
    const msg = '<div class="mini">' + (sl.status === 'error' ? '状态表不可读' : '立方体未训练') + '</div>';
    if (prodEl) prodEl.innerHTML = msg;
    if (resEl) resEl.innerHTML = '';
    if (modeEl) modeEl.innerHTML = '';
    if (dualEl) dualEl.innerHTML = '';
    return;
  }
  const d = sl.data;
  const prodLayer = d.production_layer || 'ddsm';
  const resLayer = d.research_layer || 'naive';
  const defaultLayer = d.default_layer || prodLayer;
  if (lgEl) lgEl.innerHTML = cubeLegendHTML(d.legend);
  if (modeEl) modeEl.innerHTML = tag('默认 ' + defaultLayer, 'blue') + tag('研究层折叠', 'gray');
  if (dualEl) dualEl.innerHTML = esc(d.dual_view_note || '生产口径 ddsm 默认展示；研究口径 naive 仅供审计，勿据此判结论。');
  const slice = (d.layers || []).find(function (l) { return l.vr_layer === cubeLayer; });
  const prodKey = prodLayer + '_p';
  if (prodEl) prodEl.innerHTML = cubeSliceHTML(slice, prodKey, d.legend);
  if (resEl) resEl.innerHTML = cubeSliceHTML(slice, resLayer + '_p', d.legend);
  const cmp = d.comparison || {};
  const prodCs = document.getElementById('cs-prod');
  const resCs = document.getElementById('cs-research');
  if (prodCs) prodCs.innerHTML = '生产口径 ' + prodLayer + '：' + int(cmp.empty_count_ddsm) + ' 格无样本 · P 极差 ' + num(cmp.p_range_ddsm, 2) + ' · 标准差 ' + num(cmp.p_std_ddsm, 3);
  if (resCs) resCs.innerHTML = '研究口径 ' + resLayer + '：' + int(cmp.empty_count_naive) + ' 格无样本 · P 极差 ' + num(cmp.p_range_naive, 2) + ' · 标准差 ' + num(cmp.p_std_naive, 3);
  const cmpEl = document.getElementById('eg-cmp');
  const cmpHtml = function (k, a, b, unit) {
    return '<div class="cmp-c"><div class="k">' + esc(k) + '</div><div class="v"><span style="color:var(--ink2)">' + a + '</span> → <span style="color:var(--down)">' + b + '</span>' + (unit || '') + '</div></div>';
  };
  cmpEl.innerHTML = cmpHtml('有效覆盖', rateU(cmp.valid_coverage_naive_pct), rateU(cmp.valid_coverage_ddsm_pct))
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
  // C2 裁定（§11.2）：注册表三态诚实标注降级——单版本现实 + 预留态（文案取 copy.js 字典）
  const noteEl = document.getElementById('eg-registry-note');
  if (noteEl) noteEl.textContent = REGISTRY_PROVISIONAL_NOTE;
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
