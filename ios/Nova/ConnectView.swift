import Network
import SwiftUI

struct FoundPC: Identifiable, Hashable {
    let id: String
    let name: String
    let urls: [URL]
}

/// Finds PCs running Nova on the same Wi-Fi (Nova announces itself with Bonjour).
final class PCBrowser: ObservableObject {
    @Published var found: [FoundPC] = []
    private var browser: NWBrowser?

    func start() {
        guard browser == nil else { return }
        let params = NWParameters()
        params.includePeerToPeer = true
        let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_nova._tcp", domain: nil), using: params)
        b.browseResultsChangedHandler = { [weak self] results, _ in
            var list: [FoundPC] = []
            for result in results {
                guard case let .service(name, _, _, _) = result.endpoint else { continue }
                guard case let .bonjour(txt) = result.metadata else { continue }
                let port = txt["port"] ?? "8765"
                let ips = (txt["ips"] ?? "").split(separator: ",").map { String($0) }
                let urls = ips.compactMap { URL(string: "http://\($0):\(port)") }
                if !urls.isEmpty {
                    list.append(FoundPC(id: name, name: txt["host"] ?? name, urls: urls))
                }
            }
            DispatchQueue.main.async { self?.found = list }
        }
        b.start(queue: .main)
        browser = b
    }

    func stop() {
        browser?.cancel()
        browser = nil
    }
}

struct ConnectView: View {
    @ObservedObject var state: AppState
    @StateObject private var browser = PCBrowser()
    @State private var manual = ""
    @State private var checking = false
    @State private var errorText: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Image("Orb")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 92, height: 92)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .padding(.top, 36)

                Text("Connect to your PC")
                    .font(.largeTitle.bold())
                Text("Start Nova on your PC. If your iPhone is on the same Wi-Fi, it appears below.")
                    .foregroundColor(.secondary)

                VStack(spacing: 10) {
                    if browser.found.isEmpty {
                        HStack(spacing: 12) {
                            ProgressView()
                            Text("Looking for Nova on your Wi-Fi…")
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .padding(16)
                        .background(card)
                    }
                    ForEach(browser.found) { pc in
                        Button {
                            connect(pc.urls)
                        } label: {
                            HStack(spacing: 14) {
                                Image(systemName: "desktopcomputer")
                                    .font(.title2)
                                    .foregroundColor(.purple)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(pc.name).font(.headline).foregroundColor(.primary)
                                    Text(pc.urls.first?.absoluteString ?? "")
                                        .font(.footnote).foregroundColor(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").foregroundColor(.secondary)
                            }
                            .padding(16)
                            .background(card)
                        }
                        .disabled(checking)
                    }
                }

                Text("Or type the address shown in Nova's settings")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.top, 8)

                TextField("192.168.1.20:8765", text: $manual)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .onSubmit { connectManual() }
                    .padding(14)
                    .background(card)

                Button {
                    connectManual()
                } label: {
                    Text(checking ? "Connecting…" : "Connect")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
                .tint(.white)
                .foregroundColor(.black)
                .disabled(manual.trimmingCharacters(in: .whitespaces).isEmpty || checking)

                if let errorText {
                    Text(errorText).font(.footnote).foregroundColor(.red)
                }

                Text("Away from home? Install Tailscale on your PC and iPhone, then type the 100.x.x.x address.")
                    .font(.footnote)
                    .foregroundColor(.secondary)

                Button {
                    state.deviceOnly = true
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "iphone")
                            .font(.title3)
                            .foregroundColor(.orange)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Use Nova on this iPhone only").font(.headline).foregroundColor(.primary)
                            Text("Chat with the AI on your iPhone, without a PC. Works offline.")
                                .font(.footnote).foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding(16)
                    .background(card)
                }
                .padding(.top, 8)
            }
            .padding(24)
            .frame(maxWidth: 520)
            .frame(maxWidth: .infinity)
        }
        .background(novaBackground.ignoresSafeArea())
        .onAppear { browser.start() }
        .onDisappear { browser.stop() }
    }

    private var card: some View {
        RoundedRectangle(cornerRadius: 16, style: .continuous)
            .fill(Color.white.opacity(0.06))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Color.white.opacity(0.10), lineWidth: 1))
    }

    private func connectManual() {
        guard let url = normalized(manual) else {
            errorText = "That doesn't look like an address. Example: 192.168.1.20:8765"
            return
        }
        connect([url])
    }

    private func normalized(_ text: String) -> URL? {
        var t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return nil }
        if !t.lowercased().hasPrefix("http://") && !t.lowercased().hasPrefix("https://") {
            t = "http://" + t
        }
        guard var parts = URLComponents(string: t), parts.host != nil else { return nil }
        if parts.port == nil && parts.scheme == "http" { parts.port = 8765 }
        parts.path = ""
        parts.query = nil
        return parts.url
    }

    private func connect(_ urls: [URL]) {
        checking = true
        errorText = nil
        Task {
            for url in urls {
                if await reachable(url) {
                    await MainActor.run {
                        checking = false
                        state.offline = false
                        state.serverURL = url
                    }
                    return
                }
            }
            await MainActor.run {
                checking = false
                errorText = "Couldn't reach Nova. Is it running on the PC, and is this iPhone on the same Wi-Fi (or Tailscale)?"
            }
        }
    }

    private func reachable(_ base: URL) async -> Bool {
        var request = URLRequest(url: base.appendingPathComponent("api/state"))
        request.timeoutInterval = 5
        guard let result = try? await URLSession.shared.data(for: request) else { return false }
        let (data, response) = result
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { return false }
        return (try? JSONSerialization.jsonObject(with: data)) is [String: Any]
    }
}
