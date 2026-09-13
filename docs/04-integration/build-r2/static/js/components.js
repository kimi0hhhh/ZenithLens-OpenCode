// 极境 ZenithLens · UI 基础组件 v3（R2：四态 / 命脉组件 / 通用件）
// 口径唯一来源：09-api-contract v9.1（字段名逐字一致）；数值只经 format.js；文案只经 copy.js。
import { amt, prob, rate, rateU, pp, num, delta, z as fz, cls, isNum, timeHM, dateTimeShort } from './format.js';
import {
  STATE_COPY, errorText, DIRECTION_REASON,
  CONF_CLASS, SOURCE_LAYER, confReasonText, QDII_FALLBACK_REASON,
  verifyStatusText, verifyStatusKind, METRIC_TIP
} from './copy.js';

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

// U-11 · 口径 tooltip：文案只从 copy.js 字典取（组件不硬编码口径长文）
export function tipAttr(text) {
  return text ? ' title="' + esc(text) + '"' : '';
}
export function metricTip(key) {
  return METRIC_TIP[key] || '';
}

/* ---------------- R-UI-40 · 四态容器 ---------------- */
// slice: {status, data, error, variant?}；empty 时可选 copy.empty.action 渲染主行动按钮。
export function mountState(container, view, slice, onRetry, factRows) {
  if (!container) return;
  if (slice.status === 'success') {
    container.className = 'state-block';
    container.innerHTML = '';
    return;
  }
  const copy = (STATE_COPY[view] || STATE_COPY.holdings);
  // idle（首帧尚未发起请求）按 loading 渲染，不得显示错误文案
  const key = slice.status === 'idle' ? 'loading' : slice.status;
  const c = copy[key + (slice.variant ? '_' + slice.variant : '')] || copy[key] || copy.error;
  if (slice.status === 'empty') {
    const facts = (factRows || []).map(function (f) {
      return '<div class="fact"><div class="k">' + esc(f[0]) + '</div><div class="v">' + f[1] + '</div></div>';
    }).join('');
    container.className = 'state-block empty';
    container.innerHTML = '<div class="inner"><div class="big">' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(c.sub) + '</div>'
      + (facts ? '<div class="facts">' + facts + '</div>' : '')
      + (c.action && typeof onRetry === 'function'
        ? '<button class="sbtn" data-retry data-empty-action>' + esc(c.action) + '</button>' : '')
      + '</div>';
  } else if (slice.status === 'loading' || slice.status === 'idle') {
    container.className = 'state-block loading';
    container.innerHTML = '<div class="inner"><div class="big"><span class="pulse"></span>' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(c.sub) + '</div>'
      + '<div style="max-width:520px;margin:0 auto">' + '<div class="skeleton"></div>'.repeat(4) + '</div></div>';
  } else {
    container.className = 'state-block error';
    container.innerHTML = '<div class="inner"><div class="big">' + esc(c.big) + '</div>'
      + '<div class="sub">' + esc(errorText(slice.error || c.sub)) + '</div>'
      + '<button class="sbtn" data-retry>重试</button></div>';
  }
  const btn = container.querySelector('[data-retry]');
  if (btn) btn.addEventListener('click', function () {
    if (typeof onRetry === 'function') onRetry(btn.hasAttribute('data-empty-action') ? 'empty' : null);
  });
}

// 净值滞后横幅：只描述「净值快照」数据域滞后，不冒充引擎状态（引擎状态由 livebar 单独表达）。
// opts.engineOnline === false 时才附「引擎未运行」；opts.market_date 标注「行情快照」数据域。
export function staleBanner(as_of, opts) {
  const o = opts || {};
  const nav = as_of
    ? '净值快照 ' + esc(as_of) + (o.days_behind ? '（滞后 ' + esc(o.days_behind) + ' 天）' : '')
    : '';
  const mkt = o.market_date ? '行情快照 ' + esc(o.market_date) : '';
  const eng = o.engineOnline === false ? '引擎未运行' : '引擎在线';
  return '<div class="stalebar">' + [nav, mkt, eng].filter(Boolean).join(' · ') + '</div>';
}

