// ⑦ 设置页 —— R-UI-32/33/34/35/36
import { loadSlice, get, post, put } from '../api.js';
import { getSlice, setPrivacy } from '../store.js';
import { mountState, tag, toast, esc } from '../components.js';
import { timeHM, dateTimeShort, int, isNum } from '../format.js';

export function init() {
  const sw = document.getElementById('sw-hide');
  if (sw) sw.addEventListener('change', function () { savePrivacy(sw.checked); });
  const swH = document.getElementById('sw-hide-holdings');
  if (swH) swH.addEventListener('change', function () { savePrivacy(null, swH.checked); });

  bind('llm-provider', 'change', function () { llmPreset(this.value); });
  bind('llm-test', 'click', function () { probe('llm'); });
  bind('llm-save', 'click', saveLlm);
  bind('llm-toggle-key', 'click', toggleKey);
  bind('src-probe', 'click', function () { probeSources(); });
  bind('hd-import', 'click', function () { importHoldings(); });
}

function bind(id, ev, fn) { const el = document.getElementById(id); if (el) el.addEventListener(ev, fn); }

export async function activate() {
  render();
  await Promise.allSettled([
    loadSlice('settings', '/settings'),
    loadSlice('sources', '/data-sources/health'),
    loadSlice('registry', '/engine/registry'),
    loadSlice('holdingsData', '/settings/holdings-data'),
    loadSlice('about', '/about')
  ]);
  render();
}

export function render() {
  const root = document.getElementById('view-settings');
  const sl = getSlice('settings');
  const mount = root.querySelector('[data-slot]');
  if (sl.status !== 'success') mountState(mount, 'settings', sl, activate);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = sl.status === 'success' ? 'success' : sl.status;
  renderPrivacy();
  renderLlm();
  renderSources();
  renderRegistry();
  renderHoldingsData();
  renderAbout();
}

/* ---------- R-UI-32 隐私 ---------- */
function renderPrivacy() {
  const sl = getSlice('settings');
  const sw = document.getElementById('sw-hide');
  const swH = document.getElementById('sw-hide-holdings');
  if (sl.status !== 'success' || !sl.data) return;
  const p = sl.data.privacy || {};
  if (sw) sw.checked = !!p.masked;
  if (swH) swH.checked = !!p.mask_holdings_only;
}

function savePrivacy(masked, holdingsOnly) {
  const sl = getSlice('settings');
  const cur = (sl.data && sl.data.privacy) || {};
  const patch = { privacy: { masked: masked == null ? !!cur.masked : masked, mask_holdings_only: holdingsOnly == null ? !!cur.mask_holdings_only : holdingsOnly } };
  put('/settings', patch).then(function (env) {
    const p = (env.data && env.data.privacy) || patch.privacy;
    setPrivacy(p);
    if (getSlice('settings').data) getSlice('settings').data.privacy = p;
    toast(p.masked ? '已隐藏金额（占比与涨跌保留）' : '已显示金额');
  }).catch(function (e) { toast('保存配置失败：' + e.message); });
}

/* ---------- R-UI-33 LLM ---------- */
const PRESETS = {
  deepseek: { u: 'https://api.deepseek.com/v1', m: 'deepseek-chat' },
  qwen: { u: 'https://dashscope.aliyuncs.com/compatible-mode/v1', m: 'qwen-plus' },
  moonshot: { u: 'https://api.moonshot.cn/v1', m: 'moonshot-v1-8k' },
  custom: { u: '', m: '' }
};

function renderLlm() {
  const sl = getSlice('settings');
  if (sl.status !== 'success' || !sl.data) return;
  const l = sl.data.llm || {};
  const prov = document.getElementById('llm-provider');
  if (prov && l.provider) prov.value = l.provider;
  const model = document.getElementById('llm-model');
  if (model && l.model) model.value = l.model;
  const url = document.getElementById('llm-url');
  if (url && l.base_url) url.value = l.base_url;
  const key = document.getElementById('llm-key');
  if (key) key.placeholder = l.api_key_set ? '已设置（不回显）' : 'sk-…';
  const st = document.getElementById('llm-status');
  if (st) st.innerHTML = '<b style="color:var(--gold)">当前状态：' + esc(l.mode || 'shadow') + ' 观察区。</b>温度固定 ' + esc(String(l.temperature != null ? l.temperature : 0)) + '、输出 ' + esc(l.output_format || 'json') + '。';
}

function llmPreset(v) {
  const p = PRESETS[v]; if (!p) return;
  document.getElementById('llm-url').value = p.u;
  document.getElementById('llm-model').value = p.m;
}

function saveLlm() {
  const body = { llm: {
    provider: document.getElementById('llm-provider').value,
    model: document.getElementById('llm-model').value,
    base_url: document.getElementById('llm-url').value
  } };
  const key = document.getElementById('llm-key').value;
  if (key) body.llm.api_key = key;
  put('/settings', body).then(function (env) {
    toast('配置已保存（Key 不回显）');
    const l = env.data && env.data.llm;
    if (l) getSlice('settings').data.llm = l;
    document.getElementById('llm-key').value = '';
    renderLlm();
  }).catch(function (e) { toast('保存配置失败：' + e.message); });
}

function toggleKey() {
  const i = document.getElementById('llm-key');
  const show = i.type === 'password';
  i.type = show ? 'text' : 'password';
  document.getElementById('llm-toggle-key').textContent = show ? '隐藏' : '显示';
}

function probe(what) {
  if (what === 'llm') { toast('已发起连接测试（异步任务）'); return; }
}

