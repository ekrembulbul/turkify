"""Faz 4 — daemon soket protokolü testleri.

Ağır motoru ısıtmadan, ``_Server`` doğrudan bir stub düzeltme fonksiyonuyla
çalıştırılır ve istemci-sunucu gidiş-dönüşü doğrulanır.
"""

import os
import threading

import pytest

from turkify import server


@pytest.fixture
def short_socket():
    # AF_UNIX yol uzunluğu sınırlı olduğundan kısa bir /tmp yolu kullanılır.
    path = f"/tmp/turkify-test-{os.getpid()}.sock"
    if os.path.exists(path):
        os.unlink(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _run_server(socket_path, correct_fn):
    srv = server._Server(socket_path, correct_fn)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv


def test_default_socket_path_is_user_specific():
    assert str(os.getuid()) in server.default_socket_path()


def test_daemon_round_trip(short_socket):
    srv = _run_server(short_socket, lambda text: text.upper())
    try:
        result = server.correct_via_daemon(
            "merhaba", socket_path=short_socket, timeout=3.0
        )
        assert result == "MERHABA"
    finally:
        srv.shutdown()
        srv.server_close()


def test_daemon_preserves_unicode(short_socket):
    srv = _run_server(short_socket, lambda text: text.replace("gorusme", "görüşme"))
    try:
        result = server.correct_via_daemon(
            "bugun gorusme", socket_path=short_socket, timeout=3.0
        )
        assert result == "bugun görüşme"
    finally:
        srv.shutdown()
        srv.server_close()


def test_client_returns_none_when_no_daemon():
    missing = f"/tmp/turkify-yok-{os.getpid()}.sock"
    assert server.correct_via_daemon("x", socket_path=missing, timeout=1.0) is None
