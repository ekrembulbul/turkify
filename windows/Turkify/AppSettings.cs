using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace Turkify;

/// Windows uygulamasının ayarları — **native saklanır** (Registry
/// <c>HKCU\Software\Turkify</c>), config.json **kullanılmaz** (yalnızca Linux/CLI
/// içindir; bkz. ADR 0007). Ayarlar motora <c>turkify serve</c>'e **CLI bayrakları**
/// olarak geçirilir; bayraklar önceliklidir (CLI > env > config), bu yüzden bir
/// config.json olsa bile GUI ayarları kazanır. Ayar değişince motor yeni bayraklarla
/// yeniden başlatılır. (macOS AppSettings.swift'in karşılığı.)
public sealed class AppSettings
{
    public string Model { get; set; } = "";
    public bool UseLLM { get; set; }
    public bool UseMorphology { get; set; } = true;
    public int Timeout { get; set; } = 60; // saniye
    public string BaseURL { get; set; } = "http://localhost:11434/v1";
    public string ApiKey { get; set; } = "";
    public string AssistantPrefill { get; set; } = "";

    /// /chat/completions gövdesine eklenecek ham JSON (boş = gönderilmez).
    public string LlmOptions { get; set; } = "";

    // Varsayılan: Hyper (Ctrl+Alt+Win) — macOS'taki Hyper (Ctrl+Opt+Cmd) ile aynı,
    // cmd→Win. Düz Win-kombinasyonlarının OS çakışmasını azaltır.
    public string[] HotkeyMods { get; set; } = ["ctrl", "alt", "win"]; // düzeltme kısayolu
    public string HotkeyKey { get; set; } = "a";
    public string[] CancelHotkeyMods { get; set; } = ["ctrl", "alt", "win"]; // işlem iptali
    public string CancelHotkeyKey { get; set; } = "q";

    /// UI tercihi: model seçimi otomatik mi (combobox'tan, model/url salt-okunur)
    /// yoksa manuel mi (elle yazılır)?
    public bool AutoModelSelection { get; set; } = true;

    private const string RegistryKeyPath = @"Software\Turkify";

    public static AppSettings Load()
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(RegistryKeyPath);
        if (key is null)
        {
            return new AppSettings();
        }

