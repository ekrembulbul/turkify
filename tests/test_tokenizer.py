from turkify.tokenizer import Token, tokenize


def test_tokenize_is_lossless_when_joined():
    text = "Merhaba, bugun  gorusme yapacagiz."
    assert "".join(t.text for t in tokenize(text)) == text


def test_tokenize_separates_words_and_separators():
    tokens = tokenize("ab cd")
    assert tokens == [
        Token("ab", 0, 2, is_word=True),
        Token(" ", 2, 3, is_word=False),
        Token("cd", 3, 5, is_word=True),
    ]


def test_tokenize_keeps_leading_separator():
    tokens = tokenize("  ab")
    assert tokens[0] == Token("  ", 0, 2, is_word=False)
    assert tokens[1] == Token("ab", 2, 4, is_word=True)


def test_tokenize_underscore_is_separator_not_word():
    tokens = tokenize("user_name")
    assert [t.text for t in tokens] == ["user", "_", "name"]


def test_tokenize_turkish_letters_are_word_chars():
    tokens = tokenize("görüşme")
    assert tokens == [Token("görüşme", 0, 7, is_word=True)]


def test_tokenize_empty_string_returns_no_tokens():
    assert tokenize("") == []
