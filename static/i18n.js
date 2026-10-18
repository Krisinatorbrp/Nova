// App language. English texts are the keys; German translations below.
// t('Settings') -> 'Einstellungen' when the language is German.

const DE = {
  // header / chat
  'Ready': 'Bereit', 'Thinking…': 'Denke nach…', 'Working on your PC': 'Arbeite an deinem PC', 'Needs your OK': 'Braucht dein OK',
  'Listening…': 'Höre zu…', 'Offline': 'Offline', 'Phone is viewing': 'Handy schaut zu', 'Chat': 'Chat', 'Screen': 'Bildschirm',
  'Good morning': 'Guten Morgen', 'Good afternoon': 'Guten Tag', 'Good evening': 'Guten Abend', 'Up late?': 'Noch wach?',
  'What can I do for you?': 'Was kann ich für dich tun?',
  'Tidy up my Downloads folder': 'Räum meinen Downloads-Ordner auf',
  "What's taking up my disk space?": 'Was belegt meinen Speicherplatz?',
  'Open YouTube and play lo-fi music': 'Öffne YouTube und spiel Lo-Fi-Musik',
  "Write a note in Notepad with today's to-dos": 'Schreib eine Notiz mit meinen heutigen To-dos',
  'Ask {name} anything…': 'Frag {name} etwas…',
  'Working': 'Arbeite', 'Did {n} step on your PC': '{n} Schritt am PC erledigt', 'Did {n} steps on your PC': '{n} Schritte am PC erledigt',
  'from iPhone': 'vom iPhone', 'from PC': 'vom PC', "Don't run": 'Nicht ausführen', 'Allow': 'Erlauben',
  '✓ Allowed': '✓ Erlaubt', '✕ Declined': '✕ Abgelehnt', 'Run this PowerShell command?': 'Diesen PowerShell-Befehl ausführen?',
  'Finish setting up Nova on your PC first.': 'Richte Nova zuerst auf deinem PC ein.',
  'Restart Nova': 'Nova neu starten',
  'Fullscreen (F11)': 'Vollbild (F11)', 'Fullscreen': 'Vollbild', 'New conversation': 'Neues Gespräch', 'Settings': 'Einstellungen',
  'Minimize': 'Minimieren', 'Hide (Ctrl+Alt+Space brings it back)': 'Ausblenden (Strg+Alt+Leertaste holt es zurück)', 'Close': 'Schließen',
  'Speak': 'Sprechen', 'Send': 'Senden',
  // HUD
  'ONLINE': 'ONLINE', 'PROCESSING': 'VERARBEITE', 'EXECUTING': 'FÜHRE AUS', 'AWAITING CONFIRMATION': 'WARTE AUF BESTÄTIGUNG',
  'LISTENING': 'HÖRE ZU', 'OFFLINE': 'OFFLINE',
  // screen tab
  'Connecting to your PC…': 'Verbinde mit deinem PC…', 'Reconnecting…': 'Verbinde neu…',
  'Nova is using your PC. View only.': 'Nova arbeitet gerade am PC. Nur ansehen.', 'Stop Nova': 'Nova stoppen',
  'Del': 'Entf', 'Copy': 'Kopieren', 'Paste': 'Einfügen', 'Undo': 'Rückgängig', 'Select all': 'Alles', 'Mute': 'Stumm',
  'Type': 'Tippen', 'Keys': 'Tasten', 'Scroll': 'Scrollen', 'Right': 'Rechts', 'Fit': 'Einpassen', 'Rotate': 'Drehen',
  'Main': 'Haupt', 'Screen {n}': 'Bildschirm {n}', 'All': 'Alle',
  'Back to chat': 'Zurück zum Chat', 'Keyboard': 'Tastatur', 'Special keys': 'Sondertasten', 'Scroll mode': 'Scroll-Modus',
  'Right-click next tap': 'Nächster Tipp = Rechtsklick', 'Right-click': 'Rechtsklick', 'Sharper picture': 'Schärferes Bild',
  'Fit screen': 'Einpassen', 'Type on your PC': 'Am PC tippen',
  'Controlling your PC': 'Du steuerst deinen PC',
  'Tap to click · double-tap to open': 'Tippen = Klick · Doppeltippen = Öffnen',
  'Long-press for right-click · long-press + move to drag': 'Lang drücken = Rechtsklick · lang drücken + ziehen = Verschieben',
  'Pinch to zoom · turn your phone sideways for a bigger view': 'Zwei Finger = Zoom · Handy quer = größere Ansicht',
  'Got it': 'Verstanden',
  'Screen sharing is turned off on your PC.\nTurn on “Screen tab on iPhone” in Nova’s settings.':
    'Bildschirmfreigabe ist am PC aus.\nSchalte „Bildschirm-Tab am iPhone“ in Novas Einstellungen ein.',
  'Please reconnect: open the Chat tab and sign in again.': 'Bitte neu verbinden: Öffne den Chat-Tab und melde dich erneut an.',
  // setup / login
  "Let's set up": 'Lass uns einrichten:', "First, choose where Nova's brain runs.": 'Wähle zuerst, wo Novas Gehirn läuft.',
  'This PC': 'Dieser PC', 'Free · private · works offline': 'Kostenlos · privat · offline', 'Claude': 'Claude',
  'Smartest · needs paid API credit': 'Am klügsten · braucht API-Guthaben', 'Claude API key': 'Claude-API-Schlüssel', 'get one': 'hier holen',
  'Assistant name': 'Name des Assistenten', 'iPhone passcode': 'iPhone-Code', '(optional, 6+ characters)': '(optional, mind. 6 Zeichen)',
  'Used to connect your phone': 'Damit verbindest du dein Handy', 'Start': 'Starten', 'Connect to': 'Verbinden mit',
  'Enter the passcode you set on your PC.': 'Gib den Code ein, den du am PC festgelegt hast.', 'Passcode': 'Code', 'Connect': 'Verbinden',
  'Download a model first (or pick one that says Ready).': 'Lade zuerst ein Modell herunter (oder wähle eins mit „Bereit“).',
  // settings
  'Brain': 'Gehirn', 'Free · private': 'Kostenlos · privat', 'Smartest · paid': 'Am klügsten · kostet',
  'Let the local brain see screenshots': 'Lokales Gehirn darf Screenshots sehen',
  'Turn off on slow PCs (it still reads buttons by name)': 'Auf langsamen PCs ausschalten (es liest Knöpfe trotzdem per Name)',
  'Claude model': 'Claude-Modell', 'Claude Sonnet 5.5 · fast': 'Claude Sonnet 5.5 · schnell', 'Claude Opus 5.5 · smartest': 'Claude Opus 5.5 · am klügsten',
  'API key': 'API-Schlüssel', 'Leave empty to keep the current key': 'Leer lassen, um den aktuellen Schlüssel zu behalten',
  'Allow PowerShell commands': 'PowerShell-Befehle erlauben', 'Faster file and system tasks': 'Schneller bei Dateien und System',
  'Ask before each command': 'Vor jedem Befehl fragen', 'You tap Allow first': 'Du tippst zuerst auf Erlauben',
  'Keep window on top': 'Fenster im Vordergrund halten', 'Desktop widget': 'Desktop-Widget',
  'Round particle sphere you can drag anywhere on the desktop': 'Partikel-Kugel, die du überall auf den Desktop ziehen kannst',
  'iPhone access': 'iPhone-Zugriff', 'Restart Nova after changing': 'Nach Änderung Nova neu starten',
  'Screen tab on iPhone': 'Bildschirm-Tab am iPhone', 'See and control this PC from your phone': 'Diesen PC vom Handy aus sehen und steuern',
  'Language': 'Sprache', 'Automatic (Windows)': 'Automatisch (Windows)',
  'Look': 'Aussehen', 'Orb colour': 'Farbe der Kugel', 'Blue': 'Blau', 'Cyan': 'Cyan', 'Purple': 'Lila', 'Pink': 'Pink', 'Red': 'Rot',
  'Gold': 'Gold', 'Green': 'Grün', 'White': 'Weiß',
  'Show transcript': 'Transkript anzeigen', 'Speech bubble under the widget and text in fullscreen': 'Sprechblase am Widget und Text im Vollbild',
  'Greet me when Nova starts': 'Beim Start begrüßen', '“Good day, sir. What can I do for you?”': '„Guten Tag, Sir. Was kann ich für Sie tun?“',
  'Voice': 'Stimme', 'Read replies aloud': 'Antworten vorlesen', 'System default': 'Systemstandard', 'Speed': 'Tempo', 'Pitch': 'Tonhöhe',
  'Volume': 'Lautstärke', '▶ Test voice': '▶ Stimme testen', 'Your iPhone': 'Dein iPhone', 'Phone passcode': 'Handy-Code',
  'Set or change (6+ characters)': 'Festlegen oder ändern (mind. 6 Zeichen)',
  'On your iPhone, open Safari and go to:': 'Öffne auf dem iPhone Safari und gehe zu:', 'Tap Share →': 'Tippe auf Teilen →',
  'Add to Home Screen': 'Zum Home-Bildschirm', '. Nova now opens like an app.': '. Nova öffnet sich dann wie eine App.',
  'Away from home? Install': 'Unterwegs? Installiere', 'on both devices and use the Tailscale address.': 'auf beiden Geräten und nutze die Tailscale-Adresse.',
  'Save': 'Speichern', 'Connect to a different PC': 'Mit anderem PC verbinden', 'Disconnect this phone': 'Dieses Handy trennen',
  'Wi-Fi (same network)': 'WLAN (gleiches Netzwerk)', 'Tailscale (works anywhere)': 'Tailscale (funktioniert überall)',
  'Hotkeys': 'Tastenkürzel', 'Ask': 'Fragen', 'Opens the chat ready to type, from any app': 'Öffnet den Chat zum Tippen, aus jeder App',
  'Show / hide window': 'Fenster zeigen / ausblenden', 'Off': 'Aus', 'Press keys…': 'Tasten drücken…',
  'Click a box, then press your key combination. Esc cancels, Backspace turns it off.': 'Klicke ein Feld an und drücke deine Tastenkombination. Esc bricht ab, Rücktaste schaltet sie aus.',
  'Use at least one of Ctrl, Alt, Shift or Win (or an F key).': 'Nutze mindestens Strg, Alt, Umschalt oder Win (oder eine F-Taste).',
  'That combination is already used by the other hotkey.': 'Diese Kombination nutzt schon das andere Tastenkürzel.',
  'This hotkey could not be registered (another app may use it):': 'Dieses Tastenkürzel ließ sich nicht festlegen (evtl. nutzt es eine andere App):',
  'Voice engine': 'Stimmen-Engine', 'Built in · robotic': 'Eingebaut · roboterhaft', 'Natural · free · offline': 'Natürlich · kostenlos · offline',
  'Premium · paid · online': 'Premium · kostet · online', 'ElevenLabs API key': 'ElevenLabs-API-Schlüssel', 'Load voices first': 'Zuerst Stimmen laden',
  'Load my voices': 'Meine Stimmen laden', 'Model': 'Modell', 'Saved voice': 'Gespeicherte Stimme',
  'Voice input': 'Spracheingabe', 'Speech recognition': 'Spracherkennung', 'Fast · less accurate (75 MB)': 'Schnell · ungenauer (75 MB)',
  'Balanced (145 MB)': 'Ausgewogen (145 MB)', 'Accurate · slower (480 MB)': 'Genau · langsamer (480 MB)', 'Send right away': 'Sofort senden',
  'Off: the text lands in the chat box so you can check it first': 'Aus: Der Text landet im Chatfeld, damit du ihn erst prüfen kannst',
  'Runs on your PC with Whisper. The model downloads once on first use.': 'Läuft mit Whisper auf deinem PC. Das Modell wird beim ersten Mal einmalig geladen.',
  'Talk': 'Einsprechen', 'Start talking, it stops when you pause': 'Losreden, stoppt von selbst, wenn du eine Pause machst',
  "I didn't hear anything. Try again a bit louder.": 'Ich habe nichts gehört. Versuch es etwas lauter.',
  'Loading speech recognition…': 'Lade Spracherkennung…',
  'Turn on iPhone access first.': 'Schalte zuerst den iPhone-Zugriff ein.',
  'Pick a downloaded model (or download one) for “This PC”.': 'Wähle ein heruntergeladenes Modell für „Dieser PC“ (oder lade eins).',
  'Paste a Claude API key to use Claude.': 'Füge einen Claude-API-Schlüssel ein, um Claude zu nutzen.',
  'Hello, I am {name}. This is how I sound with these settings.': 'Hallo, ich bin {name}. So klinge ich mit diesen Einstellungen.',
  // local model box
  'Checking your PC…': 'Prüfe deinen PC…', 'Ollama is installed but not running.': 'Ollama ist installiert, läuft aber nicht.',
  "It's the free program that runs the AI on your PC.": 'Das ist das kostenlose Programm, das die KI auf deinem PC ausführt.',
  'Start Ollama': 'Ollama starten', 'Starting…': 'Starte…', 'One more thing to install: Ollama': 'Noch eine Sache installieren: Ollama',
  "It's the free program that runs the AI on your PC. Install it, then come back here.": 'Das kostenlose Programm, das die KI auf deinem PC ausführt. Installiere es und komm dann zurück.',
  'Get Ollama': 'Ollama holen', 'Check again': 'Nochmal prüfen', 'Graphics': 'Grafikkarte',
  'No dedicated graphics card found (it will run slower on the CPU)': 'Keine eigene Grafikkarte gefunden (läuft langsamer auf dem Prozessor)',
  'best for your PC': 'am besten für deinen PC', '✓ Ready': '✓ Bereit', 'Download': 'Herunterladen',
  'Qwen3-VL 2B · tiny, for weak PCs': 'Qwen3-VL 2B · winzig, für schwache PCs', 'Qwen3-VL 4B · light': 'Qwen3-VL 4B · leicht',
  'Qwen3-VL 8B · balanced': 'Qwen3-VL 8B · ausgewogen', 'Qwen3-VL 30B · smartest, needs a big GPU': 'Qwen3-VL 30B · am klügsten, braucht große Grafikkarte',
};

