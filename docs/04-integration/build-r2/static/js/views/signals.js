// ③ 信号页 —— R-UI-07/08/09（R2：U-03 双变体空态 + U-04 回填态激活 + U-08 QDII 标注 + U-11/U-12）
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, chainHTML, tag, toast, esc, tipAttr } from '../components.js';
import { prob, rate, pp, isNum, md, int } from '../format.js';
import { BACKFILL_METHOD_FALLBACK, BACKFILL_PENDING, LOW_FREQ_FALLBACK, CHAIN_UNAVAILABLE } from '../copy.js';

export function init() {
  const tl = document.getElementById('tl-list');
  if (tl) {
    tl.addEventListener('click', function (e) {
      const card = e.target.closest('.sigcard');
      if (!card) return;
      const ev = card.querySelector('.ev');
      const opening = !card.classList.contains('open');
      card.classList.toggle('open');
      if (opening && card.dataset.date && card.dataset.code && !ev.dataset.loaded) {
        ev.dataset.loaded = '1';
        // S5/BLOCK-A3：按 chain_available 分支——false 明示不可复现（不发请求、不空壳）；true 正常拉链
        if (card.dataset.chain === '0') {
          ev.innerHTML = '<div class="mini">' + CHAIN_UNAVAILABLE + '</div>';
          return;
        }
        get('/ledger/chain?date=' + card.dataset.date + '&code=' + card.dataset.code).then(function (env) {
          ev.innerHTML = chainHTML(env.data && env.data.chain);
        }).catch(function () { ev.innerHTML = '<div class="mini">链路不可读（E_NOT_FOUND / E_IO）</div>'; });
      }
    });
  }
}

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('signalsState', '/signals/state'),
    loadSlice('ledger', '/ledger?limit=60', null, function (d) {
      return !((d && d.rows || []).length);
    })
  ]);
  render();
}

// U-03：页面四态由「信号台账」真实条件驱动；台账为空 = 变体①（从未记录）
function viewState() {
  const ss = getSlice('signalsState');
  const lg = getSlice('ledger');
  if (ss.status === 'error') return { status: 'error', error: ss.error };
  if (lg.status === 'error') return { status: 'error', error: lg.error };
  if (ss.status === 'loading' || ss.status === 'idle' || lg.status === 'loading' || lg.status === 'idle') return { status: 'loading' };
  if (lg.status === 'empty') return { status: 'empty', variant: 'never' };
  return { status: 'success' };
}

export function render() {
  const root = document.getElementById('view-signals');
  const st = viewState();
  const mount = root.querySelector('[data-slot]');
  if (st.status !== 'success') mountState(mount, 'signals', st, activate, st.status === 'empty' ? emptyFacts() : null);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = st.status;
  renderEmpty();
  renderGates();
  renderTimeline();
}

// 变体①事实卡：数字只取接口字段
function emptyFacts() {
  const ss = getSlice('signalsState');
  const d = ss.data || {};
  return [
    ['台账', '0 条（从未记录）'],
    ['已在监控', int(d.monitored_count) + '/' + int(d.total_count) + ' 只'],
    ['滚动开口', isNum(d.rolling_open_assets) ? int(d.rolling_open_assets) + ' 只 / ' + int(d.rolling_window_days) + ' 日' : '—'],
    ['下一步', '运行台账维护任务开始记录']
  ];
}

/* R-UI-07 信号空态：今日无信号（变体②）+ 四要素；今日已开口 → 开口卡 */
function renderEmpty() {
  const el = document.getElementById('sg-empty');
  const sl = getSlice('signalsState');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="card mini">' + (sl.status === 'error' ? '读取信号台账失败' : '—') + '</div>';
    return;
  }
  const d = sl.data;
  const last = d.last_open;
  const isOpen = d.state === 'opened';
  if (isOpen && last) {
    const qdii = last.qdii_lead_note
      ? ' <span class="tag blue" title="' + esc(last.qdii_lead_note) + '">' + esc(last.qdii_lead_note) + '</span>' : '';
    el.innerHTML = '<div class="card"><div class="mini" style="text-align:center;padding:18px 10px">'
      + '<b style="font-size:15px">今日已开口</b><br><span style="color:var(--ink2)">' + esc(last.name || last.code) + qdii + ' · ' + esc(last.gate || '') + '</span></div></div>';
    return;
  }
  // 变体②：有台账但窗口内无开口 → 四要素 + 低频期望说明
  const lowFreq = d.low_frequency_note || LOW_FREQ_FALLBACK;
  const roll = isNum(d.rolling_open_assets)
    ? '近 ' + int(d.rolling_window_days) + ' 交易日开口资产 ' + int(d.rolling_open_assets) + ' 只 · ' : '';
  el.innerHTML = '<div class="card"><div class="mini" style="text-align:center;padding:26px 10px">'
    + '<b style="font-size:15px">今日无信号</b><br><span style="color:var(--ink2)">' + esc(d.empty_note || '这是常态，不是故障。') + '</span>'
    + '<div class="grid4" style="margin-top:18px">'
    + '<div class="factor"><div class="k">已在监控</div><div class="v">' + int(d.monitored_count) + '/' + int(d.total_count) + ' 只</div></div>'
    + '<div class="factor"><div class="k">距上次开口</div><div class="v">' + (d.days_since_last_open == null ? '—' : int(d.days_since_last_open) + ' 个交易日') + '</div></div>'
    + '<div class="factor"><div class="k">上次开口</div><div class="v" style="font-size:13px">' + (last ? esc(md(last.date) + ' ' + (last.name || last.code)) : '—') + '</div></div>'
    + '<div class="factor"><div class="k">上次结果</div><div class="v ' + resultCls(d.last_result) + '" style="font-size:13px">' + resultText(d.last_result, last) + '</div></div>'
    + '</div>'
    + '<div class="mini" style="margin-top:14px">' + esc(roll + lowFreq) + '</div>'
    + '</div></div>';
}

