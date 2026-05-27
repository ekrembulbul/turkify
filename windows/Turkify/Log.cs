namespace Turkify;

/// Log kaynağı: sistem (native app) ya da motor (Python serve stderr).
public enum LogSource
{
    System,
    Engine,
}

/// Tanı günlüğü köprüsü. Üreten kod kaynağı bilmez; <see cref="Sink"/> aboneliği
/// (AppState) satırları zaman damgalı olarak toplar ve UI'ya iletir.
/// (macOS Log.swift'in karşılığı.)
public static class Log
{
    public static event Action<LogSource, string>? Sink;

    public static void Info(string message) => Sink?.Invoke(LogSource.System, message);

    public static void Engine(string message) => Sink?.Invoke(LogSource.Engine, message);

    /// Motorun <c>--verbose</c> çıktısı her satıra <c>HH:MM:SS.SSS </c> zaman damgası
    /// ekler; Log görünümü kendi zaman sütununu gösterdiği için bu öneki ayıklarız
    /// (çift zaman damgasını önler). Desen eşleşmezse satır olduğu gibi döner.
    public static string StripLeadingTimestamp(string line)
    {
        const int prefixLength = 13; // "HH:MM:SS.SSS " = 12 karakter + boşluk
        if (line.Length <= prefixLength)
        {
            return line;
        }

        bool IsDigit(int i) => char.IsDigit(line[i]);
        bool matches =
            IsDigit(0) && IsDigit(1) && line[2] == ':' &&
            IsDigit(3) && IsDigit(4) && line[5] == ':' &&
            IsDigit(6) && IsDigit(7) && line[8] == '.' &&
            IsDigit(9) && IsDigit(10) && IsDigit(11) && line[12] == ' ';

        return matches ? line[prefixLength..] : line;
    }
}
