# Stream Deck buttons

WinDock can turn the phone into a Stream Deck: a grid of coloured keys that each
run something on the PC.

## Add a button

On the phone, tap **Add** (or swipe up → Arrange → **+**) and open the **Stream Deck** tab:

| Button | What it does |
| --- | --- |
| **Keyboard shortcut** | Presses a key combination in the window that is in front on the PC: Ctrl, Alt, Shift, Win plus a letter, number, F1–F24, arrows, Enter, Esc, number pad… |
| **Website** | Opens an http(s) address in the PC's default browser. |
| **Multi-action** | Up to 10 steps in order: shortcuts, websites, opening an app, volume/media controls and waits (up to 30 s in total). |

Give each button a name, an emoji symbol and a colour. In **Arrange** mode, tap a
button → **Edit button** to change it.

For the real Stream Deck feel, open **Settings → Icons per page → Stream Deck**
(5 × 3 keys) and turn on labels.

## Tips

- **OBS, Discord, Streamlabs:** bind actions to **F13–F24**. No keyboard has those
  keys, so they never clash with games or other apps. In OBS: Settings → Hotkeys,
  click the field, then press the WinDock button.
- Shortcuts go to the foreground window. Windows blocks input into apps running
  as administrator unless WinDock also runs as administrator.
- Power actions (sleep, restart, shut down, lock) are not allowed inside
  multi-actions, because they always ask first.

## Security

Buttons are stored on the PC and validated there (`src/deck.js`): shortcuts use a
fixed key allowlist, websites must be http(s) without credentials, and the phone
can only run buttons that are already saved. The Windows helper checks every
shortcut and address again before using `SendInput` or the default browser.
Linux supports website buttons; keyboard shortcuts are Windows-only for now.