/* ---------------- R-UI-03 · 估值来源徽章（命脉 · U-02 双层编码 + 7 项 tooltip） ---------------- */
const MODE_LABEL = { official: '官方净值', intraday: '盘中估算', holdings: '重仓加权', proxy: '代理近似', unknown: '未知' };

function holdingsTraceDetail(v) {
  if (!Array.isArray(v.trace)) return null;
  const step = v.trace.find(function (t) { return t && t.mode === 'holdings'; });
  return step && step.detail && typeof step.detail === 'object' ? step.detail : null;
}

export function valBadge(v, opts) {
  const o = opts || {};
  // 状态不可用（无估值记录）→「来源不可用」虚线，不编造
  if (!v) return '<span class="vb cu l0" title="来源不可用：该行无估值记录">来源不可用</span>';
  const mode = v.valuation_mode || 'unknown';
  const label = v.mode_label || MODE_LABEL[mode] || '未知';
  const layer = SOURCE_LAYER[mode] || 'l0';            // 第一层：来源底色
  const cc = v.confidence_color_class || CONF_CLASS[v.confidence] || 'cu'; // 第二层：置信度描边
  const tip = [];
  // ① 来源说明
  tip.push('来源：' + label + (v.source_label ? '（' + v.source_label + '）' : ''));
  // ② 降级链路（缺失只显示 mode，不编造）
  if (v.trace_text) tip.push('降级链路：' + v.trace_text);
  // ③ MAE
  if (isNum(v.mae_rate)) {
    const base = isNum(v.industry_baseline_mae_rate) ? v.industry_baseline_mae_rate : 0.008;
    tip.push('历史平均误差 MAE ' + rateU(v.mae_rate) + '（行业基准 ' + rateU(base) + '）');
  }
  // ④ 方向命中率 ⑤ 样本数
  if (isNum(v.dir_hit_rate)) {
    tip.push('方向命中率 ' + (v.dir_hit_rate * 100).toFixed(1) + '%'
      + (isNum(v.n_test) ? '，样本 n=' + v.n_test + ' 个可配对日' : ''));
  } else if (isNum(v.n_test)) {
    tip.push('样本 n=' + v.n_test + ' 个可配对日');
  }
  // ⑥ 回测窗
  if (isNum(v.accuracy_window_days)) tip.push('回测窗：最近 ' + v.accuracy_window_days + ' 个可配对日');
  // ⑦ 披露口径（仅 holdings 档 detail 有值；非 holdings 档不显示该行）
  const detail = holdingsTraceDetail(v);
  if (detail) {
    const parts = [];
    if (detail.report_date) parts.push('披露截止日 ' + detail.report_date);
    if (isNum(detail.covered_weight_pct)) parts.push('覆盖权重 ' + detail.covered_weight_pct.toFixed(2) + '%');
    if (detail.top_n) parts.push('抓取档位 top' + detail.top_n);
    if (Array.isArray(detail.included_markets) && detail.included_markets.length) parts.push('纳入 ' + detail.included_markets.join('/'));
    if (parts.length) tip.push('披露口径：' + parts.join(' · '));
  }
  // unknown 必须带原因（conf_reason 五值；禁止裸「未知」）
  if (v.confidence === 'unknown' || mode === 'unknown') {
    tip.push('未知原因：' + (confReasonText(v.conf_reason) || '原因未提供'));
  }
  if (v.nav_date) tip.push('净值截止日 ' + v.nav_date);
  if (v.written_at) tip.push('入账 ' + dateTimeShort(v.written_at));
  // QDII 校正（非 null 时追加一行；applied=false 给出回退原因，不静默）
  const qc = v.qdii_correction;
  if (qc && typeof qc === 'object') {
    const seg = qc.applied ? '双段' : '单段';
    const fr = qc.applied ? '' : ('（' + (QDII_FALLBACK_REASON[qc.fallback_reason] || qc.fallback_reason || '原因未提供') + '）');
    tip.push('QDII 校正：' + seg + fr + (qc.note ? ' · ' + qc.note : ''));
  }
  const code = o.code || '';
  return '<span class="vb ' + layer + ' ' + cc + '" title="' + esc(tip.join('\n')) + '"'
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

/* ---------------- U-07 · C 档验证状态行内标签 ---------------- */
// 直读后端 verify_status / verify_status_label；状态缺失 → 「待验证」兜底 + 标注（不推测）。
export function verifyTag(r) {
  if (!r) return '';
  const code = r.verify_status;
  const label = verifyStatusText(code, r.verify_status_label);
  const kind = verifyStatusKind(code);
  const bits = [];
  if (r.tier_reason) bits.push('档位依据：' + r.tier_reason);
  if (r.verify_note) bits.push('结论：' + r.verify_note);
  if (r.verify_batch_id) bits.push('批次：' + r.verify_batch_id);
  if (r.verify_review_date) bits.push('复查日：' + r.verify_review_date + '（挂档观察，不计入覆盖增长）');
  if (!code && !r.verify_status_label) bits.push('状态缺失 → 待验证兜底（不推测）');
  return '<span class="verify ' + kind + '"' + tipAttr(bits.join('\n')) + '>' + esc(label) + '</span>';
}

/* ---------------- 通用：状态标签 / 进度条 / z-bar ---------------- */
export function tag(text, kind, title) {
  return '<span class="tag ' + (kind || 'gray') + '"' + (title ? ' title="' + esc(title) + '"' : '') + '>' + esc(text) + '</span>';
}

export function progressBar(ratio, color, title) {
  const w = Math.max(0, Math.min(100, (isNum(ratio) ? ratio : 0) * 100));
  return '<div class="prg"' + (title ? ' title="' + esc(title) + '"' : '') + '><i style="width:' + w.toFixed(1) + '%;' + (color ? 'background:' + color : '') + '"></i></div>';
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

/* ---------------- R-UI-13 · 六步推导链（09 §5.34 / §6.4；第⑥步回填值由后端 detail 直出） ---------------- */
const VETO_STATUS_LABEL = { pass: '通过', veto: '亮灯否决', missing: '数据缺失' };
// metrics 键 → [标签, 格式化]；键枚举来自契约 §6.4，缺键=数据缺失，不编造
const CHAIN_METRIC = {
  ret_rate: ['触发日涨跌', function (v) { return rate(v); }],
  vr: ['量比', function (v) { return num(v, 2) + '×'; }],
  r2: ['2日累计收益', function (v) { return num(v, 3); }],
  om: ['σ归一动量', function (v) { return num(v, 4); }],
  ddsm_state: ['档位', function (v) { return Array.isArray(v) ? '[' + v.join(',') + ']' : '—'; }],
  p_up: ['P(涨)', function (v) { return prob(v); }],
  crowd_z: ['拥挤度 z', function (v) { return fz(v); }],
  crowd_quantile: ['拥挤度分位', function (v) { return isNum(v) ? (v * 100).toFixed(0) + '%' : '—'; }],
  klow2: ['KLOW2', function (v) { return num(v, 4); }],
  klow2_quantile: ['KLOW2 分位', function (v) { return isNum(v) ? (v * 100).toFixed(0) + '%' : '—'; }],
  band: ['出口带宽', function (v) { return prob(v); }],
  exit_threshold: ['出口阈值', function (v) { return prob(v); }],
  veto_crowd_status: ['拥挤度态', function (v) { return VETO_STATUS_LABEL[v] || v; }],
  veto_klow2_status: ['KLOW2 态', function (v) { return VETO_STATUS_LABEL[v] || v; }]
};

export function chainHTML(steps) {
  if (!steps || !steps.length) return '<div class="mini">无链路数据</div>';
  const items = steps.map(function (s) {
    const on = s.status === 'on';
    const off = s.status === 'off';
    const miss = s.status === 'missing';
    const k = 'chain-item' + (on ? ' on' : (off ? ' off' : ''));
    const tagCls = miss ? 'gray' : (on ? 'red' : 'ok');
    const metrics = (s.metrics && Object.keys(s.metrics).length)
      ? '<div class="cd" style="margin-top:4px">' + Object.keys(s.metrics).map(function (key) {
        const def = CHAIN_METRIC[key];
        if (!def) return '';
        return '<span style="display:inline-block;margin-right:12px">' + esc(def[0]) + ' <span class="mono">' + esc(def[1](s.metrics[key])) + '</span></span>';
      }).join('') + '</div>'
      : '';
    // 第⑥步（output）：回填值/待回填由后端 detail 直出，前端不编造数值
    const outStep = s.key === 'output' || s.step === 6;
    return '<div class="' + k + '"><div class="ct"><span class="tag ' + tagCls + '">' + esc(s.title || ('第' + s.step + '步')) + '</span>'
      + (miss ? '<span class="tag gray">数据缺失</span>' : '')
      + (outStep ? '<span class="tag blue">回填态</span>' : '')
      + '</div>'
      + '<div class="cd">' + esc(s.detail || '') + '</div>' + metrics + '</div>';
  }).join('');
  return '<div class="chain">' + items + '</div>';
}

/* ---------------- U-10 · dialog 焦点回位 / Esc / modal / toast ---------------- */
// 原生 <dialog> 自带 Esc；此处补「打开时记录触发元素、关闭后焦点回位」。
export function initDialogs() {
  if (typeof document === 'undefined' || typeof HTMLDialogElement === 'undefined') return;
  const proto = HTMLDialogElement.prototype;
  if (!proto.__zlPatched) {
    const origShowModal = proto.showModal;
    proto.showModal = function () {
      this.__zlOpener = document.activeElement;
      return origShowModal.apply(this, arguments);
    };
    proto.__zlPatched = true;
    document.addEventListener('close', function (e) {
      const dlg = e.target;
      if (dlg && dlg.tagName === 'DIALOG' && dlg.__zlOpener && typeof dlg.__zlOpener.focus === 'function') {
        try { dlg.__zlOpener.focus(); } catch (err) { /* noop */ }
        dlg.__zlOpener = null;
      }
    }, true);
  }
}

export function showModal(title, html) {
  let m = document.getElementById('zl-modal');
  if (!m) {
    m = document.createElement('div');
    m.id = 'zl-modal';
    m.className = 'modal-mask';
    document.body.appendChild(m);
  }
  m.__zlOpener = document.activeElement;
  m.innerHTML = '<div class="dlg" role="dialog" aria-modal="true"><h3>' + esc(title) + '</h3><div class="mini" style="line-height:1.8">' + (html || '')
    + '</div><div class="dlg-acts"><button class="btn" data-close>关闭</button></div></div>';
  m.classList.add('show');
  const closeM = function () {
    m.classList.remove('show');
    if (m.__zlOpener && typeof m.__zlOpener.focus === 'function') { try { m.__zlOpener.focus(); } catch (e) { /* noop */ } }
  };
  m.querySelector('[data-close]').addEventListener('click', closeM);
  m.addEventListener('click', function (e) { if (e.target === m) closeM(); });
  // U-10：Esc 关闭（任意 dialog）
  if (!m.__zlEscBound) {
    m.__zlEscBound = true;
    m.__zlKey = function (e) { if (e.key === 'Escape' && m.classList.contains('show')) { e.preventDefault(); closeM(); } };
    document.addEventListener('keydown', m.__zlKey);
  }
}

export function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  // U-10：屏幕阅读器播报
  t.setAttribute('role', 'status');
  t.setAttribute('aria-live', 'polite');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._tt);
  toast._tt = setTimeout(function () { t.classList.remove('show'); }, 2200);
}

