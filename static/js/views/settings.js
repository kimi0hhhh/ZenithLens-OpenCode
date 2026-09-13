// ⑦ 设置页 —— R-UI-32/33/34/35/36（R2：U-03 空态=尚未检测 + U-06 时间窗计数/新浪实测/主源口径 + U-11/U-12）
import { loadSlice, get, post, put } from '../api.js';
import { getSlice, setPrivacy } from '../store.js';
import { mountState, tag, toast, esc, tipAttr } from '../components.js';
import { timeHM, dateTimeShort, int, isNum } from '../format.js';
import { METRIC_TIP, LLM_CHECK_MISSING, LLM_CHECK_BAD_URL, LLM_CHECK_OK, LLM_CHECK_BUTTON_TITLE, PRIVACY_SUB_ON, PRIVACY_SUB_OFF, REGISTRY_PROVISIONAL_NOTE } from '../copy.js';

export function init() {
  const sw = document.getElementById('sw-hide');
  if (sw) sw.addEventListener('change', function () { savePrivacy(sw.checked); });
  const swH = document.getElementById('sw-hide-holdings');
  if (swH) swH.addEventListener('change', function () { savePrivacy(null, swH.checked); });

  bind('llm-provider', 'change', function () { llmPreset(this.value); });
  bind('llm-test', 'click', function () { probe('llm'); });
  // S5/BLOCK-A1：按钮语义标注「本地校验」（不发起网络请求）
  const llmTestBtn = document.getElementById('llm-test');
  if (llmTestBtn) llmTestBtn.title = LLM_CHECK_BUTTON_TITLE;
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

// U-03：设置页空态真实条件 = 数据源从未检测（health 行全为 unchecked 或无行）
function neverChecked() {
  const src = getSlice('sources');
  if (src.status !== 'success' || !src.data) return false;
  const rows = src.data.sources || [];
  return !rows.length || rows.every(function (s) { return s.status === 'unchecked' && !s.last_ok_at; });
}

function viewState() {
  const st = getSlice('settings');
  const src = getSlice('sources');
  if (st.status === 'error') return { status: 'error', error: st.error };
  if (st.status === 'loading' || st.status === 'idle' || src.status === 'loading' || src.status === 'idle') return { status: 'loading' };
  if (st.status === 'success' && neverChecked()) return { status: 'empty' };
  return { status: 'success' };
}

function stateRetry(reason) {
  if (reason === 'empty') { probeSources(); return; }
  activate();
}

export function render() {
  const root = document.getElementById('view-settings');
  const st = viewState();
  const mount = root.querySelector('[data-slot]');
  if (st.status !== 'success') mountState(mount, 'settings', st, stateRetry);
  else { mount.className = 'state-block'; mount.innerHTML = ''; }
  root.dataset.state = st.status;
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
    // S5/BLOCK-A2：toast 按本次操作的开关分支
    if (masked != null) toast(p.masked ? '已隐藏金额（占比与涨跌保留）' : '已显示金额');
    else toast(p.mask_holdings_only ? PRIVACY_SUB_ON : PRIVACY_SUB_OFF);
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

// S5/BLOCK-A1：诚实降级——「测试连接」改为本地校验，不发起任何网络请求
// （真连通性探测端点列入架构裁定 C1；契约未定义此前端不得擅调）
function probe(what) {
  if (what !== 'llm') return;
  const provider = (document.getElementById('llm-provider') || {}).value || '';
  const model = (document.getElementById('llm-model').value || '').trim();
  const url = (document.getElementById('llm-url').value || '').trim();
  const keyInput = (document.getElementById('llm-key').value || '').trim();
  const sl = getSlice('settings');
  const apiKeySet = !!(sl.data && sl.data.llm && sl.data.llm.api_key_set);
  if (!provider || !model || !url || (!keyInput && !apiKeySet)) { toast(LLM_CHECK_MISSING); return; }
  if (!/^https?:\/\/.+/.test(url)) { toast(LLM_CHECK_BAD_URL); return; }
  toast(LLM_CHECK_OK);
}

/* ---------- R-UI-34 数据源健康（U-06：失败计数=近 7 日时间窗；历史折叠；sina 实测行随后端留痕） ---------- */
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
    const fail7 = isNum(s.fail_window_7d) ? s.fail_window_7d : null;
    const days = isNum(s.fail_window_days) ? s.fail_window_days : 7;
    const failures = Array.isArray(s.recent_failures) ? s.recent_failures : [];
    // 累计 fail_count 只允许出现在历史折叠区（C1：不得再作当前状态展示）
    const fold = (failures.length || isNum(s.fail_count))
      ? '<details class="srcfold"><summary>历史失败（累计 ' + int(s.fail_count) + ' 次 · 审计用）</summary>'
        + (failures.length
          ? failures.map(function (f) { return '<div class="mini mono">' + esc(f.at || '—') + ' · ' + esc(f.note || '') + '</div>'; }).join('')
          : '<div class="mini">近 ' + int(days) + ' 日无失败记录</div>')
        + '</details>'
      : '';
    return '<div class="kv"><span class="k">' + esc(s.label || s.source_id)
      + (s.note ? '<div class="mini" style="margin-top:3px">' + esc(s.note) + '</div>' : '') + fold + '</span>'
      + '<span style="display:flex;align-items:center;gap:12px">' + tag(t[0], t[1])
      + '<span class="mini mono">' + (s.last_ok_at ? dateTimeShort(s.last_ok_at) : '—') + '</span>'
      + '<span class="mini ' + (fail7 ? 'down' : '') + '"' + tipAttr(METRIC_TIP.fail_window) + '>'
      + (fail7 != null ? '近 ' + int(days) + ' 日失败 ' + int(fail7) + ' 次' : '近 ' + int(days) + ' 日失败 —') + '</span>'
      + (isNum(s.latency_ms) ? '<span class="mini mono">' + int(s.latency_ms) + 'ms</span>' : '') + '</span></div>';
  }).join('');
}

