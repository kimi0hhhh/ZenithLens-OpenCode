// 极境 ZenithLens · mock 演示数据（默认关闭；仅 ?mock=1 或 localStorage.zl_mock='1' 时注入）
// 本文件与生产代码隔离；字段名严格按 09-api-contract v3。mock 是"后端替身"，可做展示折算。
/* eslint-disable */
const AS_OF = '2026-08-24';
const IS_TODAY = false;
const SESSION = 'closed';
const MODES = {
  official: ['官方净值', 'high', 0.0031, 0.0064, 62, 60, '官方当日净值已公布，可直接采信'],
  intraday: ['盘中估算', 'mid', 0.0066, 0.0071, 57, 42, '官方未出 → 行情源盘中估算净值'],
  holdings: ['重仓加权', 'mid', 0.0066, 0.0071, 57, 42, '官方未出 → 前十大重仓股当日涨跌加权'],
  proxy: ['代理近似', 'low', 0.0124, 0.009, 52, 35, '官方未出 → 代理 ETF 当日涨跌 × 最新官方净值'],
  unknown: ['未知', 'unknown', null, null, null, null, '回测证明估算无信息量 → 只标净值截止日']
};
const CONF_LABEL = { high: '误差达标', mid: '误差中等', low: '误差偏大', unknown: '无可信估算' };
const CONF_CLASS = { high: 'ch', mid: 'cm', low: 'cl', unknown: 'cu' };

const RAW = [
  { code: '014320', name: '德邦半导体产业混合C', group: 'active', group_label: '主动', tier: 'A', shares: 486.9687, cost_amount: 1149.01, confirm_days: 1, proxy_code: '512480', proxy_name: '512480 半导体ETF', nav: 2.678, pct: -0.0382, mode: 'intraday' },
  { code: '013566', name: '华夏军工安全混合C', group: 'active', group_label: '主动', tier: 'A', shares: 523.0885, cost_amount: 1117.99, confirm_days: 1, proxy_code: '512660', proxy_name: '512660 军工ETF', nav: 2.2405, pct: -0.0229, mode: 'holdings' },
  { code: '017412', name: '创金合信科创创业50指数增强A', group: 'domestic_index', group_label: '境内指数', tier: 'B', shares: 2834.5577, cost_amount: 4608.38, confirm_days: 1, proxy_code: '588300', proxy_name: '588300 双创50', nav: 1.7172, pct: -0.036, mode: 'official' },
  { code: '008087', name: '华夏中证5G通信主题ETF联接C', group: 'domestic_index', group_label: '境内指数', tier: 'B', shares: 1124.2689, cost_amount: 2927.11, confirm_days: 1, proxy_code: '515880', proxy_name: '515880 通信ETF', nav: 2.8189, pct: -0.0426, mode: 'proxy' },
  { code: '000217', name: '华安黄金ETF联接C', group: 'gold', group_label: '黄金', tier: 'B', shares: 1272.6375, cost_amount: 4200.00, confirm_days: 1, proxy_code: '518880', proxy_name: '518880 黄金ETF', nav: 3.3667, pct: 0.0178, mode: 'official' },
  { code: '012922', name: '易方达全球成长精选混合(QDII)C', group: 'qdii', group_label: 'QDII', tier: 'B', shares: 880.28, cost_amount: 2430.00, confirm_days: 2, proxy_code: '513100', proxy_name: '513100 纳指ETF', nav: 3.6112, pct: -0.0226, mode: 'intraday' },
  { code: '022485', name: '国金中证A500指数增强A', group: 'domestic_index', group_label: '境内指数', tier: 'C', shares: 3289.3267, cost_amount: 4690.00, confirm_days: 1, proxy_code: '159352', proxy_name: '159352 A500ETF', nav: 1.455, pct: -0.0145, mode: 'proxy' },
  { code: '025500', name: '东方阿尔法科技智选混合发起C', group: 'active', group_label: '主动', tier: 'D', shares: 847.3875, cost_amount: 802.48, confirm_days: 1, proxy_code: null, proxy_name: null, nav: 1.5824, pct: null, mode: 'unknown' }
];

function valuationOf(r, date) {
  const m = MODES[r.mode];
  return {
    valuation_mode: r.mode, mode_label: m[0], change_rate: r.pct, estimated_nav: r.pct == null ? null : r.nav,
    source_label: r.mode === 'official' ? '基金公司公布净值' : '腾讯/天天基金实时估算',
    confidence: m[1], mae_rate: m[3], nav_date: date || AS_OF,
    trace: traceOf(r.mode), written_at: AS_OF + 'T15:30:00+08:00', run_id: 'run_20260824_1530',
    is_first_of_day: true, history_available: true,
    dir_hit_rate: m[4] == null ? null : m[4] / 100, n_test: m[5], accuracy_window_days: 40,
    industry_baseline_mae_rate: 0.008, confidence_label: CONF_LABEL[m[1]],
    confidence_color_class: CONF_CLASS[m[1]],
    trace_text: traceText(r.mode), as_of: date || AS_OF
  };
}
function traceOf(mode) {
  const order = ['official', 'intraday', 'holdings', 'proxy', 'unknown'];
  const idx = order.indexOf(mode);
  return order.map(function (m, i) {
    return { mode: m, tried: i <= idx, hit: i === idx, reason: i < idx ? 'not_published' : (i === idx ? 'hit' : 'missing') };
  });
}
function traceText(mode) {
  const map = {
    official: 'official 命中', intraday: 'official 未出 → intraday 命中',
    holdings: 'official 未出 → intraday 未命中 → holdings 命中',
    proxy: 'official 未出 → intraday 未命中 → holdings 无重仓 → proxy 命中',
    unknown: null
  };
  return map[mode];
}
function navOf(r) {
  return { official_nav: r.mode === 'official' ? r.nav : r.nav * 0.997, official_nav_date: AS_OF, official_change_rate: r.mode === 'official' ? r.pct : -0.0012, previous_nav: r.nav * 0.998, is_today_official: false };
}

const PRED_MAP = {
  '014320': { gate: 'E3', p_up: 0.61, vc: 0, vk: 0, out: 'up' },
  '013566': { gate: 'E3', p_up: 0.51, vc: 0, vk: 0, out: 'gray' },
  '017412': { gate: 'E1', p_up: 0.54, vc: 0, vk: 0, out: 'up' },
  '008087': { gate: 'E3', p_up: 0.59, vc: 1, vk: 0, out: 'abstain' },
  '000217': { gate: 'E1', p_up: 0.54, vc: 0, vk: 1, out: 'abstain' }
};

function win(window, formula, dir, p, validation) {
  return {
    window: window, formula: formula, formula_source: window === 'T1' ? 'brief_5.1' : 'arch_baseline_v1',
    validation_status: window === 'T1' ? 'brief_mandated' : (validation || 'pending_cv'),
    validated: window === 'T1', direction: dir, provisional_direction: dir,
    p: window === 'T3' ? null : p, provisional_p: window === 'T3' ? null : p,
    open: dir === 'up', hit_rate: window === 'T1' ? 0.583 : (window === 'T3' ? 0.556 : 0.597),
    baseline_rate: window === 'T1' ? 0.484 : null, delta_pp: window === 'T1' ? 0.099 : null
  };
}
function predictionOf(r) {
  const p = PRED_MAP[r.code];
  if (!p) return null;
  const isAbstain = p.out === 'abstain';
  return {
    code: r.code, gate: p.gate, gate_label: p.gate === 'E3' ? '无量急跌' : '跳空', p_up: p.p_up,
    ddsm_state: p.gate === 'E3' ? [1, 2, 2] : [3, 3, 3],
    veto_crowd: !!p.vc, veto_crowd_status: p.vc ? 'veto' : 'pass',
    veto_klow2: !!p.vk, veto_klow2_status: p.vk ? 'veto' : 'pass',
    signal: p.out, signal_label: p.out === 'up' ? '涨' : (p.out === 'abstain' ? '弃权' : '灰'),
    reason: p.out === 'up' ? 'ok' : (isAbstain ? (p.vc ? 'veto_crowd' : 'veto_klow2') : 'below_band'),
    windows: {
      T1: win('T1', 'gate+ddsm+veto', p.out === 'up' ? 'up' : 'gray', p.p_up, null),
      T3: win('T3', 'gate_only', 'gray', null, 'pending_cv'),
      T15: win('T15', 'gate+ddsm', 'gray', 0.597, 'pending_cv')
    },
    as_of: AS_OF
  };
}

