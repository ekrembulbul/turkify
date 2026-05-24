# Turkify — Yol Haritası (ROADMAP)

Bu doküman fazlara bölünmüş uygulama planını içerir. Mimari ve tasarım kararları için
bkz. [PLAN.md](PLAN.md); kalıcı karar kayıtları için [ADR](adr/README.md).

> **İlke:** Önce deterministik ve doğrulanabilir bir çekirdek; karmaşıklık ancak
> ölçülen ihtiyaç ortaya çıktıkça eklenir.

---

## Faz Özeti

| Faz | Başlık | Çekirdek mi? | Durum | Bağımlılık |
|---|---|---|---|---|
| 0 | Hazırlık ve İskelet | ✅ | bitti | — |
| 1 | Deterministik MVP | ✅ | bitti | Faz 0 |
| 2 | Morfoloji + Güven Skoru | ✅ | bitti | Faz 1 |
| 3 | LLM Rerank (OpenAI-uyumlu) | — | bitti | Faz 2 |
| 4 | Performans | — | açık | Faz 1+ |
| 5 | Doğruluk Artırımı (nöral) | — | açık | Faz 2 |
| 6 | Native Arayüzler + Motor Servisi | — | **sırada** | Faz 1+ |
| 7 | Öğrenen Sistem | — | beklemede | Faz 1+ |

**Faz 0 → 3 tamamlandı:** tamamen lokal, deterministik, offline çalışan, opsiyonel
LLM destekli kullanılabilir bir sistem. Sıradaki büyük adım **Faz 6** — native
masaüstü arayüzler ve onları besleyen motor servisi.

---

## Faz 0 — Hazırlık ve İskelet ✅

`venv`, dizin yapısı, `correct()` imzalı test edilebilir motor, `pytest`.

## Faz 1 — Deterministik MVP ✅

Tokenizer, Tier 1 deasciifier, frekans sözlüğü, koruma katmanı, reconstruction
(Türkçe-locale case korunur). DoD: `bugun gorusme yapacagiz` → `bugün görüşme
yapacağız`; noktalama/case korunur; korumalı kelimeler dönüşmez; < 50 ms/cümle.

> Not: İlk kısayol entegrasyonu Hammerspoon (macOS) ile yapılmıştı; sonradan
> kaldırıldı. Kısayol artık çok-platform `turkify agent` ile (Faz 6'da native
> arayüzlere devrediliyor — bkz. [ADR 0003](adr/0003-native-per-os-gui.md)).

## Faz 2 — Morfolojik Doğrulama + Güven Skoru ✅

Tier 2 aday üretimi, zeyrek sarmalayıcı (geçersiz adayları eler), frekans-güdümlü
escalation. Belirsiz kelimeler Tier 3'e işaretlenir.

## Faz 3 — LLM Rerank (OpenAI-uyumlu, opsiyonel) ✅

Yalnızca bağlam gerektiren belirsizlikleri çözer (`ask` → `ask`/`aşk`). LLM **sadece
seçer**, metin üretmez (sıfır hallucination). `use_llm=True` ile etkin; kapalıyken
sistem tam offline.

> **OpenAI-uyumlu API'ye geçildi** (bkz. [ADR 0002](adr/0002-openai-uyumlu-llm-api.md)):
> `/v1/chat/completions` ile Ollama, LM Studio, llama.cpp, Jan, vLLM, MLX desteklenir.
> `base_url`/`api_key`/`llm_options`/`assistant_prefill` config alanları.

---

## Faz 4 — Performans (açık)

Kelime/cümle cache, sıcak model oturumu (Faz 6 `serve` ile büyük ölçüde gelir),
batch reranking, streaming. **Önce ölç, sonra optimize et.**

## Faz 5 — Doğruluk Artırımı (Nöral) (açık)

Beam search (cümle düzeyi), özel reranker/restorasyon modeli (ByT5/mT5 veya BERTurk).
⚠️ Ek model + eğitim/değerlendirme verisi gerektirir; yalnızca Faz 2 doğruluğu
yetersiz kalırsa gerekçelendirilir.

---

## Faz 6 — Native Arayüzler + Motor Servisi ⭐ (sıradaki)

**Amaç:** Her OS'ta native bir masaüstü deneyimi; Python motoru paylaşımlı bir
**düzeltme servisi** olarak sunulur. Mimari kararlar:
[ADR 0003](adr/0003-native-per-os-gui.md) (native-per-OS),
[ADR 0004](adr/0004-motor-sinir-protokolu.md) (serve protokolü),
[ADR 0005](adr/0005-linux-terminal-servis.md) (Linux).

