"""Linux ince istemci — seçili metni düzeltip yerine koyar (DE kısayolu çağırır).

macOS/Windows native frontend'lerinin Linux karşılığı: masaüstü ortamının kendi
kısayolu bu betiği çalıştırır. Akış (bkz. [ADR 0005](../docs/adr/0005-linux-terminal-servis.md)):

    1. Seçimi PRIMARY selection'dan oku (tuş simülasyonu YOK — Wayland-uyumlu).
    2. Sıcak servise (Unix soketi) gönder; soket yoksa cold-start fallback.
    3. Düzeltilmiş metni panoya yaz + bildirim göster.
    4. Kullanıcı **Ctrl+V** ile yapıştırır. Otomatik tuş enjeksiyonu YOKTUR
       (ydotool ile Ctrl+V kararsızdı; manuel yapıştırma kararlı ve basittir).

Çekirdek motor (``src/turkify``) platform-nötr kalır; bu modül Linux'a özel pano
glue'sudur. Yalnızca hafif ``turkify.config`` baştan import edilir (soket yolu ortak
kaynağı); motor cold-start fallback'te tembel yüklenir.
"""

import json
import os
import shutil
import socket
import subprocess
import sys

from turkify import config

# Pano/seçim araçlarına timeout (saniye) — takılı kalmayı önler.
_TOOL_TIMEOUT_S = 5.0
# Sıcak servise bağlanma/yanıt timeout'u.
_SOCKET_TIMEOUT_S = 10.0

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


def _send_request(payload: dict) -> dict | None:
    """Sıcak servise (Unix soketi) bir JSON isteği gönderip yanıt nesnesini döner.

    Bağlantı kurulamazsa (servis kapalı) ya da yanıt bozuksa ``None`` döner. Soket
    yolu :func:`turkify.config.socket_path` ile servisle paylaşılır.
    """
    path = str(config.socket_path())
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(_SOCKET_TIMEOUT_S)
            sock.connect(path)
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            response = _recv_line(sock)
    except (OSError, TimeoutError, socket.timeout):
        return None
    if response is None:
        return None
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None


def correct_via_socket(text: str) -> str | None:
    """Sıcak servise düzeltmeyi ister; servis yoksa / yanıt hatalıysa ``None``.

    ``None`` dönerse çağıran cold-start'a düşer (bkz. :func:`correct`).
    """
    data = _send_request({"id": 1, "text": text})
    if data is None:
        return None
    # Hata yanıtında "corrected" yoktur → None döner, cold-start denenir.
    corrected = data.get("corrected")
    return corrected if isinstance(corrected, str) else None


def send_reload() -> bool:
    """Çalışan servise ``{"cmd":"reload"}`` gönderir (config + korumalı kelime tazeleme).

    Servis kapalıysa (bağlanılamıyorsa) tazelenecek sıcak motor yoktur — bir sonraki
    başlangıçta zaten taze config okunur; bu durumda **no-op başarı** (``True``) döner.
    Yalnızca servis ayaktayken reload hata verirse ``False`` döner.
    """
    data = _send_request({"id": 1, "cmd": "reload"})
    if data is None:
        return True  # servis kapalı → tazelenecek bir şey yok, sorun değil
    return data.get("ok") is True


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


def _cmd_reload() -> int:
    """``--reload`` modu: çalışan servise reload gönderir (config değişiminde tetiklenir)."""
    if send_reload():
        return 0
    # Servis ayakta ama reload hata verdi (bozuk config gibi). Bildirim yok: bu
    # arka plan (path-unit) işidir, ayrıntı journald'a düşer.
    sys.stderr.write("turkify-fix: reload basarisiz (servis ayakta, ayar hatali olabilir)\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--reload" in args:
        return _cmd_reload()

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

    notify("Düzeltildi — Ctrl+V ile yapıştır")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
