/**
 * Stream Deck button editor: shortcut, website and multi-action buttons.
 * Builds a tile in memory; the host validates and stores it via /api/tiles.
 */

import {
  DECK_COLORS, MODIFIERS, HOTKEY_KEYS, MAX_STEPS, DEFAULT_GLYPH,
  keyName, buildHotkey, splitHotkey, normalizeUrl, newDeckId, stepSummary,
} from "./deck-model.js";
import { renderDeckFace, escapeHtml } from "./dock.js";
import { icon } from "./icons.js";

const TITLES = { hotkey: "Shortcut button", url: "Website button", multi: "Multi-action button" };
const KEY_GROUPS = [
  ["Function keys", HOTKEY_KEYS.filter((k) => /^f\d+$/.test(k))],
  ["Letters", HOTKEY_KEYS.filter((k) => /^[a-z]$/.test(k))],
  ["Numbers", HOTKEY_KEYS.filter((k) => /^\d$/.test(k))],
  ["Keys", HOTKEY_KEYS.filter((k) => k.length > 1 && !/^f\d+$/.test(k) && !k.startsWith("numpad"))],
  ["Number pad", HOTKEY_KEYS.filter((k) => k.startsWith("numpad"))],
];
const STEP_CONTROLS = [
  ["volume-up", "Volume up"], ["volume-down", "Volume down"], ["mute-toggle", "Mute"],
  ["media-play-pause", "Play / pause"], ["media-next", "Next track"], ["media-previous", "Previous track"], ["media-stop", "Stop"],
  ["volume-set:25", "Volume 25%"], ["volume-set:50", "Volume 50%"], ["volume-set:75", "Volume 75%"],
  ["brightness-set:25", "Brightness 25%"], ["brightness-set:50", "Brightness 50%"], ["brightness-set:100", "Brightness 100%"],
];

function keyOptions(selected) {
  return KEY_GROUPS.map(([group, keys]) => `<optgroup label="${group}">${keys.map((key) =>
    `<option value="${key}"${key === selected ? " selected" : ""}>${escapeHtml(keyName(key))}</option>`).join("")}</optgroup>`).join("");
}

function modButtons(container, mods, prefix) {
  container.innerHTML = MODIFIERS.map((mod) =>
    `<button type="button" class="deck-mod" data-${prefix}-mod="${mod}" aria-pressed="${mods.includes(mod)}">${keyName(mod)}</button>`).join("");
}

/**
 * @param {object} deps
 * @param {(id: string) => HTMLElement} deps.$
 * @param {() => object} deps.getState     current dock state (tiles, verbs, deck capabilities)
 * @param {() => Promise<object[]>} deps.loadApps installed apps for "Open an app" steps
 * @param {(tile: object) => Promise<void>} deps.save
 * @param {(tile: object) => Promise<void>} deps.remove
 */
