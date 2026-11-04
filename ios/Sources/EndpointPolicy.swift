import Foundation

/// Only a literal private IPv4 address (or loopback for development), never an arbitrary website.
/// Mirrors the Android `EndpointPolicy`: RFC 1918, loopback and the Tailscale CGNAT range.
enum EndpointPolicy {
    static let defaultPort = 8620

    static func normalize(_ input: String?) -> URL? {
        guard let input = input?.trimmingCharacters(in: .whitespacesAndNewlines),
              !input.isEmpty, input.count <= 200,
              !input.contains("\\"), !input.contains("%"),
              !input.unicodeScalars.contains(where: { CharacterSet.whitespacesAndNewlines.union(.controlCharacters).contains($0) })
        else { return nil }
        let explicitScheme = input.contains("://")
        guard var parts = URLComponents(string: explicitScheme ? input : "http://" + input),
              let scheme = parts.scheme?.lowercased(), ["http", "https"].contains(scheme),
              let host = parts.host?.lowercased(), isPrivateHost(host),
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.isEmpty || parts.path == "/",
              parts.port == nil || (1...65535).contains(parts.port!)
        else { return nil }
        // Reject an empty port instead of URLComponents silently removing it.
        let authority = (explicitScheme ? String(input.split(separator: "/", omittingEmptySubsequences: false)[2]) : input)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !authority.hasSuffix(":") else { return nil }
        parts.scheme = scheme
        parts.host = host
        parts.path = ""
        if !explicitScheme && parts.port == nil { parts.port = defaultPort }
        return parts.url
    }

    static func isPrivateHost(_ host: String) -> Bool {
        if host == "localhost" { return true }
        guard let values = octets(host) else { return false }
        return values[0] == 10 || values[0] == 127 ||
            (values[0] == 192 && values[1] == 168) ||
            (values[0] == 172 && (16...31).contains(values[1])) ||
            (values[0] == 100 && (64...127).contains(values[1])) // Tailscale / CGNAT
    }

    /// Strict dotted-quad parsing: no leading zeros, hex, or shortened forms.
    static func octets(_ host: String) -> [Int]? {
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { return nil }
        var values: [Int] = []
        for octet in parts {
            guard !octet.isEmpty, octet.count <= 3, octet.allSatisfy({ $0 >= "0" && $0 <= "9" }),
                  let value = Int(octet), (0...255).contains(value), String(value) == octet else { return nil }
            values.append(value)
        }
        return values
    }

    static func allows(_ url: URL?, endpoint: URL) -> Bool {
        guard let url, url.user == nil, url.password == nil else { return false }
        return url.scheme?.lowercased() == endpoint.scheme &&
            url.host?.lowercased() == endpoint.host && effectivePort(url) == effectivePort(endpoint)
    }

    /// `origin` as reported by `location.origin` or `WKSecurityOrigin`.
    static func allows(origin: String?, endpoint: URL) -> Bool {
        guard let origin, origin.count <= 300 else { return false }
        return allows(URL(string: origin), endpoint: endpoint)
    }

    static func effectivePort(_ url: URL) -> Int { url.port ?? (url.scheme == "https" ? 443 : 80) }

    /// The dock page; low-memory phones ask the shared UI for its lighter rendering.
    static func pageURL(for endpoint: URL, lowMemory: Bool) -> URL {
        guard lowMemory, var parts = URLComponents(url: endpoint, resolvingAgainstBaseURL: false) else { return endpoint }
        parts.path = "/"
        parts.queryItems = [URLQueryItem(name: "perf", value: "1")]
        return parts.url ?? endpoint
    }

    /// Same threshold as Android's `PerformancePolicy`: 2 GiB or less.
    static func isLowMemory(_ physicalMemory: UInt64 = ProcessInfo.processInfo.physicalMemory) -> Bool {
        physicalMemory > 0 && physicalMemory < 2_147_483_649
    }

    /// WebKit content rules supplement the navigation delegate for images, scripts and fetches.
    static func contentRules(for endpoint: URL) throws -> String {
        let host = endpoint.host!.replacingOccurrences(of: ".", with: "[.]")
        let port = effectivePort(endpoint)
        let standardPort = endpoint.scheme == "https" ? 443 : 80
        let portPattern = port == standardPort ? "(:\(port))?" : ":\(port)"
        let origin = "^\(endpoint.scheme!)://\(host)\(portPattern)/"
        let socketOrigin = "^\(endpoint.scheme == "https" ? "wss" : "ws")://\(host)\(portPattern)/"
        let rules: [[String: Any]] = [
            ["trigger": ["url-filter": ".*"], "action": ["type": "block"]],
            ["trigger": ["url-filter": origin], "action": ["type": "ignore-previous-rules"]],
            ["trigger": ["url-filter": socketOrigin], "action": ["type": "ignore-previous-rules"]],
            ["trigger": ["url-filter": "^data:image/"], "action": ["type": "ignore-previous-rules"]]
        ]
        return String(data: try JSONSerialization.data(withJSONObject: rules), encoding: .utf8)!
    }
}