        var fallback = new AppSettings();
        return new AppSettings
        {
            Model = GetString(key, "Model", fallback.Model),
            UseLLM = GetBool(key, "UseLLM", fallback.UseLLM),
            UseMorphology = GetBool(key, "UseMorphology", fallback.UseMorphology),
            Timeout = GetInt(key, "Timeout", fallback.Timeout),
            BaseURL = GetString(key, "BaseURL", fallback.BaseURL),
            ApiKey = GetString(key, "ApiKey", fallback.ApiKey),
            AssistantPrefill = GetString(key, "AssistantPrefill", fallback.AssistantPrefill),
            LlmOptions = GetString(key, "LlmOptions", fallback.LlmOptions),
            HotkeyMods = GetMods(key, "HotkeyMods", fallback.HotkeyMods),
            HotkeyKey = GetString(key, "HotkeyKey", fallback.HotkeyKey),
            CancelHotkeyMods = GetMods(key, "CancelHotkeyMods", fallback.CancelHotkeyMods),
            CancelHotkeyKey = GetString(key, "CancelHotkeyKey", fallback.CancelHotkeyKey),
            AutoModelSelection = GetBool(key, "AutoModelSelection", fallback.AutoModelSelection),
        };
    }

    public void Save()
    {
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(RegistryKeyPath);
        key.SetValue("Model", Model);
        key.SetValue("UseLLM", UseLLM ? "1" : "0");
        key.SetValue("UseMorphology", UseMorphology ? "1" : "0");
        key.SetValue("Timeout", Timeout.ToString());
        key.SetValue("BaseURL", BaseURL);
        key.SetValue("ApiKey", ApiKey);
        key.SetValue("AssistantPrefill", AssistantPrefill);
        key.SetValue("LlmOptions", LlmOptions);
        key.SetValue("HotkeyMods", string.Join(' ', HotkeyMods));
        key.SetValue("HotkeyKey", HotkeyKey);
        key.SetValue("CancelHotkeyMods", string.Join(' ', CancelHotkeyMods));
        key.SetValue("CancelHotkeyKey", CancelHotkeyKey);
        key.SetValue("AutoModelSelection", AutoModelSelection ? "1" : "0");
    }

    /// Motoru bu ayarlarla başlatacak <c>serve</c> argümanları (CLI bayrakları).
    /// macOS serveArguments() ile aynı bayrak kümesi.
    public IReadOnlyList<string> ServeArguments()
    {
        // --verbose: motorun Tier 2/3 karar günlüğünü stderr'e yazdırır; bu çıktı
        // EngineClient tarafından yakalanıp Log'a (motor kaynağı) düşer. stdout
        // (JSON protokolü) temiz kalır.
        var args = new List<string> { "serve", "--stdio", "--verbose" };
        if (!string.IsNullOrEmpty(Model))
        {
            args.Add("--model");
            args.Add(Model);
        }

        args.Add(UseLLM ? "--llm" : "--no-llm");
        args.Add(UseMorphology ? "--morphology" : "--no-morphology");
        args.Add("--timeout");
        args.Add(Timeout.ToString());

        if (!string.IsNullOrEmpty(BaseURL))
        {
            args.Add("--base-url");
            args.Add(BaseURL);
        }

        if (!string.IsNullOrEmpty(ApiKey))
        {
            args.Add("--api-key");
            args.Add(ApiKey);
        }

        if (!string.IsNullOrEmpty(AssistantPrefill))
        {
            args.Add("--assistant-prefill");
            args.Add(AssistantPrefill);
        }

        // Yalnızca geçerli JSON ise gönder; geçersizse motor hiç başlamazdı.
        string trimmedOptions = LlmOptions.Trim();
        if (trimmedOptions.Length > 0 && IsValidJson(trimmedOptions))
        {
            args.Add("--llm-options");
            args.Add(trimmedOptions);
        }

        return args;
    }

    /// Boş ya da geçerli JSON mu? (UI'da uyarı + serveArguments'ta filtre için.)
    public static bool IsValidJson(string text)
    {
        string trimmed = text.Trim();
        if (trimmed.Length == 0)
        {
            return true;
        }

        try
        {
            using var _ = JsonDocument.Parse(trimmed);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    public string HotkeyDescription => Describe(HotkeyMods, HotkeyKey);

    public string CancelHotkeyDescription => Describe(CancelHotkeyMods, CancelHotkeyKey);

    private static string Describe(string[] mods, string key) =>
        string.Join('+', mods.Select(Capitalize).Append(key.ToUpperInvariant()));

    private static string Capitalize(string s) =>
        s.Length == 0 ? s : char.ToUpperInvariant(s[0]) + s[1..];

    /// Motoru çalıştıracak komut. <c>serve</c> argümanları ayrı eklenir.
    ///
    /// Öncelik:
    ///  1. **Geliştirme:** <c>TURKIFY_PYTHON</c> env'i (venv python + <c>-m turkify</c>).
    ///  2. **Release:** uygulama klasörüne gömülü donmuş motor
    ///     (<c>turkify-engine\turkify-engine.exe</c>; bkz. ADR 0009 / packaging).
    ///  3. **Son çare:** sistem <c>python -m turkify</c> (yalnızca geliştirme fallback'i).
    public static (string Executable, IReadOnlyList<string> PrefixArgs) EngineExecutable()
    {
        string? python = Environment.GetEnvironmentVariable("TURKIFY_PYTHON");
        if (!string.IsNullOrEmpty(python))
        {
            return (python, ["-m", "turkify"]);
        }

        string baseDir = AppContext.BaseDirectory;
        string embedded = Path.Combine(baseDir, "turkify-engine", "turkify-engine.exe");
        if (File.Exists(embedded))
        {
            return (embedded, []);
        }

        return ("python", ["-m", "turkify"]);
    }

    private static string GetString(RegistryKey key, string name, string fallback) =>
        key.GetValue(name) as string ?? fallback;

    private static bool GetBool(RegistryKey key, string name, bool fallback) =>
        key.GetValue(name) is string s ? s == "1" : fallback;

    private static int GetInt(RegistryKey key, string name, int fallback) =>
        key.GetValue(name) is string s && int.TryParse(s, out int v) ? v : fallback;

    private static string[] GetMods(RegistryKey key, string name, string[] fallback) =>
        key.GetValue(name) is string s
            ? s.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            : fallback;
}
