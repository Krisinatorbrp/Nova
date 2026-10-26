import './device.js';                                      // iPhone app without the PC: AI on the phone
import { createVisual } from './visual.js';
import { createRemote } from './remote.js';
import { createLocalBox } from './local.js';
import { isNative, post, haptic } from './native.js';
import { t, tAction, setLang, applyDOM, uiLang } from './i18n.js';

const $ = s => document.querySelector(s);
const body = document.body;
const feed = $('#feed'), input = $('#input');
const orb = createVisual($('#orb'), { mode: 'particles' });      // popup: blue particles
const hud = createVisual($('#hudCanvas'), { mode: 'rings' });    // fullscreen: HUD rings
// keep both visuals in sync
const both = (fn) => { fn(orb); fn(hud); };
window.__novaVisual = { orb, hud };
// the PC app tells us when its window is hidden: then the animations stop completely (no CPU/GPU use)
window.novaVisible = on => both(v => v.pause(!on));

// ---------- who am I? (PC window gets a one-time local token in the URL) ----------
const qs = new URLSearchParams(location.search);
if (qs.get('h') === '1') window.novaVisible(false);               // started hidden (as the widget)
if (qs.get('t')) { sessionStorage.setItem('nova_local', qs.get('t')); history.replaceState(null, '', '/'); }
const localToken = sessionStorage.getItem('nova_local');
const isLocal = !!localToken;
let token = localToken || localStorage.getItem('nova_phone');
if (!isLocal) body.classList.add('phone');
const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
                set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };

window.addEventListener('pywebviewready', () => body.classList.add('desktop'));
$('#btnMin').onclick = () => window.pywebview?.api.minimize();
$('#btnClose').onclick = () => window.pywebview?.api.hide();

