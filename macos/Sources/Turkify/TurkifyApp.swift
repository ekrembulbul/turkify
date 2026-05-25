import AppKit
import SwiftUI

@main
struct TurkifyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @ObservedObject private var state = AppState.shared

    var body: some Scene {
        MenuBarExtra {
            MenuContent(state: state)
        } label: {
            Image(systemName: state.busy ? "hourglass" : "textformat.abc")
        }
        .menuBarExtraStyle(.menu)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)  // menü-bar uygulaması; Dock ikonu yok
        AppState.shared.startup()
    }

    func applicationWillTerminate(_ notification: Notification) {
        AppState.shared.shutdown()
    }
}

/// Uygulama durumunu ve bileşenleri (motor, kısayol, izinler) bir arada tutan koordinatör.
@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()

    @Published var busy = false
    @Published var accessibilityGranted = false
    @Published var inputMonitoringGranted = false
    @Published var engineRunning = false
    @Published var lastStatus = "Hazir"

    let config = AppConfig.load()
    private let engine = EngineClient()
    private var hotKey: HotKey?
    private lazy var corrector = Corrector(engine: engine)

    func startup() {
        refreshPermissions()
        do {
            try engine.start()
            engineRunning = engine.isRunning
            lastStatus = engineRunning ? "Motor calisiyor" : "Motor baslamadi"
        } catch {
            lastStatus = "Motor baslatilamadi: \(error)"
        }
        registerHotKey()
    }

    func shutdown() {
        engine.stop()
    }

    func refreshPermissions() {
        accessibilityGranted = Permissions.accessibilityGranted()
        inputMonitoringGranted = Permissions.inputMonitoringGranted()
    }

    private func registerHotKey() {
        guard let keyCode = HotKey.keyCode(for: config.hotkeyKey) else {
            lastStatus = "Kisayol tusu desteklenmiyor: \(config.hotkeyKey)"
            return
        }
        let modifiers = HotKey.carbonModifiers(from: config.hotkeyMods)
        hotKey = HotKey(keyCode: keyCode, modifiers: modifiers) { [weak self] in
            Task { @MainActor in await self?.correctSelection() }
        }
        if hotKey == nil { lastStatus = "Kisayol kaydedilemedi" }
    }

    func correctSelection() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let result = try await corrector.run()
            lastStatus = "Duzeltildi: " + String(result.prefix(40))
        } catch Corrector.CorrectorError.emptySelection {
            lastStatus = "Secili metin bulunamadi"
        } catch {
            lastStatus = "Hata: \(error)"
        }
    }
}

struct MenuContent: View {
    @ObservedObject var state: AppState

    var body: some View {
        Text(state.lastStatus)

        Divider()

        Button("Secili metni duzelt") {
            Task { @MainActor in await state.correctSelection() }
        }

        Divider()

        Button(permissionLabel("Erisilebilirlik", state.accessibilityGranted)) {
            Permissions.promptAccessibility()
            Permissions.openAccessibilitySettings()
        }
        Button(permissionLabel("Girdi Izleme", state.inputMonitoringGranted)) {
            Permissions.requestInputMonitoring()
            Permissions.openInputMonitoringSettings()
        }
        Button("Izinleri yenile") { state.refreshPermissions() }

        Divider()

        Text("Model: " + (state.config.model ?? "(yok)"))
        Text(state.engineRunning ? "Motor: calisiyor" : "Motor: kapali")

        Divider()

        Button("Cikis") { NSApplication.shared.terminate(nil) }
    }

    private func permissionLabel(_ name: String, _ granted: Bool) -> String {
        (granted ? "✅ " : "❌ ") + name + " izni"
    }
}
