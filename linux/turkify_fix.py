"""Linux ince istemci — seçili metni düzeltip yerine koyar (DE kısayolu çağırır).

macOS/Windows native frontend'lerinin Linux karşılığı: masaüstü ortamının kendi
kısayolu bu betiği çalıştırır. Akış (bkz. [ADR 0005](../docs/adr/0005-linux-terminal-servis.md)):

    1. Seçimi PRIMARY selection'dan oku (tuş simülasyonu YOK — Wayland-uyumlu).
    2. Sıcak servise (Unix soketi) gönder; soket yoksa cold-start fallback.
    3. Düzeltilmiş metni panoya yaz.
    4. ydotool varsa otomatik Ctrl+V; yoksa bildirim + kullanıcı elle yapıştırır.

Çekirdek motor (``src/turkify``) platform-nötr kalır; bu modül Linux'a özel pano/
enjeksiyon glue'sudur. Yalnızca hafif ``turkify.config`` baştan import edilir
(soket yolu ortak kaynağı); motor cold-start fallback'te tembel yüklenir.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

from turkify import config

# ydotool yapıştırmadan önce hedef pencerenin odaklı kalması için kısa bekleme.
_PASTE_DELAY_S = 0.05
# Pano/seçim/enjeksiyon araçlarına timeout (saniye) — takılı kalmayı önler.
_TOOL_TIMEOUT_S = 5.0
# Sıcak servise bağlanma/yanıt timeout'u.
_SOCKET_TIMEOUT_S = 10.0
# Linux input-event-codes: KEY_LEFTCTRL=29, KEY_V=47. ydotool "keycode:durum" ister
# (1=bas, 0=bırak): Ctrl bas, V bas, V bırak, Ctrl bırak.
_YDOTOOL_PASTE = ["29:1", "47:1", "47:0", "29:0"]

# Uygulama adı (bildirim başlığı).
_APP = "Turkify"


class ClipboardToolMissing(RuntimeError):
    """Gerekli pano/seçim aracı (wl-clipboard / xclip / xsel) bulunamadı."""


def session_type() -> str:
    """Görüntü oturumunu döner: ``'wayland'``, ``'x11'`` veya ``'unknown'``.

    Önce ``XDG_SESSION_TYPE``; o belirsizse ``WAYLAND_DISPLAY``/``DISPLAY``'e bakar.
    """
    explicit = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    if explicit in ("wayland", "x11"):
        return explicit
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def _first_tool(*names: str) -> str | None:
    """Verilen adaylardan PATH'te bulunan ilk komutu döner (yoksa ``None``)."""
    for name in names:
        if shutil.which(name):
            return name
    return None


def read_selection() -> str | None:
    """O an vurgulanmış metni (PRIMARY selection) tuş simülasyonu olmadan okur.

    Wayland'da ``wl-paste --primary``, X11'de ``xclip``/``xsel`` kullanır. Seçim
    boşsa ``None`` döner. Gerekli araç yoksa :class:`ClipboardToolMissing` atar.
    """
    if session_type() == "wayland":
        tool = _first_tool("wl-paste")
        if tool is None:
            raise ClipboardToolMissing("wl-paste gerekli (Debian/Ubuntu: wl-clipboard paketi)")
        cmd = [tool, "--primary", "--no-newline"]
    else:
        tool = _first_tool("xclip", "xsel")
        if tool is None:
            raise ClipboardToolMissing("xclip veya xsel gerekli")
        cmd = (
            [tool, "-selection", "primary", "-o"]
            if tool == "xclip"
            else [tool, "--primary", "--output"]
        )
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=_TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None
    # Boş PRIMARY: wl-paste sıfırdan farklı kod döndürebilir; stdout boşsa seçim yok.
    text = result.stdout.decode("utf-8", errors="replace")
    return text or None


def write_clipboard(text: str) -> None:
    """Düzeltilmiş metni panoya (CLIPBOARD) yazar. Araç yoksa hata atar."""
    if session_type() == "wayland":
        tool = _first_tool("wl-copy")
        if tool is None:
            raise ClipboardToolMissing("wl-copy gerekli (Debian/Ubuntu: wl-clipboard paketi)")
        cmd = [tool]
    else:
        tool = _first_tool("xclip", "xsel")
        if tool is None:
            raise ClipboardToolMissing("xclip veya xsel gerekli")
        cmd = (
            [tool, "-selection", "clipboard"]
            if tool == "xclip"
            else [tool, "--clipboard", "--input"]
        )
    subprocess.run(cmd, input=text.encode("utf-8"), timeout=_TOOL_TIMEOUT_S)


