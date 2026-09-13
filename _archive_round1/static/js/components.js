// 极境 ZenithLens · UI 基础组件（四态 / 命脉组件 / 通用件）
import { amt, prob, rate, cls, isNum, timeHM, dateTimeShort } from './format.js';
import { STATE_COPY, errorText, DIRECTION_REASON } from './copy.js';

export function esc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function h(tag, attrs, html) {
  const a = attrs ? ' ' + Object.keys(attrs).map(function (k) {
    return k + '="' + esc(attrs[k]) + '"';
  }).join(' ') : '';
  return '<' + tag + a + '>' + (html == null ? '' : html) + '</' + tag + '>';
}

/* ---------------- R-UI-40 · 四态容器 ---------------- */
export function mountState(container, view, slice, onRetry, factRows) {
  if (!container) return;
  if (slice.status === 'success') {
    container.className = 'state-block';
    container.innerHTML = '';
    return;
  }
  const copy = (STATE_COPY[view] || STATE_COPY.holdings);
  const c = copy[slice.status] || copy.error;
  if (slice.status === 'empty') {
    const facts = (factRows || []).map(function (f) {
      return '<div class="fact"><div class="k">' + esc(f[0]) + '</div><div class="v">' + f[1] + '</div></div>';
    }).join('');
    container.className = 'state-block empty';
    container.innerHTML = '<div class="inner"><div class="big">' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(c.sub) + '</div>'
      + (facts ? '<div class="facts">' + facts + '</div>' : '')
      + (typeof onRetry === 'function' && view === 'holdings' ? '<button class="sbtn" data-retry>录入第一只基金</button>' : '')
      + '</div>';
  } else if (slice.status === 'loading') {
    container.className = 'state-block loading';
    container.innerHTML = '<div class="inner"><div class="big"><span class="pulse"></span>' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(c.sub) + '</div>'
      + '<div style="max-width:520px;margin:0 auto">' + '<div class="skeleton"></div>'.repeat(4) + '</div></div>';
  } else {
    container.className = 'state-block ' + (slice.status === 'idle' ? 'loading' : 'error');
    container.innerHTML = '<div class="inner"><div class="big">' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(errorText(slice.error || c.sub)) + '</div>'
      + '<button class="sbtn" data-retry>重试</button></div>';
  }
  const btn = container.querySelector('[data-retry]');
  if (btn) btn.addEventListener('click', function () {
    if (view === 'holdings' && slice.status === 'empty') {
      if (typeof onRetry === 'function') onRetry('empty');
      return;
    }
    if (typeof onRetry === 'function') onRetry();
  });
}

export function staleBanner(as_of) {
  return '<div class="stalebar">引擎未运行，展示 ' + esc(as_of || '历史') + ' 快照</div>';
}

/* ---------------- R-UI-03 · 估值来源徽章（命脉） ---------------- */
const MODE_LABEL = { official: '官方净值', intraday: '盘中估算', holdings: '重仓加权', proxy: '代理近似', unknown: '未知' };
const CONF_CLASS = { high: 'ch', mid: 'cm', low: 'cl', unknown: 'cu' };

export function valBadge(v, opts) {
  if (!v) return '<span class="vb cu" title="无估值记录">未知</span>';
  const label = v.mode_label || MODE_LABEL[v.valuation_mode] || '未知';
  const cc = v.confidence_color_class || CONF_CLASS[v.confidence] || 'cu';
  const tip = [];
  if (v.source_label) tip.push(v.source_label);
  if (v.trace_text) tip.push('降级链路：' + v.trace_text);
  if (isNum(v.mae_rate)) {
    const base = isNum(v.industry_baseline_mae_rate) ? v.industry_baseline_mae_rate : 0.008;
    tip.push('历史平均误差 MAE ' + (v.mae_rate * 100).toFixed(2) + '%（行业基准 ' + (base * 100).toFixed(2) + '%）');
  }
  if (isNum(v.dir_hit_rate)) {
    tip.push('方向命中率 ' + (v.dir_hit_rate * 100).toFixed(1) + '%' + (isNum(v.n_test) ? '，样本 ' + v.n_test + ' 个交易日' : ''));
  }
  if (v.valuation_mode === 'unknown') tip.push('净值截止日：' + (v.nav_date || '未知') + ' · 今日无可信估值');
  else if (v.nav_date) tip.push('净值截止日 ' + v.nav_date);
  if (v.written_at) tip.push('入账 ' + dateTimeShort(v.written_at));
  const code = (opts && opts.code) || '';
  return '<span class="vb ' + cc + '" title="' + esc(tip.join('\n')) + '"'
    + (code ? ' data-vb-code="' + esc(code) + '"' : '') + '>' + esc(label) + '</span>';
}

/* ---------------- R-UI-05 · 未知态（命脉） ---------------- */
export function unknownCell() { return '<span class="unk">未知</span>'; }

// 涨跌单元格：null -> 「未知」；0 -> +0.00%
export function changeCell(rateVal) {
  if (!isNum(rateVal)) return unknownCell();
  return '<span class="' + cls(rateVal) + '">' + rate(rateVal) + '</span>';
}