function mv(r) { return r.pct == null ? null : (r.confirm_days === 3 ? null : round2(r.shares * r.nav)); }
function round2(v) { return Math.round(v * 100) / 100; }
function round4(v) { return Math.round(v * 10000) / 10000; }

function buildRows() {
  const rows = RAW.map(function (r) {
    const market = mv(r);
    const fallback = market == null ? r.cost_amount : 0;
    const today = (market != null && r.pct != null) ? round2(market - market / (1 + r.pct)) : null;
    const pnl = market == null ? 0 : round2(market - r.cost_amount);
    return {
      code: r.code, name: r.name, group: r.group, group_label: r.group_label, tier: r.tier,
      shares: r.shares, cost_amount: r.cost_amount, avg_cost: r.shares ? round4(r.cost_amount / r.shares) : null,
      confirm_days: r.confirm_days, proxy_code: r.proxy_code, proxy_name: r.proxy_name,
      valuation: valuationOf(r), nav: navOf(r), prediction: predictionOf(r),
      market_value: market, mv_source: market == null ? null : (r.mode === 'official' ? 'nav' : 'valuation'),
      fallback_value: fallback, weight_ratio: null, today_pnl_amt: today, pnl_amt: pnl,
      return_rate: r.cost_amount ? round4(pnl / r.cost_amount) : null,
      staleness: { is_stale: true, latest_date: AS_OF, days_behind: 19, note: '数据快照 ' + AS_OF }
    };
  });
  const total = rows.reduce(function (s, r) { return s + (r.market_value || 0); }, 0);
  const coveredCost = rows.reduce(function (s, r) { return s + (r.market_value == null ? 0 : r.cost_amount); }, 0);
  const fallback = rows.reduce(function (s, r) { return s + r.fallback_value; }, 0);
  const totalPnl = rows.reduce(function (s, r) { return s + (r.market_value == null ? 0 : r.pnl_amt); }, 0);
  const today = rows.reduce(function (s, r) { return s + (r.today_pnl_amt || 0); }, 0);
  const covered = rows.filter(function (r) { return r.market_value != null; }).length;
  rows.forEach(function (r) { r.weight_ratio = r.market_value == null ? null : round4(r.market_value / total); });
  return { rows: rows, summary: {
    total_value: round2(total), fallback_value: round2(fallback), total_value_with_fallback: round2(total + fallback),
    covered_cost_amount: round2(coveredCost), today_pnl_amt: round2(today), total_pnl_amt: round2(totalPnl),
    return_rate: coveredCost ? round4(totalPnl / coveredCost) : null, covered_count: covered, total_count: rows.length,
    coverage_note: '可信估值覆盖 ' + covered + '/' + rows.length + ' 只' + (covered < rows.length ? ('；另有 ' + round2(fallback) + ' 元未知行按成本计，合计 ' + round2(total + fallback)) : '（全部覆盖）'),
    as_of: AS_OF
  } };
}

const HOLD = buildRows();

function env(data, as_of) { return { ok: true, data: data, error: null, as_of: as_of === undefined ? AS_OF : as_of }; }
function notFound(msg) { return { ok: false, data: null, error: { code: 'E_NOT_FOUND', message: msg || '未找到', detail: null }, as_of: null }; }

/* ---------- 派生数据 ---------- */
function precision() {
  const groups = ['high', 'mid', 'low', 'unknown'].map(function (c) {
    const rows = HOLD.rows.filter(function (r) { return (r.mode === 'unknown' ? 'unknown' : r.valuation.confidence) === c; });
    const mvv = rows.reduce(function (s, r) { return s + (r.market_value || 0); }, 0);
    return { confidence: c, count: rows.length, market_value: round2(mvv), weight_ratio: round4(mvv / HOLD.summary.total_value) };
  });
  const modeDist = ['official', 'intraday', 'holdings', 'proxy', 'unknown'].map(function (m) {
    const rows = HOLD.rows.filter(function (r) { return r.valuation.valuation_mode === m; });
    const mvv = rows.reduce(function (s, r) { return s + (r.market_value || 0); }, 0);
    return { mode: m, mode_label: MODES[m][0], count: rows.length, market_value: round2(mvv), weight_ratio: round4(mvv / HOLD.summary.total_value) };
  });
  return { groups: groups, weighted_mae_rate: 0.0068, industry_baseline_mae_rate: 0.008, window_days: 40, mode_distribution: modeDist };
}

function forecast() {
  const total = HOLD.summary.total_value;
  const open = HOLD.rows.filter(function (r) { return r.prediction && r.prediction.windows.T1.open; });
  const openMv = open.reduce(function (s, r) { return s + (r.market_value || 0); }, 0);
  const wp = open.length ? round4(open.reduce(function (s, r) { return s + (r.market_value || 0) * r.prediction.p_up; }, 0) / openMv) : null;
  const met = (openMv / total) >= 0.30 && open.length >= 3;
  const mk = function (w, p, openN, dir, reason) {
    return { window: w, weighted_p: p, coverage_ratio: round4(openMv / total), coverage_value: round2(openMv), open_value: round2(openMv),
      total_value: round2(total), open_count: openN, min_coverage_ratio: 0.3, min_open_count: 3, coverage_threshold_met: met,
      excluded_ratio: round4(1 - openMv / total), threshold_source: 'brief_5.1', direction: dir, direction_reason: reason,
      weighted_p_threshold: 0.52, tier_excluded: ['C', 'D'], engine_status: 'offline', as_of: AS_OF };
  };
  return { windows: [
    mk('T1', wp, open.length, (wp != null && wp > 0.52 && met) ? 'up' : 'gray', met ? 'ok' : 'insufficient_coverage'),
    mk('T3', null, open.length, 'gray', 'window_unvalidated'),
    mk('T15', 0.597, open.length, 'gray', 'window_unvalidated')
  ], engine_status: 'offline', as_of: AS_OF };
}

const PRED_ROWS = HOLD.rows.filter(function (r) { return r.prediction; }).map(function (r) { return r.prediction; });

function chainOf(code) {
  const p = PRED_MAP[code] || { gate: 'E3', p_up: 0.61, vc: 0, vk: 0, out: 'up' };
  const veto = function (n, title, status, detail) { return { step: n, key: n === 3 ? 'veto_crowd' : 'veto_klow2', title: title, status: status, detail: detail, metrics: {} }; };
  return [
    { step: 1, key: 'gate', title: '① 触发门', status: 'on', detail: p.gate + ' 已触发', metrics: { ret_rate: -0.0382, vr: 0.72 } },
    { step: 2, key: 'ddsm', title: '② DDSM', status: 'on', detail: '档位 [1,2,2] → P=' + p.p_up, metrics: { ddsm_state: [1, 2, 2], p_up: p.p_up } },
    veto(3, '③ 拥挤度否决', p.vc ? 'on' : 'off', p.vc ? '处最拥挤 40% · 否决' : '未亮灯'),
    veto(4, '④ KLOW2 否决', p.vk ? 'on' : 'off', p.vk ? '处最不利 40% · 否决' : '未亮灯'),
    { step: 5, key: 'exit', title: '⑤ 出口', status: p.out === 'up' ? 'on' : 'off', detail: 'P ' + (p.out === 'up' ? '>' : '≤') + ' 0.52', metrics: { exit_threshold: 0.52 } },
    { step: 6, key: 'output', title: '⑥ 输出', status: 'on', detail: '信号「' + (p.out === 'up' ? '涨' : '弃权') + '」→ 入台账', metrics: {} }
  ];
}

