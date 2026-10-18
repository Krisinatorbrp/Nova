"""Remote screen: streams the PC screen to your phone and plays back taps, drags and typing."""
import ctypes
import ctypes.wintypes
import io
import threading
import time

import mss
from PIL import Image, ImageDraw

import winutil
from computer import FAKE, _combo

if not FAKE:
    import pyautogui


# Raw Windows mouse calls: unlike pyautogui they work on every monitor, including ones
# placed left of / above the main screen (negative coordinates).
MOUSE = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010)}


def _mouse_to(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _mouse(button, down=True, up=True):
    d, u = MOUSE[button]
    if down:
        ctypes.windll.user32.mouse_event(d, 0, 0, 0, 0)
    if up:
        ctypes.windll.user32.mouse_event(u, 0, 0, 0, 0)


class RemoteScreen:
    """One instance per connected phone. Capture runs in a worker thread (mss is per-thread)."""

    def __init__(self, index: int = 1):
        self._local = threading.local()
        self.monitors = self._monitors()       # [0] = all screens together, [1..] = each screen
        self.index = 1
        self.select(index)
        self.drag_down = False
        self._last = None                      # (pixels, cursor, size, quality) of the last frame sent

    # ---------- screens ----------
    def _sct(self):
        if FAKE:
            return None
        if not hasattr(self._local, "sct"):
            self._local.sct = mss.mss()
        return self._local.sct

    @staticmethod
    def _monitors():
        if FAKE:
            mons = [{"left": 0, "top": 0, "width": 1920, "height": 1080},
                    {"left": 1920, "top": 120, "width": 1280, "height": 1024}]
        else:
            with mss.mss() as s:
                mons = [{k: m[k] for k in ("left", "top", "width", "height")} for m in s.monitors[1:]]
        if len(mons) > 1:
            left = min(m["left"] for m in mons); top = min(m["top"] for m in mons)
            right = max(m["left"] + m["width"] for m in mons); bottom = max(m["top"] + m["height"] for m in mons)
            combined = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        else:
            combined = dict(mons[0])
        return [combined] + mons

    def select(self, index: int):
        """1, 2, 3... = one screen. 0 = all screens side by side."""
        index = int(index)
        if not 0 <= index < len(self.monitors) or (index == 0 and len(self.monitors) <= 2):
            index = 1
        self.index = index
        self.mon = self.monitors[index]

    def info(self):
        return [{"index": i, "w": m["width"], "h": m["height"],
                 "primary": m["left"] == 0 and m["top"] == 0} for i, m in enumerate(self.monitors) if i > 0]

    def size(self):
        return self.mon["width"], self.mon["height"]

    # ---------- capture ----------
    def frame(self, max_width: int = 1280, quality: int = 60, force: bool = False):
        """A JPEG of the screen, or None when nothing changed since the last one (saves CPU,
        Wi-Fi and the phone's battery while the screen is still)."""
        img, raw = self._grab()
        x, y = self._cursor()
        key = (raw, x, y, max_width, quality, self.index)
        if not force and raw is not None and self._last == key:
            return None
        self._last = key
        # draw the mouse pointer (screen captures don't include it)
        if 0 <= x < img.width and 0 <= y < img.height:
            d = ImageDraw.Draw(img)
            r = max(6, img.width // 220)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255), outline=(20, 20, 20), width=2)
        if img.width > max_width:
            h = int(img.height * max_width / img.width)
            img = img.resize((max_width, h), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=False)
        return buf.getvalue()

    def _grab(self):
        """(image, raw pixel bytes for change detection)"""
        if FAKE:
            if self.index == 0:
                img = Image.new("RGB", (self.mon["width"], self.mon["height"]), (0, 0, 0))
                for i, m in enumerate(self.monitors[1:], 1):
                    img.paste(fake_desktop(m["width"], m["height"], i), (m["left"] - self.mon["left"], m["top"] - self.mon["top"]))
            else:
                img = fake_desktop(self.mon["width"], self.mon["height"], self.index)
            return img, img.tobytes()
        raw = self._sct().grab(self.mon)
        px = raw.bgra
        # read Windows' BGRA buffer directly; .copy() so we can draw the pointer on it
        return Image.frombuffer("RGB", raw.size, px, "raw", "BGRX", 0, 1).copy(), px

    def _cursor(self):
        if FAKE:
            return 960, 540
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x - self.mon["left"], pt.y - self.mon["top"]

    # ---------- input (x, y arrive as 0..1 fractions of the shown screen) ----------
    def _xy(self, ev):
        x = min(max(float(ev.get("x", 0.5)), 0.0), 1.0)
        y = min(max(float(ev.get("y", 0.5)), 0.0), 1.0)
        return (self.mon["left"] + int(x * (self.mon["width"] - 1)),
                self.mon["top"] + int(y * (self.mon["height"] - 1)))

    def handle(self, ev: dict):
        t = ev.get("t")
        if FAKE:
            return
        if t in ("click", "dbl", "right"):
            _mouse_to(*self._xy(ev))
            time.sleep(0.02)
            if t == "right":
                _mouse("right")
            else:
                _mouse("left")
                if t == "dbl":
                    time.sleep(0.05)
                    _mouse("left")
        elif t == "move":
            _mouse_to(*self._xy(ev))
        elif t == "down":
            _mouse_to(*self._xy(ev))
            _mouse("left", up=False)
            self.drag_down = True
        elif t == "up":
            if "x" in ev:
                _mouse_to(*self._xy(ev))
            _mouse("left", down=False)
            self.drag_down = False
        elif t == "scroll":
            if "x" in ev:
                _mouse_to(*self._xy(ev))
            dy = int(ev.get("dy", 0))   # positive = scroll content up (like a wheel up)
            dx = int(ev.get("dx", 0))
            if dy:
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, dy, 0)
            if dx:
                ctypes.windll.user32.mouse_event(0x1000, 0, 0, dx, 0)
        elif t == "type":
            # the characters themselves are sent: right on any keyboard layout (ä, ß, @, €, emoji)
            winutil.type_unicode(str(ev.get("text", ""))[:2000])
        elif t == "key":
            keys = _combo(str(ev.get("text", "")))
            if keys:
                pyautogui.hotkey(*keys, interval=0.02)

    def release(self):
        """Never leave the mouse button stuck down if the phone disconnects mid-drag."""
        if self.drag_down and not FAKE:
            try:
                _mouse("left", down=False)
            except Exception:
                pass
        self.drag_down = False
        sct = getattr(self._local, "sct", None)          # free the screen grabber (same thread)
        if sct is not None:
            try:
                sct.close()
            except Exception:
                pass
            del self._local.sct
        self._last = None


def fake_desktop(w, h, n=1):
    """A pretend Windows desktop for testing the UI without Windows."""
    if n == 2:   # a second pretend screen
        img = Image.new("RGB", (w, h), (70, 30, 80))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((80, 80, w - 80, h - 120), 12, fill=(250, 250, 250))
        d.text((110, 100), "YouTube - Browser", fill=(30, 30, 30))
        d.rectangle((110, 140, w - 110, h - 260), fill=(20, 20, 20))
        d.text((110, h - 240), "lo-fi beats to relax/study to", fill=(30, 30, 30))
        return img
    img = Image.new("RGB", (w, h), (18, 52, 96))
    d = ImageDraw.Draw(img)
    for i in range(h):
        if i % 6 == 0:
            d.line((0, i, w, i), fill=(18 + i // 30, 52 + i // 40, 96 + i // 25))
    d.rectangle((0, h - 48, w, h), fill=(28, 30, 38))
    for i, c in enumerate([(0, 120, 215), (240, 180, 0), (60, 180, 75), (200, 60, 60), (150, 90, 220)]):
        d.rounded_rectangle((w // 2 - 140 + i * 56, h - 40, w // 2 - 104 + i * 56, h - 8), 6, fill=c)
    d.rounded_rectangle((220, 140, 1180, 760), 10, fill=(245, 246, 248))
    d.rectangle((220, 140, 1180, 180), fill=(230, 232, 236))
    d.text((240, 152), "Downloads - File Explorer", fill=(30, 30, 30))
    for r in range(12):
        d.text((260, 210 + r * 42), f"document_{r + 1:02d}.pdf        {12 + r * 3} KB", fill=(40, 40, 40))
    d.rounded_rectangle((1260, 260, 1760, 620), 10, fill=(32, 34, 42))
    d.text((1280, 280), "Notepad - todo.txt", fill=(220, 220, 220))
    d.text((1280, 330), "- buy milk\n- finish project\n- call grandma", fill=(200, 200, 200))
    d.text((w - 120, h - 32), time.strftime("%H:%M:%S"), fill=(230, 230, 230))
    return img
