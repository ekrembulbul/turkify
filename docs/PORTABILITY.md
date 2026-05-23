# Turkify — Taşınabilirlik ve Yapılandırma

> Turkify **macOS öncelikli** olmak üzere çok-platformlu (Windows, Linux) olacak
> şekilde tasarlanmıştır. Tüm çalışma zamanı ayarları bir **config dosyasında**
> toplanır. Kısayol/pano işi, OS'a özel araçlar (Hammerspoon/Raycast) yerine
> **kendi çok-platform ajanımızla** (`turkify agent`) yapılır.
>
> Durum: **Faz A uygulandı** (macOS doğrulandı). Windows/Linux için kod yazıldı
> ama yalnızca macOS test edildi; diğerleri peyderpey doğrulanacaktır.

---

## 1. Mimari

| Katman | Sorumluluk | Bağımlılık | OS |
|---|---|---|---|
| **Çekirdek motor** | Tier 1/2/3 düzeltme | yok (zeyrek/LLM sunucusu opsiyonel) | her platform |
| **CLI** (`turkify`) | stdin/dosya → düzeltilmiş metin (in-process) | — | her platform |
| **Ajan** (`turkify agent`) | Global kısayol → kopyala→düzelt→yapıştır | `pynput`, `pyperclip` | macOS ✅ / Win / Linux* |
| **Config** (`config.py`) | Tüm ayarları tek JSON'da topla | — | her platform |

