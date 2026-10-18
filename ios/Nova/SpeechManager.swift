import AVFoundation
import Foundation
import Speech

/// On-device dictation for the mic button. Reports ("text", "start" | "result" | "end" | "error").
final class SpeechManager {
    var onEvent: ((String, String) -> Void)?

    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var lastText = ""
    private var silenceTimer: Timer?
    private var running = false

    func start(locale: String?) {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                guard status == .authorized else {
                    self.onEvent?("Allow Speech Recognition for Nova in the iPhone Settings app.", "error")
                    return
                }
                AVAudioSession.sharedInstance().requestRecordPermission { granted in
                    DispatchQueue.main.async {
                        guard granted else {
                            self.onEvent?("Allow the Microphone for Nova in the iPhone Settings app.", "error")
                            return
                        }
                        self.begin(locale: locale)
                    }
                }
            }
        }
    }

    private func begin(locale: String?) {
        stop(silent: true)
        let wanted = SFSpeechRecognizer(locale: Locale(identifier: locale ?? Locale.current.identifier))
        guard let recognizer = wanted ?? SFSpeechRecognizer(), recognizer.isAvailable else {
            onEvent?("Speech recognition isn't available right now.", "error")
            return
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)

            let req = SFSpeechAudioBufferRecognitionRequest()
            req.shouldReportPartialResults = true
            if recognizer.supportsOnDeviceRecognition {
                req.requiresOnDeviceRecognition = true   // works without internet (offline mode) and stays private
            }
            request = req

            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
                self?.request?.append(buffer)
            }
            engine.prepare()
            try engine.start()

            running = true
            lastText = ""
            onEvent?("", "start")
            task = recognizer.recognitionTask(with: req) { [weak self] result, error in
                guard let self = self else { return }
                if let result = result {
                    let text = result.bestTranscription.formattedString
                    let isFinal = result.isFinal
                    DispatchQueue.main.async {
                        guard self.running else { return }
                        self.lastText = text
                        self.onEvent?(text, "result")
                        self.armSilenceTimer(seconds: 1.6)   // stop after a short pause
                        if isFinal { self.stop() }
                    }
                }
                if error != nil {
                    DispatchQueue.main.async { self.stop() }
                }
            }
            armSilenceTimer(seconds: 6)   // nobody spoke
        } catch {
            stop(silent: true)
            onEvent?("Couldn't start the microphone.", "error")
        }
    }

    func stop(silent: Bool = false) {
        silenceTimer?.invalidate()
        silenceTimer = nil
        let wasRunning = running
        running = false
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        request = nil
        task?.cancel()
        task = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        if wasRunning && !silent { onEvent?(lastText, "end") }
    }

    private func armSilenceTimer(seconds: Double) {
        silenceTimer?.invalidate()
        silenceTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            self?.stop()
        }
    }
}
