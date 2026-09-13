// ③ 信号页 —— R-UI-07/08/09
import { loadSlice, get } from '../api.js';
import { getSlice } from '../store.js';
import { mountState, chainHTML, tag, toast, esc } from '../components.js';
import { prob, rate, pp, isNum, md, int } from '../format.js';

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
    loadSlice('ledger', '/ledger?limit=60')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-signals');
  const sl = getSlice('signalsState');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'signals', sl, activate);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
  renderEmpty();
  renderGates();
  renderTimeline();
}

/* R-UI-07 空态四要素 */
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
    el.innerHTML = '<div class="card"><div class="mini" style="text-align:center;padding:18px 10px">'
      + '<b style="font-size:15px">今日已开口</b><br><span style="color:var(--ink2)">' + esc(last.name || last.code) + ' · ' + esc(last.gate || '') + '</span></div></div>';
    return;
  }
  el.innerHTML = '<div class="card"><div class="mini" style="text-align:center;padding:26px 10px">'
    + '<b style="font-size:15px">今日无信号</b><br><span style="color:var(--ink2)">' + esc(d.empty_note || '这是常态，不是故障。') + '</span>'
    + '<div class="grid4" style="margin-top:18px">'
    + '<div class="factor"><div class="k">已在监控</div><div class="v">' + int(d.monitored_count) + '/' + int(d.total_count) + ' 只</div></div>'
    + '<div class="factor"><div class="k">距上次开口</div><div class="v">' + (d.days_since_last_open == null ? '—' : int(d.days_since_last_open) + ' 个交易日') + '</div></div>'
    + '<div class="factor"><div class="k">上次开口</div><div class="v" style="font-size:13px">' + (last ? esc(md(last.date) + ' ' + (last.name || last.code)) : '—') + '</div></div>'
    + '<div class="factor"><div class="k">上次结果</div><div class="v ' + resultCls(d.last_result) + '" style="font-size:13px">' + resultText(d.last_result, last) + '</div></div>'
    + '</div></div></div>';
}

function resultCls(r) { return r === 'hit' ? 'up' : (r === 'miss' ? 'down' : 'flat'); }
function resultText(r, last) {
  const map = { hit: '命中', miss: '未命中', abstain: '弃权', pending: '待回填' };
  const base = map[r] || '—';
  if (last && isNum(last.t1_real)) return base + ' ' + rate(last.t1_real);
  return base;
}

/* R-UI-08 触发门卡 + 剔除说明 */
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
  }).join('；');
  xel.innerHTML = '<div class="card"><div class="mini">已剔除：' + ex
    + '。<b>四类事件' + (d.or_merge_forbidden ? '禁止 OR 合并' : '') + '</b> —— 合并后互相抵消。</div></div>';
}

/* R-UI-09 信号时间线 */
function renderTimeline() {
  const el = document.getElementById('tl-list');
  const sl = getSlice('ledger');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '台账不可读' : '正在读取台账…') + '</div>';
    return;
  }
  const rows = sl.data.rows || [];
  if (!rows.length) { el.innerHTML = '<div class="mini">近 60 天无信号</div>'; return; }
  el.innerHTML = rows.map(function (r) {
    const st = r.signal === 'abstain' ? 'veto' : (isNum(r.t1_real) ? (r.t1_real > 0 ? 'hit' : 'miss') : '');
    const badge = r.signal === 'up' ? tag('涨', 'red') : (r.signal === 'abstain' ? tag('弃权', 'gray') : tag('灰', 'blue'));
    let result;
    if (r.signal === 'abstain') result = '<span class="flat">已弃权</span>';
    else if (isNum(r.t1_real)) result = '<span class="' + (r.t1_real > 0 ? 'up' : 'down') + '">' + rate(r.t1_real) + '</span>';
    else result = '<span class="mini">待回填</span>';
    return '<div class="tl-item ' + st + '"><div class="sigcard" data-date="' + esc(r.date) + '" data-code="' + esc(r.code) + '">'
      + '<div class="sig-head"><span class="sig-date">' + esc(r.date) + '</span>'
      + '<span class="sig-body"><span class="fname">' + esc(r.name || r.code) + '</span><div class="fcode">' + esc(r.code) + ' · ' + esc(r.gate) + ' · ' + esc(r.tier || '') + '</div></span>'
      + '<span class="sig-right">' + badge + '<span class="sig-p">' + (isNum(r.p_up) ? r.p_up.toFixed(4) : '—') + '</span>'
      + '<span class="sig-result">' + result + '</span></span></div>'
      + '<div class="ev" data-slot-chain></div></div></div>';
  }).join('');
}