/* ---------- R-UI-34 数据源健康 ---------- */
const SRC_STATUS = { ok: ['正常', 'ok'], warn: ['波动', 'warn'], bad: ['不通', 'red'], unchecked: ['未检测', 'gray'] };
function renderSources() {
  const el = document.getElementById('src-box');
  const sl = getSlice('sources');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '检测失败' : '尚未检测数据源') + '</div>';
    return;
  }
  const rows = sl.data.sources || [];
  if (!rows.length) { el.innerHTML = '<div class="mini">尚未检测数据源</div>'; return; }
  el.innerHTML = rows.map(function (s) {
    const t = SRC_STATUS[s.status] || SRC_STATUS.unchecked;
    return '<div class="kv"><span class="k">' + esc(s.label || s.source_id) + '</span>'
      + '<span style="display:flex;align-items:center;gap:12px">' + tag(t[0], t[1])
      + '<span class="mini mono">' + (s.last_ok_at ? dateTimeShort(s.last_ok_at) : '—') + '</span>'
      + '<span class="mini ' + (s.fail_count ? 'down' : '') + '">失败 ' + int(s.fail_count) + '</span>'
      + (isNum(s.latency_ms) ? '<span class="mini mono">' + int(s.latency_ms) + 'ms</span>' : '') + '</span></div>';
  }).join('');
}

function probeSources() {
  document.getElementById('src-box').innerHTML = '<div class="mini"><span class="pulse"></span>检测中…</div>';
  post('/data-sources/probe', { source_id: null }).then(function () {
    setTimeout(function () { loadSlice('sources', '/data-sources/health').then(renderSources).catch(function () { }); }, 1200);
  }).catch(function (e) { toast('检测失败：' + e.message); renderSources(); });
}

/* ---------- R-UI-27 引擎注册表（设置页复用） ---------- */
function renderRegistry() {
  const tbody = document.getElementById('st-registry');
  if (!tbody) return;
  const sl = getSlice('registry');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="3" class="mini">' + (sl.status === 'error' ? '注册表读取失败' : '—') + '</td></tr>'; return; }
  tbody.innerHTML = (sl.data.engines || []).map(function (r) {
    return '<tr><td class="mono">' + esc(r.version) + '</td><td>' + tag(r.status, r.status === 'active' ? 'ok' : 'gray') + '</td>'
      + '<td class="mini">' + esc(r.note || '') + '</td></tr>';
  }).join('') || '<tr><td colspan="3" class="mini">尚无注册版本</td></tr>';
}

/* ---------- R-UI-35 持仓数据 ---------- */
function renderHoldingsData() {
  const el = document.getElementById('hd-data');
  const note = document.getElementById('hd-diff');
  const sl = getSlice('holdingsData');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '读取数据文件失败' : '未找到 funds_data.json') + '</div>';
    if (note) note.innerHTML = '';
    return;
  }
  const d = sl.data;
  el.innerHTML = '<div class="kv"><span class="k">当前数据源</span><span class="mono">' + esc(d.primary_path) + '</span></div>'
    + '<div class="kv"><span class="k">持仓只数</span><span class="mono">' + int(d.primary_count) + ' 只</span></div>'
    + '<div class="kv"><span class="k">最近修改</span><span class="mono">' + (d.primary_modified_at ? dateTimeShort(d.primary_modified_at) : '—') + '</span></div>'
    + '<div class="kv"><span class="k">旧位置文件</span><span class="mono">' + (d.legacy_exists ? esc(d.legacy_path) : '不存在') + '</span></div>'
    + '<div class="kv"><span class="k">两份一致性</span><span>' + (d.consistent ? tag('一致', 'ok') : tag('不一致', 'red'))
    + (d.diff_fields && d.diff_fields.length ? ' <span class="mini mono">' + esc(d.diff_fields.join(', ')) + '</span>' : '') + '</span></div>'
    + '<div class="kv"><span class="k">只读</span><span>' + (d.readonly ? tag('只读，不改写源文件', 'blue') : '') + '</span></div>';
  if (note) note.innerHTML = esc(d.diff_note || '') + (d.checked_at ? '<br><span style="color:var(--ink3)">检查于 ' + esc(d.checked_at) + '</span>' : '');
}

function importHoldings() {
  post('/holdings/import', { mode: 'replace' }).then(function (env) {
    const d = env.data || {};
    toast('已导入 ' + int(d.imported_count) + ' 只（源：' + (d.source || '') + '）');
    loadSlice('holdingsData', '/settings/holdings-data').then(renderHoldingsData).catch(function () { });
    loadSlice('holdings', '/holdings?with=valuation,nav,prediction').catch(function () { });
  }).catch(function (e) { toast('导入失败：' + e.message); });
}

/* ---------- R-UI-36 关于 ---------- */
function renderAbout() {
  const el = document.getElementById('about-card');
  const sl = getSlice('about');
  if (sl.status !== 'success' || !sl.data) { el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '关于信息读取失败' : '—') + '</div>'; return; }
  const d = sl.data;
  el.innerHTML = '<div class="kv"><span class="k">产品</span><span class="mono">' + esc(d.product_name) + ' ' + esc(d.version) + '</span></div>'
    + '<div class="kv"><span class="k">引擎</span><span class="mono">Python ' + esc(d.python_min) + '+ 纯标准库</span></div>'
    + '<div class="kv"><span class="k">部署</span><span class="mono">' + esc(d.deployment) + '</span></div>'
    + '<div class="kv"><span class="k">存储</span><span class="mono">' + esc(d.storage_note) + '</span></div>'
    + '<div class="kv"><span class="k">审计</span><span class="mono">台账 INSERT-ONLY</span></div>'
    + '<div class="kv"><span class="k">免责</span><span class="mini" style="text-align:right">' + esc(d.disclaimer) + '</span></div>';
}
