"""Desktop control for Windows: screenshots, mouse and keyboard.

Implements the members of Claude's computer use toolset (computer_toolset_20260801).
Coordinates Claude sends are in *screenshot* pixels; we scale them to the real screen.
"""
import base64
import ctypes
import io
import math
import os
import threading
import time

import mss
from PIL import Image

import winutil

FAKE = os.environ.get("NOVA_FAKE") == "1"  # UI testing without a desktop

if not FAKE:
    import pyautogui
    import pyperclip

    pyautogui.FAILSAFE = True   # slam the mouse into a screen corner to abort
    pyautogui.PAUSE = 0.025     # short pause after each mouse/keyboard call

KEYMAP = {
    "return": "enter", "enter": "enter", "kp_enter": "enter",
    "escape": "esc", "esc": "esc",
    "super": "win", "super_l": "win", "win": "win", "windows": "win", "cmd": "win", "meta": "win",
    "ctrl": "ctrl", "control": "ctrl", "control_l": "ctrl", "ctrl_l": "ctrl",
    "alt": "alt", "alt_l": "alt", "option": "alt",
    "shift": "shift", "shift_l": "shift",
    "tab": "tab", "backspace": "backspace", "delete": "delete", "del": "delete",
    "space": "space", "insert": "insert", "home": "home", "end": "end",
    "page_up": "pageup", "pageup": "pageup", "prior": "pageup",
    "page_down": "pagedown", "pagedown": "pagedown", "next": "pagedown",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "menu": "apps", "caps_lock": "capslock", "print": "printscreen",
    "minus": "-", "plus": "+", "equal": "=", "comma": ",", "period": ".", "slash": "/",
}

MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000


def _norm_key(k: str) -> str:
    k = k.strip()
    low = k.lower().replace(" ", "_")
    if low in KEYMAP:
        return KEYMAP[low]
    if len(k) == 1:
        return k.lower()
    return low  # f1..f24 and other pyautogui names pass through


def _combo(text: str) -> list[str]:
    return [_norm_key(p) for p in text.split("+") if p.strip()]


class Stopped(Exception):
    pass


_tls = threading.local()
_geo = {"t": 0.0, "mon": None}


def _sct():
    """One screen grabber per thread (creating one costs time, and they aren't thread-safe)."""
    s = getattr(_tls, "sct", None)
    if s is None:
        s = _tls.sct = mss.mss()
    return s


def release_grabber():
    """Close this thread's screen grabber (Windows drawing handles are limited per app)."""
    s = getattr(_tls, "sct", None)
    if s is not None:
        _tls.sct = None
        try:
            s.close()
        except Exception:
            pass


def _main_monitor():
    """The main monitor's position and size; re-read at most every 5 s (cheap, but not free)."""
    now = time.time()
    if _geo["mon"] is None or now - _geo["t"] > 5:
        with mss.mss() as sct:                      # a fresh one sees resolution / monitor changes
            mons = sct.monitors
            _geo["mon"] = dict(mons[1] if len(mons) > 1 else mons[0])
        _geo["t"] = now
    return _geo["mon"]


def grab_rgb(mon) -> Image.Image:
    raw = _sct().grab(mon)
    # straight from Windows' BGRA buffer (skips a slow RGB conversion)
    return Image.frombuffer("RGB", raw.size, raw.bgra, "raw", "BGRX", 0, 1)