const LEDGER = [
  { date: '2026-08-24', code: '014320', name: '德邦半导体产业混合C', tier: 'A', gate: 'E3', p_up: 0.61, ddsm_state: [1, 2, 2], veto_crowd: false, veto_klow2: false, signal: 'up', market_value: 1304.1, cost_est: 1149.01, t1_real: null, t3_real: null, t15_real: null, written_at: AS_OF + 'T15:30:00+08:00', is_backfilled: false, created_at: AS_OF + 'T15:30:00+08:00', record_seq: 9, source_file: 'shadow_signals.jsonl', chain_available: true },
  { date: '2026-08-24', code: '008087', name: '华夏中证5G通信主题ETF联接C', tier: 'B', gate: 'E3', p_up: 0.59, ddsm_state: [1, 2, 1], veto_crowd: true, veto_klow2: false, signal: 'abstain', market_value: 3169.0, cost_est: 2927.11, t1_real: null, t3_real: null, t15_real: null, written_at: AS_OF + 'T15:30:00+08:00', is_backfilled: false, created_at: AS_OF + 'T15:30:00+08:00', record_seq: 8, source_file: 'shadow_signals.jsonl', chain_available: true },
  { date: '2026-08-18', code: '014320', name: '德邦半导体产业混合C', tier: 'A', gate: 'E3', p_up: 0.58, ddsm_state: [2, 4, 1], veto_crowd: false, veto_klow2: false, signal: 'up', market_value: 1290.0, cost_est: 1149.01, t1_real: 0.0124, t3_real: null, t15_real: null, written_at: '2026-08-18T15:30:00+08:00', is_backfilled: false, created_at: '2026-08-18T15:30:00+08:00', record_seq: 3, source_file: 'shadow_signals.jsonl', chain_available: true },
  { date: '2026-08-12', code: '008087', name: '华夏中证5G通信主题ETF联接C', tier: 'B', gate: 'E1', p_up: 0.55, ddsm_state: [4, 3, 2], veto_crowd: true, veto_klow2: false, signal: 'abstain', market_value: 3200.0, cost_est: 2927.11, t1_real: null, t3_real: null, t15_real: null, written_at: '2026-08-12T15:30:00+08:00', is_backfilled: false, created_at: '2026-08-12T15:30:00+08:00', record_seq: 2, source_file: 'shadow_signals.jsonl', chain_available: true },
  { date: '2026-07-22', code: '013566', name: '华夏军工安全混合C', tier: 'A', gate: 'E1', p_up: 0.53, ddsm_state: [3, 3, 3], veto_crowd: false, veto_klow2: false, signal: 'up', market_value: 1180.0, cost_est: 1117.99, t1_real: -0.0042, t3_real: null, t15_real: null, written_at: '2026-07-22T15:30:00+08:00', is_backfilled: false, created_at: '2026-07-22T15:30:00+08:00', record_seq: 1, source_file: 'shadow_signals.jsonl', chain_available: true }
];

function arena() {
  const labels = [['d15', '15日'], ['d30', '30日'], ['d60', '60日'], ['m6', '6月'], ['m24', '24月'], ['full', '全样本']];
  const rows = [
    { name: 'A 裸算法（仅触发）', kind: 'naive_baseline', data: [[128, 52.1], [205, 53.4], [312, 54.0], [588, 53.8], [1580, 52.9], [2301, 52.2]] },
    { name: 'A + KLOW2', kind: 'candidate', data: [[38, 57.1], [63, 57.4], [98, 57.6], [180, 57.2], [404, 57.5], [593, 57.3]] },
    { name: 'A + 拥挤度', kind: 'candidate', data: [[36, 54.2], [58, 54.6], [90, 54.9], [168, 54.5], [386, 54.4], [585, 54.4]] },
    { name: 'A + CNTN5', kind: 'candidate', data: [[112, 53.4], [178, 54.1], [268, 53.2], [502, 52.6], [1342, 51.8], [1958, 51.4]] },
    { name: 'C 当前生产（双否决）', kind: 'production', highlight: true, data: [[24, 57.9], [41, 58.2], [66, 58.5], [121, 58.1], [268, 58.4], [420, 58.3]] },
    { name: 'C − KLOW2（留一）', kind: 'leave_one_out', loo: true, data: [[52, 55.1], [88, 55.4], [138, 55.6], [258, 55.2], [592, 55.0], [872, 54.9]] },
    { name: 'C − 拥挤度（留一）', kind: 'leave_one_out', loo: true, data: [[34, 56.4], [56, 56.8], [88, 57.0], [162, 56.6], [358, 56.5], [520, 56.3]] }
  ];
  const base = [48.4, 48.4, 48.4, 48.4, 50.1, 48.4];
  const naiveRow = rows.find(function (r) { return r.kind === 'naive_baseline'; });
  const d = function (row, i) { return row.data[i][1] - base[i]; };
  return {
    windows: labels.map(function (l) { return { window: l[0], window_label: l[1] }; }),
    rows: rows.map(function (r) {
      const cells = r.data.map(function (c, i) {
        const del = r.kind === 'naive_baseline' ? null : round4(d(r, i) / 100);
        let color = 'blue';
        if (r.kind === 'naive_baseline') color = 'base';
        else if (del != null && del < d(naiveRow, i) / 100) color = 'yellow';
        return { window: labels[i][0], open_count: c[0], hit_rate: round4(c[1] / 100), paired_delta_pp: del, is_leave_one_out: !!r.loo, warning: color === 'yellow', color: color, is_window_max: false, is_window_min: false };
      });
      return { config_id: r.name, config_name: r.name, config_kind: r.kind, is_leave_one_out: !!r.loo, is_highlight: !!r.highlight, warning: cells.some(function (c) { return c.warning; }), cells: cells };
    }),
    legend: [{ color: 'red', label: '该窗最高' }, { color: 'green', label: '该窗最低' }, { color: 'blue', label: '居中' }, { color: 'yellow', label: '警示：加了反而比不加差' }, { color: 'base', label: '基准行' }],
    naive_method_note: '同一份数据、同一个门、同一个模型，只换一个因子 —— 这是加一法与留一法能给出因果结论的前提。留一法（C − eᵢ）移除后组合 Δ 上升 ≥0.5pp 持续 30 天 = 结构红线，进 A/B。',
    as_of: AS_OF
  };
}

function cubeBand(p) {
  if (p == null) return 'no_sample';
  if (p < 0.45) return 'P<0.45 看跌';
  if (p < 0.52) return '0.45–0.52 中性';
  if (p < 0.58) return '0.52–0.58 弱看涨';
  return '>0.58 强看涨';
}

