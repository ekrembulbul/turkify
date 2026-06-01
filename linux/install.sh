#!/usr/bin/env bash
# Turkify Linux bootstrap — temiz bir klondan TEK KOMUTLA kurulum (kişisel/few-machines).
#
#   linux/install.sh
#
# Yaptıkları (hepsi idempotent; gerekmiyorsa atlar, kurulu makinede no-op):
#   1) .venv oluştur + paketi kur (morphology dahil)
#   2) eksik sistem araçlarını apt ile kur: clipboard (wl-clipboard/xclip),
#      libnotify-bin, ydotool                                          [sudo]
#   3) ydotool: 'input' grubuna ekle + servisini aç  [sudo; grup için relogin gerekir]
#   4) config.json + protected_words.txt başlangıç dosyaları (varsa DOKUNMAZ)
#   5) systemd --user unit'leri (sıcak motor + otomatik reload) + enable/restart
#   6) GNOME kısayolunu gsettings ile bağla (varsa DOKUNMAZ)
#
# Seçenekler:
#   --shortcut '<Control><Super><Alt>a'  GNOME kısayolu (varsayılan bu; TURKIFY_SHORTCUT env de geçer)
#   --paste-delay-ms N                   kısayol komutuna TURKIFY_PASTE_DELAY_MS=N gömer (otomatik
#                                        yapıştırma ıskalıyorsa artır; varsayılan: gömme, kod 250 ms)
#   --no-shortcut                        kısayolu bağlama, yalnızca talimat yaz
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # linux/
repo="$(cd "$here/.." && pwd)"                          # repo kökü

SHORTCUT="${TURKIFY_SHORTCUT:-<Control><Super><Alt>a}"
PASTE_DELAY_MS=""
BIND_SHORTCUT=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shortcut) SHORTCUT="${2:?--shortcut bir deger ister}"; shift 2 ;;
    --paste-delay-ms) PASTE_DELAY_MS="${2:?--paste-delay-ms bir deger ister}"; shift 2 ;;
    --no-shortcut) BIND_SHORTCUT=0; shift ;;
    *) echo "Bilinmeyen secenek: $1" >&2; exit 2 ;;
  esac
done

log()  { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }

relogin_needed=0

# GNOME özel kısayolunu güvenli (mevcut kısayolları ezmeden) bağlar; turkify kısayolu
# zaten varsa dokunmaz (kullanıcının özelleştirdiği komut/tuş korunur).
bind_shortcut() {
  local base="org.gnome.settings-daemon.plugins.media-keys"
  local kpath="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/turkify/"
  local schema="$base.custom-keybinding:$kpath"
  local cur; cur="$(gsettings get "$base" custom-keybindings 2>/dev/null || echo '@as []')"
  if printf '%s' "$cur" | grep -q "custom-keybindings/turkify/"; then
    log "GNOME kısayolu zaten tanımlı, dokunulmadı ($(gsettings get "$schema" binding 2>/dev/null || echo '?'))"
    return
  fi
  local new
  new="$("$py" - "$cur" "$kpath" <<'PY'
import ast, sys
raw, kp = sys.argv[1].strip(), sys.argv[2]
if raw.startswith("@as"):
    raw = raw[3:].strip()
try:
    lst = ast.literal_eval(raw) if raw else []
except Exception:
    lst = []
if not isinstance(lst, list):
    lst = []
if kp not in lst:
    lst.append(kp)
print("[" + ", ".join("'%s'" % x for x in lst) + "]")
PY
)"
  local cmd="$repo/linux/bin/turkify-fix"
  [[ -n "$PASTE_DELAY_MS" ]] && cmd="env TURKIFY_PASTE_DELAY_MS=$PASTE_DELAY_MS $cmd"
  gsettings set "$base" custom-keybindings "$new"
  gsettings set "$schema" name 'Turkify duzelt'
  gsettings set "$schema" command "$cmd"
  gsettings set "$schema" binding "$SHORTCUT"
  log "GNOME kısayolu bağlandı: $SHORTCUT → turkify-fix"
}

# --- 1) Python venv + paket ---
if [[ ! -x "$repo/.venv/bin/python" ]]; then
  log "venv oluşturuluyor: $repo/.venv"
  python3 -m venv "$repo/.venv"
fi
py="$repo/.venv/bin/python"
if "$py" -c "import turkify" 2>/dev/null; then
  log "paket zaten kurulu (turkify import edilebiliyor)"
else
  log "paket kuruluyor: pip install -e .[morphology]"
  "$py" -m pip install --upgrade pip >/dev/null
  "$py" -m pip install -e "$repo[morphology]"
fi

# --- 2) Sistem araçları (apt ile eksikleri kur) ---
session="${XDG_SESSION_TYPE:-}"
[[ -z "$session" && -n "${WAYLAND_DISPLAY:-}" ]] && session="wayland"
[[ -z "$session" && -n "${DISPLAY:-}" ]] && session="x11"

