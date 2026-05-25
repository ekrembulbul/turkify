import Foundation

/// Basit teşhis logu — stderr'e yazar (Xcode konsolunda görünür).
enum Log {
    static func info(_ message: String) {
        let line = "[turkify-mac] \(message)\n"
        FileHandle.standardError.write(Data(line.utf8))
    }
}
