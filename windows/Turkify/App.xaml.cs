using System.Drawing;
using System.Windows;
using WinForms = System.Windows.Forms;
using Application = System.Windows.Application;

namespace Turkify;

/// <summary>
/// Tray uygulaması giriş noktası. Pencere açılışta görünmez; kullanıcı tray
/// ikonundan açar (macOS menü-bar app'inin Windows karşılığı, bkz. ADR 0003).
/// </summary>
public partial class App : Application
{
    // Tek-instance kilidi: ikinci kez başlatılırsa yeni süreç sessizce çıkar.
    private const string SingleInstanceMutexName = "Turkify.SingleInstance.Mutex";
    private Mutex? _singleInstanceMutex;

    private WinForms.NotifyIcon? _trayIcon;
    private MainWindow? _mainWindow;
    private AppState? _appState;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _singleInstanceMutex = new Mutex(initiallyOwned: true, SingleInstanceMutexName, out bool isNew);
        if (!isNew)
        {
            Shutdown();
            return;
        }

        _appState = new AppState(Dispatcher);
        _appState.Startup();

        // Pencere oluşturulmadan önce temayı uygula ki ilk açılışta doğru renkler gelsin.
        ThemeManager.Apply(ThemeManager.Parse(_appState.Settings.Theme));

        _mainWindow = new MainWindow(_appState);
        SetUpTrayIcon();

        // --show: doğrudan ana pencereye aç (aksi halde yalnızca tray'de başlar).
        if (e.Args.Contains("--show"))
        {
            ShowMainWindow();
        }
    }

    private void SetUpTrayIcon()
    {
        var menu = new WinForms.ContextMenuStrip();
        menu.Items.Add("Turkify'ı aç", null, (_, _) => ShowMainWindow());
        menu.Items.Add(new WinForms.ToolStripSeparator());
        menu.Items.Add("Seçili metni düzelt", null, (_, _) => _appState?.RequestCorrection());
        menu.Items.Add("İşlemi iptal et", null, (_, _) => _appState?.CancelCorrection());
        menu.Items.Add(new WinForms.ToolStripSeparator());
        menu.Items.Add("Çıkış", null, (_, _) => Shutdown());

        _trayIcon = new WinForms.NotifyIcon
        {
            Icon = LoadAppIcon(),
            Text = "Turkify",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _trayIcon.DoubleClick += (_, _) => ShowMainWindow();
    }

    /// Tray ikonu: gömülü Turkify.ico'dan tray'e uygun küçük boyutu seçer.
    /// Kaynak bulunamazsa sistem ikonuna düşer (uygulama yine de açılır).
    private static Icon LoadAppIcon()
    {
        try
        {
            var info = Application.GetResourceStream(new Uri("pack://application:,,,/Assets/Turkify.ico"));
            if (info is not null)
            {
                using var stream = info.Stream;
                return new Icon(stream, WinForms.SystemInformation.SmallIconSize);
            }
        }
        catch (Exception)
        {
            // Kaynak okunamadı: aşağıdaki sistem ikonuna düş.
        }

        return SystemIcons.Application;
    }

    private void ShowMainWindow()
    {
        _mainWindow ??= new MainWindow(_appState!);
        _mainWindow.Show();
        if (_mainWindow.WindowState == WindowState.Minimized)
        {
            _mainWindow.WindowState = WindowState.Normal;
        }
        _mainWindow.Activate();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _appState?.Dispose();
        if (_trayIcon is not null)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
        }
        _singleInstanceMutex?.ReleaseMutex();
        _singleInstanceMutex?.Dispose();
        base.OnExit(e);
    }
}
