using System.ComponentModel;
using System.Windows;

namespace Turkify;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }

    /// Tray uygulaması: pencere kapatılınca uygulama sonlanmaz, yalnızca gizlenir.
    /// Çıkış yalnızca tray menüsündeki "Çıkış" ile yapılır.
    protected override void OnClosing(CancelEventArgs e)
    {
        e.Cancel = true;
        Hide();
        base.OnClosing(e);
    }
}
