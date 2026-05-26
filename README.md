# Turkify

> **Tamamen lokal**, ücretsiz Türkçe diakritik (şapka) restorasyon sistemi.
> ASCII karakterlerle yazılmış Türkçe metni otomatik olarak doğru Türkçe
> karakterlere dönüştürür. macOS önceliklidir; Windows ve Linux hedeflenir.

```text
Girdi:  bugun gorusme yapacagiz
Çıktı:  bugün görüşme yapacağız
```

İnternet gerektirmez, kelime uydurmaz (sıfır hallucination hedefi), boşluk /
noktalama / büyük-küçük harf yapısını birebir korur.

---

## Nasıl çalışır?

Pahalı LLM varsayılan yol değildir. Ucuz ve **deterministik** katmanlar önce
çalışır; LLM yalnızca gerçekten bağlam gerektiren belirsiz kelimeler için bir
*tiebreaker* olarak devreye girer.

| Katman | İş | Bağımlılık |
|---|---|---|
| **Ses uyumu** | Soru eki (`mi/mı/mu/mü`) bağlama göre deterministik çözülür | yok |
| **Tier 1** | Yüret deasciifier — pattern tabanlı dönüşüm | yok |
| **Tier 2** | Frekans + zeyrek morfolojik doğrulama | opsiyonel (`zeyrek`) |
| **Tier 3** | LLM rerank — sadece seçer, metin üretmez | opsiyonel (OpenAI-uyumlu sunucu: Ollama, LM Studio, …) |

Tier 3 kapalıyken (varsayılan) sistem tam offline çalışır.

---

## Hızlı başlangıç

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Tek satır düzeltme
echo "bugun gorusme yapacagiz" | python -m turkify

# Hangi katmanın çözdüğünü gör
echo "bugun gorusme" | python -m turkify --verbose

# Sistem geneli kısayol (seç → kısayola bas → düzeltilir): native macOS uygulaması
# bkz. macos/README.md
```

> **CLI birincil arayüzdür** ve her zaman kullanılabilir kalır — script'lenebilir,
> pipe'lanabilir, otomasyona uygundur ([ADR 0006](docs/adr/0006-cli-birinci-sinif-kalici.md)).
> Native masaüstü arayüzleri (Faz 6) CLI'ın *üstüne* eklenir, yerine geçmez.

Ayrıntılı kurulum, yapılandırma ve sorun giderme için **[docs/KURULUM.md](docs/KURULUM.md)**.

---

## macOS uygulaması (indir & çalıştır)

Hazır `.app`'i [**Releases**](https://github.com/ekrembulbul/turkify/releases) sayfasından
indirebilirsin (menü-bar uygulaması; Python kurmana gerek yok — motor gömülüdür).

> ⚠️ **Bu sürüm imzasız/notarize edilmemiş** (henüz Apple Developer hesabı yok). Bu
> yüzden indirince macOS Gatekeeper engeller ("hasarlı/açılamıyor"). Açmak için indirdikten
> sonra **bir kez** karantinayı kaldır:
> ```bash
> xattr -dr com.apple.quarantine /Applications/Turkify.app
> open /Applications/Turkify.app
> ```
> İlk açılışta **Erişilebilirlik** izni iste (Cmd+C/Cmd+V ile düzeltme için). İmzalı/notarize
> "indir-çift tıkla-çalış" sürümü ileride gelecek (bkz. [macos/packaging/README.md](macos/packaging/README.md)).

Kaynaktan derleme/paketleme: **[macos/packaging/README.md](macos/packaging/README.md)**.

---

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/KURULUM.md](docs/KURULUM.md) | Kurulum, kullanım, yapılandırma, sorun giderme |
| [docs/PLAN.md](docs/PLAN.md) | Mimari ve tasarım kararları |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fazlara bölünmüş uygulama planı |
| [docs/PORTABILITY.md](docs/PORTABILITY.md) | Çok-platform tasarım ve config |

---

## Lisans

[MIT](LICENSE) — © 2026 Ekrem Bülbül.
Kullanılan üçüncü taraf bileşenlerin lisansları: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
