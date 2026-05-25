# ADR 0009 — Paketleme: motoru donmuş (frozen) yardımcı olarak .app/.exe içine göm

**Durum:** ✅ Kabul · [ADR 0003](0003-native-per-os-gui.md)/[0004](0004-motor-sinir-protokolu.md)'ü tamamlar (Faz 6.4)

## Bağlam
Dağıtımda son kullanıcının makinesinde **Python yok** (ve venv kurması beklenemez).
Native uygulama (macOS Swift, ileride Windows) motoru `turkify serve` ile çocuk
süreç olarak başlatıyor; bugün bu, geliştirici venv'ine bağlı
(`engineExecutable()` → `$TURKIFY_PYTHON` ya da `python3 -m turkify`). Bu, dağıtım
için uygun değil.

Ayrıca motorun çalışma-zamanı **veri dosyaları** (`tr_frequency.txt`,
`rerank_prompt.txt`) repo köküne göre (`Path(__file__).parents[2]/...`) okunuyordu;
paketlenince/dondurulunca bu yol kırılır.

> Not: **Tier 3 LLM gömülmez.** O, kullanıcının kendi yerel sunucusudur (`base_url`,
> [ADR 0002](0002-openai-uyumlu-llm-api.md)). Biz yalnızca motoru (Tier 1 + opsiyonel
> Tier 2 + HTTP istemcisi) paketleriz.

## Karar
1. **Motor, donmuş bağımsız bir yardımcı çalıştırılabilir** olarak paketlenir
   (**PyInstaller**, `onedir` modu — `onefile`'dan hızlı açılır ve imzalaması temiz)
   ve native uygulamanın bundle'ı **içine** gömülür
   (ör. `Turkify.app/Contents/Resources/turkify-engine/`). Kullanıcı Python/venv
   kurmaz; motor uygulamayla gelir.
2. Native uygulama bu gömülü ikiliyi `serve --stdio` ile başlatır. `engineExecutable()`
   geliştirmede `$TURKIFY_PYTHON`'ı, **release'te bundle içindeki ikiliyi** kullanır.
3. **Veri dosyaları pakete gömülür** ve `importlib.resources` ile okunur
   (`turkify/data/`, `turkify/prompts/`). Bu; editable kurulum, wheel ve frozen
   uygulama — üçünde de çalışır. (`parents[2]` repo-kökü yöntemi terk edildi.)
4. **Kanal: Developer ID + notarization** (App Store **dışı**). Gömülü ikili ve tüm
   `.dylib`'ler uygulamanın kimliğiyle imzalanır, **hardened runtime** açık, sonra
   notarize + staple. App Sandbox **kapalı** kalır (Erişilebilirlik + CGEvent gerekli;
   bkz. [ADR 0003](0003-native-per-os-gui.md)).

## Sonuçlar
- ✅ Kullanıcı tek bir `.app` indirir; Python/bağımlılık kurulumu yok.
- ✅ Veri erişimi her ortamda (dev / wheel / frozen) tutarlı (`importlib.resources`).
- ✅ Tier 3 dışarıda kaldığı için paket küçük ve LLM lisans/indirme derdi yok.
- ➖ Build hattı karmaşıklaşır: PyInstaller → bundle'a kopyala → codesign → notarize
   → DMG (Faz 6.4 işi). CI'da otomatikleştirilmeli.
- ➖ **Tier 2 (zeyrek)** dahil edilecekse PyInstaller hook'ları + zeyrek verisi gerekir
   (paket büyür). Almazsak shipping uygulama Tier 1 + Tier 3 ile çıkar; karar Faz 6.4'te.
- ➖ Mac App Store yolu kapalı (Erişilebilirlik/CGEvent + helper spawn MAS'a takılır).
- ➖ Frozen ikili imzalama: PyInstaller çıktısındaki iç ikili/dylib'lerin hepsi ayrı
   ayrı imzalanmalı; aksi halde Gatekeeper reddeder.

## Değerlendirilen alternatifler
- **Sistem Python'ına güvenmek:** kullanıcıda Python/venv olmayabilir; dağıtım için
  kabul edilemez. Reddedildi.
- **Relocatable Python framework + kaynak gömme (python-build-standalone):** çalışır
  ama her dylib'i imzalamak ve yolları ayarlamak PyInstaller'dan daha zahmetli.
  Reddedildi (PyInstaller daha hazır bir çözüm).
- **Motoru Swift/C#'a yeniden yazmak:** tier mantığı, zeyrek, frekans Python'da;
  yeniden yazım devasa ve [ADR 0001](0001-kademeli-hibrit-mimari.md)'i bozar. Reddedildi.
- **Veri için `sys._MEIPASS` + repo-kökü ikili çözüm:** wheel kurulumda çalışmaz ve
  daha kırılgan; `importlib.resources` tek tutarlı yol. Reddedildi.
