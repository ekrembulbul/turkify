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
    @Published var discoveredBackends: [DiscoveredBackend] = []
    @Published var logLines: [LogLine] = []
    @Published var spinnerAngle: Double = 0  // busy iken menü-bar ikonunu döndürür

    private let engine = EngineClient()
    private var hotKey: HotKey?
    private lazy var corrector = Corrector(engine: engine)
    private var windowOpen = false
    private var spinnerTimer: Timer?
    private var correctionTask: Task<Void, Never>?

    /// İşlem göstergesi: ProgressView menü-bar'da animasyon yapmaz; bu yüzden
    /// timer ile açıyı güncelleyip ikonu döndürürüz (her tick yeni bir kare).
    private func startSpinner() {
        spinnerTimer?.invalidate()
        spinnerTimer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.spinnerAngle += 30 }
        }
    }

    private func stopSpinner() {
        spinnerTimer?.invalidate()
        spinnerTimer = nil
        spinnerAngle = 0
    }

    private static let logTimeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss.SSS"
        return f
    }()

    /// Log satırını (zaman damgalı) UI deposuna ekler; son 1000 satır tutulur.
    func appendLog(_ message: String) {
        let stamped = "\(Self.logTimeFormatter.string(from: Date())) \(message)"
        logLines.append(LogLine(text: stamped))
        if logLines.count > 1000 { logLines.removeFirst(logLines.count - 1000) }
    }

    /// İdle/durum ikonu (busy iken spinner gösterilir; bkz. MenuBarLabel).
    var menuBarSymbol: String {
        engineRunning ? "textformat" : "exclamationmark.triangle"
    }

    func startup() {
        // Log'ları UI'ya yönlendir (her thread'den çağrılabilir → main'e geç).
        Log.sink = { message in
            Task { @MainActor in AppState.shared.appendLog(message) }
        }
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
        Task { await discoverModels() }
    }

    /// Yerel sunucuları tarayıp modelleri türlerine göre listeler.
    func discoverModels() async {
        discoveredBackends = await ModelDiscovery.discover()
    }

    /// Combobox'tan model seçimi: modeli ve sunucu adresini birlikte ayarlar
    /// (Kaydet ile uygulanır).
    func selectModel(_ model: String, baseURL: String) {
        settings.model = model
        settings.baseURL = baseURL
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
            Task { @MainActor in self?.requestCorrection() }
        }
        if hotKey == nil { lastStatus = "Kısayol kaydedilemedi" }
    }

    /// Düzeltmeyi iptal edilebilir bir görev olarak başlatır (kısayol/test çağırır).
    func requestCorrection() {
        guard !busy else { return }
        correctionTask = Task { await correctSelection() }
    }

    /// Devam eden düzeltmeyi iptal eder (LLM beklemesi dahil).
    func cancelCorrection() {
        correctionTask?.cancel()
    }

    func correctSelection() async {
        guard !busy else { Log.info("correctSelection: zaten mesgul, atlandi"); return }
        busy = true
        startSpinner()
        defer { busy = false; stopSpinner(); correctionTask = nil }
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
        } catch is CancellationError {
            lastStatus = "İşlem iptal edildi"
            Log.info("correctSelection: iptal edildi")
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

        // İptal seçeneği her zaman görünür; işlem yokken pasif (kullanıcıya
        // bu yeteneğin var olduğunu bildirir).
        Button("İşlemi iptal et") { state.cancelCorrection() }
            .disabled(!state.busy)

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
        content
            .onAppear {
                // Dock-tık (AppDelegate) ana pencereyi bu kapanışla açar.
                state.presentMainWindow = {
                    openWindow(id: AppState.mainWindowID)
                    NSApp.activate(ignoringOtherApps: true)
                }
            }
    }

    @ViewBuilder
    private var content: some View {
        if state.busy {
            // İşlem (LLM) sürerken dönen gösterge. ProgressView menü-bar'da
            // animasyon yapmadığı için timer-güdümlü dönen bir SF Symbol kullanıyoruz.
            Image(systemName: "rays")
                .rotationEffect(.degrees(state.spinnerAngle))
        } else {
            Image(systemName: state.menuBarSymbol)
        }
    }
}

// MARK: - Ana pencere (sekmeli; ileride sekme eklenebilir)

struct MainView: View {
    @ObservedObject var state: AppState

    var body: some View {
        TabView {
            SettingsView(state: state)
                .tabItem { Label("Motor Ayarları", systemImage: "cpu") }
            OtherSettingsView(state: state)
                .tabItem { Label("Diğer Ayarlar", systemImage: "slider.horizontal.3") }
            LogView(state: state)
                .tabItem { Label("Log", systemImage: "doc.plaintext") }
        }
        // .contentMinSize ilk boyutu idealWidth/idealHeight'ten alır → geniş açılır;
        // minWidth ile küçültülebilir, maxWidth .infinity ile büyütülebilir.
        .frame(minWidth: 440, idealWidth: 680, maxWidth: .infinity,
               minHeight: 460, idealHeight: 660, maxHeight: .infinity)
        .onAppear { state.windowAppeared() }
        .onDisappear { state.windowDisappeared() }
    }
}

