# Turkify — macOS native uygulaması (Faz 6.1)

SwiftUI menü-bar uygulaması. Kısayol/pano/izinleri **native** yapar; metin
düzeltmeyi paylaşımlı Python motoruna (`turkify serve --stdio`) bırakır
(bkz. [ADR 0003](../docs/adr/0003-native-per-os-gui.md), [0004](../docs/adr/0004-motor-sinir-protokolu.md)).

> ⚠️ **Durum: ilk iskelet.** Bu kod henüz derlenip çalıştırılmadı (Xcode sizde).
> Aşağıdaki "Bilinen iterasyon noktaları"na bakın.

## Yapı
```
macos/
├── Package.swift                 # SwiftUI executable, macOS 13+
└── Sources/Turkify/
    ├── TurkifyApp.swift          # @main App + AppDelegate + AppState + menü UI
    ├── EngineClient.swift        # turkify serve köprüsü (stdio JSON)
    ├── Corrector.swift           # kopyala→düzelt→yapıştır + pano
    ├── Permissions.swift         # Accessibility + Input Monitoring
    ├── HotKey.swift              # Carbon global kısayol
    └── AppConfig.swift           # ~/.config/turkify/config.json okur
```

## Ön koşul: Python motoru erişilebilir olmalı
Uygulama motoru `turkify serve --stdio` ile başlatır. Turkify'ın kurulu olduğu
Python'ı bulması gerekir:

- **Venv kullanıyorsanız (önerilen):** Xcode'da scheme → Edit Scheme → Run →
  Arguments → Environment Variables'a şunu ekleyin:
  - `TURKIFY_PYTHON` = `/Users/<siz>/projects/turkify/.venv/bin/python`
- Aksi halde varsayılan `/usr/bin/env python3 -m turkify serve --stdio` denenir
  (turkify, PATH'teki python3'te kurulu olmalı).

Test: terminalde `echo '{"text":"bugun"}' | <python> -m turkify serve --stdio`
bir satır JSON yanıt vermeli.

## Çalıştırma
1. `macos/Package.swift`'i Xcode ile açın (File → Open).
2. Şemada `TURKIFY_PYTHON` env'ini ayarlayın (yukarı).
3. Run (⌘R). Menü-bar'da bir simge belirir (Dock ikonu yok — accessory app).
4. **İzinleri verin:** menüden "Erisilebilirlik" ve "Girdi Izleme" butonlarına
   tıklayın → System Settings açılır → Turkify'a izin verin → "Izinleri yenile".
   - Accessibility: Cmd+C/Cmd+V simülasyonu için.
   - Input Monitoring: global kısayol için gerekebilir.
5. Test: bir yerde metin seçin, menüden **"Secili metni duzelt"** ya da global
   kısayola (config'teki, varsayılan Hyper+A) basın.

## Bilinen iterasyon noktaları (ilk derlemede kontrol)
- **MenuBarExtra + SPM executable:** `@main App` SPM'de çalışır; sorun olursa
  Xcode'da bir **App target** (.xcodeproj) oluşturup kaynakları eklemek gerekebilir.
- **HotKey.swift (Carbon):** en düşük seviye parça. Capture'sız closure'ın C
  fonksiyon işaretçisine dönüşümü ve `GetEventParameter` kullanımı derlemede
  doğrulanmalı.
- **İzin API'leri:** `IOHIDCheckAccess`/`IOHIDRequestAccess` (`import IOKit.hid`),
  `AXIsProcessTrusted` (`import ApplicationServices`).
- **TCC ve imzalama:** geliştirmede izinler "Xcode/binary"ye bağlanır. Düzgün ve
  kalıcı izin/atıf için **imzalı `.app` paketi** gerekir — bu, paketleme fazında
  (Faz 6.4) ele alınacak.
- **Tuş kodları** US-ANSI varsayar (`HotKey.keyCode(for:)`).

## Mimari hatırlatma
- Bu app metni **düzeltmez**; yalnızca seçimi alır, `serve`'e gönderir, sonucu yapıştırır.
- CLI (`turkify`) bundan tamamen bağımsızdır ve her zaman çalışır ([ADR 0006](../docs/adr/0006-cli-birinci-sinif-kalici.md)).
- Düzeltme mantığını değiştirmek için Python motoruna bakın (`src/turkify/`).