\* Linux/Wayland'da global kısayol/enjeksiyon OS kısıtları nedeniyle sınırlıdır
(bkz. [§5](#5-bilinen-kısıtlar)).

> **Not:** Eski **daemon** (Unix soketi) ve **Hammerspoon/Raycast/launchd**
> (yalnızca macOS) **kaldırıldı.** Ajan, motoru bellekte sıcak tuttuğu için ayrı
> daemon'a gerek kalmaz ve tek bir çok-platform çözüm sağlar.

---

## 2. Yapılandırma (config)

### Öncelik
```
CLI bayrağı  >  TURKIFY_* ortam değişkeni  >  config dosyası  >  yerleşik varsayılan
```
Bu sıra `config.resolve()` içinde uygulanır: `load()` (config+varsayılan) → env
katmanı → CLI override. `hotkey` dışındaki her ayar hem env hem CLI bayrağı
olarak verilebilir.

### Ortam değişkenleri
Her config alanının bir `TURKIFY_*` karşılığı vardır: `TURKIFY_MODEL`,
`TURKIFY_USE_LLM`, `TURKIFY_USE_MORPHOLOGY`, `TURKIFY_TIMEOUT`, `TURKIFY_BASE_URL`,
`TURKIFY_API_KEY`, `TURKIFY_LLM_OPTIONS` (JSON metni). Geçersiz bir env değeri
(ör. sayı olmayan `TURKIFY_TIMEOUT`) yok sayılır ve uyarı yazılır.

### CLI bayrakları
`--model`, `--llm`/`--no-llm`, `--morphology`/`--no-morphology`, `--timeout`,
`--base-url`, `--api-key`, `--llm-options` (JSON), `--verbose`/`-v`. Hem düzeltme
komutu hem `agent` kabul eder.

### Format & konum
- **Format: JSON** (stdlib `json` ile bağımlılıksız okunur). JSON **yorum
  desteklemez**; `//` içeren bir config geçersiz sayılır, varsayılanlara dönülür
  ve stderr'e uyarı yazılır.
- **Konum** (`TURKIFY_CONFIG` ile override):
  - macOS / Linux: `~/.config/turkify/config.json` (`$XDG_CONFIG_HOME` varsa o)
  - Windows: `%APPDATA%\turkify\config.json`
- Yol **elle hesaplanır** — yeni bağımlılık yok.

### Şema
```jsonc
{
  "model": null,                    // Tier 3 modeli — ZORUNLU; null ise Tier 3 çalışmaz
  "use_llm": false,
  "use_morphology": true,
  "timeout": 60,
  "base_url": "http://localhost:11434/v1",  // OpenAI-uyumlu sunucu (LM Studio: .../1234/v1)
  "api_key": null,                  // sunucu isterse (yerelde genelde gerekmez)
  "llm_options": {},                // /chat/completions isteğine eklenecek ekstra alanlar
  "hotkey": { "mods": ["ctrl", "alt", "cmd"], "key": "a" }   // Hyper+A
}
```
Örnek: [`config/config.example.json`](../config/config.example.json).

---

## 3. Model

- Model **config'ten gelir ve zorunludur** (`model`). Belirtilmezse (`null`)
  Tier 3 (LLM) **çalışmaz** — otomatik model tespiti yapılmaz.
- Önceliğe göre `--model` / `TURKIFY_MODEL` config'i geçersiz kılar.
- İleride GUI'de kurulu modeller bir combobox'a getirilip kullanıcıya seçtirilecek.

### LLM sunucusu (Tier 3)
- Turkify, **OpenAI-uyumlu** `/v1/chat/completions` ucunu konuşur; bu protokolü
  Ollama, LM Studio, llama.cpp (server), Jan, GPT4All, vLLM, MLX gibi araçların
  hepsi sunar. Böylece tek istemci geniş bir ekosistemi kapsar.
- Sunucu adresi `base_url` ile seçilir (varsayılan Ollama'nın yerel ucu
  `http://localhost:11434/v1`); `TURKIFY_BASE_URL` env'i ile de geçilebilir.
- Sunucu API anahtarı isterse `api_key` (veya `TURKIFY_API_KEY`) kullanılır;
  yerel sunucular genelde istemez.
- `llm_options` (dict) `/chat/completions` gövdesine olduğu gibi eklenir; böylece
  sunucu/model-özel ayarlar (ör. reasoning'i kapatma: `chat_template_kwargs`,
  `reasoning_effort`) Turkify'a hardcode edilmeden kullanıcı tarafından yönetilir.
  `temperature`/`max_tokens` de buradan ezilebilir; `model`/`messages`/`stream`
  korunur (doğruluğa etkili oldukları için).

---

## 4. Kısayol ajanı (`turkify agent`)

- Motoru bir kez yükler (sıcak tutar), config'teki kısayolu **global** dinler.
- Kısayola basınca: `Cmd/Ctrl+C` (kopyala) → düzelt → panoya yaz → `Cmd/Ctrl+V`
  (yapıştır) → eski panoyu geri yükle. Modifier macOS'ta `Cmd`, diğerlerinde `Ctrl`.
- Kısayol config'ten gelir; değiştirmek için config'i düzenle ve ajanı yeniden başlat.
- Çekirdek akış (`agent.correct_clipboard_selection`) OS-bağımsız ve test edilebilir;
  pynput/pyperclip yalnızca `agent.run()` içinde kullanılır.

---

## 5. Bilinen kısıtlar

| Platform | Durum |
|---|---|
| Windows | ✅ Beklenen şekilde çalışır |
| macOS | ✅ Çalışır — **Erişilebilirlik (Accessibility) izni** gerekir |
| Linux / X11 | ✅ Çalışır — pano için `xclip`/`xsel` kurulu olmalı |
| Linux / Wayland | ⚠️ Global kısayol/enjeksiyon OS güvenlik kısıtları nedeniyle sınırlı |

---

## 6. Yol haritası

| Faz | Kapsam | Durum |
|---|---|---|
| **A** | macOS, config-güdümlü + çok-platform ajan | ✅ Uygulandı (macOS doğrulandı) |
| **B** | Windows doğrulama + Linux/X11 doğrulama | sırada |
| **C** | Linux/Wayland çözümü, oturum açılışında otomatik başlatma (per-OS) | sonra |
| **D** | GUI fazı — izin butonları, model combobox'u, işlem göstergesi, ayar arayüzü (bkz. [§7](#7-gui-fazı--kapsam-ileride)) | ileride |

---

## 7. GUI fazı — kapsam (ileride)

Aşağıdaki işler, çok-platform bir **GUI** (öneri: menü-bar uygulaması; framework
olarak **Tkinter** — sıfır bağımlılık, her OS) ile ele alınacaktır. Konuştuğumuz
ve buraya not ettiğimiz maddeler:

### 7.1 İzin yönetimi (macOS)
- İki buton: **"Girdi İzleme (Input Monitoring) izni"** ve **"Erişilebilirlik
  (Accessibility) izni"** — her biri doğrudan ilgili System Settings panelini
  açar (`x-apple.systempreferences:com.apple.preference.security?...`).
- Her izin için **canlı durum** göstergesi (✅/❌); izin verilince otomatik güncellenir.
- macOS'un kendi **izin istemi** butondan tetiklenebilir.
- Sınır: butonlar paneli açar ve durumu gösterir; **son anahtarı kullanıcı
  çevirir** (Apple, izni programatik vermeye izin vermez).

### 7.2 Model seçimi (combobox)
- Sunucudaki **kurulu modeller otomatik listelenip** (OpenAI-uyumlu `/v1/models`)
  bir combobox'a getirilir; kullanıcı seçer, seçim `config.json`'daki `model`
  alanına yazılır.
- Şu an model config'te elle yazılıyor; GUI bunu seçilebilir/keşfedilebilir yapar.

### 7.3 İşlem geri bildirimi (LLM beklemesi)
- LLM çalışırken **menü-bar simgesi döner/yanıp söner** (⟳), bitince normale döner.
- Böylece kısayol sonrası birkaç saniyelik LLM beklemesinde "çalışıyor" geri
  bildirimi verilir (şu an terminal dışında görünmüyor).
- Not: harmony + frekans + morfoloji çoğu durumu anlık çözdüğü için LLM beklemesi
  zaten yalnızca gerçek belirsizliklerde olur.

### 7.4 Ayar arayüzü
- `config.json` alanları (kısayol, `use_llm`, `use_morphology`, `timeout`,
  `model`, `base_url`, `api_key`, `llm_options`) GUI'den düzenlenebilir.
- Kısayol kaydedici (hotkey recorder), Tier 2/Tier 3 aç-kapa anahtarları.

**Framework önerisi:** Tkinter (stdlib, çok-platform). Menü-bar/tepsi göstergesi
için platforma özel ince bir katman gerekebilir (macOS: rumps benzeri).
