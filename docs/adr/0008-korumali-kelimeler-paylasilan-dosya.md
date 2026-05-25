# ADR 0008 — Korumalı kelimeler: kullanıcı dosyası (paket listesi yalnızca örnek)

**Durum:** ✅ Kabul · [ADR 0007](0007-ayar-saklama-gui-native.md)'nin kapsamını inceltir

## Bağlam
Korumalı kelimeler diakritik dönüşümünden muaf tutulacak yabancı/teknik
terimlerdir; **motorda (Python)** `protect.py` tarafından okunup `engine.correct`
içinde kullanılır. Eskiden repo'yla gelen tek bir dosya (`config/protected_words.txt`)
**otomatik** yükleniyordu; kullanıcı kendi listesini yönetemiyordu.

Kullanıcının bu listeyi (özellikle native GUI'den) **tam** yönetebilmesi isteniyor:
kelime ekleyebilmeli **ve çıkarabilmeli**. Otomatik yüklenen bir paket listesiyle
"birleştirme" yapılırsa kullanıcı yerleşik bir kelimeyi kaldıramaz (yalnızca
ekleyebilir) — bu, "istediğim gibi yönetebilmeliyim" beklentisini karşılamaz.

## Karar
**Yalnızca kullanıcı dosyasındaki kelimeler korunur.** Paketle gelen liste
**otomatik yüklenmez**; yalnızca kopyalanacak bir **örnektir**.

- Repo'daki dosya `config/protected_words.example.txt` olarak adlandırılır
  (`config.example.json` ile aynı mantık). Motor bu dosyayı **hiç referans almaz**.
- Aktif korumalı kelimeler tek bir **kullanıcı dosyasından** gelir:
  - macOS / Linux: `~/.config/turkify/protected_words.txt` (`$XDG_CONFIG_HOME` varsa o)
  - Windows: `%APPDATA%\turkify\protected_words.txt`
  - `--protected-words-file PATH` bayrağı / `protected_words_file` config alanı ile
    özel bir yol verilebilir; verilmezse yukarıdaki standart konum kullanılır.
  - Dosya yoksa kelime-listesi koruması **boştur** (URL/e-posta/sayı/Türkçe-karakter
    koruması yine uygulanır).
- Birleştirme (merge) **yoktur**: dosya neyi içeriyorsa korunan tam liste odur →
  kullanıcı tam kontrole sahip (ekler **ve** çıkarır).

Tüm arayüzler **aynı kullanıcı dosyasını** okur/yazar:

- **CLI / Linux servisi:** kullanıcı dosyayı doğrudan düzenler; motor
  `{"cmd":"reload"}` ile listeyi tazeler.
- **macOS / Windows GUI:** çok-satırlı editör; kaydedince aynı dosyaya yazar ve
  motora reload gönderir.

Bu, [ADR 0007](0007-ayar-saklama-gui-native.md)'yi **çelişmez, inceltir**: tekil
çalışma-zamanı ayarları (model, timeout, kısayol) native saklanır; **veri listeleri**
(korumalı kelimeler) paylaşılan dosyada tutulur, çünkü arayüzler arası tutarlılık
gerekir (CLI'da eklenen kelime GUI'de de geçerli olmalı).

## Sonuçlar
- ✅ Kullanıcı tam kontrol: kelime ekler ve çıkarır; gizli/otomatik bir liste yok.
- ✅ Tek mekanizma; CLI, Linux, macOS, Windows aynı dosyayı paylaşır.
- ✅ Editörde görünen liste = korunan tam liste (şaşırtıcı "gizli varsayılan" yok).
- ✅ Kalıcılık bedava (dosya); `reload` zaten var.
- ➖ **Davranış değişikliği:** Önceden "framework", "mail" gibi terimler kutudan
  çıkar korunuyordu; artık kullanıcı dosyası oluşturulana kadar **korunmaz**.
  Başlamak için örnek kopyalanır:
  `cp config/protected_words.example.txt ~/.config/turkify/protected_words.txt`.
- ➖ `engine._protected_words()` `lru_cache`'lidir; `reload` sırasında
  `reload_protected_words()` ile temizlenmelidir.
- ➖ macOS GUI config dizinine bir **veri dosyası** yazar (config.json değil); ADR
  0007'nin ruhuyla uyumlu (yazılan şey ayar deposu değil, motor veri girdisi).

## Değerlendirilen alternatifler
- **Paket listesi ∪ kullanıcı dosyası (merge):** kullanıcı yerleşik bir kelimeyi
  kaldıramaz; "tam kontrol" beklentisini karşılamaz. Reddedildi (bu ADR'nin ilk
  taslağıydı; tam yönetim için terk edildi).
- **Serve protokolüyle bellekte gönderme (`{"cmd":"set_protected_words",[...]}`):**
  kalıcılık native depo + her açılışta yeniden gönderme; Linux yine dosya ister;
  yeni protokol yüzeyi. Reddedildi.
- **Listeyi CLI bayrağı olarak geçirmek (`--protected-words "a,b,c"`):** uzun
  listelerde elverişsiz. Reddedildi.
