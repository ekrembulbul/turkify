import Foundation

/// Basit teşhis logu — stderr'e yazar (Xcode konsolu) **ve** UI'daki Log sekmesine
/// iletir. `sink` AppState tarafından kurulur; herhangi bir thread'den çağrılabilir
/// (sink, main actor'a kendisi geçer).
enum Log {
    /// UI'ya iletim kancası (AppState kurar). Boşsa yalnızca stderr'e yazılır.
    static var sink: ((String) -> Void)?

    static func info(_ message: String) {
        FileHandle.standardError.write(Data("[turkify-mac] \(message)\n".utf8))
        sink?(message)
    }
}
