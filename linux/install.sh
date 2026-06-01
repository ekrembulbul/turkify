#!/usr/bin/env bash
# Turkify Linux servisini (systemd --user) kurar: doğru Python yolunu çözer, unit'i
# yazar, servisi etkinleştirip başlatır ve kısayol/yapıştırma talimatını basar.
#
# Önkoşul: turkify paketi kurulu olmalı (repo kökünde):
#   python3 -m venv .venv && .venv/bin/python -m pip install -e ".[morphology]"
#
# Kullanım:  linux/install.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # linux
repo="$(cd "$here/.." && pwd)"                          # repo kökü

# 1) Python yorumlayıcısını çöz: önce repo venv, sonra PATH.
if [[ -x "$repo/.venv/bin/python" ]]; then
  py="$repo/.venv/bin/python"
else
  py="$(command -v python3 || true)"
fi
[[ -n "$py" ]] || { echo "HATA: python3 bulunamadı." >&2; exit 1; }

# 2) turkify importlanabiliyor mu? (servis 'python -m turkify serve' çalıştıracak)
if ! "$py" -c "import turkify" 2>/dev/null; then
  echo "HATA: '$py' ile 'turkify' import edilemiyor." >&2
  echo "Önce kurun:  $py -m pip install -e \"$repo[morphology]\"" >&2
  exit 1
fi

# 3) Başlangıç dosyalarını oluştur (varsa ASLA üzerine yazma). Yollar, motorun
#    okuduğu yerle birebir aynı olsun diye turkify.config'ten çözülür.
cfg_json="$("$py" -c 'from turkify import config; print(config.config_path())')"
prot_txt="$("$py" -c 'from turkify import config; print(config.protected_words_path())')"
mkdir -p "$(dirname "$cfg_json")"

if [[ -f "$cfg_json" ]]; then
  echo "==> config.json mevcut, korundu: $cfg_json"
else
  cp "$repo/config/config.example.json" "$cfg_json"
  echo "==> config.json oluşturuldu (örnek varsayılanlardan): $cfg_json"
fi

# protected_words.txt: ADR 0008 gereği örnek kelimeler OTOMATİK kopyalanmaz;
# yalnızca yorumlu boş şablon yazılır (kullanıcı kendi terimlerini ekler).
if [[ -f "$prot_txt" ]]; then
  echo "==> protected_words.txt mevcut, korundu: $prot_txt"
else
  cat > "$prot_txt" <<'PROT'
# Turkify korumalı kelimeler — bu dosyadaki kelimelere diakritik dönüşümü UYGULANMAZ.
# Her satıra bir kelime/terim. '#' ile başlayan ve boş satırlar yok sayılır.
# Karşılaştırma büyük/küçük harf duyarsızdır (Türkçe locale).
#
# Yalnızca Türkçe şapkalı karşılığı OLMAYAN yabancı/teknik terimler ekleyin
# (ör. server, framework). Türkçeleşmiş kelimeleri (monitör, doküman) EKLEMEYİN.
# Hazır geniş başlangıç listesi: config/protected_words.example.txt (ADR 0008
# gereği otomatik yüklenmez; istersen içeriğini buraya kopyalayabilirsin).

# Örnek (yorumu kaldırıp kullanın):
# OpenAI
# Github
PROT
  echo "==> protected_words.txt oluşturuldu (yorumlu boş şablon): $prot_txt"
fi

# 4) systemd --user unit'ini yaz.
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
unit="$unit_dir/turkify.service"
cat > "$unit" <<EOF
[Unit]
Description=Turkify düzeltme motoru (sıcak servis)
Documentation=https://github.com/ekrembulbul/turkify

[Service]
Type=simple
RuntimeDirectory=turkify
ExecStart=$py -m turkify serve --socket %t/turkify/engine.sock --verbose
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
echo "==> Unit yazıldı: $unit"

# 4b) Otomatik reload: config dosyaları değişince motora {"cmd":"reload"} gönderen
#     path + oneshot servis (Faz 6.3b). Yollar motorun okuduğu config dizininden çözülür.
cfg_dir="$(dirname "$cfg_json")"
cat > "$unit_dir/turkify-reload.service" <<EOF
[Unit]
Description=Turkify ayarlarini yeniden yukle

[Service]
Type=oneshot
ExecStart=$repo/linux/bin/turkify-fix --reload
EOF
cat > "$unit_dir/turkify-reload.path" <<EOF
[Unit]
Description=Turkify ayar dosyalarini izle (degisince reload)

[Path]
PathChanged=$cfg_json
PathChanged=$prot_txt
PathChanged=$cfg_dir
Unit=turkify-reload.service

[Install]
WantedBy=default.target
EOF
echo "==> Reload izleyici yazıldı: $unit_dir/turkify-reload.path"

# 5) Servisi + reload izleyiciyi etkinleştir + (yeniden) başlat. restart kullanılır
#    ki re-install'da güncellenen unit çalışan sürece de uygulansın (enable --now
#    zaten çalışan servisi yeniden başlatmaz).
systemctl --user daemon-reload
systemctl --user enable turkify.service turkify-reload.path
systemctl --user restart turkify.service turkify-reload.path
echo "==> Servis durumu:"
systemctl --user --no-pager --lines=0 status turkify.service || true

# 6) Kullanım talimatı.
cat <<EOF

==> Kısayol kurulumu (GNOME → Ayarlar → Klavye → Özel Kısayollar → +):
      Ad     : Turkify düzelt
      Komut  : $repo/linux/bin/turkify-fix
      Kısayol: tercihin (ör. Ctrl+Alt+T)
    (KDE: Sistem Ayarları → Kısayollar → Özel Kısayollar.)

==> Kullanım: metni vurgula → kısayola bas. Düzeltilmiş metin panoya yazılır.
    ydotool kuruluysa otomatik yapıştırılır; değilse Ctrl+V ile yapıştır.

==> (Opsiyonel) otomatik yapıştırma için ydotool:
      sudo apt install ydotool          # veya dağıtımının paketi
      sudo usermod -aG input "\$USER"    # /dev/uinput erişimi (zorunlu adım)
      # --- oturumu kapatıp açın (grup üyeliği yeni oturumda geçerli olur) ---
      systemctl --user enable --now ydotool.service
    Detay/sorun giderme: linux/README.md → "Otomatik yapıştırma (ydotool)".
    Not: Flatpak sandbox uinput'a erişemez → ydotool Flatpak'te çalışmaz (ADR 0005).

==> Config değişince motor OTOMATİK tazelenir (turkify-reload.path izliyor).
    Elle tazeleme gerekirse:  systemctl --user restart turkify.service
EOF
