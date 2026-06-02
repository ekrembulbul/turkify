#!/usr/bin/env bash
# Turkify — macOS dagitim DMG'sini (imzali + notarize + staple) TEK ADIMDA uretir.
#
# Sirasiyla:
#   1) motoru dondur (PyInstaller)
#   2) Release .app derle (imzasiz; motor Run Script ile .app icine gomulur)
#   3) Developer ID ile imzala (icten-disa; hardened runtime)
#   4) .app'i notarize et + staple'la
#   5) DMG uret (icinde Applications kisayolu — surukle-birak kurulum)
#   6) DMG'yi de notarize et + staple'la (indirme sonrasi cevrimdisi Gatekeeper icin)
# Cikti: macos/packaging/dist/Turkify-<surum>.dmg
#
# Gerekli ortam degiskenleri (CI'da GitHub Secrets'tan gelir; yerelde elle ayarla):
#   MACOS_SIGN_IDENTITY   "Developer ID Application: Ad Soyad (TEAMID)" — keychain'de kurulu olmali
#   APPLE_API_KEY_PATH    App Store Connect API anahtari (.p8) dosya yolu
#   APPLE_API_KEY_ID      Anahtarin Key ID'si
#   APPLE_API_ISSUER_ID   Issuer ID
#
# Secenekler (yerel hizli yineleme icin):
#   --skip-engine    Motoru yeniden dondurme; mevcut donmus motoru kullan
#   --skip-build     Derleme yapma; mevcut Release .app'i imzala/paketle
#   --no-notarize    Yalnizca imzala + DMG (notarize ATLA — yerel test; dagitilamaz)
#
# On kosul: Xcode + Python 3 (motor icin; build venv kendi olusur).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PROJECT="$REPO/macos/Turkify/Turkify.xcodeproj"
SCHEME="Turkify"
CONFIG="Release"
ENGINE_DIST="$HERE/dist/turkify-engine/turkify-engine"
DIST="$HERE/dist"

SKIP_BUILD=0
SKIP_ENGINE=0
NOTARIZE=1

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=1 ;;
        --skip-engine) SKIP_ENGINE=1 ;;
        --no-notarize) NOTARIZE=0 ;;
        -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Bilinmeyen secenek: $1" >&2; exit 2 ;;
    esac
    shift
done

# --- Gerekli ayarlari erken dogrula (fail fast) ---
: "${MACOS_SIGN_IDENTITY:?MACOS_SIGN_IDENTITY ayarli olmali (Developer ID Application: ...)}"
if [ "$NOTARIZE" -eq 1 ]; then
    : "${APPLE_API_KEY_PATH:?APPLE_API_KEY_PATH ayarli olmali (.p8 yolu) — ya da --no-notarize}"
    : "${APPLE_API_KEY_ID:?APPLE_API_KEY_ID ayarli olmali}"
    : "${APPLE_API_ISSUER_ID:?APPLE_API_ISSUER_ID ayarli olmali}"
fi

VERSION="$(awk -F'"' '/^version[[:space:]]*=/{print $2; exit}' "$REPO/pyproject.toml")"
if [ -z "$VERSION" ]; then
    echo "HATA: pyproject.toml icinde surum bulunamadi." >&2
    exit 1
fi

SECONDS=0

# Notarize: artifact'i Apple notary servisine gonderir ve onayi BEKLER — kendi
# yoklama dongusuyle (canli ilerleme + sert zaman asimi). notarytool --wait bazen
# (notary servisi gecikince) saatlerce takilabildiginden, burada gonderim sonrasi
# her 30 sn'de bir durum sorgulanir ve NOTARY_TIMEOUT_SECONDS (varsayilan 30 dk)
# sonunda pes edilir. "Invalid"de Apple'in detay logu basilir (hangi ikili reddedildi).
notarize() {
    local artifact="$1" submit_json id status elapsed=0
    local interval=30 max="${NOTARY_TIMEOUT_SECONDS:-1800}"

    echo "==> Notarize gonderiliyor: $artifact"
    submit_json="$(xcrun notarytool submit "$artifact" \
        --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" \
        --output-format json)" || { echo "HATA: notarytool submit basarisiz." >&2; return 1; }
    id="$(printf '%s' "$submit_json" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))' 2>/dev/null || true)"
    if [ -z "$id" ]; then
        echo "HATA: Gonderim ID alinamadi. Yanit: $submit_json" >&2
        return 1
    fi
    echo "    Gonderim ID: $id — onay bekleniyor (en fazla $((max / 60)) dk)..."

    while :; do
        status="$(xcrun notarytool info "$id" \
            --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" \
            --output-format json 2>/dev/null \
            | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || true)"
        echo "    [${elapsed} sn] durum: ${status:-(sorgulanamadi)}"
        case "$status" in
            Accepted) break ;;
            Invalid | Rejected)
                echo "HATA: Notarization $status (ID: $id). Apple detay logu:" >&2
                xcrun notarytool log "$id" \
                    --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" >&2 || true
                return 1 ;;
        esac
        if [ "$elapsed" -ge "$max" ]; then
            echo "HATA: Notarization zaman asimi ($((max / 60)) dk; ID: $id, son durum: ${status:-bilinmiyor})." >&2
            echo "      Apple notary servisi gecikmis olabilir (developer.apple.com/system-status)." >&2
            echo "      Servis duzelince is'i yeniden calistirin (Re-run) veya tekrar tag atin." >&2
            return 1
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    echo "    Notarization: Accepted (ID: $id)"
}

