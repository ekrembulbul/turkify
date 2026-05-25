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
    var hotkeyMods: [String]
    var hotkeyKey: String

    static let fallback = AppSettings(
        model: "",
        useLLM: false,
        useMorphology: true,
        timeout: 60,
        baseURL: "http://localhost:11434/v1",
        apiKey: "",
        assistantPrefill: "",
        hotkeyMods: ["ctrl", "opt", "cmd"],
        hotkeyKey: "a"
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
            hotkeyMods: d.stringArray(forKey: "hotkeyMods") ?? fallback.hotkeyMods,
            hotkeyKey: d.string(forKey: "hotkeyKey") ?? fallback.hotkeyKey
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
        d.set(hotkeyMods, forKey: "hotkeyMods")
        d.set(hotkeyKey, forKey: "hotkeyKey")
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
        return args
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