def try_paste() -> bool:
    """ydotool kuruluysa otomatik Ctrl+V enjekte eder; başardıysa ``True`` döner.

    GNOME/KDE Wayland'da tek gerçekçi enjeksiyon yolu ydotool'dur (kernel uinput).
    ydotool yoksa ya da ``ydotoold`` çalışmıyorsa sessizce ``False`` döner; çağıran
    elle-yapıştırma bildirimine düşer.
    """
    tool = _first_tool("ydotool")
    if tool is None:
        return False
    time.sleep(_PASTE_DELAY_S)
    try:
        result = subprocess.run(
            [tool, "key", *_YDOTOOL_PASTE], capture_output=True, timeout=_TOOL_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def notify(message: str) -> None:
    """Masaüstü bildirimi gösterir (en iyi-çaba; ``notify-send`` yoksa sessiz)."""
    tool = _first_tool("notify-send")
    if tool is None:
        return
    try:
        subprocess.run([tool, _APP, message], capture_output=True, timeout=_TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        pass


def _recv_line(sock: socket.socket) -> str | None:
    """Soketten ilk satırı (``\\n``'e kadar) okuyup UTF-8 çözer; veri yoksa ``None``."""
    chunks: list[bytes] = []
    while True:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            return None
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    data = b"".join(chunks)
    if not data:
        return None
    return data.split(b"\n", 1)[0].decode("utf-8", errors="replace")


def correct_via_socket(text: str) -> str | None:
    """Sıcak servise (Unix soketi) bağlanıp düzeltmeyi ister.

    Servis ayakta değilse / yanıt hatalıysa ``None`` döner (çağıran cold-start'a düşer).
    Soket yolu :func:`turkify.config.socket_path` ile servisle paylaşılır.
    """
    path = str(config.socket_path())
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(_SOCKET_TIMEOUT_S)
            sock.connect(path)
            request = json.dumps({"id": 1, "text": text}, ensure_ascii=False) + "\n"
            sock.sendall(request.encode("utf-8"))
            response = _recv_line(sock)
    except (OSError, TimeoutError, socket.timeout):
        return None
    if response is None:
        return None
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return None
    # Hata yanıtında "corrected" yoktur → None döner, cold-start denenir.
    corrected = data.get("corrected")
    return corrected if isinstance(corrected, str) else None


def correct_local(text: str) -> str:
    """Servis yoksa motoru in-process yükleyip düzeltir (cold-start fallback).

    Soketli yolla birebir aynı mantığı kullanmak için ``serve.EngineService``
    yeniden kullanılır (config çözümü + ``engine.correct`` aynı yerde).
    """
    from turkify import serve

    service = serve.EngineService()
    response = service.handle({"text": text})
    if "error" in response:
        raise RuntimeError(response["error"])
    return response["corrected"]


def correct(text: str) -> str:
    """Önce sıcak servisi dener; soket yoksa/başarısızsa cold-start'a düşer."""
    via_socket = correct_via_socket(text)
    if via_socket is not None:
        return via_socket
    return correct_local(text)


def main() -> int:
    try:
        selection = read_selection()
    except ClipboardToolMissing as exc:
        notify(f"Pano aracı eksik: {exc}")
        sys.stderr.write(f"turkify-fix: {exc}\n")
        return 1

    if not selection or not selection.strip():
        notify("Düzeltilecek seçim yok — metni vurgulayıp tekrar deneyin")
        return 0

    try:
        corrected = correct(selection)
    except Exception as exc:  # motor/servis hatası: kullanıcıya bildir, çökme
        notify(f"Düzeltme hatası: {exc}")
        sys.stderr.write(f"turkify-fix: duzeltme hatasi: {exc}\n")
        return 1

    try:
        write_clipboard(corrected)
    except ClipboardToolMissing as exc:
        notify(f"Pano aracı eksik: {exc}")
        sys.stderr.write(f"turkify-fix: {exc}\n")
        return 1

    if try_paste():
        return 0
    notify("Düzeltildi — Ctrl+V ile yapıştır")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
