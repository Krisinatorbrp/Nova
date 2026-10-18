"""Voice input on the PC: records from the microphone and turns speech into text with Whisper,
locally on your PC (nothing is uploaded).

Press the mic button / hotkey once to start. Recording stops by itself when you pause
for a moment (or when you press again), then the text is sent to the assistant.
"""
import os
import threading
import time

import re

import numpy as np

import lang as lang_mod

FAKE = os.environ.get("NOVA_FAKE") == "1"
RATE = 16000
STT_MODELS = {"tiny": "tiny", "base": "base", "small": "small"}
SILENCE_END = 1.0          # seconds of quiet after speaking that end the recording
# saying just this stops what Nova is doing (and its voice) instead of asking something new
STOP_WORDS = re.compile(r"^(?:(?:nova|jarvis|hey|ok|okay)[,!]?\s+)?(?:stopp?|halt|abbrechen|aufhören|hör auf|cancel|stop it|be quiet|sei still|ruhe)[.!]*$", re.I)


class Listener:
    def __init__(self, hub, submit):
        self.hub = hub
        self.submit = submit               # submit(text) -> sends it to the assistant
        self.recording = False
        self._stop = threading.Event()
        self._model = None
        self._model_name = None
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()

    # ---------- public ----------
    def toggle(self):
        if self.recording:
            self._stop.set()
        else:
            self.start()

    def start(self):
        with self._lock:
            if self.recording:
                return
            self.recording = True
        self._stop.clear()
        threading.Thread(target=self._run, daemon=True, name="listen").start()

    def preload(self):
        threading.Thread(target=self._load_model, args=(True,), daemon=True).start()

    # ---------- recording ----------
    def _emit(self, **kw):
        self.hub.emit({"type": "listen", **kw})

    def _state(self, s):
        """Show listening / thinking on the orb, but never hide that the assistant is busy working."""
        agent = getattr(self.hub, "agent", None)
        if not (agent and agent.busy):
            self.hub.emit({"type": "state", "state": s})

    def _run(self):
        chunks = []
        try:
            self._emit(on=True)
            self._state("listening")
            if hasattr(self.hub, "warm"):
                self.hub.warm()                         # the AI model loads while you talk
            if self._model is None:
                self.preload()                          # load Whisper while you speak, not after
            audio = self._record(chunks)
            self._emit(on=False, working=True)
            self._state("thinking")
            if audio is None or len(audio) < RATE * 0.3:
                self._emit(on=False, text="", heard=False)
                self._state("idle")
                return
            text = self._transcribe(audio)
            if not self.hub.cfg.get("stt_used"):
                import config
                self.hub.cfg["stt_used"] = True           # from now on: preload at start-up
                config.save(self.hub.cfg)
            self._emit(on=False, text=text, heard=bool(text))
            if text and STOP_WORDS.match(text.strip()):
                self._state("idle")
                agent = getattr(self.hub, "agent", None)
                if agent and agent.busy:
                    agent.stop()
                self.hub.speaker.stop()
                return
            self._state("idle")
            if text:
                self.submit(text)
        except Exception as e:
            self._emit(on=False, text="")
            self._state("idle")
            self.hub.emit({"type": "error", "text": f"Microphone: {e}"})
        finally:
            self.recording = False

    def _record(self, chunks):
        """Records until you're quiet for ~1 s after speaking (or 30 s, or you press again)."""
        if FAKE:
            time.sleep(0.5)
            return np.zeros(RATE, np.float32)
        import sounddevice as sd
        level = {"v": 0.0}

        def cb(indata, frames, t, status):
            chunks.append(indata[:, 0].copy())
            level["v"] = float(np.sqrt(np.mean(indata[:, 0] ** 2)))

        started, spoke, quiet_since, last_emit = time.time(), False, None, 0
        noise = None
        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=1600, callback=cb):
            while not self._stop.is_set():
                time.sleep(0.05)
                v = level["v"]
                if noise is None and time.time() - started > 0.3:
                    noise = max(v, 0.004)                 # room noise during the first moment
                thr = max((noise or 0.004) * 3, 0.012)
                now = time.time()
                if now - last_emit > 0.08:                 # let the orb react to your voice
                    last_emit = now
                    self._emit(level=round(min(1.0, v / (thr * 4)), 2))
                if v > thr:
                    spoke, quiet_since = True, None
                elif spoke:
                    quiet_since = quiet_since or now
                    if now - quiet_since > SILENCE_END:
                        break
                if not spoke and now - started > 7:       # nobody said anything
                    return None
                if now - started > 30:
                    break
        return np.concatenate(chunks) if chunks else None

    # ---------- speech to text ----------
    def _load_model(self, quiet=False):
        name = STT_MODELS.get(self.hub.cfg.get("stt_model", "base"), "base")
        with self._model_lock:                         # preload and first use never load it twice
            if self._model is not None and self._model_name == name:
                return self._model
            if FAKE:
                self._model, self._model_name = "fake", name
                return self._model
            if not quiet:
                self.hub.emit({"type": "action", "text": "Loading speech recognition…"})
            from faster_whisper import WhisperModel
            threads = max(2, min(8, (os.cpu_count() or 4) - 1))
            self._model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=threads)
            self._model_name = name
            return self._model

    def _transcribe(self, audio):
        model = self._load_model()
        if FAKE:
            return "öffne spotify"
        # a fixed language is faster and much more reliable for short commands than auto-detect
        segments, _ = model.transcribe(audio.astype(np.float32), language=lang_mod.current(self.hub.cfg),
                                       beam_size=1, vad_filter=True, condition_on_previous_text=False,
                                       without_timestamps=True)
        return " ".join(s.text.strip() for s in segments).strip()
