using System.IO;
using System.Net.Http;
using System.Text.Json;

namespace Turkify;

/// Keşfedilen bir yerel LLM sunucusu ve modelleri (tür/başlık ile).
public sealed record DiscoveredBackend(string Name, string BaseURL, IReadOnlyList<string> Models);

/// Bilinen yerel OpenAI-uyumlu sunucuları tarar ve modelleri **türlerine göre**
/// (Ollama, LM Studio, …) listeler. Her biri <c>/v1/models</c> ucuyla yoklanır.
/// (macOS ModelDiscovery.swift'in karşılığı.)
public static class ModelDiscovery
{
    /// (görünen ad, base_url). Yaygın yerel sunucuların varsayılan portları.
    private static readonly (string Name, string BaseURL)[] Known =
    [
        ("Ollama", "http://localhost:11434/v1"),
        ("LM Studio", "http://localhost:1234/v1"),
        ("llama.cpp", "http://localhost:8080/v1"),
        ("Jan", "http://localhost:1337/v1"),
    ];

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(1.5) };

    /// Tüm bilinen sunucuları paralel yoklar; erişilebilen + modeli olanları döner
    /// (known sırasını koruyarak).
    public static async Task<IReadOnlyList<DiscoveredBackend>> DiscoverAsync()
    {
        IEnumerable<Task<DiscoveredBackend?>> probes =
            Known.Select(entry => ProbeAsync(entry.Name, entry.BaseURL));
        DiscoveredBackend?[] results = await Task.WhenAll(probes).ConfigureAwait(false);
        return results.Where(b => b is not null).Cast<DiscoveredBackend>().ToList();
    }

    private static async Task<DiscoveredBackend?> ProbeAsync(string name, string baseURL)
    {
        try
        {
            using HttpResponseMessage response = await Http.GetAsync(baseURL + "/models").ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            await using Stream stream = await response.Content.ReadAsStreamAsync().ConfigureAwait(false);
            using JsonDocument document = await JsonDocument.ParseAsync(stream).ConfigureAwait(false);
            if (!document.RootElement.TryGetProperty("data", out JsonElement data) ||
                data.ValueKind != JsonValueKind.Array)
            {
                return null;
            }

            var models = data.EnumerateArray()
                .Select(item => item.TryGetProperty("id", out JsonElement id) ? id.GetString() : null)
                .Where(id => !string.IsNullOrEmpty(id))
                .Cast<string>()
                .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return models.Count == 0 ? null : new DiscoveredBackend(name, baseURL, models);
        }
        catch (Exception)
        {
            // Kapalı/erişilemeyen sunucu: sessizce atla (keşif best-effort).
            return null;
        }
    }
}
