import UIKit

/// "Switch PC": the current PC, saved PCs (checked live) and PCs found on the network.
/// Same structure and rules as the Android `PcPicker`.
final class PCPickerViewController: UITableViewController {
    private enum Status { case checking, available, missing }
    private struct Row { var host: KnownHost; var status: Status; var url: URL? }
    private enum Section { case current, saved, found, manual }

    var onSelect: ((KnownHost, URL) -> Void)?
    var onManual: (() -> Void)?

    private let store: KnownHosts
    private let current: URL?
    private let discovery = LANDiscovery()
    private var probes: [String: HealthProbe] = [:]
    private var currentRow: Row?
    private var saved: [Row] = []
    private var found: [Row] = []
    private var scanning = false
    private var scanID = 0

    init(store: KnownHosts, current: URL?) {
        self.store = store
        self.current = current
        super.init(style: .insetGrouped)
        title = "Switch PC"
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        overrideUserInterfaceStyle = .dark
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "cell")
        navigationItem.leftBarButtonItem = UIBarButtonItem(systemItem: .close, primaryAction: UIAction { [weak self] _ in
            self?.dismiss(animated: true)
        })
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Refresh", primaryAction: UIAction { [weak self] _ in self?.scan() })
        scan()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed || navigationController?.isBeingDismissed == true { stop() }
    }

    private func stop() {
        scanID += 1
        discovery.cancel()
        probes.values.forEach { $0.cancel() }
        probes.removeAll()
    }

    func scan() {
        stop()
        let id = scanID
        scanning = true
        let hosts = store.hosts
        currentRow = nil
        if let current {
            let host = hosts.first { $0.endpoint == current.absoluteString } ?? KnownHost(endpoint: current.absoluteString)
            currentRow = Row(host: host, status: .available, url: current)
        }
        saved = hosts.filter { $0.endpoint != current?.absoluteString }.map { Row(host: $0, status: .checking, url: $0.url) }
        found = []
        tableView.reloadData()
        for row in saved { if let url = row.url { check(url, hotspot: row.host.hotspot, scan: id) } }
        discovery.scan { [weak self] candidates in
            guard let self, self.scanID == id else { return }
            for candidate in candidates where candidate.endpoint != self.current && self.probes[candidate.endpoint.absoluteString] == nil {
                if self.saved.contains(where: { $0.url == candidate.endpoint && $0.status == .available }) { continue }
                self.check(candidate.endpoint, hotspot: candidate.hotspot, scan: id)
            }
            self.finishIfIdle(id)
        }
    }

    private func check(_ url: URL, hotspot: Bool, scan id: Int) {
        let probe = HealthProbe(requestTimeout: 2.5, resourceTimeout: 4, waitsForConnectivity: false)
        probes[url.absoluteString] = probe
        probe.start(endpoint: url, hotspot: hotspot) { [weak self] host in
            guard let self, self.scanID == id else { return }
            self.probes[url.absoluteString] = nil
            self.record(url, host: host)
            self.finishIfIdle(id)
        }
    }

    /// A reply updates the saved row for the same PC (also when its address changed),
    /// or adds the PC under "Available now".
    private func record(_ url: URL, host: KnownHost?) {
        if let index = saved.firstIndex(where: { $0.url == url }) {
            if let host { saved[index].host.label = host.label.isEmpty ? saved[index].host.label : host.label }
            if saved[index].status != .available { saved[index].status = host == nil ? .missing : .available }
        } else if let host {
            if host.endpoint == current?.absoluteString || (!host.hostId.isEmpty && host.hostId == currentRow?.host.hostId) {
                // Already connected to this PC.
            } else if let index = saved.firstIndex(where: { !host.hostId.isEmpty && $0.host.hostId == host.hostId }) {
                saved[index].host = host
                saved[index].url = url
                saved[index].status = .available
            } else if !found.contains(where: { $0.url == url }) {
                found.append(Row(host: host, status: .available, url: url))
            }
        }
        tableView.reloadData()
    }

    private func finishIfIdle(_ id: Int) {
        guard scanID == id, probes.isEmpty else { return }
        scanning = false
        for index in saved.indices where saved[index].status == .checking { saved[index].status = .missing }
        tableView.reloadData()
    }

    private var sections: [Section] {
        var result: [Section] = []
        if currentRow != nil { result.append(.current) }
        if !saved.isEmpty { result.append(.saved) }
        result.append(.found)
        result.append(.manual)
        return result
    }

    override func numberOfSections(in tableView: UITableView) -> Int { sections.count }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        switch sections[section] {
        case .current: return 1
        case .saved: return saved.count
        case .found: return found.count
        case .manual: return 1
        }
    }

    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        switch sections[section] {
        case .current: return "Current PC"
        case .saved: return "Saved PCs"
        case .found: return "Available now"
        case .manual: return nil
        }
    }

    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        switch sections[section] {
        case .found:
            if scanning { return "Looking for PCs running WinDock on your network…" }
            if found.isEmpty && saved.allSatisfy({ $0.status != .available }) {
                return "No PCs found. Keep WinDock running on the same network, tap Refresh, or enter its address. "
                    + "If this keeps happening, check Settings → Privacy & Security → Local Network → WinDock."
            }
            return "Choose a PC. New connections may ask for its pairing code."
        case .saved: return "Swipe left on a saved PC to forget it."
        default: return nil
        }
    }

    private func row(at indexPath: IndexPath) -> Row? {
        switch sections[indexPath.section] {
        case .current: return currentRow
        case .saved: return saved[indexPath.row]
        case .found: return found[indexPath.row]
        case .manual: return nil
        }
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "cell", for: indexPath)
        var content = UIListContentConfiguration.subtitleCell()
        cell.accessoryType = .none
        if let row = row(at: indexPath) {
            content.text = row.host.name
            let address = row.url.map { KnownHost(endpoint: $0.absoluteString, hotspot: row.host.hotspot, platform: row.host.platform).detail } ?? row.host.detail
            let status: String
            switch (sections[indexPath.section], row.status) {
            case (.current, _): status = "Connected"
            case (_, .checking): status = "Checking…"
            case (_, .available): status = "Available"
            case (_, .missing): status = "Not found this scan · Tap to retry"
            }
            content.secondaryText = address + "\n" + status
            content.secondaryTextProperties.color = row.status == .available ? UIColor(red: 0.51, green: 0.91, blue: 0.75, alpha: 1) : .secondaryLabel
            content.image = UIImage(systemName: row.host.hotspot ? "personalhotspot" : "desktopcomputer")
            if sections[indexPath.section] == .current { cell.accessoryType = .checkmark }
        } else {
            content.text = "Enter address"
            content.secondaryText = "Type the address from WinDock’s tray menu → Show connection info."
            content.image = UIImage(systemName: "keyboard")
        }
        cell.contentConfiguration = content
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard let row = row(at: indexPath) else {
            let manual = onManual
            dismiss(animated: true) { manual?() }
            return
        }
        if sections[indexPath.section] == .current { dismiss(animated: true); return }
        guard let url = row.url else { return }
        if row.status == .missing {
            if let index = saved.firstIndex(where: { $0.url == url }) { saved[index].status = .checking }
            scanning = true
            tableView.reloadData()
            check(url, hotspot: row.host.hotspot, scan: scanID)
            return
        }
        let select = onSelect
        dismiss(animated: true) { select?(row.host, url) }
    }

    override func tableView(_ tableView: UITableView,
                            trailingSwipeActionsConfigurationForRowAt indexPath: IndexPath) -> UISwipeActionsConfiguration? {
        guard sections[indexPath.section] == .saved else { return nil }
        let host = saved[indexPath.row].host
        let forget = UIContextualAction(style: .destructive, title: "Forget") { [weak self] _, _, done in
            self?.confirmForget(host)
            done(false)
        }
        return UISwipeActionsConfiguration(actions: [forget])
    }

    private func confirmForget(_ host: KnownHost) {
        let alert = UIAlertController(
            title: "Forget \(host.name)?",
            message: "Remove this saved PC and stop automatic reconnection. A running PC can still appear under Available now; "
                + "selecting it saves it again. This does not disconnect the current session or revoke pairing. "
                + "Older hosts are remembered by address only.",
            preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        alert.addAction(UIAlertAction(title: "Forget", style: .destructive) { [weak self] _ in
            guard let self else { return }
            self.store.forget(host)
            self.saved.removeAll { $0.host.endpoint == host.endpoint }
            self.tableView.reloadData()
        })
        present(alert, animated: true)
    }

    deinit { discovery.cancel(); probes.values.forEach { $0.cancel() } }
}
