"""Instant commands: simple things Nova does right away, without asking the AI.

"Öffne Spotify", "lauter", "Lautstärke auf 30", "Pause", "nächstes Lied", "sperr den PC",
"zeig den Desktop", "wie spät ist es" ... answer in well under a second.
Anything that doesn't match exactly goes to the AI as usual.
"""
import ctypes
import os
import re
import subprocess
import time
from datetime import datetime

import winutil
from computer import FAKE

# app / website names -> what to open
APPS = {
    "chrome": "chrome", "google chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "opera": "opera", "brave": "brave",
    "spotify": "spotify:", "discord": "discord:", "steam": "steam:", "whatsapp": "whatsapp:",
    "teams": "msteams:", "outlook": "outlook", "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "notepad": "notepad", "editor": "notepad", "rechner": "calc", "taschenrechner": "calc", "calculator": "calc",
    "explorer": "explorer", "datei explorer": "explorer", "file explorer": "explorer", "dateien": "explorer",
    "einstellungen": "ms-settings:", "settings": "ms-settings:", "task manager": "taskmgr", "taskmanager": "taskmgr",
    "paint": "mspaint", "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
    "vs code": "code", "vscode": "code", "visual studio code": "code", "obs": "obs64",
    "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    "dokumente": os.path.join(os.path.expanduser("~"), "Documents"),
    "documents": os.path.join(os.path.expanduser("~"), "Documents"),
    "bilder": os.path.join(os.path.expanduser("~"), "Pictures"),
    "pictures": os.path.join(os.path.expanduser("~"), "Pictures"),
    "desktop ordner": os.path.join(os.path.expanduser("~"), "Desktop"),
    "youtube": "https://youtube.com", "google": "https://google.com", "netflix": "https://netflix.com",
    "twitch": "https://twitch.tv", "gmail": "https://mail.google.com", "chatgpt": "https://chatgpt.com",
    "amazon": "https://amazon.de", "instagram": "https://instagram.com", "tiktok": "https://tiktok.com",
    "reddit": "https://reddit.com", "github": "https://github.com", "wikipedia": "https://wikipedia.org",
}

FILLER = r"(?:bitte|mal|doch|kurz|please|for me|für mich|jarvis|nova|hey|hallo|ok|okay)"
OPEN = re.compile(rf"^(?:{FILLER}\s+)*(?:öffne|oeffne|starte|start|open|launch|geh auf|go to)\s+(?:mir\s+)?(?:die\s+|den\s+|das\s+|the\s+|meine?n?\s+|my\s+|app\s+|website\s+)?(.+?)(?:\s+auf)?(?:\s+{FILLER})*[.!?]*$", re.I)
# "öffne den Downloads Ordner", "open the Spotify app": the last word only says what kind of thing it is
KIND = re.compile(r"\s+(?:ordner|folder|app|programm|program|anwendung|website|webseite|seite|site)$", re.I)
# "starte einen Timer", "open a new tab": not an app name, the AI should handle it
NOT_A_NAME = re.compile(r"^(?:a|an|ein|eine|einen|einem|new|neue[nrs]?|all|alle)\b", re.I)
VK = {"volumedown": 0xAE, "volumeup": 0xAF, "volumemute": 0xAD, "nexttrack": 0xB0, "prevtrack": 0xB1, "playpause": 0xB3}
VOL_SET = re.compile(r"(?:lautstärke|volume|laut)\s*(?:auf|to|=)?\s*(\d{1,3})\s*%?", re.I)


def _keys(*names, times=1):
    if FAKE:
        return
    if len(names) == 1 and names[0] in VK:          # media keys: straight to Windows, no delay per press
        vk, kb = VK[names[0]], ctypes.windll.user32.keybd_event
        for _ in range(times):
            kb(vk, 0, 1, 0)                            # 1 = extended key
            kb(vk, 0, 3, 0)                            # + key up
            if times > 1:
                time.sleep(0.003)
        return
    import pyautogui
    for _ in range(times):
        pyautogui.press(names[0]) if len(names) == 1 else pyautogui.hotkey(*names)


def _open(target):
    if FAKE:
        return
    try:
        os.startfile(target)  # type: ignore[attr-defined]
    except OSError:
        subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _search_and_open(name):
    """Unknown app: let Windows search find it (Win key, type, Enter)."""
    if FAKE:
        return
    import pyautogui
    pyautogui.press("win")
    time.sleep(0.45)
    winutil.type_unicode(name)                         # umlauts work too ("Übersetzer")
    time.sleep(0.8)
    pyautogui.press("enter")


