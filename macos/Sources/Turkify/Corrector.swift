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

        Clipboard.copy()
        try await Task.sleep(nanoseconds: 150_000_000)  // panonun güncellenmesi için

        guard let selected = Clipboard.read(), !selected.isEmpty else {
            throw CorrectorError.emptySelection
        }

        let corrected = try await engine.correct(selected)

        Clipboard.write(corrected)
        try await Task.sleep(nanoseconds: 50_000_000)
        Clipboard.paste()
        try await Task.sleep(nanoseconds: 200_000_000)  // yapıştırma tamamlansın

        if let original {
            Clipboard.write(original)  // kullanıcının panosunu geri yükle
        }
        return corrected
    }
}
