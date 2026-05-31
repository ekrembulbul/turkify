#!/usr/bin/env bash
# Turkify — macOS dagitim paketini (Turkify-<surum>.zip) TEK ADIMDA uretir.
#
# Sirasiyla:  motoru dondur (PyInstaller)  ->  Release .app derle (xcodebuild;
#             motor Run Script ile .app icine gomulur)  ->  .app'i ditto ile zip'le
# Cikti:      macos/packaging/dist/Turkify-<surum>.zip
#
# Kullanim (repo kokunden veya herhangi bir yerden):
#   macos/packaging/build_all.sh                # motor dondur + Release derle + zip'le
#   macos/packaging/build_all.sh --skip-engine  # motoru yeniden dondurme; mevcut motorla derle
#   macos/packaging/build_all.sh --skip-build   # derleme yapma; mevcut Release .app'i zip'le
#   macos/packaging/build_all.sh --app YOL/Turkify.app   # belirtilen .app'i zip'le
#
# On kosul: Xcode + Python 3 (motoru dondurmek icin; build venv kendi olusturulur).
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
SKIP_ENGINE=0
APP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=1 ;;
        --skip-engine) SKIP_ENGINE=1 ;;
        --app) shift; APP="${1:-}"; SKIP_BUILD=1 ;;
        -h|--help)
            sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Bilinmeyen secenek: $1" >&2; exit 2 ;;
    esac
    shift
done

# Surumu tek kaynaktan al: pyproject.toml (zip adiyla ayni konvansiyon).
VERSION="$(awk -F'"' '/^version[[:space:]]*=/{print $2; exit}' "$REPO/pyproject.toml")"
if [ -z "$VERSION" ]; then
    echo "HATA: pyproject.toml icinde surum bulunamadi." >&2
    exit 1
fi

SECONDS=0

# 1) Motoru dondur (PyInstaller). Derleme yapilacaksa motor VARSAYILAN olarak
#    her zaman tazelenir; boylece kaynaktaki en guncel motor .app'e gomulur
#    (eski/eksik motorun sessizce dagitilmasini onler). --skip-engine ile atlanip
#    mevcut donmus motor kullanilir. --skip-build / --app, .app'i yeniden
#    derlemedigi icin motor dondurmak anlamsizdir (donmus motor .app'e girmez).
if [ "$SKIP_BUILD" -eq 1 ]; then
    echo "==> [1/3] Motor + derleme atlandi (--skip-build/--app); mevcut .app zip'lenecek."
elif [ "$SKIP_ENGINE" -eq 1 ]; then
    echo "==> [1/3] Motor dondurma atlandi (--skip-engine); mevcut donmus motor kullanilacak."
    if [ ! -x "$ENGINE_DIST" ]; then
        echo "HATA: Donmus motor yok: $ENGINE_DIST" >&2
        echo "      --skip-engine'siz calistirip motoru bir kez uret." >&2
        exit 1
    fi
else
    echo "==> [1/3] Motor donduruluyor (PyInstaller)..."
    "$HERE/build_engine.sh"
fi

# 2) Release .app derle (istenmediyse atla). Xcode Run Script fazi, yukarida
#    uretilen dist/turkify-engine'i .app/Contents/Resources icine kopyalar.
if [ "$SKIP_BUILD" -eq 0 ]; then
    echo "==> [2/3] Release derleniyor (xcodebuild; motor gomuluyor)..."
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration "$CONFIG" \
        -quiet build
fi

# .app yolunu belirle.
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
ZIP="$DIST/Turkify-$VERSION.zip"
echo "==> [3/3] Paketleniyor: $ZIP"
mkdir -p "$DIST"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

SIZE_MB="$(awk -v b="$(stat -f%z "$ZIP")" 'BEGIN{printf "%.1f", b/1048576}')"
echo ""
echo "==> TAMAM (${SECONDS} sn): $ZIP  (${SIZE_MB} MB)"
echo "    Kaynak .app: $APP"
echo "    Imzasiz + notarize edilmemis olabilir; baska Mac'te Gatekeeper uyarir."
echo "    Notarization icin: macos/packaging/README.md (§3-§5)."