const api = async (path, data) => {
  const r = await fetch(path, { method: data ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    body: data ? JSON.stringify(data) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || 'Request failed');
  return j;
};

// ---------- language (first guess from the browser, then the PC's setting) ----------
setLang((navigator.language || 'en').toLowerCase().startsWith('de') ? 'de' : 'en');
applyDOM();

// ---------- greeting ----------
const h = new Date().getHours();
const greet = () => { $('#greeting').textContent = t(h < 5 ? 'Up late?' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'); };
greet();

// ---------- state ----------
let state = 'idle', speak = false, name = 'Nova', ws = null, activity = null;
const STATUS = { idle: 'Ready', thinking: 'Thinking…', acting: 'Working on your PC', waiting: 'Needs your OK', listening: 'Listening…' };

function setState(s) {
  state = s;
  body.classList.toggle('busy', s === 'thinking' || s === 'acting');
  body.classList.toggle('waiting', s === 'waiting');
  both(v => v.setState(s));
  hudStatus(s);
  $('#status b').textContent = t(body.classList.contains('offline') ? 'Offline' : STATUS[s] || 'Ready');
  if (s === 'idle' && activity) finishActivity();
}

function setName(n) {
  name = n || 'Nova';
  document.title = name;
  $('#name').textContent = name;
  both(v => v.setName(name));
  document.querySelectorAll('.nm').forEach(e => e.textContent = name);
  input.placeholder = t('Ask {name} anything…', { name });
}

// ---------- feed rendering ----------
const esc = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = s => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');

function add(el) {
  body.classList.remove('empty');
  feed.appendChild(el);
  requestAnimationFrame(() => feed.scrollTop = feed.scrollHeight);
  return el;
}
function el(tag, cls, html) { const e = document.createElement(tag); e.className = cls; if (html != null) e.innerHTML = html; return e; }

function finishActivity() {
  if (!activity) return;
  activity.classList.add('done');
  const n = activity.querySelectorAll('li').length;
  activity.querySelector('.label').textContent = t(n === 1 ? 'Did {n} step on your PC' : 'Did {n} steps on your PC', { n });
  activity = null;
}

function render(ev, replay = false) {
  switch (ev.type) {
    case 'user': {
      finishActivity();
      $('#hudUser').textContent = ev.text; $('#hudCaption').textContent = '';
      const m = add(el('div', 'msg-user'));
      m.textContent = ev.text;
      if (ev.from === 'phone' && isLocal) m.appendChild(el('span', 'via', t('from iPhone')));
      if (ev.from === 'local' && !isLocal) m.appendChild(el('span', 'via', t('from PC')));
      break;
    }
    case 'stream': {                                    // answer arriving word by word
      finishActivity();
      let m = feed.querySelector(`.msg-ai[data-sid="${ev.id}"]`);
      if (!m) { m = add(el('div', 'msg-ai streaming')); m.dataset.sid = ev.id; }
      m.innerHTML = fmt(ev.text);
      requestAnimationFrame(() => feed.scrollTop = feed.scrollHeight);
      caption(ev.text, false);
      speakChunks(ev.id, ev.text, false);
      break;
    }
    case 'assistant': {
      finishActivity();
      const m = ev.id != null && feed.querySelector(`.msg-ai[data-sid="${ev.id}"]`);
      if (m) { m.innerHTML = fmt(ev.text); m.classList.remove('streaming'); }
      else add(el('div', 'msg-ai', fmt(ev.text)));
      caption(ev.text, !replay && !m);
      if (!replay && !ev.greeting) speakChunks(ev.id ?? ('q' + Date.now()), ev.text, true);   // (the greeting speaks itself)
      break;
    }
    case 'action': {
      if (!activity) {
        activity = add(el('div', 'activity', `<div class="head"><span class="spin"></span><span class="label">${t('Working')}</span><span class="count"></span></div><ul></ul><div class="shot"><img alt="Live view of your PC screen"></div>`));
        const a = activity;
        a.querySelector('.head').onclick = () => a.classList.toggle('open');
      }
      const ul = activity.querySelector('ul');
      ul.appendChild(el('li', '', esc(tAction(ev.text))));
      activity.querySelector('.label').textContent = tAction(ev.text);
      activity.querySelector('.count').textContent = ul.children.length;
      if (!replay) { both(v => v.pulse()); $('#hudStatus').textContent = '› ' + tAction(ev.text); }
      break;
    }
    case 'frame':
      if (activity) {
        const s = activity.querySelector('.shot');
        s.classList.add('has');
        s.querySelector('img').src = 'data:image/jpeg;base64,' + ev.jpeg;
      }
      break;
    case 'confirm': {
      const c = add(el('div', 'confirm', `<h4>${esc(t(ev.title))}</h4>${ev.why ? `<p>${esc(ev.why)}</p>` : ''}<pre>${esc(ev.detail)}</pre>
        <div class="btns"><button class="deny">${t("Don't run")}</button><button class="allow">${t('Allow')}</button></div><div class="verdict"></div>`));
      c.id = 'c-' + ev.id;
      c.querySelector('.allow').onclick = () => send({ type: 'confirm', id: ev.id, ok: true });
      c.querySelector('.deny').onclick = () => send({ type: 'confirm', id: ev.id, ok: false });
      break;
    }
    case 'confirm_done': {
      const c = document.getElementById('c-' + ev.id);
      if (c) { c.classList.add('resolved'); c.querySelector('.verdict').textContent = t(ev.ok ? '✓ Allowed' : '✕ Declined'); }
      break;
    }
    case 'error':
      finishActivity();
      caption('⚠ ' + ev.text, false);
      add(el('div', 'msg-err', esc(ev.text)));
      break;
    case 'state':
      setState(ev.state);
      break;
    case 'voice':                                       // Piper / ElevenLabs talking on the PC
      if (isLocal && voiceEngine === 'windows') break;  // (that's our own echo)
      if (ev.ev === 'start') both(v => v.speakStart());
      else if (ev.ev === 'word') both(v => v.kick());
      else if (ev.ev === 'end') both(v => v.speakEnd());
      break;
    case 'listen':
      $('#btnMic').classList.toggle('on', !!ev.on);
      if (ev.on) {
        both(v => v.setState('listening')); $('#status b').textContent = t('Listening…'); $('#hudStatus').textContent = t('LISTENING');
        if (isLocal && 'speechSynthesis' in window) speechSynthesis.cancel();   // don't record our own voice
      }
      if (ev.on === false && !replay) setState(state);    // back to what the assistant is doing
      if (ev.level > 0.5) both(v => v.kick());
      if (ev.heard === false) add(el('div', 'msg-err', esc(t("I didn't hear anything. Try again a bit louder."))));
      break;
    case 'dictation':
      input.value = ev.text; autosize(); input.focus();
      break;
    case 'voice_pull':
      piperPull(ev);
      break;
    case 'prefs':
      applyPrefs(ev);
      if (ev.name && ev.name !== name) setName(ev.name);
      break;
    case 'pull':
      setupBox?.onPull(ev); settingsBox?.onPull(ev);
      break;
    case 'remote':
      $('#viewing').hidden = !(isLocal && ev.viewers > 0);
      break;
    case 'reset':
      feed.innerHTML = ''; activity = null; body.classList.add('empty');
      break;
    case 'progress':                                    // the browser / iPhone AI is loading
      $('#status b').textContent = ev.text; $('#hudStatus').textContent = ev.text;
      break;
  }
}

// ---------- connection ----------
let retry = 0;
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  ws.onopen = () => { retry = 0; body.classList.remove('offline'); setState(state); };
  ws.onmessage = e => {
    const ev = JSON.parse(e.data);
    if (ev.type === 'history') {
      feed.innerHTML = ''; activity = null;
      if (ev.events.length) ev.events.forEach(x => render(x, true)); else body.classList.add('empty');
      if (!ev.busy) finishActivity();
      setState(ev.busy ? 'thinking' : 'idle');
    } else render(ev);
  };
  ws.onclose = e => {
    body.classList.add('offline'); $('#status b').textContent = t('Offline'); hudStatus(state);
    if (e.code === 4401 && !isLocal) { localStorage.removeItem('nova_phone'); return showLogin(); }
    setTimeout(connect, Math.min(1000 * 2 ** retry++, 8000));
  };
}
function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }

// ---------- composer ----------
function autosize() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; }
input.addEventListener('input', autosize);
input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('#composer').requestSubmit(); }
});
$('#composer').onsubmit = e => {
  e.preventDefault();
  if (state === 'thinking' || state === 'acting' || state === 'waiting') return send({ type: 'stop' });
  const text = input.value.trim();
  if (!text) return;
  send({ type: 'task', text });
  input.value = ''; autosize();
  setState('thinking');
};
$('#chips').onclick = e => { const b = e.target.closest('button'); if (b) { input.value = b.textContent.trim(); $('#composer').requestSubmit(); } };
$('#btnNew').onclick = () => { if (state === 'idle') send({ type: 'reset' }); };
document.addEventListener('keydown', e => {
  if (e.key === 'F11') { e.preventDefault(); setFull(!body.classList.contains('full')); return; }
  if (e.key !== 'Escape') return;
  if (state !== 'idle') send({ type: 'stop' });
  else if (body.classList.contains('full')) setFull(false);
});

