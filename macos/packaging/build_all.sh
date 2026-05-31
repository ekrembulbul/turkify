#!/usr/bin/env bash
# Turkify — macOS dagitim paketini (Turkify-<surum>-macos.zip) TEK ADIMDA uretir.
#
# Sirasiyla:  Release .app derle (xcodebuild; motor Run Script ile gomulur)
#             ->  .app'i ditto ile zip'le
# Cikti:      macos/packaging/dist/Turkify-<surum>-macos.zip
#
# Kullanim (repo kokunden veya herhangi bir yerden):
#   macos/packaging/build_all.sh                 # Release derle + zip'le
#   macos/packaging/build_all.sh --skip-build    # derleme yapma; mevcut Release .app'i zip'le
#   macos/packaging/build_all.sh --app /yol/Turkify.app   # belirtilen .app'i zip'le
#
# On kosul (derleme yapilacaksa): Xcode + donmus motor (macos/packaging/build_engine.sh).
# Imza: Personal Team ile xcodebuild build calisir; sorun olursa Xcode'da ⌘B yapip
#       --skip-build ile bu scripti yalniz zip icin kullan.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PROJECT="$REPO/macos/Turkify/Turkify.xcodeproj"
SCHEME="Turkify"
CONFIG="Release"
ENGINE_DIST="$HERE/dist/turkify-engine/turkify-engine"
DIST="$HERE/dist"

SKIP_BUILD=0
APP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=1 ;;
        --app) shift; APP="${1:-}"; SKIP_BUILD=1 ;;
        -h|--help)
            sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Bilinmeyen secenek: $1" >&2; exit 2 ;;
    esac
    shift
done

# Surumu tek kaynaktan al: pyproject.toml (kok zip adiyla ayni konvansiyon).
VERSION="$(awk -F'"' '/^version[[:space:]]*=/{print $2; exit}' "$REPO/pyproject.toml")"
if [ -z "$VERSION" ]; then
    echo "HATA: pyproject.toml icinde surum bulunamadi." >&2
    exit 1
fi

SECONDS=0

# 1) Release .app derle (istenmediyse atla).
if [ "$SKIP_BUILD" -eq 0 ]; then
    if [ ! -x "$ENGINE_DIST" ]; then
        echo "HATA: Donmus motor yok: $ENGINE_DIST" >&2
        echo "      Once motoru uret: macos/packaging/build_engine.sh" >&2
        echo "      (veya hazir bir .app'i --skip-build / --app ile zip'le)" >&2
        exit 1
    fi
    echo "==> [1/2] Release derleniyor (xcodebuild; motor gomuluyor)..."
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration "$CONFIG" \
        -quiet build
else
    echo "==> [1/2] Derleme atlandi (--skip-build); mevcut .app kullanilacak."
fi

# 2) .app yolunu belirle.
if [ -z "$APP" ]; then
    # DerivedData hash'ini sabit yazma: gercek yolu build ayarlarindan oku.
    SETTINGS="$(xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration "$CONFIG" -showBuildSettings 2>/dev/null)"
    BUILD_DIR="$(printf '%s\n' "$SETTINGS" | awk '/^[[:space:]]*TARGET_BUILD_DIR[[:space:]]*=/{sub(/^[^=]*= /,""); print; exit}')"
    PRODUCT="$(printf '%s\n' "$SETTINGS" | awk '/^[[:space:]]*FULL_PRODUCT_NAME[[:space:]]*=/{sub(/^[^=]*= /,""); print; exit}')"
    APP="$BUILD_DIR/$PRODUCT"
fi

# Goreli yolu mutlaklastir (ditto ve raporlama net olsun).
APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"

if [ ! -d "$APP" ]; then
    echo "HATA: .app bulunamadi: $APP" >&2
    echo "      Xcode'da Release derle (⌘B) veya --app ile yolu ver." >&2
    exit 1
fi

# Motorsuz bir .app dagitilamaz: gomulu motoru dogrula (fail fast).
if [ ! -x "$APP/Contents/Resources/turkify-engine/turkify-engine" ]; then
    echo "HATA: .app icinde gomulu motor yok: $APP" >&2
    echo "      Motoru uret (build_engine.sh) ve Release'i yeniden derle." >&2
    exit 1
fi

# 3) ditto ile zip'le (--keepParent: zip kokunde Turkify.app olur).
ZIP="$DIST/Turkify-$VERSION-macos.zip"
echo "==> [2/2] Paketleniyor: $ZIP"
mkdir -p "$DIST"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

SIZE_MB="$(awk -v b="$(stat -f%z "$ZIP")" 'BEGIN{printf "%.1f", b/1048576}')"
echo ""
echo "==> TAMAM (${SECONDS} sn): $ZIP  (${SIZE_MB} MB)"
echo "    Kaynak .app: $APP"
echo "    Imzasiz + notarize edilmemis olabilir; baska Mac'te Gatekeeper uyarir."
echo "    Notarization icin: macos/packaging/README.md (§3-§5)."
