# Turkify — Windows native uygulaması (Faz 6.2)

WPF (.NET 8) tray uygulaması. Global kısayol / pano / tuş simülasyonunu **native**
yapar; metin düzeltmeyi paylaşımlı Python motoruna (`turkify serve --stdio`) bırakır
(bkz. [ADR 0003](../docs/adr/0003-native-per-os-gui.md), [0004](../docs/adr/0004-motor-sinir-protokolu.md)).

Windows'ta kısayol/pano için **ek izin gerekmez** (macOS Accessibility derdi yok).

## Yapı
```
windows/Turkify/
├── Turkify.csproj      # WPF (.NET 8) projesi (net8.0-windows, WinExe)
├── App.xaml(.cs)       # tray (NotifyIcon) + tek-instance + giriş noktası
└── MainWindow.xaml(.cs)# ana pencere (kapatınca gizlenir; çıkış tray menüsünden)
```

## Ön koşul: .NET 8 SDK
`dotnet --version` → `8.0.x`. Yoksa: `winget install Microsoft.DotNet.SDK.8`.

## Ön koşul: Python motoru erişilebilir olmalı
Uygulama motoru `turkify serve --stdio` ile başlatır. Geliştirmede Turkify'ın kurulu
olduğu Python'ı `TURKIFY_PYTHON` ortam değişkeniyle gösterin:

```powershell
$env:TURKIFY_PYTHON = 'C:\Users\<siz>\projects\turkify\.venv\Scripts\python.exe'
```

Hızlı test: `'{"text":"bugun"}' | <python> -m turkify serve --stdio` bir satır JSON
yanıt vermeli.

Release'te motor PyInstaller ile dondurulup uygulama klasörüne gömülür
(`turkify-engine.exe`; Aşama 3 / [ADR 0009](../docs/adr/0009-paketleme-frozen-motor.md)).

## Çalıştırma (geliştirme)
```powershell
cd windows\Turkify
dotnet run
```
Tray'de Turkify ikonu belirir. Çift tık veya sağ tık → **Turkify'ı aç**. Pencereyi
kapatmak uygulamayı sonlandırmaz (gizler); **Çıkış** tray menüsündedir.

## Ayar saklama
Ayarlar **Registry**'de tutulur (`HKCU\Software\Turkify`); `config.json`
**kullanılmaz** ([ADR 0007](../docs/adr/0007-ayar-saklama-gui-native.md)). Korumalı
kelimeler motorun Windows'ta okuduğu yere yazılır:
`%APPDATA%\turkify\protected_words.txt` ([ADR 0008](../docs/adr/0008-korumali-kelimeler-paylasilan-dosya.md)).

## Mimari hatırlatma
- Bu app metni **düzeltmez**; seçimi alır, `serve`'e gönderir, sonucu yapıştırır.
- CLI (`turkify`) bundan bağımsızdır ve her zaman çalışır ([ADR 0006](../docs/adr/0006-cli-birinci-sinif-kalici.md)).
- Düzeltme mantığı Python motorunda (`src/turkify/`).
