// The AI that runs right inside the browser (Nova as a website). Uses WebGPU through WebLLM,
// so nothing is sent anywhere: the model downloads once (about 1 GB), then works offline too.
//
//   ask(text, de, name, emit)   emit({type: 'progress' | 'stream' | 'assistant' | 'state' | 'error', ...})
// shipped with the website (vendor/, added when it's published); the CDN is only a fallback
const WEBLLM = ['./vendor/web-llm.js', 'https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.79/+esm'];
const MODELS = { small: 'Qwen2.5-0.5B-Instruct', mid: 'Qwen2.5-1.5B-Instruct', big: 'Qwen2.5-3B-Instruct' };
const LOADING_KEY = 'nova_web_loading', MODEL_KEY = 'nova_web_model';

let engine = null, loading = null, history = [], stopped = false, counter = 0;
const store = {
  get: k => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};

const plain = msg => Object.assign(new Error(msg), { plain: true });   // shown as it is

async function pickModel(de) {
  if (!navigator.gpu) {
    throw plain(de ? 'Dieser Browser kann keine KI selbst ausführen (WebGPU fehlt). Nimm Safari ab iOS 26 oder einen aktuellen Chrome/Edge.'
                       : "This browser can't run the AI itself (no WebGPU). Use Safari on iOS 26+ or a current Chrome/Edge.");
  }
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) throw plain(de ? 'Kein Grafikchip für die KI gefunden.' : 'No graphics chip found for the AI.');
  const quant = adapter.features.has('shader-f16') ? 'q4f16_1' : 'q4f32_1';
  const phone = /iPhone|iPad|Android/i.test(navigator.userAgent) || (navigator.maxTouchPoints > 1 && /Mac/.test(navigator.userAgent));
  let size = phone ? 'mid' : 'big';
  const remembered = store.get(MODEL_KEY);                 // this one worked here before
  if (remembered) return remembered;
  // the page was closed while loading last time (usually: the phone ran out of memory): go smaller
  const crashed = store.get(LOADING_KEY);
  if (crashed) size = crashed.startsWith(MODELS.big) ? 'mid' : 'small';
  return `${MODELS[size]}-${quant}-MLC`;
}

function load(de, emit) {
  if (engine) return Promise.resolve(engine);
  if (loading) return loading;
  loading = (async () => {
    const model = await pickModel(de);
    store.set(LOADING_KEY, model);
    emit({ type: 'progress', text: de ? 'Lade die KI…' : 'Loading the AI…' });
    let webllm = null;
    for (const src of WEBLLM) { try { webllm = await import(src); break; } catch {} }
    if (!webllm) throw new Error(de ? 'Die KI-Bibliothek lädt nicht (bist du offline beim ersten Start?)' : "The AI library didn't load (offline on the first start?)");
    let last = 0;
    const e = await webllm.CreateMLCEngine(model, {
      initProgressCallback: r => {
        const now = performance.now();
        if (now - last < 250 && r.progress < 1) return;
        last = now;
        const pct = Math.round((r.progress || 0) * 100);
        const first = /fetch|download/i.test(r.text || '');
        emit({ type: 'progress', text: de ? `${first ? 'Lade KI herunter (nur beim ersten Mal)' : 'Starte KI'} · ${pct} %`
                                         : `${first ? 'Downloading the AI (first time only)' : 'Starting the AI'} · ${pct}%` });
      },
    }, { context_window_size: 2048 });
    store.set(LOADING_KEY, null);
    store.set(MODEL_KEY, model);
    engine = e;
    return e;
  })().catch(err => {
    loading = null;
    if (err?.plain) throw err;
    if (/fetch|network|load failed/i.test(String(err?.message || err))) {   // no internet for the first download
      store.set(LOADING_KEY, null);
      throw plain(de ? 'Für den ersten Start muss die KI einmal heruntergeladen werden (ca. 1 GB). Bitte mit dem Internet (am besten WLAN) verbinden und nochmal fragen.'
                     : 'The AI has to be downloaded once for the first start (about 1 GB). Please connect to the internet (Wi-Fi is best) and ask again.');
    }
    store.set(MODEL_KEY, null);                // next time pick again (smaller, LOADING_KEY is still set)
    throw new Error((de ? 'Die KI konnte nicht starten: ' : "The AI couldn't start: ") + (err?.message || err)
      + (de ? ' Versuch es noch einmal; beim nächsten Mal nehme ich ein kleineres Modell.' : ' Try again; next time I use a smaller model.'));
  });
  return loading;
}

function system(de, name) {
  return de
    ? `Du bist ${name}, ein persönlicher KI-Assistent. Du läufst direkt im Browser des Nutzers, ohne Internet. `
      + 'Du kannst chatten, Fragen beantworten, Texte schreiben, übersetzen und rechnen. Den PC steuern kannst du hier nicht. '
      + 'Antworte immer auf Deutsch, kurz und freundlich (1-4 Sätze), ohne Überschriften. Sprich den Nutzer mit „Sir“ an.'
    : `You are ${name}, a personal AI assistant. You run right in the user's browser, without internet. `
      + "You can chat, answer questions, write, translate and calculate. You can't control the PC from here. "
      + 'Always answer in English, short and friendly (1-4 sentences), no headings. Address the user as "sir".';
}

export async function ask(text, de, name, emit) {
  stopped = false;
  const id = `web-${++counter}`;
  try {
    const e = await load(de, emit);
    emit({ type: 'state', state: 'thinking' });
    const now = new Date().toLocaleString(de ? 'de-AT' : 'en-GB', { dateStyle: 'full', timeStyle: 'short' });
    history.push({ role: 'user', content: `${text}\n\n(${de ? 'Jetzt' : 'Now'}: ${now})` });
    while (history.length > 10 || (history.length && history[0].role !== 'user')) history.shift();
    const stream = await e.chat.completions.create({
      messages: [{ role: 'system', content: system(de, name) }, ...history],
      stream: true, max_tokens: 400, temperature: 0.6,
    });
    let out = '', last = 0;
    for await (const chunk of stream) {
      out += chunk.choices?.[0]?.delta?.content || '';
      const t = performance.now();
      if (t - last > 60 && out.trim()) { last = t; emit({ type: 'stream', id, text: out.trim() }); }
    }
    out = out.trim();
    history.push({ role: 'assistant', content: out });
    if (stopped) out = (out ? out + ' … ' : '') + (de ? '(gestoppt)' : '(stopped)');
    emit({ type: 'assistant', id, text: out || (de ? 'Hm, dazu fällt mir nichts ein.' : "Hm, I don't have an answer for that.") });
  } catch (err) {
    if (history.length && history[history.length - 1].role === 'user') history.pop();
    emit({ type: 'error', text: String(err?.message || err) });
  } finally {
    emit({ type: 'state', state: 'idle' });
  }
}

export function stop() {
  stopped = true;
  try { engine?.interruptGenerate(); } catch {}
}

export function reset() {
  stop();
  history = [];
}