export function createDeckEditor({ $, getState, loadApps, save, remove }) {
  const dialog = $("deck-editor");
  let tile = null, editingExisting = false, apps = [];

  function paintPreview() {
    $("deck-preview").innerHTML = renderDeckFace({ ...tile, glyph: $("deck-glyph").value.trim() || DEFAULT_GLYPH[tile.kind] })
      + `<span class="deck-editor__preview-label">${escapeHtml($("deck-label").value.trim() || "Button")}</span>`;
    $("deck-colors").querySelectorAll("[data-color]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.color === tile.color)));
  }

  function paintSteps() {
    const steps = tile.steps || [];
    $("deck-step-list").innerHTML = steps.length ? steps.map((step, i) => `<li><span class="deck-steps__n">${i + 1}</span><span class="deck-steps__text">${escapeHtml(stepSummary(step))}</span>`
      + `<button type="button" class="icon-button" data-step-move="${i}" data-delta="-1" aria-label="Move step ${i + 1} up"${i === 0 ? " disabled" : ""}>${icon("left")}</button>`
      + `<button type="button" class="icon-button" data-step-move="${i}" data-delta="1" aria-label="Move step ${i + 1} down"${i === steps.length - 1 ? " disabled" : ""}>${icon("right")}</button>`
      + `<button type="button" class="icon-button" data-step-remove="${i}" aria-label="Remove step ${i + 1}">${icon("trash")}</button></li>`).join("")
      : '<li class="deck-steps__empty">Add the first step below.</li>';
    $("deck-step-add").disabled = steps.length >= MAX_STEPS;
  }

  function paintStepConfig() {
    const type = $("deck-step-type").value;
    const box = $("deck-step-config");
    const caps = getState().deck || {};
    if (type === "hotkey") {
      box.innerHTML = '<div id="deck-step-mods" class="deck-mods"></div><select id="deck-step-key" aria-label="Key">' + keyOptions("f13") + "</select>";
      modButtons($("deck-step-mods"), [], "step");
      if (!caps.hotkey) box.insertAdjacentHTML("beforeend", '<p class="deck-editor__note">Shortcuts need the updated WinDock on your PC.</p>');
    } else if (type === "url") {
      box.innerHTML = '<input id="deck-step-url" type="url" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="twitch.tv/dashboard" aria-label="Website address">';
    } else if (type === "app") {
      box.innerHTML = apps.length
        ? '<select id="deck-step-app" aria-label="App">' + apps.map((app) => `<option value="${escapeHtml(app.id)}">${escapeHtml(app.name)}</option>`).join("") + "</select>"
        : '<p class="deck-editor__note">Loading your apps…</p>';
    } else if (type === "control") {
      box.innerHTML = '<select id="deck-step-control" aria-label="Control">' + STEP_CONTROLS
        .filter(([key]) => (getState().verbs || []).includes(key.split(":")[0]))
        .map(([key, label]) => `<option value="${key}">${label}</option>`).join("") + "</select>";
    } else {
      box.innerHTML = '<label class="deck-inline">Seconds <input id="deck-step-delay" type="number" min="0.1" max="10" step="0.1" value="0.5" inputmode="decimal"></label>';
    }
  }

  function readStep() {
    const type = $("deck-step-type").value;
    if (type === "hotkey") {
      const mods = [...$("deck-step-mods").querySelectorAll('[aria-pressed="true"]')].map((b) => b.dataset.stepMod);
      const keys = buildHotkey(mods, $("deck-step-key").value);
      return keys ? { type, keys } : null;
    }
    if (type === "url") {
      const url = normalizeUrl($("deck-step-url").value);
      return url ? { type, url } : null;
    }
    if (type === "app") {
      const app = apps.find((a) => a.id === $("deck-step-app")?.value);
      return app ? { type, id: app.id, label: app.name } : null;
    }
    if (type === "control") {
      const [verb, value] = String($("deck-step-control")?.value || "").split(":");
      if (!verb) return null;
      return value === undefined ? { type, verb } : { type, verb, value: Number(value) };
    }
    const seconds = Number($("deck-step-delay").value);
    const ms = Math.round(seconds * 1000);
    return Number.isFinite(ms) && ms >= 50 && ms <= 10000 ? { type: "delay", ms } : null;
  }

  function error(message = "") { $("deck-error").textContent = message; }

  async function open(source) {
    editingExisting = typeof source === "object";
    tile = editingExisting ? JSON.parse(JSON.stringify(source)) : { kind: source, id: newDeckId(), label: "", color: "slate", glyph: "" };
    if (tile.kind === "multi" && !Array.isArray(tile.steps)) tile.steps = [];
    $("deck-editor-title").textContent = (editingExisting ? "Edit " : "New ") + TITLES[tile.kind].toLowerCase();
    $("deck-label").value = tile.label || "";
    $("deck-glyph").value = tile.glyph || "";
    $("deck-colors").innerHTML = DECK_COLORS.map((color) => `<button type="button" role="radio" class="deck-swatch deck-key--${color}" data-color="${color}" aria-label="${color}"></button>`).join("");
    for (const kind of ["hotkey", "url", "multi"]) $(kind === "multi" ? "deck-steps" : `deck-${kind}`).hidden = tile.kind !== kind;
    if (tile.kind === "hotkey") {
      // New shortcuts start on F13: no other app uses it, so OBS or Discord can bind it.
      const { mods, key } = splitHotkey(tile.keys || "f13");
      modButtons($("deck-mods"), mods, "main");
      $("deck-key").innerHTML = keyOptions(key || "f13");
    }
    if (tile.kind === "url") $("deck-url-input").value = tile.url || "";
    if (tile.kind === "multi") { paintSteps(); paintStepConfig(); }
    $("deck-delete").hidden = !editingExisting;
    error();
    paintPreview();
    if (!dialog.open) dialog.showModal();
    if (tile.kind === "multi" && !apps.length) {
      try { apps = await loadApps(); if ($("deck-step-type").value === "app") paintStepConfig(); } catch { /* app steps stay unavailable */ }
    }
  }

  dialog.addEventListener("click", (event) => {
    const swatch = event.target.closest("[data-color]");
    if (swatch) { tile.color = swatch.dataset.color; paintPreview(); return; }
    const mod = event.target.closest("[data-main-mod], [data-step-mod]");
    if (mod) { mod.setAttribute("aria-pressed", String(mod.getAttribute("aria-pressed") !== "true")); return; }
    const move = event.target.closest("[data-step-move]");
    if (move) {
      const i = Number(move.dataset.stepMove), j = i + Number(move.dataset.delta);
      if (j >= 0 && j < tile.steps.length) [tile.steps[i], tile.steps[j]] = [tile.steps[j], tile.steps[i]];
      paintSteps(); return;
    }
    const drop = event.target.closest("[data-step-remove]");
    if (drop) { tile.steps.splice(Number(drop.dataset.stepRemove), 1); paintSteps(); }
  });
  $("deck-label").addEventListener("input", paintPreview);
  $("deck-glyph").addEventListener("input", paintPreview);
  $("deck-step-type").addEventListener("change", paintStepConfig);
  $("deck-step-add").addEventListener("click", () => {
    const step = readStep();
    if (!step) return error("Finish this step first: choose a key, a website, an app or a time.");
    if (tile.steps.length >= MAX_STEPS) return error(`A button can have up to ${MAX_STEPS} steps.`);
    error(); tile.steps.push(step); paintSteps();
    if (step.type === "url") $("deck-step-url").value = "";
  });
  $("deck-delete").addEventListener("click", async () => {
    try { await remove(tile); dialog.close(); } catch (e) { error(e.message || "Couldn’t delete the button."); }
  });
  $("deck-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    tile.label = $("deck-label").value.trim();
    tile.glyph = $("deck-glyph").value.trim();
    if (tile.kind === "hotkey") {
      const mods = [...$("deck-mods").querySelectorAll('[aria-pressed="true"]')].map((b) => b.dataset.mainMod);
      tile.keys = buildHotkey(mods, $("deck-key").value);
      if (!tile.keys) return error("Choose a key for the shortcut.");
    } else if (tile.kind === "url") {
      tile.url = normalizeUrl($("deck-url-input").value);
      if (!tile.url) return error("Enter a website address, for example youtube.com.");
    } else {
      if (!tile.steps.length) return error("Add at least one step.");
      if (tile.steps.every((step) => step.type === "delay")) return error("Add a step that does something, not only waits.");
      const waits = tile.steps.reduce((sum, step) => sum + (step.type === "delay" ? step.ms : 0), 0);
      if (waits > 30000) return error("Waits can add up to 30 seconds per button.");
    }
    $("deck-save").disabled = true;
    try { await save(tile); dialog.close(); }
    catch (e) { error(e.message || "Couldn’t save the button."); }
    finally { $("deck-save").disabled = false; }
  });

  return { open };
}

/** The Stream Deck tab in "Add to your dock". */
export function renderDeckPicker(caps = {}) {
  const items = [
    ["hotkey", "⌨️", "Keyboard shortcut", "Ctrl+Shift+M, F13–F24, Alt+Tab…", caps.hotkey],
    ["url", "🌐", "Website", "Opens in your PC’s browser", caps.url],
    ["multi", "⚡", "Multi-action", "Several steps from one press", true],
  ];
  return items.map(([kind, glyph, name, hint, ok]) => `<li><button type="button" data-deck-new="${kind}"${ok ? "" : " disabled"}>`
    + `<span class="picker__symbol deck-picker__glyph">${glyph}</span><span class="picker__name">${name}<small>${ok ? hint : "Needs the updated WinDock on your PC"}</small></span>`
    + `<span class="picker__add">${icon("plus")}</span></button></li>`).join("");
}
