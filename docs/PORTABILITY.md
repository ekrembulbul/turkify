# Turkify — Taşınabilirlik ve Yapılandırma

> Turkify **macOS öncelikli** olmak üzere çok-platformludur (Windows, Linux). Tüm
> çalışma zamanı ayarları bir **config dosyasında** toplanır.
>
> **Mimari yön (Faz 6):** Her OS kendi **native** frontend'ini kullanır; paylaşımlı
> Python motoru bir **düzeltme servisi** (`turkify serve`) olarak sunulur. Kararlar:
> [ADR 0003](adr/0003-native-per-os-gui.md) (native-per-OS),
> [ADR 0004](adr/0004-motor-sinir-protokolu.md) (serve protokolü),
> [ADR 0005](adr/0005-linux-terminal-servis.md) (Linux).
>
> Durum: Çekirdek + CLI + `turkify serve` ve **macOS native uygulaması** çalışıyor.
> Windows/Linux native frontend'leri sıradaki iştir (bkz. [ROADMAP Faz 6](ROADMAP.md)).

---

## 1. Mimari

| Katman | Sorumluluk | Bağımlılık | OS |
|---|---|---|---|
| **Çekirdek motor** | Tier 1/2/3 düzeltme (`correct()`) | yok (zeyrek/LLM sunucusu opsiyonel) | her platform |
| **CLI** (`turkify`) — *birincil, kalıcı* | stdin/dosya → düzeltilmiş metin (in-process) | — | her platform |
| **Motor servisi** (`turkify serve`) | Sıcak motoru JSON protokolüyle sunar (stdio/soket) | — | her platform |
| **Native frontend** | menü-bar/tray + kısayol + pano + izinler → servise konuşur | OS'a özel (bkz. aşağı) | macOS ✅ / Win / Linux |
| **Config** (`config.py`) | Tüm ayarları tek JSON'da topla + öncelik çöz | — | her platform |

Native frontend'ler (Faz 6):

| OS | Dil / UI | Motor erişimi |
|---|---|---|
| macOS | Swift / SwiftUI menü-bar | `serve --stdio` (GUI sıcak süreç sahibi) |
| Windows | C#/.NET / WPF tray | `serve --stdio` (GUI sıcak süreç sahibi) |
| Linux | Python / terminal + `systemd --user` | `serve --socket` (servis sıcak) |

