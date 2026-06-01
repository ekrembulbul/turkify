"""Linux ince istemci (turkify_fix) testleri.

Dış araçlar (wl-paste/xclip/ydotool/notify-send) ve soket subprocess/socket
seviyesinde mock'lanır; gerçek pano/enjeksiyon yapılmaz. Düzeltme dağıtımının
(soket → cold-start düşüşü) ve akışın saf mantığı doğrulanır.
"""

import subprocess
import types

import pytest

import turkify_fix as tf


# --- yardımcılar ---


def _completed(stdout: bytes = b"", returncode: int = 0):
    """subprocess.run dönüşünü taklit eden hafif nesne."""
    return types.SimpleNamespace(stdout=stdout, returncode=returncode)


def _fake_which(available):
    """Yalnızca ``available`` kümesindeki araçlar için yol döndüren which sahtesi."""
    return lambda name: f"/usr/bin/{name}" if name in available else None


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Testlerde ydotool öncesi beklemeyi atla."""
    monkeypatch.setattr(tf.time, "sleep", lambda _s: None)


# --- session_type ---


def test_session_type_explicit_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert tf.session_type() == "wayland"


def test_session_type_explicit_x11(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert tf.session_type() == "x11"


def test_session_type_falls_back_to_wayland_display(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert tf.session_type() == "wayland"


def test_session_type_unknown(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    assert tf.session_type() == "unknown"


# --- read_selection ---


def test_read_selection_wayland_uses_wl_paste(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"wl-paste"}))
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _completed(stdout="bugun gorusme".encode("utf-8"))

    monkeypatch.setattr(tf.subprocess, "run", fake_run)
    assert tf.read_selection() == "bugun gorusme"
    assert captured["cmd"][0] == "wl-paste"
    assert "--primary" in captured["cmd"]


def test_read_selection_x11_uses_xclip(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"xclip"}))
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _completed(stdout=b"selam")

    monkeypatch.setattr(tf.subprocess, "run", fake_run)
    assert tf.read_selection() == "selam"
    assert captured["cmd"][0] == "xclip"
    assert captured["cmd"][1:3] == ["-selection", "primary"]


def test_read_selection_empty_returns_none(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"wl-paste"}))
    monkeypatch.setattr(tf.subprocess, "run", lambda *a, **k: _completed(stdout=b"", returncode=1))
    assert tf.read_selection() is None


def test_read_selection_missing_tool_raises(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(tf.shutil, "which", _fake_which(set()))
    with pytest.raises(tf.ClipboardToolMissing):
        tf.read_selection()


# --- write_clipboard ---


def test_write_clipboard_wayland_uses_wl_copy(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"wl-copy"}))
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return _completed()

    monkeypatch.setattr(tf.subprocess, "run", fake_run)
    tf.write_clipboard("düzeltildi")
    assert captured["cmd"][0] == "wl-copy"
    assert captured["input"] == "düzeltildi".encode("utf-8")


def test_write_clipboard_missing_tool_raises(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr(tf.shutil, "which", _fake_which(set()))
    with pytest.raises(tf.ClipboardToolMissing):
        tf.write_clipboard("x")


# --- try_paste ---


def test_try_paste_no_ydotool_returns_false(monkeypatch):
    monkeypatch.setattr(tf.shutil, "which", _fake_which(set()))
    assert tf.try_paste() is False


def test_try_paste_success(monkeypatch):
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"ydotool"}))
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _completed(returncode=0)

    monkeypatch.setattr(tf.subprocess, "run", fake_run)
    assert tf.try_paste() is True
    # İki ayrı çağrı: önce modifier'ları bırak, sonra temiz Ctrl+V.
    assert len(calls) == 2
    assert calls[0] == ["ydotool", "key", *tf._MODIFIER_RELEASE]
    assert calls[1][:2] == ["ydotool", "key"]
    assert "--key-delay" in calls[1]
    assert calls[1][-len(tf._YDOTOOL_PASTE):] == tf._YDOTOOL_PASTE


def test_paste_delay_env_override(monkeypatch):
    monkeypatch.setenv("TURKIFY_PASTE_DELAY_MS", "400")
    assert tf._paste_delay_s() == 0.4
    monkeypatch.setenv("TURKIFY_PASTE_DELAY_MS", "gecersiz")
    assert tf._paste_delay_s() == tf._DEFAULT_PASTE_DELAY_S  # bozuk deger yok sayilir
    monkeypatch.delenv("TURKIFY_PASTE_DELAY_MS", raising=False)
    assert tf._paste_delay_s() == tf._DEFAULT_PASTE_DELAY_S


def test_try_paste_nonzero_returns_false(monkeypatch):
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"ydotool"}))
    monkeypatch.setattr(tf.subprocess, "run", lambda *a, **k: _completed(returncode=1))
    assert tf.try_paste() is False


def test_try_paste_timeout_returns_false(monkeypatch):
    monkeypatch.setattr(tf.shutil, "which", _fake_which({"ydotool"}))

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ydotool", timeout=5)

    monkeypatch.setattr(tf.subprocess, "run", boom)
    assert tf.try_paste() is False


# --- notify ---


def test_notify_no_tool_is_silent(monkeypatch):
    monkeypatch.setattr(tf.shutil, "which", _fake_which(set()))
    tf.notify("merhaba")  # exception atmamalı


# --- correct() dağıtımı: soket > cold-start ---


def test_correct_prefers_socket(monkeypatch):
    monkeypatch.setattr(tf, "correct_via_socket", lambda text: "SOKET")
    monkeypatch.setattr(tf, "correct_local", lambda text: pytest.fail("cold-start çağrılmamalı"))
    assert tf.correct("x") == "SOKET"


def test_correct_falls_back_to_local_when_socket_down(monkeypatch):
    monkeypatch.setattr(tf, "correct_via_socket", lambda text: None)
    monkeypatch.setattr(tf, "correct_local", lambda text: "COLDSTART")
    assert tf.correct("x") == "COLDSTART"


# --- main() akışı ---


def test_main_empty_selection_notifies_and_succeeds(monkeypatch):
    monkeypatch.setattr(tf, "read_selection", lambda: None)
    msgs = []
    monkeypatch.setattr(tf, "notify", lambda m: msgs.append(m))
    monkeypatch.setattr(tf, "correct", lambda t: pytest.fail("düzeltme çağrılmamalı"))
    assert tf.main() == 0
    assert any("seçim yok" in m for m in msgs)


def test_main_tool_missing_returns_error(monkeypatch):
    def raise_missing():
        raise tf.ClipboardToolMissing("wl-paste gerekli")

    monkeypatch.setattr(tf, "read_selection", raise_missing)
    monkeypatch.setattr(tf, "notify", lambda m: None)
    assert tf.main() == 1


def test_main_success_with_auto_paste(monkeypatch):
    monkeypatch.setattr(tf, "read_selection", lambda: "bugun")
    monkeypatch.setattr(tf, "correct", lambda t: "bugün")
    written = {}
    monkeypatch.setattr(tf, "write_clipboard", lambda text: written.setdefault("text", text))
    monkeypatch.setattr(tf, "try_paste", lambda: True)
    monkeypatch.setattr(tf, "notify", lambda m: pytest.fail("otomatik yapıştırınca bildirim olmamalı"))
    assert tf.main() == 0
    assert written["text"] == "bugün"


def test_main_success_manual_paste_notifies(monkeypatch):
    monkeypatch.setattr(tf, "read_selection", lambda: "bugun")
    monkeypatch.setattr(tf, "correct", lambda t: "bugün")
    monkeypatch.setattr(tf, "write_clipboard", lambda text: None)
    monkeypatch.setattr(tf, "try_paste", lambda: False)
    msgs = []
    monkeypatch.setattr(tf, "notify", lambda m: msgs.append(m))
    assert tf.main() == 0
    assert any("Ctrl+V" in m for m in msgs)


def test_main_correction_error_returns_error(monkeypatch):
    monkeypatch.setattr(tf, "read_selection", lambda: "bugun")

    def boom(_t):
        raise RuntimeError("motor patladı")

    monkeypatch.setattr(tf, "correct", boom)
    msgs = []
    monkeypatch.setattr(tf, "notify", lambda m: msgs.append(m))
    assert tf.main() == 1
    assert any("hata" in m.lower() for m in msgs)
