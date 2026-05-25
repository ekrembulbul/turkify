# Turkify — Türkçe Karakter Düzeltme Sistemi (Mimari Plan)

> macOS üzerinde çalışan, **tamamen lokal**, ücretsiz bir Türkçe diakritik (şapka) restorasyon sistemi.
> ASCII karakterlerle yazılmış Türkçe metinleri otomatik olarak doğru Türkçe karakterlere dönüştürür.

```text
Girdi:  bugun gorusme yapacagiz
Çıktı:  bugün görüşme yapacağız
```

Bu doküman **mimariyi ve tasarım kararlarını** tanımlar. Fazlara bölünmüş uygulama
takvimi için bkz. [ROADMAP.md](ROADMAP.md).

> ⚠️ **Güncellik notu:** Bu belge özgün tasarım gerekçesini tutar; **kademeli (Tier
> 1/2/3) çekirdek mimari hâlâ geçerlidir.** Ancak bazı teslimat detayları sonradan
> değişti — güncel kararlar için [ADR](adr/README.md):
> - Kısayol/GUI: Hammerspoon **kaldırıldı**; her OS için **native frontend** + `turkify
>   serve` ([ADR 0003](adr/0003-native-per-os-gui.md), [0004](adr/0004-motor-sinir-protokolu.md), [0005](adr/0005-linux-terminal-servis.md)).
> - Tier 3: **OpenAI-uyumlu** API ([ADR 0002](adr/0002-openai-uyumlu-llm-api.md)).
>
> Aşağıdaki Hammerspoon/dizin/araç ayrıntıları **tarihseldir**; güncel yapı için
> [PORTABILITY.md](PORTABILITY.md) ve [ROADMAP.md](ROADMAP.md)'e bakın.

---

## 1. Amaç ve Hedefler

### Fonksiyonel Hedefler

- Tamamen lokal çalışır, internet gerektirmez, ücretsizdir.
- Seçili metni dönüştürür.
- Boşluk, noktalama ve büyük/küçük harf yapısını **birebir korur**.
- Metnin anlamını değiştirmez, kelime uydurmaz (**sıfır hallucination** hedefi).

### Teknik Hedefler