/* ---------------- R-UI-26 · 125 格立方体切片（A-07 双口径） ---------------- */
// 阈值/标签由后端 legend 提供（§5.25）；配色为前端设计 token，但分档**只认后端 color_band**，
// 禁止前端用 P 重算分档（避免与后端口径分叉）。
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

function cubeBandIndex(cell, legend) {
  const lg = (legend && legend.length) ? legend : CUBE_LEGEND_FALLBACK;
  if (cell && cell.color_band) {
    for (let i = 0; i < lg.length; i++) { if (lg[i].label === cell.color_band) return i; }
  }
  return -1; // 后端未给 / 未命中：走中性色，不前端重算
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
      return '<div class="cc empty" title="档位 [' + (state[0] + 1) + ',' + (state[1] + 1) + ',' + (state[2] + 1) + '] · n=0 · 无估计值">无样本</div>';
    }
    const idx = cubeBandIndex(c, legend);
    const band = idx >= 0 ? (CUBE_BAND_STYLES[idx] || CUBE_BAND_STYLES[2]) : { bg: 'rgba(124,133,126,.26)', col: 'var(--ink2)' };
    const n = key === 'naive_p' ? c.naive_n : c.ddsm_n;
    // 契约 §5.25（v5 SHOULD-5）：研究口径 naive_n<min_n(15) 的低样本格须叠加「低样本·仅供审计」角标，不得据此判结论。
    const low = key === 'naive_p' && c.naive_low_sample === true;
    const lowMark = low ? '<sup class="low-mark" title="低样本·仅供审计（naive_n<15），不得据此判结论">低</sup>' : '';
    return '<div class="cc' + (low ? ' low' : '') + '"' + (low ? ' data-low-sample="1"' : '') + ' style="background:' + band.bg + ';color:' + band.col + '" '
      + 'title="档位 [' + (state[0] + 1) + ',' + (state[1] + 1) + ',' + (state[2] + 1) + '] · n=' + n + ' · P=' + p.toFixed(3) + (low ? ' · 低样本（仅供审计）' : '') + '">'
      + (p * 100).toFixed(0) + lowMark + '</div>';
  }).join('');
  return head + body;
}

