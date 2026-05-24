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
from datetime import datetime
from typing import NamedTuple

from turkify import config as _config
from turkify.engine import correct


class Correction(NamedTuple):
    """Bir düzeltme işleminin girdisi ve çıktısı — loglama/inceleme için ikisi de tutulur."""

    original: str   # kullanıcının seçtiği (düzeltilmeden önceki) metin
    corrected: str  # düzeltilmiş metin

# Meta/süper tuşu her OS'ta kendi yerel adıyla yazılır; pynput tokenı ise her
# platformda ``<cmd>`` olduğundan (pynput bunu OS'a göre Command/Win/Super'e
# çözer) yerel ad ``cmd``'ye eşlenir. Yalnızca çalışılan OS'un yerel adı kabul
# edilir: macOS→"cmd", Windows→"win", Linux/diğer→"super".
_META_ALIASES_BY_PLATFORM = {
    "darwin": {"cmd": "cmd", "command": "cmd"},
    "win32": {"win": "cmd", "windows": "cmd"},
}
_META_ALIASES = _META_ALIASES_BY_PLATFORM.get(sys.platform, {"super": "cmd"})

# Meta tuşunun bu OS'taki gösterim adı (kullanıcıya/log'a). pynput tokenı her
# yerde "cmd" olsa da kullanıcı kendi OS'unun adını görmeli.
_META_DISPLAY = {"darwin": "cmd", "win32": "win"}.get(sys.platform, "super")

# config'teki kısayol adları → pynput modifier adları. ctrl/alt/shift her
# platformda aynı; meta tuşu OS'a göre (_META_ALIASES) eklenir.
_MOD_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
    **_META_ALIASES,
}


def to_pynput_hotkey(hotkey: dict) -> str:
    """``{mods:[...], key:"t"}`` → pynput biçimi ``"<ctrl>+<alt>+<cmd>+t"``.

    Meta tuşu OS'un yerel adıyla yazılır (macOS "cmd", Windows "win", Linux
    "super"); hepsi pynput'un platforma-uyarlı ``<cmd>`` tokenına çevrilir.
    """
    mods = [f"<{_MOD_ALIASES.get(m.lower(), m.lower())}>" for m in hotkey.get("mods", [])]
    return "+".join([*mods, hotkey.get("key", "a").lower()])


def to_display_hotkey(hotkey: dict) -> str:
    """Kısayolu kullanıcıya/log'a göstermek için OS-yerel adlarla biçimler.

    ``to_pynput_hotkey`` pynput'un iç ``<cmd>`` tokenını üretir; gösterimde ise
    meta tuşu OS'un yerel adıyla (macOS "cmd", Windows "win", Linux "super")
    yazılır. Ör. Windows'ta ``ctrl+alt+win+a``.
    """
    parts = []
    for mod in hotkey.get("mods", []):
        canonical = _MOD_ALIASES.get(mod.lower(), mod.lower())
        parts.append(_META_DISPLAY if canonical == "cmd" else canonical)
    parts.append(hotkey.get("key", "a").lower())
    return "+".join(parts)


def correct_clipboard_selection(
    settings: dict,
    *,
    copy_fn,
    paste_fn,
    read_clip,
    write_clip,
    sleep=time.sleep,
) -> Correction | None:
    """Seçimi kopyala→düzelt→yapıştır akışının çekirdeği (OS-bağımsız, test edilebilir).

    Tüm OS/kütüphane çağrıları parametre olarak verilir; böylece pynput/pyperclip
    olmadan mock'lanarak test edilebilir.

    Returns:
        Girdi ve çıktıyı içeren ``Correction``; seçim boşsa ``None``.
    """
    original_clipboard = read_clip()
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
    if original_clipboard is not None:
        write_clip(original_clipboard)  # kullanıcının panosunu geri yükle
    return Correction(original=selected, corrected=corrected)


def _modifier_key():
    """Platforma uygun kopyala/yapıştır modifier'ı (macOS: Cmd, diğer: Ctrl)."""
    from pynput.keyboard import Key

    return Key.cmd if sys.platform == "darwin" else Key.ctrl


