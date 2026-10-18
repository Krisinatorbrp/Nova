"""Local web server: serves the app UI to the PC window and to your iPhone."""
import asyncio
import queue
import threading
import re
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import socket
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from agent import Agent, new_sid
import lang
import quick
from local_agent import LocalAgent
import ollama
from remote import RemoteScreen

STATIC = Path(__file__).parent / "static"
HISTORY_TYPES = ("user", "assistant", "action", "error", "confirm", "confirm_done")


class FreshStatic(StaticFiles):
    """The app files are always checked for a newer version (a quick 304 when nothing changed),
    so an update of Nova never leaves an old, cached interface in the window or on the phone."""

    def file_response(self, *args, **kwargs):
        r = super().file_response(*args, **kwargs)
        r.headers["Cache-Control"] = "no-cache"
        return r


class Hub:
    def __init__(self):
        self.cfg = config.load()
        self.local_token = secrets.token_urlsafe(24)   # given only to the PC window
        # signed-in phones: only hashes, saved in the settings so phones stay signed in after a restart
        self.phone_tokens: set[str] = set(self.cfg.get("phone_tokens") or [])
        self.clients: dict[WebSocket, asyncio.Queue] = {}   # each client has its own send queue
        self.loop: asyncio.AbstractEventLoop | None = None
        self.history: deque = deque(maxlen=150)        # replayed to newly connected clients
        self.last_frame = None
        self.login_fails: dict[str, list[float]] = {}
        self.agent = None
        self.remote_viewers = 0
        self.listeners = []                            # in-process subscribers (desktop widget)
        self._events = queue.Queue()
        threading.Thread(target=self._dispatch, daemon=True, name="nova-events").start()
        self.greeted = False
        self._greet_lock = threading.Lock()
        self.puller = ollama.Puller(self.cfg, self.emit)
        self.ensure_agent()
        import speech
        from listen import Listener
        self.speaker = speech.Speaker(self)                       # Piper / ElevenLabs voices
        self.listener = Listener(self, self.submit_spoken)        # microphone -> Whisper -> text

    # ---------- start greeting ----------
    def greet(self, by_page=False):
        """'Guten Tag, Sir. Was kann ich für Sie tun?' once per start, in the app's language.
        Piper / ElevenLabs speak it here. With the Windows voice the PC window speaks it (by_page:
        returns the text for it); if the window can't, a built-in Windows voice speaks it from here."""
        with self._greet_lock:
            if self.greeted or not self.cfg.get("greet_on_start", True) or not self.configured():
                return None
            self.greeted = True
        text = lang.t(self.cfg, "greeting")
        self.emit({"type": "assistant", "text": text, "greeting": True, "id": new_sid()})
        engine = self.cfg.get("voice_engine", "windows")
        if engine in ("piper", "eleven"):
            self.speaker.say(text, fallback=lambda: self.say_windows(text))
            return None
        if by_page:
            return text
        threading.Thread(target=self.say_windows, args=(text,), daemon=True).start()
        return None

    def say_windows(self, text):
        import speech
        self.emit({"type": "voice", "ev": "start"})
        try:
            speech.say_windows(text, lang.current(self.cfg))
        finally:
            self.emit({"type": "voice", "ev": "end"})

    def warm(self):
        """You're about to ask something: make sure the local model is loaded (it unloads after
        30 idle minutes). Cheap when it's already loaded."""
        if self.cfg.get("brain", "local") == "local":
            ollama.warm_up(self.cfg, min_gap=120)

    def submit_spoken(self, text):
        """Text from the microphone: send it like a typed question (or just fill the box)."""
        if not self.cfg.get("auto_send", True):
            self.emit({"type": "dictation", "text": text})
            return
        if self.loop:
            fut = asyncio.run_coroutine_threadsafe(run_task(text, "local"), self.loop)

            def done(f):
                try:
                    err = f.result()
                except Exception as e:
                    err = str(e)
                if err:                                 # e.g. still busy with the last request: say so
                    self.emit({"type": "error", "text": err})
            fut.add_done_callback(done)

    # called from any thread (agent, widget, microphone, server)
    def emit(self, event: dict):
        event["ts"] = time.time()
        # in-process listeners (widget, voice, hotkeys) run on their own thread, in order,
        # so a slow or stuck listener can never freeze the caller (window, server, widget...)
        if self.listeners:
            self._events.put(event)
        if self.loop:
            try:
                self.loop.call_soon_threadsafe(self._publish, event, True)
                return
            except RuntimeError:                       # loop already closed (quitting)
                pass
        self._remember(event)

    def _remember(self, event):
        if event["type"] == "frame":
            self.last_frame = event
        elif event["type"] in HISTORY_TYPES:
            self.history.append(event)

    def _publish(self, event, remember=False):
        """Runs on the server loop: history and every client's queue are updated in one step,
        so a client that connects never misses or doubles an event, and the order is kept."""
        if remember:
            self._remember(event)
        data = json.dumps(event)
        for ws, q in list(self.clients.items()):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:                  # a client that stopped reading: drop it
                self.clients.pop(ws, None)
                asyncio.ensure_future(_close_quietly(ws))

    def _dispatch(self):
        while True:
            event = self._events.get()
            for fn in list(self.listeners):
                try:
                    fn(event)
                except Exception as e:
                    print("listener error:", e)

    async def _broadcast(self, event: dict):
        self._publish(event)

    def role(self, token: str | None) -> str | None:
        if token and secrets.compare_digest(token, self.local_token):
            return "local"
        if token and config.token_hash(token) in self.phone_tokens:
            return "phone"
        return None

    def add_phone(self) -> str:
        tok = secrets.token_urlsafe(32)
        keep = [h for h in (self.cfg.get("phone_tokens") or []) if h in self.phone_tokens][-19:]
        keep.append(config.token_hash(tok))
        self.phone_tokens = set(keep)
        self.cfg["phone_tokens"] = keep
        config.save(self.cfg)
        return tok

    def sign_out_phones(self):
        self.phone_tokens = set()
        self.cfg["phone_tokens"] = []

    def configured(self) -> bool:
        if self.cfg.get("brain") == "claude":
            return bool(self.cfg.get("api_key"))
        return bool(self.cfg.get("local_model"))

    def ensure_agent(self):
        """(Re)create the brain when the setting changes. Never swaps mid-task."""
        want = LocalAgent if self.cfg.get("brain", "local") == "local" else Agent
        if self.agent is not None and self.agent.busy:
            return
        if want is Agent and not self.cfg.get("api_key"):
            self.agent = None
            return
        if type(self.agent) is not want:
            self.agent = want(self.cfg, self.emit)
        else:
            self.agent.cfg = self.cfg


