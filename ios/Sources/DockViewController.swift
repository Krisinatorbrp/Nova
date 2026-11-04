import UIKit
import WebKit

final class DockViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, UITextFieldDelegate, NativeBridgeDelegate {
    static let rememberedPCKey = KnownHosts.rememberedKey
    private let defaults: UserDefaults
    private let autoConnect: Bool
    private let store: KnownHosts
    private let appearance: AppearanceStore
    private let probe = HealthProbe()
    private let quickProbe = HealthProbe(requestTimeout: 4, resourceTimeout: 6, waitsForConnectivity: false)
    private var candidateProbes: [HealthProbe] = []
    private let discovery = LANDiscovery()
    private let bridge = NativeBridge()
    private let keyboard = RemoteKeyboardBar()
    private let restCover = UIView()
    private lazy var idle = IdleDisplayController(policy: PhoneSettings.display(defaults), cover: restCover)
    private let lowMemory = EndpointPolicy.isLowMemory()

    private let connection = UIScrollView()
    let address = UITextField()
    let status = UILabel()
    let connectButton = UIButton(type: .system)
    private let findButton = UIButton(type: .system)
    private let savedButton = UIButton(type: .system)
    private let phoneButton = UIButton(type: .system)
    private let pcButton = UIButton(type: .system)
    private let spinner = UIActivityIndicatorView(style: .medium)
    private(set) var webView: WKWebView?
    private(set) var endpoint: URL?
    private var pendingHost: KnownHost?
    private var keyboardTarget: String?
    private var dockVisible = false
    private var appActive = true
    private var attempt = UUID()
    private var loadTimeout: DispatchWorkItem?
    private var started = false
    private let mint = UIColor(red: 0.51, green: 0.91, blue: 0.75, alpha: 1)
    private let background = UIColor(red: 0.035, green: 0.055, blue: 0.063, alpha: 1)

