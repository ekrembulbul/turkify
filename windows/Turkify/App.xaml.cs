using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Threading;
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

    // Tray ikonu: normal ("Tr") ve işlem sürerken dönen bekleme çerçeveleri.
    private Icon? _normalIcon;
    private Icon[]? _spinnerFrames;
    private DispatcherTimer? _spinnerTimer;
    private int _spinnerIndex;

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

        _normalIcon = LoadAppIcon();
        _trayIcon = new WinForms.NotifyIcon
        {
            Icon = _normalIcon,
            Text = "Turkify",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _trayIcon.DoubleClick += (_, _) => ShowMainWindow();

        // İşlem sürerken (IsBusy) tray ikonunu dönen bekleme göstergesiyle değiştir.
        _appState!.PropertyChanged += OnAppStatePropertyChanged;
    }

    // ============ Tray bekleme göstergesi (macOS'taki dönen "rays" karşılığı) ============

    private void OnAppStatePropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName != nameof(AppState.IsBusy) || _appState is null)
        {
            return;
        }

        if (_appState.IsBusy)
        {
            StartSpinner();
        }
        else
        {
            StopSpinner();
        }
    }

    private void StartSpinner()
    {
        if (_trayIcon is null)
        {
            return;
        }

        _spinnerFrames ??= BuildSpinnerFrames();
        _spinnerTimer ??= CreateSpinnerTimer();
        _spinnerIndex = 0;
        _trayIcon.Icon = _spinnerFrames[0];
        _spinnerTimer.Start();
    }

    private void StopSpinner()
    {
        _spinnerTimer?.Stop();
        if (_trayIcon is not null && _normalIcon is not null)
        {
            _trayIcon.Icon = _normalIcon;
        }
    }

    private DispatcherTimer CreateSpinnerTimer()
    {
        var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(90) };
        timer.Tick += (_, _) =>
        {
            if (_trayIcon is null || _spinnerFrames is null)
            {
                return;
            }

            _spinnerIndex = (_spinnerIndex + 1) % _spinnerFrames.Length;
            _trayIcon.Icon = _spinnerFrames[_spinnerIndex];
        };
        return timer;
    }

    /// Dönen bekleme göstergesinin çerçeveleri: 8 ışın, baştan kuyruğa solan,
    /// marka mavisi. Her çerçevede parlak baş bir ışın kayar → dönme hissi.
    private static Icon[] BuildSpinnerFrames()
    {
        const int size = 32;
        const int count = 8;
        float cx = size / 2f, cy = size / 2f;
        float r0 = size * 0.24f, r1 = size * 0.44f, penW = size * 0.11f;

        var frames = new Icon[count];
        for (int f = 0; f < count; f++)
        {
            using var bmp = new Bitmap(size, size);
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                for (int i = 0; i < count; i++)
                {
                    int rel = (f - i + count) % count;
                    int alpha = 255 - rel * (195 / (count - 1)); // baş 255 → kuyruk 60
                    double ang = -Math.PI / 2 + i * (2 * Math.PI / count);
                    var p0 = new PointF(cx + (float)Math.Cos(ang) * r0, cy + (float)Math.Sin(ang) * r0);
                    var p1 = new PointF(cx + (float)Math.Cos(ang) * r1, cy + (float)Math.Sin(ang) * r1);
                    using var pen = new Pen(Color.FromArgb(alpha, 0x3E, 0x83, 0xF4), penW)
                    {
                        StartCap = LineCap.Round,
                        EndCap = LineCap.Round,
                    };
                    g.DrawLine(pen, p0, p1);
                }
            }

            // GDI HICON'u yönetilen bir kopyaya çevir, sonra handle'ı serbest bırak (sızıntı yok).
            IntPtr hicon = bmp.GetHicon();
            frames[f] = (Icon)Icon.FromHandle(hicon).Clone();
            DestroyIcon(hicon);
        }

        return frames;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyIcon(IntPtr handle);

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
        _spinnerTimer?.Stop();
        if (_appState is not null)
        {
            _appState.PropertyChanged -= OnAppStatePropertyChanged;
        }

        _appState?.Dispose();
        if (_trayIcon is not null)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
        }

        if (_spinnerFrames is not null)
        {
            foreach (Icon frame in _spinnerFrames)
            {
                frame.Dispose();
            }
        }

        _normalIcon?.Dispose();
        _singleInstanceMutex?.ReleaseMutex();
        _singleInstanceMutex?.Dispose();
        base.OnExit(e);
    }
}
