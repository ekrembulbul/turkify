# Changelog

Bu dosya, projedeki kayda değer değişiklikleri sürüm sürüm belgeler.

Biçim [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) temellidir ve proje
[Semantic Versioning](https://semver.org/lang/tr/) kullanır.

## [1.3.0] - 2026-06-02

### Eklendi
- **Linux desteği** (terminal/sunucu odaklı): ince istemci (`turkify-fix`) +
  `systemd --user` servisi. Seçili metni (PRIMARY) okur, düzeltip panoya yazar;
  uygulama **manuel Ctrl+V** ile yapılır. Soket üzerinden motor sıcak kalır, servis
  kapalıysa tek seferlik (cold-start) çalışır. `linux/install.sh` temiz klondan
  venv, paket ve sistem araçlarını (ydotool input grubu, GNOME kısayolu) tek adımda
  kurar.
- Linux servisi **yapılandırma değişikliğinde otomatik yenilenir**: config dizini
  izlenir, motor yeniden başlamadan ayarlar ve korumalı kelimeler tazelenir.
- Linux servisi varsayılan olarak **ayrıntılı loglar** (her istek/karar journald'a).
- **Otomatik sürüm yayını** (GitHub Actions): `v*` tag'i push'lanınca macOS DMG ve
  Windows kurulumu derlenip GitHub Release oluşturulur.

### Düzeltildi
- **Düzeltme** sekmesi açılınca metin kutusu otomatik **odaklanır** (macOS + Windows).
- **Log** ekranı konsol gibi davranır: sekme açılınca en yeni satıra kayar, eski
  satırlar bir sınırdan sonra düşer; Windows'ta liste sanallaştırması iyileştirilerek
  kasma azaltıldı.

### Değişti
- macOS dağıtımı artık **imzalı + notarize edilmiş DMG** (`Turkify-<sürüm>.dmg`):
  "tanınmayan geliştirici / hasarlı" uyarısı ve `xattr` adımı **gerekmez**.
- macOS en düşük sürüm **13.0 (Ventura)** — daha eski Mac'lerde de çalışır.

### İndirme
- **macOS:** `Turkify-1.3.0.dmg`
- **Windows:** `TurkifySetup-1.3.0.exe`
- **Linux:** kaynaktan kurulum — `linux/install.sh`

> Windows sürümü imzasızdır; ilk açılışta SmartScreen "Yine de çalıştır" diyebilir.

## [1.2.0] - 2026-05-31

### Eklendi
- macOS ve Windows uygulamalarına **Hakkında** sekmesi: uygulama adı, sürüm,
  kısa açıklama ve bağlantılar (proje sayfası, sürüm notları, lisans, üçüncü
  taraf bileşenler). Sürüm dinamik okunur (macOS Info.plist, Windows assembly).

### Düzeltildi
- **Korumalı kelimeler** artık cümle başında/noktalama sonrası **büyük harfe
  çevrilir**. Büyük harf yapma yalnızca yapısal kalıplardan (URL/e-posta/sayı/
  kod) muaftır; kullanıcı korumalı kelimeleri yalnızca diakritik (şapka)
  restorasyonundan muaf kalır, büyük harften değil.

### İndirme
- **macOS:** `Turkify-1.2.0.zip`
- **Windows:** `TurkifySetup-1.2.0.exe`

> macOS sürümü imzasız/notarize edilmemiştir. Açmak için bir kez:
> `xattr -dr com.apple.quarantine /Applications/Turkify.app`

## [1.1.0] - 2026-05-31

### Eklendi
- **Windows uygulaması** (WPF tray uygulaması; gömülü motor, ek izin gerektirmez).
- **Açık / koyu / otomatik tema** ve yenilenen tasarım dili.
- **Uygulama ikonu** (Windows + macOS); menü-bar simgesi artık "Tr" gösterir.
- macOS menü-bar simgesine **sağ tık** (veya Cmd/Ctrl+tık) ana pencereyi doğrudan açar.
- **Cümle başı** otomatik büyük harfe çevirme seçeneği.
- **Seçimin ilk harfini** büyütme seçeneği.
- İşlem sırasında menü-bar simgesinde **dönen gösterge** (spinner).
- Kısayol **rozetleri** ve kopyala/kaydet işlemlerinde görsel geri bildirim.
- Tek adımda dağıtım çıktısı üreten paketleme betikleri: macOS `build_all.sh`,
  Windows `build_all.ps1`.

### Düzeltildi
- Düzeltme sırasında eski pano metninin yapıştırılması sorunu giderildi.
- Aynı kısayolu yeniden atayınca çalışmama sorunu düzeltildi.
- Kısayol kaydında Windows modifier tutarsızlığı giderildi.
- Otomatik model seçiminde kayıtlı modelin görünmemesi düzeltildi.
- Log ekranında uzun satırlar artık satır kaydırıyor.
- macOS biçimlendirme seçenek açıklamaları ve ayar başlığı düzeltildi.
- Panellerde imleç standart ok olarak düzeltildi.

### Değişti
- Dağıtım çıktı adları sürümlü ve aynı desende: `Turkify-<sürüm>.zip` (macOS),
  `TurkifySetup-<sürüm>.exe` (Windows).

### İndirme
- **macOS:** `Turkify-1.1.0.zip`
- **Windows:** `TurkifySetup-1.1.0.exe`

> macOS sürümü imzasız/notarize edilmemiştir. Açmak için bir kez:
> `xattr -dr com.apple.quarantine /Applications/Turkify.app`

## [1.0.0] - 2026-05-26

### Eklendi
- **macOS menü-bar uygulaması** (SwiftUI): seç → kısayol → düzelt akışı, native
  kısayol/pano/izinler.
- Motor `.app` içine **gömülü** (PyInstaller ile dondurulmuş); kullanıcı Python/venv
  kurmaz.
- Ana pencere: **Düzeltme**, **Motor Ayarları**, **Korumalı Kelimeler**,
  **Diğer Ayarlar**, **Log** bölümleri.
- GUI'de **kısayol kaydedici** (düzeltme ve iptal kısayolları), işlem iptali.
- Kullanıcı **korumalı kelime** dosyası desteği (paylaşımlı dosya).
- Ayarlar native saklanır (UserDefaults); `config.json` macOS'ta kullanılmaz.

### Notlar
- Apple Silicon (arm64) için derlenmiştir.
- İmzasız/notarize edilmemiş; açmak için bir kez
  `xattr -dr com.apple.quarantine /Applications/Turkify.app`.

## [0.1.0] - 2026-05-23

### Eklendi
- İlk genel sürüm: **tamamen lokal Türkçe diakritik (şapka) restorasyon motoru**.
- **Kademeli hibrit mimari:** ses uyumu (soru eki) + Tier 1 deterministik
  deasciifier + Tier 2 frekans/zeyrek morfolojik doğrulama + Tier 3 opsiyonel
  LLM rerank (OpenAI-uyumlu yerel sunucu).
- **CLI birincil arayüz** (`python -m turkify`), `--verbose` ile katman karar günlüğü.
- `turkify serve --stdio` motor servisi (native GUI'ler için stdio JSON köprüsü).
- Çok-platform yapılandırma ve kısayol altyapısı.
- MIT lisansı ve üçüncü taraf atıfları.

[1.3.0]: https://github.com/ekrembulbul/turkify/releases/tag/v1.3.0
[1.2.0]: https://github.com/ekrembulbul/turkify/releases/tag/v1.2.0
[1.1.0]: https://github.com/ekrembulbul/turkify/releases/tag/v1.1.0
[1.0.0]: https://github.com/ekrembulbul/turkify/releases/tag/v1.0.0
[0.1.0]: https://github.com/ekrembulbul/turkify/releases/tag/v0.1.0
