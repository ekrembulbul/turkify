# Turkify — Yol Haritası (ROADMAP)

Bu doküman fazlara bölünmüş uygulama planını içerir. Mimari ve tasarım kararları için
bkz. [PLAN.md](PLAN.md).

> **İlke:** Önce deterministik ve doğrulanabilir bir çekirdek; karmaşıklık ancak
> ölçülen ihtiyaç ortaya çıktıkça eklenir.

---

## Faz Özeti

| Faz | Başlık | Çekirdek mi? | Bağımlılık |
|---|---|---|---|
| 0 | Hazırlık ve İskelet | ✅ | — |
| 1 | Deterministik MVP | ✅ | Faz 0 |
| 2 | Morfoloji + Güven Skoru | ✅ | Faz 1 |
| 3 | LLM Rerank (opsiyonel) | — | Faz 2 |
| 4 | Performans | — | Faz 1+ |
| 5 | Doğruluk Artırımı (nöral) | — | Faz 2 |
| 6 | Native macOS Entegrasyonu | — | Faz 1 |
| 7 | Öğrenen Sistem | — | Faz 1+ |

İlk hedef **Faz 0 → 2**: tamamen lokal, deterministik, offline çalışan, kullanılabilir
bir sistem. Faz 3+ isteğe bağlı iyileştirmelerdir.

---

## Faz 0 — Hazırlık ve İskelet

**Amaç:** Geliştirme ortamını ve test edilebilir proje iskeletini kurmak.

**Çıktılar:**
- `venv`, `requirements.txt`, [PLAN.md §9](PLAN.md)'deki dizin yapısı.
- `correct(text, *, use_llm=False) -> str` imzasıyla boş ama test edilebilir motor.
- CI/test komutu (`pytest`) çalışır durumda.

**Başarı kriteri:** `pytest` çalışıyor; iskelet importları sorunsuz.

---

## Faz 1 — Deterministik MVP ⭐

**Amaç:** Kullanılabilir, tamamen offline, LLM'siz uçtan uca düzeltme.

**Çıktılar:**
- **Tokenizer:** kelime/noktalama/boşluk ayrıştırma.
- **Tier 1 deasciifier:** pattern/n-gram tabanlı deterministik dönüşüm.
- **Frekans sözlüğü:** aday sıralaması için temel veri.
- **Koruma katmanı:** yabancı/teknik kelimeler, zaten doğru kelimeler, URL/kod/sayı.
- **Reconstruction:** boşluk, noktalama ve Türkçe-locale case korunur.
- **Hammerspoon entegrasyonu:** Hyper+T, clipboard kopyala/yapıştır + clipboard restore.

**Başarı kriteri (Definition of Done):**
- `bugun gorusme yapacagiz` → `bugün görüşme yapacağız`.
- Noktalama ve büyük/küçük harf korunur.
- Korumalı kelimeler (`mail`, `framework`) dönüştürülmez.
- LLM'siz gecikme < 50 ms/cümle.
- Çekirdek birim testleri yeşil.

---

## Faz 2 — Morfolojik Doğrulama + Güven Skoru ⭐

**Amaç:** Belirsiz kelimelerde doğruluğu artırmak; ne zaman LLM'e yükseleceğini belirlemek.

**Çıktılar:**
- **Tier 2 aday üretimi** (sınırlı, frekansa göre sıralı).
- **Zemberek sarmalayıcı:** geçersiz adayları eler.
- **Güven skoru / escalation politikası:** Tier 1 düşük güvende → Tier 2; çoklu geçerli
  yaygın aday → Tier 3'e işaretle.

**Başarı kriteri:** Morfolojik olarak geçersiz çıktılar elenir; benchmark doğruluğu
Faz 1'e göre ölçülebilir biçimde artar (altın veri setinde).

---

## Faz 3 — LLM Rerank (Opsiyonel, Bağlamsal)

**Amaç:** Yalnızca bağlam gerektiren belirsizlikleri çözmek (`ask` → `ask`/`aşk`).

**Çıktılar:**
- **Tier 3 reranker:** OpenAI-uyumlu yerel sunucu (Ollama, LM Studio, …) + model; sadece seçim yapar, metin üretmez.
- `use_llm=True` ile etkinleşir; kapalıyken sistem tam offline kalır.
- Belirsiz kelimeler için cache.

**Başarı kriteri:** Bağlamsal test vakalarında doğru aday seçilir; hallucination yok
(çıktı her zaman verilen adaylardan biri); LLM dahil gecikme < 2 sn.

---

## Faz 4 — Performans

**Amaç:** Günlük kullanımda akıcılık.

**Fikirler:**
- Kelime/cümle cache.
- Persistent model session (her çağrıda model yeniden yüklenmesin).
- Batch reranking.
- Streaming çıktı.

**Başarı kriteri:** Profiling ile ölçülen darboğazlar giderilir (önce ölç, sonra optimize et).

---

## Faz 5 — Doğruluk Artırımı (Nöral)

**Amaç:** Deterministik tavanın üzerine çıkmak.

**Seçenekler:**
- **Beam search:** cümle düzeyinde optimizasyon (kelime kararlarını birbirinden bağımsız almak yerine).
- **Özel reranker / restorasyon modeli:** karakter düzeyli seq2seq diakritik restorasyon
  için **ByT5 / mT5**; veya bağlamsal doğrulama için **BERTurk** (`dbmdz/bert-base-turkish-cased`).

> ⚠️ Bu faz ek model bağımlılığı ve eğitim/değerlendirme verisi gerektirir; yalnızca
> Faz 2 doğruluğu yetersiz kalırsa gerekçelendirilir.

---

## Faz 6 — GUI / Native Entegrasyon

**Amaç:** Çok-platform kısayol ajanının üzerine akıcı bir kullanıcı arayüzü.

**Kapsam (detay: [PORTABILITY.md §7](PORTABILITY.md)):** menü-bar uygulaması,
izin butonları (Girdi İzleme + Erişilebilirlik, durum göstergeli), model
combobox'u (kurulu modelleri otomatik listeler), işlem göstergesi (LLM
beklemesinde dönen simge), config ayar arayüzü. Framework önerisi: Tkinter.

> Not: Hammerspoon/Raycast kaldırıldı; kısayol artık çok-platform `turkify
> agent` ile yapılıyor (bkz. PORTABILITY.md).

---

## Faz 7 — Öğrenen Sistem

**Amaç:** Kullanıcı düzeltmelerinden öğrenmek (gizlilik korunarak, lokal).

**Çıktılar:**
- Kullanıcı bir düzeltmeyi değiştirdiğinde tercih lokal olarak saklanır (`ask → aşk`).
- Korumalı kelime listesi ve frekans tercihleri zamanla kişiselleşir.

**Başarı kriteri:** Tekrarlanan kullanıcı tercihleri sonraki düzeltmelerde uygulanır;
tüm veri lokal kalır.
