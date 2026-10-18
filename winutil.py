"""Windows helpers: read the UI like a screen reader, list/focus windows, keep Nova out of the way.

The local brain works with numbered UI elements ("click 12") instead of raw pixels,
which small local models handle much more reliably.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont

FAKE = os.environ.get("NOVA_FAKE") == "1"
IS_WIN = os.name == "nt"

user32 = ctypes.windll.user32 if IS_WIN and not FAKE else None

# uiautomation is big (loads COM type libraries), so it is loaded the first time it is needed
_auto = None
_auto_lock = threading.Lock()
_com = threading.local()
ROLE = {}


def _automation():
    """The uiautomation module, ready to use on the calling thread (or None)."""
    global _auto
    if not user32:
        return None
    with _auto_lock:
        if _auto is None:
            try:
                import uiautomation as auto
                auto.SetGlobalSearchTimeout(1)
                CT = auto.ControlType
                ROLE.update({
                    CT.ButtonControl: "button", CT.SplitButtonControl: "button", CT.EditControl: "textbox",
                    CT.MenuItemControl: "menu item", CT.ListItemControl: "list item", CT.TabItemControl: "tab",
                    CT.HyperlinkControl: "link", CT.CheckBoxControl: "checkbox", CT.ComboBoxControl: "dropdown",
                    CT.TreeItemControl: "tree item", CT.RadioButtonControl: "radio", CT.DataItemControl: "item",
                    CT.MenuBarControl: None, CT.DocumentControl: "document",
                })
                _auto = auto
            except Exception as e:     # still works without it, just no element list
                print("UI Automation unavailable:", e)
                _auto = False
    if not _auto:
        return None
    if not getattr(_com, "ready", False):
        # every thread that talks to UI Automation needs COM set up (the agent runs on worker threads)
        try:
            _com.init = _auto.UIAutomationInitializerInThread(debug=False)
        except Exception:
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 0)
            except Exception:
                pass
        _com.ready = True
    return _auto


def preload():
    """Load UI Automation in the background so the first task doesn't wait for it."""
    if user32:
        threading.Thread(target=_automation, daemon=True).start()

GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80


# ---------- windows ----------
def _title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _is_ours(hwnd) -> bool:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def _is_app_window(hwnd) -> bool:
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    t = _title(hwnd)
    return bool(t) and t not in ("Program Manager",)


def top_windows(limit=15):
    """Visible app windows, front to back (skipping Nova itself)."""
    if FAKE or not user32:
        return [(1, "Downloads - File Explorer"), (2, "todo.txt - Notepad")]
    out = []
    hwnd = user32.GetTopWindow(None)
    while hwnd and len(out) < limit:
        if _is_app_window(hwnd) and not _is_ours(hwnd):
            out.append((hwnd, _title(hwnd)))
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    return out


def target_window():
    """The window the user is working in: the foreground one, or the one behind Nova."""
    if FAKE or not user32:
        return 1
    fg = user32.GetForegroundWindow()
    if fg and not _is_ours(fg) and _is_app_window(fg):
        return fg
    wins = top_windows(1)
    return wins[0][0] if wins else None


def step_out_of_nova():
    """If Nova's own window has keyboard focus, hand focus to the app behind it.
    Otherwise typed text would land in Nova's chat box."""
    if FAKE or not user32:
        return
    fg = user32.GetForegroundWindow()
    if fg and _is_ours(fg):
        t = target_window()
        if t:
            focus_hwnd(t)


def focus_hwnd(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    # pressing Alt lets SetForegroundWindow work even when another app is in front
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.25)


def focus_window(title_part: str) -> str:
    if FAKE or not user32:
        return f"Focused {title_part}"
    want = title_part.lower().strip()
    for hwnd, title in top_windows(40):
        if want in title.lower():
            focus_hwnd(hwnd)
            return f"Focused “{title}”."
    names = ", ".join(t for _, t in top_windows(10))
    return f"No window matching “{title_part}”. Open windows: {names}"


