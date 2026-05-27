using System.Runtime.InteropServices;
using System.Windows.Interop;

namespace Turkify;

/// Global kısayol yöneticisi — Win32 <c>RegisterHotKey</c> + <c>WM_HOTKEY</c> ile.
/// Windows'ta sistem geneli kısayol için **ek izin gerekmez** (macOS Carbon
/// HotKey'in karşılığı; orada Accessibility de ayrı bir izindi).
///
/// Mesaj almak için bir pencere tutamacı (HWND) gerekir; görünmez bir
/// message-only <see cref="HwndSource"/> oluşturup <c>WM_HOTKEY</c>'i dinleriz.
/// UI thread'inde oluşturulmalıdır (kanca o thread'de çalışır).
public sealed class HotKeyManager : IDisposable
{
    private const int WmHotKey = 0x0312;

    private const uint ModAlt = 0x0001;
    private const uint ModControl = 0x0002;
    private const uint ModShift = 0x0004;
    private const uint ModWin = 0x0008;
    private const uint ModNoRepeat = 0x4000;

    private readonly HwndSource _source;
    private readonly Dictionary<int, Action> _actions = new();
    private int _nextId = 1;

    public HotKeyManager()
    {
        var parameters = new HwndSourceParameters("TurkifyHotKey")
        {
            // Message-only pencere (HWND_MESSAGE = -3): görünmez, yalnızca mesaj alır.
            ParentWindow = new IntPtr(-3),
            Width = 0,
            Height = 0,
        };
        _source = new HwndSource(parameters);
        _source.AddHook(WndProc);
    }

    /// Bir kısayolu kaydeder. Başarılıysa true; kombinasyon başka uygulamada
    /// kayıtlıysa (RegisterHotKey false döner) ya da tuş desteklenmiyorsa false.
    public bool Register(string[] mods, string key, Action action)
    {
        ushort? virtualKey = VirtualKeyFor(key);
        if (virtualKey is null)
        {
            return false;
        }

        int id = _nextId++;
        uint modifiers = ModifiersFrom(mods) | ModNoRepeat;
        if (!RegisterHotKey(_source.Handle, id, modifiers, virtualKey.Value))
        {
            return false;
        }

        _actions[id] = action;
        return true;
    }

    /// Tüm kayıtlı kısayolları kaldırır (yeniden kayıttan önce çağrılır).
    public void UnregisterAll()
    {
        foreach (int id in _actions.Keys)
        {
            UnregisterHotKey(_source.Handle, id);
        }

        _actions.Clear();
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WmHotKey && _actions.TryGetValue(wParam.ToInt32(), out Action? action))
        {
            action();
            handled = true;
        }

        return IntPtr.Zero;
    }

    public void Dispose()
    {
        UnregisterAll();
        _source.RemoveHook(WndProc);
        _source.Dispose();
    }

    /// Tek harf/rakam → Win32 sanal tuş kodu (VK). Harfler 'A'-'Z' (0x41-0x5A),
    /// rakamlar '0'-'9' (0x30-0x39) ile aynıdır. Bilinmiyorsa null.
    public static ushort? VirtualKeyFor(string key)
    {
        if (key.Length != 1)
        {
            return null;
        }

        char c = char.ToUpperInvariant(key[0]);
        if (c is >= 'A' and <= 'Z')
        {
            return c;
        }

        if (c is >= '0' and <= '9')
        {
            return c;
        }

        return null;
    }

    /// Modifier adlarını Win32 maskesine çevirir. macOS adlarıyla uyumlu: "cmd"/
    /// "win"/"super" → Windows tuşu.
    public static uint ModifiersFrom(string[] mods)
    {
        uint mask = 0;
        foreach (string mod in mods)
        {
            switch (mod.ToLowerInvariant())
            {
                case "ctrl":
                case "control":
                    mask |= ModControl;
                    break;
                case "alt":
                case "opt":
                case "option":
                    mask |= ModAlt;
                    break;
                case "cmd":
                case "command":
                case "win":
                case "windows":
                case "super":
                    mask |= ModWin;
                    break;
                case "shift":
                    mask |= ModShift;
                    break;
            }
        }

        return mask;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);
}
