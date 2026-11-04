import Foundation
import Darwin

/// One IPv4 network this iPhone is attached to (Wi-Fi, or Personal Hotspot clients over Wi-Fi/USB).
struct LocalNetwork: Equatable {
    let name: String
    let address: String
    let prefixLength: Int
    /// `bridge*` interfaces exist while Personal Hotspot is serving a PC (Wi-Fi or USB cable).
    let hotspot: Bool

    private static let maxSweepHosts = 1022

    var mask: UInt32 { prefixLength <= 0 ? 0 : UInt32.max << UInt32(32 - min(prefixLength, 32)) }

    var broadcast: String? {
        guard let own = Self.ipv4(address), (1...30).contains(prefixLength) else { return nil }
        return Self.string((own & mask) | ~mask)
    }

    func contains(_ host: String) -> Bool {
        guard (1...32).contains(prefixLength), let own = Self.ipv4(address), let peer = Self.ipv4(host) else { return false }
        return own & mask == peer & mask
    }

    /// Unicast probe targets. iOS only lets apps send broadcast datagrams with Apple's
    /// multicast entitlement, so discovery also asks each nearby address directly.
    /// Large networks are limited to the /24 around this phone.
    func sweepTargets() -> [String] {
        guard let own = Self.ipv4(address), (1...30).contains(prefixLength) else { return [] }
        var prefix = prefixLength
        if (1 << (32 - prefix)) - 2 > Self.maxSweepHosts { prefix = 24 }
        let netmask = UInt32.max << UInt32(32 - prefix)
        let network = own & netmask
        let last = network | ~netmask
        guard last > network + 1 else { return [] }
        var targets: [String] = []
        targets.reserveCapacity(Int(last - network))
        var host = network + 1
        while host < last {
            if host != own { targets.append(Self.string(host)) }
            host += 1
        }
        return targets
    }

    static func ipv4(_ value: String) -> UInt32? {
        guard let octets = EndpointPolicy.octets(value) else { return nil }
        return octets.reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
    }

    static func string(_ value: UInt32) -> String {
        "\(value >> 24 & 0xff).\(value >> 16 & 0xff).\(value >> 8 & 0xff).\(value & 0xff)"
    }

    /// Private IPv4 networks on Wi-Fi (`en*`) and Personal Hotspot (`bridge*`).
    /// Cellular (`pdp_ip*`) and VPN tunnels are skipped; enter a Tailscale address manually.
    static func available() -> [LocalNetwork] {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return [] }
        defer { freeifaddrs(head) }
        var result: [LocalNetwork] = []
        var cursor: UnsafeMutablePointer<ifaddrs>? = first
        while let entry = cursor {
            cursor = entry.pointee.ifa_next
            let flags = Int32(bitPattern: entry.pointee.ifa_flags)
            guard flags & IFF_UP != 0, flags & IFF_RUNNING != 0, flags & IFF_LOOPBACK == 0,
                  let addr = entry.pointee.ifa_addr, addr.pointee.sa_family == sa_family_t(AF_INET),
                  let netmask = entry.pointee.ifa_netmask else { continue }
            let name = String(cString: entry.pointee.ifa_name)
            guard name.hasPrefix("en") || name.hasPrefix("bridge") else { continue }
            let ip = addr.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { UInt32(bigEndian: $0.pointee.sin_addr.s_addr) }
            let mask = netmask.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { UInt32(bigEndian: $0.pointee.sin_addr.s_addr) }
            let network = LocalNetwork(name: name, address: string(ip), prefixLength: mask.nonzeroBitCount,
                                       hotspot: name.hasPrefix("bridge"))
            guard EndpointPolicy.isPrivateHost(network.address), !result.contains(network) else { continue }
            result.append(network)
        }
        return result
    }
}
