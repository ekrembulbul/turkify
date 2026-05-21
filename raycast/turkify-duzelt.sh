#!/bin/bash
# Turkify — Raycast script command (Faz 6, minimal frontend)
# Panodaki (clipboard) ASCII Türkçe metni şapkalı doğru hâline çevirir.
# Kullanım: önce metni kopyala (Cmd+C), sonra bu komutu çalıştır; sonuç panoya yazılır.
#
# Kurulum: Raycast → Extensions → Script Commands → bu klasörü ekle.
#
# @raycast.schemaVersion 1
# @raycast.title Türkçe Düzelt (pano)
# @raycast.mode silent
# @raycast.packageName Turkify
# @raycast.icon 🇹🇷
# @raycast.description Panodaki ASCII Türkçe metni doğru diakritiklerle düzeltir.

PYTHON="$HOME/projects/turkify/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "Turkify venv bulunamadı: $PYTHON"
  exit 1
fi

corrected="$(pbpaste | "$PYTHON" -m turkify)"
printf '%s' "$corrected" | pbcopy
echo "Düzeltildi ve panoya kopyalandı."
