from turkify.protect import (
    load_protected_words,
    protected_spans,
    tr_lower,
)

PROTECTED = frozenset({"mail", "framework"})


def _protected_substrings(text: str, words=PROTECTED) -> list[str]:
    return [text[s:e] for s, e in protected_spans(text, words)]


def test_tr_lower_handles_dotless_and_dotted_i():
    assert tr_lower("IŞIK") == "ışık"
    assert tr_lower("İSTANBUL") == "istanbul"


def test_url_chunk_is_protected_whole():
    text = "siteye https://Example.com/Path bak"
    assert _protected_substrings(text) == ["https://Example.com/Path"]


def test_email_chunk_is_protected_whole():
    text = "bana Ekrem@Site.com yaz"
    assert _protected_substrings(text) == ["Ekrem@Site.com"]


def test_chunk_with_digit_is_protected():
    text = "surum v2 cikti"
    assert _protected_substrings(text) == ["v2"]


def test_code_chunk_with_underscore_is_protected():
    text = "degisken user_name olsun"
    assert _protected_substrings(text) == ["user_name"]


def test_protected_word_is_matched_case_insensitively():
    text = "Mail attim"
    assert _protected_substrings(text) == ["Mail"]


def test_word_already_having_turkish_char_is_protected():
    text = "görüşme yapildi"
    assert "görüşme" in _protected_substrings(text)


def test_ordinary_word_is_not_protected():
    assert _protected_substrings("gorusme") == []


def test_load_protected_words_without_path_is_empty():
    # Paketle gelen ornek OTOMATIK yuklenmez (bkz. ADR 0008).
    assert load_protected_words() == frozenset()


def test_load_protected_words_reads_given_file(tmp_path):
    user_file = tmp_path / "protected_words.txt"
    user_file.write_text("# kullanici\nKubernetes\nDTO\n", encoding="utf-8")
    words = load_protected_words(user_file)
    assert words == frozenset({"kubernetes", "dto"})  # tr_lower normalize, yorum atlanir


def test_load_protected_words_missing_file_is_empty(tmp_path):
    assert load_protected_words(tmp_path / "yok.txt") == frozenset()
