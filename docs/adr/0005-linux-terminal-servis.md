# ADR 0005 — Linux: terminal + systemd servisi (native GUI yok)

**Durum:** ✅ Kabul · [ADR 0003](0003-native-per-os-gui.md)'ün Linux ayağı
· 2026-06 güncellemesi: akış kararları netleşti (aşağıda "Güncelleme").

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
- **Kısayollar config'te tutulmaz.** Düzeltme kısayolu bir DE custom shortcut'tır;
  ince istemciyi çalıştırır (seçim → sokete gönder → yapıştır). Kullanıcı
  kombinasyonu doğrudan GNOME/KDE klavye ayarlarında tanımlar — uygulama bu
  tuşları bilmez/dinlemez. (macOS native uygulaması ise kendi kısayollarını
  UserDefaults'ta saklar; bkz. [ADR 0007](0007-ayar-saklama-gui-native.md).)
- Pano: X11 `xclip`/`xsel`, Wayland `wl-clipboard`. **config.json yalnızca motor
  ayarlarını** (model, base_url, timeout, …) taşır.
- Dağıtım: `.deb`/`.rpm`/AUR veya **Flatpak** (ayrı paketleme fazı).

## Güncelleme (2026-06) — akış kararları

İlk taslakta "seçimi al → düzelt → yapıştır" akışının ayrıntıları ve "iptal"
kısayolu açık bırakılmıştı. MVP (Faz 6.3a) için aşağıdaki kararlar verildi:

### 1. Seçim okuma: PRIMARY selection (tuş simülasyonu YOK)
macOS ince istemcisi seçimi okumak için Cmd+C sentezler. Linux'ta buna **gerek
yok**: X11 ve Wayland'da o an vurgulanmış metin **PRIMARY selection**'da hazırdır
ve doğrudan okunabilir:
- Wayland: `wl-paste --primary --no-newline`
- X11: `xclip -selection primary -o`

Böylece macOS'un "Cmd+C sentezle" problemi (ve onun Accessibility izni) Linux'ta
**tamamen atlanır**; Wayland'da kopya tuşunu enjekte edememe kısıtı okuma tarafını
hiç etkilemez.

### 2. Yapıştırma: pano + `ydotool` (best-effort), elle fallback
Düzeltilmiş metin **panoya** yazılır (`wl-copy` / `xclip -selection clipboard`).
Ardından yapıştırma denenir:
- **`ydotool` kuruluysa** otomatik Ctrl+V enjekte edilir (kernel `uinput`;
  derleyiciden bağımsız çalışır). GNOME/Mutter'da `wtype` **çalışmaz** (yalnızca
  wlroots tabanlı derleyiciler virtual-keyboard protokolünü uygular), bu yüzden
  Wayland'da tek gerçekçi enjeksiyon yolu `ydotool`'dur.
- **`ydotool` yoksa** `notify-send` ile bildirim gösterilir ("düzeltildi —
  Ctrl+V ile yapıştır") ve kullanıcı elle yapıştırır. Düzeltilmiş metin panoda
  kaldığından bu her ortamda (GNOME Wayland dahil) çalışır.

`ydotool`, `/dev/uinput` erişimi ve `ydotoold` daemon'u gerektirir (root ya da
`input` grubu / udev kuralı). Bu yük kullanıcıya bırakılır; istemci `ydotool`'u
en iyi-çaba ile kullanır, başarısızlıkta sessizce elle-yapıştırmaya düşer.

### 3. İptal (cancel): ERTELENDİ
İlk taslak bir "iptal kısayolu" (çalışan isteğe iptal sinyali) tarif ediyordu.
Bu, mevcut motor sınırıyla **uygulanamaz** ve şimdilik **kapsam dışıdır**:
- `serve_socket` bağlantıları **sırayla, tek tek** işler; protokolde `cancel`
  komutu yok ve devam eden bir `correct()` çağrısını kesme yolu yok.
- Deterministik katmanlar (harmony + frekans + morfoloji) çoğu durumu anlık çözer;
  iptal yalnızca Tier 3 (LLM) yoğun ve yavaş kullanıldığında anlam kazanır.

