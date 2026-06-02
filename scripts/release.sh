#!/usr/bin/env bash
# Turkify surum yayinla — TEK KOMUT.
# Surum numaralarini gunceller, commit'ler, "v<surum>" tag'i atar ve push'lar.
# Tag push'u GitHub Actions "Release" workflow'unu tetikler (macOS DMG + Windows
# EXE derler ve GitHub Release'i olusturur).
#
# Kullanim (repo kokunde, main branch'inde, calisma agaci temizken):
#   scripts/release.sh 1.3.0
#
# On kosul: CHANGELOG.md icine "## [1.3.0] - TARIH" bolumunu ONCEDEN yazmis ol.
set -euo pipefail

VERSION="${1:-}"
VERSION="${VERSION#v}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "HATA: Gecerli bir surum ver (ornek: 1.3.0). Alinan: '${1:-}'" >&2
    exit 2
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
TAG="v$VERSION"

# --- Guvenlik kontrolleri (fail fast) ---
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
    echo "HATA: 'main' branch'inde degilsin (su an: $BRANCH)." >&2
    echo "      Once: git checkout main && git pull" >&2
    exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
    echo "HATA: Calisma agacin temiz degil. Once degisiklikleri commit'le veya temizle." >&2
    echo "      (CHANGELOG.md degisikligini de bu komuttan ONCE commit'lemis ol.)" >&2
    exit 1
fi
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "HATA: Tag zaten var: $TAG (bu surum daha once cikmis)." >&2
    exit 1
fi
if ! grep -qE "^## \[$VERSION\]" CHANGELOG.md; then
    echo "HATA: CHANGELOG.md icinde '## [$VERSION]' bolumu yok." >&2
    echo "      Once surum notlarini yaz ve commit'le, sonra bu komutu calistir." >&2
    exit 1
fi

echo "==> Surum dosyalari guncelleniyor ($VERSION)..."
scripts/set_version.sh "$VERSION"

echo "==> Commit + tag + push..."
git add -A
# Surum dosyalari zaten istenen surumdeyse (or. basarisiz bir yayini yeniden deneme)
# yeni commit'e gerek yok; dogrudan tag'lenir.
if git diff --cached --quiet; then
    echo "    (surum dosyalari zaten $VERSION — commit atlandi)"
else
    git commit -m "build: surum $VERSION"
fi
git tag -a "$TAG" -m "Turkify $VERSION"
git push origin main
git push origin "$TAG"

echo ""
echo "==> Tamam. '$TAG' push'landi → GitHub Actions 'Release' workflow'u tetiklendi."
echo "    Ilerlemeyi izle: repo → Actions sekmesi."
