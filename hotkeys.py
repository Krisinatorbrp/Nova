"""Global hotkeys (work in every app): ask Nova (type), talk to Nova (microphone), show / hide the window.

Both are freely assignable in Settings and change immediately, without restarting Nova.
"""
import ctypes
import os
import threading

IS_WIN = os.name == "nt"


def bring_to_front(hwnd):
    """Windows only lets an app grab focus in some situations; a tapped Alt key unlocks it."""
    if not (IS_WIN and hwnd):
        return
    u = ctypes.windll.user32
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)                     # restore
    u.keybd_event(0x12, 0, 0, 0)                  # Alt down
    u.SetForegroundWindow(hwnd)
    u.keybd_event(0x12, 0, 2, 0)                  # Alt up
    u.SetFocus(hwnd)


class Hotkeys:
    def __init__(self, hub, window, get_hwnd, api=None):
        self.hub = hub
        self.window = window
        self.api = api                    # app.WindowApi: shows / hides and tells the page
        self.get_hwnd = get_hwnd
        self.paused = False
        self._handles = []
        self._active = None               # the combinations currently registered
        self._lock = threading.Lock()
        self.errors = {}

    # ---------- actions ----------
    def ask(self):
        """Show Nova with the cursor in the input box, ready to type."""
        if self.paused:
            return
        self.hub.warm()
        self._show()
        bring_to_front(self.get_hwnd())
        try:
            self.window.evaluate_js("window.novaAsk && window.novaAsk()")
        except Exception:
            pass
        self.hub.emit({"type": "ask"})            # the widget gives a little pulse

    def talk(self):
        """Start (or stop) talking to Nova."""
        if self.paused:
            return
        self.hub.listener.toggle()

    def toggle(self):
        if self.paused:
            return
        h = self.get_hwnd()
        if IS_WIN and h and ctypes.windll.user32.IsWindowVisible(h) and ctypes.windll.user32.GetForegroundWindow() == h:
            self.api.hide_window() if self.api else self.window.hide()
        else:
            self._show()
            bring_to_front(h)

    def _show(self):
        if self.api:
            self.api.show_window()
        else:
            self.window.show()
            self.window.restore()

    # ---------- (re)registering ----------
    def apply(self):
        """Register the hotkeys from the settings. Safe to call again after they change."""
        try:
            import keyboard
        except Exception as e:
            self.errors = {"all": str(e)}
            return
        cfg = self.hub.cfg
        wanted = tuple((cfg.get(k) or "").strip() for k in ("ask_hotkey", "hotkey", "talk_hotkey"))
        if wanted == self._active:
            return                        # nothing changed (e.g. you only picked a new colour)
        with self._lock:
            for h in self._handles:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
            self._handles, self.errors = [], {}
            cfg = self.hub.cfg
            for key, fn in (("ask_hotkey", self.ask), ("hotkey", self.toggle), ("talk_hotkey", self.talk)):
                combo = (cfg.get(key) or "").strip()
                if not combo:
                    continue
                try:
                    # no key blocking (suppress): that mode of the keyboard library can freeze input
                    self._handles.append(keyboard.add_hotkey(combo, lambda f=fn: threading.Thread(target=f, daemon=True).start()))
                except Exception as e:
                    self.errors[key] = str(e)
            self._active = wanted
