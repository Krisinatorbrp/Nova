// Nova's look: a blue particle sphere (popup window) and holographic HUD rings (fullscreen).
// Both react to what the assistant is doing, and pulse while it speaks.
//
//   const v = createVisual(canvas, { mode: 'particles' | 'rings' })
//   v.setState('idle' | 'thinking' | 'acting' | 'waiting' | 'listening')
//   v.setName('Nova')           – text in the middle of the rings
//   v.speakStart() / v.speakEnd() / v.kick()  – speaking animation (kick = one syllable/word)
//   v.speakFor(ms)              – fake speaking when voice output is off
//   v.pulse()                   – small burst (an action happened)

const STATES = {
  idle:      { speed: 1.0, energy: 0.10 },
  thinking:  { speed: 2.4, energy: 0.35 },
  acting:    { speed: 3.0, energy: 0.45 },
  waiting:   { speed: 0.8, energy: 0.25, hue: [1.00, 0.70, 0.25] },   // amber: needs your OK
  listening: { speed: 1.8, energy: 0.55 },
};
export function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
  return m ? [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255] : [0.16, 0.59, 1.0];
}
const AMBER = 'rgba(255,170,40,';

// tiny smooth noise
function hash(n) { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); }
function noise1(x) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return hash(i) * (1 - u) + hash(i + 1) * u; }

let fontReady = false;
if (document.fonts?.load) document.fonts.load('700 40px Orbitron').then(() => { fontReady = true; }).catch(() => {});

