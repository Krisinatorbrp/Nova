/**
 * Stream Deck buttons: keyboard shortcuts, websites and multi-step actions.
 *
 * Every deck tile is validated here before it is saved and again before it
 * runs. Shortcuts are an allowlist of key names (never raw scan codes), URLs
 * are plain http(s) addresses, and multi-actions are a short, bounded list of
 * the same steps plus waits, so a stored button can never become a command line.
 */

import { isControlVerb, isDestructiveVerb, verbTakesValue, CONTROL_VERB_RANGES } from "./platform/contract.js";

export const DECK_KINDS = Object.freeze(["hotkey", "url", "multi"]);
export const DECK_COLORS = Object.freeze(["slate", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink"]);
export const MODIFIERS = Object.freeze(["ctrl", "alt", "shift", "win"]);
export const MAX_STEPS = 10;
export const MAX_DELAY_MS = 10000;
export const MAX_TOTAL_DELAY_MS = 30000;

const NAMED_KEYS = [
  "enter", "tab", "escape", "space", "backspace", "delete", "insert", "home", "end", "pageup", "pagedown",
  "up", "down", "left", "right", "printscreen", "pause",
  "minus", "equals", "comma", "period", "slash", "semicolon", "quote",
  "bracketleft", "bracketright", "backslash", "backquote",
];
/** Every key a shortcut may end with, in picker order. */
export const HOTKEY_KEYS = Object.freeze([
  ..."abcdefghijklmnopqrstuvwxyz".split(""),
  ..."0123456789".split(""),
  ...Array.from({ length: 24 }, (_, i) => `f${i + 1}`),
  ...NAMED_KEYS,
  ...Array.from({ length: 10 }, (_, i) => `numpad${i}`),
]);

const ID = /^d-[a-z0-9]{4,24}$/;

function cleanText(value, max) {
  if (typeof value !== "string") return "";
  return value.replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, max);
}

/**
 * Canonical shortcut string, e.g. "ctrl+shift+m", or null.
 * Modifiers are de-duplicated and ordered; exactly one non-modifier key ends it.
 */
export function normalizeHotkey(value) {
  if (typeof value !== "string" || value.length > 60) return null;
  const parts = value.toLowerCase().split("+").map((part) => part.trim()).filter(Boolean);
  if (parts.length < 1 || parts.length > 5) return null;
  const key = parts.at(-1);
  const mods = parts.slice(0, -1);
  if (!HOTKEY_KEYS.includes(key) || mods.some((mod) => !MODIFIERS.includes(mod))) return null;
  if (new Set(mods).size !== mods.length) return null;
  return [...MODIFIERS.filter((mod) => mods.includes(mod)), key].join("+");
}

/** A plain http(s) address with a host and no embedded credentials, or null. */
export function normalizeUrl(value) {
  if (typeof value !== "string") return null;
  let text = value.trim();
  if (!text || text.length > 500 || /[\s\u0000-\u001f\u007f]/.test(text)) return null;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) text = `https://${text}`;
  let url;
  try { url = new URL(text); } catch { return null; }
  if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) return null;
  const href = url.href;
  return href.length <= 500 ? href : null;
}

/** One multi-action step, or null. Power actions are excluded: they ask first. */
export function normalizeStep(raw) {
  if (!raw || typeof raw !== "object") return null;
  switch (raw.type) {
    case "hotkey": {
      const keys = normalizeHotkey(raw.keys);
      return keys ? { type: "hotkey", keys } : null;
    }
    case "url": {
      const url = normalizeUrl(raw.url);
      return url ? { type: "url", url } : null;
    }
    case "app": {
      const id = cleanText(raw.id, 400);
      return id ? { type: "app", id, label: cleanText(raw.label, 80) || id } : null;
    }
    case "control": {
      const verb = cleanText(raw.verb, 40);
      if (!isControlVerb(verb) || isDestructiveVerb(verb)) return null;
      if (!verbTakesValue(verb)) return { type: "control", verb };
      const value = Number(raw.value);
      const range = CONTROL_VERB_RANGES[verb];
      if (!Number.isInteger(value) || value < range.min || value > range.max) return null;
      return { type: "control", verb, value };
    }
    case "delay": {
      const ms = Number(raw.ms);
      if (!Number.isInteger(ms) || ms < 50 || ms > MAX_DELAY_MS) return null;
      return { type: "delay", ms };
    }
    default:
      return null;
  }
}

