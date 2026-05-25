import Foundation

/// Python düzeltme motoruyla (`turkify serve --stdio`) köprü.
///
/// Motoru çocuk süreç olarak başlatır (sıcak tutar) ve satır-bazlı JSON
/// protokolüyle konuşur (bkz. ADR 0004):
///
///     istek :  {"id": 1, "text": "..."}
///     yanıt :  {"id": 1, "corrected": "..."} | {"id": 1, "error": "..."}
///
/// Ayarlar, motoru başlatırken **CLI bayrakları** olarak geçirilir (config.json
/// kullanılmaz — bkz. ADR 0007). Ayar değişince `restart(settings:)` ile yeni
/// bayraklarla yeniden başlatılır.
final class EngineClient {
    enum EngineError: Error {
        case engine(String)
        case badResponse
        case notRunning
    }

    private var process: Process?
    private var stdinHandle: FileHandle?

    private let queue = DispatchQueue(label: "com.turkify.engine")
    private var buffer = Data()
    private var pending: [Int: CheckedContinuation<String, Error>] = [:]
    private var nextID = 1

    var isRunning: Bool { process?.isRunning ?? false }

    /// Motoru verilen ayarlarla başlatır (önce çalışan varsa durdurur).
    func start(settings: AppSettings) throws {
        stop()
        let proc = Process()
        let launch = AppSettings.engineExecutable()
        proc.executableURL = URL(fileURLWithPath: launch.executable)
        proc.arguments = launch.prefixArgs + settings.serveArguments()
        Log.info("motor komutu: \(launch.executable) \((launch.prefixArgs + settings.serveArguments()).joined(separator: " "))")
        proc.terminationHandler = { p in
            Log.info("motor sonlandi (kod \(p.terminationStatus))")
        }

        let stdin = Pipe()
        let stdout = Pipe()
        let stderr = Pipe()
        proc.standardInput = stdin
        proc.standardOutput = stdout
        proc.standardError = stderr  // motor tanı mesajlarını yakala → Log sekmesi

        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            self?.queue.async { self?.ingest(data) }
        }
        stderr.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            for line in text.split(whereSeparator: \.isNewline) where !line.isEmpty {
                Log.engine(String(line))
            }
        }

        try proc.run()
        process = proc
        stdinHandle = stdin.fileHandleForWriting
    }

    func restart(settings: AppSettings) throws {
        try start(settings: settings)
    }

    func stop() {
        if let proc = process, proc.isRunning { proc.terminate() }
        process = nil
        stdinHandle = nil
        queue.async {
            let waiting = self.pending
            self.pending.removeAll()
            self.buffer.removeAll()
            for (_, continuation) in waiting {
                continuation.resume(throwing: EngineError.notRunning)
            }
        }
    }

    /// Metni motora gönderir ve düzeltilmiş halini döndürür. Task iptal edilirse
    /// bekleyen istek bırakılır (motor isteği arka planda bitirir, yanıtı yok sayılır).
    func correct(_ text: String) async throws -> String {
        // id'yi önceden üret ki iptal işleyicisi doğru isteği temizleyebilsin.
        let id = queue.sync { () -> Int in
            let current = nextID
            nextID += 1
            return current
        }
        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                queue.async {
                    guard let handle = self.stdinHandle, self.isRunning else {
                        continuation.resume(throwing: EngineError.notRunning)
                        return
                    }
                    self.pending[id] = continuation
                    let payload: [String: Any] = ["id": id, "text": text]
                    guard var line = try? JSONSerialization.data(withJSONObject: payload) else {
                        self.pending.removeValue(forKey: id)
                        continuation.resume(throwing: EngineError.badResponse)
                        return
                    }
                    line.append(0x0A)  // satır sonu
                    handle.write(line)
                }
            }
        } onCancel: {
            queue.async {
                if let continuation = self.pending.removeValue(forKey: id) {
                    continuation.resume(throwing: CancellationError())
                }
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