async def _close_quietly(ws):
    try:
        await ws.close()
    except Exception:
        pass


hub = Hub()
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", FreshStatic(directory=STATIC), name="static")


@app.on_event("startup")
async def _startup():
    hub.loop = asyncio.get_running_loop()


def _token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else None


def _require(request: Request, local_only=False) -> str:
    role = hub.role(_token(request))
    if role is None or (local_only and role != "local"):
        raise HTTPException(401, "Not allowed")
    return role


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/manifest.json")
async def manifest():
    return FileResponse(STATIC / "manifest.json", media_type="application/manifest+json")


@app.get("/api/state")
async def state(request: Request):
    role = hub.role(_token(request))
    c = hub.cfg
    base = {"name": c["assistant_name"], "configured": hub.configured(), "brain": c.get("brain", "local"),
            "phone_ready": bool(c.get("passcode_hash")), "role": role}
    if role is None:
        return base
    base.update({"busy": bool(hub.agent and hub.agent.busy),
                 "speak_replies": c["speak_replies"],
                 "orb_color": c.get("orb_color", "#2896FF"),
                 "show_transcript": c.get("show_transcript", True),
                 "language": lang.current(c),
                 "remote": bool(c.get("allow_remote"))})
    if role == "local":
        base.update({
            "settings": {k: c[k] for k in sorted(config.EDITABLE)},
            "has_key": bool(c.get("api_key")),
            "has_eleven_key": bool(c.get("eleven_key")),
            "phone_urls": phone_urls(c["port"]) if c.get("phone_access") else [],
            "config_path": str(config.CONFIG_PATH),
        })
    return base


