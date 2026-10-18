# Nova: your own AI for Windows + iPhone

Nova is your own AI assistant for Windows. It sees your screen, clicks, types, opens apps, and runs PowerShell, and you can use it from your iPhone too.

It has two possible brains, and you can switch anytime in Settings:

| | **This PC** (default) | **Claude** |
|---|---|---|
| Cost | Free | Pay per use (API credit) |
| Privacy | Nothing leaves your PC | Screenshots go to Anthropic |
| Smarts | Good for simple tasks | Much better at long or tricky tasks |
| Needs | Ollama + a graphics card with 6 GB+ is ideal | An API key with credit |

## 1. Install (once)

1. **Install Python 3.11 or newer** from https://www.python.org/downloads/
   In the installer, tick **"Add python.exe to PATH"**.
2. Unzip this folder somewhere permanent, for example `Documents\Nova`.
3. Double-click **`start.bat`**. The first launch installs everything, including **Ollama** (the free program that runs the AI locally), and puts a **Nova** shortcut on your desktop.
4. In the setup screen, keep **This PC** selected and tap **Download** next to the model marked *best for your PC*. That's a one-time download of about 2–20 GB.
5. Pick a name and an iPhone passcode, then tap **Start**.

From then on, open Nova from the desktop shortcut.

**Hotkeys (work in every app):** **Ctrl+Shift+Space** asks Nova: the chat pops up with the cursor ready, so you can type straight away. **Ctrl+Alt+Space** shows or hides the window. Change both under Settings → *Hotkeys*: click the box and press any combination (Esc cancels, Backspace turns it off). Changes apply instantly.

**Desktop widget:** the glowing particle orb floats directly on your desktop, with no background or frame. A band of sparks stretches out to the left and right, and widens while the assistant talks. Clicks on empty spots go straight through to your desktop.
- **Move it:** drag the orb anywhere. It remembers the spot.
- **Open the chat:** double-click the orb, or hover and click the chat button.
- **Options:** right-click, or hover and click **⋯**. You can choose *Show transcript* (speech bubble on/off), *Always on top*, size S/M/L, *Hide widget* and *Quit*.
- The buttons only appear while your mouse is over the orb.
- While a game, video or presentation runs in fullscreen on the same monitor, the widget steps aside and comes back afterwards.
- Closing the chat window (✕ or Alt+F4) only hides it; Nova keeps running as the widget. To really quit, use *Quit* in the widget menu.

**Talk to it:** click the 🎙 button in the widget (hover over the orb) or in the chat, or press **Ctrl+Shift+M** anywhere. Just speak; it stops by itself when you pause, then does what you said. Say **„Stopp"** (or "stop", „abbrechen") to stop whatever Nova is doing and make it be quiet. Speech recognition (Whisper) runs on your PC; the model downloads once on first use. Settings → *Voice input* lets you pick fast / balanced / accurate, and whether the text is sent right away.

**Better voices:** Settings → *Voice* → *Voice engine*:
- **Windows:** the built-in voices.
- **Piper:** natural voices, free and offline. Tap *Download* next to a voice (~60 MB). Thorsten is a great German voice, and Alan gives an English butler feel.
- **ElevenLabs:** premium, near-human voices. Paste your API key, tap *Load my voices*, pick one. It's paid per text, with a small free allowance.

Turn on *Read replies aloud*, then press *Test voice*.

**Greeting:** every time Nova starts, it says „Guten Tag, Sir. Was kann ich für Sie tun?" (in English: "Good day, sir. What can I do for you?") with the voice you picked, even if *Read replies aloud* is off. It follows the language setting. Switch it off under Settings → *Voice* → *Greet me when Nova starts*.

**Your colour and voice:** in Settings → *Look*, pick any RGB colour for the orb, the widget and the HUD rings. Use the colour picker, the R/G/B sliders or the presets; it previews live. Under *Voice*, choose the voice, speed, pitch and volume, and press *Test voice*. The widget and rings move in time with the real voice.

**Fullscreen HUD:** click the expand button at the top (or press **F11**). The window turns into a full-screen HUD with rotating rings and your assistant's name in the middle; the rings speed up while it works and pulse while it talks (turn on *Read replies aloud* in Settings to hear it). **Esc** or the same button goes back to the small popup with the blue particle sphere.

**Speed & language:**
- **Instant commands** run in under a second, without the AI. Examples: „Öffne Spotify“ / "open Chrome", „lauter“, „leiser“, „stumm“, „Lautstärke auf 30“, „Pause“, „nächstes Lied“, „zeig den Desktop“, „sperr den PC“, „mach einen Screenshot“, „wie spät ist es?“. Anything longer goes to the AI as usual.
- Answers appear word by word, and the voice starts with the first sentence.
- The local brain only takes screenshots when it really needs them, the AI model is preloaded at start (and again when you press a hotkey after a long break), and a smaller memory window makes every answer faster. Its instructions stay the same all day, so Ollama can reuse its memory between questions.
- With Claude, the unchanged part of each conversation is cached on Claude's side (prompt caching), so every step answers faster and costs much less. Screenshots are sent as compact JPEGs.
- Nova starts faster: heavy parts (the Claude library, Windows UI reading, voices, speech recognition) load in the background.
- The widget draws its particles about 5× more efficiently and slows down when nothing happens. The chat window stops animating completely while it's hidden.
- Typing works with every keyboard layout (German QWERTZ, umlauts, ß, @, €, emoji).
- **Language:** Settings → *Language*: Automatic (follows Windows), Deutsch or English. This changes the app, the widget menu, the replies and the default voice.

### Which local model?
Nova checks your graphics card and suggests one automatically:

