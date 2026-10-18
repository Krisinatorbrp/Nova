import SwiftUI
import UIKit

final class AppDelegate: NSObject, UIApplicationDelegate {
    /// Which orientations are allowed right now. The Rotate button changes this.
    static var orientationLock: UIInterfaceOrientationMask = .allButUpsideDown

    func application(_ application: UIApplication,
                     supportedInterfaceOrientationsFor window: UIWindow?) -> UIInterfaceOrientationMask {
        AppDelegate.orientationLock
    }
}

@main
struct NovaApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            RootView()
                .preferredColorScheme(.dark)
        }
    }
}

let novaBackground = Color(red: 6 / 255, green: 7 / 255, blue: 11 / 255)
let novaBackgroundUI = UIColor(red: 6 / 255, green: 7 / 255, blue: 11 / 255, alpha: 1)

/// Remembers which PC to connect to, and switches between the PC and the iPhone's own AI:
/// whenever the PC can't be reached, Nova keeps working with the AI on the iPhone (offline mode),
/// and goes back to the PC by itself as soon as it's reachable again.
final class AppState: ObservableObject {
    @Published var serverURL: URL? {
        didSet { UserDefaults.standard.set(serverURL?.absoluteString, forKey: "serverURL") }
    }
    @Published var immersive = false
    /// true = the PC can't be reached right now: the AI on the iPhone answers
    @Published var offline = false
    /// "Use on this iPhone only" (no PC set up yet)
    @Published var deviceOnly = UserDefaults.standard.bool(forKey: "deviceOnly") {
        didSet { UserDefaults.standard.set(deviceOnly, forKey: "deviceOnly") }
    }
    private var pcName = UserDefaults.standard.string(forKey: "pcName") ?? "Nova"
    private var failures = 0
    private var wasOnline = false
    private var timer: Timer?
    private var checking = false

    init() {
        if let saved = UserDefaults.standard.string(forKey: "serverURL"), let url = URL(string: saved) {
            serverURL = url
        }
        timer = Timer.scheduledTimer(withTimeInterval: 8, repeats: true) { [weak self] _ in self?.check() }
        check()
    }

    /// The built-in interface with the assistant's name from the PC.
    var deviceURL: URL {
        var c = URLComponents(string: "nova://app/")!
        c.queryItems = [URLQueryItem(name: "name", value: pcName)]
        return c.url!
    }

    func forgetPC() {
        serverURL = nil
        offline = false
        deviceOnly = false
    }

    /// The PC page failed to load: go offline straight away.
    func pcUnreachable() {
        failures = 2
        if serverURL != nil { offline = true }
    }

    /// Is the PC there? Checked every few seconds (and when the app comes back to the front).
    func check() {
        guard let base = serverURL, !checking else { return }
        checking = true
        var request = URLRequest(url: base.appendingPathComponent("api/state"))
        request.timeoutInterval = 3
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            let name = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }?["name"] as? String
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.checking = false
                guard self.serverURL == base else { return }
                if ok {
                    if let name, !name.isEmpty {
                        self.pcName = name
                        UserDefaults.standard.set(name, forKey: "pcName")
                    }
                    self.failures = 0
                    self.wasOnline = true
                    if self.offline { self.offline = false }          // PC is back: use it again
                } else {
                    self.failures += 1
                    // at start one failed try is enough; while connected, two (a short Wi-Fi hiccup is fine)
                    if !self.offline && (self.failures >= 2 || !self.wasOnline) { self.offline = true }
                }
            }
        }.resume()
    }
}

struct RootView: View {
    @StateObject private var state = AppState()
    @Environment(\.scenePhase) private var phase

    var body: some View {
        ZStack {
            novaBackground.ignoresSafeArea()
            if let url = state.serverURL, !state.offline {
                WebScreen(url: url, state: state)
                    .id(url)
                    .ignoresSafeArea()
            } else if state.serverURL != nil || state.deviceOnly {
                WebScreen(url: state.deviceURL, state: state)       // offline: the AI on the iPhone
                    .id("device")
                    .ignoresSafeArea()
            } else {
                ConnectView(state: state)
            }
        }
        .statusBarHidden(state.immersive)
        .persistentSystemOverlays(state.immersive ? .hidden : .automatic)
        .onChange(of: phase) { p in
            if p == .active { state.check() }
        }
    }
}

/// Forces landscape (or back to portrait) when the Screen tab's Rotate button is tapped.
enum Orientation {
    static var forcedLandscape = false

    static func toggle() {
        DispatchQueue.main.async {
            guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene }).first else { return }
            let root = scene.windows.first?.rootViewController
            if Orientation.forcedLandscape || scene.interfaceOrientation.isLandscape {
                Orientation.forcedLandscape = false
                AppDelegate.orientationLock = .portrait
                root?.setNeedsUpdateOfSupportedInterfaceOrientations()
                scene.requestGeometryUpdate(.iOS(interfaceOrientations: .portrait)) { _ in }
                // let the phone rotate freely again once we're upright
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    AppDelegate.orientationLock = .allButUpsideDown
                    root?.setNeedsUpdateOfSupportedInterfaceOrientations()
                }
            } else {
                Orientation.forcedLandscape = true
                AppDelegate.orientationLock = .landscape
                root?.setNeedsUpdateOfSupportedInterfaceOrientations()
                scene.requestGeometryUpdate(.iOS(interfaceOrientations: .landscapeRight)) { _ in }
            }
        }
    }

    static func release() {
        guard Orientation.forcedLandscape else { return }
        toggle()
    }
}
