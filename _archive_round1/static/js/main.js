// 极境 ZenithLens · 入口：初始化 store、路由、首屏拉取（07-frontend-arch §1）
import { enableMock, mockEnabled, get, put, loadSlice } from './api.js';
import { getState, getSlice, setPrivacy, applyPrivacyClass, setRoute, subscribe } from './store.js';
import { mountState, toast, esc } from './components.js';
import { SESSION_LABEL } from './format.js';

import * as holdings from './views/holdings.js';
import * as analyze from './views/analyze.js';
import * as signals from './views/signals.js';
import * as factors from './views/factors.js';
import * as review from './views/review.js';
import * as engine from './views/engine.js';
import * as settings from './views/settings.js';

const VIEWS = { holdings: holdings, analyze: analyze, signals: signals, factors: factors, review: review, engine: engine, settings: settings };

// R-UI-38 · 注销历史 Service Worker，保证每次最新界面
if ('serviceWorker' in navigator) {
  try { navigator.serviceWorker.getRegistrations().then(function (rs) { rs.forEach(function (r) { r.unregister(); }); }); } catch (e) { /* noop */ }
}
if (window.caches && caches.keys) {
  try { caches.keys().then(function (ks) { ks.forEach(function (k) { caches.delete(k); }); }); } catch (e) { /* noop */ }
}

let current = null;

function routeFromHash() {
  const h = (location.hash || '').replace(/^#\/?/, '');
  return VIEWS[h] ? h : 'holdings';
}

async function switchRoute(name) {
  if (!VIEWS[name]) name = 'holdings';
  if (current && VIEWS[current] && VIEWS[current].deactivate) {
    try { VIEWS[current].deactivate(); } catch (e) { /* noop */ }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.nav button'), function (b) {
    b.classList.toggle('active', b.dataset.v === name);
  });
  Array.prototype.forEach.call(document.querySelectorAll('.view'), function (v) { v.classList.remove('active'); });
  const view = document.getElementById('view-' + name);
  if (view) view.classList.add('active');
  current = name;
  setRoute(name);
  const mod = VIEWS[name];
  if (mod.activate) { try { await mod.activate(); } catch (e) { console.error('[route] activate failed', e); } }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------- 顶栏 / LiveBar（R-UI-39） ---------- */
let sourcesRendered = false;
function renderRuntime() {
  const rt = getSlice('runtime');
  const d = rt.data;
  const dateEl = document.getElementById('top-date');
  if (dateEl) {
    const now = new Date();
    const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][now.getDay()];
    dateEl.textContent = now.toISOString().slice(0, 10) + ' ' + week;
  }
  const sess = document.getElementById('top-session');
  if (sess) sess.textContent = d ? (SESSION_LABEL[d.trade_session] || d.trade_session || '') : '连接中…';
  const snap = document.getElementById('top-snapshot');
  if (snap) {
    if (d && d.staleness) {
      const s = d.staleness;
      snap.textContent = s.is_stale ? ('数据快照 ' + (s.latest_date || '') + ' · 滞后') : ('数据 ' + (d.as_of || '—'));
      snap.className = 'chip' + (s.is_stale ? ' warn' : '');
    } else { snap.textContent = '数据快照 —'; snap.className = 'chip'; }
  }
  const open = document.getElementById('top-open');
  if (open) open.innerHTML = '本次开口 <b class="mono">' + (d && d.open_count != null ? d.open_count : '—') + '</b> 个信号';
  const stale = document.getElementById('stale-banner');
  if (stale) {
    if (d && d.staleness && d.staleness.is_stale) {
      stale.innerHTML = '<div class="stalebar">引擎未运行，展示 ' + esc(d.staleness.latest_date || '') + ' 快照（' + esc(d.staleness.note || '') + '）</div>';
    } else stale.innerHTML = '';
  }
  renderLivebar(d);
  if (!sourcesRendered) {
    sourcesRendered = true;
    loadSlice('sources', '/data-sources/health').then(renderLiveSources).catch(function () { renderLiveSources(); });
  }
}

function renderLivebar(rt) {
  const el = document.getElementById('livebar');
  if (!el) return;
  if (!rt) {
    el.className = 'livebar warn';
    el.innerHTML = '<span class="dot"></span>正在连接本地引擎…（未接入时按四态显示错误/陈旧，不以假数据填充）<span id="live-src"></span>';
    return;
  }
  const live = rt.engine_status === 'online' || rt.engine_status === 'running';
  el.className = 'livebar ' + (live ? 'ok' : 'warn');
  el.innerHTML = '<span class="dot"></span>' + (live
    ? '已接入本地引擎 · 持仓/预测真实数据 · 快照 ' + (rt.as_of || '—')
    : '引擎未运行（' + (rt.engine_status || 'offline') + '）· 持仓/预测按接口四态显示，不以假数据填充') + '<span id="live-src"></span>';
  renderLiveSources();
}

