"""Çok-platform kısayol ajanı.

Hammerspoon/Raycast (yalnızca macOS) yerine, motoru bellekte sıcak tutan ve
config'ten okunan global bir kısayolu dinleyen tek bir süreç. Kısayola basınca
seçili metni kopyalar → düzeltir → yerine yapıştırır.

Bağımlılıklar (yalnızca ajan için, çekirdek motor bağımsız kalır):
  * ``pynput``   — global kısayol + tuş basışı simülasyonu (macOS/Windows/Linux)
  * ``pyperclip``— pano okuma/yazma

Öncelik macOS'tur; kod Windows/Linux için de yazılmıştır ama Linux/Wayland'da
global kısayol/enjeksiyon OS kısıtları nedeniyle sınırlı olabilir (bkz.
PORTABILITY.md). macOS'ta Erişilebilirlik (Accessibility) izni gerekir.
"""

import sys
import time

from turkify import config as _config
from turkify.engine import correct

# config'teki kısayol adları → pynput modifier adları
_MOD_ALIASES = {
    "cmd": "cmd",
    "command": "cmd",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
}


def to_pynput_hotkey(hotkey: dict) -> str:
    """``{mods:[...], key:"t"}`` → pynput biçimi ``"<ctrl>+<alt>+<cmd>+t"``."""
    mods = [f"<{_MOD_ALIASES.get(m.lower(), m.lower())}>" for m in hotkey.get("mods", [])]
    return "+".join([*mods, hotkey.get("key", "t").lower()])


def correct_clipboard_selection(
    settings: dict,
    *,
    copy_fn,
    paste_fn,
    read_clip,
    write_clip,
    sleep=time.sleep,
) -> str | None:
    """Seçimi kopyala→düzelt→yapıştır akışının çekirdeği (OS-bağımsız, test edilebilir).

    Tüm OS/kütüphane çağrıları parametre olarak verilir; böylece pynput/pyperclip
    olmadan mock'lanarak test edilebilir.

    Returns:
        Düzeltilmiş metin; seçim boşsa ``None``.
    """
    original = read_clip()
    copy_fn()
    sleep(0.15)  # panonun güncellenmesi için
    selected = read_clip()
    if not selected:
        return None
    corrected = correct(
        selected,
        use_llm=settings.get("use_llm", False),
        use_morphology=settings.get("use_morphology", True),
        model=settings.get("model"),
    )
    write_clip(corrected)
    sleep(0.05)
    paste_fn()
    sleep(0.2)  # yapıştırma tamamlansın
    if original is not None:
        write_clip(original)  # kullanıcının panosunu geri yükle
    return corrected


def _modifier_key():
    """Platforma uygun kopyala/yapıştır modifier'ı (macOS: Cmd, diğer: Ctrl)."""
    from pynput.keyboard import Key

    return Key.cmd if sys.platform == "darwin" else Key.ctrl


def run(settings: dict | None = None) -> None:
    """Ajanı başlatır: motoru ısıtır, config'teki kısayolu global olarak dinler."""
    import pyperclip
    from pynput import keyboard

    cfg = settings or _config.load()
    _config.apply(cfg)
    correct("isinma", use_morphology=cfg.get("use_morphology", True))  # motoru ısıt

    controller = keyboard.Controller()
    modifier = _modifier_key()

    def _combo(letter: str) -> None:
        controller.press(modifier)
        controller.press(letter)
        controller.release(letter)
        controller.release(modifier)

    def _on_activate() -> None:
        # Anlık teşhis: kısayolun algılandığını ve sonucu doğrudan göster.
        sys.stderr.write("[agent] kisayol algilandi\n")
        sys.stderr.flush()
        try:
            result = correct_clipboard_selection(
                cfg,
                copy_fn=lambda: _combo("c"),
                paste_fn=lambda: _combo("v"),
                read_clip=pyperclip.paste,
                write_clip=pyperclip.copy,
            )
            if result is None:
                sys.stderr.write("[agent] secili metin bulunamadi (once metni sec)\n")
            else:
                sys.stderr.write(f"[agent] duzeltildi -> {result!r}\n")
        except Exception as exc:  # ajan tek bir hatayla çökmesin
            sys.stderr.write(f"[agent] hata: {exc}\n")
        sys.stderr.flush()

    hotkey = to_pynput_hotkey(cfg["hotkey"])
    sys.stderr.write(f"[agent] hazir. Kisayol: {hotkey}. Cikmak icin Ctrl-C.\n")
    sys.stderr.flush()
    with keyboard.GlobalHotKeys({hotkey: _on_activate}) as listener:
        listener.join()
