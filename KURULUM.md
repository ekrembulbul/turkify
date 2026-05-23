# Turkify — Kurulum ve Kullanım Kılavuzu

ASCII ile yazılmış Türkçe metni (`bugun gorusme yapacagiz`) doğru diakritiklerle
(`bugün görüşme yapacağız`) düzelten, **tamamen lokal** çalışan bir araç.

> Mimari ve tasarım için bkz. [PLAN.md](PLAN.md) · Faz planı için [ROADMAP.md](ROADMAP.md)

---

## İçindekiler

1. [Hızlı başlangıç (5 dakika)](#1-hızlı-başlangıç-5-dakika)
2. [Katmanlar ve neyi ne zaman kurmalı](#2-katmanlar-ve-neyi-ne-zaman-kurmalı)
3. [Ön koşullar](#3-ön-koşullar)
4. [Adım adım kurulum](#4-adım-adım-kurulum)
5. [Komut satırı kullanımı](#5-komut-satırı-kullanımı)
6. [Yapılandırma (config)](#6-yapılandırma-config)
7. [Kısayol ajanı (Hyper+A) — çok-platform](#7-kısayol-ajanı-hypera--çok-platform)
8. [Diğer platformlar (Windows / Linux)](#8-diğer-platformlar-windows--linux)
9. [Öğrenen sistem (tercihler)](#9-öğrenen-sistem-tercihler)
10. [Yapılandırma](#10-yapılandırma)
11. [Testler](#11-testler)
12. [Sorun giderme](#12-sorun-giderme)
13. [Kaldırma](#13-kaldırma)

---

## 1. Hızlı başlangıç (5 dakika)

En sade kurulum — yalnızca deterministik çekirdek (Tier 1), hiçbir dış bağımlılık yok:

```bash
cd ~/projects/turkify
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Dene:
echo "bugun gorusme yapacagiz" | python -m turkify
# Çıktı: bugün görüşme yapacağız
```

Bu kadarı bile günlük kullanım için yeterlidir ve **tamamen offline**, anlık çalışır.
Daha fazla doğruluk veya kısayol istersen aşağıdaki adımlara devam et.

---

## 2. Katmanlar ve neyi ne zaman kurmalı

Sistem kademelidir; her katman opsiyoneldir ve kurulu değilse sessizce atlanır.

| Katman | Ne yapar | Gerektirdiği | Kurmasan ne olur |
|---|---|---|---|
| **Tier 1** | Deterministik şapka restorasyonu | Yok (sadece Python) | — (her zaman çalışır) |
| **Tier 2** | Morfolojik doğrulama + frekans (geçersiz/belirsiz kelimeleri çözer) | `zeyrek` paketi (frekans verisi gömülü) | Tier 1 ile devam eder |
| **Tier 3** | Bağlamsal belirsizlik için LLM | Ollama + model (config'te) | LLM atlanır, deterministik kalır |
| **Kısayol ajanı** | Sistem geneli kısayol (seç → düzelt → yapıştır) | `pynput` + `pyperclip` | CLI'den elle çalıştırırsın |

**Öneri:** Tier 1 + Tier 2 + Ajan kombinasyonu çoğu kullanıcı için en iyi denge
(yüksek doğruluk + anlık kısayol). Tier 3'ü yalnızca bağlamsal belirsizliklerle
uğraşıyorsan, config'e bir model yazarak ekle.

---

## 3. Ön koşullar

- **macOS** (öncelikli; çekirdek motor ve ajan kodu çok-platform — bkz. [Bölüm 8](#8-diğer-platformlar-windows--linux)).
- **Python 3.10+** — kontrol: `python3 --version`
- (Tier 3 için) **Ollama** — `brew install ollama`
- (Kısayol için) **ajan bağımlılıkları** — `pip install -e ".[agent]"` (pynput + pyperclip)

---

## 4. Adım adım kurulum

### 4.1 Sanal ortam ve çekirdek (Tier 1)

```bash
cd ~/projects/turkify
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

> `-e` (editable) kurulumu, kaynak kodu düzenlediğinde yeniden kurmadan
> değişikliklerin geçerli olmasını sağlar.

### 4.2 Tier 2 — morfolojik doğrulama (opsiyonel, önerilir)

```bash
pip install -e ".[morphology]"
```

Bu `zeyrek` (ve bağımlılıkları `nltk`, `numpy`) kurar. **Not:** `zeyrek` normalde
NLTK tokenizer verisi ister; Turkify bunu baypas ettiği için **ek veri indirmen
gerekmez**. Kurulu olunca Tier 2 otomatik devreye girer.

Kontrol:

```bash
echo "citcit kopardim" | python -m turkify
# Çıktı: çıtçıt kopardım   (Tier 2 olmadan: çitçit)
```

### 4.3 Tier 3 — LLM rerank (opsiyonel)

Tier 3 **tamamen opsiyoneldir**; kurmasan da sistem Tier 1 + morfoloji + frekans
ile çalışır. LLM yalnızca **frekansın bile karar veremediği** gerçek bağlamsal
belirsizliklerde (`asmak`/`aşmak`, `ucu`/`üçü` gibi) ve `--llm` ile devreye girer.

```bash
brew install ollama
ollama serve                 # ayrı bir terminalde açık kalmalı
ollama pull qwen3.5:9b       # önerilen model (aşağıya bakın)

echo "bu zorlugu birlikte asmak zorundayiz" | python -m turkify --llm
```

> Tier 3 için config'te (ya da `--model` ile) bir model belirtilmelidir; model
> yoksa Tier 3 atlanır. İlk çağrıda model belleğe yüklenir (yavaş); ajan
> kullanıldığında motor sıcak kaldığı için sonraki çağrılar hızlıdır.

#### Hangi modeli kullanmalı?

**Model seçimi sana kalmış.** Genel kural: model büyüdükçe Türkçe bağlamı daha
iyi çözer ama yavaşlar ve daha çok bellek ister. Doğruluk/hız dengesini kendi
makinende ölç ve sana uyanı seç.

| Seviye | Model | Not |
|---|---|---|
| **Minimum** | Tier 3'süz (model yok) | Tier 1+2+frekans çoğu metni zaten doğru çözer |
| Hafif | `qwen2.5:7b` / `qwen3.5:4b` | Çalışır ama zor vakalarda hata yapabilir |
| **Önerilen** | `qwen3.5:9b` | Belirgin daha isabetli; biraz yavaş ama değer 🟢 |
| Daha güçlü | `qwen3.6:27b` / `qwen3.6:35b-a3b` | Daha iyi olabilir; ciddi bellek ister |

Kabaca bellek: 7b ~5 GB, 9b ~6–9 GB, 27b ~16 GB+ RAM/VRAM.

Modeli ayarlama (`--model` veya `TURKIFY_MODEL`):

```bash
# Tek seferlik:
echo "..." | python -m turkify --llm --model qwen3.5:9b-mlx

# Kalıcı (her komutta yazmadan):
export TURKIFY_MODEL=qwen3.5:9b-mlx

# Yavaş/büyük model için zaman aşımını da artırabilirsin (varsayılan 60 sn):
export TURKIFY_TIMEOUT=120
```

> Belirttiğin model Ollama'da yüklü değilse **hata vermez**; `--verbose` ile
> "model bulunamadi (once: ollama pull ...)" uyarısını görür, sistem
> deterministik sonuçla devam eder.

---

## 5. Komut satırı kullanımı

Tüm komutlar venv etkinken (`source .venv/bin/activate`) ya da
`./.venv/bin/python` tam yoluyla çalışır.

| Komut | Açıklama |
|---|---|
| `echo "metin" \| python -m turkify` | stdin'den okur, düzeltilmişi yazar |
| `python -m turkify dosya.txt` | Dosyadan okur |
| `python -m turkify --llm` | Tier 3 LLM'i etkinleştir |
| `python -m turkify --model AD` | Tier 3 modelini seç (config'i geçersiz kılar) |
| `python -m turkify --verbose` | Hangi kelimenin hangi katmanda (Tier 2/3) çözüldüğünü `stderr`'e yazar |
| `python -m turkify agent` | Çok-platform kısayol ajanını başlatır (bkz. [Bölüm 7](#7-kısayol-ajanı-hypera--çok-platform)) |

> `learn` / `forget` komutları **Faz 7 ile birlikte şimdilik devre dışıdır**
> (bkz. [Bölüm 9](#9-öğrenen-sistem-tercihler)).

**Davranış notları:**
- Çıktının sonuna yeni satır eklenmez; boşluk/noktalama/büyük-küçük harf birebir korunur.
- Ayarlar config'ten okunur (bkz. [Bölüm 6](#6-yapılandırma-config)); bayrak/env onları geçersiz kılar.
- URL, e-posta, sayı/kod içeren parçalar ve korumalı kelimeler **dokunulmaz**.

---

## 6. Yapılandırma (config)

Tüm ayarlar tek bir JSON config dosyasında toplanır.

- **Konum:** macOS/Linux → `~/.config/turkify/config.json`, Windows →
  `%APPDATA%\turkify\config.json` (`TURKIFY_CONFIG` ile değiştirilebilir).
- **Öncelik:** CLI bayrağı > `TURKIFY_*` env > config > varsayılan.

```jsonc
{
  "model": "qwen3.5:9b-mlx",        // ZORUNLU (Tier 3 için); null ise Tier 3 kapalı
  "use_llm": true,
  "use_morphology": true,
  "timeout": 120,
  "ollama_host": "http://localhost:11434",
  "hotkey": { "mods": ["ctrl", "alt", "cmd"], "key": "a" }
}
```

Başlamak için örneği kopyalayıp düzenle:

```bash
mkdir -p ~/.config/turkify
cp config/config.example.json ~/.config/turkify/config.json
# en azından "model" alanını doldur (Tier 3 isteniyorsa)
```

---

## 7. Kısayol ajanı (Hyper+A) — çok-platform

Herhangi bir uygulamada **seçili metni** kısayolla yerinde düzeltir (kopyala →
düzelt → yapıştır; panonu geri yükler). Hammerspoon/Raycast yerine **kendi
çok-platform ajanımız** kullanılır.

```bash
pip install -e ".[agent]"     # pynput + pyperclip
python -m turkify agent        # config'teki kısayolu dinler (varsayılan Hyper+A)
```

- Kısayolu değiştirmek için `config.json`'daki `hotkey` alanını düzenle, ajanı
  yeniden başlat.
- **macOS:** ilk çalıştırmada **Erişilebilirlik (Accessibility) izni** gerekir
  (Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik). Pano/tuş
  simülasyonu için zorunludur.
- Çıkış: `Ctrl-C`.

---

## 8. Diğer platformlar (Windows / Linux)

Çekirdek motor ve ajan kodu çok-platformdur; **öncelik macOS'tur**, diğerleri
peyderpey doğrulanacaktır.

| Platform | Durum |
|---|---|
| Windows | Beklenen şekilde çalışır (henüz doğrulanmadı) |
| Linux / X11 | Pano için `xclip` veya `xsel` kurulu olmalı |
| Linux / Wayland | Global kısayol/enjeksiyon OS kısıtları nedeniyle sınırlı |

Ayrıntı: [PORTABILITY.md](PORTABILITY.md).

---

## 9. Öğrenen sistem (tercihler)

> ⚠️ **Faz 7 şimdilik DEVRE DIŞIDIR; daha sonra ele alınacaktır.**
>
> Kod tabanı korunmuştur ancak ne motor ne de CLI buna bağlıdır:
> - `engine.py` içinde `_FAZ7_ENABLED = False` (tercih sorgulanmaz),
> - `learn` / `forget` komutları `__main__.py` dağıtımına kayıtlı değildir.
>
> Yeniden etkinleştirmek için: `_FAZ7_ENABLED = True` yap, `__main__.py`'deki
> `_COMMANDS` girdilerinin yorumunu kaldır ve `tests/test_learn.py`'deki skip'i sil.

**Tasarlanan davranış (etkinleştirildiğinde):** belirli bir kelimenin nasıl
düzeltileceğini kullanıcı belirler; tercihler lokal `cache/preferences.json`
dosyasında saklanır ve diğer tüm katmanların önüne geçer. Otomatik öğrenme
(kullanıcı düzeltmesini algılama) henüz yoktur — yalnızca elle `learn` komutu
tasarlanmıştır.

---

## 10. Yapılandırma

| Ne | Nerede | Açıklama |
|---|---|---|
| Korumalı kelimeler | `config/protected_words.txt` | Her satıra bir kelime; `#` yorum. Dönüştürülmez. |
| Frekans listesi | `data/tr_frequency.txt` | Tier 2 belirsizlik çözümü için (MIT, gömülü). `kelime sayı` biçimi. |
| Tercihler | `cache/preferences.json` | Faz 7 (devre dışı) — şu an kullanılmıyor. |
| Ana ayarlar | `~/.config/turkify/config.json` | model, use_llm, timeout, hotkey (bkz. [§6](#6-yapılandırma-config)) |
| LLM modeli | config `model` / `--model` / `TURKIFY_MODEL` | Önerilen `qwen3.5:9b-mlx`. |
| LLM zaman aşımı | config `timeout` / `TURKIFY_TIMEOUT` | Saniye; varsayılan 60. |
| Kısayol (hotkey) | config `hotkey` | Varsayılan Hyper+A; ajan okur. |
| Rerank prompt'u | `prompts/rerank_prompt.txt` | LLM'e verilen şablon. |

---

## 11. Testler

```bash
source .venv/bin/activate
pip install -e ".[morphology]"   # tam test kapsamı için
pip install pytest
pytest -q
```

- zeyrek/Ollama kurulu değilse ilgili entegrasyon testleri **otomatik atlanır**
  (mantık testleri yine de çalışır).

---

## 12. Sorun giderme

**`No module named turkify`**
venv etkin değil ya da paket kurulu değil. `source .venv/bin/activate` ve
`pip install -e .` çalıştır.

**Tier 2 çalışmıyor (geçersiz kelimeler düzelmiyor)**
`zeyrek` kurulu mu? `pip install -e ".[morphology]"`. Kontrol:
`python -c "from turkify import morphology; print(morphology.available())"` → `True` olmalı.

**`--llm` etkisiz / Tier 3 atlanıyor**
Config'te bir `model` var mı? Model yoksa Tier 3 çalışmaz. Ollama açık mı
(`ollama serve`) ve o model kurulu mu (`ollama list`)? Kontrol:
`curl -s http://localhost:11434/api/tags`. `--verbose` ile sebebi görebilirsin.

**Kısayol ajanı tepki vermiyor**
`pip install -e ".[agent]"` yapıldı mı? **macOS'ta Erişilebilirlik izni**
gerekir (Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik → terminal/
Python'a izin ver). Kısayolu `config.json`'dan kontrol et. Linux/Wayland'da
kısıt olabilir (bkz. [§8](#8-diğer-platformlar-windows--linux)).

**Düzeltme bir kelimeyi yanlış değiştirdi**
Sürekli yanlış dönüştürülen yabancı/teknik bir terimse
`config/protected_words.txt`'e ekle (her satıra bir kelime). Kelime bazlı
kullanıcı tercihi (Faz 7) şimdilik devre dışıdır.

---

## 13. Kaldırma

```bash
# Çalışan ajan varsa durdur (Ctrl-C ya da süreci sonlandır)

# Paket, ortam ve config
rm -rf ~/projects/turkify/.venv
rm -rf ~/.config/turkify
```
