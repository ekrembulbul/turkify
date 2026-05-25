import Foundation

/// Basit teşhis logu — stderr'e yazar (Xcode konsolu) **ve** UI'daki Log sekmesine
/// iletir. `sink` AppState tarafından kurulur; herhangi bir thread'den çağrılabilir
/// (sink, main actor'a kendisi geçer).
///
/// Her satırın bir **kaynağı** vardır: `.system` = bu native macOS uygulaması
/// (OS'a özel çalışan taraf), `.engine` = Python düzeltme motoru (çapraz-platform).
/// Böylece Log sekmesinde iki kaynak ayrı ayrı görünür.
enum Log {
    enum Source: String {
        case system = "sistem"  // native macOS uygulaması
        case engine = "motor"   // Python düzeltme motoru
    }

    /// UI'ya iletim kancası (AppState kurar). Boşsa yalnızca stderr'e yazılır.
    static var sink: ((Source, String) -> Void)?

    /// Native uygulamanın (OS tarafı) olayını loglar.
    static func info(_ message: String) {
        emit(.system, message)
    }

    /// Motorun (Python) çıktısını loglar.
    static func engine(_ message: String) {
        emit(.engine, message)
    }

    private static func emit(_ source: Source, _ message: String) {
        FileHandle.standardError.write(Data("[turkify-\(source.rawValue)] \(message)\n".utf8))
        sink?(source, message)
    }
}
