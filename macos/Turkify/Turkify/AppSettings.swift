import Foundation

/// macOS uygulamasının ayarları — **native saklanır** (`UserDefaults`), config.json
/// **kullanılmaz**. (config.json yalnızca Linux servisi ve CLI içindir.)
///
/// Ayarlar motora `turkify serve`'e **CLI bayrakları** olarak geçirilir; bayraklar
/// önceliklidir (CLI > env > config), bu yüzden bir config.json olsa bile GUI
/// ayarları kazanır. Ayar değişince motor yeni bayraklarla yeniden başlatılır.
struct AppSettings {
    var model: String
    var useLLM: Bool
    var useMorphology: Bool
    var timeout: Double
    var baseURL: String
    var apiKey: String
    var assistantPrefill: String
    /// /chat/completions gövdesine eklenecek ham JSON (boş = gönderilmez).
    var llmOptions: String
    var hotkeyMods: [String]
    var hotkeyKey: String
    /// Yalnızca UI tercihi (motora gönderilmez): uygulama çalışırken Dock'ta
    /// simge görünsün mü? Kapalıysa menü-bar-only (accessory).
    var showInDock: Bool
    /// UI tercihi: model seçimi otomatik mi (combobox'tan, model/url readonly) yoksa
    /// manuel mi (combobox kapalı, model/url elle yazılır)?
    var autoModelSelection: Bool

    static let fallback = AppSettings(
        model: "",
        useLLM: false,
        useMorphology: true,
        timeout: 60,
        baseURL: "http://localhost:11434/v1",
        apiKey: "",
        assistantPrefill: "",
        llmOptions: "",
        hotkeyMods: ["ctrl", "opt", "cmd"],
        hotkeyKey: "a",
        showInDock: false,
        autoModelSelection: true
    )

    static func load() -> AppSettings {
        let d = UserDefaults.standard
        return AppSettings(
            model: d.string(forKey: "model") ?? "",
            useLLM: d.object(forKey: "useLLM") as? Bool ?? fallback.useLLM,
            useMorphology: d.object(forKey: "useMorphology") as? Bool ?? fallback.useMorphology,
            timeout: d.object(forKey: "timeout") as? Double ?? fallback.timeout,
            baseURL: d.string(forKey: "baseURL") ?? fallback.baseURL,
            apiKey: d.string(forKey: "apiKey") ?? "",
            assistantPrefill: d.string(forKey: "assistantPrefill") ?? "",
            llmOptions: d.string(forKey: "llmOptions") ?? "",
            hotkeyMods: d.stringArray(forKey: "hotkeyMods") ?? fallback.hotkeyMods,
            hotkeyKey: d.string(forKey: "hotkeyKey") ?? fallback.hotkeyKey,
            showInDock: d.object(forKey: "showInDock") as? Bool ?? fallback.showInDock,
            autoModelSelection: d.object(forKey: "autoModelSelection") as? Bool ?? fallback.autoModelSelection
        )
    }

    func save() {
        let d = UserDefaults.standard
        d.set(model, forKey: "model")
        d.set(useLLM, forKey: "useLLM")
        d.set(useMorphology, forKey: "useMorphology")
        d.set(timeout, forKey: "timeout")
        d.set(baseURL, forKey: "baseURL")
        d.set(apiKey, forKey: "apiKey")
        d.set(assistantPrefill, forKey: "assistantPrefill")
        d.set(llmOptions, forKey: "llmOptions")
        d.set(hotkeyMods, forKey: "hotkeyMods")
        d.set(hotkeyKey, forKey: "hotkeyKey")
        d.set(showInDock, forKey: "showInDock")
        d.set(autoModelSelection, forKey: "autoModelSelection")
    }

    /// Motoru bu ayarlarla başlatacak `serve` argümanları (CLI bayrakları).
    func serveArguments() -> [String] {
        var args = ["serve", "--stdio"]
        if !model.isEmpty { args += ["--model", model] }
        args += [useLLM ? "--llm" : "--no-llm"]
        args += [useMorphology ? "--morphology" : "--no-morphology"]
        args += ["--timeout", String(timeout)]
        if !baseURL.isEmpty { args += ["--base-url", baseURL] }
        if !apiKey.isEmpty { args += ["--api-key", apiKey] }
        if !assistantPrefill.isEmpty { args += ["--assistant-prefill", assistantPrefill] }
        // Yalnızca geçerli JSON ise gönder; geçersizse motor hiç başlamazdı.
        let trimmedOptions = llmOptions.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedOptions.isEmpty, AppSettings.isValidJSON(trimmedOptions) {
            args += ["--llm-options", trimmedOptions]
        }
        return args
    }

    /// Boş ya da geçerli JSON mu? (UI'da uyarı + serveArguments'ta filtre için.)
    static func isValidJSON(_ text: String) -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return true }
        guard let data = trimmed.data(using: .utf8) else { return false }
        return (try? JSONSerialization.jsonObject(with: data)) != nil
    }

    var hotkeyDescription: String {
        hotkeyMods.map { $0.capitalized }.joined(separator: "+") + "+" + hotkeyKey.uppercased()
    }

    /// Python yürütücüsü + `-m turkify` öneki. `serve` argümanları ayrı eklenir.
    /// Venv için Xcode scheme'inde `TURKIFY_PYTHON` env'ini ayarla.
    static func engineExecutable() -> (executable: String, prefixArgs: [String]) {
        if let python = ProcessInfo.processInfo.environment["TURKIFY_PYTHON"], !python.isEmpty {
            return (python, ["-m", "turkify"])
        }
        return ("/usr/bin/env", ["python3", "-m", "turkify"])
    }
}
