# ADR 0007 — Ayar saklama: GUI native, config.json Linux/CLI'ya özgü

**Durum:** ✅ Kabul · [ADR 0003](0003-native-per-os-gui.md)/[0005](0005-linux-terminal-servis.md)'i tamamlar

## Bağlam
`config.json` çok-platform ayar mekanizması olarak tasarlanmıştı. Ancak macOS ve
Windows'ta artık **native GUI** var; kullanıcı ayarları arayüzden yönetiyor. Bir
JSON dosyasını ayrıca düzenlemek/senkronlamak hem gereksiz hem de native-olmayan
bir deneyim.

## Karar
- **macOS/Windows (GUI):** ayarlar **native saklanır** (macOS `UserDefaults`,
  Windows muhtemelen registry/native). config.json **kullanılmaz**. GUI, motoru
  (`turkify serve`) bu ayarları **CLI bayrakları** olarak geçirerek başlatır.
  Ayar değişince motor yeni bayraklarla **yeniden başlatılır**.
- **Linux (servis) + CLI:** `config.json` mekanizması geçerlidir (GUI yok).
- Öncelik (CLI > env > config) sayesinde GUI'nin geçtiği bayraklar, ortamda bir
  config.json olsa bile **kazanır** — yani GUI ile CLI aynı makinede çakışmadan yaşar.

## Sonuçlar
- ✅ macOS/Windows kullanıcısı tek bir yerden (GUI) ayar yapar; dosya düzenlemez.
- ✅ Ayarlar platformun doğal yerinde saklanır (UserDefaults vb.).
- ✅ `serve` zaten tüm ayarları bayrak olarak kabul ettiğinden ([CLI](../PORTABILITY.md#2-yapılandırma-config))
  Python tarafında değişiklik gerekmez; sadece GUI bayrak üretir.
- ➖ GUI ayar değişiminde motor yeniden başlatılır (~1 sn sıcak yükleme). Kabul
  edilebilir; alternatif canlı `set` protokol mesajıydı, gereksiz karmaşıklık
  bulundu.
- ➖ İki saklama yolu var (native vs config.json); ama bunlar farklı platform/arayüz
  içindir, çakışmaz.

## Değerlendirilen alternatifler
- **config.json'u her yerde kullanmak (GUI dahil):** native-olmayan deneyim, dosya
  senkron derdi. Reddedildi.
- **GUI ayarları config.json'a yazsın:** GUI'yi dosya formatına bağlar; native
  saklama (UserDefaults) daha doğru. Reddedildi.
- **Canlı ayar güncelleme protokolü (`{"cmd":"set",...}`):** restart yerine; ekstra
  protokol yüzeyi. Şimdilik restart yeterli; ileride değerlendirilebilir.
