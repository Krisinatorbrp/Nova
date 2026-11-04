import Foundation

/// Idle display rules for this phone only (Android `DisplayPolicy`).
struct DisplayPolicy: Equatable {
    enum Stage { case awake, dimmed, resting }

    static let dimTimes: [TimeInterval] = [0, 15, 30, 60, 120]
    /// 0 = follow iOS Auto-Lock; -1 = stay awake while the dock is open.
    static let sleepTimes: [TimeInterval] = [0, 60, 120, 300, 600, -1]
    static let dimLevels: [Int] = [5, 10, 20]

    static let dimLabels = ["Never", "After 15 seconds", "After 30 seconds", "After 1 minute", "After 2 minutes"]
    static let sleepLabels = ["Use iPhone Auto-Lock", "After 1 minute idle", "After 2 minutes idle",
                              "After 5 minutes idle", "After 10 minutes idle", "Stay awake while dock is open"]

    var dimAfter: TimeInterval = 30
    /// iPhone default keeps the earlier iOS behaviour (screen stays on with the dock open);
    /// Android defaults to the phone's own timeout.
    var sleepAfter: TimeInterval = -1
    var dimPercent: Int = 10

    func stage(_ elapsed: TimeInterval) -> Stage {
        if sleepAfter > 0 && elapsed >= sleepAfter { return .resting }
        if dimAfter > 0 && elapsed >= dimAfter { return .dimmed }
        return .awake
    }

    func nextDeadline(_ elapsed: TimeInterval) -> TimeInterval? {
        [dimAfter, sleepAfter].filter { $0 > 0 && $0 > elapsed }.min()
    }

    /// Whether to disable iOS Auto-Lock at this stage.
    func keepsAwake(_ stage: Stage) -> Bool { sleepAfter != 0 && stage != .resting }
}

enum PhoneSettings {
    private static let dimAfterKey = "phone.dimAfter"
    private static let sleepAfterKey = "phone.sleepAfter"
    private static let dimPercentKey = "phone.dimPercent"

    static func display(_ defaults: UserDefaults) -> DisplayPolicy {
        var policy = DisplayPolicy()
        if let value = defaults.object(forKey: dimAfterKey) as? Double, DisplayPolicy.dimTimes.contains(value) { policy.dimAfter = value }
        if let value = defaults.object(forKey: sleepAfterKey) as? Double, DisplayPolicy.sleepTimes.contains(value) { policy.sleepAfter = value }
        if let value = defaults.object(forKey: dimPercentKey) as? Int, DisplayPolicy.dimLevels.contains(value) { policy.dimPercent = value }
        return policy
    }

    static func save(_ policy: DisplayPolicy, _ defaults: UserDefaults) {
        defaults.set(policy.dimAfter, forKey: dimAfterKey)
        defaults.set(policy.sleepAfter, forKey: sleepAfterKey)
        defaults.set(policy.dimPercent, forKey: dimPercentKey)
    }
}

/// Dock appearance kept per PC identity, so two PCs reached at the same address over
/// time keep separate layouts (Android `AppearancePreferences`).
final class AppearanceStore {
    static let keys = ["windock-performance", "windock-layout"]
    private let defaults: UserDefaults
    private var target: (endpoint: URL, scope: String)?

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    private func key(_ suffix: String) -> String { "appearance." + suffix }

    func select(endpoint: URL?, hostId: String?) {
        guard let endpoint else { target = nil; return }
        let id = KnownHosts.cleanId(hostId)
        target = (endpoint, id.isEmpty ? endpoint.absoluteString : id)
    }

    /// JSON `{"scope": …, "values": {…}}` for the page at `origin`, or nil.
    func snapshot(origin: String, legacy: String) -> String? {
        guard let selected = target, EndpointPolicy.allows(origin: origin, endpoint: selected.endpoint) else { return nil }
        let ownerKey = key("origin:" + selected.endpoint.absoluteString)
        let initializedKey = key("initialized:" + selected.scope)
        let previousOwner = defaults.string(forKey: ownerKey)
        var values: [String: String] = [:]
        for name in Self.keys {
            if let value = defaults.string(forKey: key(selected.scope + ":" + name)) { values[name] = value }
        }
        // First visit for this PC: adopt values the page kept in web storage, unless that
        // storage belonged to a different PC that previously used this address.
        if !defaults.bool(forKey: initializedKey) && (previousOwner == nil || previousOwner == selected.scope) {
            let old = legacy.utf8.count <= 4096
                ? (try? JSONSerialization.jsonObject(with: Data(legacy.utf8)) as? [String: Any]) ?? [:] : [:]
            for name in Self.keys {
                if let value = old[name] as? String, Self.valid(name, value) {
                    values[name] = value
                    defaults.set(value, forKey: key(selected.scope + ":" + name))
                }
            }
        }
        defaults.set(selected.scope, forKey: ownerKey)
        defaults.set(true, forKey: initializedKey)
        let result: [String: Any] = ["scope": selected.scope, "values": values]
        guard let data = try? JSONSerialization.data(withJSONObject: result) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func save(origin: String, scope: String, key name: String, value: String) -> Bool {
        guard let selected = target, scope == selected.scope,
              EndpointPolicy.allows(origin: origin, endpoint: selected.endpoint), Self.valid(name, value) else { return false }
        defaults.set(value, forKey: key(scope + ":" + name))
        return true
    }

    static func valid(_ name: String, _ value: String) -> Bool {
        guard keys.contains(name), value.utf8.count <= 2048 else { return false }
        if name == "windock-performance" { return ["auto", "on", "off"].contains(value) }
        guard let layout = (try? JSONSerialization.jsonObject(with: Data(value.utf8))) as? [String: Any] else { return false }
        for (field, item) in layout {
            switch field {
            case "background": guard let text = item as? String, ["aurora", "dusk", "ember", "midnight"].contains(text) else { return false }
            case "theme": guard let text = item as? String, ["glass", "frost", "smoke"].contains(text) else { return false }
            case "iconSize", "perPage", "rows", "columns": guard isNumber(item) else { return false }
            case "showLabels", "immersive": guard isBoolean(item) else { return false }
            default: return false
            }
        }
        return true
    }

    private static func isBoolean(_ value: Any) -> Bool {
        guard let number = value as? NSNumber else { return false }
        return CFGetTypeID(number) == CFBooleanGetTypeID()
    }

    private static func isNumber(_ value: Any) -> Bool {
        guard let number = value as? NSNumber else { return false }
        return CFGetTypeID(number) != CFBooleanGetTypeID()
    }
}
