import Foundation

/// Keşfedilen bir yerel LLM sunucusu ve modelleri (tür/başlık ile).
struct DiscoveredBackend: Identifiable {
    let name: String      // ör. "Ollama", "LM Studio"
    let baseURL: String   // ör. "http://localhost:11434/v1"
    let models: [String]  // /v1/models -> data[].id
    var id: String { baseURL }
}

/// Bilinen yerel OpenAI-uyumlu sunucuları tarar ve modelleri **türlerine göre**
/// (Ollama, LM Studio, …) listeler. Her biri `/v1/models` ucuyla yoklanır.
enum ModelDiscovery {
    /// (görünen ad, base_url). Yaygın yerel sunucuların varsayılan portları.
    static let known: [(name: String, baseURL: String)] = [
        ("Ollama", "http://localhost:11434/v1"),
        ("LM Studio", "http://localhost:1234/v1"),
        ("llama.cpp", "http://localhost:8080/v1"),
        ("Jan", "http://localhost:1337/v1"),
    ]

    /// Tüm bilinen sunucuları paralel yoklar; erişilebilen + modeli olanları döner
    /// (known sırasını koruyarak).
    static func discover() async -> [DiscoveredBackend] {
        let found = await withTaskGroup(of: DiscoveredBackend?.self) { group -> [DiscoveredBackend] in
            for backend in known {
                group.addTask { await probe(name: backend.name, baseURL: backend.baseURL) }
            }
            var result: [DiscoveredBackend] = []
            for await item in group {
                if let item { result.append(item) }
            }
            return result
        }
        return known.compactMap { entry in found.first { $0.baseURL == entry.baseURL } }
    }

    private static func probe(name: String, baseURL: String) async -> DiscoveredBackend? {
        guard let url = URL(string: baseURL + "/models") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5  // yerel; kapalı sunucu anında reddedilir
        guard
            let (data, response) = try? await URLSession.shared.data(for: request),
            (response as? HTTPURLResponse)?.statusCode == 200,
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let array = object["data"] as? [[String: Any]]
        else { return nil }

        let models = array.compactMap { $0["id"] as? String }.sorted()
        return models.isEmpty ? nil : DiscoveredBackend(name: name, baseURL: baseURL, models: models)
    }
}
