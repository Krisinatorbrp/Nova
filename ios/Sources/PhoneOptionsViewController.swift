import UIKit

/// "This phone · screen & sleep": display settings for this iPhone only.
final class PhoneOptionsViewController: UITableViewController {
    var onChange: ((DisplayPolicy) -> Void)?
    private var policy: DisplayPolicy
    private let defaults: UserDefaults

    init(defaults: UserDefaults) {
        self.defaults = defaults
        policy = PhoneSettings.display(defaults)
        super.init(style: .insetGrouped)
        title = "This phone"
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        overrideUserInterfaceStyle = .dark
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "cell")
        navigationItem.rightBarButtonItem = UIBarButtonItem(systemItem: .done, primaryAction: UIAction { [weak self] _ in
            self?.dismiss(animated: true)
        })
    }

    override func numberOfSections(in tableView: UITableView) -> Int { 3 }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        [DisplayPolicy.dimLabels.count, DisplayPolicy.dimLevels.count, DisplayPolicy.sleepLabels.count][section]
    }

    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        ["Dim after inactivity", "Dim brightness", "Screen off"][section]
    }

    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        switch section {
        case 0: return "Display settings for this phone only. Your PC display is unchanged."
        case 2: return "At a timed limit, the dock goes black and lets iOS Auto-Lock turn the screen off "
            + "(Settings → Display & Brightness → Auto-Lock may add a delay). Tap to return while the screen is still on. "
            + "Lower brightness and screen breaks reduce display wear, but cannot guarantee that burn-in never happens. "
            + "Stay awake keeps the display on only while the dock is visible."
        default: return nil
        }
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "cell", for: indexPath)
        var content = cell.defaultContentConfiguration()
        let selected: Bool
        switch indexPath.section {
        case 0:
            content.text = DisplayPolicy.dimLabels[indexPath.row]
            selected = policy.dimAfter == DisplayPolicy.dimTimes[indexPath.row]
        case 1:
            content.text = "\(DisplayPolicy.dimLevels[indexPath.row])%"
            selected = policy.dimPercent == DisplayPolicy.dimLevels[indexPath.row]
        default:
            content.text = DisplayPolicy.sleepLabels[indexPath.row]
            selected = policy.sleepAfter == DisplayPolicy.sleepTimes[indexPath.row]
        }
        cell.contentConfiguration = content
        cell.accessoryType = selected ? .checkmark : .none
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        switch indexPath.section {
        case 0: policy.dimAfter = DisplayPolicy.dimTimes[indexPath.row]
        case 1: policy.dimPercent = DisplayPolicy.dimLevels[indexPath.row]
        default: policy.sleepAfter = DisplayPolicy.sleepTimes[indexPath.row]
        }
        PhoneSettings.save(policy, defaults)
        onChange?(policy)
        tableView.reloadSections(IndexSet(integer: indexPath.section), with: .none)
    }
}
