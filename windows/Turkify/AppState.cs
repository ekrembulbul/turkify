using System.ComponentModel;
using System.IO;
using System.Runtime.CompilerServices;
using System.Windows.Threading;

namespace Turkify;

/// Bir log satırı (zaman damgalı, kaynak etiketli).
public sealed record LogLine(string Time, LogSource Source, string Text);

/// Düzeltme sekmesi durumu.
public enum CorrectionPhase
{
    Idle,
    Processing,
    Done,
    Failed,
}

/// Uygulama durumunu ve bileşenleri (motor, kısayol, ayarlar) bir arada tutar.
/// UI'ya veri-bağlama (INotifyPropertyChanged) + olaylarla haber verir; PropertyChanged
/// her zaman UI thread'inde tetiklenir. (macOS AppState'in karşılığı.)
public sealed class AppState : INotifyPropertyChanged, IDisposable
{
    private const int MaxLogLines = 1000;

    private readonly Dispatcher _dispatcher;
    private readonly EngineClient _engine = new();
    private readonly HotKeyManager _hotKeys = new();
    private readonly List<LogLine> _logLines = new();
    private readonly object _logGate = new();

    private Corrector? _corrector;
    private CancellationTokenSource? _correctionCts; // pano akışı (kısayol)
    private CancellationTokenSource? _textCts; // Düzeltme sekmesi
    private volatile bool _busy;

    private string _lastStatus = "Hazır";
    private string _correctionInput = "";
    private string _correctionOutput = "";
    private string _correctionStatus = "Hazır";
    private CorrectionPhase _correctionPhase = CorrectionPhase.Idle;

    public AppState(Dispatcher dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<LogLine>? LogAdded;

    public AppSettings Settings { get; private set; } = AppSettings.Load();

    public bool IsBusy => _busy;

    public bool EngineRunning => _engine.IsRunning;

    public string LastStatus
    {
        get => _lastStatus;
        private set => SetField(ref _lastStatus, value);
    }

    public string CorrectionInput
    {
        get => _correctionInput;
        set => SetField(ref _correctionInput, value);
    }

    public string CorrectionOutput
    {
        get => _correctionOutput;
        private set => SetField(ref _correctionOutput, value);
    }

    public string CorrectionStatus
    {
        get => _correctionStatus;
        private set => SetField(ref _correctionStatus, value);
    }

    public CorrectionPhase CorrectionPhase
    {
        get => _correctionPhase;
        private set
        {
            if (SetField(ref _correctionPhase, value))
            {
                OnPropertyChanged(nameof(CorrectionProcessing));
            }
        }
    }

    public bool CorrectionProcessing => _correctionPhase == CorrectionPhase.Processing;

    public IReadOnlyList<LogLine> LogLines
    {
        get
        {
            lock (_logGate)
            {
                return _logLines.ToArray();
            }
        }
    }

    public void Startup()
    {
        Log.Sink += AppendLog;
        _corrector = new Corrector(_engine, _dispatcher);
        StartEngine();
        RegisterHotKeys();
    }

    /// Ayarları native saklar (Registry), motoru yeni bayraklarla yeniden başlatır
    /// ve kısayolu yeniden kaydeder. config.json kullanılmaz (ADR 0007).
    public void SaveSettings()
    {
        Settings.Save();
        StartEngine();
        RegisterHotKeys();
        LastStatus = EngineRunning ? "Ayarlar kaydedildi" : "Ayarlar kaydedildi (motor başlamadı)";
    }

    // MARK: - Pano akışı (kısayol; seç → düzelt → yapıştır)

    public void RequestCorrection()
    {
        if (_busy)
        {
            Log.Info("requestCorrection: zaten mesgul, atlandi");
            return;
        }

        _busy = true;
        OnPropertyChanged(nameof(IsBusy));
        _correctionCts = new CancellationTokenSource();
        _ = Task.Run(() => CorrectSelectionAsync(_correctionCts.Token));
    }

    public void CancelCorrection() => _correctionCts?.Cancel();

    private async Task CorrectSelectionAsync(CancellationToken cancellationToken)
    {
        try
        {
            string result = await _corrector!.RunAsync(cancellationToken).ConfigureAwait(false);
            LastStatus = "Düzeltildi: " + Truncate(result, 40);
            Log.Info($"correctSelection: OK -> '{result.Replace("\n", "\\n")}'");
        }
        catch (EmptySelectionException)
        {
            LastStatus = "Seçili metin bulunamadı";
            Log.Info("correctSelection: secim bos");
        }
        catch (OperationCanceledException)
        {
            LastStatus = "İşlem iptal edildi";
            Log.Info("correctSelection: iptal edildi");
        }
        catch (EngineException ex)
        {
            LastStatus = "Motor hatası: " + ex.Message;
            Log.Info($"correctSelection: HATA {ex.Message}");
        }
        catch (Exception ex)
        {
            LastStatus = "Hata: " + ex.Message;
            Log.Info($"correctSelection: HATA {ex}");
        }
        finally
        {
            _busy = false;
            OnPropertyChanged(nameof(IsBusy));
            _correctionCts?.Dispose();
            _correctionCts = null;
        }
    }

    // MARK: - Düzeltme sekmesi (metin yaz → düzelt; pano akışından bağımsız)

    /// Giriş metnini motora gönderir; <paramref name="copy"/> ise sonucu panoya da yazar.
    public async void RunTextCorrection(bool copy)
    {
        string text = CorrectionInput;
        if (string.IsNullOrEmpty(text) || CorrectionProcessing)
        {
            return;
        }

        CorrectionPhase = CorrectionPhase.Processing;
        CorrectionStatus = copy ? "Düzeltiliyor (panoya kopyalanacak)…" : "Düzeltiliyor…";
        _textCts = new CancellationTokenSource();
        try
        {
            string result = await _engine.CorrectAsync(text, _textCts.Token);
            CorrectionOutput = result;
            if (copy)
            {
                ClipboardBridge.Write(_dispatcher, result);
                CorrectionStatus = "Düzeltildi ve panoya kopyalandı";
            }
            else
            {
                CorrectionStatus = "Düzeltildi";
            }

            CorrectionPhase = CorrectionPhase.Done;
        }
        catch (OperationCanceledException)
        {
            CorrectionStatus = "İşlem iptal edildi";
            CorrectionPhase = CorrectionPhase.Idle;
        }
        catch (EngineException ex)
        {
            CorrectionStatus = "Motor hatası: " + ex.Message;
            CorrectionPhase = CorrectionPhase.Failed;
        }
        catch (EngineNotRunningException)
        {
            CorrectionStatus = "Motor çalışmıyor";
            CorrectionPhase = CorrectionPhase.Failed;
        }
        catch (Exception ex)
        {
            CorrectionStatus = "Hata: " + ex.Message;
            CorrectionPhase = CorrectionPhase.Failed;
        }
        finally
        {
            _textCts?.Dispose();
            _textCts = null;
        }
    }

    public void CancelTextCorrection()
    {
        if (CorrectionProcessing)
        {
            _textCts?.Cancel();
        }
    }

    public void ClearCorrection()
    {
        if (CorrectionProcessing)
        {
            return;
        }

        CorrectionInput = "";
        CorrectionOutput = "";
        CorrectionStatus = "Hazır";
        CorrectionPhase = CorrectionPhase.Idle;
    }

    // MARK: - Model keşfi

    public Task<IReadOnlyList<DiscoveredBackend>> DiscoverModelsAsync() => ModelDiscovery.DiscoverAsync();

    // MARK: - Korumalı kelimeler (paylaşılan dosya — ADR 0008)

    /// Korumalı kelime dosyasının yolu. Motorun Windows'ta okuduğu konumla AYNI
    /// olmalı: <c>%APPDATA%\turkify\protected_words.txt</c> (config.protected_words_path
    /// ile aynı mantık; TURKIFY_CONFIG verilmişse onun dizini). Bkz. ADR 0008.
    public static string ProtectedWordsPath()
    {
        string? configOverride = Environment.GetEnvironmentVariable("TURKIFY_CONFIG");
        string configFile = !string.IsNullOrEmpty(configOverride)
            ? configOverride
            : Path.Combine(ConfigBaseDir(), "turkify", "config.json");
        string dir = Path.GetDirectoryName(configFile) ?? ConfigBaseDir();
        return Path.Combine(dir, "protected_words.txt");
    }

    private static string ConfigBaseDir()
    {
        string? appData = Environment.GetEnvironmentVariable("APPDATA");
        return !string.IsNullOrEmpty(appData)
            ? appData
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "AppData", "Roaming");
    }