**Hedef yapı:**

| OS | Frontend | UI | Motor erişimi |
|---|---|---|---|
| macOS | Swift | SwiftUI menü-bar | `serve --stdio` (GUI sıcak süreç sahibi) |
| Windows | C#/.NET 8 | WPF tray | `serve --stdio` (GUI sıcak süreç sahibi) |
| Linux | Python | terminal + `systemd --user` | `serve --socket` (servis sıcak) |

Rol dağılımı: native taraf **menü-bar/tray + global kısayol + pano + izinler**;
Python yalnızca **metin düzeltme**. Aradan geçen tek şey "metin → düzeltilmiş metin".

### 6.0 — Refactor: motor servisi (`turkify serve`) ✅
**Tüm frontend'lerin ortak sözleşmesi — tamamlandı.**
- ➕ `turkify serve` komutu: satır-bazlı JSON protokolü (bkz. [ADR 0004](adr/0004-motor-sinir-protokolu.md)).
  İki taşıma: `--stdio` (GUI sahipli) ve `--socket PATH` (Linux servis). Mesaj formatı aynı.
  - `{"text": …}` → `{"corrected": …}` / `{"error": …}`; `{"cmd":"ping"|"reload"}`.
  - `engine.correct` aynen kullanılır; `serve` ince bir döngü/sarmalayıcıdır.
  - ✅ `src/turkify/serve.py` (`EngineService.handle` + `serve_stdio` + `serve_socket`),
    `turkify serve [--stdio|--socket YOL]`, testler. İki taşıma da uçtan uca doğrulandı.
- 🔄 `agent.py` (pynput/pyperclip) **geçici statüye** alınır: kısayol+pano native'e
  devredildikçe emekliye ayrılır. Henüz native frontend'i olmayan OS'lar için durur.
- 🔒 **CLI dokunulmaz:** `turkify` CLI birinci-sınıf ve birincil senaryodur; `serve`
  onun *üstüne* eklenir, yerine geçmez ([ADR 0006](adr/0006-cli-birinci-sinif-kalici.md)).
  CLI in-process kalır (serve'e bağımlı değil) ve her zaman test kapsamındadır.
- ✅ `correct()` + config + serve protokolü = kararlı sözleşme.
- Testler: serve protokolü (istek/yanıt, hata, reload, EOF davranışı).

### 6.1 — macOS (Swift) — **MVP, ilk hedef**
- Menü-bar app (SwiftUI `MenuBarExtra`).
- Global kısayol (CGEvent) + pano (NSPasteboard) → seç, motora gönder, yapıştır.
- Python motor köprüsü: sıcak `serve --stdio` süreci, stdio JSON.
- **İzinler:** Accessibility + Input Monitoring canlı durum (✅/❌) + ilgili System
  Settings panelini açan butonlar. İmzalı `.app` → temiz TCC.
- İşlem göstergesi: LLM çalışırken ikon döner.
- Model seçimi (`/v1/models`) + temel ayarlar (`config.json`'a yazar).

### 6.2 — Windows (C#/.NET + WPF)
- Tray app (NotifyIcon), `RegisterHotKey`, `Clipboard`.
- Aynı `serve --stdio` köprüsü; aynı ayar/model akışı. (İzin sorunu yok.)

### 6.3 — Linux (Python, terminal + servis)
- Native GUI yok; `systemd --user` servisi motoru sıcak tutar (`serve --socket`).
- Tetikleme: masaüstü ortamının kendi kısayolu (Wayland-uyumlu).
- Pano: X11 `xclip`/`xsel`, Wayland `wl-clipboard`. ⚠️ Wayland yapıştırma best-effort.

### 6.4 — Paketleme & dağıtım
- ⚠️ Her native app'in içine **Python çalışma zamanı + bağımlılıklar** gömülür
  (yaklaşım: `python-build-standalone`). Geliştirmede yerel venv yeterli.
- macOS: `.app` + kod imzalama/notarization. Windows: kurulum paketi. Linux:
  `.deb`/`.rpm`/AUR veya Flatpak.

**Faz 6 başarı kriteri:** macOS'ta kısayolla seçili metin düzeltilir; izinler
arayüzden yönetilir; motor sıcak (`serve`) ve frontend'den bağımsız test edilebilir.

---

## Faz 7 — Öğrenen Sistem (beklemede, kod devre dışı)

Kullanıcı bir düzeltmeyi değiştirince tercih lokal saklanır (`ask → aşk`); korumalı
liste ve frekans tercihleri zamanla kişiselleşir. Tüm veri lokal kalır.
(Şu an `_FAZ7_ENABLED = False`.)
