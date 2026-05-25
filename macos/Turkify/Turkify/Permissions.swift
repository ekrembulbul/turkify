import AppKit
import ApplicationServices
import IOKit.hid

/// macOS izin kontrolleri ve ilgili System Settings panellerini açma.
///
/// - **Accessibility (Erişilebilirlik):** tuş simülasyonu (Cmd+C / Cmd+V) için gerekir.
/// - **Input Monitoring (Girdi İzleme):** global kısayolu dinlemek için gerekebilir.
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

    static func inputMonitoringGranted() -> Bool {
        IOHIDCheckAccess(kIOHIDRequestTypeListenEvent) == kIOHIDAccessTypeGranted
    }

    /// Input Monitoring iznini ister (macOS prompt'unu tetikleyebilir).
    static func requestInputMonitoring() {
        _ = IOHIDRequestAccess(kIOHIDRequestTypeListenEvent)
    }

    static func openAccessibilitySettings() {
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
    }

    static func openInputMonitoringSettings() {
        open("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")
    }

    private static func open(_ urlString: String) {
        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}
