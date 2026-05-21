"""Faz 4 — Kalıcı süreç (daemon) ve hızlı istemci.

Sorun: tek-atış CLI her çağrıda Python başlatma + morfoloji motoru yükleme
(~1 sn) maliyeti öder. Daemon, motoru bir kez yükleyip bir Unix soketinde
dinler; istemci yalnızca soket üzerinden metin gönderip yanıt alır (motoru
yüklemez). Böylece etkileşimli kullanımda gecikme milisaniyelere iner.

Protokol (basit, çerçeveleme bağlantı kapanışıyla):
    istemci → metni gönderir, yazma yönünü kapatır (EOF)
    sunucu  → EOF'a kadar okur, düzeltir, sonucu gönderir, bağlantıyı kapatır
"""

import atexit
import os
import signal
import socket
import socketserver

_RECV_CHUNK = 65536

# AF_UNIX yol uzunluğu sınırlıdır (macOS ~104 bayt). macOS'ta
# tempfile.gettempdir() uzun bir yol döndüğünden kısa ve sabit /tmp kullanılır.
_SOCKET_DIR = "/tmp"


def default_socket_path() -> str:
    """Kullanıcıya özel varsayılan soket yolu (çoklu kullanıcıda çakışmaz)."""
    return os.path.join(_SOCKET_DIR, f"turkify-{os.getuid()}.sock")


def correct_via_daemon(
    text: str, *, socket_path: str | None = None, timeout: float = 5.0
) -> str | None:
    """Metni çalışan daemon'a gönderip düzeltilmiş hâlini alır.

    Args:
        text: Düzeltilecek metin.
        socket_path: Daemon soketi; ``None`` ise varsayılan kullanılır.
        timeout: Bağlantı/okuma zaman aşımı (sn).

    Returns:
        Düzeltilmiş metin; daemon çalışmıyor veya hata olursa ``None``
        (çağıran taraf in-process düzeltmeye düşebilir).
    """
    path = socket_path or default_socket_path()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(path)
            client.sendall(text.encode("utf-8"))
            client.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                data = client.recv(_RECV_CHUNK)
                if not data:
                    break
                chunks.append(data)
        return b"".join(chunks).decode("utf-8")
    except (OSError, socket.timeout):
        return None


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        chunks = []
        while True:
            data = self.request.recv(_RECV_CHUNK)
            if not data:
                break
            chunks.append(data)
        text = b"".join(chunks).decode("utf-8")
        result = self.server.correct_fn(text)
        self.request.sendall(result.encode("utf-8"))


class _Server(socketserver.ThreadingUnixStreamServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, socket_path, correct_fn):
        self.correct_fn = correct_fn
        super().__init__(socket_path, _Handler)


def serve(*, socket_path: str | None = None, use_llm: bool = False) -> None:
    """Düzeltme motorunu yükleyip Unix soketinde dinlemeye başlar.

    Motor başlangıçta ısıtılır (morfoloji bir kez yüklenir). ``Ctrl-C`` ile
    durdurulur; çıkışta soket dosyası temizlenir.
    """
    from turkify.engine import correct

    path = socket_path or default_socket_path()
    if os.path.exists(path):
        os.unlink(path)

    def _cleanup():
        if os.path.exists(path):
            os.unlink(path)

    # Temizlik güvencesi: SIGTERM (kill) temiz kapanışa yönlendirilir ve
    # atexit normal çıkışta soketi siler. Handler ISINMADAN ÖNCE kurulur ki
    # uzun süren ilk yükleme sırasında gelen sinyal de yakalansın.
    atexit.register(_cleanup)

    def _on_term(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _on_term)

    def correct_fn(text: str) -> str:
        return correct(text, use_llm=use_llm)

    correct_fn("isinma")  # motoru ısıt (morfoloji yüklensin)

    server = _Server(path, correct_fn)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if os.path.exists(path):
            os.unlink(path)
