"""Yapılandırma yükleyici testleri."""

import json
import os

import pytest

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
    # POSIX yol biçimini varsayar; Windows'ta str() ters bölü çizgisi verir.
    assert config.config_path() == config.Path("/tmp/ozel/config.json")


@pytest.mark.skipif(os.name == "nt", reason="POSIX-yalniz: Windows'ta PosixPath uretilemez")
def test_config_path_uses_xdg_on_unix(monkeypatch):
    monkeypatch.delenv("TURKIFY_CONFIG", raising=False)
    monkeypatch.setattr(config.os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    assert str(config.config_path()) == "/tmp/xdg/turkify/config.json"


# --- resolve(): tam oncelik (CLI > env > config > varsayilan) ---


def _clear_turkify_env(monkeypatch):
    for _key, (env_name, _conv) in config._ENV_MAP.items():
        monkeypatch.delenv(env_name, raising=False)


def test_resolve_uses_defaults_when_nothing_set(monkeypatch, tmp_path):
    _clear_turkify_env(monkeypatch)
    cfg = config.resolve(path=tmp_path / "yok.json")
    assert cfg["model"] is None
    assert cfg["base_url"] == config.DEFAULTS["base_url"]


def test_resolve_env_overrides_file(monkeypatch, tmp_path):
    _clear_turkify_env(monkeypatch)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "config-model", "timeout": 30}), encoding="utf-8")
    monkeypatch.setenv("TURKIFY_MODEL", "env-model")
    cfg = config.resolve(path=path)
    assert cfg["model"] == "env-model"  # env > config
    assert cfg["timeout"] == 30          # env yoksa config kalir


def test_resolve_cli_overrides_env_and_file(monkeypatch, tmp_path):
    _clear_turkify_env(monkeypatch)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "config-model"}), encoding="utf-8")
    monkeypatch.setenv("TURKIFY_MODEL", "env-model")
    cfg = config.resolve({"model": "cli-model"}, path=path)
    assert cfg["model"] == "cli-model"  # CLI > env > config


def test_resolve_none_override_keeps_lower_layer(monkeypatch, tmp_path):
    _clear_turkify_env(monkeypatch)
    monkeypatch.setenv("TURKIFY_MODEL", "env-model")
    cfg = config.resolve({"model": None}, path=tmp_path / "yok.json")
    assert cfg["model"] == "env-model"  # None override yok sayilir


def test_resolve_coerces_env_types(monkeypatch, tmp_path):
    _clear_turkify_env(monkeypatch)
    monkeypatch.setenv("TURKIFY_USE_LLM", "true")
    monkeypatch.setenv("TURKIFY_TIMEOUT", "12.5")
    monkeypatch.setenv("TURKIFY_LLM_OPTIONS", '{"max_tokens": 512}')
    cfg = config.resolve(path=tmp_path / "yok.json")
    assert cfg["use_llm"] is True
    assert cfg["timeout"] == 12.5
    assert cfg["llm_options"] == {"max_tokens": 512}


def test_resolve_invalid_env_warns_and_keeps_lower(monkeypatch, tmp_path, caplog):
    import logging

    _clear_turkify_env(monkeypatch)
    monkeypatch.setenv("TURKIFY_TIMEOUT", "abc")  # float'a cevrilemez
    with caplog.at_level(logging.WARNING, logger="turkify"):
        cfg = config.resolve(path=tmp_path / "yok.json")
    assert cfg["timeout"] == config.DEFAULTS["timeout"]  # gecersiz env yok sayilir
    assert any("TURKIFY_TIMEOUT" in r.getMessage() for r in caplog.records)