function renderLiveSources() {
  const el = document.getElementById('live-src');
  if (!el) return;
  const sl = getSlice('sources');
  if (sl.status !== 'success' || !sl.data) { el.textContent = ''; return; }
  const bad = (sl.data.sources || []).filter(function (s) { return s.status === 'bad'; });
  el.innerHTML = bad.length ? ' · <span class="up">' + bad.length + ' 个数据源不通</span>' : ' · 数据源正常';
}

/* ---------- R-UI-40 四态演示条 ---------- */
function setDemoState(st) {
  const view = getState().route;
  Array.prototype.forEach.call(document.querySelectorAll('.statebar button'), function (b) {
    b.classList.toggle('on', b.dataset.st === st);
  });
  const root = document.getElementById('view-' + view);
  if (!root) return;
  const slot = root.querySelector('[data-slot]');
  if (st === 'success') {
    root.dataset.state = 'success';
    slot.className = 'state-block'; slot.innerHTML = '';
    if (VIEWS[view] && VIEWS[view].render) VIEWS[view].render();
    return;
  }
  root.dataset.state = st;
  mountState(slot, view, { status: st, error: st === 'error' ? { code: 'E_IO', message: '演示：本地文件不可读' } : null }, function () { setDemoState('success'); });
}

/* ---------- 隐私 ---------- */
function togglePrivacy() {
  const masked = !getState().privacy.masked;
  setPrivacy({ masked: masked });
  put('/settings', { privacy: { masked: masked } }).catch(function () { /* 展示先行，持久化失败不阻塞 */ });
  toast(masked ? '已隐藏金额（占比与涨跌保留）' : '已显示金额');
}

/* ---------- 初始化 ---------- */
async function boot() {
  if (mockEnabled()) {
    const m = await import('./mock/mock.js');
    enableMock(m.mockRequest);
    const badge = document.getElementById('flavor-badge');
    if (badge) badge.textContent += ' · MOCK';
    toast('已启用 mock 演示数据（默认关闭）');
  }
  applyPrivacyClass();

  ['holdings', 'analyze', 'signals', 'factors', 'review', 'engine', 'settings'].forEach(function (v) {
    if (VIEWS[v].init) { try { VIEWS[v].init(); } catch (e) { console.error('[init] ' + v, e); } }
  });

  Array.prototype.forEach.call(document.querySelectorAll('.nav button'), function (b) {
    b.addEventListener('click', function () { location.hash = '#/' + b.dataset.v; });
  });
  window.addEventListener('hashchange', function () { switchRoute(routeFromHash()); });

  const eye = document.getElementById('eye-btn');
  if (eye) eye.addEventListener('click', togglePrivacy);
  subscribe(function (changed) { if (changed === 'privacy') syncEye(); });
  const demo = document.getElementById('statebar-btns');
  if (demo) {
    demo.addEventListener('click', function (e) {
      const b = e.target.closest('button[data-st]');
      if (b) setDemoState(b.dataset.st);
    });
  }

  loadSlice('runtime', '/runtime').then(function () {
    renderRuntime();
    const d = getSlice('runtime').data;
    if (d && d.staleness) {
      const side = document.getElementById('side-date');
      const lag = document.getElementById('side-lag');
      if (side) side.textContent = d.staleness.latest_date || '—';
      if (lag) {
        const days = d.staleness.days_behind;
        lag.textContent = days ? '滞后 ' + days + ' 个自然日' : '数据最新';
        lag.style.color = days ? 'var(--gold)' : 'var(--down)';
      }
    }
  }).catch(function () { renderRuntime(); });

  setInterval(function () { loadSlice('runtime', '/runtime').then(renderRuntime).catch(function () { }); }, 15000);

  syncEye();
  await switchRoute(routeFromHash());
}

function syncEye() {
  const btn = document.getElementById('eye-btn');
  if (btn) btn.textContent = getState().privacy.masked ? '显示金额' : '隐藏金额';
}

document.addEventListener('DOMContentLoaded', function () { boot().catch(function (e) { console.error('[boot]', e); }); });
