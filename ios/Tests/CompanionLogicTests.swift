import XCTest
@testable import WinDock

/// Discovery, saved PCs, appearance and idle rules ported from the Android app.
final class CompanionLogicTests: XCTestCase {
    private var defaults: UserDefaults!

    override func setUp() {
        defaults = UserDefaults(suiteName: "WinDockLogicTests")!
        defaults.removePersistentDomain(forName: "WinDockLogicTests")
    }

    override func tearDown() { defaults.removePersistentDomain(forName: "WinDockLogicTests") }

    func testDiscoveryReplyUsesSenderAddress() {
        XCTAssertEqual(DiscoveryProtocol.parseReply("windock:here:v1:http://192.168.1.20:8620")?.absoluteString, "http://192.168.1.20:8620")
        XCTAssertEqual(DiscoveryProtocol.parseReply("windock:here:v1: 192.168.1.20 \n")?.absoluteString, "http://192.168.1.20:8620")
        // The advertised address is replaced with the one the reply came from.
        XCTAssertEqual(DiscoveryProtocol.parseReply("windock:here:v1:http://10.0.0.9:9000", sender: "192.168.1.30")?.absoluteString,
                       "http://192.168.1.30:9000")
        for message in ["", "windock:here:v1:", "windock:here:v2:http://192.168.1.20:8620",
                        "windock:here:v1:http://8.8.8.8:8620", "windock:here:v1:http://example.com"] {
            XCTAssertNil(DiscoveryProtocol.parseReply(message), message)
        }
        XCTAssertNil(DiscoveryProtocol.parseReply("windock:here:v1:http://192.168.1.20:8620", sender: "8.8.8.8"))
        XCTAssertNil(DiscoveryProtocol.parseReply("windock:here:v1:http://192.168.1.20:8620", sender: "fe80::1"))
    }

    func testLocalNetworkMath() throws {
        let wifi = LocalNetwork(name: "en0", address: "192.168.1.37", prefixLength: 24, hotspot: false)
        XCTAssertEqual(wifi.broadcast, "192.168.1.255")
        XCTAssertTrue(wifi.contains("192.168.1.200"))
        XCTAssertFalse(wifi.contains("192.168.2.1"))
        let sweep = wifi.sweepTargets()
        XCTAssertEqual(sweep.count, 253)
        XCTAssertFalse(sweep.contains("192.168.1.37"))
        XCTAssertFalse(sweep.contains("192.168.1.0"))
        XCTAssertFalse(sweep.contains("192.168.1.255"))
        let hotspot = LocalNetwork(name: "bridge100", address: "172.20.10.1", prefixLength: 28, hotspot: true)
        XCTAssertEqual(hotspot.broadcast, "172.20.10.15")
        XCTAssertEqual(hotspot.sweepTargets().first, "172.20.10.2")
        XCTAssertEqual(hotspot.sweepTargets().count, 13)
        // Very large networks only sweep the /24 around the phone.
        let large = LocalNetwork(name: "en0", address: "10.4.7.9", prefixLength: 8, hotspot: false)
        XCTAssertEqual(large.sweepTargets().count, 253)
        XCTAssertEqual(large.sweepTargets().first, "10.4.7.1")
    }

    func testEndpointAcceptsTailscaleAndBuildsLowMemoryPage() throws {
        XCTAssertEqual(EndpointPolicy.normalize("100.101.102.103")?.absoluteString, "http://100.101.102.103:8620")
        XCTAssertNil(EndpointPolicy.normalize("100.63.0.1"))
        XCTAssertNil(EndpointPolicy.normalize("100.128.0.1"))
        let endpoint = try XCTUnwrap(EndpointPolicy.normalize("192.168.1.20"))
        XCTAssertEqual(EndpointPolicy.pageURL(for: endpoint, lowMemory: true).absoluteString, "http://192.168.1.20:8620/?perf=1")
        XCTAssertEqual(EndpointPolicy.pageURL(for: endpoint, lowMemory: false), endpoint)
        XCTAssertTrue(EndpointPolicy.isLowMemory(2 * 1_073_741_824))
        XCTAssertFalse(EndpointPolicy.isLowMemory(3 * 1_073_741_824))
        XCTAssertTrue(EndpointPolicy.allows(origin: "http://192.168.1.20:8620", endpoint: endpoint))
        XCTAssertFalse(EndpointPolicy.allows(origin: "http://192.168.1.21:8620", endpoint: endpoint))
    }

