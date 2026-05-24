"""Kısayol ajanı testleri — OS/kütüphane çağrıları mock'lanır (pynput/pyperclip gerekmez)."""

import sys

from turkify import agent

# Meta tuşunun calisilan OS'taki yerel adi (testler her platformda gecsin).
_META = {"darwin": "cmd", "win32": "win"}.get(sys.platform, "super")


def test_to_pynput_hotkey_default():
    result = agent.to_pynput_hotkey({"mods": ["ctrl", "alt", _META], "key": "t"})
    assert result == "<ctrl>+<alt>+<cmd>+t"


def test_to_pynput_hotkey_meta_is_os_native():
    # Calisilan OS'un yerel meta adi <cmd> tokenina cevrilir.
    assert agent.to_pynput_hotkey({"mods": [_META], "key": "a"}) == "<cmd>+a"
    # Baska OS'un meta adi bu OS'ta meta sayilmaz (literal kalir, pynput tanimaz).
    other = "win" if _META != "win" else "super"
    assert agent.to_pynput_hotkey({"mods": [other], "key": "a"}) == f"<{other}>+a"


def test_to_pynput_hotkey_case_and_universal_aliases():
    result = agent.to_pynput_hotkey({"mods": ["Control", "Option"], "key": "K"})
    assert result == "<ctrl>+<alt>+k"


def test_to_display_hotkey_shows_setting_verbatim():
    # "hazir" logu kisayolu ayardaki haliyle gosterir; adlar normalize EDILMEZ.
    assert agent.to_display_hotkey({"mods": ["ctrl", "opt", "win"], "key": "a"}) == "ctrl+opt+win+a"
    assert agent.to_display_hotkey({"mods": ["command"], "key": "K"}) == "command+K"
    assert agent.to_display_hotkey({"mods": ["ctrl", "alt", _META], "key": "a"}) == f"ctrl+alt+{_META}+a"


def test_alt_option_opt_all_map_to_alt():
    # macOS'ta tus "Option"; alt/opt/option uc ad da <alt>'e eslenir (her platformda).
    for name in ("alt", "opt", "option", "Opt", "OPTION"):
        assert agent.to_pynput_hotkey({"mods": [name], "key": "a"}) == "<alt>+a"


def test_clipboard_flow_corrects_and_restores(monkeypatch):
    monkeypatch.setattr(agent, "correct", lambda text, **k: text.replace("gorusme", "görüşme"))
    clip = {"value": "ESKI_PANO"}
    pasted = []

    def read_clip():
        return clip["value"]

    def write_clip(text):
        clip["value"] = text

    def copy_fn():
        clip["value"] = "bugun gorusme"  # seçim panoya kopyalandı

    def paste_fn():
        pasted.append(clip["value"])

    out = agent.correct_clipboard_selection(
        {"use_llm": False, "use_morphology": True, "model": None},
        copy_fn=copy_fn,
        paste_fn=paste_fn,
        read_clip=read_clip,
        write_clip=write_clip,
        sleep=lambda _s: None,
    )
    assert out.original == "bugun gorusme"   # girdi de loglama icin doner
    assert out.corrected == "bugun görüşme"
    assert pasted == ["bugun görüşme"]   # düzeltilmiş metin yapıştırıldı
    assert clip["value"] == "ESKI_PANO"  # pano eski haline döndü


def test_empty_selection_skips_correction(monkeypatch):
    called = []
    monkeypatch.setattr(agent, "correct", lambda *a, **k: called.append(1))

    out = agent.correct_clipboard_selection(
        {"use_llm": False, "use_morphology": True, "model": None},
        copy_fn=lambda: None,
        paste_fn=lambda: None,
        read_clip=lambda: "",
        write_clip=lambda _t: None,
        sleep=lambda _s: None,
    )
    assert out is None
    assert called == []  # boş seçimde motor çağrılmaz