/* ---------------- R-UI-22 · 竞技场配色（A-09：独立色板，禁止复用涨跌色） ---------------- */
const ARENA_COLORS = ['red', 'green', 'blue', 'yellow', 'base'];
export function arenaColorVar(color, prefix) {
  const c = ARENA_COLORS.indexOf(color) >= 0 ? color : 'blue';
  const p = prefix || '--arena-';
  return 'var(' + p + c + ')';
}
export function arenaClass(color) {
  const c = ARENA_COLORS.indexOf(color) >= 0 ? color : 'blue';
  return 'c-' + c;
}

/* ---------------- R-UI-11 · 组合加权口径（A-08） ---------------- */
export function weightingNote(win) {
  if (!win) return '';
  const basis = win.weighting_basis || 'market_value';
  const policy = win.weighting_policy_note || '';
  return '<b>权重口径 <code>' + esc(basis) + '</code></b>（冻结，变更须版本 +1）'
    + (policy ? '：' + esc(policy) : '') + '<br>';
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

/* ---------------- R-UI-11 · 三窗口组合预测卡（U-11 口径 tooltip） ---------------- */
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
    + '<div class="dir ' + (isUp ? 'up' : 'flat') + '"' + tipAttr(canShow ? METRIC_TIP.weighted_p : '') + '>' + pText + '</div>'
    + '<div class="p">' + esc(WIN_FORMULA[w.window] || '') + (w.validation_status === 'pending_cv' ? ' · 未验证' : '') + '</div>'
    + '<div class="cov">' + esc(pNote) + (reason ? ' · ' + esc(reason) : '')
    + '<div class="covbar2"' + tipAttr(METRIC_TIP.coverage_ratio) + '><i style="width:' + Math.min(cov * 100, 100).toFixed(1) + '%;' + (isUp ? '' : 'background:var(--ink3)') + '"></i></div>'
    + '<b style="color:var(--ink2)">覆盖 ' + (cov * 100).toFixed(1) + '% 市值 · ' + int(w.open_count) + ' 只开口</b>'
    + (w.weighting_basis ? ' · 权重 <code>' + esc(w.weighting_basis) + '</code>' : '') + '</div></div>';
}

function int(v) { return (v == null) ? '—' : String(v); }
