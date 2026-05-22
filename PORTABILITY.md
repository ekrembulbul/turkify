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
| **Çekirdek motor** | Tier 1/2/3 düzeltme | yok (zeyrek/Ollama opsiyonel) | her platform |
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

### Format & konum
- **Format: JSON** (stdlib `json` ile bağımlılıksız okunur).
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
  "ollama_host": "http://localhost:11434",
  "hotkey": { "mods": ["ctrl", "alt", "cmd"], "key": "t" }   // Hyper+T
}
```
Örnek: [`config/config.example.json`](config/config.example.json).

---

## 3. Model

- Model **config'ten gelir ve zorunludur** (`model`). Belirtilmezse (`null`)
  Tier 3 (LLM) **çalışmaz** — otomatik model tespiti yapılmaz.
- Önceliğe göre `--model` / `TURKIFY_MODEL` config'i geçersiz kılar.
- İleride GUI'de kurulu modeller bir combobox'a getirilip kullanıcıya seçtirilecek.

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
| **D** | GUI / native arayüz, model combobox'u (ROADMAP Faz 6) | ileride |
