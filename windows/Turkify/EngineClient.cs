using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace Turkify;

/// Motor hata türleri.
public sealed class EngineException(string message) : Exception(message);

public sealed class EngineNotRunningException() : Exception("Motor çalışmıyor");

public sealed class EngineBadResponseException() : Exception("Motor yanıtı çözülemedi");

/// Python düzeltme motoruyla (<c>turkify serve --stdio</c>) köprü.
///
/// Motoru çocuk süreç olarak başlatır (sıcak tutar) ve satır-bazlı JSON
/// protokolüyle konuşur (bkz. ADR 0004):
///
///     istek :  {"id": 1, "text": "..."}
///     yanıt :  {"id": 1, "corrected": "..."} | {"id": 1, "error": "..."}
///
/// Ayarlar, motoru başlatırken **CLI bayrakları** olarak geçirilir (config.json
/// kullanılmaz — bkz. ADR 0007). Ayar değişince <see cref="Restart"/> ile yeni
/// bayraklarla yeniden başlatılır. (macOS EngineClient.swift'in karşılığı.)
public sealed class EngineClient : IDisposable
{
    private static readonly UTF8Encoding Utf8NoBom = new(encoderShouldEmitUTF8Identifier: false);

    private readonly object _gate = new();
    private readonly ConcurrentDictionary<int, TaskCompletionSource<string>> _pending = new();
    private Process? _process;
    private int _nextId = 1;

    public bool IsRunning
    {
        get
        {
            lock (_gate)
            {
                return _process is { HasExited: false };
            }
        }
    }

    /// Motoru verilen ayarlarla başlatır (önce çalışan varsa durdurur).
    public void Start(AppSettings settings)
    {
        Stop();

        (string executable, IReadOnlyList<string> prefixArgs) = AppSettings.EngineExecutable();
        var startInfo = new ProcessStartInfo
        {
            FileName = executable,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Utf8NoBom,
            StandardErrorEncoding = Utf8NoBom,
            StandardInputEncoding = Utf8NoBom,
        };
        foreach (string arg in prefixArgs)
        {
            startInfo.ArgumentList.Add(arg);
        }

        foreach (string arg in settings.ServeArguments())
        {
            startInfo.ArgumentList.Add(arg);
        }

        Log.Info($"motor komutu: {executable} {string.Join(' ', startInfo.ArgumentList)}");

        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        process.OutputDataReceived += OnOutput;
        process.ErrorDataReceived += OnError;
        process.Exited += (_, _) => Log.Info("motor sonlandi");

        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        lock (_gate)
        {
            _process = process;
        }
    }

    public void Restart(AppSettings settings) => Start(settings);

    /// Motora ateşle-unut bir <c>{"cmd":"reload"}</c> gönderir; motor ayarları ve
    /// korumalı kelime önbelleğini tazeler (model sıcak kalır). Yanıt id taşımadığından
    /// yok sayılır. Motor çalışmıyorsa sessizce atlanır.
    public void Reload()
    {
        WriteLine("{\"cmd\":\"reload\"}");
    }

    public void Stop()
    {
        Process? process;
        lock (_gate)
        {
            process = _process;
            _process = null;
        }

        if (process is not null)
        {
            try
            {
                if (!process.HasExited)
                {
                    // stdin EOF → motor temiz çıkar (serve_stdio EOF'ta döner).
                    process.StandardInput.Close();
                    if (!process.WaitForExit(1000))
                    {
                        process.Kill();
                    }
                }
            }
            catch (InvalidOperationException)
            {
                // süreç zaten gitmiş
            }
            finally
            {
                process.Dispose();
            }
        }

        // Bekleyen tüm istekleri "çalışmıyor" ile sonlandır.
        foreach (KeyValuePair<int, TaskCompletionSource<string>> entry in _pending)
        {
            if (_pending.TryRemove(entry.Key, out TaskCompletionSource<string>? tcs))
            {
                tcs.TrySetException(new EngineNotRunningException());
            }
        }
    }

    /// Metni motora gönderir ve düzeltilmiş halini döndürür. İptal edilirse bekleyen
    /// istek bırakılır (motor isteği arka planda bitirir, yanıtı yok sayılır).
    public async Task<string> CorrectAsync(string text, CancellationToken cancellationToken = default)
    {
        if (!IsRunning)
        {
            throw new EngineNotRunningException();
        }

        int id = Interlocked.Increment(ref _nextId);
        var tcs = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        _pending[id] = tcs;

        string payload = JsonSerializer.Serialize(new RequestPayload(id, text));
        if (!WriteLine(payload))
        {
            _pending.TryRemove(id, out _);
            throw new EngineNotRunningException();
        }

        await using (cancellationToken.Register(() =>
        {
            if (_pending.TryRemove(id, out TaskCompletionSource<string>? pendingTcs))
            {
                pendingTcs.TrySetCanceled(cancellationToken);
            }
        }))
        {
            return await tcs.Task.ConfigureAwait(false);
        }
    }

    private bool WriteLine(string line)
    {
        lock (_gate)
        {
            if (_process is null || _process.HasExited)
            {
                return false;
            }

            try
            {
                // Motor satırı strip() eder; "\n" yeterli (Windows "\r\n" de sorun değil).
                _process.StandardInput.Write(line);
                _process.StandardInput.Write('\n');
                _process.StandardInput.Flush();
                return true;
            }
            catch (IOException)
            {
                return false;
            }
            catch (ObjectDisposedException)
            {
                return false;
            }
        }
    }

    private void OnOutput(object sender, DataReceivedEventArgs e)
    {
        if (string.IsNullOrEmpty(e.Data))
        {
            return;
        }

        HandleLine(e.Data);
    }

    private void OnError(object sender, DataReceivedEventArgs e)
    {
        if (string.IsNullOrEmpty(e.Data))
        {
            return;
        }

        Log.Engine(Log.StripLeadingTimestamp(e.Data));
    }

    private void HandleLine(string line)
    {
        int? id;
        string? corrected;
        string? error;
        try
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("id", out JsonElement idElement))
            {
                return; // id taşımayan yanıt (ör. reload {"ok":true}) yok sayılır
            }

            id = idElement.GetInt32();
            corrected = root.TryGetProperty("corrected", out JsonElement c) ? c.GetString() : null;
            error = root.TryGetProperty("error", out JsonElement err) ? err.GetString() : null;
        }
        catch (JsonException)
        {
            return; // bozuk satır yok sayılır
        }

        if (id is null || !_pending.TryRemove(id.Value, out TaskCompletionSource<string>? tcs))
        {
            return;
        }

        if (corrected is not null)
        {
            tcs.TrySetResult(corrected);
        }
        else if (error is not null)
        {
            tcs.TrySetException(new EngineException(error));
        }
        else
        {
            tcs.TrySetException(new EngineBadResponseException());
        }
    }

    public void Dispose() => Stop();

    private sealed record RequestPayload(int id, string text);
}
