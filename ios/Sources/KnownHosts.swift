import Foundation

/// A PC that answered `/health` as WinDock. `hostId` is the PC's stable identity when the
/// host reports one; older hosts are remembered by address only.
struct KnownHost: Codable, Equatable {
    var endpoint: String
    var label: String
    var hotspot: Bool
    var lastSeen: Date
    var platform: String
    var hostId: String

    init(endpoint: String, label: String = "", hotspot: Bool = false, lastSeen: Date = Date(),
         platform: String = "", hostId: String = "") {
        self.endpoint = endpoint
        self.label = KnownHosts.cleanLabel(label)
        self.hotspot = hotspot
        self.lastSeen = lastSeen
        self.platform = KnownHosts.cleanLabel(platform)
        self.hostId = KnownHosts.cleanId(hostId)
    }

    var url: URL? { EndpointPolicy.normalize(endpoint) }
    var address: String { endpoint.replacingOccurrences(of: "http://", with: "") }
    var identity: String { hostId.isEmpty ? endpoint : hostId }
    var name: String { !label.isEmpty ? label : !platform.isEmpty ? platform : address }
    var detail: String {
        [platform.isEmpty || platform == label ? nil : platform, address, hotspot ? "Hotspot" : nil]
            .compactMap { $0 }.joined(separator: " · ")
    }
}

/// Saved PCs (up to eight, most recent first) plus the "forget" lists that stop
/// automatic reconnection. Same rules as the Android `KnownHosts`/`ServerUrl`.
final class KnownHosts {
    static let limit = 8
    static let rememberedKey = "windock.pcAddress"
    private static let hostsKey = "windock.knownHosts"
    private static let forgottenEndpointsKey = "windock.forgottenEndpoints"
    private static let forgottenHostsKey = "windock.forgottenHosts"

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    static func cleanLabel(_ value: String?) -> String {
        let scalars = (value ?? "").unicodeScalars.map { scalar -> Character in
            switch scalar.properties.generalCategory {
            case .control, .format, .lineSeparator, .paragraphSeparator: return " "
            default: return scalar == "|" ? " " : Character(scalar)
            }
        }
        return String(String(scalars).trimmingCharacters(in: .whitespacesAndNewlines).prefix(40))
    }

    static func cleanId(_ value: String?) -> String {
        guard let value, value.count == 36,
              value.range(of: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", options: .regularExpression) != nil
        else { return "" }
        return value
    }

    static func platformName(_ value: String?) -> String {
        switch value {
        case "windows": return "Windows"
        case "darwin": return "macOS"
        case "linux": return "Linux"
        default: return ""
        }
    }

    var remembered: URL? {
        get {
            guard let url = EndpointPolicy.normalize(defaults.string(forKey: Self.rememberedKey)),
                  canAutoConnect(url) else { return nil }
            return url
        }
    }

    var hosts: [KnownHost] {
        guard let data = defaults.data(forKey: Self.hostsKey),
              let decoded = try? JSONDecoder().decode([KnownHost].self, from: data) else { return [] }
        var result: [KnownHost] = []
        for host in decoded {
            guard let url = EndpointPolicy.normalize(host.endpoint) else { continue }
            var clean = KnownHost(endpoint: url.absoluteString, label: host.label, hotspot: host.hotspot,
                                  lastSeen: host.lastSeen, platform: host.platform, hostId: host.hostId)
            clean.endpoint = url.absoluteString
            guard !result.contains(where: { $0.endpoint == clean.endpoint || $0.identity == clean.identity }) else { continue }
            result.append(clean)
            if result.count == Self.limit { break }
        }
        return result
    }

    private func save(_ hosts: [KnownHost]) {
        if let data = try? JSONEncoder().encode(Array(hosts.prefix(Self.limit))) { defaults.set(data, forKey: Self.hostsKey) }
    }

    private func set(_ key: String) -> Set<String> { Set(defaults.stringArray(forKey: key) ?? []) }
    private func store(_ values: Set<String>, _ key: String) { defaults.set(values.sorted(), forKey: key) }

    /// A successful, user-visible connection: remember it first and clear any "forget".
    func connected(_ endpoint: URL, host: KnownHost?) {
        defaults.set(endpoint.absoluteString, forKey: Self.rememberedKey)
        var forgottenEndpoints = set(Self.forgottenEndpointsKey)
        forgottenEndpoints.remove(endpoint.absoluteString)
        store(forgottenEndpoints, Self.forgottenEndpointsKey)
        guard var host else { return }
        host.endpoint = endpoint.absoluteString
        host.lastSeen = Date()
        if !host.hostId.isEmpty {
            var forgottenHosts = set(Self.forgottenHostsKey)
            forgottenHosts.remove(host.hostId)
            store(forgottenHosts, Self.forgottenHostsKey)
        }
        let others = hosts.filter { $0.endpoint != host.endpoint && $0.identity != host.identity }
        save([host] + others)
    }

    /// Removes a saved PC and stops automatic reconnection to it. It can still be picked
    /// from "Available now"; selecting it saves it again.
    func forget(_ host: KnownHost) {
        guard let url = EndpointPolicy.normalize(host.endpoint) else { return }
        var forgottenEndpoints = set(Self.forgottenEndpointsKey)
        forgottenEndpoints.insert(url.absoluteString)
        store(forgottenEndpoints, Self.forgottenEndpointsKey)
        if !host.hostId.isEmpty {
            var forgottenHosts = set(Self.forgottenHostsKey)
            forgottenHosts.insert(host.hostId)
            store(forgottenHosts, Self.forgottenHostsKey)
        }
        save(hosts.filter { $0.endpoint != url.absoluteString && (host.hostId.isEmpty || $0.hostId != host.hostId) })
        if defaults.string(forKey: Self.rememberedKey) == url.absoluteString { defaults.removeObject(forKey: Self.rememberedKey) }
    }

    func canAutoConnect(_ endpoint: URL) -> Bool {
        !set(Self.forgottenEndpointsKey).contains(endpoint.absoluteString)
    }

    func canAutoConnect(_ host: KnownHost) -> Bool {
        guard let url = host.url, canAutoConnect(url) else { return false }
        return host.hostId.isEmpty || !set(Self.forgottenHostsKey).contains(host.hostId)
    }
}
