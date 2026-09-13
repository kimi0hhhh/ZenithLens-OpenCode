// 极境 ZenithLens · 唯一数字格式化出口（v3）
// 口径唯一来源：docs/01-architecture/09-api-contract-r2.md v9.1 §2（沿用 v8 §1.2）
// 组件不得各自实现百分比逻辑（避免 12.42% vs 0.1242 分叉）。
import { getState } from './store.js';

export function isNum(v) {
  return typeof v === 'number' && !Number.isNaN(v) && Number.isFinite(v);
}

function grouped(v, d) {
  return v.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d });
}

// 金额：¥ + 千分位 + 2 位；未知返回 —
export function amt(v) {
  if (!isNum(v)) return '—';
  return '¥' + grouped(v, 2);
}

// 概率 *_p：[0,1] -> 58.3%
export function prob(v) {
  if (!isNum(v)) return '—';
  return (v * 100).toFixed(1) + '%';
}

// 比率 *_rate / *_ratio / pct：0.0124 -> +1.24%（带符号）
export function rate(v) {
  if (!isNum(v)) return '—';
  return (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%';
}

// 不带符号的比率（用于误差/离散度等，展示 2 位）
export function rateU(v) {
  if (!isNum(v)) return '—';
  return (v * 100).toFixed(2) + '%';
}

// 百分点 delta_pp（小数比率口径）：0.099 -> +9.9pp
export function delta(v) {
  if (!isNum(v)) return '—';
  return (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + 'pp';
}

// 百分点 effect_pp（契约 §5.21 单位已是百分点）：3.9 -> +3.90pp，禁止再 ×100
export function pp(v, d) {
  if (!isNum(v)) return '—';
  return (v >= 0 ? '+' : '') + v.toFixed(d == null ? 2 : d) + 'pp';
}

// 倍数 lift：1.06 -> 1.06
export function lift(v, d) {
  if (!isNum(v)) return '—';
  return v.toFixed(d == null ? 2 : d);
}

// 分数/得分：保留 d 位（默认 1），带符号
export function score(v, d) {
  if (!isNum(v)) return '—';
  const s = v.toFixed(d == null ? 1 : d);
  return v > 0 ? '+' + s : s;
}

export function num(v, d) {
  if (!isNum(v)) return '—';
  return grouped(v, d == null ? 2 : d);
}

// 份额 4 位
export function shares(v) {
  if (!isNum(v)) return '—';
  return grouped(v, 4);
}

// 净值/价格 4 位
export function nav(v) {
  if (!isNum(v)) return '—';
  return grouped(v, 4);
}

// z 值 3 位，带符号
export function z(v) {
  if (!isNum(v)) return '—';
  return (v >= 0 ? '+' : '') + v.toFixed(3);
}

// 整数（无小数的计数）
export function int(v) {
  if (!isNum(v)) return '—';
  return String(Math.round(v));
}

// 涨跌配色类：正 -> up(红)，负 -> down(绿)，零 -> flat
export function cls(v) {
  if (!isNum(v)) return 'flat';
  return v > 0 ? 'up' : (v < 0 ? 'down' : 'flat');
}

// 涨跌配色（带符号字符串，用于 text）
export function signedRate(v) {
  if (!isNum(v)) return '—';
  return rate(v);
}

export function dateStr(v) {
  return v == null || v === '' ? '—' : String(v);
}

// C0/E-1：本地时区日期 YYYY-MM-DD（顶栏日期不得用 toISOString 的 UTC 日期；
// 本地 00:00–08:00 时段 UTC 日期会早一天，与 getDay() 本地星期错配）
export function localDate(d) {
  const dt = (d instanceof Date) ? d : new Date();
  const p = function (n) { return String(n).padStart(2, '0'); };
  return dt.getFullYear() + '-' + p(dt.getMonth() + 1) + '-' + p(dt.getDate());
}

// ISO 时间戳 -> 本地 HH:mm（Asia/Shanghai）
export function timeHM(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return hh + ':' + mm;
}

export function dateTimeShort(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const M = String(d.getMonth() + 1).padStart(2, '0');
  const D = String(d.getDate()).padStart(2, '0');
  return M + '-' + D + ' ' + timeHM(iso);
}

// 'YYYY-MM-DD' -> 'MM-DD'
export function md(date) {
  if (!date) return '—';
  const s = String(date);
  return s.length >= 10 ? s.slice(5, 10) : s;
}

export const SESSION_LABEL = {
  pre_open: '盘前',
  trading: '盘中',
  closed: '收盘后',
  non_trading_day: '非交易日'
};

export const GATE_LABEL = { E1: '跳空', E3: '无量急跌', none: '未触发' };
export const SIGNAL_LABEL = { up: '涨', gray: '灰', abstain: '弃权' };
export const TIER_ORDER = ['A', 'B', 'C', 'D'];
export const FACTOR_WINDOWS = ['d15', 'd30', 'd60', 'm6', 'm24', 'full'];
export const FACTOR_WINDOW_LABEL = {
  d15: '15日', d30: '30日', d60: '60日', m6: '6月', m24: '24月', full: '全样本'
};

// 隐私打码只作用于展示；此处只判断金额是否应包 amt 类（样式层负责打码）
export function isMasked() {
  return !!getState().privacy.masked;
}
