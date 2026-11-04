import Foundation

/// A bounded, cookie-free probe. Redirects never select a different host for the user.
/// On success it reports the PC's identity from `/health` (name, platform, stable host ID).
final class HealthProbe: NSObject, URLSessionDataDelegate {
    private var session: URLSession?
    private var completion: ((KnownHost?) -> Void)?
    private var endpoint: URL?
    private var hotspot = false
    private var body = Data()
    private var validResponse = false
    private let requestTimeout: TimeInterval
    private let resourceTimeout: TimeInterval
    private let waitsForConnectivity: Bool

    /// Defaults suit a user-chosen PC (time to answer the Local Network prompt).
    /// The PC picker uses short timeouts to check several PCs at once.
    init(requestTimeout: TimeInterval = 10, resourceTimeout: TimeInterval = 20, waitsForConnectivity: Bool = true) {
        self.requestTimeout = requestTimeout
        self.resourceTimeout = resourceTimeout
        self.waitsForConnectivity = waitsForConnectivity
    }

    func start(endpoint: URL, hotspot: Bool = false, completion: @escaping (KnownHost?) -> Void) {
        cancel()
        self.completion = completion
        self.endpoint = endpoint
        self.hotspot = hotspot
        body = Data()
        validResponse = false
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = requestTimeout
        config.timeoutIntervalForResource = resourceTimeout
        config.waitsForConnectivity = waitsForConnectivity
        config.httpShouldSetCookies = false
        config.urlCache = nil
        let session = URLSession(configuration: config, delegate: self, delegateQueue: .main)
        self.session = session
        session.dataTask(with: endpoint.appendingPathComponent("health")).resume()
    }

    func cancel() {
        completion = nil
        session?.invalidateAndCancel()
        session = nil
    }

    private func finish(_ host: KnownHost?) {
        let callback = completion
        cancel()
        callback?(host)
    }

    static func isWinDock(_ body: Data) -> Bool { health(body) != nil }

    private static func health(_ body: Data) -> [String: Any]? {
        guard body.count <= 4096,
              let object = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
              object["app"] as? String == "windock", object["ok"] as? Bool == true else { return nil }
        return object
    }

    static func host(from body: Data, endpoint: URL, hotspot: Bool = false) -> KnownHost? {
        guard let health = health(body) else { return nil }
        let platform = KnownHosts.platformName(health["platform"] as? String)
        let label = KnownHosts.cleanLabel(health["hostName"] as? String)
        return KnownHost(endpoint: endpoint.absoluteString, label: label.isEmpty ? platform : label, hotspot: hotspot,
                         lastSeen: Date(), platform: platform, hostId: health["hostId"] as? String ?? "")
    }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard session === self.session else { completionHandler(.cancel); return }
        validResponse = (response as? HTTPURLResponse)?.statusCode == 200 && response.expectedContentLength <= 4096
        completionHandler(validResponse ? .allow : .cancel)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard session === self.session else { return }
        guard body.count + data.count <= 4096 else { finish(nil); return }
        body.append(data)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard session === self.session else { return }
        guard error == nil, validResponse, let endpoint else { finish(nil); return }
        finish(Self.host(from: body, endpoint: endpoint, hotspot: hotspot))
    }
}
