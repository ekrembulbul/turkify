using System.Runtime.InteropServices;
using System.Windows;
using Microsoft.Win32;
using Application = System.Windows.Application;

namespace Turkify;

/// Uygulamanın görünüm modu. <see cref="Auto"/> Windows sistem temasını izler.
public enum AppTheme
{
    Light,
    Dark,
    Auto,
}

/// <summary>
/// Açık/koyu temayı yönetir: aktif renk paletini (Palette.Light/Dark.xaml) çalışma
/// anında <see cref="Application"/> kaynaklarına takar. <see cref="AppTheme.Auto"/>
/// modunda Windows sistem temasını okur ve sistem teması değiştiğinde UI'yı canlı
/// günceller. (macOS tarafının NSApp.appearance = nil otomatik davranışının karşılığı.)
/// </summary>
public static class ThemeManager
{
    // Windows kişiselleştirme: AppsUseLightTheme (REG_DWORD) 0 = koyu, 1 = açık.
    private const string PersonalizeKeyPath =
        @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";
    private const string AppsUseLightThemeValue = "AppsUseLightTheme";

    private static readonly Uri LightPalette =
        new("pack://application:,,,/Themes/Palette.Light.xaml", UriKind.Absolute);
    private static readonly Uri DarkPalette =
        new("pack://application:,,,/Themes/Palette.Dark.xaml", UriKind.Absolute);

    private static AppTheme _current = AppTheme.Auto;
    private static ResourceDictionary? _activePalette;
    private static bool _systemHookAttached;

    public static AppTheme Current => _current;

    /// Şu an etkin olan görünüm koyu mu? (Auto modda sistemden çözülmüş hâli.)
    public static bool IsDarkActive { get; private set; }

    /// Etkin görünüm (açık/koyu) değiştiğinde UI thread'inde tetiklenir. Pencere
    /// başlık çubuğunu (native, DWM) temaya uyarlamak için kullanılır.
    public static event Action? Changed;

    /// Ayarda saklanan metni (örn. "Auto") <see cref="AppTheme"/>'e çevirir.
    /// Bilinmeyen/boş değer güvenli varsayılan olan <see cref="AppTheme.Auto"/>'ya düşer.
    public static AppTheme Parse(string? value) => value switch
    {
        "Light" => AppTheme.Light,
        "Dark" => AppTheme.Dark,
        _ => AppTheme.Auto,
    };

    /// <summary>İstenen temayı uygular. Auto ise sistemden çözülür ve sistem
    /// değişiklikleri dinlenmeye başlanır; aksi halde dinleme bırakılır.</summary>
    public static void Apply(AppTheme theme)
    {
        _current = theme;
        SwapPalette(ResolveDark(theme));
        UpdateSystemHook(listen: theme == AppTheme.Auto);
    }

    private static bool ResolveDark(AppTheme theme) => theme switch
    {
        AppTheme.Dark => true,
        AppTheme.Light => false,
        _ => IsSystemDark(),
    };

    private static void SwapPalette(bool dark)
    {
        Application? app = Application.Current;
        if (app is null)
        {
            return;
        }

        var next = new ResourceDictionary { Source = dark ? DarkPalette : LightPalette };
        var merged = app.Resources.MergedDictionaries;

        // Yeni paleti ekle, sonra eskisini çıkar: DynamicResource referansları en az
        // bir an boşta kalmaz (anahtarlar yeni sözlükte zaten mevcut).
        merged.Add(next);
        if (_activePalette is not null)
        {
            merged.Remove(_activePalette);
        }

        _activePalette = next;
        IsDarkActive = dark;
        Changed?.Invoke();
    }

    /// Windows uygulamaları için koyu tema mı aktif? Anahtar/değer yoksa açık varsayar.
    private static bool IsSystemDark()
    {
        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(PersonalizeKeyPath);
            return key?.GetValue(AppsUseLightThemeValue) is int v && v == 0;
        }
        catch (Exception)
        {
            // Registry okunamazsa koyu olduğunu varsaymak yerine açıkta kal (güvenli taraf).
            return false;
        }
    }

    private static void UpdateSystemHook(bool listen)
    {
        if (listen && !_systemHookAttached)
        {
            SystemEvents.UserPreferenceChanged += OnUserPreferenceChanged;
            _systemHookAttached = true;
        }
        else if (!listen && _systemHookAttached)
        {
            SystemEvents.UserPreferenceChanged -= OnUserPreferenceChanged;
            _systemHookAttached = false;
        }
    }

    private static void OnUserPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
    {
        // Tema değişimi "General" kategorisinde gelir. Yalnızca Auto modda tepki ver.
        if (e.Category != UserPreferenceCategory.General || _current != AppTheme.Auto)
        {
            return;
        }

        // Olay UI thread'inde gelmeyebilir; palet değişimi UI thread'inde yapılmalı.
        Application.Current?.Dispatcher.BeginInvoke(() => SwapPalette(IsSystemDark()));
    }
}

/// Pencerenin native başlık çubuğunu (DWM) koyu/açık temaya uyarlar. WPF içerik
/// alanını temalandırır ama non-client (başlık) alanı OS'e aittir; bu API ile
/// onu da temaya uydururuz. Windows 10 2004+ / Windows 11 destekler; eski
/// sürümlerde çağrı sessizce yok sayılır (DWM hata kodu döner, atılmaz).
internal static class NativeTitleBar
{
    private const int UseImmersiveDarkMode = 20;       // Win10 2004+/Win11
    private const int UseImmersiveDarkModeLegacy = 19; // Win10 1809-1903

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

    public static void Apply(IntPtr hwnd, bool dark)
    {
        if (hwnd == IntPtr.Zero)
        {
            return;
        }

        int value = dark ? 1 : 0;
        if (DwmSetWindowAttribute(hwnd, UseImmersiveDarkMode, ref value, sizeof(int)) != 0)
        {
            DwmSetWindowAttribute(hwnd, UseImmersiveDarkModeLegacy, ref value, sizeof(int));
        }
    }
}