// ---------- voice input ----------
if (isLocal) {
  // on the PC, the mic uses Nova's own speech recognition (Whisper, runs locally)
  const mic = $('#btnMic'); mic.hidden = false;
  mic.onclick = () => api('/api/listen', {}).catch(e => add(el('div', 'msg-err', esc(e.message))));
} else if (isNative) {
  // the iPhone app does speech recognition natively (Safari's needs HTTPS)
  const mic = $('#btnMic'); mic.hidden = false;
  let listening = false;
  mic.onclick = () => { post({ type: 'speech', action: listening ? 'stop' : 'start', lang: speechLang() }); haptic('medium'); };
  window.novaNative.speech = (text, event) => {
    if (event === 'start') { listening = true; mic.classList.add('on'); both(v => v.setState('listening')); $('#status b').textContent = t(STATUS.listening); }
    if (event === 'result' && text) { input.value = text; autosize(); }
    if (event === 'end' || event === 'error') {
      listening = false; mic.classList.remove('on'); setState(state);
      if (event === 'end' && input.value.trim()) $('#composer').requestSubmit();
      if (event === 'error' && text) add(el('div', 'msg-err', esc(text)));
    }
  };
}
const SR = !isNative && !isLocal && (window.SpeechRecognition || window.webkitSpeechRecognition);
if (SR) {
  const mic = $('#btnMic'); mic.hidden = false;
  let rec = null;
  mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = speechLang(); rec.interimResults = true;
    let finalText = '';
    rec.onresult = e => {
      let interim = '';
      for (const r of e.results) (r.isFinal ? (finalText += r[0].transcript) : (interim += r[0].transcript));
      input.value = finalText + interim; autosize();
    };
    rec.onstart = () => { mic.classList.add('on'); both(v => v.setState('listening')); $('#status b').textContent = t(STATUS.listening); };
    rec.onend = () => {
      mic.classList.remove('on'); rec = null; setState(state);
      if (input.value.trim()) $('#composer').requestSubmit();
    };
    rec.onerror = () => {};
    rec.start();
  };
}
// Speak a streamed answer sentence by sentence, so the voice starts before the answer is complete.
const spoken = new Map();
function speakChunks(id, text, final) {
  const done = spoken.get(id) || 0;
  let upto = done;
  if (final) upto = text.length;
  else { const m = text.slice(done).match(/^[\s\S]*[.!?:;\n](?=\s|$)/); if (m) upto = done + m[0].length; }
  if (upto <= done) return;
  const part = text.slice(done, upto).trim();
  spoken.set(id, upto);
  if (spoken.size > 50) spoken.delete(spoken.keys().next().value);
  if (!part) return;
  if (isLocal && voiceEngine !== 'windows' && speak) return;   // Piper / ElevenLabs speak on the PC itself
  if (speak) say(part, done > 0);
  else both(v => v.speakFor(Math.min(12000, 900 + part.length * 45)));
}

function pickVoice(vp) {
  const voices = speechSynthesis.getVoices();
  if (vp.name) { const v = voices.find(x => x.name === vp.name); if (v) return v; }
  // no voice chosen: take a nice one in the app language (natural/online voices first)
  const want = uiLang === 'de' ? 'de' : 'en';
  const list = voices.filter(v => v.lang.toLowerCase().startsWith(want));
  return list.find(v => /natural|online|neural/i.test(v.name)) || list[0] || null;
}