İptal, gerçek ihtiyaç doğunca (Tier 3 yoğunlaşırsa) eklenir; gerektireceği iş:
`serve`'e eşzamanlılık + istek kaydı + `cancel` komutu + kesilebilir `correct()`.
Bkz. [ROADMAP Faz 6.3c](../ROADMAP.md).

### 4. Soket yol sözleşmesi
İnce istemci ve servisin aynı soketi bulması için tek kaynak: `config.socket_path()`.
- `TURKIFY_SOCKET` env değişkeni öncelikli;
- yoksa varsayılan `$XDG_RUNTIME_DIR/turkify/engine.sock`.

systemd unit'i `RuntimeDirectory=turkify` ile `$XDG_RUNTIME_DIR/turkify`'ı oluşturur
ve servisi bu yolda `serve --socket` ile başlatır; istemci aynı varsayılana bağlanır.
Soket düşükse (servis kapalı) istemci **cold-start fallback** yapar (motoru
in-process yükleyip düzeltir) — böylece servis olmadan da çalışır.

### 5. Servis baştan kurulur (cold-start fallback ile)
MVP, `systemd --user` socket servisini **baştan** kurar (motor sıcak; Tier 2
zeyrek yüklemesinin her çağrıda tekrarlanmasını önler). İstemci servis ayaktaysa
sokete bağlanır, değilse cold-start'a düşer; ikisi de aynı sonucu verir.

## Sonuçlar
- ✅ Üçüncü native dil yok; Linux paylaşımlı Python motorunun "servis + paket" kılığı.
- ✅ GTK/tray/Wayland GUI cehenneminden kaçınılır; DE-kısayolu Wayland-uyumlu.
- ✅ Seçim okuma PRIMARY selection ile tuş simülasyonsuz → Wayland'ın enjeksiyon
  kısıtı okuma tarafını hiç etkilemez; izin (Accessibility benzeri) gerekmez.
- ✅ Linux kullanıcısının doğal beklentisi (CLI + config + systemd) karşılanır.
- ✅ Servis kapalıyken bile istemci cold-start ile çalışır (sıfır-servis senaryosu).
- ➖ Wayland'da **otomatik yapıştırma** `ydotool`'a bağlı (uinput izni gerekir);
  yoksa kullanıcı elle yapıştırır. OS kaynaklı; "best-effort". X11'de daha rahat.
- ➖ GNOME'da tray ikonu olmadığından "çalışıyor" göstergesi `systemctl --user
  status` / loglara ve `notify-send` bildirimlerine düşer (menü-bar yok).
- ➖ İptal özelliği yok (ertelendi); Tier 3 yoğunsa elle bekleme gerekir.
- ⚠️ **Paketleme tuzağı:** Flatpak sandbox'ı `/dev/uinput`'a erişimi engeller →
  `ydotool` otomatik yapıştırma Flatpak'te **çalışmaz**. Otomatik yapıştırma
  hedeflendiğinden native paketleme (pipx/AUR/.deb) tercih edilir; karar
  paketleme fazında (bkz. [ADR 0009](0009-paketleme-frozen-motor.md), Faz 6.4).

## Değerlendirilen alternatifler
- **Rust + GTK4 / C++ + Qt native GUI:** tray+Wayland sorunlarını çözmüyor, üçüncü dil
  yükü getiriyor. Reddedildi.
- **Seçimi Cmd+C benzeri tuş enjeksiyonuyla okumak:** Wayland'da ayrıcalıksız
  uygulama kopya tuşu üretemez; PRIMARY selection zaten hazır. Gereksiz. Reddedildi.
- **`wtype` ile yapıştırma:** yalnızca wlroots derleyicilerde çalışır, GNOME/KDE'de
  değil. Yerine `ydotool` (uinput, derleyiciden bağımsız). Reddedildi.
- **Her kısayolda cold-start CLI (servissiz):** basit ama her çağrıda zeyrek
  yüklemesi yavaş. Servisli sıcak model tercih edildi; cold-start yalnızca
  **fallback** olarak korunur.
