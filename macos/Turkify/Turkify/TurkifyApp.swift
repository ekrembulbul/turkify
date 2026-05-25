import AppKit
import Combine
import SwiftUI

@main
struct TurkifyApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @ObservedObject private var state = AppState.shared

    var body: some Scene {
        // Menü-bar: yalnızca durum + pencere + Çıkış. Asıl arayüz ana penceredir.
        MenuBarExtra {
            MenuContent(state: state)
        } label: {
            MenuBarLabel(state: state)
        }
        .menuBarExtraStyle(.menu)

        // Ana pencere: başlık "Turkify", sekmeli (ilk sekme Ayarlar).
        Window("Turkify", id: AppState.mainWindowID) {
            MainView(state: state)
        }
        .windowResizability(.contentMinSize)  // içerik min boyutu kadar küçülür, serbest büyür
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        AppState.shared.startup()  // aktivasyon politikası startup içinde ayarlanır
    }

    func applicationWillTerminate(_ notification: Notification) {
        AppState.shared.shutdown()
    }

    /// Dock ikonuna tıklanınca (görünür pencere yoksa) ana pencereyi aç.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { AppState.shared.presentMainWindow?() }
        return true
    }
}

/// Uygulama durumunu ve bileşenleri (motor, kısayol, izinler, config) bir arada tutar.
@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()
    static let mainWindowID = "turkify-main"

    /// Ana pencereyi açan kapanış; menü-bar label'ı (her zaman canlı) tarafından
    /// `openWindow` yakalanıp buraya yazılır. AppDelegate Dock-tık'ta bunu çağırır.
    var presentMainWindow: (() -> Void)?

    @Published var busy = false
    @Published var accessibilityGranted = false
    @Published var inputMonitoringGranted = false
    @Published var engineRunning = false
    @Published var lastStatus = "Hazır"
    @Published var settings = AppSettings.load()

    private let engine = EngineClient()
    private var hotKey: HotKey?
    private lazy var corrector = Corrector(engine: engine)
    private var windowOpen = false

    var menuBarSymbol: String {
        if busy { return "hourglass" }
        return engineRunning ? "textformat.abc" : "exclamationmark.triangle"
    }

    func startup() {
        applyActivationPolicy()
        refreshPermissions()
        startEngine()
        registerHotKey()
    }

    /// Dock ikonu görünürlüğü: Ayarlar penceresi açıkken VEYA kullanıcı "Dock'ta
    /// göster" seçtiyse uygulama normal (.regular, Dock'ta) olur; aksi halde
    /// menü-bar-only (.accessory, Dock'ta yok).
    func applyActivationPolicy() {
        let policy: NSApplication.ActivationPolicy =
            (windowOpen || settings.showInDock) ? .regular : .accessory
        NSApp.setActivationPolicy(policy)
    }

    func windowAppeared() {
        windowOpen = true
        applyActivationPolicy()
        NSApp.activate(ignoringOtherApps: true)  // pencereyi öne getir
        refreshPermissions()
    }

    func windowDisappeared() {
        windowOpen = false
        applyActivationPolicy()
    }

    /// "Dock'ta göster" tercihi değişince: kaydet + politikayı uygula.
    func setShowInDock(_ value: Bool) {
        settings.showInDock = value
        settings.save()
        applyActivationPolicy()
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

        Button("Turkify'ı aç") {
            openWindow(id: AppState.mainWindowID)
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

// MARK: - Menü-bar simgesi (her zaman canlı → openWindow'u yakalar)

struct MenuBarLabel: View {
    @ObservedObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Image(systemName: state.menuBarSymbol)
            .onAppear {
                // Dock-tık (AppDelegate) ana pencereyi bu kapanışla açar.
                state.presentMainWindow = {
                    openWindow(id: AppState.mainWindowID)
                    NSApp.activate(ignoringOtherApps: true)
                }
            }
    }
}

// MARK: - Ana pencere (sekmeli; ileride sekme eklenebilir)

struct MainView: View {
    @ObservedObject var state: AppState

    var body: some View {
        TabView {
            SettingsView(state: state)
                .tabItem { Label("Ayarlar", systemImage: "gearshape") }
            StatusView(state: state)
                .tabItem { Label("Durum", systemImage: "gauge") }
            // İleride buraya yeni sekmeler eklenebilir (ör. Geçmiş, Hakkında).
        }
        // Yeniden boyutlanabilir: küçük alt sınır, serbest büyüme.
        .frame(minWidth: 440, idealWidth: 520, maxWidth: .infinity,
               minHeight: 460, idealHeight: 600, maxHeight: .infinity)
        .onAppear { state.windowAppeared() }
        .onDisappear { state.windowDisappeared() }
    }
}

// MARK: - Ayarlar sekmesi (üstte Kaydet; Kaydet-gerektiren ve anlık bölümler ayrı)

struct SettingsView: View {
    @ObservedObject var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            // Sağ üstte belirgin Kaydet — yalnızca "Motor / LLM" ayarlarını uygular.
            HStack {
                Text(state.lastStatus)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer()
                Button("Kaydet") { state.saveSettings() }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.defaultAction)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

            Divider()

            Form {
                Section {
                    Toggle("LLM kullan (Tier 3)", isOn: $state.settings.useLLM)
                    Toggle("Morfoloji (Tier 2)", isOn: $state.settings.useMorphology)
                    TextField("Model", text: $state.settings.model)
                    TextField("Sunucu (base_url)", text: $state.settings.baseURL)
                    TextField("API anahtarı", text: $state.settings.apiKey)
                    TextField("Zaman aşımı (sn)", value: $state.settings.timeout, format: .number)
                    TextField("assistant_prefill", text: $state.settings.assistantPrefill)
                } header: {
                    Text("Motor / LLM")
                } footer: {
                    Text("Bu bölümdeki değişiklikler **Kaydet** ile uygulanır (motor yeniden başlar).")
                }

                Section("Kısayol") {
                    LabeledContent("Kısayol", value: state.settings.hotkeyDescription)
                    Text("Kısayol kaydedici sonraki adımda eklenecek.")
                        .font(.caption).foregroundStyle(.secondary)
                }

                Section {
                    permissionRow("Erişilebilirlik (Accessibility)", granted: state.accessibilityGranted) {
                        Permissions.promptAccessibility()
                        Permissions.openAccessibilitySettings()
                    }
                    permissionRow("Girdi İzleme (Input Monitoring)", granted: state.inputMonitoringGranted) {
                        Permissions.requestInputMonitoring()
                        Permissions.openInputMonitoringSettings()
                    }
                    Button("İzinleri yenile") { state.refreshPermissions() }
                } header: {
                    Text("İzinler")
                } footer: {
                    Text("Anında etki eder; Kaydet gerekmez.")
                }

                Section {
                    Toggle("Dock'ta göster", isOn: Binding(
                        get: { state.settings.showInDock },
                        set: { state.setShowInDock($0) }
                    ))
                } header: {
                    Text("Görünüm")
                } footer: {
                    Text("Anında etki eder. Kapalıyken uygulama yalnızca menü-bar'da durur.")
                }
            }
            .formStyle(.grouped)
        }
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

// MARK: - Durum sekmesi (motor durumu + test)

struct StatusView: View {
    @ObservedObject var state: AppState

    var body: some View {
        Form {
            Section("Motor") {
                LabeledContent("Durum", value: state.engineRunning ? "çalışıyor" : "kapalı")
                Button("Seçili metni düzelt (test)") {
                    Task { @MainActor in await state.correctSelection() }
                }
                LabeledContent("Son işlem", value: state.lastStatus)
            }
        }
        .formStyle(.grouped)
    }
}
