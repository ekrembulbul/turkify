"""Motor servisi (`turkify serve`) testleri — engine.correct mock'lanır."""

import io
import json
import socket
import threading

import pytest

from turkify import serve


@pytest.fixture
def service(monkeypatch):
    """correct() sahte; settings enjekte edilmiş bir servis (config'e dokunmaz)."""
    monkeypatch.setattr(serve, "correct", lambda text, **k: text.replace("gorusme", "görüşme"))
    return serve.EngineService(
        settings={"use_llm": False, "use_morphology": True, "model": None}
    )


# --- handle (saf) ---


def test_handle_corrects_text(service):
    assert service.handle({"text": "bugun gorusme"}) == {"corrected": "bugun görüşme"}


def test_handle_preserves_id(service):
    assert service.handle({"id": 7, "text": "bugun gorusme"}) == {
        "id": 7,
        "corrected": "bugun görüşme",
    }


def test_handle_ping(service):
    assert service.handle({"cmd": "ping"}) == {"ok": True}


def test_handle_reload(monkeypatch, service):
    # reload yeni ayar okumalı; _resolve_and_apply'ı sahteleyip çağrıldığını doğrula.
    called = {"n": 0}

    def fake_resolve(overrides=None):
        called["n"] += 1
        return {"use_llm": True, "use_morphology": True, "model": "x"}

    monkeypatch.setattr(serve, "_resolve_and_apply", fake_resolve)
    assert service.handle({"cmd": "reload"}) == {"ok": True}
    assert called["n"] == 1
    assert service._settings["model"] == "x"


def test_handle_unknown_command(service):
    resp = service.handle({"cmd": "zipla"})
    assert "error" in resp and "bilinmeyen" in resp["error"]


def test_handle_missing_text_and_cmd(service):
    resp = service.handle({"foo": 1})
    assert "error" in resp and "text" in resp["error"]


def test_handle_non_dict(service):
    assert service.handle(["liste"]) == {"error": "istek bir JSON nesnesi olmali"}


def test_handle_correct_exception_returns_error(monkeypatch, service):
    def boom(*a, **k):
        raise RuntimeError("motor patladi")

    monkeypatch.setattr(serve, "correct", boom)
    resp = service.handle({"id": 3, "text": "x"})
    assert resp == {"id": 3, "error": "motor patladi"}


# --- _process_line ---


def test_process_line_invalid_json(service):
    resp = serve._process_line(service, "{bozuk")
    assert "error" in resp and "gecersiz JSON" in resp["error"]


# --- serve_stdio (StringIO, thread yok) ---


def test_serve_stdio_roundtrip(service):
    stdin = io.StringIO('{"id": 1, "text": "bugun gorusme"}\n\n{"cmd": "ping"}\n')
    stdout = io.StringIO()
    serve.serve_stdio(service, stdin=stdin, stdout=stdout)
    lines = [json.loads(l) for l in stdout.getvalue().splitlines() if l.strip()]
    # Bos satir atlanir; iki yanit beklenir.
    assert lines == [{"id": 1, "corrected": "bugun görüşme"}, {"ok": True}]


# --- soket bağlantı işleyici (socketpair: bind/path yok, AF_UNIX 104 limiti yok) ---


def test_handle_connection_roundtrip(service):
    srv_sock, cli_sock = socket.socketpair()
    worker = threading.Thread(target=serve._handle_connection, args=(service, srv_sock))
    worker.start()
    try:
        cli = cli_sock.makefile("rw", encoding="utf-8", newline="\n")
        cli.write('{"id": 9, "text": "bugun gorusme"}\n')
        cli.flush()
        response = json.loads(cli.readline())
        assert response == {"id": 9, "corrected": "bugun görüşme"}
        cli.close()  # istemci kapanır → _handle_connection döngüsü biter
    finally:
        cli_sock.close()
        worker.join(timeout=5)
    assert not worker.is_alive()
