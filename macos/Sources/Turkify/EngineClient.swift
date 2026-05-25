import Foundation

/// Python düzeltme motoruyla (`turkify serve --stdio`) köprü.
///
/// Motoru bir kez çocuk süreç olarak başlatır (sıcak tutar) ve satır-bazlı JSON
/// protokolüyle konuşur (bkz. ADR 0004):
///
///     istek :  {"id": 1, "text": "..."}
///     yanıt :  {"id": 1, "corrected": "..."} | {"id": 1, "error": "..."}
///
/// İstekler `id` ile eşleştirilir; tüm durum erişimi tek bir kuyrukta seri yapılır.
final class EngineClient {
    enum EngineError: Error {
        case engine(String)
        case badResponse
        case notRunning
    }

    private let process = Process()
    private let stdinPipe = Pipe()
    private let stdoutPipe = Pipe()

    private let queue = DispatchQueue(label: "com.turkify.engine")
    private var buffer = Data()
    private var pending: [Int: CheckedContinuation<String, Error>] = [:]
    private var nextID = 1

    init() {
        let launch = AppConfig.engineLaunch()
        process.executableURL = URL(fileURLWithPath: launch.executable)
        process.arguments = launch.arguments
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        // stderr devralınır → motor tanı mesajları Xcode konsolunda görünür.
    }

    func start() throws {
        stdoutPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            self?.queue.async { self?.ingest(data) }
        }
        try process.run()
    }

    func stop() {
        if process.isRunning { process.terminate() }
    }

    var isRunning: Bool { process.isRunning }

    /// Metni motora gönderir ve düzeltilmiş halini döndürür.
    func correct(_ text: String) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard self.process.isRunning else {
                    continuation.resume(throwing: EngineError.notRunning)
                    return
                }
                let id = self.nextID
                self.nextID += 1
                self.pending[id] = continuation
                let payload: [String: Any] = ["id": id, "text": text]
                guard var line = try? JSONSerialization.data(withJSONObject: payload) else {
                    self.pending.removeValue(forKey: id)
                    continuation.resume(throwing: EngineError.badResponse)
                    return
                }
                line.append(0x0A)  // satır sonu
                self.stdinPipe.fileHandleForWriting.write(line)
            }
        }
    }

    // MARK: - Gelen veriyi satırlara böl (queue üzerinde çalışır)

    private func ingest(_ data: Data) {
        buffer.append(data)
        while let newline = buffer.firstIndex(of: 0x0A) {
            let lineData = buffer.subdata(in: buffer.startIndex..<newline)
            buffer.removeSubrange(buffer.startIndex...newline)
            handleLine(lineData)
        }
    }

    private func handleLine(_ data: Data) {
        guard
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let id = obj["id"] as? Int,
            let continuation = pending.removeValue(forKey: id)
        else { return }

        if let corrected = obj["corrected"] as? String {
            continuation.resume(returning: corrected)
        } else if let error = obj["error"] as? String {
            continuation.resume(throwing: EngineError.engine(error))
        } else {
            continuation.resume(throwing: EngineError.badResponse)
        }
    }
}
