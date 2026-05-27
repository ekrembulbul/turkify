using System.Windows.Threading;

namespace Turkify;

/// Bir log satırı (zaman damgalı, kaynak etiketli).
public sealed record LogLine(string Time, LogSource Source, string Text);

/// Uygulama durumunu ve bileşenleri (motor, kısayol, ayarlar) bir arada tutar.
/// UI'dan bağımsızdır (yalnızca <see cref="Dispatcher"/>'a bağlı); olaylarla UI'ya
/// haber verir. (macOS AppState'in çekirdek mantığının karşılığı.)
public sealed class AppState : IDisposable
{
    private const int MaxLogLines = 1000;

    private readonly Dispatcher _dispatcher;
    private readonly EngineClient _engine = new();
    private readonly HotKeyManager _hotKeys = new();
    private readonly List<LogLine> _logLines = new();
    private readonly object _logGate = new();

    private Corrector? _corrector;
    private CancellationTokenSource? _correctionCts;
    private volatile bool _busy;

    public AppState(Dispatcher dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public AppSettings Settings { get; private set; } = AppSettings.Load();

    public bool IsBusy => _busy;

    public string LastStatus { get; private set; } = "Hazır";

    public bool EngineRunning => _engine.IsRunning;

    public event Action? StatusChanged;

    public event Action<LogLine>? LogAdded;

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
        SetStatus(EngineRunning ? "Ayarlar kaydedildi" : "Ayarlar kaydedildi (motor başlamadı)");
    }

    /// Düzeltmeyi iptal edilebilir bir görev olarak başlatır (kısayol/menü çağırır).
    public void RequestCorrection()
    {
        if (_busy)
        {
            Log.Info("requestCorrection: zaten mesgul, atlandi");
            return;
        }

        _busy = true;
        _correctionCts = new CancellationTokenSource();
        _ = Task.Run(() => CorrectSelectionAsync(_correctionCts.Token));
    }

    /// Devam eden düzeltmeyi iptal eder (LLM beklemesi dahil).
    public void CancelCorrection() => _correctionCts?.Cancel();

    private async Task CorrectSelectionAsync(CancellationToken cancellationToken)
    {
        try
        {
            string result = await _corrector!.RunAsync(cancellationToken).ConfigureAwait(false);
            SetStatus("Düzeltildi: " + Truncate(result, 40));
            Log.Info($"correctSelection: OK -> '{result.Replace("\n", "\\n")}'");
        }
        catch (EmptySelectionException)
        {
            SetStatus("Seçili metin bulunamadı");
            Log.Info("correctSelection: secim bos");
        }
        catch (OperationCanceledException)
        {
            SetStatus("İşlem iptal edildi");
            Log.Info("correctSelection: iptal edildi");
        }
        catch (EngineException ex)
        {
            SetStatus("Motor hatası: " + ex.Message);
            Log.Info($"correctSelection: HATA {ex.Message}");
        }
        catch (Exception ex)
        {
            SetStatus("Hata: " + ex.Message);
            Log.Info($"correctSelection: HATA {ex}");
        }
        finally
        {
            _busy = false;
            _correctionCts?.Dispose();
            _correctionCts = null;
        }
    }

    private void StartEngine()
    {
        try
        {
            _engine.Start(Settings);
            SetStatus(EngineRunning ? "Motor çalışıyor" : "Motor başlamadı");
        }
        catch (Exception ex)
        {
            SetStatus($"Motor başlatılamadı: {ex.Message}");
        }
    }

    private void RegisterHotKeys()
    {
        _hotKeys.UnregisterAll();

        if (!_hotKeys.Register(Settings.HotkeyMods, Settings.HotkeyKey, RequestCorrection))
        {
            SetStatus($"Düzeltme kısayolu kaydedilemedi ({Settings.HotkeyDescription})");
        }

        if (!_hotKeys.Register(Settings.CancelHotkeyMods, Settings.CancelHotkeyKey, CancelCorrection))
        {
            SetStatus($"İptal kısayolu kaydedilemedi ({Settings.CancelHotkeyDescription})");
        }
    }

    private void SetStatus(string status)
    {
        LastStatus = status;
        StatusChanged?.Invoke();
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

    public void Dispose()
    {
        Log.Sink -= AppendLog;
        _correctionCts?.Cancel();
        _hotKeys.Dispose();
        _engine.Dispose();
    }
}
