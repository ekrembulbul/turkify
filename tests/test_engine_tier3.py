"""Tier 3 entegrasyonu — belirsiz kelimelerin TEK batch LLM isteğiyle çözümü.

Tier 3 yalnızca birden fazla geçerli aday frekansça baskın değilken devreye
girer. Senaryoyu kurmak için morfoloji mock'lanır ve frekans nötrlenir; LLM
çağrısı (``reranker.choose_batch``) mock'lanır.
"""

import pytest

from turkify import engine, frequency, morphology, reranker

# "sis" adaylari arasinda "şiş" ve "sış" gecerli sayilir; frekans notr -> belirsiz.
_VALID = {"şiş", "sış"}

# Model zorunlu oldugundan, Tier 3'un calismasi icin testlerde bir model verilir.
_MODEL = "test:1b"


@pytest.fixture
def ambiguous_morphology(monkeypatch):
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in _VALID)
    monkeypatch.setattr(frequency, "get_frequency", lambda w: 0)


def test_llm_resolves_ambiguous_word_when_enabled(ambiguous_morphology, monkeypatch):
    monkeypatch.setattr(reranker, "choose_batch", lambda sentence, asks, **k: ("şiş",))
    assert engine.correct("sis", use_llm=True, model=_MODEL) == "şiş"


def test_ambiguous_word_keeps_tier1_when_llm_disabled(ambiguous_morphology, monkeypatch):
    def fail(*a, **k):
        raise AssertionError("use_llm=False iken LLM cagrilmamali")

    monkeypatch.setattr(reranker, "choose_batch", fail)
    assert engine.correct("sis", use_llm=False, model=_MODEL) == "sis"


def test_ambiguous_word_keeps_tier1_when_llm_returns_none(ambiguous_morphology, monkeypatch):
    monkeypatch.setattr(reranker, "choose_batch", lambda sentence, asks, **k: (None,))
    assert engine.correct("sis", use_llm=True, model=_MODEL) == "sis"


def test_missing_model_skips_tier3(ambiguous_morphology, monkeypatch):
    # Model verilmezse (config'te yok) use_llm=True olsa bile Tier 3 calismaz.
    def fail(*a, **k):
        raise AssertionError("model yokken LLM cagrilmamali")

    monkeypatch.setattr(reranker, "choose_batch", fail)
    monkeypatch.setattr(reranker, "DEFAULT_MODEL", None)
    assert engine.correct("sis", use_llm=True, model=None) == "sis"


def test_model_is_forwarded_to_reranker(ambiguous_morphology, monkeypatch):
    captured = {}

    def fake_batch(sentence, asks, *, model=None, **kwargs):
        captured["model"] = model
        return tuple(cands[0] for _word, cands in asks)

    monkeypatch.setattr(reranker, "choose_batch", fake_batch)
    engine.correct("sis", use_llm=True, model="deneme-model:1b")
    assert captured["model"] == "deneme-model:1b"


def test_tier3_call_is_logged(ambiguous_morphology, monkeypatch, caplog):
    import logging

    monkeypatch.setattr(reranker, "choose_batch", lambda sentence, asks, **k: ("şiş",))
    with caplog.at_level(logging.INFO, logger="turkify"):
        engine.correct("sis", use_llm=True, model=_MODEL)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "[Tier3]" in messages and "LLM secti" in messages


def test_batch_resolves_multiple_words_in_one_call(monkeypatch):
    # Iki belirsiz kelime tek batch cagrisinda cozulur.
    valid = {"şiş", "sış", "asmak", "aşmak"}
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in valid)
    monkeypatch.setattr(frequency, "get_frequency", lambda w: 0)

    calls = {"count": 0}

    def fake_batch(sentence, asks, **kwargs):
        calls["count"] += 1
        # her soru icin dogru adayi sec
        choice_map = {"sis": "şiş", "asmak": "aşmak"}
        return tuple(choice_map.get(word) for word, _cands in asks)

    monkeypatch.setattr(reranker, "choose_batch", fake_batch)
    out = engine.correct("sis asmak", use_llm=True, model=_MODEL)
    assert out == "şiş aşmak"
    assert calls["count"] == 1  # tek istek


def test_llm_context_corrects_nonambiguous_keeps_ambiguous_ascii(monkeypatch):
    # "citcit" -> tek gecerli aday "çıtçıt" (belirsiz degil) -> baglamda duzeltilir.
    # "sis"    -> belirsiz (şiş/sış)                          -> baglamda ASCII kalir.
    valid = {"çıtçıt", "şiş", "sış"}
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in valid)
    monkeypatch.setattr(frequency, "get_frequency", lambda w: 0)

    captured = {}

    def fake_batch(sentence, asks, **kwargs):
        captured["sentence"] = sentence
        return tuple(None for _ in asks)

    monkeypatch.setattr(reranker, "choose_batch", fake_batch)
    engine.correct("citcit sis", use_llm=True, model=_MODEL)
    assert "çıtçıt" in captured["sentence"]  # belirsiz olmayan duzeltildi
    assert "sis" in captured["sentence"]      # belirsiz olan ASCII kaldi


def test_marked_context_numbers_each_ambiguous_occurrence(monkeypatch):
    # Ayni kelime ("sor") iki kez gecince her geçiş ayri [numara] ile isaretlenir.
    valid = {"sor", "şor"}
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in valid)
    monkeypatch.setattr(frequency, "get_frequency", lambda w: 0)

    captured = {}

    def fake_batch(sentence, asks, **kwargs):
        captured["sentence"] = sentence
        captured["asks"] = asks
        return tuple(None for _ in asks)

    monkeypatch.setattr(reranker, "choose_batch", fake_batch)
    engine.correct("sor ve tekrar sor", use_llm=True, model=_MODEL)
    assert "sor[1]" in captured["sentence"]
    assert "sor[2]" in captured["sentence"]
    assert len(captured["asks"]) == 2


def test_dominant_frequency_resolves_without_llm(monkeypatch):
    # "sana" >> "şana" (gercek frekans) -> baskin frekans deterministik secer.
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in {"sana", "şana"})

    def fail(*a, **k):
        raise AssertionError("baskin frekansta LLM cagrilmamali")

    monkeypatch.setattr(reranker, "choose_batch", fail)
    assert engine.correct("sana", use_llm=True) == "sana"
