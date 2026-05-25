# Turkify — macOS native uygulaması (Faz 6.1)

SwiftUI menü-bar uygulaması. Kısayol/pano/izinleri **native** yapar; metin
düzeltmeyi paylaşımlı Python motoruna (`turkify serve --stdio`) bırakır
(bkz. [ADR 0003](../docs/adr/0003-native-per-os-gui.md), [0004](../docs/adr/0004-motor-sinir-protokolu.md)).

Proje bir **Xcode App target**'ıdır (imzalı `.app` → TCC izinleri çalışır).

## Yapı
```
macos/Turkify/
├── Turkify.xcodeproj            # Xcode projesi (App target)
├── Turkify-Bridging-Header.h    # bos (proje ayarindaki yolu karsilar)
└── Turkify/
    ├── TurkifyApp.swift          # @main App + AppDelegate + AppState + menü/Ayarlar UI
    ├── EngineClient.swift        # turkify serve köprüsü (stdio JSON, restart)
    ├── Corrector.swift           # kopyala→düzelt→yapıştır + pano
    ├── Permissions.swift         # Accessibility + Input Monitoring
    ├── HotKey.swift              # Carbon global kısayol
    ├── AppSettings.swift         # ayarlar (UserDefaults) + serve bayraklari
    ├── Log.swift                 # stderr teshis logu
    └── Assets.xcassets
```

## Ön koşul: Python motoru erişilebilir olmalı
Uygulama motoru `turkify serve --stdio` ile başlatır. Turkify'ın kurulu olduğu
Python'ı bulması gerekir:

- **Venv (önerilen):** Xcode → şema adı → **Edit Scheme → Run → Arguments →
  Environment Variables**'a ekleyin:
  - `TURKIFY_PYTHON` = `/Users/<siz>/projects/turkify/.venv/bin/python`
- Aksi halde varsayılan `/usr/bin/env python3 -m turkify serve --stdio` denenir.

Hızlı test (terminal): `echo '{"text":"bugun"}' | <python> -m turkify serve --stdio`
bir satır JSON yanıt vermeli.

## Açma ve çalıştırma
1. `macos/Turkify/Turkify.xcodeproj`'u Xcode ile açın.
2. Şemada `TURKIFY_PYTHON` env'ini ayarlayın (yukarı).
3. **Run (⌘R).** Menü-bar'da simge belirir (Dock ikonu yok — accessory app).
   Menü sade: **durum**, **İşlemi iptal et** (işlem sürerken etkin; Hyper+Q),
   **Turkify'ı aç**, **Çıkış**.
4. **Ayarlar…** penceresi:
   - **Ayar düzenleme:** LLM/morfoloji, model, base_url, API anahtarı, timeout,
     assistant_prefill. **Kaydet** → **UserDefaults**'a yazar + motoru yeni
     ayarlarla yeniden başlatır. macOS'ta `config.json` **kullanılmaz**
     ([ADR 0007](../docs/adr/0007-ayar-saklama-gui-native.md)).
   - **İzinler:** "Erisilebilirlik" / "Girdi Izleme" → **Ac** → System Settings →
     izni aç → **Izinleri yenile**.
5. Gerçek kullanım: başka uygulamada metin seçin → global kısayol (varsayılan Hyper+A).
   İşlem uzun sürerse (LLM) **iptal kısayolu** (varsayılan Hyper+Q) ya da menü-bar
   menüsündeki "İşlemi iptal et" ile durdurabilirsiniz.

> Ayarları sıfırlama: `defaults delete com.ekrem.Turkify` (bundle id'nize göre).

## Proje yapılandırması (yeni makinede / sıfırdan kurulumda)
Bu proje şu ayarlarla kurulmuştur; klonlayıp farklı makinede açarken gerekebilir:
- **Signing & Capabilities → Team:** kendi Apple ID'nizi seçin (imzalı kimlik → TCC çalışır).
- **App Sandbox = NO** (Build Settings → `Enable App Sandbox`). ⚠️ **Açık olursa**
  Python alt sürecini ve global tuş/CGEvent'i **engeller** — sandbox kapalı olmalı.
- **Application is agent (UIElement) / `setActivationPolicy(.accessory)`** → menü-bar-only.

## Bilinen iterasyon / dikkat noktaları
- **HotKey.swift (Carbon):** en düşük seviye parça; tuş kodları US-ANSI varsayar.
- **İzin API'leri:** `IOHIDCheckAccess`/`IOHIDRequestAccess`, `AXIsProcessTrusted`.
- **Kısayol kaydedici** henüz yok (varsayılan: düzeltme Hyper+A, iptal Hyper+Q) — ROADMAP 7.4.
- **İmzalama/notarization & dağıtım:** Faz 6.4 (paketleme).

## Mimari hatırlatma
- Bu app metni **düzeltmez**; seçimi alır, `serve`'e gönderir, sonucu yapıştırır.
- CLI (`turkify`) bundan tamamen bağımsızdır ve her zaman çalışır ([ADR 0006](../docs/adr/0006-cli-birinci-sinif-kalici.md)).
- Düzeltme mantığı Python motorunda (`src/turkify/`).
