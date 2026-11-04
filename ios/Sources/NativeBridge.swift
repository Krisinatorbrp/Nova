import Foundation
import WebKit

/// What the shared dock page may ask of the phone app.
protocol NativeBridgeDelegate: AnyObject {
    /// True only for the selected PC's page in the main frame, while it is on screen.
    func bridge(_ bridge: NativeBridge, trusts frame: WKFrameInfo) -> Bool
    func bridgeAppearance(origin: String, legacy: String) -> String?
    func bridgeSaveAppearance(origin: String, scope: String, key: String, value: String) -> Bool
    func bridgeShowKeyboard(target: String, password: Bool)
    func bridgeHideKeyboard()
    func bridgeShowPCPicker()
    func bridgeShowPhoneSettings()
    func bridgeOpenPCRelease(version: String)
}

/// The shared dock (`public/*.js` on the PC) feature-detects `window.WinDockAndroid`.
/// The iPhone app provides the same object so the existing page enables native keyboard,
/// per-PC appearance, Switch PC and phone display settings without any PC changes.
///
/// WKWebView has no synchronous JavaScript bridge, but the dock reads appearance
/// synchronously before first paint. Calls that return a value are carried through
/// `window.prompt`, whose WKUIDelegate callback blocks the page until answered;
/// fire-and-forget calls use a script message handler.
final class NativeBridge: NSObject, WKScriptMessageHandler {
    static let handlerName = "windockNative"
    static let promptMarker = "windock-native:v1"
    private static let maxPayload = 16_384
    weak var delegate: NativeBridgeDelegate?

    static let script = """
    (() => {
      "use strict";
      if (window.WinDockAndroid) return;
      const marker = \(jsonString(promptMarker));
      const ask = window.prompt.bind(window);
      const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers[\(jsonString(handlerName))];
      const call = (method, args) => { try { return ask(marker, JSON.stringify({ method, args })); } catch (_) { return null; } };
      const post = (method, args) => { try { handler.postMessage({ method, args }); } catch (_) {} };
      const api = Object.freeze({
        getAppearance: (origin, legacy) => call("getAppearance", [String(origin), String(legacy)]),
        saveAppearance: (origin, scope, key, value) => call("saveAppearance", [String(origin), String(scope), String(key), String(value)]) === "true",
        showKeyboard: (target, password) => post("showKeyboard", [String(target), Boolean(password)]),
        hideKeyboard: () => post("hideKeyboard", []),
        showPcPicker: () => post("showPcPicker", []),
        showPhoneSettings: () => post("showPhoneSettings", []),
        openPcRelease: (version) => post("openPcRelease", [String(version)]),
      });
      Object.defineProperty(window, "WinDockAndroid", { value: api, enumerable: false, configurable: false, writable: false });
      Object.defineProperty(window, "WinDockIOS", { value: true, enumerable: false, configurable: false, writable: false });
    })();
    """

    private static func jsonString(_ value: String) -> String {
        let data = try! JSONSerialization.data(withJSONObject: [value])
        return String(String(data: data, encoding: .utf8)!.dropFirst().dropLast())
    }

    func install(into controller: WKUserContentController) {
        controller.addUserScript(WKUserScript(source: Self.script, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        controller.add(self, name: Self.handlerName)
    }

    func uninstall(from controller: WKUserContentController) {
        controller.removeScriptMessageHandler(forName: Self.handlerName)
        controller.removeAllUserScripts()
    }

    private struct Call {
        let method: String
        let args: [Any]
        func string(_ index: Int) -> String? { index < args.count ? args[index] as? String : nil }
        func bool(_ index: Int) -> Bool { index < args.count ? (args[index] as? Bool ?? false) : false }
    }

    private func decode(_ body: Any?) -> Call? {
        guard let object = body as? [String: Any], let method = object["method"] as? String,
              let args = object["args"] as? [Any], args.count <= 4 else { return nil }
        return Call(method: method, args: args)
    }

    /// Returns nil when the prompt is not a bridge call (then show a normal prompt),
    /// otherwise the string handed back to JavaScript (`.some(nil)` means `null`).
    func answer(prompt: String, defaultText: String?, frame: WKFrameInfo) -> String?? {
        guard prompt == Self.promptMarker else { return nil }
        guard let text = defaultText, text.utf8.count <= Self.maxPayload,
              let call = decode(try? JSONSerialization.jsonObject(with: Data(text.utf8))),
              let delegate, delegate.bridge(self, trusts: frame) else { return .some(nil) }
        switch call.method {
        case "getAppearance":
            guard let origin = call.string(0), let legacy = call.string(1) else { return .some(nil) }
            return .some(delegate.bridgeAppearance(origin: origin, legacy: legacy))
        case "saveAppearance":
            guard let origin = call.string(0), let scope = call.string(1), let key = call.string(2), let value = call.string(3)
            else { return .some("false") }
            return .some(delegate.bridgeSaveAppearance(origin: origin, scope: scope, key: key, value: value) ? "true" : "false")
        default:
            return .some(nil)
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == Self.handlerName, let delegate, delegate.bridge(self, trusts: message.frameInfo),
              let call = decode(message.body) else { return }
        switch call.method {
        case "showKeyboard":
            // The dock's text-target IDs are positive decimal integers (Android checks the same).
            guard let target = call.string(0), target.range(of: "^[1-9][0-9]{0,15}$", options: .regularExpression) != nil else { return }
            delegate.bridgeShowKeyboard(target: target, password: call.bool(1))
        case "hideKeyboard": delegate.bridgeHideKeyboard()
        case "showPcPicker": delegate.bridgeShowPCPicker()
        case "showPhoneSettings": delegate.bridgeShowPhoneSettings()
        case "openPcRelease":
            if let version = call.string(0) { delegate.bridgeOpenPCRelease(version: version) }
        default: break
        }
    }

    /// Script that delivers a native keyboard event to the page.
    static func dispatch(_ event: String, detail: [String: Any]) -> String? {
        guard ["windock-keyboard-input", "windock-keyboard-action"].contains(event),
              let data = try? JSONSerialization.data(withJSONObject: detail),
              let json = String(data: data, encoding: .utf8) else { return nil }
        return "window.dispatchEvent(new CustomEvent(\(jsonString(event)),{detail:\(json)}))"
    }

    /// GitHub release page for a well-formed version, like Android's `UpdatePolicy`.
    static func releasePage(_ version: String) -> URL? {
        guard version.count <= 100,
              version.range(of: "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?$",
                            options: .regularExpression) != nil else { return nil }
        return URL(string: "https://github.com/aliihsaad/WinDock/releases/tag/v" + version)
    }
}
