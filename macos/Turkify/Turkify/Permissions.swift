import AppKit
import ApplicationServices

/// macOS izin kontrolleri ve ilgili System Settings panellerini açma.
///
/// - **Accessibility (Erişilebilirlik):** tuş simülasyonu (Cmd+C / Cmd+V) için gerekir.
///
/// Global kısayol Carbon `RegisterEventHotKey` ile dinlenir ve kayıt UI'ı yerel
/// `NSEvent` monitörü kullanır; ikisi de **Input Monitoring** izni gerektirmez,
/// bu yüzden yalnızca Erişilebilirlik istenir.
///
/// Apple, izni programatik **vermeye** izin vermez; biz yalnızca durumu okur ve
/// ilgili paneli açarız — son anahtarı kullanıcı çevirir.
enum Permissions {
    static func accessibilityGranted() -> Bool {
        AXIsProcessTrusted()
    }

    /// macOS'un kendi izin istemini (prompt) tetikler.
    static func promptAccessibility() {
        let key = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        _ = AXIsProcessTrustedWithOptions([key: true] as CFDictionary)
    }

    static func openAccessibilitySettings() {
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    }

    private static func open(_ urlString: String) {
        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}
