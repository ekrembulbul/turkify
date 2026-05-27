using System.Windows.Threading;

namespace Turkify;

public sealed class EmptySelectionException() : Exception("Seçili metin bulunamadı");

/// Seçili metni düzeltme akışı: kopyala → motora gönder → yapıştır → eski panoyu
/// geri yükle. (macOS Corrector.swift'in karşılığı.)
public sealed class Corrector(EngineClient engine, Dispatcher dispatcher)
{
    // macOS'taki gecikmelerle aynı (pano güncellemesi / yapıştırma için).
    private const int AfterCopyDelayMs = 150;
    private const int BeforePasteDelayMs = 50;
    private const int AfterPasteDelayMs = 200;

    /// Akışı çalıştırır. Düzeltilmiş metni döndürür; seçim boşsa <see
    /// cref="EmptySelectionException"/> atar. İptal edilebilir.
    public async Task<string> RunAsync(CancellationToken cancellationToken)
    {
        string? original = ClipboardBridge.Read(dispatcher);
        Log.Info($"akis: basladi; orijinal pano = {Quoted(original)}");

        ClipboardBridge.SendCopy(dispatcher);
        Log.Info("akis: Ctrl+C gonderildi");
        await Task.Delay(AfterCopyDelayMs, cancellationToken).ConfigureAwait(false);

        string? selected = ClipboardBridge.Read(dispatcher);
        Log.Info($"akis: kopya sonrasi pano = {Quoted(selected)}");
        if (string.IsNullOrEmpty(selected))
        {
            Log.Info("akis: secim BOS -> durduruldu");
            throw new EmptySelectionException();
        }

        if (selected == original)
        {
            Log.Info("akis: UYARI pano degismedi (Ctrl+C islememis olabilir; eski pano duzeltilecek)");
        }

        Log.Info("akis: motora gonderiliyor…");
        string corrected = await engine.CorrectAsync(selected, cancellationToken).ConfigureAwait(false);
        Log.Info($"akis: motordan donen = {Quoted(corrected)}");

        ClipboardBridge.Write(dispatcher, corrected);
        await Task.Delay(BeforePasteDelayMs, cancellationToken).ConfigureAwait(false);
        ClipboardBridge.SendPaste(dispatcher);
        Log.Info("akis: Ctrl+V gonderildi");
        await Task.Delay(AfterPasteDelayMs, cancellationToken).ConfigureAwait(false);

        if (original is not null)
        {
            ClipboardBridge.Write(dispatcher, original); // kullanıcının panosunu geri yükle
        }

        Log.Info("akis: tamam");
        return corrected;
    }

    /// Metni tek satıra indirip tırnak içinde döner (log için; kısaltma yok).
    private static string Quoted(string? text) =>
        text is null ? "nil" : "'" + text.Replace("\n", "\\n") + "'";
}