// 今日盈亏：null -> —
export function pnlCell(v) {
  if (!isNum(v)) return '<span class="unk">—</span>';
  return '<span class="' + cls(v) + '">' + amt(v) + '</span>';
}

/* ---------------- 通用：状态标签 / 进度条 / z-bar ---------------- */
export function tag(text, kind, title) {
  return '<span class="tag ' + (kind || 'gray') + '"' + (title ? ' title="' + esc(title) + '"' : '') + '>' + esc(text) + '</span>';
}

export function progressBar(ratio, color) {
  const w = Math.max(0, Math.min(100, (isNum(ratio) ? ratio : 0) * 100));
  return '<div class="prg"><i style="width:' + w.toFixed(1) + '%;' + (color ? 'background:' + color : '') + '"></i></div>';
}

// R-UI-25 z-bar：中轴 + 填充 + 档位指针
export function zbar(z, level) {
  const zz = isNum(z) ? z : 0;
  const w = Math.min(50, Math.abs(zz) / 2.2 * 50);
  const fill = zz >= 0
    ? '<div class="fill pos" style="left:50%;width:' + w + '%"></div>'
    : '<div class="fill neg" style="right:50%;width:' + w + '%"></div>';
  const bz = isNum(z) ? '<div class="bz" style="left:calc(' + (50 + zz / 2.2 * 50) + '% - 1px)"></div>' : '';
  return '<div class="zbar" title="z=' + (isNum(z) ? z.toFixed(3) : '—') + ' · 档 ' + (level == null ? '—' : level) + '">'
    + '<div class="mid"></div>' + fill + bz + '</div>';
}

/* ---------------- R-UI-13 · 六步推导链 ---------------- */
export function chainHTML(steps) {
  if (!steps || !steps.length) return '<div class="mini">无链路数据</div>';
  const items = steps.map(function (s) {
    const on = s.status === 'on';
    const off = s.status === 'off';
    const miss = s.status === 'missing';
    const k = 'chain-item' + (on && s.key !== 'veto_crowd' && s.key !== 'veto_klow2' ? ' on' : (off ? ' off' : ''));
    const tagCls = miss ? 'gray' : (on ? 'red' : 'ok');
    const metrics = s.metrics && Object.keys(s.metrics).length
      ? '<span class="cd">' + esc(JSON.stringify(s.metrics)) + '</span>' : '';
    return '<div class="' + k + '"><div class="ct"><span class="tag ' + tagCls + '">' + esc(s.title || ('第' + s.step + '步')) + '</span>'
      + (miss ? '<span class="tag gray">数据缺失</span>' : '') + '</div>'
      + '<div class="cd">' + esc(s.detail || '') + '</div>' + metrics + '</div>';
  }).join('');
  return '<div class="chain">' + items + '</div>';
}

export function showModal(title, html) {
  let m = document.getElementById('zl-modal');
  if (!m) {
    m = document.createElement('div');
    m.id = 'zl-modal';
    m.className = 'modal-mask';
    document.body.appendChild(m);
  }
  m.innerHTML = '<div class="dlg"><h3>' + esc(title) + '</h3><div class="mini" style="line-height:1.8">' + (html || '')
    + '</div><div class="dlg-acts"><button class="btn" data-close>关闭</button></div></div>';
  m.classList.add('show');
  m.querySelector('[data-close]').addEventListener('click', function () { m.classList.remove('show'); });
  m.addEventListener('click', function (e) { if (e.target === m) m.classList.remove('show'); });
}

export function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._tt);
  toast._tt = setTimeout(function () { t.classList.remove('show'); }, 2200);
}

/* ---------------- R-UI-26 · 125 格立方体切片 ---------------- */
// 阈值/标签由后端 legend 提供（§5.34）；仅配色为前端设计 token，避免后端改阈值导致分叉
const CUBE_LEGEND_FALLBACK = [
  { min_p: 0, max_p: 0.45, label: 'P<0.45 看跌' },
  { min_p: 0.45, max_p: 0.52, label: '0.45–0.52 中性' },
  { min_p: 0.52, max_p: 0.58, label: '0.52–0.58 弱看涨' },
  { min_p: 0.58, max_p: 1, label: '>0.58 强看涨' },
  { min_p: null, max_p: null, label: '无样本' }
];
const CUBE_BAND_STYLES = [
  { bg: 'rgba(14,138,99,.72)', col: '#fff' },
  { bg: 'rgba(124,133,126,.26)', col: 'var(--ink2)' },
  { bg: 'rgba(217,56,67,.28)', col: 'var(--ink)' },
  { bg: 'rgba(217,56,67,.72)', col: '#fff' }
];

function cubeBandIndex(cell, p, legend) {
  const lg = (legend && legend.length) ? legend : CUBE_LEGEND_FALLBACK;
  if (cell && cell.color_band) {
    for (let i = 0; i < lg.length; i++) { if (lg[i].label === cell.color_band) return i; }
  }
  const real = lg.filter(function (l) { return l.min_p != null && l.max_p != null; });
  for (let i = 0; i < real.length; i++) {
    const last = i === real.length - 1;
    if (p >= real[i].min_p && (last ? p <= real[i].max_p : p < real[i].max_p)) return lg.indexOf(real[i]);
  }
  return CUBE_BAND_STYLES.length - 1;
}

