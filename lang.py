"""Language helpers: which language Nova speaks, and the texts the backend says itself."""
import ctypes
import locale
import os

NAMES = {"de": "German", "en": "English"}


_system = None


def _system_lang() -> str:
    """The Windows display language (looked up once)."""
    global _system
    if _system is None:
        loc = ""
        try:
            if os.name == "nt":
                lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                _system = "de" if (lid & 0x3FF) == 0x07 else "en"   # 0x07 = German (DE, AT, CH...)
                return _system
        except Exception:
            pass
        try:
            loc = (locale.getlocale()[0] or "").lower()
        except Exception:
            pass
        _system = "de" if loc.startswith(("de", "german")) else "en"
    return _system


def current(cfg) -> str:
    """'de' or 'en'. 'auto' follows the Windows display language."""
    lang = cfg.get("language", "auto")
    if lang in NAMES:
        return lang
    return _system_lang()


TEXTS = {
    "stopped": {"en": "Okay, I stopped.", "de": "Okay, ich habe aufgehört."},
    "greeting": {"en": "Good day, sir. What can I do for you?", "de": "Guten Tag, Sir. Was kann ich für Sie tun?"},
    "cant": {"en": "I can't help with that one.", "de": "Dabei kann ich nicht helfen."},
    "step_limit": {"en": "I hit my step limit, so I paused here. Say 'continue' to keep going.",
                   "de": "Ich habe mein Schritt-Limit erreicht und hier pausiert. Sag „weiter“, dann mache ich weiter."},
    "busy": {"en": "I'm still working on the last request. Tap stop first if you want to change it.",
             "de": "Ich arbeite noch an der letzten Aufgabe. Tippe zuerst auf Stopp, wenn du etwas ändern willst."},
    "setup_first": {"en": "Finish setup first: open Settings and pick a brain.",
                    "de": "Bitte zuerst einrichten: Öffne die Einstellungen und wähle ein Gehirn."},
    "need_ok": {"en": "I need your OK for something. Double-click me to open the chat.",
                "de": "Ich brauche dein OK. Doppelklick auf mich öffnet den Chat."},
    "starting_ollama": {"en": "Starting Ollama…", "de": "Starte Ollama…"},
    "looking": {"en": "Looking at the screen", "de": "Schaue auf den Bildschirm"},
    "menu_chat": {"en": "Open chat", "de": "Chat öffnen"},
    "menu_transcript": {"en": "Show transcript", "de": "Transkript anzeigen"},
    "menu_top": {"en": "Always on top", "de": "Immer im Vordergrund"},
    "menu_size": {"en": "Size", "de": "Größe"},
    "menu_small": {"en": "Small", "de": "Klein"},
    "menu_medium": {"en": "Medium", "de": "Mittel"},
    "menu_large": {"en": "Large", "de": "Groß"},
    "menu_hide": {"en": "Hide widget", "de": "Widget ausblenden"},
    "menu_quit": {"en": "Quit {name}", "de": "{name} beenden"},
}


def t(cfg, key, **kw) -> str:
    text = TEXTS.get(key, {}).get(current(cfg)) or TEXTS.get(key, {}).get("en", key)
    return text.format(**kw) if kw else text


def reply_rule(cfg) -> str:
    """Line for the system prompt so the AI answers in the chosen language."""
    lang = cfg.get("language", "auto")
    if lang in NAMES:
        return f"Always reply in {NAMES[lang]}, even if the user writes in another language."
    return "Reply in the language the user writes in."
