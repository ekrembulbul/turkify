"""CLI argüman ayrıştırma testleri (``_parse_settings_args``)."""

import pytest

from turkify import __main__ as cli


def test_value_options_parsed():
    overrides, remaining = cli._parse_settings_args(
        ["--model", "qwen", "--base-url", "http://x/v1", "--timeout", "90", "dosya.txt"]
    )
    assert overrides["model"] == "qwen"
    assert overrides["base_url"] == "http://x/v1"
    assert overrides["timeout"] == 90.0
    assert remaining == ["dosya.txt"]  # deger-opsiyonlari cikarildi, konumsal kaldi


def test_unset_options_are_none():
    overrides, _ = cli._parse_settings_args([])
    assert overrides["model"] is None
    assert overrides["use_llm"] is None
    assert overrides["use_morphology"] is None
    assert overrides["llm_options"] is None


def test_llm_tristate_flags():
    assert cli._parse_settings_args(["--llm"])[0]["use_llm"] is True
    assert cli._parse_settings_args(["--no-llm"])[0]["use_llm"] is False
    assert cli._parse_settings_args([])[0]["use_llm"] is None


def test_no_morphology_flag():
    assert cli._parse_settings_args(["--no-morphology"])[0]["use_morphology"] is False


def test_llm_options_parsed_as_json():
    overrides, _ = cli._parse_settings_args(["--llm-options", '{"max_tokens": 512}'])
    assert overrides["llm_options"] == {"max_tokens": 512}


def test_invalid_timeout_raises():
    with pytest.raises(ValueError):
        cli._parse_settings_args(["--timeout", "abc"])


def test_invalid_llm_options_raises():
    import json

    with pytest.raises(json.JSONDecodeError):
        cli._parse_settings_args(["--llm-options", "{bozuk"])
