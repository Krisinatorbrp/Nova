import Foundation
import Darwin

/// The WinDock LAN discovery protocol (`src/discovery.js` on the PC).
enum DiscoveryProtocol {
    static let port: UInt16 = 41234
    static let probe = "windock:discover:v1"
    static let replyPrefix = "windock:here:v1:"

    /// Parses a host reply. When `sender` is given, the advertised scheme and port are
    /// kept but the address is replaced with the one the datagram actually came from,
    /// so a reply cannot point the phone at a different machine.
    static func parseReply(_ message: String, sender: String? = nil) -> URL? {
        guard message.hasPrefix(replyPrefix), message.utf8.count <= 256 else { return nil }
        let advertised = String(message.dropFirst(replyPrefix.count)).trimmingCharacters(in: .whitespacesAndNewlines)
        guard let endpoint = EndpointPolicy.normalize(advertised) else { return nil }
        guard let sender else { return endpoint }
        guard EndpointPolicy.octets(sender) != nil,
              var parts = URLComponents(url: endpoint, resolvingAgainstBaseURL: false) else { return nil }
        parts.host = sender
        return EndpointPolicy.normalize(parts.url?.absoluteString)
    }
}

struct DiscoveryCandidate: Equatable {
    let endpoint: URL
    let hotspot: Bool
}

/// Finds running WinDock hosts with the same UDP probe as the Android app.
/// Each run sends the probe to subnet broadcast addresses (works when the app holds
/// Apple's multicast entitlement) and to every nearby address individually (works
/// for every build once Local Network access is allowed).
final class LANDiscovery {
    private let queue = DispatchQueue(label: "windock.discovery")
    private let lock = NSLock()
    private var generation = 0

    static let maxResults = 24

    func cancel() {
        lock.lock(); generation += 1; lock.unlock()
    }

    private func isCurrent(_ run: Int) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return generation == run
    }

    /// Calls `completion` on the main queue. A cancelled or superseded scan never calls back.
    func scan(duration: TimeInterval = 1.8, port: UInt16 = DiscoveryProtocol.port,
              networks: [LocalNetwork]? = nil, completion: @escaping ([DiscoveryCandidate]) -> Void) {
        lock.lock(); generation += 1; let run = generation; lock.unlock()
        queue.async { [weak self] in
            guard let self else { return }
            let found = self.run(run, duration: duration, port: port, networks: networks ?? LocalNetwork.available())
            DispatchQueue.main.async { if self.isCurrent(run) { completion(found) } }
        }
    }

    private func run(_ run: Int, duration: TimeInterval, port: UInt16, networks: [LocalNetwork]) -> [DiscoveryCandidate] {
        let fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        guard fd >= 0 else { return [] }
        defer { close(fd) }
        var yes: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &yes, socklen_t(MemoryLayout<Int32>.size))
        setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &yes, socklen_t(MemoryLayout<Int32>.size))
        var local = sockaddr_in()
        local.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        local.sin_family = sa_family_t(AF_INET)
        local.sin_port = 0
        local.sin_addr.s_addr = 0 // INADDR_ANY
        let bound = withUnsafePointer(to: &local) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        guard bound == 0 else { return [] }
        _ = fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)

        let payload = Array(DiscoveryProtocol.probe.utf8)
        let broadcasts = Array(Set(networks.compactMap(\.broadcast) + ["255.255.255.255"]))
        let sweep = networks.flatMap { $0.sweepTargets() }
        let deadline = Date().addingTimeInterval(duration)
        var rounds = 0, nextRound = Date.distantPast
        var found: [DiscoveryCandidate] = []

        while Date() < deadline, isCurrent(run), found.count < Self.maxResults {
            if rounds < 2, Date() >= nextRound {
                for host in broadcasts { send(fd, payload, to: host, port: port) }
                for (index, host) in sweep.enumerated() {
                    send(fd, payload, to: host, port: port)
                    if index % 48 == 47 { usleep(3_000); drain(fd, networks, &found) } // Avoid ENOBUFS bursts.
                }
                rounds += 1
                nextRound = Date().addingTimeInterval(0.7)
            }
            var poller = pollfd(fd: fd, events: Int16(POLLIN), revents: 0)
            if poll(&poller, 1, 40) > 0 { drain(fd, networks, &found) }
        }
        return found
    }

    private func send(_ fd: Int32, _ payload: [UInt8], to host: String, port: UInt16) {
        var target = sockaddr_in()
        target.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        target.sin_family = sa_family_t(AF_INET)
        target.sin_port = port.bigEndian
        guard inet_pton(AF_INET, host, &target.sin_addr) == 1 else { return }
        _ = payload.withUnsafeBytes { bytes in
            withUnsafePointer(to: &target) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    sendto(fd, bytes.baseAddress, bytes.count, 0, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
        }
    }

    private func drain(_ fd: Int32, _ networks: [LocalNetwork], _ found: inout [DiscoveryCandidate]) {
        var buffer = [UInt8](repeating: 0, count: 257)
        while found.count < Self.maxResults {
            var from = sockaddr_in()
            var length = socklen_t(MemoryLayout<sockaddr_in>.size)
            let count = buffer.withUnsafeMutableBytes { bytes in
                withUnsafeMutablePointer(to: &from) {
                    $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                        recvfrom(fd, bytes.baseAddress, bytes.count, 0, $0, &length)
                    }
                }
            }
            guard count > 0 else { return }
            guard count <= 256 else { continue }
            var address = from.sin_addr
            var text = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
            guard inet_ntop(AF_INET, &address, &text, socklen_t(INET_ADDRSTRLEN)) != nil else { continue }
            let sender = String(cString: text)
            // Only accept replies from a network this phone is directly attached to.
            guard let network = networks.first(where: { $0.contains(sender) }),
                  let message = String(bytes: buffer[0..<count], encoding: .utf8),
                  let endpoint = DiscoveryProtocol.parseReply(message, sender: sender),
                  !found.contains(where: { $0.endpoint == endpoint }) else { continue }
            found.append(DiscoveryCandidate(endpoint: endpoint, hotspot: network.hotspot))
        }
    }
}
