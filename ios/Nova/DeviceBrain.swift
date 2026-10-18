import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// The AI that runs on the iPhone itself (Apple's on-device model, part of Apple Intelligence).
/// Used automatically when your PC can't be reached. Free, private, works without internet.
/// It can chat and answer questions; controlling the PC needs the PC, of course.
final class DeviceBrain {
    /// Events for the page: ["type": "stream" | "assistant" | "state" | "error", ...]
    var onEvent: (([String: Any]) -> Void)?

    private var task: Task<Void, Never>?
    private var session: AnyObject?          // LanguageModelSession (kept so it remembers the chat)
    private var sessionLang = ""
    private var counter = 0

    func ask(_ text: String, lang: String, name: String) {
        task?.cancel()
        counter += 1
        let id = "dev-\(counter)"
        task = Task { [weak self] in
            await self?.run(text, lang: lang, name: name, id: id)
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        let de = sessionLang == "de"
        send(["type": "assistant", "text": de ? "Okay, ich habe aufgehört." : "Okay, I stopped."])
        send(["type": "state", "state": "idle"])
    }

    func reset() {
        task?.cancel()
        task = nil
        session = nil
    }

    private func send(_ event: [String: Any]) {
        DispatchQueue.main.async { self.onEvent?(event) }
    }

    private func run(_ text: String, lang: String, name: String, id: String) async {
        defer { if !Task.isCancelled { send(["type": "state", "state": "idle"]) } }
        let de = lang == "de"
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            await respond(text, de: de, name: name, id: id)
            return
        }
        #endif
        send(["type": "error", "text": de
            ? "Die KI auf dem iPhone braucht iOS 26 mit Apple Intelligence. Verbinde dich mit deinem PC, um Fragen zu stellen."
            : "The AI on the iPhone needs iOS 26 with Apple Intelligence. Connect to your PC to ask questions."])
    }

    #if canImport(FoundationModels)
    @available(iOS 26.0, *)
    private func respond(_ text: String, de: Bool, name: String, id: String) async {
        let model = SystemLanguageModel.default
        if case .unavailable(let reason) = model.availability {
            let msg: String
            switch reason {
            case .deviceNotEligible:
                msg = de ? "Dieses iPhone kann die KI nicht selbst ausführen. Verbinde dich mit deinem PC."
                         : "This iPhone can't run the AI itself. Connect to your PC."
            case .appleIntelligenceNotEnabled:
                msg = de ? "Schalte Apple Intelligence in den Einstellungen ein, dann kann ich auch ohne PC antworten."
                         : "Turn on Apple Intelligence in Settings, then I can answer without your PC too."
            case .modelNotReady:
                msg = de ? "Die KI auf dem iPhone wird gerade noch geladen. Versuch es gleich noch einmal."
                         : "The AI on your iPhone is still getting ready. Try again in a moment."
            @unknown default:
                msg = de ? "Die KI auf dem iPhone ist gerade nicht verfügbar." : "The AI on your iPhone isn't available right now."
            }
            send(["type": "error", "text": msg])
            return
        }

        let lang = de ? "de" : "en"
        var current = session as? LanguageModelSession
        if current == nil || sessionLang != lang || current?.isResponding == true {
            current = LanguageModelSession(instructions: instructions(de: de, name: name))
            sessionLang = lang
        }
        guard var s = current else { return }
        session = s

        let now = DateFormatter.localizedString(from: Date(), dateStyle: .full, timeStyle: .short)
        let prompt = "\(text)\n\n(\(de ? "Jetzt" : "Now"): \(now))"
        for attempt in 0..<2 {
            do {
                let response = try await s.respond(to: prompt)
                if Task.isCancelled { return }
                let answer = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
                send(["type": "assistant", "text": answer, "id": id])
                return
            } catch let error as LanguageModelSession.GenerationError {
                if Task.isCancelled { return }
                if case .exceededContextWindowSize = error, attempt == 0 {
                    // the chat got too long for the small model: start fresh and try again
                    s = LanguageModelSession(instructions: instructions(de: de, name: name))
                    session = s
                    continue
                }
                if case .guardrailViolation = error {
                    send(["type": "assistant", "text": de ? "Dabei kann ich nicht helfen." : "I can't help with that one.", "id": id])
                } else {
                    send(["type": "error", "text": (de ? "iPhone-KI: " : "iPhone AI: ") + error.localizedDescription])
                }
                return
            } catch {
                if Task.isCancelled { return }
                send(["type": "error", "text": (de ? "iPhone-KI: " : "iPhone AI: ") + error.localizedDescription])
                return
            }
        }
    }

    private func instructions(de: Bool, name: String) -> String {
        if de {
            return """
            Du bist \(name), ein persönlicher KI-Assistent. Gerade läufst du direkt auf dem iPhone des Nutzers, \
            weil sein PC nicht erreichbar ist. Du kannst chatten, Fragen beantworten, Texte schreiben, \
            übersetzen, rechnen und Ideen liefern. Den PC steuern oder Apps öffnen kannst du jetzt nicht; \
            wenn danach gefragt wird, sag freundlich, dass das wieder geht, sobald der PC an ist. \
            Antworte immer auf Deutsch, kurz und freundlich (1-4 Sätze), ohne Überschriften. Sprich den Nutzer mit „Sir“ an.
            """
        }
        return """
        You are \(name), a personal AI assistant. Right now you run directly on the user's iPhone because \
        their PC can't be reached. You can chat, answer questions, write texts, translate, calculate and \
        give ideas. You can't control the PC or open apps right now; if asked, say kindly that this works \
        again as soon as the PC is on. Always answer in English, short and friendly (1-4 sentences), no headings. \
        Address the user as "sir".
        """
    }
    #endif
}