# ---------- typing (works with every keyboard layout) ----------
INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 1, 0x2, 0x4
VK_RETURN, VK_TAB = 0x0D, 0x09
ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _key_events(text):
    """KEYEVENTF_UNICODE events: the character itself is sent, not a key on a (US) layout.
    So ä, ß, @, € and emoji come out right on a German keyboard too."""
    out = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in text:
        if ch in "\n\t":                  # real Enter / Tab keys, so line breaks and forms work
            vk = VK_RETURN if ch == "\n" else VK_TAB
            out += [(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)]
            continue
        b = ch.encode("utf-16-le")
        for i in range(0, len(b), 2):       # emoji are two UTF-16 units
            unit = int.from_bytes(b[i:i + 2], "little")
            out += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return out


def type_unicode(text, check=None, chunk=12, pause=0.012):
    """Types text into the focused app. `check()` is called between chunks (raise to stop)."""
    if FAKE or not user32 or not text:
        return
    events = _key_events(text)
    for i in range(0, len(events), chunk * 2):
        if check:
            check()
        part = events[i:i + chunk * 2]
        arr = (_INPUT * len(part))()
        for j, (vk, scan, flags) in enumerate(part):
            arr[j].type = INPUT_KEYBOARD
            arr[j].u.ki = _KEYBDINPUT(vk, scan, flags, 0, 0)
        user32.SendInput(len(part), arr, ctypes.sizeof(_INPUT))
        time.sleep(pause)


# ---------- UI elements ----------
def ui_elements(budget_s=1.4, max_items=120):
    """Returns [(role, name, (left, top, right, bottom), window_title)], front window + taskbar."""
    if FAKE:
        return [("textbox", "Search Downloads", (900, 150, 1160, 175), "Downloads - File Explorer"),
                ("list item", "document_01.pdf", (240, 200, 700, 230), "Downloads - File Explorer"),
                ("list item", "document_02.pdf", (240, 240, 700, 270), "Downloads - File Explorer"),
                ("button", "Close", (1140, 140, 1180, 180), "Downloads - File Explorer"),
                ("button", "Start", (820, 1040, 860, 1078), "Taskbar")]
    auto = _automation()
    if not auto:
        return []
    items, t0 = [], time.time()
    roots = []
    hwnd = target_window()
    if hwnd:
        roots.append((hwnd, _title(hwnd), budget_s))
    tray = user32.FindWindowW("Shell_TrayWnd", None)
    if tray:
        roots.append((tray, "Taskbar", budget_s + 0.4))      # the taskbar gets a little extra time
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    for root_hwnd, wtitle, limit in roots:
        if wtitle == "Taskbar" and len(items) >= 25:
            break                                            # the app had plenty; skip the slow taskbar walk
        try:
            root = auto.ControlFromHandle(root_hwnd)
        except Exception:
            root = None
        if root is None:
            continue
        for c, _depth in auto.WalkControl(root, includeTop=False, maxDepth=20):
            if time.time() - t0 > limit or len(items) >= max_items:
                break
            try:
                role = ROLE.get(c.ControlType)
                if not role:
                    continue
                r = c.BoundingRectangle
                if r.width() < 4 or r.height() < 4 or r.right < 0 or r.bottom < 0 or r.left > sw or r.top > sh:
                    continue
                if c.IsOffscreen:
                    continue
                name = (c.Name or "").strip().replace("\n", " ")
                if role == "textbox" and not name:
                    name = "(empty textbox)"
                if not name:
                    continue
                items.append((role, name[:70], (r.left, r.top, r.right, r.bottom), wtitle))
            except Exception:
                continue
    return items


def annotate(img: Image.Image, elements, scale: float, offset=(0, 0)):
    """Draw numbered boxes on a screenshot so a vision model can match ids to what it sees."""
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    for i, (_role, _name, (l, t, r, b), _w) in enumerate(elements, 1):
        box = [(l - offset[0]) * scale, (t - offset[1]) * scale, (r - offset[0]) * scale, (b - offset[1]) * scale]
        d.rectangle(box, outline=(255, 40, 160), width=2)
        label = str(i)
        tw = d.textlength(label, font=font) + 6
        d.rectangle([box[0], box[1] - 15, box[0] + tw, box[1]], fill=(255, 40, 160))
        d.text((box[0] + 3, box[1] - 15), label, fill=(255, 255, 255), font=font)
    return img
