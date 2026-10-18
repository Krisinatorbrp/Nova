"""Settings storage for Nova. Lives in %APPDATA%\\Nova\\config.json on Windows."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

_save_lock = threading.Lock()

if os.name == "nt" and os.environ.get("APPDATA"):
    CONFIG_DIR = Path(os.environ["APPDATA"]) / "Nova"
else:
    CONFIG_DIR = Path.home() / ".nova"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS = {
    "assistant_name": "Nova",
    # "local" = runs on this PC with Ollama (free, private). "claude" = Claude API (smarter, paid).
    "brain": "local",
    "local_model": "",               # picked for your GPU on first run, e.g. qwen3-vl:8b
    "ollama_host": "http://127.0.0.1:11434",
    "local_ctx": 8192,               # smaller = faster answers
    "local_vision": True,            # send screenshots to the local model (turn off on very weak PCs)
    "local_max_steps": 30,
    "local_shot_width": 1024,
    "api_key": "",
    # Sonnet 5.5 = fast + cheaper, Opus 5.5 = smartest. Both support the computer toolset.
    "model": "claude-sonnet-5-5",
    "computer_tool": "computer_toolset_20260801",
    "max_steps": 60,                 # safety cap on actions per request
    "screenshot_long_edge": 1456,    # screenshots are downscaled to this before sending
    "port": 8765,
    "phone_access": True,            # serve on your network so the iPhone app can connect
    "passcode_hash": "",
    "passcode_salt": "",
    "allow_shell": True,             # lets Nova run PowerShell commands
    "confirm_shell": True,           # ...but only after you tap Allow
    "always_on_top": True,
    "hide_from_screenshots": True,   # Nova's own window is invisible to its screenshots
    "hotkey": "ctrl+alt+space",      # show / hide the window
    "ask_hotkey": "ctrl+shift+space",  # ask Nova something from any app
    "speak_replies": False,
    "allow_remote": True,            # Screen tab: view and control the PC from your phone
    "remote_fps": 8,
    "widget": True,                  # round particle widget on the desktop
    "widget_size": "m",              # s / m / l
    "widget_on_top": False,          # False = rests on the desktop below your windows
    "widget_x": None,                # remembered position
    "widget_y": None,
    "orb_color": "#2896FF",          # colour of the orb / HUD (any RGB colour)
    "show_transcript": True,         # speech bubble under the widget + caption in fullscreen
    "voice_name": "",                # "" = system default voice
    "voice_rate": 1.0,
    "voice_pitch": 1.0,
    "voice_volume": 1.0,
    "voice_engine": "windows",       # windows / piper (local, natural) / eleven (ElevenLabs, premium)
    "piper_voice": "",
    "eleven_key": "",
    "eleven_voice": "",
    "eleven_model": "eleven_flash_v2_5",
    "stt_model": "base",             # speech recognition: tiny / base / small
    "auto_send": True,               # send what you said right away
    "talk_hotkey": "ctrl+shift+m",   # start / stop talking from any app
    "language": "auto",              # auto / de / en: app texts, replies and voice
    "greet_on_start": True,          # "Guten Tag, Sir. Was kann ich für Sie tun?" when Nova starts
    "phone_tokens": [],              # signed-in phones (only hashes are stored), survive restarts
    "config_version": 2,
}

# Settings the UI is allowed to change (api_key / passcode go through setup).
EDITABLE = {"assistant_name", "model", "brain", "local_model", "local_vision", "max_steps", "allow_shell", "confirm_shell",
            "always_on_top", "speak_replies", "phone_access", "screenshot_long_edge",
            "allow_remote", "widget", "widget_size", "widget_on_top", "orb_color", "show_transcript",
            "voice_name", "voice_rate", "voice_pitch", "voice_volume", "language",
            "hotkey", "ask_hotkey", "talk_hotkey", "voice_engine", "piper_voice", "eleven_voice",
            "eleven_model", "stt_model", "auto_send", "greet_on_start"}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if cfg.get("config_version", 1) < 2:          # faster defaults for existing installs
        if cfg.get("local_ctx") == 16384:
            cfg["local_ctx"] = 8192
        if cfg.get("local_shot_width") == 1280:
            cfg["local_shot_width"] = 1024
        cfg["config_version"] = 2
    if not cfg["api_key"] and os.environ.get("ANTHROPIC_API_KEY"):
        cfg["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    return cfg


def save(cfg: dict) -> None:
    """Writes the settings atomically. Safe to call from several threads at once."""
    data = json.dumps(dict(cfg), indent=2)      # copy first: another thread may be changing cfg
    with _save_lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(data, encoding="utf-8")
        for attempt in range(5):
            try:
                tmp.replace(CONFIG_PATH)
                return
            except PermissionError:              # Windows: a virus scanner may hold the file a moment
                if attempt == 4:
                    raise
                time.sleep(0.1)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_passcode(cfg: dict, passcode: str) -> None:
    salt = secrets.token_hex(16)
    cfg["passcode_salt"] = salt
    cfg["passcode_hash"] = _hash(passcode, salt)


def check_passcode(cfg: dict, passcode: str) -> bool:
    if not cfg.get("passcode_hash"):
        return False
    return hmac.compare_digest(_hash(passcode, cfg["passcode_salt"]), cfg["passcode_hash"])


def _hash(passcode: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", passcode.encode(), salt.encode(), 200_000).hex()
