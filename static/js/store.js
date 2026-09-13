// 极境 ZenithLens · 单一 store + 订阅（依据 07-frontend-arch §3，约 60 行原生实现）
// 每个数据切片自带四态：idle | loading | success | empty | error
const state = {
  route: 'holdings',
  privacy: { masked: false, mask_holdings_only: false },
  runtime: null,
  engineStatus: null,
  slices: {}
};

const listeners = [];

export function getState() {
  return state;
}

export function getSlice(name) {
  return state.slices[name] || { status: 'idle', data: null, error: null, as_of: null };
}

export function setSlice(name, patch) {
  state.slices[name] = Object.assign({ status: 'idle', data: null, error: null, as_of: null }, getSlice(name), patch);
  emit(name);
}

export function setPrivacy(patch) {
  Object.assign(state.privacy, patch);
  applyPrivacyClass();
  emit('privacy');
}

// S5/BLOCK-A2：主开关 masked → 全站 .amt；副开关 mask-holdings-only → 仅明细行（汇总保留）
// 两 class 独立 toggle（主开关开启时副开关不再产生额外效果，CSS 以 body.masked 兜底）
export function applyPrivacyClass() {
  if (typeof document === 'undefined') return;
  document.body.classList.toggle('masked', !!state.privacy.masked);
  document.body.classList.toggle('mask-holdings-only', !!state.privacy.mask_holdings_only);
}

export function setRoute(route) {
  state.route = route;
  emit('route');
}

export function subscribe(fn) {
  listeners.push(fn);
  return function unsubscribe() {
    const i = listeners.indexOf(fn);
    if (i >= 0) listeners.splice(i, 1);
  };
}

function emit(changed) {
  listeners.forEach(function (fn) {
    try { fn(changed); } catch (e) { console.error('[store] listener error', e); }
  });
}