def handle(text: str, lang: str):
    """Returns a short reply if the command was handled instantly, otherwise None."""
    de = lang == "de"
    s = text.strip().lower().rstrip(".!? ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(rf"^(?:{FILLER}[,!]?\s+)+", "", s)        # "hey nova, ...", "bitte ..."
    if not s or len(s) > 60:
        return None
    say = lambda d, e: d if de else e  # noqa: E731

    # volume
    m = VOL_SET.search(s)
    if m:
        n = max(0, min(100, int(m.group(1))))
        _keys("volumedown", times=50)
        _keys("volumeup", times=round(n / 2))
        return say(f"Lautstärke auf {n} %.", f"Volume set to {n}%.")
    if re.fullmatch(r"(?:mach\s+)?(?:(?:mal|bitte|doch|es)\s+)*(?:lauter|louder|volume up|lautstärke hoch|mehr lautstärke)(?: bitte| please)?", s):
        _keys("volumeup", times=5)
        return say("Lauter.", "Louder.")
    if re.fullmatch(r"(?:mach\s+)?(?:(?:mal|bitte|doch|es)\s+)*(?:leiser|quieter|volume down|lautstärke runter)(?: bitte| please)?", s):
        _keys("volumedown", times=5)
        return say("Leiser.", "Quieter.")
    if re.fullmatch(r"(?:stumm|ton aus|mute|unmute|ton an|stummschalten)(?: bitte| please)?", s):
        _keys("volumemute")
        return say("Ton umgeschaltet.", "Toggled mute.")

    # media
    if re.fullmatch(r"(?:pause|pausieren|play|abspielen|weiter abspielen|musik (?:an|aus|pausieren)|resume|play pause)", s):
        _keys("playpause")
        return say("Okay.", "Okay.")
    if re.fullmatch(r"(?:nächstes|nächster|next)(?: lied| song| track| titel)?|skip|überspringen", s):
        _keys("nexttrack")
        return say("Nächster Titel.", "Next track.")
    if re.fullmatch(r"(?:vorheriges|vorheriger|letztes|previous|zurück)(?: lied| song| track| titel)", s):
        _keys("prevtrack")
        return say("Vorheriger Titel.", "Previous track.")

    # windows
    if re.fullmatch(r"(?:sperr(?:e)? (?:den )?(?:pc|computer|bildschirm)|lock (?:the )?(?:pc|computer|screen))", s):
        if not FAKE:
            ctypes.windll.user32.LockWorkStation()
        return say("PC gesperrt.", "PC locked.")
    if re.fullmatch(r"(?:zeig(?:e)? (?:mir )?(?:den )?desktop|show (?:the )?desktop|alle fenster minimieren|minimize all)", s):
        _keys("win", "d")
        return say("Hier ist dein Desktop.", "Here's your desktop.")
    if re.fullmatch(r"(?:mach (?:einen |ein )?screenshot|screenshot|take a screenshot)", s):
        _keys("win", "printscreen")
        return say("Screenshot gespeichert unter Bilder → Screenshots.", "Screenshot saved in Pictures → Screenshots.")

    # time / date
    if re.fullmatch(r"(?:wie spät ist es|wieviel uhr ist es|wie viel uhr ist es|uhrzeit|what time is it|time)", s):
        return say(f"Es ist {datetime.now():%H:%M} Uhr.", f"It's {datetime.now():%H:%M}.")
    if re.fullmatch(r"(?:welcher tag ist heute|welches datum (?:ist|haben wir) heute|datum|what(?:'s| is) the date(?: today)?|what day is it)", s):
        days_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        now = datetime.now()
        return say(f"Heute ist {days_de[now.weekday()]}, der {now:%d.%m.%Y}.", f"Today is {now:%A, %B %d, %Y}.")

    # open apps / websites / folders
    m = OPEN.match(s)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"\s+(?:auf|for me|bitte|please)$", "", name)
        name = re.sub(rf"^(?:(?:{FILLER}|mir|die|den|das|the|my|meine?n?)\s+)+", "", name)
        if NOT_A_NAME.match(name):
            return None
        target = APPS.get(name)
        if target is None and KIND.search(name):
            name = KIND.sub("", name).strip()
            target = APPS.get(name)
        if target is None and len(name.split()) > 2:   # longer requests: let the AI handle them
            return None
        if target is None and re.fullmatch(r"[\w-]+\.(?:com|de|org|net|at|ch|io|tv|gg)(?:/\S*)?", name):
            target = "https://" + name
        if target:
            _open(target)
        else:
            _search_and_open(name)
        pretty = name[:1].upper() + name[1:]
        return say(f"Öffne {pretty}.", f"Opening {pretty}.")
    return None