function cube(code) {
  const seed = (function (s) { return function () { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; })(20260904);
  const layers = [];
  for (let c = 0; c < 5; c++) {
    const cells = [];
    for (let a = 0; a < 5; a++) for (let b = 0; b < 5; b++) {
      const dist = (a - 2) * (a - 2) + (b - 2) * (b - 2) + (c - 2) * (c - 2);
      const n = Math.max(0, Math.round(95 * Math.exp(-dist / 2.4) - 1.4 + (seed() - 0.5) * 4));
      const pTrue = 0.638 - 0.058 * (a / 4) - 0.042 * (b / 4) + 0.014 * (c / 4);
      const pNaive = n === 0 ? null : Math.max(0, Math.min(1, n < 7 ? (seed() < 0.5 ? 0 : 1) : pTrue + (seed() - 0.5) * 0.3));
      const ddsmN = n * 5;
      const pDdsm = Math.max(0.30, Math.min(0.72, (pTrue * ddsmN + 10 * 0.484) / (ddsmN + 10) + (seed() - 0.5) * 0.013));
      cells.push({ state: [a, b, c], vr_layer: c, status: n === 0 ? 'empty' : 'filled', is_empty: n === 0, naive_n: n, naive_p: pNaive, ddsm_n: ddsmN, ddsm_p: n === 0 ? null : round4(pDdsm), color_band: cubeBand(pNaive != null ? pNaive : (n === 0 ? null : pDdsm)) });
    }
    layers.push({ vr_layer: c, vr_label: ['≈0.55', '≈0.75', '≈0.95', '≈1.20', '≈1.55'][c], cell_axis: { row: 'r2', col: 'om' }, cells: cells, filled_count: cells.filter(function (x) { return !x.is_empty; }).length, empty_count: cells.filter(function (x) { return x.is_empty; }).length });
  }
  return {
    code: code || '014320', name: '德邦半导体产业混合C', dims: ['r2', 'om', 'vr'], bins_per_dim: 5,
    vlabels: ['≈0.55', '≈0.75', '≈0.95', '≈1.20', '≈1.55'], layers: layers,
    comparison: { valid_coverage_naive_pct: 0.944, valid_coverage_ddsm_pct: 1.0, mean_naive: 0.52, mean_ddsm: 0.51,
      p_std_naive: 0.213, p_std_ddsm: 0.084, p_range_naive: 0.86, p_range_ddsm: 0.31,
      extreme_count_naive: 21, extreme_count_ddsm: 3, empty_count_naive: 7, empty_count_ddsm: 0,
      walk_forward_delta_naive_pp: -0.039, walk_forward_delta_ddsm_pp: 0.028, walk_forward_delta_ddsm_lo_pp: 0.016, walk_forward_delta_ddsm_hi_pp: 0.055,
      note: '左边为什么会烂：125 个状态格里边缘格样本极少甚至为零，n=0 时该格根本没有估计值。右边做了什么：①加噪增强（K=4、p=0.25）＝状态空间平滑正则化；②收缩 P=(n_up+10×涨率)/(n+10)。已证伪：loss-guided、IC 自适应加噪。' },
    legend: [
      { min_p: 0, max_p: 0.45, label: 'P<0.45 看跌' }, { min_p: 0.45, max_p: 0.52, label: '0.45–0.52 中性' },
      { min_p: 0.52, max_p: 0.58, label: '0.52–0.58 弱看涨' }, { min_p: 0.58, max_p: 1, label: '>0.58 强看涨' },
      { min_p: null, max_p: null, label: '无样本' }
    ], train_as_of: AS_OF, snapshot_at: AS_OF + 'T08:00:00+08:00'
  };
}

function inputs(code) {
  const assets = {
    '014320': { name: '德邦半导体产业混合C', d3: [[-5.1, -1.42, 1], [-0.82, -1.18, 1], [0.72, -0.95, 2]], d6: [[-6.8, -1.34, 1, -1], [0.72, -0.95, 2, 1], [-4.2, -1.12, 1, -1], [-0.31, 0.42, 4, 1], [2.14, 0.88, 4, 1], [-0.15, -0.34, 3, -1]], crowd: [-0.21, 0.42, 2, 0], klow: [0.19, 2, 0] },
    '008087': { name: '华夏中证5G通信主题ETF联接C', d3: [[-6.4, -1.68, 1], [-0.34, -0.55, 2], [0.65, -1.22, 1]], d6: [[2.1, 0.94, 4, -1], [0.65, -1.22, 1, 1], [1.8, 1.31, 5, -1], [0.52, 1.14, 5, 1], [2.68, 1.42, 5, 1], [0.41, 0.88, 5, -1]], crowd: [1.08, 0.78, 4, 1], klow: [0.31, 3, 0] },
    '000217': { name: '华安黄金ETF联接C', d3: [[2.9, 1.24, 5], [0.92, 1.18, 5], [1.12, 0.42, 4]], d6: [[3.4, 1.32, 5, -1], [1.12, 0.42, 4, 1], [2.8, 1.46, 5, -1], [0.28, 0.68, 4, 1], [1.24, -0.32, 2, 1], [0.31, 0.72, 4, -1]], crowd: [0.42, 0.62, 4, 0], klow: [0.62, 5, 1] }
  };
  const a = assets[code] || assets['014320'];
  const labels3 = ['2日累计收益', 'σ归一动量', '量比'];
  const labels6 = ['5日动量', '量能水平', '乖离率', '量价相关', '已实现波动', '收益偏度'];
  const feats3 = ['r2', 'om', 'vr'], feats6 = ['mom5', 'vr', 'dev', 'vpcorr', 'volat', 'skew'];
  const mk = function (feat, label, arr, group) {
    return { feature: feat, group: group, label: label, raw: arr[0] / 100, raw_unit: '比率', z: arr[1], level: arr[2], level_label: arr[2] + '/5', ic_sign: group === 'ddsm_3d' ? '0' : (arr[3] > 0 ? '+' : '-'), signed_z: round4(arr[1] * (group === 'ddsm_3d' ? 1 : (arr[3] > 0 ? 1 : -1))), formula: group === 'ddsm_3d' ? label : label + '（训练段 IC）' };
  };
  return {
    code: code, name: a.name, train_as_of: AS_OF, snapshot_at: AS_OF + 'T15:00:00+08:00',
    ddsm_3d: a.d3.map(function (arr, i) { return mk(feats3[i], labels3[i], arr, 'ddsm_3d'); }),
    crowd_6d: a.d6.map(function (arr, i) { return mk(feats6[i], labels6[i], arr, 'crowd_6d'); }),
    crowd: { composite_z: a.crowd[0], quantile: a.crowd[1], quantile_level: a.crowd[2], quantile_threshold: 0.6, is_veto: !!a.crowd[3], status: a.crowd[3] ? 'veto' : 'pass', klow2: a.klow[0], klow2_quantile: 0.42, klow2_level: a.klow[1], klow2_threshold: 0.4, klow2_is_veto: !!a.klow[2], klow2_status: a.klow[2] ? 'veto' : 'pass' }
  };
}

/* ---------- 路由 ---------- */
export async function mockRequest(path, opts) {
  await new Promise(function (r) { setTimeout(r, 60); });
  opts = opts || {};
  const method = opts.method || 'GET';
  const [p, qs] = path.split('?');
  const q = {}; (qs || '').split('&').filter(Boolean).forEach(function (kv) { const kv2 = kv.split('='); q[decodeURIComponent(kv2[0])] = decodeURIComponent(kv2[1] || ''); });
  const body = opts.body || {};

  if (p === '/runtime') return env({ server_time: AS_OF + 'T15:40:00+08:00', port: 8787, as_of: AS_OF, staleness: { is_stale: true, latest_date: AS_OF, days_behind: 19, note: '数据快照 ' + AS_OF }, open_count: forecast().windows[0].open_count, trade_session: SESSION, engine_status: 'offline' });
  if (p === '/holdings/summary') return env(HOLD.summary);
  if (p === '/holdings/coverage') return env({
    tiers: [
      { tier: 'A', tier_label: 'A 已接入', color: '#0e8a63', count: 2, market_value: 2473.3, weight_ratio: 0.16, description: '引擎直接产出信号，可采信', action_hint: '信号已可用', invalidation: 'definition_failure', member_names: ['德邦半导体', '华夏军工'] },
      { tier: 'B', tier_label: 'B 代理已验证', color: '#1d9e75', count: 4, market_value: 10576.8, weight_ratio: 0.68, description: '映射 ETF 已过六关', action_hint: '接线即可用', invalidation: 'data_failure', member_names: ['创金科创创业50', '华夏5G', '华安黄金', '易方达全球成长'] },
      { tier: 'C', tier_label: 'C 代理待验证', color: '#c99700', count: 1, market_value: 4786.9, weight_ratio: 0.31, description: '标的明确但未过六关', action_hint: '验证后可用', invalidation: 'data_failure', member_names: ['国金A500'] },
      { tier: 'D', tier_label: 'D 暴露待定', color: '#a3aaa4', count: 1, market_value: 0, weight_ratio: 0, description: '需先做穿透或 RBSA', action_hint: '穿透后可用', invalidation: 'framework_failure', member_names: ['东方阿尔法科技'] }
    ], total_count: HOLD.summary.total_count, total_value: HOLD.summary.total_value,
    invalidation_note: '分级依据 = 项目自己的「失效三类」原则：定义失效／数据失效／框架失效，只有定义失效才是真死。A 已接入：信号可用。B 代理已验证：映射 ETF 在验证池内、已过六关；黄金和 QDII 都在这档，QDII 的 T+2 是信息优势不是缺陷。C 代理待验证：标的明确但不在验证池。D 暴露待定：主动全市场，需先做穿透或 RBSA。',
    no_solution_count: 0, as_of: AS_OF
  });
  if (p === '/holdings/risk') return env({ sharpe: 0.82, var95_rate: 0.0194, downside_vol_rate: 0.113, max_drawdown_rate: 0.186, sample_days: 250, stale: true, computed_at: AS_OF + 'T16:00:00+08:00', note: '历史模拟法，回看 250 交易日；慢接口，按需计算' });
  if (p === '/holdings') {
    if (method === 'POST') return env({ code: body.code, name: body.name });
    return env({ rows: HOLD.rows, summary: HOLD.summary });
  }
  if (/^\/holdings\/([^/]+)\/transactions$/.test(p)) return env(HOLD.rows[0]);
  if (/^\/holdings\/[^/]+$/.test(p)) {
    const code = p.split('/')[2];
    if (method === 'PUT') return env({ code: code, name: body.name || code });
    if (method === 'DELETE') return env({ deleted_code: code });
    const row = HOLD.rows.find(function (r) { return r.code === code; });
    return row ? env(row) : notFound('无此 code');
  }
  if (p === '/holdings/import') return env({ imported_count: 22, source: 'app_data/funds_data.json', imported_at: AS_OF + 'T16:10:00+08:00', warnings: [] });
  if (p === '/valuations/precision') return env(precision());
  if (/^\/valuations\/[^/]+$/.test(p)) {
    const code = p.split('/')[2];
    const row = HOLD.rows.find(function (r) { return r.code === code; });
    if (!row) return notFound('无此 code');
    const hist = [{ ...row.valuation, mode_label: '盘中估算' }, { ...row.valuation, mode_label: '官方净值', valuation_mode: 'official', written_at: AS_OF + 'T20:00:00+08:00', is_first_of_day: false }];
    return env(q.history === 'true' ? { code: code, name: row.name, valuation: row.valuation, nav: row.nav, history: hist } : { code: code, name: row.name, valuation: row.valuation, nav: row.nav });
  }
  if (p === '/portfolio/forecast') return env(forecast());
  if (p === '/predictions') return env({ rows: PRED_ROWS, engine_status: 'offline', as_of: AS_OF });
  if (/^\/predictions\/[^/]+$/.test(p)) {
    const code = p.split('/')[2];
    const row = HOLD.rows.find(function (r) { return r.code === code; });
    if (!row || !row.prediction) return notFound('无此 code');
    return env(Object.assign({}, row.prediction, { chain: chainOf(code) }));
  }
  if (p === '/review/scores') return env({ scores: [
    { window: 'T1', formula: '门 + DDSM + 双否决', hit_rate: 0.583, open_count: 420, baseline_rate: 0.484, baseline_status: 'filled', delta_pp: 0.099, cv_mode: 'walk_forward', purge_gap: 'H+2', holdout_days: 60, data_kind: 'backtest', sample_period: '2024-01-01..2026-08-31', as_of: AS_OF },
    { window: 'T3', formula: '仅触发做多', hit_rate: 0.556, open_count: 2295, baseline_rate: null, baseline_status: 'pending', delta_pp: null, cv_mode: 'walk_forward', purge_gap: 'H+2', holdout_days: 60, data_kind: 'backtest', sample_period: '2024-01-01..2026-08-31', as_of: AS_OF },
    { window: 'T15', formula: '门 + DDSM', hit_rate: 0.597, open_count: 1208, baseline_rate: null, baseline_status: 'pending', delta_pp: null, cv_mode: 'walk_forward', purge_gap: 'H+2', holdout_days: 60, data_kind: 'backtest', sample_period: '2024-01-01..2026-08-31', as_of: AS_OF }
  ], hero: { window: 'T1', hit_rate: 0.583, baseline_rate: 0.484, delta_pp: 0.099, label: 'T+1 双否决命中率' } });
  if (p === '/review/reconciliation') return env({ rows: LEDGER.map(function (r) { return Object.assign({}, r, { result: r.t1_real == null ? 'pending' : (r.signal === 'abstain' ? 'abstain' : (r.t1_real > 0 ? 'hit' : 'miss')) }); }), total: LEDGER.length });
  if (p === '/review/cv-config') return env({ cv_mode: 'walk_forward', random_split: false, purge_gap: 'H+2', placebo_min_pp: 0.02, holdout_days: 60, holdout_start_date: null, ledger_policy: 'insert_only' });
  if (p === '/ledger') return env({ rows: LEDGER, total: LEDGER.length });
  if (p === '/ledger/chain') {
    const row = LEDGER.find(function (r) { return r.date === q.date && r.code === q.code; }) || LEDGER[0];
    return env({ date: row.date, code: row.code, name: row.name, gate: row.gate, signal: row.signal, p_up: row.p_up, chain: chainOf(row.code), metrics: { ret_rate: -0.0382, vr: 0.72, p_up: row.p_up, exit_threshold: 0.52 }, source_ledger: 'shadow_signals.jsonl', created_at: row.created_at });
  }
  if (p === '/ledger/shadow') return env({
    rows: LEDGER, total: LEDGER.length,
    summary: { total_records: LEDGER.length, open_signals: 3, veto_abstains: 2, backfilled_count: 1, hit_rate: 1.0, baseline_rate: 0.583 },
    progress: { status: 'not_started', consecutive_days: 0, target_days: 60, progress_ratio: 0, start_date: null, target_date: null, gap_days: 0, hit_rate: null, baseline_rate: 0.583, deviation_pp: null, note: '连续 60 日无漏单且偏差 <2pp 才具上线资格' },
    field_list: ['date', 'code', 'gate', 'p_up', 'ddsm_state', 'veto_crowd', 'veto_klow2', 'signal', 't1_real', 't3_real', 't15_real', 'created_at'],
    insert_only_note: '收盘时点固定写盘、事后不可改（INSERT-ONLY），到期自动回填 T+1 / T+3 / T+15 实际涨跌。', as_of: AS_OF
  });
  if (p === '/signals/state') return env({
    state: 'no_open', as_of: AS_OF, monitored_count: 6, total_count: 8, days_since_last_open: 4,
    last_open: { date: '2026-08-18', code: '014320', name: '德邦半导体产业混合C', gate: 'E3', result: 'hit', t1_real: 0.0124 },
    last_result: 'hit', empty_note: '监控中均未触发开门条件 —— 这是常态，不是故障。',
    gates: [
      { gate: 'E1', gate_key: 'E1', label: 'E1 跳空', formula: 'low[t] > high[t-1]', role: 'secondary', effect_pp: 0.88, t_value: 0.7, note: '当日最低价高于昨日最高价。' },
      { gate: 'E3', gate_key: 'E3', label: 'E3 无量急跌', formula: 'ret < -0.02 且 vr < 0.8', role: 'primary', effect_pp: 3.9, t_value: 2.33, note: '跌得深且缩量。' }
    ],
    excluded_gates: [
      { gate: 'E1', gate_key: 'E4', label: '点火', formula: '3日 +4%', role: 'excluded', effect_pp: -2.72, t_value: null, note: '做多反向' },
      { gate: 'E1', gate_key: 'E2', label: '放量上涨', formula: '放量上涨', role: 'excluded', effect_pp: -3.09, t_value: null, note: '做多全反向，仅作止盈回避' }
    ], or_merge_forbidden: true
  });
  if (p === '/meta/definitions') return env({
    formula: 'up = 1 若 close[T+1] > close[T]', signal_time: 'T 日 15:30 收盘后',
    timing_note: '是"明日收盘价 vs 今日收盘价"。时序坑：场外基金申购截止 15:00，而信号 15:30 才出 —— 当天按 close[T] 成交的窗口已经关了。',
    paths: [
      { path: 'new_position', label: 'A · 新建仓位', steps: 'T+1 申购按 close[T+1] 成交', executable: false, caveat: '吃的是 close[T+2]−close[T+1]，晚了一拍' },
      { path: 'hold_existing', label: 'B · 已持有仓位', steps: '看到"明日涨"→ 决定不在 T+1 赎回', executable: true, caveat: '这条可执行' },
      { path: 'onsite_etf', label: 'C · 场内 ETF', steps: 'T+1 开→收', executable: false, caveat: '口径仍不同' }
    ], conclusion: '结论：对场外基金最现实的用法是 B（持有/赎回决策），不是 A（择时建仓）。'
  });
  if (p === '/factors/pans') return env({ pans: pans() });
  if (p === '/factors/books') return env({ books: books() });
  if (/^\/factors\/books\/[^/]+$/.test(p)) {
    const book = p.split('/')[3];
    const b = books().find(function (x) { return x.book === book; });
    return b ? env({ book: b.book, book_label: b.book_label, record_kind: b.record_kind, schema_fields: b.schema_fields, records: b.sample, total: b.record_count, last_record_at: b.last_record_at }) : notFound('未知 book');
  }
  if (p === '/factors/score-chain') return env(scoreChain());
  if (p === '/factors/score-detail') return env(scoreDetail(q.factor_id));
  if (p === '/factors/lifecycle') return env(lifecycle());
  if (p === '/factors/governance-cycle') return env(governance());
  if (p === '/factors/dig-records') return env({ records: digRecords(), panel: { nomination_limit: 3, cooldown_days: 90, week_rule: '每周提名 ≤3' } });
  if (p === '/engine/status') return env({
    status: 'offline', pid: null, port: 8787, version: 'v1.5', active_engine_version: 'v1.5', started_at: null,
    last_heartbeat_at: null, last_success_at: '2026-08-24T15:40:00+08:00', snapshot_as_of: AS_OF,
    shadow_status: 'not_started', shadow_consecutive_days: 0, shadow_target_days: 60, training_assets: 38, index_only_assets: 3,
    state_grid_total_cells: 125, state_grid_filled_cells: 118, state_grid_coverage_pct: 0.944, avg_samples_per_cell: 47.3, min_samples_cell: 3,
    last_retrain_at: '2026-07-01', next_retrain_at: '2026-10-01', data_freshness_snapshot_date: AS_OF, data_freshness_days_behind: 19
  });
  if (p === '/engine/inputs') return env(inputs(q.code));
  if (p === '/engine/ddsm/cube') return env(cube(q.code));
  if (p === '/engine/training-status') return env({
    total_cells: 125, filled_cells: 118, coverage_pct: 0.944, avg_samples_per_cell: 47.3, min_samples_cell: 3, min_n: 15,
    noise: { k_noise: 4, p_perturb: 0.25 },
    train_mode: '逐资产、全样本、季度滚动重训；参数全项目统一冻结，无逐资产调参。',
    noise_text: '每样本生成 K=4 个副本，每维以 p=0.25 概率 ±1 档扰动，副本沿用原标签 → 有效样本 ×5。实测加噪后 +1.6~5.5pp，覆盖率提升 7~60 倍。',
    retrain_cycle: 'quarterly', last_retrain_at: '2026-07-01', next_retrain_at: '2026-10-01',
    retrain_note: '重训周期由年改季，属参数变更须重走六关，标注待验证。',
    training_assets: 38, index_only_assets: 3,
    dead_ends: ['第 4/5 维因子', 'DDSM 用于 T+3', '逐资产路由 / 统一决策树', 'loss-guided 加噪', 'IC 自适应加噪']
  });
  if (p === '/engine/frozen-params') return env({
    k_noise: 4, p_perturb: 0.25, min_n: 15, shrink: 10, band: 0.02, veto_crowd_quantile: 0.6, veto_klow2_quantile: 0.4,
    min_coverage_ratio: 0.3, min_open_count: 3, gate_e1: 'low[t] > high[t-1]', gate_e3: 'ret < -0.02 且 vr < 0.8', purge_gap: 'H+2',
    window_weights: [{ window: 'd15', weight: 8 }, { window: 'd30', weight: 22 }, { window: 'd60', weight: 15 }, { window: 'm6', weight: 10 }, { window: 'm24', weight: 30 }, { window: 'full', weight: 15 }],
    window_min_days: [{ window: 'd15', n_w: 5 }, { window: 'd30', n_w: 10 }, { window: 'd60', n_w: 15 }, { window: 'm6', n_w: 30 }, { window: 'm24', n_w: 60 }, { window: 'full', n_w: 120 }],
    license_lines: [{ license: 'candidate', min_independent_days: 50, note: '只记账不参与生产' }, { license: 'probation', min_independent_days: 60, window_k: 0.5 }, { license: 'renew_t2', min_independent_days: 70, window_k: 0.7 }, { license: 'full_t3', min_independent_days: 80, window_k: 0.7 }],
    change_policy: '任何一项改动必须重走六关'
  });
  if (p === '/engine/arena') return env(arena());
  if (p === '/engine/registry') return env({ engines: [
    { version: 'v1.5', status: 'active', note: '门 + DDSM + 双否决，T+1 58.3%，六关全过 —— 当前生产', metrics: { hit_rate: 0.583, baseline_rate: 0.484, delta_pp: 0.099 }, can_rollback: false },
    { version: 'v2.0-event', status: 'shadow', note: '事件维接入，三窗口均无增量（−1.5 / −0.4 / +0.0pp），观察区', metrics: { hit_rate: 0.583, baseline_rate: 0.484, delta_pp: 0.099 }, can_rollback: false },
    { version: 'v1.3', status: 'retired', note: '单否决（仅拥挤度）55.3%，被 v1.5 取代，可回滚', metrics: { hit_rate: 0.553, baseline_rate: 0.484, delta_pp: 0.069 }, can_rollback: true }
  ] });
  if (p === '/engine/shadow-review') return env({ status: 'idle', rolling_days: 60, hit_rate: null, baseline_rate: 0.583, deviation_pp: null, threshold_pp: 0.02, message: '影子盘尚未启动（idle）—— 逐日记录后此处显示滚动 60 日命中率 vs 58.3% 基准，偏离 >2pp 自动标红降级。', checked_at: null, note: '回测再漂亮也只是回测。上线前的最后保险是影子盘：连续 60 日无漏单且命中率与基准偏差 <2pp，才算具备上线资格。' });
  if (p === '/settings') return env({ privacy: { masked: false, mask_holdings_only: false }, llm: { enabled: false, provider: 'deepseek', model: 'deepseek-chat', api_key_set: false, temperature: 0, output_format: 'json', mode: 'shadow' }, port: 8787, auto_refresh: true, refresh_interval_sec: 300, theme: 'light' });
  if (p === '/data-sources/health') return env({ sources: [
    { source_id: 'tencent_kline', label: '腾讯日K（web.ifzq.gtimg.cn）', status: 'ok', last_ok_at: AS_OF + 'T15:40:00+08:00', fail_count: 0, latency_ms: 210, note: '' },
    { source_id: 'tencent_rt', label: '腾讯实时（qt.gtimg.cn）', status: 'ok', last_ok_at: AS_OF + 'T15:41:00+08:00', fail_count: 0, latency_ms: 130, note: '' },
    { source_id: 'eastmoney', label: '天天基金', status: 'ok', last_ok_at: AS_OF + 'T15:39:00+08:00', fail_count: 0, latency_ms: 260, note: '' },
    { source_id: 'sina_rt', label: '新浪（hq.sinajs.cn）', status: 'warn', last_ok_at: AS_OF + 'T15:38:00+08:00', fail_count: 1, latency_ms: null, note: '偶发波动' }
  ] });
  if (p === '/settings/holdings-data') return env({
    primary_path: 'C:\\Users\\10719\\Desktop\\基金监控项目\\app_data\\funds_data.json', primary_exists: true, primary_modified_at: AS_OF + 'T08:00:00+08:00', primary_count: 22,
    legacy_path: 'C:\\Users\\10719\\Desktop\\基金监控项目\\funds_data.json', legacy_exists: true, legacy_modified_at: '2026-08-21T08:00:00+08:00', legacy_count: 22,
    consistent: false, diff_fields: ['018957.pend_gz', 'modified_at'], readonly: true,
    diff_note: '存在两份 funds_data.json 且不同步。旧文件停在 2026-08-21，本产品读较新的 app_data 那份。018957 在旧文件里 08-21 的 pend_gz=4.6251，新文件同日实际净值 4.5912，差 0.73%。旧文件存的是盘中估算，新文件是后来回填的官方净值 —— 这正是「估值来源徽章」必须存在的原因。',
    checked_at: AS_OF + 'T16:00:00+08:00'
  });
  if (p === '/about') return env({ product_name: '极境 ZenithLens', version: 'v1.0.0', api_version: 'v1', python_min: '3.8', deployment: 'local_single_user', storage_note: '全部本地存储，数据不出本机', disclaimer: '不构成投资建议', built_at: AS_OF + 'T08:00:00+08:00' });
  if (p === '/data-sources/probe') return env({ task_id: 'tsk_probe', type: 'refresh_quotes', status: 'running', progress: 0.1, step: '探测中', submitted_at: AS_OF + 'T16:00:00+08:00', started_at: AS_OF + 'T16:00:00+08:00', finished_at: null, error: null, result_summary: null });
  if (p === '/tasks') return env({ tasks: [] });

  return notFound('mock 未覆盖：' + p);
}

/* ---------- 因子静态数据 ---------- */
function pans() {
  const F = [
    { id: 'klow2', n: 'KLOW2 下影线否决', lift: [1.41, 1.36, 1.28, 1.19, 1.12, 1.06], days: [3, 7, 15, 30, 55, 120], lic: 'full_t3', licLabel: '正式 T3', role: '否决位', pan: 'adopted', status: 'active', note: '六窗 lift 全 ≥1.06 · bootstrap P99.5 之上', death: '滚动 60 日中，该因子否决掉的子集命中率反超保留子集 +2pp 且持续 30 天 = 失效' },
    { id: 'crowd', n: '拥挤度六维复合', lift: [1.22, 1.18, 1.14, 1.09, 1.07, 1.04], days: [4, 8, 15, 30, 49, 120], lic: 'renew_t2', licLabel: '续聘 T2', role: '否决位', pan: 'adopted', status: 'active', note: 'mom5 / vr / dev / vpcorr / volat / skew 按训练段 IC 符号等权', death: '24 月窗 lift<1.00 或留一法移除后组合 Δ 升 ≥0.5pp 持续 30 天 = 结构红线' },
    { id: 'cntn5', n: 'CNTN5 事件计数', lift: [1.32, 1.22, 1.10, 1.04, 1.01, 0.99], days: [5, 10, 15, 28, 52, 105], lic: 'probation', licLabel: '试用（红线）', role: '打分位', pan: 'shadow_retired', status: 'cooling', note: '全量窗 0.99 跌破 1.00 → 扣 0.80', ab: { day: 23, total_days: 60, delta_after_removal_pp: 0.002, conclusion: '移出后组合 +0.2pp（尚在观察）' } },
    { id: 'rsv10', n: 'RSV10 超买超卖', lift: [1.24, 1.15, 1.06, 1.02, 1.00, 0.98], days: [5, 10, 15, 29, 54, 110], lic: 'candidate', licLabel: '候补（A/B）', role: '打分位', pan: 'shadow_retired', status: 'probation', note: '总分已低于随机 P90', ab: { day: 8, total_days: 60, delta_after_removal_pp: -0.001, conclusion: '移出后组合 −0.1pp（倾向误杀）' } },
    { id: 'vr', n: '量能 vr', lift: [1.31, 1.12, 1.05, 1.02, 1.01, 1.00], days: [5, 8, 12, 25, 39, 85], lic: 'candidate', licLabel: '候补观察', role: '打分位', pan: 'shadow_effective', status: 'probation', note: '15 日窗亮眼但长窗迅速衰减到 1.00 地板', death: '连续两季总分 <50 → 直接进冷冻盘' },
    { id: 'mom5', n: 'mom5 动量', lift: [0.94, 0.97, 1.02, 1.05, 1.03, 1.01], days: [4, 9, 13, 26, 42, 95], lic: 'probation', licLabel: '试用', role: '打分位', pan: 'shadow_effective', status: 'probation', note: '短窗反号 → 两个窗各扣 0.80', death: '当前总分已跌破 19，下一评分期若仍 <19 直接进 A/B' },
    { id: 'vpcorr', n: 'vpcorr 量价相关', lift: [1.44, 1.02, 0.96, 0.98, 0.97, 0.98], days: [5, 10, 15, 30, 60, 120], lic: 'none', licLabel: '冷冻盘', role: '已剔除', pan: 'frozen', status: 'frozen', note: '15 日窗 +0.441 是噪声；四个长窗全部跌破 1.00', frozen: '2026-08-24 判定淘汰正确（移除后 +0.3pp）· 已冷冻 12 天 · 满 90 天可重扫' }
  ];
  const toItem = function (f) {
    const total = f.lift.reduce(function (s, l, i) { return s + kLift(l) * [8, 22, 15, 10, 30, 15][i] * Math.min(1, f.days[i] / [5, 10, 15, 30, 60, 120][i]); }, 0);
    return { factor_id: f.id, name: f.n, role: f.pan, role_label: f.role, score: round4(total), total_score: round4(total), status: f.status, license: f.lic, license_label: f.licLabel, lift_bars: f.lift.map(function (l, i) { return { window: ['d15', 'd30', 'd60', 'm6', 'm24', 'full'][i], window_label: ['15日', '30日', '60日', '6月', '24月', '全样本'][i], lift: l }; }), independent_trigger_days: f.days[5], death_condition: f.death || null, note: f.note, ab_progress: f.ab || null, added_at: '2026-09-01' };
  };
  const pans2 = [
    { role: 'adopted', role_label: '正式盘（进化盘）', description: '参与组合决策 · 采纳当天预注册死亡条件', pan_status: 'on', flow_kind: 'promotion', factor_cap: 4, nomination_limit: null, rule_text: '总数上限：否决位 ≤4 个，打分位受状态空间约束（≤3 维）。月检留一法：每月移除该因子跑一遍当月，Δ 变化即真实贡献。新因子转正须池子未满或有旧因子让位 —— 在位者无终身制。' },
    { role: 'shadow_retired', role_label: '淘汰影子盘', description: '移出生产但继续并行跑 · A/B 对照 60 交易日', pan_status: 'warn', flow_kind: 'promotion', factor_cap: null, nomination_limit: null, rule_text: '同数据、同门、同模型。移除后组合 ≥ 移除前 +0.5pp → 淘汰正确，进冷冻盘；移除后变差 ≥0.5pp → 判误杀，无损回原牌照级。' },
    { role: 'shadow_effective', role_label: '有效因子影子盘', description: '试用期 · 独立记账，不参与生产决策', pan_status: 'on', flow_kind: 'promotion', factor_cap: null, nomination_limit: 3, rule_text: '准入三项 AND：F1 近 6 月或近 60 日任一超基线｜F2 与现役最大共线 <0.7｜F3 加入现配置 Δ≥+0.5pp 且开口不塌方（>50%）。' },
    { role: 'frozen', role_label: '冷冻盘', description: '候补库不是坟墓 · 台账全保留', pan_status: 'bad', flow_kind: 'revival', factor_cap: null, nomination_limit: null, rule_text: '复活触发：regime 切到有利状态 / 新信息源解锁 / 冷冻满 90 天重扫。复活路径：回候补（50 线）重爬，禁止直接回生产。' }
  ];
  F.forEach(function (f) { if (f.frozen) f.death = null; });
  return pans2.map(function (p) {
    const fs = F.filter(function (f) { return f.pan === p.role; });
    return Object.assign({}, p, { factor_count: fs.length, factors: fs.map(toItem), updated_at: AS_OF + 'T08:00:00+08:00' });
  });
}
function kLift(v) { return v >= 1.30 ? 1.0 : (v >= 1.20 ? 0.80 : (v >= 1.10 ? 0.65 : (v >= 1.00 ? 0.50 : (v >= 0.84 ? -0.80 : -1.3)))); }

function books() {
  return [
    { book: 'adopted_factors', book_label: '采纳登记表', filename: 'adopted_factors.json', purpose: '因子 → 角色 → 死亡条件 → 牌照 → 采纳日期', record_kind: 'adopted_record', schema_fields: ['factor_id', 'role', 'death_condition', 'license', 'adopted_at'], record_count: 2, last_record_at: '2026-09-01T08:00:00+08:00', sample: [{ factor_id: 'klow2', role: '否决位', death_condition: '滚动 60 日中否决子集命中率反超 +2pp 持续 30 天 = 失效', license: 'full_t3', adopted_at: '2026-09-01' }] },
    { book: 'scan_history', book_label: '挖掘台账', filename: 'scan_history.jsonl', purpose: '每次扫描的候选与判定 · 周提名 ≤3 · 冷却 90 天', record_kind: 'scan_record', schema_fields: ['scan_date', 'candidate', 'f1_result', 'f2_result', 'f3_result', 'verdict'], record_count: 5, last_record_at: '2026-08-30T08:00:00+08:00', sample: [{ scan_date: '2026-08-30', candidate: 'RESI30', f1_result: 'pass', f2_result: 'pass', f3_result: 'fail', verdict: 'rejected_f3' }] },
    { book: 'factor_health', book_label: '体检台账', filename: 'factor_health.jsonl', purpose: '月检留一法结果 · 红线触发 · regime 标签', record_kind: 'health_record', schema_fields: ['date', 'factor_id', 'loo_delta_pp', 'red_line', 'regime'], record_count: 0, last_record_at: null, sample: [] },
    { book: 'retired_log', book_label: '淘汰台账', filename: 'retired_log.jsonl', purpose: 'A/B 对照结果 · 环境快照 · 隔离 / 封存 / 复职记录', record_kind: 'retired_record', schema_fields: ['date', 'factor_id', 'delta_after_removal_pp', 'conclusion', 'regime'], record_count: 1, last_record_at: '2026-08-24T08:00:00+08:00', sample: [{ date: '2026-08-24', factor_id: 'vpcorr', delta_after_removal_pp: 0.003, conclusion: '淘汰正确 → 冷冻盘', regime: '短窗高波动' }] },
    { book: 'shadow_signals', book_label: '影子信号', filename: 'shadow_signals.jsonl', purpose: '系统最终输出台账（引擎页展示）', record_kind: 'signal_record', schema_fields: ['date', 'code', 'gate', 'p_up', 'signal', 'created_at'], record_count: LEDGER.length, last_record_at: AS_OF + 'T15:30:00+08:00', sample: [LEDGER[0]] },
    { book: 'factor_arena', book_label: '因子竞技场', filename: 'factor_arena.jsonl', purpose: '每个因子同日独立记账（引擎页展示）', record_kind: 'arena_record', schema_fields: ['date', 'config_id', 'window', 'open_count', 'hit_rate', 'paired_delta_pp'], record_count: 0, last_record_at: null, sample: [] }
  ];
}

function scoreChain() {
  return {
    lift_bins: [{ min_lift: 1.3, k_lift: 1.0, label: '≥1.30' }, { min_lift: 1.2, k_lift: 0.8, label: '≥1.20' }, { min_lift: 1.1, k_lift: 0.65, label: '≥1.10' }, { min_lift: 1.0, k_lift: 0.5, label: '≥1.00' }, { min_lift: 0.84, k_lift: -0.8, label: '<1.00' }, { min_lift: 0, k_lift: -1.3, label: '<0.84' }],
    window_weights: [{ window: 'd15', window_label: '15日', weight: 8 }, { window: 'd30', window_label: '30日', weight: 22 }, { window: 'd60', window_label: '60日', weight: 15 }, { window: 'm6', window_label: '6月', weight: 10 }, { window: 'm24', window_label: '24月', weight: 30 }, { window: 'full', window_label: '全样本', weight: 15 }],
    formula_text: '每窗 lift = 命中率 ÷ 基线 → k_lift 五档悬崖查表 → × 窗权重 × 准入度 min(1, 独立触发日 ÷ N_w) → 六窗加总。',
    bootstrap_percentiles: { p50: -10.8, p90: 38.7, p95: 48.4, p99: 61.7, p995: 64.1 },
    judges: [{ judge: 'lift', scope: '分数', metric: 'k_lift', note: '管分数' }, { judge: 't', scope: '闸门', metric: 't 值', note: '管闸门' }, { judge: 'admission', scope: '折扣', metric: '准入度', note: '管折扣' }, { judge: 'backtest', scope: '晋升', metric: '实测', note: '管晋升' }],
    floor_note: 'k_lift <1.00 → −0.80 天花板，<0.84 → −1.3；不对称惩罚即噪声抑制器。',
    rule_source: 'docs/00-charter/00-design-reference-legacy-v2.html §评分链'
  };
}
function scoreDetail(factorId) {
  const panList = pans();
  let item = null, panRole = null;
  panList.forEach(function (p) { p.factors.forEach(function (f) { if (f.factor_id === factorId) { item = f; panRole = p.role; } }); });
  if (!item) item = panList[0].factors[0];
  const weights = [8, 22, 15, 10, 30, 15], nws = [5, 10, 15, 30, 60, 120];
  const labels = ['15日', '30日', '60日', '6月', '24月', '全样本'];
  const keys = ['d15', 'd30', 'd60', 'm6', 'm24', 'full'];
  let total = 0;
  const windows = item.lift_bars.map(function (b, i) {
    const lift = b.lift, k = kLift(lift), adm = Math.min(1, item.independent_trigger_days / nws[i]);
    const sc = round4(k * weights[i] * adm); total += sc;
    return { window: keys[i], window_label: labels[i], lift: lift, k_lift: k, weight: weights[i], independent_trigger_days: item.independent_trigger_days, n_w: nws[i], admission: round4(adm), score: sc, cliff_hit: '≥1.20' };
  });
  return { factor_id: item.factor_id, name: item.name, total_score: round4(total), windows: windows, bootstrap_percentiles: scoreChain().bootstrap_percentiles, judges: scoreChain().judges, formula_text: scoreChain().formula_text };
}

function lifecycle() {
  return {
    admission_rules: ['F1 超基线（近 6 月或近 60 日任一超基线）', 'F2 与现役最大共线 <0.7', 'F3 加入后 Δ≥+0.5pp 且开口不塌方'],
    license_lines: [{ license: 'candidate', threshold: 50, condition: '独立触发日 ≥50', note: '候补' }, { license: 'probation', threshold: 60, condition: '≥60 且 30日窗 k≥0.5', note: '试用' }, { license: 'renew_t2', threshold: 70, condition: '≥70 且 60日窗 k≥0.7 且持牌满一季', note: '续聘 T2' }, { license: 'full_t3', threshold: 80, condition: '≥80 且 24月窗 k≥0.7', note: '正式 T3' }],
    retire_rules: ['急性熔断（连错 5 次或 15 日命中 <基线−15pp）', '缓性衰减（60 日 lift<1.00 连 30 日）', '结构红线（24 月 lift<1.00 或留一法移除后 Δ 升 ≥0.5pp）', '分数失守（<39 连续两期降级、<19 进 A/B、<−11 隔离）'],
    dual_exit: ['软出口降级梯（正式→续聘→试用→候补，台账全留）', '硬出口 A/B 对照 60 交易日'],
    false_kill_guards: ['条件绩效口径（分 regime 判读）', '开口 <20 不出结论', 'A/B 期间牌照冻结，误杀无损回位'],
    revive_rules: ['regime 有利 / 新信息源 / 满 90 天重扫', '复活回候补（50 线）重爬', '禁止直接回生产'],
    source: 'docs/00-charter/00-design-reference-legacy-v2.html §四盘/生命周期 + docs/00-charter/02-prd.md F-14',
    freeze_note: '规则文本冻结，改动须重走六关。'
  };
}
function governance() {
  return { phases: [
    { phase: 'dig_scan', label: '下次挖掘扫描', cadence: '周六', status: 'scheduled', last_run_at: '2026-08-30', next_run_at: '2026-09-05', rule_text: '提名 ≤3 · 冷却 90 天防多重检验', human_retained: '机制变更权' },
    { phase: 'scorecard', label: '下次评分卡', cadence: '周日', status: 'scheduled', last_run_at: '2026-08-31', next_run_at: '2026-09-06', rule_text: '六窗重算 + 异常复盘', human_retained: '机制变更权' },
    { phase: 'monthly_rank', label: '下次月榜 / 牌照', cadence: '每月 1 日', status: 'scheduled', last_run_at: '2026-09-01', next_run_at: '2026-10-01', rule_text: '排名只产生提名，不直接变更生产', human_retained: '机制变更权' },
    { phase: 'quarterly_review', label: '下次季复查', cadence: '每季首月', status: 'scheduled', last_run_at: null, next_run_at: '2026-10-01', rule_text: '试用→续聘判定，破格条款在此', human_retained: '机制变更权' },
    { phase: 'ddsm_retrain', label: '下次 DDSM 重训', cadence: '每季', status: 'scheduled', last_run_at: '2026-07-01', next_run_at: '2026-10-01', rule_text: '参数变更须重走六关', human_retained: '紧急停机权' }
  ], note: '机器自动裁判，人只留机制变更权与紧急停机权。' };
}
function digRecords() {
  return [
    { record_id: 'r5', scan_date: '2026-08-30', candidate: 'RESI30', f1_result: 'pass', f1_detail: '✓', f2_result: 'pass', f2_detail: '0.31', f3_result: 'fail', f3_detail: '+0.2pp', verdict: 'rejected_f3', verdict_text: '未过 F3，回落候选池', nomination_week: '2026-W35', cooldown_until: '2026-11-28', created_at: '2026-08-30T08:00:00+08:00' },
    { record_id: 'r4', scan_date: '2026-08-30', candidate: 'CNTN5', f1_result: 'pass', f1_detail: '✓', f2_result: 'pass', f2_detail: '0.42', f3_result: 'fail', f3_detail: '−0.1pp', verdict: 'rejected_f3', verdict_text: '未过 F3', nomination_week: '2026-W35', cooldown_until: '2026-11-28', created_at: '2026-08-30T08:00:00+08:00' },
    { record_id: 'r3', scan_date: '2026-08-30', candidate: 'RSV5', f1_result: 'pass', f1_detail: '✓', f2_result: 'fail', f2_detail: '0.78', f3_result: 'na', f3_detail: '', verdict: 'rejected_f2', verdict_text: '未过 F2，与 vr 共线', nomination_week: '2026-W35', cooldown_until: '2026-11-28', created_at: '2026-08-30T08:00:00+08:00' },
    { record_id: 'r2', scan_date: '2026-08-23', candidate: 'KSFT2', f1_result: 'pass', f1_detail: '✓', f2_result: 'pass', f2_detail: '0.29', f3_result: 'pass', f3_detail: '+0.6pp', verdict: 'admitted_to_arena', verdict_text: '进入竞技场影子盘', nomination_week: '2026-W34', cooldown_until: null, created_at: '2026-08-23T08:00:00+08:00' },
    { record_id: 'r1', scan_date: '2026-08-16', candidate: 'RSV10', f1_result: 'fail', f1_detail: '✗', f2_result: 'pass', f2_detail: '0.55', f3_result: 'na', f3_detail: '', verdict: 'rejected_f1', verdict_text: '未过 F1', nomination_week: '2026-W33', cooldown_until: '2026-11-14', created_at: '2026-08-16T08:00:00+08:00' }
  ];
}
