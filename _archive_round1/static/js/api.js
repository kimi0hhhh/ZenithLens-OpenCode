// 极境 ZenithLens · 唯一 fetch 出口（07-frontend-arch §7）
// 页面层禁止直接 fetch；一律经本模块。mock 仅在显式开启时注入，默认关闭。
export class ApiError extends Error {
  constructor(code, message, detail) {
    super(message || code);
    this.name = 'ApiError';
    this.code = code || 'E_UNKNOWN';
    this.detail = detail || null;
  }
}

export const BASE = '/api/v1';

const TIMEOUT_DEFAULT = 8000;
const TIMEOUT_LONG = 30000;
// 慢接口例外名单（07 §3.1）：风险指标 / 组合预测 / 全量预测 / 复盘 / 因子 / 引擎重计算
const LONG_PATTERNS = [
  /^\/holdings\/risk/,
  /^\/portfolio\/forecast/,
  /^\/predictions(\?|$)/,
  /^\/review\//,
  /^\/engine\/(ddsm|arena|inputs|training-status)/,
  /^\/factors\//
];

function timeoutFor(path) {
  for (const re of LONG_PATTERNS) if (re.test(path)) return TIMEOUT_LONG;
  return TIMEOUT_DEFAULT;
}

let MOCK = null;
export function enableMock(fn) { MOCK = fn; }
export function mockEnabled() {
  try {
    if (typeof location !== 'undefined' && new URLSearchParams(location.search).get('mock') === '1') return true;
    if (typeof localStorage !== 'undefined' && localStorage.getItem('zl_mock') === '1') return true;
  } catch (e) { /* noop */ }
  return false;
}

export async function request(path, opts) {
  opts = opts || {};
  const method = opts.method || 'GET';
  const body = opts.body || null;
  const timeout = opts.timeout || timeoutFor(path);

  if (MOCK) {
    try {
      return await MOCK(path, { method: method, body: body });
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError('E_UNKNOWN', String(e && e.message || e));
    }
  }

  const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeout) : null;
  let res;
  try {
    res = await fetch(BASE + path, {
      method: method,
      headers: body ? { 'Content-Type': 'application/json; charset=utf-8' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl ? ctrl.signal : undefined
    });
  } catch (e) {
    if (timer) clearTimeout(timer);
    if (e && e.name === 'AbortError') throw new ApiError('E_TIMEOUT', '请求超时');
    throw new ApiError('E_NETWORK', '无法连接本地服务（请经 http://127.0.0.1 访问）');
  }
  if (timer) clearTimeout(timer);

  let env;
  try {
    env = await res.json();
  } catch (e) {
    throw new ApiError('E_PARSE', '返回不是合法 JSON');
  }
  if (!env || env.ok !== true) {
    const err = (env && env.error) || {};
    throw new ApiError(err.code || 'E_UNKNOWN',
      err.message || ('HTTP ' + res.status), err.detail || null);
  }
  return env; // {ok, data, error, as_of}
}

export function get(path, opts) { return request(path, Object.assign({ method: 'GET' }, opts)); }
export function post(path, body, opts) { return request(path, Object.assign({ method: 'POST', body: body }, opts)); }
export function put(path, body, opts) { return request(path, Object.assign({ method: 'PUT', body: body }, opts)); }
export function del(path, opts) { return request(path, Object.assign({ method: 'DELETE' }, opts)); }

// 四态封装：loading -> success/empty/error，写回 store 切片
import { setSlice } from './store.js';

export async function loadSlice(name, path, opts, emptyWhen) {
  setSlice(name, { status: 'loading', error: null });
  try {
    const env = await get(path, opts);
    const data = env.data;
    const isEmpty = typeof emptyWhen === 'function' ? emptyWhen(data) : false;
    setSlice(name, { status: isEmpty ? 'empty' : 'success', data: data, error: null, as_of: env.as_of });
    return data;
  } catch (e) {
    setSlice(name, { status: 'error', data: null, error: { code: e.code, message: e.message }, as_of: null });
    throw e;
  }
}
