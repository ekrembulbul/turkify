"""Yapılandırma yükleyici testleri."""

import json

from turkify import config


def test_missing_file_returns_defaults(tmp_path):
    cfg = config.load(tmp_path / "yok.json")
    assert cfg == config.DEFAULTS
    assert cfg["model"] is None  # model varsayilani None (Tier 3 icin zorunlu)


def test_file_overrides_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "qwen3.5:9b", "use_llm": True}), encoding="utf-8")
    cfg = config.load(path)
    assert cfg["model"] == "qwen3.5:9b"
    assert cfg["use_llm"] is True
    assert cfg["use_morphology"] is True  # belirtilmeyen varsayilanda kalir


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"bilinmeyen": 1, "model": "x"}), encoding="utf-8")
    cfg = config.load(path)
    assert "bilinmeyen" not in cfg
    assert cfg["model"] == "x"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ bozuk json", encoding="utf-8")
    assert config.load(path) == config.DEFAULTS


def test_corrupt_file_logs_warning(tmp_path, caplog):
    import logging

    # // yorumlu JSON gecersizdir; sessizce yutulmamali, uyari verilmeli.
    path = tmp_path / "config.json"
    path.write_text('{\n  "model": "x"  // yorum\n}', encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="turkify"):
        cfg = config.load(path)
    assert cfg == config.DEFAULTS
    assert any("gecersiz JSON" in r.getMessage() for r in caplog.records)


def test_config_path_respects_env(monkeypatch):
    monkeypatch.setenv("TURKIFY_CONFIG", "/tmp/ozel/config.json")
    assert str(config.config_path()) == "/tmp/ozel/config.json"


def test_config_path_uses_xdg_on_unix(monkeypatch):
    monkeypatch.delenv("TURKIFY_CONFIG", raising=False)
    monkeypatch.setattr(config.os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    assert str(config.config_path()) == "/tmp/xdg/turkify/config.json"
