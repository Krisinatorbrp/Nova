import UIKit

/// Dims the screen after inactivity, then rests behind a black cover so iOS Auto-Lock
/// can turn the display off (Android `IdleDisplayController`). Only active while the
/// dock is visible. iOS brightness is system-wide, so it is always restored when the
/// dock stops being active or the app leaves the foreground.
final class IdleDisplayController {
    private(set) var policy: DisplayPolicy
    private(set) var stage: DisplayPolicy.Stage = .awake
    private(set) var active = false
    var onRest: (() -> Void)?

    private let cover: UIView
    private var lastInput = CACurrentMediaTime()
    private var timer: Timer?
    private var savedBrightness: CGFloat?

    init(policy: DisplayPolicy, cover: UIView) {
        self.policy = policy
        self.cover = cover
        cover.isHidden = true
    }

    func setActive(_ enabled: Bool) {
        guard active != enabled else { return }
        active = enabled
        lastInput = CACurrentMediaTime()
        refresh()
    }

    func reload(_ policy: DisplayPolicy) {
        self.policy = policy
        userActivity()
    }

    /// Returns true when this input woke a dimmed or resting screen; that touch is
    /// consumed so it does not also press something in the dock.
    @discardableResult
    func userActivity() -> Bool {
        guard active else { return false }
        let waking = stage != .awake
        lastInput = CACurrentMediaTime()
        if waking || timer == nil { refresh() }
        return waking
    }

    private func refresh() {
        timer?.invalidate()
        timer = nil
        let elapsed = max(0, CACurrentMediaTime() - lastInput)
        let previous = stage
        stage = active ? policy.stage(elapsed) : .awake
        if stage == .resting && previous != .resting { onRest?() }

        cover.isHidden = stage != .resting
        if stage == .resting { cover.superview?.bringSubviewToFront(cover) }
        UIApplication.shared.isIdleTimerDisabled = active && policy.keepsAwake(stage)
        applyBrightness()

        if active, stage != .resting, let deadline = policy.nextDeadline(elapsed) {
            let timer = Timer(timeInterval: max(0.05, deadline - elapsed), repeats: false) { [weak self] _ in
                self?.timer = nil
                self?.refresh()
            }
            RunLoop.main.add(timer, forMode: .common)
            self.timer = timer
        }
    }

    private func applyBrightness() {
        let screen = UIScreen.main
        switch stage {
        case .awake:
            if let saved = savedBrightness { screen.brightness = saved }
            savedBrightness = nil
        case .dimmed, .resting:
            if savedBrightness == nil { savedBrightness = screen.brightness }
            let target = stage == .resting ? 0 : min(savedBrightness ?? screen.brightness, CGFloat(policy.dimPercent) / 100)
            if abs(screen.brightness - target) > 0.001 { screen.brightness = target }
        }
    }

    deinit {
        timer?.invalidate()
        if let saved = savedBrightness { UIScreen.main.brightness = saved }
    }
}

/// Reports every touch and hardware key to the idle controller before UIKit routes it.
final class ActivityWindow: UIWindow {
    /// Return true to consume the touch sequence that just began.
    var onActivity: (() -> Bool)?
    private var consuming = false

    override func sendEvent(_ event: UIEvent) {
        if event.type == .touches, let touches = event.allTouches, !touches.isEmpty {
            if touches.contains(where: { $0.phase == .began }) {
                if onActivity?() == true { consuming = true }
            } else if touches.contains(where: { $0.phase == .moved }) {
                _ = onActivity?()
            }
            if consuming {
                if touches.allSatisfy({ $0.phase == .ended || $0.phase == .cancelled }) { consuming = false }
                return
            }
        } else if event.type == .presses {
            _ = onActivity?()
        }
        super.sendEvent(event)
    }
}
