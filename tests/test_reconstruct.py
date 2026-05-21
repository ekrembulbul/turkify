import pytest

from turkify.reconstruct import restore_spans


def test_restore_spans_replaces_given_ranges_with_original():
    original = "mail attim"
    corrected = "mail attım"
    assert restore_spans(corrected, original, [(0, 4)]) == "mail attım"


def test_restore_spans_without_spans_returns_corrected():
    assert restore_spans("görüşme", "gorusme", []) == "görüşme"


def test_restore_spans_raises_on_length_mismatch():
    with pytest.raises(ValueError):
        restore_spans("abc", "abcd", [])
