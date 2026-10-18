// Screen tab: watch and control the PC from the phone.
//  tap = click · double-tap = double-click · long-press = right-click
//  long-press then move = drag · two fingers = zoom & pan · Scroll mode = one finger scrolls
import { haptic, post, isNative } from './native.js';
import { t } from './i18n.js';
const $ = s => document.querySelector(s);

export function createRemote({ getToken, onStopAgent, onBack }) {
  const vp = $('#viewport'), cv = $('#rcanvas'), ctx = cv.getContext('2d'), msg = $('#rmsg');
  let ws = null, active = false, meta = null, locked = false, retry = 0, retryTimer = null;
  let hd = localStorage.getItem('nova_hd') === '1';
  let screen = +(localStorage.getItem('nova_screen') || 1);
  let scrollMode = false, rightNext = false;
  // view transform: base fit + user zoom/pan
  let base = { x: 0, y: 0, w: 0, h: 0 }, zoom = 1, tx = 0, ty = 0;

  // ---------- connection ----------
  function connect() {
    clearTimeout(retryTimer);
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/remote?token=${encodeURIComponent(getToken())}&screen=${screen}`);
    ws.binaryType = 'blob';
    showMsg(t('Connecting to your PC…'));
    ws.onopen = () => { retry = 0; sendOpts(); };
    ws.onmessage = async e => {
      if (typeof e.data === 'string') {
        const m = JSON.parse(e.data);
        if (m.type === 'meta') { const changed = !meta || meta.w !== m.w || meta.h !== m.h; meta = m; screen = m.screen; setLocked(m.locked); renderScreens(); if (changed) { zoom = 1; tx = 0; ty = 0; } layout(); }
        if (m.type === 'locked') setLocked(m.value);
        return;
      }
      try {
        const bmp = await createImageBitmap(e.data);
        if (cv.width !== bmp.width || cv.height !== bmp.height) { cv.width = bmp.width; cv.height = bmp.height; }
        ctx.drawImage(bmp, 0, 0); bmp.close?.();
        showMsg(null);
      } catch {}
      if (ws && ws.readyState === 1) ws.send('{"t":"next"}');   // ask for the next frame only when ready
    };
    ws.onclose = e => {
      ws = null;
      if (!active) return;
      if (e.code === 4403) return showMsg(t('Screen sharing is turned off on your PC.\nTurn on “Screen tab on iPhone” in Nova’s settings.'));
      if (e.code === 4401) return showMsg(t('Please reconnect: open the Chat tab and sign in again.'));
      showMsg(t('Reconnecting…'));
      retryTimer = setTimeout(connect, Math.min(800 * 2 ** retry++, 6000));
    };
  }
  const send = obj => { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); };
  function sendOpts() {
    const w = hd ? Math.min(2560, Math.round(vp.clientWidth * (window.devicePixelRatio || 2) * Math.max(zoom, 1.6))) : 1280;
    send({ t: 'opts', w: Math.max(960, w), q: hd ? 72 : 55 });
  }
  // ---------- multiple monitors ----------
  const screensEl = $('#screens');
  function renderScreens() {
    const list = meta?.screens || [];
    screensEl.hidden = list.length < 2;
    if (list.length < 2) return;
    const btns = list.map(s => `<button data-s="${s.index}" class="${s.index === screen ? 'on' : ''}">${s.primary ? t('Main') : t('Screen {n}', { n: s.index })}</button>`);
    btns.push(`<button data-s="0" class="${screen === 0 ? 'on' : ''}">${t('All')}</button>`);
    screensEl.innerHTML = btns.join('');
  }
  screensEl.addEventListener('pointerdown', e => e.stopPropagation());
  screensEl.addEventListener('pointerup', e => {
    e.stopPropagation();
    const b = e.target.closest('button'); if (!b) return;
    screen = +b.dataset.s; localStorage.setItem('nova_screen', screen);
    screensEl.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    send({ t: 'screen', index: screen }); buzz();
  });

  function showMsg(text) { msg.hidden = !text; if (text) msg.textContent = text; }
  function setLocked(v) { locked = !!v; $('#lockbar').hidden = !locked; }

  // ---------- layout: fit the PC screen into the viewport ----------
  function layout() {
    if (!meta) return;
    const W = vp.clientWidth, H = vp.clientHeight, ar = meta.w / meta.h;
    let w = W, h = W / ar;
    if (h > H) { h = H; w = H * ar; }
    base = { x: (W - w) / 2, y: (H - h) / 2, w, h };
    cv.style.width = w + 'px'; cv.style.height = h + 'px';
    clamp(); apply();
  }
  function clamp() {
    zoom = Math.min(Math.max(zoom, 1), 6);
    const W = vp.clientWidth, H = vp.clientHeight, w = base.w * zoom, h = base.h * zoom;
    const loX = w > W ? W - w - base.x : (W - w) / 2 - base.x, hiX = w > W ? -base.x : loX;
    const loY = h > H ? H - h - base.y : (H - h) / 2 - base.y, hiY = h > H ? -base.y : loY;
    tx = Math.min(Math.max(tx, loX), hiX);
    ty = Math.min(Math.max(ty, loY), hiY);
  }
  function apply() { cv.style.transform = `translate(${base.x + tx}px, ${base.y + ty}px) scale(${zoom})`; }
  addEventListener('resize', () => setTimeout(layout, 120));

  // screen fraction (0..1) for a finger position
  function frac(cx, cy) {
    const r = cv.getBoundingClientRect();
    return { x: (cx - r.left) / r.width, y: (cy - r.top) / r.height };
  }
  function inside(f) { return f.x >= 0 && f.x <= 1 && f.y >= 0 && f.y <= 1; }
  function fx(cx, cy, right) {
    const r = vp.getBoundingClientRect(), d = document.createElement('div');
    d.className = 'tapfx' + (right ? ' right' : ''); d.style.left = (cx - r.left) + 'px'; d.style.top = (cy - r.top) + 'px';
    vp.appendChild(d); setTimeout(() => d.remove(), 500);
  }
  const buzz = () => haptic('light');

  // ---------- touch gestures ----------
  const pts = new Map();
  let g = null;          // current one-finger gesture
  let pinch = null;      // current two-finger gesture
  let lastTap = null;    // for double-tap: reuse the first tap's exact spot
  let moveTimer = 0, scrollAcc = 0, scrollTimer = 0;

  vp.addEventListener('pointerdown', e => {
    vp.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 2) {                         // switch to pinch/pan
      if (g?.dragging) send({ t: 'up' });
      clearTimeout(g?.lpTimer); g = null;
      const [a, b] = [...pts.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, zoom, tx, ty };
      return;
    }
    if (pts.size > 2) return;
    g = { sx: e.clientX, sy: e.clientY, x: e.clientX, y: e.clientY, t: Date.now(), moved: false, lp: false, dragging: false, tx, ty };
    g.lpTimer = setTimeout(() => { if (g && !g.moved && !scrollMode) { g.lp = true; buzz(); } }, 480);
  });

  vp.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pts.size >= 2) {
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y), cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const r = vp.getBoundingClientRect();
      const nz = Math.min(Math.max(pinch.zoom * d / pinch.d, 1), 6);
      // keep the point between the fingers under the fingers
      const ox = pinch.cx - r.left - base.x - pinch.tx, oy = pinch.cy - r.top - base.y - pinch.ty;
      zoom = nz;
      tx = pinch.tx + (cx - pinch.cx) - ox * (nz / pinch.zoom - 1);
      ty = pinch.ty + (cy - pinch.cy) - oy * (nz / pinch.zoom - 1);
      clamp(); apply();
      return;
    }
    if (!g) return;
    const dx = e.clientX - g.x, dy = e.clientY - g.y;
    g.x = e.clientX; g.y = e.clientY;
    if (!g.moved && Math.hypot(e.clientX - g.sx, e.clientY - g.sy) > 9) { g.moved = true; if (!g.lp) clearTimeout(g.lpTimer); }
    if (!g.moved || locked) return;

    if (g.lp) {                                   // long-press + move = drag on the PC
      if (!g.dragging) { g.dragging = true; const f = frac(g.sx, g.sy); send({ t: 'down', ...f }); }
      const now = Date.now();
      if (now - moveTimer > 30) { moveTimer = now; send({ t: 'move', ...frac(e.clientX, e.clientY) }); }
    } else if (scrollMode) {                      // finger scrolls the PC
      scrollAcc += dy * 4;
      if (!scrollTimer) scrollTimer = setTimeout(() => {
        const f = frac(g?.x ?? e.clientX, g?.y ?? e.clientY);
        send({ t: 'scroll', dy: Math.round(scrollAcc), ...(inside(f) ? f : {}) });
        scrollAcc = 0; scrollTimer = 0;
      }, 40);
    } else if (zoom > 1.01) {                     // pan the zoomed view
      tx += dx; ty += dy; clamp(); apply();
    }
  });

  function end(e) {
    if (!pts.has(e.pointerId)) return;
    pts.delete(e.pointerId);
    if (pinch) { if (pts.size < 2) { pinch = null; if (hd) sendOpts(); } return; }
    if (!g) return;
    clearTimeout(g.lpTimer);
    const cur = g; g = null;
    if (e.type === 'pointercancel') { if (cur.dragging) send({ t: 'up' }); return; }
    if (cur.dragging) { send({ t: 'up', ...frac(e.clientX, e.clientY) }); return; }
    if (cur.moved) return;
    if (locked) { fx(e.clientX, e.clientY); return; }
    let f = frac(cur.sx, cur.sy);
    if (!inside(f)) return;
    if (cur.lp || rightNext) {
      send({ t: 'right', ...f }); fx(cur.sx, cur.sy, true);
      if (rightNext) { rightNext = false; $('#rRight').classList.remove('on'); }
      lastTap = null; return;
    }
    const now = Date.now();
    if (lastTap && now - lastTap.t < 420 && Math.hypot(cur.sx - lastTap.cx, cur.sy - lastTap.cy) < 40) f = lastTap.f;
    send({ t: 'click', ...f }); fx(cur.sx, cur.sy);
    lastTap = { t: now, f, cx: cur.sx, cy: cur.sy };
  }
  vp.addEventListener('pointerup', end);
  vp.addEventListener('pointercancel', end);
  vp.addEventListener('contextmenu', e => e.preventDefault());

  // ---------- keyboard ----------
  const kbd = $('#rkbd');
  const SENT = '​​';                    // keeps Backspace working on an "empty" field
  const resetKbd = () => { kbd.value = SENT; try { kbd.setSelectionRange(1, 1); } catch {} };
  let lastKey = 0;
  $('#rKbd').onclick = () => {
    if (document.activeElement === kbd) { kbd.blur(); return; }
    resetKbd(); kbd.focus();
  };
  kbd.addEventListener('focus', () => $('#rKbd').classList.add('on'));
  kbd.addEventListener('blur', () => $('#rKbd').classList.remove('on'));
  kbd.addEventListener('keydown', e => {
    const map = { Backspace: 'backspace', Enter: 'enter', Tab: 'tab', Escape: 'esc', ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
    if (map[e.key]) { e.preventDefault(); lastKey = Date.now(); if (!locked) send({ t: 'key', text: map[e.key] }); resetKbd(); }
  });
  kbd.addEventListener('beforeinput', e => {
    const t = e.inputType;
    if (t === 'insertText' || t === 'insertReplacementText' || t === 'insertFromPaste') {
      const text = e.data ?? e.dataTransfer?.getData('text/plain') ?? '';
      if (text && !locked) send({ t: 'type', text });
      e.preventDefault(); resetKbd();
    } else if (t === 'deleteContentBackward') {
      e.preventDefault();
      if (Date.now() - lastKey > 60 && !locked) send({ t: 'key', text: 'backspace' });
      resetKbd();
    } else if (t === 'insertLineBreak' || t === 'insertParagraph') {
      e.preventDefault();
      if (Date.now() - lastKey > 60 && !locked) send({ t: 'key', text: 'enter' });
      resetKbd();
    }
  });
  kbd.addEventListener('input', () => {             // fallback (e.g. dictation)
    const text = kbd.value.replace(/​/g, '');
    if (text && !locked) send({ t: 'type', text });
    resetKbd();
  });

  // ---------- toolbar ----------
  $('#rKeys').onclick = () => { const k = $('#keyrow'); k.hidden = !k.hidden; $('#rKeys').classList.toggle('on', !k.hidden); setTimeout(layout, 50); };
  $('#keyrow').onclick = e => { const k = e.target.closest('button')?.dataset.k; if (k && !locked) { send({ t: 'key', text: k }); buzz(); } };
  $('#rScroll').onclick = () => { scrollMode = !scrollMode; $('#rScroll').classList.toggle('on', scrollMode); };
  $('#rRight').onclick = () => { rightNext = !rightNext; $('#rRight').classList.toggle('on', rightNext); };
  $('#rHd').onclick = () => { hd = !hd; localStorage.setItem('nova_hd', hd ? '1' : '0'); $('#rHd').classList.toggle('on', hd); sendOpts(); };
  $('#rHd').classList.toggle('on', hd);
  $('#rFit').onclick = () => { zoom = 1; tx = 0; ty = 0; clamp(); apply(); };
  $('#lockStop').onclick = () => onStopAgent();
  $('#rBack').onclick = () => onBack?.();
  $('#rRotate').onclick = () => { post({ type: 'orientation', value: 'toggle' }); buzz(); };
  // in the app, hide the iPhone status bar while watching the PC sideways
  const landscape = matchMedia('(orientation: landscape) and (max-height: 520px)');
  const immersive = () => { if (isNative) post({ type: 'immersive', on: active && landscape.matches }); setTimeout(layout, 150); };
  landscape.addEventListener?.('change', immersive);
  document.addEventListener('visibilitychange', () => {
    if (!active) return;
    if (document.hidden) { ws?.close(); } else if (!ws) connect();
  });

  return {
    open() {
      active = true; setTimeout(immersive, 0); $('#remote').hidden = false; setTimeout(layout, 30); if (!ws) connect();
      if (!localStorage.getItem('nova_hint')) {
        const h = document.createElement('div'); h.className = 'rhint';
        h.innerHTML = `<b>${t('Controlling your PC')}</b>${t('Tap to click · double-tap to open')}<br>${t('Long-press for right-click · long-press + move to drag')}<br>${t('Pinch to zoom · turn your phone sideways for a bigger view')}<span>${t('Got it')}</span>`;
        h.addEventListener('pointerdown', e => e.stopPropagation());
        h.addEventListener('pointerup', e => { e.stopPropagation(); localStorage.setItem('nova_hint', '1'); h.remove(); });
        vp.appendChild(h);
      }
    },
    close() { active = false; if (isNative) post({ type: 'immersive', on: false }); $('#remote').hidden = true; kbd.blur(); clearTimeout(retryTimer); ws?.close(); ws = null; },
  };
}
