"""Better voices: speaks Nova's answers on the PC with Piper (local, free) or ElevenLabs (premium).

Answers are spoken sentence by sentence while they stream in. The next sentence is synthesised
while the current one plays, so there are no gaps. The orb/rings react to the real loudness.
("windows" = the built-in browser voices, handled by the app window itself.)
"""
import io
import os
import queue
import re
import tempfile
import threading
import time
import wave

import httpx
import numpy as np

import config

FAKE = os.environ.get("NOVA_FAKE") == "1"
VOICE_DIR = config.CONFIG_DIR / "voices"
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Hand-picked Piper voices (name, label). Files come from the official piper-voices collection.
PIPER_VOICES = [
    ("de_DE-thorsten-high", "Thorsten · Deutsch, männlich · beste Qualität"),
    ("de_DE-thorsten_emotional-medium", "Thorsten emotional · Deutsch, männlich"),
    ("de_DE-kerstin-low", "Kerstin · Deutsch, weiblich"),
    ("de_DE-ramona-low", "Ramona · Deutsch, weiblich"),
    ("de_DE-eva_k-x_low", "Eva · Deutsch, weiblich · sehr klein"),
    ("de_DE-karlsson-low", "Karlsson · Deutsch, männlich"),
    ("en_GB-alan-medium", "Alan · British English, male (butler vibe)"),
    ("en_GB-northern_english_male-medium", "Northern English · male"),
    ("en_GB-cori-high", "Cori · British English, female · best quality"),
    ("en_GB-jenny_dioco-medium", "Jenny · British English, female"),
    ("en_US-ryan-high", "Ryan · American English, male · best quality"),
    ("en_US-lessac-high", "Lessac · American English, female · best quality"),
    ("en_US-amy-medium", "Amy · American English, female"),
]
ELEVEN_MODELS = [("eleven_flash_v2_5", "Flash · fast and cheap"), ("eleven_multilingual_v2", "Multilingual v2 · best quality")]
SENTENCE_END = re.compile(r"[.!?:;…\n](?=\s|$)")


def _piper_url(name, ext):
    locale, voice, quality = name.split("-", 2)
    return f"{HF}/{locale.split('_')[0]}/{locale}/{voice}/{quality}/{name}{ext}"


def piper_installed(name):
    return (VOICE_DIR / f"{name}.onnx").exists() and (VOICE_DIR / f"{name}.onnx.json").exists()


