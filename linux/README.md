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

## Kullanım

Metni **vurgula** → kısayola **bas**. Düzeltilmiş metin panoya yazılır:
- `ydotool` kuruluysa **otomatik** Ctrl+V ile yapıştırılır.
- değilse bir bildirim çıkar; **Ctrl+V** ile elle yapıştırırsın.

> Seçim **PRIMARY selection**'dan okunur (vurgulanan metin) — kopya tuşu (Ctrl+C)
> simüle edilmez, bu yüzden Wayland'da da çalışır.

## Otomatik yapıştırma (ydotool, opsiyonel)

GNOME/KDE Wayland'da otomatik yapıştırma yalnızca **ydotool** ile mümkündür
(`wtype` sadece wlroots tabanlı Sway/Hyprland'de çalışır):

```bash
sudo apt install ydotool
systemctl --user enable --now ydotool   # ydotoold daemon'u — /dev/uinput erişimi ister
```

`/dev/uinput` erişimi için kullanıcının `input` grubunda olması veya bir udev kuralı
gerekebilir (dağıtıma göre). Kurulu/erişilebilir değilse istemci sessizce
elle-yapıştırma bildirimine düşer.

## Servis yönetimi

```bash
systemctl --user status  turkify.service     # durum
systemctl --user restart turkify.service     # config.json değişince tazele
journalctl --user -u turkify.service -f      # canlı log
```

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
