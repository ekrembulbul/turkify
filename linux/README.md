# Turkify — Linux

Linux'ta native GUI yoktur: paylaşımlı Python motoru bir **`systemd --user` servisi**
olarak sıcak tutulur, masaüstü ortamının (GNOME/KDE) **kendi kısayolu** ince istemciyi
çalıştırır. Tasarım gerekçesi: [ADR 0005](../docs/adr/0005-linux-terminal-servis.md).

```
vurgula  ──(DE kısayolu)──▶  turkify-fix  ──(Unix soketi)──▶  serve (sıcak motor)
                                  │                                   │
                            PRIMARY oku                         {"corrected": …}
                                  ▼
                         panoya yaz → bildirim → kullanıcı Ctrl+V ile yapıştırır
```

> **Yapıştırma manueldir:** düzeltilen metin panoya yazılır + bildirim çıkar; Ctrl+V
> ile sen yapıştırırsın. Otomatik tuş enjeksiyonu (ydotool) yoktur — Wayland'da
> kararsız olduğu için kaldırıldı (bkz. [ADR 0005 §2](../docs/adr/0005-linux-terminal-servis.md)).

## Bileşenler

| Dosya | İş |
|---|---|
| `turkify_fix.py` | İnce istemci: PRIMARY oku → soket/cold-start → pano → bildirim |
| `bin/turkify-fix` | Başlatıcı (doğru Python'u bulur); DE kısayolu buna işaret eder |
| `service/turkify.service` | `systemd --user` unit şablonu (`serve --socket`) |
| `install.sh` | Unit'i yazar, servisi etkinleştirir, talimatı basar |

## Kurulum

Temiz bir klondan **tek komut** (kişisel/few-machines kurulum):

```bash
linux/install.sh
```

`install.sh` eksiksiz, **idempotent** bir bootstrap'tır — gerekeni yapar, gerekmeyeni
atlar (kurulu makinede güvenle tekrar çalıştırılır):

1. `.venv` oluşturur + paketi kurar (`pip install -e ".[morphology]"`).
2. Eksik sistem araçlarını `apt` ile kurar: clipboard (`wl-clipboard`/`xclip`) +
   `libnotify-bin` (bildirim) *(sudo sorabilir)*.
3. **Başlangıç dosyaları** (varsa **üzerine yazmaz**):
   - `~/.config/turkify/config.json` — örnek varsayılanlardan (`use_llm=false`, tam offline).
     Tier 3/LLM için `model` + `use_llm`'i düzenleyin.
   - `~/.config/turkify/protected_words.txt` — yorumlu boş şablon (ADR 0008: örnek liste
     otomatik kopyalanmaz; hazır liste [`config/protected_words.example.txt`](../config/protected_words.example.txt)).
4. systemd `--user` unit'leri (sıcak motor + otomatik reload) yazar, enable+restart eder.
5. **GNOME kısayolunu** `gsettings` ile bağlar (varsa **dokunmaz**).

### Seçenekler

```bash
linux/install.sh --shortcut '<Control><Alt>y'   # kısayol kombinasyonu (varsayılan <Control><Super><Alt>a)
linux/install.sh --no-shortcut                  # kısayolu bağlama, sadece talimat yaz
```

> Yalnızca **engine'i** (CLI, servis olmadan) istiyorsanız `install.sh` gerekmez:
> `python3 -m venv .venv && .venv/bin/python -m pip install -e ".[morphology]"` yeter.

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

Metni **vurgula** → kısayola **bas** → "Düzeltildi — Ctrl+V ile yapıştır" bildirimi
çıkar → **Ctrl+V** ile yapıştır. Düzeltilmiş metin panoya yazılır; yapıştırmayı sen
yaparsın (otomatik tuş enjeksiyonu yoktur).

> Seçim **PRIMARY selection**'dan okunur (vurgulanan metin) — kopya tuşu (Ctrl+C)
> simüle edilmez, bu yüzden Wayland'da da çalışır.

> **Neden otomatik yapıştırma yok?** Wayland'da tuş enjeksiyonu yalnızca `ydotool`
> (kernel `uinput`) ile mümkündü; ama `uinput` izni + oturum yenileme yükü getiriyor
> ve enjekte edilen Ctrl+V güvenilmez çalışıyordu (bazen düz `v` olup seçimi siliyordu).
> Bu yüzden tamamen kaldırıldı; manuel Ctrl+V kararlı ve basittir
> (bkz. [ADR 0005 §2](../docs/adr/0005-linux-terminal-servis.md)).
>
> Daha önce kurduysanız `ydotool` artık kullanılmıyor; isterseniz kapatabilirsiniz:
> `systemctl --user disable --now ydotool.service`.

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
| Yapıştırma | Manuel: düzeltilen metin panoda, **Ctrl+V** ile yapıştırılır (otomatik enjeksiyon yok) |
| Pano araçları | Wayland `wl-clipboard`, X11 `xclip`/`xsel` kurulu olmalı |
| Tray ikonu yok | "Çalışıyor" göstergesi `systemctl status` + `notify-send` bildirimleri |
| İptal (cancel) | Şimdilik yok — ertelendi (ADR 0005 §3) |

Genel kurulum/yapılandırma: [docs/KURULUM.md](../docs/KURULUM.md) ·
çok-platform tasarım: [docs/PORTABILITY.md](../docs/PORTABILITY.md).
