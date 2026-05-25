import Foundation

/// `~/.config/turkify/config.json`'u okur ve motoru başlatma bilgilerini sağlar.
///
/// Native app config'i yalnızca **okur** (model adı, kısayol); düzeltme mantığı
/// Python motorundadır. Motor `turkify serve --stdio` ile başlatılır.
struct AppConfig {
    var model: String?
    var hotkeyMods: [String]
    var hotkeyKey: String

    static func load() -> AppConfig {
        let path = ("~/.config/turkify/config.json" as NSString).expandingTildeInPath
        var model: String?
        var mods = ["ctrl", "opt", "cmd"]
        var key = "a"
        if let data = FileManager.default.contents(atPath: path),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            model = obj["model"] as? String
            if let hk = obj["hotkey"] as? [String: Any] {
                if let m = hk["mods"] as? [String] { mods = m }
                if let k = hk["key"] as? String { key = k }
            }
        }
        return AppConfig(model: model, hotkeyMods: mods, hotkeyKey: key)
    }

    /// Motoru başlatacak komut. Varsayılan: `/usr/bin/env python3 -m turkify serve --stdio`
    /// (turkify, PATH'teki python3'te kurulu olmalı). Venv kullanıyorsan Xcode
    /// scheme'inde `TURKIFY_PYTHON` env'ini venv python yoluna ayarla.
    static func engineLaunch() -> (executable: String, arguments: [String]) {
        let serve = ["-m", "turkify", "serve", "--stdio"]
        if let python = ProcessInfo.processInfo.environment["TURKIFY_PYTHON"], !python.isEmpty {
            return (python, serve)
        }
        return ("/usr/bin/env", ["python3"] + serve)
    }
}
