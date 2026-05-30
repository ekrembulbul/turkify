using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Interop;
using Microsoft.Win32;
using KeyEventArgs = System.Windows.Input.KeyEventArgs;

namespace Turkify;

/// Log satırının görünüm temsili. Kaynağa göre renklendirme XAML'de (tema-duyarlı
/// DynamicResource) yapılır; bu yüzden burada yalnızca <see cref="Source"/> taşınır.
public sealed class LogRow(LogLine line)
{
    public string Time { get; } = line.Time;
    public LogSource Source { get; } = line.Source;
    public string Text { get; } = line.Text;
    public string SourceLabel { get; } = line.Source == LogSource.System ? "[sistem]" : "[motor]";
}

public partial class MainWindow : Window
{
    private const string StartupRegistryPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string StartupValueName = "Turkify";

    private readonly AppState _state;
    private readonly ObservableCollection<LogRow> _logs = new();
    private ICollectionView? _logsView;
    private string _logFilter = "Tümü";

    private bool _recording;
    private bool _recordingCancelTarget;
    private bool _themeInitialized;
    private bool _discovering;            // eşzamanlı model keşfini önler (yükleme + radyo init yarışı)
    private bool _suppressModelSelection; // programatik combobox doldurması ayarları ezmesin

    public MainWindow(AppState state)
    {
        _state = state;
        InitializeComponent();
        DataContext = state;

        _logsView = CollectionViewSource.GetDefaultView(_logs);
        _logsView.Filter = LogFilterPredicate;
        LogList.ItemsSource = _logsView;

        // Mevcut log birikimini al, sonra canlı akışa abone ol.
        foreach (LogLine line in state.LogLines)
        {
            _logs.Add(new LogRow(line));
        }

        state.LogAdded += OnLogAdded;

        Loaded += OnLoaded;
        // Pencere handle'ı oluşunca başlık çubuğunu (native) temaya uyarla; tema
        // sonradan değişirse (Auto'da sistem teması dahil) yeniden uygula.
        SourceInitialized += (_, _) => ApplyTitleBarTheme();
        ThemeManager.Changed += ApplyTitleBarTheme;
        Closed += (_, _) =>
        {
            state.LogAdded -= OnLogAdded;
            ThemeManager.Changed -= ApplyTitleBarTheme;
        };
    }

    /// Native başlık çubuğunu (DWM) o an etkin görünüme (açık/koyu) uyarlar.
    private void ApplyTitleBarTheme() =>
        NativeTitleBar.Apply(new WindowInteropHelper(this).Handle, ThemeManager.IsDarkActive);

    /// Tray uygulaması: pencere kapatılınca uygulama sonlanmaz, yalnızca gizlenir.
    /// Çıkış yalnızca tray menüsündeki "Çıkış" ile yapılır.
    protected override void OnClosing(CancelEventArgs e)
    {
        e.Cancel = true;
        Hide();
        base.OnClosing(e);
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        // Model modu radyolarını ayara göre işaretle (Checked handler enable durumunu kurar).
        AutoRadio.IsChecked = _state.Settings.AutoModelSelection;
        ManualRadio.IsChecked = !_state.Settings.AutoModelSelection;

        // Görünüm radyolarını ayara göre işaretle. _themeInitialized, init sırasında
        // OnThemeChanged'in gereksiz Apply/Save yapmasını engeller (tema zaten App
        // startup'ta uygulandı).
        AppTheme theme = ThemeManager.Parse(_state.Settings.Theme);
        ThemeAutoRadio.IsChecked = theme == AppTheme.Auto;
        ThemeLightRadio.IsChecked = theme == AppTheme.Light;
        ThemeDarkRadio.IsChecked = theme == AppTheme.Dark;
        _themeInitialized = true;

        RefreshHotkeyLabels();
        ValidateLlmOptions();
        StartupCheck.IsChecked = IsStartupEnabled();
        ProtectedWordsBox.Text = _state.LoadProtectedWords();
        LogFilterCombo.SelectedIndex = 0; // varsayılan "Tümü" (controls hazırken)
        UpdateLogCount();

        if (_state.Settings.AutoModelSelection)
        {
            _ = RefreshModelsAsync();
        }
    }

    // ============ Düzeltme ============

    private void OnInputKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            if ((Keyboard.Modifiers & ModifierKeys.Shift) != 0)
            {
                return; // ⇧Enter: alt satır (varsayılan davranış)
            }

