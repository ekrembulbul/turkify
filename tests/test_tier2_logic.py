"""Tier 2 escalation mantığı — zeyrek'ten bağımsız, kontrollü doğrulayıcı ile.

``morphology.is_valid_word`` ve ``morphology.available`` monkeypatch edilerek
escalation kararları deterministik biçimde test edilir; gerçek morfoloji
motoruna bağımlı kalınmaz.
"""

import pytest

from turkify import engine, frequency, morphology


@pytest.fixture
def fake_morphology(monkeypatch):
    """Belirli kelimeleri 'geçerli' sayan sahte morfoloji + nötr frekans kurar.

    Frekans nötrlenir (tümü 0) ki bu testler yalnızca morfoloji escalation
    mantığını izole etsin; frekans-baskınlığı ayrı testlerde sınanır.
    """

    def install(valid_words):
        valid = set(valid_words)
        monkeypatch.setattr(morphology, "available", lambda: True)
        monkeypatch.setattr(morphology, "is_valid_word", lambda w: w in valid)
        monkeypatch.setattr(frequency, "get_frequency", lambda w: 0)

    return install


def _resolve(ascii_word, tier1_word, sentence="", *, use_llm=False):
    return engine._resolve_word(
        ascii_word, tier1_word, sentence, use_morphology=True, use_llm=use_llm
    )


def test_tier1_valid_word_is_kept(fake_morphology):
    fake_morphology({"görüşme"})
    assert _resolve("gorusme", "görüşme") == "görüşme"


def test_tier1_invalid_word_switches_to_unique_valid_candidate(fake_morphology):
    # Tier 1 "sırıl" gecersiz; tek gecerli aday "şırıl" -> ona gecilir.
    fake_morphology({"şırıl"})
    assert _resolve("siril", "sırıl") == "şırıl"


def test_multiple_valid_candidates_keep_tier1_without_llm(fake_morphology):
    # Hem "şiş" hem "sis" gecerli, LLM kapali -> belirsiz -> Tier 1 ("sis") korunur.
    fake_morphology({"şiş", "sis"})
    assert _resolve("sis", "sis") == "sis"


def test_no_valid_candidate_keeps_tier1(fake_morphology):
    fake_morphology(set())
    assert _resolve("sudcu", "sudcu") == "sudcu"


def test_tier2_decision_is_logged(fake_morphology, caplog):
    import logging

    fake_morphology({"şırıl"})
    with caplog.at_level(logging.INFO, logger="turkify"):
        _resolve("siril", "sırıl")
    assert any("[Tier2]" in record.getMessage() for record in caplog.records)


def test_correct_applies_tier2_in_sentence(fake_morphology):
    fake_morphology({"şırıl"})
    # "siril akan su" -> Tier1 "sırıl" gecersiz, "şırıl" gecerli; digerleri dokunulmaz.
    out = engine.correct("siril akan su")
    assert out.startswith("şırıl ")


def test_correct_skips_protected_words_in_tier2(fake_morphology):
    # "mail" korumali; gecerli kelime sayilmasa bile Tier 2 ona dokunmaz.
    fake_morphology(set())
    assert engine.correct("mail") == "mail"


def test_use_morphology_false_disables_tier2(fake_morphology):
    fake_morphology({"şırıl"})
    # Tier 2 kapali -> Tier 1 ciktisi ("sırıl") aynen kalir.
    assert engine.correct("siril", use_morphology=False) == "sırıl"
