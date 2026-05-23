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

# Global kısayol ajanı (Hyper+A): metni seç → kısayola bas → düzeltilir
python -m turkify agent
```

Ayrıntılı kurulum, yapılandırma ve sorun giderme için **[docs/KURULUM.md](docs/KURULUM.md)**.

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
