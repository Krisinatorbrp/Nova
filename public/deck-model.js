/**
 * Stream Deck buttons in the dock UI: shortcut keys, websites and multi-actions.
 *
 * Pure and DOM-free so the gate can prove it under Node. The host re-validates
 * everything (src/deck.js); these mirrors only keep the editor honest, and the
 * gate checks that both sides agree on keys, modifiers and colors.
 */

export const DECK_KINDS = Object.freeze(["hotkey", "url", "multi"]);
export const DECK_COLORS = Object.freeze(["slate", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink"]);
export const MODIFIERS = Object.freeze(["ctrl", "alt", "shift", "win"]);
export const MAX_STEPS = 10;

const NAMED_KEYS = [
  "enter", "tab", "escape", "space", "backspace", "delete", "insert", "home", "end", "pageup", "pagedown",
  "up", "down", "left", "right", "printscreen", "pause",
  "minus", "equals", "comma", "period", "slash", "semicolon", "quote",
  "bracketleft", "bracketright", "backslash", "backquote",
];
export const HOTKEY_KEYS = Object.freeze([
  ..."abcdefghijklmnopqrstuvwxyz".split(""),
  ..."0123456789".split(""),
  ...Array.from({ length: 24 }, (_, i) => `f${i + 1}`),
  ...NAMED_KEYS,
  ...Array.from({ length: 10 }, (_, i) => `numpad${i}`),
]);

const KEY_NAMES = {
  ctrl: "Ctrl", alt: "Alt", shift: "Shift", win: "Win", enter: "Enter", tab: "Tab", escape: "Esc", space: "Space",
  backspace: "Backspace", delete: "Del", insert: "Ins", home: "Home", end: "End", pageup: "PgUp", pagedown: "PgDn",
  up: "↑", down: "↓", left: "←", right: "→", printscreen: "PrtSc", pause: "Pause", minus: "-", equals: "=",
  comma: ",", period: ".", slash: "/", semicolon: ";", quote: "'", bracketleft: "[", bracketright: "]",
  backslash: "\\", backquote: "`",
};

export function keyName(part) {
  return KEY_NAMES[part] || (String(part).startsWith("numpad") ? `Num ${String(part).slice(6)}` : String(part).toUpperCase());
}

/** "ctrl+shift+m" → "Ctrl+Shift+M". */
export function hotkeyLabel(keys) {
  return String(keys || "").split("+").filter(Boolean).map(keyName).join("+");
}

/** Build the canonical combo from editor state, or "" when no key is chosen. */
export function buildHotkey(mods, key) {
  if (!HOTKEY_KEYS.includes(key)) return "";
  const chosen = new Set(Array.isArray(mods) ? mods : []);
  return [...MODIFIERS.filter((mod) => chosen.has(mod)), key].join("+");
}

export function splitHotkey(keys) {
  const parts = String(keys || "").split("+").filter(Boolean);
  return { mods: parts.slice(0, -1).filter((part) => MODIFIERS.includes(part)), key: parts.at(-1) || "" };
}

/** Same rules as the host: http(s) only, bare names get https://. */
export function normalizeUrl(value) {
  if (typeof value !== "string") return "";
  let text = value.trim();
  if (!text || text.length > 500 || /[\s\u0000-\u001f\u007f]/.test(text)) return "";
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) text = `https://${text}`;
  try {
    const url = new URL(text);
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) return "";
    return url.href.length <= 500 ? url.href : "";
  } catch { return ""; }
}

/** A short random id the host accepts (`d-` + 10 base-36 characters). */
export function newDeckId(random = Math.random) {
  let id = "d-";
  for (let i = 0; i < 10; i += 1) id += "abcdefghijklmnopqrstuvwxyz0123456789"[Math.floor(random() * 36)];
  return id;
}

export const DEFAULT_GLYPH = { hotkey: "⌨️", url: "🌐", multi: "⚡" };

/** One line under the button's label. */
export function deckHint(tile) {
  if (tile.kind === "hotkey") return hotkeyLabel(tile.keys);
  if (tile.kind === "url") {
    try { return new URL(tile.url).hostname.replace(/^www\./, ""); } catch { return "Website"; }
  }
  const count = Array.isArray(tile.steps) ? tile.steps.length : 0;
  return `${count} step${count === 1 ? "" : "s"}`;
}

const CONTROL_NAMES = {
  "volume-up": "Volume up", "volume-down": "Volume down", "mute-toggle": "Mute", "volume-set": "Set volume to",
  "media-play-pause": "Play / pause", "media-next": "Next track", "media-previous": "Previous track", "media-stop": "Stop media",
  "brightness-set": "Set brightness to",
};

export function stepSummary(step) {
  switch (step?.type) {
    case "hotkey": return `Press ${hotkeyLabel(step.keys)}`;
    case "url": return `Open ${deckHint({ kind: "url", url: step.url })}`;
    case "app": return `Open ${step.label || "app"}`;
    case "control": return CONTROL_NAMES[step.verb] ? `${CONTROL_NAMES[step.verb]}${step.value === undefined ? "" : ` ${step.value}%`}` : "Control";
    case "delay": return `Wait ${(step.ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} s`;
    default: return "Step";
  }
}

/** Wire shape of a deck tile (drops anything the host would not store). */
export function deckWireTile(tile) {
  const out = { kind: tile.kind, id: tile.id, label: tile.label || "", color: tile.color || "slate", glyph: tile.glyph || "" };
  if (tile.kind === "hotkey") out.keys = tile.keys;
  else if (tile.kind === "url") out.url = tile.url;
  else out.steps = (tile.steps || []).map((step) => ({ ...step }));
  return out;
}
