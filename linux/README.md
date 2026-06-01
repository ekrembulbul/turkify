# Turkify — Linux

Linux'ta native GUI yoktur: paylaşımlı Python motoru bir **`systemd --user` servisi**
olarak sıcak tutulur, masaüstü ortamının (GNOME/KDE) **kendi kısayolu** ince istemciyi
çalıştırır. Tasarım gerekçesi: [ADR 0005](../docs/adr/0005-linux-terminal-servis.md).

```
vurgula  ──(DE kısayolu)──▶  turkify-fix  ──(Unix soketi)──▶  serve (sıcak motor)
                                  │                                   │
                            PRIMARY oku                         {"corrected": …}
                                  ▼
                         panoya yaz → ydotool ile Ctrl+V  (yoksa: elle yapıştır)
```

## Bileşenler

| Dosya | İş |
|---|---|
| `turkify_fix.py` | İnce istemci: PRIMARY oku → soket/cold-start → pano → ydotool/bildirim |
| `bin/turkify-fix` | Başlatıcı (doğru Python'u bulur); DE kısayolu buna işaret eder |
| `service/turkify.service` | `systemd --user` unit şablonu (`serve --socket`) |
| `install.sh` | Unit'i yazar, servisi etkinleştirir, talimatı basar |

## Kurulum

```bash
# 1) Motoru kur (repo kökünde)
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[morphology]"   # morphology opsiyonel (Tier 2)

# 2) Pano araçları (oturuma göre)
#   Wayland: sudo apt install wl-clipboard
#   X11    : sudo apt install xclip            # veya xsel

# 3) Servisi kur
linux/install.sh
```

`install.sh` ayrıca ilk kurulumda **başlangıç dosyalarını** oluşturur (mevcutsa
**üzerine yazmaz**):
- `~/.config/turkify/config.json` — örnek varsayılanlardan (`use_llm=false`, tam offline).
  Tier 3/LLM açmak için `model` + `use_llm`'i burada düzenleyin.
- `~/.config/turkify/protected_words.txt` — **yorumlu boş şablon**. ADR 0008 gereği
  paketteki örnek liste otomatik kopyalanmaz; korunacak terimleri buraya ekleyin
  (hazır liste: [`config/protected_words.example.txt`](../config/protected_words.example.txt)).

Sonra **GNOME/KDE kısayol** kurulum adımlarını ve komutun tam yolunu
(`…/linux/bin/turkify-fix`) ekrana yazar.

## Kısayol tanımlama (GNOME/KDE)

Düzeltme, masaüstü ortamının **kendi kısayoludur** (uygulama tuş yakalamaz —
Wayland kısıtı). Kısayol `linux/bin/turkify-fix`'i çalıştırır. Kombinasyonu siz
seçersiniz; başka kısayollarla çakışmayan biri olsun (Ubuntu'da `Ctrl+Alt+T`
terminale bağlıdır — kullanmayın).

### GNOME — Ayarlar (GUI)

Ayarlar → **Klavye** → **Özel Kısayollar** → **+**:

- **Ad:** `Turkify duzelt`
- **Komut:** `<REPO>/linux/bin/turkify-fix` (tam yol; `install.sh` ekrana yazar)
- **Kısayol:** tercihiniz (ör. `Ctrl+Super+Alt+A`)

### GNOME — gsettings (komut satırı)

Aynı tanımı terminalden yapmak için (komut yolunu ve `binding`'i kendinize göre
düzenleyin):

```bash
KEY=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/turkify/
SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY"
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$KEY']"
gsettings set "$SCHEMA" name 'Turkify duzelt'
gsettings set "$SCHEMA" command "$HOME/projects/turkify/linux/bin/turkify-fix"
gsettings set "$SCHEMA" binding '<Control><Super><Alt>a'   # ctrl+super+alt+a
```

> ⚠️ İlk `set` listeyi **tek girdiyle değiştirir**. Zaten özel kısayollarınız
> varsa onları kaybetmemek için mevcut listeye `turkify` yolunu **ekleyin** (ya da
> GUI'yi kullanın). Mevcut listeyi görmek için:
> `gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings`

### KDE

Sistem Ayarları → **Kısayollar** → **Özel Kısayollar** → yeni global kısayol;
eylem (komut) olarak `<REPO>/linux/bin/turkify-fix`.

## Kullanım

Metni **vurgula** → kısayola **bas**. Düzeltilmiş metin panoya yazılır:
- `ydotool` kuruluysa **otomatik** Ctrl+V ile yapıştırılır.
- değilse bir bildirim çıkar; **Ctrl+V** ile elle yapıştırırsın.

> Seçim **PRIMARY selection**'dan okunur (vurgulanan metin) — kopya tuşu (Ctrl+C)
> simüle edilmez, bu yüzden Wayland'da da çalışır.

## Otomatik yapıştırma (ydotool, opsiyonel)

GNOME/KDE Wayland'da otomatik yapıştırma yalnızca **ydotool** ile mümkündür
(`wtype` yalnızca wlroots tabanlı Sway/Hyprland'de çalışır). ydotool, `ydotoold`
daemon'u üzerinden `/dev/uinput`'a tuş enjekte eder; bu cihaz `root:input 0660`
olduğundan kullanıcının **`input` grubunda** olması gerekir.

```bash
# 1) Kur
sudo apt install ydotool          # veya dağıtımınızın paketi

# 2) /dev/uinput erişimi için 'input' grubuna gir (daemon cihazı açabilsin)
sudo usermod -aG input "$USER"

# 3) OTURUMU KAPATIP AÇIN (veya yeniden başlatın) — grup üyeliği yalnızca yeni
#    oturumda (ve systemd --user yöneticisinde) geçerli olur.

# 4) Girişten sonra daemon'u başlat
systemctl --user reset-failed ydotool.service   # eski başarısız denemeleri temizle
systemctl --user enable --now ydotool.service
systemctl --user status ydotool.service          # 'active (running)' olmalı
```

`/dev/uinput`'in grup/izni `80-uinput.rules` udev kuralıyla zaten ayarlıdır
(`KERNEL=="uinput", GROUP="input", MODE="0660"`); tek gereken kullanıcının `input`
grubunda olmasıdır.

**Sorun giderme.** `systemctl --user status ydotool` `failed` ve logda
`failed to open uinput device: Permission denied` görüyorsanız: henüz `input`
grubunda değilsiniz ya da oturumu yenilemediniz.

```bash
groups | grep -q input && echo "input grubunda" || echo "input grubunda DEGIL -> 2-3. adim"
journalctl --user -u ydotool.service -n 20 --no-pager   # gercek hata
```

ydotool kurulu/erişilebilir **değilse** `turkify-fix` sessizce elle-yapıştırma
bildirimine düşer (metin panoda kalır, **Ctrl+V** ile yapıştırılır) — yani ydotool
tamamen opsiyoneldir, kurulu olmadan da düzeltme çalışır.

### Otomatik yapıştırma aralıklı ıskalıyorsa — bekleme süresi

Kısayolun modifier tuşları (Ctrl/Super/Alt) hâlâ basılıyken enjekte edilen Ctrl+V
onlarla çakışır. `turkify-fix` bunu iki yolla azaltır: yapıştırmadan önce modifier'ları
bırakır ve kısa bir süre bekler. Bekleme **varsayılan 250 ms**; tuşları geç
bırakıyorsan ara sıra ıskalayabilir. Süreyi `TURKIFY_PASTE_DELAY_MS` ile artır.

Kısayol komutuna env ekleyerek (GNOME, gsettings):

```bash
SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/turkify/"
gsettings set "$SCHEMA" command "env TURKIFY_PASTE_DELAY_MS=400 $HOME/projects/turkify/linux/bin/turkify-fix"
```

(400 → 500/600 deneyebilirsin; geri almak için `env TURKIFY_PASTE_DELAY_MS=… ` önekini çıkar.)

## Servis yönetimi

Servis **`--verbose` ile** çalışır (varsayılan): her istek ve karar journald'a düşer.

```bash
systemctl --user status  turkify.service     # durum
systemctl --user restart turkify.service     # elle tam yeniden başlatma
journalctl --user -u turkify.service -f      # canlı log ([Motor]/[Istek] satırları)
```

## Otomatik reload (config değişince)

`config.json` veya `protected_words.txt`'i düzenlediğinde motor **otomatik tazelenir**
— servis sıcak kalır, restart gerekmez. Mekanizma (`install.sh` kurar):

- `turkify-reload.path` config dizinini izler (dosya içi düzenleme + atomik kaydet).
- Değişiklikte `turkify-reload.service` (oneshot) çalışır → `turkify-fix --reload` →
  motora `{"cmd":"reload"}` gönderilir (config + korumalı kelimeler yeniden okunur).
- Servis kapalıysa no-op'tur (bir sonraki başlangıçta taze config zaten okunur).

```bash
systemctl --user status turkify-reload.path           # izleyici durumu
journalctl --user -u turkify-reload.service --no-pager # son reload tetiklemeleri
```

Editörün bu olayları üretmiyorsa (nadiren) elle: `systemctl --user restart turkify.service`.

## Cold-start (servissiz) çalışma

Servis kapalıysa `turkify-fix` motoru **in-process** yükleyip düzeltir (biraz
yavaş — her çağrıda Tier 2/zeyrek yüklenir). Yani servis olmadan da çalışır;
servis yalnızca motoru sıcak tutarak gecikmeyi yok eder.

## Bilinen kısıtlar

| Durum | Not |
|---|---|
| Wayland + GNOME/KDE | Otomatik yapıştırma için `ydotool` gerekir; yoksa elle Ctrl+V |
| X11 | `xclip`/`xsel` ile sorunsuz; otomatik yapıştırma için `ydotool` |
| Tray ikonu yok | "Çalışıyor" göstergesi `systemctl status` + `notify-send` bildirimleri |
| İptal (cancel) | Şimdilik yok — ertelendi (ADR 0005 §3) |

Genel kurulum/yapılandırma: [docs/KURULUM.md](../docs/KURULUM.md) ·
çok-platform tasarım: [docs/PORTABILITY.md](../docs/PORTABILITY.md).
