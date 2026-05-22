"""Kısayol ajanı testleri — OS/kütüphane çağrıları mock'lanır (pynput/pyperclip gerekmez)."""

from turkify import agent


def test_to_pynput_hotkey_default():
    result = agent.to_pynput_hotkey({"mods": ["ctrl", "alt", "cmd"], "key": "t"})
    assert result == "<ctrl>+<alt>+<cmd>+t"


def test_to_pynput_hotkey_aliases_and_case():
    result = agent.to_pynput_hotkey({"mods": ["command", "option"], "key": "K"})
    assert result == "<cmd>+<alt>+k"


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
    assert out == "bugun görüşme"
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