            e.Handled = true;
            bool copy = (Keyboard.Modifiers & ModifierKeys.Control) != 0;
            _state.RunTextCorrection(copy);
        }
        else if (e.Key == Key.Escape)
        {
            e.Handled = true;
            _state.CancelTextCorrection();
        }
    }

    private void OnCorrect(object sender, RoutedEventArgs e) => _state.RunTextCorrection(copy: false);

    private void OnCorrectAndCopy(object sender, RoutedEventArgs e) => _state.RunTextCorrection(copy: true);

    private void OnCancelTextCorrection(object sender, RoutedEventArgs e) => _state.CancelTextCorrection();

    private void OnClearCorrection(object sender, RoutedEventArgs e) => _state.ClearCorrection();

    private void OnCopyOutput(object sender, RoutedEventArgs e)
    {
        if (!string.IsNullOrEmpty(OutputBox.Text))
        {
            ClipboardBridge.Write(Dispatcher, OutputBox.Text);
        }
    }

    // ============ Motor Ayarları ============

    private void OnSaveSettings(object sender, RoutedEventArgs e) => _state.SaveSettings();

    private void OnModelModeChanged(object sender, RoutedEventArgs e)
    {
        bool auto = AutoRadio.IsChecked == true;
        _state.Settings.AutoModelSelection = auto;

        // Otomatik modda model/sunucu salt-okunur (combobox doldurur).
        ModelBox.IsEnabled = !auto;
        BaseUrlBox.IsEnabled = !auto;
        if (AutoPanel is not null)
        {
            AutoPanel.IsEnabled = auto;
        }

        // Otomatiğe geçince yerel modelleri tara. (Yükleme anında radyo init ile
        // tetiklenen çağrıyla yarışı _discovering bayrağı engeller.)
        if (auto)
        {
            _ = RefreshModelsAsync();
        }
    }

    private void OnModelSelected(object sender, SelectionChangedEventArgs e)
    {
        // Programatik doldurma (Clear/Add/SelectedItem) ayarları ezmesin; ayrıca
        // "Model bulunamadı" placeholder'ı (boş Model) seçilirse ayarları silmesin.
        if (_suppressModelSelection)
        {
            return;
        }

        if (ModelCombo.SelectedItem is ModelItem { Model.Length: > 0 } item)
        {
            _state.Settings.Model = item.Model;
            _state.Settings.BaseURL = item.BaseURL;
            ModelBox.Text = item.Model;
            BaseUrlBox.Text = item.BaseURL;
        }
    }

    private async void OnRefreshModels(object sender, RoutedEventArgs e) => await RefreshModelsAsync();

    /// Yerel LLM sunucularını tarar ve combobox'ı doldurur. macOS davranışıyla aynı:
    /// kayıtlı model her zaman görünür kalır (keşifte yoksa "(kayıtlı)" olarak eklenir);
    /// "Model bulunamadı" yalnızca hiç model VE kayıtlı model yokken gösterilir ve
    /// seçilse bile ayarları ezmez.
    private async Task RefreshModelsAsync()
    {
        if (_discovering)
        {
            return;
        }

        _discovering = true;
        try
        {
            IReadOnlyList<DiscoveredBackend> backends = await _state.DiscoverModelsAsync();

            var items = new List<ModelItem>();
            foreach (DiscoveredBackend backend in backends)
            {
                foreach (string model in backend.Models)
                {
                    items.Add(new ModelItem(model, backend.BaseURL, $"{model}  ({backend.Name})"));
                }
            }

            string savedModel = _state.Settings.Model;

            // Kayıtlı model keşifte yoksa (sunucu kapalı/uzak) yine de görünür kalsın.
            if (savedModel.Length > 0 && items.All(i => i.Model != savedModel))
            {
                items.Insert(0, new ModelItem(savedModel, _state.Settings.BaseURL, $"{savedModel}  (kayıtlı)"));
            }

            // Seçilecek: kayıtlı modele karşılık gelen öğe (varsa). Hiç aday yoksa
            // bilgilendirici, seçilse de ayar ezmeyen placeholder göster.
            ModelItem? toSelect = items.FirstOrDefault(i => i.Model == savedModel);
            if (items.Count == 0)
            {
                var placeholder = new ModelItem("", "", "Model bulunamadı");
                items.Add(placeholder);
                toSelect = placeholder;
            }

            _suppressModelSelection = true;
            ModelCombo.Items.Clear();
            foreach (ModelItem item in items)
            {
                ModelCombo.Items.Add(item);
            }

            ModelCombo.SelectedItem = toSelect;
        }
        finally
        {
            _suppressModelSelection = false;
            _discovering = false;
        }
    }

    private void OnLlmOptionsChanged(object sender, TextChangedEventArgs e) => ValidateLlmOptions();

    private void ValidateLlmOptions()
    {
        if (JsonWarning is null || LlmOptionsBox is null)
        {
            return;
        }

        bool valid = AppSettings.IsValidJson(LlmOptionsBox.Text);
        JsonWarning.Visibility = valid ? Visibility.Collapsed : Visibility.Visible;
    }

    // ============ Diğer Ayarlar (görünüm + kısayollar + başlangıç) ============

    private void OnThemeChanged(object sender, RoutedEventArgs e)
    {
        // Init sırasında (radyolar ayara göre kurulurken) tetiklenmesini yok say.
        if (!_themeInitialized)
        {
            return;
        }

        AppTheme theme =
            ThemeAutoRadio.IsChecked == true ? AppTheme.Auto :
            ThemeDarkRadio.IsChecked == true ? AppTheme.Dark :
            AppTheme.Light;

        ThemeManager.Apply(theme);
        _state.Settings.Theme = theme.ToString();
        _state.Settings.SaveTheme();
    }

    private void OnRecordCorrectionHotkey(object sender, RoutedEventArgs e) => ToggleRecording(cancelTarget: false);

    private void OnRecordCancelHotkey(object sender, RoutedEventArgs e) => ToggleRecording(cancelTarget: true);

    private void ToggleRecording(bool cancelTarget)
    {
        if (_recording)
        {
            StopRecording();
            return;
        }

        _recording = true;
        _recordingCancelTarget = cancelTarget;
        PreviewKeyDown += OnRecordingKeyDown;
        RecordCorrectionButton.Content = cancelTarget ? "Değiştir" : "İptal";
        RecordCancelButton.Content = cancelTarget ? "İptal" : "Değiştir";
        HotkeyHint.Text = "Yeni kombinasyona basın. En az bir Ctrl/Alt/Win ve bir harf/rakam. (Esc: iptal)";
        (cancelTarget ? CancelHotkeyText : CorrectionHotkeyText).Text = "Tuşa basın…";
    }

    private void StopRecording()
    {
        _recording = false;
        PreviewKeyDown -= OnRecordingKeyDown;
        RecordCorrectionButton.Content = "Değiştir";
        RecordCancelButton.Content = "Değiştir";
        HotkeyHint.Text = "“Değiştir”e basıp istediğiniz kombinasyona basın. En az bir Ctrl/Alt/Win ve bir harf/rakam. (Esc: iptal)";
        RefreshHotkeyLabels();
    }

    private void OnRecordingKeyDown(object sender, KeyEventArgs e)
    {
        e.Handled = true;
        Key key = e.Key == Key.System ? e.SystemKey : e.Key;

        if (key == Key.Escape)
        {
            StopRecording();
            return;
        }

        // Yalnızca modifier basıldıysa gerçek tuşu beklemeye devam et.
        if (IsModifierKey(key))
        {
            return;
        }

        string? keyName = KeyName(key);
        if (keyName is null)
        {
            HotkeyHint.Text = "Bu tuş desteklenmiyor (harf veya rakam seçin).";
            return;
        }

        var mods = new List<string>();
        if ((Keyboard.Modifiers & ModifierKeys.Control) != 0) mods.Add("ctrl");
        if ((Keyboard.Modifiers & ModifierKeys.Alt) != 0) mods.Add("alt");
        if (Keyboard.IsKeyDown(Key.LWin) || Keyboard.IsKeyDown(Key.RWin)) mods.Add("win");
        if ((Keyboard.Modifiers & ModifierKeys.Shift) != 0) mods.Add("shift");

        // Shift tek başına yeterli değil; en az bir Ctrl/Alt/Win gerekir.
        if (!mods.Any(m => m != "shift"))
        {
            HotkeyHint.Text = "En az bir Ctrl, Alt veya Win gerekli.";
            return;
        }

        if (_recordingCancelTarget)
        {
            _state.Settings.CancelHotkeyMods = mods.ToArray();
            _state.Settings.CancelHotkeyKey = keyName;
        }
        else
        {
            _state.Settings.HotkeyMods = mods.ToArray();
            _state.Settings.HotkeyKey = keyName;
        }

        _state.Settings.Save();
        _state.RegisterHotKeys();
        StopRecording();
    }

    private void RefreshHotkeyLabels()
    {
        CorrectionHotkeyText.Text = _state.Settings.HotkeyDescription;
        CancelHotkeyText.Text = _state.Settings.CancelHotkeyDescription;
    }

    private static bool IsModifierKey(Key key) => key is
        Key.LeftCtrl or Key.RightCtrl or Key.LeftAlt or Key.RightAlt or
        Key.LeftShift or Key.RightShift or Key.LWin or Key.RWin or Key.System;

    /// WPF Key → harf/rakam adı (kısayol için). Bilinmiyorsa null.
    private static string? KeyName(Key key)
    {
        if (key is >= Key.A and <= Key.Z)
        {
            return ((char)('a' + (key - Key.A))).ToString();
        }

        if (key is >= Key.D0 and <= Key.D9)
        {
            return ((char)('0' + (key - Key.D0))).ToString();
        }

        if (key is >= Key.NumPad0 and <= Key.NumPad9)
        {
            return ((char)('0' + (key - Key.NumPad0))).ToString();
        }

        return null;
    }

    private void OnToggleStartup(object sender, RoutedEventArgs e)
    {
        bool enable = StartupCheck.IsChecked == true;
        try
        {
            using RegistryKey key = Registry.CurrentUser.CreateSubKey(StartupRegistryPath);
            if (enable)
            {
                string exe = Environment.ProcessPath ?? "";
                key.SetValue(StartupValueName, $"\"{exe}\"");
            }
            else
            {
                key.DeleteValue(StartupValueName, throwOnMissingValue: false);
            }
        }
        catch
        {
            // Registry yazılamadı: checkbox'ı gerçek duruma geri al.
            StartupCheck.IsChecked = IsStartupEnabled();
        }
    }

    private static bool IsStartupEnabled()
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(StartupRegistryPath);
        return key?.GetValue(StartupValueName) is not null;
    }

    // ============ Korumalı Kelimeler ============

    private void OnSaveProtectedWords(object sender, RoutedEventArgs e) =>
        _state.SaveProtectedWords(ProtectedWordsBox.Text);

    // ============ Log ============

    private void OnLogAdded(LogLine line)
    {
        Dispatcher.BeginInvoke(() =>
        {
            _logs.Add(new LogRow(line));
            if (_logs.Count > 1000)
            {
                _logs.RemoveAt(0);
            }

            UpdateLogCount();
            AutoScrollLog();
        });
    }

    private void OnLogFilterChanged(object sender, SelectionChangedEventArgs e)
    {
        // XAML yüklenirken (controls henüz oluşmadan) tetiklenebilir; güvenli çık.
        if (_logsView is null || LogList is null)
        {
            return;
        }

        _logFilter = (LogFilterCombo.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "Tümü";
        _logsView.Refresh();
        UpdateLogCount();
        AutoScrollLog();
    }

    private bool LogFilterPredicate(object item) => _logFilter switch
    {
        "Sistem" => item is LogRow { Source: LogSource.System },
        "Motor" => item is LogRow { Source: LogSource.Engine },
        _ => true,
    };

    private void OnClearLog(object sender, RoutedEventArgs e)
    {
        _logs.Clear();
        UpdateLogCount();
    }

    private void UpdateLogCount()
    {
        if (LogCountText is null || _logsView is null)
        {
            return;
        }

        int count = _logsView.Cast<object>().Count();
        LogCountText.Text = $"{count} satır";
    }

    private void AutoScrollLog()
    {
        if (LogList is not null && LogList.Items.Count > 0)
        {
            LogList.ScrollIntoView(LogList.Items[^1]);
        }
    }

    /// ToString, combobox seçim kutusunda gösterilen metni belirler. Özel ComboBox
    /// şablonunda seçili öğe ContentPresenter ile çizilir; DisplayMemberPath seçim
    /// kutusuna uygulanmaz, bu yüzden okunur metni ToString üzerinden veririz
    /// (aksi halde record'un varsayılan "ModelItem { … }" çıktısı görünür).
    private sealed record ModelItem(string Model, string BaseURL, string Display)
    {
        public override string ToString() => Display;
    }
}
