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
    @Published var engineRunning = false
    @Published var lastStatus = "Hazır"
    @Published var settings = AppSettings.load()
    @Published var discoveredBackends: [DiscoveredBackend] = []
    @Published var logLines: [LogLine] = []
    @Published var spinnerAngle: Double = 0  // busy iken menü-bar ikonunu döndürür

    /// Kısayol kaydedicinin hangi kısayolu beklediği (nil = kayıt yok).
    enum HotkeyTarget { case correction, cancel }
    @Published var recordingTarget: HotkeyTarget?
    /// Kayıt sırasında geçersiz kombinasyon uyarısı (nil = uyarı yok).
    @Published var recordingError: String?

    private let engine = EngineClient()
    private var hotKey: HotKey?
    private var cancelHotKey: HotKey?
    private var hotkeyRecordMonitor: Any?
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

    /// Log satırını (zaman damgalı, kaynak etiketli) UI deposuna ekler; son 1000
    /// satır tutulur.
    func appendLog(_ source: Log.Source, _ message: String) {
        let stamp = Self.logTimeFormatter.string(from: Date())
        logLines.append(LogLine(time: stamp, source: source, text: message))
        if logLines.count > 1000 { logLines.removeFirst(logLines.count - 1000) }
    }

    /// İdle/durum ikonu (busy iken spinner gösterilir; bkz. MenuBarLabel).
    var menuBarSymbol: String {
        engineRunning ? "textformat" : "exclamationmark.triangle"
    }

    func startup() {
        // Log'ları UI'ya yönlendir (her thread'den çağrılabilir → main'e geç).
        Log.sink = { source, message in
            Task { @MainActor in AppState.shared.appendLog(source, message) }
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
        if recordingTarget != nil { stopHotkeyRecording() }  // yarıda kalan kaydı temizle
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
    /// Kaydetme her zaman başarılıdır (UserDefaults); ``true`` döner.
    @discardableResult
    func saveSettings() -> Bool {
        settings.save()
        startEngine()
        registerHotKey()
        lastStatus = engineRunning ? "Ayarlar kaydedildi" : "Ayarlar kaydedildi (motor başlamadı)"
        return true
    }

    // MARK: - Korumalı kelimeler (paylaşılan dosya — ADR 0008)

    /// Kullanıcı korumalı-kelime dosyasının yolu. Motorun okuduğu standart konumla
    /// AYNI olmalı: `$XDG_CONFIG_HOME`/turkify ya da `~/.config/turkify`. Motor bu
    /// yolu `config.protected_words_path` ile aynı mantıkla çözer (bkz. ADR 0008).
    static func protectedWordsFileURL() -> URL {
        let env = ProcessInfo.processInfo.environment
        let base: URL
        if let xdg = env["XDG_CONFIG_HOME"], !xdg.isEmpty {
            base = URL(fileURLWithPath: xdg, isDirectory: true)
        } else {
            base = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".config", isDirectory: true)
        }
        return base.appendingPathComponent("turkify", isDirectory: true)
            .appendingPathComponent("protected_words.txt")
    }

    /// Dosyadaki korumalı kelimeleri okur (yoksa boş döner).
    func loadProtectedWords() -> String {
        (try? String(contentsOf: Self.protectedWordsFileURL(), encoding: .utf8)) ?? ""
    }

    /// Korumalı kelimeleri standart paylaşılan dosyaya yazar ve motora reload
    /// gönderir. Yalnızca bu dosyadaki kelimeler korunur (motor sıcak kalır; ADR 0008).
    /// Başarılıysa ``true``, dosya yazılamazsa ``false`` döner.
    @discardableResult
    func saveProtectedWords(_ text: String) -> Bool {
        let url = Self.protectedWordsFileURL()
        do {
            try FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true
            )
            try text.write(to: url, atomically: true, encoding: .utf8)
            engine.reload()
            lastStatus = "Korumalı kelimeler kaydedildi"
            return true
        } catch {
            lastStatus = "Korumalı kelimeler kaydedilemedi: \(error.localizedDescription)"
            return false
        }
    }

    // MARK: - Metin düzeltme (Düzeltme sekmesi; pano akışından bağımsız)

    /// Verilen metni motora gönderip düzeltilmiş halini döndürür. Görev iptal
    /// edilirse ``CancellationError`` fırlatır (motor isteği bırakılır).
    func correctText(_ text: String) async throws -> String {
        try await engine.correct(text)
    }

    /// Metni sistem panosuna yazar.
    func copyToClipboard(_ text: String) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
    }

    private func registerHotKey() {
        // Eskileri bırak (deinit unregister eder).
        hotKey = nil
        cancelHotKey = nil

        // Düzeltme kısayolu.
        if let keyCode = HotKey.keyCode(for: settings.hotkeyKey) {
            let modifiers = HotKey.carbonModifiers(from: settings.hotkeyMods)
            hotKey = HotKey(keyCode: keyCode, modifiers: modifiers) { [weak self] in
                Task { @MainActor in self?.requestCorrection() }
            }
            if hotKey == nil { lastStatus = "Düzeltme kısayolu kaydedilemedi" }
        } else {
            lastStatus = "Kısayol tuşu desteklenmiyor: \(settings.hotkeyKey)"
        }

        // İptal kısayolu.
        if let cancelCode = HotKey.keyCode(for: settings.cancelHotkeyKey) {
            let cancelMods = HotKey.carbonModifiers(from: settings.cancelHotkeyMods)
            cancelHotKey = HotKey(keyCode: cancelCode, modifiers: cancelMods) { [weak self] in
                Task { @MainActor in self?.cancelCorrection() }
            }
            if cancelHotKey == nil { lastStatus = "İptal kısayolu kaydedilemedi" }
        }
    }

    // MARK: - Kısayol kaydedici

    /// Kaydı başlatır: global kısayolları geçici durdurur (kayıt sırasında
    /// tetiklenmesinler) ve uygulamaya gelen tuşları yakalamak için yerel bir
    /// NSEvent monitörü kurar. Yerel monitör yalnızca odaktaki kendi penceremize
    /// gelen olayları görür — Girdi İzleme izni gerekmez.
    func startHotkeyRecording(_ target: HotkeyTarget) {
        hotKey = nil
        cancelHotKey = nil
        recordingError = nil
        recordingTarget = target
        hotkeyRecordMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            self?.handleRecordingEvent(event)
            return nil  // olayı yut (başka yere yazılmasın)
        }
    }

    /// Kaydı bitirir: monitörü kaldırır ve global kısayolları yeniden kaydeder
    /// (kaydedilen yeni değer ya da iptalde eski değer geçerli olur).
    func stopHotkeyRecording() {
        if let monitor = hotkeyRecordMonitor {
            NSEvent.removeMonitor(monitor)
            hotkeyRecordMonitor = nil
        }
        recordingTarget = nil
        recordingError = nil
        registerHotKey()
    }

    /// Kayıt sırasında basılan tuşu değerlendirir; geçerliyse kısayolu kaydeder.
    private func handleRecordingEvent(_ event: NSEvent) {
        if event.keyCode == 53 {  // Esc → iptal
            stopHotkeyRecording()
            return
        }
        guard let keyName = HotKey.keyName(for: UInt32(event.keyCode)) else {
            recordingError = "Bu tuş desteklenmiyor (harf veya rakam seçin)."
            return
        }
        let flags = event.modifierFlags
        var mods: [String] = []
        if flags.contains(.control) { mods.append("ctrl") }
        if flags.contains(.option) { mods.append("opt") }
        if flags.contains(.command) { mods.append("cmd") }
        if flags.contains(.shift) { mods.append("shift") }
        // Shift tek başına yeterli değil; en az bir Ctrl/Alt/Cmd gerekir
        // (yoksa düz harfler kazara kısayol olur).
        guard mods.contains(where: { $0 != "shift" }) else {
            recordingError = "En az bir Ctrl, Alt veya Cmd gerekli."
            return
        }
        switch recordingTarget {
        case .correction:
            settings.hotkeyMods = mods
            settings.hotkeyKey = keyName
        case .cancel:
            settings.cancelHotkeyMods = mods
            settings.cancelHotkeyKey = keyName
        case nil:
            return
        }
        settings.save()
        stopHotkeyRecording()  // monitörü kaldırır + yeni kısayolu kaydeder
        lastStatus = "Kısayol güncellendi"
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
        Log.info("correctSelection: basladi; accessibility=\(accessibilityGranted) engineRunning=\(engine.isRunning)")
        if !accessibilityGranted {
            Log.info("correctSelection: UYARI Accessibility izni YOK -> Cmd+C/Cmd+V calismaz")
        }
        do {
            let result = try await corrector.run()
            lastStatus = "Düzeltildi: " + String(result.prefix(40))
            Log.info("correctSelection: OK -> '\(result.replacingOccurrences(of: "\n", with: "\\n"))'")
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

        // Düzeltmeyi kısayol yanında menüden de başlatılabilir kıl. İşlem
        // sürerken pasif. Kısayol etiketi config'ten gelir.
        Button("Seçili metni düzelt") { state.requestCorrection() }
            .keyboardShortcut(correctionShortcut.key, modifiers: correctionShortcut.modifiers)
            .disabled(state.busy)

        // İptal seçeneği her zaman görünür; işlem yokken pasif (kullanıcıya
        // bu yeteneğin var olduğunu bildirir). Kısayol etiketi config'ten gelir.
        Button("İşlemi iptal et") { state.cancelCorrection() }
            .keyboardShortcut(cancelShortcut.key, modifiers: cancelShortcut.modifiers)
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

    /// Düzeltme ve iptal kısayollarını config'ten SwiftUI menü kısayoluna çevirir
    /// (yalnızca menüde gösterim; global yakalama Carbon HotKey ile yapılır).
    private var correctionShortcut: (key: KeyEquivalent, modifiers: EventModifiers) {
        Self.shortcut(mods: state.settings.hotkeyMods, key: state.settings.hotkeyKey, fallback: "a")
    }

    private var cancelShortcut: (key: KeyEquivalent, modifiers: EventModifiers) {
        Self.shortcut(mods: state.settings.cancelHotkeyMods, key: state.settings.cancelHotkeyKey, fallback: "q")
    }

    private static func shortcut(
        mods: [String], key: String, fallback: Character
    ) -> (key: KeyEquivalent, modifiers: EventModifiers) {
        let character = Character(key.first.map(String.init) ?? String(fallback))
        var modifiers: EventModifiers = []
        for mod in mods {
            switch mod.lowercased() {
            case "ctrl", "control": modifiers.insert(.control)
            case "alt", "opt", "option": modifiers.insert(.option)
            case "cmd", "command", "win", "windows", "super": modifiers.insert(.command)
            case "shift": modifiers.insert(.shift)
            default: break
            }
        }
        return (KeyEquivalent(character), modifiers)
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

// MARK: - Ana pencere (sidebar; ileride bölüm eklenebilir)

struct MainView: View {
    @ObservedObject var state: AppState

    /// Sidebar bölümleri. Yeni ekran eklemek için buraya bir case + `detail`
    /// switch'ine bir satır eklemek yeterli.
    enum Section: String, CaseIterable, Identifiable {
        case correct = "Düzeltme"
        case engine = "Motor Ayarları"
        case other = "Diğer Ayarlar"
        case protectedWords = "Korumalı Kelimeler"
        case log = "Log"

        var id: String { rawValue }
        var icon: String {
            switch self {
            case .correct: return "text.badge.checkmark"
            case .engine: return "cpu"
            case .protectedWords: return "shield"
            case .other: return "slider.horizontal.3"
            case .log: return "doc.plaintext"
            }
        }
    }

    @State private var selection: Section? = .correct

    var body: some View {
        NavigationSplitView {
            List(Section.allCases, selection: $selection) { section in
                Label(section.rawValue, systemImage: section.icon).tag(section)
            }
            .navigationSplitViewColumnWidth(min: 180, ideal: 200, max: 260)
        } detail: {
            detail
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle("Turkify")
        .frame(minWidth: 640, idealWidth: 920, maxWidth: .infinity,
               minHeight: 460, idealHeight: 660, maxHeight: .infinity)
        .onAppear { state.windowAppeared() }
        .onDisappear { state.windowDisappeared() }
    }

    @ViewBuilder
    private var detail: some View {
        switch selection ?? .correct {
        case .correct: CorrectionView(state: state)
        case .engine: SettingsView(state: state)
        case .protectedWords: ProtectedWordsView(state: state)
        case .other: OtherSettingsView(state: state)
        case .log: LogView(state: state)
        }
    }
}

// MARK: - Düzeltme sekmesi (metin yaz → düzelt; opsiyonel panoya kopyala)

struct CorrectionView: View {
    @ObservedObject var state: AppState

    @State private var input = ""
    @State private var output = ""
    @State private var task: Task<Void, Never>?
    @State private var phase: Phase = .idle
    @State private var status = "Hazır"

    private enum Phase: Equatable { case idle, processing, done, failed }
    private var isProcessing: Bool { phase == .processing }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                if isProcessing { ProgressView().controlSize(.small) }
                Text(status)
                    .font(.caption)
                    .foregroundStyle(phase == .failed ? .red : .secondary)
                    .lineLimit(1)
                Spacer()
                Button("İptal") { cancel() }
                    .disabled(!isProcessing)
                    .keyboardShortcut(.cancelAction)
                Button("Düzelt") { run(copy: false) }
                    .disabled(isProcessing || input.isEmpty)
                Button("Düzelt ve Kopyala") { run(copy: true) }
                    .buttonStyle(.borderedProminent)
                    .disabled(isProcessing || input.isEmpty)
            }
            .padding(.horizontal).padding(.vertical, 8)

            Divider()

            Text("Metin  ·  Enter: düzelt  ·  ⇧Enter: alt satır  ·  ⌘Enter: düzelt + kopyala")
                .font(.caption).foregroundStyle(.secondary)
                .padding(.horizontal).padding(.top, 6)
            CorrectionInputEditor(
                text: $input,
                isEditable: !isProcessing,
                onSubmit: { run(copy: false) },
                onSubmitAndCopy: { run(copy: true) },
                onCancel: { cancel() }
            )
            .frame(minHeight: 140)
            .padding(.horizontal).padding(.bottom, 6)

            Divider()

            Text("Düzeltilmiş metin")
                .font(.caption).foregroundStyle(.secondary)
                .padding(.horizontal).padding(.top, 6)
            ScrollView {
                Text(output.isEmpty ? "Düzeltilmiş metin burada görünecek." : output)
                    .foregroundStyle(output.isEmpty ? .secondary : .primary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(8)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    /// Düzeltmeyi iptal edilebilir bir görev olarak başlatır.
    private func run(copy: Bool) {
        let text = input
        guard !text.isEmpty, !isProcessing else { return }
        phase = .processing
        status = copy ? "Düzeltiliyor (panoya kopyalanacak)…" : "Düzeltiliyor…"
        task = Task { @MainActor in
            do {
                let result = try await state.correctText(text)
                try Task.checkCancellation()
                output = result
                if copy {
                    state.copyToClipboard(result)
                    status = "Düzeltildi ve panoya kopyalandı"
                } else {
                    status = "Düzeltildi"
                }
                phase = .done
            } catch is CancellationError {
                status = "İşlem iptal edildi"
                phase = .idle
            } catch let error as EngineClient.EngineError {
                status = Self.engineErrorText(error)
                phase = .failed
            } catch {
                status = "Hata: \(error.localizedDescription)"
                phase = .failed
            }
            task = nil
        }
    }

    private func cancel() {
        guard isProcessing else { return }
        task?.cancel()
    }

    private static func engineErrorText(_ error: EngineClient.EngineError) -> String {
        switch error {
        case .engine(let message): return "Motor hatası: \(message)"
        case .notRunning: return "Motor çalışmıyor"
        case .badResponse: return "Motor yanıtı çözülemedi"
        }
    }
}

/// Düzeltme giriş alanı: Enter düzeltir, ⇧Enter alt satır, ⌘Enter düzelt+kopyala,
/// Esc iptal. Bu davranış çok-satırlı NSTextView'de SwiftUI ile sağlanamadığından
/// (Enter newline ekler) tuşları NSTextView seviyesinde yakalıyoruz.
struct CorrectionInputEditor: NSViewRepresentable {
    @Binding var text: String
    var isEditable: Bool
    var onSubmit: () -> Void
    var onSubmitAndCopy: () -> Void
    var onCancel: () -> Void

    func makeNSView(context: Context) -> NSScrollView {
        let textView = SubmitTextView()
        textView.delegate = context.coordinator
        textView.isRichText = false
        textView.allowsUndo = true
        textView.font = .systemFont(ofSize: NSFont.systemFontSize)
        textView.textContainerInset = NSSize(width: 4, height: 6)
        textView.autoresizingMask = [.width]
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true
        textView.string = text

        let scroll = NSScrollView()
        scroll.documentView = textView
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .bezelBorder
        return scroll
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? SubmitTextView else { return }
        if textView.string != text { textView.string = text }
        textView.isEditable = isEditable
        textView.isSelectable = true
        textView.onSubmit = onSubmit
        textView.onSubmitAndCopy = onSubmitAndCopy
        textView.onCancel = onCancel
    }

    func makeCoordinator() -> Coordinator { Coordinator(text: $text) }

    final class Coordinator: NSObject, NSTextViewDelegate {
        private let text: Binding<String>
        init(text: Binding<String>) { self.text = text }
        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            text.wrappedValue = textView.string
        }
    }
}

/// Enter/⇧Enter/⌘Enter/Esc tuşlarını yakalayan NSTextView.
final class SubmitTextView: NSTextView {
    var onSubmit: (() -> Void)?
    var onSubmitAndCopy: (() -> Void)?
    var onCancel: (() -> Void)?

    override func keyDown(with event: NSEvent) {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        if event.keyCode == 36 || event.keyCode == 76 {  // Return / numpad Enter
            if flags.contains(.command) { onSubmitAndCopy?(); return }
            if flags.contains(.shift) { super.keyDown(with: event); return }  // alt satır
            onSubmit?(); return
        }
        if event.keyCode == 53 {  // Esc
            onCancel?(); return
        }
        super.keyDown(with: event)
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
                SaveButton(defaultAction: true) { state.saveSettings() }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

            Divider()

            Form {
                Section {
                    tierRow(
                        title: "Tier 1 — Deterministik",
                        detail: "Şapkaları kalıp tabanlı (Yüret) geri ekler. Hızlı, çevrimdışı temel düzeltme; her zaman açıktır.",
                        isOn: .constant(true),
                        locked: true
                    )
                    tierRow(
                        title: "Tier 2 — Morfoloji + frekans",
                        detail: "Geçersiz/belirsiz kelimeleri biçimbilim (zeyrek) ve kelime sıklığıyla çözer. zeyrek kurulu değilse sessizce atlanır.",
                        isOn: $state.settings.useMorphology
                    )
                    tierRow(
                        title: "Tier 3 — LLM (bağlam)",
                        detail: "Yalnızca birden çok geçerli aday bağlam gerektirdiğinde LLM doğru olanı seçer. OpenAI-uyumlu sunucu + model gerekir.",
                        isOn: $state.settings.useLLM
                    )
                } header: {
                    Text("Katmanlar")
                } footer: {
                    Text("Düzeltme kademelidir: her katman bir öncekinin çözemediği kelimelere bakar.")
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

    /// Bir katman satırı: aç/kapa anahtarı + altında ne yaptığının kısa açıklaması.
    /// ``locked`` (Tier 1) ise anahtar açık ve devre dışıdır (kapatılamaz).
    @ViewBuilder
    private func tierRow(
        title: String, detail: String, isOn: Binding<Bool>, locked: Bool = false
    ) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Toggle(title, isOn: isOn)
                .disabled(locked)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - Diğer Ayarlar sekmesi (Kaydet YOK; anlık kontroller + durum)

struct OtherSettingsView: View {
    @ObservedObject var state: AppState

    var body: some View {
        Form {
            Section {
                permissionRow(
                    "Erişilebilirlik (Accessibility)",
                    explanation: "Zorunlu. Seçili metni almak için Cmd+C, düzeltilmiş metni geri yazmak için Cmd+V tuşlarını aktif uygulamaya gönderir. İzin yoksa düzeltme uygulanamaz.",
                    granted: state.accessibilityGranted
                ) {
                    Permissions.promptAccessibility()
                    Permissions.openAccessibilitySettings()
                }
                Button("İzinleri yenile") { state.refreshPermissions() }
            } header: {
                Text("İzinler")
            } footer: {
                Text("İzinleri Apple güvenlik nedeniyle uygulama veremez; “Aç” ile System Settings açılır, anahtarı siz çevirirsiniz. Sonra “İzinleri yenile”.")
            }

            Section {
                Toggle("Dock'ta göster", isOn: Binding(
                    get: { state.settings.showInDock },
                    set: { state.setShowInDock($0) }
                ))
            } header: {
                Text("Görünüm")
            } footer: {
                Text("Kapalıyken uygulama yalnızca menü-bar'da durur.")
            }

            Section {
                hotkeyRow("Düzeltme", description: state.settings.hotkeyDescription, target: .correction)
                hotkeyRow("İşlemi iptal", description: state.settings.cancelHotkeyDescription, target: .cancel)
            } header: {
                Text("Kısayollar")
            } footer: {
                if let error = state.recordingError {
                    Text(error).foregroundStyle(.red)
                } else if state.recordingTarget != nil {
                    Text("Yeni kısayol kombinasyonuna basın. En az bir Ctrl/Alt/Cmd ve bir harf/rakam. (Esc: iptal)")
                } else {
                    Text("“Değiştir”e basıp istediğiniz kısayol kombinasyonuna basın.")
                }
            }
        }
        .formStyle(.grouped)
    }

    /// Bir kısayol satırı: mevcut kombinasyonu gösterir, "Değiştir" ile kaydı başlatır.
    @ViewBuilder
    private func hotkeyRow(
        _ title: String, description: String, target: AppState.HotkeyTarget
    ) -> some View {
        let isRecording = state.recordingTarget == target
        LabeledContent(title) {
            HStack(spacing: 12) {
                Text(isRecording ? "Tuşa basın…" : description)
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(isRecording ? Color.orange : .primary)
                Button(isRecording ? "İptal" : "Değiştir") {
                    if isRecording {
                        state.stopHotkeyRecording()
                    } else {
                        state.startHotkeyRecording(target)
                    }
                }
                // Diğer satır kayıttayken bu satırın butonunu kilitle.
                .disabled(state.recordingTarget != nil && !isRecording)
            }
        }
    }

    @ViewBuilder
    private func permissionRow(
        _ name: String, explanation: String, granted: Bool, action: @escaping () -> Void
    ) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(granted ? "✅" : "❌")
                Text(name)
                Spacer()
                Button("Aç") { action() }
            }
            Text(explanation)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - Korumalı Kelimeler sekmesi (paylaşılan dosya — ADR 0008)

struct ProtectedWordsView: View {
    @ObservedObject var state: AppState
    @State private var text: String = ""
    @State private var loaded = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Bu kelimeler düzeltilmez (her satıra bir kelime). Yalnızca buradaki kelimeler korunur. Aramak için ⌘F.")
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                SaveButton { state.saveProtectedWords(text) }
            }
            .padding(.horizontal)
            .padding(.vertical, 6)

            Divider()

            // NSTextView tabanlı: ⌘F ile sistem arama çubuğu açılır.
            FindableTextEditor(text: $text)
        }
        .onAppear {
            // Dosyayı yalnızca ilk açılışta yükle; kullanıcının düzenlemesini ezmesin.
            if !loaded {
                text = state.loadProtectedWords()
                loaded = true
            }
        }
    }
}

// MARK: - Kaydet butonu (geri bildirimli)

/// Kaydet butonu: tıklanınca ``action`` çalışır; başarılıysa kısa süreli yeşil
/// ✓, başarısızsa kırmızı uyarı gösterir, sonra normale döner.
struct SaveButton: View {
    var title: String = "Kaydet"
    /// ``true`` döndürürse başarı, ``false`` döndürürse hata geri bildirimi gösterilir.
    var defaultAction: Bool = false
    let action: () -> Bool

    private enum Phase { case idle, saved, failed }
    @State private var phase: Phase = .idle

    var body: some View {
        let button = Button(action: run) {
            switch phase {
            case .idle: Text(title)
            case .saved: Label("Kaydedildi", systemImage: "checkmark.circle.fill")
            case .failed: Label("Kaydedilemedi", systemImage: "exclamationmark.triangle.fill")
            }
        }
        .buttonStyle(.borderedProminent)
        .tint(phase == .saved ? .green : (phase == .failed ? .red : .accentColor))
        .animation(.easeInOut(duration: 0.15), value: phase)

        // Motor Ayarları'nda Enter ile tetiklenebilsin (varsayılan eylem).
        if defaultAction {
            button.keyboardShortcut(.defaultAction)
        } else {
            button
        }
    }

    private func run() {
        let ok = action()
        phase = ok ? .saved : .failed
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
            if phase != .idle { phase = .idle }
        }
    }
}

// MARK: - Aranabilir metin editörü (NSTextView; ⌘F ile sistem arama çubuğu)

/// SwiftUI ``TextEditor`` ⌘F arama çubuğunu desteklemez; bu yüzden NSTextView'i
/// (bul çubuğu açık) sarıyoruz. ⌘F basınca sistemin yerleşik arama çubuğu açılır.
struct FindableTextEditor: NSViewRepresentable {
    @Binding var text: String

    func makeNSView(context: Context) -> NSScrollView {
        let textView = FindableTextView()
        textView.delegate = context.coordinator
        textView.isRichText = false
        textView.isEditable = true
        textView.isSelectable = true
        textView.allowsUndo = true
        textView.font = .monospacedSystemFont(ofSize: NSFont.systemFontSize, weight: .regular)
        textView.textContainerInset = NSSize(width: 4, height: 6)
        textView.usesFindBar = true                       // bul çubuğu (panel değil)
        textView.isIncrementalSearchingEnabled = true     // yazdıkça eşleşmeleri vurgula
        textView.autoresizingMask = [.width]
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true
        textView.string = text

        let scroll = NSScrollView()
        scroll.documentView = textView
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .noBorder
        return scroll
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? FindableTextView else { return }
        // Sonsuz döngüyü önle: yalnızca dışarıdan gerçekten değiştiyse yaz.
        if textView.string != text {
            textView.string = text
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(text: $text) }

    final class Coordinator: NSObject, NSTextViewDelegate {
        private let text: Binding<String>
        init(text: Binding<String>) { self.text = text }
        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            text.wrappedValue = textView.string
        }
    }
}

/// ⌘F'yi yakalayıp yerleşik bul çubuğunu açan NSTextView (menüye bağımlı değil).
final class FindableTextView: NSTextView {
    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        if flags == .command, event.charactersIgnoringModifiers == "f" {
            let item = NSMenuItem()
            item.tag = Int(NSTextFinder.Action.showFindInterface.rawValue)
            performTextFinderAction(item)
            return true
        }
        return super.performKeyEquivalent(with: event)
    }
}

// MARK: - Log sekmesi (canlı; yeni satırlar anında düşer)

struct LogLine: Identifiable {
    let id = UUID()
    let time: String
    let source: Log.Source
    let text: String

    /// Kaynak etiketi rengi: sistem (native app) mavi, motor (Python) mor.
    var sourceColor: Color {
        switch source {
        case .system: return .blue
        case .engine: return .purple
        }
    }
}

struct LogView: View {
    @ObservedObject var state: AppState

    /// Kaynak filtresi: tümü / yalnızca sistem (native app) / yalnızca motor.
    enum Filter: String, CaseIterable, Identifiable {
        case all = "Tümü"
        case system = "Sistem"
        case engine = "Motor"
        var id: String { rawValue }
    }
    @State private var filter: Filter = .all

    private var visibleLines: [LogLine] {
        switch filter {
        case .all: return state.logLines
        case .system: return state.logLines.filter { $0.source == .system }
        case .engine: return state.logLines.filter { $0.source == .engine }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Picker("Kaynak", selection: $filter) {
                    ForEach(Filter.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(maxWidth: 240)

                Spacer()

                Text("\(visibleLines.count) satır")
                    .font(.caption).foregroundStyle(.secondary)
                Button("Temizle") { state.logLines.removeAll() }
            }
            .padding(.horizontal)
            .padding(.vertical, 6)

            Divider()

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 1) {
                        ForEach(visibleLines) { line in
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                Text(line.time)
                                    .foregroundStyle(.secondary)
                                Text("[\(line.source.rawValue)]")
                                    .foregroundStyle(line.sourceColor)
                                Text(line.text)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .id(line.id)
                        }
                    }
                    .padding(8)
                }
                .onChange(of: visibleLines.count) { _ in
                    // Yeni satır gelince en alta kaydır (canlı akış).
                    if let last = visibleLines.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }
}
