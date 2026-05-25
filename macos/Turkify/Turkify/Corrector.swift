import AppKit
import CoreGraphics

/// Pano okuma/yazma + tuş simülasyonu (Cmd+C / Cmd+V).
enum Clipboard {
    static func read() -> String? {
        NSPasteboard.general.string(forType: .string)
    }

    static func write(_ text: String) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
    }

    /// US-ANSI sanal tuş kodları: c = 8, v = 9.
    private static func sendCommandKey(_ keyCode: CGKeyCode) {
        let source = CGEventSource(stateID: .combinedSessionState)
        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: true)
        keyDown?.flags = .maskCommand
        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: false)
        keyUp?.flags = .maskCommand
        keyDown?.post(tap: .cgAnnotatedSessionEventTap)
        keyUp?.post(tap: .cgAnnotatedSessionEventTap)
    }

    static func copy() { sendCommandKey(8) }
    static func paste() { sendCommandKey(9) }
}

/// Seçili metni düzeltme akışı: kopyala → motora gönder → yapıştır → eski panoyu geri yükle.
///
/// `agent.correct_clipboard_selection` (Python) ile aynı mantık; native tarafta.
struct Corrector {
    let engine: EngineClient

    enum CorrectorError: Error { case emptySelection }

    /// Akışı çalıştırır. Düzeltilmiş metni döndürür; seçim boşsa hata atar.
    @discardableResult
    func run() async throws -> String {
        let original = Clipboard.read()
        Log.info("akis: basladi; orijinal pano = \(snippet(original))")

        Clipboard.copy()
        Log.info("akis: Cmd+C gonderildi (Accessibility yoksa sessizce etkisizdir)")
        try await Task.sleep(nanoseconds: 150_000_000)  // panonun güncellenmesi için

        let selected = Clipboard.read()
        Log.info("akis: kopya sonrasi pano = \(snippet(selected))")
        guard let selected, !selected.isEmpty else {
            Log.info("akis: secim BOS -> durduruldu")
            throw CorrectorError.emptySelection
        }
        if selected == original {
            Log.info("akis: UYARI pano degismedi (Cmd+C islememis olabilir; eski pano duzeltilecek)")
        }

        Log.info("akis: motora gonderiliyor…")
        let corrected = try await engine.correct(selected)
        Log.info("akis: motordan donen = \(snippet(corrected))")

        Clipboard.write(corrected)
        try await Task.sleep(nanoseconds: 50_000_000)
        Clipboard.paste()
        Log.info("akis: Cmd+V gonderildi")
        try await Task.sleep(nanoseconds: 200_000_000)  // yapıştırma tamamlansın

        if let original {
            Clipboard.write(original)  // kullanıcının panosunu geri yükle
        }
        Log.info("akis: tamam")
        return corrected
    }

    private func snippet(_ text: String?) -> String {
        guard let text else { return "nil" }
        return "'" + text.prefix(40).replacingOccurrences(of: "\n", with: "\\n") + "'"
    }
}