function probeSources() {
  document.getElementById('src-box').innerHTML = '<div class="mini"><span class="pulse"></span>检测中…</div>';
  post('/data-sources/probe', { source_id: null }).then(function () {
    setTimeout(function () {
      loadSlice('sources', '/data-sources/health').then(function () { renderSources(); render(); }).catch(function () { });
    }, 1200);
  }).catch(function (e) { toast('检测失败：' + e.message); renderSources(); });
}

/* ---------- R-UI-27 引擎注册表（设置页复用） ---------- */
function renderRegistry() {
  const tbody = document.getElementById('st-registry');
  if (!tbody) return;
  // C2 裁定（§11.2）：单版本现实 + 预留态标注（文案取 copy.js 字典）
  const noteEl = document.getElementById('st-registry-note');
  if (noteEl) noteEl.textContent = REGISTRY_PROVISIONAL_NOTE;
  const sl = getSlice('registry');
  if (sl.status !== 'success' || !sl.data) { tbody.innerHTML = '<tr><td colspan="3" class="mini">' + (sl.status === 'error' ? '注册表读取失败' : '—') + '</td></tr>'; return; }
  tbody.innerHTML = (sl.data.engines || []).map(function (r) {
    return '<tr><td class="mono">' + esc(r.version) + '</td><td>' + tag(r.status, r.status === 'active' ? 'ok' : 'gray') + '</td>'
      + '<td class="mini">' + esc(r.note || '') + '</td></tr>';
  }).join('') || '<tr><td colspan="3" class="mini">尚无注册版本</td></tr>';
}

/* ---------- R-UI-35 持仓数据（U-06/B6：主源读 main_source；导入按钮按 import_available 禁用） ---------- */
function renderHoldingsData() {
  const el = document.getElementById('hd-data');
  const note = document.getElementById('hd-diff');
  const sl = getSlice('holdingsData');
  if (sl.status !== 'success' || !sl.data) {
    el.innerHTML = '<div class="mini">' + (sl.status === 'error' ? '读取数据文件失败' : '主源 data/holdings.json 缺失') + '</div>';
    if (note) note.innerHTML = '';
    return;
  }
  const d = sl.data;
  const ms = d.main_source || null;
  const mainPath = (ms && ms.path) || 'data/holdings.json';
  const mainCount = ms ? ms.count : d.primary_count;
  const mainModified = ms ? ms.modified_at : d.primary_modified_at;
  const importAvail = d.import_available !== false;
  const importWhy = d.import_disabled_reason || '';
  el.innerHTML = '<div class="kv"><span class="k">当前主源（产品自持）</span><span class="mono">' + esc(mainPath)
    + (ms && ms.exists === false ? '（缺失，请导入）' : '') + '</span></div>'
    + '<div class="kv"><span class="k">持仓只数</span><span class="mono">' + int(mainCount) + ' 只</span></div>'
    + '<div class="kv"><span class="k">最近同步</span><span class="mono">' + (mainModified ? dateTimeShort(mainModified) : '—') + '</span></div>'
    + '<div class="kv"><span class="k">只读</span><span>' + ((ms ? ms.readonly : d.readonly) ? tag('只读，不改写源文件', 'blue') : '') + '</span></div>'
    + '<div class="kv"><span class="k">外部导入源（可选）</span><span style="display:flex;align-items:center;gap:10px;text-align:right">'
    + (importAvail ? tag('可用', 'ok') : tag('不可用（按钮已禁用）', 'gray'))
    + (importWhy ? '<span class="mini" style="max-width:420px">' + esc(importWhy) + '</span>' : '') + '</span></div>'
    + '<div class="kv"><span class="k">两份一致性（估值≠净值实证）</span><span>' + (d.consistent ? tag('一致', 'ok') : tag('不一致', 'red'))
    + (d.diff_fields && d.diff_fields.length ? ' <span class="mini mono">' + esc(d.diff_fields.join(', ')) + '</span>' : '') + '</span></div>';
  // 导入按钮可用性由后端 import_available 驱动（false → 禁用 + reason 直出，不裸报 E_IO）
  const btn = document.getElementById('hd-import');
  if (btn) {
    btn.disabled = !importAvail;
    btn.title = importWhy || '';
  }
  if (note) note.innerHTML = esc(d.diff_note || '') + (d.checked_at ? '<br><span style="color:var(--ink3)">检查于 ' + esc(d.checked_at) + '</span>' : '');
}

function importHoldings() {
  const sl = getSlice('holdingsData');
  const d = sl.data || {};
  if (d.import_available === false) {
    toast(d.import_disabled_reason || '外部导入源不可用');
    return;
  }
  post('/holdings/import', { mode: 'replace' }).then(function (env) {
    const res = env.data || {};
    toast('已导入 ' + int(res.imported_count) + ' 只（源：' + (res.source || '') + '）');
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
