from turkify.deasciifier import deasciify


def test_deasciify_restores_basic_sentence():
    assert deasciify("bugun gorusme yapacagiz") == "bugün görüşme yapacağız"


def test_deasciify_preserves_length():
    text = "Merhaba, bugun gorusme yapacagiz."
    assert len(deasciify(text)) == len(text)


def test_deasciify_handles_turkish_dotted_capital_i():
    assert deasciify("Istanbul'a gidecegim") == "İstanbul'a gideceğim"


def test_deasciify_empty_string():
    assert deasciify("") == ""