@app.post("/api/setup")
async def setup(request: Request):
    _require(request, local_only=True)
    body = await request.json()
    if body.get("brain") == "claude" and not (body.get("api_key") or hub.cfg.get("api_key")):
        raise HTTPException(400, "Paste a Claude API key, or choose “This PC” as the brain.")
    if body.get("api_key"):
        key = body["api_key"].strip()
        if not key.startswith("sk-"):
            raise HTTPException(400, "That doesn't look like an Anthropic API key (sk-ant-...).")
        hub.cfg["api_key"] = key
    if body.get("passcode"):
        if len(body["passcode"]) < 6:
            raise HTTPException(400, "Use at least 6 characters for the phone passcode.")
        config.set_passcode(hub.cfg, body["passcode"])
        hub.sign_out_phones()             # log out old phones
    if body.get("assistant_name"):
        hub.cfg["assistant_name"] = body["assistant_name"].strip()[:24]
    if body.get("brain") in ("local", "claude"):
        hub.cfg["brain"] = body["brain"]
    if body.get("local_model"):
        hub.cfg["local_model"] = body["local_model"]
    config.save(hub.cfg)
    hub.ensure_agent()
    return {"ok": True}


@app.post("/api/settings")
async def settings(request: Request):
    _require(request, local_only=True)
    body = await request.json()
    if "orb_color" in body and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(body["orb_color"])):
        raise HTTPException(400, "Colour must look like #2896FF.")
    if body.get("eleven_key"):
        hub.cfg["eleven_key"] = str(body["eleven_key"]).strip()
    for k in ("hotkey", "ask_hotkey", "talk_hotkey"):
        if k in body and not re.fullmatch(r"[\w +]{0,60}", str(body[k])):
            raise HTTPException(400, "Invalid hotkey.")
    for k, v in body.items():
        if k in config.EDITABLE:
            hub.cfg[k] = v
    config.save(hub.cfg)
    hub.ensure_agent()
    # tell every open screen (and the desktop widget) right away
    hub.emit({"type": "prefs", "orb_color": hub.cfg.get("orb_color"), "show_transcript": hub.cfg.get("show_transcript"),
              "name": hub.cfg.get("assistant_name"), "language": lang.current(hub.cfg)})
    if hub.cfg.get("brain") == "local":
        ollama.warm_up(hub.cfg)               # load the (maybe new) model now, not on the first question
    return {"ok": True}


@app.get("/api/local/status")
async def local_status(request: Request):
    _require(request, local_only=True)
    st = await asyncio.to_thread(ollama.status, hub.cfg)
    st["pulling"] = hub.puller.active
    st["selected"] = hub.cfg.get("local_model")
    return st


@app.post("/api/local/pull")
async def local_pull(request: Request):
    _require(request, local_only=True)
    tag = (await request.json()).get("model", "")
    if tag not in {m["tag"] for m in ollama.MODELS} and not tag.replace(":", "").replace(".", "").replace("-", "").isalnum():
        raise HTTPException(400, "Unknown model name.")
    if not hub.puller.start(tag):
        raise HTTPException(409, "A download is already running.")
    return {"ok": True}


@app.post("/api/local/start")
async def local_start(request: Request):
    _require(request, local_only=True)
    ok = await asyncio.to_thread(ollama.try_start, hub.cfg)
    await asyncio.sleep(3 if ok else 0)
    return {"ok": ok}


@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    fails = [t for t in hub.login_fails.get(ip, []) if time.time() - t < 600]
    if len(fails) >= 5:
        raise HTTPException(429, "Too many attempts. Wait 10 minutes.")
    body = await request.json()
    if not hub.cfg.get("phone_access") or not config.check_passcode(hub.cfg, body.get("passcode", "")):
        fails.append(time.time())
        hub.login_fails[ip] = fails
        raise HTTPException(401, "Wrong passcode.")
    hub.login_fails.pop(ip, None)
    return {"token": await asyncio.to_thread(hub.add_phone)}


