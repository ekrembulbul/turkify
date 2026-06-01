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
> kaldırıldı. Geçici `turkify agent` (pynput/pyperclip) de kaldırıldı; sistem
> geneli kısayol artık **native frontend'in** görevidir (bkz. [ADR 0003](adr/0003-native-per-os-gui.md)).

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
- ✅ `agent.py` (pynput/pyperclip) **kaldırıldı**: sistem geneli kısayol+pano
  görevi native frontend'lere (macOS uygulaması) devredildi.
- 🔒 **CLI dokunulmaz:** `turkify` CLI birinci-sınıf ve birincil senaryodur; `serve`
  onun *üstüne* eklenir, yerine geçmez ([ADR 0006](adr/0006-cli-birinci-sinif-kalici.md)).
  CLI in-process kalır (serve'e bağımlı değil) ve her zaman test kapsamındadır.
- ✅ `correct()` + config + serve protokolü = kararlı sözleşme.
- Testler: serve protokolü (istek/yanıt, hata, reload, EOF davranışı).

### 6.1 — macOS (Swift) — **MVP, ilk hedef** 🚧 iskelet yazıldı
- Menü-bar app (SwiftUI `MenuBarExtra`).
- Global kısayol (Carbon `RegisterEventHotKey`) + pano (NSPasteboard) + tuş
  simülasyonu (CGEvent) → seç, motora gönder, yapıştır.
- Python motor köprüsü: sıcak `serve --stdio` süreci, stdio JSON.
- **İzin:** Accessibility canlı durum (✅/❌) + ilgili System Settings panelini açan
  buton. İmzalı `.app` → temiz TCC. (Input Monitoring gerekmez: kısayol Carbon ile.)
- İşlem göstergesi: LLM çalışırken ikon döner.
- Model seçimi (`/v1/models`) + temel ayarlar (`config.json`'a yazar).
- ✅ `macos/` Swift Package iskeleti yazıldı (EngineClient, Corrector, Permissions,
  HotKey, AppConfig, MenuBarExtra). ⏳ Xcode'da derleme/test + iterasyon bekliyor
  (bkz. [macos/README.md](../macos/README.md)). Model seçimi/işlem göstergesi sonraki tur.

### 6.2 — Windows (C#/.NET 8 + WPF) 🚧 iskele + sekmeler yazıldı
- Tray app (NotifyIcon), `RegisterHotKey` + `WM_HOTKEY`, `SendInput` (Ctrl+C/V) + pano.
- Aynı `serve --stdio` köprüsü; aynı ayar/model akışı. (İzin sorunu yok.)
- ✅ `windows/Turkify` WPF projesi: EngineClient (stdio JSON), AppSettings (Registry —
  ADR 0007), HotKey, Clipboard/Corrector, AppState koordinatör, ModelDiscovery.
- ✅ Ana pencere 5 sekme: Düzeltme, Motor Ayarları, Diğer Ayarlar (kısayol kaydedici +
  "Windows ile başlat"), Korumalı Kelimeler (`%APPDATA%\turkify\protected_words.txt` —
  ADR 0008), Log (sistem/motor filtresi).
- ✅ Doğrulandı: motor köprüsü uçtan uca (UTF-8 JSON turu), pencere yüklenip render
  oluyor. ⏳ Etkileşimli akış (gerçek seçimle kısayol→pano) elle test bekliyor.
- ⏳ Varsayılan kısayol Hyper+A/Hyper+Q (Ctrl+Alt+Win).

### 6.3 — Linux (Python, terminal + servis)
Native GUI yok; ince istemci motora `serve --socket` ile konuşur. Akış kararları
[ADR 0005 (2026-06 güncellemesi)](adr/0005-linux-terminal-servis.md)'te.

#### 6.3a — Çekirdek istemci + servis (MVP) 🚧 sıradaki
- ➕ `config.socket_path()` (platform-nötr): `TURKIFY_SOCKET` env > varsayılan
  `$XDG_RUNTIME_DIR/turkify/engine.sock`. İstemci ve servis aynı soketi paylaşır.
- ➕ İnce istemci (`linux/turkify_fix.py` + `linux/bin/turkify-fix`): seçimi
  **PRIMARY selection**'dan okur (tuş simülasyonu yok — `wl-paste --primary` /
  `xclip -selection primary`), sokete gönderir; **soket düşükse cold-start
  fallback** (motoru in-process yükler). Sonucu panoya yazar + `notify-send` ile
  bildirim gösterir; kullanıcı **Ctrl+V** ile yapıştırır (otomatik enjeksiyon yok —
  ydotool denendi, kararsız olduğu için kaldırıldı; bkz. ADR 0005 §2).
- ➕ `systemd --user` servisi (`turkify serve --socket …`, `RuntimeDirectory=turkify`)
  motoru **baştan** sıcak tutar. `linux/service/turkify.service` + `linux/install.sh`
  (python/repo yolunu çözüp unit'i yazar, servisi etkinleştirir, GNOME/KDE kısayol
  talimatını basar).
- ➕ Pano soyutlaması: `XDG_SESSION_TYPE` ile Wayland↔X11 tespiti; araç yoksa
  eyleme geçirilebilir hata.
- Testler: istemcinin saf parçaları (boş seçim, session tespiti, soket→cold-start
  düşüşü, paste fallback) subprocess mock'lanarak.

#### 6.3b — Rafine
- ✅ **Otomatik `reload`:** `config.json`/`protected_words.txt` değişince motor sıcak
  kalarak tazelenir. `turkify-fix --reload` → sokete `{"cmd":"reload"}`; bir
  `systemd --user` **path unit**'i (`turkify-reload.path`) config dizinini izleyip
  oneshot `turkify-reload.service`'i tetikler (`install.sh` kurar). Servis kapalıysa
  no-op. Testler dahil.
- ⏸️ **Socket activation:** ertelendi (değeri mütevazı — yalnızca kullanılmayan
  oturumda RAM tasarrufu; her açılışta ilk düzeltmeyi ~1.3 sn yavaşlatır). İlk
  bağlantıda servisi başlatmak için `serve`'e `LISTEN_FDS`/`socket.fromfd` + ayrı
  `turkify.socket` unit'i gerekir. İhtiyaç doğarsa opt-in olarak eklenir.

#### 6.3c — İptal + eşzamanlılık ⏸️ ertelendi
- `serve`'e eşzamanlılık + istek kaydı + `cancel` komutu + kesilebilir `correct()`.
- Yalnızca Tier 3 (LLM) yoğun/yavaş kullanılırsa gerekçelenir (bkz. ADR 0005 §3).

### 6.4 — Paketleme & dağıtım
- ⚠️ Motor **donmuş bağımsız ikili** (PyInstaller) olarak native app'in içine gömülür;
  kullanıcı Python/venv kurmaz ([ADR 0009](adr/0009-paketleme-frozen-motor.md)).
  Geliştirmede yerel venv yeterli.
- ✅ Hazırlık yapıldı: veri dosyaları (`tr_frequency.txt`, `rerank_prompt.txt`) pakete
  taşındı ve `importlib.resources` ile okunuyor (frozen/wheel/dev uyumlu).
- ✅ **Windows:** `windows/packaging` — PyInstaller (`turkify-engine.exe`, onedir,
  zeyrek dahil) + `dotnet publish` (self-contained) + motoru gömme + Inno Setup
  (`turkify.iss`). Uçtan uca doğrulandı: yayınlanmış app Python'suz açılıyor ve
  **gömülü** motoru başlatıyor.
- macOS: `.app` + Developer ID kod imzalama/notarization (App Sandbox kapalı).
- ✅ **Linux (kişisel/few-machines):** `linux/install.sh` eksiksiz **idempotent
  bootstrap** — venv+paket, eksik araçları `apt` (clipboard + libnotify-bin), config
  scaffold, systemd unit'leri, GNOME kısayolu (`gsettings`). Fresh clone → tek komut.
  Yapıştırma manuel (Ctrl+V; otomatik enjeksiyon/ydotool kaldırıldı — ADR 0005 §2).
  Yayın kapsamı (PyPI/.deb/AUR) **bilinçli ertelendi** (şimdilik kişisel kullanım).
- ⏸️ Geniş dağıtım (PyPI · `.deb`/`.rpm` frozen motor · AUR) ihtiyaç doğarsa.

**Faz 6 başarı kriteri:** macOS'ta kısayolla seçili metin düzeltilir; izinler
arayüzden yönetilir; motor sıcak (`serve`) ve frontend'den bağımsız test edilebilir.

---

## Faz 7 — Öğrenen Sistem (beklemede, kod devre dışı)

Kullanıcı bir düzeltmeyi değiştirince tercih lokal saklanır (`ask → aşk`); korumalı
liste ve frekans tercihleri zamanla kişiselleşir. Tüm veri lokal kalır.
(Şu an `_FAZ7_ENABLED = False`.)
