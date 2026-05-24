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
| **Tier 3** | Bağlamsal belirsizlik için LLM | OpenAI-uyumlu yerel sunucu (Ollama, LM Studio, …) + model | LLM atlanır, deterministik kalır |
| **Kısayol ajanı** | Sistem geneli kısayol (seç → düzelt → yapıştır) | `pynput` + `pyperclip` | CLI'den elle çalıştırırsın |

**Öneri:** Tier 1 + Tier 2 + Ajan kombinasyonu çoğu kullanıcı için en iyi denge
(yüksek doğruluk + anlık kısayol). Tier 3'ü yalnızca bağlamsal belirsizliklerle
uğraşıyorsan, config'e bir model yazarak ekle.

---

## 3. Ön koşullar

- **macOS** (öncelikli; çekirdek motor ve ajan kodu çok-platform — bkz. [Bölüm 8](#8-diğer-platformlar-windows--linux)).
- **Python 3.10+** — kontrol: `python3 --version`
- (Tier 3 için) **OpenAI-uyumlu bir yerel LLM sunucusu** — ör. Ollama (`brew install ollama`), LM Studio, llama.cpp, Jan, MLX
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

Turkify, **OpenAI-uyumlu** (`/v1/chat/completions`) herhangi bir yerel LLM
sunucusuyla konuşur. Bu protokolü **Ollama, LM Studio, llama.cpp (server), Jan,
GPT4All, vLLM, MLX** gibi araçların hepsi destekler; sunucunun adresini
config'teki `base_url` ile seçersin.

```bash
# Örnek: Ollama (OpenAI-uyumlu ucu localhost:11434/v1)
brew install ollama
ollama serve                 # ayrı bir terminalde açık kalmalı
ollama pull qwen3.5:9b       # önerilen model (aşağıya bakın)

echo "bu zorlugu birlikte asmak zorundayiz" | python -m turkify --llm
```

> **Başka sunucu kullanmak için** `base_url`'ü değiştir (varsayılan Ollama'nın
> ucu). Örn. LM Studio için `http://localhost:1234/v1`. Sunucu API anahtarı
> istiyorsa config'teki `api_key` (ya da `TURKIFY_API_KEY`) alanını doldur;
> yerel sunucular genelde istemez.

> Tier 3 için config'te (ya da `--model` ile) bir model belirtilmelidir; model
> yoksa Tier 3 atlanır. İlk çağrıda model belleğe yüklenir (yavaş); ajan
> kullanıldığında motor sıcak kaldığı için sonraki çağrılar hızlıdır.

> ⚠️ **Düşünen (reasoning) modeller** (Qwen3.5/3.6 gibi) yanıttan önce uzun bir
> akıl yürütme üretip yavaşlayabilir. Kapatma yöntemleri ve ödünleşimi için
> aşağıdaki [Düşünme modunu kapatma](#düşünme-reasoning-modunu-kapatma) bölümüne bak.

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

#### Düşünme (reasoning) modunu kapatma

**"Düşünen" modeller** (Qwen3.5/3.6 gibi) cevaptan önce uzun bir akıl yürütme
(reasoning) üretir. Bu **doğruluğu artırır** ama yavaşlatır (tek belirsiz kelime
için ~15–20 sn). Tier 3 zaten yalnızca gerçek belirsizliklerde çalıştığı ve ajan
motoru sıcak tuttuğu için günlük kullanımda bu bekleme seyrektir.

> ⚠️ **Ödünleşim:** Düşünmeyi kapatmak hızlandırır **ama doğruluğu düşürebilir** —
> hem de tam olarak Tier 3'ün devreye girdiği zor/belirsiz vakalarda. Ölçtük:
> *"bu engeli birlikte asmak"* → düşününce doğru **aşmak** (~16 sn), düşünmeyince
> yanlış **asmak** (~1 sn). Bu yüzden **varsayılan: düşünme açık.**

Yine de kapatmak istersen iki kaldıraç var; hangisinin işe yaradığı modelin
**çalıştırma motoruna** bağlıdır:

**MLX vs normal (GGUF) modeller**
- **MLX** (Apple Silicon'da hızlı; LM Studio'da adı `...-mlx`): MLX motoru
  `chat_template_kwargs`'ı template'e **geçirmez**, o yüzden o yöntem MLX'te etkisizdir.
- **GGUF / llama.cpp tabanlı** (Ollama, LM Studio GGUF, llama.cpp server):
  `chat_template_kwargs`'ı düzgün işler. Hatta bazı GGUF build'leri (ör. Unsloth
  Qwen3.5 küçük modeller) düşünmeyi **varsayılan kapalı** getirir.

**Yöntem 1 — `llm_options` → `chat_template_kwargs`** (template-bilinçli motorlar):
```jsonc
"llm_options": { "chat_template_kwargs": { "enable_thinking": false } }
```
`llm_options` içeriği `/chat/completions` gövdesine **olduğu gibi** eklenir (Turkify
yorumlamaz). vLLM, SGLang, llama.cpp ve GGUF modellerde çalışır; **LM Studio MLX'te
yok sayılır.**

**Yöntem 2 — `assistant_prefill`** (motor `chat_template_kwargs`'ı yok sayıyorsa):
```jsonc
"assistant_prefill": "<think>\n\n</think>\n\n"
```
İsteğin sonuna boş bir `<think></think>` bloğu içeren bir asistan mesajı ekler; model
"zaten düşündüm (boş)" sayıp doğrudan cevaba geçer (Qwen'in kendi non-thinking
mekanizması). **Her motorda çalışır** — MLX dahil.

| Yöntem | LM Studio (MLX) | Ollama / GGUF / llama.cpp / vLLM |
|---|---|---|
| `llm_options.chat_template_kwargs` | ❌ yok sayılır | ✅ çalışır (en temiz) |
| `assistant_prefill` (`<think></think>`) | ✅ çalışır | ✅ çalışır |

> 💡 **En sağlam hız çözümü:** düşünmeyen bir **instruct** model seçmek (ör.
> Qwen2.5-Instruct veya Unsloth'un non-thinking GGUF'u). O zaman hiçbir ayara gerek
> kalmaz; ama yukarıdaki doğruluk ödünleşimini hatırla.

> ℹ️ **`llm_options` ile `assistant_prefill` farkı:** `llm_options` isteğin
> **gövdesine alan** ekler (parametre); `assistant_prefill` ise isteğe bir **mesaj**
> ekler. Düşünmeyi kapatmak bir mesaj (boş `<think>`) gerektirdiğinden, MLX gibi
> motorlarda yalnızca `assistant_prefill` işe yarar.

---

## 5. Komut satırı kullanımı

Tüm komutlar venv etkinken (`source .venv/bin/activate`) ya da
`./.venv/bin/python` tam yoluyla çalışır.

| Komut | Açıklama |
|---|---|
| `echo "metin" \| python -m turkify` | stdin'den okur, düzeltilmişi yazar |
| `python -m turkify dosya.txt` | Dosyadan okur |
| `python -m turkify agent` | Çok-platform kısayol ajanını başlatır (bkz. [Bölüm 7](#7-kısayol-ajanı-hypera--çok-platform)) |

**Ayar bayrakları** (her ikisi — düzeltme ve `agent` — kabul eder; hepsi
config'i geçersiz kılar):

| Bayrak | Açıklama |
|---|---|
| `--llm` / `--no-llm` | Tier 3 LLM'i aç / kapat |
| `--morphology` / `--no-morphology` | Tier 2 morfolojiyi aç / kapat |
| `--model AD` | Tier 3 modeli |
| `--timeout SN` | LLM istek zaman aşımı (saniye) |
| `--base-url URL` | OpenAI-uyumlu sunucu kökü (ör. `http://localhost:1234/v1`) |
| `--api-key ANAHTAR` | Sunucu API anahtarı |
| `--llm-options JSON` | İsteğe eklenecek JSON gövdesi alanları, ör. `'{"chat_template_kwargs":{"enable_thinking":false}}'` |
| `--assistant-prefill S` | İsteğe asistan prefill'i ekler; düşünmeyi atlatmak için `$'<think>\n\n</think>\n\n'` |
| `--verbose` / `-v` | Hangi kelimenin hangi katmanda çözüldüğünü `stderr`'e yazar |

Örnek (config'e dokunmadan, tamamen bayrakla):
```bash
echo "bu engeli asmak gerek" | python -m turkify \
  --llm --model qwen3.5-9b-mlx --base-url http://localhost:1234/v1 --verbose
```

> `learn` / `forget` komutları **Faz 7 ile birlikte şimdilik devre dışıdır**
> (bkz. [Bölüm 9](#9-öğrenen-sistem-tercihler)).

**Davranış notları:**
- Çıktının sonuna yeni satır eklenmez; boşluk/noktalama/büyük-küçük harf birebir korunur.
- Öncelik: **CLI bayrağı > `TURKIFY_*` env > config > varsayılan** (bkz. [Bölüm 6](#6-yapılandırma-config)).
- URL, e-posta, sayı/kod içeren parçalar ve korumalı kelimeler **dokunulmaz**.

---

## 6. Yapılandırma (config)

Tüm ayarlar tek bir JSON config dosyasında toplanır.

- **Konum:** macOS/Linux → `~/.config/turkify/config.json`, Windows →
  `%APPDATA%\turkify\config.json` (`TURKIFY_CONFIG` ile değiştirilebilir).
- **Öncelik:** CLI bayrağı > `TURKIFY_*` env > config > varsayılan.
- **Ortam değişkenleri** (config alanının karşılığı): `TURKIFY_MODEL`,
  `TURKIFY_USE_LLM`, `TURKIFY_USE_MORPHOLOGY`, `TURKIFY_TIMEOUT`,
  `TURKIFY_BASE_URL`, `TURKIFY_API_KEY`, `TURKIFY_LLM_OPTIONS` (JSON metni),
  `TURKIFY_ASSISTANT_PREFILL`.

```jsonc
{
  "model": "qwen3.5:9b-mlx",        // ZORUNLU (Tier 3 için); null ise Tier 3 kapalı
  "use_llm": true,
  "use_morphology": true,
  "timeout": 120,
  "base_url": "http://localhost:11434/v1",  // OpenAI-uyumlu sunucu (LM Studio: .../1234/v1)
  "api_key": null,                  // yerel sunucular genelde istemez
  "llm_options": {},                // istek govdesine eklenecek alanlar ( or. chat_template_kwargs)
  "assistant_prefill": null,        // ust asistan prefill'i; dusunmeyi kapatmak icin "<think>\n\n</think>\n\n"
  "hotkey": { "mods": ["ctrl", "alt", "cmd"], "key": "a" }   // meta=OS'a göre: macOS cmd / Windows win / Linux super
}
```

> ⚠️ **Yukarıdaki `//` açıklamalar yalnızca anlatım içindir.** Gerçek
> `config.json` **saf JSON** olmalı — JSON yorum (`//`) desteklemez. Yorumlu bir
> dosya geçersiz sayılır ve config sessizce **yok sayılıp** varsayılanlara
> dönülür (artık bu durumda stderr'e bir uyarı yazılır). En temizi:
> `config/config.example.json`'u (yorumsuz) kopyalamak.

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
- **Modifier adları OS'a göre:** meta tuşu macOS `cmd`, Windows `win`, Linux
  `super`. Alt/Option her yerde `alt`/`opt`/`option` olarak yazılabilir (macOS'ta
  bu tuş **Option**'dır, "alt" etiketi yoktur). `ctrl`/`shift` her platformda aynı.
  Tam tablo: [PORTABILITY.md §4](PORTABILITY.md#4-kısayol-ajanı-turkify-agent).
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
Config'te bir `model` var mı? Model yoksa Tier 3 çalışmaz. LLM sunucusu açık mı
(ör. Ollama için `ollama serve`) ve o model kurulu mu? Kontrol (OpenAI-uyumlu uç):
`curl -s http://localhost:11434/v1/models`. `--verbose` ile sebebi görebilirsin.

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