| Your graphics card memory | Model |
|---|---|
| Under 4 GB or none | Qwen3-VL 2B (works, but slow and basic) |
| 4–6 GB | Qwen3-VL 4B |
| 8–16 GB | Qwen3-VL 8B |
| 20 GB+ | Qwen3-VL 30B |

**Tips for the local brain:** give it short, clear tasks ("open Notepad and write X" rather than a five-step plan). It reads the buttons on screen by name, so it works best in normal Windows apps. If it's slow, turn off *Let the local brain see screenshots* in Settings.

## 2. Put it on your iPhone

1. Run Nova on the PC. Windows will ask about network access: allow **Private networks**.
2. In Nova, open **Settings** (the gear icon). It shows the address to use, such as `http://192.168.1.20:8765`.
3. On the iPhone, open that address in **Safari**, enter your passcode, then tap **Share → Add to Home Screen**.
   Nova now has its own icon and opens full screen like an app.
4. **Away from home?** Install the free app **Tailscale** on both the PC and the iPhone and sign in with the same account. Then use the Tailscale address (`http://100.x.x.x:8765`) shown in Settings. It works from anywhere and the connection is encrypted.

**Want a real iPhone app (.ipa)?** See **IPHONE_APP.md**. It builds free on GitHub (no Mac needed) and adds automatic PC discovery, a working mic, haptics, and a full-screen landscape mode. When the PC is off, the app keeps working with the AI on the iPhone itself (offline mode, iPhone 15 Pro or newer with Apple Intelligence).

## Screen tab: control your PC from the phone

On the iPhone, switch from **Chat** to **Screen** at the top to see your PC live and control it yourself.

| Gesture | Does |
|---|---|
| Tap | Click |
| Double-tap | Double-click (open files) |
| Long-press | Right-click |
| Long-press, then move | Drag (move windows, select text) |
| Pinch / two fingers | Zoom and pan the view |
| **Scroll** button | One finger now scrolls the PC |
| **Type** | Opens the keyboard and types on the PC |
| **Keys** | Esc, Tab, Win, arrows, Copy/Paste, Alt+Tab, volume |
| **HD** | Sharper picture (uses more data) |
| **Main / Screen 2 / All** (top of the view) | Switch monitors, or see them all side by side |

Turn your phone sideways for a full-screen view: the controls move to a slim rail on the right, and the chat bubble at the top takes you back. While Nova itself is working, the Screen tab is view-only, with a **Stop Nova** button. When nothing changes on the PC screen, no new pictures are sent, which saves Wi-Fi and battery.
Whenever a phone is watching, the PC window shows a red **Phone is viewing** badge. You can switch the Screen tab off in Settings.

## What it can do

- "Tidy up my Downloads folder by file type"
- "Open Spotify and play my Discover Weekly"
- "What's using all my disk space?"
- "Write an email draft in Outlook to Max saying I'll be late" (it asks before sending)
- "Rename all the photos in this folder by date"
- "Turn on dark mode" / "Set my volume to 30%"

## Safety built in

- **Stop anytime:** tap the ■ button, press **Esc**, or slam the mouse into a screen corner.
- **You approve PowerShell commands** before they run (you can turn this off in Settings).
- Nova asks before sending messages, buying anything, deleting files, or typing passwords.
- Your phone needs the passcode. Five wrong tries locks logins for 10 minutes. Phones stay signed in when you restart Nova; changing the passcode signs all phones out.
- With the **This PC** brain, nothing ever leaves your computer. With Claude, screenshots are sent only while Nova is working on a request.
- Nova's window is hidden from screenshots so it never blocks the view. This also hides it from your own screen recordings.

## Settings

| Setting | What it does |
|---|---|
| Brain | **Sonnet 5.5** is fast and cheaper. **Opus 5.5** is smarter for tricky tasks. |
| Allow PowerShell | Much faster file and system work |
| Ask before each command | Shows an Allow / Don't run card |
| Read replies aloud | Speaks Nova's answers |

Advanced options (port, hotkey, step limit) live in `%APPDATA%\Nova\config.json`.

## Troubleshooting

- **Nothing happens when I open it:** run `debug.bat` to see the error.
- **Clicks land in the wrong place:** Nova controls your *main* monitor only. Move the windows you need there.
- **iPhone can't connect:** both devices must be on the same Wi-Fi (or both on Tailscale), and Windows Firewall must allow Python on private networks.
- **Mic button missing on iPhone:** Safari only allows the mic over HTTPS. Use the dictation key on the iPhone keyboard instead.

## Files

| File | Purpose |
|---|---|
| `app.py` | Starts the app window and server |
| `agent.py` | The Claude brain |
| `local_agent.py` | The local brain (Ollama) |
| `ollama.py` | Model downloads and graphics card detection |
| `winutil.py` | Reads on-screen buttons by name, manages windows |
| `computer.py` | Screenshots, mouse and keyboard control |
| `server.py` | Local web server shared by the PC window and the iPhone |
| `remote.py` | Screen tab: live screen stream and touch control |
| `static/` | The interface (particle sphere + HUD rings in `visual.js`) |
| `widget.py` + `orb_render.py` | The transparent desktop widget |
| `hotkeys.py` | Global hotkeys (ask, show/hide) |
| `speech.py` | Piper / ElevenLabs voices |
| `listen.py` | Microphone + Whisper speech recognition |
| `quick.py` | Instant commands without the AI |
| `lang.py` + `static/i18n.js` | Languages (German / English) |
| `discovery.py` | Lets the iPhone app find this PC on Wi-Fi |
| `ios/` + `.github/` | The iPhone app and its build recipe |
