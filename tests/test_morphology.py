"""Gerçek zeyrek morfoloji motoru testleri.

zeyrek kurulu değilse bu testler atlanır (Tier 2 opsiyoneldir).
"""

import pytest

from turkify import morphology

pytestmark = pytest.mark.skipif(
    not morphology.available(), reason="zeyrek kurulu değil (Tier 2 opsiyonel)"
)


def test_valid_turkish_word_is_recognized():
    assert morphology.is_valid_word("görüşme")


def test_inflected_word_is_recognized():
    assert morphology.is_valid_word("kitaplarımızdan")


def test_sentence_initial_capital_is_recognized():
    assert morphology.is_valid_word("Görüşme")


def test_ascii_mangled_word_is_invalid():
    assert not morphology.is_valid_word("gorusme")
    assert not morphology.is_valid_word("yapacagiz")


def test_nonword_is_invalid():
    assert not morphology.is_valid_word("asdfgh")


def test_empty_word_is_invalid():
    assert not morphology.is_valid_word("")