export function cubeLegendHTML(legend) {
  const lg = (legend && legend.length) ? legend : CUBE_LEGEND_FALLBACK;
  const swatch = function (l, i) {
    if (l.min_p == null || l.max_p == null) {
      return '<i style="background:repeating-linear-gradient(45deg,rgba(124,133,126,.3),rgba(124,133,126,.3) 3px,transparent 3px,transparent 6px)"></i>';
    }
    const s = CUBE_BAND_STYLES[i] || CUBE_BAND_STYLES[1];
    return '<i style="background:' + s.bg + '"></i>';
  };
  return lg.map(function (l, i) { return '<span>' + swatch(l, i) + esc(l.label) + '</span>'; }).join('')
    + '<span style="margin-left:auto;color:var(--ink3)">横轴 = om 档 · 纵轴 = r2 档</span>';
}

export function cubeSliceHTML(slice, key, legend) {
  if (!slice) return '<div class="mini">无切片数据</div>';
  const cells = (slice.cells || []).slice().sort(function (a, b) {
    return (a.state[0] - b.state[0]) || (a.state[1] - b.state[1]);
  });
  const head = '<div class="cl">om 1 → 5　　·　　vr 层 ' + (slice.vr_layer + 1) + '/5（量比 ' + esc(slice.vr_label || '') + '）</div>';
  const body = cells.map(function (c) {
    const p = c[key];
    const state = c.state || [0, 0, 0];
    if (c.is_empty || c.status === 'empty' || !isNum(p)) {
      return '<div class="cc empty" title="档位 [' + (state[0] + 1) + ',' + (state[1] + 1) + ',' + (state[2] + 1) + '] · n=0 · 无估计值">—</div>';
    }
    const band = CUBE_BAND_STYLES[cubeBandIndex(c, p, legend)] || CUBE_BAND_STYLES[3];
    const n = key === 'naive_p' ? c.naive_n : c.ddsm_n;
    return '<div class="cc" style="background:' + band.bg + ';color:' + band.col + '" '
      + 'title="档位 [' + (state[0] + 1) + ',' + (state[1] + 1) + ',' + (state[2] + 1) + '] · n=' + n + ' · P=' + p.toFixed(3) + '">'
      + (p * 100).toFixed(0) + '</div>';
  }).join('');
  return head + body;
}

export function statCard(k, v, s, vClass, amtFlag) {
  return '<div class="sc"><div class="k">' + esc(k) + '</div><div class="v' + (amtFlag ? ' amt' : '') + (vClass ? ' ' + vClass : '') + '">' + v + '</div>'
    + (s ? '<div class="s">' + s + '</div>' : '') + '</div>';
}

export function factor(k, v, unit) {
  return '<div class="factor"><div class="k">' + esc(k) + '</div><div class="v">' + v + (unit || '') + '</div></div>';
}

export function hudCard(k, v, s, state) {
  return '<div class="hud-c ' + (state || '') + '"><div class="k">' + esc(k) + '</div><div class="v">' + v + '</div>'
    + (s ? '<div class="s">' + s + '</div>' : '') + '</div>';
}

/* ---------------- R-UI-11 · 三窗口组合预测卡 ---------------- */
const WIN_LABEL = { T1: 'T+1', T3: 'T+3', T15: 'T+15' };
const WIN_FORMULA = { T1: '门 + DDSM + 双否决', T3: '仅触发做多', T15: '门 + DDSM' };

export function forecastCard(w) {
  const isUp = w.direction === 'up';
  const canShow = w.weighted_p != null;
  const reason = DIRECTION_REASON[w.direction_reason] || '';
  const cov = isNum(w.coverage_ratio) ? w.coverage_ratio : 0;
  const pText = canShow ? prob(w.weighted_p) : '—';
  const pNote = canShow ? '持仓加权 P(涨)' : (w.window === 'T3' ? '该窗口无概率定式' : '无开口，不表态');
  return '<div class="win"><div class="h">' + esc(WIN_LABEL[w.window] || w.window)
    + ' ' + tag(isUp ? '看涨' : '不表态', isUp ? 'red' : 'gray', reason)
    + '</div>'
    + '<div class="dir ' + (isUp ? 'up' : 'flat') + '">' + pText + '</div>'
    + '<div class="p">' + esc(WIN_FORMULA[w.window] || '') + (w.validation_status === 'pending_cv' ? ' · 未验证' : '') + '</div>'
    + '<div class="cov">' + esc(pNote) + (reason ? ' · ' + esc(reason) : '')
    + '<div class="covbar2"><i style="width:' + Math.min(cov * 100, 100).toFixed(1) + '%;' + (isUp ? '' : 'background:var(--ink3)') + '"></i></div>'
    + '<b style="color:var(--ink2)">覆盖 ' + (cov * 100).toFixed(1) + '% 市值 · ' + int(w.open_count) + ' 只开口</b></div></div>';
}

function int(v) { return (v == null) ? '—' : String(v); }

