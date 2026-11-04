/** Stream Deck buttons: shortcut, website and multi-action tiles, end to end. */
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createChecker } from "./lib/assert.mjs";
import * as host from "../src/deck.js";
import * as model from "../public/deck-model.js";
import { normalizeTile, normalizeTiles, createConfigStore } from "../src/config.js";
import { tileKey, toWireTiles, upsertDeckTile, removeTile } from "../public/tiles.js";
import { renderTile } from "../public/dock.js";
import { normalizeLayout } from "../public/launcher.js";
import { createWindowsProvider } from "../src/platform/windows.js";
import { createLinuxProvider } from "../src/platform/linux.js";
import { createApp } from "../server.js";

const t = createChecker("deck");

// ---- the phone and the PC agree on what a button may contain ----
t.deepEqual(model.HOTKEY_KEYS, host.HOTKEY_KEYS, "editor and host offer the same keys");
t.deepEqual(model.MODIFIERS, host.MODIFIERS, "editor and host use the same modifier order");
t.deepEqual(model.DECK_COLORS, host.DECK_COLORS, "editor and host share the colour palette");
t.deepEqual(model.DECK_KINDS, host.DECK_KINDS, "editor and host share the button kinds");
t.equal(model.MAX_STEPS, host.MAX_STEPS, "editor and host share the step limit");
for (const url of ["youtube.com", "https://twitch.tv/dashboard", "http://192.168.1.5:8080/x?y=1", "ftp://x", "javascript:alert(1)", "https://a:b@c.d", "a b"]) {
  t.equal(model.normalizeUrl(url), host.normalizeUrl(url) ?? "", `editor and host agree on ${url}`);
}

// ---- shortcuts ----
t.equal(host.normalizeHotkey("Shift+CTRL+m"), "ctrl+shift+m", "modifiers are lower-cased and ordered");
t.equal(host.normalizeHotkey("f13"), "f13", "a bare F-key is a shortcut");
t.equal(host.normalizeHotkey("win+alt+numpad7"), "alt+win+numpad7", "win and numpad keys are supported");
for (const bad of ["", "ctrl", "ctrl+ctrl+m", "hyper+m", "ctrl+shift+alt+win+m+x", "ctrl+mm", "f25", "ctrl+;", "ctrl+m; calc", null, 7]) {
  t.equal(host.normalizeHotkey(bad), null, `shortcut rejected: ${JSON.stringify(bad)}`);
}
t.equal(model.buildHotkey(["shift", "ctrl"], "m"), "ctrl+shift+m", "the editor builds canonical shortcuts");
t.deepEqual(model.splitHotkey("ctrl+alt+delete"), { mods: ["ctrl", "alt"], key: "delete" }, "the editor splits shortcuts back");
t.equal(model.hotkeyLabel("ctrl+shift+left"), "Ctrl+Shift+←", "shortcut labels are readable");

// ---- websites ----
t.equal(host.normalizeUrl("youtube.com"), "https://youtube.com/", "bare names become https");
for (const bad of ["file:///C:/Windows/notepad.exe", "javascript:alert(1)", "ms-settings:", "steam://run/1", "https://user:pw@x.com", "https://exa mple.com", "x".repeat(600)]) {
  t.equal(host.normalizeUrl(bad), null, `website rejected: ${bad.slice(0, 40)}`);
}

