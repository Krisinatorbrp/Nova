# WinDock for iPhone

A native iOS companion for the **existing WinDock host** on Windows or Linux, at feature
parity with the Android app (0.2.6-preview.1). It finds your PC on the network, verifies
`/health`, and opens the shared landscape dock in `WKWebView`. PIN pairing, app icons, the
drawer and live updates come from your PC; nothing on the PC needs to change.

This is source plus a GitHub simulator build, **not a public iPhone download**. An unsigned
archive cannot be installed on a phone by downloading it; it has to be signed first (see
[Install on your own iPhone](#install-on-your-own-iphone)).

## What the iPhone app does

| Android feature | iPhone |
| --- | --- |
| Automatic PC discovery (UDP `windock:discover:v1` on port 41234) | Yes. Broadcast, plus a unicast probe of each address on the local subnet, so it works without Apple's multicast entitlement |
| Switch PC picker: current PC, up to 8 saved PCs checked live, PCs available now, forget | Yes. The connection screen, the **…** menu and the dock drawer's **Switch PC** button all open it |
| Forgotten PCs stop automatic reconnection (by address and host ID) | Yes |
| Native keyboard bridge for PC text fields (text, Backspace, Enter, Tab, arrows, Escape, Delete, **Sign**) | Yes. Typing strip above the iOS keyboard; hardware keyboards supported |
| Dock appearance saved per PC identity (`windock-layout`, `windock-performance`) | Yes |
| "This phone · screen & sleep": dim after, dim level, screen-off rest | Yes. The default keeps the screen on while the dock is open; it can follow iOS Auto-Lock instead |
| Low-RAM devices get the lighter dock (`?perf=1`) | Yes (2 GB iPhones) |
| Open PC release page from the dock's updates dialog | Yes, opens in Safari |
| Tailscale (100.64.0.0/10) addresses | Yes, by manual entry |
| Stream Deck buttons (shortcuts, websites, multi-actions, 5×3 grid) | Yes, from the dock's **Add → Stream Deck** tab, with a haptic tap. Needs the matching WinDock build on the PC |
| USB connection | Via **Personal Hotspot** over USB or Wi-Fi: the PC joins the iPhone's hotspot network and discovery finds it there. iPhones have no Android-style USB tethering mode |
| Android APK self-update check | Not applicable. iPhone builds are installed through Xcode or TestFlight |

The shared dock detects the native features through the same `window.WinDockAndroid`
contract the Android app uses (`public/remote-keyboard.js`, `appearance.js`, `app.js`,
`updates.js`). Calls that return a value use a synchronous `prompt()` channel answered by
the `WKUIDelegate`; the rest use a script message handler. Every call is checked against
the selected PC's origin in the main frame.

## Connect

1. Run WinDock on your PC and put the iPhone on the same trusted network.
2. Open WinDock on the iPhone and allow **Local Network** access when iOS asks.
3. The app reconnects to the last PC, or searches the network. If it finds several PCs,
   it shows the picker. Otherwise tap **Find my PC**, **Switch PC**, or type the address from the
   tray menu → **Show connection info** (for example `192.168.1.20:8620`).
4. Enter the PC's PIN. The pairing cookie is kept, so later launches reconnect directly.

If nothing is found, check the Wi-Fi network, the PC firewall (UDP 41234 and TCP 8620), and
**Settings → Privacy & Security → Local Network → WinDock**.

## Install on your own iPhone

You need a Mac with Xcode 16.4 or later. A free Apple ID works; personal-team builds
expire after 7 days and then need reinstalling from Xcode. A paid developer account adds
TestFlight and one-year profiles.

```sh
npm ci
cd ios
brew install xcodegen          # once
swift scripts/generate-icon.swift
xcodegen generate
open WinDock.xcodeproj
```

In Xcode, open the **WinDock** target → *Signing & Capabilities*, choose your team, and
change the bundle ID to something unique (for example `com.yourname.windock`). Connect
the iPhone, select it as the run destination and press **Run**. On first launch, trust
the developer profile in **Settings → General → VPN & Device Management**, and turn on
**Developer Mode** if iOS asks.

## Build on GitHub

Open [Build WinDock iOS](https://github.com/aliihsaad/WinDock/actions/workflows/build-ios.yml)
and select **Run workflow**. It uses a GitHub-hosted macOS runner, Xcode 16.4 and XcodeGen,
runs the unit and simulator tests against the real Node host with a fake PC provider, and
uploads:

- `WinDock-simulator.zip`: the app for **iOS Simulator on a Mac**.
- `WinDock-unsigned-archive.zip`: an **unsigned device archive** for a later signing step.
- Simulator screenshots, `.xcresult` test results, build logs and fixture events.

## Tests

- `CompanionLogicTests`: discovery reply parsing and sender rebinding, subnet sweep math,
  saved/forgotten PCs, per-PC appearance validation, idle stages, bridge event scripts.
- `EndpointPolicyTests`: address normalisation and origin checks.
- `DockIntegrationTests` (simulator, needs `node ios/scripts/smoke-host.mjs`): PIN pairing,
  cookie reuse, launch/focus, drawer, failure recovery, foreign-origin blocking, and the
  native bridge serving only the selected PC's page.

## Boundaries

- iOS 16+, landscape iPhone/iPad. Physical-device acceptance testing is still pending.
- Discovery sweeps up to 1,022 addresses per network (the /24 around the phone on larger
  networks) and skips VPN tunnels; enter Tailscale or remote-subnet addresses manually.
- Health checks reject redirects, bound the response to 4 KiB and time out. Navigation is
  limited to the selected origin, and WebKit content rules also restrict subresources.
  Local HTTP exceptions cover private, loopback and CGNAT addresses only. This is a
  companion for a trusted LAN, not internet remote access.
- Screen dimming uses the system brightness, which is restored whenever the dock stops
  being active or the app leaves the foreground.
- The bundle ID in `project.yml` is `dev.ali-saad.windock`. Do not commit certificates,
  profiles or Apple secrets.
