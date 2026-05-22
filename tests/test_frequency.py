"""Frekans sözlüğü ve frekans-güdümlü escalation testleri.

Birim testleri vendor edilmiş gerçek listeyi kullanır (repoda mevcut).
Escalation testi morfolojiyi mock'lar; böylece zeyrek'ten bağımsız ve
deterministiktir, ama gerçek frekans verisini kullanır.
"""

from turkify import engine, frequency, morphology


def test_known_word_has_frequency():
    assert frequency.get_frequency("sana") > 0


def test_frequent_word_beats_rare_variant():
    assert frequency.get_frequency("sana") > frequency.get_frequency("şana")
    assert frequency.get_frequency("çiş") > frequency.get_frequency("çis")


def test_unknown_word_is_zero():
    assert frequency.get_frequency("qwxyzk") == 0


def test_empty_word_is_zero():
    assert frequency.get_frequency("") == 0


def test_lookup_is_turkish_case_insensitive():
    assert frequency.get_frequency("SANA") == frequency.get_frequency("sana")


def test_frequency_data_is_available():
    assert frequency.available() is True


def test_dominant_frequency_resolves_ambiguity_without_llm(monkeypatch):
    # 'cis' adaylari: cis(0), çis(0), cıs(0), çiş(986...) -> çiş baskin.
    # use_llm=False olmasina ragmen frekans deterministik olarak 'çiş' secer.
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(
        morphology, "is_valid_word", lambda w: w in {"çiş", "çis", "cıs"}
    )
    assert engine.correct("cis") == "çiş"


def test_close_pair_is_not_dominant():
    # "tür"/"tur" orani ~6.3 (<10) -> yakin -> baskin degil, LLM'e birakilir.
    assert engine._dominant_by_frequency(["tür", "tur"]) is None


def test_overwhelming_pair_is_dominant():
    # "böyle"/"boyle" orani ~194 -> ezici baskin -> deterministik secilir.
    # (boyle korpusta ASCII-yazim olarak gecse de oran cok yuksek.)
    assert engine._dominant_by_frequency(["böyle", "boyle"]) == "böyle"


def test_rare_runnerup_is_dominant():
    # "şana"(0) nadir -> "sana" baskin secilir.
    assert engine._dominant_by_frequency(["sana", "şana"]) == "sana"


def test_ascii_dominant_with_real_diacritic_sibling_is_not_trusted():
    # "simdi"(5121) korpusta "şimdi"(307)'den sik gorunse de (ASCII kirliligi),
    # sapkali rakip gercek/var oldugu icin baskinligina guvenilmez -> bağlama birak.
    assert engine._dominant_by_frequency(["simdi", "şimdi"]) is None


def test_dominant_frequency_keeps_common_word_unchanged(monkeypatch):
    # 'sana' >> 'şana' -> 'sana' korunur (frekans baskinligi).
    monkeypatch.setattr(morphology, "available", lambda: True)
    monkeypatch.setattr(
        morphology, "is_valid_word", lambda w: w in {"sana", "şana"}
    )
    assert engine.correct("sana") == "sana"
