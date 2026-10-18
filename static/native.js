// Bridge to the Nova iPhone app (when running inside it instead of Safari).
const handler = window.webkit?.messageHandlers?.nova;
export const isNative = !!handler;
export function post(msg) { try { handler?.postMessage(msg); } catch {} }
export function haptic(style = 'light') { if (handler) post({ type: 'haptic', style }); else navigator.vibrate?.(12); }
window.novaNative = window.novaNative || {};
if (isNative) document.body.classList.add('native');