/** Normalize a deck tile, or return null when any part of it is unusable. */
export function normalizeDeckTile(raw) {
  if (!raw || typeof raw !== "object" || !DECK_KINDS.includes(raw.kind)) return null;
  const id = typeof raw.id === "string" && ID.test(raw.id) ? raw.id : null;
  if (!id) return null;
  const base = {
    kind: raw.kind,
    id,
    label: cleanText(raw.label, 40),
    color: DECK_COLORS.includes(raw.color) ? raw.color : "slate",
    glyph: Array.from(cleanText(raw.glyph, 16)).slice(0, 4).join(""),
  };
  if (raw.kind === "hotkey") {
    const keys = normalizeHotkey(raw.keys);
    if (!keys) return null;
    return { ...base, label: base.label || hotkeyLabel(keys), keys };
  }
  if (raw.kind === "url") {
    const url = normalizeUrl(raw.url);
    if (!url) return null;
    return { ...base, label: base.label || new URL(url).hostname.replace(/^www\./, ""), url };
  }
  if (!Array.isArray(raw.steps) || raw.steps.length < 1 || raw.steps.length > MAX_STEPS) return null;
  const steps = raw.steps.map(normalizeStep);
  if (steps.some((step) => !step)) return null;
  if (steps.every((step) => step.type === "delay")) return null;
  const waits = steps.reduce((sum, step) => sum + (step.type === "delay" ? step.ms : 0), 0);
  if (waits > MAX_TOTAL_DELAY_MS) return null;
  return { ...base, label: base.label || "Multi-action", steps };
}

const KEY_NAMES = {
  ctrl: "Ctrl", alt: "Alt", shift: "Shift", win: "Win", enter: "Enter", tab: "Tab", escape: "Esc", space: "Space",
  backspace: "Backspace", delete: "Del", insert: "Ins", home: "Home", end: "End", pageup: "PgUp", pagedown: "PgDn",
  up: "↑", down: "↓", left: "←", right: "→", printscreen: "PrtSc", pause: "Pause", minus: "-", equals: "=",
  comma: ",", period: ".", slash: "/", semicolon: ";", quote: "'", bracketleft: "[", bracketright: "]",
  backslash: "\\", backquote: "`",
};

/** "ctrl+shift+m" → "Ctrl+Shift+M". */
export function hotkeyLabel(keys) {
  return String(keys || "").split("+").filter(Boolean).map((part) =>
    KEY_NAMES[part] || (part.startsWith("numpad") ? `Num ${part.slice(6)}` : part.toUpperCase())).join("+");
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run a saved deck tile against the provider. Each step is checked again, so a
 * config file edited by hand cannot reach the provider with an unchecked value.
 * `findApp(id)` resolves an installed app for app steps; `findRunning(id)` lets a
 * running app be brought forward instead of opened again.
 */
export async function runDeckTile(raw, { provider, findApp, findRunning = async () => null, wait = sleep }) {
  const tile = normalizeDeckTile(raw);
  if (!tile) throw Object.assign(new Error("This button is not valid. Edit it and try again."), { status: 400 });
  const steps = tile.kind === "hotkey" ? [{ type: "hotkey", keys: tile.keys }]
    : tile.kind === "url" ? [{ type: "url", url: tile.url }]
      : tile.steps;
  for (const step of steps) {
    if (step.type === "hotkey") {
      if (typeof provider.sendHotkey !== "function") throw unsupported("Keyboard shortcuts");
      await provider.sendHotkey(step.keys);
    } else if (step.type === "url") {
      if (typeof provider.openUrl !== "function") throw unsupported("Opening websites");
      await provider.openUrl(step.url);
    } else if (step.type === "app") {
      const app = await findApp(step.id);
      if (!app) throw Object.assign(new Error(`${step.label} is no longer installed on your PC.`), { status: 404 });
      const running = await findRunning(step.id);
      if (running) await provider.focusApp(running);
      else await provider.launchApp(app);
    } else if (step.type === "control") {
      await provider.control(step.verb, step.value ?? null);
    } else if (step.type === "delay") {
      await wait(step.ms);
    }
  }
  return { ok: true, id: tile.id, steps: steps.length };
}

function unsupported(what) {
  return Object.assign(new Error(`${what} need an updated WinDock on this PC.`), { status: 501 });
}

/** What the phone may offer, based on what this PC's provider implements. */
export function deckCapabilities(provider) {
  return { hotkey: typeof provider?.sendHotkey === "function", url: typeof provider?.openUrl === "function" };
}
