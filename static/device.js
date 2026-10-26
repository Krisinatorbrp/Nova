// Nova without the PC. Two ways:
//  - iPhone app, PC not reachable: the app shows this interface from inside itself (nova://app/)
//    and answers with Apple's on-device AI (through the native bridge).
//  - Nova as a website (GitHub Pages): the AI runs right in the browser (web.js, WebGPU).
//
// It stands in for the PC's server: /api/* requests and the live connection are answered here,
// and questions go to the app through the native bridge (post → Swift → window.novaNative.llm).
import { post } from './native.js';

export const onDevice = location.protocol === 'nova:' || !!window.__novaDeviceTest;   // (test hook)
export const onWeb = !onDevice && !!window.__novaWeb;        // set by the published website

if (onDevice || onWeb) install(onWeb ? 'web' : 'device');

function install(kind) {
  const qs = new URLSearchParams(location.search);
  const de = (navigator.language || 'en').toLowerCase().startsWith('de');
  if (qs.get('name')) { try { localStorage.setItem('nova_name', qs.get('name')); } catch {} }
  let saved = null; try { saved = localStorage.getItem('nova_name'); } catch {}
  const name = (qs.get('name') || saved || 'Nova').slice(0, 24);
  // where the answers come from: Apple's AI in the app, or the browser's own (loaded on first use)
  let webBrain = null;
  const brain = () => webBrain || (webBrain = import('./web.js'));
  const dev = { history: [], busy: false, sock: null };

  // ---------- the server's API, answered locally ----------
  const realFetch = window.fetch.bind(window);
  const json = body => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  window.fetch = (url, opts) => {
    const path = new URL(url, location.href).pathname;
    if (!path.startsWith('/api/')) return realFetch(url, opts);
    if (path === '/api/state') {
      return Promise.resolve(json({ name, configured: true, brain: 'device', phone_ready: true, role: 'phone',
        busy: dev.busy, speak_replies: false, orb_color: localStorage.getItem('nova_device_color') || '#2896FF',
        show_transcript: true, language: de ? 'de' : 'en', remote: false, device: true }));
    }
    if (path === '/api/login') return Promise.resolve(json({ token: 'device' }));
    return Promise.resolve(json({ ok: true }));
  };

  // ---------- the live connection ----------
  const emit = ev => {
    ev.ts = Date.now() / 1000;
    if (['user', 'assistant', 'error'].includes(ev.type)) { dev.history.push(ev); if (dev.history.length > 100) dev.history.shift(); }
    if (ev.type === 'state') dev.busy = ev.state !== 'idle';
    const s = dev.sock;
    if (s && s.readyState === 1) s.onmessage?.({ data: JSON.stringify(ev) });
  };

  class DeviceSocket {
    constructor() {
      this.readyState = 0;
      dev.sock = this;
      setTimeout(() => {
        this.readyState = 1;
        this.onopen?.({});
        this.onmessage?.({ data: JSON.stringify({ type: 'history', events: dev.history, busy: dev.busy }) });
      }, 0);
    }
    send(data) {
      let m; try { m = JSON.parse(data); } catch { return; }
      if (m.type === 'task') {
        const text = String(m.text || '').trim().slice(0, 2000);
        if (!text) return;
        if (dev.busy) return emit({ type: 'error', text: de ? 'Moment, ich bin noch bei der letzten Frage.' : "One moment, I'm still on the last question." });
        emit({ type: 'user', text, from: 'device' });
        emit({ type: 'state', state: 'thinking' });
        if (kind === 'web') brain().then(b => b.ask(text, de, name, emit)).catch(e => {
          emit({ type: 'error', text: String(e.message || e) }); emit({ type: 'state', state: 'idle' });
        });
        else post({ type: 'llm', action: 'ask', text, lang: de ? 'de' : 'en', name });
      } else if (m.type === 'stop') {
        if (kind === 'web') brain().then(b => b.stop());
        else post({ type: 'llm', action: 'stop' });
      } else if (m.type === 'reset') {
        dev.history = [];
        if (kind === 'web') brain().then(b => b.reset());
        else post({ type: 'llm', action: 'reset' });
        emit({ type: 'reset' });
      }
    }
    close() { this.readyState = 3; if (dev.sock === this) dev.sock = null; }
  }
  window.WebSocket = DeviceSocket;

  // the app sends the answers back here: {type: 'stream' | 'assistant' | 'state' | 'error', ...}
  window.novaNative = window.novaNative || {};
  window.novaNative.llm = ev => emit(ev);

  // a small badge so you always know you're talking to the iPhone, not the PC
  const badge = () => {
    document.body.classList.add('on-device');
    const b = document.createElement('span');
    b.className = 'device-badge';
    if (kind === 'web') {
      b.title = de ? 'Die KI läuft direkt in diesem Browser' : 'The AI runs right in this browser';
      b.innerHTML = `<i></i>${de ? 'Browser-KI' : 'Browser AI'}`;
    } else {
      b.title = de ? 'PC nicht erreichbar: die KI auf dem iPhone antwortet' : "PC not reachable: the AI on your iPhone answers";
      b.innerHTML = `<i></i>${de ? 'iPhone-KI' : 'iPhone AI'}`;
    }
    document.querySelector('.brand')?.appendChild(b);
  };
  if (document.body) badge(); else addEventListener('DOMContentLoaded', badge);
}
