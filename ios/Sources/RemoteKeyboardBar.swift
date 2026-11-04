import UIKit

/// The native typing strip shown above the iOS keyboard while a PC text field has focus.
/// Text is forwarded as soon as it is committed (after IME composition), and editing
/// keys go to the PC — the same contract as Android's `RemoteKeyboardEditor`.
final class RemoteKeyboardBar: UIView, UITextFieldDelegate {
    var onText: ((String) -> Void)?
    var onKey: ((String) -> Void)?
    var onClose: (() -> Void)?
    var onSignature: (() -> Void)?
    var onActivity: (() -> Void)?

    private let field = RemoteTextField()
    private var hiding = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = UIColor(red: 0x10 / 255, green: 0x17 / 255, blue: 0x22 / 255, alpha: 1)
        isHidden = true

        var hideConfig = UIButton.Configuration.plain()
        hideConfig.image = UIImage(systemName: "keyboard.chevron.compact.down")
        hideConfig.baseForegroundColor = .white
        let hide = UIButton(configuration: hideConfig, primaryAction: UIAction { [weak self] _ in
            guard let self else { return }
            self.commit()
            self.onClose?()
        })
        hide.accessibilityLabel = "Hide keyboard"

        var signConfig = UIButton.Configuration.gray()
        signConfig.title = "Sign"
        signConfig.baseForegroundColor = .white
        let sign = UIButton(configuration: signConfig, primaryAction: UIAction { [weak self] _ in
            guard let self else { return }
            self.commit()
            self.onSignature?()
        })
        sign.accessibilityLabel = "Draw and insert a signature"

        field.placeholder = "Type on PC…"
        field.attributedPlaceholder = NSAttributedString(string: "Type on PC…", attributes: [.foregroundColor: UIColor(white: 1, alpha: 0.45)])
        field.textColor = .white
        field.tintColor = UIColor(red: 0.51, green: 0.91, blue: 0.75, alpha: 1)
        field.backgroundColor = UIColor.white.withAlphaComponent(0.08)
        field.layer.cornerRadius = 10
        field.leftView = UIView(frame: CGRect(x: 0, y: 0, width: 12, height: 1))
        field.leftViewMode = .always
        field.returnKeyType = .default
        field.keyboardAppearance = .dark
        field.autocorrectionType = .no
        field.autocapitalizationType = .none
        field.spellCheckingType = .no
        field.smartQuotesType = .no
        field.smartDashesType = .no
        field.smartInsertDeleteType = .no
        field.accessibilityIdentifier = "remote-keyboard"
        field.delegate = self
        field.addTarget(self, action: #selector(changed), for: .editingChanged)
        field.onDeleteWhenEmpty = { [weak self] in self?.onActivity?(); self?.onKey?("Backspace") }
        field.onSpecialKey = { [weak self] key in self?.commit(); self?.onActivity?(); self?.onKey?(key) }

        let row = UIStackView(arrangedSubviews: [hide, field, sign])
        row.spacing = 8
        row.alignment = .center
        row.translatesAutoresizingMaskIntoConstraints = false
        addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: safeAreaLayoutGuide.leadingAnchor, constant: 8),
            row.trailingAnchor.constraint(equalTo: safeAreaLayoutGuide.trailingAnchor, constant: -8),
            row.centerYAnchor.constraint(equalTo: centerYAnchor),
            hide.widthAnchor.constraint(equalToConstant: 48),
            sign.widthAnchor.constraint(equalToConstant: 72),
            field.heightAnchor.constraint(equalToConstant: 40)
        ])
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    var isActive: Bool { !isHidden }

    func show(password: Bool) {
        if field.isSecureTextEntry != password {
            field.resignFirstResponder()
            field.isSecureTextEntry = password
        }
        isHidden = false
        hiding = false
        field.becomeFirstResponder()
    }

    /// Hides without telling the page (the page asked, or the dock is going away).
    func hide() {
        hiding = true
        field.unmarkText()
        field.text = ""
        field.resignFirstResponder()
        isHidden = true
        hiding = false
    }

    /// Sends text that is still being composed (for example before Hide or Sign).
    func commit() {
        field.unmarkText()
        send()
    }

    private func send() {
        guard field.markedTextRange == nil, let text = field.text, !text.isEmpty else { return }
        field.text = ""
        onActivity?()
        // The page accepts up to 1024 characters per message.
        var rest = Substring(text)
        while !rest.isEmpty {
            let chunk = rest.prefix(1000)
            onText?(String(chunk))
            rest = rest.dropFirst(chunk.count)
        }
    }

    @objc private func changed() { send() }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        commit()
        onActivity?()
        onKey?("Enter")
        return false
    }

    func textFieldDidEndEditing(_ textField: UITextField) {
        // Keyboard dismissed by iOS (for example a hardware keyboard toggle): close like "Hide".
        guard !hiding, !isHidden else { return }
        commit()
        onClose?()
    }
}

/// Reports Backspace on an empty field and hardware editing keys.
final class RemoteTextField: UITextField {
    var onDeleteWhenEmpty: (() -> Void)?
    var onSpecialKey: ((String) -> Void)?

    override func deleteBackward() {
        if markedTextRange == nil && (text ?? "").isEmpty { onDeleteWhenEmpty?(); return }
        super.deleteBackward()
    }

    private static let keys: [UIKeyboardHIDUsage: String] = [
        .keyboardLeftArrow: "ArrowLeft", .keyboardRightArrow: "ArrowRight",
        .keyboardUpArrow: "ArrowUp", .keyboardDownArrow: "ArrowDown",
        .keyboardTab: "Tab", .keyboardEscape: "Escape", .keyboardDeleteForward: "Delete"
    ]

    override func pressesBegan(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        var handled = false
        if markedTextRange == nil {
            for press in presses {
                if let code = press.key?.keyCode, let key = Self.keys[code], press.key?.modifierFlags.isDisjoint(with: [.command, .control, .alternate]) ?? true {
                    onSpecialKey?(key)
                    handled = true
                }
            }
        }
        if !handled { super.pressesBegan(presses, with: event) }
    }
}