def clean_for_speech(text):
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)                 # code isn't fun to listen to
    text = re.sub(r"[*_#>|]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Downloader:
    """Downloads a Piper voice in the background and reports progress."""

    def __init__(self, emit):
        self.emit = emit
        self.active = None

    def start(self, name):
        if self.active or name not in dict(PIPER_VOICES):
            return False
        self.active = name
        threading.Thread(target=self._run, args=(name,), daemon=True).start()
        return True

    def _run(self, name):
        try:
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            for ext in (".onnx.json", ".onnx"):
                dest = VOICE_DIR / f"{name}{ext}"
                tmp = dest.with_suffix(dest.suffix + ".part")
                with httpx.stream("GET", _piper_url(name, ext), follow_redirects=True,
                                  timeout=httpx.Timeout(20, read=120)) as r:
                    r.raise_for_status()
                    total, done, last = int(r.headers.get("content-length") or 0), 0, 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_bytes(1 << 16):
                            f.write(chunk)
                            done += len(chunk)
                            pct = done * 100 / total if total else None
                            if ext == ".onnx" and pct and pct - last >= 2:
                                last = pct
                                self.emit({"type": "voice_pull", "voice": name, "pct": round(pct, 1)})
                tmp.replace(dest)
            self.emit({"type": "voice_pull", "voice": name, "pct": 100, "done": True})
        except Exception as e:
            self.emit({"type": "voice_pull", "voice": name, "error": f"Download failed: {e}", "done": True})
        finally:
            self.active = None


class Speaker:
    def __init__(self, hub):
        self.hub = hub
        self.text_q = queue.Queue()
        self.audio_q = queue.Queue(maxsize=3)
        self.gen = 0                       # bumps on stop(): stale audio is thrown away
        self.spoken = {}                   # message id -> characters already queued
        self._piper = {}
        self._piper_lock = threading.Lock()
        self.playing = False
        self.downloader = Downloader(hub.emit)
        threading.Thread(target=self._synth_loop, daemon=True, name="tts-synth").start()
        threading.Thread(target=self._play_loop, daemon=True, name="tts-play").start()
        hub.listeners.append(self.on_event)

    # ---------- which engine ----------
    @property
    def cfg(self):
        return self.hub.cfg

    def active(self):
        return self.cfg.get("speak_replies") and self.cfg.get("voice_engine", "windows") in ("piper", "eleven")

    def preload(self):
        """Load the Piper voice in the background, so the first answer isn't delayed by ~2 s."""
        c = self.cfg
        if FAKE or not self.active() or c.get("voice_engine") != "piper" or not piper_installed(c.get("piper_voice") or ""):
            return
        threading.Thread(target=self._load_piper, args=(c["piper_voice"],), daemon=True).start()

    def _load_piper(self, name):
        with self._piper_lock:
            if name not in self._piper:
                from piper import PiperVoice
                self._piper = {name: PiperVoice.load(str(VOICE_DIR / f"{name}.onnx"))}   # keep one voice in memory
            return self._piper[name]

    # ---------- events from the agent ----------
    def on_event(self, ev):
        t = ev.get("type")
        if t == "user" or (t == "listen" and ev.get("on")):
            self.stop()                    # new question / you start talking: stop talking
            return
        if not self.active() or t not in ("stream", "assistant") or ev.get("greeting"):
            return                         # (the start greeting is spoken separately)
        sid = ev.get("id", f"q{time.time()}")
        text = ev.get("text", "")
        done = self.spoken.get(sid, 0)
        upto = len(text) if t == "assistant" else 0
        if t == "stream":
            for m in SENTENCE_END.finditer(text, done):
                upto = m.end()
        if upto > done:
            self.spoken[sid] = upto
            if len(self.spoken) > 50:
                self.spoken.pop(next(iter(self.spoken)))
            part = clean_for_speech(text[done:upto])
            if part:
                self.text_q.put((self.gen, part, None, None))

    def say(self, text, override=None, fallback=None):
        """Speak something right now (e.g. 'Test voice'). fallback(): called instead of showing an
        error if this voice can't speak it (no internet, voice not downloaded...)."""
        self.stop()
        self.text_q.put((self.gen, clean_for_speech(text), override, fallback))

    def stop(self):
        self.gen += 1
        for q in (self.text_q, self.audio_q):
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass
        if not FAKE and os.name == "nt":
            import winsound
            try:
                winsound.PlaySound(None, 0)          # stops the sound that is playing right now
            except Exception:
                pass

    # ---------- synthesis ----------
    def _synth_loop(self):
        while True:
            gen, text, override, fallback = self.text_q.get()
            if gen != self.gen or not text:
                continue
            try:
                pcm, sr = self.synth(text, override)
            except Exception as e:
                if fallback:
                    threading.Thread(target=fallback, daemon=True).start()
                else:
                    self.hub.emit({"type": "error", "text": f"Voice: {e}"})
                continue
            if gen == self.gen and pcm is not None and len(pcm):
                self.audio_q.put((gen, pcm, sr))

    def synth(self, text, override=None):
        c = dict(self.cfg)
        c.update(override or {})
        engine = c.get("voice_engine", "windows")
        if engine == "piper":
            return self._synth_piper(text, c)
        if engine == "eleven":
            return self._synth_eleven(text, c)
        raise RuntimeError("no engine")

    def _synth_piper(self, text, c):
        name = c.get("piper_voice") or ""
        if not piper_installed(name):
            raise RuntimeError("the Piper voice isn't downloaded yet (Settings → Voice).")
        if FAKE:
            return np.zeros(8000, np.int16), 16000
        voice = self._load_piper(name)
        rate = float(c.get("voice_rate", 1.0) or 1.0)
        syn = None
        try:
            from piper import SynthesisConfig
            syn = SynthesisConfig(length_scale=1 / max(0.5, min(rate, 2.0)))
        except Exception:
            pass
        chunks, sr = [], 22050
        for ch in (voice.synthesize(text, syn_config=syn) if syn else voice.synthesize(text)):
            chunks.append(ch.audio_int16_bytes)
            sr = ch.sample_rate
        return np.frombuffer(b"".join(chunks), np.int16), sr

    def _synth_eleven(self, text, c):
        key = c.get("eleven_key") or ""
        voice = c.get("eleven_voice") or ""
        if not key or not voice:
            raise RuntimeError("add your ElevenLabs key and pick a voice in Settings → Voice.")
        if FAKE:
            return np.zeros(8000, np.int16), 16000
        body = {"text": text, "model_id": c.get("eleven_model") or "eleven_flash_v2_5"}
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        h = {"xi-api-key": key, "Content-Type": "application/json"}
        r = httpx.post(url, params={"output_format": "pcm_22050"}, headers=h, json=body, timeout=30)
        if r.status_code == 200:
            return np.frombuffer(r.content, np.int16), 22050
        if r.status_code in (400, 403, 422):           # raw audio not allowed on this plan: take MP3
            r2 = httpx.post(url, params={"output_format": "mp3_44100_128"}, headers=h, json=body, timeout=30)
            if r2.status_code == 200:
                return _decode_mp3(r2.content)
            r = r2
        try:
            msg = r.json().get("detail", {})
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"ElevenLabs said no ({r.status_code}): {msg}")

    # ---------- playback ----------
    def _play_loop(self):
        n = 0
        while True:
            gen, pcm, sr = self.audio_q.get()
            if gen != self.gen:
                continue
            vol = float(self.cfg.get("voice_volume", 1.0) or 1.0)
            if vol != 1.0:
                pcm = np.clip(pcm.astype(np.float32) * vol, -32768, 32767).astype(np.int16)
            if not self.playing:
                self.playing = True
                self.hub.emit({"type": "voice", "ev": "start"})
            # a short silent tail: Windows starts each sound a few ms late, and starting the next one
            # cuts off the previous one; the tail is what gets cut, never the last syllable
            pcm = np.concatenate([pcm, np.zeros(int(sr * 0.14), np.int16)])
            n = (n + 1) % 4
            path = os.path.join(tempfile.gettempdir(), f"nova_voice_{n}.wav")
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(pcm.tobytes())
            if not FAKE and os.name == "nt":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self._drive_visuals(pcm, sr, gen)
            if self.audio_q.empty() and self.text_q.empty():
                time.sleep(0.15)
                if self.audio_q.empty() and self.text_q.empty():
                    self.playing = False
                    self.hub.emit({"type": "voice", "ev": "end"})

    def _drive_visuals(self, pcm, sr, gen):
        """Follow the loudness while it plays: a 'word' pulse on every syllable."""
        hop = int(sr * 0.04)
        x = pcm.astype(np.float32) / 32768
        frames = len(x) // hop
        rms = np.sqrt(np.mean(x[: frames * hop].reshape(frames, hop) ** 2, axis=1)) if frames else np.zeros(1)
        peak = max(float(rms.max()), 1e-4)
        loud, start = False, time.time()
        for i, v in enumerate(rms / peak):
            if gen != self.gen:
                return
            if v > 0.45 and not loud:
                self.hub.emit({"type": "voice", "ev": "word"})
                loud = True
            elif v < 0.25:
                loud = False
            delay = start + (i + 1) * 0.04 - time.time()
            if delay > 0:
                time.sleep(delay)
        rest = start + len(pcm) / sr - time.time()       # the part after the last full 40 ms step
        while rest > 0 and gen == self.gen:
            time.sleep(min(rest, 0.05))
            rest = start + len(pcm) / sr - time.time()