def _log(message: str) -> None:
    """Saliseli zaman damgalı tek satır teşhis logu (stderr) yazar ve hemen boşaltır."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # mikrosaniyeyi milisaniyeye kıs
    sys.stderr.write(f"{timestamp} [agent] {message}\n")
    sys.stderr.flush()


def run(settings: dict | None = None) -> None:
    """Ajanı başlatır: motoru ısıtır, config'teki kısayolu global olarak dinler."""
    import pyperclip
    from pynput import keyboard

    cfg = settings if settings is not None else _config.resolve()
    _config.apply(cfg)
    correct("isinma", use_morphology=cfg.get("use_morphology", True))  # motoru ısıt

    controller = keyboard.Controller()
    modifier = _modifier_key()
    Key = keyboard.Key

    # Kullanıcının kısayolu hâlâ basılı olabilir (ör. CapsLock'u Hyper=Ctrl+Alt+Win
    # yapan AHK scripti, CapsLock bırakılana kadar bu tuşları basılı tutar). O
    # durumda simüle ettiğimiz Ctrl+C aslında Ctrl+Alt+Win+C olur ve kopyalama
    # başarısız olur. Bu yüzden kombinasyondan önce olası basılı modifier'ları
    # bırakırız; basılı değillerse bırakma zararsızdır.
    _HELD_MODS = (
        Key.alt, Key.alt_l, Key.alt_r,
        Key.cmd, Key.cmd_l, Key.cmd_r,
        Key.shift, Key.shift_l, Key.shift_r,
        Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    )

    def _release_held_mods() -> None:
        for key in _HELD_MODS:
            try:
                controller.release(key)
            except Exception:
                pass

    def _combo(letter: str) -> None:
        _release_held_mods()  # basılı Hyper'i (ör. Alt+Win) temizle ki Ctrl+C/V bozulmasın
        controller.press(modifier)
        controller.press(letter)
        controller.release(letter)
        controller.release(modifier)

    def _on_activate() -> None:
        # Anlık teşhis: kısayolun algılandığını, girdiyi ve çıktıyı göster.
        _log("kisayol algilandi")
        try:
            result = correct_clipboard_selection(
                cfg,
                copy_fn=lambda: _combo("c"),
                paste_fn=lambda: _combo("v"),
                read_clip=pyperclip.paste,
                write_clip=pyperclip.copy,
            )
            if result is None:
                _log("secili metin bulunamadi (once metni sec)")
            elif result.original == result.corrected:
                _log(f"degisiklik yok: {result.original!r}")
            else:
                _log(f"duzeltildi: {result.original!r} -> {result.corrected!r}")
        except Exception as exc:  # ajan tek bir hatayla çökmesin
            _log(f"hata: {exc}")

    hotkey = to_pynput_hotkey(cfg["hotkey"])

    # pynput'un GlobalHotKeys'i enjekte edilmiş (sentetik) tuş olaylarını BİLEREK
    # yok sayar (kaynak: _on_press içinde "if not injected"). Ancak CapsLock'u
    # Hyper'a eşleyen AutoHotkey gibi araçlar modifier'ları sentetik (injected)
    # gönderir; o durumda GlobalHotKeys kısayolu hiç algılayamaz. Bu yüzden
    # eşleştirmeyi, injected ayrımı yapmayan Listener + HotKey ile kendimiz
    # yaparız (pynput'un dokümante ettiği kalıp). Fiziksel tuşlar da aynı yoldan
    # işlendiği için bu, tüm platformlarda çalışır.
    hot = keyboard.HotKey(keyboard.HotKey.parse(hotkey), _on_activate)

    def _for_canonical(handler):
        return lambda key: handler(listener.canonical(key))

    listener = keyboard.Listener(
        on_press=_for_canonical(hot.press),
        on_release=_for_canonical(hot.release),
    )
    _log(f"hazir. Kisayol: {to_display_hotkey(cfg['hotkey'])}. Cikmak icin Ctrl-C.")
    with listener:
        listener.join()