async def run_task(text: str, role: str):
    """A question from the chat box, the phone or the microphone. Returns an error text or None."""
    text = text.strip()[:4000]
    if not text:
        return None
    if hub.agent is not None and hub.agent.busy:
        return lang.t(hub.cfg, "busy")
    hub.emit({"type": "user", "text": text, "from": role})
    # instant commands ("öffne Spotify", "lauter", ...) skip the AI completely
    reply = await asyncio.to_thread(quick.handle, text, lang.current(hub.cfg))
    if reply:
        hub.emit({"type": "action", "text": reply})
        hub.emit({"type": "assistant", "text": reply, "quick": True})
        hub.emit({"type": "state", "state": "idle"})
        return None
    hub.ensure_agent()                    # a brain switch made while it was busy takes effect now
    if hub.agent is None or not hub.configured():
        hub.emit({"type": "error", "text": lang.t(hub.cfg, "setup_first")})
        return None
    if not hub.agent.submit(text):                 # another request started a moment earlier
        hub.emit({"type": "error", "text": lang.t(hub.cfg, "busy")})
    return None


# ---------- voices & microphone ----------
@app.get("/api/voices")
async def voices(request: Request):
    _require(request, local_only=True)
    import speech
    return {"piper": [{"name": n, "label": l, "installed": speech.piper_installed(n)} for n, l in speech.PIPER_VOICES],
            "pulling": hub.speaker.downloader.active,
            "eleven_models": [{"id": i, "label": l} for i, l in speech.ELEVEN_MODELS],
            "has_eleven_key": bool(hub.cfg.get("eleven_key"))}


@app.post("/api/voices/download")
async def voice_download(request: Request):
    _require(request, local_only=True)
    if not hub.speaker.downloader.start((await request.json()).get("name", "")):
        raise HTTPException(409, "A download is already running.")
    return {"ok": True}