def say_windows(text, language="en"):
    """Speaks with a built-in Windows voice straight from Python (SAPI), picking a voice in the
    right language. Used for the start greeting when the app window can't speak yet."""
    if FAKE or os.name != "nt":
        return
    want = "407" if language == "de" else "409"            # language ids: German / English (US)
    try:
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        try:
            v = comtypes.client.CreateObject("SAPI.SpVoice")
            voices = v.GetVoices()
            for i in range(voices.Count):
                tok = voices.Item(i)
                langs = (tok.GetAttribute("Language") or "").lower().split(";")
                if want in langs or (language == "en" and "809" in langs):
                    v.Voice = tok
                    break
            v.Speak(text)
        finally:
            comtypes.CoUninitialize()
    except Exception:
        # no comtypes: the same voices through PowerShell (a bit slower to start)
        import subprocess
        culture = "de-DE" if language == "de" else "en-US"
        safe = text.replace("'", "''")
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"try {{ $s.SelectVoiceByHints('NotSet', 'NotSet', 0, [Globalization.CultureInfo]'{culture}') }} catch {{}}; "
              f"$s.Speak('{safe}')")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _decode_mp3(data):
    import av                                            # comes with faster-whisper
    with av.open(io.BytesIO(data)) as f:
        stream = f.streams.audio[0]
        res = av.AudioResampler(format="s16", layout="mono", rate=24000)
        out = []
        for frame in f.decode(stream):
            for r in res.resample(frame):
                out.append(r.to_ndarray().reshape(-1))
    return np.concatenate(out).astype(np.int16), 24000


def eleven_voices(key):
    """List the voices on an ElevenLabs account: [{id, name, info}]."""
    r = httpx.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError("ElevenLabs key not accepted." if r.status_code in (401, 403) else f"ElevenLabs error {r.status_code}")
    out = []
    for v in r.json().get("voices", []):
        labels = v.get("labels") or {}
        info = " · ".join(x for x in (labels.get("gender"), labels.get("accent"), labels.get("description")) if x)
        out.append({"id": v.get("voice_id"), "name": v.get("name"), "info": info})
    return out
