// 极境 ZenithLens · 入口 v3：初始化 store、路由、首屏拉取（07-frontend-arch §1；09-api-contract v9.1）
import { enableMock, mockEnabled, get, put, loadSlice } from './api.js';
import { getState, getSlice, setPrivacy, applyPrivacyClass, setRoute, subscribe } from './store.js';
import { toast, esc, initDialogs } from './components.js';
import { SESSION_LABEL, localDate } from './format.js';

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
    // C0/E-1：本地时区日期（原 toISOString 为 UTC，00:00–08:00 时段早一天）
    dateEl.textContent = localDate(now) + ' ' + week;
  }
  const sess = document.getElementById('top-session');
  if (sess) sess.textContent = d ? (SESSION_LABEL[d.trade_session] || d.trade_session || '') : '连接中…';
  // 顶部 chip 只表达「服务日期」（runtime.as_of），不与净值快照混称
  const snap = document.getElementById('top-snapshot');
  if (snap) {
    if (d) {
      snap.textContent = '服务日期 ' + (d.as_of || '—');
      snap.className = 'chip' + (d.staleness && d.staleness.is_stale ? ' warn' : '');
    } else { snap.textContent = '服务日期 —'; snap.className = 'chip'; }
  }
  const open = document.getElementById('top-open');
  if (open) open.innerHTML = '本次开口 <b class="mono">' + (d && d.open_count != null ? d.open_count : '—') + '</b> 个信号';
  renderDomains(d);
  renderStaleBanner(d);
  renderLivebar(d);
  if (!sourcesRendered) {
    sourcesRendered = true;
    loadSlice('sources', '/data-sources/health').then(renderLiveSources).catch(function () { renderLiveSources(); });
  }
}

/* ---------- 数据域：服务日期 / 净值快照 / 行情快照（三者互不冒充） ---------- */
function isEngineOnline(status) { return status === 'online' || status === 'running'; }

// 行情快照来自 /engine/status.data_freshness_snapshot_date（ETF/指数 bars 最新日）
function marketSnapshotDate() {
  const sl = getSlice('engineStatus');
  return (sl && sl.data) ? (sl.data.data_freshness_snapshot_date || null) : null;
}

function renderDomains(d) {
  const s = (d && d.staleness) || {};
  const svc = document.getElementById('side-svc');
  const side = document.getElementById('side-date');
  const lag = document.getElementById('side-lag');
  const mkt = document.getElementById('side-market');
  if (svc) svc.textContent = (d && d.as_of) || '—';
  if (side) side.textContent = s.latest_date || '—';
  if (lag) {
    const days = s.days_behind;
    lag.textContent = days ? ('滞后 ' + days + ' 个自然日') : '数据最新';
    lag.style.color = days ? 'var(--gold)' : 'var(--down)';
  }
  if (mkt) mkt.textContent = marketSnapshotDate() || '—';
}

// 陈旧横幅只表达「净值快照滞后」；引擎是否运行由 engine_status 单独决定，二者不再互相冒充。
function renderStaleBanner(d) {
  const stale = document.getElementById('stale-banner');
  if (!stale) return;
  if (!d) { stale.innerHTML = ''; return; }
  const s = d.staleness || {};
  const online = isEngineOnline(d.engine_status);
  const mkt = marketSnapshotDate();
  const navPart = s.latest_date
    ? ('净值快照 ' + esc(s.latest_date) + (s.days_behind ? '（滞后 ' + esc(s.days_behind) + ' 天）' : ''))
    : '';
  const mktPart = mkt ? ('行情快照 ' + esc(mkt)) : '';
  const engPart = online ? '引擎在线' : '引擎未运行';
  if (s.is_stale && navPart) {
    stale.innerHTML = '<div class="stalebar">' + [navPart, mktPart, engPart].filter(Boolean).join(' · ') + '</div>';
  } else if (!online) {
    // 引擎真正离线时，才允许出现「引擎未运行」
    stale.innerHTML = '<div class="stalebar">' + [engPart, mktPart].filter(Boolean).join(' · ') + '</div>';
  } else {
    stale.innerHTML = '';
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
  const live = isEngineOnline(rt.engine_status);
  el.className = 'livebar ' + (live ? 'ok' : 'warn');
  el.innerHTML = '<span class="dot"></span>' + (live
    ? '已接入本地引擎 · 持仓/预测真实数据 · 服务日期 ' + (rt.as_of || '—')
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

/* ---------- 隐私 ---------- */
// S5/BLOCK-A2：启动水合——拉 /settings 恢复两个隐私开关（失败静默，不阻塞、不影响计算）
function hydratePrivacy() {
  get('/settings').then(function (env) {
    const p = env && env.data && env.data.privacy;
    if (p) setPrivacy({ masked: !!p.masked, mask_holdings_only: !!p.mask_holdings_only });
  }).catch(function () { /* 静默：水合失败不影响页面与计算 */ });
}

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
  }
  applyPrivacyClass();
  initDialogs(); // U-10：dialog 焦点回位（Esc 由原生 dialog 处理）
  hydratePrivacy(); // S5/BLOCK-A2：刷新后两开关状态与打码效果保持

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

  // 并行取 服务日期(/runtime) 与 行情快照(/engine/status)；任一到达即重绘顶部数据域
  loadSlice('runtime', '/runtime').then(renderRuntime).catch(function () { renderRuntime(); });
  loadSlice('engineStatus', '/engine/status').then(renderRuntime).catch(function () { renderRuntime(); });

  setInterval(function () { loadSlice('runtime', '/runtime').then(renderRuntime).catch(function () { }); }, 15000);

  syncEye();
  await switchRoute(routeFromHash());
}

function syncEye() {
  const btn = document.getElementById('eye-btn');
  if (btn) btn.textContent = getState().privacy.masked ? '显示金额' : '隐藏金额';
}

document.addEventListener('DOMContentLoaded', function () { boot().catch(function (e) { console.error('[boot]', e); }); });