function resultCls(r) { return r === 'hit' ? 'up' : (r === 'miss' ? 'down' : 'flat'); }
function resultText(r, last) {
  const map = { hit: '命中', miss: '未命中', abstain: '弃权', pending: BACKFILL_PENDING };
  const base = map[r] || '—';
  if (last && isNum(last.t1_real)) return base + ' ' + rate(last.t1_real);
  return base;
}

/* R-UI-08 触发门卡 + 剔除说明 + 滚动开口口径（R2-08） */
function renderGates() {
  const el = document.getElementById('sg-gates');
  const xel = document.getElementById('sg-excl');
  const sl = getSlice('signalsState');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = ''; xel.innerHTML = ''; return; }
  const d = sl.data;
  el.innerHTML = (d.gates || []).map(function (g) {
    return '<div class="card"><div style="font-size:13px;font-weight:500;margin-bottom:8px">' + esc(g.label) + ' '
      + (g.role === 'primary' ? tag('主力', 'ok') : '') + '</div>'
      + '<div class="mono" style="font-size:13px;color:var(--ink2)">' + esc(g.formula) + '</div>'
      + '<div class="mini" style="margin-top:8px">' + esc(g.note || '')
      + (isNum(g.effect_pp) ? ' 纯事件效应 ' + pp(g.effect_pp) : '')
      + (isNum(g.t_value) ? '（t=' + (g.t_value >= 0 ? '+' : '') + g.t_value.toFixed(2) + '）' : '') + '</div></div>';
  }).join('');
  const ex = (d.excluded_gates || []).map(function (g) {
    return esc(g.label) + '（' + esc(g.note || '') + (isNum(g.effect_pp) ? '，' + pp(g.effect_pp) : '') + '）';
  }).join('');
  xel.innerHTML = '<div class="card"><div class="mini">已剔除：' + ex
    + '。<b>四类事件' + (d.or_merge_forbidden ? '禁止 OR 合并' : '') + '</b> —— 合并后互相抵消。'
    + (d.low_frequency_note ? '<br>' + esc(d.low_frequency_note) : '') + '</div></div>';
}

/* R-UI-09 信号时间线（U-04：hit/miss 由 result 直读，pending 仅限未到期） */
function renderTimeline() {
  const el = document.getElementById('tl-list');
  const sl = getSlice('ledger');
  if (!sl.data || (sl.status !== 'success' && sl.status !== 'empty')) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '台账不可读' : '正在读取台账…') + '</div>';
    return;
  }
  const rows = sl.data.rows || [];
  if (!rows.length) { el.innerHTML = '<div class="mini">近 60 天无信号</div>'; return; }
  el.innerHTML = rows.map(function (r) {
    // result 为后端字段（ReconcileRow）；/ledger 行若无该键则按契约同一判定式回退，语义一致
    const res = r.result != null ? r.result : (isNum(r.t1_real) ? (r.t1_real > 0 ? 'hit' : 'miss') : 'pending');
    const st = r.signal === 'abstain' ? 'veto' : (res === 'hit' ? 'hit' : (res === 'miss' ? 'miss' : ''));
    const badge = r.signal === 'up' ? tag('涨', 'red') : (r.signal === 'abstain' ? tag('弃权', 'gray') : tag('灰', 'blue'));
    // 回填口径 tooltip：t1_real_method（proxy_bar）+ 回填代理代码（复算锚），未回填不显示
    const methodTip = (res !== 'pending')
      ? BACKFILL_METHOD_FALLBACK + (r.t1_real_method ? '（' + r.t1_real_method + '）' : '')
        + (r.backfill_proxy_code ? ' · 代理 ' + r.backfill_proxy_code : '')
      : '';
    let result;
    if (r.signal === 'abstain') result = '<span class="flat">已弃权</span>';
    else if (res !== 'pending') {
      const val = isNum(r.t1_real) ? rate(r.t1_real) : (r.t1_real_method ? '' : '');
      result = '<span class="' + (res === 'hit' ? 'up' : 'down') + '"' + tipAttr(methodTip) + '>'
        + (val || (res === 'hit' ? '命中' : '未命中')) + '</span>';
    } else result = '<span class="mini" title="未到期，t1_real 未产生">' + BACKFILL_PENDING + '</span>';
    return '<div class="tl-item ' + st + '"><div class="sigcard" data-date="' + esc(r.date) + '" data-code="' + esc(r.code) + '"'
      + ' data-chain="' + (r.chain_available === false ? '0' : '1') + '">'
      + '<div class="sig-head"><span class="sig-date">' + esc(r.date) + '</span>'
      + '<span class="sig-body"><span class="fname">' + esc(r.name || r.code) + '</span><div class="fcode">' + esc(r.code) + ' · ' + esc(r.gate) + ' · ' + esc(r.tier || '') + '</div></span>'
      + '<span class="sig-right">' + badge + '<span class="sig-p">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</span>'
      + '<span class="sig-result">' + result + '</span></span></div>'
      + '<div class="ev" data-slot-chain></div></div></div>';
  }).join('');
}