function say(text, queue = false, onFail = null) {
  const clean = text.replace(/[`*]/g, '');
  if (!('speechSynthesis' in window)) { if (onFail) onFail('unsupported'); else both(v => v.speakFor(Math.min(12000, 900 + clean.length * 45))); return; }
  if (!queue) speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(clean);
  const vp = voicePrefs;
  const chosen = pickVoice(vp);
  if (chosen) { u.voice = chosen; u.lang = chosen.lang; } else u.lang = uiLang === 'de' ? 'de-DE' : 'en-US';
  u.rate = +vp.rate || 1; u.pitch = +vp.pitch || 1; u.volume = vp.volume == null ? 1 : +vp.volume;
  // the rings (and the desktop widget) move while the voice talks, and jump on every word
  let lastWord = 0, started = false;
  // onFail: Windows sometimes doesn't let a page talk before you clicked it (e.g. right at start-up)
  const watchdog = onFail && setTimeout(() => { if (!started) { speechSynthesis.cancel(); onFail('timeout'); } }, 2500);
  u.onstart = () => { started = true; clearTimeout(watchdog); both(v => v.speakStart()); if (isLocal) send({ type: 'voice', ev: 'start' }); };
  u.onboundary = () => {
    both(v => v.kick());
    if (isLocal && performance.now() - lastWord > 120) { lastWord = performance.now(); send({ type: 'voice', ev: 'word' }); }
  };
  u.onend = u.onerror = e => {
    if (onFail && !started && e?.error && e.error !== 'interrupted' && e.error !== 'canceled') {
      started = true; clearTimeout(watchdog); onFail(e.error); return;
    }
    if (speechSynthesis.pending) return;                 // more sentences queued: keep talking
    both(v => v.speakEnd()); if (isLocal) send({ type: 'voice', ev: 'end' });
  };
  speechSynthesis.speak(u);
}

// ---------- colour, transcript and voice preferences ----------
let voicePrefs = store.get('nova_voice', { name: '', rate: 1, pitch: 1, volume: 1 });
function applyPrefs(p) {
  if (p.language && p.language !== uiLang) applyLanguage(p.language);
  if (p.orb_color) { both(v => v.setColor(p.orb_color)); document.documentElement.style.setProperty('--hud', p.orb_color); }
  if ('show_transcript' in p && p.show_transcript != null) body.classList.toggle('no-transcript', !p.show_transcript);
}
// switch the whole app to another language
function applyLanguage(l) {
  setLang(l);
  applyDOM();
  greet(); setName(name); setState(state);
}
const speechLang = () => (uiLang === 'de' ? 'de-DE' : (navigator.language || 'en-US').split('@')[0]);
const hex2 = n => (+n).toString(16).padStart(2, '0');
function setColorUI(hex) {
  $('#sColor').value = hex.toUpperCase();
  $('#sSwatch').style.background = hex;
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  [['R', r], ['G', g], ['B', b]].forEach(([k, v]) => { $('#s' + k).value = v; $('#v' + k).textContent = v; });
  document.querySelectorAll('#presets button').forEach(x => x.classList.toggle('on', x.dataset.c.toLowerCase() === hex.toLowerCase()));
  previewColor(hex);                                            // live preview
}
// hex field (no Windows colour dialog: it could hide behind Nova and freeze the window)
$('#sColor').addEventListener('input', () => {
  let v = $('#sColor').value.trim(); if (!v.startsWith('#')) v = '#' + v;
  if (/^#[0-9a-f]{6}$/i.test(v)) setColorUI(v);
});
// live preview, but at most ~30 times a second while you drag a slider
let previewTimer = 0, previewHex = null;
function previewColor(hex) {
  previewHex = hex;
  if (previewTimer) return;
  previewTimer = setTimeout(() => { previewTimer = 0; both(v => v.setColor(previewHex)); }, 33);
}
['R', 'G', 'B'].forEach(k => $('#s' + k).addEventListener('input', () =>
  setColorUI('#' + hex2($('#sR').value) + hex2($('#sG').value) + hex2($('#sB').value))));
$('#presets').onclick = e => { const c = e.target.closest('button')?.dataset.c; if (c) setColorUI(c); };

function fillVoices() {
  if (!('speechSynthesis' in window)) return;
  const sel = $('#sVoice'), cur = voicePrefs.name;
  const voices = speechSynthesis.getVoices().slice().sort((a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name));
  sel.innerHTML = `<option value="">${t('System default')}</option>` +
    voices.map(v => `<option value="${esc(v.name)}">${esc(v.name.replace(/^Microsoft /, ''))} · ${esc(v.lang)}</option>`).join('');
  sel.value = voices.some(v => v.name === cur) ? cur : '';
}
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = fillVoices;
function voiceUI() {
  fillVoices();
  for (const [k, id] of [['rate', 'Rate'], ['pitch', 'Pitch'], ['volume', 'Volume']]) {
    $('#s' + id).value = voicePrefs[k] ?? 1; $('#v' + id).textContent = (+$('#s' + id).value).toFixed(2);
  }
}
function readVoiceUI() {
  return { name: $('#sVoice').value, rate: +$('#sRate').value, pitch: +$('#sPitch').value, volume: +$('#sVolume').value };
}
['Rate', 'Pitch', 'Volume'].forEach(id => $('#s' + id).addEventListener('input', () => {
  $('#v' + id).textContent = (+$('#s' + id).value).toFixed(2);
  if (!isLocal) { voicePrefs = readVoiceUI(); store.set('nova_voice', voicePrefs); }
}));
$('#sVoice').addEventListener('change', () => { if (!isLocal) { voicePrefs = readVoiceUI(); store.set('nova_voice', voicePrefs); } });
$('#voiceTest').onclick = () => {
  const text = t('Hello, I am {name}. This is how I sound with these settings.', { name });
  const eng = isLocal ? pickedEngine() : 'windows';
  if (eng === 'windows') {
    const keep = voicePrefs; voicePrefs = readVoiceUI(); say(text); voicePrefs = keep;
    return;
  }
  api('/api/tts/test', { text, voice_engine: eng, piper_voice: piperSel, eleven_voice: $('#sElevenVoice').value,
    eleven_model: $('#sElevenModel').value, eleven_key: $('#sElevenKey').value, voice_rate: +$('#sRate').value, voice_volume: +$('#sVolume').value })
    .catch(e => { $('#settingsErr').textContent = e.message; });
};

// ---------- voice engines: Windows / Piper / ElevenLabs ----------
let voiceEngine = 'windows', piperSel = '', piperData = null, piperPulling = null;
const pickedEngine = () => $('#engines .brain.on')?.dataset.engine || 'windows';
function showEngine(eng) {
  document.querySelectorAll('#engines .brain').forEach(b => b.classList.toggle('on', b.dataset.engine === eng));
  document.querySelectorAll('.eng-piper').forEach(e => e.hidden = eng !== 'piper');
  document.querySelectorAll('.eng-eleven').forEach(e => e.hidden = eng !== 'eleven');
  document.querySelectorAll('.eng-windows').forEach(e => e.hidden = isLocal && eng !== 'windows');
  if (eng === 'piper') loadPiper();
}
$('#engines').onclick = e => { const b = e.target.closest('.brain'); if (b) showEngine(b.dataset.engine); };
async function loadPiper() {
  try { piperData = await api('/api/voices'); } catch { return; }
  piperPulling = piperData.pulling ? { voice: piperData.pulling, pct: null } : piperPulling;
  fillElevenModels();
  renderPiper();
}
function renderPiper() {
  if (!piperData) return;
  const de = uiLang === 'de';
  const list = piperData.piper.slice().sort((a, b) => (b.name.startsWith(de ? 'de' : 'en') - a.name.startsWith(de ? 'de' : 'en')));
  if (!piperSel) piperSel = (list.find(v => v.installed) || list[0]).name;
  $('#piperBox').innerHTML = list.map(v => {
    const p = piperPulling && piperPulling.voice === v.name;
    const right = v.installed ? `<span class="lb-ok">${t('✓ Ready')}</span>`
      : p ? `<span class="lb-pct">${piperPulling.pct != null ? Math.floor(piperPulling.pct) + '%' : '…'}</span>`
      : `<button type="button" class="lb-dl" data-dl="${esc(v.name)}" ${piperPulling ? 'disabled' : ''}>${t('Download')}</button>`;
    return `<label class="lb-model ${piperSel === v.name ? 'on' : ''}"><input type="radio" name="piperv" value="${esc(v.name)}" ${piperSel === v.name ? 'checked' : ''}>
      <span class="lb-name">${esc(v.label)}</span>${right}${p ? `<span class="lb-bar"><i style="width:${piperPulling.pct || 2}%"></i></span>` : ''}</label>`;
  }).join('');
}
function piperPull(ev) {
  piperPulling = ev.done ? null : { voice: ev.voice, pct: ev.pct };
  if (ev.error) $('#settingsErr').textContent = ev.error;
  if (ev.done) loadPiper(); else renderPiper();
}
$('#piperBox').addEventListener('change', e => { if (e.target.name === 'piperv') { piperSel = e.target.value; renderPiper(); } });
$('#piperBox').addEventListener('click', async e => {
  const b = e.target.closest('[data-dl]'); if (!b) return;
  e.preventDefault(); piperSel = b.dataset.dl; piperPulling = { voice: piperSel, pct: 0 }; renderPiper();
  try { await api('/api/voices/download', { name: piperSel }); } catch (err) { piperPulling = null; $('#settingsErr').textContent = err.message; renderPiper(); }
});
function fillElevenModels() {
  const sel = $('#sElevenModel'), cur = sel.dataset.want || sel.value;
  if (piperData && !sel.options.length) sel.innerHTML = piperData.eleven_models.map(m => `<option value="${esc(m.id)}">${esc(m.label)}</option>`).join('');
  if (cur) sel.value = cur;
}
$('#elevenLoad').onclick = async () => {
  $('#settingsErr').textContent = '';
  try {
    const r = await api('/api/voices/eleven', { key: $('#sElevenKey').value });
    const sel = $('#sElevenVoice'), want = sel.dataset.want;
    sel.innerHTML = r.voices.map(v => `<option value="${esc(v.id)}">${esc(v.name)}${v.info ? ' · ' + esc(v.info) : ''}</option>`).join('');
    if (want) sel.value = want;
  } catch (e) { $('#settingsErr').textContent = e.message; }
};

// ---------- hotkeys: freely assignable key combinations ----------
const KEY_NAMES = { ' ': 'space', Enter: 'enter', Escape: 'esc', Tab: 'tab', Backspace: 'backspace', Delete: 'delete',
  Insert: 'insert', Home: 'home', End: 'end', PageUp: 'page up', PageDown: 'page down',
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Pause: 'pause', ScrollLock: 'scroll lock' };
const MODS = ['Control', 'Shift', 'Alt', 'AltGraph', 'Meta', 'OS'];
function comboFromEvent(e) {
  let key = KEY_NAMES[e.key];
  if (!key && /^F\d{1,2}$/.test(e.key)) key = e.key.toLowerCase();
  if (!key && /^Digit\d$/.test(e.code)) key = e.code.slice(5);
  if (!key && e.key.length === 1 && /\p{L}/u.test(e.key)) key = e.key.toLowerCase();
  if (!key && /^Key[A-Z]$/.test(e.code)) key = e.code.slice(3).toLowerCase();
  if (!key && e.key.length === 1) key = e.key;
  if (!key) return null;
  const mods = [e.ctrlKey && 'ctrl', e.shiftKey && 'shift', e.altKey && 'alt', e.metaKey && 'windows'].filter(Boolean);
  return [...mods, key].join('+');
}
function prettyCombo(c) {
  if (!c) return t('Off');
  const de = uiLang === 'de';
  const nice = { ctrl: de ? 'Strg' : 'Ctrl', shift: de ? 'Umschalt' : 'Shift', alt: 'Alt', windows: 'Win',
    space: de ? 'Leertaste' : 'Space', enter: 'Enter', esc: 'Esc', 'page up': 'Bild ↑', 'page down': 'Bild ↓',
    up: '↑', down: '↓', left: '←', right: '→' };
  return c.split('+').map(k => nice[k] || (k.length === 1 ? k.toUpperCase() : k.replace(/^f(\d+)$/, 'F$1'))).join(' + ');
}
let hkValues = { hotkey: 'ctrl+alt+space', ask_hotkey: 'ctrl+shift+space', talk_hotkey: 'ctrl+shift+m' };
let recording = null;
function showHotkeys() {
  document.querySelectorAll('.hk').forEach(b => { b.textContent = prettyCombo(hkValues[b.dataset.key]); b.classList.remove('rec'); });
}
function stopRecording() {
  recording = null; showHotkeys();
  window.pywebview?.api.pause_hotkeys(false);
}
document.querySelectorAll('.hk').forEach(b => b.addEventListener('click', () => {
  if (recording === b) return stopRecording();
  recording = b; showHotkeys();
  b.classList.add('rec'); b.textContent = t('Press keys…');
  window.pywebview?.api.pause_hotkeys(true);              // old hotkeys must not fire while you record
}));
document.addEventListener('keydown', e => {
  if (!recording) return;
  e.preventDefault(); e.stopPropagation();
  const key = recording.dataset.key;
  if (e.key === 'Escape') return stopRecording();
  if (e.key === 'Backspace' && !e.ctrlKey && !e.altKey && !e.shiftKey) { hkValues[key] = ''; return stopRecording(); }
  if (MODS.includes(e.key)) {                                // only modifiers so far: show them live
    recording.textContent = prettyCombo([e.ctrlKey && 'ctrl', e.shiftKey && 'shift', e.altKey && 'alt', e.metaKey && 'windows'].filter(Boolean).join('+')) + ' + …';
    return;
  }
  const combo = comboFromEvent(e);
  if (!combo) return;
  const hasMod = /^(ctrl|shift|alt|windows)\+/.test(combo);
  if (!hasMod && !/^f\d+$/.test(combo)) { $('#settingsErr').textContent = t('Use at least one of Ctrl, Alt, Shift or Win (or an F key).'); return; }
  if (Object.entries(hkValues).some(([k, v]) => k !== key && v === combo)) { $('#settingsErr').textContent = t('That combination is already used by the other hotkey.'); return; }
  $('#settingsErr').textContent = '';
  hkValues[key] = combo;
  stopRecording();
}, true);

// the Ask hotkey calls this: chat ready to type
window.novaAsk = () => {
  if (!$('#settings').hidden) closeSettings();
  if (body.classList.contains('tab-screen')) showTab('chat');
  input.focus(); input.select();
  both(v => v.pulse());
};

// ---------- fullscreen HUD ----------
const HUD_STATUS = { idle: 'ONLINE', thinking: 'PROCESSING', acting: 'EXECUTING', waiting: 'AWAITING CONFIRMATION', listening: 'LISTENING' };
function hudStatus(s) { $('#hudStatus').textContent = t(body.classList.contains('offline') ? 'OFFLINE' : HUD_STATUS[s] || 'ONLINE'); }
let capTimer = 0;
function caption(text, typewriter) {
  const elc = $('#hudCaption'); clearInterval(capTimer);
  if (!typewriter) { elc.textContent = text; return; }
  let i = 0; elc.textContent = '';
  capTimer = setInterval(() => { i += 2; elc.textContent = text.slice(0, i); if (i >= text.length) clearInterval(capTimer); }, 22);
}
function setFull(on) {
  on = !!on;
  if (on === body.classList.contains('full')) return;
  if (on && body.classList.contains('tab-screen')) showTab('chat');
  body.classList.toggle('full', on);
  try { localStorage.setItem('nova_full', on ? '1' : '0'); } catch {}
  if (window.pywebview?.api?.set_fullscreen) window.pywebview.api.set_fullscreen(on);
  else if (!isNative) {
    try { on ? document.documentElement.requestFullscreen?.().catch(() => {}) : document.fullscreenElement && document.exitFullscreen(); } catch {}
  }
}
$('#btnFull').onclick = () => setFull(!body.classList.contains('full'));
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && body.classList.contains('full') && !window.pywebview) setFull(false); });

// ---------- setup / login / settings ----------
function showLogin() {
  $('#login').hidden = false; setTimeout(() => $('#loginPass').focus(), 200);
}
$('#loginGo').onclick = async () => {
  $('#loginErr').textContent = '';
  try {
    const r = await api('/api/login', { passcode: $('#loginPass').value });
    token = r.token; localStorage.setItem('nova_phone', token);
    $('#login').hidden = true; boot();
  } catch (e) { $('#loginErr').textContent = e.message; }
};
$('#loginPass').onkeydown = e => { if (e.key === 'Enter') $('#loginGo').click(); };

// ---------- brain choice: This PC (Ollama) or Claude ----------
const setupBox = isLocal ? createLocalBox($('#setupLocal'), api) : null;
const settingsBox = isLocal ? createLocalBox($('#settingsLocal'), api) : null;
function pickBrain(card, brain) {
  card.querySelectorAll('.brain[data-brain]').forEach(b => b.classList.toggle('on', b.dataset.brain === brain));
  card.querySelector('.brain-local').hidden = brain !== 'local';
  card.querySelector('.brain-claude').hidden = brain !== 'claude';
  card.dataset.brain = brain;
  if (brain === 'local') (card.closest('#setup') ? setupBox : settingsBox)?.refresh();
}
document.querySelectorAll('.brains').forEach(group => group.addEventListener('click', e => {
  const b = e.target.closest('.brain'); if (b) pickBrain(group.closest('.card'), b.dataset.brain);
}));
const brainOf = sel => $(sel + ' .card').dataset.brain || 'local';
let hasKey = false;

$('#setupGo').onclick = async () => {
  $('#setupErr').textContent = '';
  const brain = brainOf('#setup');
  if (brain === 'local' && !setupBox.ready()) { $('#setupErr').textContent = t('Download a model first (or pick one that says Ready).'); return; }
  const btn = $('#setupGo'); btn.disabled = true;
  try {
    await api('/api/setup', { brain, local_model: brain === 'local' ? setupBox.model() : undefined,
      api_key: brain === 'claude' ? $('#setKey').value : '', assistant_name: $('#setName').value, passcode: $('#setPass').value });
    $('#setup').hidden = true; boot();
  } catch (e) { $('#setupErr').textContent = e.message; }
  btn.disabled = false;
};

let lastState = null;
$('#btnSettings').onclick = async () => {
  const s = await api('/api/state').catch(() => null);
  if (!s) return;
  lastState = s;
  $('#sSpeak').checked = isLocal ? !!s.speak_replies : store.get('nova_speak', false);
  if (isLocal && s.settings) {
    const c = s.settings;
    hasKey = !!s.has_key;
    $('#sName').value = c.assistant_name; $('#sModel').value = c.model;
    $('#sShell').checked = c.allow_shell; $('#sConfirm').checked = c.confirm_shell;
    $('#sTop').checked = c.always_on_top; $('#sPhone').checked = c.phone_access;
    $('#sRemote').checked = c.allow_remote; $('#sWidget').checked = c.widget !== false;
    $('#sLang').value = c.language || 'auto';
    hkValues = { hotkey: c.hotkey ?? 'ctrl+alt+space', ask_hotkey: c.ask_hotkey ?? 'ctrl+shift+space', talk_hotkey: c.talk_hotkey ?? 'ctrl+shift+m' };
    showHotkeys();
    voiceEngine = c.voice_engine || 'windows'; piperSel = c.piper_voice || '';
    $('#sElevenKey').value = ''; $('#sElevenKey').placeholder = t(s.has_eleven_key ? 'Leave empty to keep the current key' : 'sk_…');
    $('#sElevenVoice').dataset.want = c.eleven_voice || ''; $('#sElevenModel').dataset.want = c.eleven_model || 'eleven_flash_v2_5';
    if (c.eleven_voice && !$('#sElevenVoice').querySelector(`option[value="${c.eleven_voice}"]`))
      $('#sElevenVoice').innerHTML = `<option value="${esc(c.eleven_voice)}">${esc(t('Saved voice'))}</option>`;
    $('#sStt').value = c.stt_model || 'base'; $('#sAutoSend').checked = c.auto_send !== false;
    $('#sGreet').checked = c.greet_on_start !== false;
    showEngine(voiceEngine);
    if (voiceEngine !== 'piper') loadPiper();             // (Piper loads its list itself)
    setColorUI(c.orb_color || '#2896FF'); $('#sTranscript').checked = c.show_transcript !== false;
    voicePrefs = { name: c.voice_name || '', rate: c.voice_rate ?? 1, pitch: c.voice_pitch ?? 1, volume: c.voice_volume ?? 1 }; $('#sVision').checked = c.local_vision;
    $('#sKey').value = ''; $('#sPass').value = '';
    $('#urls').innerHTML = s.phone_urls.length
      ? s.phone_urls.map(u => `<div><b>${esc(u.url)}</b><span>${esc(t(u.kind))}</span></div>`).join('')
      : `<div><span>${t('Turn on iPhone access first.')}</span></div>`;
    pickBrain($('#settings .card'), c.brain || 'local');
  }
  voiceUI();
  $('#settingsErr').textContent = '';
  $('#settings').hidden = false;
};
function closeSettings() {
  if (recording) stopRecording();
  $('#settings').hidden = true;
  if (lastState?.settings) both(v => v.setColor(lastState.settings.orb_color || '#2896FF'));   // undo unsaved preview
}
$('#settingsClose').onclick = closeSettings;
$('#settings').onclick = e => { if (e.target.id === 'settings') closeSettings(); };
$('#sSpeak').onchange = () => { if (!isLocal) { speak = $('#sSpeak').checked; store.set('nova_speak', speak); } };
$('#settingsSave').onclick = async () => {
  $('#settingsErr').textContent = '';
  const brain = brainOf('#settings');
  if (brain === 'local' && !settingsBox.ready()) { $('#settingsErr').textContent = t('Pick a downloaded model (or download one) for “This PC”.'); return; }
  if (brain === 'claude' && !hasKey && !$('#sKey').value) { $('#settingsErr').textContent = t('Paste a Claude API key to use Claude.'); return; }
  try {
    if ($('#sKey').value || $('#sPass').value) await api('/api/setup', { api_key: $('#sKey').value, passcode: $('#sPass').value });
    await api('/api/settings', {
      assistant_name: $('#sName').value.trim() || 'Nova', model: $('#sModel').value, brain,
      ...(brain === 'local' ? { local_model: settingsBox.model() } : {}), local_vision: $('#sVision').checked,
      allow_shell: $('#sShell').checked, confirm_shell: $('#sConfirm').checked,
      always_on_top: $('#sTop').checked, phone_access: $('#sPhone').checked, allow_remote: $('#sRemote').checked, widget: $('#sWidget').checked,
      language: $('#sLang').value, hotkey: hkValues.hotkey, ask_hotkey: hkValues.ask_hotkey, talk_hotkey: hkValues.talk_hotkey,
      voice_engine: pickedEngine(), piper_voice: piperSel, eleven_voice: $('#sElevenVoice').value || ($('#sElevenVoice').dataset.want || ''),
      eleven_model: $('#sElevenModel').value || 'eleven_flash_v2_5', eleven_key: $('#sElevenKey').value,
      stt_model: $('#sStt').value, auto_send: $('#sAutoSend').checked, greet_on_start: $('#sGreet').checked,
      orb_color: $('#sColor').value.toUpperCase(), show_transcript: $('#sTranscript').checked,
      voice_name: $('#sVoice').value, voice_rate: +$('#sRate').value, voice_pitch: +$('#sPitch').value, voice_volume: +$('#sVolume').value, speak_replies: $('#sSpeak').checked,
    });
    const before = lastState?.settings || {};
    if (before.always_on_top !== $('#sTop').checked) window.pywebview?.api.set_on_top($('#sTop').checked);
    setTimeout(async () => {                                 // tell you if Windows refused a combination
      const errs = await window.pywebview?.api.hotkey_errors?.();
      if (errs && Object.keys(errs).length) add(el('div', 'msg-err', esc(t('This hotkey could not be registered (another app may use it):') + ' ' + Object.keys(errs).map(k => prettyCombo(hkValues[k] || '')).join(', '))));
    }, 600);
    if ((before.widget !== false) !== $('#sWidget').checked) window.pywebview?.api.set_widget?.($('#sWidget').checked);
    if (lastState?.settings) Object.assign(lastState.settings, { always_on_top: $('#sTop').checked, widget: $('#sWidget').checked });
    speak = $('#sSpeak').checked; setName($('#sName').value.trim());
    voicePrefs = readVoiceUI(); voiceEngine = pickedEngine();
    if (lastState?.settings) lastState.settings.orb_color = $('#sColor').value;
    $('#settings').hidden = true;
  } catch (e) { $('#settingsErr').textContent = e.message; }
};
$('#signOut').onclick = () => { localStorage.removeItem('nova_phone'); location.reload(); };
$('#changePc').onclick = () => post({ type: 'changePC' });

// ---------- tabs (phone): Chat | Screen ----------
const remote = createRemote({ getToken: () => token, onStopAgent: () => send({ type: 'stop' }), onBack: () => showTab('chat') });
function showTab(tab) {
  if (tab === 'screen') setFull(false);
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  body.classList.toggle('tab-screen', tab === 'screen');
  if (tab === 'screen') remote.open(); else remote.close();
  try { sessionStorage.setItem('nova_tab', tab); } catch {}
}
$('#tabs').onclick = e => { const t = e.target.closest('button')?.dataset.tab; if (t) showTab(t); };

async function boot() {
  let s;
  try { s = await api('/api/state'); } catch { setTimeout(boot, 2000); return; }
  setName(s.name);
  if (!s.role) {
    if (isLocal) { $('#status b').textContent = t('Restart Nova'); return; }
    return showLogin();
  }
  if (!s.configured) {
    if (isLocal) { $('#setName').value = s.name; $('#setup').hidden = false; pickBrain($('#setup .card'), 'local'); }
    else add(el('div', 'msg-err', t('Finish setting up Nova on your PC first.')));
  }
  speak = isLocal ? !!s.speak_replies : store.get('nova_speak', false);
  applyPrefs(s);
  if (isLocal && s.settings) voiceEngine = s.settings.voice_engine || 'windows';
  if (isLocal && s.settings) voicePrefs = { name: s.settings.voice_name || '', rate: s.settings.voice_rate ?? 1, pitch: s.settings.voice_pitch ?? 1, volume: s.settings.voice_volume ?? 1 };
  if (!isLocal && s.remote) {
    $('#tabs').hidden = false; body.classList.add('has-tabs');
    if (sessionStorage.getItem('nova_tab') === 'screen') showTab('screen');
  }
  if (!ws || ws.readyState > 1) connect();
  if (isLocal && s.configured) greetOnce();
}

// ---------- start greeting: "Guten Tag, Sir. Was kann ich für Sie tun?" (once per start) ----------
function voicesReady() {
  if (!('speechSynthesis' in window) || speechSynthesis.getVoices().length) return Promise.resolve();
  return new Promise(res => {
    const done = () => { speechSynthesis.removeEventListener('voiceschanged', done); res(); };
    speechSynthesis.addEventListener('voiceschanged', done);
    setTimeout(done, 1500);
  });
}
async function greetOnce() {
  let r;
  try { r = await api('/api/greet', {}); } catch { return; }
  if (!r.say) return;                                     // already greeted, or Piper / ElevenLabs speak it
  await voicesReady();
  say(r.say, false, () => api('/api/greet/fallback', { text: r.say }).catch(() => {}));
}
boot();
// Nova as a website: works offline after the first visit (the AI model is stored by the browser too)
if (window.__novaWeb && 'serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
