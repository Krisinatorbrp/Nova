"""Desktop widget: a truly transparent window that shows only the glowing particle orb.

It is a native Windows "layered" window: every pixel has its own transparency, so there is no
background at all, and clicks on empty spots go straight through to the desktop.
Drag the orb to move it, double-click to open the chat, right-click (or the ⋯ button) for options.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes

import config
import lang
from orb_render import OrbRenderer

IS_WIN = os.name == "nt"
SIZES = {"s": 120, "m": 170, "l": 240}

if IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                    ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                           ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                           wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.LPVOID]
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]

WM_DESTROY, WM_TIMER, WM_NCHITTEST, WM_LBUTTONUP = 0x0002, 0x0113, 0x0084, 0x0202
WM_NCLBUTTONDBLCLK, WM_NCRBUTTONUP, WM_RBUTTONUP, WM_EXITSIZEMOVE = 0x00A3, 0x00A5, 0x0205, 0x0232
WM_CONTEXTMENU, WM_SETCURSOR, WM_NULL = 0x007B, 0x0020, 0x0000
WM_APP_SHOW, WM_APP_SETTLE, WM_APP_CLOSE, WM_APP_RESIZE = 0x8001, 0x8002, 0x8003, 0x8004
HTCLIENT, HTCAPTION = 1, 2
WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x80000, 0x80, 0x8, 0x08000000
HWND_TOPMOST, HWND_NOTOPMOST, HWND_BOTTOM = -1, -2, 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
WDA_EXCLUDEFROMCAPTURE = 0x11
MF_STRING, MF_CHECKED, MF_POPUP, MF_SEPARATOR = 0x0, 0x8, 0x10, 0x800
TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x100, 0x2
FPS_ACTIVE, FPS_IDLE = 33, 50          # ms per frame: 30 fps while something happens, 20 fps at rest
DESKTOP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
CMD = {"chat": 1, "transcript": 2, "top": 3, "s": 10, "m": 11, "l": 12, "hide": 20, "quit": 21}


def _lp_xy(lp):
    return ctypes.c_short(lp & 0xFFFF).value, ctypes.c_short((lp >> 16) & 0xFFFF).value


class DesktopWidget:
    """Runs on its own thread with its own Windows message loop."""

    def __init__(self, hub, open_chat, quit_app):
        self.hub = hub
        self.open_chat = open_chat
        self.quit_app = quit_app
        cfg = hub.cfg
        self.r = OrbRenderer(170, cfg.get("orb_color", "#2896FF"), cfg.get("assistant_name", "Nova"))
        self.r.show_transcript = cfg.get("show_transcript", True)
        self.hwnd = None
        self.visible = bool(cfg.get("widget", True))
        self.pos = (0, 0)
        self._bits = None
        self._pending_prefs = None
        self._interval = 0
        self._fs_hidden = False          # tucked away while a fullscreen game / video runs
        self._fs_check = 0.0
        hub.listeners.append(self.on_event)

    # ---------- called from other threads ----------
    def on_event(self, ev):
        t = ev.get("type")
        r = self.r
        if t == "state":
            r.set_state(ev["state"])
        elif t in ("action", "ask"):
            r.pulse()
        elif t == "stream":
            r.stream(ev["text"])
        elif t == "assistant":
            r.say(ev["text"], min(14000, 900 + len(ev["text"]) * 60))
        elif t == "voice":
            r.voice(ev.get("ev"))
        elif t == "listen":
            de = lang.current(self.hub.cfg) == "de"
            if ev.get("on"):
                r.listening = True
                r.note("● " + ("Ich höre zu…" if de else "Listening…"), 30000)
            elif "level" in ev:
                if ev["level"] > 0.5:
                    r.kick_v = 1
            elif not ev.get("on"):
                r.listening = False
                if ev.get("working"):
                    r.note("…", 4000)
                elif ev.get("text"):
                    r.note("„" + ev["text"] + "“", 2500)
                elif ev.get("heard") is False:
                    r.note("Ich habe nichts gehört." if de else "I didn't hear anything.", 2500)
        elif t == "confirm":
            r.say(lang.t(self.hub.cfg, "need_ok"), 5000)
        elif t == "error":
            r.say("⚠ " + ev.get("text", ""), 4000)
        elif t == "prefs":
            self._pending_prefs = dict(ev)   # applied by the widget's own thread before its next frame

    def show(self, on):
        self.visible = bool(on)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_APP_SHOW, 1 if on else 0, 0)

    def close(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_APP_CLOSE, 0, 0)

    def start(self):
        if not IS_WIN:
            return
        threading.Thread(target=self._run, daemon=True, name="nova-widget").start()

    # ---------- window thread ----------
    def _scale(self):
        try:
            return user32.GetDpiForSystem() / 96
        except Exception:
            return 1.0

    def _apply_size(self):
        sc = self._scale()
        self.r.resize(int(SIZES.get(self.hub.cfg.get("widget_size", "m"), 170) * sc), sc)
        self._bits = None

    def _start_pos(self):
        cfg, W, H = self.hub.cfg, self.r.W, self.r.H
        x, y = cfg.get("widget_x"), cfg.get("widget_y")
        m = user32.GetSystemMetrics
        vx, vy, vw, vh = m(76), m(77), m(78), m(79)          # all monitors together
        if x is not None and y is not None and vx - W // 2 <= x <= vx + vw - W // 2 and vy - H // 3 <= y <= vy + vh - H // 3:
            return int(x), int(y)
        return m(0) - W - 10, m(1) - H - 50

    def _run(self):
        self._apply_size()
        self._proc = WNDPROC(self._wndproc)                    # keep a reference!
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32649))   # hand cursor
        wc.lpszClassName = "NovaOrbWidget"
        user32.RegisterClassExW(ctypes.byref(wc))
        ex = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if self.hub.cfg.get("widget_on_top"):
            ex |= WS_EX_TOPMOST
        self.pos = self._start_pos()
        self.hwnd = user32.CreateWindowExW(ex, "NovaOrbWidget", "Nova Widget", WS_POPUP,
                                           self.pos[0], self.pos[1], self.r.W, self.r.H, None, None, hinst, None)
        if not self.hwnd:
            print("Widget window failed:", ctypes.get_last_error())
            return
        try:
            user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE)   # invisible to Nova's screenshots
        except Exception:
            pass
        self._paint()
        if self.visible:
            user32.ShowWindow(self.hwnd, 4)                    # show without stealing focus
        self._settle()
        self._set_rate(FPS_ACTIVE)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _set_rate(self, ms):
        if ms != self._interval:
            self._interval = ms
            user32.SetTimer(self.hwnd, 1, ms, None)

    def _fullscreen_app(self):
        """Is a fullscreen app (game, video, presentation) in front on the widget's monitor?"""
        try:
            state = ctypes.c_int()
            if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0 or state.value not in (2, 3, 4):
                return False
            fg = user32.GetForegroundWindow()
            if not fg or fg == self.hwnd:
                return False
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(fg, cls, 64)
            if cls.value in DESKTOP_CLASSES:
                return False
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            if pid.value == os.getpid():
                return False                                   # Nova's own fullscreen HUD hides the widget anyway
            mon = user32.MonitorFromWindow(fg, 2)
            if mon != user32.MonitorFromWindow(self.hwnd, 2):
                return False                                   # fullscreen on another monitor: stay
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(mon, ctypes.byref(mi))
            rc = wintypes.RECT()
            user32.GetWindowRect(fg, ctypes.byref(rc))
            m = mi.rcMonitor
            return rc.left <= m.left and rc.top <= m.top and rc.right >= m.right and rc.bottom >= m.bottom
        except Exception:
            return False

    def _tick(self):
        now = time.time()
        if now - self._fs_check > 1.5:                         # cheap check, but not every frame
            self._fs_check = now
            fs = self._fullscreen_app()
            if fs != self._fs_hidden:
                self._fs_hidden = fs
                user32.ShowWindow(self.hwnd, 0 if fs else 4)
                if not fs:
                    self._settle()
        if self._fs_hidden:
            self._set_rate(500)
            return
        self._paint()
        self._set_rate(FPS_ACTIVE if self.r.active() else FPS_IDLE)

    def _settle(self):
        top = self.hub.cfg.get("widget_on_top", False)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST if top else HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        if not top:   # rest on the desktop, below your normal windows
            user32.SetWindowPos(self.hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _ensure_dib(self):
        W, H = self.r.W, self.r.H
        if self._bits and self._dib_size == (W, H):
            return
        if self._bits:
            gdi32.SelectObject(self._mdc, self._old)
            gdi32.DeleteObject(self._dib)
            gdi32.DeleteDC(self._mdc)
        screen = user32.GetDC(None)
        self._mdc = gdi32.CreateCompatibleDC(screen)
        user32.ReleaseDC(None, screen)
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        self._dib = gdi32.CreateDIBSection(self._mdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        self._old = gdi32.SelectObject(self._mdc, self._dib)
        self._bits, self._dib_size = bits, (W, H)

    def _apply_prefs(self):
        ev, self._pending_prefs = self._pending_prefs, None
        if not ev:
            return
        r = self.r
        if ev.get("orb_color"):
            r.set_color(ev["orb_color"])
        if ev.get("show_transcript") is not None:
            r.show_transcript = bool(ev["show_transcript"])
        if ev.get("name"):
            r.name = ev["name"]

    def _paint(self):
        self._apply_prefs()
        r = self.r
        # hover: is the mouse over the orb or its bubble?
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        rc = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rc))
        self.pos = (rc.left, rc.top)
        r.hover = r.over_orb(pt.x - rc.left, pt.y - rc.top)
        frame = r.frame()                                  # contiguous, interleaved BGRA (what Windows reads)
        self._ensure_dib()
        ctypes.memmove(self._bits, frame.ctypes.data, frame.nbytes)
        screen = user32.GetDC(None)
        blend = BLENDFUNCTION(0, 0, 255, 1)                    # per-pixel alpha
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wintypes.POINT(*self.pos)),
                                   ctypes.byref(wintypes.SIZE(r.W, r.H)), self._mdc,
                                   ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), 2)
        user32.ReleaseDC(None, screen)

    def _button_at(self, x, y):
        if not (self.r.hover or self.r.listening):
            return None
        for name, bx, by, br in self.r.buttons():
            if (x - bx) ** 2 + (y - by) ** 2 <= (br + 3) ** 2:
                return name
        if self.r.bubble_visible():
            x0, y0, x1, y1 = self.r.bubble_rect()
            if x0 <= x <= x1 and y0 <= y <= y1:
                return "bubble"
        return None

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if msg == WM_TIMER:
                if self.visible:
                    self._tick()
                else:
                    self._set_rate(500)                        # hidden: just wake up now and then
                return 0
            if msg == WM_NCHITTEST:
                x, y = _lp_xy(lp)
                return HTCLIENT if self._button_at(x - self.pos[0], y - self.pos[1]) else HTCAPTION   # drag the orb
            if msg == WM_LBUTTONUP:
                x, y = _lp_xy(lp)
                b = self._button_at(x, y)
                if b in ("chat", "bubble"):
                    self._later(self.open_chat)
                elif b == "mic":
                    self._later(self.hub.listener.toggle)
                elif b == "menu":
                    self._menu()
                return 0
            if msg == WM_NCLBUTTONDBLCLK:
                self._later(self.open_chat)
                return 0
            if msg in (WM_NCRBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU):
                self._menu()
                return 0
            if msg == WM_EXITSIZEMOVE:                         # you let go after dragging: remember the spot
                rc = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rc))
                self.hub.cfg["widget_x"], self.hub.cfg["widget_y"] = rc.left, rc.top
                self._later(config.save, self.hub.cfg)
                self._settle()
                return 0
            if msg == WM_APP_SHOW:
                user32.ShowWindow(hwnd, 4 if wp and not self._fs_hidden else 0)
                if wp:
                    self._settle()
                    self._set_rate(FPS_ACTIVE)
                return 0
            if msg == WM_APP_SETTLE:
                self._settle()
                return 0
            if msg == WM_APP_RESIZE:
                cx, cy = self.pos[0] + self.r.W // 2, self.pos[1] + self.r.SH // 2
                self._apply_size()
                self.pos = (cx - self.r.W // 2, cy - self.r.SH // 2)   # keep the orb centred where it was
                user32.SetWindowPos(hwnd, None, self.pos[0], self.pos[1], self.r.W, self.r.H, SWP_NOACTIVATE | 0x4)
                self._paint()
                return 0
            if msg == WM_APP_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception as e:                                 # never crash the message loop
            print("widget:", e)
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    @staticmethod
    def _later(fn, *args):
        """Run something that may take a while (open the chat window, save, quit) off the widget's
        thread, so the orb never freezes while it happens."""
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _menu(self):
        cfg = self.hub.cfg
        m = user32.CreatePopupMenu()
        sub = user32.CreatePopupMenu()
        size = cfg.get("widget_size", "m")
        T = lambda k, **kw: lang.t(cfg, k, **kw)  # noqa: E731
        for key, label in (("s", T("menu_small")), ("m", T("menu_medium")), ("l", T("menu_large"))):
            user32.AppendMenuW(sub, MF_STRING | (MF_CHECKED if size == key else 0), CMD[key], label)
        user32.AppendMenuW(m, MF_STRING, CMD["chat"], T("menu_chat"))
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(m, MF_STRING | (MF_CHECKED if self.r.show_transcript else 0), CMD["transcript"], T("menu_transcript"))
        user32.AppendMenuW(m, MF_STRING | (MF_CHECKED if cfg.get("widget_on_top") else 0), CMD["top"], T("menu_top"))
        user32.AppendMenuW(m, MF_POPUP, sub, T("menu_size"))
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(m, MF_STRING, CMD["hide"], T("menu_hide"))
        user32.AppendMenuW(m, MF_STRING, CMD["quit"], T("menu_quit", name=cfg.get("assistant_name", "Nova")))
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(m)
        if cmd == CMD["chat"]:
            self._later(self.open_chat)
        elif cmd == CMD["transcript"]:
            self.r.show_transcript = not self.r.show_transcript
            cfg["show_transcript"] = self.r.show_transcript
            self._later(config.save, cfg)
            self.hub.emit({"type": "prefs", "show_transcript": self.r.show_transcript})
        elif cmd == CMD["top"]:
            cfg["widget_on_top"] = not cfg.get("widget_on_top")
            self._later(config.save, cfg)
            self._settle()
        elif cmd in (CMD["s"], CMD["m"], CMD["l"]):
            cfg["widget_size"] = {CMD["s"]: "s", CMD["m"]: "m", CMD["l"]: "l"}[cmd]
            self._later(config.save, cfg)
            user32.PostMessageW(self.hwnd, WM_APP_RESIZE, 0, 0)
        elif cmd == CMD["hide"]:
            cfg["widget"] = False
            self._later(config.save, cfg)
            self.show(False)
        elif cmd == CMD["quit"]:
            self._later(self.quit_app)
        self._settle()