// ---- tiles ----
const hotkey = { kind: "hotkey", id: "d-abc123", label: "Mute mic", color: "red", glyph: "🎙️", keys: "ctrl+shift+m" };
const url = { kind: "url", id: "d-web001", label: "", url: "twitch.tv", color: "purple" };
const multi = {
  kind: "multi", id: "d-multi1", label: "Go live", color: "green", glyph: "🔴",
  steps: [{ type: "app", id: "c:/obs.exe", label: "OBS" }, { type: "delay", ms: 500 }, { type: "hotkey", keys: "f13" }, { type: "url", url: "https://twitch.tv" }, { type: "control", verb: "volume-set", value: 30 }],
};
t.deepEqual(normalizeTile(hotkey), hotkey, "a shortcut tile is stored as sent");
t.equal(normalizeTile(url).url, "https://twitch.tv/", "a website tile stores a full address");
t.equal(normalizeTile(url).label, "twitch.tv", "an unnamed website button is named after its site");
t.equal(normalizeTile(url).color, "purple", "colours are kept");
t.equal(normalizeTile(multi).steps.length, 5, "a multi-action keeps its steps");
t.equal(normalizeTile({ ...hotkey, color: "#ff0000" }).color, "slate", "unknown colours fall back");
t.equal(Array.from(normalizeTile({ ...hotkey, glyph: "🎮🎮🎮🎮🎮🎮" }).glyph).length, 4, "symbols are short");
for (const [why, bad] of [
  ["bad id", { ...hotkey, id: "../../x" }],
  ["bad shortcut", { ...hotkey, keys: "ctrl+evil" }],
  ["bad website", { ...url, url: "file:///c:/x" }],
  ["power step", { ...multi, steps: [{ type: "control", verb: "shutdown" }] }],
  ["only waits", { ...multi, steps: [{ type: "delay", ms: 500 }] }],
  ["too many steps", { ...multi, steps: Array.from({ length: 11 }, () => ({ type: "hotkey", keys: "f13" })) }],
  ["long waits", { ...multi, steps: [{ type: "delay", ms: 10000 }, { type: "delay", ms: 10000 }, { type: "delay", ms: 10000 }, { type: "delay", ms: 1000 }, { type: "hotkey", keys: "f1" }] }],
  ["unknown step", { ...multi, steps: [{ type: "shell", command: "calc" }] }],
  ["no steps", { ...multi, steps: [] }],
]) t.equal(normalizeTile(bad), null, `deck tile rejected: ${why}`);
t.equal(normalizeTiles([hotkey, { ...hotkey, label: "dupe" }, url]).length, 2, "deck ids are unique on the dock");

const tiles = upsertDeckTile(upsertDeckTile([], hotkey), url);
t.deepEqual(tiles.map(tileKey), ["deck:d-abc123", "deck:d-web001"], "new buttons are appended");
const edited = upsertDeckTile(tiles, { ...hotkey, label: "Mute Discord" });
t.equal(edited[0].label, "Mute Discord", "editing a button replaces it in place");
t.equal(edited.length, 2, "editing does not add a copy");
t.deepEqual(removeTile(edited, "deck:d-abc123").map(tileKey), ["deck:d-web001"], "buttons can be removed");
t.deepEqual(toWireTiles([{ ...hotkey, running: true, extra: "x" }]), [hotkey], "only stored fields go back to the PC");

const face = renderTile({ ...hotkey, label: '<img src=x onerror="a()">', glyph: "<b>" });
t.ok(face.includes('data-action="deck"') && face.includes('data-key="d-abc123"'), "a deck key runs by id");
t.ok(face.includes("deck-key--red") && face.includes("Ctrl+Shift+M"), "a deck key shows its colour and shortcut");
t.ok(!face.includes("<img") && !face.includes("<b>"), "labels and symbols cannot inject markup");

const deckGrid = normalizeLayout({ perPage: 15 });
t.deepEqual([deckGrid.columns, deckGrid.rows], [5, 3], "the Stream Deck layout is five keys by three rows");
t.equal(normalizeLayout({ perPage: 12 }).perPage, 4, "unsupported densities still reset");

// ---- providers dispatch fixed argv only ----
const winCalls = [];
const win = createWindowsProvider({ helperPath: "H.exe", exec: async (file, args) => { winCalls.push([file, ...args]); return { stdout: "" }; } });
await win.sendHotkey("shift+ctrl+m");
await win.openUrl("https://twitch.tv/");
t.deepEqual(winCalls, [["H.exe", "hotkey", "ctrl+shift+m"], ["H.exe", "open-url", "https://twitch.tv/"]], "Windows sends canonical helper argv");
await t.rejects(() => win.sendHotkey("ctrl+evil"), "Windows refuses an unknown shortcut");
await t.rejects(() => win.openUrl("file:///c:/x"), "Windows refuses a non-web address");
t.equal(winCalls.length, 2, "rejected input never reaches the helper");
t.deepEqual(host.deckCapabilities(win), { hotkey: true, url: true }, "Windows offers shortcuts and websites");

const linuxCalls = [];
const linux = createLinuxProvider({ exec: async (file, args) => { linuxCalls.push([file, ...args]); return { stdout: "" }; } });
await linux.openUrl("example.com");
t.deepEqual(linuxCalls.at(-1), ["xdg-open", "https://example.com/"], "Linux opens websites with xdg-open");
t.deepEqual(host.deckCapabilities(linux), { hotkey: false, url: true }, "Linux does not offer shortcuts yet");

