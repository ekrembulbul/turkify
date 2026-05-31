# macOS Paketleme

Turkify motorunu (Python) **donmuş bağımsız bir ikiliye** çevirip `.app` içine
gömeriz; kullanıcı Python/venv kurmaz. Dağıtım **Developer ID + notarization**
iledir (App Store dışı). Karar: [ADR 0009](../../docs/adr/0009-paketleme-frozen-motor.md).

```
PyInstaller (motor → turkify-engine)  →  .app Resources'a kopyala
   →  codesign (Developer ID + hardened)  →  notarize  →  staple  →  DMG
```

## Bu klasördeki dosyalar
| Dosya | Ne |
|---|---|
| `turkify_engine.py` | PyInstaller giriş noktası (`turkify` CLI `main()`'i çağırır) |
| `turkify-engine.spec` | PyInstaller yapılandırması (onedir; turkify + zeyrek verisi gömülü) |
| `build_engine.sh` | Temiz venv'de motoru dondurur → `dist/turkify-engine/` |
| `build_all.sh` | Release `.app`'i derler + `dist/Turkify-<surum>-macos.zip` uretir |

`build/`, `dist/`, `.build-venv/` git'te yok sayılır.

---

## Şimdilik: ücretsiz (geliştirme imzası) ile yerel kullanım

Ücretli Apple Developer hesabı olmadan da uygulamayı **kendi Mac'inde** çalıştırabilirsin
(gerçek dağıtım/notarization sonraya). Adımlar:

1. **Motoru dondur:** `macos/packaging/build_engine.sh` (bkz. §1).
2. **Xcode imza:** Signing & Capabilities → **Automatically manage signing** açık,
   **Team** olarak kendi (ücretsiz) Apple ID / Personal Team. Developer ID gerekmez.
3. **Derle (Distribute KULLANMA):** Personal Team, **Distribute App** akışını
   yapamaz ("not enrolled in the Apple Developer Program" hatası verir). Bunun
   yerine **Product → Build** (⌘B) → **Product → Show Build Folder in Finder** →
   `Products/Debug/` (veya `Release/`) içindeki **`Turkify.app`**.
4. **Çalıştır:** `Turkify.app`'i **Finder'dan çift tıkla.**
   - ⚠️ Xcode'dan **⌘R ile açma**: scheme'de `TURKIFY_PYTHON` env'i ayarlı olduğundan
     ⌘R venv'i kullanır, gömülü motoru test etmez. Finder'dan açınca o env olmadığı
     için **gömülü motor** devreye girer (gerçek paketi test edersin).
5. Menü-bar'da Turkify görünür → **Erişilebilirlik** iznini ver → kullan. Motor
   gömülüdür; Python/venv kurman **gerekmez**.

> Yerelde derlenen `.app` karantinalı olmadığından `xattr` gerekmez; doğrudan açılır.
> Sadece `.app`'i **başka bir Mac'e taşırsan/indirisen** Gatekeeper devreye girer
> (`xattr -dr com.apple.quarantine Turkify.app`) — ve imzasız + gömülü motor yüzünden
> çoğu zaman "hasarlı" der. "İndir-çalıştır" dağıtımı için ücretli **Developer ID +
> notarization** şart (§3–§6).

---

## 1. Motoru dondur (her sürümde)
```bash
macos/packaging/build_engine.sh
```
Çıktı: `macos/packaging/dist/turkify-engine/turkify-engine` (+ yanında kütüphaneler).
Hızlı test: `echo "bugun gorusme" | macos/packaging/dist/turkify-engine/turkify-engine`

## 2. `.app` içine gömme (Xcode — tek seferlik kurulum)
Xcode'da **Turkify hedefi → Build Phases**'e bir **Run Script** fazı ekle (en sona,
"Embed"/"Copy" fazlarından sonra) ve şunu yapıştır:

```sh
# Donmuş motoru .app/Contents/Resources/turkify-engine/ içine kopyala
SRC="$SRCROOT/../packaging/dist/turkify-engine"
DST="$TARGET_BUILD_DIR/$CONTENTS_FOLDER_PATH/Resources/turkify-engine"
if [ -d "$SRC" ]; then
  rm -rf "$DST"
  mkdir -p "$DST"
  cp -R "$SRC/" "$DST/"
fi
```
> `$SRCROOT` Xcode projesinin (`macos/Turkify`) köküdür; `../packaging` bu klasördür.
> Bu faz Run Script olduğundan derlemeye dahildir; önce `build_engine.sh`'i çalıştırmış olmalısın.
>
> ⚠️ **User Script Sandboxing:** Bu betik app bundle'ına yazdığından, Xcode 15+'in
> **User Script Sandboxing** ayarı açıkken `Sandbox: mkdir/cp deny` hatası alırsın.
> Build Settings → **User Script Sandboxing → No** yap. (Bu, App Sandbox'tan ayrıdır;
> yalnızca build betiği kum havuzudur.)

Geliştirmede (scheme'de `TURKIFY_PYTHON` ayarlıysa) uygulama yine venv'i kullanır;
gömülü ikili yalnızca o env yokken (release) devreye girer — `AppSettings.engineExecutable()`.

## 3. Kod imzalama (senin Developer ID'nle)
`.app` derlendikten sonra gömülü ikili + tüm `.dylib`'ler **derinlemesine** imzalanmalı,
**hardened runtime** açık olmalı:
```bash
APP="/path/to/Turkify.app"
IDENTITY="Developer ID Application: ADIN (TEAMID)"
codesign --force --options runtime --timestamp --deep \
  --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
```
> En sağlamı: Xcode'da **Signing & Capabilities → Team** seçili + **Hardened Runtime**
> açık olarak **Product → Archive** yapmak; arşiv tüm gömülü içeriği imzalar.
> App Sandbox **kapalı** kalır (Erişilebilirlik + CGEvent gerekli).

## 4. Notarization + staple (Apple ID gerekir)
```bash
# Bir kez: app-specific password'u sakla
xcrun notarytool store-credentials turkify-notary \
  --apple-id "ekrem@ornek.com" --team-id "TEAMID" --password "uygulamaya-ozel-sifre"

# .app'i zip'le ve gönder
ditto -c -k --keepParent "Turkify.app" "Turkify.zip"
xcrun notarytool submit "Turkify.zip" --keychain-profile turkify-notary --wait

# Onaylanınca damgala
xcrun stapler staple "Turkify.app"
```

## 5. DMG (dağıtım)
```bash
hdiutil create -volname Turkify -srcfolder "Turkify.app" -ov -format UDZO Turkify.dmg
# (istege bagli) DMG'yi de notarize + staple et
```

---

## Notlar / kararlar
- **Tier 2 (zeyrek)** spec'te `collect_all("zeyrek")` ile dahil edilir (build venv'inde
  kurulu olduğu için). İstenmezse `build_engine.sh`'te `[morphology]` çıkarılır ve
  uygulama Tier 1 + Tier 3 ile çıkar.
- **Tier 3 LLM gömülmez** — kullanıcının kendi yerel sunucusu (`base_url`).
- **Universal2:** Hem Apple Silicon hem Intel için tek ikili istenirse spec'te
  `target_arch="universal2"` + universal Python gerekir.
- **App Store:** Erişilebilirlik/CGEvent nedeniyle hedeflenmiyor (Developer ID yolu).