    func testHealthIdentity() throws {
        let endpoint = try XCTUnwrap(EndpointPolicy.normalize("192.168.1.20"))
        let body = #"{"ok":true,"app":"windock","platform":"windows","hostName":"Desk\u0007PC|1","hostId":"0f8fad5b-d9cb-469f-a165-70867728950e"}"#
        let host = try XCTUnwrap(HealthProbe.host(from: Data(body.utf8), endpoint: endpoint))
        XCTAssertEqual(host.label, "Desk PC 1")
        XCTAssertEqual(host.platform, "Windows")
        XCTAssertEqual(host.hostId, "0f8fad5b-d9cb-469f-a165-70867728950e")
        let old = try XCTUnwrap(HealthProbe.host(from: Data(#"{"ok":true,"app":"windock","hostId":"not-a-uuid"}"#.utf8), endpoint: endpoint))
        XCTAssertEqual(old.hostId, "")
        XCTAssertEqual(old.identity, "http://192.168.1.20:8620")
        XCTAssertEqual(old.name, "192.168.1.20:8620")
    }

    func testSavedPCsRememberForgetAndLimit() throws {
        let store = KnownHosts(defaults: defaults)
        for i in 1...10 {
            let url = try XCTUnwrap(EndpointPolicy.normalize("192.168.1.\(i)"))
            store.connected(url, host: KnownHost(endpoint: url.absoluteString, label: "PC \(i)"))
        }
        XCTAssertEqual(store.hosts.count, KnownHosts.limit)
        XCTAssertEqual(store.hosts.first?.label, "PC 10")
        XCTAssertEqual(store.remembered?.absoluteString, "http://192.168.1.10:8620")

        // The same PC (by host ID) at a new address replaces its old entry.
        let id = "0f8fad5b-d9cb-469f-a165-70867728950e"
        let first = try XCTUnwrap(EndpointPolicy.normalize("10.0.0.5"))
        store.connected(first, host: KnownHost(endpoint: first.absoluteString, label: "Studio", hostId: id))
        let moved = try XCTUnwrap(EndpointPolicy.normalize("10.0.0.6"))
        store.connected(moved, host: KnownHost(endpoint: moved.absoluteString, label: "Studio", hostId: id))
        XCTAssertEqual(store.hosts.filter { $0.hostId == id }.map(\.endpoint), [moved.absoluteString])

        let studio = try XCTUnwrap(store.hosts.first)
        store.forget(studio)
        XCTAssertFalse(store.hosts.contains { $0.hostId == id })
        XCTAssertNil(store.remembered)
        XCTAssertFalse(store.canAutoConnect(moved))
        XCTAssertFalse(store.canAutoConnect(KnownHost(endpoint: "http://10.0.0.7:8620", hostId: id)), "Forgotten by identity too")
        // Choosing it again restores automatic reconnection.
        store.connected(moved, host: studio)
        XCTAssertTrue(store.canAutoConnect(moved))
        XCTAssertTrue(store.canAutoConnect(studio))
    }

    func testAppearanceIsScopedPerPCAndValidated() throws {
        let appearance = AppearanceStore(defaults: defaults)
        let endpoint = try XCTUnwrap(EndpointPolicy.normalize("192.168.1.20"))
        let origin = "http://192.168.1.20:8620"
        XCTAssertNil(appearance.snapshot(origin: origin, legacy: "{}"), "No PC selected")
        appearance.select(endpoint: endpoint, hostId: "0f8fad5b-d9cb-469f-a165-70867728950e")
        XCTAssertNil(appearance.snapshot(origin: "http://192.168.1.21:8620", legacy: "{}"))
        let legacy = #"{"windock-performance":"on","windock-layout":"{\"perPage\":6,\"theme\":\"frost\",\"showLabels\":true}"}"#
        let first = try XCTUnwrap(appearance.snapshot(origin: origin, legacy: legacy))
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(first.utf8)) as? [String: Any])
        XCTAssertEqual(object["scope"] as? String, "0f8fad5b-d9cb-469f-a165-70867728950e")
        XCTAssertEqual((object["values"] as? [String: String])?["windock-performance"], "on")
        let scope = try XCTUnwrap(object["scope"] as? String)
        XCTAssertTrue(appearance.save(origin: origin, scope: scope, key: "windock-performance", value: "off"))
        XCTAssertFalse(appearance.save(origin: origin, scope: scope, key: "windock-performance", value: "turbo"))
        XCTAssertFalse(appearance.save(origin: origin, scope: "other", key: "windock-performance", value: "off"))
        XCTAssertFalse(appearance.save(origin: origin, scope: scope, key: "other", value: "off"))
        XCTAssertFalse(appearance.save(origin: origin, scope: scope, key: "windock-layout", value: #"{"theme":"neon"}"#))
        XCTAssertFalse(appearance.save(origin: origin, scope: scope, key: "windock-layout", value: #"{"perPage":true}"#))
        XCTAssertFalse(appearance.save(origin: origin, scope: scope, key: "windock-layout", value: #"{"unknown":1}"#))
        XCTAssertTrue(appearance.save(origin: origin, scope: scope, key: "windock-layout", value: #"{"perPage":8,"immersive":false}"#))
        // Once initialised, later legacy web storage no longer overrides native values.
        let again = try XCTUnwrap(appearance.snapshot(origin: origin, legacy: #"{"windock-performance":"on"}"#))
        XCTAssertTrue(again.contains(#""windock-performance":"off""#))
        // A different PC reached at the same address does not inherit those values.
        appearance.select(endpoint: endpoint, hostId: "7c9e6679-7425-40de-944b-e07fc1f90ae7")
        let other = try XCTUnwrap(appearance.snapshot(origin: origin, legacy: legacy))
        XCTAssertTrue(other.contains(#""values":{}"#), other)
    }

    func testIdleStagesAndSettings() {
        var policy = DisplayPolicy(dimAfter: 30, sleepAfter: 120, dimPercent: 10)
        XCTAssertEqual(policy.stage(10), .awake)
        XCTAssertEqual(policy.stage(30), .dimmed)
        XCTAssertEqual(policy.stage(125), .resting)
        XCTAssertEqual(policy.nextDeadline(10), 30)
        XCTAssertEqual(policy.nextDeadline(40), 120)
        XCTAssertNil(policy.nextDeadline(130))
        XCTAssertTrue(policy.keepsAwake(.dimmed))
        XCTAssertFalse(policy.keepsAwake(.resting))
        policy.sleepAfter = 0
        XCTAssertFalse(policy.keepsAwake(.awake), "Follow iOS Auto-Lock")
        policy.sleepAfter = -1
        XCTAssertEqual(policy.stage(100_000), .dimmed, "Stay awake never rests")
        XCTAssertTrue(policy.keepsAwake(.dimmed))

        XCTAssertEqual(PhoneSettings.display(defaults), DisplayPolicy())
        PhoneSettings.save(DisplayPolicy(dimAfter: 60, sleepAfter: 300, dimPercent: 20), defaults)
        XCTAssertEqual(PhoneSettings.display(defaults), DisplayPolicy(dimAfter: 60, sleepAfter: 300, dimPercent: 20))
        defaults.set(7.0, forKey: "phone.dimAfter")
        XCTAssertEqual(PhoneSettings.display(defaults).dimAfter, 30, "Unknown stored values fall back")
    }

    func testBridgeScriptsAndReleaseLinks() {
        XCTAssertTrue(NativeBridge.script.contains("WinDockAndroid"))
        XCTAssertTrue(NativeBridge.script.contains("\"windock-native:v1\""))
        XCTAssertEqual(NativeBridge.dispatch("windock-keyboard-action", detail: ["action": "closed"]),
                       #"window.dispatchEvent(new CustomEvent("windock-keyboard-action",{detail:{"action":"closed"}}))"#)
        XCTAssertNil(NativeBridge.dispatch("click", detail: [:]))
        XCTAssertEqual(NativeBridge.releasePage("0.2.6-preview.1")?.absoluteString,
                       "https://github.com/aliihsaad/WinDock/releases/tag/v0.2.6-preview.1")
        XCTAssertNil(NativeBridge.releasePage("../../evil"))
        XCTAssertNil(NativeBridge.releasePage("1.2"))
    }
}
