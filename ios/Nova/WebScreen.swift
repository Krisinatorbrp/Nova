import SwiftUI
import UIKit
import WebKit

/// Shows Nova's interface: from your PC, or (nova://app/) the copy inside the app with the iPhone's own AI.
struct WebScreen: View {
    let url: URL
    @ObservedObject var state: AppState
    @State private var failed: String?
    @State private var reloadToken = 0

    var body: some View {
        ZStack {
            NovaWebView(url: url, state: state, failed: $failed, reloadToken: reloadToken)
            if let message = failed, url.scheme == "nova" {
                VStack(spacing: 16) {
                    Image(systemName: "wifi.exclamationmark")
                        .font(.system(size: 44))
                        .foregroundColor(.purple)
                    Text("Can't reach your PC")
                        .font(.title2.bold())
                    Text(message)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    Button {
                        failed = nil
                        reloadToken += 1
                    } label: {
                        Text("Try again").font(.headline).frame(maxWidth: 260).padding(.vertical, 6)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.white)
                    .foregroundColor(.black)
                    Button("Connect to a different PC") {
                        Orientation.release()
                        state.serverURL = nil
                    }
                    .foregroundColor(.secondary)
                }
                .padding(32)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(novaBackground.ignoresSafeArea())
            }
        }
    }
}

struct NovaWebView: UIViewRepresentable {
    let url: URL
    let state: AppState
    @Binding var failed: String?
    let reloadToken: Int

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.websiteDataStore = .default()      // keeps you signed in between launches
        config.setURLSchemeHandler(BundleSchemeHandler(), forURLScheme: "nova")   // the built-in copy of the app
        let controller = WKUserContentController()
        controller.add(WeakMessageHandler(context.coordinator), name: "nova")
        config.userContentController = controller

        let web = WKWebView(frame: .zero, configuration: config)
        web.isOpaque = false
        web.backgroundColor = novaBackgroundUI
        web.scrollView.backgroundColor = novaBackgroundUI
        web.scrollView.contentInsetAdjustmentBehavior = .never   // the page handles the notch itself
        web.scrollView.bounces = false
        web.allowsBackForwardNavigationGestures = false
        web.allowsLinkPreview = false
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator
        if #available(iOS 16.4, *) { web.isInspectable = true }