// MARK: - Motor Ayarları sekmesi (üstte Kaydet; tüm alanlar Kaydet ile uygulanır)

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
                Section("Katmanlar") {
                    Toggle("Morfoloji (Tier 2)", isOn: $state.settings.useMorphology)
                    Toggle("LLM kullan (Tier 3)", isOn: $state.settings.useLLM)
                }

                Section {
                    // Mod: Otomatik (combobox) veya Manuel (elle).
                    Picker("Model seçimi", selection: $state.settings.autoModelSelection) {
                        Text("Otomatik").tag(true)
                        Text("Manuel").tag(false)
                    }
                    .pickerStyle(.segmented)

                    if state.settings.autoModelSelection {
                        // Bulunan yerel modeller (Ollama / LM Studio / …) — tür başlıklarıyla.
                        HStack {
                            Menu {
                                if state.discoveredBackends.isEmpty {
                                    Text("Model bulunamadı")
                                }
                                ForEach(state.discoveredBackends) { backend in
                                    Section(backend.name) {
                                        ForEach(backend.models, id: \.self) { model in
                                            Button(model) {
                                                state.selectModel(model, baseURL: backend.baseURL)
                                            }
                                        }
                                    }
                                }
                            } label: {
                                Label(
                                    state.settings.model.isEmpty ? "Model seç" : state.settings.model,
                                    systemImage: "cpu"
                                )
                            }
                            Button {
                                Task { await state.discoverModels() }
                            } label: {
                                Image(systemName: "arrow.clockwise")
                            }
                            .help("Yerel modelleri yeniden tara")
                        }
                    }

                    // Otomatik modda model/sunucu salt-okunur (combobox doldurur).
                    TextField("Model", text: $state.settings.model)
                        .disabled(state.settings.autoModelSelection)
                    TextField("Sunucu (base_url)", text: $state.settings.baseURL)
                        .disabled(state.settings.autoModelSelection)
                    TextField("API anahtarı", text: $state.settings.apiKey)
                    LabeledContent("Zaman aşımı (sn)") {
                        HStack(spacing: 8) {
                            TextField("", value: $state.settings.timeout, format: .number)
                                .labelsHidden()
                                .frame(width: 60)
                                .multilineTextAlignment(.trailing)
                            Stepper("", value: $state.settings.timeout, in: 5...600, step: 5)
                                .labelsHidden()
                        }
                    }
                } header: {
                    Text("LLM bağlantısı (Tier 3)")
                } footer: {
                    Text(state.settings.autoModelSelection
                         ? "Otomatik: combobox'tan model seç; model ve sunucu otomatik dolar (salt-okunur)."
                         : "Manuel: model ve sunucu adresini elle gir.")
                }

                Section {
                    codeEditor(text: $state.settings.assistantPrefill, minHeight: 60)
                } header: {
                    Text("assistant_prefill")
                } footer: {
                    Text("İsteğe eklenecek asistan metni. Düşünmeyi kapatmak için: `<think>\\n\\n</think>\\n\\n`")
                }

                Section {
                    codeEditor(text: $state.settings.llmOptions, minHeight: 90)
                    if !AppSettings.isValidJSON(state.settings.llmOptions) {
                        Label("Geçersiz JSON — kaydedilse de motora gönderilmez.", systemImage: "exclamationmark.triangle")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                } header: {
                    Text("llm_options (JSON)")
                } footer: {
                    Text("İsteğin gövdesine eklenecek JSON. Ör: `{\"chat_template_kwargs\":{\"enable_thinking\":false}}`")
                }
            }
            .formStyle(.grouped)
        }
    }

    /// Kod (monospace) fontlu, çok satırlı giriş alanı — JSON / prefill için.
    private func codeEditor(text: Binding<String>, minHeight: CGFloat) -> some View {
        TextEditor(text: text)
            .font(.system(.body, design: .monospaced))
            .frame(minHeight: minHeight)
            .padding(4)
            .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(.quaternary))
    }
}

// MARK: - Diğer Ayarlar sekmesi (Kaydet YOK; anlık kontroller + durum)

struct OtherSettingsView: View {
    @ObservedObject var state: AppState

    var body: some View {
        Form {
            Section("Durum") {
                LabeledContent("Motor", value: state.engineRunning ? "çalışıyor" : "kapalı")
                Button("Seçili metni düzelt (test)") {
                    state.requestCorrection()
                }
                .disabled(state.busy)
                LabeledContent("Son işlem", value: state.lastStatus)
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

            Section("Kısayol") {
                LabeledContent("Kısayol", value: state.settings.hotkeyDescription)
                Text("Kısayol kaydedici sonraki adımda eklenecek.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
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

// MARK: - Log sekmesi (canlı; yeni satırlar anında düşer)

struct LogLine: Identifiable {
    let id = UUID()
    let text: String
}

struct LogView: View {
    @ObservedObject var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("\(state.logLines.count) satır")
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button("Temizle") { state.logLines.removeAll() }
            }
            .padding(.horizontal)
            .padding(.vertical, 6)

            Divider()

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 1) {
                        ForEach(state.logLines) { line in
                            Text(line.text)
                                .font(.system(.caption, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .id(line.id)
                        }
                    }
                    .padding(8)
                }
                .onChange(of: state.logLines.count) { _ in
                    // Yeni satır gelince en alta kaydır (canlı akış).
                    if let last = state.logLines.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }
}
