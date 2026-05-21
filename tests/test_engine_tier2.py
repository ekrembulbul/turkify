"""Gerçek zeyrek ile uçtan uca Tier 2 entegrasyon testleri.

Tier 1 (Yüret) geçersiz bir kelime üretip Tier 2'nin tek geçerli adaya
düzelttiği gerçek örnekler. zeyrek yoksa atlanır.
"""

import pytest

from turkify import correct, morphology

pytestmark = pytest.mark.skipif(
    not morphology.available(), reason="zeyrek kurulu değil (Tier 2 opsiyonel)"
)


@pytest.mark.parametrize(
    "ascii_input,expected",
    [
        ("citcit", "çıtçıt"),
        ("hosmerim", "höşmerim"),
        ("surcus", "sürçüş"),
    ],
)
def test_tier2_recovers_words_tier1_gets_wrong(ascii_input, expected):
    # Bu kelimelerde Tier 1 morfolojik olarak gecersiz bir cikti uretir;
    # Tier 2 tek gecerli adaya gecer.
    assert correct(ascii_input) == expected


def test_tier2_keeps_valid_tier1_output_unchanged():
    # Tier 1 zaten dogru ve gecerli -> Tier 2 dokunmaz.
    assert correct("bugun gorusme yapacagiz") == "bugün görüşme yapacağız"


def test_tier2_does_not_change_output_for_protected_url():
    out = correct("detay https://example.com/path icin")
    assert "https://example.com/path" in out
