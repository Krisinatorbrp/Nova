"""Nova - your own AI for Windows. Run this file (or start.bat) to launch the app."""
import ctypes
import os
import sys
import threading
import time

# Make screen coordinates match real pixels on scaled (125%, 150%...) displays.
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402
import webview  # noqa: E402

from server import app, hub  # noqa: E402
import config  # noqa: E402

WDA_EXCLUDEFROMCAPTURE = 0x11


class WindowApi:
    """Functions the window's buttons can call (window.pywebview.api.*)."""

    def __init__(self):
        self.window = None
        self.widget = None          # the desktop widget (widget.DesktopWidget)
        self.hotkeys = None         # global hotkeys (hotkeys.Hotkeys)
        self.quitting = False       # True = really close; otherwise closing only hides the window

    # ---------- showing / hiding (the page pauses its animations while hidden) ----------
    def _visible(self, on):
        try:
            self.window.evaluate_js(f"window.novaVisible && window.novaVisible({'true' if on else 'false'})")
        except Exception:
            pass

    def show_window(self):
        self.window.show()
        self.window.restore()
        self._visible(True)

    def hide_window(self):
        self.window.hide()
        self._visible(False)

    def minimize(self):
        self.window.minimize()

    def hide(self):
        self.hide_window()

    def quit(self):
        self.quitting = True
        if self.widget:
            self.widget.close()
        self.window.destroy()

    def set_on_top(self, on):
        self.window.on_top = bool(on)

    def set_fullscreen(self, on):
        """Fullscreen HUD mode. Goes back to the small popup when turned off."""
        on = bool(on)
        if on != getattr(self, "_full", False):
            self._full = on
            self.window.toggle_fullscreen()
            # the widget would float over the HUD, so it steps aside meanwhile
            if self.widget and hub.cfg.get("widget", True):
                self.widget.show(not on)

    def open_chat(self):
        self.show_window()

    def pause_hotkeys(self, on):
        """While you record a new hotkey in Settings, the old ones must not fire."""
        if self.hotkeys:
            self.hotkeys.paused = bool(on)

    def hotkey_errors(self):
        return self.hotkeys.errors if self.hotkeys else {}

    def set_widget(self, on):
        """Show or hide the desktop widget (from Settings)."""
        hub.cfg["widget"] = bool(on)
        config.save(hub.cfg)
        if self.widget:
            self.widget.show(bool(on))


def start_server(host: str, port: int):
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.05)
    raise RuntimeError(f"Couldn't start the server on port {port}. Is Nova already running?")


def hwnd_of(window, title: str):
    try:
        return int(window.native.Handle.ToInt64())   # pywebview WinForms backend
    except Exception:
        return ctypes.windll.user32.FindWindowW(None, title) or None


def after_start(window, api: WindowApi, title: str):
    cfg = hub.cfg
    if os.name != "nt":
        return
    time.sleep(0.8)
    hwnd = hwnd_of(window, title)
    if hwnd and cfg.get("hide_from_screenshots", True):
        # Nova's own window disappears from screenshots (its own AND yours), so it never
        # blocks what Claude needs to see. Needs Windows 10 2004 or newer.
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

    if api.hotkeys:
        api.hotkeys.apply()


def preload(cfg):
    """Everything slow is loaded in the background while the window opens."""
    if cfg.get("brain") == "local":
        import ollama
        import winutil
        ollama.warm_up(cfg)            # the AI model goes into the graphics card now
        winutil.preload()              # Windows UI Automation (reads buttons by name)
        threading.Thread(target=ollama.gpu_info, daemon=True).start()   # Settings open without a wait
    else:
        import agent
        agent.preload_sdk()            # the Claude library (~2 s to import)
    hub.speaker.preload()              # Piper voice
    if cfg.get("stt_used"):
        hub.listener.preload()         # speech recognition ready before you press the mic


def main():
    cfg = hub.cfg
    host = "0.0.0.0" if cfg.get("phone_access") else "127.0.0.1"
    start_server(host, cfg["port"])
    preload(cfg)
    # the window says hello as soon as it's loaded; if it hasn't after a few seconds, Nova does it itself
    greeter = threading.Timer(8.0, hub.greet)
    greeter.daemon = True
    greeter.start()
    zc = []
    if cfg.get("phone_access"):
        from discovery import advertise
        # lets the iPhone app find this PC by itself (takes a few seconds, so not on the start path)
        threading.Thread(target=lambda: zc.append(advertise(cfg)), daemon=True).start()

    title = cfg.get("assistant_name", "Nova")
    # With the desktop widget on, Nova starts quietly as the widget; click it to open the chat.
    use_widget = cfg.get("widget", True)
    start_hidden = bool(use_widget and hub.configured())
    url = f"http://127.0.0.1:{cfg['port']}/?t={hub.local_token}" + ("&h=1" if start_hidden else "")
    api = WindowApi()

    # Park the window in the bottom-right corner, like Siri.
    w, h = 430, 720
    try:
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        x, y = sw - w - 24, sh - h - 72
    except Exception:
        x = y = None

    window = webview.create_window(
        title, url, js_api=api, width=w, height=h, x=x, y=y,
        min_size=(360, 520), frameless=True, easy_drag=False,
        on_top=cfg.get("always_on_top", True), background_color="#06070B",
        hidden=start_hidden,
    )
    api.window = window
    from widget import DesktopWidget

    def quit_app():
        api.quitting = True
        api.widget.close()
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass
    api.widget = DesktopWidget(hub, api.open_chat, quit_app)
    api.widget.start()

    def on_closing():
        """Alt+F4 / the taskbar's Close: with the widget on, Nova keeps running and only hides the
        chat (open it again from the widget or the hotkey). Quit from the menu really quits."""
        shutting_down = os.name == "nt" and ctypes.windll.user32.GetSystemMetrics(0x2000)   # SM_SHUTTINGDOWN
        if api.quitting or shutting_down or not hub.cfg.get("widget", True) or not hub.configured():
            api.quitting = True
            try:
                api.widget.close()
            except Exception:
                pass
            return True
        threading.Thread(target=api.hide_window, daemon=True).start()
        return False
    window.events.closing += on_closing
    # minimized: no animations either (the handlers run off the window thread)
    # (handlers take no parameters: pywebview passes the window to handlers that have any)
    def on_minimized():
        threading.Thread(target=api._visible, args=(False,), daemon=True).start()

    def on_restored():
        threading.Thread(target=api._visible, args=(True,), daemon=True).start()
    for name, fn in (("minimized", on_minimized), ("restored", on_restored)):
        ev = getattr(window.events, name, None)
        if ev is not None:
            ev += fn

    from hotkeys import Hotkeys
    api.hotkeys = Hotkeys(hub, window, lambda: hwnd_of(window, title), api)
    # new hotkeys from Settings take effect right away
    hub.listeners.append(lambda ev: ev.get("type") == "prefs" and api.hotkeys.apply())
    # "send automatically" is off: show the chat so you can check the dictated text
    hub.listeners.append(lambda ev: ev.get("type") == "dictation" and api.open_chat())
    webview.start(after_start, (window, api, title), private_mode=False)
    for z in zc:
        try:
            z and z.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