def image_block(img: Image.Image, quality=88) -> dict:
    """JPEG: several times smaller and faster to encode than PNG, still crisp for reading text."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, subsampling=0)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()}}


class Computer:
    def __init__(self, long_edge: int = 1456, cancel: threading.Event | None = None):
        self.long_edge = long_edge
        self.cancel = cancel or threading.Event()
        self._sct = None
        self._refresh_geometry()

    # ---------- geometry ----------
    def _refresh_geometry(self):
        mon = {"left": 0, "top": 0, "width": 1920, "height": 1080} if FAKE else _main_monitor()
        self.left, self.top = mon["left"], mon["top"]
        self.width, self.height = mon["width"], mon["height"]
        long_edge = max(self.width, self.height)
        # also respect the visual-token budget (ceil(w/28)*ceil(h/28) <= 4784)
        token_scale = math.sqrt(4600 * 28 * 28 / (self.width * self.height))
        self.scale = min(1.0, self.long_edge / long_edge, token_scale)
        self.sw = max(1, int(self.width * self.scale))
        self.sh = max(1, int(self.height * self.scale))

    def to_real(self, xy):
        x, y = xy
        x = min(max(x, 0), self.sw - 1)
        y = min(max(y, 0), self.sh - 1)
        return int(x / self.scale) + self.left, int(y / self.scale) + self.top

    def to_shot(self, x, y):
        return int((x - self.left) * self.scale), int((y - self.top) * self.scale)

    # ---------- capture ----------
    def grab(self) -> Image.Image:
        if FAKE:
            return Image.new("RGB", (self.width, self.height), (30, 40, 60))
        return grab_rgb({"left": self.left, "top": self.top, "width": self.width, "height": self.height})

    def screenshot(self):
        """Returns (content blocks for Claude, small jpeg for the live view)."""
        self._refresh_geometry()
        img = self.grab()
        if img.size != (self.sw, self.sh):
            img = img.resize((self.sw, self.sh), Image.LANCZOS, reducing_gap=3.0)
        return [image_block(img)], self.thumbnail(img)

    def zoom(self, region):
        x0, y0, x1, y1 = region
        rx0, ry0 = self.to_real((min(x0, x1), min(y0, y1)))
        rx1, ry1 = self.to_real((max(x0, x1), max(y0, y1)))
        full = self.grab()
        crop = full.crop((rx0 - self.left, ry0 - self.top,
                          max(rx1 - self.left, rx0 - self.left + 4),
                          max(ry1 - self.top, ry0 - self.top + 4)))
        crop.thumbnail((self.sw, self.sh), Image.LANCZOS)  # fit, keep aspect
        return [image_block(crop, 92)], self.thumbnail(crop)

    @staticmethod
    def thumbnail(img: Image.Image) -> str:
        t = img.copy()
        t.thumbnail((560, 560), Image.BILINEAR, reducing_gap=2.0)
        buf = io.BytesIO()
        t.save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()

    # ---------- helpers ----------
    def _check(self):
        if self.cancel.is_set():
            raise Stopped("Stopped by the user.")

    def _sleep(self, seconds: float):
        end = time.time() + min(float(seconds), 300)
        while time.time() < end:
            self._check()
            time.sleep(0.1)

    def _with_mods(self, mods: str | None, fn):
        keys = _combo(mods) if mods else []
        for k in keys:
            pyautogui.keyDown(k)
        try:
            fn()
        finally:
            for k in reversed(keys):
                pyautogui.keyUp(k)

    def _move(self, coord):
        if coord is not None:
            x, y = self.to_real(coord)
            pyautogui.moveTo(x, y, duration=0.08)

    # ---------- the toolset members ----------
    def run(self, name: str, inp: dict):
        """Run one member action. Returns (result_content, thumbnail_or_None)."""
        self._check()
        if name == "screenshot":
            return self.screenshot()
        if name == "zoom":
            return self.zoom(inp["region"])
        if FAKE:
            time.sleep(0.3)
            return "OK", None

        if name in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
            self._move(inp.get("coordinate"))
            button = {"right_click": "right", "middle_click": "middle"}.get(name, "left")
            clicks = {"double_click": 2, "triple_click": 3}.get(name, 1)
            self._with_mods(inp.get("text"),
                            lambda: pyautogui.click(button=button, clicks=clicks, interval=0.06))
            time.sleep(0.25)
            return "OK", None

        if name == "left_click_drag":
            sx, sy = self.to_real(inp["start_coordinate"])
            ex, ey = self.to_real(inp["coordinate"])

            def drag():
                pyautogui.moveTo(sx, sy, duration=0.1)
                pyautogui.mouseDown()
                pyautogui.moveTo(ex, ey, duration=0.45)
                pyautogui.mouseUp()
            self._with_mods(inp.get("text"), drag)
            return "OK", None

        if name == "mouse_move":
            self._move(inp["coordinate"])
            return "OK", None
        if name == "left_mouse_down":
            pyautogui.mouseDown()
            return "OK", None
        if name == "left_mouse_up":
            pyautogui.mouseUp()
            return "OK", None
        if name == "cursor_position":
            x, y = pyautogui.position()
            sx, sy = self.to_shot(x, y)
            return f"X={sx}, Y={sy}", None

        if name == "scroll":
            self._move(inp.get("coordinate"))
            amount = int(inp.get("scroll_amount", 3))
            direction = inp.get("scroll_direction", "down")

            def scroll():
                for _ in range(amount):
                    if direction in ("up", "down"):
                        delta = 120 if direction == "up" else -120
                        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
                    else:
                        delta = 120 if direction == "right" else -120
                        ctypes.windll.user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, delta, 0)
                    time.sleep(0.03)
            self._with_mods(inp.get("text"), scroll)
            time.sleep(0.2)
            return "OK", None

        if name in ("type", "key", "hold_key"):
            winutil.step_out_of_nova()   # never type into Nova's own chat box
        if name == "type":
            self.type_text(inp["text"])
            return "OK", None

        if name == "key":
            keys = _combo(inp["text"])
            for _ in range(max(1, min(int(inp.get("repeat", 1)), 100))):
                self._check()
                pyautogui.hotkey(*keys, interval=0.03)
                time.sleep(0.03)
            time.sleep(0.15)
            return "OK", None

        if name == "hold_key":
            keys = _combo(inp["text"])
            for k in keys:
                pyautogui.keyDown(k)
            try:
                self._sleep(inp.get("duration", 1))
            finally:
                for k in reversed(keys):
                    pyautogui.keyUp(k)
            return "OK", None

        if name == "wait":
            self._sleep(inp.get("duration", 1))
            return "OK", None

        raise ValueError(f"Unsupported action: {name}")

    def type_text(self, text: str):
        # Sends the characters themselves, so it works on any keyboard layout (QWERTZ: y/z, @, ä, ß, €)
        # and with emoji. Very long text is pasted instead, which is quicker.
        if len(text) <= 600:
            winutil.type_unicode(text, check=self._check)
            return
        try:
            old = pyperclip.paste()
        except Exception:
            old = None
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.25)
        if old is not None:
            try:
                pyperclip.copy(old)
            except Exception:
                pass
