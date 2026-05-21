"""Tier 3 entegrasyonu — çoklu geçerli adayda LLM seçimi (mock'lu).

Tier 3 yalnızca Tier 1 **geçersiz** bir kelime ürettiğinde ve birden fazla
geçerli alternatif olduğunda devreye girer (hassasiyet önceliği politikası).
Bu senaryoyu kurmak için morfoloji mock'lanır: Tier 1 çıktısı geçersiz,
iki aday geçerli sayılır.
"""

import pytest

from turkify import engine, morphology, reranker

# "sis" kelimesinin adaylari arasinda Tier 1 ciktisi ("sis") gecersiz,
# "şiş" ve "sış" gecerli sayilir -> belirsiz -> Tier 3.
_VALID = {"şiş", "sış"}


@pytest.fixture
def ambiguous_morphology(monkeypatch):
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in _VALID)


def test_llm_resolves_ambiguous_word_when_enabled(ambiguous_morphology, monkeypatch):
    monkeypatch.setattr(reranker, "choose", lambda *a, **k: "şiş")
    assert engine.correct("sis", use_llm=True) == "şiş"


def test_ambiguous_word_keeps_tier1_when_llm_disabled(ambiguous_morphology, monkeypatch):
    def fail(*a, **k):
        raise AssertionError("use_llm=False iken LLM cagrilmamali")

    monkeypatch.setattr(reranker, "choose", fail)
    assert engine.correct("sis", use_llm=False) == "sis"


def test_ambiguous_word_keeps_tier1_when_llm_returns_none(ambiguous_morphology, monkeypatch):
    monkeypatch.setattr(reranker, "choose", lambda *a, **k: None)
    assert engine.correct("sis", use_llm=True) == "sis"


def test_tier3_call_is_logged(ambiguous_morphology, monkeypatch, caplog):
    import logging

    monkeypatch.setattr(reranker, "choose", lambda *a, **k: "şiş")
    with caplog.at_level(logging.INFO, logger="turkify"):
        engine.correct("sis", use_llm=True)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "[Tier3]" in messages and "LLM secti" in messages


def test_valid_tier1_word_is_never_overridden_by_llm(monkeypatch):
    # Tier 1 "sana" gecerli; baska gecerli aday ("şana") olsa bile LLM cagrilmaz.
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in {"sana", "şana"})

    def fail(*a, **k):
        raise AssertionError("gecerli Tier 1 ciktisi icin LLM cagrilmamali")

    monkeypatch.setattr(reranker, "choose", fail)
    assert engine.correct("sana", use_llm=True) == "sana"