- macOS uyumlu, düşük gecikmeli (LLM'siz yolda hedef **< 50 ms/cümle**).
- Genişletilebilir, kademeli (escalation) mimari.
- Deterministik çekirdek: aynı girdi her zaman aynı çıktıyı verir.

---

## 2. Tasarım Felsefesi — Neden Kademeli Mimari?

Türkçe diakritik restorasyonu (literatürde *deasciification* / *diacritic restoration*)
**iyi çalışılmış bir problemdir** ve büyük ölçüde deterministik yöntemlerle çözülür.

> **Temel karar:** Pahalı LLM'i varsayılan yol yapma. Ucuz ve deterministik yolu
> önce çalıştır; LLM'i yalnızca gerçekten bağlam gerektiren belirsiz kelimeler için
> bir *tiebreaker* olarak kullan.

Bu yaklaşımın orijinal "her kelime → brute-force → Zemberek → 7B LLM" akışına göre avantajları:

| Boyut | Her kelimede LLM | Kademeli mimari |
|---|---|---|
| Gecikme | Her kelimede 7B model çağrısı (cümlede saniyeler) | Çoğu kelime LLM'siz (< 50 ms) |
| Hallucination | LLM her kelimeye dokunur → risk yüksek | LLM yalnızca belirsiz kelimelerde, seçimle sınırlı |
| Belirleyicilik | Düşük (örnekleme) | Çekirdek deterministik |
| Bağımlılık | Ollama her zaman gerekli | Ollama opsiyonel |

> 🟡 **Güven:** Deasciification'ın deterministik yöntemlerle yüksek doğrulukla
> çözülebildiği genel kabul görmüş bir pratiktir; kesin doğruluk oranları kullanılan
> korpusa bağlıdır ve [benchmark](#11-test-ve-benchmark-stratejisi) ile ölçülmelidir.

---

## 3. Genel Mimari

```text
Kullanıcı metni seçer
        ↓
Hammerspoon hotkey (Hyper + T) tetiklenir
        ↓
Seçili metin clipboard'a kopyalanır
        ↓
Python düzeltme motoru çalışır
        ↓
┌─────────────────────────────────────────────┐
│  Düzeltme Pipeline (kelime bazında)          │
│                                              │
│  Tokenization                                │
│        ↓                                     │
│  Korumalı kelime? (foreign/kod/zaten doğru)  │
│        ├─ Evet → dokunma                     │
│        └─ Hayır ↓                            │
│  Tier 1: Deterministik deasciifier           │
│        ↓ (emin değilse)                      │
│  Tier 2: Aday üretimi + frekans + Zemberek   │
│        ↓ (hâlâ belirsizse ve LLM açıksa)     │
│  Tier 3: LLM rerank (bağlamsal tiebreaker)   │
└─────────────────────────────────────────────┘
        ↓
Sentence reconstruction (boşluk/noktalama/case korunur)
        ↓
Clipboard değiştirilir → metin yapıştırılır
```

---

## 4. Teknoloji Yığını

| Katman | Teknoloji | Faz | Not |
|---|---|---|---|
| Kısayol/arayüz | Native frontend (Swift/C#) + `serve`; (eski: Hammerspoon) | 1 / 6 | bkz. ADR 0003/0004 |
| Deasciifier | Pattern/n-gram tabanlı (Yüret tarzı) | 1 | Deterministik çekirdek |
| Frekans sözlüğü | Türkçe korpus frekans listesi | 1 | Aday sıralama |
| Morfoloji | Zemberek | 2 | Aday doğrulama/eleme |
| LLM runtime | OpenAI-uyumlu sunucu (Ollama, LM Studio, …) | 3 | Opsiyonel, belirsiz kelimeler |
| Lokal model | Qwen2.5 (örn. 7B) | 3 | Yalnızca rerank |
| Ana dil | Python (venv) | — | Orkestrasyon |

> 💡 **Öneri / ❓ doğrulanmalı:** Hazır paketlerin (`zemberek-python`, Yüret tarzı
> deasciifier paketleri vb.) güncel adı, sürümü ve bakım durumu PyPI'da
> **kullanılmadan önce doğrulanmalıdır.** Bakımsız bir bağımlılık yerine, gerekirse
> deasciifier algoritması doğrudan implemente edilebilir (algoritma kompakttır).

---

## 5. Bileşenler

### 5.1 Hammerspoon Katmanı

**Görevi:** Hotkey'i yakalamak, seçili metni kopyalamak, Python motorunu çalıştırmak,
sonucu geri yapıştırmak.

- Hotkey: **Hyper + T** (`Ctrl + Alt + Cmd + T`)
- Clipboard'ı işlem sonunda **eski haline döndür** (kullanıcının panosunu kirletme).
- Python süreci için **timeout** uygula; takılırsa sessizce başarısız olmak yerine
  kullanıcıya geri bildirim ver (orijinal metni bozmadan).

### 5.2 Python Düzeltme Motoru (Orkestrasyon)

Ana kontrat (genişletilebilir, test edilebilir):

```python
def correct(text: str, *, use_llm: bool = False) -> str:
    """ASCII Türkçe metni doğru diakritiklerle düzeltir.

    Boşluk, noktalama ve büyük/küçük harf yapısı korunur.
    use_llm=False iken tamamen deterministik ve offline çalışır.
    """
```

Sorumluluklar: tokenization → koruma kontrolü → tier'lar → reconstruction.

### 5.3 Tier 1 — Deterministik Deasciifier

**Yöntem:** Karakter bağlamına dayalı pattern/karar-listesi yaklaşımı
(Deniz Yüret'in Türkçe deasciifier algoritması bu sınıfın bilinen örneğidir).

- Bir kelimedeki dönüştürülebilir her karakter için, çevreleyen n-gram bağlamına
  göre diakritik konup konmayacağına karar verir.
- Deterministik ve çok hızlı; aday patlaması (`2^n`) yaşanmaz.
- Çoğu kelime burada çözülür ve sonraki tier'lara hiç geçmez.

### 5.4 Tier 2 — Aday Üretimi + Frekans + Morfoloji

Tier 1 düşük güven verirse devreye girer.

**Aday üretimi.** Dönüştürülebilir karakterler için varyasyon üretilir, ancak:

- Aday sayısı **sınırlandırılır** (örn. en fazla N dönüştürülebilir karakter),
  çünkü `k` dönüştürülebilir karakter `2^k` aday üretir.
- Adaylar **frekans sözlüğüne** göre sıralanır → daha yaygın kelime tercih edilir.

**Dönüşüm tablosu:**

| ASCII | Türkçe |
|---|---|
| `c` | `ç` |
| `g` | `ğ` |
| `i` | `ı` / `i` |
| `o` | `ö` |
| `s` | `ş` |
| `u` | `ü` |

> ⚠️ **`i`/`ı` ve `I`/`İ` özel durumu:** Türkçe'de noktalı/noktasız i ayrımı çift
> yönlüdür. ASCII `i`, bağlama göre `i` **veya** `ı` olabilir; büyük harfte `I` →
> `I` veya `İ`. Bu yüzden `i` tek yönlü bir eşleme değildir ve case dönüşümleri
> Türkçe kurallarına (`tr_TR` locale) göre yapılmalıdır.

**Morfolojik doğrulama (Zemberek).** Morfolojik olarak geçersiz adaylar elenir:

| Aday | Geçerli |
|---|---|
| `gorusme` | ❌ |
| `gorüşme` | ❌ |
| `görüşme` | ✅ |

Birden fazla geçerli aday kalırsa frekans sıralaması belirler; frekanslar yakınsa
**Tier 3**'e güven skoruyla birlikte yükseltilir.

### 5.5 Tier 3 — LLM Rerank (Opsiyonel, Bağlamsal Belirsizlik)

**Yalnızca** birden fazla geçerli ve yaygın aday bağlam gerektirdiğinde çağrılır.

**Kritik kısıt:** LLM **metin üretmez**, yalnızca verilen adaylardan birini seçer.
Bu sayede anlam bozulmaz, kelime uydurulmaz, gramer yeniden yazılmaz.

Örnek prompt (deterministik seçim davranışı):

```text
Sentence: bugun gorusme yapacagiz
Original word: gorusme
Candidates:
- görusme
- gorüşme
- görüşme
Choose the best candidate for the sentence.
Return only one word, exactly as written in the candidates.
```

> İlk fazda bu katman **kapalı** (`use_llm=False`) gelir; doğru çalışan deterministik
> çekirdek üzerine sonradan eklenir.

### 5.6 Sentence Reconstruction

Orijinal metnin yapısını birebir korur:

```text
Girdi:  Merhaba, bugun gorusme yapacagiz.
Çıktı:  Merhaba, bugün görüşme yapacağız.
```

- Boşluklar, sekme ve satır sonları korunur.
- Noktalama işaretleri kelimeden ayrıştırılır, sonra yerine konur.
- Büyük/küçük harf deseni (ör. `Istanbul` → `İstanbul`) korunur.

---

## 6. Koruma Katmanı (Yanlış Dönüşümü Önleme)

Düzeltme uygulanmadan önce şu kelimeler **dokunulmadan geçirilir**:

- **Yabancı/teknik kelimeler:** `mail`, `framework`, `backend`, ... → korumalı liste.
- **Zaten doğru kelimeler:** İçinde Türkçe karakter olan veya geçerli Türkçe kelime
  olanlar tekrar dönüştürülmez.
- **Kod/URL/e-posta/sayı içeren tokenlar:** Regex ile tespit edilip atlanır.

> Korumalı liste konfigürasyondan okunur ve [Faz 7](ROADMAP.md)'de kullanıcı
> düzeltmeleriyle öğrenilerek genişletilebilir.

---

## 7. Bilinen Problemler ve Azaltma Stratejileri

| Problem | Örnek | Azaltma |
|---|---|---|
| Bağlamsal belirsizlik | `ask` → `ask` / `aşk` | Frekans + (gerekirse) Tier 3 LLM |
| Özel isimler | `Istanbul` → `İstanbul` | Türkçe locale + özel isim sözlüğü |
| Yabancı kelimeler | `mail`, `framework` | Korumalı liste (Bölüm 6) |
| Aday patlaması | uzun kelimelerde `2^k` | Aday sınırı + deterministik Tier 1 |
| LLM gecikmesi | 7B model yavaş | LLM yalnızca belirsiz kelimelerde + cache |

---

## 8. Ortam Kurulumu

```bash
# Python sanal ortamı
python3 -m venv ~/venvs/turkify-env
source ~/venvs/turkify-env/bin/activate

# macOS bağımlılıkları
brew install --cask hammerspoon
brew install ollama         # yalnızca Tier 3 için (OpenAI-uyumlu sunucu örneği)

# Tier 3 modeli (OpenAI-uyumlu herhangi bir sunucu kullanılabilir; ör. Ollama)
ollama pull qwen2.5:7b
ollama serve
```

> Python paket adları (`zemberek-python`, deasciifier paketi vb.) `requirements.txt`'e
> eklenmeden önce PyPI'da doğrulanmalıdır (Bölüm 4 notu).

---

## 9. Proje Yapısı

```text
~/projects/turkify/
├── PLAN.md
├── ROADMAP.md
├── requirements.txt
├── config/
│   └── protected_words.example.txt  # korumalı kelime ÖRNEĞİ (kopyalanır; otomatik yüklenmez)
├── src/turkify/
│   ├── __init__.py
│   ├── engine.py                  # correct() orkestrasyonu
│   ├── tokenizer.py
│   ├── deasciifier.py             # Tier 1
│   ├── candidates.py              # Tier 2 aday üretimi
│   ├── frequency.py               # frekans sözlüğü
│   ├── morphology.py              # Tier 2 Zemberek sarmalayıcı
│   ├── reranker.py                # Tier 3 LLM (opsiyonel)
│   └── reconstruct.py
├── data/
│   └── tr_frequency.txt           # Türkçe frekans listesi
├── prompts/
│   └── rerank_prompt.txt
├── hammerspoon/
│   └── turkify.lua
├── cache/
├── tests/
└── benchmarks/
```

---

## 10. Veri İhtiyaçları

- **Frekans sözlüğü:** Türkçe korpustan türetilmiş kelime-frekans listesi
  (ör. Wikipedia/OSCAR türevli açık listeler veya Zemberek sözlüğü).
  > ❓ **Doğrulanmalı:** Seçilecek listenin lisansı (Bölüm: bağımlılık/lisans uyumu)
  > ve kapsamı projeyle uyumlu olmalıdır.
- **Korumalı kelime listesi:** Yabancı/teknik terimler; elle başlatılır, zamanla büyür.
- **Test/altın veri seti:** Etiketli (ASCII → doğru Türkçe) cümle çiftleri (Bölüm 11).

---

## 11. Test ve Benchmark Stratejisi

**Birim testleri:** tokenization, deasciifier (Tier 1), aday üretimi, morfoloji,
reconstruction, koruma katmanı. Test adları neyi doğruladığını anlatmalı
(ör. `test_reconstruct_preserves_punctuation_and_case`).

**Entegrasyon testleri:** tam cümle düzeltme, clipboard pipeline, Hammerspoon akışı.

**Benchmark metrikleri:**

| Metrik | Hedef |
|---|---|
| Karakter/kelime doğruluğu | ≥ %90 |
| False positive (yanlış dönüşüm) oranı | mümkün olduğunca düşük |
| Hallucination oranı | ~0 (deterministik yolda 0) |
| Gecikme (LLM'siz) | < 50 ms / cümle |
| Gecikme (LLM dahil) | < 2 sn / cümle |

> Doğruluk oranları **altın veri seti üzerinde ölçülerek** raporlanır; tahmini
> rakamlar plan kapsamında bağlayıcı değildir.

---

## 12. Başarı Kriterleri

Sistem başarılı kabul edilir eğer:

- Günlük kullanımda pratikse,
- Hallucination oranı ~0 ise,
- Cümle anlamı korunuyorsa,
- Doğruluk ≥ %90 ise,
- LLM'siz ortalama gecikme < 50 ms, LLM dahil < 2 sn ise.

---

## 13. Uzun Vadeli Vizyon

Tamamen lokal çalışan, gizliliği koruyan, macOS ile derin entegre (Raycast benzeri)
bir Türkçe yazım asistanı. Detaylı fazlar için bkz. [ROADMAP.md](ROADMAP.md).
