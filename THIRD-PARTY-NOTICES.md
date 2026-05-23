# Üçüncü Taraf Bileşenler ve Lisanslar

Turkify **MIT** lisansıyla dağıtılır (bkz. [LICENSE](LICENSE)). Bu dosya,
projenin barındırdığı (vendored/gömülü) veya çalışma/geliştirme sırasında
kullandığı üçüncü taraf bileşenleri ve lisanslarını listeler.

| Bileşen | Kullanım | Lisans | Konum / Kaynak |
|---|---|---|---|
| Türkçe deasciifier (Deniz Yüret algoritması, Emre Sevinç Python uygulaması) | Gömülü (Tier 1) | Public Domain | `src/turkify/_yuret.py` · github.com/emres/turkish-deasciifier |
| FrequencyWords — Türkçe frekans listesi (Hermit Dave) | Gömülü veri (Tier 2 frekans) | MIT | `data/tr_frequency.txt` · github.com/hermitdave/FrequencyWords |
| zeyrek — morfolojik analizci | Opsiyonel çalışma zamanı bağımlılığı (Tier 2) | MIT | PyPI: `zeyrek` (paketlenmez) |
| nltk, numpy | zeyrek'in dolaylı bağımlılıkları | Apache-2.0 / BSD-3 | PyPI (paketlenmez) |
| pynput — global kısayol/tuş simülasyonu | Opsiyonel (`turkify agent`) | LGPL-3.0 | PyPI: `pynput` (paketlenmez) |
| pyperclip — pano okuma/yazma | Opsiyonel (`turkify agent`) | BSD-3 | PyPI: `pyperclip` (paketlenmez) |
| OpenAI-uyumlu yerel LLM sunucusu (ör. Ollama, LM Studio) + model (ör. Qwen) | Opsiyonel çalışma zamanı (Tier 3) | Kendi lisansları | Yerel olarak çalışır; paketlenmez |
| pytest | Yalnızca geliştirme/test | MIT | PyPI (paketlenmez) |

> "Paketlenmez": pip ile kurulan/dışarıda çalışan bileşenlerdir; bu repoda
> kaynak/veri olarak **dağıtılmaz**, yalnızca kullanılır. "Gömülü" olanlar bu
> repoda yer aldığından lisans/atıf bilgileri ilgili dosyaların başında da
> korunmuştur.

---

## Gömülü bileşenlerin lisans metinleri

### 1. Türkçe deasciifier — Public Domain

Algoritma: Deniz Yüret. Python uygulaması: Emre Sevinç
(github.com/emres/turkish-deasciifier). Kamu malı (public domain) olarak
yayımlanmıştır; herhangi bir kısıtlama olmaksızın kullanılabilir. Vendor edilen
dosyanın başında kaynak ve lisans notu korunmaktadır (`src/turkify/_yuret.py`).

### 2. FrequencyWords (Türkçe frekans listesi) — MIT

```
MIT License

Copyright (c) 2016 Hermit Dave

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> Not: FrequencyWords verisi OpenSubtitles korpusundan türetilmiştir.
