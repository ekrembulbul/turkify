#!/usr/bin/env bash
# Turkify surum numarasini TUM dagitim noktalarinda tek adimda gunceller.
# Tek kaynak: bu script. Elle 4 ayri dosyayi degistirme hatasini onler.
#
# Guncellenen dosyalar:
#   pyproject.toml                                  version = "X.Y.Z"
#   macos/.../project.pbxproj                       MARKETING_VERSION = X.Y.Z;  (Debug + Release)
#   windows/Turkify/Turkify.csproj                  <Version>X.Y.Z</Version>
#   windows/packaging/turkify.iss                   #define AppVersion "X.Y.Z"
#
# Kullanim:  scripts/set_version.sh 1.3.0
set -euo pipefail

VERSION="${1:-}"
# Bastaki olasi "v" onekini at (v1.3.0 -> 1.3.0), sonra semver dogrula.
VERSION="${VERSION#v}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "HATA: Gecerli bir surum ver (ornek: 1.3.0). Alinan: '${1:-}'" >&2
    exit 2
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Bir dosyada perl ile yerinde degisiklik yapar (macOS + Linux'ta tasinabilir).
# Eslesme bulunmazsa hata verir (sessiz "guncellendi ama degismedi" durumunu yakalar).
bump() {
    local file="$1" pattern="$2"
    if [[ ! -f "$file" ]]; then
        echo "HATA: dosya yok: $file" >&2
        exit 1
    fi
    if ! grep -qE "$3" "$file"; then
        echo "HATA: surum kalibi bulunamadi: ${file#"$REPO"/}" >&2
        exit 1
    fi
    perl -i -pe "$pattern" "$file"
    echo "  guncellendi: ${file#"$REPO"/}"
}

echo "==> Surum -> $VERSION"
bump "$REPO/pyproject.toml" \
    "s/^version = \"[^\"]*\"/version = \"$VERSION\"/" \
    '^version = "[^"]*"'
bump "$REPO/macos/Turkify/Turkify.xcodeproj/project.pbxproj" \
    "s/MARKETING_VERSION = [^;]*;/MARKETING_VERSION = $VERSION;/" \
    'MARKETING_VERSION = [^;]*;'
bump "$REPO/windows/Turkify/Turkify.csproj" \
    "s|<Version>[^<]*</Version>|<Version>$VERSION</Version>|" \
    '<Version>[^<]*</Version>'
bump "$REPO/windows/packaging/turkify.iss" \
    "s/#define AppVersion \"[^\"]*\"/#define AppVersion \"$VERSION\"/" \
    '#define AppVersion "[^"]*"'
echo "==> Tamam: tum dosyalar $VERSION."