        context.coordinator.webView = web
        context.coordinator.lastReload = reloadToken
        web.load(Self.request(url))
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        context.coordinator.parent = self
        if context.coordinator.lastReload != reloadToken {
            context.coordinator.lastReload = reloadToken
            web.load(Self.request(url))
        }
    }

    /// A PC that's off shouldn't keep you waiting a minute: give up after a few seconds.
    static func request(_ url: URL) -> URLRequest {
        var r = URLRequest(url: url)
        if url.scheme != "nova" { r.timeoutInterval = 6 }
        return r
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        var parent: NovaWebView
        weak var webView: WKWebView?
        var lastReload = 0
        private let speech = SpeechManager()
        private let brain = DeviceBrain()

        init(_ parent: NovaWebView) {
            self.parent = parent
            super.init()
            speech.onEvent = { [weak self] text, event in self?.sendSpeech(text, event) }
            brain.onEvent = { [weak self] event in self?.sendLLM(event) }
        }

        // MARK: messages from the page (window.webkit.messageHandlers.nova.postMessage)
        func userContentController(_ userContentController: WKUserContentController,
                                   didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
            switch type {
            case "haptic":
                let style = body["style"] as? String
                let feedback: UIImpactFeedbackGenerator.FeedbackStyle =
                    style == "heavy" ? .heavy : (style == "medium" ? .medium : .light)
                UIImpactFeedbackGenerator(style: feedback).impactOccurred()
            case "speech":
                if (body["action"] as? String) == "stop" {
                    speech.stop()
                } else {
                    speech.start(locale: body["lang"] as? String)
                }
            case "orientation":
                Orientation.toggle()
            case "immersive":
                let on = body["on"] as? Bool ?? false
                DispatchQueue.main.async { self.parent.state.immersive = on }
            case "changePC":
                DispatchQueue.main.async {
                    Orientation.release()
                    self.parent.state.immersive = false
                    self.parent.state.forgetPC()
                }
            case "llm":                                   // offline mode: the iPhone's own AI
                switch body["action"] as? String {
                case "ask":
                    brain.ask(body["text"] as? String ?? "", lang: body["lang"] as? String ?? "en",
                              name: body["name"] as? String ?? "Nova")
                case "stop":
                    brain.stop()
                case "reset":
                    brain.reset()
                default:
                    break
                }
            default:
                break
            }
        }

        private func sendLLM(_ event: [String: Any]) {
            guard let data = try? JSONSerialization.data(withJSONObject: event),
                  let json = String(data: data, encoding: .utf8) else { return }
            let js = "window.novaNative && window.novaNative.llm && window.novaNative.llm(\(json));"
            DispatchQueue.main.async { self.webView?.evaluateJavaScript(js, completionHandler: nil) }
        }

        private func sendSpeech(_ text: String, _ event: String) {
            guard let data = try? JSONSerialization.data(withJSONObject: [text, event]),
                  let args = String(data: data, encoding: .utf8) else { return }
            let js = "window.novaNative && window.novaNative.speech && window.novaNative.speech.apply(null, \(args));"
            DispatchQueue.main.async { self.webView?.evaluateJavaScript(js, completionHandler: nil) }
        }

        // MARK: navigation
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            // links to other websites (like ollama.com) open in Safari
            if let target = navigationAction.request.url,
               let host = target.host, host != parent.url.host, target.scheme != "nova",
               navigationAction.navigationType == .linkActivated {
                UIApplication.shared.open(target)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let target = navigationAction.request.url { UIApplication.shared.open(target) }
            return nil
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!,
                     withError error: Error) {
            showError(error)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            showError(error)
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.reload()
        }

        private func showError(_ error: Error) {
            let ns = error as NSError
            if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled { return }
            if parent.url.scheme != "nova" {
                // the PC isn't there: switch to the AI on the iPhone right away
                DispatchQueue.main.async { self.parent.state.pcUnreachable() }
                return
            }
            DispatchQueue.main.async {
                self.parent.failed = "Make sure Nova is running on your PC and this iPhone is on the same Wi-Fi (or Tailscale).\n\n\(ns.localizedDescription)"
            }
        }
    }
}

/// Serves the copy of Nova's interface that's built into the app (nova://app/...), used offline.
final class BundleSchemeHandler: NSObject, WKURLSchemeHandler {
    private static let types = ["html": "text/html", "js": "text/javascript", "css": "text/css", "json": "application/json",
                                "png": "image/png", "woff2": "font/woff2", "svg": "image/svg+xml", "txt": "text/plain"]

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url, let root = Bundle.main.url(forResource: "static", withExtension: nil) else {
            task.didFailWithError(URLError(.fileDoesNotExist)); return
        }
        var path = url.path
        if path.isEmpty || path == "/" { path = "/index.html" }
        if path.hasPrefix("/static/") { path = String(path.dropFirst("/static".count)) }
        let file = root.appendingPathComponent(String(path.dropFirst())).standardizedFileURL
        guard file.path.hasPrefix(root.standardizedFileURL.path), let data = try? Data(contentsOf: file) else {
            task.didFailWithError(URLError(.fileDoesNotExist)); return
        }
        let mime = Self.types[file.pathExtension.lowercased()] ?? "application/octet-stream"
        let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1",
                                       headerFields: ["Content-Type": mime, "Content-Length": "\(data.count)",
                                                      "Cache-Control": "no-cache"])!
        task.didReceive(response)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}
}

/// Avoids a retain cycle between WKUserContentController and the coordinator.
final class WeakMessageHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?

    init(_ target: WKScriptMessageHandler) {
        self.target = target
    }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        target?.userContentController(userContentController, didReceive: message)
    }
}