// action labels coming from the PC ("Clicking [3] Save" ...)
const ACTION_DE = [
  [/^Looking at the screen/, 'Schaue auf den Bildschirm'], [/^Zooming in/, 'Zoome hinein'], [/^Typing /, 'Tippe '],
  [/^Pressing /, 'Drücke '], [/^Left click/, 'Linksklick'], [/^Right click/, 'Rechtsklick'], [/^Double click/, 'Doppelklick'],
  [/^Triple click/, 'Dreifachklick'], [/^Middle click/, 'Mittelklick'], [/^Scrolling down/, 'Scrolle nach unten'],
  [/^Scrolling up/, 'Scrolle nach oben'], [/^Scrolling /, 'Scrolle '], [/^Dragging/, 'Ziehe'], [/^Waiting a moment/, 'Warte kurz'],
  [/^Opening /, 'Öffne '], [/^Clicking /, 'Klicke '], [/^Right-clicking /, 'Rechtsklick auf '], [/^Running: /, 'Führe aus: '],
  [/^Switching to /, 'Wechsle zu '], [/^Starting Ollama/, 'Starte Ollama'], [/^Loading speech recognition/, 'Lade Spracherkennung'],
];

export let uiLang = 'en';
export function setLang(l) { uiLang = l === 'de' ? 'de' : 'en'; document.documentElement.lang = uiLang; }
export function t(key, vars = {}) {
  let s = (uiLang === 'de' && DE[key]) || key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}
export function tAction(text) {
  if (uiLang !== 'de') return text;
  for (const [re, rep] of ACTION_DE) if (re.test(text)) return text.replace(re, rep);
  return text;
}
// translate every element marked with data-i18n, plus titles / labels / placeholders
export function applyDOM(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(el => {
    if (!el.dataset.en) el.dataset.en = el.textContent;
    el.textContent = t(el.dataset.en);
  });
  for (const attr of ['title', 'aria-label', 'placeholder']) {
    root.querySelectorAll(`[${attr}]`).forEach(el => {
      const keep = 'en' + attr.replace(/-./g, m => m[1].toUpperCase()).replace(/^./, c => c.toUpperCase());
      if (el.dataset.noi18n !== undefined) return;
      if (!el.dataset[keep]) el.dataset[keep] = el.getAttribute(attr);
      el.setAttribute(attr, t(el.dataset[keep]));
    });
  }
}
