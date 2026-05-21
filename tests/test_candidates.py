from turkify.candidates import generate_candidates, is_convertible


def test_is_convertible_detects_ascii_and_turkish_forms():
    assert is_convertible("c") and is_convertible("ç")
    assert is_convertible("I") and is_convertible("İ")
    assert not is_convertible("a")
    assert not is_convertible("k")


def test_generate_candidates_without_convertible_returns_word_itself():
    assert generate_candidates("kalem") == ["kalem"]


def test_generate_candidates_single_convertible_has_two_variants():
    # "ko": yalnizca 'o' cevrilebilir -> 2 varyant.
    assert set(generate_candidates("ko")) == {"ko", "kö"}


def test_generate_candidates_count_is_two_to_the_k():
    # "cis": c ve s çevrilebilir, i çevrilebilir -> 3 konum -> 2^3 = 8
    assert len(generate_candidates("cis")) == 8


def test_generate_candidates_preserves_case_skeleton():
    cands = generate_candidates("Ko")
    assert set(cands) == {"Ko", "Kö"}


def test_generate_candidates_respects_max_convertible_limit():
    # "susus": 5 cevrilebilir karakter, sinir 3 -> bos liste (aday patlamasi onlenir)
    assert generate_candidates("susus", max_convertible=3) == []


def test_generate_candidates_includes_original_ascii_form():
    assert "gorusme" in generate_candidates("gorusme")
    assert "görüşme" in generate_candidates("gorusme")