export function createVisual(canvas, opts = {}) {
  const ctx = canvas.getContext('2d');
  let mode = opts.mode || 'particles';
  let name = opts.name || 'Nova';
  let target = STATES.idle;
  let base = hexToRgb(opts.color || '#2896FF');          // the orb colour you picked
  const cur = { speed: 1, energy: 0.1, hue: [...base] };
  let t = 0, last = performance.now(), boost = 0;
  // speaking
  let speaking = false, speakUntil = 0, level = 0, kickV = 0;
  let W = 0, H = 0, dpr = 1;

  // ---------- particles ----------
  const N = 520;
  const pts = [];
  for (let i = 0; i < N; i++) {           // evenly spread over a sphere
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
    pts.push({ x: Math.cos(th) * r, y, z: Math.sin(th) * r, seed: Math.random() * 100, s: 0.6 + Math.random() * 0.9 });
  }
  const sparks = Array.from({ length: 70 }, () => ({
    a: Math.random() * Math.PI * 2, r: 1.15 + Math.random() * 0.55, v: 0.2 + Math.random() * 0.6,
    tilt: (Math.random() - 0.5) * 1.6, s: 0.4 + Math.random() * 0.8, seed: Math.random() * 100,
  }));
  const sprite = document.createElement('canvas');
  const rgb = (c, a, lift = 0) => `rgba(${Math.round((c[0] + (1 - c[0]) * lift) * 255)},${Math.round((c[1] + (1 - c[1]) * lift) * 255)},${Math.round((c[2] + (1 - c[2]) * lift) * 255)},${a})`;
  function makeSprite() {
    sprite.width = sprite.height = 64;
    const g = sprite.getContext('2d'), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.clearRect(0, 0, 64, 64);
    gr.addColorStop(0, 'rgba(255,255,255,1)');
    gr.addColorStop(0.18, rgb(base, 0.9, 0.55));
    gr.addColorStop(0.45, rgb(base, 0.35));
    gr.addColorStop(1, rgb(base, 0));
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  }
  makeSprite();

  // size is tracked by the browser (no layout work every frame); a hidden canvas reports 0 x 0
  function applySize(w, h) {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = w; H = h;
    const cw = Math.max(1, Math.round(w * dpr)), ch = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
  }
  if ('ResizeObserver' in window) {
    new ResizeObserver(([e]) => applySize(e.contentRect.width, e.contentRect.height)).observe(canvas);
  }
  function resize() {                       // fallback for old browsers
    const r = canvas.getBoundingClientRect(); applySize(r.width, r.height);
  }

  function drawParticles(e, lv) {
    const S = Math.min(W, H), cx = W / 2, cy = H / 2, R = S * 0.30 * (1 + lv * 0.10 + boost * 0.06);
    // core glow
    let g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.9);
    g.addColorStop(0, rgb(cur.hue.map(v => v * 0.8), 0.30 + lv * 0.25));
    g.addColorStop(0.45, rgb(cur.hue.map(v => v * 0.35), 0.12 + lv * 0.1));
    g.addColorStop(1, 'rgba(0,20,60,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    ctx.globalCompositeOperation = 'lighter';
    const ry = t * 0.35, rx = 0.45 + Math.sin(t * 0.13) * 0.25;
    const cyr = Math.cos(ry), syr = Math.sin(ry), cxr = Math.cos(rx), sxr = Math.sin(rx);
    const base = S * 0.022;
    for (const p of pts) {
      // breathing / speaking ripples on the surface
      const wob = 1 + (noise1(p.seed + t * (0.6 + e)) - 0.5) * (0.08 + e * 0.35)
                    + lv * 0.22 * Math.sin(p.y * 6 + t * 9 + p.seed);
      let x = p.x * wob, y = p.y * wob, z = p.z * wob;
      let x1 = x * cyr - z * syr, z1 = x * syr + z * cyr;            // spin
      let y1 = y * cxr - z1 * sxr, z2 = y * sxr + z1 * cxr;          // tilt
      const persp = 1 / (1.9 - z2 * 0.6);
      const px = cx + x1 * R * persp * 1.3, py = cy + y1 * R * persp * 1.3;
      const depth = (z2 + 1) / 2;                                    // 0 back .. 1 front
      const sz = base * p.s * (0.45 + depth * 0.9) * (1 + lv * 0.5);
      ctx.globalAlpha = 0.18 + depth * 0.7;
      ctx.drawImage(sprite, px - sz, py - sz, sz * 2, sz * 2);
    }
    // orbiting sparks
    for (const s of sparks) {
      s.a += s.v * 0.004 * (1 + cur.speed * 1.5 + lv * 3);
      const rr = R * (s.r + lv * 0.35 * Math.sin(t * 3 + s.seed));
      const x = Math.cos(s.a) * rr, z = Math.sin(s.a) * rr, y = z * s.tilt * 0.5;
      const depth = (Math.sin(s.a) + 1) / 2;
      const sz = base * s.s * (0.5 + depth * 0.7);
      ctx.globalAlpha = (0.25 + depth * 0.6) * (0.4 + noise1(s.seed + t * 2) * 0.6);
      ctx.drawImage(sprite, cx + x - sz, cy + y * 0.6 - sz, sz * 2, sz * 2);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  // ---------- rings ----------
  function ring(cx, cy, r, width, color, a0 = 0, a1 = Math.PI * 2) {
    ctx.beginPath(); ctx.arc(cx, cy, r, a0, a1); ctx.lineWidth = width; ctx.strokeStyle = color; ctx.stroke();
  }
  function ticks(cx, cy, r, len, count, rot, color, width, every = 0, longLen = 0) {
    ctx.beginPath();
    for (let i = 0; i < count; i++) {
      const a = rot + i / count * Math.PI * 2, l = every && i % every === 0 ? longLen : len;
      ctx.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.lineTo(cx + Math.cos(a) * (r + l), cy + Math.sin(a) * (r + l));
    }
    ctx.lineWidth = width; ctx.strokeStyle = color; ctx.stroke();
  }
  function band(cx, cy, r0, r1, a0, a1, fill) {
    ctx.beginPath(); ctx.arc(cx, cy, r1, a0, a1); ctx.arc(cx, cy, r0, a1, a0, true); ctx.closePath();
    ctx.fillStyle = fill; ctx.fill();
  }

  function drawRings(e, lv) {
    const S = Math.min(W, H) * 0.96, cx = W / 2, cy = H / 2;
    const k = 1 + lv * 0.035 + boost * 0.02;          // the whole HUD "breathes" when speaking
    const C = (a) => rgb(cur.hue, a, 0.3);
    const tint = (a) => rgb(cur.hue, a, 0.1);
    const glowCol = rgb(cur.hue, 0.85, 0.3);
    const sp = t;                                      // already speed-scaled time

    // background glow + faint blueprint circles
    let g = ctx.createRadialGradient(cx, cy, 0, cx, cy, S * 0.55);
    g.addColorStop(0, rgb(cur.hue.map(v => v * 0.6), 0.22 + lv * 0.2));
    g.addColorStop(0.6, rgb(cur.hue.map(v => v * 0.3), 0.10));
    g.addColorStop(1, 'rgba(0,10,30,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.translate(cx, cy); ctx.scale(k, k); ctx.translate(-cx, -cy);
    ctx.shadowColor = glowCol;

    for (let i = 0; i < 4; i++) ring(cx, cy, S * (0.10 + i * 0.045), 1, C(0.06));

    // 1. outer fine tick ring (slow clockwise)
    ctx.shadowBlur = 0;
    ring(cx, cy, S * 0.475, 1.2, C(0.35));
    ticks(cx, cy, S * 0.478, S * 0.010, 120, sp * 0.05, C(0.55), 1.2, 10, S * 0.026);

    // 2. thick segmented band (counter-clockwise), brightens when speaking
    const rot2 = -sp * 0.11;
    const bandA = 0.20 + e * 0.15 + lv * 0.35;
    band(cx, cy, S * 0.405, S * 0.448, rot2 + 3.55, rot2 + 6.05, tint(bandA));
    band(cx, cy, S * 0.405, S * 0.448, rot2 + 0.25, rot2 + 1.35, tint(bandA * 0.7));
    band(cx, cy, S * 0.405, S * 0.448, rot2 + 1.55, rot2 + 2.0, tint(bandA * 0.5));
    ring(cx, cy, S * 0.405, 1.5, C(0.55)); ring(cx, cy, S * 0.448, 1.5, C(0.4));
    // little segment notches on the band
    ticks(cx, cy, S * 0.405, S * 0.043, 64, rot2, 'rgba(0,30,60,0.55)', 2);

    // 3. bright dots riding the band (amber)
    ctx.shadowColor = 'rgba(255,190,60,0.9)'; ctx.shadowBlur = 8;
    for (let i = 0; i < 5; i++) {
      const a = rot2 + 4.35 + i * 0.13;
      ctx.beginPath(); ctx.arc(cx + Math.cos(a) * S * 0.427, cy + Math.sin(a) * S * 0.427, S * 0.0055, 0, 7);
      ctx.fillStyle = AMBER + (0.65 + 0.35 * Math.sin(t * 4 + i)) + ')'; ctx.fill();
    }

    // 4. amber bracket arc (opposite direction)
    const rot4 = sp * 0.17 + 2.6;
    ctx.shadowBlur = 10;
    ring(cx, cy, S * 0.372, S * 0.008, AMBER + '0.85)', rot4, rot4 + 0.75);
    ring(cx, cy, S * 0.372, S * 0.004, AMBER + '0.6)', rot4 + 0.82, rot4 + 1.05);
    for (const a of [rot4, rot4 + 1.05]) {
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * S * 0.355, cy + Math.sin(a) * S * 0.355);
      ctx.lineTo(cx + Math.cos(a) * S * 0.39, cy + Math.sin(a) * S * 0.39);
      ctx.lineWidth = 2; ctx.strokeStyle = AMBER + '0.8)'; ctx.stroke();
    }

    // 5. main bright ring with gaps
    ctx.shadowColor = glowCol; ctx.shadowBlur = 14 + lv * 18;
    const rot5 = sp * 0.07;
    for (let i = 0; i < 4; i++) {
      const a = rot5 + i * Math.PI / 2;
      ring(cx, cy, S * 0.335, S * 0.012, C(0.75 + lv * 0.25), a + 0.08, a + Math.PI / 2 - 0.08);
    }

    // 6. voice waveform: bars around the inner circle
    ctx.shadowBlur = 6 + lv * 10;
    const bars = 96, r6 = S * 0.285;
    ctx.beginPath();
    for (let i = 0; i < bars; i++) {
      const a = i / bars * Math.PI * 2 - sp * 0.02;
      const n = noise1(i * 0.7 + t * 6) * 0.6 + noise1(i * 0.21 - t * 3) * 0.4;
      const len = S * (0.006 + e * 0.01 + lv * 0.06 * n + kickV * 0.02 * n);
      ctx.moveTo(cx + Math.cos(a) * r6, cy + Math.sin(a) * r6);
      ctx.lineTo(cx + Math.cos(a) * (r6 + len), cy + Math.sin(a) * (r6 + len));
    }
    ctx.lineWidth = Math.max(1.5, S * 0.004); ctx.strokeStyle = C(0.85); ctx.stroke();

    // 7. inner double ring + dashed spinner
    ctx.shadowBlur = 8;
    ring(cx, cy, S * 0.262, 1.5, C(0.6));
    ring(cx, cy, S * 0.250, 1, C(0.35));
    ctx.setLineDash([S * 0.012, S * 0.018]); ctx.lineDashOffset = -sp * S * 0.04;
    ring(cx, cy, S * 0.228, 2, C(0.55));
    ctx.setLineDash([]);

    // 8. scanner sweep while thinking / working
    if (e > 0.2) {
      const a = t * 1.8;
      for (let i = 0; i < 18; i++) {
        ring(cx, cy, S * 0.31, S * 0.035, tint((e - 0.15) * 0.18 * (1 - i / 18)), a - i * 0.04 - 0.04, a - i * 0.04);
      }
    }

    // 9. the name in the middle
    ctx.shadowColor = glowCol; ctx.shadowBlur = 18 + lv * 22;
    const label = name.toUpperCase().split('').join(' ');
    let fs = Math.min(S * 0.075, (S * 0.36) / Math.max(3, name.length * 0.95));
    ctx.font = `700 ${fs}px ${fontReady ? 'Orbitron' : ''}, "Segoe UI", system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    try { ctx.letterSpacing = `${fs * 0.18}px`; } catch {}
    const grad = ctx.createLinearGradient(cx, cy - fs, cx, cy + fs);
    grad.addColorStop(0, '#ffffff'); grad.addColorStop(0.55, rgb(cur.hue, 1, 0.85)); grad.addColorStop(1, rgb(cur.hue, 1, 0.45));
    ctx.fillStyle = grad;
    ctx.globalAlpha = 0.85 + lv * 0.15;
    ctx.fillText(label, cx + fs * 0.09, cy);
    ctx.globalAlpha = 1;
    try { ctx.letterSpacing = '0px'; } catch {}
    ctx.restore();
    ctx.shadowBlur = 0;
  }

  // ---------- loop ----------
  // frame-rate caps: no need to draw 144 times a second on fast monitors, and less while idle
  let paused = false, lastDraw = 0;
  function frameGap(now) {
    if (mode === 'rings') return 1000 / 60;
    const busy = speaking || now < speakUntil || target !== STATES.idle || boost > 0.05;
    return busy ? 1000 / 45 : 1000 / 30;
  }
  function frame(now) {
    if (paused) return;                                  // window hidden: no work at all
    requestAnimationFrame(frame);
    if (document.hidden) return;
    if (!('ResizeObserver' in window)) resize();
    if (W < 2 || H < 2) return;                          // not visible: skip work
    if (now - lastDraw < frameGap(now) - 2) return;
    lastDraw = now;
    const dt = Math.min((now - last) / 1000, 0.05); last = now;
    const kk = 1 - Math.pow(0.03, dt);
    cur.speed += (target.speed - cur.speed) * kk;
    cur.energy += (target.energy - cur.energy) * kk;
    const want = target.hue || base;
    for (let i = 0; i < 3; i++) cur.hue[i] += (want[i] - cur.hue[i]) * kk;
    boost += (0 - boost) * (1 - Math.pow(0.08, dt));
    kickV += (0 - kickV) * (1 - Math.pow(0.02, dt));

    const talking = speaking || now < speakUntil;
    // speech envelope: syllable-like wobble plus word "kicks"
    const env = talking ? 0.35 + 0.65 * Math.abs(Math.sin(now * 0.017) * noise1(now * 0.004)) + kickV * 0.5 : 0;
    level += (Math.min(env, 1.2) - level) * (1 - Math.pow(talking ? 0.0005 : 0.02, dt));

    t += dt * (cur.speed + level * 1.5 + boost);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (mode === 'rings') drawRings(cur.energy, level); else drawParticles(cur.energy, level);
  }
  requestAnimationFrame(frame);

  return {
    pause(on) {
      on = !!on;
      if (on === paused) return;
      paused = on;
      if (!on) { last = performance.now(); requestAnimationFrame(frame); }
    },
    setState(s) { target = STATES[s] || STATES.idle; },
    setMode(m) { mode = m; },
    setColor(hex) { base = hexToRgb(hex); makeSprite(); },
    setName(n) { name = (n || 'Nova').slice(0, 24); },
    pulse() { boost = 1; },
    kick() { kickV = 1; },
    speakStart() { speaking = true; kickV = 1; },
    speakEnd() { speaking = false; },
    speakFor(ms) { speakUntil = performance.now() + ms; kickV = 1; },
    get speaking() { return speaking || performance.now() < speakUntil; },
  };
}
