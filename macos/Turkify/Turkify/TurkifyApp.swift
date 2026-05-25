import AppKit
import Combine
import SwiftUI

@main
struct TurkifyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @ObservedObject private var state = AppState.shared

    var body: some Scene {
        // Menü-bar: yalnızca durum + Ayarlar + Çıkış. Gerisi Ayarlar penceresinde.
        MenuBarExtra {
            MenuContent(state: state)
        } label: {
            Image(systemName: state.menuBarSymbol)
        }
        .menuBarExtraStyle(.menu)

        Window("Turkify Ayarlar", id: AppState.settingsWindowID) {
            SettingsView(state: state)
        }
        .windowResizability(.contentSize)
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

/// Uygulama durumunu ve bileşenleri (motor, kısayol, izinler, config) bir arada tutar.
@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()
    static let settingsWindowID = "turkify-settings"

    @Published var busy = false
    @Published var accessibilityGranted = false
    @Published var inputMonitoringGranted = false
    @Published var engineRunning = false
    @Published var lastStatus = "Hazır"
    @Published var settings = AppSettings.load()

    private let engine = EngineClient()
    private var hotKey: HotKey?
    private lazy var corrector = Corrector(engine: engine)

    var menuBarSymbol: String {
        if busy { return "hourglass" }
        return engineRunning ? "textformat.abc" : "exclamationmark.triangle"
    }

    func startup() {
        refreshPermissions()
        startEngine()
        registerHotKey()
    }

    func shutdown() {
        engine.stop()
    }

    func refreshPermissions() {
        accessibilityGranted = Permissions.accessibilityGranted()
        inputMonitoringGranted = Permissions.inputMonitoringGranted()
    }

    /// Motoru mevcut ayarlarla (yeniden) başlatır.
    private func startEngine() {
        do {
            try engine.start(settings: settings)
            engineRunning = engine.isRunning
            lastStatus = engineRunning ? "Motor çalışıyor" : "Motor başlamadı"
        } catch {
            engineRunning = false
            lastStatus = "Motor başlatılamadı: \(error)"
        }
    }

    /// Ayarları native saklar (UserDefaults), motoru yeni bayraklarla yeniden
    /// başlatır ve kısayolu yeniden kaydeder. config.json kullanılmaz (ADR 0007).
    func saveSettings() {
        settings.save()
        startEngine()
        registerHotKey()
        if engineRunning { lastStatus = "Ayarlar kaydedildi" }
    }

    private func registerHotKey() {
        hotKey = nil  // eskisini bırak (deinit unregister eder)
        guard let keyCode = HotKey.keyCode(for: settings.hotkeyKey) else {
            lastStatus = "Kısayol tuşu desteklenmiyor: \(settings.hotkeyKey)"
            return
        }
        let modifiers = HotKey.carbonModifiers(from: settings.hotkeyMods)
        hotKey = HotKey(keyCode: keyCode, modifiers: modifiers) { [weak self] in
            Task { @MainActor in await self?.correctSelection() }
        }
        if hotKey == nil { lastStatus = "Kısayol kaydedilemedi" }
    }

    func correctSelection() async {
        guard !busy else { Log.info("correctSelection: zaten mesgul, atlandi"); return }
        busy = true
        defer { busy = false }
        Log.info("correctSelection: basladi; accessibility=\(accessibilityGranted) inputMonitoring=\(inputMonitoringGranted) engineRunning=\(engine.isRunning)")
        if !accessibilityGranted {
            Log.info("correctSelection: UYARI Accessibility izni YOK -> Cmd+C/Cmd+V calismaz")
        }
        do {
            let result = try await corrector.run()
            lastStatus = "Düzeltildi: " + String(result.prefix(40))
            Log.info("correctSelection: OK -> \(result.prefix(40))")
        } catch Corrector.CorrectorError.emptySelection {
            lastStatus = "Seçili metin bulunamadı"
            Log.info("correctSelection: secim bos")
        } catch {
            lastStatus = "Hata: \(error)"
            Log.info("correctSelection: HATA \(error)")
        }
    }
}

// MARK: - Menü-bar içeriği (sade)

struct MenuContent: View {
    @ObservedObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Text(statusLine)

        Divider()

        Button("Ayarlar") {
            openWindow(id: AppState.settingsWindowID)
            NSApp.activate(ignoringOtherApps: true)
        }
        .keyboardShortcut(",", modifiers: .command)

        Button("Çıkış") { NSApplication.shared.terminate(nil) }
            .keyboardShortcut("q", modifiers: .command)
    }

    private var statusLine: String {
        if state.busy { return "Turkify — işleniyor…" }
        return state.engineRunning ? "Turkify — çalışıyor" : "Turkify — motor kapalı"
    }
}

// MARK: - Ayarlar penceresi (config düzenleme + izinler + test)

struct SettingsView: View {
    @ObservedObject var state: AppState

    var body: some View {
        Form {
            Section("Motor / LLM") {
                Toggle("LLM kullan (Tier 3)", isOn: $state.settings.useLLM)
                Toggle("Morfoloji (Tier 2)", isOn: $state.settings.useMorphology)
                TextField("Model", text: $state.settings.model)
                TextField("Sunucu (base_url)", text: $state.settings.baseURL)
                TextField("API anahtarı", text: $state.settings.apiKey)
                TextField("Zaman aşımı (sn)", value: $state.settings.timeout, format: .number)
                TextField("assistant_prefill", text: $state.settings.assistantPrefill)
            }

            Section("Kısayol") {
                LabeledContent("Kısayol", value: state.settings.hotkeyDescription)
                Text("Kısayol kaydedici sonraki adımda eklenecek.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("İzinler") {
                permissionRow("Erişilebilirlik (Accessibility)", granted: state.accessibilityGranted) {
                    Permissions.promptAccessibility()
                    Permissions.openAccessibilitySettings()
                }
                permissionRow("Girdi İzleme (Input Monitoring)", granted: state.inputMonitoringGranted) {
                    Permissions.requestInputMonitoring()
                    Permissions.openInputMonitoringSettings()
                }
                Button("İzinleri yenile") { state.refreshPermissions() }
            }

            Section("Durum / Test") {
                LabeledContent("Motor", value: state.engineRunning ? "çalışıyor" : "kapalı")
                Button("Seçili metni düzelt (test)") {
                    Task { @MainActor in await state.correctSelection() }
                }
                Text(state.lastStatus).font(.caption).foregroundStyle(.secondary)
            }

            Section {
                Button("Kaydet") { state.saveSettings() }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .formStyle(.grouped)
        .frame(width: 420, height: 560)
        .onAppear { state.refreshPermissions() }
    }

    @ViewBuilder
    private func permissionRow(
        _ name: String, granted: Bool, action: @escaping () -> Void
    ) -> some View {
        HStack {
            Text(granted ? "✅" : "❌")
            Text(name)
            Spacer()
            Button("Aç") { action() }
        }
    }
}
