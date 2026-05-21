from turkify import correct


def test_correct_definition_of_done_example():
    assert correct("bugun gorusme yapacagiz") == "bugün görüşme yapacağız"


def test_correct_preserves_punctuation_and_case():
    assert correct("Merhaba, bugun gorusme yapacagiz.") == (
        "Merhaba, bugün görüşme yapacağız."
    )


def test_correct_does_not_touch_protected_words():
    assert correct("mail attim framework kullandim") == (
        "mail attım framework kullandım"
    )


def test_correct_does_not_touch_url():
    text = "detay icin https://example.com/path adresine bak"
    out = correct(text)
    assert "https://example.com/path" in out
    assert out.startswith("detay için ")


def test_correct_does_not_touch_email():
    out = correct("bana mate@site.com yaz")
    assert "mate@site.com" in out


def test_correct_preserves_newlines_and_spacing():
    text = "ilk satir\nikinci  satir"
    out = correct(text)
    assert out == "ilk satır\nikinci  satır"


def test_correct_empty_string():
    assert correct("") == ""


def test_correct_use_llm_flag_is_noop_in_phase1():
    text = "bugun gorusme yapacagiz"
    assert correct(text, use_llm=True) == correct(text, use_llm=False)
