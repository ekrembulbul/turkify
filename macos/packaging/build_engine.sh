#!/usr/bin/env bash
# Turkify motorunu (turkify-engine) PyInstaller ile bağımsız bir ikiliye dondurur.
# Cikti: macos/packaging/dist/turkify-engine/turkify-engine  (bkz. ADR 0009)
#
# Kullanim:
#   macos/packaging/build_engine.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BUILD_VENV="$HERE/.build-venv"

echo "==> Temiz build venv: $BUILD_VENV"
rm -rf "$BUILD_VENV"
python3 -m venv "$BUILD_VENV"
# shellcheck disable=SC1091
source "$BUILD_VENV/bin/activate"
pip install --upgrade pip wheel >/dev/null

echo "==> Bagimliliklar: turkify + Tier 2 (zeyrek) + pyinstaller"
pip install "$REPO[morphology]" pyinstaller

echo "==> PyInstaller (onedir)"
cd "$HERE"
rm -rf build dist
pyinstaller --clean --noconfirm turkify-engine.spec

ENGINE="$HERE/dist/turkify-engine/turkify-engine"
echo "==> Hizli kontrol"
echo "bugun gorusme yapacagiz" | "$ENGINE" || true

echo ""
echo "==> Tamam: $ENGINE"
echo "    Bu klasoru (.app icine) kopyalama/imzalama icin bkz. packaging/README.md"