@app.post("/api/voices/eleven")
async def voice_eleven(request: Request):
    _require(request, local_only=True)
    import speech
    key = ((await request.json()).get("key") or hub.cfg.get("eleven_key") or "").strip()
    if not key:
        raise HTTPException(400, "Paste your ElevenLabs API key first.")
    try:
        return {"voices": await asyncio.to_thread(speech.eleven_voices, key)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/tts/test")
async def tts_test(request: Request):
    _require(request, local_only=True)
    body = await request.json()
    override = {k: body[k] for k in ("voice_engine", "piper_voice", "eleven_voice", "eleven_model", "voice_rate", "voice_volume")
                if k in body}
    if body.get("eleven_key"):
        override["eleven_key"] = body["eleven_key"]
    hub.speaker.say(str(body.get("text", ""))[:300], override)
    return {"ok": True}


@app.post("/api/greet")
async def greet(request: Request):
    """The PC window asks once it is loaded. say = text it should speak with the chosen Windows voice."""
    _require(request, local_only=True)
    return {"say": hub.greet(by_page=True)}


@app.post("/api/greet/fallback")
async def greet_fallback(request: Request):
    """The window couldn't speak (Windows didn't let it): a built-in voice speaks from here."""
    _require(request, local_only=True)
    text = str((await request.json()).get("text", ""))[:200] or lang.t(hub.cfg, "greeting")
    threading.Thread(target=hub.say_windows, args=(text,), daemon=True).start()
    return {"ok": True}


@app.post("/api/listen")
async def listen(request: Request):
    _require(request, local_only=True)
    hub.listener.toggle()
    return {"recording": hub.listener.recording}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    role = hub.role(websocket.query_params.get("token"))
    if role is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=600)
    # snapshot + subscribe in one step (no await in between): nothing is lost or sent twice
    q.put_nowait(json.dumps({"type": "history", "events": list(hub.history),
                             "busy": bool(hub.agent and hub.agent.busy)}))
    if hub.last_frame:
        q.put_nowait(json.dumps(hub.last_frame))
    q.put_nowait(json.dumps({"type": "remote", "viewers": hub.remote_viewers}))
    hub.clients[websocket] = q

    async def writer():
        while True:
            await websocket.send_text(await q.get())

    wtask = asyncio.create_task(writer())
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            t = msg.get("type")
            if t == "task":
                err = await run_task(msg.get("text") or "", role)
                if err:
                    q.put_nowait(json.dumps({"type": "error", "text": err, "ts": time.time()}))
            elif t == "voice" and role == "local":
                hub.emit({"type": "voice", "ev": str(msg.get("ev", ""))[:8]})
            elif t == "stop" and hub.agent:
                hub.agent.stop()
            elif t == "confirm" and hub.agent:
                hub.agent.answer_confirm(msg.get("id", ""), bool(msg.get("ok")))
            elif t == "reset" and hub.agent and not hub.agent.busy:
                hub.agent.reset()
                hub.history.clear()
                hub.last_frame = None
                await hub._broadcast({"type": "reset"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.clients.pop(websocket, None)
        wtask.cancel()


@app.websocket("/remote")
async def remote(websocket: WebSocket):
    """Screen tab: live JPEG frames out, taps/typing in. Phone only."""
    role = hub.role(websocket.query_params.get("token"))
    if role != "phone" or not hub.cfg.get("allow_remote"):
        await websocket.close(code=4401 if role is None else 4403)
        return
    await websocket.accept()
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=1)      # one thread = one screen grabber
    try:
        start_screen = int(websocket.query_params.get("screen", "1"))
    except ValueError:
        start_screen = 1
    rs = await loop.run_in_executor(pool, RemoteScreen, start_screen)
    opts = {"w": 1280, "q": 60}
    ready = asyncio.Event()
    ready.set()
    hub.remote_viewers += 1
    await hub._broadcast({"type": "remote", "viewers": hub.remote_viewers})

    def locked():
        return bool(hub.agent and hub.agent.busy)

    async def send_meta():
        w, h = rs.size()
        await websocket.send_text(json.dumps({"type": "meta", "w": w, "h": h, "locked": locked(),
                                              "screen": rs.index, "screens": rs.info()}))
    await send_meta()

    async def sender():
        was_locked = locked()
        last_sent = 0.0
        while True:
            await ready.wait()                       # the phone asks for the next frame when it shows one
            t0 = time.time()
            force = t0 - last_sent > 2.0 or opts.get("force", False)   # a keep-alive frame now and then
            opts["force"] = False
            data = await loop.run_in_executor(pool, rs.frame, opts["w"], opts["q"], force)
            if data is not None:                     # unchanged screen: nothing to send
                ready.clear()
                last_sent = time.time()
                await websocket.send_bytes(data)
            if locked() != was_locked:
                was_locked = locked()
                await websocket.send_text(json.dumps({"type": "locked", "value": was_locked}))
            fps = max(1, min(int(hub.cfg.get("remote_fps", 8)), 20))
            await asyncio.sleep(max(0.0, 1 / fps - (time.time() - t0)))

    send_task = asyncio.create_task(sender())
    try:
        while True:
            ev = json.loads(await websocket.receive_text())
            t = ev.get("t")
            if t == "next":
                ready.set()
            elif t == "screen":
                await loop.run_in_executor(pool, rs.select, ev.get("index", 1))
                await send_meta()
                opts["force"] = True
                ready.set()
            elif t == "opts":
                opts["w"] = max(480, min(int(ev.get("w", 1280)), 2560))
                opts["q"] = max(25, min(int(ev.get("q", 60)), 90))
                opts["force"] = True
            elif locked():
                await websocket.send_text(json.dumps({"type": "locked", "value": True}))
            else:
                await loop.run_in_executor(pool, rs.handle, ev)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        send_task.cancel()
        await loop.run_in_executor(pool, rs.release)
        pool.shutdown(wait=False)
        hub.remote_viewers = max(0, hub.remote_viewers - 1)
        await hub._broadcast({"type": "remote", "viewers": hub.remote_viewers})


def phone_urls(port: int) -> list[dict]:
    """Addresses your phone can use: Wi-Fi (same network) and Tailscale (anywhere)."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    out = []
    for ip in sorted(ips):
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        a, b = (int(x) for x in ip.split(".")[:2])
        kind = "Tailscale (works anywhere)" if a == 100 and 64 <= b <= 127 else "Wi-Fi (same network)"
        out.append({"kind": kind, "url": f"http://{ip}:{port}"})
    return out