# --- 1) Motoru dondur ---
if [ "$SKIP_BUILD" -eq 1 ]; then
    echo "==> [1/6] Motor + derleme atlandi (--skip-build); mevcut .app imzalanacak."
elif [ "$SKIP_ENGINE" -eq 1 ]; then
    echo "==> [1/6] Motor dondurma atlandi (--skip-engine)."
    [ -x "$ENGINE_DIST" ] || { echo "HATA: Donmus motor yok: $ENGINE_DIST" >&2; exit 1; }
else
    echo "==> [1/6] Motor donduruluyor (PyInstaller)..."
    "$HERE/build_engine.sh"
fi

# --- 2) Release .app derle (IMZASIZ; imzayi biz atacagiz) ---
# CODE_SIGNING_ALLOWED=NO: xcodebuild imza/hesap gerektirmesin; .app'i sonra
# Developer ID ile kendimiz imzalariz (CI'da Apple ID oturumu olmadan calisir).
if [ "$SKIP_BUILD" -eq 0 ]; then
    echo "==> [2/6] Release derleniyor (xcodebuild; imzasiz, motor gomuluyor)..."
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration "$CONFIG" \
        CODE_SIGNING_ALLOWED=NO -quiet build
fi

# .app yolunu build ayarlarindan oku (DerivedData hash'ini sabit yazma).
SETTINGS="$(xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration "$CONFIG" -showBuildSettings 2>/dev/null)"
BUILD_DIR="$(printf '%s\n' "$SETTINGS" | awk '/^[[:space:]]*TARGET_BUILD_DIR[[:space:]]*=/{sub(/^[^=]*= /,""); print; exit}')"
PRODUCT="$(printf '%s\n' "$SETTINGS" | awk '/^[[:space:]]*FULL_PRODUCT_NAME[[:space:]]*=/{sub(/^[^=]*= /,""); print; exit}')"
APP="$BUILD_DIR/$PRODUCT"

[ -d "$APP" ] || { echo "HATA: .app bulunamadi: $APP" >&2; exit 1; }
ENGINE_IN_APP="$APP/Contents/Resources/turkify-engine/turkify-engine"
[ -x "$ENGINE_IN_APP" ] || { echo "HATA: .app icinde gomulu motor yok: $ENGINE_IN_APP" >&2; exit 1; }

# --- 3) Imzala (icten-disa: once gomulu motorun kutuphaneleri, sonra exe, sonra .app) ---
# Notarization, TUM ic Mach-O ikililerinin ayni Developer ID ile + hardened runtime
# ile imzali olmasini ister. PyInstaller motoru cok sayida .dylib/.so icerir.
echo "==> [3/6] Imzalaniyor: $MACOS_SIGN_IDENTITY"
ENGINE_DIR="$APP/Contents/Resources/turkify-engine"
# Gomulu motordaki TUM Mach-O ikililerini (uzanti farketmeksizin) icten-disa imzala.
# Onemli: codesign --deep, Resources/ altindaki gevsek Mach-O dosyalarini imzalamaz;
# ayrica PyInstaller uzantisiz Mach-O da uretir (or. _internal/Python.framework/.../
# Python). Bunlari 'file' ile tespit edip tek tek imzalamazsak notarization
# "hardened runtime yok / imzasiz" diye REDDEDER. (Symlink'leri -type f eler.)
while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q 'Mach-O'; then
        codesign --force --options runtime --timestamp --sign "$MACOS_SIGN_IDENTITY" "$f"
    fi
done < <(find "$ENGINE_DIR" -type f -print0)
# Tum .app: ana ikili + muhur. --deep son guvenlik agi (ic ikililer yukarida imzalandi).
codesign --force --options runtime --timestamp --deep --sign "$MACOS_SIGN_IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$DIST"

# --- 4) .app'i notarize + staple ---
if [ "$NOTARIZE" -eq 1 ]; then
    APP_ZIP="$DIST/Turkify-$VERSION-app.zip"
    rm -f "$APP_ZIP"
    ditto -c -k --keepParent "$APP" "$APP_ZIP"
    echo "==> [4/6] .app notarize ediliyor..."
    notarize "$APP_ZIP"
    xcrun stapler staple "$APP"
    rm -f "$APP_ZIP"
else
    echo "==> [4/6] Notarize atlandi (--no-notarize)."
fi

# --- 5) DMG uret (icinde Applications kisayolu — surukle-birak kurulum) ---
echo "==> [5/6] DMG hazirlaniyor..."
DMG="$DIST/Turkify-$VERSION.dmg"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Turkify" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null

# --- 6) DMG'yi imzala + notarize + staple ---
codesign --force --timestamp --sign "$MACOS_SIGN_IDENTITY" "$DMG"
if [ "$NOTARIZE" -eq 1 ]; then
    echo "==> [6/6] DMG notarize ediliyor..."
    notarize "$DMG"
    xcrun stapler staple "$DMG"
else
    echo "==> [6/6] DMG notarize atlandi (--no-notarize)."
fi

SIZE_MB="$(awk -v b="$(stat -f%z "$DMG")" 'BEGIN{printf "%.1f", b/1048576}')"
echo ""
echo "==> TAMAM (${SECONDS} sn): $DMG  (${SIZE_MB} MB)"
[ "$NOTARIZE" -eq 1 ] && echo "    Imzali + notarize + staple — indir-ac dagitimina hazir." \
                      || echo "    UYARI: notarize EDILMEDI; yalnizca yerel test icindir."
