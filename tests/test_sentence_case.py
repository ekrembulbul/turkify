"""``sentence_case.capitalize_sentences`` ve motor entegrasyonu testleri."""

from turkify import engine
from turkify.sentence_case import capitalize_sentences


def test_capitalizes_after_period():
    assert capitalize_sentences("merhaba. nasilsin") == "merhaba. Nasilsin"


def test_capitalizes_after_question_and_exclamation():
    assert capitalize_sentences("ne? evet! oldu. son") == "ne? Evet! Oldu. Son"


def test_does_not_touch_first_letter_of_text_by_default():
    # Cümle ortasından seçilen parçada ilk harf büyütülmemeli (varsayılan).
    assert capitalize_sentences("merhaba dunya") == "merhaba dunya"
    assert capitalize_sentences("bir cumle.") == "bir cumle."


def test_capitalize_first_capitalizes_text_start():
    assert capitalize_sentences("merhaba dunya", capitalize_first=True) == "Merhaba dunya"
    # İlk harf + cümle başı birlikte.
    assert (
        capitalize_sentences("merhaba. nasilsin", capitalize_first=True)
        == "Merhaba. Nasilsin"
    )


def test_capitalize_first_turkish_and_openers_and_protected():
    assert capitalize_sentences("iyi gunler", capitalize_first=True) == "İyi gunler"
    # Baştaki açılış işareti atlanır.
    assert capitalize_sentences('"merhaba"', capitalize_first=True) == '"Merhaba"'
    # Korunan ilk kelime büyütülmez.
    assert capitalize_sentences("github reposu", [(0, 6)], capitalize_first=True) == "github reposu"


def test_turkish_dotted_i_uppercase():
    # i → İ (Türkçe-duyarlı), I değil.
    assert capitalize_sentences("bitti. iyi gunler") == "bitti. İyi gunler"


def test_turkish_dotless_i_uppercase():
    # ı → I (Türkçe-duyarlı).
    assert capitalize_sentences("oldu. ışık yandı") == "oldu. Işık yandı"


def test_decimal_number_not_split():
    # Nokta + boşluksuz rakam: cümle sonu değil, büyütme yapılmaz.
    assert capitalize_sentences("fiyat 3.14 tl") == "fiyat 3.14 tl"


def test_consecutive_punctuation():
    assert capitalize_sentences("dur... git") == "dur... Git"
    assert capitalize_sentences("oyle mi?! evet") == "oyle mi?! Evet"


def test_ellipsis_char():
    assert capitalize_sentences("bekle… sonra gel") == "bekle… Sonra gel"


def test_skips_opening_quote():
    assert capitalize_sentences('dedi. "merhaba" dedi') == 'dedi. "Merhaba" dedi'


def test_already_uppercase_unchanged():
    assert capitalize_sentences("bitti. Sonra") == "bitti. Sonra"


def test_protected_span_not_capitalized():
    # "bitti. " 7 karakter; 'g' index 7'de. Span onu kapsarsa büyütülmez.
    text = "bitti. github"
    assert capitalize_sentences(text, [(7, 13)]) == "bitti. github"
    # Span yoksa büyütülür.
    assert capitalize_sentences(text) == "bitti. Github"


def test_newline_after_period_capitalizes():
    assert capitalize_sentences("birinci.\nikinci satir") == "birinci.\nİkinci satir"


# --- Motor entegrasyonu (engine.correct) ---
# "art" ve "ben" çevrilebilir karakter (c/g/i/o/s/u) içermez → motor onları
# değiştirmez; böylece yalnızca büyük-harf son-işlemini izole test ederiz.


def test_engine_capitalize_off_by_default():
    assert engine.correct("art. ben", use_morphology=False) == "art. ben"


def test_engine_capitalize_when_enabled():
    assert (
        engine.correct("art. ben", use_morphology=False, capitalize_sentences=True)
        == "art. Ben"
    )


def test_engine_capitalize_first_when_enabled():
    assert (
        engine.correct(
            "ben art",
            use_morphology=False,
            capitalize_sentences=True,
            capitalize_first=True,
        )
        == "Ben art"
    )


def test_engine_capitalize_first_ignored_when_sentences_off():
    # Bağımlı ayar: üst ayar (capitalize_sentences) kapalıyken etkisiz.
    assert (
        engine.correct(
            "ben art",
            use_morphology=False,
            capitalize_sentences=False,
            capitalize_first=True,
        )
        == "ben art"
    )