declare -a pkgs=()
if [[ "$session" == "wayland" ]]; then
  command -v wl-copy >/dev/null || pkgs+=("wl-clipboard")
else
  command -v xclip >/dev/null || pkgs+=("xclip")
fi
command -v notify-send >/dev/null || pkgs+=("libnotify-bin")
command -v ydotool >/dev/null || pkgs+=("ydotool")

if [[ ${#pkgs[@]} -gt 0 ]]; then
  if command -v sudo >/dev/null && command -v apt-get >/dev/null; then
    log "eksik araçlar kuruluyor (apt): ${pkgs[*]}"
    sudo apt-get install -y "${pkgs[@]}" || warn "apt başarısız; gerekirse önce: sudo apt-get update"
  else
    warn "şu paketleri elle kurun: ${pkgs[*]}"
  fi
else
  log "sistem araçları hazır (clipboard, notify-send, ydotool)"
fi

# --- 3) ydotool: /dev/uinput erişimi (input grubu) + servis ---
if command -v ydotool >/dev/null; then
  if id -nG | tr ' ' '\n' | grep -qx input; then
    log "'input' grubu üyeliği var"
  elif command -v sudo >/dev/null; then
    log "'input' grubuna ekleniyor (ydotool /dev/uinput erişimi için)"
    sudo usermod -aG input "$USER" && relogin_needed=1 || warn "usermod başarısız; elle: sudo usermod -aG input $USER"
  else
    warn "ydotool için: sudo usermod -aG input $USER (sonra oturum yenile)"
  fi
  systemctl --user enable ydotool.service >/dev/null 2>&1 || true
  if systemctl --user start ydotool.service 2>/dev/null; then
    log "ydotool.service aktif"
  else
    warn "ydotool.service şimdi başlamadı (büyük olasılıkla 'input' grubu için oturum yenilemek gerekiyor)"
    relogin_needed=1
  fi
fi

# --- 4) Başlangıç dosyaları (varsa ASLA üzerine yazma). Yollar turkify.config'ten ---
cfg_json="$("$py" -c 'from turkify import config; print(config.config_path())')"
prot_txt="$("$py" -c 'from turkify import config; print(config.protected_words_path())')"
mkdir -p "$(dirname "$cfg_json")"

if [[ -f "$cfg_json" ]]; then
  log "config.json mevcut, korundu: $cfg_json"
else
  cp "$repo/config/config.example.json" "$cfg_json"
  log "config.json oluşturuldu (örnek varsayılanlardan): $cfg_json"
fi

# protected_words.txt: ADR 0008 gereği örnek kelimeler OTOMATİK kopyalanmaz; yorumlu boş şablon.
if [[ -f "$prot_txt" ]]; then
  log "protected_words.txt mevcut, korundu: $prot_txt"
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
  log "protected_words.txt oluşturuldu (yorumlu boş şablon): $prot_txt"
fi

# --- 5) systemd --user unit'leri (motor servisi + otomatik reload) ---
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cat > "$unit_dir/turkify.service" <<EOF
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
log "systemd unit'leri yazıldı: $unit_dir/{turkify.service, turkify-reload.path}"

# restart kullanılır ki re-install'da güncellenen unit çalışan sürece de uygulansın.
systemctl --user daemon-reload
systemctl --user enable turkify.service turkify-reload.path >/dev/null
systemctl --user restart turkify.service turkify-reload.path
log "servis durumu: $(systemctl --user is-active turkify.service) / reload izleyici: $(systemctl --user is-active turkify-reload.path)"

# --- 6) GNOME kısayolu ---
if [[ "$BIND_SHORTCUT" -eq 1 ]] && command -v gsettings >/dev/null \
   && printf '%s' "${XDG_CURRENT_DESKTOP:-}" | grep -qi gnome; then
  bind_shortcut
else
  cat <<EOF
==> Kısayolu elle tanımlayın (GNOME: Ayarlar → Klavye → Özel Kısayollar → +):
      Ad: Turkify duzelt   Komut: $repo/linux/bin/turkify-fix   Kısayol: tercihiniz
    (KDE: Sistem Ayarları → Kısayollar → Özel Kısayollar.)
EOF
fi

# --- Özet ---
cat <<EOF

==> Kurulum tamam. Kullanım: metni vurgula → kısayola bas.
    ydotool çalışıyorsa otomatik yapıştırılır; değilse bildirim çıkar → Ctrl+V.
    Config değişince motor otomatik tazelenir (restart gerekmez).
    Loglar: journalctl --user -u turkify.service -f
EOF
if [[ "$relogin_needed" -eq 1 ]]; then
  warn "ydotool otomatik yapıştırma için OTURUMU KAPATIP AÇIN (input grubu üyeliği yeni oturumda geçerli olur)."
fi