// ---- run order, waits and errors ----
const calls = [];
const fake = {
  sendHotkey: async (keys) => calls.push(`hotkey ${keys}`),
  openUrl: async (href) => calls.push(`url ${href}`),
  launchApp: async (app) => calls.push(`launch ${app.id}`),
  focusApp: async (app) => calls.push(`focus ${app.id}`),
  control: async (verb, value) => calls.push(`control ${verb} ${value}`),
};
const waits = [];
await host.runDeckTile(multi, { provider: fake, findApp: async (id) => ({ id }), wait: async (ms) => { waits.push(ms); calls.push(`wait ${ms}`); } });
t.deepEqual(calls, ["launch c:/obs.exe", "wait 500", "hotkey f13", "url https://twitch.tv/", "control volume-set 30"], "multi-action steps run in order");
calls.length = 0;
await host.runDeckTile(multi, { provider: fake, findApp: async (id) => ({ id }), findRunning: async (id) => ({ id, pid: 4 }), wait: async () => {} });
t.equal(calls[0], "focus c:/obs.exe", "an app that is already open is brought forward");
await t.rejects(() => host.runDeckTile(multi, { provider: fake, findApp: async () => null, wait: async () => {} }), "a missing app stops the button");
await t.rejects(() => host.runDeckTile(hotkey, { provider: { ...fake, sendHotkey: undefined }, findApp: async () => null }), "shortcuts fail clearly without PC support");
await t.rejects(() => host.runDeckTile({ ...hotkey, keys: "ctrl+evil" }, { provider: fake, findApp: async () => null }), "a hand-edited invalid button never runs");

// ---- the host API ----
const apiCalls = [];
const provider = createWindowsProvider({
  helperPath: "H.exe",
  exec: async (file, args) => {
    if (file === "H.exe") { apiCalls.push(args.join(" ")); return { stdout: "" }; }
    const script = args[args.length - 1];
    if (script.includes("MainWindowHandle")) return { stdout: "[]" };
    if (script.includes("WScript.Shell")) return { stdout: "[]" };
    return { stdout: "{}" };
  },
});
const dir = await mkdtemp(join(tmpdir(), "windock-deck-"));
const configStore = createConfigStore({ path: join(dir, "config.json") });
const app = await createApp({ provider, configStore, pin: "222222", trustLoopback: true });
await new Promise((r) => app.server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${app.server.address().port}`;
const post = (path, body, method = "POST") => fetch(`${base}${path}`, { method, headers: { "content-type": "application/json", origin: base }, body: JSON.stringify(body) });

const state = await (await fetch(`${base}/api/state`)).json();
t.deepEqual(state.deck, { hotkey: true, url: true }, "the dock is told which button kinds this PC supports");
const put = await post("/api/tiles", { tiles: [hotkey, url, { kind: "multi", id: "d-multi2", steps: [{ type: "hotkey", keys: "alt+tab" }, { type: "delay", ms: 50 }, { type: "hotkey", keys: "f14" }] }] }, "PUT");
t.equal(put.status, 200, "deck buttons are saved");
t.equal((await put.json()).tiles.length, 3, "all three buttons are stored");
t.equal((await post("/api/deck/run", { id: "d-abc123" })).status, 200, "a shortcut button runs");
t.equal((await post("/api/deck/run", { id: "d-web001" })).status, 200, "a website button runs");
t.equal((await post("/api/deck/run", { id: "d-multi2" })).status, 200, "a multi-action button runs");
t.deepEqual(apiCalls, ["hotkey ctrl+shift+m", "open-url https://twitch.tv/", "hotkey alt+tab", "hotkey f14"], "the helper receives exactly the stored actions");
t.equal((await post("/api/deck/run", { id: "d-nothere" })).status, 404, "an unknown button is refused");
t.equal((await post("/api/deck/run", { keys: "ctrl+alt+delete" })).status, 404, "the phone cannot run an unsaved shortcut");
const busy = [post("/api/deck/run", { id: "d-multi2" }), post("/api/deck/run", { id: "d-multi2" })];
const statuses = (await Promise.all(busy)).map((r) => r.status).sort();
t.deepEqual(statuses, [200, 409], "a second press waits for the first multi-action to finish");

app.server.closeAllConnections?.();
await app.hub.close();
await new Promise((r) => app.server.close(r));
await rm(dir, { recursive: true, force: true });

t.done("deck verification passed");
