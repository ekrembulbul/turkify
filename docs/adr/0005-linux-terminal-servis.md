# ADR 0005 — Linux: terminal + systemd servisi (native GUI yok)

**Durum:** ✅ Kabul · [ADR 0003](0003-native-per-os-gui.md)'ün Linux ayağı

## Bağlam
[ADR 0003](0003-native-per-os-gui.md) "her OS native frontend" diyor. Linux için
native bir GUI (Rust+GTK4 veya C++/Qt) düşünüldü, ama:
- Linux'ta tek bir "native dil" yok; GTK tray'i GNOME'da AppIndicator uzantısı ister.
- **Wayland**, bir uygulamanın global kısayolu kendisi yakalamasına ve tuş/pano
  enjeksiyonuna izin vermez — bu dilden bağımsız, OS kaynaklı bir kısıt.

Proje sahibi: Linux'u terminal-tabanlı, arkada servis + config ile çalışan, repo'dan
kurulabilen bir yazılım olarak sunalım.

## Karar
**Linux native GUI yazmaz; Python'da kalır.** Üçüncü bir native dile (Rust/GTK) gerek yok.

- Arka planda **`systemd --user` servisi** motoru sıcak tutar (`turkify serve --socket`).
- Tetikleme **masaüstü ortamının kendi kısayolu** (GNOME/KDE custom shortcut) ile —
  bir komut/ince istemci çalıştırır. Bu, Wayland'ın "uygulama hotkey grab edemez"
  kısıtını **atlatır** (kısayolu uygulama değil, DE yakalar).
- **Kısayollar config'te tutulmaz.** Hem düzeltme hem de işlem iptali ayrı birer
  DE custom shortcut'tır; her biri bir komut çalıştırır (düzeltme: seçim → sokete
  gönder → yapıştır; iptal: çalışan isteğe iptal sinyali gönder). Kullanıcı
  kombinasyonları doğrudan GNOME/KDE klavye ayarlarında tanımlar — uygulama bu
  tuşları bilmez/dinlemez. (macOS native uygulaması ise kendi kısayollarını
  UserDefaults'ta saklar; bkz. [ADR 0007](0007-ayar-saklama-gui-native.md).)
- Pano: X11 `xclip`/`xsel`, Wayland `wl-clipboard`. **config.json yalnızca motor
  ayarlarını** (model, base_url, timeout, …) taşır.
- Dağıtım: `.deb`/`.rpm`/AUR veya **Flatpak** (ayrı paketleme fazı).

## Sonuçlar
- ✅ Üçüncü native dil yok; Linux paylaşımlı Python motorunun "servis + paket" kılığı.
- ✅ GTK/tray/Wayland GUI cehenneminden kaçınılır; DE-kısayolu Wayland-uyumlu.
- ✅ Linux kullanıcısının doğal beklentisi (CLI + config + systemd) karşılanır.
- ➖ Wayland'da **yapıştırma enjeksiyonu** hâlâ pürüzlü (`wtype`/`ydotool` gerekebilir
  veya kullanıcı elle yapıştırır). OS kaynaklı; "best-effort" kalır. X11'de sorunsuz.
- ➖ GNOME'da tray ikonu olmadığından "çalışıyor" göstergesi terminal/loglara düşer
  (menü-bar yok).

## Değerlendirilen alternatifler
- **Rust + GTK4 / C++ + Qt native GUI:** tray+Wayland sorunlarını çözmüyor, üçüncü dil
  yükü getiriyor. Reddedildi.
- **Her kısayolda cold-start CLI:** servissiz, basit ama yavaş. Servisli sıcak model tercih edildi
  (MVP'de cold-start ile başlanabilir).
