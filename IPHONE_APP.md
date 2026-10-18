# The Nova iPhone app (.ipa)

The app is a native shell around Nova's interface. Compared with the Safari home-screen version, it adds:

- **Finds your PC automatically** on your Wi-Fi.
- **A working mic button** with on-device speech recognition.
- **Haptics** when you tap on the remote screen.
- **A Rotate button and a full-screen landscape mode** for the Screen tab.

You need a free **GitHub** account to build it and **Sideloadly** on your Windows PC to install it. No Mac is required.

---

## Part 1: Build Nova.ipa (once, about 10 minutes)

1. Create a free account at **github.com**.
2. Click **+ → New repository**. Name it `nova`, choose **Private**, and click **Create repository**.
3. On the new page, click **"uploading an existing file"**.
4. Open your Nova folder on the PC, select **everything inside it** (including the `.github` and `ios` folders), and drag it into the browser. Then click **Commit changes**.
   *If the `.github` folder doesn't show up: in File Explorer, go to View → Show → Hidden items.*
5. Open the **Actions** tab, click **Build iPhone app** on the left, then **Run workflow → Run workflow**.
6. Wait about 5–8 minutes until the run shows a green ✓. Click it, scroll to **Artifacts**, and download **Nova-ipa**.
7. Unzip the download. Inside is **Nova.ipa**.

A private repository includes enough free build minutes for many builds a month.

## Part 2: Install it on your iPhone

1. On the PC, install **iTunes** and **iCloud** from **apple.com**. The Microsoft Store versions don't work with Sideloadly.
2. Install **Sideloadly** from **sideloadly.io**.
3. Connect the iPhone with a cable. Unlock it and tap **Trust**.
4. Open Sideloadly, drag **Nova.ipa** into it, type your Apple ID email, and click **Start**. Enter your password and the 2-factor code when asked.
   *Tip: a separate free Apple ID just for sideloading works fine too.*
5. On the iPhone:
   - Go to **Settings → Privacy & Security → Developer Mode** and turn it on. The phone restarts; confirm afterwards.
   - Go to **Settings → General → VPN & Device Management**, tap your Apple ID, and tap **Trust**.
6. Open **Nova**. Allow **Local Network**, tap your PC in the list, and sign in with your passcode.

## Offline mode: the AI on your iPhone

When your PC can't be reached (it's off, or you're away from home without Tailscale), the app switches by itself to the AI that runs **on the iPhone** (Apple's on-device model). An orange **iPhone-KI** badge at the top shows that this mode is on. As soon as your PC is reachable again, the app goes back to it automatically, within about 10 seconds.

- It works without internet and nothing leaves your phone. Speech recognition runs on the phone too.
- It can chat, answer questions, write, translate and calculate. It can't control your PC, of course.
- It needs an iPhone 15 Pro or newer with iOS 26 and Apple Intelligence turned on (Settings → Apple Intelligence & Siri).
- No PC at all? On the connect screen, tap **Use Nova on this iPhone only**.

## The 7-day rule

With a free Apple ID, Apple makes sideloaded apps stop opening after **7 days**. To renew, connect the iPhone and click **Start** in Sideloadly again with the same Nova.ipa. Your sign-in is kept. Sideloadly can also refresh automatically over Wi-Fi while the PC is on; look for the auto-refresh option.

A paid Apple Developer account ($99 a year) makes it last a full year instead.

**Even when the app expires**, the home-screen version in Safari keeps working, so you're never locked out.

## Using the Screen tab sideways

- Turn your phone sideways (or tap **Rotate** in the app). The PC screen fills the display, controls move to a slim rail on the right, and the iPhone status bar hides.
- Tap the **chat bubble** at the top of the rail to go back to the chat.
- **Main / Screen 2 / All** at the top switches monitors.
- In the app, **Rotate** works even with the iPhone's rotation lock on.

## Updating the app later

Change files in the `ios` folder on GitHub (or re-upload them) and the app builds again automatically. You can also run the workflow from the Actions tab yourself. Changes to the PC part of Nova (the chat and Screen tab design) show up in the app right away without rebuilding, because the app loads them from your PC.

## If the build fails

Open the failed run, click the red step, and copy the last 30 or so lines. Send them to Claude, which can fix it.