    init(defaults: UserDefaults = .standard, autoConnect: Bool = true) {
        self.defaults = defaults
        self.autoConnect = autoConnect
        store = KnownHosts(defaults: defaults)
        appearance = AppearanceStore(defaults: defaults)
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("Use init(defaults:autoConnect:)") }
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscape }
    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { webView != nil }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = background
        view.tintColor = mint
        buildConnectionScreen()
        buildPCMenu()
        buildKeyboard()
        buildRestCover()
        idle.onRest = { [weak self] in self?.hideKeyboard() }
        address.text = defaults.string(forKey: Self.rememberedPCKey)
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(appWillResign), name: UIApplication.willResignActiveNotification, object: nil)
        center.addObserver(self, selector: #selector(appDidBecomeActive), name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        (view.window as? ActivityWindow)?.onActivity = { [weak self] in self?.idle.userActivity() ?? false }
        if !started {
            started = true
            if autoConnect { findPC() }
        }
    }

    @objc private func appWillResign() { appActive = false; syncIdle() }
    @objc private func appDidBecomeActive() { appActive = true; syncIdle() }

    // MARK: - Connection screen

    private func label(_ text: String, size: CGFloat, weight: UIFont.Weight = .regular) -> UILabel {
        let label = UILabel()
        label.text = text
        label.textColor = .white
        label.font = .systemFont(ofSize: size, weight: weight)
        label.numberOfLines = 0
        label.adjustsFontForContentSizeCategory = true
        return label
    }

    private func secondaryButton(_ button: UIButton, title: String, image: String, action: @escaping () -> Void) {
        var config = UIButton.Configuration.gray()
        config.title = title
        config.image = UIImage(systemName: image)
        config.imagePadding = 6
        config.buttonSize = .small
        config.baseForegroundColor = .white
        config.cornerStyle = .medium
        button.configuration = config
        button.addAction(UIAction { _ in action() }, for: .touchUpInside)
    }

    private func buildConnectionScreen() {
        connection.translatesAutoresizingMaskIntoConstraints = false
        connection.keyboardDismissMode = .interactive
        view.addSubview(connection)
        let safe = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            connection.topAnchor.constraint(equalTo: safe.topAnchor),
            connection.leadingAnchor.constraint(equalTo: safe.leadingAnchor),
            connection.trailingAnchor.constraint(equalTo: safe.trailingAnchor),
            connection.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor)
        ])
        let brand = label("WinDock", size: 17, weight: .semibold)
        let mark = BrandMark()
        NSLayoutConstraint.activate([mark.widthAnchor.constraint(equalToConstant: 38), mark.heightAnchor.constraint(equalToConstant: 38)])
        let brandRow = UIStackView(arrangedSubviews: [mark, brand])
        brandRow.spacing = 12
        brandRow.alignment = .center
        let title = label("Your PC.\nWithin reach.", size: 34, weight: .bold)
        let intro = label("A little space for your PC apps.\nKeep both devices on the same Wi-Fi.", size: 14)
        intro.textColor = .secondaryLabel
        let left = UIStackView(arrangedSubviews: [brandRow, title, intro])
        left.axis = .vertical
        left.spacing = 18
        left.alignment = .leading

        let heading = label("Connect to your PC", size: 21, weight: .semibold)
        let hint = label("WinDock looks for your PC automatically. Or enter the address from the tray menu → Show connection info.", size: 13)
        hint.textColor = .secondaryLabel
        address.accessibilityIdentifier = "pc-address"
        address.accessibilityLabel = "PC address"
        address.placeholder = "192.168.1.20:8620"
        address.keyboardType = .URL
        address.autocapitalizationType = .none
        address.autocorrectionType = .no
        address.spellCheckingType = .no
        address.smartQuotesType = .no
        address.smartDashesType = .no
        address.returnKeyType = .go
        address.clearButtonMode = .whileEditing
        address.font = .monospacedSystemFont(ofSize: 16, weight: .regular)
        address.backgroundColor = UIColor.white.withAlphaComponent(0.065)
        address.layer.cornerRadius = 12
        address.leftView = UIView(frame: CGRect(x: 0, y: 0, width: 14, height: 1))
        address.leftViewMode = .always
        address.heightAnchor.constraint(equalToConstant: 48).isActive = true
        address.delegate = self
        var config = UIButton.Configuration.filled()
        config.title = "Connect"
        config.image = UIImage(systemName: "arrow.right")
        config.imagePlacement = .trailing
        config.imagePadding = 10
        config.baseBackgroundColor = mint
        config.baseForegroundColor = UIColor(red: 0.04, green: 0.11, blue: 0.10, alpha: 1)
        config.cornerStyle = .medium
        connectButton.configuration = config
        connectButton.heightAnchor.constraint(equalToConstant: 46).isActive = true
        connectButton.accessibilityIdentifier = "connect"
        connectButton.addTarget(self, action: #selector(connect), for: .touchUpInside)

        secondaryButton(findButton, title: "Find my PC", image: "magnifyingglass") { [weak self] in self?.findPC() }
        findButton.accessibilityIdentifier = "find-pc"
        secondaryButton(savedButton, title: "Switch PC", image: "desktopcomputer") { [weak self] in self?.showPCPicker() }
        savedButton.accessibilityIdentifier = "switch-pc"
        secondaryButton(phoneButton, title: "This phone", image: "iphone") { [weak self] in self?.showPhoneOptions() }
        phoneButton.accessibilityIdentifier = "phone-options"
        let tools = UIStackView(arrangedSubviews: [findButton, savedButton, phoneButton])
        tools.spacing = 8
        tools.distribution = .fillEqually

        status.font = .systemFont(ofSize: 12)
        status.textColor = .secondaryLabel
        status.numberOfLines = 0
        status.text = "Your PC will ask you to pair with a PIN."
        status.accessibilityIdentifier = "connection-status"
        let statusRow = UIStackView(arrangedSubviews: [spinner, status])
        statusRow.spacing = 8
        statusRow.alignment = .top
        spinner.hidesWhenStopped = true
        let right = UIStackView(arrangedSubviews: [heading, hint, address, connectButton, tools, statusRow])
        right.axis = .vertical
        right.spacing = 12
        let columns = UIStackView(arrangedSubviews: [left, right])
        columns.distribution = .fillEqually
        columns.alignment = .center
        columns.spacing = 36
        columns.translatesAutoresizingMaskIntoConstraints = false
        connection.addSubview(columns)
        NSLayoutConstraint.activate([
            columns.leadingAnchor.constraint(equalTo: connection.contentLayoutGuide.leadingAnchor, constant: 28),
            columns.trailingAnchor.constraint(equalTo: connection.contentLayoutGuide.trailingAnchor, constant: -28),
            columns.topAnchor.constraint(equalTo: connection.contentLayoutGuide.topAnchor, constant: 24),
            columns.bottomAnchor.constraint(equalTo: connection.contentLayoutGuide.bottomAnchor, constant: -24),
            columns.widthAnchor.constraint(equalTo: connection.frameLayoutGuide.widthAnchor, constant: -56)
        ])
        let height = columns.heightAnchor.constraint(greaterThanOrEqualTo: connection.frameLayoutGuide.heightAnchor, constant: -48)
        height.priority = .defaultLow
        height.isActive = true
    }

    private func buildPCMenu() {
        var config = UIButton.Configuration.gray()
        config.image = UIImage(systemName: "ellipsis")
        config.baseForegroundColor = .white
        config.background.backgroundColor = UIColor.black.withAlphaComponent(0.5)
        config.cornerStyle = .capsule
        pcButton.configuration = config
        pcButton.accessibilityLabel = "PC connection options"
        pcButton.accessibilityIdentifier = "pc-options"
        pcButton.showsMenuAsPrimaryAction = true
        pcButton.menu = UIMenu(children: [
            UIAction(title: "Reconnect", image: UIImage(systemName: "arrow.clockwise")) { [weak self] _ in self?.connect() },
            UIAction(title: "Switch PC", image: UIImage(systemName: "desktopcomputer")) { [weak self] _ in self?.showPCPicker() },
            UIAction(title: "This phone", image: UIImage(systemName: "iphone")) { [weak self] _ in self?.showPhoneOptions() }
        ])
        pcButton.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(pcButton)
        NSLayoutConstraint.activate([
            pcButton.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 8),
            pcButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            pcButton.widthAnchor.constraint(equalToConstant: 44), pcButton.heightAnchor.constraint(equalToConstant: 44)
        ])
        pcButton.isHidden = true
    }

    private func buildKeyboard() {
        keyboard.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(keyboard)
        NSLayoutConstraint.activate([
            keyboard.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            keyboard.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            keyboard.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor),
            keyboard.heightAnchor.constraint(equalToConstant: 56)
        ])
        keyboard.onText = { [weak self] text in self?.emitKeyboardInput(["type": "text", "text": text]) }
        keyboard.onKey = { [weak self] key in self?.emitKeyboardInput(["type": "key", "key": key]) }
        keyboard.onActivity = { [weak self] in _ = self?.idle.userActivity() }
        keyboard.onClose = { [weak self] in self?.hideKeyboard(); self?.emitKeyboardAction("closed") }
        keyboard.onSignature = { [weak self] in self?.hideKeyboard(); self?.emitKeyboardAction("signature") }
    }

    private func buildRestCover() {
        restCover.backgroundColor = .black
        restCover.isAccessibilityElement = true
        restCover.accessibilityLabel = "Screen resting. Tap to return to the dock."
        restCover.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(restCover)
        NSLayoutConstraint.activate([
            restCover.leadingAnchor.constraint(equalTo: view.leadingAnchor), restCover.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            restCover.topAnchor.constraint(equalTo: view.topAnchor), restCover.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        restCover.isHidden = true
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool { connect(); return true }

    private func setBusy(_ busy: Bool, _ message: String? = nil) {
        connectButton.isEnabled = !busy
        address.isEnabled = !busy
        findButton.isEnabled = !busy
        savedButton.isEnabled = !busy
        if busy { spinner.startAnimating() } else { spinner.stopAnimating() }
        if let message { status.text = message }
    }

    // MARK: - Connecting

    /// Connect to the typed address only.
    @objc func connect() {
        showConnection()
        view.endEditing(true)
        guard let endpoint = EndpointPolicy.normalize(address.text) else {
            status.text = "Enter a local PC address, for example 192.168.1.20:8620."
            return
        }
        openPC(endpoint, hotspot: false)
    }

    /// A user-chosen PC: forget lists do not apply, and a success saves it again.
    private func openPC(_ endpoint: URL, hotspot: Bool) {
        showConnection()
        address.text = endpoint.absoluteString
        let id = attempt
        setBusy(true, "Looking for WinDock… Allow Local Network access if asked.")
        probe.start(endpoint: endpoint, hotspot: hotspot) { [weak self] host in
            guard let self, self.attempt == id else { return }
            guard let host else {
                self.showConnection(message: "Couldn’t reach WinDock. Check the tray address, Wi-Fi, Windows firewall and Settings → Privacy & Security → Local Network, then retry.")
                return
            }
            self.loadDock(endpoint, host: host, attempt: id)
        }
    }

    /// Automatic: the last PC if it still answers, otherwise search the network.
    func findPC() {
        showConnection()
        view.endEditing(true)
        let id = attempt
        setBusy(true, "Looking for your PC on Wi-Fi…")
        guard let remembered = store.remembered else { discover(id); return }
        quickProbe.start(endpoint: remembered) { [weak self] host in
            guard let self, self.attempt == id else { return }
            if let host, self.store.canAutoConnect(host) { self.loadDock(remembered, host: host, attempt: id) }
            else { self.discover(id) }
        }
    }

    private func discover(_ id: UUID) {
        status.text = "Looking for your PC on Wi-Fi… Allow Local Network access if asked."
        discovery.scan { [weak self] candidates in
            guard let self, self.attempt == id else { return }
            self.check(candidates, attempt: id)
        }
    }

    private func check(_ candidates: [DiscoveryCandidate], attempt id: UUID) {
        guard !candidates.isEmpty else { notFound(); return }
        var pending = candidates.count
        var answered: [KnownHost] = []
        for candidate in candidates {
            let probe = HealthProbe(requestTimeout: 3, resourceTimeout: 5, waitsForConnectivity: false)
            candidateProbes.append(probe)
            probe.start(endpoint: candidate.endpoint, hotspot: candidate.hotspot) { [weak self] host in
                guard let self, self.attempt == id else { return }
                if let host, self.store.canAutoConnect(host) { answered.append(host) }
                pending -= 1
                if pending == 0 { self.choose(answered, attempt: id) }
            }
        }
    }

    /// Prefer the most recently used saved PC; with several unknown PCs, let the user pick.
    private func choose(_ hosts: [KnownHost], attempt id: UUID) {
        candidateProbes.removeAll()
        let saved = store.hosts
        let ranked = hosts.compactMap { host -> (Int, KnownHost)? in
            guard let rank = saved.firstIndex(where: { $0.identity == host.identity || $0.endpoint == host.endpoint }) else { return nil }
            return (rank, host)
        }.sorted { $0.0 < $1.0 }
        if let best = ranked.first?.1 ?? (hosts.count == 1 ? hosts.first : nil), let url = best.url {
            loadDock(url, host: best, attempt: id)
        } else if hosts.isEmpty {
            notFound()
        } else {
            showConnection(message: "Found \(hosts.count) PCs running WinDock. Choose one to connect.")
            showPCPicker()
        }
    }

    private func notFound() {
        showConnection(message: "Couldn’t find WinDock on this network. Keep WinDock running on your PC with both devices on the same Wi-Fi, "
            + "then tap Find my PC — or enter the address from the tray menu → Show connection info. "
            + "If this keeps happening, check Settings → Privacy & Security → Local Network → WinDock.")
    }

    private func loadDock(_ endpoint: URL, host: KnownHost, attempt id: UUID) {
        guard let rules = try? EndpointPolicy.contentRules(for: endpoint) else {
            showConnection(message: "Couldn’t prepare the dock. Please try again."); return
        }
        address.text = endpoint.absoluteString
        status.text = "Opening your dock…"
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "windock-pc", encodedContentRuleList: rules) { [weak self] rules, error in
            guard let self, self.attempt == id else { return }
            guard let rules, error == nil else {
                self.showConnection(message: "Couldn’t prepare the dock. Please try again."); return
            }
            self.endpoint = endpoint
            self.pendingHost = host
            // Appearance is read synchronously while the page starts, so pick the PC first.
            self.appearance.select(endpoint: endpoint, hostId: host.hostId)
            let config = WKWebViewConfiguration()
            config.websiteDataStore = .default() // HttpOnly pairing cookie survives switching/reopening the app.
            config.userContentController.add(rules)
            self.bridge.delegate = self
            self.bridge.install(into: config.userContentController)
            let web = WKWebView(frame: .zero, configuration: config)
            web.navigationDelegate = self
            web.uiDelegate = self
            web.isOpaque = false
            web.backgroundColor = self.background
            web.scrollView.backgroundColor = self.background
            web.scrollView.contentInsetAdjustmentBehavior = .never
            web.scrollView.bounces = false
            web.allowsBackForwardNavigationGestures = false
            web.translatesAutoresizingMaskIntoConstraints = false
            self.view.insertSubview(web, belowSubview: self.connection)
            NSLayoutConstraint.activate([
                web.leadingAnchor.constraint(equalTo: self.view.leadingAnchor), web.trailingAnchor.constraint(equalTo: self.view.trailingAnchor),
                web.topAnchor.constraint(equalTo: self.view.topAnchor), web.bottomAnchor.constraint(equalTo: self.view.bottomAnchor)
            ])
            self.webView = web
            let timeout = DispatchWorkItem { [weak self] in
                guard let self, self.attempt == id else { return }
                self.showConnection(message: "The dock took too long to load. Check that WinDock is still running, then retry.")
            }
            self.loadTimeout = timeout
            DispatchQueue.main.asyncAfter(deadline: .now() + 20, execute: timeout)
            web.load(URLRequest(url: EndpointPolicy.pageURL(for: endpoint, lowMemory: self.lowMemory)))
        }
    }

    func showConnection(message: String = "Enter your PC address to connect.") {
        attempt = UUID()
        probe.cancel()
        quickProbe.cancel()
        candidateProbes.forEach { $0.cancel() }
        candidateProbes.removeAll()
        discovery.cancel()
        loadTimeout?.cancel()
        loadTimeout = nil
        hideKeyboard()
        keyboardTarget = nil
        if let webView {
            webView.stopLoading()
            webView.navigationDelegate = nil
            webView.uiDelegate = nil
            bridge.uninstall(from: webView.configuration.userContentController)
            webView.removeFromSuperview()
        }
        webView = nil // Close sockets and release any remote gestures with the old page.
        endpoint = nil
        pendingHost = nil
        appearance.select(endpoint: nil, hostId: nil)
        dockVisible = false
        pcButton.isHidden = true
        connection.isHidden = false
        setBusy(false, message)
        syncIdle()
        setNeedsUpdateOfHomeIndicatorAutoHidden()
    }

    // MARK: - Sheets

    private func presentSheet(_ sheet: UIViewController) {
        guard presentedViewController == nil else { return }
        hideKeyboard()
        let navigation = SheetNavigationController(rootViewController: sheet)
        navigation.modalPresentationStyle = .formSheet
        navigation.overrideUserInterfaceStyle = .dark
        navigation.onDismiss = { [weak self] in self?.syncIdle() }
        present(navigation, animated: true)
        syncIdle()
    }

    func showPCPicker() {
        let picker = PCPickerViewController(store: store, current: dockVisible ? endpoint : nil)
        picker.onSelect = { [weak self] host, url in self?.openPC(url, hotspot: host.hotspot) }
        picker.onManual = { [weak self] in
            guard let self else { return }
            self.showConnection(message: "Connect to your PC, or search for another one.")
            self.address.becomeFirstResponder()
        }
        presentSheet(picker)
    }

    func showPhoneOptions() {
        let options = PhoneOptionsViewController(defaults: defaults)
        options.onChange = { [weak self] policy in self?.idle.reload(policy) }
        presentSheet(options)
    }

    // MARK: - Idle display and keyboard

    private func syncIdle() {
        idle.setActive(dockVisible && appActive && presentedViewController == nil)
    }

    /// The selected PC's page is on screen (Android `trustedKeyboardPage`).
    private var trustedPage: Bool {
        guard dockVisible, appActive, let endpoint, let webView else { return false }
        return EndpointPolicy.allows(webView.url, endpoint: endpoint)
    }

    private func hideKeyboard() {
        if keyboard.isActive { keyboard.hide() }
    }

    private func emitKeyboardInput(_ message: [String: Any]) {
        guard let target = keyboardTarget, trustedPage else { return }
        idle.userActivity()
        var detail = message
        detail["target"] = target
        if let script = NativeBridge.dispatch("windock-keyboard-input", detail: detail) { webView?.evaluateJavaScript(script) }
    }

    private func emitKeyboardAction(_ action: String) {
        guard trustedPage, let script = NativeBridge.dispatch("windock-keyboard-action", detail: ["action": action]) else { return }
        webView?.evaluateJavaScript(script)
    }

    // MARK: - NativeBridgeDelegate

    func bridge(_ bridge: NativeBridge, trusts frame: WKFrameInfo) -> Bool {
        guard let webView, let endpoint, frame.isMainFrame, frame.webView === webView else { return false }
        let origin = frame.securityOrigin
        var text = "\(origin.`protocol`)://\(origin.host)"
        if origin.port != 0 { text += ":\(origin.port)" }
        return EndpointPolicy.allows(origin: text, endpoint: endpoint)
    }

    func bridgeAppearance(origin: String, legacy: String) -> String? {
        appearance.snapshot(origin: origin, legacy: legacy)
    }

    func bridgeSaveAppearance(origin: String, scope: String, key: String, value: String) -> Bool {
        appearance.save(origin: origin, scope: scope, key: key, value: value)
    }

    func bridgeShowKeyboard(target: String, password: Bool) {
        guard trustedPage, presentedViewController == nil, idle.stage != .resting else { return }
        keyboardTarget = target
        keyboard.show(password: password)
    }

    func bridgeHideKeyboard() { hideKeyboard() }

    func bridgeShowPCPicker() { if trustedPage { showPCPicker() } }

    func bridgeShowPhoneSettings() { if trustedPage { showPhoneOptions() } }

    func bridgeOpenPCRelease(version: String) {
        guard trustedPage, let url = NativeBridge.releasePage(version) else { return }
        UIApplication.shared.open(url)
    }

    // MARK: - WKUIDelegate

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        guard webView === self.webView, let answer = bridge.answer(prompt: prompt, defaultText: defaultText, frame: frame) else {
            completionHandler(nil); return
        }
        completionHandler(answer)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? { nil }

    // MARK: - WKNavigationDelegate

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let endpoint, navigationAction.targetFrame != nil,
              EndpointPolicy.allows(navigationAction.request.url, endpoint: endpoint) else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard let endpoint, EndpointPolicy.allows(navigationResponse.response.url, endpoint: endpoint) else {
            decisionHandler(.cancel); return
        }
        if navigationResponse.isForMainFrame,
           let response = navigationResponse.response as? HTTPURLResponse, !(200...299).contains(response.statusCode) {
            decisionHandler(.cancel)
            showConnection(message: "WinDock couldn’t open the dock. Check the PC and retry.")
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        guard webView === self.webView else { return }
        hideKeyboard()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard webView === self.webView, let endpoint else { return }
        loadTimeout?.cancel()
        loadTimeout = nil
        store.connected(endpoint, host: pendingHost)
        address.text = endpoint.absoluteString
        connection.isHidden = true
        pcButton.isHidden = false
        spinner.stopAnimating()
        dockVisible = true
        syncIdle()
        setNeedsUpdateOfHomeIndicatorAutoHidden()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { failed(webView, error) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { failed(webView, error) }
    private func failed(_ web: WKWebView, _ error: Error) {
        guard web === webView, (error as NSError).code != NSURLErrorCancelled else { return }
        showConnection(message: "Connection interrupted. Check your PC and Wi-Fi, then reconnect.")
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard webView === self.webView else { return }
        showConnection(message: "The dock was paused by iOS. Tap Connect to reopen it.")
    }
    deinit {
        probe.cancel(); quickProbe.cancel(); discovery.cancel(); loadTimeout?.cancel()
        NotificationCenter.default.removeObserver(self)
    }
}

/// Lets the dock resume idle dimming however a sheet is closed.
final class SheetNavigationController: UINavigationController {
    var onDismiss: (() -> Void)?
    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed { onDismiss?() }
    }
}

private final class BrandMark: UIView {
    override func draw(_ rect: CGRect) {
        let colors: [UIColor] = [
            UIColor(red: 0.51, green: 0.91, blue: 0.75, alpha: 1),
            UIColor(red: 0.78, green: 0.98, blue: 0.91, alpha: 1),
            UIColor(red: 0.50, green: 0.73, blue: 1, alpha: 1),
            UIColor(red: 0.41, green: 0.85, blue: 0.80, alpha: 1)
        ]
        for i in 0..<4 {
            colors[i].setFill()
            let size = bounds.width * 0.42
            UIBezierPath(roundedRect: CGRect(x: CGFloat(i % 2) * bounds.width * 0.58,
                                            y: CGFloat(i / 2) * bounds.height * 0.58,
                                            width: size, height: size), cornerRadius: 4).fill()
        }
    }
}
