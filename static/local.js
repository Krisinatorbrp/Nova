import { t } from './i18n.js';
// "This PC" brain: shows Ollama status, the GPU, and lets you download a model with progress.
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function createLocalBox(el, api) {
  let st = null, selected = null, pull = null, onChange = () => {};

  async function refresh() {
    if (!st) el.innerHTML = `<div class="lb-note">${t('Checking your PC…')}</div>`;
    try { st = await api('/api/local/status'); } catch (e) { el.innerHTML = `<div class="lb-note err">${esc(e.message)}</div>`; return; }
    if (st.pulling) pull = pull || { model: st.pulling, pct: null, status: 'downloading' };
    const have = new Set(st.models);
    if (!selected) selected = (st.selected && have.has(st.selected)) ? st.selected
      : (st.catalog.find(m => have.has(m.tag) && m.tag === st.recommended)?.tag
        || st.catalog.find(m => have.has(m.tag))?.tag || st.recommended);
    render();
  }

  function render() {
    if (!st) return;
    if (!st.running) {
      el.innerHTML = st.installed
        ? `<div class="lb-note"><b>${t('Ollama is installed but not running.')}</b>${t("It's the free program that runs the AI on your PC.")}</div>
           <button type="button" class="lb-btn" data-act="start">${t('Start Ollama')}</button>`
        : `<div class="lb-note"><b>${t('One more thing to install: Ollama')}</b>${t("It's the free program that runs the AI on your PC. Install it, then come back here.")}</div>
           <div class="lb-row2"><a class="lb-btn" href="https://ollama.com/download/windows" target="_blank" rel="noopener">${t('Get Ollama')}</a>
           <button type="button" class="lb-btn ghost" data-act="retry">${t('Check again')}</button></div>`;
      onChange(); return;
    }
    const have = new Set(st.models);
    const gpu = st.gpu?.name ? `${esc(st.gpu.name)}${st.gpu.vram_gb ? ` · ${st.gpu.vram_gb} GB` : ''}` : t('No dedicated graphics card found (it will run slower on the CPU)');
    const extra = st.models.filter(m => !st.catalog.some(c => c.tag === m) && /vl|vision|llava|gemma3|gemma4|qwen2\.5vl/i.test(m));
    const rows = [...st.catalog.map(m => ({ ...m, local: have.has(m.tag) })), ...extra.map(t => ({ tag: t, label: t, local: true }))];
    el.innerHTML = `<div class="lb-gpu">${t('Graphics')}: ${gpu}</div>` + rows.map(m => {
      const isPull = pull && pull.model === m.tag;
      const rec = m.tag === st.recommended ? `<em>${t('best for your PC')}</em>` : '';
      const right = m.local ? `<span class="lb-ok">${t('✓ Ready')}</span>`
        : isPull ? `<span class="lb-pct">${pull.pct != null ? Math.floor(pull.pct) + '%' : '…'}</span>`
        : `<button type="button" class="lb-dl" data-dl="${esc(m.tag)}" ${pull ? 'disabled' : ''}>${t('Download')}${m.size_gb ? ' ' + m.size_gb + ' GB' : ''}</button>`;
      return `<label class="lb-model ${selected === m.tag ? 'on' : ''}">
        <input type="radio" name="lbm-${el.id}" value="${esc(m.tag)}" ${selected === m.tag ? 'checked' : ''}>
        <span class="lb-name">${esc(t(m.label))} ${rec}</span>${right}
        ${isPull ? `<span class="lb-bar"><i style="width:${pull.pct || 2}%"></i></span>` : ''}</label>`;
    }).join('') + (pull?.error ? `<div class="lb-note err">${esc(pull.status)}</div>` : '');
    onChange();
  }

  el.addEventListener('change', e => { if (e.target.name?.startsWith('lbm-')) { selected = e.target.value; render(); } });
  el.addEventListener('click', async e => {
    const dl = e.target.closest('[data-dl]'), act = e.target.closest('[data-act]');
    if (dl) {
      e.preventDefault();
      selected = dl.dataset.dl; pull = { model: selected, pct: 0, status: 'starting' }; render();
      try { await api('/api/local/pull', { model: selected }); } catch (err) { pull = { ...pull, error: true, status: err.message }; render(); pull = null; }
    } else if (act?.dataset.act === 'start') {
      act.textContent = t('Starting…'); act.disabled = true;
      await api('/api/local/start', {}).catch(() => {}); st = null; refresh();
    } else if (act?.dataset.act === 'retry') { st = null; refresh(); }
  });

  return {
    refresh,
    onPull(ev) {               // progress events from the server
      pull = ev.done ? (ev.error ? { ...ev } : null) : { model: ev.model, pct: ev.pct, status: ev.status };
      if (ev.done && !ev.error) refresh(); else render();
      if (ev.done && ev.error) setTimeout(() => { pull = null; }, 0);
    },
    model: () => selected,
    ready: () => !!(st?.running && st.models.includes(selected)),
    set onChange(fn) { onChange = fn; },
  };
}