\* Linux/Wayland'da global kısayol/enjeksiyon OS kısıtları nedeniyle sınırlıdır
(bkz. [§5](#5-bilinen-kısıtlar)); Linux'ta tetikleme masaüstü ortamının kısayoluyla yapılır.

> **CLI birincildir ve kalıcıdır.** `turkify` CLI birinci-sınıf ve **birincil
> kullanım senaryosudur** — in-process çalışır, `serve`/native frontend'e bağımlı
> değildir, her zaman kullanılabilir kalır ([ADR 0006](adr/0006-cli-birinci-sinif-kalici.md)).
> Sistem geneli kısayol artık **native frontend'in** görevidir; eski geçici
> `turkify agent` (pynput/pyperclip) **kaldırıldı**. `serve`/native katmanlar
> CLI'ın **üstüne** eklenir, yerine geçmez.
>
> **`serve` ve daemon:** Eskiden bir "daemon" vardı, kaldırılmıştı. Frontend'ler
> artık farklı dillerde (Swift/C#) olduğundan motoru o dilden sıcak tutmak için
> `serve` geri getirildi — bu sefer **gerekçeli ve tek JSON protokolüyle**
> (bkz. [ADR 0004](adr/0004-motor-sinir-protokolu.md)). Eski
> **Hammerspoon/Raycast/launchd** (yalnızca macOS) kaldırılmış durumda.

### Motor servisi sözleşmesi (`turkify serve`)
Tek bir **satır-bazlı JSON** protokolü; iki taşıma, aynı mesaj formatı
([ADR 0004](adr/0004-motor-sinir-protokolu.md)):

```
istek :  {"id": 1, "text": "bugun gorusme"}
yanıt :  {"id": 1, "corrected": "bugün görüşme"}
hata  :  {"id": 1, "error": "..."}
kontrol: {"cmd": "ping"} → {"ok": true}
         {"cmd": "reload"}   (config.json değişince motor ayarları yeniden okur)
```

- `serve --stdio`: GUI sahipli (macOS/Windows). GUI motoru çocuk süreç olarak
  başlatır, sıcak tutar; GUI kapanınca stdin EOF → motor temiz çıkar.
- `serve --socket PATH`: bağımsız servis (Linux `systemd --user`).
- Motor başlangıçta `config.resolve()` ile ayarları okur; `reload` ile tazeler.
- `engine.correct` aynen kullanılır; `serve` yalnızca ince bir taşıma sarmalayıcısıdır.

---

## 2. Yapılandırma (config)

> **`config.json` kapsamı:** Linux servisi ve **CLI** içindir. **macOS/Windows
> GUI** ayarları native saklar (macOS `UserDefaults`) ve motora **CLI bayrakları**
> olarak geçirir — config.json kullanmaz ([ADR 0007](adr/0007-ayar-saklama-gui-native.md)).
> Bayraklar öncelikli olduğundan (aşağıya bkz.) GUI ayarları, ortamda bir config.json
> olsa bile kazanır.

### Öncelik
```
CLI bayrağı  >  TURKIFY_* ortam değişkeni  >  config dosyası  >  yerleşik varsayılan
```
Bu sıra `config.resolve()` içinde uygulanır: `load()` (config+varsayılan) → env
katmanı → CLI override. Her ayar hem env hem CLI bayrağı olarak verilebilir.

### Ortam değişkenleri
Her config alanının bir `TURKIFY_*` karşılığı vardır: `TURKIFY_MODEL`,
`TURKIFY_USE_LLM`, `TURKIFY_USE_MORPHOLOGY`, `TURKIFY_TIMEOUT`, `TURKIFY_BASE_URL`,
`TURKIFY_API_KEY`, `TURKIFY_LLM_OPTIONS` (JSON metni), `TURKIFY_ASSISTANT_PREFILL`.
Geçersiz bir env değeri (ör. sayı olmayan `TURKIFY_TIMEOUT`) yok sayılır ve uyarı yazılır.

### CLI bayrakları
`--model`, `--llm`/`--no-llm`, `--morphology`/`--no-morphology`, `--timeout`,
`--base-url`, `--api-key`, `--llm-options` (JSON), `--assistant-prefill`,
`--verbose`/`-v`. Düzeltme ve `serve` komutları kabul eder.

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
  "llm_options": {},                // /chat/completions gövdesine eklenecek ekstra ALANLAR
  "assistant_prefill": null         // isteğe eklenecek asistan MESAJI (ör. "<think>\n\n</think>\n\n")
}
```
Örnek: [`config/config.example.json`](../config/config.example.json).

> **Not:** Kısayollar config'te tutulmaz. Sistem geneli kısayol (düzeltme/iptal)
> **native frontend'in** ayarıdır ve orada saklanır (macOS: UserDefaults —
> [ADR 0007](adr/0007-ayar-saklama-gui-native.md)); config.json yalnızca motor
> ayarlarını taşır.

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
- `llm_options` (dict) `/chat/completions` gövdesine ekstra **alan** olarak eklenir;
  böylece sunucu/model-özel ayarlar (ör. `chat_template_kwargs`, `reasoning_effort`)
  Turkify'a hardcode edilmeden yönetilir. `temperature`/`max_tokens` buradan
  ezilebilir; `model`/`messages`/`stream` korunur (doğruluğa etkili oldukları için).
- `assistant_prefill` (str) isteğin sonuna bir asistan **mesajı** ekler. Başlıca
  kullanım: düşünen modellerde reasoning'i atlatmak — `"<think>\n\n</think>\n\n"`
  verilince model doğrudan cevaba geçer. `llm_options`'tan farkı: o **alan** ekler,
  bu **mesaj** ekler.

### Düşünme (reasoning) modu — motor farkı
"Düşünen" modeller (Qwen3.5/3.6) cevaptan önce uzun reasoning üretir: daha doğru
ama yavaş. Kapatma yöntemi **çalıştırma motoruna** bağlıdır:

| Yöntem | LM Studio (MLX) | Ollama / GGUF / llama.cpp / vLLM |
|---|---|---|
| `llm_options: {chat_template_kwargs:{enable_thinking:false}}` | ❌ yok sayılır | ✅ çalışır |
| `assistant_prefill: "<think>\n\n</think>\n\n"` | ✅ çalışır | ✅ çalışır |

- **MLX** motoru `chat_template_kwargs`'ı template'e geçirmez → o yöntem MLX'te
  etkisiz; `assistant_prefill` gerekir. **GGUF/llama.cpp** ikisini de işler (bazı
  GGUF build'leri düşünmeyi varsayılan kapalı getirir).
- ⚠️ Düşünmeyi kapatmak hızlandırır ama **doğruluğu düşürebilir** — hem de tam Tier 3'ün
  devreye girdiği belirsiz vakalarda. Varsayılan: düşünme açık. (Ayrıntı:
  [KURULUM.md → Düşünme modunu kapatma](KURULUM.md#düşünme-reasoning-modunu-kapatma).)

---

## 4. Sistem geneli kısayol (native frontend)

Sistem geneli kısayol artık **native frontend'in** görevidir (eski `turkify agent`
kaldırıldı). Frontend motoru `serve` ile sıcak tutar, global kısayolu dinler ve
seçili metni kopyala → düzelt → yapıştır yapar.

- **macOS uygulaması:** kısayol Carbon `RegisterEventHotKey` ile global dinlenir;
  pano/tuş simülasyonu CGEvent (Cmd+C / Cmd+V) ile yapılır. İki kısayol vardır:
  düzeltme (varsayılan **Hyper+A**) ve işlem iptali (varsayılan **Hyper+Q**).
  Kullanıcı uygulama içinden "Değiştir" ile yeniden atar.
- **Kısayollar config'te değil**, native frontend'in kendi deposundadır (macOS:
  UserDefaults — [ADR 0007](adr/0007-ayar-saklama-gui-native.md)). Modifier adları
  uygulama içinde `ctrl`/`opt`/`cmd`/`shift` olarak tutulur; meta tuşu OS'a göre
  (macOS `cmd`, Windows `win`, Linux `super`).
- **Linux:** uygulama kısayol *yakalamaz* (Wayland kısıtı). Hem düzeltme hem iptal
  birer **DE custom shortcut**'tır (GNOME/KDE klavye ayarları); her biri bir komut
  çalıştırır (düzeltme: seçim → sokete gönder → yapıştır; iptal: çalışan isteğe
  iptal sinyali). Kombinasyonu kullanıcı DE'de tanımlar — bkz.
  [ADR 0005](adr/0005-linux-terminal-servis.md).
- Kurulum/kullanım (macOS): [`macos/README.md`](../macos/README.md).

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

Taşınabilirlik artık **Faz 6 (Native Arayüzler + Motor Servisi)** altında ilerliyor;
tam plan: [ROADMAP.md → Faz 6](ROADMAP.md). Özet sıra:

| Aşama | Kapsam | Durum |
|---|---|---|
| **6.0** | `turkify serve` (stdio + soket JSON protokolü); eski `agent` kaldırıldı | tamam |
| **6.1** | macOS native app (Swift / SwiftUI menü-bar) — MVP | sonra |
| **6.2** | Windows native app (C#/.NET / WPF tray) | sonra |
| **6.3** | Linux (Python, terminal + `systemd --user` servisi) | sonra |
| **6.4** | Paketleme & dağıtım (Python gömme, imzalama, repo/Flatpak) | en son |

---

## 7. GUI fazı — kapsam (Faz 6)

Aşağıdaki işler **native frontend**'lerle ele alınır (tek çok-platform framework
**değil** — bkz. [ADR 0003](adr/0003-native-per-os-gui.md)):

- **macOS:** Swift / SwiftUI menü-bar (`MenuBarExtra`).
- **Windows:** C#/.NET / WPF tray.
- **Linux:** native GUI yok; terminal + `systemd --user` servisi ([ADR 0005](adr/0005-linux-terminal-servis.md)).

Her frontend motora `turkify serve` (JSON protokolü) üzerinden konuşur. Aşağıdaki
maddeler özellikle **macOS/Windows GUI** için geçerlidir (Linux'ta config + log ile):

### 7.1 İzin yönetimi (macOS)
- Tek izin gerekir: **"Erişilebilirlik (Accessibility)"** — buton doğrudan ilgili
  System Settings panelini açar (`x-apple.systempreferences:com.apple.preference.security?...`).
  CGEvent ile Cmd+C/Cmd+V göndermek için zorunludur. Global kısayol Carbon
  `RegisterEventHotKey` ile, kayıt UI'ı yerel `NSEvent` monitörüyle çalışır;
  ikisi de **Input Monitoring gerektirmez**, bu yüzden o izin istenmez.
- İzin için **canlı durum** göstergesi (✅/❌); izin verilince otomatik güncellenir.
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
- Motor ayarları (`use_llm`, `use_morphology`, `timeout`, `model`, `base_url`,
  `api_key`, `llm_options`, `assistant_prefill`) ve kısayollar (düzeltme/iptal)
  düzenlenebilir; kısayol kaydedici (hotkey recorder) uygulamada mevcuttur.
- macOS GUI ayarları **native saklar** (UserDefaults) ve motora **CLI bayrakları**
  olarak geçirir; `config.json` kullanmaz ([ADR 0007](adr/0007-ayar-saklama-gui-native.md)).
  (Linux servisi config.json + `{"cmd":"reload"}` kullanır.)

**Teknoloji:** native-per-OS (macOS Swift, Windows C#/WPF, Linux config+terminal).
Tek çapraz-platform framework (Tkinter vb.) **terk edildi** — gerekçe: macOS izin
yönetimi native API gerektiriyor ve native kalite hedefleniyor ([ADR 0003](adr/0003-native-per-os-gui.md)).
