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
6. [Daemon (kalıcı süreç) — hız için](#6-daemon-kalıcı-süreç--hız-için)
7. [Hammerspoon kısayolu (Hyper + T)](#7-hammerspoon-kısayolu-hyper--t)
8. [Raycast komutu](#8-raycast-komutu)
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
| **Tier 3** | Bağlamsal belirsizlik için LLM | Ollama + model | LLM atlanır, deterministik kalır |
| **Daemon** | Gecikmeyi ~1 sn → ~30 ms düşürür | — | Her çağrı motoru yeniden yükler |
| **Hammerspoon / Raycast** | Sistem geneli kısayol | İlgili uygulama | CLI'den elle çalıştırırsın |

**Öneri:** Tier 1 + Tier 2 + Daemon + Hammerspoon kombinasyonu çoğu kullanıcı için
en iyi denge (yüksek doğruluk + anlık hız). Tier 3'ü yalnızca bağlamsal
belirsizliklerle uğraşıyorsan ekle.

---

## 3. Ön koşullar

- **macOS** (Hammerspoon/Raycast/daemon yolları macOS'a göredir; çekirdek motor taşınabilir).
- **Python 3.10+** — kontrol: `python3 --version`
- (Tier 3 için) **Ollama** — `brew install ollama`
- (Kısayol için) **Hammerspoon** — `brew install --cask hammerspoon` ve/veya **Raycast**

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
echo "citcit kopardim" | python -m turkify --no-daemon
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

> Tier 3 daemon üzerinden **gitmez**; `--llm` her zaman in-process çalışır. İlk
> çağrıda model belleğe yüklenir (yavaş), sonrakiler hızlanır.

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
| `python -m turkify --no-daemon` | Daemon'u atla, doğrudan in-process çalış |
| `python -m turkify --llm` | Tier 3 LLM'i etkinleştir (in-process) |
| `python -m turkify --verbose` | Hangi kelimenin hangi katmanda (Tier 2/3) çözüldüğünü `stderr`'e yazar (in-process'i zorlar) |
| `python -m turkify serve` | Daemon'u başlat |

> `learn` / `forget` komutları **Faz 7 ile birlikte şimdilik devre dışıdır**
> (bkz. [Bölüm 9](#9-öğrenen-sistem-tercihler)).

**Davranış notları:**
- Çıktının sonuna yeni satır eklenmez; boşluk/noktalama/büyük-küçük harf birebir korunur.
- Varsayılan olarak önce çalışan daemon denenir; yoksa in-process'e düşülür.
- URL, e-posta, sayı/kod içeren parçalar ve korumalı kelimeler **dokunulmaz**.

---

## 6. Daemon (kalıcı süreç) — hız için

Sorun: her çağrıda Python başlatma + morfoloji motoru yükleme ~1 saniye sürer.
Daemon motoru **bir kez** yükleyip bir Unix soketinde dinler; istemci sadece
sokete bağlanır → gecikme **~30 ms**'ye iner.

### Elle başlatma

```bash
python -m turkify serve
# Soket: /tmp/turkify-<kullanıcı-id>.sock
# Durdurmak için: Ctrl-C
```

Daemon çalışırken normal komutlar otomatik olarak ona bağlanır.

### Oturum açılışında otomatik başlatma (launchd)

```bash
# plist içindeki YOL'ların doğru olduğundan emin ol (varsayılan kullanıcı: ekrem)
cp launchd/com.turkify.daemon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.turkify.daemon.plist
```

Durdurma:

```bash
launchctl unload ~/Library/LaunchAgents/com.turkify.daemon.plist
```

Loglar: `/tmp/turkify-daemon.out.log` ve `/tmp/turkify-daemon.err.log`

---

## 7. Hammerspoon kısayolu (Hyper + T)

Herhangi bir uygulamada seçili metni **Ctrl+Alt+Cmd+T** ile yerinde düzeltir
(kopyala → düzelt → yapıştır; panonu eski haline döndürür).

1. Hammerspoon'u kur ve aç: `brew install --cask hammerspoon`
2. `~/.hammerspoon/init.lua` dosyasına şu satırı ekle:

   ```lua
   dofile(os.getenv("HOME") .. "/projects/turkify/hammerspoon/turkify.lua")
   ```

3. Hammerspoon menüsünden **Reload Config**.
4. Bir yere `bugun gorusme` yaz, seç, **Hyper+T**'ye bas.

> Daemon çalışıyorsa anlık; çalışmıyorsa ilk basışta ~1 sn sürer (motor yüklenir).
> Hammerspoon betiğinde hotkey, timeout gibi ayarlar dosyanın başındadır.

---

## 8. Raycast komutu

Panodaki (clipboard) metni düzelten basit bir script command.

1. Raycast → **Settings → Extensions → Script Commands → Add Script Directory**
2. `~/projects/turkify/raycast` klasörünü ekle.
3. Kullanım: metni kopyala (Cmd+C) → Raycast'te **"Türkçe Düzelt (pano)"** komutunu çalıştır → sonuç panoya yazılır.

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
| LLM modeli | `--model` bayrağı / `TURKIFY_MODEL` env | Önerilen `qwen3.5:9b-mlx`; bkz. [§4.3](#43-tier-3--llm-rerank-opsiyonel). |
| LLM zaman aşımı | `TURKIFY_TIMEOUT` env | Saniye; varsayılan 60. |
| Rerank prompt'u | `prompts/rerank_prompt.txt` | LLM'e verilen şablon. |
| Hotkey / timeout | `hammerspoon/turkify.lua` (dosya başı) | Hyper+T, süreler. |
| Soket yolu | `src/turkify/server.py` → `default_socket_path()` | `/tmp/turkify-<uid>.sock` |

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

**`--llm` etkisiz / yavaş**
Ollama açık mı? `ollama serve` çalışıyor olmalı ve `ollama pull qwen2.5:7b`
yapılmış olmalı. Kontrol: `curl -s http://localhost:11434/api/tags`.

**Hammerspoon Hyper+T tepki vermiyor**
init.lua'daki `dofile` yolunu ve Reload Config'i kontrol et. Betikteki `PYTHON`
yolu `~/projects/turkify/.venv/bin/python` ile eşleşmeli.

**Daemon'a bağlanmıyor / eski soket**
Daemon yeniden başlayınca eski soketi kendisi temizler. Elle:
`rm -f /tmp/turkify-$(id -u).sock` sonra `python -m turkify serve`.

**Düzeltme bir kelimeyi yanlış değiştirdi**
Sürekli yanlış dönüştürülen yabancı/teknik bir terimse
`config/protected_words.txt`'e ekle (her satıra bir kelime). Kelime bazlı
kullanıcı tercihi (Faz 7) şimdilik devre dışıdır.

---

## 13. Kaldırma

```bash
# launchd servisi (kurduysan)
launchctl unload ~/Library/LaunchAgents/com.turkify.daemon.plist
rm -f ~/Library/LaunchAgents/com.turkify.daemon.plist

# Hammerspoon: init.lua'daki dofile satırını sil, Reload Config

# Paket ve ortam
rm -rf ~/projects/turkify/.venv
rm -f /tmp/turkify-$(id -u).sock
```