    public string LoadProtectedWords()
    {
        try
        {
            string path = ProtectedWordsPath();
            return File.Exists(path) ? File.ReadAllText(path) : "";
        }
        catch (IOException)
        {
            return "";
        }
    }

    /// Korumalı kelimeleri standart paylaşılan dosyaya yazar ve motora reload gönderir.
    /// Başarılıysa true, dosya yazılamazsa false döner.
    public bool SaveProtectedWords(string text)
    {
        try
        {
            string path = ProtectedWordsPath();
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, text);
            _engine.Reload();
            LastStatus = "Korumalı kelimeler kaydedildi";
            return true;
        }
        catch (Exception ex)
        {
            LastStatus = "Korumalı kelimeler kaydedilemedi: " + ex.Message;
            return false;
        }
    }

    // MARK: - Motor / kısayol

    private void StartEngine()
    {
        try
        {
            _engine.Start(Settings);
            LastStatus = EngineRunning ? "Motor çalışıyor" : "Motor başlamadı";
        }
        catch (Exception ex)
        {
            LastStatus = $"Motor başlatılamadı: {ex.Message}";
        }

        OnPropertyChanged(nameof(EngineRunning));
    }

    public void RegisterHotKeys()
    {
        _hotKeys.UnregisterAll();

        if (!_hotKeys.Register(Settings.HotkeyMods, Settings.HotkeyKey, RequestCorrection))
        {
            LastStatus = $"Düzeltme kısayolu kaydedilemedi ({Settings.HotkeyDescription})";
        }

        if (!_hotKeys.Register(Settings.CancelHotkeyMods, Settings.CancelHotkeyKey, CancelCorrection))
        {
            LastStatus = $"İptal kısayolu kaydedilemedi ({Settings.CancelHotkeyDescription})";
        }
    }

    private void AppendLog(LogSource source, string message)
    {
        var line = new LogLine(DateTime.Now.ToString("HH:mm:ss.fff"), source, message);
        lock (_logGate)
        {
            _logLines.Add(line);
            if (_logLines.Count > MaxLogLines)
            {
                _logLines.RemoveRange(0, _logLines.Count - MaxLogLines);
            }
        }

        LogAdded?.Invoke(line);
    }

    private static string Truncate(string text, int max) =>
        text.Length <= max ? text : text[..max];

    private bool SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }

        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        if (_dispatcher.CheckAccess())
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
        else
        {
            _dispatcher.BeginInvoke(() =>
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName)));
        }
    }

    public void Dispose()
    {
        Log.Sink -= AppendLog;
        _correctionCts?.Cancel();
        _textCts?.Cancel();
        _hotKeys.Dispose();
        _engine.Dispose();
    }
}
