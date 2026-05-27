# Windows Paketleme

Turkify motorunu (Python) **donmuş bağımsız bir ikiliye** (`turkify-engine.exe`)
çevirip WPF uygulamasının yanına gömeriz; kullanıcı Python/venv kurmaz. Karar:
[ADR 0009](../../docs/adr/0009-paketleme-frozen-motor.md).

```
PyInstaller (motor → turkify-engine.exe)   [build_engine.ps1]
   →  dotnet publish (self-contained) + motoru gom   [build_app.ps1]
   →  Inno Setup installer   [turkify.iss]
```

## Bu klasördeki dosyalar
| Dosya | Ne |
|---|---|
| `turkify_engine.py` | PyInstaller giriş noktası (`turkify` CLI `main()`'i çağırır) |
| `turkify-engine.spec` | PyInstaller yapılandırması (onedir; turkify + zeyrek verisi gömülü) |
| `build_engine.ps1` | Temiz venv'de motoru dondurur → `dist\turkify-engine\turkify-engine.exe` |
| `build_app.ps1` | WPF'i self-contained yayınlar + motoru gömer → `dist\Turkify\` |
| `turkify.iss` | Inno Setup installer betiği → `dist\TurkifySetup.exe` |

`build\`, `dist\`, `.build-venv\` git'te yok sayılır.

## On kosul
- **.NET 8 SDK** (`dotnet --version`).
- **Python 3** (motoru dondurmek icin; build venv kendi olusturulur).
- (Installer icin) **Inno Setup** — https://jrsoftware.org/isdl.php

## 1. Motoru dondur (her surumde)
```powershell
windows\packaging\build_engine.ps1
```
Çıktı: `windows\packaging\dist\turkify-engine\turkify-engine.exe` (+ yanında kütüphaneler).
Hızlı test (script sonunda otomatik): bir satır JSON yanıt vermeli.

## 2. Uygulamayi yayinla + motoru gom
```powershell
windows\packaging\build_app.ps1
```
Çıktı: `windows\packaging\dist\Turkify\Turkify.exe` (gömülü `turkify-engine\` ile;
Python/venv gerekmez). `AppSettings.EngineExecutable()` `TURKIFY_PYTHON` env yoksa
bu gömülü ikiliyi kullanır.

## 3. Installer (opsiyonel)
```powershell
iscc windows\packaging\turkify.iss
```
Çıktı: `windows\packaging\dist\TurkifySetup.exe`. Program Files'a kurar, Başlat menüsü
kısayolu ekler; isteğe bağlı masaüstü simgesi ve "Windows ile başlat".

---

## Notlar / kararlar
- **Tier 2 (zeyrek)** spec'te `collect_all("zeyrek")` ile dahil edilir (build venv'inde
  `[morphology]` kurulu olduğu için). İstenmezse `build_engine.ps1`'de `[morphology]`
  çıkarılır ve uygulama Tier 1 + Tier 3 ile çıkar.
- **Tier 3 LLM gömülmez** — kullanıcının kendi yerel sunucusu (`base_url`).
- **Kod imzalama:** dağıtımda SmartScreen uyarısını azaltmak için `Turkify.exe` ve
  `turkify-engine.exe` bir Authenticode sertifikasıyla imzalanabilir (`signtool`).
  İmzasız da çalışır; kullanıcı SmartScreen'de "yine de çalıştır" der.
